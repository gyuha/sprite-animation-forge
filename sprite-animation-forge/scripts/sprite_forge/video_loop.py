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
``find_loop(dist, n, thumbs, min_len=, max_len=, cycles=) -> LoopChoice``  ``select_loop`` plus what a real clip needs:
                             (1) a SECOND, wider search when the first cut does not close (a slow walk: its cycle is
                             almost the whole clip, so no seam fits the normal window): thumbnails scaled back to 8x8,
                             periods up to the clip length, a one-frame window; it is used only when clearly better.
                             (2) ``cycles_suspected``: the chosen cut also closes at 1/2 or 1/3 of its length, so it may
                             hold two or three cycles - reported, never cut on the pixels' word; a caller who knows
                             (``cycles=N``) gets one cycle. (3) ``min_len``/``max_len`` bound the period on every path.
``detect_held(thumbs)``      ``(ratio, unique)``: a clip that shows each drawing for several frames (on twos / threes) has
                             many near-identical adjacent pairs; ``unique`` are the first frames of its drawings.
``seam_pop(thumbs, start, span)``  how much larger the closing one-frame step is than the largest step inside the cut (~1 = it
                             closes like any other step), read on the UPPER
                             half of the frame (where head and arms move); ``None`` when the top cannot be read.
``reduce_indices(start, span, n, loop)``  ``n`` evenly spaced source indices (round-half-up); a loop never repeats
                             its start, a one-shot includes both ends.
