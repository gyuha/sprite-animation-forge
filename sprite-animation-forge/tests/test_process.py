"""process (whole chain) tests (docs/11 sections 4 and 5)."""

import hashlib
import json

import numpy as np
import pytest
from fixtures.synthetic.make import make_sheet
from PIL import Image

from sprite_forge.pipeline import PipelineError
from sprite_forge.pipeline.process import ProcessParams, process_sheet

PARAMS = ProcessParams(rows=2, cols=3, frames=6)


def run(tmp_path, variant="clean", params=PARAMS, name="out", profile=None, rows=2, cols=3):
    raw = tmp_path / "raw.png"
    make_sheet(variant, rows=rows, cols=cols, cell_size=(256, 256)).save(raw)
    return process_sheet(raw, tmp_path / name, params, profile)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_process_writes_all_outputs(tmp_path):
    res = run(tmp_path)
    out = tmp_path / "out"
    assert (out / "clean.png").exists() and (out / "sheet.png").exists() and (out / "process.json").exists()
    assert sorted(p.name for p in (out / "frames").iterdir()) == [f"{i:03d}.png" for i in range(6)]
    assert len(res.frames) == 6


def test_process_frame_and_sheet_dimensions(tmp_path):
    run(tmp_path)
    out = tmp_path / "out"
    assert Image.open(out / "frames/000.png").size == (128, 128)
    assert Image.open(out / "sheet.png").size == (6 * 128, 128)
    assert Image.open(out / "clean.png").size == (768, 512)
    assert Image.open(out / "sheet.png").mode == "RGBA"


def test_process_sheet_corners_are_transparent(tmp_path):
    res = run(tmp_path)
    sheet = np.array(Image.open(tmp_path / "out" / "sheet.png"))
    for y, x in ((0, 0), (0, -1), (-1, 0), (-1, -1)):
        assert sheet[y, x, 3] == 0
    assert (res.sheet == sheet).all()


def test_process_frames_equal_sheet_slices(tmp_path):
    run(tmp_path)
    out = tmp_path / "out"
    sheet = np.array(Image.open(out / "sheet.png"))
    for i in range(6):
        assert np.array_equal(np.array(Image.open(out / f"frames/{i:03d}.png")), sheet[:, i * 128 : (i + 1) * 128])


def test_process_baseline_jitter_frames_end_on_baseline(tmp_path):
    # legacy per-frame alignment pins every frame's feet to the baseline (align=register keeps the model's grounding)
    res = run(tmp_path, "baseline_jitter", params=ProcessParams(align="per_frame"))
    for f in res.data["derived"]["frames"]:
        assert f["offset"] is not None and all(isinstance(v, int) for v in f["offset"])
    assert res.data["derived"]["baseline_y"] == 118
    bottoms = []
    for frame in res.frames:
        rows = np.nonzero((frame[..., 3] >= 64).sum(axis=1) >= 3)[0]
        bottoms.append(rows.max() + 1)
    assert max(bottoms) - min(bottoms) <= 1
    assert all(abs(b - 118) <= 1 for b in bottoms)


def test_process_json_structure(tmp_path):
    res = run(tmp_path)
    data = json.loads((tmp_path / "out" / "process.json").read_text())
    assert data == json.loads(json.dumps(res.data))
    assert data["schema_version"] == 1
    assert set(data) == {"schema_version", "pipeline_version", "raw", "params", "derived", "outputs", "warnings"}
    assert data["raw"]["file"] == "raw.png" and data["raw"]["sha256"] == sha(tmp_path / "raw.png")
    assert data["params"]["grid"] == "2x3" and data["params"]["background"]["key_color"] == "#FF00FF"
    assert data["params"]["resample"] == "lanczos"
    assert len(data["derived"]["frames"]) == 6
    assert len(data["derived"]["row_boundaries"]) == 3 and len(data["derived"]["col_boundaries"]) == 2
    assert data["outputs"]["sheet.png"] == "sha256:" + sha(tmp_path / "out" / "sheet.png")
    assert set(data["outputs"]) == {"clean.png", "sheet.png", *(f"frames/{i:03d}.png" for i in range(6))}


