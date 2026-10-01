"""Startup recovery (docs/10 section 6): ``recover(root)`` runs once before the server accepts requests.

* Every ``<root>/<cid>/manifest.json`` attempt with ``generation_status == "running"`` becomes ``interrupted``
  (docs/08 6) - the server (or a CLI process) died mid-generation.
* Leftover ``attempts/NNN/.lock`` files are removed when no process holds them: the lock is a flock (the kernel
  frees it when its owner dies, so the file merely lingers) and ``fsutil.attempt_lock`` records the owner's PID in it.

Notes on ambiguous spots
------------------------
* A Skill CLI generation may legitimately be running while the server starts. Every Codex call holds the
  ``<root>/.codex.lock`` flock, so when it is held right now nothing is touched at all (``skipped: true``).
* A lock file is kept when it is flock-held, or when its recorded PID is still alive (conservative: PID reuse can
  keep an orphan file around; a lock without a PID - written by an older Core - is judged by the flock alone).
"""

from __future__ import annotations

import contextlib
import fcntl
import os
from pathlib import Path

from sprite_forge import manifest as mf
from sprite_forge.cli import CID_RE


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _remove_if_stale(lock: Path) -> bool:
    try:
        text = lock.read_text().strip()
        pid = int(text) if text.isdigit() else None
        with open(lock, "a+") as f:
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return False
            try:
                if pid is not None and _pid_alive(pid):
                    return False
                lock.unlink()
                return True
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
    except OSError:
        return False


def _mark_interrupted(cd: Path) -> list[str]:
    found = [(u, a) for u, ent in mf.load(cd)["actions"].items() for a, row in ent.get("attempts", {}).items()
             if row.get("generation_status") == "running"]
    if found:
        def apply(m):
            for u, a in found:
                m["actions"][u]["attempts"][a]["generation_status"] = "interrupted"

        mf.update(cd, apply)
    return [f"{cd.name}/{u}/{a}" for u, a in found]


def recover(root: Path) -> dict:
    out = {"skipped": False, "interrupted": [], "locks_removed": []}
    if not root.is_dir():
        return out
    with open(root / ".codex.lock", "a+") as guard:
        try:
            fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            out["skipped"] = True
            return out
        try:
            for cd in sorted(root.iterdir()):
                if not (CID_RE.match(cd.name) and (cd / "manifest.json").is_file()):
                    continue
                with contextlib.suppress(Exception):  # a broken character must not stop the server
                    out["interrupted"] += _mark_interrupted(cd)
                for lock in cd.glob("**/attempts/*/.lock"):
                    if _remove_if_stale(lock):
                        out["locks_removed"].append(lock.relative_to(root).as_posix())
        finally:
            fcntl.flock(guard, fcntl.LOCK_UN)
    return out
