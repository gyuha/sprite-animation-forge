"""Reference upload and candidate selection (docs/10 5.1).

Notes on ambiguous spots
------------------------
* docs/10 shows no response body for these; both return ``{reference, bg_removed, selected_attempt, files}``
  where ``files`` are ``/files`` URLs (``source``, ``character``, ``keyed``) and ``selected_attempt`` is null
  for an upload.
* Upload checks (docs/10 4): decode failure or a format other than PNG/JPEG/WebP -> 400 ``invalid_image``
  (``detail.reason == "unsupported_format"`` for the latter), > 20MB -> 413 ``file_too_large``, an existing
  ``reference/source.*`` -> 409 ``already_exists`` (Core: the source is immutable). Multipart field: ``file``.
"""

from __future__ import annotations

from fastapi import APIRouter, File, Request, UploadFile
from pydantic import BaseModel

from sprite_forge import generation, workflow

from ..deps import file_url, load_cd, uploaded_image

router = APIRouter()


class ReferenceFiles(BaseModel):
    source: str | None
    character: str | None
    keyed: str | None


class ReferenceResponse(BaseModel):
    reference: str
    bg_removed: bool
    selected_attempt: str | None = None
    files: ReferenceFiles


def _response(cd, cid: str, out: dict) -> ReferenceResponse:
    files = ReferenceFiles(source=file_url(cd, cid, out["reference"]),
                           character=file_url(cd, cid, "reference/character.png"),
                           keyed=file_url(cd, cid, "reference/character-keyed.png"))
    return ReferenceResponse(reference=out["reference"], bg_removed=out["bg_removed"],
                             selected_attempt=out.get("selected_attempt"), files=files)


@router.post("/api/characters/{cid}/reference")
def upload_reference(request: Request, cid: str, file: UploadFile = File(...)) -> ReferenceResponse:
    cd = load_cd(request, cid)
    with uploaded_image(file) as path:
        out = workflow.import_reference(cd, path)
    return _response(cd, cid, out)


@router.post("/api/characters/{cid}/reference/attempts/{aid}/select")
def select_reference(request: Request, cid: str, aid: str) -> ReferenceResponse:
    cd = load_cd(request, cid)
    return _response(cd, cid, generation.select_reference(cd, aid))
