"""Pick the video provider: ``SPRITE_FORGE_VIDEO_PROVIDER`` = ``xai`` (default) | ``fake`` (offline, tests)."""

from __future__ import annotations

import os

from .fake_video import FakeXaiTransport
from .xai_video import XaiVideoProvider


def make_video_provider(name: str | None = None):
    name = name or os.environ.get("SPRITE_FORGE_VIDEO_PROVIDER") or "xai"
    if name == "fake":
        provider = XaiVideoProvider(transport=FakeXaiTransport(), token="fake", poll_interval_s=0.0, sleep=lambda s: None)
        provider.name = "fake"
        return provider
    return XaiVideoProvider()
