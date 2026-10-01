"""split stage tests (docs/11 section 4)."""

import numpy as np
from fixtures.synthetic.make import make_sheet

from sprite_forge.pipeline.chroma import remove_background
from sprite_forge.pipeline.split import (
    crop,
    ideal_boundaries,
    select_cells,
    snap_boundary,
    split_grid,
)


def _split(variant, rows=2, cols=2, cell_size=(256, 256)):
    sheet = make_sheet(variant, rows=rows, cols=cols, cell_size=cell_size)
    alpha = remove_background(np.array(sheet.image)).rgba[..., 3]
    return sheet, alpha, split_grid(alpha, rows, cols)


def _assert_within_six_percent(result, rows, cols, W, H):
    ideal_y, ideal_x = ideal_boundaries(rows, H), ideal_boundaries(cols, W)
    for y, iy in zip(result.row_boundaries, ideal_y):
        assert abs(y - iy) <= 0.06 * H
    for bounds in result.col_boundaries:
        for x, ix in zip(bounds, ideal_x):
            assert abs(x - ix) <= 0.06 * W


def test_split_ideal_boundaries():
    assert ideal_boundaries(3, 1254) == [0, 418, 836, 1254]
    assert ideal_boundaries(2, 1254) == [0, 627, 1254]
    assert ideal_boundaries(3, 100) == [0, 33, 67, 100]


def test_split_snap_gutter_containing_ideal_uses_run_centre():
    empty = np.zeros(1254, dtype=bool)
    empty[586:646] = True
    assert snap_boundary(empty, 627, 75) == (616, True)


def test_split_snap_picks_nearest_gutter_when_ideal_not_inside():
    empty = np.zeros(1000, dtype=bool)
    empty[420:440] = True  # centre 430, distance 70
    empty[560:564] = True  # centre 562, distance 62
    assert snap_boundary(empty, 500, 80) == (562, True)


def test_split_snap_without_gutter_returns_ideal_and_not_found():
    empty = np.zeros(1000, dtype=bool)
    empty[100:200] = True  # outside the window
    assert snap_boundary(empty, 500, 60) == (500, False)


def test_split_snap_clamps_long_run_into_window():
    empty = np.zeros(1000, dtype=bool)
    empty[500:1000] = True  # e.g. an empty cell: centre 750
    pos, found = snap_boundary(empty, 500, 60)
    assert found and pos == 560


def test_split_clean_boundaries_match_ground_truth():
    sheet, _, result = _split("clean", rows=2, cols=3)
    assert result.row_boundaries[0::2] == [0, 512]
    gap_top = max(c.bbox[3] for c in sheet.cells[:3])
    gap_bottom = min(c.bbox[1] for c in sheet.cells[3:])
    assert gap_top < result.row_boundaries[1] < gap_bottom
    for bounds in result.col_boundaries:
        assert all(abs(a - b) <= 1 for a, b in zip(bounds, sheet.col_edges))
    assert [c.rect for c in result.cells][0] == (0, 0, result.col_boundaries[0][1], result.row_boundaries[1])
    assert not any(c.gutter_missing for c in result.cells)


def test_split_cells_tile_the_sheet_row_major():
    sheet, alpha, result = _split("clean", rows=2, cols=3)
    assert [c.index for c in result.cells] == list(range(6))
    assert sum((x1 - x0) * (y1 - y0) for x0, y0, x1, y1 in (c.rect for c in result.cells)) == alpha.size
    assert (result.cells[4].row, result.cells[4].col) == (1, 1)


def test_split_shifted_gutters_within_six_percent_of_ideal():
    sheet, alpha, result = _split("shifted_gutters", rows=2, cols=3)
    _assert_within_six_percent(result, 2, 3, alpha.shape[1], alpha.shape[0])
    # snapped to the shifted gutters, not left on the ideal grid
    ideal = ideal_boundaries(3, alpha.shape[1])
    assert result.col_boundaries[0][1] != ideal[1]
    for c in result.cells:
        assert not c.empty and not c.gutter_missing


def test_split_shifted_gutters_cells_contain_their_character():
    sheet, _, result = _split("shifted_gutters", rows=2, cols=2)
    for truth, cell in zip(sheet.cells, result.cells):
        x0, y0, x1, y1 = cell.rect
        assert x0 <= truth.bbox[0] and truth.bbox[2] <= x1
        assert y0 <= truth.bbox[1] and truth.bbox[3] <= y1


def test_split_narrow_gutter_within_six_percent_of_ideal():
    sheet, alpha, result = _split("narrow_gutter", rows=2, cols=3)
    _assert_within_six_percent(result, 2, 3, alpha.shape[1], alpha.shape[0])
    for truth, cell in zip(sheet.cells, result.cells):
        x0, _, x1, _ = cell.rect
        assert x0 <= truth.bbox[0] and truth.bbox[2] <= x1  # no character is cut


def test_split_vertical_boundaries_are_computed_per_row_strip():
    alpha = np.zeros((400, 600), dtype=np.uint8)
    alpha[20:180, 20:250] = 255  # row 0 gutter 250..350 -> centre 300
    alpha[20:180, 350:580] = 255
    alpha[220:380, 20:200] = 255  # row 1 gutter 200..350 -> centre 275
    alpha[220:380, 350:580] = 255
    result = split_grid(alpha, 2, 2)
    assert result.row_boundaries == [0, 200, 400]
    assert result.col_boundaries == [[0, 300, 600], [0, 275, 600]]
    assert result.cells[0].rect == (0, 0, 300, 200)
    assert result.cells[2].rect == (0, 200, 275, 400)


def test_split_missing_gutter_keeps_ideal_boundary_and_flags_cells():
    alpha = np.full((400, 600), 255, dtype=np.uint8)
    result = split_grid(alpha, 2, 2)
    assert result.row_boundaries == [0, 200, 400]
    assert result.col_boundaries == [[0, 300, 600], [0, 300, 600]]
    assert all(c.gutter_missing for c in result.cells)


def test_split_missing_gutter_flags_only_the_two_neighbours_of_a_column_boundary():
    alpha = np.zeros((300, 900), dtype=np.uint8)
    alpha[:, 240:360] = 255  # fills the whole window of the first column boundary (ideal 300)
    result = split_grid(alpha, 1, 3)
    assert [c.gutter_missing for c in result.cells] == [True, True, False]


def test_split_empty_cell_is_ignored():
    sheet, alpha, result = _split("empty_cell", rows=2, cols=2)
    assert [c.empty for c in result.cells] == [False, False, False, True]
    assert [c.index for c in select_cells(result, 3)] == [0, 1, 2]
    _assert_within_six_percent(result, 2, 2, alpha.shape[1], alpha.shape[0])
    for truth, cell in zip(sheet.cells[:3], result.cells[:3]):
        assert cell.rect[0] <= truth.bbox[0] and truth.bbox[2] <= cell.rect[2]


def test_split_select_cells_takes_first_frames_in_reading_order():
    _, _, result = _split("clean", rows=2, cols=3)
    assert [c.index for c in select_cells(result, 4)] == [0, 1, 2, 3]
    assert len(select_cells(result, 6)) == 6


def test_split_crop_returns_cell_rect_view():
    _, alpha, result = _split("clean", rows=2, cols=2)
    cell = result.cells[3]
    x0, y0, x1, y1 = cell.rect
    assert crop(alpha, cell).shape == (y1 - y0, x1 - x0)


def test_split_is_deterministic():
    _, alpha, a = _split("shifted_gutters", rows=2, cols=3)
    assert split_grid(alpha, 2, 3) == a
