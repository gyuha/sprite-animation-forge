"""Per-action endpoints: prompt preview, manual upload, attempts, process, accept, save-params (docs/10 5.1-5.2).

Notes on ambiguous spots
------------------------
* ``?direction=`` rules (docs/10 5.1): ignored for single-direction plans; with 2+ directions it is required
  (missing -> 400 ``direction_required``, not in the action's directions -> 400 ``invalid_direction``). A mirror-derived
  ``left`` gives 409 ``mirrored_direction`` on prompt/upload/process/accept; the read-only GET attempts
  endpoints answer it leniently (list: ``attempts: []`` + ``mirror_of``; detail: 404 ``not_found``) and
  save-params accepts it (the params live on the action, not the direction).
* File URLs are ``/files/<cid>/<unit>/attempts/<aid>/...?v=<sha256[:12]>``; a missing file is null.
* Upload response = process response (``AttemptResult``) plus ``unit``; ``qc.recommendations`` carries the
  recommendations. If automatic processing fails the attempt stays imported and the error ``detail.attempt`` names it.
* Process ``set`` is ``{key: value}`` with the CLI ``process --set`` keys/validation (invalid -> 400 ``invalid_param``).
* Accept: QC ``fail`` without ``force`` -> 409 ``qc_failed`` (Core itself always allows it and records
  ``forced``). ``scale_profile_updated`` = the scale profile file changed; ``requalified_actions`` is always ``[]``
  because Core does not recompute other actions' QC when the profile changes (workflow.py note).
* save-params persists only the plan's per-action fields ``anchor``, ``x_anchor``, ``scale_strategy`` and
  ``components``; other process keys (t_in, t_out, despill, merge_gap_px, margins, key_color ...) have no
  per-action home in the plan schema and are rejected with 400 ``invalid_param``; an invalid value (e.g. anchor=foo) fails the plan schema -> 422.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, File, Query, Request, UploadFile
from pydantic import BaseModel

from sprite_forge import identity, workflow
from sprite_forge import manifest as mf
from sprite_forge.errors import ForgeError
from sprite_forge.plan import save_plan
from sprite_forge.prompt import build_prompt

from ..deps import Direction, file_url, load_cd_plan, read_json, resolve, uploaded_image, validate_or_422
from ..errors import ApiError

router = APIRouter()
BASE = "/api/characters/{cid}/actions/{action}"
SAVEABLE = ("anchor", "x_anchor", "scale_strategy", "components")


class PromptRequest(BaseModel):
    extra: str | None = None
    recovery: list[str] = []


class PromptResponse(BaseModel):
    prompt: str
    references_needed: list[str]
    warnings: list[str]


class AttemptFiles(BaseModel):
    raw: str | None
    clean: str | None
    sheet: str | None
    prompt: str | None
    video: str | None = None  # raw.mp4 of a method=video attempt
    frames: list[str]


class Qc(BaseModel, extra="allow"):
    status: str
    score: int | float
    results: list[dict]
    recommendations: list[dict]


class AttemptResult(BaseModel):
    attempt: str
    unit: str
    qc: Qc
    files: AttemptFiles
    derived: dict


class AttemptSummary(BaseModel):
    attempt: str
    created_at: str | None = None
    provider: str | None = None
    generation_status: str | None = None
    qc_status: str | None = None
    score: int | float | None = None
    recovery: list[str] = []
    extra: str | None = None
    prompt_version: str | None = None  # generation.json prompt_template_version (e.g. action_prompt@3)
    accepted: bool
    sheet: str | None


class AttemptList(BaseModel):
    action: str
    direction: str | None
    unit: str
    mirror_of: str | None
    accepted_attempt: str | None
    attempts: list[AttemptSummary]


class AttemptDetail(BaseModel):
    attempt: str
    unit: str
    accepted: bool
    summary: AttemptSummary
    generation: dict | None
    process: dict | None
    qc: dict | None
    vision_review: dict | None = None  # vision-review.json: advisory Codex review of the frames (POST .../review)
    files: AttemptFiles


class ProcessRequest(BaseModel):
    set: dict[str, str | int | float | bool] = {}


class AcceptRequest(BaseModel):
    force: bool = False


class AcceptResult(BaseModel):
    accepted: str
    unit: str
    forced: bool
    derived: list[str]
    scale_profile_updated: bool
    requalified_actions: list[str]


class SaveParamsRequest(BaseModel):
    set: dict[str, str]


class SaveParamsResult(BaseModel):
    action: str
    saved: dict[str, str]
    settings: dict


DirectionQuery = Query(None, description="down|up|right|left; required when the plan has 2+ directions")


def _files(cd: Path, cid: str, unit: str, aid: str) -> AttemptFiles:
    base = f"{unit}/attempts/{aid}"
    frames = sorted((cd / base / "frames").glob("*.png"))
    return AttemptFiles(
        raw=file_url(cd, cid, f"{base}/raw.png"), clean=file_url(cd, cid, f"{base}/clean.png"),
        sheet=file_url(cd, cid, f"{base}/sheet.png"), prompt=file_url(cd, cid, f"{base}/prompt.txt"),
        video=file_url(cd, cid, f"{base}/raw.mp4"),
        frames=[file_url(cd, cid, f"{base}/frames/{p.name}") for p in frames])


def _result(cd: Path, cid: str, unit: str, aid: str) -> AttemptResult:
    adir = cd / unit / "attempts" / aid
    return AttemptResult(attempt=aid, unit=unit, qc=read_json(adir / "qc-report.json"),
                         files=_files(cd, cid, unit, aid), derived=read_json(adir / "process.json")["derived"])


def _attempt_dir(cd: Path, unit: str, aid: str) -> Path:
    adir = cd / unit / "attempts" / aid
    if not re.fullmatch(r"\d{3}", aid) or not adir.is_dir():
        raise ForgeError("no_attempt", f"{unit} attempt {aid!r} does not exist")
    return adir


def _summary(cd: Path, cid: str, unit: str, aid: str, ent: dict) -> AttemptSummary:
    row = ent.get("attempts", {}).get(aid, {})
    version = (read_json(cd / unit / "attempts" / aid / "generation.json") or {}).get("prompt_template_version")
    return AttemptSummary(attempt=aid, accepted=ent.get("accepted_attempt") == aid, prompt_version=version,
                          sheet=file_url(cd, cid, f"{unit}/attempts/{aid}/sheet.png"), **row)


@router.post(BASE + "/prompt")
def preview_prompt(request: Request, cid: str, action: str, body: PromptRequest | None = None,
                   direction: Direction | None = DirectionQuery) -> PromptResponse:
    cd, plan = load_cd_plan(request, cid)
    body = body or PromptRequest()
    _, d, _ = resolve(plan, action, direction)
    pr = build_prompt(plan, identity.load_profile(cd), action, d, body.extra, body.recovery)
    return PromptResponse(prompt=pr.text, references_needed=pr.references_needed, warnings=pr.warnings)


@router.post(BASE + "/upload")
def upload_raw(request: Request, cid: str, action: str, file: UploadFile = File(...),
               direction: Direction | None = DirectionQuery) -> AttemptResult:
    cd, plan = load_cd_plan(request, cid)
    unit, d, _ = resolve(plan, action, direction)
    with uploaded_image(file) as path:
        imported = workflow.import_raw(cd, plan, action, d, path)
    aid = imported["attempt"]
    try:
        workflow.process_attempt(cd, plan, action, d, aid)
    except ForgeError as exc:
        raise ForgeError(exc.code, exc.message, exc.exit_code, {**exc.extra, "attempt": aid}) from None
    return _result(cd, cid, unit, aid)


@router.get(BASE + "/attempts")
def list_attempts(request: Request, cid: str, action: str,
                  direction: Direction | None = DirectionQuery) -> AttemptList:
    cd, plan = load_cd_plan(request, cid)
    unit, d, mirrored = resolve(plan, action, direction, allow_mirrored=True)
    ent = mf.load(cd)["actions"].get(unit, {})
    ids = [] if mirrored else sorted(ent.get("attempts", {}))
    return AttemptList(action=action, direction=d, unit=unit,
                       mirror_of=(ent.get("mirror_of") or f"{action}/right") if mirrored else None,
                       accepted_attempt=ent.get("accepted_attempt"),
                       attempts=[_summary(cd, cid, unit, a, ent) for a in ids])


@router.get(BASE + "/attempts/{aid}")
def get_attempt(request: Request, cid: str, action: str, aid: str,
                direction: Direction | None = DirectionQuery) -> AttemptDetail:
    cd, plan = load_cd_plan(request, cid)
    unit, _, _ = resolve(plan, action, direction, allow_mirrored=True)
    adir = _attempt_dir(cd, unit, aid)
    ent = mf.load(cd)["actions"].get(unit, {})
    return AttemptDetail(attempt=aid, unit=unit, accepted=ent.get("accepted_attempt") == aid,
                         summary=_summary(cd, cid, unit, aid, ent), generation=read_json(adir / "generation.json"),
                         process=read_json(adir / "process.json"), qc=read_json(adir / "qc-report.json"),
                         vision_review=read_json(adir / "vision-review.json"),
                         files=_files(cd, cid, unit, aid))


@router.post(BASE + "/attempts/{aid}/process")
def process_attempt(request: Request, cid: str, action: str, aid: str, body: ProcessRequest | None = None,
                    direction: Direction | None = DirectionQuery) -> AttemptResult:
    cd, plan = load_cd_plan(request, cid)
    unit, d, _ = resolve(plan, action, direction)
    sets = [f"{k}={str(v).lower() if isinstance(v, bool) else v}" for k, v in (body.set if body else {}).items()]
    workflow.process_attempt(cd, plan, action, d, aid, sets)
    return _result(cd, cid, unit, aid)


@router.post(BASE + "/attempts/{aid}/accept")
def accept_attempt(request: Request, cid: str, action: str, aid: str, body: AcceptRequest | None = None,
                   direction: Direction | None = DirectionQuery) -> AcceptResult:
    cd, plan = load_cd_plan(request, cid)
    unit, d, _ = resolve(plan, action, direction)
    qc = read_json(cd / unit / "attempts" / aid / "qc-report.json") if re.fullmatch(r"\d{3}", aid) else None
    if qc and qc["status"] == "fail" and not (body and body.force):
        raise ApiError(409, "qc_failed", "QC failed; accept with force=true to override",
                       {"attempt": aid, "qc_status": "fail"})
    profile = cd / "character-scale-profile.json"
    before = profile.read_bytes() if profile.exists() else None
    out = workflow.accept_attempt(cd, plan, action, d, aid)
    after = profile.read_bytes() if profile.exists() else None
    return AcceptResult(accepted=out["accepted"], unit=out["unit"], forced=out["forced"], derived=out["mirrored"],
                        scale_profile_updated=after is not None and after != before, requalified_actions=[])


@router.post(BASE + "/save-params")
def save_params(request: Request, cid: str, action: str, body: SaveParamsRequest,
                direction: Direction | None = DirectionQuery) -> SaveParamsResult:
    cd, plan = load_cd_plan(request, cid)
    resolve(plan, action, direction, allow_mirrored=True)
    unsupported = sorted(set(body.set) - set(SAVEABLE))
    if unsupported:
        raise ForgeError("invalid_params", f"cannot be saved into the plan: {unsupported}; allowed: {list(SAVEABLE)}")
    plan["actions"][action].update(body.set)
    validate_or_422("animation-plan", plan)
    save_plan(cd, plan)
    return SaveParamsResult(action=action, saved=body.set, settings=plan["actions"][action])
