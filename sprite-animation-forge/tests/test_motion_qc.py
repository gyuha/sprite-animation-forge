"""Motion quality QC items (QC-10 loop seam, QC-11 silhouette drift, QC-12 palette drift, QC-13 motion presence)
and the recovery recommendations built on them."""

import numpy as np
import pytest
from test_align_register import figure_sheet

from sprite_forge import prompt as pr
from sprite_forge import qc, recovery, schemas
from sprite_forge import qc_motion as qm
from sprite_forge.pipeline.process import ProcessParams, process_sheet


def blob(x, y=20, size=12, color=(200, 60, 60), canvas=64):
    a = np.zeros((canvas, canvas, 4), np.uint8)
    a[y:y + size, x:x + size] = (*color, 255)
    return a


# ---- pure metrics ----------------------------------------------------------------------------

def test_motion_qc_seam_ratio_is_one_for_a_closed_cycle_and_large_when_the_last_frame_jumps():
    closed = [blob(10), blob(14), blob(18), blob(14), blob(10 + 2)]
    assert qm.seam_ratio(closed) < 1.5
    broken = [blob(10), blob(12), blob(14), blob(16), blob(40)]  # the last frame is far from the first
    assert qm.seam_ratio(broken) > 2.0


def test_motion_qc_seam_ratio_is_undefined_for_static_or_too_short_sequences():
    assert qm.seam_ratio([blob(10)] * 4) is None
    assert qm.seam_ratio([blob(10), blob(30)]) is None


def test_motion_qc_silhouette_similarity_is_one_for_identical_frames_and_low_for_different_shapes():
    assert qm.silhouette_similarity([blob(10)] * 3) == pytest.approx(1.0)
    left = np.zeros((64, 64, 4), np.uint8)
    left[8:56, 4:30] = (200, 60, 60, 255)
    right = np.zeros((64, 64, 4), np.uint8)
    right[8:56, 34:60] = (200, 60, 60, 255)
    assert qm.silhouette_similarity([left, right]) < 0.6


def test_motion_qc_palette_intersection_detects_a_recoloured_frame():
    same = [blob(10), blob(20)]
    assert qm.palette_intersection(same) == pytest.approx(1.0)
    assert qm.palette_intersection([blob(10), blob(10, color=(20, 30, 220)), blob(10)]) < 0.2


def test_motion_qc_spread_is_zero_when_nothing_moves():
    assert qm.motion_spread([blob(10)] * 4) == pytest.approx(0.0)
    assert qm.motion_spread([blob(10), blob(30)]) > 0.01


@pytest.mark.parametrize("value,grade", [(1.99, "pass"), (2.01, "warn"), (3.49, "warn"), (3.51, "fail")])
def test_motion_qc_seam_grade_boundaries(value, grade):
    assert qc.qc10_grade(value) == grade


@pytest.mark.parametrize("value,grade", [(0.56, "pass"), (0.54, "warn"), (0.36, "warn"), (0.34, "fail")])
def test_motion_qc_silhouette_grade_boundaries(value, grade):
    assert qc.qc11_grade(value) == grade


@pytest.mark.parametrize("value,grade", [(0.81, "pass"), (0.79, "warn"), (0.61, "warn"), (0.59, "fail")])
def test_motion_qc_palette_grade_boundaries(value, grade):
    assert qc.qc12_grade(value) == grade


@pytest.mark.parametrize("value,grade", [(0.009, "pass"), (0.0079, "warn"), (0.0001, "warn"), (0.0, "warn")])
def test_motion_qc_static_grade_boundaries(value, grade):
    assert qc.qc13_grade(value) == grade


# ---- applicability ---------------------------------------------------------------------------

def test_motion_qc_matrix():
    walk, idle, death, fx = (qc.applicability(a) for a in ("walk", "idle", "death", "fx"))
    assert walk["QC-10"] == walk["QC-11"] == walk["QC-12"] == walk["QC-13"] == "apply" or walk["QC-11"] == "apply"
    assert idle["QC-13"] == "info"          # idle may legitimately barely move
    assert death["QC-10"] == "skip" and death["QC-11"] == "info"
    assert all(fx[k] == "skip" for k in ("QC-10", "QC-11", "QC-12", "QC-13"))
    assert qc.applicability("attack")["QC-11"] == "warn_only"


