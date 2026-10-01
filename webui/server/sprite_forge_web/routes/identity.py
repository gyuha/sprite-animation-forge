"""Identity profile GET / PUT (docs/10 5.1).

Notes on ambiguous spots
------------------------
* GET without a profile file returns ``{"profile": null}`` (200), not an error.
* PUT body is ``{"identity": {...}}``. The server wraps it as the full ``character-profile`` document with
  ``edited_by_user: true`` and validates that document against the schema (violation -> 422
  ``validation_error`` with ``detail.errors``). ``source`` keeps its previous value, except ``empty``/missing
  becomes ``manual``.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from sprite_forge import identity
from sprite_forge.fsutil import atomic_write_json

from ..deps import load_cd, validate_or_422

router = APIRouter()


class IdentityResponse(BaseModel):
    profile: dict | None


class IdentityUpdate(BaseModel):
    identity: dict


@router.get("/api/characters/{cid}/identity")
def get_identity(request: Request, cid: str) -> IdentityResponse:
    return IdentityResponse(profile=identity.load_profile(load_cd(request, cid)))


@router.put("/api/characters/{cid}/identity")
def put_identity(request: Request, cid: str, body: IdentityUpdate) -> IdentityResponse:
    cd = load_cd(request, cid)
    previous = (identity.load_profile(cd) or {}).get("source", "empty")
    profile = {"schema_version": 1, "source": "manual" if previous == "empty" else previous,
               "edited_by_user": True, "identity": body.identity}
    validate_or_422("character-profile", profile)
    atomic_write_json(cd / "character-profile.json", profile)
    return IdentityResponse(profile=profile)
