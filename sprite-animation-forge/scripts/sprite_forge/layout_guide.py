"""Layout guide for single-still generation (docs/14 area B): a flat key-colour square with a thin outline for the safe
area, a line for the top of the head and a line for the feet. Attached as an extra reference so the model sizes and places
the character the way the pipeline expects, instead of guessing from words alone.

``safe_area(margin_pct) -> (lo, hi, crown, floor)``  percentages of the canvas: the safe box runs ``lo..hi`` on both axes,
    the head line is one margin inside the box (``2*margin``) and the feet line one margin inside the bottom.
``make_layout_guide(key_hex, margin_pct=8, size=GUIDE_SIZE) -> PIL.Image``  deterministic RGB image.
"""

from __future__ import annotations

from PIL import Image, ImageDraw

from .pipeline import round_half_up

GUIDE_SIZE = 512
OUTLINE_RGB = (150, 150, 150)  # the safe-area outline
LINE_RGB = (40, 40, 40)        # the head and feet lines
THICKNESS = 3                  # px, centred on the line


def safe_area(margin_pct: int = 8) -> tuple[int, int, int, int]:
    return margin_pct, 100 - margin_pct, 2 * margin_pct, 100 - 2 * margin_pct


def make_layout_guide(key_hex: str, margin_pct: int = 8, size: int = GUIDE_SIZE) -> Image.Image:
    key = tuple(int(key_hex[i:i + 2], 16) for i in (1, 3, 5))
    lo, hi, crown, floor = (round_half_up(size * p / 100) for p in safe_area(margin_pct))
    img = Image.new("RGB", (size, size), key)
    draw = ImageDraw.Draw(img)
    half = THICKNESS // 2

    def hline(y, x0, x1, rgb):
        draw.rectangle([x0, y - half, x1, y + half], fill=rgb)

    def vline(x, y0, y1, rgb):
        draw.rectangle([x - half, y0, x + half, y1], fill=rgb)

    hline(lo, lo - half, hi + half, OUTLINE_RGB)
    hline(hi, lo - half, hi + half, OUTLINE_RGB)
    vline(lo, lo - half, hi + half, OUTLINE_RGB)
    vline(hi, lo - half, hi + half, OUTLINE_RGB)
    hline(crown, lo + half + 1, hi - half - 1, LINE_RGB)
    hline(floor, lo + half + 1, hi - half - 1, LINE_RGB)
    return img
