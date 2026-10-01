"""Shared helpers for routers: app state access and character-id validation (same rule as CLI ``init``)."""

from __future__ import annotations

from pathlib import Path

from fastapi import Request

from sprite_forge.cli import CID_RE
from sprite_forge.errors import ForgeError


def root_of(request: Request) -> Path:
    return request.app.state.root


def char_dir(request: Request, cid: str) -> Path:
    if not CID_RE.match(cid):
        raise ForgeError("invalid_character_id", f"{cid!r} must match {CID_RE.pattern}")
    return root_of(request) / cid
