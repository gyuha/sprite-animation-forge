"""Shared helpers for routers: app state access and character-id validation (same rule as CLI ``init``)."""

from __future__ import annotations

import io
import json
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Literal

from fastapi import Request, UploadFile
from jsonschema import Draft202012Validator
from PIL import Image

from sprite_forge import manifest as mf
from sprite_forge import schemas
from sprite_forge.cli import CID_RE
from sprite_forge.errors import ForgeError
from sprite_forge.fsutil import sha256_file
from sprite_forge.plan import load_plan, resolve_unit
from sprite_forge.workflow import SOURCE_EXT

from .errors import ApiError


def root_of(request: Request) -> Path:
    return request.app.state.root


def char_dir(request: Request, cid: str) -> Path:
    if not CID_RE.match(cid):
        raise ForgeError("invalid_character_id", f"{cid!r} must match {CID_RE.pattern}")
    return root_of(request) / cid


# ---- helpers for the synchronous endpoints (reference / identity / plan / actions / export) ------------------

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
Direction = Literal["down", "up", "right", "left"]


def load_cd(request: Request, cid: str) -> Path:
    """Character directory of an existing character (unknown -> ForgeError no_character -> 404)."""
    cd = char_dir(request, cid)
    mf.load(cd)
    return cd


def load_cd_plan(request: Request, cid: str) -> tuple[Path, dict]:
    cd = load_cd(request, cid)
    return cd, load_plan(cd)  # no plan -> 412 precondition_failed


def resolve(plan: dict, action: str, direction: str | None, allow_mirrored: bool = False) -> tuple[str, str | None, bool]:
    """``(unit, direction, mirrored)``. The ``direction`` query is ignored for single-direction plans and
    required otherwise (docs/10 5.1). A mirror-derived ``left`` raises ``mirrored_direction`` (409) unless
    ``allow_mirrored`` (read-only endpoints)."""
    if len(plan["directions"]) == 1:
        direction = None
    try:
        unit, d, _ = resolve_unit(plan, action, direction)
    except ForgeError as exc:
        if allow_mirrored and exc.code == "mirrored_direction":
            return f"{action}/{direction}", direction, True
        raise
    return unit, d, False


def file_url(cd: Path, cid: str, rel: str) -> str | None:
    """``/files/<cid>/<rel>?v=<sha256[:12]>`` (cache-busting hash), or None when the file does not exist."""
    path = cd / rel
    return f"/files/{cid}/{rel}?v={sha256_file(path)[:12]}" if path.is_file() else None


def read_json(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def validate_or_422(name: str, doc) -> None:
    errs = sorted(Draft202012Validator(schemas.load_schema(name)).iter_errors(doc), key=lambda e: list(e.absolute_path))
    if errs:
        detail = {"errors": [{"loc": list(e.absolute_path), "msg": e.message} for e in errs]}
        raise ApiError(422, "validation_error", f"{name} schema violation", detail)


@contextmanager
def uploaded_image(file: UploadFile):
    """Validate an uploaded image (<=20MB, decodable, PNG/JPEG/WebP) and yield a temp path with a matching suffix."""
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise ApiError(413, "file_too_large", f"upload exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)}MB")
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as exc:
        raise ApiError(400, "invalid_image", f"cannot decode image: {type(exc).__name__}") from None
    if img.format not in SOURCE_EXT:
        raise ApiError(400, "invalid_image", f"{img.format}: only PNG, JPEG and WebP are accepted",
                       {"reason": "unsupported_format", "format": img.format})
    stem = re.sub(r"[^A-Za-z0-9._-]", "_", Path(file.filename or "").stem)[:64] or "upload"
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"{stem}{SOURCE_EXT[img.format]}"
        path.write_bytes(data)
        yield path
