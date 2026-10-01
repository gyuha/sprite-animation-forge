"""Plan GET / PUT / POST (docs/10 5.1).

Notes on ambiguous spots
------------------------
* All three return ``{plan, estimated_seconds, units}`` (``units`` = Core ``plan.units``: unit path, action,
  direction, mirrored) so the UI need not re-derive mirror logic. Plan POST answers 200.
* POST calls the CLI ``plan`` handler (``cli.cmd_plan``) with the same fields; like the CLI it overwrites an
  existing plan (docs say "최초 생성" but do not forbid re-creation).
* PUT body is ``{"plan": {...}}`` (a whole plan). Recalculation (docs/10 "grid·키 색 재계산"): an action whose
  ``frames`` changed while its ``grid`` is unchanged from the stored plan gets ``grid_for(frames)``; ``key_color``
  is always recomputed from the identity profile palette (as ``build_plan`` does). Then: schema check (422),
  ``character`` must match the URL, ``order`` must list exactly the actions, grid must hold the frames,
  per-action ``directions`` must be a subset of the plan's, and ``mirror.left`` needs ``left`` + ``right``
  (400 ``invalid_param``). Mid-project mirror/direction switching of existing attempts is NOT handled (Core
  does not implement it either); changing the direction count renames unit paths for new attempts only.
"""

from __future__ import annotations

import copy
from types import SimpleNamespace
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel

from sprite_forge import cli, identity
from sprite_forge import plan as pl
from sprite_forge.errors import ForgeError
from sprite_forge.pipeline.chroma import resolve_key_color

from ..deps import Direction, load_cd, load_cd_plan, root_of, validate_or_422

router = APIRouter()


class UnitInfo(BaseModel):
    unit: str
    action: str
    direction: str
    mirrored: bool


class PlanResponse(BaseModel):
    plan: dict
    estimated_seconds: int
    units: list[UnitInfo]


class PlanCreate(BaseModel):
    actions: list[str] | None = None
    bundle: str | None = None
    set: list[str] = []  # "<action>.<key>=<value>" as the CLI --set
    cell: str = "128x128"
    view: Literal[cli.VIEWS] | None = None
    facing: str | None = None
    directions: list[Direction] | None = None
    mirror: bool | None = None


class PlanUpdate(BaseModel):
    plan: dict


def _response(plan: dict) -> PlanResponse:
    return PlanResponse(plan=plan, estimated_seconds=pl.estimated_seconds(plan), units=pl.units(plan))


@router.get("/api/characters/{cid}/plan")
def get_plan(request: Request, cid: str) -> PlanResponse:
    return _response(load_cd_plan(request, cid)[1])


@router.post("/api/characters/{cid}/plan")
def create_plan(request: Request, cid: str, body: PlanCreate) -> PlanResponse:
    load_cd(request, cid)
    args = SimpleNamespace(
        cid=cid, root=str(root_of(request)), actions=",".join(body.actions) if body.actions else None,
        bundle=body.bundle, sets=body.set, cell=body.cell, view=body.view, facing=body.facing,
        directions=",".join(body.directions) if body.directions else None, mirror=body.mirror)
    return _response(cli.cmd_plan(args)["plan"])


@router.put("/api/characters/{cid}/plan")
def put_plan(request: Request, cid: str, body: PlanUpdate) -> PlanResponse:
    cd = load_cd(request, cid)
    plan = copy.deepcopy(body.plan)
    validate_or_422("animation-plan", plan)
    try:
        old = pl.load_plan(cd)["actions"]
    except ForgeError:
        old = {}
    for name, act in plan["actions"].items():
        prev = old.get(name)
        if prev and act["frames"] != prev["frames"] and act["grid"] == prev["grid"]:
            act["grid"] = pl.grid_for(act["frames"])
    key_rgb, _ = resolve_key_color(pl._profile_colors(identity.load_profile(cd)))
    plan["key_color"] = "#{:02X}{:02X}{:02X}".format(*key_rgb)
    validate_or_422("animation-plan", plan)
    _check_invariants(cid, plan)
    pl.save_plan(cd, plan)
    return _response(plan)


def _check_invariants(cid: str, plan: dict) -> None:
    def bad(msg):
        return ForgeError("invalid_params", msg)

    if plan["character"] != cid:
        raise bad(f"plan.character {plan['character']!r} does not match {cid!r}")
    if sorted(plan["order"]) != sorted(plan["actions"]) or len(set(plan["order"])) != len(plan["order"]):
        raise bad("order must list every action exactly once")
    dirs = plan["directions"]
    for name, act in plan["actions"].items():
        r, c = (int(x) for x in act["grid"].split("x"))
        if r * c < act["frames"] and act.get("method", "grid") != "breathe":
            raise bad(f"{name}: grid {act['grid']} cannot hold {act['frames']} frames")
        if not set(act.get("directions", dirs)) <= set(dirs):
            raise bad(f"{name}: directions not a subset of {dirs}")
        if plan.get("mirror") and "left" in act.get("directions", dirs) and "right" not in act.get("directions", dirs):
            raise bad(f"{name}: mirror left<-right needs right in its directions")
    if plan.get("mirror") and not {"left", "right"} <= set(dirs):
        raise bad("mirror needs both left and right in directions")
