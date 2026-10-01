"""Frame measurement (docs/05 section 6) and the output-cell geometry.

Public API
----------
``Layout(cell_w=128, cell_h=128, margin_top=8, margin_side=8, margin_bottom=10)``
    Output cell geometry. ``baseline`` = ``cell_h - margin_bottom`` (118 by default,
    README conflict-resolution #1). ``target(anchor)`` -> ``(x, y)`` alignment target
    (docs/05 section 6 tables); ``limits(anchor)`` -> ``(up, down, side)`` room around the
    target used by the fit scale. Lives here so scale/align share it.
``measure_frame(rgba) -> Measure | None``
    ``rgba`` is one filtered cell (HxWx4). ``None`` when the cell has no foreground.
``Measure``: ``bbox`` (x0, y0, x1, y1; exclusive end), ``w``, ``h``, ``feet_y``,
``feet_y_strict``, ``mass_cx``, ``feet_cx``, ``bbox_cx``, ``bbox_cy`` (cell-local px).
``Measure.anchor_point(anchor, x_anchor) -> (x, y)``.

Notes on ambiguous spots
------------------------
* Coordinates are continuous with pixel ``i`` covering ``[i, i + 1)``: centroids add 0.5,
  ``bbox_cx = (x0 + x1) / 2``.
* ``feet_y`` / ``feet_y_strict`` are the *exclusive* lower edge (scan row + 1), the same
  convention as ``bbox`` y1 and as the synthetic ground truth ("first row below the legs").
  If no row reaches the threshold the bbox bottom is used.
* ``k1 = max(3, 0.02 * w)``, ``k2 = max(6, 0.08 * w)`` with ``w`` the bbox width.
* ``feet_cx`` band: rows ``[feet_y - 0.12 * h, feet_y)`` (at least one row).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

ALPHA_THRESHOLD = 64
ANCHORS = ("feet", "bottom", "center")
X_ANCHORS = ("mass", "feet", "bbox")


@dataclass(frozen=True)
class Layout:
    cell_w: int = 128
    cell_h: int = 128
    margin_top: int = 8
    margin_side: int = 8
    margin_bottom: int = 10

    @property
    def baseline(self) -> int:
        return self.cell_h - self.margin_bottom

    def target(self, anchor: str) -> tuple[float, float]:
        _check(anchor, ANCHORS, "anchor")
        y = self.cell_h / 2 if anchor == "center" else self.baseline
        return (self.cell_w / 2, y)

    def limits(self, anchor: str) -> tuple[float, float, float]:
        """Room above / below / left-right of the target point (docs/05 section 7.1)."""
        _check(anchor, ANCHORS, "anchor")
        side = self.cell_w / 2 - self.margin_side
        if anchor == "center":
            return (self.cell_h / 2 - self.margin_top, self.cell_h / 2 - self.margin_bottom, side)
        b = self.baseline
        return (b - self.margin_top, self.cell_h - 1 - b, side)


def _check(value: str, allowed: tuple[str, ...], name: str) -> None:
    if value not in allowed:
        raise ValueError(f"unknown {name} {value!r}; choose from {allowed}")


@dataclass
class Measure:
    bbox: tuple[int, int, int, int]
    feet_y: int
    feet_y_strict: int
    mass_cx: float
    feet_cx: float

    @property
    def w(self) -> int:
        return self.bbox[2] - self.bbox[0]

    @property
    def h(self) -> int:
        return self.bbox[3] - self.bbox[1]

    @property
    def bbox_cx(self) -> float:
        return (self.bbox[0] + self.bbox[2]) / 2

    @property
    def bbox_cy(self) -> float:
        return (self.bbox[1] + self.bbox[3]) / 2

    def anchor_point(self, anchor: str, x_anchor: str) -> tuple[float, float]:
        _check(anchor, ANCHORS, "anchor")
        _check(x_anchor, X_ANCHORS, "x_anchor")
        y = {"feet": self.feet_y, "bottom": self.bbox[3], "center": self.bbox_cy}[anchor]
        x = {"mass": self.mass_cx, "feet": self.feet_cx, "bbox": self.bbox_cx}[x_anchor]
        return (float(x), float(y))


def _feet_line(row_counts: np.ndarray, y0: int, k: float) -> int:
    """Exclusive lower edge of the lowest row with at least ``k`` foreground pixels."""
    rows = np.flatnonzero(row_counts >= k)
    return y0 + int(rows[-1]) + 1 if len(rows) else y0 + len(row_counts)


def measure_frame(rgba: np.ndarray) -> Measure | None:
    mask = rgba[..., 3] >= ALPHA_THRESHOLD
    ys, xs = np.nonzero(mask)
    if len(ys) == 0:
        return None
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()) + 1, int(ys.min()), int(ys.max()) + 1
    w, h = x1 - x0, y1 - y0
    sub = mask[y0:y1, x0:x1]
    counts = sub.sum(axis=1)
    feet_y = _feet_line(counts, y0, max(3, 0.02 * w))
    feet_y_strict = _feet_line(counts, y0, max(6, 0.08 * w))

    band_top = max(y0, min(feet_y - 1, math.ceil(round(feet_y - 0.12 * h, 4))))
    band = mask[band_top:feet_y, x0:x1]
    bx = np.nonzero(band)[1]
    feet_cx = float(bx.mean()) + x0 + 0.5 if len(bx) else (x0 + x1) / 2
    return Measure(
        bbox=(x0, y0, x1, y1),
        feet_y=feet_y,
        feet_y_strict=feet_y_strict,
        mass_cx=float(xs.mean()) + 0.5,
        feet_cx=feet_cx,
    )
