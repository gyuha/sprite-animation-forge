"""Video provider robustness (docs/14 area A): one deadline, unfinished-on-request_id, masking, refusal lines.
Scripted transports and a fake clock; no network, no real credentials."""

import json

import pytest
from sprite_forge.providers import VideoRequest, XaiVideoProvider
from sprite_forge.providers import redact as rd
from sg_helpers import ACCEPTED, LONG_KEY, OK_DONE, Clock, Script  # noqa: F401
from sprite_forge.providers.fake_video import FAKE_MP4
from sprite_forge.providers.xai_video import TransportError


@pytest.fixture
def frame(tmp_path):
    p = tmp_path / "first.png"
    p.write_bytes(b"\x89PNG-fake")
    return p


def make(script, clock, **kw):
    return XaiVideoProvider(transport=script, token=kw.pop("token", "tok-1234567890"), clock=clock, sleep=clock.sleep,
                            poll_interval_s=kw.pop("poll_interval_s", 2.0), backoff_s=kw.pop("backoff_s", 1.0), **kw)


def req(tmp_path, frame, **kw):
    return VideoRequest("p", frame, tmp_path / "out" / "v.mp4", **kw)


def test_sg_provider_one_deadline_bounds_every_call_and_names_the_request(tmp_path, frame):
    clock = Clock()
    script = Script(clock, polls=[(200, json.dumps({"status": "pending"}).encode())], step=7.0)
    res = make(script, clock).generate(req(tmp_path, frame, timeout_s=30))
    assert (res.status, res.error_code) == ("timeout", "video_timeout")
    assert res.meta["request_id"] == "req-1" and res.meta["unfinished"] is True
    started = 1000.0
    assert clock.now - started <= 30 + 7.0 + 2.0  # at most one call past the deadline, never a wait past it
    polls = [c for c in script.calls if c[0] == "GET"]
    assert all(c[2] <= 30 for c in polls) and polls[-1][2] < polls[0][2]  # each read waits only for the time left


def test_sg_provider_no_wait_is_started_that_would_reach_the_deadline(tmp_path, frame):
    clock = Clock()
    slept = []
    script = Script(clock, polls=[(200, json.dumps({"status": "pending"}).encode())])
    provider = make(script, clock, poll_interval_s=10.0)
    provider._sleep = lambda s: (slept.append(s), clock.sleep(s))
    res = provider.generate(req(tmp_path, frame, timeout_s=25))
    assert res.error_code == "video_timeout" and res.meta["request_id"] == "req-1"
    assert clock.now <= 1000.0 + 25 and slept == [10.0, 10.0]  # the third wait would have reached the deadline: not started


def test_sg_provider_download_is_retried_then_succeeds(tmp_path, frame):
    clock = Clock()
    script = Script(clock, polls=[(200, OK_DONE)], downloads=[(503, b""), TransportError("reset"), (200, FAKE_MP4)])
    res = make(script, clock, retries=3).generate(req(tmp_path, frame))
    assert res.status == "succeeded" and res.video_path.read_bytes() == FAKE_MP4
    assert len([c for c in script.calls if c[1].startswith("https://cdn")]) == 3
    assert len([c for c in script.calls if c[0] == "POST"]) == 1  # nothing was bought twice


def test_sg_provider_download_still_failing_ends_unfinished_on_the_request_id(tmp_path, frame):
    clock = Clock()
    script = Script(clock, polls=[(200, OK_DONE)], downloads=[(503, b"")])
    res = make(script, clock, retries=2).generate(req(tmp_path, frame))
    assert (res.status, res.error_code) == ("failed", "video_unfinished")
    assert res.meta["request_id"] == "req-1" and res.meta["unfinished"] is True and res.video_path is None
    assert len([c for c in script.calls if c[1].startswith("https://cdn")]) == 3  # retries + 1 downloads


def test_sg_provider_a_download_refused_with_another_status_is_not_retried(tmp_path, frame):
    clock = Clock()
    script = Script(clock, polls=[(200, OK_DONE)], downloads=[(403, b"{}")])
    res = make(script, clock, retries=3).generate(req(tmp_path, frame))
    assert res.error_code == "video_unfinished" and "HTTP 403" in res.error_message
    assert len([c for c in script.calls if c[1].startswith("https://cdn")]) == 1


def test_sg_provider_done_without_a_url_ends_unfinished(tmp_path, frame):
    clock = Clock()
    script = Script(clock, polls=[(200, json.dumps({"status": "done", "video": {}}).encode())])
    res = make(script, clock).generate(req(tmp_path, frame))
    assert (res.error_code, res.meta["request_id"], res.meta["unfinished"]) == ("video_unfinished", "req-1", True)


@pytest.mark.parametrize("bad", [(200, b'{"status": "pen'), (200, b"<html>gateway</html>"), (502, b""), (429, b"{}"),
                                 TransportError("reset by peer")])
def test_sg_provider_an_unreadable_poll_is_asked_again_on_the_same_id(tmp_path, frame, bad):
    clock = Clock()
    script = Script(clock, polls=[bad, bad, (200, OK_DONE)], downloads=[(200, FAKE_MP4)])
    res = make(script, clock).generate(req(tmp_path, frame))
    assert res.status == "succeeded"
    assert len([c for c in script.calls if c[0] == "POST"]) == 1
    assert len([c for c in script.calls if c[1].endswith("/v1/videos/req-1")]) == 3


