"""Job queries and cancel (docs/10 5.1). Responses: list ``{"jobs": [Job]}``, detail / cancel ``{"job": Job}``.

* ``GET /api/jobs`` lists every job kept in memory in creation order; ``?active=1`` only ``queued``/``running``
  ones (running first by construction, then the queue order) - what the UI reads after an SSE (re)connect.
* ``POST /api/jobs/{jid}/cancel``: queued -> removed (``canceled``); running -> provider cancel (SIGTERM, SIGKILL after
  5 s), answered once the job left ``running`` (at most ~8 s; the job is then returned as it is). A finished job or a
  running ``identity_analyze`` -> 409 ``not_cancelable``; unknown id -> 404 ``not_found``.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from ..jobs import Job

router = APIRouter()


class JobList(BaseModel):
    jobs: list[Job]


class JobResponse(BaseModel):
    job: Job


@router.get("/api/jobs")
async def list_jobs(request: Request, active: int = 0) -> JobList:
    return JobList(jobs=request.app.state.jobs.list(active=bool(active)))


@router.get("/api/jobs/{jid}")
async def get_job(request: Request, jid: str) -> JobResponse:
    return JobResponse(job=request.app.state.jobs.get(jid))


@router.post("/api/jobs/{jid}/cancel")
async def cancel_job(request: Request, jid: str) -> JobResponse:
    return JobResponse(job=await request.app.state.jobs.cancel(jid))
