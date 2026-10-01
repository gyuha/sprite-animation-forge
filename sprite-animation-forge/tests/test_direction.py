import json

import numpy as np
from fixtures.synthetic.make import make_sheet
from PIL import Image

from sprite_forge import plan as pl
from sprite_forge.pipeline.measure import measure_frame
from sprite_forge.pipeline.process import process_sheet


def load_frames(d):
    return [np.array(Image.open(p).convert("RGBA")) for p in sorted(d.glob("[0-9]*.png"))]


def setup_topdown(forge, raw, extra_plan=()):
    forge.ok("init", "hero", "--view", "topdown")
    forge.ok("plan", "hero", "--actions", "walk", *extra_plan)
    forge.ok("import-raw", "hero", "walk", raw, "--direction", "right")
    forge.ok("process", "hero", "walk", "--direction", "right")
    return forge.ok("accept", "hero", "walk", "--direction", "right")


def test_direction_unit_paths_on_disk(forge, raw_sheet):
    out = setup_topdown(forge, raw_sheet)
    cd = forge.root / "hero"
    assert out == {"accepted": "001", "unit": "walk/right", "forced": False, "mirrored": ["walk/left"]}
    assert (cd / "walk/right/attempts/001/raw.png").exists()
    assert (cd / "walk/right/frames/000.png").exists() and (cd / "walk/right/sheet.png").exists()
    assert not (cd / "walk/attempts").exists()
    left = cd / "walk/left"
    assert (left / "frames/000.png").exists() and (left / "sheet.png").exists() and (left / "mirror.json").exists()
    assert not (left / "attempts").exists()  # mirror units have no attempts
    assert json.loads((left / "mirror.json").read_text()) == {"source": "right", "attempt": "001"}


def test_direction_left_is_exact_horizontal_flip_of_asymmetric_right(forge, raw_sheet, tmp_path):
    setup_topdown(forge, raw_sheet)
    cd = forge.root / "hero"
    right = load_frames(cd / "walk/right/frames")
    left = load_frames(cd / "walk/left/frames")
    assert len(right) == len(left) == 6
    # independent expectation: run the library pipeline directly and flip its output
    plan = json.loads((cd / "animation-plan.json").read_text())
    ref = process_sheet(raw_sheet, tmp_path / "ref_out", pl.process_params(plan, "walk"))
    for i, (r, l) in enumerate(zip(right, left)):
        assert np.array_equal(r, ref.frames[i])
        assert np.array_equal(l, np.fliplr(ref.frames[i])), f"frame {i} is not the exact flip"
        assert not np.array_equal(l, r), "asymmetric_right fixture must differ from its mirror"
    sheet = np.array(Image.open(cd / "walk/left/sheet.png").convert("RGBA"))
    assert sheet.shape == (128, 6 * 128, 4)
    assert np.array_equal(sheet, np.concatenate(left, axis=1))


def test_direction_flip_keeps_baseline_and_feet(forge, raw_sheet):
    setup_topdown(forge, raw_sheet)
    cd = forge.root / "hero"
    for r, l in zip(load_frames(cd / "walk/right/frames"), load_frames(cd / "walk/left/frames")):
        mr, ml = measure_frame(r), measure_frame(l)
        assert ml.feet_y == mr.feet_y and ml.feet_y_strict == mr.feet_y_strict
        assert (ml.bbox[1], ml.bbox[3]) == (mr.bbox[1], mr.bbox[3])
        assert ml.h == mr.h and ml.w == mr.w
        assert abs(ml.feet_cx - (128 - mr.feet_cx)) < 1e-6  # feet mirror about the cell centre
        assert abs(ml.bbox_cx - (128 - mr.bbox_cx)) < 1e-6
        assert mr.feet_y == 118  # baseline = cell_h - margin_bottom


