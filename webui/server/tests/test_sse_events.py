"""``GET /api/events`` against a real uvicorn server (Starlette's TestClient cannot stream an endless response).

Event wire format and ordering: docs/10 3 and the ``sse.py`` docstring."""

import asyncio
import json
import threading
import time

import httpx
import pytest
import uvicorn

from fastapi.testclient import TestClient

from sprite_forge_web import jobs, sse
from sprite_forge_web.main import create_app

from .conftest import BASE
from .jobs_helpers import ready_character, wrapper_bin


class Stream:
    """Reads an SSE response in a thread; ``events`` holds ``{id, event, data}`` dicts, ``comments`` the ': x' lines."""

    def __init__(self, base, headers=None):
        self.events, self.comments, self.error = [], [], None
        self.resp_cm = httpx.stream("GET", base + "/api/events", headers=headers, timeout=httpx.Timeout(10, read=None))
        self.resp = self.resp_cm.__enter__()
        assert self.resp.status_code == 200 and self.resp.headers["content-type"].startswith("text/event-stream")
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()

    def _read(self):
        cur = {}
        try:
            for line in self.resp.iter_lines():
                if line == "":
                    if cur:
                        self.events.append(cur)
                    cur = {}
                elif line.startswith(":"):
                    self.comments.append(line)
                else:
                    k, _, v = line.partition(": ")
                    cur[k] = json.loads(v) if k == "data" else v
        except Exception as exc:  # noqa: BLE001 - closing the response from the test ends the read
            self.error = exc

    def wait(self, pred, timeout=30.0):
        deadline = time.time() + timeout
        while not pred():
            assert time.time() < deadline, f"timeout; events so far: {[e['data'] for e in self.events]}"
            time.sleep(0.02)

    def for_job(self, jid):
        return [e["data"] for e in self.events if e["data"]["id"] == jid]

    def close(self):
        self.resp_cm.__exit__(None, None, None)
        self.thread.join(5)


class Live:
    """A uvicorn server (own thread, free port) around a fresh app on ``root``."""

    def __init__(self, root):
        self.app = create_app(root=root, static_dir=None)
        self.server = uvicorn.Server(uvicorn.Config(self.app, host="127.0.0.1", port=0, log_level="warning",
                                                    timeout_graceful_shutdown=2))
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()
        deadline = time.time() + 10
        while not self.server.started:
            assert time.time() < deadline, "server did not start"
            time.sleep(0.02)
        self.base = f"http://127.0.0.1:{self.server.servers[0].sockets[0].getsockname()[1]}"
        self.client = httpx.Client(base_url=self.base, timeout=30)

    def stop(self):
        self.server.should_exit = True
        self.thread.join(15)
        assert not self.thread.is_alive(), "server did not shut down"


@pytest.fixture
def make_live(root):
    servers = []

    def make():
        servers.append(Live(root))
        return servers[-1]

    yield make
    for srv in servers:
        srv.stop()
        srv.client.close()


@pytest.fixture
def live(make_live):
    return make_live()


def post_generate(live, cid="hero", **params):
    r = live.client.post(f"/api/characters/{cid}/actions/idle/generate", params=params, json={})
    assert r.status_code == 202, r.text
    return r.json()["job"]["id"]


def prepare(live, root, cid="hero"):
    # the helpers want a TestClient; the sync endpoints they use work on the same root
    with TestClient(create_app(root=root, static_dir=None), base_url=BASE) as c:
        ready_character(c, root, cid)


def test_sse_succeeded_job_event_order_and_shape(live, root):
    prepare(live, root)
    s = Stream(live.base)
    try:
        s.wait(lambda: s.comments)  # ": connected" arrived: subscribed
        jid = post_generate(live)
        s.wait(lambda: any(d["state"] == "succeeded" for d in s.for_job(jid)))
        events = s.for_job(jid)
        states = [e["state"] for e in events]
        assert states[0] == "queued" and states[1] == "running" and states[-1] == "succeeded"
        assert all(st == "running" for st in states[1:-1])
        stages = [e["stage"] for e in events if e["state"] == "running"]
        dedup = [st for i, st in enumerate(stages) if i == 0 or st != stages[i - 1]]
        assert dedup == ["starting", "session", "generating", "collecting", "processing", "qc"]
        assert events[0]["kind"] == "state" and events[0]["queue_position"] == 1 and events[0]["message"] == "대기 중"
        last = events[-1]
        assert last["result"] == {"attempt": "001", "qc_status": last["result"]["qc_status"], "accepted": False}
        assert last["stage"] == "qc" and last["finished_at"] and "log" not in last and last["error"] is None
        assert any(e["kind"] == "log" and e["line"]["text"] for e in events)  # codex agent message
        ids = [e["id"] for e in s.events]
        assert len(set(ids)) == len(ids) and all(i.count(":") == 1 for i in ids)
        assert {e["event"] for e in s.events} == {"job"}
    finally:
        s.close()


