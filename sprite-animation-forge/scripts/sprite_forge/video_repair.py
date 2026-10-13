"""Repairing a walk loop that hitches (docs/14 area D): jump frames remade between their neighbours, only when that helps.

A video model redraws thin parts a little differently every frame, and now and then one frame puts the body somewhere
its neighbours do not: every still looks right and the loop still hitches. The loop is read as it will play (cyclic, the last
frame followed by the first), on the DENSE cut - the 6-8 frames of the final sheet are too sparse to tell a hitch from a
pose that simply changes the silhouette a lot.

``odd_scores(frames, baseline=None)``  per frame, how much farther the frame is from both its neighbours than they are from
                          each other: ``(d(k-1,k) + d(k,k+1)) / max(d(k-1,k+1), HALF * typical step)`` on premultiplied RGBA
                          (coverage and colour) over the union box and over its upper part. The turning point of a swing is NOT odd (its steps are
                          tiny); a frame displaced against two similar neighbours is. A frame also has to be off by more than
                          ``MAG_RATIO`` typical steps. (A plain "step / median step" was tried first: a legitimate walk's steps
                          vary 0.35-2.5x in the synthetic clips, so it flags every walk.)
``find_jumps(frames)``    the odd frames: ``[{"frame": k, "score": s}]``.
``repair_jumps(frames, interpolator=None, mode="auto", discover=find_interpolator) -> (frames, report)``
    the odd frame is remade by ``interpolator.between(prev, next, 0.5)`` and kept only when the loop's worst odd score
    (measured against the ORIGINAL box and typical steps, so a garbage frame cannot widen the box and look better) drops under
    ``IMPROVE``; else it is reported under ``unmade`` and left as filmed. At most ``MAX_REPAIRS`` frames per loop. The
    interpolator is looked for ONLY when a frame is to be made. ``mode`` ``"off"``: nothing; ``"auto"``: without one the loop is
    cut as filmed and the report carries a ``rife_unavailable`` warning; ``"on"``: without one a
    ``ForgeError("rife_missing", exit 3)``. A found interpolator that fails is an error in every mode.
``report``: ``{applied, jumps, made, unmade, why, warnings}`` (``why``: ``off`` / ``cut_too_short`` (under ``MIN_CUT``
frames) / ``rife_not_found`` / None).
"""

from __future__ import annotations

import numpy as np

from .errors import EXIT_PRECONDITION, ForgeError
from .interpolate import find_interpolator

ODD_RATIO = 2.5          # (d1 + d2) / d(prev, next): 1 for a straight path, ~2 at a sharp turn, more for a displaced frame
MAG_RATIO = 1.2          # and the frame is off from its neighbours by more than this many typical steps
HALF = 0.5               # d(prev, next) is never taken below this share of a typical step
MIN_CUT = 12             # a loop of fewer frames is too sparse: a swing sampled 6 times per cycle scores 2.6 even when smooth
MAX_REPAIRS = 3
IMPROVE = 0.9            # a repair must bring the loop's worst odd score under this share of what it was
UPPER = 0.45             # the upper part of the union box (head, hair, arms) is scored apart
EPS = 1e-6


def _union_box(frames):
    mask = np.zeros(frames[0].shape[:2], bool)
    for f in frames:
        mask |= f[..., 3] >= 32
    ys, xs = np.where(mask)
    if not ys.size:
        return 0, frames[0].shape[0], 0, frames[0].shape[1]
    return int(ys.min()), int(ys.max()) + 1, int(xs.min()), int(xs.max()) + 1


def _premult(f: np.ndarray, box) -> np.ndarray:
    """Premultiplied RGBA in 0..1 inside the box: coverage AND colour, so two poses that cover the same pixels (legs swapped, a
    mirror image) still differ - alpha alone loses which way the body is moving."""
    y0, y1, x0, x1 = box
    a = f[y0:y1, x0:x1].astype(np.float64) / 255.0
    return np.concatenate([a[..., :3] * a[..., 3:4], a[..., 3:4]], axis=2)


def _regions(frames, box):
    pm = [_premult(f, box) for f in frames]
    top = max(1, int(UPPER * (box[1] - box[0])))
    return [pm, [a[:top] for a in pm]]


def _typical(regions) -> list[float]:
    n = len(regions[0])
    return [float(np.median([np.abs(r[(k + 1) % n] - r[k]).mean() for k in range(n)])) for r in regions]


def baseline_of(frames):
    """``(box, typical steps)`` of a loop as filmed: what later readings of the same loop are measured against."""
    box = _union_box(frames)
    return box, _typical(_regions(frames, box))


def odd_scores(frames, baseline=None) -> list[float]:
    """``baseline`` = ``(box, typical steps)`` from the loop as filmed; None = measured from ``frames`` themselves."""
    n = len(frames)
    box = baseline[0] if baseline else _union_box(frames)
    regions = _regions(frames, box)
    typical = baseline[1] if baseline else _typical(regions)
    out = []
    for k in range(n):
        best = 0.0
        for region, step in zip(regions, typical):
            if step < EPS:
                continue
            d = lambda i, j: float(np.abs(region[i % n] - region[j % n]).mean())  # noqa: E731
            around = d(k - 1, k) + d(k, k + 1)
            odd = around / max(d(k - 1, k + 1), HALF * step)
            if odd >= ODD_RATIO and around / 2 >= MAG_RATIO * step:
                best = max(best, odd)
        out.append(best)
    return out


def find_jumps(frames) -> list[dict]:
    return [{"frame": k, "score": round(s, 3)} for k, s in enumerate(odd_scores(frames)) if s > 0] if len(frames) >= 4 else []


def repair_jumps(frames, interpolator=None, mode: str = "auto", discover=find_interpolator):
    n = len(frames)
    report = {"applied": False, "jumps": find_jumps(frames) if n >= 3 else [], "made": [], "unmade": [], "why": None,
              "warnings": []}
    if mode == "off":
        report["why"] = "off"
        return list(frames), report
    if n < MIN_CUT:
        report["why"], report["jumps"] = "cut_too_short", []
        return list(frames), report
    if not report["jumps"]:
        return list(frames), report
    out = list(frames)
    baseline = baseline_of(frames)
    for _ in range(MAX_REPAIRS):
        scores = odd_scores(out, baseline)
        target = int(np.argmax(scores))
        if scores[target] <= 0:
            break
        if interpolator is None:
            interpolator = discover()
            if interpolator is None:
                if mode == "on":
                    raise ForgeError("rife_missing", "repair=on needs RIFE: set SPRITE_FORGE_RIFE_BIN or put rife-ncnn-vulkan "
                                     "on PATH (docs/13-video-api-setup.md)", EXIT_PRECONDITION)
                report["why"] = "rife_not_found"
                report["warnings"].append(f"rife_unavailable: {len(report['jumps'])} jump(s) not repaired, the loop is cut as filmed")
                break
        made = interpolator.between(out[(target - 1) % n], out[(target + 1) % n], 0.5)
        trial = list(out)
        trial[target] = made
        if max(odd_scores(trial, baseline)) < IMPROVE * scores[target]:
            out = trial
            report["made"].append(target)
        else:
            report["unmade"].append({"frame": target, "score": round(scores[target], 3)})
            break
    report["applied"] = bool(report["made"])
    return out, report
