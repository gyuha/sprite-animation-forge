"""generate-all passes the regenerate recommendations of a failed attempt on as recovery phrases (e.g. loop_closure)."""

from types import SimpleNamespace

from sprite_forge_web import job_tasks

FAIL = {"status": "fail", "recommendations": [
    {"type": "reprocess", "code": "use_fit", "set": {"scale_strategy": "fit"}},
    {"type": "regenerate", "code": "loop_closure"}, {"type": "regenerate", "code": "identity_drift"},
    {"type": "regenerate", "code": "loop_closure"}]}
PASS = {"status": "pass", "recommendations": []}


def run(monkeypatch, outcomes, max_regenerations=1):
    calls = []

    def fake_generate(ctx, cd, plan, profile, action, direction, extra, recovery):
        calls.append(list(recovery))
        return f"{len(calls):03d}", outcomes[len(calls) - 1]

    monkeypatch.setattr(job_tasks, "generate_and_process", fake_generate)
    monkeypatch.setattr(job_tasks.workflow, "process_attempt", lambda *a, **k: {"qc": FAIL})
    monkeypatch.setattr(job_tasks.workflow, "accept_attempt", lambda *a, **k: None)
    plan = {"directions": ["right"]}
    row = job_tasks._run_unit(SimpleNamespace(canceled=False), None, plan, {}, {"unit": "walk", "action": "walk", "direction": "right"},
                              True, max_regenerations)
    return row, calls


def test_jobs_regenerate_passes_the_failed_attempts_recovery_codes_once_each(monkeypatch):
    row, calls = run(monkeypatch, [FAIL, PASS])
    assert calls == [[], ["loop_closure", "identity_drift"]]  # first try plain, the retry carries the codes (deduplicated)
    assert row["status"] == "accepted" and row["attempt"] == "002"


def test_jobs_regenerate_stops_at_the_limit_and_marks_review(monkeypatch):
    row, calls = run(monkeypatch, [FAIL, FAIL], max_regenerations=1)
    assert len(calls) == 2 and row["status"] == "review" and row["qc_status"] == "fail"
