"""Acceptance scenarios 1 and 2 on the manual raw path (docs/11 §5; export is covered in M3)."""

import json

from fixtures.synthetic.make import make_sheet
from PIL import Image

from sprite_forge import schemas


def qc_result(report: dict, qc_id: str) -> dict:
    return next(r for r in report["results"] if r["id"] == qc_id)


def run_unit(forge, tmp_path, character, unit, rows, cols, variant="clean"):
    raw = tmp_path / f"{unit}_raw.png"
    make_sheet(variant, rows=rows, cols=cols, cell_size=(256, 256)).save(raw)
    forge.ok("import-raw", character, unit, raw)
    forge.ok("process", character, unit)
    return forge.ok("accept", character, unit)


def test_scenario_1_idle_4_frames_manual_path(forge, tmp_path):
    ref = tmp_path / "ref.png"
    make_sheet("clean", rows=1, cols=1, cell_size=(300, 300)).save(ref)
    forge.ok("init", "hero")
    forge.ok("reference", "import", "hero", ref)
    forge.ok("plan", "hero", "--actions", "idle")

    assert run_unit(forge, tmp_path, "hero", "idle", 2, 2)["accepted"] == "001"

    idle = forge.root / "hero" / "idle"
    assert sorted(p.name for p in (idle / "frames").glob("*.png")) == [f"{i:03d}.png" for i in range(4)]
    sheet = Image.open(idle / "sheet.png").convert("RGBA")
    w, h = sheet.size
    assert all(sheet.getpixel(xy)[3] == 0 for xy in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)))

    report = json.loads((idle / "qc-report.json").read_text())
    schemas.validate("qc-report", report)
    assert (idle / "qc-report.json").read_bytes() == (idle / "attempts/001/qc-report.json").read_bytes()

    row = {r["unit"]: r for r in forge.ok("status", "hero")["units"]}["idle"]
    assert row["state"] == "accepted" and row["accepted_attempt"] == "001"


def test_scenario_2_walk_6_frames_manual_path(forge, tmp_path):
    forge.ok("init", "hero")
    forge.ok("plan", "hero", "--actions", "idle,walk")
    run_unit(forge, tmp_path, "hero", "idle", 2, 2)
    run_unit(forge, tmp_path, "hero", "walk", 2, 3, variant="model_like_bg")

    walk = forge.root / "hero" / "walk"
    assert len(list((walk / "frames").glob("*.png"))) == 6
    report = json.loads((walk / "qc-report.json").read_text())
    schemas.validate("qc-report", report)
    assert qc_result(report, "QC-01")["grade"] == "pass"
    assert qc_result(report, "QC-02")["value"] <= 0.10
    assert qc_result(report, "QC-03")["value"] <= 3

    rows = {r["unit"]: r for r in forge.ok("status", "hero")["units"]}
    assert rows["idle"]["state"] == rows["walk"]["state"] == "accepted"
