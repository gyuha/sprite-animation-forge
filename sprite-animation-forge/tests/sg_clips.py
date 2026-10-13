"""Synthetic walker clips for the sg_video_* tests: a figure on a key background whose legs and arms swing."""

import math

from PIL import Image, ImageDraw

KEY = (255, 0, 255)
W, H = 200, 260
BASE = 1.5  # the walker fills the frame like a first frame made by prepare_first_frame does


def walker(phase, scale=1.0, amp=1.0, lift=0, top_hidden=False):
    """One frame: body, head, two swinging legs and arms, feet on the line y = 250."""
    img = Image.new("RGB", (W, H), KEY)
    d = ImageDraw.Draw(img)
    s = scale * BASE
    cx, feet = W / 2, 250 - lift

    def box(x0, y0, x1, y1, color):
        d.rectangle([cx + x0 * s, feet - y1 * s, cx + x1 * s, feet - y0 * s], fill=color)

    swing = math.sin(phase) * 22 * amp
    box(-10 + swing, 0, 2 + swing, 38, (40, 60, 200))        # leg a
    box(-2 - swing, 0, 10 - swing, 38, (30, 90, 160))        # leg b
    box(-14, 38, 14, 86, (200, 60, 40))                      # torso
    box(-24 - swing * .7, 52, -14 - swing * .7, 84, (220, 170, 60))  # arm a
    box(14 + swing * .7, 52, 24 + swing * .7, 84, (220, 170, 60))    # arm b
    box(-9, 86, 9, 104, (240, 200, 160))                     # head
    if top_hidden:  # a subject that never reaches the upper half of the frame
        d.rectangle([0, 0, W, 180], fill=KEY)
    return img


def clip(tmp_path, total, period, *, scale=lambda i: 1.0, held=1, amp=lambda i: 1.0, lift=lambda i: 0, top_hidden=False):
    paths = []
    for i in range(total):
        j = i // held
        p = tmp_path / f"{i:04d}.png"
        walker(2 * math.pi * j / period, scale(i), amp(i), lift(i), top_hidden).save(p)
        paths.append(p)
    return paths


def walker_front(phase, scale=1.0, lift_px=26, bob=0):
    """Front / back view: the two legs lift alternately (one foot down at a time); both are down at phase 0 and pi."""
    img = Image.new("RGB", (W, H), KEY)
    d = ImageDraw.Draw(img)
    s, cx, feet = scale * BASE, W / 2, 250 - bob

    def box(x0, y0, x1, y1, color):
        d.rectangle([cx + x0 * s, feet - y1 * s, cx + x1 * s, feet - y0 * s], fill=color)

    sw = math.sin(phase)
    box(-14, max(0, sw) * lift_px, -3, 38 + max(0, sw) * lift_px, (40, 60, 200))      # left leg lifts while sin > 0
    box(3, max(0, -sw) * lift_px, 14, 38 + max(0, -sw) * lift_px, (30, 90, 160))      # right leg lifts while sin < 0
    box(-16, 38, 16, 86, (200, 60, 40))
    box(-26, 52, -16, 84, (220, 170, 60))
    box(16, 52, 26, 84, (220, 170, 60))
    box(-9, 86, 9, 104, (240, 200, 160))
    return img


def blob(phase, scale=1.0, bob=0):
    """A body with no legs (a slime): an ellipse that only squashes a little."""
    img = Image.new("RGB", (W, H), KEY)
    d = ImageDraw.Draw(img)
    s, cx, feet = scale * BASE, W / 2, 250 - bob
    wide = 1.0 + 0.04 * math.sin(phase)
    d.ellipse([cx - 40 * s * wide, feet - 90 * s, cx + 40 * s * wide, feet], fill=(80, 200, 120))
    return img


def clip_of(draw, tmp_path, total, period, **kw):
    paths = []
    for i in range(total):
        p = tmp_path / f"{i:04d}.png"
        draw(2 * math.pi * i / period, **kw(i) if callable(kw) else kw).save(p)
        paths.append(p)
    return paths
