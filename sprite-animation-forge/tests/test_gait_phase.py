"""QC-14 gait phase: a walk whose frames do not advance the stride evenly (docs/06, forge task #41).

The value compares the walk's leg signal (``video_gait.leg_signal``), scaled to 0..1, with the shape an evenly timed cycle
draws (side: |cos|, front/back: |sin|), at the best cyclic shift. 0 = even steps; ~1 = a stalled or shuffled cycle."""

import numpy as np
import pytest
from test_align_register import figure_sheet

from sprite_forge import prompt as pr
from sprite_forge import qc, recovery, schemas
from sprite_forge import qc_motion as qm
from sprite_forge.pipeline.process import ProcessParams, process_sheet

CANVAS = 128


def side_walker(spreads):
    """Side view: torso + two legs whose feet are ``d`` px either side of the centre (leg width = 2d + 4)."""
    frames = []
    for d in spreads:
        a = np.zeros((CANVAS, CANVAS, 4), np.uint8)
        cx = CANVAS // 2
        a[10:70, cx - 10:cx + 10] = (200, 60, 60, 255)            # head + torso
        a[70:110, cx - d - 2:cx - d + 2] = (40, 40, 160, 255)     # leg 1
        a[70:110, cx + d - 2:cx + d + 2] = (40, 40, 160, 255)     # leg 2
        frames.append(a)
    return frames


def front_walker(lifts):
    """Front view: two legs side by side; ``(left, right)`` = how far each foot is lifted off the ground (px)."""
    frames = []
    for left, right in lifts:
        a = np.zeros((CANVAS, CANVAS, 4), np.uint8)
        cx = CANVAS // 2
        a[10:70, cx - 14:cx + 14] = (200, 60, 60, 255)
        a[70:110 - left, cx - 12:cx - 4] = (40, 40, 160, 255)
        a[70:110 - right, cx + 4:cx + 12] = (40, 40, 160, 255)
        frames.append(a)
    return frames


EVEN_SIDE = [20, 10, 10, 20, 10, 10]                                 # |cos| at 0, 60, 120 ... degrees
EVEN_FRONT = [(0, 0), (0, 13), (0, 13), (0, 0), (13, 0), (13, 0)]    # |sin|: one foot up, then the other

# Leg signals of the walks generated with prompt action_prompt@4 (sprites/, 2026-10-15). The user judged all seven
# unnatural by eye; the eighth (green up) was judged natural and its legs barely move, so there is no gait to read.
RECORDED_UNNATURAL = {
    "pink-2 side": ("side", [0.495, 0.376, 0.369, 0.532, 0.38, 0.505]),
    "green right": ("side", [0.489, 0.333, 0.304, 0.489, 0.341, 0.4]),
    "pink right 002": ("side", [0.491, 0.339, 0.306, 0.5, 0.275, 0.409]),
    "pink right 001": ("side", [0.436, 0.394, 0.297, 0.5, 0.34, 0.294]),
    "pink up": ("front", [0.099, 0.018, 0.009, 0.091, 0.036, 0.091]),
    "green down": ("front", [0.065, 0.044, 0.065, 0.087, 0.044, 0.065]),
    "pink down": ("front", [0.018, 0.054, 0.018, 0.018, 0.055, 0.009]),
}
RECORDED_GREEN_UP = ("front", [0.087, 0.067, 0.065, 0.087, 0.067, 0.087])


# ---- the metric ------------------------------------------------------------------------------

def test_gait_phase_an_evenly_timed_side_walk_scores_zero():
    assert qm.gait_phase_deviation(side_walker(EVEN_SIDE), "side") == pytest.approx(0.0, abs=0.05)


def test_gait_phase_an_evenly_timed_front_walk_scores_zero():
    assert qm.gait_phase_deviation(front_walker(EVEN_FRONT), "front") == pytest.approx(0.0, abs=0.05)


def test_gait_phase_an_even_walk_that_starts_elsewhere_in_the_cycle_still_scores_zero():
    shifted = EVEN_SIDE[2:] + EVEN_SIDE[:2]
    assert qm.gait_phase_deviation(side_walker(shifted), "side") == pytest.approx(0.0, abs=0.05)


def test_gait_phase_a_last_frame_drawn_as_a_contact_pose_is_far_off():
    stalled = [20, 10, 10, 20, 10, 19]  # frame 6 back at full stride: two contacts in a row at the loop seam
    assert qm.gait_phase_deviation(side_walker(stalled), "side") >= 0.45