def test_sse_canceled_job_event_order(live, root, tmp_path, monkeypatch):
    prepare(live, root)
    wrapper_bin(tmp_path, monkeypatch, ":")
    monkeypatch.setenv("FAKE_CODEX_MODE", "hang")
    s = Stream(live.base)
    try:
        s.wait(lambda: s.comments)
        jid = post_generate(live)
        s.wait(lambda: any(d["stage"] == "generating" for d in s.for_job(jid)))
        assert live.client.post(f"/api/jobs/{jid}/cancel").json()["job"]["state"] == "canceled"
        s.wait(lambda: s.for_job(jid)[-1]["state"] == "canceled")
        states = [e["state"] for e in s.for_job(jid)]
        assert states[0] == "queued" and states[-1] == "canceled"
        assert set(states) == {"queued", "running", "canceled"} and states.count("canceled") == 1
        assert s.for_job(jid)[-1]["result"] is None
    finally:
        s.close()


def test_sse_failed_job_carries_the_error(live, root, monkeypatch):
    prepare(live, root)
    monkeypatch.setenv("FAKE_CODEX_MODE", "no_image")
    s = Stream(live.base)
    try:
        s.wait(lambda: s.comments)
        jid = post_generate(live)
        s.wait(lambda: s.for_job(jid) and s.for_job(jid)[-1]["state"] == "failed")
        last = s.for_job(jid)[-1]
        assert last["error"]["code"] == "no_image" and last["error"]["detail"]["attempt"] == "001"
        assert [e["state"] for e in s.for_job(jid)][0:2] == ["queued", "running"]
    finally:
        s.close()


def test_sse_disconnect_unsubscribes_and_server_keeps_serving(live, root):
    bus = live.app.state.bus
    s1, s2 = Stream(live.base), Stream(live.base)
    s1.wait(lambda: s1.comments)
    s2.wait(lambda: s2.comments)
    assert len(bus._subs) == 2
    s1.close()
    deadline = time.time() + 5
    while len(bus._subs) != 1:
        assert time.time() < deadline, "closed client was not unsubscribed"
        time.sleep(0.02)
    s2.close()
    deadline = time.time() + 5
    while bus._subs:
        assert time.time() < deadline
        time.sleep(0.02)
    assert live.client.get("/api/jobs").status_code == 200


def test_sse_last_event_id_replays_only_newer_events_of_the_same_boot(live, root):
    prepare(live, root)
    jid = post_generate(live)
    deadline = time.time() + 30
    while live.client.get(f"/api/jobs/{jid}").json()["job"]["state"] != "succeeded":
        assert time.time() < deadline
        time.sleep(0.05)
    ring = list(live.app.state.bus._ring)
    boot = live.app.state.bus.boot
    assert len(ring) >= 4
    s = Stream(live.base, headers={"Last-Event-ID": f"{boot}:{ring[-3][0]}"})
    try:
        s.wait(lambda: len(s.events) >= 2)
        assert [e["id"] for e in s.events] == [f"{boot}:{ring[-2][0]}", f"{boot}:{ring[-1][0]}"]
    finally:
        s.close()
    other = Stream(live.base, headers={"Last-Event-ID": f"deadbeef:{ring[0][0]}"})  # another boot: nothing replayed
    try:
        other.wait(lambda: other.comments)
        time.sleep(0.2)
        assert other.events == []
    finally:
        other.close()
    fresh = Stream(live.base)  # no header: docs/10 3 - no replay, the client reads /api/jobs?active=1
    try:
        fresh.wait(lambda: fresh.comments)
        time.sleep(0.2)
        assert fresh.events == []
    finally:
        fresh.close()


def test_sse_running_job_gets_tick_events(make_live, root, monkeypatch):
    monkeypatch.setattr(jobs, "TICK_S", 0.2)
    monkeypatch.setenv("FAKE_CODEX_DELAY_S", "1.5")
    live = make_live()
    prepare(live, root)
    s = Stream(live.base)
    try:
        s.wait(lambda: s.comments)
        jid = post_generate(live)
        s.wait(lambda: any(d["kind"] == "tick" for d in s.for_job(jid)))
        assert all(d["state"] == "running" for d in s.for_job(jid) if d["kind"] == "tick")
    finally:
        s.close()


def test_sse_open_stream_does_not_block_server_shutdown(live, root):
    s = Stream(live.base)
    s.wait(lambda: s.comments)
    started = time.time()
    live.stop()  # connection still open: graceful timeout, lifespan shutdown closes the bus
    assert not live.thread.is_alive() and time.time() - started < 10
    s.thread.join(5)
    assert not s.thread.is_alive()


def test_sse_bus_unit_frames_replay_and_close():
    async def scenario():
        bus = sse.EventBus()
        bus.publish({"id": "a", "n": 1})
        gen = bus.stream()
        assert await gen.__anext__() == ": connected\n\n"
        bus.publish({"id": "a", "n": 2})
        frame = await gen.__anext__()
        assert frame == f'id: {bus.boot}:2\nevent: job\ndata: {{"id":"a","n":2}}\n\n'
        bus.close()
        with pytest.raises(StopAsyncIteration):
            await gen.__anext__()
        assert not bus._subs

    asyncio.run(scenario())


def test_sse_ping_comment_when_idle(monkeypatch):
    monkeypatch.setattr(sse, "PING_S", 0.05)

    async def scenario():
        gen = sse.EventBus().stream()
        assert await gen.__anext__() == ": connected\n\n"
        assert await gen.__anext__() == ": ping\n\n"
        await gen.aclose()

    asyncio.run(scenario())
