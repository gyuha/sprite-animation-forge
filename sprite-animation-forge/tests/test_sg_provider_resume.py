"""Resuming an unfinished video generation (docs/14 area A): Core, CLI. A scripted provider leaves the attempt
unfinished; ``resume`` finishes THE SAME attempt without submitting again."""

import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest
from fixtures.synthetic.make import make_sheet
from sg_helpers import Clock, Script
from sprite_forge import generation, identity
from sprite_forge import manifest as mf
from sprite_forge import plan as plan_mod
from sprite_forge.errors import ForgeError
from sprite_forge.providers import XaiVideoProvider
from sprite_forge.providers.fake_video import make_bobbing_mp4

FAKE = Path(__file__).resolve().parent / "fixtures" / "fake_codex" / "codex"
needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None, reason="ffmpeg missing")
PENDING = (200, json.dumps({"status": "pending"}).encode())
DONE = (200, json.dumps({"status": "done", "video": {"url": "https://cdn.fake/v.mp4"}}).encode())


@pytest.fixture
def env(tmp_path, monkeypatch):
    home = tmp_path / "codex_home"
    home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.setenv("SPRITE_FORGE_CODEX_BIN", str(FAKE))
    for k in [k for k in os.environ if k.startswith("FAKE_CODEX")]:
        monkeypatch.delenv(k)
    monkeypatch.setenv("FAKE_CODEX_IMAGE", "clean")
    monkeypatch.setenv("SPRITE_FORGE_VIDEO_PROVIDER", "fake")  # a plan may only choose method=video when a provider is connected


@pytest.fixture
def hero(forge, tmp_path, env):
    ref = tmp_path / "ref.png"
    make_sheet("clean", rows=1, cols=1).save(ref)
    forge.ok("init", "hero")
    forge.ok("reference", "import", "hero", ref)
    forge.ok("identity", "analyze", "hero")
    return forge


def plan_walk(forge, video=True):
    sets = ["--set", "walk.method=video", "--set", "walk.frames=6"] if video else []
    forge.ok("plan", "hero", "--actions", "walk,idle", *sets)


def load(forge):
    cd = forge.root / "hero"
    return cd, plan_mod.load_plan(cd), identity.load_profile(cd)


def clip_bytes(tmp_path):
    out = tmp_path / "clip.mp4"
    png = tmp_path / "c.png"
    from PIL import Image
    img = Image.new("RGB", (480, 480), (255, 0, 255))
    img.paste((30, 140, 220), (182, 120, 298, 240))
    img.paste((200, 60, 40), (182, 240, 298, 384))
    img.save(png)
    assert make_bobbing_mp4(png.read_bytes(), out)
    return out.read_bytes()


def leave_unfinished(forge, polls=(PENDING,)):
    """generate with a provider that times out after the request was accepted -> attempt 001 left unfinished."""
    cd, plan, profile = load(forge)
    clock = Clock()
    script = Script(clock, polls=list(polls), step=100.0)
    provider = XaiVideoProvider(transport=script, token="tok-1234567890", clock=clock, sleep=clock.sleep)
    with pytest.raises(ForgeError) as exc:
        generation.generate_unit(cd, plan, profile, "walk", video_provider=provider)
    return cd, plan, exc.value, script


def test_sg_provider_resume_an_unfinished_generation_leaves_the_request_id_to_resume(hero):
    plan_walk(hero)
    cd, plan, err, script = leave_unfinished(hero)
    adir = cd / "walk" / "attempts" / "001"
    assert err.code == "video_timeout" and err.extra["attempt"] == "001"
    assert err.extra["request_id"] == "req-1" and err.extra["resumable"] is True
    saved = json.loads((adir / "video-request.json").read_text())
    assert saved["request_id"] == "req-1" and saved["pinned_last_frame"] is False and not (adir / "raw.png").exists()
    assert mf.load(cd)["actions"]["walk"]["attempts"]["001"]["generation_status"] == "timeout"  # the provider result status, as on the image path


