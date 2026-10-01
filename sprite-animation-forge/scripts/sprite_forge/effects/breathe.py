"""Deterministic breathing idle: one still pose -> N loop frames (generation method ``breathe``).

Why: four independently redrawn idle frames "boil" (tiny differences in every cell). One still plus a
deterministic warp has no such noise and costs a single Codex call.

How: ``find_neck`` splits the figure into head (rigid) and body at the narrowest horizontal band below the
head. For frame i the body below the neck is stretched or squashed vertically by ``dh_i`` rows
(``dh_i = round(dh * sin(2*pi*i/n))``, so frame 0 is the still and the sequence is one full breath), with the
feet fixed on their baseline; the head is only translated (never resampled), so it stays bit-identical.
Rows are mapped with integer arithmetic (endpoints preserved), which keeps pixel art crisp.

If no neck bottleneck is found (hood, cape, no head/torso split) the split falls back to a fixed fraction of the
figure height and ``neck_not_found`` is returned in ``info["warnings"]``; the result is still usable but the
seam may cut through the head.

Public API
----------
``find_neck(rgba) -> (neck_row, found)``  row index (canvas coordinates) where the body starts.
``breathe_frames(rgba, n, amplitude=0.04) -> (frames, info)``  ``info``: ``neck_row``, ``found``, ``dh``,
    ``amplitude``, ``warnings``. Blinking is not implemented (eye detection on arbitrary art is unreliable).
"""

from __future__ import annotations

import math

import numpy as np

ALPHA_THRESHOLD = 64
NECK_BAND = (0.12, 0.50)     # search the narrowest row between these fractions of the figure height
FALLBACK_FRAC = 0.30
NARROW_RATIO = 0.80          # a neck must be at most this wide relative to the head above it
RUN_SLACK = 1.15             # rows within this factor of the minimum width belong to the neck run
BODY_RATIO = 1.20            # ... and the body below must be at least this much wider than the neck


def _widths(rgba: np.ndarray) -> tuple[np.ndarray, int, int]:
    mask = rgba[..., 3] >= ALPHA_THRESHOLD
    rows = np.nonzero(mask.any(axis=1))[0]
    if len(rows) == 0:
        raise ValueError("empty frame")
    return mask.sum(axis=1), int(rows.min()), int(rows.max()) + 1


def find_neck(rgba: np.ndarray) -> tuple[int, bool]:
    widths, y0, y1 = _widths(rgba)
    h = y1 - y0
    fallback = y0 + int(round(FALLBACK_FRAC * h))
    lo, hi = y0 + int(math.ceil(NECK_BAND[0] * h)), y0 + int(NECK_BAND[1] * h)
    if hi - lo < 3:
        return fallback, False
    band = widths[lo:hi]
    min_w = int(band.min())
    if min_w == 0:
        return fallback, False
    run = np.nonzero(band <= min_w * RUN_SLACK)[0]
    # keep the first contiguous run of narrow rows
    end = 1
    while end < len(run) and run[end] == run[end - 1] + 1:
        end += 1
    start_row, end_row = lo + int(run[0]), lo + int(run[end - 1]) + 1
    head_w = int(widths[y0:start_row].max()) if start_row > y0 else 0
    body_w = int(widths[end_row:y1].max()) if end_row < y1 else 0
    if head_w == 0 or min_w > NARROW_RATIO * head_w or body_w < BODY_RATIO * min_w:
        return fallback, False
    return (start_row + end_row) // 2, True


def _row_map(src_h: int, dst_h: int) -> np.ndarray:
    """Source row for each destination row; first and last rows are preserved (integer, deterministic)."""
    if dst_h == 1:
        return np.array([0])
    r = np.arange(dst_h)
    return np.floor(r * (src_h - 1) / (dst_h - 1) + 0.5).astype(int)


def breathe_frames(rgba: np.ndarray, n: int, amplitude: float = 0.04) -> tuple[list[np.ndarray], dict]:
    if n < 2:
        raise ValueError("n must be >= 2")
    _, y0, y1 = _widths(rgba)
    neck, found = find_neck(rgba)
    body_h = y1 - neck
    dh = max(1, int(math.floor(amplitude * body_h + 0.5)))
    warnings = [] if found else ["neck_not_found"]
    frames = []
    for i in range(n):
        step = int(math.floor(dh * math.sin(2 * math.pi * i / n) + 0.5))
        step = min(step, y0)  # the head moves up by `step` rows; never out of the canvas
        if step == 0:
            frames.append(rgba.copy())
            continue
        out = np.zeros_like(rgba)
        new_h = body_h + step
        body = rgba[neck:y1][_row_map(body_h, new_h)]
        out[y1 - new_h : y1] = body
        head = rgba[:neck]
        if step > 0:
            out[: neck - step] = head[step:]
        else:
            out[-step : neck - step] = head
        frames.append(out)
    return frames, {"neck_row": neck, "found": found, "dh": dh, "amplitude": amplitude, "warnings": warnings}
