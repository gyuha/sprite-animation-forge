"""xAI Grok Imagine video provider (docs/13-video-api-setup.md). Re-implemented from the public API shape;
the endpoint, model and response field names are settings because they are NOT verified against a live account.

Flow: ``POST {base}/v1/videos/generations`` -> request id -> poll ``GET {base}/v1/videos/{id}`` until ``done`` ->
download the mp4 (checked for ``ftyp``, written atomically). 429 / 5xx are retried with backoff.

Auth priority: ``~/.grok/auth.json`` (``grok login``; path overridable with ``SPRITE_FORGE_GROK_AUTH``), then
``XAI_API_KEY``. ``transport`` is injectable (tests never touch the network):
``transport(method, url, headers, body, timeout) -> (status, bytes)``.
"""

from __future__ import annotations

import base64
import json
import os
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from ..fsutil import atomic_write_bytes
from .base import ProgressFn
from .video_base import VideoRequest, VideoResult, is_mp4

DEFAULT_BASE_URL = "https://api.x.ai"
DEFAULT_MODEL = "grok-imagine-video-1.5"  # unverified: confirm in the xAI console / docs
RETRY_STATUS = {429, 500, 502, 503, 504}
AUTH_KEYS = ("api_key", "apiKey", "key", "access_token", "token")


def urllib_transport(method: str, url: str, headers: dict, body: bytes | None, timeout: float) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


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
                 token: str | None = None):
        self.transport = transport or urllib_transport
        self.base_url = (base_url or os.environ.get("SPRITE_FORGE_XAI_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.model = model or os.environ.get("SPRITE_FORGE_XAI_VIDEO_MODEL") or DEFAULT_MODEL
        self.poll_interval_s, self.retries, self.backoff_s, self._sleep = poll_interval_s, retries, backoff_s, sleep
        self._token = token  # injected credentials (fake provider); bypasses auth.json / env
        self._cancel = threading.Event()

    def _auth(self) -> tuple[str | None, str | None]:
        return (self._token, "injected") if self._token else load_auth()

    def check(self) -> dict:
        token, source = self._auth()
        return {"provider": self.name, "configured": token is not None, "auth": source, "model": self.model}

    def cancel(self) -> None:
        self._cancel.set()

    def _call(self, method, path, token, payload=None, timeout=60.0) -> tuple[int, bytes]:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        body = json.dumps(payload).encode() if payload is not None else None
        for attempt in range(self.retries + 1):
            status, data = self.transport(method, self.base_url + path, headers, body, timeout)
            if status not in RETRY_STATUS or attempt == self.retries:
                return status, data
            self._sleep(self.backoff_s * 2 ** attempt)
        raise AssertionError("unreachable")

    def _fail(self, code, message, status="failed", **meta) -> VideoResult:
        return VideoResult(status, None, code, message, {"provider": self.name, "model": self.model, **meta})

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
        status, data = self._call("POST", "/v1/videos/generations", token, payload)
        if status in (401, 403):
            return self._fail("video_auth_failed", f"xAI rejected the credentials (HTTP {status})")
        if status != 200:
            return self._fail("video_request_failed", f"HTTP {status}: {data[:200].decode(errors='replace')}")
        try:
            rid = json.loads(data)["request_id"]
        except (ValueError, KeyError, TypeError):
            return self._fail("video_bad_response", "no request_id in the xAI response")

        deadline = time.monotonic() + req.timeout_s
        while True:
            if self._cancel.is_set():
                return self._fail("canceled", "canceled", "canceled", request_id=rid)
            if time.monotonic() > deadline:
                return self._fail("video_timeout", f"no result after {req.timeout_s}s", "timeout", request_id=rid)
            status, data = self._call("GET", f"/v1/videos/{rid}", token)
            if status != 200:
                return self._fail("video_request_failed", f"poll HTTP {status}", request_id=rid)
            try:
                info = json.loads(data)
            except ValueError:
                return self._fail("video_bad_response", "poll response is not JSON", request_id=rid)
            state = info.get("status")
            emit("polling", {"status": state})
            if state == "done":
                break
            if state in ("failed", "expired"):
                return self._fail("video_failed", str(info.get("error") or state), request_id=rid)
            self._sleep(self.poll_interval_s)

        url = (info.get("video") or {}).get("url")
        if not url:
            return self._fail("video_bad_response", "done without a video url", request_id=rid)
        emit("downloading", {})
        status, video = self._download(url) if url.startswith("http") else self._call("GET", url, token, timeout=300.0)
        if status != 200 or not is_mp4(video):
            return self._fail("video_bad_file", "downloaded file is not an mp4", request_id=rid)
        atomic_write_bytes(req.out_path, video)
        return VideoResult("succeeded", req.out_path,
                           meta={"provider": self.name, "model": self.model, "request_id": rid, "auth": source,
                                 "duration_s": req.duration_s, "resolution": req.resolution})

    def _download(self, url: str) -> tuple[int, bytes]:
        for attempt in range(self.retries + 1):  # signed download URL: no Authorization header
            status, data = self.transport("GET", url, {}, None, 300.0)
            if status not in RETRY_STATUS or attempt == self.retries:
                return status, data
            self._sleep(self.backoff_s * 2 ** attempt)
        raise AssertionError("unreachable")
