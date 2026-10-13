"""Video provider (docs/13): XaiVideoProvider against FakeXaiTransport. No network, no real credentials."""

import json

import pytest
from sprite_forge import doctor, plan as pl
from sprite_forge.providers import VideoRequest, XaiVideoProvider
from sprite_forge.providers import xai_video
from sprite_forge.providers.fake_video import FAKE_MP4, FakeXaiTransport
from sprite_forge.providers.video_base import is_mp4
from sprite_forge.providers.video_factory import make_video_provider


@pytest.fixture
def frame(tmp_path):
    p = tmp_path / "first.png"
    p.write_bytes(b"\x89PNG-fake")
    return p


def provider(transport, **kw):
    kw.setdefault("poll_interval_s", 0.0)
    kw.setdefault("sleep", lambda s: None)
    return XaiVideoProvider(transport=transport, token=kw.pop("token", "tok"), **kw)


def req(tmp_path, frame, **kw):
    return VideoRequest("a hero idles", frame, tmp_path / "out" / "video.mp4", **kw)


def test_success_polls_then_downloads_an_atomic_mp4(tmp_path, frame):
    t = FakeXaiTransport(polls_until_done=3)
    res = provider(t).generate(req(tmp_path, frame))
    assert res.status == "succeeded" and res.video_path.read_bytes() == FAKE_MP4
    assert [c[0] for c in t.calls] == ["POST", "GET", "GET", "GET", "GET"]
    assert res.meta["request_id"] == "req-1" and res.meta["model"] == xai_video.DEFAULT_MODEL
    assert not list(res.video_path.parent.glob("*.tmp*"))


def test_request_carries_first_and_last_frame_prompt_and_settings(tmp_path, frame):
    t = FakeXaiTransport()
    provider(t).generate(req(tmp_path, frame, last_frame=frame, duration_s=4, resolution="480p"))
    body = t.requests[0]
    assert body["prompt"] == "a hero idles" and body["duration"] == 4 and body["resolution"] == "480p"
    assert body["image"]["url"].startswith("data:image/png;base64,") and "last_image" in body
    t2 = FakeXaiTransport()
    provider(t2).generate(req(tmp_path, frame))
    assert "last_image" not in t2.requests[0]


def test_download_does_not_send_the_api_token(tmp_path, frame):
    t = FakeXaiTransport()
    provider(t).generate(req(tmp_path, frame))
    assert t.auth_headers[0] == "Bearer tok" and t.auth_headers[-1] is None


def test_generation_failure_is_reported(tmp_path, frame):
    res = provider(FakeXaiTransport("fail")).generate(req(tmp_path, frame))
    assert (res.status, res.error_code) == ("failed", "video_failed") and "content policy" in res.error_message
    assert res.video_path is None


def test_timeout(tmp_path, frame):
    res = provider(FakeXaiTransport("pending")).generate(req(tmp_path, frame, timeout_s=0))
    assert (res.status, res.error_code) == ("timeout", "video_timeout")


def test_rate_limit_is_retried_with_backoff_then_succeeds(tmp_path, frame):
    sleeps = []
    t = FakeXaiTransport("rate_limit", rate_limits=2)
    res = provider(t, sleep=sleeps.append, backoff_s=1.0).generate(req(tmp_path, frame))
    assert res.status == "succeeded" and sleeps[:2] == [1.0, 2.0]


def test_rate_limit_exhausted_fails(tmp_path, frame):
    res = provider(FakeXaiTransport("rate_limit", rate_limits=99), retries=1).generate(req(tmp_path, frame))
    assert (res.status, res.error_code) == ("failed", "video_request_failed") and "429" in res.error_message


def test_rejected_credentials(tmp_path, frame):
    res = provider(FakeXaiTransport("unauthorized")).generate(req(tmp_path, frame))
    assert res.error_code == "video_auth_failed"


def test_non_mp4_download_is_rejected_and_nothing_is_written(tmp_path, frame):
    r = req(tmp_path, frame)
    res = provider(FakeXaiTransport("bad_file")).generate(r)
    assert res.error_code == "video_bad_file" and not r.out_path.exists()


def test_is_mp4():
    assert is_mp4(FAKE_MP4) and not is_mp4(b"RIFF....WEBP") and not is_mp4(b"")


def test_no_credentials_means_not_configured_and_generate_refuses(tmp_path, frame):
    p = XaiVideoProvider(transport=FakeXaiTransport())
    assert p.check()["configured"] is False and p.check()["auth"] is None
    assert p.generate(req(tmp_path, frame)).error_code == "video_not_configured"


def test_auth_json_wins_over_env(tmp_path, monkeypatch):
    auth = tmp_path / "auth.json"
    auth.write_text(json.dumps({"api_key": "from-file"}))
    monkeypatch.setenv("SPRITE_FORGE_GROK_AUTH", str(auth))
    monkeypatch.setenv("XAI_API_KEY", "from-env")
    assert xai_video.load_auth() == ("from-file", "grok_auth_json")
    auth.write_text("{not json")
    assert xai_video.load_auth() == ("from-env", "env")


def test_env_only(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "k")
    assert XaiVideoProvider().check() == {"provider": "xai", "configured": True, "auth": "env", "model": xai_video.DEFAULT_MODEL}


def test_cancel_stops_polling(tmp_path, frame):
    p = provider(FakeXaiTransport("pending"))
    p._sleep = lambda s: p.cancel()
    assert p.generate(req(tmp_path, frame)).status == "canceled"


def test_factory_fake_is_configured_and_works_offline(tmp_path, frame, monkeypatch):
    monkeypatch.setenv("SPRITE_FORGE_VIDEO_PROVIDER", "fake")
    p = make_video_provider()
    assert p.check()["configured"] is True and p.name == "fake"
    assert p.generate(req(tmp_path, frame)).status == "succeeded"


def test_doctor_reports_video_but_it_never_blocks_ready():
    out = doctor.run_doctor()
    assert out["video"]["configured"] is False
    assert not any("video" in w for w in out["warnings"])


def test_video_method_follows_the_provider_connection(monkeypatch):
    assert pl.video_method_available() is False
    monkeypatch.setenv("XAI_API_KEY", "k")
    assert pl.video_method_available() is True
    monkeypatch.delenv("XAI_API_KEY")
    assert pl.video_method_available() is False
