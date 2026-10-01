"""chroma stage tests (docs/11 section 4)."""

import numpy as np
import pytest
from fixtures.synthetic.make import make_sheet
from PIL import Image

from sprite_forge.pipeline import PipelineError
from sprite_forge.pipeline.chroma import (
    KEY_GREEN,
    KEY_MAGENTA,
    compute_alpha,
    despill,
    estimate_background,
    has_native_alpha,
    remove_background,
    resolve_key_color,
    validate_input,
)


def _arr(sheet):
    return np.array(sheet.image)


def test_chroma_estimates_vignetted_background():
    bg = estimate_background(_arr(make_sheet("model_like_bg"))[..., :3])
    assert np.linalg.norm(np.array(bg) - (250, 3, 250)) < 15


def test_chroma_model_like_corners_transparent_and_no_magenta_left():
    res = remove_background(_arr(make_sheet("model_like_bg")))
    h, w = res.rgba.shape[:2]
    assert res.mode == "chroma"
    assert np.linalg.norm(np.array(res.bg_color) - (250, 3, 250)) < 15
    for y, x in ((0, 0), (0, w - 1), (h - 1, 0), (h - 1, w - 1)):
        assert res.rgba[y, x, 3] == 0
    fg = res.rgba[res.rgba[..., 3] > 0].astype(int)
    assert len(fg) > 0
    assert (np.minimum(fg[:, 0], fg[:, 2]) - fg[:, 1]).max() <= 40


def test_chroma_clean_sheet_alpha_matches_ground_truth():
    sheet = make_sheet("clean")
    res = remove_background(_arr(sheet))
    ys, xs = np.nonzero(res.rgba[..., 3])
    for cell in sheet.cells:
        x0, y0, x1, y1 = cell.rect
        inside = (xs >= x0) & (xs < x1) & (ys >= y0) & (ys < y1)
        assert (xs[inside].min(), ys[inside].min(), xs[inside].max() + 1, ys[inside].max() + 1) == cell.bbox
    assert res.bg_distance_to_key == 0
    assert res.warnings == []


def test_chroma_ramp_boundaries():
    bg = (20, 100, 100)
    rgb = np.array([[[20 + d, 100, 100] for d in (0, 30, 31, 60, 89, 90, 200)]], dtype=np.uint8)
    alpha = compute_alpha(rgb, bg)[0]
    assert alpha[0] == 0 and alpha[1] == 0
    assert alpha[2] == 4  # 255 * 1 / 60 = 4.25
    assert alpha[3] == 128  # 127.5 rounds half up
    assert alpha[4] == 251
    assert alpha[5] == 255 and alpha[6] == 255


def test_chroma_ramp_uses_euclidean_distance():
    rgb = np.array([[[130, 100, 100], [118, 118, 118]]], dtype=np.uint8)  # d=30 and d~31.2
    alpha = compute_alpha(rgb, (100, 100, 100))[0]
    assert alpha[0] == 0
    assert alpha[1] > 0


def test_chroma_removes_enclosed_background_globally():
    arr = np.zeros((300, 300, 3), dtype=np.uint8)
    arr[:] = KEY_MAGENTA
    arr[50:250, 50:250] = (40, 90, 200)
    arr[120:180, 120:180] = KEY_MAGENTA  # closed hole
    res = remove_background(arr)
    assert res.rgba[150, 150, 3] == 0
    assert res.rgba[60, 60, 3] == 255


def test_chroma_despill_leaves_red_unchanged():
    rgba = np.zeros((7, 7, 4), dtype=np.uint8)
    rgba[2:5, 2:5] = (200, 40, 30, 255)
    out = despill(rgba, KEY_MAGENTA)
    assert (out[2:5, 2:5, :3] == (200, 40, 30)).all()


