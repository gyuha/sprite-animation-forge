"""Provider interface (docs/01 section 4) plus one shared helper, ``install_raw``."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

from PIL import Image

from ..fsutil import atomic_write_bytes, atomic_write_png, sha256_file


@dataclass(frozen=True)
class GenerationRequest:
    prompt: str                      # Prompt Generator output (verbatim)
    reference_images: list[Path]     # references to attach (0-2)
    out_dir: Path                    # attempts/NNN/
    timeout_s: int = 300


@dataclass
class GenerationResult:
    status: str                      # "succeeded" | "failed" | "canceled" | "timeout"
    raw_path: Path | None            # out_dir/raw.png
    error_code: str | None = None    # docs/03 section 8
    error_message: str | None = None
    meta: dict = field(default_factory=dict)  # provider specific -> generation.json


ProgressFn = Callable[[str, dict], None]   # (stage, payload)


class ImageProvider(Protocol):
    name: str
    def check(self) -> dict: ...
    def generate(self, req: GenerationRequest, on_progress: ProgressFn | None = None) -> GenerationResult: ...
    def cancel(self) -> None: ...


def install_raw(src: Path, dest: Path) -> dict:
    """Decode ``src`` fully with Pillow and write it as PNG at ``dest``.

    PNG sources are copied byte-for-byte; other decodable formats are re-encoded.
    Raises any Pillow/OS error when the file is not a decodable image.
    Returns the ``raw`` block of generation.json.
    """
    with Image.open(src) as im:
        fmt = im.format
        im.load()
        size, mode = im.size, im.mode
        if fmt == "PNG":
            atomic_write_bytes(dest, Path(src).read_bytes())
        else:
            atomic_write_png(im, dest)
    return {"file": dest.name, "width": size[0], "height": size[1], "mode": mode,
            "sha256": sha256_file(dest)}
