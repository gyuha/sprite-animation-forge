"""Bodies of the four Job types (run in the worker thread via ``JobManager``). They only call Core functions.

Notes on ambiguous spots (docs/09 7 batch behaviour)
----------------------------------------------------
* Units: ``plan.units`` order (per action ``down -> right -> up``, actions in plan ``order``), mirror-derived
  units excluded. ``actions`` omitted -> every unit that has no accepted attempt yet; ``actions`` given -> all
  units of those actions (already accepted ones are generated again, the old accepted result stays until a new
  attempt is accepted).
* Per unit: generate -> process -> QC. ``pass``/``warn`` is accepted when ``auto_accept`` else left for review.
  ``fail`` -> up to 2 automatic reprocesses using the first ``reprocess`` recommendation (``recovery``
  recommendations), then regeneration while fewer than ``max_regenerations`` were done (each new attempt gets its
  own 2 reprocesses), else review. A generation / processing error marks the unit ``review`` (no retry) and the
  batch continues; the batch Job itself ends ``succeeded`` and lists every unit in ``result.units``.
* Cancel stops after the current Codex call is killed; finished units stay as they are. Each finished unit is
  logged (``<unit>: accepted|review``) so the UI can show them even for a canceled batch.
* ``action_generate`` never accepts: ``result = {attempt, qc_status, accepted: false}`` (docs/10 2.4).
"""

from __future__ import annotations

import os
from pathlib import Path

from sprite_forge import generation, identity, vision, workflow
from sprite_forge.errors import ForgeError
from sprite_forge.plan import load_plan, units

from .jobs import Canceled, JobContext

MAX_AUTO_REPROCESS = 2


def codex_timeout() -> int:
    return int(os.environ.get("SPRITE_FORGE_CODEX_TIMEOUT") or 300)


def set_args(rec_set: dict) -> list[str]:
    return [f"{k}={str(v).lower() if isinstance(v, bool) else v}" for k, v in rec_set.items()]


def generate_and_process(ctx: JobContext, cd: Path, plan: dict, profile: dict, action: str, direction: str | None,
                         extra: str | None, recovery: list[str]) -> tuple[str, dict]:
    """Generate one attempt, then process + QC it. Returns ``(attempt, qc)``."""
    out = generation.generate_unit(cd, plan, profile, action, direction, extra, recovery, codex_timeout(),
                                   provider=ctx.provider)
    aid = out["attempt"]
    ctx.attempt(aid)
    ctx.stage("processing")
    try:
        res = workflow.process_attempt(cd, plan, action, direction, aid)
    except ForgeError as exc:
        raise ForgeError(exc.code, exc.message, exc.exit_code, {**exc.extra, "attempt": aid}) from None
    ctx.stage("qc")
    return aid, res["qc"]


def action_generate(cd: Path, action: str, direction: str | None, extra: str | None, recovery: list[str]):
    def run(ctx: JobContext) -> dict:
        plan = load_plan(cd)
        aid, qc = generate_and_process(ctx, cd, plan, identity.load_profile(cd), action, direction, extra, recovery)
        return {"attempt": aid, "qc_status": qc["status"], "accepted": False}

    return run


def vision_review(cd: Path, action: str, direction: str | None, attempt: str):
    def run(ctx: JobContext) -> dict:
        ctx.stage("generating")
        out = vision.review_attempt(cd, load_plan(cd), action, direction, attempt, codex_timeout(), provider=ctx.provider.inner)
        return {"attempt": out["attempt"], "review": out["review"]}

    return run


def reference_generate(cd: Path, description: str, count: int):
    def run(ctx: JobContext) -> dict:
        ctx.stage("starting")
        return generation.generate_reference(cd, description, count, codex_timeout(), provider=ctx.provider)

    return run


def identity_analyze(cd: Path, force: bool):
    def run(ctx: JobContext) -> dict:
        ctx.stage("generating")
        return {"profile": identity.analyze(cd, codex_timeout(), force, provider=ctx.provider.inner)["profile"]}

    return run


def batch_units(plan: dict, actions: list[str] | None, accepted: set[str]) -> list[dict]:
    wanted = [u for u in units(plan) if not u["mirrored"]]
    if actions is not None:
        return [u for u in wanted if u["action"] in actions]
    return [u for u in wanted if u["unit"] not in accepted]


def _run_unit(ctx: JobContext, cd: Path, plan: dict, profile: dict, unit: dict, auto_accept: bool,
              max_regenerations: int) -> dict:
    action, direction = unit["action"], unit["direction"] if len(plan["directions"]) > 1 else None
    row = {"unit": unit["unit"], "status": "review", "attempt": None, "qc_status": None}
    regenerations = 0
    codes: list[str] = []  # regenerate recommendations of the previous failed attempt become recovery phrases
    while True:
        try:
            aid, qc = generate_and_process(ctx, cd, plan, profile, action, direction, None, codes)
            row["attempt"] = aid
            reprocessed = 0
            while qc["status"] == "fail" and reprocessed < MAX_AUTO_REPROCESS and not ctx.canceled:
                rec = next((r for r in qc["recommendations"] if r["type"] == "reprocess"), None)
                if rec is None:
                    break
                qc = workflow.process_attempt(cd, plan, action, direction, aid, set_args(rec["set"]))["qc"]
                reprocessed += 1
        except ForgeError as exc:
            if ctx.canceled:
                raise Canceled from None
            row.update(attempt=exc.extra.get("attempt", row["attempt"]), error={"code": exc.code, "message": exc.message})
            return row
        if ctx.canceled:
            raise Canceled
        row["qc_status"] = qc["status"]
        if qc["status"] != "fail":
            if auto_accept:
                workflow.accept_attempt(cd, plan, action, direction, aid)
                row["status"] = "accepted"
            return row
        if regenerations >= max_regenerations:
            return row
        regenerations += 1
        codes = list(dict.fromkeys(r["code"] for r in qc["recommendations"] if r["type"] == "regenerate"))


def batch_generate(cd: Path, todo: list[dict], auto_accept: bool, max_regenerations: int):
    def run(ctx: JobContext) -> dict:
        plan = load_plan(cd)
        profile = identity.load_profile(cd)
        rows = []
        for i, unit in enumerate(todo):
            if ctx.canceled:
                raise Canceled
            ctx.progress(i, len(todo), unit["unit"])
            ctx.target(unit["action"], unit["direction"] if len(plan["directions"]) > 1 else None)
            row = _run_unit(ctx, cd, plan, profile, unit, auto_accept, max_regenerations)
            rows.append(row)
            ctx.log("info" if row["status"] == "accepted" else "warning", f"{row['unit']}: {row['status']}")
        ctx.progress(len(todo), len(todo), None)
        return {"units": rows, "accepted": sum(r["status"] == "accepted" for r in rows),
                "review": sum(r["status"] == "review" for r in rows)}

    return run
