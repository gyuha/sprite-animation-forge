"""Pick the sprite frames out of a generated clip (docs/13; ``video_sprite`` does the I/O around this).

``distance_matrix(thumbs)``  mean absolute thumbnail difference between every pair of source frames.
``select_loop(dist, n)``     ``(start, period)`` of the best looping window: for each candidate period the best
                             start is the one whose frames ``start + period + k`` look most like ``start + k`` for
                             ``k < SEAM_WINDOW`` (a window, so a pose that merely passes through the same place
                             in the opposite direction does not count as a seam); among
                             the periods whose seam is within ``SEAM_SLACK`` of the best, the SHORTEST wins.
                             A half-cycle shifted period (e.g. 1.5 cycles) has a large seam, so it is never chosen.
``select_oneshot(dist, n)``  ``(start, end)``: from frame 0 to the frame where the clip returns closest to its
                             first pose (latest among near-ties), or the whole clip when it never returns.
``reduce_indices(start, span, n, loop)``  ``n`` evenly spaced source indices (round-half-up); a loop never repeats
                             its start, a one-shot includes both ends.
"""

from __future__ import annotations

import numpy as np

from .pipeline import round_half_up

SEAM_SLACK = 1.25
SEAM_WINDOW = 3
SEAM_FLOOR = 1e-3        # a seam this small is "identical" whatever the best one was
RETURN_RATIO = 0.35      # one-shot "returns" when its closest approach to frame 0 is below this share of the max


def distance_matrix(thumbs) -> np.ndarray:
    flat = np.stack([np.asarray(t, dtype=np.float64).ravel() for t in thumbs])
    return np.abs(flat[:, None, :] - flat[None, :, :]).mean(axis=2)


def select_loop(dist: np.ndarray, n: int) -> tuple[int, int]:
    total = len(dist)
    min_period = max(n, 2)
    if total <= min_period:
        return 0, max(total - 1, 1)
    best: dict[int, tuple[float, int]] = {}
    for period in range(min_period, total - SEAM_WINDOW + 1):
        seams = [(float(np.mean([dist[s + k, s + period + k] for k in range(SEAM_WINDOW)])), s)
                 for s in range(total - period - SEAM_WINDOW + 1)]
        best[period] = min(seams)
    if not best:
        return 0, total - 1
    floor = max(min(v[0] for v in best.values()) * SEAM_SLACK, SEAM_FLOOR)
    period = min(p for p, (seam, _) in best.items() if seam <= floor)
    return best[period][1], period


def select_oneshot(dist: np.ndarray, n: int) -> tuple[int, int]:
    total = len(dist)
    if total <= max(n, 2):
        return 0, total - 1
    from_first = dist[0]
    peak_at = int(from_first.argmax())
    peak = from_first[peak_at]
    candidates = range(max(n, 2, peak_at + 1), total)  # a return can only happen after the farthest pose
    if peak <= 0 or not candidates:
        return 0, total - 1
    closest = min(from_first[e] for e in candidates)
    if closest > RETURN_RATIO * peak:
        return 0, total - 1
    near = [e for e in candidates if from_first[e] <= closest * SEAM_SLACK + SEAM_FLOOR]
    return 0, max(near)


def reduce_indices(start: int, span: int, n: int, loop: bool) -> list[int]:
    """``span`` is the period (loop) or ``end - start`` (one-shot)."""
    if n == 1:
        return [start]
    step = span / n if loop else span / (n - 1)
    return [start + round_half_up(k * step) for k in range(n)]
