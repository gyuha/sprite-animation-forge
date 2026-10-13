"""Loop selection from a clip (docs/14 area C): slow walks, subject size drift, two cycles in one cut, held drawings, seam pop,
explicit windows. Clips are synthetic PNG frames (no ffmpeg): a walker on a key background whose legs and arms swing."""

import math

import numpy as np
import pytest
from sprite_forge import plan as plan_mod
from sprite_forge import video_loop as vl
from sprite_forge import video_sprite as vs
from sprite_forge.qc_motion import thumb

from sg_clips import BASE, H, KEY, W, clip, walker  # noqa: F401


def thumbs_of(paths):
    return [thumb(vs._rgba(p)) for p in paths]


def subject_heights(sheet, rows, cols, cell):
    arr = np.asarray(sheet.convert("RGB")).astype(int)
    out = []
    for k in range(rows * cols):
        r, c = divmod(k, cols)
        tile = arr[r * cell:(r + 1) * cell, c * cell:(c + 1) * cell]
        ys, xs = np.where(np.abs(tile - KEY).sum(axis=-1) > 60)
        if ys.size:
            out.append((ys.min(), ys.max(), cell))
    return out


# ---- slow walks ---------------------------------------------------------------------------------------------

def test_sg_video_loop_slow_walk_is_found_by_a_second_wider_search(tmp_path):
    paths = clip(tmp_path, 48, 46)  # almost one whole cycle in the clip: no seam fits the normal window
    thumbs = thumbs_of(paths)
    dist = vl.distance_matrix(thumbs)
    assert vl.select_loop(dist, 6)[1] != 46  # the plain search cannot name the cycle
    choice = vl.find_loop(dist, 6, thumbs)
    assert choice.research == "wider" and abs(choice.span - 46) <= 1


def test_sg_video_loop_a_clip_with_a_clean_cycle_is_not_searched_again(tmp_path):
    thumbs = thumbs_of(clip(tmp_path, 48, 12))
    choice = vl.find_loop(vl.distance_matrix(thumbs), 6, thumbs)
    assert choice.research is None and choice.span == 12 and choice.seam_ratio is not None and choice.seam_ratio < 0.2


# ---- size hold ----------------------------------------------------------------------------------------------

GROW = lambda i: 1.0 + 0.55 * i / 47  # noqa: E731  the walker comes toward the camera and grows by 55 %


def height_spread(sheet, n, cols, rows, cell):
    tops_bottoms = subject_heights(sheet, rows, cols, cell)[:n]
    heights = [b - t + 1 for t, b, _ in tops_bottoms]
    return (max(heights) - min(heights)) / np.mean(heights)


def test_sg_video_loop_size_hold_makes_the_subject_the_same_height_in_every_cell(tmp_path):
    paths = clip(tmp_path, 48, 12, scale=GROW)
    held, info = vs.build_raw_sheet(paths, 6, 2, 3, "#FF00FF", True, cell=128)
    free, _ = vs.build_raw_sheet(paths, 6, 2, 3, "#FF00FF", True, cell=128, size_hold=False)
    assert info["size_hold"]["applied"] is True and info["size_hold"]["max_ratio"] > 1.2
    assert height_spread(held, 6, 3, 2, 128) <= 0.03
    assert height_spread(free, 6, 3, 2, 128) > 0.10  # the contrast: without the hold the subject grows across the cut


def test_sg_video_loop_size_hold_widens_the_canvas_instead_of_cutting_the_crown(tmp_path):
    sheet, _ = vs.build_raw_sheet(clip(tmp_path, 48, 12, scale=GROW), 6, 2, 3, "#FF00FF", True, cell=128)
    for top, bottom, cell in subject_heights(sheet, 2, 3, 128)[:6]:
        assert top >= 1 and bottom <= cell - 2  # the head and the feet are inside every cell, none is touching the edge


def test_sg_video_loop_a_constant_size_clip_is_left_untouched(tmp_path):
    paths = clip(tmp_path, 48, 12)
    a, info = vs.build_raw_sheet(paths, 6, 2, 3, "#FF00FF", True, cell=128)
    b, _ = vs.build_raw_sheet(paths, 6, 2, 3, "#FF00FF", True, cell=128, size_hold=False)
    assert info["size_hold"]["applied"] is False and a.tobytes() == b.tobytes()


# ---- two cycles in one cut ----------------------------------------------------------------------------------

