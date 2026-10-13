"""POST .../attempts/{aid}/resume: finishes an unfinished video attempt as a Job (video provider only, no Codex)."""

import shutil
from pathlib import Path

import pytest
from sg_helpers import Clock, Script
from sprite_forge import generation, identity
from sprite_forge import plan as plan_mod
from sprite_forge.errors import ForgeError
from sprite_forge.providers import XaiVideoProvider

from .api_sync_helpers import char_url, err
from .jobs_helpers import wait_job
from .test_jobs_video import video_character

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None, reason="ffmpeg missing")
PENDING = (200, b'{"status": "pending"}')


@pytest.fixture
def fake_video(monkeypatch):
    monkeypatch.setenv("SPRITE_FORGE_VIDEO_PROVIDER", "fake")


def unfinished_attempt(jc, root):
    """A video character whose walk generation was accepted by the provider and then timed out."""
    video_character(jc, root)
    cd = Path(root) / "hero"
    clock = Clock()
    provider = XaiVideoProvider(transport=Script(clock, polls=[PENDING], step=100.0), token="tok-1234567890",
                                clock=clock, sleep=clock.sleep)
    with pytest.raises(ForgeError):
        generation.generate_unit(cd, plan_mod.load_plan(cd), identity.load_profile(cd), "walk", video_provider=provider)
    return cd


def resume_url(aid="001", action="walk"):
    return char_url("hero", f"/actions/{action}/attempts/{aid}/resume")


@needs_ffmpeg
def test_sg_provider_resume_api_finishes_the_attempt_as_a_job_without_codex(jc, root, fake_video, monkeypatch):
    unfinished_attempt(jc, root)
    monkeypatch.setenv("FAKE_CODEX_DOCTOR", "logged_out")  # a resume needs the video provider, not Codex
    r = jc.post(resume_url())
    assert r.status_code == 202, r.text
    job = wait_job(jc, r.json()["job"]["id"], timeout=60)
    assert job["state"] == "succeeded", job
    assert job["result"]["attempt"] == "001" and job["result"]["qc_status"] in ("pass", "warn", "fail")
    detail = jc.get(char_url("hero", "/actions/walk/attempts/001")).json()
    assert len(detail["files"]["frames"]) == 6 and detail["files"]["video"]
    assert sorted(p.name for p in (Path(root) / "hero/walk/attempts").iterdir()) == ["001"]


def test_sg_provider_resume_api_refuses_what_cannot_be_resumed(jc, root, fake_video):
    unfinished_attempt(jc, root)
    err(jc.post(resume_url("009")), 404, "not_found")
    err(jc.post(resume_url("abc")), 404, "not_found")
    (Path(root) / "hero/walk/attempts/001/video-request.json").unlink()
    err(jc.post(resume_url()), 412, "precondition_failed")
    assert jc.get("/api/jobs").json() == {"jobs": []}


def test_sg_provider_resume_api_needs_a_connected_video_provider(jc, root, fake_video, monkeypatch):
    unfinished_attempt(jc, root)
    monkeypatch.delenv("SPRITE_FORGE_VIDEO_PROVIDER")
    err(jc.post(resume_url()), 412, "precondition_failed")
    assert jc.get("/api/jobs").json() == {"jobs": []}
