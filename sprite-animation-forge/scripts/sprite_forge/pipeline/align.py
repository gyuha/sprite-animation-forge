"""Baseline alignment and compositing (docs/05 section 8).

Public API
----------
``place_frame(cell_rgba, measure, scale, layout, anchor, x_anchor, pixel_art) -> Placement``
    Crop the bbox (+2 px margin), resample by ``scale``, recompute the anchor point on the
    resampled crop, and paste it on a transparent ``cell_w x cell_h`` canvas at the integer
    offset ``floor(target - anchor' + 0.5)``. Pixels outside the canvas are clipped (the
    caller reports them via ``scale.overflow_px``).
``blank_frame(layout) -> np.ndarray``  transparent canvas (for empty cells).
``compose_sheet(frames) -> np.ndarray``  frames joined in a single row.

``Placement``: ``frame`` (canvas), ``offset`` (dx, dy of the resampled crop's top-left on
the canvas), ``anchor_out`` (anchor point on the canvas, continuous; equals the target
within 0.5 px).

Notes
-----
* The resampled crop has integer size ``round(size * scale)``, so the anchor is mapped with
  the *actual* per-axis factors (new size / crop size), not with ``scale`` itself.
* Subpixel shifts are never applied (docs/05 section 8 step 4).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import round_half_up
from .measure import Layout, Measure
from .scale import resample

CROP_PAD = 2


@dataclass
class Placement:
    frame: np.ndarray
    offset: tuple[int, int]
    anchor_out: tuple[float, float]


def blank_frame(layout: Layout) -> np.ndarray:
    return np.zeros((layout.cell_h, layout.cell_w, 4), dtype=np.uint8)


def place_frame(
    cell_rgba: np.ndarray,
    measure: Measure,
    scale: float,
    layout: Layout,
    anchor: str,
    x_anchor: str,
    pixel_art: bool = False,
) -> Placement:
    h, w = cell_rgba.shape[:2]
    x0, y0, x1, y1 = measure.bbox
    cx0, cy0 = max(0, x0 - CROP_PAD), max(0, y0 - CROP_PAD)
    cx1, cy1 = min(w, x1 + CROP_PAD), min(h, y1 + CROP_PAD)
    crop = np.ascontiguousarray(cell_rgba[cy0:cy1, cx0:cx1])
    small = resample(crop, scale, pixel_art)

    fx = small.shape[1] / crop.shape[1]
    fy = small.shape[0] / crop.shape[0]
    ax, ay = measure.anchor_point(anchor, x_anchor)
    ax_s, ay_s = (ax - cx0) * fx, (ay - cy0) * fy
    tx, ty = layout.target(anchor)
    dx, dy = round_half_up(tx - ax_s), round_half_up(ty - ay_s)

    canvas = blank_frame(layout)
    sx0, sy0 = max(0, -dx), max(0, -dy)
    sx1 = min(small.shape[1], layout.cell_w - dx)
    sy1 = min(small.shape[0], layout.cell_h - dy)
    if sx1 > sx0 and sy1 > sy0:
        canvas[dy + sy0 : dy + sy1, dx + sx0 : dx + sx1] = small[sy0:sy1, sx0:sx1]
    return Placement(canvas, (dx, dy), (round(ax_s + dx, 4), round(ay_s + dy, 4)))


def compose_sheet(frames: list[np.ndarray]) -> np.ndarray:
    return np.concatenate(frames, axis=1)
