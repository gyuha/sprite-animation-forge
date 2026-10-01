"""``export`` command core (docs/07): accepted frames -> atlas, Phaser JSON, animations.json, GIFs, qc-report.

Public API
----------
``export_character(cd, engine="phaser") -> {"files": [...], "warnings": [...]}``

Output (relative to the character directory): ``atlas/<cid>.png|.json|.generic.json|.meta.json``,
``animations.json``, ``preview/<key>.gif``, ``qc-report.json`` (docs/06 4.3). The manifest gets
``exports.phaser = {exported_at, files: {path: "sha256:..."}}`` (``manifest.json`` itself is not hashed).
Everything is written to ``.export.new/``, validated, then moved into place.

Notes on ambiguous spots
------------------------
* Only accepted units get atlas rows; the rest is reported as ``warnings: ["missing_actions: [...]"]``.
  A unit is accepted when the manifest has ``accepted_attempt`` (a mirror unit: its ``mirror_of`` source
  is accepted) and ``<unit>/frames`` exists. No accepted unit at all -> ``nothing_to_export`` (exit 3).
* Character ``qc-report.json`` keys ``actions`` by unit path (``walk/up`` for multi-direction plans, as in
  the manifest); a mirror unit reports its source's attempt/status/score. ``warnings`` lists QC ids graded
  ``warn`` and is omitted when empty. ``forced_accepts`` lists forced units (manifest ``forced``).
* ``baseline_y`` comes from ``character-scale-profile.json``, falling back to cell_h - margin.bottom.
* Only ``--engine phaser`` exists (Phase 2 engines are out of scope); the generic JSON is always written.
"""

from __future__ import annotations

import copy
import json
import os
import shutil
from pathlib import Path

from PIL import Image

from .. import manifest as mf
from .. import schemas
from ..errors import EXIT_PRECONDITION, ForgeError
from ..fsutil import atomic_write_bytes, atomic_write_json, atomic_write_png, sha256_file, utc_now
from ..plan import load_plan
from .atlas import build_atlas, export_units
from .gif import render_gif
from .phaser import anim_key, animations_json, generic_json, meta_json, origin_for, phaser_json
from .validate import validate_export

TMP_NAME = ".export.new"
_RANK = {"pass": 0, "warn": 1, "fail": 2}


def _unit_state(cd: Path, m: dict, unit: str):
    """``(source_unit, forced)`` when the unit is accepted and has frames, else None."""
    ent = m["actions"].get(unit)
    if not ent:
        return None
    source = ent.get("mirror_of", unit)
    src = m["actions"].get(source)
    if not src or not src.get("accepted_attempt") or not any((cd / unit / "frames").glob("*.png")):
        return None
    return source, bool(src.get("forced"))


def _qc_summary(cd: Path, source: str, attempt: str) -> dict:
    rep = json.loads((cd / source / "qc-report.json").read_text(encoding="utf-8"))
    out = {"attempt": attempt, "status": rep["status"], "score": rep["score"]}
    warns = [r["id"] for r in rep["results"] if r["grade"] == "warn"]
    if warns:
        out["warnings"] = warns
    return out


def _baseline(cd: Path, plan: dict) -> int:
    prof = cd / "character-scale-profile.json"
    if prof.exists():
        return int(json.loads(prof.read_text(encoding="utf-8"))["baseline_y"])
    return plan["cell"]["h"] - plan["margin"]["bottom"]


def export_character(cd, engine: str = "phaser") -> dict:
    if engine != "phaser":
        raise ForgeError("invalid_engine", f"unsupported engine {engine!r} (only phaser)")
    cd = Path(cd)
    m = mf.load(cd)
    plan = load_plan(cd)
    cid = plan["character"]

    frames_by_unit, info, report_actions, forced, missing = {}, {}, {}, [], []
    for u in export_units(plan):
        state = _unit_state(cd, m, u["unit"])
        if state is None:
            missing.append(u["unit"])
            continue
        source, is_forced = state
        attempt = m["actions"][source]["accepted_attempt"]
        frames_by_unit[u["unit"]] = [Image.open(p).convert("RGBA") for p in sorted((cd / u["unit"] / "frames").glob("*.png"))]
        summary = _qc_summary(cd, source, attempt)
        report_actions[u["unit"]] = summary
        info[u["unit"]] = {"attempt": attempt, "qc": summary["status"],
                           **({"mirror_of": source} if source != u["unit"] else {})}
        if is_forced and source == u["unit"]:
            forced.append(u["unit"])
    if not frames_by_unit:
        raise ForgeError("nothing_to_export", "no accepted unit to export; run accept first", EXIT_PRECONDITION)
    warnings = [f"missing_actions: {json.dumps(missing)}"] if missing else []

    atlas = build_atlas(plan, frames_by_unit)
    baseline = _baseline(cd, plan)
    origin = origin_for(baseline, atlas.cell[1])
    png_name = f"{cid}.png"

    tmp = cd / TMP_NAME
    shutil.rmtree(tmp, ignore_errors=True)
    (tmp / "atlas").mkdir(parents=True)
    (tmp / "preview").mkdir()
    try:
        atomic_write_png(atlas.image, tmp / "atlas" / png_name)
        phaser = phaser_json(atlas, origin, png_name)
        anims = animations_json(plan, atlas)
        generic = generic_json(plan, atlas, origin, png_name)
        meta = meta_json(plan, atlas, origin, baseline, sha256_file(tmp / "atlas" / png_name), png_name, info)
        validate_export(plan, atlas.size, phaser, anims, generic, meta)
        report = {"schema_version": 1, "character": cid,
                  "status": max((a["status"] for a in report_actions.values()), key=_RANK.__getitem__),
                  "actions": report_actions, "forced_accepts": forced}
        schemas.validate("qc-report", report)
        atomic_write_json(tmp / "atlas" / f"{cid}.json", phaser)
        atomic_write_json(tmp / "atlas" / f"{cid}.generic.json", generic)
        atomic_write_json(tmp / "atlas" / f"{cid}.meta.json", meta)
        atomic_write_json(tmp / "animations.json", anims)
        atomic_write_json(tmp / "qc-report.json", report)
        for r in atlas.rows:
            atomic_write_bytes(tmp / "preview" / f"{anim_key(r['action'], r['direction'])}.gif",
                               render_gif(frames_by_unit[r["unit"]], plan["actions"][r["action"]]["fps"]))
        rels = sorted(str(p.relative_to(tmp)) for p in tmp.rglob("*") if p.is_file())
        hashes = {rel: f"sha256:{sha256_file(tmp / rel)}" for rel in rels}
        exports = {"exported_at": utc_now(), "files": hashes}
        check = copy.deepcopy(m)
        check.setdefault("exports", {})["phaser"] = exports
        schemas.validate("manifest", check)
        for d in ("atlas", "preview"):
            shutil.rmtree(cd / d, ignore_errors=True)
            os.replace(tmp / d, cd / d)
        for f in ("animations.json", "qc-report.json"):
            os.replace(tmp / f, cd / f)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    mf.update(cd, lambda data: data.setdefault("exports", {}).__setitem__("phaser", exports))
    return {"files": rels, "warnings": warnings}
