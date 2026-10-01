"""Manual-path workflow operations shared by the CLI and (later) the Web UI server.

Public API (``cd`` = character directory ``<root>/<cid>``)
----------------------------------------------------------
``import_reference(cd, file) -> {reference, bg_removed}``  reference/source.*, character.png, character-keyed.png
``write_character(ref_dir, image) -> chroma result``  character.png + character-keyed.png
``make_keyed(rgba_image, key_color=(255, 0, 255), max_side=1024) -> PIL.Image``
``import_raw(cd, plan, action, direction, file) -> {attempt, unit}``
``process_attempt(cd, plan, action, direction, attempt=None, sets=None) -> {attempt, unit, qc}``
``accept_attempt(cd, plan, action, direction, attempt=None) -> {accepted, unit, forced, mirrored}``
    Also (re)writes ``character-scale-profile.json`` when the unit is the scale reference (docs/06 5).
``build_scale_profile(cd, plan, unit, action, attempt) -> dict``  the character-scale-profile.json content.
``derive_mirror(cd, action, source_unit, attempt) -> mirror unit path``
``status_report(cd) -> dict``

Directory layout written (docs/08 section 2): ``<unit>/attempts/NNN/{raw.png, generation.json, clean.png,
frames/, sheet.png, process.json, qc-report.json, .lock}`` and, on accept, the same files copied to
``<unit>/``. ``<unit>`` is ``<action>`` or ``<action>/<direction>``.

Notes on ambiguous spots
------------------------
* ``reference import`` refuses to overwrite an existing ``reference/source.*`` (docs/08: source is immutable).
  The keyed reference is built with #FF00FF; a later key-colour switch needs ``make_keyed`` again.
* ``accept`` of an attempt whose QC status is ``fail`` is allowed and recorded as ``forced: true``.
* ``accept`` defaults to the latest attempt; it must have been processed (qc-report.json exists).
* Scale profile: written by ``accept`` of a body unit when none exists and the unit is the reference unit
  (single direction: any body action, i.e. the first accepted; multi-direction: the representative
  direction unit such as ``idle/down``). Afterwards only re-accepting that same reference action/unit
  rewrites it. ``center_x`` is the median ``mass_cx`` and ``feet_y`` the median ``feet_y`` of the
  accepted output frames. Other accepted actions' QC is not recomputed when the profile changes.
* ``manifest["scale_profile"]`` = {file, reference_action, reference_unit, reference_attempt};
  ``manifest["forced_accepts"]`` lists units whose accepted attempt is forced (QC fail); a unit leaves
  the list when re-accepted without force. ``unit["reprocess_count"]`` counts ``process --set`` runs
  (recovery budget, docs/06 6.1).
* Non-PNG raw files are re-encoded losslessly to ``raw.png``.
"""

from __future__ import annotations

import dataclasses
import io
import json
import os
import re
import shutil
import statistics
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from . import manifest as mf
from .errors import EXIT_PRECONDITION, ForgeError
from .fsutil import (
    allocate_attempt,
    atomic_write_bytes,
    atomic_write_json,
    atomic_write_png,
    attempt_lock,
    latest_attempt,
    sha256_bytes,
    utc_now,
)
from .pipeline import PipelineError
from .pipeline.chroma import KEY_MAGENTA, remove_background
from .pipeline.process import process_sheet
from .pipeline.scale import ScaleProfile
from . import recovery, schemas
from .pipeline.measure import measure_frame
from .plan import process_params, resolve_unit, units
from .prompt import direction_reference_unit
from .qc import run_qc, select_best_attempt

SOURCE_EXT = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}
OUTPUT_FILES = ("raw.png", "clean.png", "sheet.png", "process.json", "qc-report.json")


def _open_image(path) -> Image.Image:
    try:
        img = Image.open(path)
        img.load()
    except FileNotFoundError:
        raise ForgeError("file_not_found", str(path)) from None
    except Exception as exc:
        raise ForgeError("invalid_image", f"{path}: {exc}") from None
    return img