def test_chroma_despill_reduces_magenta_spill_on_edge_only():
    rgba = np.zeros((11, 11, 4), dtype=np.uint8)
    rgba[2:9, 2:9] = (230, 90, 200, 255)  # pinkish; interior is > 2 px from alpha 0
    out = despill(rgba, KEY_MAGENTA, edge_band_px=2)
    s = 200 - 90
    assert tuple(out[2, 2, :3]) == (230 - s, 90, 200 - s)
    assert tuple(out[5, 5, :3]) == (230, 90, 200)  # interior untouched


def test_chroma_despill_green_key_rule():
    rgba = np.zeros((7, 7, 4), dtype=np.uint8)
    rgba[2:5, 2:5] = (50, 200, 60, 255)
    out = despill(rgba, KEY_GREEN)
    assert tuple(out[3, 3, :3]) == (50, 60, 60)
    assert out[3, 3, 3] == 255


def test_chroma_key_conflict_pinkish_character_switches_to_green():
    sheet = make_sheet("pinkish_character")
    patch = sheet.cells[0].extras["pink_patch"]
    pink = tuple(int(v) for v in np.array(sheet.image)[patch[1], patch[0]])
    key, warnings = resolve_key_color([pink, (40, 90, 200)])
    assert key == KEY_GREEN and warnings == []


def test_chroma_key_no_conflict_keeps_magenta():
    key, warnings = resolve_key_color([(40, 90, 200), (60, 60, 60)])
    assert key == KEY_MAGENTA and warnings == []


def test_chroma_key_conflict_with_both_keys_keeps_magenta_with_warning():
    key, warnings = resolve_key_color([(230, 90, 200), (30, 220, 40)])
    assert key == KEY_MAGENTA
    assert len(warnings) == 1


def test_chroma_native_alpha_skips_keying():
    sheet = make_sheet("native_alpha")
    arr = _arr(sheet)
    assert has_native_alpha(arr)
    res = remove_background(arr)
    assert res.mode == "native_alpha"
    assert res.bg_color is None and res.key_color is None
    assert np.array_equal(res.rgba, arr)


def test_chroma_native_alpha_not_detected_for_rgb_or_opaque_border():
    assert not has_native_alpha(_arr(make_sheet("clean")))
    rgba = np.zeros((300, 300, 4), dtype=np.uint8)
    rgba[0, 0, 3] = 255
    assert not has_native_alpha(rgba)


def test_chroma_far_background_warns():
    arr = np.zeros((300, 300, 3), dtype=np.uint8)
    arr[:] = (0, 0, 0)
    arr[100:200, 100:200] = (255, 255, 255)
    res = remove_background(arr)
    assert res.warnings == ["bg_far_from_key"]
    assert res.rgba[150, 150, 3] == 255 and res.rgba[0, 0, 3] == 0


def test_chroma_background_median_ignores_foreground_on_border():
    arr = np.zeros((400, 400, 3), dtype=np.uint8)
    arr[:] = KEY_MAGENTA
    arr[0:4, 100:160] = (10, 10, 10)  # character touching the border
    assert estimate_background(arr) == (255.0, 0.0, 255.0)


def test_chroma_is_deterministic():
    arr = _arr(make_sheet("model_like_bg"))
    assert np.array_equal(remove_background(arr).rgba, remove_background(arr).rgba)


def test_chroma_validate_accepts_rgb_and_converts_palette_mode():
    img = Image.new("P", (300, 300))
    arr = validate_input(img, 1, 1)
    assert arr.shape == (300, 300, 3)


def test_chroma_validate_errors(tmp_path):
    with pytest.raises(PipelineError) as e:
        validate_input(Image.new("RGB", (255, 600)), 1, 1)
    assert e.value.code == "too_small"
    with pytest.raises(PipelineError) as e:
        validate_input(Image.new("RGB", (600, 600)), 7, 1)
    assert e.value.code == "cell_too_small"
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not a png")
    with pytest.raises(PipelineError) as e:
        validate_input(bad, 1, 1)
    assert e.value.code == "invalid_image"


def test_chroma_validate_reads_path(tmp_path):
    sheet = make_sheet("clean")
    path = tmp_path / "raw.png"
    sheet.save(path)
    assert validate_input(path, 2, 2).shape == (512, 512, 3)