ALTERNATE = lambda i: 1.0 + 0.18 * ((i // 12) % 2)  # noqa: E731  every other cycle swings a little wider


def test_sg_video_loop_two_cycles_in_one_cut_are_suspected_and_counted_but_not_cut_on_the_pixels_word(tmp_path):
    thumbs = thumbs_of(clip(tmp_path, 60, 12, amp=ALTERNATE))
    dist = vl.distance_matrix(thumbs)
    choice = vl.find_loop(dist, 6, thumbs)
    assert choice.span == 24 and choice.cycles_suspected == 2  # cut as found, only reported


def test_sg_video_loop_a_declared_cycle_count_cuts_one_cycle(tmp_path):
    thumbs = thumbs_of(clip(tmp_path, 60, 12, amp=ALTERNATE))
    choice = vl.find_loop(vl.distance_matrix(thumbs), 6, thumbs, cycles=2)
    assert choice.span == 12 and choice.cycles_suspected == 2


def test_sg_video_loop_a_single_cycle_is_not_suspected(tmp_path):
    thumbs = thumbs_of(clip(tmp_path, 48, 12))
    assert vl.find_loop(vl.distance_matrix(thumbs), 6, thumbs).cycles_suspected in (None, 2)  # period 12 may hold 2 steps...
    assert vl.find_loop(vl.distance_matrix(thumbs), 6, thumbs, cycles=1).span == 12  # ... but cycles=1 is taken as said


# ---- held drawings ------------------------------------------------------------------------------------------

def test_sg_video_loop_a_clip_that_holds_each_drawing_for_several_frames_is_read_by_its_drawings(tmp_path):
    paths = clip(tmp_path, 72, 8, held=3)  # 24 drawings, three frames each
    sheet, info = vs.build_raw_sheet(paths, 6, 2, 3, "#FF00FF", True, cell=96)
    assert info["held"]["drawings"] == 24 and info["held"]["ratio"] >= 0.6
    pictures = {i // 3 for i in info["indices"]}
    assert len(pictures) == 6  # six different drawings, never two frames of the same one
    assert all(i % 3 == 0 for i in info["indices"])  # each picked at the start of its drawing


def test_sg_video_loop_a_clip_without_held_drawings_reports_none(tmp_path):
    _, info = vs.build_raw_sheet(clip(tmp_path, 48, 12), 6, 2, 3, "#FF00FF", True, cell=96)
    assert info["held"]["drawings"] == 48 and info["held"]["ratio"] < 0.1


# ---- seam pop -----------------------------------------------------------------------------------------------

def test_sg_video_loop_the_closing_seam_is_read_as_a_pop_ratio(tmp_path):
    thumbs = thumbs_of(clip(tmp_path, 48, 12))
    pop = vl.seam_pop(thumbs, 0, 12)
    assert pop is not None and pop < 1.5  # a clean loop closes as smoothly as any step
    broken = thumbs_of(clip(tmp_path, 48, 12, lift=lambda i: 60 * (i == 12)))  # the subject jumps for one frame at the seam
    assert vl.seam_pop(broken, 0, 12) > 3


def test_sg_video_loop_a_cut_whose_top_cannot_be_read_skips_the_seam_pop(tmp_path):
    thumbs = thumbs_of(clip(tmp_path, 48, 12, top_hidden=True))
    assert vl.seam_pop(thumbs, 0, 12) is None


# ---- explicit window ----------------------------------------------------------------------------------------

def test_sg_video_loop_an_explicit_window_wins_on_every_path(tmp_path):
    thumbs = thumbs_of(clip(tmp_path, 60, 12))
    dist = vl.distance_matrix(thumbs)
    assert 20 <= vl.find_loop(dist, 6, thumbs, min_len=20, max_len=30).span <= 30  # 24 (two cycles), not 12
    (tmp_path / "slow").mkdir()
    slow = thumbs_of(clip(tmp_path / "slow", 48, 46))
    assert vl.find_loop(vl.distance_matrix(slow), 6, slow, max_len=40).span <= 40  # the wider search keeps the cap


def test_sg_video_loop_plan_accepts_the_window_and_cycle_keys():
    plan = plan_mod.build_plan("hero", ["walk"], view="side", art_style="project_native", has_reference=True, profile=None,
                               overrides=plan_mod.parse_overrides(["walk.cycles=2", "walk.min_len=10", "walk.max_len=40"]))
    assert {k: plan["actions"]["walk"][k] for k in ("cycles", "min_len", "max_len")} == {"cycles": 2, "min_len": 10, "max_len": 40}
