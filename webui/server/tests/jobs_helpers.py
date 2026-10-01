"""Helpers for the Job / SSE / recovery tests: ready characters, wrapper "codex" scripts, waiting, event recording."""

import os
import stat
import time
from pathlib import Path

from sprite_forge import identity

from .api_sync_helpers import char_url, image_bytes, make_character, make_plan, png_file
from .conftest import FAKE_CODEX

TERMINAL = ("succeeded", "failed", "canceled", "interrupted")


def ready_character(client, root, cid="hero", actions=("idle",), topdown=False, sets=()):
    """Character with reference, (empty) identity profile and plan; idle = 4 frames 2x2 = the fake codex default grid."""
    make_character(client, cid, view="topdown" if topdown else "side")
    ref = client.post(char_url(cid, "/reference"), files=png_file(image_bytes("PNG", (300, 300))))
    assert ref.status_code == 200, ref.text
    identity.write_empty(Path(root) / cid)
    body = {"actions": list(actions), "set": list(sets)}
    if topdown:
        body["view"] = "topdown"
    make_plan(client, cid, **body)
    return cid


def gen_url(cid="hero", action="idle"):
    return char_url(cid, f"/actions/{action}/generate")


def post_generate(client, cid="hero", action="idle", expect=202, **params):
    r = client.post(gen_url(cid, action), params=params, json={})
    assert r.status_code == expect, r.text
    return r.json()


def job_of(client, jid) -> dict:
    r = client.get(f"/api/jobs/{jid}")
    assert r.status_code == 200, r.text
    return r.json()["job"]


def wait_job(client, jid, states=TERMINAL, timeout=30.0) -> dict:
    deadline = time.time() + timeout
    while True:
        job = job_of(client, jid)
        if job["state"] in states:
            return job
        assert time.time() < deadline, f"job {jid} still {job['state']}/{job['stage']} after {timeout}s"
        time.sleep(0.05)


def wait_until(pred, timeout=15.0, what="condition"):
    deadline = time.time() + timeout
    while not pred():
        assert time.time() < deadline, f"timeout waiting for {what}"
        time.sleep(0.05)


def record_events(client) -> list[dict]:
    """Capture every event the server publishes (the same dicts SSE clients receive)."""
    events: list[dict] = []
    bus = client.app.state.bus
    original = bus.publish

    def publish(data):
        events.append(data)
        original(data)

    bus.publish = publish
    return events


def states_of(events, jid) -> list[str]:
    """Event ``state`` values of one job, consecutive duplicates (stage / update / tick events) removed."""
    out: list[str] = []
    for e in events:
        if e["id"] == jid and (not out or out[-1] != e["state"]):
            out.append(e["state"])
    return out


def wrapper_bin(tmp_path: Path, monkeypatch, body: str) -> Path:
    """A shell wrapper around the fake codex; ``body`` runs for ``exec`` calls (image generation) before it execs."""
    script = tmp_path / "codex_wrapper"
    script.write_text(f'#!/bin/sh\nif [ "$1" = exec ]; then\n{body}\nfi\nexec "{FAKE_CODEX}" "$@"\n')
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("SPRITE_FORGE_CODEX_BIN", str(script))
    return script


def mode_by_call(tmp_path: Path, monkeypatch, modes: list[str]) -> None:
    """The n-th ``exec`` call of the fake codex runs with FAKE_CODEX_MODE=modes[n-1] (last one repeats)."""
    counter = tmp_path / "calls"
    cases = "\n".join(f'  {i}) export FAKE_CODEX_MODE={m};;' for i, m in enumerate(modes, 1))
    wrapper_bin(tmp_path, monkeypatch, f'n=$(cat "{counter}" 2>/dev/null || echo 0); n=$((n+1)); echo $n > "{counter}"\n'
                f'case $n in\n{cases}\n  *) export FAKE_CODEX_MODE={modes[-1]};;\nesac')


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def unit_attempts(root, cid, unit):
    return sorted(p.name for p in (Path(root) / cid / unit / "attempts").glob("*"))

