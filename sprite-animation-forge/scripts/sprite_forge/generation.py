"""Codex-backed generation workflows: ``generate`` (action units) and ``reference generate/select`` (Case B).

Public API (``cd`` = character directory ``<root>/<cid>``)
----------------------------------------------------------
``codex_lock(cd)``  process-wide serialisation of Codex calls (ADR-009): a blocking exclusive ``flock`` on
    ``<root>/.codex.lock`` (``cd.parent``). Every Codex call (generate, reference generate, identity analyze)
    holds it for the whole call, so a second CLI process waits (FIFO is not guaranteed) instead of running.
``record_usage(cd, usage)``  adds one call and its token usage to ``manifest.usage``.
``generate_unit(cd, plan, profile, action, direction, extra, recovery, timeout, provider=None,
                video_provider=None, on_progress=None) -> {attempt, unit, status}``
    allocates ``<unit>/attempts/NNN``, writes ``prompt.txt``, calls the provider. ``method=video`` actions go through
    ``video_provider`` instead (clip -> ``raw.mp4`` + ``video-meta.json``, then a ``raw.png`` sheet made by
    ``video_sprite`` so the normal pipeline processes it; no Codex lock held while the clip renders). A failed generation
    raises ``ForgeError(error_code, exit_code=2, extra={attempt, unit, status})``.
``generate_reference(cd, description, count, timeout, provider=None) -> {attempts: [{attempt, status, error_code?}]}``
``select_reference(cd, attempt) -> {reference, selected_attempt, bg_removed}``

Notes on ambiguous spots
------------------------
* The direction reference (``Image 2``) is ONE adopted frame (``frames/000.png``) of the representative unit,
  enlarged and composited on the key colour (``direction_reference_image``); a whole sheet dilutes the facing lock.
  If that unit was not accepted yet: ``no_direction_reference`` (exit 3).
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
import shutil
import tempfile
from pathlib import Path

from PIL import Image

from . import manifest as mf
from .errors import EXIT_PRECONDITION, EXIT_PROVIDER, ForgeError
from .fsutil import allocate_attempt, atomic_write_json, atomic_write_png, atomic_write_text, file_lock, sha256_file
from .plan import resolve_unit
from .prompt import PromptResult, build_canonical_prompt, build_prompt, build_video_prompt
from .providers import CodexCliProvider, GenerationRequest, VideoRequest
from .providers.video_factory import make_video_provider
from . import video_sprite
from .workflow import _attempt_entry, _kind, _open_image, write_character

MAX_REFERENCE_COUNT = 4
VIDEO_MIN_TIMEOUT = 600  # a clip takes minutes; the image default (300 s) is too short


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


def direction_reference_image(cd, unit: str, key_hex: str, out_dir, index: int = 0, target: int = 512) -> Path:
    """The direction reference (``Image 2``): ONE adopted frame of the representative unit, enlarged to ~``target`` px
    and placed on the key colour like the keyed character. A multi-pose sheet dilutes the facing lock (sprite-gen's
    measurement), and the raw sheet is not a good reference anyway. Raises ``no_direction_reference`` (exit 3)
    when the unit has no adopted frames."""
    frames = sorted((Path(cd) / unit / "frames").glob("*.png"))
    if not frames:
        raise ForgeError("no_direction_reference", f"accept {unit} first (its adopted frame is the direction reference)",
                         EXIT_PRECONDITION)
    img = Image.open(frames[min(index, len(frames) - 1)]).convert("RGBA")
    factor = max(1, target // max(img.size))
    if factor > 1:
        img = img.resize((img.width * factor, img.height * factor), Image.NEAREST)
    key = tuple(int(key_hex[i:i + 2], 16) for i in (1, 3, 5))
    out = Image.new("RGB", img.size, key)
    out.paste(img, mask=img.getchannel("A"))
    path = Path(out_dir) / "direction-reference.png"
    out.save(path, format="PNG", optimize=False, compress_level=6)
    return path


def _run_attempt(cd, provider, adir: Path, pr: PromptResult, refs: list[Path], timeout: int, labels=None):
    """Write prompt.txt, call the provider, amend generation.json, record usage. ``labels`` maps a reference path
    outside the character directory (a temporary file) to the name recorded in generation.json."""
    cd = Path(cd)
    atomic_write_text(adir / "prompt.txt", pr.text)
    result = provider.generate(GenerationRequest(pr.text, refs, adir, timeout))
    meta = result.meta
    if meta:
        meta["prompt_template_version"] = pr.template_version
        for ref in meta.get("references", []):
            if labels and ref["source"] in labels:
                ref["source"] = labels[ref["source"]]
                continue
            with contextlib.suppress(ValueError):
                ref["source"] = Path(ref["source"]).relative_to(cd).as_posix()
        atomic_write_json(adir / "generation.json", meta)
    record_usage(cd, meta.get("usage"))
    return result


def _fail(result, **extra) -> ForgeError:
    return ForgeError(result.error_code or result.status, result.error_message or "", EXIT_PROVIDER,
                      {**extra, "status": result.status})


def _generate_video_unit(cd, plan, profile, action, unit, extra, timeout, provider, on_progress) -> dict:
    act = plan["actions"][action]
    keyed = cd / "reference" / "character-keyed.png"
    provider = provider or make_video_provider()
    if not provider.check()["configured"]:
        raise ForgeError("method_unavailable", f"{action}: method=video needs a connected video provider "
                         "(see docs/13-video-api-setup.md)", EXIT_PRECONDITION)
    pr = build_video_prompt(plan, profile, action, extra)
    rows, cols = (int(x) for x in act["grid"].split("x"))
    with codex_lock(cd):  # only to allocate the attempt; the clip renders without holding the Codex lock
        attempt, adir = allocate_attempt(cd / unit / "attempts")
        fields = {"provider": provider.name, "recovery": [], "extra": (extra or "").strip() or None}
        mf.update(cd, lambda m: _attempt_entry(m, unit, _kind(plan, action), attempt, generation_status="running", **fields))

    def failed(code, message, status="failed"):
        mf.update(cd, lambda m: _attempt_entry(m, unit, _kind(plan, action), attempt, generation_status=status))
        return ForgeError(code, message, EXIT_PROVIDER, {"attempt": attempt, "unit": unit, "status": status})

    try:
        atomic_write_text(adir / "prompt.txt", pr.text)
        first = video_sprite.prepare_first_frame(keyed, adir / "first-frame.png", plan["key_color"])
        pin_last = action == "idle" or not act["loop"]  # idle / one-shot must come back to the first pose
        res = provider.generate(VideoRequest(pr.text, first, adir / "raw.mp4", last_frame=first if pin_last else None,
                                             timeout_s=max(timeout, VIDEO_MIN_TIMEOUT)), on_progress)
        if res.status != "succeeded":
            raise failed(res.error_code or res.status, res.error_message or "", res.status)
        frames, fps = video_sprite.extract_frames(res.video_path, adir / ".clip-frames")
        sheet, info = video_sprite.build_raw_sheet(frames, act["frames"], rows, cols, plan["key_color"], act["loop"])
    except ForgeError as exc:
        if "attempt" in exc.extra:
            raise
        raise failed(exc.code, exc.message) from None
    finally:
        shutil.rmtree(adir / ".clip-frames", ignore_errors=True)
    atomic_write_png(sheet, adir / "raw.png")
    meta = {**info, "fps": fps, "pinned_last_frame": pin_last, "provider": res.meta}
    atomic_write_json(adir / "video-meta.json", meta)
    atomic_write_json(adir / "generation.json", {
        "provider": provider.name, "method": "video", "prompt_template_version": pr.template_version,
        "references": [{"role": "character", "source": "reference/character-keyed.png"}],
        "raw": {"file": "raw.png", "width": sheet.width, "height": sheet.height, "mode": sheet.mode,
                "sha256": sha256_file(adir / "raw.png")},
        "video": {"file": "raw.mp4", "sha256": sha256_file(adir / "raw.mp4"), "first_frame": "first-frame.png", **res.meta}})
    mf.update(cd, lambda m: _attempt_entry(m, unit, _kind(plan, action), attempt, generation_status="succeeded"))
    return {"attempt": attempt, "unit": unit, "status": "succeeded"}


def generate_unit(cd, plan, profile, action, direction=None, extra=None, recovery=(), timeout=300,
                  provider=None, video_provider=None, on_progress=None) -> dict:
    cd = Path(cd)
    m = mf.load(cd)
    unit, direction, _ = resolve_unit(plan, action, direction)
    keyed = cd / "reference" / "character-keyed.png"
    if m["reference"] is None or not keyed.exists():
        raise ForgeError("no_reference", "run reference import (or reference generate/select) first", EXIT_PRECONDITION)
    if profile is None:
        raise ForgeError("no_profile", "run identity analyze first", EXIT_PRECONDITION)
    if plan["actions"][action].get("method", "grid") == "video":
        return _generate_video_unit(cd, plan, profile, action, unit, extra, timeout, video_provider, on_progress)
    pr = build_prompt(plan, profile, action, direction, extra, recovery)
    provider = provider or CodexCliProvider()
    with tempfile.TemporaryDirectory(prefix="sprite-forge-ref-") as tmp:
        refs, labels = [], {}
        for role in pr.references_needed:
            if role == "character":
                refs.append(keyed)
                continue
            ref_unit = role.split(":", 1)[1]
            path = direction_reference_image(cd, ref_unit, plan["key_color"], tmp)
            refs.append(path)
            labels[str(path)] = f"{ref_unit}/frames/000.png"
        with codex_lock(cd):
            attempt, adir = allocate_attempt(cd / unit / "attempts")
            fields = {"provider": provider.name, "recovery": list(dict.fromkeys(recovery or ())),
                      "extra": (extra or "").strip() or None}
            mf.update(cd, lambda m: _attempt_entry(m, unit, _kind(plan, action), attempt,
                                                   generation_status="running", **fields))
            try:
                result = _run_attempt(cd, provider, adir, pr, refs, timeout, labels)
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
