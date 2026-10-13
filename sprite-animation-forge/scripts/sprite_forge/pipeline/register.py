"""Shared-placement alignment for ``align=register`` (default).

Why: placing every frame by its *own* feet line and mass centroid (``align=per_frame``, the legacy
behaviour) makes the body slide and bob whenever limbs swing, and flattens a jump's vertical arc.
Here the whole action is registered once:

1. ``upper_mask`` keeps the head+torso (the upper ``UPPER_FRAC`` of each frame's bbox) - the part
   that is rigid between poses.
2. ``estimate_displacements`` finds, per frame, the integer shift that maximises the overlap of that
   mask with the first frame's mask (coarse search on a 2x subsample, then +-``REFINE`` px at full
   resolution, starting from the centroid difference). The result ``d_i`` is how far frame i's body
   sits from the reference body, in raw cell pixels.
3. ``plan_anchors`` removes only the *linear drift* of ``d_i`` over the frame index (slope times the
   centred index). A deliberate bob (non-linear) survives. It then returns, per frame, the raw point
   that maps to the canvas target: one shared point plus the drift term, so every frame shares one
   placement.

Ground actions: the shared y is the median frame's feet line, so it sits on the baseline.
Airborne actions (``preserve_vertical``): no vertical correction at all - the shared y is the first
frame's feet line, so the raw vertical travel is kept.

Everything is integer / median / least-squares arithmetic: deterministic (docs/05 section 10).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .measure import ALPHA_THRESHOLD, Measure

UPPER_FRAC = 0.65
REFINE = 2          # full-resolution refinement radius (px)
SEARCH_FRAC = 0.05  # coarse search radius as a fraction of the larger cell side (min 6 px)


@dataclass
class UpperBody:
    mask: np.ndarray            # bool, cell coordinates, head+torso only
    bbox: tuple[int, int, int, int]  # x0, y0, x1, y1 of ``mask``
    cx: float
    cy: float


def upper_body(rgba: np.ndarray, m: Measure, ref_height: float | None = None) -> UpperBody:
    """Head+torso mask. ``ref_height`` (the action's median bbox height) keeps the cut at the same body height
    in every frame, even when a swinging leg or weapon changes this frame's own bbox height."""
    mask = rgba[..., 3] >= ALPHA_THRESHOLD
    x0, y0, x1, y1 = m.bbox
    height = ref_height if ref_height is not None else (y1 - y0)
    cut = y0 + max(1, int(np.ceil(round(height * UPPER_FRAC, 4))))
    mask = mask.copy()
    mask[cut:] = False
    ys, xs = np.nonzero(mask)
    return UpperBody(mask, (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1),
                     float(xs.mean()) + 0.5, float(ys.mean()) + 0.5)


def _overlap(ref: UpperBody, cur: UpperBody, dx: int, dy: int, step: int = 1) -> int:
    """Pixels of ``cur`` shifted by (dx, dy) that fall on ``ref`` (both cropped to their bboxes)."""
    rx0, ry0, rx1, ry1 = ref.bbox
    cx0, cy0, cx1, cy1 = cur.bbox
    ix0, iy0 = max(rx0, cx0 + dx), max(ry0, cy0 + dy)
    ix1, iy1 = min(rx1, cx1 + dx), min(ry1, cy1 + dy)
    if ix1 <= ix0 or iy1 <= iy0:
        return 0
    a = ref.mask[iy0:iy1:step, ix0:ix1:step]
    b = cur.mask[iy0 - dy : iy1 - dy : step, ix0 - dx : ix1 - dx : step]
    return int(np.count_nonzero(a & b))


def _best_shift(ref: UpperBody, cur: UpperBody, radius: int) -> tuple[int, int]:
    sx = int(np.floor(ref.cx - cur.cx + 0.5))
    sy = int(np.floor(ref.cy - cur.cy + 0.5))
    best, best_score = (sx, sy), -1
    r2 = max(1, radius // 2)
    for ddy in range(-r2, r2 + 1):          # coarse: every 2nd px, scored on a 2x subsample
        for ddx in range(-r2, r2 + 1):
            dx, dy = sx + 2 * ddx, sy + 2 * ddy
            score = _overlap(ref, cur, dx, dy, step=2)
            if score > best_score:
                best, best_score = (dx, dy), score
    cx, cy = best
    best_score = -1
    for dy in range(cy - REFINE, cy + REFINE + 1):  # fine: full resolution
        for dx in range(cx - REFINE, cx + REFINE + 1):
            score = _overlap(ref, cur, dx, dy)
            if score > best_score:
                best, best_score = (dx, dy), score
    return best


def estimate_displacements(bodies: list[UpperBody | None], cell_w: int, cell_h: int) -> list[tuple[float, float] | None]:
    """``d_i``: how far frame i's upper body sits from the first non-empty frame's (None for empty frames)."""
    ref = next((b for b in bodies if b is not None), None)
    radius = max(6, int(round(SEARCH_FRAC * max(cell_w, cell_h))))
    out: list[tuple[float, float] | None] = []
    for b in bodies:
        if b is None:
            out.append(None)
        elif b is ref:
            out.append((0.0, 0.0))
        else:
            tx, ty = _best_shift(ref, b, radius)  # shifting frame i by (tx, ty) lands it on the reference
            out.append((float(-tx), float(-ty)))
    return out


def _slope(idx: list[int], vals: list[float]) -> float:
    if len(idx) < 3:
        return 0.0
    return float(np.polyfit(np.array(idx, dtype=float), np.array(vals, dtype=float), 1)[0])


def plan_anchors(
    bodies: list[UpperBody | None],
    measures: list[Measure | None],
    d: list[tuple[float, float] | None],
    preserve_vertical: bool,
    shifts: list[tuple[float, float]] | None = None,
) -> list[tuple[float, float] | None]:
    """Per frame: the raw cell point that is mapped onto the canvas target (None for empty frames).

    ``shifts[i]`` = (cell origin - nominal grid origin) of frame i. Gutter snapping moves the cut cells by a few
    px, which would otherwise look like body motion, so everything is computed in nominal-slot coordinates and the
    result is converted back to the cell's own coordinates."""
    idx = [i for i, b in enumerate(bodies) if b is not None]
    if not idx:
        return [None] * len(bodies)
    sh = shifts or [(0.0, 0.0)] * len(bodies)
    r = idx[0]
    dn = {i: (d[i][0] + sh[i][0] - sh[r][0], d[i][1] + sh[i][1] - sh[r][1]) for i in idx}  # nominal-slot displacement
    mean_i = float(np.mean(idx))
    sx = _slope(idx, [dn[i][0] for i in idx])
    sy = 0.0 if preserve_vertical else _slope(idx, [dn[i][1] for i in idx])
    drift = {i: (sx * (i - mean_i), sy * (i - mean_i)) for i in idx}
    ax = float(np.median([bodies[i].cx + sh[i][0] - drift[i][0] for i in idx]))
    if preserve_vertical:
        ay_all = float(measures[idx[0]].feet_y + sh[idx[0]][1])
    else:
        ay_all = float(np.median([measures[i].feet_y + sh[i][1] - drift[i][1] for i in idx]))
    out: list[tuple[float, float] | None] = []
    for i in range(len(bodies)):
        if i not in drift:
            out.append(None)
        else:
            ay = ay_all + (0.0 if preserve_vertical else drift[i][1])
            out.append((round(ax + drift[i][0] - sh[i][0], 4), round(ay - sh[i][1], 4)))
    return out
