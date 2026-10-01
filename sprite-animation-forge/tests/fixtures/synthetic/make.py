"""Deterministic synthetic sprite sheets with known ground truth (docs/11 section 3.1).

Usage (from tests, pytest puts ``tests/`` on sys.path)::

    from fixtures.synthetic.make import make_sheet, VARIANTS

    sheet = make_sheet("clean", rows=2, cols=3, cell_size=(256, 256), seed=0)
    sheet.image            # PIL.Image: RGB (RGBA for ``native_alpha``)
    sheet.key_color        # (255, 0, 255), or None for ``native_alpha``
    sheet.grid             # (rows, cols)
    sheet.cells            # list[Cell], row-major order
    sheet.cells[0].bbox    # (x0, y0, x1, y1) in sheet pixels, x1/y1 exclusive (PIL style)
    sheet.cells[0].feet    # (x, y): x = center between the legs, y = first row BELOW the legs
    sheet.png_bytes()      # deterministic PNG bytes; same args -> same bytes

``make_sheet(variant, rows=2, cols=2, cell_size=(256, 256), seed=0)``

* ``cell_size`` is the nominal (width, height) of one cell; the sheet is
  ``cols*w`` x ``rows*h``. Minimum 128x128 (the baseline jitter is +-15 px).
* ``seed`` only affects the specks variant (speck positions) and any future
  randomness. Everything else is a pure function of the arguments.
* ``VARIANTS`` lists the 15 variant names of docs/11 section 3.1.

Ground truth per ``Cell``:

* ``rect``: the actual cell rectangle (differs from the ideal equal division in
  ``shifted_gutters``). ``sheet.col_edges`` / ``sheet.row_edges`` are the actual
  cell edges (the gutter centers) including the outer edges.
* ``bbox``: bounding box of the whole intended foreground of the character
  (body, weapon, thin tip) and NOT the specks. ``None`` for an empty cell.
* ``feet``: the baseline point. Thin things hanging below the legs (the
  ``thin_below_feet`` tip) are inside ``bbox`` but do not move ``feet``.
* ``extras``: variant specific ground truth, e.g. ``body_bbox``, ``specks``
  (list of rects), ``sword_bbox``, ``pink_patch``.
* ``empty``: True when nothing was drawn.

The character is an ellipse body + circle head + two rectangle legs, hard
edged (no antialiasing) so bboxes are exact. Cell index ``k`` is ``row*cols+col``.
Variant specifics where docs/11 is ambiguous:

* ``shifted_gutters``: inner edges move by +-4 % of the sheet width/height,
  alternating sign (+, -, +, ...), characters stay centered in the shifted cells.
* ``narrow_gutter``: body width is ``cell_w - 20`` so neighbours are 20 px apart.
* ``edge_touch``: cell 0's character is moved right so it crosses into cell 1.
* ``scale_drift_12``: height factor alternates 1.06 / 0.94 by cell index.
* ``baseline_jitter``: feet Y offset cycles through 15, -15, 0, 10, -10, 5.
* ``empty_cell``: the last cell is empty.
* ``specks``: five 3x3 specks per cell, away from the character and cell edges.
* ``detached_sword``: sword is a 6 px wide bar with a 6 px empty gap to the body.
"""

from __future__ import annotations

import io
import random
from dataclasses import dataclass, field

import numpy as np
from PIL import Image, ImageDraw

VARIANTS = (
    "clean",
    "model_like_bg",
    "shifted_gutters",
    "narrow_gutter",
    "edge_touch",
    "scale_drift_12",
    "baseline_jitter",
    "empty_cell",
    "specks",
    "detached_sword",
    "thin_below_feet",
    "pinkish_character",
    "native_alpha",
    "wide_attack",
    "asymmetric_right",
)

KEY_COLOR = (255, 0, 255)
BODY = (40, 90, 200)
HEAD = (230, 200, 160)
LEG = (60, 60, 60)
SWORD = (200, 200, 210)
NOSE = (200, 120, 60)
PINK = (230, 90, 200)
JITTER_CYCLE = (15, -15, 0, 10, -10, 5)

Box = tuple[int, int, int, int]


@dataclass
class Cell:
    index: int
    row: int
    col: int
    rect: Box
    bbox: Box | None
    feet: tuple[int, int] | None
    extras: dict = field(default_factory=dict)

    @property
    def empty(self) -> bool:
        return self.bbox is None