def test_gait_phase_two_frames_with_both_feet_down_in_a_row_is_far_off():
    stall = [(0, 0), (0, 13), (0, 0), (0, 0), (13, 0), (0, 0)]  # a foot is up in one frame of three
    assert qm.gait_phase_deviation(front_walker(stall), "front") >= 0.45


def test_gait_phase_every_recorded_unnatural_walk_fails():
    for name, (view, signal) in RECORDED_UNNATURAL.items():
        assert qm.gait_phase_from_signal(signal, view) >= 0.45, name


def test_gait_phase_the_recorded_walk_whose_legs_barely_move_is_not_read():
    view, signal = RECORDED_GREEN_UP
    assert qm.gait_phase_from_signal(signal, view) is None


def test_gait_phase_a_body_without_swinging_legs_or_too_few_frames_is_not_read():
    assert qm.gait_phase_deviation(side_walker([12] * 6), "side") is None
    assert qm.gait_phase_deviation(side_walker([20, 10, 20]), "side") is None
    blank = np.zeros((CANVAS, CANVAS, 4), np.uint8)
    assert qm.gait_phase_deviation([*side_walker(EVEN_SIDE[:5]), blank], "side") is None


@pytest.mark.parametrize("value,grade", [(0.29, "pass"), (0.30, "warn"), (0.44, "warn"), (0.45, "fail"), (0.9, "fail")])
def test_gait_phase_grade_boundaries(value, grade):
    assert qc.qc14_grade(value) == grade


# ---- where QC-14 applies ---------------------------------------------------------------------

def test_gait_phase_applies_to_walk_only():
    assert qc.applicability("walk")["QC-14"] == "warn_only"  # until recalibrated: it failed a walk judged natural (task #42)
    for action in ("idle", "run", "attack", "jump", "death", "fx"):
        assert qc.applicability(action)["QC-14"] == "skip", action


@pytest.mark.parametrize("direction,view", [("right", "side"), ("left", "side"), ("down", "front"), ("up", "front")])
def test_gait_phase_view_follows_the_direction(direction, view):
    assert qc.gait_view(direction) == view


def test_gait_phase_item_results():
    bad = side_walker([20, 10, 10, 20, 10, 19])
    res = qc.qc14(bad, "walk", True, "side")
    assert res["id"] == "QC-14" and res["grade"] == "fail" and res["limit"] == {"warn": 0.30, "fail": 0.45}
    assert res["view"] == "side" and len(res["signal"]) == 6
    assert qc.qc14(side_walker(EVEN_SIDE), "walk", True, "side")["grade"] == "pass"
    assert qc.qc14(bad, "walk", False, "side") == {"id": "QC-14", "grade": "skipped", "reason": "not_loop"}
    assert qc.qc14(bad, "run", True, "side")["reason"] == "not_applicable"
    assert qc.qc14(bad, "walk", True, None)["reason"] == "no_view"
    assert qc.qc14(side_walker([12] * 6), "walk", True, "side")["reason"] == "no_gait"


def test_gait_phase_is_in_the_report_and_the_report_validates(tmp_path):
    figure_sheet(tmp_path / "raw.png", leg_h=[30, 65, 100, 65, 30, 48])
    res = process_sheet(tmp_path / "raw.png", tmp_path / "out", ProcessParams())
    rep = qc.run_qc(res, action="walk", gait_view="side")
    item = next(r for r in rep["results"] if r["id"] == "QC-14")
    assert item["grade"] in ("pass", "warn", "fail", "skipped")
    schemas.validate("qc-report", rep)
    without_view = qc.run_qc(res, action="walk")
    assert next(r for r in without_view["results"] if r["id"] == "QC-14")["reason"] == "no_view"


# ---- recovery --------------------------------------------------------------------------------

def test_gait_phase_failure_recommends_regeneration_with_the_gait_phase_code():
    results = [{"id": f"QC-{i:02d}", "grade": "pass"} for i in (1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13)]
    results.append({"id": "QC-14", "grade": "fail"})
    rep = {"results": results, "recommendations": [], "status": "fail", "score": 75}
    recs = recovery.recommend(rep, {"params": {"align": "register"}, "derived": {"scale_strategy_used": "fit"}})
    first = next(r for r in recs if r["qc_id"] == "QC-14")
    assert first["type"] == "regenerate" and first["code"] == "gait_phase" and "gait_phase" in pr.RECOVERY_CODES


