"""components stage tests (docs/11 section 4)."""

import numpy as np
import pytest
from fixtures.synthetic.make import make_sheet

from sprite_forge.pipeline.chroma import remove_background
from sprite_forge.pipeline.components import default_merge_gap_px, filter_components
from sprite_forge.pipeline.split import crop, split_grid


def _cell_rgba(variant, k=0, cell_size=(256, 256)):
    sheet = make_sheet(variant, rows=2, cols=2, cell_size=cell_size)
    rgba = remove_background(np.array(sheet.image)).rgba
    cell = split_grid(rgba[..., 3], 2, 2).cells[k]
    return sheet, sheet.cells[k], crop(rgba, cell).copy(), cell


def _blank(h=200, w=200):
    return np.zeros((h, w, 4), dtype=np.uint8)


def _block(rgba, y0, y1, x0, x1, alpha=255):
    rgba[y0:y1, x0:x1] = (10, 20, 30, alpha)


def test_components_default_merge_gap():
    assert default_merge_gap_px(100) == 4
    assert default_merge_gap_px(615) == 12  # round(12.3)
    assert default_merge_gap_px(627) == 13


def test_components_specks_removed_in_largest_mode():
    sheet, truth, rgba, cell = _cell_rgba("specks")
    res = filter_components(rgba, "largest")
    assert res.kept == 1 and res.removed == 5
    assert res.removed_area == 5 * 9
    ys, xs = np.nonzero(res.rgba[..., 3])
    ox, oy = cell.rect[0], cell.rect[1]
    assert (xs.min() + ox, ys.min() + oy, xs.max() + 1 + ox, ys.max() + 1 + oy) == truth.bbox
    for x0, y0, x1, y1 in truth.extras["specks"]:
        assert not res.rgba[y0 - oy : y1 - oy, x0 - ox : x1 - ox, 3].any()


def test_components_detached_sword_kept_in_largest_mode():
    sheet, truth, rgba, cell = _cell_rgba("detached_sword", cell_size=(384, 384))
    res = filter_components(rgba, "largest")  # default gap for RH=384 is 8 >= 6
    assert res.kept == 2 and res.removed == 0
    sx0, sy0, sx1, sy1 = truth.extras["sword_bbox"]
    ox, oy = cell.rect[0], cell.rect[1]
    assert (res.rgba[sy0 - oy : sy1 - oy, sx0 - ox : sx1 - ox, 3] == 255).all()


def test_components_detached_sword_dropped_when_gap_exceeds_merge_gap():
    _, _, rgba, _ = _cell_rgba("detached_sword")
    res = filter_components(rgba, "largest", merge_gap_px=5)
    assert res.kept == 1 and res.removed == 1


def test_components_largest_keeps_main_and_drops_far_component():
    rgba = _blank()
    _block(rgba, 20, 120, 20, 120)  # main, 10000 px
    _block(rgba, 20, 40, 130, 135)  # 100 px = 1 % of main, gap 10
    _block(rgba, 150, 175, 150, 175)  # 625 px but far (gap 30)
    res = filter_components(rgba, "largest", merge_gap_px=12)
    assert res.kept == 2 and res.removed == 1
    assert res.rgba[160, 160, 3] == 0
    assert res.rgba[30, 132, 3] == 255
    assert res.main_area == 10000 and res.removed_area == 625


def test_components_largest_area_threshold_is_one_percent_of_main():
    rgba = _blank()
    _block(rgba, 20, 120, 20, 120)
    _block(rgba, 20, 29, 125, 136)  # 99 px < 1 % of 10000, adjacent
    res = filter_components(rgba, "largest", merge_gap_px=10)
    assert res.removed == 1


def test_components_largest_gap_boundary_is_inclusive():
    rgba = _blank()
    _block(rgba, 20, 120, 20, 120)
    _block(rgba, 40, 60, 125, 135)  # 5 empty columns between
    assert filter_components(rgba, "largest", merge_gap_px=5).removed == 0
    assert filter_components(rgba, "largest", merge_gap_px=4).removed == 1


def test_components_touching_bboxes_have_zero_gap():
    rgba = _blank()
    _block(rgba, 20, 120, 20, 120)
    _block(rgba, 50, 70, 120, 140)  # touches the main bbox
    assert filter_components(rgba, "largest", merge_gap_px=0).removed == 0


def test_components_uses_eight_connectivity():
    rgba = _blank()
    _block(rgba, 20, 40, 20, 40)
    _block(rgba, 40, 60, 40, 60)  # diagonal neighbour: one component with 8-connectivity
    res = filter_components(rgba, "all", min_area_px=1)
    assert res.kept == 1 and res.removed == 0


def test_components_mask_threshold_is_alpha_64():
    rgba = _blank()
    _block(rgba, 20, 60, 20, 60, alpha=63)
    res = filter_components(rgba, "all")
    assert res.kept == 0 and res.main_area == 0
    assert np.array_equal(res.rgba, rgba)  # nothing to clear
    _block(rgba, 20, 60, 20, 60, alpha=64)
    assert filter_components(rgba, "all").kept == 1


def test_components_all_mode_keeps_everything_above_min_area():
    rgba = _blank()
    _block(rgba, 10, 50, 10, 50)
    _block(rgba, 100, 104, 100, 104)  # 16 px: kept
    _block(rgba, 150, 153, 150, 155)  # 15 px: removed
    res = filter_components(rgba, "all", min_area_px=16)
    assert res.kept == 2 and res.removed == 1 and res.removed_area == 15
    assert res.rgba[101, 101, 3] == 255 and res.rgba[151, 151, 3] == 0


def test_components_all_mode_keeps_far_projectile_that_largest_drops():
    rgba = _blank()
    _block(rgba, 10, 90, 10, 90)
    _block(rgba, 150, 170, 150, 170)
    assert filter_components(rgba, "largest", merge_gap_px=8).removed == 1
    assert filter_components(rgba, "all").removed == 0


def test_components_all_mode_removes_specks_with_default_min_area():
    _, _, rgba, _ = _cell_rgba("specks")
    res = filter_components(rgba, "all")  # specks are 9 px < 16
    assert res.kept == 1 and res.removed == 5


def test_components_info_flag_when_removed_area_over_five_percent():
    rgba = _blank()
    _block(rgba, 20, 120, 20, 120)
    _block(rgba, 150, 165, 150, 165)  # 225 px = 2.25 %
    assert not filter_components(rgba, "largest", merge_gap_px=4).info_flag
    _block(rgba, 130, 150, 160, 185)  # +500 px, separate component
    assert filter_components(rgba, "largest", merge_gap_px=4).info_flag


def test_components_empty_cell_returns_unchanged_copy():
    rgba = _blank()
    res = filter_components(rgba, "largest")
    assert (res.kept, res.removed, res.removed_area, res.main_area) == (0, 0, 0, 0)
    assert res.rgba is not rgba
    assert not res.info_flag


def test_components_does_not_modify_input_and_keeps_rgb():
    rgba = _blank()
    _block(rgba, 10, 90, 10, 90)
    _block(rgba, 150, 170, 150, 170)
    before = rgba.copy()
    res = filter_components(rgba, "largest", merge_gap_px=4)
    assert np.array_equal(rgba, before)
    assert (res.rgba[160, 160, :3] == (10, 20, 30)).all()


def test_components_unknown_mode_raises():
    with pytest.raises(ValueError):
        filter_components(_blank(), "biggest")


def test_components_is_deterministic():
    _, _, rgba, _ = _cell_rgba("specks")
    assert np.array_equal(filter_components(rgba).rgba, filter_components(rgba).rgba)
