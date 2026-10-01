"""scale stage tests (docs/11 section 4)."""

import numpy as np
import pytest
from fixtures.synthetic.make import make_sheet

from sprite_forge.pipeline.chroma import remove_background
from sprite_forge.pipeline.components import filter_components
from sprite_forge.pipeline.measure import Layout, Measure, measure_frame
from sprite_forge.pipeline.scale import (
    ScaleProfile,
    choose_scale,
    fit_scale,
    overflow_px,
    preserve_scale,
    resample,
)
from sprite_forge.pipeline.split import crop, split_grid

LAYOUT = Layout()


def measures_of(variant, n=4):
    sheet = make_sheet(variant, rows=2, cols=2, cell_size=(256, 256))
    rgba = remove_background(np.array(sheet.image)).rgba
    split = split_grid(rgba[..., 3], 2, 2)
    return [measure_frame(filter_components(crop(rgba, c).copy()).rgba) for c in split.cells[:n]]


def synth_measure(bbox, feet_y=None, mass_cx=None):
    x0, y0, x1, y1 = bbox
    return Measure(bbox, feet_y if feet_y is not None else y1, y1, mass_cx or (x0 + x1) / 2, (x0 + x1) / 2)


def test_scale_fit_formula_on_hand_made_measures():
    # anchor (feet, bbox x): up=100, down=0 (excluded), side=40 -> min(110/100, 56/40)
    m = synth_measure((60, 10, 140, 110))
    assert fit_scale([m], LAYOUT, "feet", "bbox") == pytest.approx(1.1)
    # limited by the downward cape: down=20 -> 9/20
    m2 = synth_measure((60, 10, 140, 130), feet_y=110)
    assert fit_scale([m2], LAYOUT, "feet", "bbox") == pytest.approx(0.45)


def test_scale_fit_is_shared_by_taking_the_worst_frame():
    small = synth_measure((60, 10, 140, 110))
    tall = synth_measure((60, 0, 140, 110))  # up=110
    assert fit_scale([small, tall], LAYOUT, "feet", "bbox") == pytest.approx(1.0)
    assert fit_scale([small, None, tall], LAYOUT, "feet", "bbox") == pytest.approx(1.0)


def test_scale_fit_center_anchor_uses_half_cell_room():
    m = synth_measure((0, 0, 100, 100))  # center anchor at (50, 50): up=down=50, side=50
    # up room 64-8=56, down room 64-10=54, side room 56
    assert fit_scale([m], LAYOUT, "center", "bbox") == pytest.approx(54 / 50)


def test_scale_fit_without_frames_is_one():
    assert fit_scale([None], LAYOUT, "feet", "mass") == 1.0


def test_scale_fit_wide_attack_stays_inside_the_cell():
    measures = measures_of("wide_attack")
    s = fit_scale(measures, LAYOUT, "feet", "mass")
    for m in measures:
        assert not any(overflow_px(m, s, LAYOUT, "feet", "mass").values())


def test_scale_fit_wide_attack_is_smaller_than_bbox_centered_fit():
    """Anchor-relative room matters: the blade sticks out far to the right of the anchor."""
    measures = measures_of("wide_attack")
    s_anchor = fit_scale(measures, LAYOUT, "feet", "mass")
    m = measures[0]
    naive = (LAYOUT.cell_w / 2 - LAYOUT.margin_side) / (m.w / 2)  # as if centered on the bbox
    assert s_anchor < naive
    # bbox-centered placement of the same scale would be fine; anchor placement needs the room
    assert overflow_px(m, naive, LAYOUT, "feet", "mass")["right"] > 0


def test_scale_overflow_is_reported_not_clipped():
    m = synth_measure((0, 0, 200, 100))
    over = overflow_px(m, 1.0, LAYOUT, "feet", "bbox")
    assert over["left"] == 36 and over["right"] == 36 and over["top"] == 0 and over["bottom"] == 0
    assert overflow_px(m, 0.5, LAYOUT, "feet", "bbox") == {"left": 0, "top": 0, "right": 0, "bottom": 0}


def test_scale_preserve_formula():
    profile = ScaleProfile(norm_scale=131.1)
    assert preserve_scale(profile, 627) == pytest.approx(131.1 / 627, abs=1e-4)
    assert preserve_scale(profile, 655) == pytest.approx(0.2, abs=1e-3)


def test_scale_choose_preserve_uses_profile_and_accepts_dict():
    measures = measures_of("clean")
    for profile in (ScaleProfile(norm_scale=100.0), {"norm_scale": 100.0, "character": "hero"}):
        choice = choose_scale("preserve", measures, LAYOUT, "feet", "mass", profile, 400)
        assert choice.strategy == "preserve" and choice.scale == pytest.approx(0.25) and not choice.warnings


def test_scale_choose_preserve_without_profile_falls_back_to_fit():
    measures = measures_of("clean")
    choice = choose_scale("preserve", measures, LAYOUT, "feet", "mass", None, 400)
    assert choice.strategy == "fit"
    assert choice.warnings == ["no_scale_profile"]
    assert choice.scale == fit_scale(measures, LAYOUT, "feet", "mass")


def test_scale_choose_rejects_unknown_strategy():
    with pytest.raises(ValueError):
        choose_scale("stretch", [], LAYOUT, "feet", "mass")


def test_scale_resample_lanczos_has_no_key_color_fringe():
    img = np.zeros((40, 40, 4), dtype=np.uint8)
    img[:] = (255, 0, 255, 0)  # transparent pixels carry the key color
    img[10:30, 10:30] = (20, 200, 20, 255)
    out = resample(img, 0.5, pixel_art=False)
    assert out.shape == (20, 20, 4)
    visible = out[out[..., 3] > 0]
    assert visible[:, 0].max() <= 25 and visible[:, 2].max() <= 25  # still green, no pink


def test_scale_resample_pixel_art_binarises_alpha():
    img = np.zeros((40, 40, 4), dtype=np.uint8)
    img[10:25, 10:25] = (20, 20, 200, 255)
    out = resample(img, 0.7, pixel_art=True)
    assert set(np.unique(out[..., 3])) <= {0, 255}


def test_scale_resample_size_rounds_half_up_min_one():
    img = np.full((5, 5, 4), 255, dtype=np.uint8)
    assert resample(img, 0.5, False).shape[:2] == (3, 3)  # 2.5 -> 3
    assert resample(img, 0.01, False).shape[:2] == (1, 1)