@dataclass
class SyntheticSheet:
    variant: str
    image: Image.Image
    rows: int
    cols: int
    cell_size: tuple[int, int]
    key_color: tuple[int, int, int] | None
    col_edges: list[int]
    row_edges: list[int]
    cells: list[Cell]
    seed: int

    @property
    def grid(self) -> tuple[int, int]:
        return (self.rows, self.cols)

    def cell(self, row: int, col: int) -> Cell:
        return self.cells[row * self.cols + col]

    def png_bytes(self) -> bytes:
        buf = io.BytesIO()
        self.image.save(buf, format="PNG")
        return buf.getvalue()

    def save(self, path) -> None:
        with open(path, "wb") as f:
            f.write(self.png_bytes())


@dataclass
class _Spec:
    cx: int
    feet_y: int
    h: int
    bw: int
    body_color: tuple = BODY
    extra: str | None = None


class _Painter:
    """Draws on the sheet and, in parallel, on a mask used to measure the bbox."""

    def __init__(self, draw: ImageDraw.ImageDraw, size: tuple[int, int], rgba: bool):
        self.draw = draw
        self.mask = Image.new("L", size, 0)
        self._mdraw = ImageDraw.Draw(self.mask)
        self.rgba = rgba

    def _c(self, color):
        return (*color, 255) if self.rgba else color

    def rect(self, box, color):
        self.draw.rectangle(box, fill=self._c(color))
        self._mdraw.rectangle(box, fill=255)

    def ellipse(self, box, color):
        self.draw.ellipse(box, fill=self._c(color))
        self._mdraw.ellipse(box, fill=255)


def _background(variant: str, w: int, h: int) -> Image.Image:
    if variant == "native_alpha":
        return Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if variant == "model_like_bg":
        base = np.array((250, 3, 250), dtype=np.float64)
        corner = np.array((240, 13, 242), dtype=np.float64)
        yy, xx = np.mgrid[0:h, 0:w]
        d = np.sqrt(((xx - (w - 1) / 2) / (w / 2)) ** 2 + ((yy - (h - 1) / 2) / (h / 2)) ** 2)
        d = np.clip(d / np.sqrt(2), 0, 1)[..., None]
        arr = np.rint(base + d * (corner - base)).astype(np.uint8)
        return Image.fromarray(arr, "RGB")
    return Image.new("RGB", (w, h), KEY_COLOR)


def _edges(n: int, step: int, total: int, shifted: bool) -> list[int]:
    edges = [i * step for i in range(n + 1)]
    if shifted:
        shift = round(0.04 * total)
        for j in range(1, n):
            edges[j] += shift if j % 2 == 1 else -shift
    return edges


