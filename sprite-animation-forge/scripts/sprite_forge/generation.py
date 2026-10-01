"""Codex-backed generation workflows: ``generate`` (action units) and ``reference generate/select`` (Case B).

Public API (``cd`` = character directory ``<root>/<cid>``)
----------------------------------------------------------
``codex_lock(cd)``  process-wide serialisation of Codex calls (ADR-009): a blocking exclusive ``flock`` on
    ``<root>/.codex.lock`` (``cd.parent``). Every Codex call (generate, reference generate, identity analyze)
    holds it for the whole call, so a second CLI process waits (FIFO is not guaranteed) instead of running.
``record_usage(cd, usage)``  adds one call and its token usage to ``manifest.usage``.
``generate_unit(cd, plan, profile, action, direction, extra, recovery, timeout, provider=None) -> {attempt, unit, status}``
    allocates ``<unit>/attempts/NNN``, writes ``prompt.txt``, calls the provider. A failed generation
    raises ``ForgeError(error_code, exit_code=2, extra={attempt, unit, status})``.
``generate_reference(cd, description, count, timeout, provider=None) -> {attempts: [{attempt, status, error_code?}]}``
``select_reference(cd, attempt) -> {reference, selected_attempt, bg_removed}``

Notes on ambiguous spots
------------------------
* The direction reference (``Image 2``) is the representative unit's accepted ``raw.png`` (key-colour
  background like the keyed character), not its processed ``sheet.png``; docs/03 section 10 only says "sheet".
  It is copied unchanged (no <=1024px resize). If that unit was not accepted yet: ``no_direction_reference`` (exit 3).
* ``generation.json`` is written by the provider; right after the call we amend ``prompt_template_version``
  and make ``references[].source`` character-dir relative, then leave it alone (immutable afterwards).
* ``reference generate --count N`` exits 2 only when every attempt failed; otherwise the failed ones are
  listed in ``attempts`` with their ``error_code``.
* ``reference select`` writes ``character.png`` / ``character-keyed.png`` from the attempt's ``raw.png`` and
  sets ``manifest.reference`` (mode ``generated_image``); it never creates ``reference/source.*``.
* No pre-flight ``codex login status`` call: a missing install is detected by the provider
  (``codex_not_installed``); login / feature problems are what ``doctor`` is for.
"""

from __future__ import annotations

import contextlib
import re
from pathlib import Path

from . import manifest as mf
from .errors import EXIT_PRECONDITION, EXIT_PROVIDER, ForgeError
from .fsutil import allocate_attempt, atomic_write_json, atomic_write_text, file_lock, sha256_file
from .plan import resolve_unit
from .prompt import PromptResult, build_canonical_prompt, build_prompt
from .providers import CodexCliProvider, GenerationRequest
from .workflow import _attempt_entry, _kind, _open_image, write_character

MAX_REFERENCE_COUNT = 4


@contextlib.contextmanager
def codex_lock(cd):
    with file_lock(Path(cd).parent / ".codex.lock"):
        yield


def record_usage(cd, usage) -> None:
    usage = usage if isinstance(usage, dict) else {}

    def apply(m):
        u = m.setdefault("usage", {})
        u["codex_calls"] = u.get("codex_calls", 0) + 1
        for key in ("input_tokens", "cached_input_tokens", "output_tokens"):
            u[key] = u.get(key, 0) + int(usage.get(key) or 0)

    mf.update(cd, apply)


def _run_attempt(cd, provider, adir: Path, pr: PromptResult, refs: list[Path], timeout: int):
    """Write prompt.txt, call the provider, amend generation.json, record usage."""
    cd = Path(cd)
    atomic_write_text(adir / "prompt.txt", pr.text)
    result = provider.generate(GenerationRequest(pr.text, refs, adir, timeout))
    meta = result.meta
    if meta:
        meta["prompt_template_version"] = pr.template_version
        for ref in meta.get("references", []):
            with contextlib.suppress(ValueError):
                ref["source"] = Path(ref["source"]).relative_to(cd).as_posix()
        atomic_write_json(adir / "generation.json", meta)
    record_usage(cd, meta.get("usage"))
    return result