# ---- reference ----------------------------------------------------------------------------

def make_keyed(rgba: Image.Image, key_color=KEY_MAGENTA, max_side: int = 1024) -> Image.Image:
    """Composite onto the key colour (opaque RGB) and shrink the long side to ``max_side``."""
    rgba = rgba.convert("RGBA")
    out = Image.new("RGB", rgba.size, tuple(key_color))
    out.paste(rgba, mask=rgba.getchannel("A"))
    long_side = max(out.size)
    if long_side > max_side:
        k = max_side / long_side
        out = out.resize((max(1, round(out.width * k)), max(1, round(out.height * k))), Image.LANCZOS)
    return out


def write_character(ref_dir, img: Image.Image):
    """Background-removed ``character.png`` + keyed ``character-keyed.png`` from ``img``; returns the chroma result."""
    has_alpha = "A" in img.getbands() or "transparency" in img.info
    arr = np.array(img.convert("RGBA" if has_alpha else "RGB"), dtype=np.uint8)
    chroma = remove_background(arr)
    character = Image.fromarray(chroma.rgba, "RGBA")
    atomic_write_png(character, Path(ref_dir) / "character.png")
    atomic_write_png(make_keyed(character), Path(ref_dir) / "character-keyed.png")
    return chroma


def import_reference(cd, file) -> dict:
    cd = Path(cd)
    mf.load(cd)
    ref_dir = cd / "reference"
    if list(ref_dir.glob("source.*")):
        raise ForgeError("reference_exists", f"{ref_dir}/source.* already exists (source is immutable)")
    src = Path(file)
    img = _open_image(src)
    if img.format not in SOURCE_EXT:
        raise ForgeError("unsupported_format", f"{img.format}: only PNG, JPEG and WebP are accepted")
    suffix = src.suffix.lower() if src.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp") else SOURCE_EXT[img.format]
    data = src.read_bytes()
    atomic_write_bytes(ref_dir / f"source{suffix}", data)

    chroma = write_character(ref_dir, img)

    rel = f"reference/source{suffix}"

    def apply(m):
        m["reference"] = {"mode": "local_file", "source": rel, "source_sha256": sha256_bytes(data), "selected_attempt": None}

    mf.update(cd, apply)
    return {"reference": rel, "bg_removed": chroma.mode == "chroma"}


# ---- attempts -----------------------------------------------------------------------------

def _kind(plan, action) -> str:
    return plan["actions"][action].get("kind", "body")


def _attempt_dir(cd, unit, attempt) -> Path:
    return Path(cd) / unit / "attempts" / attempt


def _pick_attempt(cd, unit, attempt) -> str:
    attempts = Path(cd) / unit / "attempts"
    if attempt is None:
        attempt = latest_attempt(attempts)
        if attempt is None:
            raise ForgeError("no_attempt", f"no attempts for {unit}; run import-raw first", EXIT_PRECONDITION)
    elif not re.fullmatch(r"\d{3}", attempt) or not (attempts / attempt).is_dir():
        raise ForgeError("no_attempt", f"{unit} attempt {attempt!r} does not exist", EXIT_PRECONDITION)
    return attempt


def _attempt_entry(m, unit, kind, attempt, **fields) -> dict:
    ent = mf.unit_entry(m, unit, kind)["attempts"].setdefault(
        attempt,
        {"created_at": utc_now(), "provider": "manual", "generation_status": "succeeded",
         "qc_status": None, "score": None, "recovery": [], "extra": None},
    )
    ent.update(fields)
    return ent


