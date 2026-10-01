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

    def _animate(self, data_url: str) -> None:
        """Default ``ok`` mode: answer with a real clip animating the submitted first frame (when ffmpeg exists)."""
        import base64
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory(prefix="fake-video-") as tmp:
            out = Path(tmp) / "clip.mp4"
            try:
                if make_bobbing_mp4(base64.b64decode(data_url.split(",", 1)[1]), out):
                    self.video = out.read_bytes()
            except Exception:  # not a decodable image (unit tests send placeholder bytes): keep the stub clip
                pass

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
            if self.mode == "ok" and self.video is FAKE_MP4:
                self._animate(self.requests[-1]["image"]["url"])
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


def make_bobbing_mp4(first_png: bytes, out_path, frames: int = 48, period: int = 16, fps: int = 24) -> bool:
    """Encode a looping clip from the first frame (whole image bobs vertically, the upper half sways), like a model
    that animates the given character. False when ffmpeg is unavailable. Offline/test use only."""
    import io
    import math
    import shutil
    import subprocess
    import tempfile
    from pathlib import Path

    import numpy as np
    from PIL import Image

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return False
    base = np.asarray(Image.open(io.BytesIO(first_png)).convert("RGB"))
    h = base.shape[0]
    with tempfile.TemporaryDirectory(prefix="fake-clip-") as tmp:
        for i in range(frames):
            phase = 2 * math.pi * i / period
            img = np.roll(base, round(h * 0.02 * math.sin(phase)), axis=0)
            top = np.roll(img[: h // 2], round(h * 0.015 * math.sin(2 * phase)), axis=1)
            Image.fromarray(np.concatenate([top, img[h // 2:]]), "RGB").save(Path(tmp) / f"{i:04d}.png")
        proc = subprocess.run([ffmpeg, "-v", "error", "-y", "-framerate", str(fps), "-i", str(Path(tmp) / "%04d.png"),
                               "-pix_fmt", "yuv420p", "-c:v", "libx264", "-crf", "12", str(out_path)], capture_output=True)
    return proc.returncode == 0
