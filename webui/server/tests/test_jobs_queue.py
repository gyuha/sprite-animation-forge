"""Job queue: FIFO, concurrency 1, queue_position, cancel (queued / running), job list and lookups (docs/10 2)."""

import pytest

from .api_sync_helpers import char_url, err, make_character
from .jobs_helpers import (job_of, pid_alive, post_generate, ready_character, record_events,
                           states_of, unit_attempts, wait_job, wait_until, wrapper_bin)


def test_jobs_fifo_single_worker_and_queue_position(jc, root, monkeypatch):
    ready_character(jc, root, "hero")
    ready_character(jc, root, "mage")
    monkeypatch.setenv("FAKE_CODEX_DELAY_S", "0.6")
    events = record_events(jc)
    ids = [post_generate(jc, cid)["job"]["id"] for cid in ("hero", "mage", "hero")]

    active = jc.get("/api/jobs", params={"active": 1}).json()["jobs"]
    assert [j["id"] for j in active] == ids  # creation order = run order
    assert sum(j["state"] == "running" for j in active) <= 1
    assert [j["queue_position"] for j in active if j["state"] == "queued"] == list(
        range(1, sum(j["state"] == "queued" for j in active) + 1))

    jobs = [wait_job(jc, jid) for jid in ids]
    assert [j["state"] for j in jobs] == ["succeeded"] * 3
    running_order = [e["id"] for e in events if e["kind"] == "state" and e["state"] == "running"]
    assert running_order == ids
    # concurrency 1: between a job's "running" and its terminal event nobody else starts
    current = None
    for e in events:
        if e["kind"] != "state":
            continue
        if e["state"] == "running":
            assert current is None, f"{e['id']} started while {current} was running"
            current = e["id"]
        elif e["state"] == "succeeded":
            assert current == e["id"]
            current = None
    assert unit_attempts(root, "hero", "idle") == ["001", "002"]
    assert all(j["queue_position"] == 0 for j in jobs)


def test_jobs_queue_position_shifts_when_head_leaves(jc, root, monkeypatch):
    ready_character(jc, root, "hero")
    monkeypatch.setenv("FAKE_CODEX_DELAY_S", "0.6")
    events = record_events(jc)
    a, b, c = (post_generate(jc)["job"]["id"] for _ in range(3))
    wait_job(jc, a)
    wait_until(lambda: job_of(jc, b)["state"] == "running", what="b running")
    assert job_of(jc, c)["queue_position"] == 1
    assert any(e["id"] == c and e["kind"] == "queue" and e["queue_position"] == 1 for e in events)
    wait_job(jc, c)


def test_jobs_cancel_queued_removes_from_queue(jc, root, monkeypatch):
    ready_character(jc, root, "hero")
    monkeypatch.setenv("FAKE_CODEX_DELAY_S", "0.8")
    events = record_events(jc)
    a = post_generate(jc)["job"]["id"]
    b = post_generate(jc)["job"]["id"]
    c = post_generate(jc)["job"]["id"]
    r = jc.post(f"/api/jobs/{b}/cancel")
    assert r.status_code == 200 and r.json()["job"]["state"] == "canceled"
    assert job_of(jc, b)["finished_at"] and job_of(jc, b)["started_at"] is None
    assert [j["id"] for j in jc.get("/api/jobs", params={"active": 1}).json()["jobs"]] == [a, c]
    assert wait_job(jc, a)["state"] == "succeeded" and wait_job(jc, c)["state"] == "succeeded"
    assert states_of(events, b) == ["queued", "canceled"]
    assert unit_attempts(root, "hero", "idle") == ["001", "002"]  # b never ran


def test_jobs_cancel_running_kills_the_codex_process(jc, root, tmp_path, monkeypatch):
    ready_character(jc, root, "hero")
    pidfile = tmp_path / "codex.pid"
    wrapper_bin(tmp_path, monkeypatch, f'echo $$ > "{pidfile}"')
    monkeypatch.setenv("FAKE_CODEX_MODE", "hang")
    events = record_events(jc)
    jid = post_generate(jc)["job"]["id"]
    wait_until(lambda: job_of(jc, jid)["stage"] == "generating", what="generating stage")
    pid = int(pidfile.read_text())
    assert pid_alive(pid)

    r = jc.post(f"/api/jobs/{jid}/cancel")
    assert r.status_code == 200
    job = r.json()["job"]
    assert job["state"] == "canceled" and job["finished_at"] and job["error"] is None
    assert not pid_alive(pid)  # SIGTERM took the whole process group down
    assert states_of(events, jid) == ["queued", "running", "canceled"]
    attempt = jc.get(char_url("hero", "/actions/idle/attempts")).json()["attempts"][0]
    assert attempt["generation_status"] == "canceled"
    # the worker is free again
    monkeypatch.setenv("FAKE_CODEX_MODE", "success")
    assert wait_job(jc, post_generate(jc)["job"]["id"])["state"] == "succeeded"


