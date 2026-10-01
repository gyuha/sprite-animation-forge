"""Identity Analyzer: one vision call to Codex with ``--output-schema`` -> ``character-profile.json`` (docs/03 9).

Public API (``cd`` = character directory ``<root>/<cid>``)
----------------------------------------------------------
``load_profile(cd) -> dict | None``
``analyze(cd, timeout=300, force=False, provider=None) -> {profile}``  runs ``codex exec`` (read-only sandbox,
    ``-i reference/character-keyed.png``, ``--output-schema schemas/character-profile.llm.schema.json``,
    ``-o reference/identity-raw.json``), parses and validates the answer, writes ``character-profile.json``
    (``source: "codex-analysis"``, ``edited_by_user: false``) and records usage in the manifest.
``write_empty(cd, force=False) -> {profile}``  all-unknown profile (``source: "empty"``) without calling Codex.

Notes on ambiguous spots
------------------------
* docs do not say what happens to a profile the user edited. Rule used: a profile with
  ``edited_by_user: true`` is never overwritten unless ``force`` (CLI ``--force``): error ``profile_edited`` (exit 1).
  A non-edited profile (including ``source: "empty"``) is replaced.
* ``character-profile.llm.schema.json`` (new file) holds the ``identity`` object only; the colour hex pattern is
  left out of it (structured-output support for ``pattern`` is unconfirmed, docs/03 spike S-6) and is enforced
  afterwards by the strict ``character-profile`` schema. A reply that fails either check is ``invalid_profile``
  (exit 2); nothing is written, ``identity-raw.json`` keeps the raw reply for inspection.
* docs/03 9 says analysis failure may continue with an empty profile; ``generate`` requires a profile file,
  so ``write_empty`` (CLI ``identity analyze --empty``) is the explicit way to continue.
* The Codex process is run directly (not through ``CodexCliProvider.generate``, which is image specific);
  only the binary and ``CODEX_HOME`` come from the provider.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import jsonschema

from . import manifest as mf
from .errors import EXIT_PRECONDITION, EXIT_PROVIDER, ForgeError
from .fsutil import atomic_write_json
from .generation import codex_lock, record_usage
from .providers import CodexCliProvider
from .schemas import SCHEMA_DIR, empty_character_profile, validate

LLM_SCHEMA = SCHEMA_DIR / "character-profile.llm.schema.json"

_INSTRUCTION = """Analyze the attached 2D game character image and fill every field of the JSON schema.
Describe only what is visible. Use short English noun phrases.
Colors must be hex codes sampled from the image. Do not generate images. Do not run shell commands.
"""


def load_profile(cd) -> dict | None:
    path = Path(cd) / "character-profile.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _guard_edited(cd, force: bool) -> None:
    existing = load_profile(cd)
    if existing and existing.get("edited_by_user") and not force:
        raise ForgeError("profile_edited", "character-profile.json was edited by the user; use --force to overwrite")


def _save(cd, identity: dict, source: str) -> dict:
    profile = {"schema_version": 1, "source": source, "edited_by_user": False, "identity": identity}
    validate("character-profile", profile)
    atomic_write_json(Path(cd) / "character-profile.json", profile)
    return profile


def write_empty(cd, force: bool = False) -> dict:
    mf.load(cd)
    _guard_edited(cd, force)
    return {"profile": _save(cd, empty_character_profile()["identity"], "empty")}


def _parse_reply(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")  # tolerate prose or code fences around the object
    try:
        value = json.loads(text[start:end + 1]) if 0 <= start < end else None
    except ValueError:
        value = None
    if not isinstance(value, dict):
        raise ForgeError("invalid_profile", "Codex reply is not a JSON object", EXIT_PROVIDER)
    return value


def analyze(cd, timeout: int = 300, force: bool = False, provider=None) -> dict:
    cd = Path(cd)
    m = mf.load(cd)
    keyed = cd / "reference" / "character-keyed.png"
    if m["reference"] is None or not keyed.exists():
        raise ForgeError("no_reference", "run reference import (or reference generate/select) first", EXIT_PRECONDITION)
    _guard_edited(cd, force)

    provider = provider or CodexCliProvider()
    ref_dir = keyed.parent.resolve()
    raw_path = ref_dir / "identity-raw.json"
    raw_path.unlink(missing_ok=True)
    argv = [provider.codex_bin, "exec", "--json", "--skip-git-repo-check", "-s", "read-only",
            "-C", str(ref_dir), "-c", 'model_reasoning_effort="medium"', "-i", str(ref_dir / keyed.name),
            "--output-schema", str(LLM_SCHEMA), "-o", str(raw_path), "-"]
    with codex_lock(cd):
        try:
            proc = subprocess.run(argv, input=_INSTRUCTION, capture_output=True, text=True, timeout=timeout,
                                  env=provider._env(), errors="replace")
        except FileNotFoundError as exc:
            raise ForgeError("codex_not_installed", f"codex executable not found: {provider.codex_bin} ({exc})",
                             EXIT_PROVIDER) from None
        except subprocess.TimeoutExpired:
            raise ForgeError("timeout", f"codex did not finish within {timeout}s", EXIT_PROVIDER) from None
    usage = next((ev.get("usage") for ev in map(_try_json, reversed(proc.stdout.splitlines()))
                  if ev and ev.get("type") == "turn.completed"), None)
    record_usage(cd, usage)
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-20:])
        raise ForgeError("codex_failed", f"codex exited with {proc.returncode}\n{tail}", EXIT_PROVIDER)

    reply = raw_path.read_text(encoding="utf-8", errors="replace") if raw_path.exists() else ""
    try:
        identity = _parse_reply(reply)
        validate("character-profile.llm", identity)
        return {"profile": _save(cd, identity, "codex-analysis")}
    except jsonschema.ValidationError as exc:
        raise ForgeError("invalid_profile", f"reply does not match the profile schema: {exc.message}",
                         EXIT_PROVIDER) from None


def _try_json(line: str):
    try:
        v = json.loads(line)
    except ValueError:
        return None
    return v if isinstance(v, dict) else None
