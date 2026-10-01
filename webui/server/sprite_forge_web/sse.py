"""Event bus and ``GET /api/events`` (docs/10 section 3).

Wire format (one EventSource per tab receives every job event)::

    id: <boot>:<seq>
    event: job
    data: {"id": "job_...", "state": "running", "stage": "generating", "kind": "stage", ...}

``data`` is the Job object without ``log`` plus ``message`` (Korean stage text), ``kind`` and, for ``kind == "log"``,
``line`` ``{t, level, text}``. ``kind`` is ``state`` (queued / running / terminal state change), ``stage``,
``log``, ``update`` (attempt / target / progress changed), ``queue`` (queue_position changed) or ``tick``
(``elapsed_s`` refresh every 5 s). Every event carries the full job snapshot, so clients can simply upsert by ``id``.

Notes on ambiguous spots
------------------------
* docs/10 3 says events are not replayed on reconnect and the client re-reads ``GET /api/jobs?active=1``. That
  stays the contract. On top of it, a ``Last-Event-ID`` header (sent automatically by EventSource) is honoured
  best-effort: events newer than that id are replayed from a ring buffer of the last 500 events, but only if the id
  belongs to the same server boot (``<boot>`` prefix); otherwise nothing is replayed.
* A fresh connection first receives the comment ``: connected`` (flushes the headers), then only new events.
  ``: ping`` comments follow every 15 s. The stream ends on client disconnect (Starlette cancels the generator) or
  when the server stops (``EventBus.close``).
* uvicorn waits for open connections on shutdown; ``cli.py`` therefore passes ``timeout_graceful_shutdown``.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import deque

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

PING_S = 15.0
RING = 500
_CLOSED = object()

router = APIRouter()


class EventBus:
    def __init__(self):
        self.boot = format(int(time.time() * 1000), "x")
        self._seq = 0
        self._ring: deque[tuple[int, dict]] = deque(maxlen=RING)
        self._subs: set[asyncio.Queue] = set()

    def publish(self, data: dict) -> None:
        self._seq += 1
        self._ring.append((self._seq, data))
        for q in self._subs:
            q.put_nowait((self._seq, data))

    def close(self) -> None:
        for q in self._subs:
            q.put_nowait(_CLOSED)

    def subscribe(self, last_event_id: str | None = None) -> tuple[asyncio.Queue, list[tuple[int, dict]]]:
        replay: list[tuple[int, dict]] = []
        boot, _, seq = (last_event_id or "").partition(":")
        if boot == self.boot and seq.isdigit():
            replay = [(n, d) for n, d in self._ring if n > int(seq)]
        q: asyncio.Queue = asyncio.Queue()
        self._subs.add(q)
        return q, replay

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subs.discard(q)

    def frame(self, seq: int, data: dict) -> str:
        return f"id: {self.boot}:{seq}\nevent: job\ndata: {json.dumps(data, ensure_ascii=False, separators=(',', ':'))}\n\n"

    async def stream(self, last_event_id: str | None = None):
        q, replay = self.subscribe(last_event_id)
        try:
            yield ": connected\n\n"
            for seq, data in replay:
                yield self.frame(seq, data)
            while True:
                try:
                    item = await asyncio.wait_for(q.get(), PING_S)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                    continue
                if item is _CLOSED:
                    return
                yield self.frame(*item)
        finally:
            self.unsubscribe(q)


@router.get("/api/events")
async def events(request: Request) -> StreamingResponse:
    bus: EventBus = request.app.state.bus
    return StreamingResponse(bus.stream(request.headers.get("last-event-id")), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