def test_jobs_cancel_unknown_and_finished_errors(jc, root):
    err(jc.post("/api/jobs/job_nope/cancel"), 404, "not_found")
    err(jc.get("/api/jobs/job_nope"), 404, "not_found")
    ready_character(jc, root, "hero")
    jid = post_generate(jc)["job"]["id"]
    assert wait_job(jc, jid)["state"] == "succeeded"
    err(jc.post(f"/api/jobs/{jid}/cancel"), 409, "not_cancelable")


def test_jobs_list_active_filter_and_detail(jc, root, monkeypatch):
    ready_character(jc, root, "hero")
    assert jc.get("/api/jobs").json() == {"jobs": []}
    monkeypatch.setenv("FAKE_CODEX_DELAY_S", "0.5")
    first = post_generate(jc)["job"]["id"]
    second = post_generate(jc)["job"]["id"]
    wait_job(jc, first)
    active = jc.get("/api/jobs", params={"active": 1}).json()["jobs"]
    assert [j["id"] for j in active] == [second]
    wait_job(jc, second)
    assert jc.get("/api/jobs", params={"active": 1}).json() == {"jobs": []}
    assert [j["id"] for j in jc.get("/api/jobs").json()["jobs"]] == [first, second]
    job = job_of(jc, first)
    assert job["type"] == "action_generate" and job["character"] == "hero" and job["action"] == "idle"
    assert job["attempt"] == "001" and job["stage"] == "qc" and job["expected_s"] == 90
    assert job["result"] == {"attempt": "001", "qc_status": job["result"]["qc_status"], "accepted": False}
    assert job["created_at"] <= job["started_at"] <= job["finished_at"]


def test_jobs_identity_analyze_job_and_not_cancelable_while_running(jc, root, monkeypatch):
    ready_character(jc, root, "hero")
    monkeypatch.setenv("FAKE_CODEX_DELAY_S", "0.8")
    jid = jc.post(char_url("hero", "/identity/analyze")).json()["job"]["id"]
    wait_until(lambda: job_of(jc, jid)["state"] == "running", what="running")
    err(jc.post(f"/api/jobs/{jid}/cancel"), 409, "not_cancelable")
    job = wait_job(jc, jid)
    assert job["type"] == "identity_analyze" and job["state"] == "succeeded"
    assert job["result"]["profile"]["source"] == "codex-analysis"
    assert jc.get(char_url("hero", "/identity")).json()["profile"]["source"] == "codex-analysis"


def test_jobs_reference_generate_collects_candidates(jc, root):
    make_character(jc, "newbie")
    r = jc.post(char_url("newbie", "/reference/generate"), json={"description": "a small knight", "count": 2})
    assert r.status_code == 202, r.text
    job = r.json()["job"]
    assert job["type"] == "reference_generate" and job["expected_s"] == 180
    done = wait_job(jc, job["id"])
    assert done["state"] == "succeeded", done
    assert [a["status"] for a in done["result"]["attempts"]] == ["succeeded", "succeeded"]
    assert jc.post(char_url("newbie", "/reference/attempts/002/select")).status_code == 200


@pytest.mark.parametrize("body", [{"description": ""}, {"description": "x", "count": 9}, {}])
def test_jobs_reference_generate_validates_body(jc, root, body):
    make_character(jc, "newbie")
    assert jc.post(char_url("newbie", "/reference/generate"), json=body).status_code == 422


def test_jobs_unavailable_codex_is_503(jc, root, monkeypatch):
    ready_character(jc, root, "hero")
    monkeypatch.setenv("FAKE_CODEX_DOCTOR", "logged_out")
    body = err(jc.post(char_url("hero", "/actions/idle/generate"), json={}), 503, "codex_unavailable")
    assert body["detail"]["doctor"]["ready"] is False
    assert jc.get("/api/jobs").json() == {"jobs": []}


def test_jobs_generate_preconditions_are_412_before_queueing(jc, root):
    make_character(jc, "bare")
    err(jc.post(char_url("bare", "/actions/idle/generate"), json={}), 412, "precondition_failed")
    err(jc.post(char_url("bare", "/identity/analyze")), 412, "precondition_failed")
    err(jc.post(char_url("ghost", "/identity/analyze")), 404, "not_found")
    assert jc.get("/api/jobs").json() == {"jobs": []}
