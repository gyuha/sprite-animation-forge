"""Connected-component filter per cell (docs/05 section 5).

Public API
----------
``default_merge_gap_px(raw_cell_height) -> int``   ``max(4, round(0.02 * RH))``
``filter_components(rgba, mode="largest", merge_gap_px=None, min_area_px=16) -> ComponentResult``
    ``rgba`` is one cell (HxWx4 uint8). Removed components get alpha 0 (RGB untouched).
    ``merge_gap_px=None`` uses ``default_merge_gap_px(rgba.shape[0])``.

``ComponentResult``: ``rgba`` (filtered copy), ``kept`` / ``removed`` (component counts),
``removed_area`` (px), ``main_area`` (px; 0 for an empty cell), and ``info_flag``
(removed area > 5 % of main area, docs/05 section 5 last paragraph).

Notes on ambiguous spots
------------------------
* Mask is ``alpha >= 64``; labelling is 8-connected. Area is the pixel count of the mask.
* Only pixels of the mask (alpha >= 64) that belong to a removed component are cleared;
  weaker edge pixels (alpha 1..63) are left unchanged.
* Gap between two bboxes is ``max(dx, dy)`` where ``dx``/``dy`` are the numbers of empty
  pixel columns/rows between them (0 if they overlap or touch). Only the gap to ``main``
  is checked (not transitive). Ties for the largest component go to the lowest label
  (first in scan order).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage

from . import round_half_up

ALPHA_THRESHOLD = 64
MIN_AREA_RATIO = 0.01
INFO_REMOVED_RATIO = 0.05
DEFAULT_MIN_AREA_PX = 16


@dataclass
class ComponentResult:
    rgba: np.ndarray
    kept: int
    removed: int
    removed_area: int
    main_area: int

    @property
    def info_flag(self) -> bool:
        return self.removed_area > INFO_REMOVED_RATIO * self.main_area


def default_merge_gap_px(raw_cell_height: int) -> int:
    return max(4, round_half_up(0.02 * raw_cell_height))


def _bbox_gap(a: tuple[slice, slice], b: tuple[slice, slice]) -> int:
    gaps = []
    for sa, sb in zip(a, b):
        gaps.append(max(0, max(sa.start, sb.start) - min(sa.stop, sb.stop)))
    return max(gaps)


def filter_components(
    rgba: np.ndarray,
    mode: str = "largest",
    merge_gap_px: int | None = None,
    min_area_px: int = DEFAULT_MIN_AREA_PX,
) -> ComponentResult:
    if mode not in ("largest", "all"):
        raise ValueError(f"unknown components mode {mode!r}")
    if merge_gap_px is None:
        merge_gap_px = default_merge_gap_px(rgba.shape[0])

    mask = rgba[..., 3] >= ALPHA_THRESHOLD
    labels, n = ndimage.label(mask, structure=np.ones((3, 3), dtype=int))
    if n == 0:
        return ComponentResult(rgba.copy(), 0, 0, 0, 0)

    areas = np.bincount(labels.ravel(), minlength=n + 1)[1:]
    boxes = ndimage.find_objects(labels)
    main = int(np.argmax(areas))  # lowest label on ties

    if mode == "largest":
        keep = [
            i == main
            or (
                areas[i] >= MIN_AREA_RATIO * areas[main]
                and _bbox_gap(boxes[i], boxes[main]) <= merge_gap_px
            )
            for i in range(n)
        ]
    else:
        keep = [bool(areas[i] >= min_area_px) for i in range(n)]

    keep_lut = np.concatenate(([False], keep))
    remove = mask & ~keep_lut[labels]
    out = rgba.copy()
    out[..., 3][remove] = 0
    removed = n - sum(keep)
    return ComponentResult(
        out,
        kept=sum(keep),
        removed=removed,
        removed_area=int(areas[[i for i in range(n) if not keep[i]]].sum()),
        main_area=int(areas[main]),
    )
