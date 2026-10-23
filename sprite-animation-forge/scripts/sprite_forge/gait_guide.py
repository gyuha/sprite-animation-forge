"""Gait guide (forge task #42): a stick-figure sheet laid out like a walk's grid, one evenly timed pose per cell, attached as
the second reference of a side-view walk so the model sees the poses instead of only reading them (docs/04).

``make_gait_guide(key_hex, rows, cols, frames, facing="right", cell=CELL) -> PIL.Image``  deterministic RGB image,
    ``cols*cell`` x ``rows*cell``. Frame ``i`` (reading order) is the pose at ``i/frames`` of the cycle: frame 1 is contact
    with the left foot forward, frame ``frames/2 + 1`` the same with the sides swapped (the 6-frame walk of
    ``motion_library.txt``). Each arm swings opposite to its leg; the swinging foot is lifted off the ground.
    The character's left limbs are ``LEFT_RGB`` (dark), the right ones ``RIGHT_RGB`` (light), head and torso ``BODY_RGB``.
    Facing right shows the left side, so the left limbs are drawn on top. ``facing="left"`` mirrors every cell.
    The figure stands between the layout guide's head and feet lines (``layout_guide.safe_area``). No text, no grid lines,
    no anti-aliasing: the image holds the key colour and the three grays only.
"""

from __future__ import annotations

import math

from PIL import Image, ImageDraw, ImageOps

from .layout_guide import safe_area

CELL = 256
LEFT_RGB = (60, 60, 60)
BODY_RGB = (115, 115, 115)
RIGHT_RGB = (175, 175, 175)
WIDTH = 7                 # px, every line
LEG_SWING = 26.0          # degrees either side of vertical at contact
ARM_SWING = 24.0
FOOT_LIFT = 0.07          # of the figure height, the swinging foot at mid-swing. A lift, not a knee bend: a bent shin moves
                          # the foot sideways and breaks the stride width's |cos| shape (the guide scored QC-14 0.31)


def _limb(start, angle_deg, length):
    a = math.radians(angle_deg)
    return start[0] + length * math.sin(a), start[1] + length * math.cos(a)


def _pose(draw: ImageDraw.ImageDraw, phase: float, cell: int, margin_pct: int) -> None:
    _, _, crown_pct, floor_pct = safe_area(margin_pct)
    crown, floor = cell * crown_pct / 100, cell * floor_pct / 100
    height = floor - crown
    head_r = 0.14 * height
    thigh, shin = 0.22 * height, 0.22 * height
    arm = 0.30 * height
    cx = cell / 2

    c = math.cos(2 * math.pi * phase)
    s = math.sin(2 * math.pi * phase)
    legs = {"left": LEG_SWING * c, "right": -LEG_SWING * c}
    swing = {"left": max(0.0, -s), "right": max(0.0, s)}  # the leg moving forward is off the ground
    arms = {"left": -ARM_SWING * c, "right": ARM_SWING * c}

    def foot(side, hip):
        knee = _limb(hip, legs[side], thigh)
        toe = _limb(knee, legs[side], shin)
        return knee, (toe[0], toe[1] - FOOT_LIFT * height * swing[side])

    # stand the lower foot on the feet line
    probe = (0.0, 0.0)
    lowest = max(foot(side, probe)[1][1] for side in ("left", "right"))
    hip = (cx, floor - lowest - WIDTH / 2)
    neck = (cx, hip[1] - 0.30 * height)
    head = (cx, neck[1] - head_r)
    shoulder = (cx, neck[1] + WIDTH)

    def leg(side, rgb):
        knee, toe = foot(side, hip)
        draw.line([hip, knee, toe], fill=rgb, width=WIDTH, joint="curve")
        draw.line([toe, (toe[0] + 0.06 * height, toe[1])], fill=rgb, width=WIDTH)  # the foot points forward

    def arm_line(side, rgb):
        draw.line([shoulder, _limb(shoulder, arms[side], arm)], fill=rgb, width=WIDTH)

    leg("right", RIGHT_RGB)        # the far side first
    arm_line("right", RIGHT_RGB)
    draw.line([neck, hip], fill=BODY_RGB, width=WIDTH)
    draw.ellipse([head[0] - head_r, head[1] - head_r, head[0] + head_r, head[1] + head_r], fill=BODY_RGB)
    draw.line([(head[0] + head_r - 2, head[1]), (head[0] + head_r + 0.05 * height, head[1])], fill=BODY_RGB, width=WIDTH)
    leg("left", LEFT_RGB)          # the near side on top
    arm_line("left", LEFT_RGB)


def make_gait_guide(key_hex: str, rows: int, cols: int, frames: int, facing: str = "right", cell: int = CELL,
                    margin_pct: int = 8) -> Image.Image:
    key = tuple(int(key_hex[i:i + 2], 16) for i in (1, 3, 5))
    sheet = Image.new("RGB", (cols * cell, rows * cell), key)
    for i in range(frames):
        tile = Image.new("RGB", (cell, cell), key)
        _pose(ImageDraw.Draw(tile), i / frames, cell, margin_pct)
        if facing == "left":
            tile = ImageOps.mirror(tile)
        r, col = divmod(i, cols)
        sheet.paste(tile, (col * cell, r * cell))
    return sheet
