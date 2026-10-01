"""The four Job-creating endpoints (docs/10 5.1-5.2): reference generate, identity analyze, action generate,
generate-all. Each validates like its synchronous sibling, checks that Codex is usable (503 ``codex_unavailable``
with the doctor result in ``detail.doctor``), queues the Job and answers ``202 {"job": Job, "attempt": null}``.

Notes on ambiguous spots
------------------------
* Request-time preconditions mirror Core (412 ``precondition_failed``): reference (and for generation the identity
  profile and, for non-representative directions, the representative unit's adopted frame) must exist; ``direction`` rules and 409 ``mirrored_direction`` are those of the sync action endpoints; the
  recovery codes / extra are validated by building the prompt once.
* ``attempt`` in the 202 body is always null: Core allocates the attempt inside the Codex lock (see jobs.py); the
  Job's ``attempt`` is filled once the job runs.
* ``reference/generate`` body: ``{description, count=1}``; ``identity/analyze`` body (optional): ``{force=false}``
  (overwrite an edited profile); ``generate-all`` body: ``{actions?, auto_accept=true, max_regenerations=1 (0..2)}``
  (defaults are not specified in docs/10 5.2 except ``max_regenerations`` from docs/09 7). An empty unit list ->
  400 ``nothing_to_generate``.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Query, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from sprite_forge import identity
from sprite_forge import plan as plan_mod
from sprite_forge import manifest as mf
from sprite_forge.errors import EXIT_PRECONDITION, ForgeError
from sprite_forge.generation import MAX_REFERENCE_COUNT
from sprite_forge.plan import SECONDS_PER_CALL
from sprite_forge.prompt import build_prompt

from .. import job_tasks
from ..deps import Direction, load_cd, load_cd_plan, resolve
from ..errors import ApiError
from ..jobs import Job, Progress
from .actions import BASE, DirectionQuery, PromptRequest
from .health import health

router = APIRouter()


class JobCreated(BaseModel):
    job: Job
    attempt: str | None = None


class ReferenceGenerateRequest(BaseModel):
    description: str = Field(min_length=1)
    count: int = Field(1, ge=1, le=MAX_REFERENCE_COUNT)


class IdentityAnalyzeRequest(BaseModel):
    force: bool = False


class GenerateAllRequest(BaseModel):
    actions: list[str] | None = None
    auto_accept: bool = True
    max_regenerations: int = Field(1, ge=0, le=2)


async def require_codex(request: Request) -> None:
    doctor = await run_in_threadpool(health, request)
    if not doctor["ready"]:
        raise ApiError(503, "codex_unavailable", "Codex is not ready; see detail.doctor", {"doctor": doctor})


def require_reference(cd) -> None:
    if mf.load(cd)["reference"] is None or not (cd / "reference" / "character-keyed.png").exists():
        raise ForgeError("no_reference", "run reference import (or reference generate/select) first", EXIT_PRECONDITION)


def require_video() -> None:
    if not plan_mod.video_method_available():
        raise ForgeError("method_unavailable", "method=video needs a connected video provider "
                         "(see docs/13-video-api-setup.md)", EXIT_PRECONDITION)


async def require_providers(request: Request, plan: dict, actions) -> None:
    """Codex is needed only by grid/breathe units, the video provider only by video units."""
    methods = {plan["actions"][a].get("method", "grid") for a in actions}
    if methods & {"grid", "breathe"}:
        await require_codex(request)
    if "video" in methods:
        require_video()


def require_profile(cd) -> dict:
    profile = identity.load_profile(cd)
    if profile is None:
        raise ForgeError("no_profile", "run identity analyze first", EXIT_PRECONDITION)
    return profile


@router.post("/api/characters/{cid}/reference/generate", status_code=202)
async def generate_reference(request: Request, cid: str, body: ReferenceGenerateRequest) -> JobCreated:
    cd = load_cd(request, cid)
    await require_codex(request)
    job = request.app.state.jobs.submit("reference_generate", cid, job_tasks.reference_generate(cd, body.description, body.count),
                                        expected_s=body.count * SECONDS_PER_CALL)
    return JobCreated(job=job)


@router.post("/api/characters/{cid}/identity/analyze", status_code=202)
async def analyze_identity(request: Request, cid: str, body: IdentityAnalyzeRequest | None = None) -> JobCreated:
    cd = load_cd(request, cid)
    require_reference(cd)
    await require_codex(request)
    job = request.app.state.jobs.submit("identity_analyze", cid, job_tasks.identity_analyze(cd, bool(body and body.force)),
                                        cancelable=False)
    return JobCreated(job=job)


@router.post(BASE + "/attempts/{aid}/review", status_code=202)
async def review_attempt(request: Request, cid: str, action: str, aid: str,
                         direction: Direction | None = DirectionQuery) -> JobCreated:
    cd, plan = load_cd_plan(request, cid)
    unit, d, _ = resolve(plan, action, direction)
    if not re.fullmatch(r"\d{3}", aid) or not (cd / unit / "attempts" / aid).is_dir():
        raise ApiError(404, "not_found", f"{unit} attempt {aid!r} does not exist")
    if not any((cd / unit / "attempts" / aid / "frames").glob("*.png")):
        raise ForgeError("not_processed", f"{unit} attempt {aid} has no frames; process it first", EXIT_PRECONDITION)
    await require_codex(request)
    job = request.app.state.jobs.submit("vision_review", cid, job_tasks.vision_review(cd, action, d, aid), action=action,
                                        direction=d, cancelable=False)
    return JobCreated(job=job)


@router.post(BASE + "/generate", status_code=202)
async def generate_action(request: Request, cid: str, action: str, body: PromptRequest | None = None,
                          direction: Direction | None = DirectionQuery) -> JobCreated:
    cd, plan = load_cd_plan(request, cid)
    body = body or PromptRequest()
    _, d, _ = resolve(plan, action, direction)
    require_reference(cd)
    profile = require_profile(cd)
    pr = build_prompt(plan, profile, action, d, body.extra, body.recovery)  # validates recovery codes
    for role in pr.references_needed:
        if role != "character" and not (cd / role.split(":", 1)[1] / "frames" / "000.png").exists():
            raise ForgeError("no_direction_reference", f"accept {role.split(':', 1)[1]} first (it is the direction reference)",
                             EXIT_PRECONDITION)
    await require_providers(request, plan, [action])
    job = request.app.state.jobs.submit(
        "action_generate", cid, job_tasks.action_generate(cd, action, d if len(plan["directions"]) > 1 else None,
                                                          body.extra, body.recovery),
        action=action, direction=d if len(plan["directions"]) > 1 else None, expected_s=SECONDS_PER_CALL)
    return JobCreated(job=job)


@router.post("/api/characters/{cid}/generate-all", status_code=202)
async def generate_all(request: Request, cid: str, body: GenerateAllRequest | None = None) -> JobCreated:
    cd, plan = load_cd_plan(request, cid)
    body = body or GenerateAllRequest()
    for a in body.actions or []:
        if a not in plan["actions"]:
            raise ForgeError("unknown_action", f"{a!r} is not in the plan (actions: {plan['order']})")
    require_reference(cd)
    require_profile(cd)
    accepted = {u for u, e in mf.load(cd)["actions"].items() if e.get("accepted_attempt")}
    todo = job_tasks.batch_units(plan, body.actions, accepted)
    if not todo:
        raise ApiError(400, "nothing_to_generate", "no unit left to generate")
    await require_providers(request, plan, {u["action"] for u in todo})
    job = request.app.state.jobs.submit(
        "batch_generate", cid, job_tasks.batch_generate(cd, todo, body.auto_accept, body.max_regenerations),
        expected_s=len(todo) * SECONDS_PER_CALL, progress=Progress(done=0, total=len(todo)))
    return JobCreated(job=job)
