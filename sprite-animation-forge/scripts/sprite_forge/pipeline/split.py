"""Grid split with gutter snapping (docs/05 section 4).

Public API
----------
``ideal_boundaries(n, total) -> list[int]``
    ``round(i * total / n)`` for ``i = 0..n`` (outer edges 0 and ``total`` included).
``snap_boundary(empty, ideal, window) -> (position, found)``
    Move one inner boundary to the centre of a fully transparent band.
``split_grid(alpha, rows, cols) -> SplitResult``
    Horizontal boundaries from whole-row alpha, vertical boundaries per row strip.
``select_cells(result, frames) -> list[CellRect]``
    The first ``frames`` cells in row-major order (docs/05 section 4.3).
``crop(arr, cell) -> np.ndarray``
    View of a sheet array restricted to ``cell.rect``.

``SplitResult``: ``row_boundaries`` (rows+1 ints), ``col_boundaries`` (per row, cols+1
ints), ``cells`` (row-major ``CellRect``: ``index, row, col, rect=(x0, y0, x1, y1)``
exclusive end, ``gutter_missing``, ``empty``).

Notes on ambiguous spots
------------------------
* A gutter is a run of lines whose alpha is entirely 0. The search window is
  +-0.06 * size around the ideal boundary (height for rows, width for columns).
* The snapped position is the run centre ``(start + end) // 2`` clamped into the window,
  so a long empty run (e.g. an empty cell) never moves a boundary by more than 6 %.
  Ties between equally distant runs go to the earlier one.
* Ideal boundaries use ``floor(x + 0.5)`` (docs/05 section 10) instead of Python ``round``.
* ``gutter_missing``: a row boundary without gutter flags every cell of the rows above and
  below it; a column boundary without gutter flags the two cells next to it.
* ``empty`` is True when the cell has no pixel with alpha > 0.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import round_half_up

WINDOW_FRACTION = 0.06


@dataclass
class CellRect:
    index: int
    row: int
    col: int
    rect: tuple[int, int, int, int]  # x0, y0, x1, y1 (x1/y1 exclusive)
    gutter_missing: bool = False
    empty: bool = False


@dataclass
class SplitResult:
    rows: int
    cols: int
    row_boundaries: list[int]
    col_boundaries: list[list[int]]
    cells: list[CellRect] = field(default_factory=list)


def ideal_boundaries(n: int, total: int) -> list[int]:
    return [round_half_up(i * total / n) for i in range(n + 1)]


def _runs(empty: np.ndarray) -> list[tuple[int, int]]:
    """Maximal runs of True as ``(start, end_exclusive)``."""
    padded = np.concatenate(([False], empty, [False])).astype(np.int8)
    edges = np.flatnonzero(np.diff(padded))
    return [(int(a), int(b)) for a, b in zip(edges[::2], edges[1::2])]


def snap_boundary(empty: np.ndarray, ideal: int, window: int) -> tuple[int, bool]:
    """``empty[i]`` is True when line ``i`` is fully transparent."""
    lo, hi = max(1, ideal - window), min(len(empty) - 1, ideal + window)
    near = [(a, b) for a, b in _runs(empty) if a <= hi and b - 1 >= lo]
    if not near:
        return ideal, False
    containing = [r for r in near if r[0] <= ideal < r[1]]
    if containing:
        a, b = containing[0]
    else:
        a, b = min(near, key=lambda r: abs((r[0] + r[1]) // 2 - ideal))
    return min(max((a + b) // 2, lo), hi), True


def _snap_axis(empty: np.ndarray, n: int) -> tuple[list[int], list[bool]]:
    total = len(empty)
    window = int(WINDOW_FRACTION * total)  # floor: never exceeds 6 %
    bounds = ideal_boundaries(n, total)
    found = [True] * (n + 1)
    for i in range(1, n):
        bounds[i], found[i] = snap_boundary(empty, bounds[i], window)
    return bounds, found


def split_grid(alpha: np.ndarray, rows: int, cols: int) -> SplitResult:
    h, w = alpha.shape[:2]
    row_bounds, row_found = _snap_axis((alpha == 0).all(axis=1), rows)

    col_bounds: list[list[int]] = []
    cells: list[CellRect] = []
    for r in range(rows):
        y0, y1 = row_bounds[r], row_bounds[r + 1]
        bounds, found = _snap_axis((alpha[y0:y1] == 0).all(axis=0), cols)
        col_bounds.append(bounds)
        for c in range(cols):
            rect = (bounds[c], y0, bounds[c + 1], y1)
            missing = (
                (r > 0 and not row_found[r])
                or (r < rows - 1 and not row_found[r + 1])
                or (c > 0 and not found[c])
                or (c < cols - 1 and not found[c + 1])
            )
            empty = not (alpha[rect[1] : rect[3], rect[0] : rect[2]] > 0).any()
            cells.append(CellRect(r * cols + c, r, c, rect, missing, empty))
    return SplitResult(rows, cols, row_bounds, col_bounds, cells)


def select_cells(result: SplitResult, frames: int) -> list[CellRect]:
    return result.cells[:frames]


def crop(arr: np.ndarray, cell: CellRect) -> np.ndarray:
    x0, y0, x1, y1 = cell.rect
    return arr[y0:y1, x0:x1]
