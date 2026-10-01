"""manifest.json read-modify-write under an exclusive lock (docs/08 sections 5.7 and 7).

Public API
----------
``manifest_path(char_dir)``, ``load(char_dir) -> dict``
``create(char_dir, character, settings=None) -> dict``  fails with ``ForgeError("exists")``.
``update(char_dir, fn) -> dict``  lock ``manifest.lock`` -> load -> ``fn(manifest)`` (mutates in
    place, may return None) -> set ``updated_at`` -> atomic replace. Returns the new manifest.
``unit_entry(manifest, unit, kind="body") -> dict``  get or create ``actions[unit]``.

Notes on ambiguous spots
------------------------
* docs/08 5.7 has no place for the ``init`` options (view, art_style, asset_type); they are
  stored under an extra top-level ``settings`` object and ``plan`` reads them as defaults.
* ``reference`` is ``null`` until ``reference import`` runs.
* A mirror-derived unit is ``{"kind", "mirror_of"}`` only (no attempts); the mirrored attempt
  lives in ``<unit>/mirror.json``.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import __version__
from .errors import EXIT_PRECONDITION, ForgeError
from .fsutil import atomic_write_json, file_lock, utc_now

SCHEMA_VERSION = 1


def manifest_path(char_dir) -> Path:
    return Path(char_dir) / "manifest.json"


def load(char_dir) -> dict:
    path = manifest_path(char_dir)
    if not path.exists():
        raise ForgeError("no_character", f"{path} not found; run init first", EXIT_PRECONDITION)
    return json.loads(path.read_text(encoding="utf-8"))


def create(char_dir, character: str, settings: dict | None = None) -> dict:
    char_dir = Path(char_dir)
    with file_lock(char_dir / "manifest.lock"):
        if manifest_path(char_dir).exists():
            raise ForgeError("exists", f"character {character!r} already exists")
        now = utc_now()
        data = {
            "schema_version": SCHEMA_VERSION,
            "character": character,
            "created_at": now,
            "updated_at": now,
            "tool": {"name": "sprite-animation-forge", "version": __version__},
            "settings": settings or {},
            "reference": None,
            "assumptions": [],
            "actions": {},
            "exports": {},
            "usage": {"codex_calls": 0, "input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0},
        }
        atomic_write_json(manifest_path(char_dir), data)
        return data


def update(char_dir, fn) -> dict:
    char_dir = Path(char_dir)
    with file_lock(char_dir / "manifest.lock"):
        data = load(char_dir)
        fn(data)
        data["updated_at"] = utc_now()
        atomic_write_json(manifest_path(char_dir), data)
        return data


def unit_entry(manifest: dict, unit: str, kind: str = "body") -> dict:
    return manifest["actions"].setdefault(
        unit, {"kind": kind, "accepted_attempt": None, "forced": False, "attempts": {}}
    )