def test_direction_reaccept_right_rederives_left(forge, raw_sheet, tmp_path):
    setup_topdown(forge, raw_sheet)
    cd = forge.root / "hero"
    other = tmp_path / "other.png"
    make_sheet("clean", rows=2, cols=3, cell_size=(256, 256)).save(other)
    forge.ok("import-raw", "hero", "walk", other, "--direction", "right")
    forge.ok("process", "hero", "walk", "--direction", "right")
    out = forge.ok("accept", "hero", "walk", "--direction", "right")
    assert out["accepted"] == "002" and out["mirrored"] == ["walk/left"]
    assert json.loads((cd / "walk/left/mirror.json").read_text())["attempt"] == "002"
    for r, l in zip(load_frames(cd / "walk/right/frames"), load_frames(cd / "walk/left/frames")):
        assert np.array_equal(l, np.fliplr(r))


def test_direction_left_cli_is_mirrored_direction_error(forge, raw_sheet):
    forge.ok("init", "hero", "--view", "topdown")
    forge.ok("plan", "hero", "--actions", "walk")
    for args in (("import-raw", "hero", "walk", raw_sheet), ("process", "hero", "walk"), ("accept", "hero", "walk")):
        code, out = forge.run(*args, "--direction", "left")
        assert code == 1 and out["error_code"] == "mirrored_direction", args
    assert not (forge.root / "hero/walk/left").exists()


def test_direction_required_and_invalid_cli(forge, raw_sheet):
    forge.ok("init", "hero", "--view", "topdown")
    forge.ok("plan", "hero", "--actions", "walk,death", "--set", "death.directions=down")
    code, out = forge.run("import-raw", "hero", "walk", raw_sheet)
    assert (code, out["error_code"]) == (1, "direction_required")
    code, out = forge.run("import-raw", "hero", "death", raw_sheet, "--direction", "up")
    assert (code, out["error_code"]) == (1, "invalid_direction")
    code, out = forge.run("import-raw", "hero", "walk", raw_sheet, "--direction", "sideways")
    assert (code, out["error_code"]) == (1, "usage")
    assert forge.ok("import-raw", "hero", "death", raw_sheet, "--direction", "down")["unit"] == "death/down"


def test_direction_single_direction_plan_rejects_other_direction(forge, raw_sheet):
    forge.ok("init", "hero")
    forge.ok("plan", "hero", "--actions", "walk")
    code, out = forge.run("import-raw", "hero", "walk", raw_sheet, "--direction", "up")
    assert (code, out["error_code"]) == (1, "invalid_direction")
    assert forge.ok("import-raw", "hero", "walk", raw_sheet, "--direction", "right")["unit"] == "walk"


def test_direction_no_mirror_left_is_a_normal_unit(forge, raw_sheet):
    out = setup_topdown(forge, raw_sheet, ("--no-mirror",))
    assert out["mirrored"] == []
    cd = forge.root / "hero"
    assert not (cd / "walk/left").exists()
    assert forge.ok("import-raw", "hero", "walk", raw_sheet, "--direction", "left")["unit"] == "walk/left"
    assert (cd / "walk/left/attempts/001/raw.png").exists()


def test_direction_manifest_and_status_for_mirror_unit(forge, raw_sheet):
    setup_topdown(forge, raw_sheet)
    m = json.loads((forge.root / "hero/manifest.json").read_text())
    assert m["actions"]["walk/left"] == {"kind": "body", "mirror_of": "walk/right"}
    assert m["actions"]["walk/right"]["accepted_attempt"] == "001"
    rows = {r["unit"]: r for r in forge.ok("status", "hero")["units"]}
    assert list(rows) == ["walk/down", "walk/right", "walk/up", "walk/left"]
    assert rows["walk/left"]["state"] == "mirrored" and rows["walk/left"]["mirror_of"] == "walk/right"
    assert rows["walk/left"]["accepted_attempt"] == "001"
    assert rows["walk/right"]["state"] == "accepted" and rows["walk/down"]["state"] == "pending"


def test_direction_attempt_numbers_are_per_unit(forge, raw_sheet):
    forge.ok("init", "hero", "--view", "topdown")
    forge.ok("plan", "hero", "--actions", "walk")
    assert forge.ok("import-raw", "hero", "walk", raw_sheet, "--direction", "down")["attempt"] == "001"
    assert forge.ok("import-raw", "hero", "walk", raw_sheet, "--direction", "down")["attempt"] == "002"
    assert forge.ok("import-raw", "hero", "walk", raw_sheet, "--direction", "up")["attempt"] == "001"
