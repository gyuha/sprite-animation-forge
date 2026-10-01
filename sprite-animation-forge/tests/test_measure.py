"""measure stage tests (docs/11 section 4)."""

import numpy as np
import pytest
from fixtures.synthetic.make import make_sheet

from sprite_forge.pipeline.chroma import remove_background
from sprite_forge.pipeline.components import filter_components
from sprite_forge.pipeline.measure import Layout, measure_frame
from sprite_forge.pipeline.split import crop, split_grid


def measured(variant, k=0, cell_size=(256, 256)):
    """(truth Cell, Measure in cell-local px, filtered cell rgba, cell rect origin)."""
    sheet = make_sheet(variant, rows=2, cols=2, cell_size=cell_size)
    rgba = remove_background(np.array(sheet.image)).rgba
    cell = split_grid(rgba[..., 3], 2, 2).cells[k]
    filtered = filter_components(crop(rgba, cell).copy(), "largest").rgba
    return sheet.cells[k], measure_frame(filtered), filtered, cell.rect[:2]


def test_measure_bbox_matches_ground_truth():
    truth, m, _, (ox, oy) = measured("clean")
    assert (m.bbox[0] + ox, m.bbox[1] + oy, m.bbox[2] + ox, m.bbox[3] + oy) == truth.bbox
    assert m.w == truth.bbox[2] - truth.bbox[0] and m.h == truth.bbox[3] - truth.bbox[1]


def test_measure_feet_line_matches_ground_truth_feet():
    truth, m, _, (ox, oy) = measured("clean")
    assert m.feet_y + oy == truth.feet[1]
    assert m.feet_y_strict + oy == truth.feet[1]


def test_measure_weak_feet_line_ignores_thin_blade_tip():
    # measure the unfiltered cell: the component filter would already delete the 1 px tip
    sheet = make_sheet("thin_below_feet", rows=2, cols=2, cell_size=(256, 256))
    rgba = remove_background(np.array(sheet.image)).rgba
    cell = split_grid(rgba[..., 3], 2, 2).cells[0]
    truth, (ox, oy) = sheet.cells[0], cell.rect[:2]
    m = measure_frame(crop(rgba, cell))
    assert truth.bbox[3] == truth.feet[1] + 12  # the 1 px tip is inside the bbox...
    assert m.bbox[3] + oy == truth.bbox[3]
    assert m.feet_y + oy == truth.feet[1]  # ...but feet_y skips it
    assert m.feet_y_strict + oy == truth.feet[1]


def test_measure_strict_line_is_not_below_weak_line():
    for variant in ("clean", "thin_below_feet", "wide_attack"):
        _, m, _, _ = measured(variant)
        assert m.feet_y_strict <= m.feet_y <= m.bbox[3]


def test_measure_x_anchor_bbox_is_bbox_center():
    truth, m, _, (ox, _) = measured("clean")
    assert m.anchor_point("feet", "bbox")[0] == m.bbox_cx
    assert m.bbox_cx + ox == pytest.approx((truth.bbox[0] + truth.bbox[2]) / 2)


def test_measure_x_anchor_feet_is_between_the_legs():
    truth, m, _, (ox, _) = measured("clean")
    assert m.anchor_point("feet", "feet")[0] + ox == pytest.approx(truth.feet[0], abs=1.0)


def test_measure_x_anchor_mass_is_centroid_of_mask():
    _, m, rgba, _ = measured("clean")
    xs = np.nonzero(rgba[..., 3] >= 64)[1]
    assert m.anchor_point("feet", "mass")[0] == pytest.approx(xs.mean() + 0.5)


def test_measure_x_anchors_differ_on_asymmetric_character():
    _, m, _, _ = measured("asymmetric_right")
    xs = {m.anchor_point("feet", x)[0] for x in ("mass", "feet", "bbox")}
    assert len(xs) == 3
    assert m.mass_cx > m.feet_cx  # staff on the right pulls the mass right


def test_measure_y_anchor_variants():
    _, m, _, _ = measured("clean")
    assert m.anchor_point("feet", "mass")[1] == m.feet_y
    assert m.anchor_point("bottom", "mass")[1] == m.bbox[3]
    assert m.anchor_point("center", "mass")[1] == m.bbox_cy


def test_measure_empty_cell_returns_none():
    assert measure_frame(np.zeros((50, 50, 4), dtype=np.uint8)) is None


def test_measure_unknown_anchor_rejected():
    _, m, _, _ = measured("clean")
    with pytest.raises(ValueError):
        m.anchor_point("head", "mass")
    with pytest.raises(ValueError):
        m.anchor_point("feet", "left")


def test_measure_layout_baseline_is_cell_minus_bottom_margin():
    layout = Layout()
    assert layout.baseline == 118
    assert layout.target("feet") == (64, 118)
    assert layout.target("center") == (64, 64)
    assert Layout(cell_h=256, margin_bottom=20).baseline == 236
