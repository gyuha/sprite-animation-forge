"""Startup recovery (docs/10 6): running attempts -> interrupted, dead-PID ``.lock`` files removed."""

import fcntl
import os
import subprocess
import sys

from sprite_forge import manifest as mf
from sprite_forge import schemas

from .api_sync_helpers import char_url
from .jobs_helpers import job_of, post_generate, ready_character, record_events, wait_job, wait_until


def seed_running_attempt(root, cid="hero", unit="idle", aid="001", status="running"):
    cd = root / cid
    (cd / unit / "attempts" / aid).mkdir(parents=True)

    def apply(m):
        mf.unit_entry(m, unit)["attempts"][aid] = {"created_at": "2026-10-01T00:00:00Z", "provider": "codex-cli",
                                                    "generation_status": status, "qc_status": None, "score": None,
                                                    "recovery": [], "extra": None}

    mf.update(cd, apply)


def dead_pid() -> int:
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    return proc.pid


def test_interrupted_running_attempts_are_marked_on_startup(make_client, root):
    with make_client() as c:  # builds the root and the characters, then "crashes" with a running attempt
        ready_character(c, root, "hero")
        ready_character(c, root, "mage")
    seed_running_attempt(root, "hero", "idle", "001", "running")
    seed_running_attempt(root, "hero", "idle", "002", "succeeded")
    seed_running_attempt(root, "mage", "idle", "001", "running")
    before = (root / "hero" / "manifest.json").read_text()

    with make_client() as c:
        assert sorted(c.app.state.recovery["interrupted"]) == ["hero/idle/001", "mage/idle/001"]
        attempts = c.get(char_url("hero", "/actions/idle/attempts")).json()["attempts"]
        assert [(a["attempt"], a["generation_status"]) for a in attempts] == [("001", "interrupted"), ("002", "succeeded")]
        detail = c.get(char_url("hero", "/actions/idle/attempts/001")).json()
        assert detail["summary"]["generation_status"] == "interrupted"
        status = c.get(char_url("hero")).json()["status"]
        unit = next(u for u in status["units"] if u["unit"] == "idle")
        assert unit["latest_generation_status"] == "succeeded"  # attempt 002 is the latest
        assert c.get(char_url("mage")).json()["status"]["units"][0]["latest_generation_status"] == "interrupted"
        assert c.get(char_url("mage")).json()["manifest"]["actions"]["idle"]["attempts"]["001"]["generation_status"] == "interrupted"
    assert (root / "hero" / "manifest.json").read_text() != before
    with make_client() as c:  # idempotent: nothing left to recover
        assert c.app.state.recovery["interrupted"] == []


def test_interrupted_attempt_can_be_generated_again_and_other_manifests_stay_valid(make_client, root):
    with make_client() as c:
        ready_character(c, root, "hero")
    seed_running_attempt(root, "hero")
    with make_client() as c:
        assert c.app.state.recovery["interrupted"] == ["hero/idle/001"]
        job = wait_job(c, post_generate(c)["job"]["id"])
        assert job["state"] == "succeeded" and job["result"]["attempt"] == "002"
        rows = {a["attempt"]: a["generation_status"] for a in c.get(char_url("hero", "/actions/idle/attempts")).json()["attempts"]}
        assert rows == {"001": "interrupted", "002": "succeeded"}
        m = mf.load(root / "hero")
        schemas.validate("manifest", m)  # "interrupted" is allowed by the schema


def test_interrupted_recovery_removes_dead_pid_locks_and_keeps_live_ones(make_client, root):
    with make_client() as c:
        ready_character(c, root, "hero")
    attempts = root / "hero" / "idle" / "attempts"
    for n in ("001", "002", "003", "004"):
        (attempts / n).mkdir(parents=True)
    (attempts / "001" / ".lock").write_text(str(dead_pid()))
    (attempts / "002" / ".lock").write_text("")  # legacy lock without a PID, not held
    (attempts / "003" / ".lock").write_text(str(os.getpid()))  # owner alive
    held = open(attempts / "004" / ".lock", "a+")
    fcntl.flock(held, fcntl.LOCK_EX)
    held.write(str(dead_pid()))  # pid says dead, but the flock is held: must stay
    held.flush()
    try:
        with make_client() as c:
            removed = c.app.state.recovery["locks_removed"]
        assert sorted(removed) == ["hero/idle/attempts/001/.lock", "hero/idle/attempts/002/.lock"]
        assert not (attempts / "001" / ".lock").exists() and not (attempts / "002" / ".lock").exists()
        assert (attempts / "003" / ".lock").exists() and (attempts / "004" / ".lock").exists()
    finally:
        held.close()


def test_interrupted_recovery_is_skipped_while_another_process_holds_the_codex_lock(make_client, root):
    with make_client() as c:
        ready_character(c, root, "hero")
    seed_running_attempt(root)
    guard = open(root / ".codex.lock", "a+")
    fcntl.flock(guard, fcntl.LOCK_EX)  # e.g. a Skill CLI generation is running right now
    try:
        with make_client() as c:
            assert c.app.state.recovery == {"skipped": True, "interrupted": [], "locks_removed": []}
            assert c.get(char_url("hero", "/actions/idle/attempts")).json()["attempts"][0]["generation_status"] == "running"
    finally:
        guard.close()


def test_interrupted_recovery_ignores_missing_root_and_broken_manifests(make_client, root):
    with make_client() as c:  # root does not exist yet
        assert c.app.state.recovery == {"skipped": False, "interrupted": [], "locks_removed": []}
        ready_character(c, root, "hero")
    (root / "hero" / "manifest.json").write_text("{not json")
    (root / "not-a-character").mkdir()
    with make_client() as c:
        assert c.app.state.recovery["interrupted"] == []


def test_interrupted_job_state_when_server_stops_with_queued_and_running_jobs(make_client, root, monkeypatch):
    monkeypatch.setenv("FAKE_CODEX_MODE", "hang")
    c = make_client()
    with c:
        ready_character(c, root, "hero")
        events = record_events(c)
        running = post_generate(c)["job"]["id"]
        queued = post_generate(c)["job"]["id"]
        wait_until(lambda: job_of(c, running)["stage"] == "generating", what="generating")
    final = {}
    for e in events:
        final[e["id"]] = e["state"]
    assert final == {running: "interrupted", queued: "interrupted"}
