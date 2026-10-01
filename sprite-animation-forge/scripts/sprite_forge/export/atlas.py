"""Row-per-unit atlas layout (docs/07 section 3).

Public API
----------
``export_units(plan) -> [{unit, action, direction, kind}]``  atlas row order: plan ``order`` with body
    actions before fx, directions ``down, up, right, left`` inside an action (this differs from
    ``plan.units`` whose generation order is down, right, up, left).
``frame_name(action, direction, index, multi_direction) -> str``
``atlas_size(cell_w, cell_h, rows, max_frames) -> (W, H)``  raises ``atlas_too_large`` beyond 4096.
``build_atlas(plan, frames_by_unit) -> Atlas``  ``frames_by_unit`` maps a unit path to its list of
    RGBA PIL frames; only units present there get a row (missing units are skipped by the caller).

Notes on ambiguous spots
------------------------
* ``cell_mismatch`` is raised when a frame size differs from the plan cell (docs/07 section 2 says all
  actions share one cell size; the plan cell is the reference).
* Single-direction plans use ``direction = None`` in entries and names without a direction.
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from ..errors import ForgeError

PAD = 2
MAX_SIZE = 4096
DIRECTION_ORDER = ("down", "up", "right", "left")


@dataclass
class Atlas:
    image: Image.Image
    size: tuple[int, int]
    cell: tuple[int, int]
    entries: list[dict]  # one per frame: name, unit, action, direction, index, row, x, y, w, h
    rows: list[dict]  # one per unit: unit, action, direction, kind, row, frames (count)


def export_units(plan: dict) -> list[dict]:
    multi = len(plan["directions"]) > 1
    out = []
    for action in sorted(plan["order"], key=lambda a: plan["actions"][a].get("kind", "body") != "body"):
        eff = plan["actions"][action].get("directions", plan["directions"])
        for d in sorted(eff, key=DIRECTION_ORDER.index):
            out.append({"unit": f"{action}/{d}" if multi else action, "action": action,
                        "direction": d if multi else None,
                        "kind": plan["actions"][action].get("kind", "body")})
    return out


def frame_name(action: str, direction: str | None, index: int, multi_direction: bool) -> str:
    return f"{action}_{direction}_{index}" if multi_direction else f"{action}_{index}"


def atlas_size(cell_w: int, cell_h: int, rows: int, max_frames: int) -> tuple[int, int]:
    w = PAD + max_frames * (cell_w + PAD)
    h = PAD + rows * (cell_h + PAD)
    if w > MAX_SIZE or h > MAX_SIZE:
        raise ForgeError(
            "atlas_too_large",
            f"atlas would be {w}x{h} (limit {MAX_SIZE}x{MAX_SIZE}; {rows} rows x {max_frames} frames at "
            f"{cell_w}x{cell_h}); reduce actions/directions or use a smaller cell",
        )
    return w, h


def build_atlas(plan: dict, frames_by_unit: dict[str, list[Image.Image]]) -> Atlas:
    cw, ch = plan["cell"]["w"], plan["cell"]["h"]
    multi = len(plan["directions"]) > 1
    units = [u for u in export_units(plan) if u["unit"] in frames_by_unit]
    for u in units:
        for i, f in enumerate(frames_by_unit[u["unit"]]):
            if f.size != (cw, ch):
                raise ForgeError("cell_mismatch", f"{u['unit']} frame {i} is {f.size[0]}x{f.size[1]}, plan cell is {cw}x{ch}")
    max_frames = max((len(frames_by_unit[u["unit"]]) for u in units), default=0)
    size = atlas_size(cw, ch, len(units), max_frames)
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    entries, rows = [], []
    for row, u in enumerate(units):
        frames = frames_by_unit[u["unit"]]
        rows.append({**u, "row": row, "frames": len(frames)})
        for i, f in enumerate(frames):
            x, y = PAD + i * (cw + PAD), PAD + row * (ch + PAD)
            image.paste(f.convert("RGBA"), (x, y))
            entries.append({"name": frame_name(u["action"], u["direction"], i, multi), "unit": u["unit"],
                            "action": u["action"], "direction": u["direction"], "index": i, "row": row,
                            "x": x, "y": y, "w": cw, "h": ch})
    return Atlas(image, size, (cw, ch), entries, rows)
