"""QC engine tests (docs/06 sections 2-4, docs/11 section 4 'qc' row)."""

import copy
import json

import numpy as np
import pytest
from fixtures.synthetic.make import make_sheet

from sprite_forge import qc
from sprite_forge.pipeline.process import ProcessParams, process_sheet
from sprite_forge.pipeline.scale import ScaleProfile

CW = 128


def rect_frame(left=40, right=80, top=20, bottom=118, alpha=255):
    f = np.zeros((128, 128, 4), np.uint8)
    f[top:bottom, left:right] = (200, 50, 50, alpha)
    return f


def record(i, h=100, empty=False, cell=(0, 0, 256, 256), bbox="auto", gutter_missing=False, overflow=None):
    if bbox == "auto":
        bbox = None if empty else [50, 50, 100, 50 + h]
    return {"index": i, "cell": list(cell), "empty": empty, "gutter_missing": gutter_missing,
            "bbox": bbox, "overflow": overflow or {"left": 0, "top": 0, "right": 0, "bottom": 0}}


def make_data(records, bg=10.0, x_anchor="mass", scale=1.0):
    return {"params": {"cell": {"w": CW, "h": 128}, "x_anchor": x_anchor},
            "derived": {"baseline_y": 118, "scale": scale, "bg_distance_to_key": bg, "frames": records}}


def distinct_frames(n):
    """Frames with clearly different shapes (large dHash distances)."""
    out = []
    for i in range(n):
        f = np.zeros((128, 128, 4), np.uint8)
        if i % 2 == 0:
            f[20:118, 20:50] = (200, 50, 50, 255)
            f[60:118, 90:120] = (30, 30, 30, 255)
        else:
            f[20:60, 70:120] = (30, 160, 30, 255)
            f[100:118, 10:100] = (250, 250, 20, 255)
        out.append(f)
    return out


def run(records, frames, action="walk", **kw):
    return qc.run_qc(make_data(records, **{k: kw.pop(k) for k in ("bg", "x_anchor", "scale") if k in kw}),
                     frames, action, **kw)


def grade(report, qid):
    return next(r for r in report["results"] if r["id"] == qid)["grade"]


def good(n=4):
    return [record(i) for i in range(n)], [rect_frame() for _ in range(n)]


# --- QC-01 -------------------------------------------------------------------------------------

def test_qc01_raw_band_boundary():
    # bbox x0 == cell x0 + 2 is just outside the 2 px band; +1 is inside
    frames = [rect_frame()]
    assert grade(run([record(0, bbox=[2, 50, 100, 150])], frames), "QC-01") == "pass"
    assert grade(run([record(0, bbox=[1, 50, 100, 150])], frames), "QC-01") == "fail"


def test_qc01_raw_band_right_bottom_boundary():
    frames = [rect_frame()]
    assert grade(run([record(0, bbox=[50, 50, 254, 254])], frames), "QC-01") == "pass"
    assert grade(run([record(0, bbox=[50, 50, 255, 200])], frames), "QC-01") == "fail"
    assert grade(run([record(0, bbox=[50, 50, 200, 255])], frames), "QC-01") == "fail"


def test_qc01_gutter_missing_fails():
    rep = run([record(0, gutter_missing=True)], [rect_frame()])
    assert grade(rep, "QC-01") == "fail" and rep["checks"]["edge_touch"] is True


def test_qc01_output_overflow_fails():
    over = {"left": 0, "top": 0, "right": 3, "bottom": 0}
    rep = run([record(0, overflow=over)], [rect_frame()])
    assert grade(rep, "QC-01") == "fail"
    assert next(r for r in rep["results"] if r["id"] == "QC-01")["output_frames"] == [0]


def test_qc01_output_edge_pixel_boundary():
    inside = rect_frame(left=1, right=80)       # touches nothing: column 0 empty
    touching = rect_frame(left=0, right=80)     # column 0 hit
    assert grade(run([record(0)], [inside]), "QC-01") == "pass"
    assert grade(run([record(0)], [touching]), "QC-01") == "fail"
    assert grade(run([record(0)], [rect_frame(bottom=128)]), "QC-01") == "fail"


# --- QC-02 -------------------------------------------------------------------------------------

def qc02_for(heights, action="walk"):
    recs = [record(i, h=h) for i, h in enumerate(heights)]
    return run(recs, [rect_frame() for _ in heights], action)


