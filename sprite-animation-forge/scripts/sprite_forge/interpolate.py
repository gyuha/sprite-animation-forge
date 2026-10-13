"""Optional frame interpolation (docs/14 area D): a frame between two neighbours of the SAME walk, where only the motion
changes. The engine never needs it for a smooth walk; it is looked for only when a frame is to be made.

``find_rife() -> {installed, bin, source}``   ``SPRITE_FORGE_RIFE_BIN`` (a runnable file) first, then ``rife-ncnn-vulkan`` on
                                              ``PATH``. Nothing is downloaded or installed (docs/13).
``find_interpolator() -> RifeNcnn | None``    ``None`` when no binary is found.
``RifeNcnn(binary, model=None).between(a, b, t=0.5)``  RGBA uint8 arrays of one shape -> the frame at ``t`` between them.
    RIFE reads three colour channels and no alpha, so a frame is interpolated as TWO images: its colour (the body's own
    colour pushed out over the transparent area, so a disagreement between the two runs reads as the body's fill, never as
    black) and its coverage as a grey image; they are put back together and coverage under ``MIN_COVERAGE``/255 is dropped
    (no faint halo is invented). A binary that runs and fails is a ``ForgeError("rife_failed")`` in every mode.

Interface (any object with ``name`` and ``between``) is what ``video_repair`` calls, so tests and other backends plug in.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Protocol

import numpy as np
from PIL import Image
from scipy import ndimage

from .errors import EXIT_PROVIDER, ForgeError

ENV_BIN = "SPRITE_FORGE_RIFE_BIN"
ENV_MODEL = "SPRITE_FORGE_RIFE_MODEL"
BIN_NAME = "rife-ncnn-vulkan"
MIN_COVERAGE = 2  # of 255
RUN_TIMEOUT_S = 120


class Interpolator(Protocol):
    name: str

    def between(self, a: np.ndarray, b: np.ndarray, t: float = 0.5) -> np.ndarray: ...


def find_rife() -> dict:
    env = os.environ.get(ENV_BIN)
    if env and os.path.isfile(env) and os.access(env, os.X_OK):
        return {"installed": True, "bin": env, "source": "env"}
    found = shutil.which(BIN_NAME)
    return {"installed": True, "bin": found, "source": "path"} if found else {"installed": False, "bin": None, "source": None}


def find_interpolator() -> "RifeNcnn | None":
    found = find_rife()
    return RifeNcnn(found["bin"], os.environ.get(ENV_MODEL)) if found["installed"] else None


def _bleed(rgba: np.ndarray) -> np.ndarray:
    """RGB image whose transparent area carries the colour of the nearest body pixel (black where there is no body at all)."""
    opaque = rgba[..., 3] > 0
    rgb = rgba[..., :3].copy()
    if opaque.any() and not opaque.all():
        _, (iy, ix) = ndimage.distance_transform_edt(~opaque, return_indices=True)
        rgb = rgb[iy, ix]
    elif not opaque.any():
        rgb[:] = 0
    return rgb


class RifeNcnn:
    name = "rife-ncnn-vulkan"

    def __init__(self, binary: str, model: str | None = None):
        self.binary, self.model = binary, model

    def _argv(self, a: Path, b: Path, out: Path, t: float) -> list[str]:
        argv = [self.binary, "-0", str(a), "-1", str(b), "-o", str(out), "-s", f"{t:g}"]
        return argv + (["-m", self.model] if self.model else [])

    def _run(self, a_img: np.ndarray, b_img: np.ndarray, t: float, tmp: Path, tag: str) -> np.ndarray:
        a, b, out = tmp / f"{tag}-a.png", tmp / f"{tag}-b.png", tmp / f"{tag}-out.png"
        Image.fromarray(a_img, "RGB").save(a)
        Image.fromarray(b_img, "RGB").save(b)
        try:
            proc = subprocess.run(self._argv(a, b, out, t), capture_output=True, text=True, timeout=RUN_TIMEOUT_S, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ForgeError("rife_failed", f"{self.binary}: {exc}", EXIT_PROVIDER) from None
        if proc.returncode != 0 or not out.is_file():
            tail = (proc.stderr or proc.stdout or "no output").strip().splitlines()[-1:]
            raise ForgeError("rife_failed", f"{self.binary} exited {proc.returncode}: {''.join(tail)}", EXIT_PROVIDER)
        return np.asarray(Image.open(out).convert("RGB"))

    def between(self, a: np.ndarray, b: np.ndarray, t: float = 0.5) -> np.ndarray:
        with tempfile.TemporaryDirectory(prefix="sprite-forge-rife-") as tmp_name:
            tmp = Path(tmp_name)
            colour = self._run(_bleed(a), _bleed(b), t, tmp, "colour")
            grey = lambda x: np.repeat(x[..., 3:4], 3, axis=2)  # noqa: E731  coverage as a grey image
            coverage = self._run(grey(a), grey(b), t, tmp, "coverage")
        alpha = np.rint(coverage.astype(np.float64).mean(axis=2)).astype(np.uint8)
        alpha[alpha < MIN_COVERAGE] = 0
        out = np.zeros(a.shape, dtype=np.uint8)
        out[..., :3] = np.where((alpha > 0)[..., None], colour, 0)
        out[..., 3] = alpha
        return out
