"""Export validation (docs/07 section 10; replaces the browser Phaser smoke, which is out of scope).

``validate_export(plan, png_size, phaser, animations, generic, meta)`` raises
``ForgeError("export_validation_failed", ...)`` listing every problem found:

* every frame rect lies inside the texture and no two rects overlap
* frame names are unique and every name referenced by animations.json exists in the Phaser JSON
* per-action frame counts equal the plan ``frames``
* ``meta.json`` / ``generic.json`` have their required fields (no JSON Schema files exist for them yet)
* the Phaser JSON ``meta.size`` equals the PNG size
"""

from __future__ import annotations

from ..errors import ForgeError

META_KEYS = ("schema_version", "character", "generator", "cell", "baseline_y", "origin", "padding", "view",
             "facing", "actions", "texture")
GENERIC_KEYS = ("schema_version", "image", "cell", "origin", "frames", "animations")


def validate_export(plan: dict, png_size: tuple[int, int], phaser: dict, animations: dict, generic: dict,
                    meta: dict) -> None:
    problems: list[str] = []
    w, h = png_size
    frames = phaser["frames"]
    if (phaser["meta"]["size"]["w"], phaser["meta"]["size"]["h"]) != (w, h):
        problems.append(f"phaser meta.size {phaser['meta']['size']} != png {w}x{h}")
    rects = []
    for name, f in frames.items():
        r = f["frame"]
        if r["x"] < 0 or r["y"] < 0 or r["x"] + r["w"] > w or r["y"] + r["h"] > h:
            problems.append(f"{name}: rect {r} outside the {w}x{h} texture")
        rects.append((name, r["x"], r["y"], r["x"] + r["w"], r["y"] + r["h"]))
    for i, (n1, ax0, ay0, ax1, ay1) in enumerate(rects):
        for n2, bx0, by0, bx1, by1 in rects[i + 1:]:
            if ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1:
                problems.append(f"{n1} overlaps {n2}")
    if len(frames) != len(generic["frames"]) or {f["name"] for f in generic["frames"]} != set(frames):
        problems.append("generic.json frames differ from the Phaser frames")
    for key, anim in animations.items():
        missing = [n for n in anim["frames"] if n not in frames]
        if missing:
            problems.append(f"animation {key} references unknown frames {missing}")
    for row in meta["actions"]:
        want = plan["actions"][row["name"]]["frames"]
        key = f"{row['name']}_{row['direction']}" if row["direction"] else row["name"]
        got = len(animations.get(key, {}).get("frames", []))
        if not (row["frames"] == got == want):
            problems.append(f"{row['unit']}: plan frames={want}, atlas={row['frames']}, animation={got}")
    if len(animations) != len(meta["actions"]):
        problems.append("animations.json and meta.actions differ in length")
    problems += [f"meta.json missing {k}" for k in META_KEYS if k not in meta]
    problems += [f"generic.json missing {k}" for k in GENERIC_KEYS if k not in generic]
    if problems:
        raise ForgeError("export_validation_failed", "; ".join(problems), extra={"problems": problems})
