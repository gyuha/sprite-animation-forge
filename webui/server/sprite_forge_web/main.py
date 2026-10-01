"""FastAPI app factory. ``from sprite_forge_web.main import app`` builds the default app (reads
``SPRITE_FORGE_ROOT`` only; no other side effects). Add a router: create ``routes/<name>.py`` with ``router``
and append it to ``ROUTERS``.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

from fastapi import FastAPI

from . import errors
from .routes import characters, files, health, presets
from .routes.static import static_router
from .security import HostGuardMiddleware

DEFAULT_STATIC_DIR = Path(__file__).resolve().parents[2] / "web" / "dist"
ROUTERS = [health.router, presets.router, characters.router, files.router]


class HealthCache:
    def __init__(self, ttl: float = 60.0, clock=time.monotonic):
        self.ttl, self.clock = ttl, clock
        self.value: dict | None = None
        self.at = 0.0
        self.lock = threading.Lock()


def create_app(root: Path | str | None = None, static_dir: Path | str | None = DEFAULT_STATIC_DIR,
               health_ttl: float = 60.0, clock=time.monotonic) -> FastAPI:
    app = FastAPI(title="sprite-forge-web")
    app.state.root = Path(root or os.environ.get("SPRITE_FORGE_ROOT") or "./sprites")
    app.state.health_cache = HealthCache(health_ttl, clock)
    errors.install(app)
    app.add_middleware(HostGuardMiddleware)
    for r in ROUTERS:
        app.include_router(r)
    if static_dir is not None and Path(static_dir).is_dir():
        app.include_router(static_router(Path(static_dir)))  # last: catch-all
    return app


app = create_app()
