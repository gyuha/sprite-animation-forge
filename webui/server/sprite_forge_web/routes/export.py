"""Export and ZIP download (docs/10 5.1, docs/07 11).

Notes on ambiguous spots
------------------------
* POST returns Core ``export_character``'s ``{files, warnings}`` (no accepted unit -> 412 ``precondition_failed``,
  ``detail.reason == "nothing_to_export"``).
* ``export.zip`` holds ``atlas/*``, ``animations.json`` and ``preview/*`` (docs/07 11: the minimal Phaser files,
  ``meta.json`` and previews; no attempts, no qc-report/manifest), flat (no top-level directory), served as
  ``<cid>.zip``. It zips what the last export wrote; no export yet -> 412 ``precondition_failed``.
"""

from __future__ import annotations

import io
import zipfile

from fastapi import APIRouter, Request
from fastapi.responses import Response
from pydantic import BaseModel

from sprite_forge.errors import EXIT_PRECONDITION, ForgeError
from sprite_forge.export import export_character

from ..deps import load_cd

router = APIRouter()


class ExportResponse(BaseModel):
    files: list[str]
    warnings: list[str]


@router.post("/api/characters/{cid}/export")
def export(request: Request, cid: str) -> ExportResponse:
    return ExportResponse(**export_character(load_cd(request, cid)))


@router.get("/api/characters/{cid}/export.zip", response_class=Response,
            responses={200: {"content": {"application/zip": {}}}})
def export_zip(request: Request, cid: str) -> Response:
    cd = load_cd(request, cid)
    members = [p for d in ("atlas", "preview") for p in sorted((cd / d).glob("*")) if p.is_file()]
    if (cd / "animations.json").is_file():
        members.append(cd / "animations.json")
    if not members:
        raise ForgeError("not_exported", "run export first", EXIT_PRECONDITION)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in members:
            z.write(p, p.relative_to(cd).as_posix())
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{cid}.zip"'})