def import_raw(cd, plan, action, direction, file) -> dict:
    cd = Path(cd)
    unit, _, _ = resolve_unit(plan, action, direction)
    src = Path(file)
    img = _open_image(src)
    if img.format == "PNG":
        data = src.read_bytes()
    else:
        buf = io.BytesIO()
        img.convert("RGBA" if "A" in img.getbands() else "RGB").save(buf, format="PNG", optimize=False, compress_level=6)
        data = buf.getvalue()
    attempt, adir = allocate_attempt(cd / unit / "attempts")
    atomic_write_bytes(adir / "raw.png", data)
    codex_fields = ("codex_version", "instruction_template_version", "prompt_template_version", "prompt_file",
                    "prompt_sha256", "thread_id", "argv", "started_at", "finished_at", "duration_s", "exit_code",
                    "error_code", "error_message", "revised_prompt", "transparent_background", "usage", "last_message")
    gen = {"schema_version": 1, "provider": "manual", **dict.fromkeys(codex_fields), "references": [],
           "status": "succeeded", "source_image": str(src),
           "raw": {"file": "raw.png", "width": img.width, "height": img.height, "mode": img.mode,
                   "sha256": sha256_bytes(data)},
           "warnings": []}
    atomic_write_json(adir / "generation.json", gen)
    mf.update(cd, lambda m: _attempt_entry(m, unit, _kind(plan, action), attempt))
    return {"attempt": attempt, "unit": unit}


def load_scale_profile(cd) -> ScaleProfile | None:
    path = Path(cd) / "character-scale-profile.json"
    if not path.exists():
        return None
    return ScaleProfile.from_dict(json.loads(path.read_text(encoding="utf-8")))


_ENUMS = {"anchor": ("feet", "bottom", "center"), "x_anchor": ("mass", "feet", "bbox"),
          "scale_strategy": ("fit", "preserve"), "components": ("largest", "all"),
          "align": ("register", "per_frame")}
_INTS = ("merge_gap_px", "min_area_px", "edge_band_px", "margin_top", "margin_side", "margin_bottom")
_FLOATS = ("t_in", "t_out")


def _apply_sets(params, sets):
    changes = {}
    for item in sets or []:
        key, sep, raw = item.partition("=")
        try:
            if not sep:
                raise ValueError("expected key=value")
            if key in _ENUMS:
                if raw not in _ENUMS[key]:
                    raise ValueError(f"choose from {_ENUMS[key]}")
                changes[key] = raw
            elif key in _INTS:
                changes[key] = int(raw)
            elif key in _FLOATS:
                changes[key] = float(raw)
            elif key == "despill":
                changes[key] = {"true": True, "false": False}[raw.lower()]
            elif key == "key_color":
                if not re.fullmatch(r"#[0-9A-Fa-f]{6}", raw):
                    raise ValueError("expected #RRGGBB")
                changes[key] = tuple(int(raw[i:i + 2], 16) for i in (1, 3, 5))
            else:
                raise ValueError("unsupported key")
        except (ValueError, KeyError) as exc:
            raise ForgeError("invalid_override", f"--set {item!r}: {exc}") from None
    return dataclasses.replace(params, **changes)


def process_attempt(cd, plan, action, direction, attempt=None, sets=None) -> dict:
    cd = Path(cd)
    unit, _, _ = resolve_unit(plan, action, direction)
    attempt = _pick_attempt(cd, unit, attempt)
    adir = _attempt_dir(cd, unit, attempt)
    if not (adir / "raw.png").exists():
        raise ForgeError("no_raw", f"{adir}/raw.png missing", EXIT_PRECONDITION)
    act = plan["actions"][action]
    params = _apply_sets(process_params(plan, action), sets)
    profile = load_scale_profile(cd)
    with attempt_lock(adir):
        shutil.rmtree(adir / "frames", ignore_errors=True)  # derived output, rebuilt below
        try:
            result = process_sheet(adir / "raw.png", adir, params, profile)
        except PipelineError as exc:
            raise ForgeError(exc.code, str(exc)) from None
        report = run_qc(result, action=action, params=params, profile=profile, attempt=attempt,
                        loop=act["loop"], qc_profile=act.get("qc_profile"))
        entry = dict(mf.load(cd)["actions"].get(unit, {}))
        if sets:
            entry["reprocess_count"] = entry.get("reprocess_count", 0) + 1
        others = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((cd / unit / "attempts").glob("*/qc-report.json"))
                  if p.parent.name != attempt]
        best = select_best_attempt([*others, report])["attempt"]
        recovery.attach(report, result.data, params, recovery.budget_state(entry, best))
        atomic_write_json(adir / "qc-report.json", report)

    def record(m):
        ent = _attempt_entry(m, unit, _kind(plan, action), attempt, qc_status=report["status"], score=report["score"])
        if sets:
            m["actions"][unit]["reprocess_count"] = entry["reprocess_count"]
        return ent

    mf.update(cd, record)
    failed = [r["id"] for r in report["results"] if r["grade"] == "fail"]
    return {"attempt": attempt, "unit": unit,
            "qc": {"status": report["status"], "failed": failed, "recommendations": report["recommendations"]}}


