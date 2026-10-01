"""File-system helpers: attempt numbers, locks, atomic writes, hashes (docs/08 sections 4 and 7).

Public API
----------
``allocate_attempt(attempts_dir) -> (number "NNN", Path)``  mkdir-atomic, safe across processes.
``latest_attempt(attempts_dir) -> str | None``
``file_lock(path)``      blocking exclusive ``fcntl.flock`` (used by the manifest).
``attempt_lock(dir)``    non-blocking ``<dir>/.lock``; raises ``ForgeError("busy")`` when held.
``atomic_write_bytes/text/json(path, ...)``, ``atomic_write_png(image, path)``  temp file + ``os.replace``.
``sha256_bytes(data)``, ``sha256_file(path)``  hex digests (no ``sha256:`` prefix).
``utc_now()``  ``YYYY-MM-DDTHH:MM:SSZ``.

Notes: ``fcntl`` is POSIX only (docs/08 section 7: Windows is out of MVP scope). PNGs are
written with ``optimize=False, compress_level=6`` and no metadata (docs/05 section 10).
"""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import io
import json
import os
import time
from pathlib import Path

from .errors import ForgeError

MAX_ATTEMPT = 999


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_write_bytes(path, data: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)


def atomic_write_text(path, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))


def atomic_write_json(path, data) -> None:
    atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def atomic_write_png(image, path) -> None:
    """``image`` is a PIL image."""
    buf = io.BytesIO()
    image.save(buf, format="PNG", optimize=False, compress_level=6)
    atomic_write_bytes(path, buf.getvalue())


@contextlib.contextmanager
def file_lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


@contextlib.contextmanager
def attempt_lock(attempt_dir):
    with open(Path(attempt_dir) / ".lock", "a+") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ForgeError("busy", f"{attempt_dir} is being processed by another process") from None
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _numbers(attempts_dir: Path) -> list[int]:
    if not attempts_dir.is_dir():
        return []
    return [int(p.name) for p in attempts_dir.iterdir() if p.is_dir() and p.name.isdigit() and len(p.name) == 3]


def latest_attempt(attempts_dir) -> str | None:
    nums = _numbers(Path(attempts_dir))
    return f"{max(nums):03d}" if nums else None


def allocate_attempt(attempts_dir) -> tuple[str, Path]:
    """Create ``attempts_dir/NNN`` for the next free number (docs/08 section 4)."""
    attempts_dir = Path(attempts_dir)
    attempts_dir.mkdir(parents=True, exist_ok=True)
    n = max(_numbers(attempts_dir), default=0) + 1
    while n <= MAX_ATTEMPT:
        path = attempts_dir / f"{n:03d}"
        try:
            os.mkdir(path)
        except FileExistsError:
            n += 1  # created concurrently: try the next number
            continue
        return f"{n:03d}", path
    raise ForgeError("too_many_attempts", f"more than {MAX_ATTEMPT} attempts in {attempts_dir}")
