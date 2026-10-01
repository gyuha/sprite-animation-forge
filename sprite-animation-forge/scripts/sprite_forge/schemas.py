"""Access to ``sprite-animation-forge/schemas/*.schema.json`` (docs/08 section 5).

``load_schema(name)`` / ``validate(name, doc)`` (raises ``jsonschema.ValidationError``);
``name`` is e.g. ``"animation-plan"``. ``empty_character_profile()`` is the all-unknown profile
(docs/08 5.2: unknown values are empty strings / arrays).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import jsonschema

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"


@lru_cache(maxsize=None)
def load_schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / f"{name}.schema.json").read_text(encoding="utf-8"))


def validate(name: str, doc) -> None:
    jsonschema.Draft202012Validator(load_schema(name)).validate(doc)


def empty_character_profile() -> dict:
    text = ("silhouette", "body_ratio", "head_ratio", "hair", "face", "eyes", "clothing",
            "weapon", "outline_style", "shading_style", "camera_angle", "orientation")
    identity = {k: "" for k in text}
    identity.update(primary_colors=[], secondary_colors=[], accessories=[])
    return {"schema_version": 1, "source": "empty", "edited_by_user": False, "identity": identity}
