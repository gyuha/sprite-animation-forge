"""Job model, in-memory registry and the single global FIFO worker (docs/10 section 2, ADR-009).

Notes on ambiguous spots
------------------------
* One worker coroutine runs one Job at a time; the blocking Core function runs in ``asyncio.to_thread``. All Job
  state is mutated on the event-loop thread only (worker threads hop back with ``call_soon_threadsafe``).
* The cross-process Codex lock is not taken here: Core's ``generate_unit`` / ``generate_reference`` / ``analyze``
  already hold ``codex_lock`` around every Codex call (a second acquisition from this process would deadlock, flock
  being per open file). A job waiting for a CLI process therefore shows ``running`` / ``starting``; cancelling it
  makes the provider wrapper return ``canceled`` as soon as the lock is obtained (no Codex process is spawned).
* ``queue_position``: 0 for running/finished jobs, 1-based position in the queue for ``queued`` jobs.
* ``attempt`` (docs/10 2.4) is known only once Core allocated the attempt directory (inside the Codex lock), i.e.
  after the job started running; the 202 response therefore carries ``attempt: null`` (docs/10 5.2 allocates at
  request time, which would need a Core change). The job event that sets ``attempt`` follows ``running``.
* ``interrupted`` as a Job state is used only for a graceful server stop (queued jobs and the running one);
  after a crash the in-memory jobs are gone and attempts are fixed by ``recovery.recover`` instead.
* Finished jobs are kept in memory (newest 200) so the UI can still read their result/error.
* ``identity_analyze`` and ``vision_review`` run a plain ``subprocess.run`` inside Core and cannot be stopped: cancelling it while
  running answers 409 ``not_cancelable``; queued identity jobs can be cancelled.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal

from pydantic import BaseModel

from sprite_forge.errors import ForgeError
from sprite_forge.fsutil import utc_now
from sprite_forge.providers import CodexCliProvider, GenerationResult
from sprite_forge.providers.video_factory import make_video_provider

from .errors import ApiError
from .sse import EventBus

JobType = Literal["reference_generate", "identity_analyze", "action_generate", "batch_generate", "vision_review"]
JobState = Literal["queued", "running", "succeeded", "failed", "canceled", "interrupted"]
FINISHED = ("succeeded", "failed", "canceled", "interrupted")
MAX_LOG = 50
MAX_FINISHED = 200
TICK_S = 5.0  # elapsed_s refresh event for running jobs
CANCEL_WAIT_S = 8.0  # SIGTERM -> SIGKILL grace (5s) + slack
MESSAGES = {"queued": "대기 중", "starting": "Codex 시작 중", "session": "세션 생성됨", "generating": "이미지 생성 중",
            "collecting": "결과 수집 중", "processing": "후처리 중", "qc": "품질 검사 중",
            "submitting": "동영상 요청 중", "polling": "동영상 생성 중", "downloading": "동영상 내려받는 중"}


class JobError(BaseModel):
    code: str
    message: str = ""
    detail: dict = {}


class LogLine(BaseModel):
    t: str
    level: str
    text: str


class Progress(BaseModel):
    done: int
    total: int
    current: str | None = None


class Job(BaseModel):
    id: str
    type: JobType
    character: str
    action: str | None = None
    direction: str | None = None
    attempt: str | None = None
    state: JobState = "queued"
    stage: str | None = None
    queue_position: int = 0
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    elapsed_s: int = 0
    expected_s: int | None = None
    progress: Progress | None = None
    log: list[LogLine] = []
    result: dict | None = None
    error: JobError | None = None


class Canceled(Exception):
    """Raised by a job function that noticed ``ctx.canceled``."""


@dataclass
class _Task:
    job: Job
    fn: Callable[["JobContext"], dict]
    cancelable: bool
    done: asyncio.Event = field(default_factory=asyncio.Event)
    cancel_requested: bool = False
    interrupted: bool = False
    provider: Any = None
    t_start: float = 0.0
    t_end: float | None = None


class _JobProvider:
    """Wraps the real provider: feeds progress callbacks into the job and honours cancel before a process exists
    (e.g. while Core waits for the cross-process Codex lock)."""

    def __init__(self, inner, ctx: "JobContext"):
        self.inner, self.ctx, self.name = inner, ctx, inner.name

    def generate(self, req, on_progress=None):
        self.ctx.attempt(Path(req.out_dir).name)
        if self.ctx.canceled:
            return GenerationResult("canceled", None, "canceled", "canceled by user")
        return self.inner.generate(req, self._emit)

    def _emit(self, stage: str, payload: dict) -> None:
        self.ctx._provider_event(stage, payload)
        if stage == "starting" and self.ctx.canceled:  # cancel raced with the spawn
            self.inner.cancel()

    def cancel(self) -> None:
        self.inner.cancel()
        self.ctx.cancel_video()


class JobContext:
    """Handed to a job function (running in a worker thread). All methods are thread-safe."""

    def __init__(self, mgr: "JobManager", task: _Task):
        self._mgr, self._task = mgr, task
        self.provider = _JobProvider(mgr.provider_factory(), self)
        task.provider = self.provider
        self._video = None

    @property
    def video_provider(self):
        """The video provider (``method=video`` units), created on first use so image-only jobs never touch it."""
        if self._video is None:
            self._video = self._mgr.video_provider_factory()
        return self._video

    def cancel_video(self) -> None:
        if self._video is not None:
            self._video.cancel()

    @property
    def canceled(self) -> bool:
        return self._task.cancel_requested or self._task.interrupted

    def _hop(self, fn, *args) -> None:
        self._mgr.loop.call_soon_threadsafe(fn, self._task, *args)

    def stage(self, name: str) -> None:
        self._hop(self._mgr._set_stage, name)

    def log(self, level: str, text: str) -> None:
        self._hop(self._mgr._add_log, level, text)

    def attempt(self, aid: str) -> None:
        self._hop(self._mgr._set_fields, {"attempt": aid})

    def target(self, action: str | None, direction: str | None) -> None:
        self._hop(self._mgr._set_fields, {"action": action, "direction": direction})

    def progress(self, done: int, total: int, current: str | None) -> None:
        self._hop(self._mgr._set_fields, {"progress": Progress(done=done, total=total, current=current)})

    def _provider_event(self, stage: str, payload: dict) -> None:
        if stage == "log":
            self.log(payload.get("level", "info"), str(payload.get("message", "")))
            return
        self.stage(stage)
        if payload.get("message"):
            self.log("info", str(payload["message"]))


def error_from(exc: BaseException) -> JobError:
    if isinstance(exc, ForgeError):
        detail = dict(exc.extra)
        if exc.code == "codex_failed":
            detail["stderr_tail"] = "\n".join(exc.message.splitlines()[1:])
        return JobError(code=exc.code, message=exc.message, detail=detail)
    return JobError(code="internal_error", message=f"{type(exc).__name__}: {exc}")


class JobManager:
    def __init__(self, bus: EventBus | None = None, provider_factory: Callable[[], Any] | None = None,
                 video_provider_factory: Callable[[], Any] | None = None):
        self.bus = bus or EventBus()
        self.provider_factory = provider_factory or CodexCliProvider
        self.video_provider_factory = video_provider_factory or make_video_provider
        self.loop: asyncio.AbstractEventLoop | None = None
        self._tasks: dict[str, _Task] = {}
        self._pending: list[_Task] = []
        self._wake = asyncio.Event()
        self._background: list[asyncio.Task] = []

    # -- lifecycle -----------------------------------------------------------------------
    async def start(self) -> None:
        self.loop = asyncio.get_running_loop()
        self._background = [asyncio.create_task(self._worker()), asyncio.create_task(self._ticker())]

    async def stop(self) -> None:
        """Graceful stop: queued jobs and the running one become ``interrupted``; the Codex process is killed."""
        for task in list(self._pending):
            self._pending.remove(task)
            self._finish(task, "interrupted")
        running = next((t for t in self._tasks.values() if t.job.state == "running"), None)
        if running is not None:
            running.interrupted = True
            if running.provider is not None:
                running.provider.cancel()
            try:
                await asyncio.wait_for(running.done.wait(), CANCEL_WAIT_S)
            except asyncio.TimeoutError:
                pass
        for t in self._background:
            t.cancel()
        await asyncio.gather(*self._background, return_exceptions=True)
        self.bus.close()

    # -- submit / query / cancel -----------------------------------------------------------
    def submit(self, type: JobType, character: str, fn: Callable[[JobContext], dict], *, action: str | None = None,
               direction: str | None = None, expected_s: int | None = None, progress: Progress | None = None,
               cancelable: bool = True) -> Job:
        job = Job(id=f"job_{uuid.uuid4().hex[:12]}", type=type, character=character, action=action,
                  direction=direction, created_at=utc_now(), expected_s=expected_s, progress=progress)
        task = _Task(job, fn, cancelable)
        self._tasks[job.id] = task
        self._pending.append(task)
        job.queue_position = len(self._pending)
        self._publish(task, "state")
        self._wake.set()
        return self._snap(task)

    def get(self, jid: str) -> Job:
        task = self._tasks.get(jid)
        if task is None:
            raise ApiError(404, "not_found", f"job {jid!r} does not exist")
        return self._snap(task)

    def list(self, active: bool = False) -> list[Job]:
        tasks = [t for t in self._tasks.values() if not active or t.job.state in ("queued", "running")]
        return [self._snap(t) for t in tasks]

    async def cancel(self, jid: str) -> Job:
        task = self._tasks.get(jid)
        if task is None:
            raise ApiError(404, "not_found", f"job {jid!r} does not exist")
        state = task.job.state
        if state == "queued":
            self._pending.remove(task)
            self._finish(task, "canceled")
            self._publish_queue()
        elif state == "running":
            if not task.cancelable:
                raise ApiError(409, "not_cancelable", f"{task.job.type} cannot be stopped while running")
            task.cancel_requested = True
            if task.provider is not None:
                task.provider.cancel()
            try:
                await asyncio.wait_for(task.done.wait(), CANCEL_WAIT_S)
            except asyncio.TimeoutError:
                pass
        else:
            raise ApiError(409, "not_cancelable", f"job is already {state}")
        return self._snap(task)

    # -- worker --------------------------------------------------------------------------
    async def _worker(self) -> None:
        while True:
            if not self._pending:
                self._wake.clear()
                await self._wake.wait()
                continue
            task = self._pending.pop(0)
            self._publish_queue()
            job = task.job
            job.state, job.stage, job.queue_position = "running", "starting", 0
            job.started_at, task.t_start = utc_now(), time.time()
            self._publish(task, "state")
            try:
                ctx = JobContext(self, task)
                job.result = await asyncio.to_thread(task.fn, ctx)
                self._finish(task, "succeeded")
            except Canceled:
                self._finish(task, "interrupted" if task.interrupted else "canceled")
            except Exception as exc:  # noqa: BLE001 - every failure becomes a failed job
                if task.interrupted or task.cancel_requested:
                    self._finish(task, "interrupted" if task.interrupted else "canceled")
                else:
                    job.error = error_from(exc)
                    if isinstance(exc, ForgeError) and exc.extra.get("attempt"):
                        job.attempt = exc.extra["attempt"]
                    self._finish(task, "failed")
            self._prune()

    async def _ticker(self) -> None:
        while True:
            await asyncio.sleep(TICK_S)
            for task in self._tasks.values():
                if task.job.state == "running":
                    self._publish(task, "tick")

    # -- state mutation (event-loop thread only) ------------------------------------------
    def _finish(self, task: _Task, state: JobState) -> None:
        job = task.job
        job.state, job.queue_position, job.finished_at = state, 0, utc_now()
        task.t_end = time.time()
        if state != "succeeded":
            job.result = None
        self._publish(task, "state")
        task.done.set()

    def _set_stage(self, task: _Task, name: str) -> None:
        if task.job.state == "running" and task.job.stage != name:
            task.job.stage = name
            self._publish(task, "stage")

    def _add_log(self, task: _Task, level: str, text: str) -> None:
        line = LogLine(t=utc_now(), level=level, text=text)
        task.job.log = [*task.job.log, line][-MAX_LOG:]
        self._publish(task, "log", line=line.model_dump())

    def _set_fields(self, task: _Task, fields: dict) -> None:
        for k, v in fields.items():
            setattr(task.job, k, v)
        self._publish(task, "update")

    def _publish_queue(self) -> None:
        for i, task in enumerate(self._pending, 1):
            if task.job.queue_position != i:
                task.job.queue_position = i
                self._publish(task, "queue")

    def _snap(self, task: _Task) -> Job:
        job = task.job
        if task.t_start:
            job.elapsed_s = int((task.t_end or time.time()) - task.t_start)
        return job.model_copy(deep=True)

    def _publish(self, task: _Task, kind: str, **extra) -> None:
        snap = self._snap(task)
        data = snap.model_dump(mode="json", exclude={"log"})
        data["kind"] = kind
        data["message"] = MESSAGES.get(snap.stage or "queued") if snap.state in ("queued", "running") else None
        data.update(extra)
        self.bus.publish(data)

    def _prune(self) -> None:
        finished = [t for t in self._tasks.values() if t.job.state in FINISHED]
        for t in finished[:-MAX_FINISHED]:
            del self._tasks[t.job.id]
