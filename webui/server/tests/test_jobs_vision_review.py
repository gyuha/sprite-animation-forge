"""POST .../attempts/{aid}/review: a Job that asks Codex for an advisory vision review; the result is saved with the
attempt and returned by the attempt detail."""

import json

from .api_sync_helpers import char_url, err
from .jobs_helpers import post_generate, ready_character, wait_job

FRAMES = ["walk.frames=4", "walk.grid=2x2"]


def review_url(action="walk", aid="001", cid="hero"):
    return char_url(cid, f"/actions/{action}/attempts/{aid}/review")


def processed(jc, root):
    ready_character(jc, root, "hero", actions=("walk",), sets=FRAMES)
    job = wait_job(jc, post_generate(jc, action="walk")["job"]["id"])
    assert job["state"] == "succeeded", job
    return job["result"]["attempt"]


def test_jobs_vision_review_runs_as_a_job_and_the_detail_returns_the_review(jc, root):
    aid = processed(jc, root)
    assert jc.get(char_url("hero", f"/actions/walk/attempts/{aid}")).json()["vision_review"] is None
    r = jc.post(review_url(aid=aid))
    assert r.status_code == 202, r.text
    job = r.json()["job"]
    assert job["type"] == "vision_review" and job["action"] == "walk"
    done = wait_job(jc, job["id"])
    assert done["state"] == "succeeded", done
    assert done["result"]["attempt"] == aid and done["result"]["review"]["overall"] == "pass"
    detail = jc.get(char_url("hero", f"/actions/walk/attempts/{aid}")).json()
    assert detail["vision_review"]["review"]["overall"] == "pass" and detail["vision_review"]["frames"] == 4
    assert json.loads((root / f"hero/walk/attempts/{aid}/vision-review.json").read_text())["attempt"] == aid


def test_jobs_vision_review_failure_is_reported_on_the_job(jc, root, monkeypatch):
    aid = processed(jc, root)
    monkeypatch.setenv("FAKE_CODEX_MODE", "invalid_json")
    job = wait_job(jc, jc.post(review_url(aid=aid)).json()["job"]["id"])
    assert job["state"] == "failed" and job["error"]["code"] == "invalid_review"


def test_jobs_vision_review_unknown_attempt_is_404(jc, root):
    processed(jc, root)
    err(jc.post(review_url(aid="009")), 404, "not_found")
    err(jc.post(review_url(aid="abc")), 404, "not_found")


def test_jobs_vision_review_needs_frames(jc, root):
    import shutil
    aid = processed(jc, root)
    shutil.rmtree(root / f"hero/walk/attempts/{aid}/frames")  # an attempt that was imported but never processed
    err(jc.post(review_url(aid=aid)), 412, "precondition_failed")


def test_jobs_vision_review_is_not_cancelable_while_running(jc, root, monkeypatch):
    aid = processed(jc, root)
    monkeypatch.setenv("FAKE_CODEX_DELAY_S", "1.5")
    job = jc.post(review_url(aid=aid)).json()["job"]
    wait_job(jc, job["id"], states=("running",))
    err(jc.post(f"/api/jobs/{job['id']}/cancel"), 409, "not_cancelable")
    wait_job(jc, job["id"])
