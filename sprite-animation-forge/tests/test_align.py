"""align stage tests (docs/11 section 4)."""

import numpy as np
import pytest
from fixtures.synthetic.make import make_sheet

from sprite_forge.pipeline.align import blank_frame, compose_sheet, place_frame
from sprite_forge.pipeline.chroma import remove_background
from sprite_forge.pipeline.components import filter_components
from sprite_forge.pipeline.measure import Layout, measure_frame
from sprite_forge.pipeline.scale import fit_scale
from sprite_forge.pipeline.split import crop, split_grid

LAYOUT = Layout()


def aligned(variant, rows=2, cols=3, anchor="feet", x_anchor="mass", pixel_art=False):
    sheet = make_sheet(variant, rows=rows, cols=cols, cell_size=(256, 256))
    rgba = remove_background(np.array(sheet.image)).rgba
    cells = split_grid(rgba[..., 3], rows, cols).cells
    filtered = [filter_components(crop(rgba, c).copy()).rgba for c in cells]
    measures = [measure_frame(f) for f in filtered]
    s = fit_scale(measures, LAYOUT, anchor, x_anchor)
    return [place_frame(f, m, s, LAYOUT, anchor, x_anchor, pixel_art) for f, m in zip(filtered, measures)]


def test_align_baseline_jitter_feet_land_on_baseline():
    placements = aligned("baseline_jitter")
    for p in placements:
        assert abs(p.anchor_out[1] - LAYOUT.baseline) <= 0.5
        assert abs(p.anchor_out[0] - LAYOUT.cell_w / 2) <= 0.5


def test_align_baseline_jitter_remeasured_feet_within_one_px():
    for p in aligned("baseline_jitter"):
        m = measure_frame(p.frame)
        assert abs(m.feet_y - LAYOUT.baseline) <= 1.0


def test_align_offsets_are_integers():
    for p in aligned("baseline_jitter"):
        assert all(isinstance(v, int) for v in p.offset)


def test_align_frames_have_cell_size_and_are_not_empty():
    for p in aligned("clean"):
        assert p.frame.shape == (128, 128, 4) and p.frame.dtype == np.uint8
        assert p.frame[..., 3].any()


def test_align_wide_attack_keeps_all_pixels_inside_the_cell():
    sheet = make_sheet("wide_attack", rows=2, cols=2, cell_size=(256, 256))
    rgba = remove_background(np.array(sheet.image)).rgba
    cells = split_grid(rgba[..., 3], 2, 2).cells
    filtered = [filter_components(crop(rgba, c).copy()).rgba for c in cells]
    measures = [measure_frame(f) for f in filtered]
    s = fit_scale(measures, LAYOUT, "feet", "mass")
    for f, m in zip(filtered, measures):
        p = place_frame(f, m, s, LAYOUT, "feet", "mass")
        resampled_pixels = (f[..., 3] >= 64).sum() * s * s
        assert (p.frame[..., 3] >= 64).sum() >= 0.9 * resampled_pixels  # nothing clipped away


def test_align_center_anchor_targets_cell_center():
    for p in aligned("clean", anchor="center", x_anchor="bbox"):
        assert abs(p.anchor_out[1] - 64) <= 0.5 and abs(p.anchor_out[0] - 64) <= 0.5


def test_align_paste_clips_instead_of_crashing_when_oversized():
    sheet = make_sheet("clean", rows=2, cols=2, cell_size=(256, 256))
    rgba = remove_background(np.array(sheet.image)).rgba
    cell = split_grid(rgba[..., 3], 2, 2).cells[0]
    f = crop(rgba, cell).copy()
    m = measure_frame(f)
    p = place_frame(f, m, 3.0, LAYOUT, "feet", "mass")
    assert p.frame.shape == (128, 128, 4)


def test_align_pixel_art_frames_have_binary_alpha():
    for p in aligned("clean", pixel_art=True):
        assert set(np.unique(p.frame[..., 3])) <= {0, 255}


def test_align_compose_sheet_is_a_single_row():
    frames = [blank_frame(LAYOUT) for _ in range(4)]
    frames[2][5, 7] = (1, 2, 3, 255)
    sheet = compose_sheet(frames)
    assert sheet.shape == (128, 512, 4)
    assert tuple(sheet[5, 2 * 128 + 7]) == (1, 2, 3, 255)


def test_align_is_deterministic():
    a = aligned("baseline_jitter")
    b = aligned("baseline_jitter")
    assert all(np.array_equal(x.frame, y.frame) and x.offset == y.offset for x, y in zip(a, b))