def _replace_dir(tmp: Path, final: Path) -> None:
    shutil.rmtree(final, ignore_errors=True)
    os.replace(tmp, final)


def derive_mirror(cd, action, source_unit, attempt) -> str:
    """Write ``<action>/left`` as the horizontal flip of every accepted ``right`` frame (docs/02 8.1)."""
    cd = Path(cd)
    left = f"{action}/left"
    ldir = cd / left
    tmp = ldir / ".frames.new"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    flipped = []
    for src in sorted((cd / source_unit / "frames").glob("*.png")):
        img = ImageOps.mirror(Image.open(src).convert("RGBA"))
        atomic_write_png(img, tmp / src.name)
        flipped.append(np.array(img))
    _replace_dir(tmp, ldir / "frames")
    atomic_write_png(Image.fromarray(np.concatenate(flipped, axis=1), "RGBA"), ldir / "sheet.png")
    atomic_write_json(ldir / "mirror.json", {"source": "right", "attempt": attempt})

    def apply(m):
        ent = m["actions"].get(left)
        if ent is None or "attempts" not in ent:
            m["actions"][left] = {"kind": m["actions"][source_unit]["kind"], "mirror_of": source_unit}
        else:
            ent["mirror_of"] = source_unit

    mf.update(cd, apply)
    return left


def build_scale_profile(cd, plan, unit, action, attempt) -> dict:
    """docs/06 5: body_height/width = median bbox of the accepted output frames; norm_scale = s x RH."""
    cd = Path(cd)
    data = json.loads((cd / unit / "process.json").read_text(encoding="utf-8"))
    measures = [m for m in (measure_frame(np.array(Image.open(p).convert("RGBA")))
                            for p in sorted((cd / unit / "frames").glob("*.png"))) if m]
    if not measures:
        raise ForgeError("empty_reference", f"{unit} attempt {attempt} has no foreground frames for a scale profile")
    med = lambda vals: round(float(statistics.median(vals)), 2)  # noqa: E731
    derived = data["derived"]
    return {
        "schema_version": 1,
        "character": mf.load(cd)["character"],
        "reference_action": action,
        "reference_attempt": attempt,
        "target_cell": [plan["cell"]["w"], plan["cell"]["h"]],
        "baseline_y": derived["baseline_y"],
        "body_height": med([m.h for m in measures]),
        "body_width": med([m.w for m in measures]),
        "feet_y": med([m.feet_y for m in measures]),
        "center_x": med([m.mass_cx for m in measures]),
        "norm_scale": round(derived["scale"] * derived["raw_cell_height"], 2),
        "raw_cell_height": derived["raw_cell_height"],
    }