# ---- integration through process_sheet -------------------------------------------------------

def report(tmp_path, action="walk", loop=True, **sheet):
    figure_sheet(tmp_path / "raw.png", **sheet)
    res = process_sheet(tmp_path / "raw.png", tmp_path / "out", ProcessParams())
    return qc.run_qc(res, action=action, loop=loop), res


def item(rep, qid):
    return next(r for r in rep["results"] if r["id"] == qid)


def test_motion_qc_static_frames_warn_about_motion_presence(tmp_path):
    rep, _ = report(tmp_path, leg_h=[50] * 6)
    assert item(rep, "QC-13")["grade"] == "warn"  # warn only: it never blocks adoption on its own
    assert item(rep, "QC-10")["grade"] == "pass"  # no motion at all: the seam ratio is not judged


def test_motion_qc_a_swinging_cycle_passes_motion_presence_and_seam(tmp_path):
    rep, _ = report(tmp_path, leg_h=[30, 65, 100, 65, 30, 48], torso_dx=[0, 6, 12, 6, 0, 3])
    assert item(rep, "QC-13")["grade"] == "pass"
    assert item(rep, "QC-10")["grade"] == "pass" and item(rep, "QC-10")["value"] < 2.0


def test_motion_qc_a_loop_whose_last_frame_does_not_return_fails_the_seam(tmp_path):
    rep, _ = report(tmp_path, leg_h=[20, 36, 52, 68, 84, 100])
    assert item(rep, "QC-10")["grade"] in ("warn", "fail") and item(rep, "QC-10")["value"] > 2.0


def test_motion_qc_one_shot_actions_have_no_seam(tmp_path):
    rep, _ = report(tmp_path, action="attack", loop=False, leg_h=[20, 36, 52, 68, 84, 100])
    q10 = item(rep, "QC-10")
    assert q10["grade"] == "skipped" and q10["reason"] == "not_loop"


def test_motion_qc_idle_static_is_only_info_and_report_validates(tmp_path):
    rep, _ = report(tmp_path, action="idle", leg_h=[50] * 6)
    assert item(rep, "QC-13")["grade"] == "info"
    schemas.validate("qc-report", rep)


def test_motion_qc_breathe_idle_is_not_flagged_as_static():
    from sprite_forge.effects.breathe import breathe_frames
    from test_method_breathe import figure
    base, _ = figure()
    frames, _ = breathe_frames(base, 6)
    assert qm.motion_spread(frames) > 0.0  # it does move, however subtly


# ---- recovery --------------------------------------------------------------------------------

def fake_report(**fails):
    results = [{"id": f"QC-{i:02d}", "grade": "pass"} for i in (1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13)]  # QC-13 never fails
    for r in results:
        if r["id"] in fails:
            r["grade"] = "fail"
    return {"results": results, "recommendations": [], "status": "fail", "score": 50}


DATA = {"params": {"align": "register"}, "derived": {"scale_strategy_used": "fit"}, "scale_strategy_used": "fit"}


@pytest.mark.parametrize("qid,code", [("QC-10", "loop_closure"), ("QC-11", "identity_drift"),
                                      ("QC-12", "identity_drift")])
def test_motion_qc_recovery_recommends_regeneration_with_a_matching_prompt_code(qid, code):
    recs = recovery.recommend(fake_report(**{qid: True}), DATA)
    first = next(r for r in recs if r["qc_id"] == qid)
    assert first["type"] == "regenerate" and first["code"] == code and code in pr.RECOVERY_CODES


def test_motion_qc_static_motion_warning_triggers_no_recommendation():
    rep = fake_report()
    next(r for r in rep["results"] if r["id"] == "QC-13")["grade"] = "warn"
    assert [r for r in recovery.recommend(rep, DATA) if r["qc_id"] == "QC-13"] == []


def test_motion_qc_loop_closure_has_a_prompt_phrase_and_builds_a_valid_prompt():
    from sprite_forge import plan as plan_mod
    plan = plan_mod.build_plan("hero", ["walk"], view="side", art_style="project_native", has_reference=True, profile=None)
    text = pr.build_prompt(plan, {"identity": {}}, "walk", recovery=["loop_closure"]).text
    assert "last frame" in text.lower() and pr.validate_prompt(text) == []