@needs_ffmpeg
def test_sg_provider_resume_finishes_the_same_attempt_without_a_second_submission(hero, tmp_path):
    plan_walk(hero)
    cd, plan, _, first = leave_unfinished(hero)
    clock = Clock()
    script = Script(clock, polls=[DONE], downloads=[(200, clip_bytes(tmp_path))])
    provider = XaiVideoProvider(transport=script, token="tok-1234567890", clock=clock, sleep=clock.sleep)
    out = generation.resume_video_unit(cd, plan, "walk", attempt="001", video_provider=provider)
    adir = cd / "walk" / "attempts" / "001"
    assert out == {"attempt": "001", "unit": "walk", "status": "succeeded"}
    assert [c[0] for c in script.calls].count("POST") == 0
    assert (adir / "raw.png").is_file() and (adir / "raw.mp4").is_file() and not (adir / "video-request.json").exists()
    assert json.loads((adir / "generation.json").read_text())["video"]["request_id"] == "req-1"
    assert mf.load(cd)["actions"]["walk"]["attempts"]["001"]["generation_status"] == "succeeded"
    assert sorted(p.name for p in (cd / "walk" / "attempts").iterdir()) == ["001"]  # no second attempt was allocated


def test_sg_provider_resume_after_the_provider_itself_failed_is_not_offered(hero):
    plan_walk(hero)
    failed = (200, json.dumps({"status": "failed", "error": "content policy"}).encode())
    cd, plan, err, _ = leave_unfinished(hero, polls=[failed])
    assert err.code == "video_failed" and err.extra["resumable"] is False
    assert not (cd / "walk" / "attempts" / "001" / "video-request.json").exists()
    with pytest.raises(ForgeError) as e:
        generation.resume_video_unit(cd, plan, "walk", attempt="001")
    assert e.value.code == "not_resumable"


def test_sg_provider_resume_that_is_refused_credentials_keeps_the_id(hero):
    plan_walk(hero)
    cd, plan, _, _ = leave_unfinished(hero)
    clock = Clock()
    provider = XaiVideoProvider(transport=Script(clock, polls=[(401, b"{}")]), token="tok-1234567890", clock=clock, sleep=clock.sleep)
    with pytest.raises(ForgeError) as e:
        generation.resume_video_unit(cd, plan, "walk", attempt="001", video_provider=provider)
    assert e.value.code == "video_auth_failed" and e.value.extra["resumable"] is True
    assert (cd / "walk" / "attempts" / "001" / "video-request.json").is_file()


def test_sg_provider_resume_refuses_what_is_not_an_unfinished_video_attempt(hero):
    plan_walk(hero)
    cd, plan, _, _ = leave_unfinished(hero)
    with pytest.raises(ForgeError) as e:  # an image-method action
        generation.resume_video_unit(cd, plan, "idle", attempt="001")
    assert e.value.code == "not_resumable"
    with pytest.raises(ForgeError) as e:
        generation.resume_video_unit(cd, plan, "walk", attempt="009")
    assert e.value.code == "no_attempt"
    with pytest.raises(ForgeError) as e:
        generation.resume_video_unit(cd, plan, "walk", attempt=None)
    assert e.value.code == "no_attempt"
    (cd / "walk" / "attempts" / "001" / "raw.png").write_bytes(b"x")  # already finished
    with pytest.raises(ForgeError) as e:
        generation.resume_video_unit(cd, plan, "walk", attempt="001")
    assert e.value.code == "not_resumable"


@needs_ffmpeg
def test_sg_provider_resume_cli_finishes_the_attempt_then_process_and_accept_work(hero):
    plan_walk(hero)
    leave_unfinished(hero)
    out = hero.ok("resume", "hero", "walk", "--attempt", "001")
    assert out == {"attempt": "001", "unit": "walk", "status": "succeeded"}
    assert hero.ok("process", "hero", "walk")["qc"]["status"] in ("pass", "warn", "fail")
    hero.ok("accept", "hero", "walk")


def test_sg_provider_resume_cli_reports_a_missing_request_as_a_precondition(hero):
    plan_walk(hero, video=False)
    code, out = hero.run("resume", "hero", "walk", "--attempt", "001")
    assert code == 3 and out["error_code"] in ("not_resumable", "no_attempt")
    assert hero.run("resume", "hero", "walk")[0] == 1  # --attempt is required
