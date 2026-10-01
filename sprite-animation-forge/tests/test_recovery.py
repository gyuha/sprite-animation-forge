"""Character Scale Profile, QC-07, preserve scale and recovery (docs/06 5-6, docs/11 scenarios 4 and 5)."""

import json

from fixtures.synthetic.make import make_sheet

from sprite_forge import qc, recovery, schemas


def qc_result(report, qc_id):
    return next(r for r in report["results"] if r["id"] == qc_id)


def read(forge, *parts):
    return json.loads(forge.root.joinpath("hero", *parts).read_text())


def put(forge, tmp_path, unit, variant, rows, cols, name=None, extra=()):
    raw = tmp_path / f"{name or unit}_{variant}.png"
    make_sheet(variant, rows=rows, cols=cols, cell_size=(256, 256)).save(raw)
    forge.ok("import-raw", "hero", unit, raw, *extra)


def idle_accepted(forge, tmp_path, actions="idle,attack"):
    forge.ok("init", "hero")
    forge.ok("plan", "hero", "--actions", actions)
    put(forge, tmp_path, "idle", "clean", 2, 2)
    forge.ok("process", "hero", "idle")
    return forge.ok("accept", "hero", "idle")


PROFILE = "character-scale-profile.json"


# ---- profile creation ------------------------------------------------------------------------

def test_scale_profile_created_on_first_body_accept_and_valid(forge, tmp_path):
    forge.ok("init", "hero")
    forge.ok("plan", "hero", "--actions", "idle,attack")
    put(forge, tmp_path, "idle", "clean", 2, 2)
    forge.ok("process", "hero", "idle")
    assert not (forge.root / "hero" / PROFILE).exists()  # process alone never writes it
    forge.ok("accept", "hero", "idle")

    profile = read(forge, PROFILE)
    schemas.validate("character-scale-profile", profile)
    process = read(forge, "idle", "process.json")["derived"]
    assert profile["character"] == "hero" and profile["reference_action"] == "idle"
    assert profile["reference_attempt"] == "001" and profile["target_cell"] == [128, 128]
    assert profile["baseline_y"] == 118 and profile["feet_y"] == 118
    assert profile["raw_cell_height"] == process["raw_cell_height"] == 256
    assert abs(profile["norm_scale"] - process["scale"] * 256) < 0.01
    # synthetic ground truth: 70% of the 256 cell, scaled by the fit scale
    assert abs(profile["body_height"] - 179 * process["scale"]) <= 1.5
    assert 0 < profile["body_width"] < profile["body_height"]
    assert abs(profile["center_x"] - 64) <= 1
    assert read(forge, "manifest.json")["scale_profile"]["reference_action"] == "idle"


def test_scale_profile_unchanged_by_other_actions_and_updated_by_reaccept(forge, tmp_path):
    idle_accepted(forge, tmp_path)
    before = (forge.root / "hero" / PROFILE).read_bytes()

    put(forge, tmp_path, "attack", "clean", 2, 3)
    forge.ok("process", "hero", "attack")
    forge.ok("accept", "hero", "attack")
    assert (forge.root / "hero" / PROFILE).read_bytes() == before

    # a second idle attempt drawn smaller -> re-accepting the reference action rewrites the profile
    raw = tmp_path / "idle_small.png"
    make_sheet("clean", rows=2, cols=2, cell_size=(256, 256)).save(raw)
    forge.ok("import-raw", "hero", "idle", raw)
    forge.ok("process", "hero", "idle", "--set", "margin_top=40")
    forge.ok("accept", "hero", "idle")
    after = read(forge, PROFILE)
    assert after["reference_attempt"] == "002"
    assert after["body_height"] < json.loads(before)["body_height"]
    schemas.validate("character-scale-profile", after)


def test_scale_profile_created_by_first_accepted_body_action_only(forge, tmp_path):
    """The first accepted body action defines the profile even if it is not idle; later ones never do."""
    forge.ok("init", "hero")
    forge.ok("plan", "hero", "--actions", "idle,walk")
    put(forge, tmp_path, "walk", "clean", 2, 3)
    forge.ok("process", "hero", "walk")
    forge.ok("accept", "hero", "walk")
    assert read(forge, PROFILE)["reference_action"] == "walk"
    put(forge, tmp_path, "idle", "clean", 2, 2)
    forge.ok("process", "hero", "idle")
    forge.ok("accept", "hero", "idle")
    assert read(forge, PROFILE)["reference_action"] == "walk"