def _fail(result, **extra) -> ForgeError:
    return ForgeError(result.error_code or result.status, result.error_message or "", EXIT_PROVIDER,
                      {**extra, "status": result.status})


def generate_unit(cd, plan, profile, action, direction=None, extra=None, recovery=(), timeout=300,
                  provider=None) -> dict:
    cd = Path(cd)
    m = mf.load(cd)
    unit, direction, _ = resolve_unit(plan, action, direction)
    keyed = cd / "reference" / "character-keyed.png"
    if m["reference"] is None or not keyed.exists():
        raise ForgeError("no_reference", "run reference import (or reference generate/select) first", EXIT_PRECONDITION)
    if profile is None:
        raise ForgeError("no_profile", "run identity analyze first", EXIT_PRECONDITION)
    pr = build_prompt(plan, profile, action, direction, extra, recovery)
    refs = []
    for role in pr.references_needed:
        if role == "character":
            refs.append(keyed)
            continue
        src = cd / role.split(":", 1)[1] / "raw.png"
        if not src.exists():
            raise ForgeError("no_direction_reference",
                             f"accept {role.split(':', 1)[1]} first (it is the direction reference)", EXIT_PRECONDITION)
        refs.append(src)

    provider = provider or CodexCliProvider()
    with codex_lock(cd):
        attempt, adir = allocate_attempt(cd / unit / "attempts")
        fields = {"provider": provider.name, "recovery": list(dict.fromkeys(recovery or ())),
                  "extra": (extra or "").strip() or None}
        mf.update(cd, lambda m: _attempt_entry(m, unit, _kind(plan, action), attempt,
                                               generation_status="running", **fields))
        try:
            result = _run_attempt(cd, provider, adir, pr, refs, timeout)
        except Exception:
            mf.update(cd, lambda m: _attempt_entry(m, unit, _kind(plan, action), attempt, generation_status="failed"))
            raise
        mf.update(cd, lambda m: _attempt_entry(m, unit, _kind(plan, action), attempt, generation_status=result.status))
    if result.status != "succeeded":
        raise _fail(result, attempt=attempt, unit=unit)
    return {"attempt": attempt, "unit": unit, "status": result.status}


def generate_reference(cd, description, count=1, timeout=300, provider=None) -> dict:
    cd = Path(cd)
    m = mf.load(cd)
    if not 1 <= count <= MAX_REFERENCE_COUNT:
        raise ForgeError("invalid_params", f"--count must be 1..{MAX_REFERENCE_COUNT}")
    settings = m.get("settings", {})
    pr = build_canonical_prompt(description, art_style=settings.get("art_style", "auto"),
                                view=settings.get("view", "side"))
    provider = provider or CodexCliProvider()
    rows = []
    for _ in range(count):
        with codex_lock(cd):
            attempt, adir = allocate_attempt(cd / "reference" / "attempts")
            result = _run_attempt(cd, provider, adir, pr, [], timeout)
        row = {"attempt": attempt, "status": result.status}
        if result.error_code:
            row["error_code"] = result.error_code
        rows.append(row)
    if not any(r["status"] == "succeeded" for r in rows):
        raise _fail(result, attempts=rows)
    return {"attempts": rows}


def select_reference(cd, attempt) -> dict:
    cd = Path(cd)
    mf.load(cd)
    raw = cd / "reference" / "attempts" / str(attempt) / "raw.png"
    if not re.fullmatch(r"\d{3}", str(attempt)) or not raw.exists():
        raise ForgeError("no_attempt", f"reference attempt {attempt!r} has no raw.png", EXIT_PRECONDITION)
    chroma = write_character(cd / "reference", _open_image(raw))
    rel = f"reference/attempts/{attempt}/raw.png"

    def apply(m):
        m["reference"] = {"mode": "generated_image", "source": rel, "source_sha256": sha256_file(raw),
                          "selected_attempt": attempt}

    mf.update(cd, apply)
    return {"reference": rel, "selected_attempt": attempt, "bg_removed": chroma.mode == "chroma"}
