"""xAI Grok Imagine video provider (docs/13-video-api-setup.md). Re-implemented from the public API shape;
the endpoint, model and response field names are settings because they are NOT verified against a live account.

Flow: ``POST {base}/v1/videos/generations`` -> request id -> poll ``GET {base}/v1/videos/{id}`` until ``done`` ->
download the mp4 (checked for ``ftyp``, written atomically).

Time: ``VideoRequest.timeout_s`` is ONE deadline, counted from the moment the request is sent, for the polls, the waits
between them and the download alike; every call waits only for the time left. The POST is never cut by it (its answer is
the only way to the request id). Once the request is accepted, any ending that is not xAI's own "failed" carries
``meta.request_id`` and ``meta.unfinished=True``: the clip may be billed, and ``resume`` asks again for it by that id.

Retries: a poll answered 429/5xx, one that gets no readable answer (transport error, cut short, not JSON) is asked again
on the same id after a doubling wait. The POST and the download retry ``retries`` times; a download still failing, or a
done poll that names no url, ends ``video_unfinished`` (bytes that are not an mp4 end ``video_bad_file``).

Errors shown to the user are masked (keys, ``Bearer`` tokens, URL signatures) before they are cut, and name the provider's
own ``code`` (``refusal_line``). Auth priority: ``~/.grok/auth.json`` (``grok login``; ``SPRITE_FORGE_GROK_AUTH``), then
``XAI_API_KEY``. ``transport(method, url, headers, body, timeout) -> (status, bytes)`` is injectable (tests never touch the
network); it raises ``TransportError`` when no answer could be read.
"""

from __future__ import annotations

import base64
import http.client
import json
import os
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from ..fsutil import atomic_write_bytes
from .base import ProgressFn
from .redact import parse_body, refusal_line
from .video_base import VideoRequest, VideoResult, is_mp4

DEFAULT_BASE_URL = "https://api.x.ai"
DEFAULT_MODEL = "grok-imagine-video-1.5"  # unverified: confirm in the xAI console / docs
RETRY_STATUS = {429, 500, 502, 503, 504}
AUTH_KEYS = ("api_key", "apiKey", "key", "access_token", "token")
POLL_BACKOFF_MAX_S = 60.0
CALL_TIMEOUT_S = 60.0
DOWNLOAD_TIMEOUT_S = 300.0


class TransportError(Exception):
    """No answer could be read (connection failed, timed out, or the answer broke on the way)."""


def urllib_transport(method: str, url: str, headers: dict, body: bytes | None, timeout: float) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, exc.read()
        except (OSError, http.client.HTTPException) as err:
            raise TransportError(str(err)) from None
    except (OSError, http.client.HTTPException) as exc:  # URLError, timeouts, resets, IncompleteRead
        raise TransportError(str(exc)) from None


def load_auth() -> tuple[str | None, str | None]:
    """``(token, source)``; source is ``grok_auth_json`` / ``env`` / None."""
    path = Path(os.environ.get("SPRITE_FORGE_GROK_AUTH") or Path.home() / ".grok" / "auth.json")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        for k in AUTH_KEYS:
            if isinstance(data.get(k), str) and data[k]:
                return data[k], "grok_auth_json"
    except (OSError, ValueError, AttributeError):
        pass
    key = os.environ.get("XAI_API_KEY")
    return (key, "env") if key else (None, None)