def _paint_character(p: _Painter, s: _Spec) -> dict:
    """Draw one character; returns extras. Measures bbox via p.mask afterwards."""
    top = s.feet_y - s.h
    r = int(0.11 * s.h)
    leg_h = int(0.3 * s.h)
    bx0 = s.cx - s.bw // 2
    bx1 = bx0 + s.bw - 1
    by0 = top + 2 * r
    by1 = s.feet_y - leg_h + int(0.05 * s.h)
    lw = max(2, int(s.bw * 0.25))
    for lx in (s.cx - s.bw // 4 - lw // 2, s.cx + s.bw // 4 - lw // 2):
        p.rect((lx, s.feet_y - leg_h, lx + lw - 1, s.feet_y - 1), LEG)
    p.ellipse((bx0, by0, bx1, by1), s.body_color)
    p.ellipse((s.cx - r, top, s.cx + r, top + 2 * r), HEAD)
    body_bbox = p.mask.getbbox()
    extras: dict = {"body_bbox": body_bbox}
    ymid = (by0 + by1) // 2

    if s.extra == "pink":
        box = (s.cx - 6, ymid - 6, s.cx + 5, ymid + 5)
        p.rect(box, PINK)
        extras["pink_patch"] = (box[0], box[1], box[2] + 1, box[3] + 1)
    elif s.extra == "detached_sword":
        x0 = body_bbox[2] + 6  # exactly 6 empty px between body and sword
        box = (x0, ymid - s.h // 4, x0 + 5, ymid + s.h // 4)
        p.rect(box, SWORD)
        extras["sword_bbox"] = (box[0], box[1], box[2] + 1, box[3] + 1)
    elif s.extra == "thin_tip":
        p.rect((s.cx, s.feet_y, s.cx, s.feet_y + 11), SWORD)  # 1 px wide, below feet
        extras["tip_bbox"] = (s.cx, s.feet_y, s.cx + 1, s.feet_y + 12)
    elif s.extra == "wide_sword":
        box = (s.cx, ymid - 4, s.cx + int(0.6 * s.bw / 0.36), ymid + 3)
        p.rect(box, SWORD)
        extras["sword_bbox"] = (box[0], box[1], box[2] + 1, box[3] + 1)
    elif s.extra == "right_facing":
        staff = (bx1 - 2, s.feet_y - int(0.75 * s.h), bx1 + 5, s.feet_y - int(0.25 * s.h))
        p.rect(staff, SWORD)
        p.rect((s.cx + r, top + r - 2, s.cx + r + 4, top + r + 2), NOSE)
        extras["staff_bbox"] = (staff[0], staff[1], staff[2] + 1, staff[3] + 1)
    return extras


def _specks(rng: random.Random, rect: Box, bbox: Box, count: int = 5) -> list[Box]:
    margin, keepout = 6, 6
    keep = (bbox[0] - keepout, bbox[1] - keepout, bbox[2] + keepout, bbox[3] + keepout)
    placed: list[Box] = []
    for _ in range(10_000):
        if len(placed) == count:
            return placed
        x = rng.randint(rect[0] + margin, rect[2] - margin - 3)
        y = rng.randint(rect[1] + margin, rect[3] - margin - 3)
        box = (x, y, x + 3, y + 3)
        if box[0] < keep[2] and box[2] > keep[0] and box[1] < keep[3] and box[3] > keep[1]:
            continue
        if any(
            box[0] < o[2] + 2 and box[2] > o[0] - 2 and box[1] < o[3] + 2 and box[3] > o[1] - 2
            for o in placed
        ):
            continue
        placed.append(box)
    raise RuntimeError("could not place specks; cell too small")


def make_sheet(
    variant: str = "clean",
    rows: int = 2,
    cols: int = 2,
    cell_size: tuple[int, int] = (256, 256),
    seed: int = 0,
) -> SyntheticSheet:
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant {variant!r}; choose from {VARIANTS}")
    cw, ch = cell_size
    if cw < 128 or ch < 128:
        raise ValueError("cell_size must be at least 128x128")
    W, H = cols * cw, rows * ch
    img = _background(variant, W, H)
    rgba = img.mode == "RGBA"
    draw = ImageDraw.Draw(img)
    rng = random.Random(seed)

    shifted = variant == "shifted_gutters"
    col_edges = _edges(cols, cw, W, shifted)
    row_edges = _edges(rows, ch, H, shifted)

    cells: list[Cell] = []
    n = rows * cols
    for k in range(n):
        row, col = divmod(k, cols)
        rect = (col_edges[col], row_edges[row], col_edges[col + 1], row_edges[row + 1])
        rw, rh = rect[2] - rect[0], rect[3] - rect[1]
        spec = _Spec(
            cx=rect[0] + rw // 2,
            feet_y=rect[1] + int(0.88 * rh),
            h=int(0.70 * ch),
            bw=int(0.36 * cw),
        )
        if variant == "narrow_gutter":
            spec.bw = cw - 20
        elif variant == "edge_touch" and k == 0:
            spec.cx = rect[2] - 10
        elif variant == "scale_drift_12":
            f = 1.06 if k % 2 == 0 else 0.94
            spec.h, spec.bw = int(spec.h * f), int(spec.bw * f)
        elif variant == "baseline_jitter":
            spec.feet_y += JITTER_CYCLE[k % len(JITTER_CYCLE)]
        elif variant == "pinkish_character":
            spec.extra = "pink"
        elif variant == "detached_sword":
            spec.extra = "detached_sword"
        elif variant == "thin_below_feet":
            spec.extra = "thin_tip"
        elif variant == "wide_attack":
            spec.cx = rect[0] + int(0.30 * rw)
            spec.extra = "wide_sword"
        elif variant == "asymmetric_right":
            spec.extra = "right_facing"

        if variant == "empty_cell" and k == n - 1:
            cells.append(Cell(k, row, col, rect, None, None))
            continue

        painter = _Painter(draw, (W, H), rgba)
        extras = _paint_character(painter, spec)
        bbox = painter.mask.getbbox()
        cells.append(Cell(k, row, col, rect, bbox, (spec.cx, spec.feet_y), extras))

    if variant == "specks":
        for c in cells:
            c.extras["specks"] = _specks(rng, c.rect, c.bbox)
            for x0, y0, x1, y1 in c.extras["specks"]:
                draw.rectangle((x0, y0, x1 - 1, y1 - 1), fill=(*BODY, 255) if rgba else BODY)

    if variant == "edge_touch":
        cells[0].extras["crosses_into"] = 1 if cols > 1 else None

    return SyntheticSheet(
        variant=variant,
        image=img,
        rows=rows,
        cols=cols,
        cell_size=(cw, ch),
        key_color=None if variant == "native_alpha" else KEY_COLOR,
        col_edges=col_edges,
        row_edges=row_edges,
        cells=cells,
        seed=seed,
    )
