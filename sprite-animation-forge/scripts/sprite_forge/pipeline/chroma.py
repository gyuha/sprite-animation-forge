"""Input validation and chroma-key background removal (docs/05 sections 2-3).

Public API
----------
``validate_input(source, rows, cols) -> np.ndarray``
    Decode (path or PIL image), convert to RGB/RGBA ``uint8`` HxWxC, check sizes.
    Raises ``PipelineError`` with code ``invalid_image`` / ``too_small`` / ``cell_too_small``.
``has_native_alpha(arr) -> bool``
    RGBA input whose border pixels all have alpha 0.
``estimate_background(rgb, border_px=None) -> tuple[float, float, float]``
    Per-channel median of the four border strips.
``compute_alpha(rgb, bg, t_in=30, t_out=90) -> np.ndarray``  (uint8 alpha ramp)
``despill(rgba, key_color, edge_band_px=2) -> np.ndarray``
    Despill on the edge band only. Returns a new RGBA array.
``resolve_key_color(colors) -> (key_color, warnings)``
    Key colour conflict rule (docs/05 section 3.4).
``remove_background(arr, key_color=KEY_MAGENTA, ...) -> ChromaResult``
    Whole stage; ``ChromaResult.rgba`` is the ``clean.png`` content.

Notes on ambiguous spots
------------------------
* Pixels with alpha 0 keep their original RGB (only alpha changes), except in the
  despill edge band.
* Key-colour rule: "both colours conflict" is read as "both #FF00FF and #00FF00
  conflict (distance < 120) with some profile colour"; then #FF00FF is kept with a warning.
* Despill picks the green rule when ``key_color`` is #00FF00, the magenta rule otherwise.
* A non-native RGBA input is keyed on its RGB; its original alpha is ignored.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

from . import PipelineError, round_half_up

KEY_MAGENTA = (255, 0, 255)
KEY_GREEN = (0, 255, 0)
KEY_CONFLICT_DISTANCE = 120
FAR_BACKGROUND_DISTANCE = 60
MIN_SHEET_SIZE = 256
MIN_CELL_SIZE = 96


@dataclass
class ChromaResult:
    rgba: np.ndarray  # HxWx4 uint8 (clean.png content)
    mode: str  # "chroma" | "native_alpha"
    key_color: tuple[int, int, int] | None
    bg_color: tuple[float, float, float] | None  # None for native_alpha
    bg_distance_to_key: float | None
    warnings: list[str] = field(default_factory=list)


def validate_input(source, rows: int, cols: int) -> np.ndarray:
    """Decode and validate a raw sheet (docs/05 section 2)."""
    if isinstance(source, Image.Image):
        img = source
    else:
        try:
            img = Image.open(Path(source))
            img.load()
        except Exception as exc:  # Pillow raises many types
            raise PipelineError("invalid_image", str(exc)) from exc
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    arr = np.array(img, dtype=np.uint8)
    h, w = arr.shape[:2]
    if min(w, h) < MIN_SHEET_SIZE:
        raise PipelineError("too_small", f"{w}x{h} < {MIN_SHEET_SIZE}")
    if w / cols < MIN_CELL_SIZE or h / rows < MIN_CELL_SIZE:
        raise PipelineError("cell_too_small", f"cell {w / cols:.0f}x{h / rows:.0f} < {MIN_CELL_SIZE}")
    return arr


def _border_mask(h: int, w: int, b: int) -> np.ndarray:
    mask = np.zeros((h, w), dtype=bool)
    mask[:b, :] = mask[-b:, :] = True
    mask[:, :b] = mask[:, -b:] = True
    return mask


def _border_px(h: int, w: int) -> int:
    return max(2, round_half_up(0.01 * min(w, h)))


def has_native_alpha(arr: np.ndarray) -> bool:
    if arr.ndim != 3 or arr.shape[2] != 4:
        return False
    h, w = arr.shape[:2]
    return not arr[..., 3][_border_mask(h, w, _border_px(h, w))].any()


def estimate_background(rgb: np.ndarray, border_px: int | None = None) -> tuple[float, float, float]:
    h, w = rgb.shape[:2]
    b = border_px if border_px is not None else _border_px(h, w)
    pixels = rgb[_border_mask(h, w, b)][:, :3]
    med = np.median(pixels, axis=0)
    return (float(med[0]), float(med[1]), float(med[2]))


def compute_alpha(rgb: np.ndarray, bg, t_in: float = 30, t_out: float = 90) -> np.ndarray:
    diff = rgb[..., :3].astype(np.float64) - np.asarray(bg, dtype=np.float64)
    d = np.sqrt((diff**2).sum(axis=-1))
    ramp = np.clip(255.0 * (d - t_in) / (t_out - t_in), 0.0, 255.0)
    return np.floor(np.round(ramp, 4) + 0.5).astype(np.uint8)


def despill(rgba: np.ndarray, key_color=KEY_MAGENTA, edge_band_px: int = 2) -> np.ndarray:
    out = rgba.copy()
    alpha = rgba[..., 3]
    near_transparent = ndimage.binary_dilation(
        alpha == 0, structure=np.ones((3, 3), dtype=bool), iterations=edge_band_px
    )
    band = (alpha > 0) & near_transparent
    r = rgba[..., 0].astype(np.int16)
    g = rgba[..., 1].astype(np.int16)
    b = rgba[..., 2].astype(np.int16)
    if tuple(key_color) == KEY_GREEN:
        s = np.maximum(0, g - np.maximum(r, b))
        g = np.where(band, g - s, g)
    else:
        s = np.maximum(0, np.minimum(r, b) - g)
        r = np.where(band, r - s, r)
        b = np.where(band, b - s, b)
    out[..., 0], out[..., 1], out[..., 2] = r, g, b
    return out


def _distance(a, b) -> float:
    return float(np.linalg.norm(np.asarray(a, dtype=np.float64) - np.asarray(b, dtype=np.float64)))


def resolve_key_color(colors) -> tuple[tuple[int, int, int], list[str]]:
    """Pick the key colour given the profile's primary/secondary RGB colours."""
    for key in (KEY_MAGENTA, KEY_GREEN):
        if all(_distance(c, key) >= KEY_CONFLICT_DISTANCE for c in colors):
            return key, []
    return KEY_MAGENTA, ["key_color_conflict: all key colours are close to the character colours"]


def remove_background(
    arr: np.ndarray,
    key_color=KEY_MAGENTA,
    t_in: float = 30,
    t_out: float = 90,
    do_despill: bool = True,
    edge_band_px: int = 2,
) -> ChromaResult:
    """Run the whole background stage on a validated RGB/RGBA array."""
    if has_native_alpha(arr):
        return ChromaResult(arr.copy(), "native_alpha", None, None, None)

    rgb = arr[..., :3]
    bg = estimate_background(rgb)
    alpha = compute_alpha(rgb, bg, t_in, t_out)
    rgba = np.dstack([rgb, alpha])
    if do_despill:
        rgba = despill(rgba, key_color, edge_band_px)

    dist = round(_distance(bg, key_color), 4)
    warnings = ["bg_far_from_key"] if dist > FAR_BACKGROUND_DISTANCE else []
    return ChromaResult(rgba, "chroma", tuple(key_color), bg, dist, warnings)
