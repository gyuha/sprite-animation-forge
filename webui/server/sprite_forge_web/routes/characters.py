"""Characters: list / create / detail (docs/10 §5.1-5.2).

Notes on ambiguous spots
------------------------
* ``next_step`` (docs/10 §5.2 shows only ``"reference"``): reference -> plan -> generate -> export, derived
  from ``workflow.status_report`` (``export`` once every non-pending unit set is accepted/mirrored).
* Card fields beyond ``id``/``created_at``/``next_step`` are not specified; see ``_card``.
* Detail response: ``{character: {id, next_step}, manifest, status}`` with ``status`` = ``status_report``.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel

from sprite_forge import manifest as mf
from sprite_forge import workflow
from sprite_forge.cli import CID_RE, ART_STYLES, ASSET_TYPES, VIEWS

from ..deps import char_dir, root_of

router = APIRouter()


class CharacterCreate(BaseModel):
    id: str
    view: Literal[VIEWS] = "side"
    art_style: Literal[ART_STYLES] = "auto"
    asset_type: Literal[ASSET_TYPES] = "character"


def _next_step(status: dict) -> str:
    if not status["has_reference"]:
        return "reference"
    if not status["has_plan"]:
        return "plan"
    done = all(u["state"] in ("accepted", "mirrored") for u in status["units"])
    return "export" if status["units"] and done else "generate"


def _card(cd, m: dict) -> dict:
    status = workflow.status_report(cd)
    units = status["units"]
    return {
        "id": m["character"], "created_at": m["created_at"], "updated_at": m["updated_at"],
        "settings": m.get("settings", {}), "has_reference": status["has_reference"],
        "has_plan": status["has_plan"], "units_total": len(units),
        "units_accepted": sum(u["state"] in ("accepted", "mirrored") for u in units),
        "next_step": _next_step(status),
    }


@router.get("/api/characters")
def list_characters(request: Request) -> dict:
    root = root_of(request)
    cards = []
    for cd in sorted(root.iterdir()) if root.is_dir() else []:
        if CID_RE.match(cd.name) and (cd / "manifest.json").is_file():
            cards.append(_card(cd, mf.load(cd)))
    return {"characters": cards}


@router.post("/api/characters", status_code=201)
def create_character(request: Request, body: CharacterCreate) -> dict:
    cd = char_dir(request, body.id)
    m = mf.create(cd, body.id, {"view": body.view, "art_style": body.art_style, "asset_type": body.asset_type})
    return {"character": {"id": body.id, "created_at": m["created_at"], "next_step": "reference"}}


@router.get("/api/characters/{cid}")
def get_character(request: Request, cid: str) -> dict:
    cd = char_dir(request, cid)
    m = mf.load(cd)
    status = workflow.status_report(cd)
    return {"character": {"id": cid, "next_step": _next_step(status)}, "manifest": m, "status": status}