"""

from __future__ import annotations

from dataclasses import dataclass

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


# ---- real-clip behaviours (docs/14 area C) ------------------------------------------------------------------

GOOD_SEAM_RATIO = 0.6    # a cut closes when its seam is under this share of a typical step (one frame of phase drift is ~1.0)
MIN_COVERAGE = 0.5       # a cut must span this share of the clip's whole motion range (else it is a tiny wiggle, not a cycle)
WIDER_WINDOW = 2         # the second search compares two consecutive frames: still sees the direction, reaches one frame further
CLEAR_GAIN = 0.7         # the wider search must beat the first by this factor to replace it
COARSE_BLOCK = 4         # 32x32 thumbnails -> 8x8 for the wider search
SUSPECT_RATIO = 0.5      # a cut closing at span/2 this well (relative to a typical step) may hold two cycles
HELD_REL = 0.15          # an adjacent pair this much closer than the clip's typical step is "the same drawing"
HELD_MIN_RATIO = 0.3     # share of such pairs that makes a clip "held"
TOP_ROWS = 16            # the upper half of a 32x32 thumbnail
TOP_MIN_ALPHA = 0.5      # summed alpha in the upper half below this = nothing to read there
EPS = 1e-6


@dataclass(frozen=True)
class LoopChoice:
    start: int
    span: int
    seam_ratio: float | None            # closing seam / typical adjacent step; None for a clip that does not move
    research: str | None = None         # "wider" when the second search replaced the first
    cycles_suspected: int | None = None


def _typical_step(dist: np.ndarray) -> float:
    return float(np.mean([dist[i, i + 1] for i in range(len(dist) - 1)])) if len(dist) > 1 else 0.0


def _best_cut(dist: np.ndarray, lo: int, hi: int, window: int) -> tuple[int, int, float] | None:
    """The shortest period in ``lo..hi`` whose best seam is within ``SEAM_SLACK`` of the best of all: ``(start, period, seam)``.
    A cut that spans less than ``MIN_COVERAGE`` of the clip's motion range is not a cycle (a pose that merely turns round at
    the extreme of a slow swing closes after a few frames) and is skipped."""
    biggest = float(dist.max())
    best: dict[int, tuple[float, int]] = {}
    for period in range(lo, hi + 1):
        starts = range(len(dist) - period - window + 1)
        seams = [(float(np.mean([dist[s + k, s + period + k] for k in range(window)])), s) for s in starts]
        if not seams:
            continue
        seam, start = min(seams)
        if biggest > EPS and dist[start:start + period + 1, start:start + period + 1].max() < MIN_COVERAGE * biggest:
            continue
        best[period] = (seam, start)
    if not best:
        return None
    floor = max(min(v[0] for v in best.values()) * SEAM_SLACK, SEAM_FLOOR)
    period = min(p for p, (seam, _) in best.items() if seam <= floor)
    return best[period][1], period, best[period][0]


def _ratio(seam: float, step: float) -> float | None:
    return None if step < EPS else seam / step


def _wider_cut(thumbs, n, lo, total, max_len):
    """Second search: thumbnails scaled back (8x8: tolerant of small drift), periods up to the clip length."""
    coarse = [np.asarray(t, dtype=np.float64).reshape(8, COARSE_BLOCK, 8, COARSE_BLOCK, -1).mean(axis=(1, 3)) for t in thumbs]
    cdist = distance_matrix(coarse)
    hi = total - WIDER_WINDOW if not max_len else min(total - WIDER_WINDOW, max_len)
    cut = _best_cut(cdist, lo, hi, WIDER_WINDOW) if lo <= hi else None
    return None if cut is None else (cut[0], cut[1], _ratio(cut[2], _typical_step(cdist)))


def find_loop(dist: np.ndarray, n: int, thumbs=None, *, min_len: int | None = None, max_len: int | None = None,
              cycles: int | None = None) -> LoopChoice:
    total = len(dist)
    lo = max(n, 2, min_len or 0)
    hi = min(total - SEAM_WINDOW, max_len) if max_len else total - SEAM_WINDOW
    step = _typical_step(dist)
    first = _best_cut(dist, lo, hi, SEAM_WINDOW) if lo <= hi else None
    ratio = _ratio(first[2], step) if first else None
    research = None
    if first is not None:
        start, period = first[0], first[1]
    if thumbs is not None and (first is None or (ratio is not None and ratio > GOOD_SEAM_RATIO)):
        second = _wider_cut(thumbs, n, lo, total, max_len)  # the cut does not close: look again, wider
        if second is not None and (first is None or (second[2] is not None and second[2] < ratio * CLEAR_GAIN)):
            start, period, ratio, research = second[0], second[1], second[2], "wider"
            first = second
    if first is None:  # nothing fits the window: the whole clip (or as much as the window allows)
        return LoopChoice(0, min(max(total - 1, 1), max_len) if max_len else max(total - 1, 1), None)
    suspected = None
    for d in (2, 3):  # a cut that closes after 1/d of its length too may hold d cycles
        q = round(period / d)
        if q < max(n, 2) or step < EPS:
            continue
        part = _best_cut(dist, q, q, SEAM_WINDOW)
        if part is not None and part[2] / step <= SUSPECT_RATIO:
            suspected = d
            break
    if cycles and cycles > 1:
        period = max(round(period / cycles), 2)
        suspected = suspected or cycles
    return LoopChoice(start, period, ratio, research, suspected)


def detect_held(thumbs) -> tuple[float, list[int]]:
    count = len(thumbs)
    if count < 4:
        return 0.0, list(range(count))
    steps = np.array([np.abs(np.asarray(thumbs[i + 1]) - np.asarray(thumbs[i])).mean() for i in range(count - 1)])
    if steps.mean() < EPS:
        return 0.0, list(range(count))
    held = steps < HELD_REL * np.percentile(steps, 75)
    ratio = float(held.mean())
    if ratio < HELD_MIN_RATIO:
        return ratio, list(range(count))
    return ratio, [0] + [i + 1 for i, h in enumerate(held) if not h]


def seam_pop(thumbs, start: int, span: int) -> float | None:
    """Closing one-frame step / the largest step inside the cut, on the upper half of the frame: ~1 for a loop that closes
    like any other step, much more for a pop. ``None`` when the top of either seam frame has nothing to read."""
    count = len(thumbs)
    last, nxt = min(start + span - 1, count - 1), min(start + span, count - 1)
    top = [np.asarray(t, dtype=np.float64)[:TOP_ROWS] for t in thumbs]
    if top[last][..., 3].sum() < TOP_MIN_ALPHA or top[nxt][..., 3].sum() < TOP_MIN_ALPHA:
        return None
    inner = [np.abs(top[i + 1] - top[i]).mean() for i in range(start, max(start, last))]
    biggest = max(inner) if inner else 0.0
    return None if biggest < EPS else float(np.abs(top[nxt] - top[last]).mean() / biggest)
