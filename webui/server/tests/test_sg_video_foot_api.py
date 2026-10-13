"""The attempt detail carries ``video_meta`` (the loop report of a method=video attempt)."""

import shutil

import pytest

from .api_sync_helpers import char_url
from .jobs_helpers import post_generate, wait_job
from .test_jobs_video import video_character

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None, reason="ffmpeg missing")


@needs_ffmpeg
def test_sg_video_foot_api_attempt_detail_exposes_the_video_meta(jc, root, monkeypatch):
    monkeypatch.setenv("SPRITE_FORGE_VIDEO_PROVIDER", "fake")
    video_character(jc, root)
    job = wait_job(jc, post_generate(jc, action="walk")["job"]["id"], timeout=60)
    assert job["state"] == "succeeded", job
    meta = jc.get(char_url("hero", "/actions/walk/attempts/001")).json()["video_meta"]
    assert {"start_foot_source", "jolt_index", "head_move", "size_hold", "held", "indices"} <= set(meta)


def test_sg_video_foot_api_a_grid_attempt_has_no_video_meta(jc, root):
    from .jobs_helpers import ready_character
    ready_character(jc, root, "hero", actions=("idle",))
    job = wait_job(jc, post_generate(jc, action="idle")["job"]["id"])
    assert job["state"] == "succeeded"
    assert jc.get(char_url("hero", "/actions/idle/attempts/001")).json()["video_meta"] is None
