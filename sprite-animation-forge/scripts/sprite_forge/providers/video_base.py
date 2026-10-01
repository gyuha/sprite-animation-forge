"""Video provider interface (docs/13): first frame in, mp4 out. Mirrors ``base.ImageProvider`` in spirit."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from .base import ProgressFn


@dataclass(frozen=True)
class VideoRequest:
    prompt: str
    first_frame: Path                # the canvas image the video starts from (and loops back to)
    out_path: Path                   # where the mp4 is written
    last_frame: Path | None = None   # optional end-frame pin (looping idle)
    duration_s: int = 5
    resolution: str = "720p"
    timeout_s: int = 600


@dataclass
class VideoResult:
    status: str                      # "succeeded" | "failed" | "canceled" | "timeout"
    video_path: Path | None
    error_code: str | None = None
    error_message: str | None = None
    meta: dict = field(default_factory=dict)


class VideoProvider(Protocol):
    name: str
    def check(self) -> dict: ...     # {provider, configured, auth, ...}; never raises
    def generate(self, req: VideoRequest, on_progress: ProgressFn | None = None) -> VideoResult: ...
    def cancel(self) -> None: ...


def is_mp4(data: bytes) -> bool:
    """ISO base media files start with a box whose type (bytes 4..8) is ``ftyp``."""
    return len(data) >= 12 and data[4:8] == b"ftyp"