def test_qc02_fail_boundary():
    # median 100: spread 10 -> 0.10 (not > 0.10), spread 11 -> 0.11
    assert grade(qc02_for([100, 100, 100, 110]), "QC-02") == "warn"
    assert grade(qc02_for([100, 100, 100, 111]), "QC-02") == "fail"


def test_qc02_warn_boundary():
    assert grade(qc02_for([100, 100, 100, 105]), "QC-02") == "pass"
    assert grade(qc02_for([100, 100, 100, 106]), "QC-02") == "warn"


def test_qc02_action_profile_warns_only_above_020():
    assert grade(qc02_for([100, 100, 100, 120], "attack"), "QC-02") == "pass"
    assert grade(qc02_for([100, 100, 100, 121], "attack"), "QC-02") == "warn"
    assert grade(qc02_for([100, 100, 100, 180], "attack"), "QC-02") == "warn"  # never fail


def test_qc02_ignores_empty_frames():
    recs = [record(0), record(1, empty=True), record(2)]
    rep = run(recs, [rect_frame(), np.zeros((128, 128, 4), np.uint8), rect_frame()])
    assert next(r for r in rep["results"] if r["id"] == "QC-02")["value"] == 0.0


# --- QC-03 / QC-04 ----------------------------------------------------------------------------

def qc03_for(bottom):
    frames = [rect_frame(), rect_frame(), rect_frame(bottom=bottom)]
    return run([record(i) for i in range(3)], frames)


def test_qc03_boundaries():
    # baseline 118: deviation 2 -> pass, 3 -> warn (> 2), 4 -> fail (> 3)
    assert grade(qc03_for(116), "QC-03") == "pass"
    assert grade(qc03_for(115), "QC-03") == "warn"
    assert grade(qc03_for(114), "QC-03") == "fail"
    assert grade(qc03_for(122), "QC-03") == "fail"


def test_qc03_uses_strict_threshold_not_weak():
    # a 1-px-thick line below the body moves feet_y/bbox but not feet_y_strict
    f = rect_frame()
    f[118:122, 60] = (200, 50, 50, 255)
    rep = run([record(i) for i in range(2)], [rect_frame(), f])
    assert grade(rep, "QC-03") == "pass"
    assert rep["per_frame"][1]["feet_y_strict"] == 118


def qc04_for(shift, x_anchor="mass"):
    frames = [rect_frame(), rect_frame(), rect_frame(left=40 + shift, right=80 + shift)]
    return run([record(i) for i in range(3)], frames, x_anchor=x_anchor)


def test_qc04_boundary_is_008_cw():
    # limit 10.24 px; measured against the median x
    assert grade(qc04_for(10), "QC-04") == "pass"
    assert grade(qc04_for(11), "QC-04") == "warn"


def test_qc04_uses_independent_metric():
    # tall body with a wide foot band: mass_cx and feet_cx differ; x_anchor picks the other one
    f = rect_frame(left=40, right=60)
    f[98:118, 60:100] = (200, 50, 50, 255)
    r_mass = run([record(0)], [f], x_anchor="mass")["per_frame"][0]["x_metric"]
    r_feet = run([record(0)], [f], x_anchor="feet")["per_frame"][0]["x_metric"]
    assert r_mass != r_feet and r_mass > 60  # feet_cx (band lies mostly right)


def test_qc04_info_for_action_profile():
    rep = run([record(i) for i in range(3)],
              [rect_frame(), rect_frame(), rect_frame(left=80, right=120)], "attack")
    assert grade(rep, "QC-04") == "info"


# --- QC-05 -------------------------------------------------------------------------------------

def test_qc05_boundary():
    cell_area = 256 * 256
    # frame area (scale 1) / cell area vs 0.005 -> 327.68 px
    small_fail = np.zeros((128, 128, 4), np.uint8)
    small_fail[20:38, 20:38] = (1, 1, 1, 255)   # 324 px
    small_ok = np.zeros((128, 128, 4), np.uint8)
    small_ok[20:38, 20:39] = (1, 1, 1, 255)     # 342 px
    assert 324 / cell_area < 0.005 < 342 / cell_area
    assert grade(run([record(0)], [small_fail]), "QC-05") == "fail"
    assert grade(run([record(0)], [small_ok]), "QC-05") == "pass"


