"""``GET /api/health``: doctor result, cached for 60 s (docs/03 §11); ``?refresh=1`` bypasses the cache."""

from __future__ import annotations

from fastapi import APIRouter, Request

from sprite_forge.doctor import run_doctor

router = APIRouter()


@router.get("/api/health")
def health(request: Request, refresh: int = 0) -> dict:
    cache = request.app.state.health_cache
    with cache.lock:
        now = cache.clock()
        if refresh or cache.value is None or now - cache.at >= cache.ttl:
            cache.value, cache.at = run_doctor(), now
        return cache.value
