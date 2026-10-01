"""Shared scale (docs/05 section 7): fit / preserve, resampling, overflow detection.

Public API
----------
``ScaleProfile(norm_scale, raw_cell_height=None, ...)``
    The fields of character-scale-profile.json (docs/06 section 5) that the pipeline
    reads; only ``norm_scale`` is required. ``ScaleProfile.from_dict(d)`` ignores
    unknown keys. Profile *generation* is a later task.
``fit_scale(measures, layout, anchor, x_anchor) -> float``
    Largest shared scale that keeps every frame inside the margins when placed by its
    anchor point (docs/05 section 7.1). Empty-cell ``None`` entries are skipped.
``preserve_scale(profile, raw_cell_height) -> float``   ``norm_scale / RH``
``choose_scale(strategy, measures, layout, anchor, x_anchor, profile, raw_cell_height)
-> ScaleChoice``  (``scale``, ``strategy`` actually used, ``warnings``). ``preserve``
    without a profile falls back to ``fit`` with warning ``no_scale_profile``.
``overflow_px(measure, scale, layout, anchor, x_anchor) -> dict``
    Pixels (left/top/right/bottom, >= 0) that the scaled bbox would leave outside the
    ``cell_w x cell_h`` canvas when aligned to the target. Nothing is ever cropped; the
    caller reports it (QC-01).
``resample(rgba, scale, pixel_art) -> np.ndarray``  resize to ``round_half_up(size*scale)``
    (at least 1 px per side). ``pixel_art``: BOX + alpha binarisation (alpha >= 128);
    otherwise premultiplied alpha (``RGBa``) + LANCZOS.

Notes
-----
* ``fit`` with no usable constraint (e.g. every frame empty) returns 1.0.
* Overflow uses the continuous (un-rounded) placement; integer offsets can differ by 0.5 px.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, fields

import numpy as np
from PIL import Image

from . import round_half_up
from .measure import Layout, Measure


@dataclass
class ScaleProfile:
    norm_scale: float
    raw_cell_height: int | None = None
    body_height: float | None = None
    body_width: float | None = None
    baseline_y: int | None = None
    center_x: float | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "ScaleProfile":
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in names})


@dataclass
class ScaleChoice:
    scale: float
    strategy: str
    warnings: list[str] = field(default_factory=list)


def fit_scale(measures, layout: Layout, anchor: str, x_anchor: str) -> float:
    up_room, down_room, side_room = layout.limits(anchor)
    up = down = side = 0.0
    for m in measures:
        if m is None:
            continue
        ax, ay = m.anchor_point(anchor, x_anchor)
        up = max(up, ay - m.bbox[1])
        down = max(down, m.bbox[3] - ay)
        side = max(side, ax - m.bbox[0], m.bbox[2] - ax)
    candidates = [room / extent for room, extent in ((up_room, up), (down_room, down), (side_room, side)) if extent > 0]
    return round(min(candidates), 4) if candidates else 1.0


def preserve_scale(profile: ScaleProfile, raw_cell_height: int) -> float:
    return round(profile.norm_scale / raw_cell_height, 4)


def choose_scale(
    strategy: str,
    measures,
    layout: Layout,
    anchor: str,
    x_anchor: str,
    profile: ScaleProfile | dict | None = None,
    raw_cell_height: int | None = None,
) -> ScaleChoice:
    if strategy not in ("fit", "preserve"):
        raise ValueError(f"unknown scale_strategy {strategy!r}")
    if strategy == "preserve":
        if isinstance(profile, dict):
            profile = ScaleProfile.from_dict(profile)
        if profile is not None and raw_cell_height:
            return ScaleChoice(preserve_scale(profile, raw_cell_height), "preserve")
        return ScaleChoice(fit_scale(measures, layout, anchor, x_anchor), "fit", ["no_scale_profile"])
    return ScaleChoice(fit_scale(measures, layout, anchor, x_anchor), "fit")


def overflow_px(m: Measure, scale: float, layout: Layout, anchor: str, x_anchor: str) -> dict:
    ax, ay = m.anchor_point(anchor, x_anchor)
    tx, ty = layout.target(anchor)
    left = tx + (m.bbox[0] - ax) * scale
    right = tx + (m.bbox[2] - ax) * scale
    top = ty + (m.bbox[1] - ay) * scale
    bottom = ty + (m.bbox[3] - ay) * scale
    pad = lambda v: max(0, math.ceil(round(v, 4)))  # noqa: E731
    return {
        "left": pad(-left),
        "top": pad(-top),
        "right": pad(right - layout.cell_w),
        "bottom": pad(bottom - layout.cell_h),
    }


def resample(rgba: np.ndarray, scale: float, pixel_art: bool) -> np.ndarray:
    h, w = rgba.shape[:2]
    size = (max(1, round_half_up(w * scale)), max(1, round_half_up(h * scale)))
    img = Image.fromarray(rgba, "RGBA").convert("RGBa")
    img = img.resize(size, Image.BOX if pixel_art else Image.LANCZOS)
    out = np.array(img.convert("RGBA"))
    if pixel_art:
        out[..., 3] = np.where(out[..., 3] >= 128, 255, 0)
        out[out[..., 3] == 0] = 0
    return out
