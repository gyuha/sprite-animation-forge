"""method=video through the Job layer with the fake video provider (SPRITE_FORGE_VIDEO_PROVIDER=fake, no network)."""

import io
import shutil
from pathlib import Path

import pytest
from PIL import Image
from sprite_forge import identity

from .api_sync_helpers import char_url, err, make_character, make_plan, png_file
from .jobs_helpers import post_generate, wait_job

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None, reason="ffmpeg missing")


def character_upload() -> bytes:
    img = Image.new("RGB", (300, 300), (255, 255, 255))
    for y in range(60, 250):
        for x in range(110, 190):
            img.putpixel((x, y), (30, 140, 220) if y < 150 else (200, 60, 40))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def video_character(jc, root, sets=("walk.method=video", "walk.frames=6")):
    make_character(jc, "hero")
    assert jc.post(char_url("hero", "/reference"), files=png_file(character_upload())).status_code == 200
    identity.write_empty(Path(root) / "hero")
    make_plan(jc, "hero", actions=["walk"], set=list(sets))


@pytest.fixture
def fake_video(monkeypatch):
    monkeypatch.setenv("SPRITE_FORGE_VIDEO_PROVIDER", "fake")


@needs_ffmpeg
def test_jobs_video_generate_runs_without_codex_and_serves_the_clip(jc, root, fake_video, monkeypatch):
    monkeypatch.setenv("FAKE_CODEX_DOCTOR", "logged_out")  # Codex is NOT needed for a video unit
    video_character(jc, root)
    job = wait_job(jc, post_generate(jc, action="walk")["job"]["id"], timeout=60)
    assert job["state"] == "succeeded", job
    assert job["result"]["attempt"] == "001" and job["result"]["qc_status"] in ("pass", "warn", "fail")
    detail = jc.get(char_url("hero", "/actions/walk/attempts/001")).json()
    assert detail["files"]["video"].startswith("/files/hero/walk/attempts/001/raw.mp4")
    assert len(detail["files"]["frames"]) == 6 and detail["summary"]["prompt_version"] == "video_prompt@1"
    clip = jc.get(detail["files"]["video"])
    assert clip.status_code == 200 and clip.content[4:8] == b"ftyp"


def test_jobs_video_generate_without_a_connected_provider_is_a_precondition_error(jc, root, monkeypatch):
    monkeypatch.setenv("SPRITE_FORGE_VIDEO_PROVIDER", "fake")
    video_character(jc, root)
    monkeypatch.delenv("SPRITE_FORGE_VIDEO_PROVIDER")
    err(jc.post(char_url("hero", "/actions/walk/generate"), json={}), 412, "precondition_failed")
    assert jc.get("/api/jobs").json() == {"jobs": []}


def test_jobs_video_plan_with_several_directions_is_rejected(jc, root, fake_video):
    make_character(jc, "hero", view="topdown")
    r = jc.post(char_url("hero", "/plan"), json={"actions": ["walk"], "view": "topdown", "set": ["walk.method=video"]})
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_param"


@needs_ffmpeg
def test_jobs_video_batch_generate_all_with_a_video_unit(jc, root, fake_video, monkeypatch):
    monkeypatch.setenv("FAKE_CODEX_DOCTOR", "logged_out")
    video_character(jc, root)
    r = jc.post(char_url("hero", "/generate-all"), json={"auto_accept": True})
    assert r.status_code == 202, r.text
    job = wait_job(jc, r.json()["job"]["id"], timeout=90)
    assert job["state"] == "succeeded" and job["result"]["units"][0]["attempt"] == "001", job
