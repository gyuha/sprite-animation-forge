"""``GET /files/{cid}/{path}`` (docs/10 §7): the only route exposing local files.

Everything outside ``<root>/<cid>/`` is 404: ``..`` segments, absolute paths, NUL bytes, and symlinks whose
target resolves outside (the character directory itself is also checked, so a symlinked ``<cid>`` is blocked).
Disallowed extensions are 404 as well (no existence oracle).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from sprite_forge.cli import CID_RE

from ..errors import ApiError
from ..deps import root_of

router = APIRouter()
ALLOWED_EXT = {".png", ".gif", ".json", ".txt", ".jsonl", ".mp4"}


def _not_found() -> ApiError:
    return ApiError(404, "not_found", "file not found")


def safe_file(root: Path, cid: str, rel: str) -> Path:
    if not CID_RE.match(cid) or not rel or "\x00" in rel or "\\" in rel or rel.startswith("/"):
        raise _not_found()
    if any(p == ".." for p in rel.split("/")):
        raise _not_found()
    base = root.resolve() / cid
    target = (base / rel).resolve()
    if not target.is_relative_to(base) or target.suffix.lower() not in ALLOWED_EXT or not target.is_file():
        raise _not_found()
    return target


@router.get("/files/{cid}/{path:path}")
def serve(request: Request, cid: str, path: str, v: str | None = None) -> FileResponse:
    target = safe_file(root_of(request), cid, path)
    cache = "public, max-age=31536000, immutable" if v else "no-cache"
    return FileResponse(target, headers={"Cache-Control": cache})
