"""Job-creating generation endpoints: action generate (direction rules, process/accept flow) and generate-all
(docs/09 7: unit order, mirror exclusion, failure policy, regeneration, cancel)."""

import json

import pytest

from .api_sync_helpers import char_url, err
from .jobs_helpers import (gen_url, job_of, mode_by_call, post_generate, ready_character, record_events, states_of,
                           unit_attempts, wait_job, wait_until)

WALK4 = ["walk.frames=4", "walk.grid=2x2"]  # the fake codex draws a 2x2 sheet unless FAKE_CODEX_GRID says otherwise


def generate_all(client, cid="hero", expect=202, **body):
    r = client.post(char_url(cid, "/generate-all"), json=body)
    assert r.status_code == expect, r.text
    return r.json()


def accept(client, action="idle", aid="001", **params):
    return client.post(char_url("hero", f"/actions/{action}/attempts/{aid}/accept"), params=params, json={"force": True})


@pytest.fixture
def calls(tmp_path, monkeypatch):
    log = tmp_path / "calls.log"
    monkeypatch.setenv("FAKE_CODEX_CALL_LOG", str(log))
    return lambda: len(log.read_text().splitlines()) if log.exists() else 0


# ---- single generation -----------------------------------------------------------------------------------

def test_jobs_generate_flows_into_process_and_accept(jc, root, calls):
    ready_character(jc, root, "hero")
    created = post_generate(jc)
    assert created["attempt"] is None and created["job"]["state"] == "queued"
    assert created["job"]["type"] == "action_generate" and created["job"]["action"] == "idle"
    job = wait_job(jc, created["job"]["id"])
    assert job["state"] == "succeeded", job
    assert job["result"]["attempt"] == "001" and job["result"]["accepted"] is False
    assert calls() == 1

    detail = jc.get(char_url("hero", "/actions/idle/attempts/001")).json()
    assert detail["summary"]["generation_status"] == "succeeded" and detail["summary"]["provider"] == "codex-cli"
    assert detail["summary"]["qc_status"] == job["result"]["qc_status"]  # auto process + QC already ran
    assert detail["files"]["sheet"] and detail["files"]["frames"] and detail["files"]["raw"]
    assert detail["generation"]["prompt_template_version"]
    again = jc.post(char_url("hero", "/actions/idle/attempts/001/process"), json={"set": {"scale_strategy": "preserve"}})
    assert again.status_code == 200, again.text
    acc = accept(jc)
    assert acc.status_code == 200 and acc.json()["accepted"] == "001"
    assert jc.get(char_url("hero", "/actions/idle/attempts")).json()["accepted_attempt"] == "001"


def test_jobs_generate_extra_and_recovery_reach_the_prompt(jc, root):
    ready_character(jc, root, "hero")
    r = jc.post(gen_url(), json={"extra": "swing the sword wider", "recovery": ["character_small"]})
    assert r.status_code == 202, r.text
    wait_job(jc, r.json()["job"]["id"])
    assert "swing the sword wider" in (root / "hero/idle/attempts/001/prompt.txt").read_text()
    entry = jc.get(char_url("hero", "/actions/idle/attempts")).json()["attempts"][0]
    assert entry["extra"] == "swing the sword wider" and entry["recovery"] == ["character_small"]
    assert jc.post(gen_url(), json={"recovery": ["no_such_code"]}).status_code == 400
    assert len(jc.get("/api/jobs").json()["jobs"]) == 1  # the invalid request queued nothing


def test_jobs_generate_failed_codex_run_marks_job_failed(jc, root, monkeypatch):
    ready_character(jc, root, "hero")
    monkeypatch.setenv("FAKE_CODEX_MODE", "no_image")
    events = record_events(jc)
    jid = post_generate(jc)["job"]["id"]
    job = wait_job(jc, jid)
    assert job["state"] == "failed" and job["result"] is None
    assert job["error"]["code"] == "no_image" and job["error"]["detail"]["attempt"] == "001"
    assert job["attempt"] == "001"
    assert states_of(events, jid) == ["queued", "running", "failed"]
    row = jc.get(char_url("hero", "/actions/idle/attempts")).json()["attempts"][0]
    assert row["generation_status"] == "failed"


