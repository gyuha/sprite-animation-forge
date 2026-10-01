"""Preview GIF (docs/07 section 9).

Public API
----------
``frame_duration_ms(fps) -> int``  ``round(1000 / fps / 10) * 10``.
``render_gif(frames, fps) -> bytes``  deterministic bytes for a list of RGBA PIL frames.

Notes on ambiguous spots
------------------------
* The duration formula uses Python ``round`` (banker's rounding): 8 fps -> 120 ms, not 130.
* The last frame is held 400 ms longer (docs/07 section 9). Pillow merges consecutive identical
  frames into one longer frame, so a GIF can have fewer frames than the action.
"""

from __future__ import annotations

import io

import numpy as np
from PIL import Image

HOLD_LAST_MS = 400
TRANSPARENT_INDEX = 255


def frame_duration_ms(fps: int) -> int:
    return round(1000 / fps / 10) * 10


def _to_paletted(frame: Image.Image) -> Image.Image:
    rgba = np.array(frame.convert("RGBA"))
    opaque = rgba[..., 3] >= 128
    q = Image.fromarray(rgba[..., :3], "RGB").quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    idx = np.array(q)
    idx[~opaque] = TRANSPARENT_INDEX
    out = Image.fromarray(idx, "P")
    pal = (q.getpalette() or [])[: 255 * 3]
    out.putpalette(pal + [0] * (768 - len(pal)))
    return out


def render_gif(frames: list[Image.Image], fps: int) -> bytes:
    pal = [_to_paletted(f) for f in frames]
    durations = [frame_duration_ms(fps)] * len(pal)
    durations[-1] += HOLD_LAST_MS
    buf = io.BytesIO()
    pal[0].save(buf, format="GIF", save_all=True, append_images=pal[1:], duration=durations, loop=0,
                transparency=TRANSPARENT_INDEX, disposal=2, optimize=False)
    return buf.getvalue()
