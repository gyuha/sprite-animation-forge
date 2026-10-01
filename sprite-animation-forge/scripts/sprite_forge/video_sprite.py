"""Video -> sprite attempt (docs/13). The clip is turned into a ``raw.png`` sheet in the plan's grid, so the normal
pipeline (chroma -> split -> scale -> align -> QC) runs unchanged on it.

``prepare_first_frame(reference, out, key_hex, size)``  square key-colour canvas with the character centred at ~60 %.
``extract_frames(mp4, out_dir) -> (paths, fps)``         ffmpeg/ffprobe; ``ffmpeg_missing`` (exit 3) when absent.
``build_raw_sheet(frames, n, rows, cols, key_hex, loop, cell) -> (sheet, info)``  selection + background normalisation.

Background normalisation: the border colour of each frame is the background; pixels the chroma alpha calls fully
transparent are repainted with the exact key colour (clip compression noise would otherwise leak into the sheet).
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

from .errors import EXIT_PRECONDITION, ForgeError
from .pipeline.chroma import compute_alpha, estimate_background
from .qc_motion import thumb
from .video_loop import distance_matrix, reduce_indices, select_loop, select_oneshot

CANVAS_FILL = 0.6        # character height / canvas height of the first frame
KEY_TOLERANCE = 60.0     # RGB distance from the key colour that counts as "character" in the reference
SHEET_CELL = 256
MAX_FRAMES = 400


def _key_rgb(key_hex: str) -> tuple[int, int, int]:
    return tuple(int(key_hex[i:i + 2], 16) for i in (1, 3, 5))


def prepare_first_frame(reference, out, key_hex: str, size: int = 768) -> Path:
    key = _key_rgb(key_hex)
    img = Image.open(reference).convert("RGB")
    arr = np.asarray(img, dtype=np.float64)
    mask = np.sqrt(((arr - np.asarray(key, dtype=np.float64)) ** 2).sum(axis=-1)) > KEY_TOLERANCE
    if not mask.any():
        raise ForgeError("invalid_image", "the reference has no character pixels (all key colour)")
    ys, xs = np.where(mask)
    box = img.crop((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))
    scale = min(size * CANVAS_FILL / box.height, size * CANVAS_FILL / box.width * 1.4)
    box = box.resize((max(1, round(box.width * scale)), max(1, round(box.height * scale))), Image.LANCZOS)
    canvas = Image.new("RGB", (size, size), key)
    canvas.paste(box, ((size - box.width) // 2, (size - box.height) // 2))
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, format="PNG")
    return out


def _tool(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise ForgeError("ffmpeg_missing", f"{name} not found; install ffmpeg (docs/13-video-api-setup.md step 4)",
                         EXIT_PRECONDITION)
    return path


def _fps(mp4: Path) -> float:
    proc = subprocess.run([_tool("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_entries",
                           "stream=avg_frame_rate", "-of", "csv=p=0", str(mp4)], capture_output=True, text=True)
    try:
        num, _, den = proc.stdout.strip().partition("/")
        return round(float(num) / float(den or 1), 3)
    except (ValueError, ZeroDivisionError):
        return 0.0


def extract_frames(mp4, out_dir) -> tuple[list[Path], float]:
    mp4, out_dir = Path(mp4), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run([_tool("ffmpeg"), "-v", "error", "-y", "-i", str(mp4), "-fps_mode", "passthrough",
                           "-frames:v", str(MAX_FRAMES), str(out_dir / "%05d.png")], capture_output=True, text=True)
    frames = sorted(out_dir.glob("*.png"))
    if proc.returncode != 0 or not frames:
        raise ForgeError("video_decode_failed", f"ffmpeg could not decode the clip: {proc.stderr.strip()[-200:]}")
    return frames, _fps(mp4)


def _rgba(path: Path) -> np.ndarray:
    rgb = np.asarray(Image.open(path).convert("RGB"), dtype=np.uint8)
    return np.dstack([rgb, compute_alpha(rgb, estimate_background(rgb))])


def _square_cell(rgb: np.ndarray, alpha: np.ndarray, key: tuple[int, int, int], cell: int) -> Image.Image:
    rgb = np.where((alpha == 0)[..., None], np.asarray(key, dtype=np.uint8), rgb)
    img = Image.fromarray(rgb, "RGB")
    side = max(img.size)
    padded = Image.new("RGB", (side, side), key)
    padded.paste(img, ((side - img.width) // 2, (side - img.height) // 2))
    return padded.resize((cell, cell), Image.LANCZOS)


def build_raw_sheet(frames: list[Path], n: int, rows: int, cols: int, key_hex: str, loop: bool,
                    cell: int = SHEET_CELL) -> tuple[Image.Image, dict]:
    if n > rows * cols:
        raise ForgeError("invalid_params", f"{n} frames do not fit a {rows}x{cols} grid")
    rgbas = [_rgba(p) for p in frames]
    dist = distance_matrix([thumb(f) for f in rgbas])
    if loop:
        start, span = select_loop(dist, n)
    else:
        start, end = select_oneshot(dist, n)
        span = end - start
    picked = reduce_indices(start, span, n, loop)
    key = _key_rgb(key_hex)
    sheet = Image.new("RGB", (cols * cell, rows * cell), key)
    for k, idx in enumerate(picked):
        f = rgbas[min(idx, len(rgbas) - 1)]
        sheet.paste(_square_cell(f[..., :3], f[..., 3], key, cell), ((k % cols) * cell, (k // cols) * cell))
    info = {"source_frames": len(frames), "selected": "loop" if loop else "oneshot", "start": start, "span": span,
            "indices": picked}
    return sheet, info