def test_jobs_generate_direction_rules(jc, root):
    ready_character(jc, root, "hero", topdown=True)
    err(jc.post(gen_url(), json={}), 400, "direction_required")
    err(jc.post(gen_url(), params={"direction": "left"}, json={}), 409, "mirrored_direction")
    err(jc.post(gen_url(), params={"direction": "sideways"}, json={}), 422, "validation_error")
    err(jc.post(gen_url(action="fly"), params={"direction": "down"}, json={}), 404, "not_found")
    # non-representative directions need the accepted representative unit first
    err(jc.post(gen_url(), params={"direction": "right"}, json={}), 412, "precondition_failed")
    assert jc.get("/api/jobs").json() == {"jobs": []}

    created = post_generate(jc, direction="down")
    assert created["job"]["direction"] == "down" and created["job"]["action"] == "idle"
    job = wait_job(jc, created["job"]["id"])
    assert job["state"] == "succeeded" and (root / "hero/idle/down/attempts/001/raw.png").exists()
    assert accept(jc, direction="down").status_code == 200
    right = post_generate(jc, direction="right")
    assert wait_job(jc, right["job"]["id"])["state"] == "succeeded"


# ---- generate-all -------------------------------------------------------------------------------------------

def test_jobs_generate_all_unit_order_and_mirror_exclusion_on_topdown(jc, root, calls):
    ready_character(jc, root, "hero", actions=("idle", "walk"), topdown=True, sets=WALK4)
    created = generate_all(jc, actions=["idle", "walk"], auto_accept=True)["job"]
    assert created["type"] == "batch_generate" and created["progress"] == {"done": 0, "total": 6, "current": None}
    assert created["expected_s"] == 6 * 90
    job = wait_job(jc, created["id"], timeout=60)
    assert job["state"] == "succeeded", job
    assert [r["unit"] for r in job["result"]["units"]] == [
        "idle/down", "idle/right", "idle/up", "walk/down", "walk/right", "walk/up"]
    assert job["progress"] == {"done": 6, "total": 6, "current": None}
    assert calls() == 6  # left is mirror-derived: no Codex call
    assert all(r["status"] in ("accepted", "review") for r in job["result"]["units"])
    assert job["result"]["accepted"] + job["result"]["review"] == 6
    assert any(line["text"].startswith("idle/down:") for line in job["log"])
    if job["result"]["units"][1]["status"] == "accepted":  # right accepted -> left derived by mirroring
        assert (root / "hero/idle/left/sheet.png").exists()


def test_jobs_generate_all_defaults_to_unaccepted_units(jc, root, calls):
    ready_character(jc, root, "hero", actions=("idle", "walk"), sets=WALK4)
    assert wait_job(jc, post_generate(jc)["job"]["id"])["state"] == "succeeded"
    assert accept(jc).status_code == 200
    job = wait_job(jc, generate_all(jc)["job"]["id"], timeout=60)  # actions omitted: only walk is left
    assert [r["unit"] for r in job["result"]["units"]] == ["walk"]
    assert calls() == 2


def test_jobs_generate_all_rejects_unknown_action_and_empty_selection(jc, root):
    ready_character(jc, root, "hero")
    err(jc.post(char_url("hero", "/generate-all"), json={"actions": ["fly"]}), 404, "not_found")
    err(jc.post(char_url("hero", "/generate-all"), json={"max_regenerations": 7}), 422, "validation_error")
    assert wait_job(jc, post_generate(jc)["job"]["id"])["state"] == "succeeded"
    assert accept(jc).status_code == 200
    err(jc.post(char_url("hero", "/generate-all"), json={}), 400, "nothing_to_generate")


