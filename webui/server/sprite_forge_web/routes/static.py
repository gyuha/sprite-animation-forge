"""Serves the built SPA (``webui/web/dist``) at ``/`` with index.html fallback for client-side routes.

``/api/*`` and ``/files/*`` never fall back to index.html (they 404 in the error format)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

from ..errors import ApiError


def static_router(static_dir: Path) -> APIRouter:
    router = APIRouter()
    base = static_dir.resolve()

    @router.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        if full_path.split("/")[0] in ("api", "files"):
            raise ApiError(404, "not_found", "not found")
        if full_path and "\x00" not in full_path:
            target = (base / full_path).resolve()
            if target.is_relative_to(base) and target.is_file():
                return FileResponse(target)
        return FileResponse(base / "index.html")

    return router