def test_scale_profile_multi_direction_only_from_representative_unit(forge, tmp_path):
    forge.ok("init", "hero", "--view", "topdown")
    forge.ok("plan", "hero", "--actions", "idle")
    plan = read(forge, "animation-plan.json")
    rep = plan["facing"]
    other = next(d for d in plan["directions"] if d not in (rep, "left"))
    put(forge, tmp_path, "idle", "clean", 2, 2, name="other", extra=("--direction", other))
    forge.ok("process", "hero", "idle", "--direction", other)
    forge.ok("accept", "hero", "idle", "--direction", other)
    assert not (forge.root / "hero" / PROFILE).exists()

    put(forge, tmp_path, "idle", "clean", 2, 2, name="rep", extra=("--direction", rep))
    forge.ok("process", "hero", "idle", "--direction", rep)
    forge.ok("accept", "hero", "idle", "--direction", rep)
    profile = read(forge, PROFILE)
    schemas.validate("character-scale-profile", profile)
    assert read(forge, "manifest.json")["scale_profile"]["reference_unit"] == f"idle/{rep}"


# ---- preserve / QC-07 wiring ----------------------------------------------------------------

def test_preserve_without_profile_falls_back_to_fit_with_warning(forge, tmp_path):
    forge.ok("init", "hero")
    forge.ok("plan", "hero", "--actions", "idle,attack")
    put(forge, tmp_path, "attack", "clean", 2, 3)
    out = forge.ok("process", "hero", "attack", "--set", "scale_strategy=preserve")
    data = read(forge, "attack", "attempts", "001", "process.json")
    assert data["derived"]["scale_strategy_used"] == "fit"
    assert "no_scale_profile" in data["warnings"]
    report = read(forge, "attack", "attempts", "001", "qc-report.json")
    assert qc_result(report, "QC-07") == {"id": "QC-07", "grade": "skipped", "reason": "no_profile"}
    assert out["qc"]["recommendations"] == []


def test_preserve_uses_profile_norm_scale_and_qc07_runs(forge, tmp_path):
    idle_accepted(forge, tmp_path)
    profile = read(forge, PROFILE)
    put(forge, tmp_path, "attack", "clean", 2, 3)
    forge.ok("process", "hero", "attack", "--set", "scale_strategy=preserve")
    data = read(forge, "attack", "attempts", "001", "process.json")["derived"]
    assert data["scale_strategy_used"] == "preserve"
    assert data["scale"] == round(profile["norm_scale"] / data["raw_cell_height"], 4)
    q07 = qc_result(read(forge, "attack", "attempts", "001", "qc-report.json"), "QC-07")
    assert q07["grade"] == "pass" and 0.95 <= q07["value"] <= 1.05


def test_qc07_skipped_for_idle_reference_and_computed_after_profile(forge, tmp_path):
    forge.ok("init", "hero")
    forge.ok("plan", "hero", "--actions", "idle,walk")
    put(forge, tmp_path, "walk", "clean", 2, 3)
    forge.ok("process", "hero", "walk")
    assert qc_result(read(forge, "walk", "attempts", "001", "qc-report.json"), "QC-07")["grade"] == "skipped"
    put(forge, tmp_path, "idle", "clean", 2, 2)
    forge.ok("process", "hero", "idle")
    forge.ok("accept", "hero", "idle")
    forge.ok("process", "hero", "walk")  # same attempt, now with the profile
    assert qc_result(read(forge, "walk", "attempts", "001", "qc-report.json"), "QC-07")["grade"] in ("pass", "warn")


