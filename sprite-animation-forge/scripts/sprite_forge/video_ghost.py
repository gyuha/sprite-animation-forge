"""Ghost frames of a clip (docs/14 area D): a frame that cross-fades two drawings.

A video model sometimes answers with a frame that is two poses laid over each other (both pairs of legs half there). Chroma
alpha saturates at 90 colour distance, so on a key background such a frame still looks opaque - its ghost only shows as colour
pulled towards the key. So a frame is read on its distance from the key colour, scaled by the frame's own body colours:

``soft_share(frame, key)``   share of the body's pixels that are only HALF there (0.25 < soft < 0.75): ~0 for a crisp frame,
                             0.3-0.5 for two poses blended (synthetic clips); anti-aliasing gives a small baseline.
``ghost_frames(frames, key)``  the frames whose share is at least ``GHOST_MIN`` and ``GHOST_RATIO`` times the clip's typical share.
``give_way(frames, key) -> (frames, report)``  a ghost is given way to the clean frame beside it (the previous one, else the
                             next); one with no clean frame beside it stays and is a retake reason ``filmed-ghost``.
``alpha_share(frame)`` / ``crossfade(frames, made)``  the same reading on COVERAGE for frames an interpolator made (their
                             alpha is meaningful): a made frame that cross-fades two drawings inside its silhouette is
                             measured and named, and kept.
"""

from __future__ import annotations

import numpy as np

GHOST_MIN = 0.12      # at least this share of the body half-there
GHOST_RATIO = 1.8     # and this many times the clip's typical share
TYPICAL_FLOOR = 0.03  # a clip of very crisp frames is judged against this, not against ~0
LOW, HIGH = 0.25, 0.75
CROSSFADE_MIN = 0.08  # alpha share (of the made frame's body) in the half band that is named a cross-fade
KEY_MARGIN = 60.0     # colour distance from the key under which a pixel is background for sure


def soft_share(frame: np.ndarray, key) -> float:
    dist = np.linalg.norm(frame[..., :3].astype(np.float64) - np.asarray(key, dtype=np.float64), axis=2)
    far = dist[dist > KEY_MARGIN]
    if not far.size:
        return 0.0
    soft = np.clip(dist / max(float(np.percentile(far, 75)), 1.0), 0.0, 1.0)
    body = int((soft >= LOW).sum())
    return float(((soft > LOW) & (soft < HIGH)).sum() / body) if body else 0.0


def alpha_share(frame: np.ndarray) -> float:
    alpha = frame[..., 3].astype(np.float64) / 255.0
    body = int((alpha >= LOW).sum())
    return float(((alpha > LOW) & (alpha < HIGH)).sum() / body) if body else 0.0


def ghost_frames(frames, key) -> list[dict]:
    shares = [soft_share(f, key) for f in frames]
    typical = max(float(np.median(shares)), TYPICAL_FLOOR)
    return [{"frame": k, "share": round(s, 3), "ratio": round(s / typical, 2)}
            for k, s in enumerate(shares) if s >= GHOST_MIN and s / typical >= GHOST_RATIO]


def give_way(frames, key):
    n = len(frames)
    flagged = {g["frame"] for g in ghost_frames(frames, key)}
    out = list(frames)
    report = {"ghosts": sorted(flagged), "given_way": [], "retake": []}
    for k in sorted(flagged):
        clean = [j for j in ((k - 1) % n, (k + 1) % n) if j not in flagged]
        if clean:
            out[k] = frames[clean[0]]
            report["given_way"].append({"frame": k, "replaced_by": clean[0]})
        else:
            report["retake"].append({"reason": "filmed-ghost", "frame": k})
    return out, report


def crossfade(frames, made) -> list[dict]:
    return [{"frame": k, "share": round(alpha_share(frames[k]), 3)} for k in made if alpha_share(frames[k]) >= CROSSFADE_MIN]