def _update_scale_profile(cd, plan, unit, action, attempt) -> str | None:
    if _kind(plan, action) != "body":
        return None
    path = cd / "character-scale-profile.json"
    ref_unit = direction_reference_unit(plan)
    if ref_unit is not None and unit != ref_unit:
        return None
    if path.exists():
        current = mf.load(cd).get("scale_profile", {}).get("reference_unit")
        if unit != current:
            return None
    profile = build_scale_profile(cd, plan, unit, action, attempt)
    schemas.validate("character-scale-profile", profile)
    state = "updated" if path.exists() else "created"
    atomic_write_json(path, profile)
    mf.update(cd, lambda m: m.__setitem__("scale_profile", {
        "file": path.name, "reference_action": action, "reference_unit": unit, "reference_attempt": attempt}))
    return state


def accept_attempt(cd, plan, action, direction, attempt=None) -> dict:
    cd = Path(cd)
    unit, direction, _ = resolve_unit(plan, action, direction)
    attempt = _pick_attempt(cd, unit, attempt)
    adir = _attempt_dir(cd, unit, attempt)
    if not (adir / "qc-report.json").exists():
        raise ForgeError("not_processed", f"{unit} attempt {attempt} has not been processed", EXIT_PRECONDITION)
    udir = cd / unit
    with attempt_lock(adir):
        for name in OUTPUT_FILES:
            atomic_write_bytes(udir / name, (adir / name).read_bytes())
        tmp = udir / ".frames.new"
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.copytree(adir / "frames", tmp)
        _replace_dir(tmp, udir / "frames")
        status = json.loads((adir / "qc-report.json").read_text(encoding="utf-8"))["status"]
    forced = status == "fail"

    def apply(m):
        ent = mf.unit_entry(m, unit, _kind(plan, action))
        ent["accepted_attempt"] = attempt
        ent["forced"] = forced
        listed = [u for u in m.get("forced_accepts", []) if u != unit]
        m["forced_accepts"] = [*listed, unit] if forced else listed

    mf.update(cd, apply)
    _update_scale_profile(cd, plan, unit, action, attempt)
    mirrored = []
    eff = plan["actions"][action].get("directions", plan["directions"])
    if direction == "right" and len(plan["directions"]) > 1 and plan.get("mirror", {}).get("left") == "right" and "left" in eff:
        mirrored.append(derive_mirror(cd, action, unit, attempt))
    return {"accepted": attempt, "unit": unit, "forced": forced, "mirrored": mirrored}


# ---- status -------------------------------------------------------------------------------

def status_report(cd) -> dict:
    cd = Path(cd)
    m = mf.load(cd)
    plan_file = cd / "animation-plan.json"
    plan = json.loads(plan_file.read_text(encoding="utf-8")) if plan_file.exists() else None
    if plan:
        listed = [(u["unit"], u["action"], u["direction"]) for u in units(plan)]
    else:
        listed = [(k, k.split("/")[0], k.split("/")[1] if "/" in k else None) for k in m["actions"]]
    rows = []
    for unit, action, direction in listed:
        ent = m["actions"].get(unit)
        row = {"unit": unit, "action": action, "direction": direction, "state": "pending", "attempts": 0,
               "latest_attempt": None, "accepted_attempt": None, "qc_status": None, "score": None}
        if ent and "mirror_of" in ent and "attempts" not in ent:
            src = m["actions"].get(ent["mirror_of"], {})
            row.update(state="mirrored", mirror_of=ent["mirror_of"], accepted_attempt=src.get("accepted_attempt"))
        elif ent:
            atts = ent.get("attempts", {})
            acc = ent.get("accepted_attempt")
            latest = max(atts) if atts else None
            shown = atts.get(acc or latest, {})
            state = "accepted" if acc else "processed" if shown.get("qc_status") else "imported" if atts else "pending"
            row.update(state=state, attempts=len(atts), latest_attempt=latest, accepted_attempt=acc,
                       qc_status=shown.get("qc_status"), score=shown.get("score"), forced=ent.get("forced", False))
        elif plan and any(u["unit"] == unit and u["mirrored"] for u in units(plan)):
            row["mirror_of"] = f"{action}/right"
        rows.append(row)
    return {"character": m["character"], "has_reference": m["reference"] is not None,
            "has_plan": plan is not None, "units": rows}
