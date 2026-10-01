"""Animation planner (docs/02 sections 4-8): presets, grid, bundles, overrides, directions.

Public API
----------
``grid_for(frames) -> "RxC"``                      docs/02 5.2 table (frames 2-16).
``resolve_actions(actions_csv, bundle) -> list[str]``
``parse_overrides(items) -> {action: {key: raw}}`` for ``--set <action>.<key>=<value>``.
``build_plan(character, actions, *, view, asset_type, art_style, has_reference, ...) -> dict``
    The ``animation-plan.json`` dict (validated against the schema).
``estimated_seconds(plan)``      generated units x 90 s (mirror-derived units are free).
``units(plan) -> [{unit, action, direction, mirrored}]`` in generation order (down, right, up, left).
``resolve_unit(plan, action, direction) -> (unit_path, direction, mirrored)``  CLI direction rules.
``process_params(plan, action) -> ProcessParams``
``plan_path(char_dir)``, ``load_plan(char_dir)``, ``unit_dir(char_dir, unit)``

Notes on ambiguous spots
------------------------
* Non-preset action names ("custom" actions, including ``kind=fx``) require
  ``--set <action>.motion=...`` (docs/08 5.1: ``motion`` is mandatory for custom actions).
  Defaults for them are not in the docs: body = 4 frames / 2x2 / no loop / 10 fps / feet-fit-mass,
  fx = 4 frames / 2x2 / no loop / 12 fps with the docs/02 6 fx row. ``qc_profile`` is written
  into the plan for those (the name alone cannot resolve it): ``action`` for body, ``fx`` for fx.
* docs/02 4 says directions default to ``[facing]`` for views other than side/topdown, but
  ``facing`` values like ``camera`` are not direction enum members. We use front -> ``[down]``,
  rear -> ``[up]``, 3/4 -> ``[right]``.
* Unit path uses ``<action>/<direction>`` whenever the PLAN-level ``directions`` has 2+ entries,
  even for an action whose own ``directions`` is narrower (docs/08 4).
* ``--set <action>.frames=N`` without an explicit grid recomputes the grid (docs/02 5.2);
  an explicit grid always wins (it must hold the frames).
* Mid-project mirror switching (docs/02 8.1 "중간에 바꾸기") is not implemented here.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import jsonschema

from . import schemas
from .errors import EXIT_PRECONDITION, ForgeError
from .fsutil import atomic_write_json
from .pipeline.chroma import KEY_GREEN, resolve_key_color
from .pipeline.process import ProcessParams

# docs/02 5.1 (frames, loop, fps) and 6 (anchor, scale_strategy, x_anchor); components is largest.
PRESETS = {
    "idle": (4, True, 6, "feet", "fit", "mass"),
    "walk": (6, True, 10, "feet", "fit", "mass"),
    "run": (6, True, 12, "feet", "fit", "mass"),
    "attack": (6, False, 12, "feet", "preserve", "feet"),
    "shoot": (4, False, 12, "feet", "preserve", "feet"),
    "cast": (6, False, 10, "feet", "preserve", "feet"),
    "jump": (4, False, 10, "feet", "fit", "mass"),
    "fall": (2, True, 8, "feet", "fit", "mass"),
    "hurt": (4, False, 10, "feet", "fit", "mass"),
    "death": (8, False, 8, "bottom", "preserve", "feet"),
}
BUNDLES = {
    "side-action": ["idle", "walk", "run", "jump", "fall", "attack", "hurt", "death"],
    "side-basic": ["idle", "walk", "run", "attack"],
    "topdown-rpg": ["idle", "walk", "attack", "hurt", "death"],
    "npc": ["idle", "walk"],
}
BUNDLE_VIEW = {"topdown-rpg": "topdown"}

GRID_BY_FRAMES = {
    2: "1x2", 3: "1x3", 4: "2x2", 5: "2x3", 6: "2x3", 7: "2x4", 8: "2x4",
    9: "3x3", 10: "3x4", 11: "3x4", 12: "3x4", 13: "4x4", 14: "4x4", 15: "4x4", 16: "4x4",
}
FACING_BY_VIEW = {"side": "right", "topdown": "down", "3/4": "down-right", "front": "camera", "rear": "away"}
DIRECTIONS_BY_VIEW = {
    "side": ["right"], "topdown": ["down", "up", "right", "left"],
    "3/4": ["right"], "front": ["down"], "rear": ["up"],
}
GEN_ORDER = ("down", "right", "up", "left")
SECONDS_PER_CALL = 90
ASYMMETRY_WORDS = re.compile(r"\b(left|right|one[- ]sided|asymmetric\w*)\b", re.I)

OVERRIDE_KEYS = {
    "kind": "str", "frames": "int", "grid": "str", "loop": "bool", "fps": "int", "anchor": "str",
    "x_anchor": "str", "scale_strategy": "str", "components": "str", "qc_profile": "str",
    "motion": "str", "poses": "pipes", "directions": "csv", "method": "str",
}
# generation method per action (.forge/CONTEXT.md "생성 방식"): grid = one sheet per call; breathe = one still +
# deterministic breathing; video = generated clip converted to sprites (needs a connected video provider)
METHODS = ("grid", "breathe", "video")
BREATHE_FRAMES = 6
MANY_FRAMES = 8  # grid actions with this many frames or more get a `frames_many` warning in plan.assumptions


def video_method_available() -> bool:
    """True once a video provider is connected (docs/13-video-api-setup.md)."""
    from .providers.video_factory import make_video_provider
    return bool(make_video_provider().check()["configured"])


def grid_for(frames: int) -> str:
    if frames not in GRID_BY_FRAMES:
        raise ForgeError("invalid_params", f"frames={frames} out of range 2-16")
    return GRID_BY_FRAMES[frames]


def resolve_actions(actions_csv: str | None, bundle: str | None) -> list[str]:
    if actions_csv and bundle:
        raise ForgeError("invalid_params", "use either --actions or --bundle, not both")
    if bundle:
        if bundle not in BUNDLES:
            raise ForgeError("invalid_params", f"unknown bundle {bundle!r}; choose from {sorted(BUNDLES)}")
        return list(BUNDLES[bundle])
    names = [a.strip() for a in (actions_csv or "").split(",") if a.strip()]
    if not names:
        raise ForgeError("invalid_params", "give --actions a,b,c or --bundle <name>")
    if len(set(names)) != len(names):
        raise ForgeError("invalid_params", "duplicate action names")
    return names


def _coerce(key: str, raw: str):
    kind = OVERRIDE_KEYS[key]
    try:
        if kind == "int":
            return int(raw)
        if kind == "bool":
            if raw.lower() in ("true", "yes", "1"):
                return True
            if raw.lower() in ("false", "no", "0"):
                return False
            raise ValueError(raw)
        if kind == "csv":
            return [x.strip() for x in raw.split(",") if x.strip()]
        if kind == "pipes":
            return [x.strip() for x in raw.split("|") if x.strip()]
    except ValueError:
        raise ForgeError("invalid_override", f"{key}={raw!r} is not a valid {kind}") from None
    return raw


def parse_overrides(items) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for item in items or []:
        m = re.fullmatch(r"([a-z][a-z0-9_]*)\.([a-z_]+)=(.*)", item, re.S)
        if not m:
            raise ForgeError("invalid_override", f"--set expects <action>.<key>=<value>, got {item!r}")
        action, key, raw = m.groups()
        if key not in OVERRIDE_KEYS:
            raise ForgeError("invalid_override", f"unknown key {key!r}; choose from {sorted(OVERRIDE_KEYS)}")
        value = _coerce(key, raw)
        if key == "method" and value not in METHODS:
            raise ForgeError("invalid_override", f"method={raw!r}; choose from {list(METHODS)}")
        out.setdefault(action, {})[key] = value
    return out


def _action_defaults(name: str, kind: str, has_override_motion: bool) -> dict:
    if kind == "fx":
        base = {"frames": 4, "loop": False, "fps": 12, "anchor": "center", "scale_strategy": "fit",
                "x_anchor": "bbox", "components": "all", "qc_profile": "fx"}
    elif name in PRESETS:
        frames, loop, fps, anchor, scale, x_anchor = PRESETS[name]
        base = {"frames": frames, "loop": loop, "fps": fps, "anchor": anchor,
                "scale_strategy": scale, "x_anchor": x_anchor, "components": "largest"}
    else:
        base = {"frames": 4, "loop": False, "fps": 10, "anchor": "feet", "scale_strategy": "fit",
                "x_anchor": "mass", "components": "largest", "qc_profile": "action"}
    if name not in PRESETS and not has_override_motion:
        raise ForgeError("invalid_params", f"custom action {name!r} needs --set {name}.motion=<description>")
    return base


def _build_action(name: str, ov: dict) -> dict:
    kind = ov.get("kind") or "body"
    base = _action_defaults(name, kind, "motion" in ov)
    action = {}
    if kind == "fx" or "kind" in ov:
        action["kind"] = kind
    action.update(base)
    action["grid"] = grid_for(action["frames"])
    action.update({k: v for k, v in ov.items() if k != "kind"})
    if "frames" in ov and "grid" not in ov:
        action["grid"] = grid_for(action["frames"])
    method = action.setdefault("method", "grid")
    if method == "video" and not video_method_available():
        raise ForgeError("method_unavailable", f"{name}: method=video needs a connected video provider "
                         "(see docs/13-video-api-setup.md)", EXIT_PRECONDITION)
    if method == "breathe":
        if kind == "fx":
            raise ForgeError("invalid_params", f"{name}: method=breathe is only for body actions")
        action["grid"] = "1x1"  # generation is one still pose; `frames` is the number of output frames
        if "frames" not in ov:
            action["frames"] = BREATHE_FRAMES
    # key order: stable, readable
    order = ["kind", "method", "frames", "grid", "loop", "fps", "anchor", "scale_strategy", "x_anchor",
             "components", "qc_profile", "motion", "poses", "directions"]
    action = {k: action[k] for k in order if k in action}
    r, c = (int(x) for x in action["grid"].split("x"))
    if (r * c < action["frames"] and method != "breathe") or r < 1 or c < 1:
        raise ForgeError("invalid_params", f"{name}: grid {action['grid']} cannot hold {action['frames']} frames")
    return action


def _parse_cell(cell) -> tuple[int, int]:
    if isinstance(cell, str):
        m = re.fullmatch(r"(\d+)[xX](\d+)", cell)
        if not m:
            raise ForgeError("invalid_params", f"--cell expects WxH, got {cell!r}")
        return int(m.group(1)), int(m.group(2))
    return cell


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    return (int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16))


def _profile_colors(profile: dict | None) -> list[tuple[int, int, int]]:
    ident = (profile or {}).get("identity", {})
    return [_hex_to_rgb(c) for c in ident.get("primary_colors", []) + ident.get("secondary_colors", [])
            if re.fullmatch(r"#[0-9A-Fa-f]{6}", c)]


def build_plan(
    character: str,
    actions: list[str],
    *,
    view: str = "side",
    asset_type: str = "character",
    art_style: str = "auto",
    has_reference: bool = False,
    facing: str | None = None,
    directions: list[str] | None = None,
    mirror: bool | None = None,
    cell="128x128",
    overrides: dict | None = None,
    profile: dict | None = None,
    engine: str = "phaser",
    assumptions: list[str] | None = None,
) -> dict:
    overrides = overrides or {}
    unknown = sorted(set(overrides) - set(actions))
    if unknown:
        raise ForgeError("unknown_action", f"--set refers to actions not in the plan: {unknown}")
    if view not in FACING_BY_VIEW:
        raise ForgeError("invalid_params", f"unknown view {view!r}")
    notes = list(assumptions or [])
    notes.append(f"view={view}")

    if art_style == "auto":
        art_style = "project_native" if has_reference else "clean_hd"
        notes.append(f"art_style={art_style}" + (" (reference 이미지 제공)" if has_reference else " (기본값)"))

    dirs = list(directions) if directions else list(DIRECTIONS_BY_VIEW[view])
    facing_explicit = facing is not None
    facing = facing or FACING_BY_VIEW[view]
    if not facing_explicit and facing in ("right", "left", "up", "down") and facing not in dirs:
        facing = dirs[0]
    if facing_explicit and facing in ("right", "left", "up", "down") and facing not in dirs:
        raise ForgeError("invalid_params", f"facing={facing} is not in directions {dirs}")

    can_mirror = "left" in dirs and "right" in dirs
    if mirror is True and not can_mirror:
        raise ForgeError("invalid_params", "--mirror needs both left and right in directions")
    use_mirror = can_mirror and view == "topdown" if mirror is None else bool(mirror)
    mirror_map = {"left": "right"} if use_mirror else {}

    key_rgb, key_warnings = resolve_key_color(_profile_colors(profile))
    key_color = "#{:02X}{:02X}{:02X}".format(*key_rgb)
    if key_rgb == tuple(KEY_GREEN):
        notes.append("key_color=#00FF00 (캐릭터 색이 #FF00FF와 충돌)")
    notes.extend(f"key_color 경고: {w}" for w in key_warnings)

    if use_mirror and profile:
        ident = profile.get("identity", {})
        text = " ".join([ident.get("weapon", ""), ident.get("clothing", "")] + list(ident.get("accessories", [])))
        if ASYMMETRY_WORDS.search(text):
            notes.append("비대칭일 수 있습니다. 좌측면을 별도 생성할까요? (--no-mirror)")

    built = {name: _build_action(name, overrides.get(name, {})) for name in actions}
    for name, act in built.items():
        sub = act.get("directions")
        if sub is None:
            continue
        if not set(sub) <= set(dirs):
            raise ForgeError("invalid_params", f"{name}: directions {sub} not a subset of {dirs}")
    if use_mirror:
        for name, act in built.items():
            eff = act.get("directions", dirs)
            if "left" in eff and "right" not in eff:
                raise ForgeError("invalid_params", f"{name}: mirror left<-right needs right in its directions")

    cw, ch = _parse_cell(cell)
    plan = {
        "schema_version": 1,
        "character": character,
        "asset_type": asset_type,
        "view": view,
        "facing": facing,
        "directions": dirs,
        "mirror": mirror_map,
        "art_style": art_style,
        "cell": {"w": cw, "h": ch},
        "margin": {"top": 8, "side": 8, "bottom": 10},
        "key_color": key_color,
        "engine": engine,
        "actions": built,
        "order": list(actions),
        "assumptions": notes,
    }
    for name, act in built.items():
        if act.get("method", "grid") != "breathe" and act["frames"] >= MANY_FRAMES:
            notes.append(f"frames_many: {name}: {act['frames']}프레임 - {MANY_FRAMES}프레임 이상은 칸 붕괴·중복 몸·빈 칸이 늘어납니다 (4~6프레임 권장)")
    try:
        schemas.validate("animation-plan", plan)
    except jsonschema.ValidationError as exc:
        where = "/".join(str(p) for p in exc.absolute_path) or "plan"
        raise ForgeError("invalid_params", f"{where}: {exc.message}") from None
    return plan


def units(plan: dict) -> list[dict]:
    dirs = plan["directions"]
    mirror = plan.get("mirror", {})
    out = []
    for action in plan["order"]:
        eff = plan["actions"][action].get("directions", dirs)
        for d in sorted(eff, key=GEN_ORDER.index):
            mirrored = d == "left" and mirror.get("left") == "right" and "right" in eff
            out.append({"unit": f"{action}/{d}" if len(dirs) > 1 else action,
                        "action": action, "direction": d, "mirrored": mirrored})
    return out


def estimated_seconds(plan: dict) -> int:
    return sum(1 for u in units(plan) if not u["mirrored"]) * SECONDS_PER_CALL


def resolve_unit(plan: dict, action: str, direction: str | None) -> tuple[str, str, bool]:
    """docs/02 8.1 CLI rules. Returns ``(unit_path, direction, mirrored)``."""
    if action not in plan["actions"]:
        raise ForgeError("unknown_action", f"{action!r} is not in the plan (actions: {plan['order']})")
    dirs = plan["directions"]
    eff = plan["actions"][action].get("directions", dirs)
    if len(dirs) == 1:
        if direction not in (None, dirs[0]):
            raise ForgeError("invalid_direction", f"plan has a single direction {dirs[0]!r}, got {direction!r}")
        return action, dirs[0], False
    if direction is None:
        raise ForgeError("direction_required", f"--direction is required ({', '.join(eff)})")
    if direction not in eff:
        raise ForgeError("invalid_direction", f"{action} has directions {eff}, got {direction!r}")
    if direction == "left" and plan.get("mirror", {}).get("left") == "right" and "right" in eff:
        raise ForgeError("mirrored_direction", f"{action}/left is derived by mirroring right; use --direction right")
    return f"{action}/{direction}", direction, False


def is_airborne(act: dict, action: str) -> bool:
    """jump/fall (QC profile airborne): the raw vertical travel is part of the animation."""
    from .qc import PROFILE_BY_ACTION  # local import: qc imports the pipeline, plan must stay light
    return (act.get("qc_profile") or PROFILE_BY_ACTION.get(action)) == "airborne"


def process_params(plan: dict, action: str) -> ProcessParams:
    act = plan["actions"][action]
    rows, cols = (int(x) for x in act["grid"].split("x"))
    return ProcessParams(
        rows=rows, cols=cols, frames=act["frames"],
        cell_w=plan["cell"]["w"], cell_h=plan["cell"]["h"],
        margin_top=plan["margin"]["top"], margin_side=plan["margin"]["side"],
        margin_bottom=plan["margin"]["bottom"],
        key_color=_hex_to_rgb(plan["key_color"]),
        components=act["components"], anchor=act["anchor"], x_anchor=act["x_anchor"],
        scale_strategy=act["scale_strategy"], art_style=plan["art_style"],
        preserve_vertical=is_airborne(act, action),
    )


def plan_path(char_dir) -> Path:
    return Path(char_dir) / "animation-plan.json"


def load_plan(char_dir) -> dict:
    path = plan_path(char_dir)
    if not path.exists():
        raise ForgeError("no_plan", f"{path} not found; run plan first", EXIT_PRECONDITION)
    return json.loads(path.read_text(encoding="utf-8"))


def save_plan(char_dir, plan: dict) -> None:
    atomic_write_json(plan_path(char_dir), plan)


def unit_dir(char_dir, unit: str) -> Path:
    return Path(char_dir) / unit
