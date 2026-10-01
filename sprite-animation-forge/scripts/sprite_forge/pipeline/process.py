"""Whole post-processing chain (docs/05 sections 1, 9, 10).

Public API
----------
``ProcessParams``  action settings with the docs' defaults (see the dataclass).
``process_sheet(raw_path, out_dir, params=None, profile=None) -> ProcessResult``
    validate -> chroma -> split -> components -> measure -> scale -> align -> compose,
    writing into ``out_dir``: ``clean.png``, ``frames/NNN.png`` (3 digits, from 000),
    ``sheet.png`` (single row, ``N*cell_w x cell_h``), ``process.json``.
    ``profile`` is an optional ``ScaleProfile``/dict used by ``scale_strategy="preserve"``
    (falls back to fit with warning ``no_scale_profile``).
``ProcessResult``: ``data`` (the process.json dict), ``frames`` (list of RGBA arrays),
``sheet`` (RGBA array), ``clean`` (RGBA array), ``out_dir``, and ``warnings`` (property).

process.json (schema_version 1; no timestamps, no absolute paths)::

    raw {file (basename), sha256, width, height}
    params {grid "RxC", frames, cell {w,h}, margin {top,side,bottom},
            background {mode, key_color "#RRGGBB"|null, t_in, t_out, despill, edge_band_px},
            components {mode, merge_gap_px, min_area_px},
            anchor, x_anchor, scale_strategy, art_style, resample "lanczos"|"box"}
    derived {bg_color, bg_distance_to_key, row_boundaries, col_boundaries, raw_cell_height,
             scale, scale_strategy_used, baseline_y,
             frames [ {index, cell [x0,y0,x1,y1], empty, gutter_missing, bbox, feet_y,
                       feet_y_strict, anchor [x,y], offset [dx,dy], overflow {l,t,r,b},
                       removed_components, removed_area, info_removed_gt_5pct} ]}
    outputs {"clean.png": "sha256:..", "sheet.png": .., "frames/000.png": ..}
    warnings [str]

Per-frame ``cell``, ``bbox``, ``feet_y``, ``feet_y_strict`` and ``anchor`` are in raw sheet
pixels (so a UI can draw them on raw.png); ``offset`` is the integer paste offset of the
resampled crop on the output canvas. Empty cells give a blank frame, null measurements and
warning ``empty_frame:<index>``; overflowing frames give ``overflow:<index>`` (never cropped
silently in the data: the amounts are recorded).

Notes on ambiguous spots
------------------------
* ``art_style`` ``pixel_art`` / ``retro_pixel`` selects BOX resampling, anything else LANCZOS.
* ``merge_gap_px=None`` is resolved once from the raw cell height (``H / rows``) and the
  resolved value is recorded and used for every cell.
* Default grid is the docs example 2x3 with 6 frames.
* PNGs are written with ``optimize=False, compress_level=6`` and no metadata chunks.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from . import PipelineError, round_half_up
from .align import blank_frame, compose_sheet, place_frame
from .chroma import KEY_MAGENTA, remove_background, validate_input
from .components import DEFAULT_MIN_AREA_PX, default_merge_gap_px, filter_components
from .measure import Layout, measure_frame
from .scale import ScaleProfile, choose_scale, overflow_px
from .split import crop, select_cells, split_grid

PIPELINE_VERSION = "sprite_forge@0.1.0"
PIXEL_ART_STYLES = ("pixel_art", "retro_pixel")


@dataclass
class ProcessParams:
    rows: int = 2
    cols: int = 3
    frames: int = 6
    cell_w: int = 128
    cell_h: int = 128
    margin_top: int = 8
    margin_side: int = 8
    margin_bottom: int = 10
    key_color: tuple[int, int, int] = KEY_MAGENTA
    t_in: float = 30
    t_out: float = 90
    despill: bool = True
    edge_band_px: int = 2
    components: str = "largest"
    merge_gap_px: int | None = None
    min_area_px: int = DEFAULT_MIN_AREA_PX
    anchor: str = "feet"
    x_anchor: str = "mass"
    scale_strategy: str = "fit"
    art_style: str = "clean_hd"

    @property
    def layout(self) -> Layout:
        return Layout(self.cell_w, self.cell_h, self.margin_top, self.margin_side, self.margin_bottom)

    @property
    def pixel_art(self) -> bool:
        return self.art_style in PIXEL_ART_STYLES


@dataclass
class ProcessResult:
    data: dict
    frames: list[np.ndarray]
    sheet: np.ndarray
    clean: np.ndarray
    out_dir: Path

    @property
    def warnings(self) -> list[str]:
        return self.data["warnings"]


def _save_png(arr: np.ndarray, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr, "RGBA").save(path, format="PNG", optimize=False, compress_level=6)
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _hex(color) -> str | None:
    return None if color is None else "#{:02X}{:02X}{:02X}".format(*(int(c) for c in color))


def _r4(v):
    return None if v is None else round(float(v), 4)


def process_sheet(
    raw_path,
    out_dir,
    params: ProcessParams | None = None,
    profile: ScaleProfile | dict | None = None,
) -> ProcessResult:
    p = params or ProcessParams()
    raw_path, out_dir = Path(raw_path), Path(out_dir)
    layout = p.layout
    if not 1 <= p.frames <= p.rows * p.cols:
        raise PipelineError("invalid_params", f"frames={p.frames} does not fit a {p.rows}x{p.cols} grid")

    raw_bytes = raw_path.read_bytes()
    arr = validate_input(raw_path, p.rows, p.cols)
    height, width = arr.shape[:2]

    chroma = remove_background(arr, p.key_color, p.t_in, p.t_out, p.despill, p.edge_band_px)
    clean = chroma.rgba
    split = split_grid(clean[..., 3], p.rows, p.cols)
    cells = select_cells(split, p.frames)

    raw_cell_h = round_half_up(height / p.rows)
    merge_gap = p.merge_gap_px if p.merge_gap_px is not None else default_merge_gap_px(raw_cell_h)

    filtered, measures, comps = [], [], []
    for cell in cells:
        res = filter_components(crop(clean, cell).copy(), p.components, merge_gap, p.min_area_px)
        filtered.append(res.rgba)
        comps.append(res)
        measures.append(measure_frame(res.rgba))

    choice = choose_scale(p.scale_strategy, measures, layout, p.anchor, p.x_anchor, profile, raw_cell_h)

    warnings = list(chroma.warnings) + list(choice.warnings)
    frames, records = [], []
    for cell, rgba, m, comp in zip(cells, filtered, measures, comps):
        x0, y0, x1, y1 = cell.rect
        rec = {
            "index": cell.index,
            "cell": [x0, y0, x1, y1],
            "empty": m is None,
            "gutter_missing": cell.gutter_missing,
            "bbox": None,
            "feet_y": None,
            "feet_y_strict": None,
            "anchor": None,
            "offset": None,
            "overflow": None,
            "removed_components": int(comp.removed),
            "removed_area": int(comp.removed_area),
            "info_removed_gt_5pct": bool(comp.info_flag),
        }
        if cell.gutter_missing:
            warnings.append(f"gutter_missing:{cell.index}")
        if m is None:
            warnings.append(f"empty_frame:{cell.index}")
            frames.append(blank_frame(layout))
        else:
            placed = place_frame(rgba, m, choice.scale, layout, p.anchor, p.x_anchor, p.pixel_art)
            over = overflow_px(m, choice.scale, layout, p.anchor, p.x_anchor)
            if any(over.values()):
                warnings.append(f"overflow:{cell.index}")
            ax, ay = m.anchor_point(p.anchor, p.x_anchor)
            rec.update(
                bbox=[m.bbox[0] + x0, m.bbox[1] + y0, m.bbox[2] + x0, m.bbox[3] + y0],
                feet_y=m.feet_y + y0,
                feet_y_strict=m.feet_y_strict + y0,
                anchor=[_r4(ax + x0), _r4(ay + y0)],
                offset=list(placed.offset),
                overflow=over,
            )
            frames.append(placed.frame)
        records.append(rec)

    sheet = compose_sheet(frames)
    outputs = {"clean.png": _save_png(clean, out_dir / "clean.png")}
    for i, frame in enumerate(frames):
        outputs[f"frames/{i:03d}.png"] = _save_png(frame, out_dir / "frames" / f"{i:03d}.png")
    outputs["sheet.png"] = _save_png(sheet, out_dir / "sheet.png")

    data = {
        "schema_version": 1,
        "pipeline_version": PIPELINE_VERSION,
        "raw": {
            "file": raw_path.name,
            "sha256": hashlib.sha256(raw_bytes).hexdigest(),
            "width": width,
            "height": height,
        },
        "params": {
            "grid": f"{p.rows}x{p.cols}",
            "frames": p.frames,
            "cell": {"w": p.cell_w, "h": p.cell_h},
            "margin": {"top": p.margin_top, "side": p.margin_side, "bottom": p.margin_bottom},
            "background": {
                "mode": chroma.mode,
                "key_color": _hex(chroma.key_color),
                "t_in": p.t_in,
                "t_out": p.t_out,
                "despill": p.despill,
                "edge_band_px": p.edge_band_px,
            },
            "components": {"mode": p.components, "merge_gap_px": merge_gap, "min_area_px": p.min_area_px},
            "anchor": p.anchor,
            "x_anchor": p.x_anchor,
            "scale_strategy": p.scale_strategy,
            "art_style": p.art_style,
            "resample": "box" if p.pixel_art else "lanczos",
        },
        "derived": {
            "bg_color": None if chroma.bg_color is None else [_r4(c) for c in chroma.bg_color],
            "bg_distance_to_key": _r4(chroma.bg_distance_to_key),
            "row_boundaries": split.row_boundaries,
            "col_boundaries": split.col_boundaries,
            "raw_cell_height": raw_cell_h,
            "scale": choice.scale,
            "scale_strategy_used": choice.strategy,
            "baseline_y": layout.baseline,
            "frames": records,
        },
        "outputs": outputs,
        "warnings": warnings,
    }
    (out_dir / "process.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return ProcessResult(data, frames, sheet, clean, out_dir)