def test_process_json_has_no_absolute_paths_or_timestamps(tmp_path):
    run(tmp_path)
    text = (tmp_path / "out" / "process.json").read_text()
    assert str(tmp_path) not in text and "/Users" not in text and "/tmp" not in text
    assert "time" not in text and "date" not in text


def test_process_is_deterministic(tmp_path):
    run(tmp_path, "model_like_bg", name="a")
    run(tmp_path, "model_like_bg", name="b")
    for rel in ("clean.png", "sheet.png", "process.json", *(f"frames/{i:03d}.png" for i in range(6))):
        assert sha(tmp_path / "a" / rel) == sha(tmp_path / "b" / rel), rel


def test_process_wide_attack_no_overflow_with_fit(tmp_path):
    res = run(tmp_path, "wide_attack", ProcessParams(rows=2, cols=3, frames=6, x_anchor="feet"))
    assert not [w for w in res.warnings if w.startswith("overflow")]
    for f in res.data["derived"]["frames"]:
        assert not any(f["overflow"].values())


def test_process_preserve_without_profile_falls_back_to_fit(tmp_path):
    res = run(tmp_path, params=ProcessParams(rows=2, cols=3, frames=6, scale_strategy="preserve"))
    assert "no_scale_profile" in res.warnings
    assert res.data["derived"]["scale_strategy_used"] == "fit"
    assert res.data["params"]["scale_strategy"] == "preserve"


def test_process_preserve_with_profile_uses_norm_scale_over_raw_cell_height(tmp_path):
    params = ProcessParams(rows=2, cols=3, frames=6, scale_strategy="preserve")
    res = run(tmp_path, params=params, profile={"norm_scale": 51.2})
    assert res.data["derived"]["scale_strategy_used"] == "preserve"
    assert res.data["derived"]["scale"] == pytest.approx(51.2 / 256, abs=1e-4)
    assert "no_scale_profile" not in res.warnings


def test_process_preserve_overflow_is_reported_not_hidden(tmp_path):
    params = ProcessParams(rows=2, cols=3, frames=6, scale_strategy="preserve")
    res = run(tmp_path, params=params, profile={"norm_scale": 400.0})
    assert any(w.startswith("overflow:") for w in res.warnings)
    assert any(any(f["overflow"].values()) for f in res.data["derived"]["frames"])


def test_process_frames_fewer_than_cells_uses_first_cells(tmp_path):
    res = run(tmp_path, params=ProcessParams(rows=2, cols=3, frames=4))
    assert len(res.frames) == 4 and res.sheet.shape == (128, 4 * 128, 4)
    assert not (tmp_path / "out" / "frames" / "004.png").exists()


def test_process_empty_cell_gives_blank_frame_and_warning(tmp_path):
    res = run(tmp_path, "empty_cell", ProcessParams(rows=2, cols=2, frames=4), rows=2, cols=2)
    assert "empty_frame:3" in res.warnings
    assert not res.frames[3].any()
    assert res.data["derived"]["frames"][3]["empty"] is True


def test_process_native_alpha_mode_recorded(tmp_path):
    res = run(tmp_path, "native_alpha")
    assert res.data["params"]["background"]["mode"] == "native_alpha"
    assert res.data["params"]["background"]["key_color"] is None


def test_process_pixel_art_style_uses_box_resample(tmp_path):
    res = run(tmp_path, params=ProcessParams(rows=2, cols=3, frames=6, art_style="pixel_art"))
    assert res.data["params"]["resample"] == "box"
    assert set(np.unique(res.sheet[..., 3])) <= {0, 255}


def test_process_rejects_frames_beyond_grid(tmp_path):
    with pytest.raises(PipelineError) as e:
        run(tmp_path, params=ProcessParams(rows=2, cols=3, frames=7))
    assert e.value.code == "invalid_params"


def test_process_rejects_too_small_image(tmp_path):
    raw = tmp_path / "raw.png"
    Image.new("RGB", (100, 100), (255, 0, 255)).save(raw)
    with pytest.raises(PipelineError) as e:
        process_sheet(raw, tmp_path / "out", PARAMS)
    assert e.value.code == "too_small"