class XaiVideoProvider:
    name = "xai"

    def __init__(self, transport=None, base_url: str | None = None, model: str | None = None,
                 poll_interval_s: float = 5.0, retries: int = 3, backoff_s: float = 2.0, sleep=time.sleep,
                 token: str | None = None, clock=time.monotonic):
        self.transport = transport or urllib_transport
        self.base_url = (base_url or os.environ.get("SPRITE_FORGE_XAI_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.model = model or os.environ.get("SPRITE_FORGE_XAI_VIDEO_MODEL") or DEFAULT_MODEL
        self.poll_interval_s, self.retries, self.backoff_s, self._sleep = poll_interval_s, retries, backoff_s, sleep
        self._clock = clock
        self._token = token  # injected credentials (fake provider); bypasses auth.json / env
        self._cancel = threading.Event()

    def _auth(self) -> tuple[str | None, str | None]:
        return (self._token, "injected") if self._token else load_auth()

    def check(self) -> dict:
        token, source = self._auth()
        return {"provider": self.name, "configured": token is not None, "auth": source, "model": self.model}

    def cancel(self) -> None:
        self._cancel.set()

    # ---- one call --------------------------------------------------------------------------------------------

    def _once(self, method, url, headers, body, timeout, deadline) -> tuple[int, bytes] | None:
        """One transport call that waits only for the time left; ``None`` when no answer could be read."""
        if deadline is not None:
            timeout = min(timeout, max(deadline - self._clock(), 0.001))
        try:
            return self.transport(method, url, headers, body, timeout)
        except TransportError:
            return None

    def _wait(self, seconds: float, deadline: float | None) -> bool:
        """Sleep ``seconds`` unless that would reach the deadline (or the run was canceled); False = do not go on."""
        if self._cancel.is_set() or (deadline is not None and self._clock() + seconds >= deadline):
            return False
        self._sleep(seconds)
        return not self._cancel.is_set()

    def _call(self, method, url, token, payload=None, timeout=CALL_TIMEOUT_S, deadline=None) -> tuple[int, bytes]:
        """POST / download style call: retried ``retries`` times on 429/5xx and unreadable answers. ``(0, b"")`` = no answer."""
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"} if token else {}
        body = json.dumps(payload).encode() if payload is not None else None
        reply = None
        for attempt in range(self.retries + 1):
            reply = self._once(method, url, headers, body, timeout, deadline)
            if reply is not None and reply[0] not in RETRY_STATUS:
                return reply
            if attempt == self.retries or not self._wait(self.backoff_s * 2 ** attempt, deadline):
                break
        return reply if reply is not None else (0, b"")

    # ---- results ----------------------------------------------------------------------------------------------

    def _fail(self, code, message, status="failed", **meta) -> VideoResult:
        return VideoResult(status, None, code, message, {"provider": self.name, "model": self.model, **meta})

    def _unfinished(self, rid, code, message, status="failed", **meta) -> VideoResult:
        """Accepted (maybe billed) but not delivered: the id is the way back to the clip (``resume``)."""
        return self._fail(code, message, status, request_id=rid, unfinished=True, **meta)

    def _refused(self, code, reason, status, data, token, **meta) -> VideoResult:
        return self._fail(code, refusal_line(reason, status, parse_body(data), token), **meta)

    # ---- generate / resume -----------------------------------------------------------------------------------

    def generate(self, req: VideoRequest, on_progress: ProgressFn | None = None) -> VideoResult:
        self._cancel.clear()
        emit = on_progress or (lambda stage, payload: None)
        token, source = self._auth()
        if token is None:
            return self._fail("video_not_configured", "no xAI credentials: run `grok login` or set XAI_API_KEY")

        def image(path: Path) -> dict:
            return {"url": "data:image/png;base64," + base64.b64encode(Path(path).read_bytes()).decode()}

        payload = {"model": self.model, "prompt": req.prompt, "image": image(req.first_frame),
                   "duration": req.duration_s, "resolution": req.resolution}
        if req.last_frame is not None:
            payload["last_image"] = image(req.last_frame)
        emit("submitting", {})
        deadline = self._clock() + req.timeout_s
        status, data = self._call("POST", self.base_url + "/v1/videos/generations", token, payload)  # not cut by the deadline
        if status in (401, 403):
            return self._refused("video_auth_failed", "xAI rejected the credentials", status, data, token)
        if status != 200:
            return self._refused("video_request_failed", "xAI did not accept the request", status, data, token)
        body = parse_body(data)
        rid = body.get("request_id") if isinstance(body, dict) else None
        if not isinstance(rid, str) or not rid:
            return self._fail("video_bad_response", "no request_id in the xAI response")
        emit("submitted", {"request_id": rid})
        return self._finish(rid, req, token, source, deadline, emit)

    def resume(self, request_id: str, out_path, timeout_s: int = 600, on_progress: ProgressFn | None = None,
               **settings) -> VideoResult:
        """Ask again for a generation an earlier run left unfinished: polls and downloads only, nothing is submitted."""
        self._cancel.clear()
        emit = on_progress or (lambda stage, payload: None)
        token, source = self._auth()
        if token is None:
            return self._fail("video_not_configured", "no xAI credentials: run `grok login` or set XAI_API_KEY",
                              request_id=request_id)
        req = VideoRequest("", Path(out_path), Path(out_path), timeout_s=timeout_s, **settings)
        return self._finish(request_id, req, token, source, self._clock() + timeout_s, emit)

    def _finish(self, rid, req, token, source, deadline, emit) -> VideoResult:
        wait, rejected = self.poll_interval_s, 0
        while True:
            if self._cancel.is_set():
                return self._fail("canceled", "canceled", "canceled", request_id=rid)
            if self._clock() >= deadline:
                return self._unfinished(rid, "video_timeout", f"no result after {req.timeout_s}s", "timeout")
            reply = self._once("GET", f"{self.base_url}/v1/videos/{rid}", {"Authorization": f"Bearer {token}"}, None,
                               CALL_TIMEOUT_S, deadline)
            status, data = reply if reply is not None else (0, b"")
            info = parse_body(data) if status == 200 else None
            if status in (401, 403):
                return self._unfinished(rid, "video_auth_failed", refusal_line(
                    "xAI rejected the credentials on a poll", status, parse_body(data), token))
            if status == 200 and isinstance(info, dict):
                rejected, wait = 0, self.poll_interval_s
                state = info.get("status")
                emit("polling", {"status": state})
                if state == "done":
                    return self._deliver(rid, info, req, token, source, deadline, emit)
                if state in ("failed", "expired"):
                    err = info.get("error")
                    return self._fail("video_failed", refusal_line(
                        f"xAI could not make the clip ({state})", 200, {"error": err} if err else None, token),
                        request_id=rid)
            elif reply is not None and status not in RETRY_STATUS and status != 200:
                return self._refused("video_request_failed", "xAI refused the poll", status, data, token, request_id=rid)
            else:  # 429/5xx, no readable answer, cut short or not JSON: ask again on the same id, waiting longer each time
                rejected += 1
                wait = min(self.poll_interval_s * 2 ** rejected, POLL_BACKOFF_MAX_S)
            if not self._wait(wait, deadline):
                if self._cancel.is_set():
                    return self._fail("canceled", "canceled", "canceled", request_id=rid)
                return self._unfinished(rid, "video_timeout", f"no result after {req.timeout_s}s", "timeout")

    def _deliver(self, rid, info, req, token, source, deadline, emit) -> VideoResult:
        video = info.get("video") if isinstance(info.get("video"), dict) else {}
        if video.get("respect_moderation") is False:
            return self._fail("video_content_policy", refusal_line("", 200, None, token, policy=True), request_id=rid)
        url = video.get("url")
        if not isinstance(url, str) or not url:
            return self._unfinished(rid, "video_unfinished", "the poll says done but names no video url")
        emit("downloading", {})
        status, data = (self._download(url, deadline) if url.startswith("http")
                        else self._call("GET", self.base_url + url, token, timeout=DOWNLOAD_TIMEOUT_S, deadline=deadline))
        if status == 200 and not is_mp4(data):
            return self._unfinished(rid, "video_bad_file", "downloaded file is not an mp4")
        if status != 200:
            what = "no answer" if status == 0 else f"HTTP {status}"
            return self._unfinished(rid, "video_unfinished", f"the clip is made but could not be downloaded ({what})")
        atomic_write_bytes(req.out_path, data)
        return VideoResult("succeeded", req.out_path,
                           meta={"provider": self.name, "model": self.model, "request_id": rid, "auth": source,
                                 "duration_s": req.duration_s, "resolution": req.resolution})

    def _download(self, url: str, deadline) -> tuple[int, bytes]:
        """Signed download URL: no Authorization header. Retried on 429/5xx / unreadable answers within the deadline."""
        return self._call("GET", url, None, timeout=DOWNLOAD_TIMEOUT_S, deadline=deadline)
