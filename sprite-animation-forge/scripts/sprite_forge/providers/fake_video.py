"""Fake xAI transport for tests and offline runs (``SPRITE_FORGE_VIDEO_PROVIDER=fake``): answers the same
three calls as the real API from memory. ``mode``: ok | fail | pending (never done) | rate_limit (first N calls 429)
| bad_file | unauthorized. ``video`` is the mp4 returned on download."""

from __future__ import annotations

import json

FAKE_MP4 = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 64


class FakeXaiTransport:
    def __init__(self, mode: str = "ok", video: bytes = FAKE_MP4, polls_until_done: int = 1, rate_limits: int = 2):
        self.mode, self.video, self.polls_until_done, self.rate_limits = mode, video, polls_until_done, rate_limits
        self.calls: list[tuple[str, str]] = []
        self.requests: list[dict] = []
        self.auth_headers: list[str | None] = []
        self._polls = 0

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append((method, url))
        self.auth_headers.append(headers.get("Authorization"))
        if self.mode == "unauthorized":
            return 401, b"{}"
        if self.mode == "rate_limit" and self.rate_limits > 0:
            self.rate_limits -= 1
            return 429, b"{}"
        if method == "POST":
            self.requests.append(json.loads(body))
            return 200, json.dumps({"request_id": "req-1"}).encode()
        if url.endswith("/v1/videos/req-1"):
            self._polls += 1
            if self.mode == "pending" or self._polls < self.polls_until_done:
                return 200, json.dumps({"status": "pending"}).encode()
            if self.mode == "fail":
                return 200, json.dumps({"status": "failed", "error": "content policy"}).encode()
            return 200, json.dumps({"status": "done", "video": {"url": "https://cdn.fake/v.mp4"}}).encode()
        if url == "https://cdn.fake/v.mp4":
            return 200, (b"not an mp4" if self.mode == "bad_file" else self.video)
        return 404, b"{}"