def test_qc07_scenario_4_wide_attack_preserve_vs_fit(forge, tmp_path):
    """Profile from a normal idle; the same wide_attack sheet is processed with preserve and with fit.

    Setup: 256x256 raw cells, 128x128 output cell, default margins. The synthetic sword is 0.6 * cell width
    long, so fit shrinks the whole sprite (QC-07 ~0.61) while preserve keeps the body (QC-07 = 1.0, but the
    sword overflows the output cell, so QC-01 fails; QC-07 itself passes).
    """
    idle_accepted(forge, tmp_path)
    put(forge, tmp_path, "attack", "wide_attack", 2, 3)
    forge.ok("process", "hero", "attack", "--set", "scale_strategy=preserve")
    keep = qc_result(read(forge, "attack", "attempts", "001", "qc-report.json"), "QC-07")["value"]
    forge.ok("process", "hero", "attack", "--set", "scale_strategy=fit")
    fit = qc_result(read(forge, "attack", "attempts", "001", "qc-report.json"), "QC-07")["value"]
    assert keep >= 0.85
    assert fit < keep and fit < 0.85


# ---- scenario 5: first recommendation -------------------------------------------------------

def first_rec(forge, tmp_path, variant, rows, cols, action="attack", sets=()):
    idle_accepted(forge, tmp_path, "idle" if action == "idle" else f"idle,{action}")
    put(forge, tmp_path, action, variant, rows, cols)
    args = [a for s in sets for a in ("--set", s)]
    out = forge.ok("process", "hero", action, *args)
    recs = out["qc"]["recommendations"]
    assert recs and [r["priority"] for r in recs] == list(range(1, len(recs) + 1))
    schemas.validate("qc-report", read(forge, action, "attempts", out["attempt"], "qc-report.json"))
    return recs[0]


def test_recovery_scenario_5_edge_touch_regenerates_edge_touch(forge, tmp_path):
    rec = first_rec(forge, tmp_path, "edge_touch", 2, 2, action="idle")
    assert (rec["action"], rec["code"], rec["qc_id"]) == ("regenerate", "edge_touch", "QC-01")


def test_recovery_scenario_5_scale_drift_regenerates_scale_drift(forge, tmp_path):
    rec = first_rec(forge, tmp_path, "scale_drift_12", 2, 3, action="walk")  # QC-02 fails for locomotion only
    assert (rec["action"], rec["code"]) == ("regenerate", "scale_drift")


def test_recovery_scenario_5_wide_attack_fit_reprocesses_with_preserve(forge, tmp_path):
    rec = first_rec(forge, tmp_path, "wide_attack", 2, 3, sets=("scale_strategy=fit",))
    assert rec["action"] == rec["type"] == "reprocess"
    assert rec["set"] == {"scale_strategy": "preserve"} and rec["code"] == "use_preserve"
    assert rec["cost"] == "~2s"


def test_recovery_budget_exhausted_records_forced_accept(forge, tmp_path):
    idle_accepted(forge, tmp_path)
    put(forge, tmp_path, "attack", "wide_attack", 2, 3)
    seen = []
    for _ in range(3):  # budget: 2 reprocesses; the 3rd run finds nothing cheap left
        out = forge.ok("process", "hero", "attack", "--set", "scale_strategy=fit")
        seen.append([(r["action"], r["code"]) for r in out["qc"]["recommendations"]])
    assert seen[0] == [("reprocess", "use_preserve"), ("regenerate", "character_small")]
    assert seen[2] == [("regenerate", "character_small")]  # reprocess budget used up, regeneration remains

    # regeneration budget: two more attempts (= 2 regenerations) and the budget is exhausted
    for _ in range(2):
        put(forge, tmp_path, "attack", "wide_attack", 2, 3, name=f"re{_}")
        out = forge.ok("process", "hero", "attack", "--set", "scale_strategy=fit")
    recs = out["qc"]["recommendations"]
    assert len(recs) == 1 and recs[0]["action"] == "force_accept" and recs[0]["attempt"] in ("001", "002", "003")
    best = recs[0]["attempt"]

    out = forge.ok("accept", "hero", "attack", "--attempt", best)
    assert out["forced"] is True
    manifest = read(forge, "manifest.json")
    assert manifest["forced_accepts"] == ["attack"]
    assert manifest["actions"]["attack"]["forced"] is True


# ---- recovery table (unit) ------------------------------------------------------------------

def report(**grades):
    """Minimal QC report: ``QC_07="fail"`` etc.; extra fields via tuples ``(grade, {...})``."""
    results = []
    for qid in ("QC-01", "QC-02", "QC-03", "QC-05", "QC-06", "QC-07", "QC-09"):
        g = grades.get(qid.replace("-", "_"), "pass")
        extra = {}
        if isinstance(g, tuple):
            g, extra = g
        results.append({"id": qid, "grade": g, **extra})
    return {"attempt": "001", "results": results, "recommendations": []}


