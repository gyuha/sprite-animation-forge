"""Vision review of one attempt: a Codex call that looks at the frames and judges motion quality.

Why: the deterministic QC items (qc.py QC-10..13) are proxies; "does this walk read as a natural, loopable
cycle, and is it still the same character" needs eyes. The review is **advisory**: it is saved next to the
attempt and shown in the Studio, it never changes the QC score and is never run automatically.

Public API (``cd`` = character directory)
-----------------------------------------
``contact_sheet(frame_paths, out_path) -> Path``  the frames in one row on a neutral gray background, width limited
    to ``MAX_SHEET_WIDTH`` (frames are only scaled down when the row would be wider).
``instruction(frames, loop, action) -> str``      the prompt text.
``review_attempt(cd, plan, action, direction=None, attempt=None, timeout=300, provider=None) -> {attempt, unit, review}``
    runs ``codex exec`` (read-only sandbox, ``-i contact-sheet.png`` and ``-i reference/character-keyed.png``,
    ``--output-schema schemas/vision-review.llm.schema.json``), validates the answer and writes
    ``<attempt>/vision-review.json`` (+ ``contact-sheet.png``). Errors: ``not_processed`` (exit 3, no frames),
    ``invalid_review`` (exit 2: reply is not JSON / does not match the schema; nothing written).

Notes
-----
* Same plumbing as ``identity.analyze`` (plain ``subprocess.run`` with the provider's binary and ``CODEX_HOME``,
  held under ``codex_lock``), so the review cannot be cancelled while running.
* The reference is attached as the second image so the reviewer can judge identity drift.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import jsonschema
from PIL import Image

from . import manifest as mf
from .errors import EXIT_PRECONDITION, EXIT_PROVIDER, ForgeError
from .fsutil import atomic_write_json
from .generation import codex_lock, record_usage
from .identity import _parse_reply, _try_json
from .plan import resolve_unit
from .providers import CodexCliProvider
from .schemas import SCHEMA_DIR, validate
from .workflow import _attempt_dir, _pick_attempt

LLM_SCHEMA = SCHEMA_DIR / "vision-review.llm.schema.json"
MAX_SHEET_WIDTH = 2048
GAP = 4
BACKGROUND = (128, 128, 128)


def contact_sheet(frame_paths, out_path) -> Path:
    imgs = [Image.open(p).convert("RGBA") for p in frame_paths]
    w, h = imgs[0].size
    n, gap = len(imgs), GAP
    scale = min(1.0, (MAX_SHEET_WIDTH - (n + 1) * gap) / (n * w))
    tw, th = max(1, int(w * scale)), max(1, int(h * scale))
    sheet = Image.new("RGB", (n * tw + (n + 1) * gap, th + 2 * gap), BACKGROUND)
    for i, im in enumerate(imgs):
        if scale < 1.0:
            im = im.resize((tw, th), Image.LANCZOS)
        sheet.paste(im, (gap + i * (tw + gap), gap), im)
    out = Path(out_path)
    sheet.save(out, format="PNG", optimize=False, compress_level=6)
    return out


def instruction(frames: int, loop: bool, action: str) -> str:
    cycle = ("The animation LOOPS: after the last frame it continues with the first frame."
             if loop else "The animation does not loop; it plays once from the first to the last frame.")
    return f"""You are reviewing a 2D game sprite animation: {action}, {frames} frames.
The first image shows the {frames} frames left to right in playback order. The second image is the character's reference design.
{cycle}
Judge only what you can see, and answer in the JSON schema:
- loop: does the last frame lead naturally into the first frame (for a one-shot: does the motion start and end cleanly)?
- limbs: do arms and legs move believably between frames (alternating steps, no teleporting or duplicated limbs)?
- identity: is it the same character as the reference in every frame (colours, outfit, proportions)?
- overall: pass, warn or fail. summary: one sentence a game artist can act on.
Keep each note short. Do not generate images. Do not run shell commands.
"""


def review_attempt(cd, plan, action, direction=None, attempt=None, timeout: int = 300, provider=None) -> dict:
    cd = Path(cd)
    unit, _, _ = resolve_unit(plan, action, direction)
    attempt = _pick_attempt(cd, unit, attempt)
    adir = _attempt_dir(cd, unit, attempt)
    frames = sorted((adir / "frames").glob("*.png"))
    if not frames:
        raise ForgeError("not_processed", f"{unit} attempt {attempt} has no frames; run process first", EXIT_PRECONDITION)
    keyed = cd / "reference" / "character-keyed.png"
    sheet = contact_sheet(frames, adir / "contact-sheet.png")
    loop = bool(plan["actions"][action].get("loop"))

    provider = provider or CodexCliProvider()
    raw_path = adir / "vision-review-raw.json"
    raw_path.unlink(missing_ok=True)
    argv = [provider.codex_bin, "exec", "--json", "--skip-git-repo-check", "-s", "read-only",
            "-C", str(adir.resolve()), "-c", 'model_reasoning_effort="medium"', "-i", str(sheet.resolve())]
    if keyed.exists():
        argv += ["-i", str(keyed.resolve())]
    argv += ["--output-schema", str(LLM_SCHEMA), "-o", str(raw_path.resolve()), "-"]
    with codex_lock(cd):
        try:
            proc = subprocess.run(argv, input=instruction(len(frames), loop, action), capture_output=True, text=True,
                                  timeout=timeout, env=provider._env(), errors="replace")
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
        review = _parse_reply(reply)
        doc = {"schema_version": 1, "attempt": attempt, "unit": unit, "frames": len(frames), "review": review}
        validate("vision-review", doc)
    except (ForgeError, jsonschema.ValidationError) as exc:
        message = exc.message if isinstance(exc, jsonschema.ValidationError) else exc.message
        raise ForgeError("invalid_review", f"the review reply is not usable: {message}", EXIT_PROVIDER) from None
    atomic_write_json(adir / "vision-review.json", doc)
    return {"attempt": attempt, "unit": unit, "review": review}
