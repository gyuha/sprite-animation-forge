"""Video -> sprite attempt (docs/13). The clip is turned into a ``raw.png`` sheet in the plan's grid, so the normal
pipeline (chroma -> split -> scale -> align -> QC) runs unchanged on it.

``prepare_first_frame(reference, out, key_hex, size, layout=None)``  square key-colour canvas with the character centred at ~60 %
                             (or placed by ``canvas_layout(action)``: walk/run big with no head-room, attack/jump with room above).
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
from .pipeline.scale import resample
from .qc_motion import thumb
from .video_restore import restore_made_frames
from .video_ghost import crossfade, give_way
from .video_gait import foot_strike_start, jolt_metrics
from .video_repair import repair_jumps
from .video_loop import detect_held, distance_matrix, find_loop, reduce_indices, seam_pop, select_oneshot

CANVAS_FILL = 0.6        # character height / canvas height of the first frame
KEY_TOLERANCE = 60.0     # RGB distance from the key colour that counts as "character" in the reference
SHEET_CELL = 256
MAX_FRAMES = 400


def _key_rgb(key_hex: str) -> tuple[int, int, int]:
    return tuple(int(key_hex[i:i + 2], 16) for i in (1, 3, 5))


# (top margin, character height) as fractions of the square canvas, by action. A walker or runner never raises anything
# above its head, so it gets no extra head-room and more pixels; an attack or jump needs room above the head for a raised
# weapon. Anything else keeps the centred default (None).
CANVAS_BY_ACTION = {"walk": (0.06, 0.80), "run": (0.06, 0.80), "attack": (0.30, 0.55), "jump": (0.30, 0.55)}


def canvas_layout(action: str) -> tuple[float, float] | None:
    return CANVAS_BY_ACTION.get(action)


def prepare_first_frame(reference, out, key_hex: str, size: int = 768, layout: tuple[float, float] | None = None) -> Path:
    """``layout`` = ``(top margin, character height)`` as fractions of the canvas, or None for the centred ~60 % default."""
    key = _key_rgb(key_hex)
    top_frac, fill = layout if layout else (None, CANVAS_FILL)
    img = Image.open(reference).convert("RGB")
    arr = np.asarray(img, dtype=np.float64)
    mask = np.sqrt(((arr - np.asarray(key, dtype=np.float64)) ** 2).sum(axis=-1)) > KEY_TOLERANCE
    if not mask.any():
        raise ForgeError("invalid_image", "the reference has no character pixels (all key colour)")
    ys, xs = np.where(mask)
    box = img.crop((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))
    scale = min(size * fill / box.height, size * fill / box.width * 1.4)
    box = box.resize((max(1, round(box.width * scale)), max(1, round(box.height * scale))), Image.LANCZOS)
    canvas = Image.new("RGB", (size, size), key)
    top = (size - box.height) // 2 if top_frac is None else round(size * top_frac)
    canvas.paste(box, ((size - box.width) // 2, top))
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


SIZE_TOL = 0.04          # a clip whose subject stays within this of its first height is not touched
SIZE_CLAMP = (0.5, 2.0)  # never rescale a frame by more than this
MIN_SUBJECT_PX = 12      # a first frame with a smaller subject cannot be measured


def _subject_height(rgba: np.ndarray) -> int:
    rows = np.where((rgba[..., 3] >= 128).any(axis=1))[0]
    return int(rows[-1] - rows[0] + 1) if rows.size else 0


def hold_size(rgbas: list[np.ndarray]) -> tuple[list[np.ndarray], dict]:
    """Bring every frame's subject back to the first frame's height (a walker coming toward the camera grows and its loop
    never closes). Each frame is scaled about its bottom centre onto a canvas wide and tall enough for the biggest scaling, so
    scaling up widens the picture instead of cutting the crown. A clip whose subject stays within ``SIZE_TOL`` is returned
    as it is."""
    heights = [_subject_height(f) for f in rgbas]
    ref = next((h for h in heights if h), 0)
    info = {"applied": False, "max_ratio": 1.0}
    if ref < MIN_SUBJECT_PX:
        return rgbas, info
    ratios = [h / ref if h else 1.0 for h in heights]
    info["max_ratio"] = round(max(max(r, 1 / r) for r in ratios), 4)
    if info["max_ratio"] - 1 <= SIZE_TOL:
        return rgbas, info
    factors = [min(max(ref / h, SIZE_CLAMP[0]), SIZE_CLAMP[1]) if h else 1.0 for h in heights]
    h0, w0 = rgbas[0].shape[:2]
    big = max(1.0, max(factors))
    cw, ch = int(np.ceil(w0 * big)), int(np.ceil(h0 * big))
    held = []
    for f, factor in zip(rgbas, factors):
        scaled = resample(f, factor, False, mode="coverage")
        canvas = np.zeros((ch, cw, 4), dtype=np.uint8)
        x0, y0 = (cw - scaled.shape[1]) // 2, ch - scaled.shape[0]
        canvas[y0:, x0:x0 + scaled.shape[1]] = scaled
        held.append(canvas)
    info["applied"] = True
    return held, info


def build_raw_sheet(frames: list[Path], n: int, rows: int, cols: int, key_hex: str, loop: bool,
                    cell: int = SHEET_CELL, *, size_hold: bool = True, cycles: int | None = None,
                    min_len: int | None = None, max_len: int | None = None, foot: str | None = None,
                    repair: str = "off", interpolator=None, source_dir: Path | None = None) -> tuple[Image.Image, dict]:
    """Pick ``n`` frames of the clip as a sheet in the plan's grid. ``min_len``/``max_len`` are the loop's period window in
    source frames (a clip that holds each drawing for k frames reads them as drawings: the window is divided by k). ``foot``
    (``"side"``/``"front"``, a looping walk or run) starts the loop on a foot strike and records the jolt index. ``repair``
    (``"off"``/``"auto"``/``"on"``, docs/14) remakes jump frames of a loop with ``interpolator`` (RIFE), see ``video_repair``; a made frame that came out damaged is restored from its source where that is
    safe (``video_restore``). ``source_dir`` keeps the sheet's source frames (``<position>-<source frame>.png``)."""
    if n > rows * cols:
        raise ForgeError("invalid_params", f"{n} frames do not fit a {rows}x{cols} grid")
    rgbas = [_rgba(p) for p in frames]
    hold = {"applied": False, "max_ratio": 1.0}
    if size_hold:
        rgbas, hold = hold_size(rgbas)
    thumbs = [thumb(f) for f in rgbas]
    held_ratio, unique = detect_held(thumbs)
    per_drawing = len(thumbs) / len(unique)
    sel = [thumbs[i] for i in unique]
    dist = distance_matrix(sel)
    info: dict = {}
    if loop:
        scale_len = lambda v: None if not v else max(1, round(v / per_drawing))  # noqa: E731
        choice = find_loop(dist, n, sel, min_len=scale_len(min_len), max_len=scale_len(max_len), cycles=cycles)
        start, span = choice.start, choice.span
        info.update(research=choice.research, cycles_suspected=choice.cycles_suspected,
                    seam_ratio=None if choice.seam_ratio is None else round(choice.seam_ratio, 4),
                    start_foot_source=None, foot_shift=0, jolt_index=None, head_move=None)
        if foot:
            sel_frames = [rgbas[i] for i in unique]
            new_start, source = foot_strike_start(sel_frames, start, span, foot)
            info.update(start_foot_source=source, foot_shift=abs(new_start - start), **jolt_metrics(sel_frames, new_start, span))
            start = new_start
        pop = seam_pop(sel, start, span)
        info["seam_pop"] = None if pop is None else round(pop, 4)
    else:
        start, end = select_oneshot(dist, n)
        span = end - start
    key = _key_rgb(key_hex)
    positions = reduce_indices(start, span, n, loop)
    picked = [unique[min(i, len(unique) - 1)] for i in positions]
    if loop:  # a hitch is read (and repaired) on the dense cut, then the sheet's frames are taken from it
        cut_src = [unique[min(i, len(unique) - 1)] for i in range(start, start + span)]
        cut, ghost = give_way([rgbas[i] for i in cut_src], key)  # a frame that cross-fades two drawings gives way to its clean neighbour
        before_repair = cut
        cut, report = repair_jumps(before_repair, interpolator, repair)
        cut, restore = restore_made_frames(cut, before_repair, report["made"], key)  # a melted made frame: back to its source if safe
        gone = {r["frame"] for r in restore["restored"]}
        report["made"] = [o for o in report["made"] if o not in gone]
        report["restored"] = [{**r, "source_frame": cut_src[r["source_frame"]], "frame": cut_src[r["frame"]]} for r in restore["restored"]]
        report["restore_regressed"] = [{**r, "frame": cut_src[r["frame"]]} for r in restore["regressed"]]
        report["made_source"] = [cut_src[o] for o in report["made"]]
        report["crossfade"] = crossfade(cut, report["made"])  # a made frame that cross-fades is measured and named, and kept
        ghost["ghosts"] = [cut_src[o] for o in ghost["ghosts"]]
        ghost["given_way"] = [{"frame": cut_src[g["frame"]], "replaced_by": cut_src[g["replaced_by"]]} for g in ghost["given_way"]]
        ghost["retake"] = [{"reason": r["reason"], "frame": cut_src[r["frame"]]} for r in ghost["retake"]]
        report["warnings"] = [*report["warnings"], *(f"retake: {r['reason']} (frame {r['frame']})" for r in ghost["retake"])]
        seq = [cut[min(max(pos - start, 0), len(cut) - 1)] for pos in positions]
        report["made_in_sheet"] = [k for k, pos in enumerate(positions) if pos - start in report["made"]]
    else:
        report = {"applied": False, "jumps": [], "made": [], "unmade": [], "why": "not_a_loop", "warnings": [], "crossfade": [],
                  "restored": [], "restore_regressed": []}
        ghost = {"ghosts": [], "given_way": [], "retake": []}
        seq = [rgbas[min(idx, len(rgbas) - 1)] for idx in picked]
    sheet = Image.new("RGB", (cols * cell, rows * cell), key)
    for k, f in enumerate(seq):
        sheet.paste(_square_cell(f[..., :3], f[..., 3], key, cell), ((k % cols) * cell, (k // cols) * cell))
    info.update({"source_frames": len(frames), "selected": "loop" if loop else "oneshot", "start": start, "span": span,
                 "indices": picked, "size_hold": hold, "held": {"ratio": round(held_ratio, 4), "drawings": len(unique)},
                 "jump_repair": report, "made": report.get("made_in_sheet", []), "ghost": ghost, "retake": ghost["retake"],
                 "restored": report["restored"], "restore_regressed": report["restore_regressed"], "warnings": report["warnings"]})
    if source_dir is not None:  # the sheet's frames as the clip had them (after the size hold), for provenance and a later reprocess
        source_dir.mkdir(parents=True, exist_ok=True)
        for old in source_dir.glob("*.png"):
            old.unlink()
        for k, idx in enumerate(picked):
            Image.fromarray(rgbas[min(idx, len(rgbas) - 1)], "RGBA").save(source_dir / f"{k:02d}-{idx:04d}.png", format="PNG")
    return sheet, info