def codes(recs):
    return [(r["action"], r["code"]) for r in recs]


def proc(strategy="fit", gap=40):
    return {"derived": {"scale_strategy_used": strategy},
            "params": {"components": {"mode": "largest", "merge_gap_px": gap}, "scale_strategy": strategy}}


def test_recovery_table_priority_order():
    rep = report(QC_05="fail", QC_01=("fail", {"raw_frames": [0], "output_frames": []}), QC_02="fail")
    assert codes(recovery.recommend(rep, proc())) == [
        ("regenerate", "empty_frame"), ("regenerate", "edge_touch"), ("regenerate", "scale_drift")]


def test_recovery_qc07_fit_vs_preserve():
    assert codes(recovery.recommend(report(QC_07="fail"), proc("fit"))) == [
        ("reprocess", "use_preserve"), ("regenerate", "character_small")]
    assert codes(recovery.recommend(report(QC_07="fail"), proc("preserve"))) == [
        ("regenerate", "character_small"), ("regenerate", "fx_in_body")]


def test_recovery_qc01b_preserve_overflow():
    rep = report(QC_01=("fail", {"raw_frames": [], "output_frames": [2]}))
    recs = recovery.recommend(rep, proc("preserve"))
    assert codes(recs) == [("regenerate", "fx_in_body"), ("reprocess", "use_fit")]
    assert recs[1]["set"] == {"scale_strategy": "fit"}


def test_recovery_qc03_reprocess_chain_halves_merge_gap():
    recs = recovery.recommend(report(QC_03="fail"), proc(gap=40))
    assert codes(recs) == [("reprocess", "anchor_bottom"), ("reprocess", "tighter_merge")]
    assert recs[0]["set"] == {"anchor": "bottom"}
    assert recs[1]["set"] == {"components": "largest", "merge_gap_px": 20}


def test_recovery_qc09_warn_only_with_qc01_or_qc05_failure_and_qc06_never():
    assert recovery.recommend(report(QC_09="warn", QC_06="warn"), proc()) == []
    recs = recovery.recommend(report(QC_09="warn", QC_05="fail"), proc())
    assert codes(recs) == [("regenerate", "empty_frame"), ("regenerate", "bg_mismatch")]
    assert recovery.recommend(report(QC_06="warn"), proc()) == []


def test_recovery_regenerate_codes_are_prompt_recovery_codes():
    from sprite_forge.prompt import RECOVERY_CODES

    rep = report(QC_05="fail", QC_01=("fail", {"raw_frames": [0], "output_frames": [0]}), QC_02="fail",
                 QC_07="fail", QC_09="warn")
    regen = [r["code"] for r in recovery.recommend(rep, proc("preserve")) if r["action"] == "regenerate"]
    assert regen and set(regen) <= set(RECOVERY_CODES)


def test_recovery_budget_state_and_forced_accept_unit():
    entry = {"reprocess_count": 2, "attempts": {"001": {}, "002": {}, "003": {}}}
    state = recovery.budget_state(entry, best_attempt="002")
    assert state["reprocess_used"] == 2 and state["regenerate_used"] == 2
    recs = recovery.recommend(report(QC_07="fail"), proc("fit"), budget_state=state)
    assert len(recs) == 1 and recs[0]["action"] == "force_accept" and recs[0]["attempt"] == "002"
    assert recs[0]["priority"] == 1
    # no budget (Web UI manual mode) -> unlimited
    assert codes(recovery.recommend(report(QC_07="fail"), proc("fit"))) == [
        ("reprocess", "use_preserve"), ("regenerate", "character_small")]


def test_recovery_pass_report_has_no_recommendations_and_run_qc_stays_pure():
    assert recovery.recommend(report(), proc()) == []
    data = {"params": {"cell": {"w": 128, "h": 128}, "x_anchor": "mass"},
            "derived": {"baseline_y": 118, "scale": 1.0, "bg_distance_to_key": 0.0, "frames": []}}
    assert qc.run_qc(data, [], "walk")["recommendations"] == []
