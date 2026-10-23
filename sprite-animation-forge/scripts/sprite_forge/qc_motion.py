"""Deterministic motion-quality metrics on the output frames (used by QC-10..QC-14 in qc.py).

All metrics work on 32x32 premultiplied-RGBA thumbnails (BOX resize, per channel) so they are cheap and
independent of the cell size. They are *proxies*: they say "this does not look like a clean loop / the
character changed / nothing moves", never "this looks natural" (that needs the vision review).

``seam_ratio(frames)``           distance(last, first) / mean adjacent distance; None when undefined (< 3 frames or
                                 no motion). ~1 for a closed cycle, large when the last frame does not lead back.
``silhouette_similarity(frames)``  minimum IoU of the alpha masks (32x32, alpha >= 0.5) of adjacent frames: a jump in
                                 silhouette between neighbouring frames (limb teleport, different pose family).
                                 (dHash was tried first: its range is too compressed - two disjoint blobs still score 0.72.)
``palette_intersection(frames)``   minimum histogram intersection (64 RGB bins of the opaque pixels) between a frame
                                 and the median histogram: a frame drawn in different colours.
``motion_spread(frames)``        largest pairwise thumbnail distance: ~0 when nothing moves.
``gait_phase_deviation(frames, view)``  QC-14: how far a walk's leg signal (``video_gait.leg_signal``, ``view`` ``"side"`` or
                                 ``"front"``) is from the shape of an evenly timed cycle, both scaled to 0..1, at the best
                                 cyclic shift (max abs difference). 0 = every frame advances the stride by the same amount;
                                 ~1 = a stalled or shuffled cycle. None when there is no gait to read (< 4 frames, a blank frame,
                                 or legs that hardly swing - the same limits ``video_gait.foot_strike_start`` uses).
``gait_phase_from_signal(signal, view)``  the same on a leg signal that was already measured.

Blank frames (no opaque pixel) are ignored by every metric; QC-05 reports them.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

from .video_gait import MIN_LEG_RANGE, MIN_SPREAD_CHANGE, leg_signal

THUMB = 32
ALPHA_MIN = 64
EPS = 1e-4


def _opaque(frames):
    return [f for f in frames if (f[..., 3] >= ALPHA_MIN).any()]


def thumb(rgba: np.ndarray) -> np.ndarray:
    a = rgba[..., 3:4].astype(np.float64) / 255.0
    pm = np.concatenate([rgba[..., :3].astype(np.float64) * a, rgba[..., 3:4].astype(np.float64)], axis=2)
    chans = [np.asarray(Image.fromarray(np.rint(pm[..., k]).astype(np.uint8), "L").resize((THUMB, THUMB), Image.BOX),
                        dtype=np.float64) / 255.0 for k in range(4)]
    return np.stack(chans, axis=2)


def _dist(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.abs(a - b).mean())


def seam_ratio(frames) -> float | None:
    t = [thumb(f) for f in _opaque(frames)]
    if len(t) < 3:
        return None
    adjacent = float(np.mean([_dist(t[i], t[i + 1]) for i in range(len(t) - 1)]))
    if adjacent < EPS:
        return None
    return _dist(t[-1], t[0]) / adjacent


def _mask(rgba: np.ndarray) -> np.ndarray:
    alpha = np.asarray(Image.fromarray(rgba[..., 3], "L").resize((THUMB, THUMB), Image.BOX), dtype=np.float64) / 255.0
    return alpha >= 0.5


def _iou(a: np.ndarray, b: np.ndarray) -> float:
    union = int((a | b).sum())
    return float((a & b).sum()) / union if union else 1.0


def silhouette_similarity(frames) -> float:
    masks = [_mask(f) for f in _opaque(frames)]
    if len(masks) < 2:
        return 1.0
    return min(_iou(masks[i], masks[i + 1]) for i in range(len(masks) - 1))


def _hist(rgba: np.ndarray) -> np.ndarray:
    px = rgba[..., :3][rgba[..., 3] >= ALPHA_MIN] // 64
    idx = px[:, 0].astype(int) * 16 + px[:, 1].astype(int) * 4 + px[:, 2].astype(int)
    h = np.bincount(idx, minlength=64).astype(np.float64)
    return h / max(h.sum(), 1.0)


def palette_intersection(frames) -> float:
    hists = [_hist(f) for f in _opaque(frames)]
    if len(hists) < 2:
        return 1.0
    median = np.median(np.stack(hists), axis=0)
    median = median / max(median.sum(), 1e-9)
    return float(min(np.minimum(h, median).sum() for h in hists))


def motion_spread(frames) -> float:
    t = [thumb(f) for f in _opaque(frames)]
    if len(t) < 2:
        return 0.0
    return max(_dist(t[i], t[j]) for i in range(len(t)) for j in range(i + 1, len(t)))


def _even_gait(n: int, view: str) -> np.ndarray:
    """Leg signal of an evenly timed cycle, scaled to 0..1. Side: the feet's spread |cos| (widest at contact);
    front/back: the height difference of the feet |sin| (level at contact). n=6 -> side 1,0,0,1,0,0 / front 0,1,1,0,1,1."""
    phase = 2 * np.pi * np.arange(n) / n
    t = np.round(np.abs(np.cos(phase) if view == "side" else np.sin(phase)), 9)
    return (t - t.min()) / (t.max() - t.min())


def gait_phase_from_signal(signal, view: str) -> float | None:
    if len(signal) < 4 or any(v is None for v in signal):
        return None
    s = np.asarray(signal, dtype=np.float64)
    span = float(s.max() - s.min())
    change = span / max(float(s.mean()), 1e-9) if view == "side" else span
    if change < (MIN_SPREAD_CHANGE if view == "side" else MIN_LEG_RANGE):
        return None
    norm = (s - s.min()) / span
    even = _even_gait(len(s), view)
    return float(min(np.abs(norm - np.roll(even, k)).max() for k in range(len(s))))


def gait_phase_deviation(frames, view: str) -> float | None:
    return gait_phase_from_signal(leg_signal(frames, view), view)
