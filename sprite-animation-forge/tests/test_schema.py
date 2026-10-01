"""Every JSON artifact validates against schemas/*.schema.json (docs/11 section 4)."""

import copy
import json
from pathlib import Path

import jsonschema
import pytest
from fixtures.synthetic.make import make_sheet

from sprite_forge import manifest as mf
from sprite_forge import plan as pl
from sprite_forge import schemas
from sprite_forge.pipeline.process import process_sheet
from sprite_forge.qc import run_qc

SCALE_PROFILE_EXAMPLE = {  # docs/06 section 5
    "schema_version": 1, "character": "hero", "reference_action": "idle", "reference_attempt": "001",
    "target_cell": [128, 128], "baseline_y": 118, "body_height": 104, "body_width": 62, "feet_y": 118,
    "center_x": 64, "norm_scale": 131.1, "raw_cell_height": 627,
}
PROFILE_EXAMPLE = {  # docs/08 section 5.2
    "schema_version": 1, "source": "codex-analysis", "edited_by_user": False,
    "identity": {
        "silhouette": "small chibi knight", "body_ratio": "short and stocky", "head_ratio": "about 1:2.5",
        "hair": "", "face": "hidden by a visor", "eyes": "", "clothing": "red hood, steel plate armor",
        "primary_colors": ["#C8281E", "#9A9CA0"], "secondary_colors": ["#E8D2A8", "#6B3F1F"],
        "weapon": "sheathed sword", "accessories": ["leather pouch"], "outline_style": "dark brown outline",
        "shading_style": "soft cel shading", "camera_angle": "side view", "orientation": "facing right",
    },
}


def test_schema_files_are_valid_draft_2020_12():
    for name in ("animation-plan", "character-profile", "character-scale-profile", "qc-report", "manifest"):
        jsonschema.Draft202012Validator.check_schema(schemas.load_schema(name))


@pytest.mark.parametrize("kw", [
    {}, {"view": "topdown"}, {"view": "topdown", "mirror": False}, {"cell": "256x256"},
])
def test_schema_plan_outputs_validate(kw):
    plan = pl.build_plan("hero", pl.resolve_actions(None, "side-action"), **kw)
    schemas.validate("animation-plan", plan)
    schemas.validate("animation-plan", pl.build_plan(
        "hero", ["idle", "slash_fx"], overrides=pl.parse_overrides(["slash_fx.kind=fx", "slash_fx.motion=arc"])))


def test_schema_plan_docs_example_validates_and_rejects_bad_values():
    plan = pl.build_plan("hero", ["idle", "walk"])
    schemas.validate("animation-plan", plan)
    bad = copy.deepcopy(plan)
    bad["actions"]["idle"]["frames"] = 99
    with pytest.raises(jsonschema.ValidationError):
        schemas.validate("animation-plan", bad)
    bad = copy.deepcopy(plan)
    bad["mirror"] = {"right": "left"}
    with pytest.raises(jsonschema.ValidationError):
        schemas.validate("animation-plan", bad)
    bad = copy.deepcopy(plan)
    bad["key_color"] = "#123456"
    with pytest.raises(jsonschema.ValidationError):
        schemas.validate("animation-plan", bad)


def test_schema_character_profile_empty_and_example():
    schemas.validate("character-profile", schemas.empty_character_profile())
    schemas.validate("character-profile", PROFILE_EXAMPLE)
    bad = copy.deepcopy(PROFILE_EXAMPLE)
    bad["identity"]["primary_colors"] = ["red"]
    with pytest.raises(jsonschema.ValidationError):
        schemas.validate("character-profile", bad)


def test_schema_character_scale_profile_example():
    schemas.validate("character-scale-profile", SCALE_PROFILE_EXAMPLE)
    bad = {k: v for k, v in SCALE_PROFILE_EXAMPLE.items() if k != "norm_scale"}
    with pytest.raises(jsonschema.ValidationError):
        schemas.validate("character-scale-profile", bad)


def test_schema_qc_report_from_run_qc(tmp_path):
    raw = tmp_path / "raw.png"
    make_sheet("clean", rows=2, cols=3, cell_size=(256, 256)).save(raw)
    plan = pl.build_plan("hero", ["walk"])
    result = process_sheet(raw, tmp_path / "out", pl.process_params(plan, "walk"))
    for action in ("walk", "attack", "death"):
        report = run_qc(result, action=action, attempt="001")
        schemas.validate("qc-report", json.loads(json.dumps(report)))


def test_schema_qc_report_character_level_example():
    doc = {"schema_version": 1, "character": "hero", "status": "warn", "forced_accepts": [],
           "actions": {"idle": {"attempt": "001", "status": "pass", "score": 100},
                       "run": {"attempt": "002", "status": "warn", "score": 92, "warnings": ["QC-02"]}}}
    schemas.validate("qc-report", doc)


def test_schema_manifest_created_and_docs_example(tmp_path):
    m = mf.create(tmp_path / "hero", "hero", {"view": "side", "art_style": "auto", "asset_type": "character"})
    schemas.validate("manifest", m)
    docs_example = {
        "schema_version": 1, "character": "hero", "created_at": "2026-09-30T13:10:00Z",
        "updated_at": "2026-09-30T13:40:12Z", "tool": {"name": "sprite-animation-forge", "version": "0.1.0"},
        "reference": {"mode": "attached_image", "source": "reference/source.png", "source_sha256": "x",
                      "selected_attempt": None},
        "assumptions": ["view=side"],
        "actions": {
            "idle": {"kind": "body", "accepted_attempt": "001", "forced": False, "attempts": {
                "001": {"created_at": "2026-09-30T13:12:03Z", "provider": "codex-cli",
                        "generation_status": "succeeded", "qc_status": "pass", "score": 100, "recovery": [],
                        "extra": None}}},
            "attack": {"kind": "body", "accepted_attempt": None, "forced": False, "attempts": {
                "002": {"provider": "codex-cli", "generation_status": "running", "qc_status": None, "score": None,
                        "recovery": ["character_small"], "extra": None}}},
            "walk/left": {"kind": "body", "mirror_of": "walk/right"},
        },
        "exports": {"phaser": {"exported_at": "2026-09-30T13:40:12Z", "files": {"atlas/hero.png": "sha256:x"}}},
        "usage": {"codex_calls": 7, "input_tokens": 1, "cached_input_tokens": 1, "output_tokens": 1},
    }
    schemas.validate("manifest", docs_example)
    bad = copy.deepcopy(docs_example)
    bad["actions"]["idle"]["attempts"]["001"]["generation_status"] = "done"
    with pytest.raises(jsonschema.ValidationError):
        schemas.validate("manifest", bad)


def test_schema_cli_outputs_validate(forge, raw_sheet):
    forge.ok("init", "hero", "--view", "topdown")
    plan = forge.ok("plan", "hero", "--actions", "walk")["plan"]
    schemas.validate("animation-plan", plan)
    forge.ok("import-raw", "hero", "walk", raw_sheet, "--direction", "right")
    forge.ok("process", "hero", "walk", "--direction", "right")
    forge.ok("accept", "hero", "walk", "--direction", "right")
    cd = forge.root / "hero"
    schemas.validate("animation-plan", json.loads((cd / "animation-plan.json").read_text()))
    schemas.validate("manifest", json.loads((cd / "manifest.json").read_text()))
    for p in (cd / "walk/attempts/001/qc-report.json", cd / "walk/right/attempts/001/qc-report.json"):
        if p.exists():
            schemas.validate("qc-report", json.loads(p.read_text()))
    assert Path(cd / "walk/right/qc-report.json").exists()
