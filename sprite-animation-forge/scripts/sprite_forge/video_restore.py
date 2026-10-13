"""Restoring a damaged made frame from its source (docs/14 area D).

An interpolator can hand back a frame that melted (a limb it could not follow, a smear). The frame it replaced - its SOURCE
frame, the one that jumped - is then the other candidate. The two are not equal, so the source is restored in place of the made
frame only where all of this holds:

1. the made frame is DAMAGED: its coverage (area of the body, alpha >= 128) differs from the source's by at least ``DAMAGE_TOL``.
   A jump moves the body, it does not change its area, so a made frame near the source's area is left alone.
2. KEY GUARD: the source does not bring more key-coloured body pixels than the made frame had (``key_excess``) - restoring
   a frame whose body is tinted by the key colour would deliver the spill.
3. it does not bring the jump back: the loop's worst odd score (``video_repair.odd_scores``, against the cut as filmed) is no
   worse than with the made frame. A restoration that revives the jump is ``regressed`` and refused.

``restore_made_frames(cut, originals, made, key) -> (cut, report)`` ``report = {restored: [{frame, source_frame, reason,
deviation}], regressed: [{frame, reason, deviation, ...}]}`` (frame = index in the cut; the caller maps it to the clip's frame).
Scoped adaptation of sprite-gen's source restoration (docs/14): no receipts or comparison artifacts, and no pixel-level key cap.
"""

from __future__ import annotations

import numpy as np

from .video_repair import baseline_of, odd_scores

DAMAGE_TOL = 0.08     # share of the source's body area the made frame may differ by
KEY_NEAR = 60.0       # colour distance from the key under which a body pixel is key-tinted
KEY_SLACK = 0.005     # extra key-tinted pixels (share of the body) the restored frame may carry over the made frame's


def _area(frame: np.ndarray) -> int:
    return int((frame[..., 3] >= 128).sum())


def damage(made: np.ndarray, source: np.ndarray) -> float:
    return abs(_area(made) - _area(source)) / max(_area(source), 1)


def key_excess(frame: np.ndarray, key) -> int:
    body = frame[..., 3] >= 128
    dist = np.linalg.norm(frame[..., :3].astype(np.float64) - np.asarray(key, dtype=np.float64), axis=2)
    return int((body & (dist < KEY_NEAR)).sum())


def restore_made_frames(cut, originals, made, key):
    out = list(cut)
    baseline = baseline_of(originals)
    restored, regressed = [], []
    for k in made:
        dev = round(damage(out[k], originals[k]), 3)
        if dev < DAMAGE_TOL:
            continue
        source = originals[k]
        if key_excess(source, key) > key_excess(out[k], key) + max(1, int(KEY_SLACK * _area(source))):
            regressed.append({"frame": k, "reason": "key_guard", "deviation": dev})
            continue
        trial = list(out)
        trial[k] = source
        before, after = max(odd_scores(out, baseline)), max(odd_scores(trial, baseline))
        if after > before:
            regressed.append({"frame": k, "reason": "restores_jump", "deviation": dev,
                              "odd_before": round(before, 3), "odd_after": round(after, 3)})
            continue
        out = trial
        restored.append({"frame": k, "source_frame": k, "reason": "coverage_deviation", "deviation": dev})
    return out, {"restored": restored, "regressed": regressed}
