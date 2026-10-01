"""Dump the FastAPI OpenAPI schema to webui/web/openapi.json (run from anywhere: paths are derived from this file)."""

import json
import sys
from pathlib import Path

WEB = Path(__file__).resolve().parents[1]
REPO = WEB.parents[1]
sys.path[:0] = [str(REPO / "webui" / "server"), str(REPO / "sprite-animation-forge" / "scripts")]

from sprite_forge_web.main import app  # noqa: E402

(WEB / "openapi.json").write_text(json.dumps(app.openapi(), indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