def test_qc05_empty_frame_listed():
    rep = run([record(0), record(1, empty=True)], [rect_frame(), np.zeros((128, 128, 4), np.uint8)])
    assert grade(rep, "QC-05") == "fail" and rep["checks"]["empty_frames"] == [1]


# --- QC-06 -------------------------------------------------------------------------------------

def test_qc06_identical_frames_warn():
    rep = run([record(i) for i in range(3)], [rect_frame()] * 3)
    assert grade(rep, "QC-06") == "warn"
    assert rep["checks"]["duplicate_frames"] == [[0, 1], [1, 2], [2, 0]]  # walk loops


def test_qc06_distinct_frames_pass():
    assert grade(run([record(i) for i in range(4)], distinct_frames(4)), "QC-06") == "pass"


def test_qc06_hamming_boundary():
    base = distinct_frames(2)[0]
    h0 = qc.dhash(base)
    # find shifts of a block that give distance exactly <=2 and >2 and check the grade follows
    seen = {}
    for shift in range(0, 60, 2):
        g = base.copy()
        g[40:80, 60:90] = (0, 0, 255, 255) if shift else g[40:80, 60:90]
        g[:, :] = np.roll(g, shift // 2, axis=1) if shift else g
        d = qc._hamming(h0, qc.dhash(g))
        rep = run([record(0), record(1)], [base, g], "attack")
        seen[d] = grade(rep, "QC-06")
    assert seen
    for d, gr in seen.items():
        assert gr == ("warn" if d <= 2 else "pass")
    assert any(d <= 2 for d in seen) and any(d > 2 for d in seen)


def test_qc06_loop_pair_only_when_looping():
    frames = [rect_frame()] + distinct_frames(2)[:1] + [rect_frame()]  # first == last, not adjacent
    recs = [record(i) for i in range(3)]
    assert grade(run(recs, frames, "walk"), "QC-06") == "warn"
    assert grade(run(recs, frames, "attack"), "QC-06") == "pass"


def test_qc06_dhash_is_deterministic_64_bit():
    h = qc.dhash(distinct_frames(1)[0])
    assert 0 <= h < 2**64 and h == qc.dhash(distinct_frames(1)[0])


# --- QC-07 -------------------------------------------------------------------------------------

def qc07_for(frame_h, body=100, action="walk", profile="dict"):
    frames = [rect_frame(top=2, bottom=2 + frame_h) for _ in range(3)]
    prof = {"norm_scale": 1.0, "body_height": body} if profile == "dict" else profile
    return run([record(i) for i in range(3)], frames, action, profile=prof)


def test_qc07_boundaries():
    assert grade(qc07_for(84), "QC-07") == "fail"
    assert grade(qc07_for(85), "QC-07") == "warn"
    assert grade(qc07_for(91), "QC-07") == "warn"
    assert grade(qc07_for(92), "QC-07") == "pass"
    assert grade(qc07_for(100), "QC-07") == "pass"
    assert grade(qc07_for(120), "QC-07") == "pass"
    assert grade(qc07_for(121), "QC-07") == "warn"


def test_qc07_accepts_scale_profile_dataclass():
    assert grade(qc07_for(80, profile=ScaleProfile(norm_scale=1.0, body_height=100)), "QC-07") == "fail"


def test_qc07_skipped_without_profile():
    rep = run(*good(), profile=None)
    r = next(r for r in rep["results"] if r["id"] == "QC-07")
    assert r["grade"] == "skipped" and r["reason"] == "no_profile"


# --- QC-09 -------------------------------------------------------------------------------------

def test_qc09_boundary():
    assert grade(run(*good(), bg=60.0), "QC-09") == "pass"
    assert grade(run(*good(), bg=60.1), "QC-09") == "warn"


def test_qc09_skipped_for_native_alpha():
    assert grade(run(*good(), bg=None), "QC-09") == "skipped"


# --- applicability / score / report ------------------------------------------------------------

@pytest.mark.parametrize("action,skipped", [
    ("idle", {"QC-07"}),
    ("walk", set()),
    ("run", set()),
    ("attack", set()),
    ("hurt", set()),
    ("jump", {"QC-02", "QC-07"}),
    ("fall", {"QC-02", "QC-07"}),
    ("death", {"QC-02", "QC-03", "QC-04", "QC-07"}),
    ("fx", {"QC-02", "QC-03", "QC-04", "QC-07"}),
])
def test_qc_applicability_matrix(action, skipped):
    m = qc.applicability(action)
    assert {k for k, v in m.items() if v == "skip"} == skipped
    for always in ("QC-01", "QC-05", "QC-06", "QC-09"):
        assert m[always] != "skip"


def test_qc_death_and_jump_skip_scale_drift_in_report():
    recs = [record(i, h=h) for i, h in enumerate([100, 50, 100])]
    frames = [rect_frame() for _ in recs]
    for action in ("death", "jump"):
        rep = run(recs, frames, action)
        item = next(r for r in rep["results"] if r["id"] == "QC-02")
        assert item["grade"] == "skipped" and item["reason"] == "not_applicable"
        assert rep["checks"]["scale_variance"] is None


def test_qc_idle_qc07_skipped_even_with_profile():
    rep = run(*good(), "idle", profile={"norm_scale": 1.0, "body_height": 1000})
    assert next(r for r in rep["results"] if r["id"] == "QC-07")["reason"] == "not_applicable"


def test_qc_idle_duplicate_is_info_grade():
    rep = run([record(i) for i in range(4)], [rect_frame()] * 4, "idle")
    assert grade(rep, "QC-06") == "info" and rep["status"] == "pass"


def test_qc_walk_duplicate_is_warn_grade():
    rep = run([record(i) for i in range(4)], [rect_frame()] * 4, "walk")
    assert grade(rep, "QC-06") == "warn" and rep["status"] == "warn"


def test_qc_unknown_action_needs_profile_override():
    with pytest.raises(ValueError):
        qc.applicability("slash_fx")
    assert qc.applicability("slash_fx", "fx")["QC-02"] == "skip"


def test_qc_score_formula():
    r = lambda *g: [{"grade": x} for x in g]  # noqa: E731
    assert qc.score_for(r("pass", "info", "skipped")) == 100
    assert qc.score_for(r("fail", "warn")) == 67
    assert qc.score_for(r("fail", "fail", "warn", "warn")) == 34
    assert qc.score_for(r(*["fail"] * 5)) == 0  # floored at 0
    assert qc.overall_status(r("pass", "warn")) == "warn"
    assert qc.overall_status(r("warn", "fail")) == "fail"
    assert qc.overall_status(r("info", "skipped")) == "pass"


def test_qc_report_structure_matches_doc():
    rep = run(*good(), "attack", attempt="002", profile={"norm_scale": 1.0, "body_height": 98})
    assert {"schema_version", "action", "attempt", "status", "score", "frames", "checks", "results",
            "per_frame", "recommendations"} <= rep.keys()
    assert rep["schema_version"] == 1 and rep["action"] == "attack" and rep["attempt"] == "002"
    assert rep["frames"] == 4 and rep["recommendations"] == []
    assert set(rep["checks"]) == {"edge_touch", "scale_variance", "anchor_variance",
                                  "duplicate_frames", "empty_frames"}
    assert [r["id"] for r in rep["results"]] == [f"QC-0{i}" for i in range(1, 10)]
    assert next(r for r in rep["results"] if r["id"] == "QC-08")["grade"] == "not_run"
    assert {"index", "bbox_h", "feet_y_strict", "x_metric", "dhash"} == set(rep["per_frame"][0])
    assert rep["status"] in ("pass", "warn", "fail")
    json.dumps(rep)  # JSON serialisable


def test_qc_is_deterministic():
    recs, frames = good()
    a = run(recs, frames, "walk")
    b = run(copy.deepcopy(recs), [f.copy() for f in frames], "walk")
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_qc_frame_count_mismatch_raises():
    with pytest.raises(ValueError):
        run([record(0)], [rect_frame(), rect_frame()])


def rep_with(attempt, score, qc02):
    return {"attempt": attempt, "score": score, "results": [{"id": "QC-02", "grade": "pass", "value": qc02}]}


def test_qc_best_attempt_prefers_score_then_qc02_then_latest():
    assert qc.select_best_attempt([rep_with("001", 75, 0.0), rep_with("002", 92, 0.09)])["attempt"] == "002"
    assert qc.select_best_attempt([rep_with("001", 92, 0.09), rep_with("002", 92, 0.03)])["attempt"] == "002"
    assert qc.select_best_attempt([rep_with("002", 92, 0.03), rep_with("001", 92, 0.09)])["attempt"] == "002"
    assert qc.select_best_attempt([rep_with("001", 92, 0.03), rep_with("002", 92, 0.03)])["attempt"] == "002"
    assert qc.select_best_attempt([rep_with("002", 92, 0.03), rep_with("001", 92, 0.03)])["attempt"] == "002"
    with pytest.raises(ValueError):
        qc.select_best_attempt([])


# --- integration with process_sheet ------------------------------------------------------------

def process(tmp_path, variant, rows=2, cols=3, **params):
    raw = tmp_path / "raw.png"
    make_sheet(variant, rows=rows, cols=cols, cell_size=(256, 256)).save(raw)
    p = ProcessParams(rows=rows, cols=cols, frames=rows * cols, **params)
    return process_sheet(raw, tmp_path / "out", p)


def test_qc_integration_clean_only_duplicates_warn(tmp_path):
    res = process(tmp_path, "clean")
    rep = qc.run_qc(res, action="walk", attempt="001")
    # the synthetic frames are identical, so QC-06 (duplicates) warns by design; nothing else trips
    assert [r["id"] for r in rep["results"] if r["grade"] in ("warn", "fail")] == ["QC-06"]
    assert rep["status"] == "warn" and rep["score"] == 92


def test_qc_integration_accepts_process_json_dict(tmp_path):
    res = process(tmp_path, "clean")
    data = json.loads((tmp_path / "out" / "process.json").read_text())
    assert qc.run_qc(data, res.frames, "walk") == qc.run_qc(res, action="walk")


def test_qc_integration_edge_touch_fails_qc01(tmp_path):
    # 2x2: the 6 % snap window cannot reach the real gutter, so the raw cell is flagged
    rep = qc.run_qc(process(tmp_path, "edge_touch", rows=2, cols=2), action="walk")
    assert grade(rep, "QC-01") == "fail" and rep["checks"]["edge_touch"] is True
    assert rep["status"] == "fail"


def test_qc_integration_scale_drift_fails_qc02(tmp_path):
    rep = qc.run_qc(process(tmp_path, "scale_drift_12"), action="walk")
    assert grade(rep, "QC-02") == "fail" and rep["checks"]["scale_variance"] > 0.10


def test_qc_integration_scale_drift_not_checked_for_death(tmp_path):
    rep = qc.run_qc(process(tmp_path, "scale_drift_12", anchor="bottom"), action="death")
    assert grade(rep, "QC-02") == "skipped"


def test_qc_integration_empty_cell_fails_qc05(tmp_path):
    rep = qc.run_qc(process(tmp_path, "empty_cell"), action="walk")
    assert grade(rep, "QC-05") == "fail" and rep["checks"]["empty_frames"] == [5]


def test_qc_integration_baseline_jitter_passes_qc03(tmp_path):
    # alignment removes the +-15 px jitter, so the independent strict-feet check passes
    rep = qc.run_qc(process(tmp_path, "baseline_jitter", align="per_frame"), action="walk")
    assert grade(rep, "QC-03") == "pass" and rep["checks"]["anchor_variance"] <= 2


def test_qc_integration_register_flags_foot_contact_slip(tmp_path):
    # align=register keeps the model's own grounding, so a +-15 px baseline jitter is reported (not hidden)
    rep = qc.run_qc(process(tmp_path, "baseline_jitter"), action="walk")
    item = next(r for r in rep["results"] if r["id"] == "QC-03")
    assert item["mode"] == "contact_slip" and item["grade"] == "fail" and item["value"] > 3


def test_qc_integration_register_clean_has_no_contact_slip(tmp_path):
    rep = qc.run_qc(process(tmp_path, "clean"), action="walk")
    assert grade(rep, "QC-03") == "pass"


def test_qc_register_airborne_vertical_travel_skips_qc03(tmp_path):
    res = process(tmp_path, "baseline_jitter", preserve_vertical=True)
    item = next(r for r in qc.run_qc(res, action="jump")["results"] if r["id"] == "QC-03")
    assert item["grade"] == "skipped" and item["reason"] == "vertical_preserved"


def test_qc_integration_qc07_with_profile(tmp_path):
    res = process(tmp_path, "clean")
    body = qc.run_qc(res, action="walk")["per_frame"][0]["bbox_h"]
    ok = qc.run_qc(res, action="walk", profile=ScaleProfile(norm_scale=1.0, body_height=body))
    small = qc.run_qc(res, action="walk", profile={"norm_scale": 1.0, "body_height": body * 2})
    assert grade(ok, "QC-07") == "pass" and grade(small, "QC-07") == "fail"