def test_jobs_generate_all_failed_unit_does_not_stop_the_batch(jc, root, tmp_path, monkeypatch):
    ready_character(jc, root, "hero", actions=("idle", "walk"), sets=WALK4)
    mode_by_call(tmp_path, monkeypatch, ["no_image", "success"])
    job = wait_job(jc, generate_all(jc, actions=["idle", "walk"])["job"]["id"], timeout=60)
    assert job["state"] == "succeeded" and job["error"] is None
    first, second = job["result"]["units"]
    assert first["unit"] == "idle" and first["status"] == "review" and first["error"]["code"] == "no_image"
    assert second["unit"] == "walk" and second["attempt"] == "001" and second["status"] in ("accepted", "review")
    assert "error" not in second
    assert job["progress"]["done"] == 2 and job["result"]["review"] >= 1
    assert jc.get(char_url("hero", "/actions/idle/attempts")).json()["attempts"][0]["generation_status"] == "failed"
    assert any(line["text"] == "idle: review" for line in job["log"])


def test_jobs_generate_all_auto_accept_off_leaves_units_for_review(jc, root):
    ready_character(jc, root, "hero")
    job = wait_job(jc, generate_all(jc, auto_accept=False)["job"]["id"], timeout=60)
    row = job["result"]["units"][0]
    assert row["status"] == "review" and row["attempt"] == "001" and row["qc_status"] in ("pass", "warn", "fail")
    assert jc.get(char_url("hero", "/actions/idle/attempts")).json()["accepted_attempt"] is None


def test_jobs_generate_all_failing_qc_regenerates_up_to_max_regenerations(jc, root, monkeypatch, calls):
    ready_character(jc, root, "hero")
    monkeypatch.setenv("FAKE_CODEX_IMAGE", "edge_touch")
    job = wait_job(jc, generate_all(jc, max_regenerations=1)["job"]["id"], timeout=60)
    row = job["result"]["units"][0]
    assert row["qc_status"] == "fail" and row["status"] == "review"
    assert calls() == 2 and unit_attempts(root, "hero", "idle") == ["001", "002"]  # 1 generation + 1 regeneration
    assert jc.get(char_url("hero", "/actions/idle/attempts")).json()["accepted_attempt"] is None


def test_jobs_generate_all_cancel_keeps_finished_units_and_batch_occupies_the_worker(jc, root, tmp_path, monkeypatch):
    ready_character(jc, root, "hero", actions=("idle", "walk"), sets=WALK4)
    mode_by_call(tmp_path, monkeypatch, ["success", "hang", "success"])
    events = record_events(jc)
    batch = generate_all(jc, actions=["idle", "walk"])["job"]["id"]
    single = post_generate(jc)  # requested while the batch owns the worker -> waits behind it
    assert single["job"]["state"] == "queued"
    wait_until(lambda: job_of(jc, batch)["progress"]["done"] == 1 and job_of(jc, batch)["stage"] == "generating",
               timeout=40, what="second unit generating")
    assert job_of(jc, single["job"]["id"])["queue_position"] == 1
    assert job_of(jc, batch)["action"] == "walk"

    canceled = jc.post(f"/api/jobs/{batch}/cancel").json()["job"]
    assert canceled["state"] == "canceled" and canceled["result"] is None
    assert any(line["text"].startswith("idle:") for line in canceled["log"])  # finished unit reported
    assert jc.get(char_url("hero", "/actions/idle/attempts")).json()["attempts"][0]["generation_status"] == "succeeded"
    assert jc.get(char_url("hero", "/actions/walk/attempts")).json()["attempts"][0]["generation_status"] == "canceled"
    assert wait_job(jc, single["job"]["id"])["state"] == "succeeded"
    assert states_of(events, batch) == ["queued", "running", "canceled"]
    order = [(e["id"], e["state"]) for e in events if e["kind"] == "state"]
    assert order.index((batch, "canceled")) < order.index((single["job"]["id"], "running"))


def test_jobs_object_has_the_documented_fields(jc, root):
    ready_character(jc, root, "hero")
    job = wait_job(jc, generate_all(jc)["job"]["id"], timeout=60)
    assert set(job) == {"id", "type", "character", "action", "direction", "attempt", "state", "stage", "queue_position",
                        "created_at", "started_at", "finished_at", "elapsed_s", "expected_s", "progress", "log",
                        "result", "error"}
    json.dumps(job)
