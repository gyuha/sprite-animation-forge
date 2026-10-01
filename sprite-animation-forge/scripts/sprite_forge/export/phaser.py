"""Phaser JSON Hash, animations.json, meta and generic JSON builders (docs/07 sections 4-6, 8).

Public API
----------
``anim_key(action, direction) -> str``     ``walk`` or ``walk_up``.
``phaser_json(atlas, origin, image_name) -> dict``      ``<cid>.json`` (JSON Hash with per-frame ``anchor``).
``animations_json(plan, atlas) -> dict``   ``{key: {frames, frameRate, repeat}}`` (loop -> -1, else 0).
``generic_json(plan, atlas, origin, image_name) -> dict``   ``<cid>.generic.json``.
``meta_json(plan, atlas, origin, baseline_y, texture_sha256, image_name, unit_info) -> dict``  ``<cid>.meta.json``.
``origin_for(baseline_y, cell_h) -> {"x": 0.5, "y": baseline_y / cell_h}``

Notes on ambiguous spots
------------------------
* Output names use the character id instead of ``hero`` (``<cid>.png`` ...).
* ``meta.actions[]`` follows docs/07 section 6 (``name`` = the plan action, one entry per atlas row) and adds
  ``direction`` (null for single-direction plans) and ``unit``; mirror-derived rows also carry ``mirror_of``.
  ``unit_info[unit]`` supplies ``attempt``, ``qc`` and optional ``mirror_of``.
"""

from __future__ import annotations

from .. import __version__
from .atlas import PAD, Atlas


def origin_for(baseline_y: int, cell_h: int) -> dict:
    return {"x": 0.5, "y": baseline_y / cell_h}


def anim_key(action: str, direction: str | None) -> str:
    return f"{action}_{direction}" if direction else action


def phaser_json(atlas: Atlas, origin: dict, image_name: str) -> dict:
    frames = {}
    for e in atlas.entries:
        frames[e["name"]] = {
            "frame": {"x": e["x"], "y": e["y"], "w": e["w"], "h": e["h"]},
            "rotated": False,
            "trimmed": False,
            "spriteSourceSize": {"x": 0, "y": 0, "w": e["w"], "h": e["h"]},
            "sourceSize": {"w": e["w"], "h": e["h"]},
            "anchor": dict(origin),
        }
    return {
        "frames": frames,
        "meta": {"app": "sprite-animation-forge", "version": __version__, "image": image_name,
                 "format": "RGBA8888", "size": {"w": atlas.size[0], "h": atlas.size[1]}, "scale": "1"},
    }


def _names(atlas: Atlas, unit: str) -> list[str]:
    return [e["name"] for e in atlas.entries if e["unit"] == unit]


def animations_json(plan: dict, atlas: Atlas) -> dict:
    out = {}
    for r in atlas.rows:
        a = plan["actions"][r["action"]]
        out[anim_key(r["action"], r["direction"])] = {
            "frames": _names(atlas, r["unit"]), "frameRate": a["fps"], "repeat": -1 if a["loop"] else 0}
    return out


def generic_json(plan: dict, atlas: Atlas, origin: dict, image_name: str) -> dict:
    animations = {}
    for r in atlas.rows:
        a = plan["actions"][r["action"]]
        animations[anim_key(r["action"], r["direction"])] = {
            "frames": _names(atlas, r["unit"]), "fps": a["fps"], "loop": a["loop"]}
    return {
        "schema_version": 1,
        "image": image_name,
        "cell": {"w": atlas.cell[0], "h": atlas.cell[1]},
        "origin": dict(origin),
        "frames": [{"name": e["name"], "action": e["action"], "direction": e["direction"], "index": e["index"],
                    "x": e["x"], "y": e["y"], "w": e["w"], "h": e["h"]} for e in atlas.entries],
        "animations": animations,
    }


def meta_json(plan: dict, atlas: Atlas, origin: dict, baseline_y: int, texture_sha256: str,
              image_name: str, unit_info: dict) -> dict:
    actions = []
    for r in atlas.rows:
        a = plan["actions"][r["action"]]
        info = unit_info[r["unit"]]
        item = {"name": r["action"], "direction": r["direction"], "unit": r["unit"], "row": r["row"],
                "frames": r["frames"], "fps": a["fps"], "loop": a["loop"], "attempt": info["attempt"],
                "qc": info["qc"]}
        if info.get("mirror_of"):
            item["mirror_of"] = info["mirror_of"]
        actions.append(item)
    return {
        "schema_version": 1,
        "character": plan["character"],
        "generator": {"name": "sprite-animation-forge", "version": __version__},
        "cell": {"w": atlas.cell[0], "h": atlas.cell[1]},
        "baseline_y": baseline_y,
        "origin": dict(origin),
        "padding": PAD,
        "view": plan["view"],
        "facing": plan["facing"],
        "actions": actions,
        "texture": {"file": image_name, "sha256": texture_sha256, "size": list(atlas.size)},
    }