def test_sg_provider_poll_wait_doubles_while_polls_fail(tmp_path, frame):
    clock = Clock()
    slept = []
    script = Script(clock, polls=[(503, b""), (503, b""), (503, b""), (200, OK_DONE)], downloads=[(200, FAKE_MP4)])
    provider = make(script, clock, poll_interval_s=2.0)
    provider._sleep = lambda s: (slept.append(s), clock.sleep(s))
    assert provider.generate(req(tmp_path, frame)).status == "succeeded"
    assert slept[:3] == [4.0, 8.0, 16.0]


def test_sg_provider_credentials_rejected_on_a_poll_keep_the_request_id(tmp_path, frame):
    clock = Clock()
    script = Script(clock, polls=[(401, b'{"error": "expired"}')])
    res = make(script, clock).generate(req(tmp_path, frame))
    assert res.error_code == "video_auth_failed" and res.meta["request_id"] == "req-1" and res.meta["unfinished"] is True


def test_sg_provider_masks_keys_bearer_tokens_and_signatures():
    text = f"bad key {LONG_KEY} and api_key_{LONG_KEY} and Authorization: Bearer abcdefghijklmnop1234 at https://cdn.x/v.mp4?X-Amz-Signature=deadbeef&Expires=1"
    out = rd.redact(text)
    assert LONG_KEY not in out and "abcdefghijklmnop1234" not in out and "deadbeef" not in out
    assert out.count(rd.REDACTED) == 4 and "https://cdn.x/v.mp4?[redacted]" in out
    assert rd.redact("task-" + "x" * 30) == "task-" + "x" * 30  # a word, not a key
    assert rd.redact("xai-****abcd1234efgh5678") == "xai-****abcd1234efgh5678"  # already masked by the provider


def test_sg_provider_the_credential_is_masked_even_when_it_has_no_key_shape():
    assert "opaque-login-token-123" not in rd.redact("echo opaque-login-token-123 here", "opaque-login-token-123")


def test_sg_provider_masks_before_it_cuts_so_no_half_key_survives():
    body = {"error": {"message": "x" * (rd.MAX_BODY_CHARS - 10) + " " + LONG_KEY + " tail"}}
    line = rd.said(body)
    assert "xai-" not in line.replace("[redacted]", "") or "xai-[redacted]" in line
    assert LONG_KEY[:12] not in line and LONG_KEY[-12:] not in line


def test_sg_provider_error_messages_never_carry_the_credential(tmp_path, frame):
    clock = Clock()
    token = "tok-SECRET-9876543210"
    script = Script(clock, post=(400, json.dumps({"error": {"message": f"bad token {token}", "code": "invalid_argument"}}).encode()))
    res = make(script, clock, token=token).generate(req(tmp_path, frame))
    assert token not in res.error_message and res.error_code == "video_request_failed"


def test_sg_provider_a_refusal_line_names_the_status_and_the_providers_code(tmp_path, frame):
    clock = Clock()
    body = json.dumps({"error": {"code": "invalid_argument", "message": "duration out of range"}}).encode()
    res = make(Script(clock, post=(400, body)), clock).generate(req(tmp_path, frame))
    assert "(HTTP 400)" in res.error_message and " code=invalid_argument" in res.error_message
    assert res.error_message.index("(HTTP 400)") < res.error_message.index("code=") < res.error_message.index("duration out of range")


def test_sg_provider_a_moderated_clip_says_content_policy_and_is_not_resumable(tmp_path, frame):
    clock = Clock()
    done = json.dumps({"status": "done", "video": {"respect_moderation": False}}).encode()
    res = make(Script(clock, polls=[(200, done)]), clock).generate(req(tmp_path, frame))
    assert res.error_code == "video_content_policy" and "content policy" in res.error_message
    assert not res.meta.get("unfinished") and res.meta["request_id"] == "req-1"


def test_sg_provider_provider_code_reads_both_error_shapes():
    assert rd.provider_code({"error": {"code": "moderation_blocked"}}) == "moderation_blocked"
    assert rd.provider_code({"code": "rate_limited", "error": "too many"}) == "rate_limited"
    assert rd.provider_code({"error": {"code": "has space"}}) is None and rd.provider_code("text") is None


# ---- resume: ask again for an accepted request, submit nothing ------------------------------------------------

def test_sg_provider_resume_polls_and_downloads_without_submitting(tmp_path):
    clock = Clock()
    script = Script(clock, polls=[(200, json.dumps({"status": "pending"}).encode()), (200, OK_DONE)], downloads=[(200, FAKE_MP4)])
    out = tmp_path / "raw.mp4"
    res = make(script, clock).resume("req-77", out, timeout_s=60)
    assert res.status == "succeeded" and out.read_bytes() == FAKE_MP4 and res.meta["request_id"] == "req-77"
    assert [c[0] for c in script.calls].count("POST") == 0 and any(c[1].endswith("/v1/videos/req-77") for c in script.calls)


def test_sg_provider_resume_that_runs_out_of_time_keeps_the_request_resumable(tmp_path):
    clock = Clock()
    script = Script(clock, polls=[(200, json.dumps({"status": "pending"}).encode())], step=5.0)
    res = make(script, clock).resume("req-77", tmp_path / "raw.mp4", timeout_s=20)
    assert (res.status, res.error_code) == ("timeout", "video_timeout")
    assert res.meta["request_id"] == "req-77" and res.meta["unfinished"] is True and not (tmp_path / "raw.mp4").exists()


def test_sg_provider_resume_without_credentials_refuses_and_names_the_id(tmp_path, monkeypatch):
    res = XaiVideoProvider(transport=Script(Clock()), clock=Clock()).resume("req-77", tmp_path / "raw.mp4")
    assert res.error_code == "video_not_configured" and res.meta["request_id"] == "req-77"
