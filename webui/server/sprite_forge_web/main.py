"""FastAPI app factory. ``from sprite_forge_web.main import app`` builds the default app (reads
``SPRITE_FORGE_ROOT`` only; no other side effects). Add a router: create ``routes/<name>.py`` with ``router``
and append it to ``ROUTERS``.
"""

from __future__ import annotations

import os
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from . import errors, recovery, sse
from .jobs import JobManager
from .routes import actions, characters, export, files, generate, health, identity, jobs, plan, presets, reference
from .routes.static import static_router
from .security import HostGuardMiddleware

DEFAULT_STATIC_DIR = Path(__file__).resolve().parents[2] / "web" / "dist"
ROUTERS = [health.router, presets.router, characters.router, reference.router, identity.router, plan.router,
           actions.router, generate.router, jobs.router, sse.router, export.router, files.router]


class HealthCache:
    def __init__(self, ttl: float = 60.0, clock=time.monotonic):
        self.ttl, self.clock = ttl, clock
        self.value: dict | None = None
        self.at = 0.0
        self.lock = threading.Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: recovery (docs/10 6), then the single job worker. Shutdown: interrupt jobs, close SSE streams.
    Tests must enter the TestClient (``with client:``) for this to run."""
    app.state.recovery = recovery.recover(app.state.root)
    await app.state.jobs.start()
    try:
        yield
    finally:
        await app.state.jobs.stop()


def create_app(root: Path | str | None = None, static_dir: Path | str | None = DEFAULT_STATIC_DIR,
               health_ttl: float = 60.0, clock=time.monotonic, provider_factory=None,
               allow_any_host: bool = False) -> FastAPI:
    """``provider_factory``: zero-arg callable returning the image provider of each job (default
    ``CodexCliProvider()``, which reads ``SPRITE_FORGE_CODEX_BIN`` / ``CODEX_HOME`` per job).
    ``allow_any_host`` disables the Host header guard (set by the CLI when a non-loopback ``--host`` is used)."""
    app = FastAPI(title="sprite-forge-web", lifespan=lifespan)
    app.state.root = Path(root or os.environ.get("SPRITE_FORGE_ROOT") or "./sprites")
    app.state.bus = sse.EventBus()
    app.state.jobs = JobManager(app.state.bus, provider_factory)
    app.state.health_cache = HealthCache(health_ttl, clock)
    errors.install(app)
    app.add_middleware(HostGuardMiddleware, allow_any=allow_any_host)
    for r in ROUTERS:
        app.include_router(r)
    if static_dir is not None and Path(static_dir).is_dir():
        app.include_router(static_router(Path(static_dir)))  # last: catch-all
    return app


app = create_app()