def test_gait_phase_a_warning_alone_recommends_nothing():
    results = [{"id": "QC-14", "grade": "warn"}]
    recs = recovery.recommend({"results": results, "recommendations": [], "status": "warn", "score": 92}, {"params": {}, "derived": {}})
    assert [r for r in recs if r["qc_id"] == "QC-14"] == []


def test_gait_phase_process_reads_the_walk_from_its_direction(tmp_path, forge, raw_sheet):
    import json
    forge.ok("init", "hero")
    forge.ok("plan", "hero", "--actions", "walk")  # single direction: right (side view)
    forge.ok("import-raw", "hero", "walk", raw_sheet)
    forge.ok("process", "hero", "walk")
    rep = json.loads((forge.root / "hero/walk/attempts/001/qc-report.json").read_text())
    item = next(r for r in rep["results"] if r["id"] == "QC-14")
    assert item.get("reason") != "no_view"
    assert item.get("view", "side") == "side"


# ---- the evenly timed walk prompt (action_prompt@5) ------------------------------------------

def _prompts():
    from test_prompt import PROFILE, SNAP_DIR, side_plan, topdown_plan
    return PROFILE, SNAP_DIR, side_plan, topdown_plan


def test_gait_phase_walk_prompt_asks_for_evenly_timed_steps_with_sides_named():
    profile, _, side_plan, _ = _prompts()
    res = pr.build_prompt(side_plan("walk"), profile, "walk")
    text = res.text
    assert "one sixth of the cycle" in text
    assert "not the same pose as frame 1" in text
    assert "they are not copies" in text
    assert "left foot forward" in text and "right arm forward" in text
    assert "passing:" not in text  # the old 1/8-1/8-2/8 sequence
    assert "Frame 6 leads into frame 1 one even step later, just as frame 3 leads into frame 4." in text
    assert "The last frame must flow seamlessly back into frame 1." not in text
    assert res.template_version == pr.GAIT_PROMPT_VERSION and pr.validate_prompt(text) == []  # @5 + the gait guide (task #42)


def test_gait_phase_walk_prompt_is_the_same_in_front_and_back_views():
    profile, _, _, topdown_plan = _prompts()
    for direction in ("down", "up"):
        text = pr.build_prompt(topdown_plan("walk"), profile, "walk", direction).text
        assert "one sixth of the cycle" in text and "they are not copies" in text, direction


def test_gait_phase_run_prompt_is_unchanged():
    profile, snap_dir, side_plan, _ = _prompts()
    before = (snap_dir / "run_side_action_prompt_4.txt").read_text(encoding="utf-8")
    assert pr.build_prompt(side_plan("run"), profile, "run").text == before


def test_gait_phase_other_loops_keep_the_generic_loop_line():
    profile, _, side_plan, _ = _prompts()
    assert "The last frame must flow seamlessly back into frame 1." in pr.build_prompt(side_plan("idle"), profile, "idle").text


def test_gait_phase_walk_with_another_frame_count_keeps_the_general_rule():
    profile, _, side_plan, _ = _prompts()
    plan = side_plan("walk")
    plan["actions"]["walk"]["frames"] = 8
    plan["actions"]["walk"]["grid"] = "2x4"
    text = pr.build_prompt(plan, profile, "walk").text
    assert "8 evenly spaced poses covering one full walk cycle." in text and "one sixth" not in text


def test_gait_phase_recovery_phrase_builds_a_valid_prompt():
    profile, _, side_plan, _ = _prompts()
    text = pr.build_prompt(side_plan("walk"), profile, "walk", recovery=["gait_phase"]).text
    assert "did not advance the walk evenly" in text and pr.validate_prompt(text) == []


def test_gait_phase_never_fails_a_walk_on_its_own_until_recalibrated(tmp_path):
    """Task #42 UAT: QC-14 scored 0.55 (fail) on the one guided walk the user judged natural, so for now it only warns:
    the value and limits stay in the report, a fail-level value is recorded as warn and recommends no regeneration."""
    bad = side_walker([20, 10, 10, 20, 10, 19])
    capped = qc.qc14(bad, "walk", True, "side", "warn_only")
    assert capped["grade"] == "warn" and capped["value"] >= 0.45 and capped["limit"] == {"warn": 0.30, "fail": 0.45}
    assert qc.qc14(bad, "walk", True, "side")["grade"] == "fail"  # the full grade is one mode switch away
    assert qc.qc14(side_walker(EVEN_SIDE), "walk", True, "side", "warn_only")["grade"] == "pass"
