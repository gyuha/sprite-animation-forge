"""Gait reading on a cut of a clip (docs/14 area C): where the foot strikes, and how much the body jolts.

``leg_signal(frames, view)``            per frame, read on the lower ``LEG_FRACTION`` of the subject: ``"side"`` = how far the
                                        legs are apart (width of the leg rows / height); ``"front"`` (front or back view) =
                                        how differently high the two feet are (|bottom of the left half - bottom of the right|).
``foot_strike_start(frames, start, span, view) -> (start, source)``  moves the cut's start to the nearest frame (within half
                                        a cycle, inside the clip) where a foot is down: side = legs furthest apart, front =
                                        both feet at the same height. ``source`` ``"legs_spread"`` / ``"legs_lift"``, or
                                        ``"none"`` (and the start is untouched) when the signal hardly changes over the cut:
                                        a body with no legs to read.
``jolt_metrics(frames, start, span)``   ``jolt_index`` = mean magnitude of the second difference of the body's centre-of-mass path
                                        (closed over the loop) / subject height - ~0 for a steady walk, large for a bounce
                                        that jumps; ``head_move`` = peak-to-peak movement of the head centre / height.
``jolt_warning(meta, max_jolt)``        ``"jolt_exceeded: ..."`` only when the plan set a limit and the index is above it.
``foot_view(plan, action)``             ``"side"`` / ``"front"`` for a looping walk or run in a single direction, else None.
"""

from __future__ import annotations

import numpy as np

from .plan import resolve_unit

LEG_FRACTION = 0.4        # lower share of the subject that counts as legs
MIN_LEG_RANGE = 0.04      # front view: foot-height difference / subject height below which there is no gait to read
MIN_SPREAD_CHANGE = 0.15  # side view: peak-to-peak of the leg width / its mean below which there are no legs swinging (a body
                          # that only squashes changes ~8 %, a walker's legs ~70 %)
TIE = 0.02                # frames within this share of the signal range of the best are ties (the nearest wins)
HEAD_BAND = 0.2


def _box(rgba: np.ndarray):
    mask = rgba[..., 3] >= 128
    rows, cols = np.where(mask.any(axis=1))[0], np.where(mask.any(axis=0))[0]
    return None if not rows.size else (int(rows[0]), int(rows[-1]), int(cols[0]), int(cols[-1]))


def leg_signal(frames, view: str) -> list[float | None]:
    out: list[float | None] = []
    for f in frames:
        box = _box(f)
        if box is None:
            out.append(None)
            continue
        y0, y1, x0, x1 = box
        height = y1 - y0 + 1
        legs = (f[..., 3] >= 128)[max(y0, y1 - int(LEG_FRACTION * height) + 1):y1 + 1, x0:x1 + 1]
        if view == "side":
            xs = np.where(legs.any(axis=0))[0]
            out.append((xs[-1] - xs[0] + 1) / height if xs.size else None)
            continue
        mid = legs.shape[1] // 2
        bottoms = []
        for half in (legs[:, :mid], legs[:, mid:]):
            ys = np.where(half.any(axis=1))[0]
            bottoms.append(ys[-1] if ys.size else None)
        out.append(None if None in bottoms else abs(bottoms[0] - bottoms[1]) / height)
    return out


def foot_strike_start(frames, start: int, span: int, view: str) -> tuple[int, str]:
    source = "legs_spread" if view == "side" else "legs_lift"
    signal = leg_signal(frames, view)
    cut = [v for v in signal[start:start + span] if v is not None]
    if len(cut) < 2:
        return start, "none"
    change = (max(cut) - min(cut)) / max(float(np.mean(cut)), 1e-9) if view == "side" else max(cut) - min(cut)
    if change < (MIN_SPREAD_CHANGE if view == "side" else MIN_LEG_RANGE):
        return start, "none"
    lo, hi = max(0, start - span // 2), min(len(frames) - span - 1, start + span // 2)
    cands = [i for i in range(lo, hi + 1) if signal[i] is not None]
    if not cands:
        return start, "none"
    sign = 1.0 if view == "side" else -1.0  # side: furthest apart is best; front: smallest difference is best
    best = max(sign * signal[i] for i in cands)
    slack = TIE * (max(cut) - min(cut))
    tied = [i for i in cands if sign * signal[i] >= best - slack]
    return min(tied, key=lambda i: (abs(i - start), i)), source


def jolt_metrics(frames, start: int, span: int) -> dict:
    cut = frames[start:start + span]
    boxes = [_box(f) for f in cut]
    known = [b for b in boxes if b]
    if len(cut) < 3 or not known:
        return {"jolt_index": None, "head_move": None}
    height = max(b[1] for b in known) - min(b[0] for b in known) + 1

    def mass_centre(f):
        ys, xs = np.where(f[..., 3] >= 128)
        return (xs.mean(), ys.mean()) if ys.size else None

    def head_centre(f, box):  # the top HEAD_BAND of THIS frame's own subject, so a body that rises takes its head with it
        ys, xs = np.where((f[..., 3] >= 128)[box[0]:box[0] + max(1, int(HEAD_BAND * (box[1] - box[0] + 1)))])
        return (xs.mean(), ys.mean() + box[0]) if ys.size else None

    def fill(path):
        have = [p for p in path if p is not None]
        return None if not have else np.array([p if p is not None else have[0] for p in path], dtype=np.float64)

    body = fill([mass_centre(f) if b else None for f, b in zip(cut, boxes)])
    head = fill([head_centre(f, b) if b else None for f, b in zip(cut, boxes)])
    jolt = None
    if body is not None:  # the body's centre of mass, closed over the loop: a steady walk is smooth, a bounce that jumps is not
        second = np.roll(body, -1, axis=0) - 2 * body + np.roll(body, 1, axis=0)
        jolt = float(np.sqrt((second ** 2).sum(axis=1)).mean() / height)
    move = None if head is None else float(max(np.ptp(head[:, 0]), np.ptp(head[:, 1])) / height)
    return {"jolt_index": None if jolt is None else round(jolt, 5), "head_move": None if move is None else round(move, 5)}


def jolt_warning(meta: dict | None, max_jolt: float | None) -> str | None:
    index = (meta or {}).get("jolt_index")
    if max_jolt is None or index is None or index <= max_jolt:
        return None
    return f"jolt_exceeded: jolt_index {index} > max_jolt {max_jolt}"


def foot_view(plan: dict, action: str) -> str | None:
    act = plan["actions"][action]
    if action not in ("walk", "run") or not act["loop"]:
        return None
    _, direction, _ = resolve_unit(plan, action, None)
    return "side" if direction in ("right", "left") else "front" if direction in ("down", "up") else None
