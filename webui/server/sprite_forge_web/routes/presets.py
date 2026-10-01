"""``GET /api/presets``: data for the plan form, taken from ``sprite_forge.plan`` (docs/10 §5.1; no §5.2 shape given).

Shape: ``{frame_presets: {name: {frames, grid, loop, fps, anchor, scale_strategy, x_anchor, components}},
bundles: {name: {actions, view|null}}, grids: {frames: "RxC"}, views, asset_types, art_styles, directions}``.
"""

from __future__ import annotations

from fastapi import APIRouter

from sprite_forge import plan
from sprite_forge.cli import ART_STYLES, ASSET_TYPES, DIRECTIONS, VIEWS

router = APIRouter()


@router.get("/api/presets")
def presets() -> dict:
    frame_presets = {}
    for name in plan.PRESETS:
        d = plan._action_defaults(name, "body", False)
        frame_presets[name] = {**d, "grid": plan.grid_for(d["frames"])}
    return {
        "frame_presets": frame_presets,
        "bundles": {n: {"actions": a, "view": plan.BUNDLE_VIEW.get(n)} for n, a in plan.BUNDLES.items()},
        "grids": {str(k): v for k, v in plan.GRID_BY_FRAMES.items()},
        "views": list(VIEWS),
        "asset_types": list(ASSET_TYPES),
        "art_styles": list(ART_STYLES),
        "directions": list(DIRECTIONS),
    }
