import json
import subprocess
import sys
import time

import pytest
from conftest import SCRIPTS

from sprite_forge import fsutil
from sprite_forge.errors import ForgeError

WORKER = """
import sys, time
sys.path.insert(0, {scripts!r})
from sprite_forge.fsutil import allocate_attempt
start = float(sys.argv[2])
while time.time() < start:
    pass
print(" ".join(allocate_attempt(sys.argv[1])[0] for _ in range({n})))
"""


def test_fsutil_allocate_attempt_sequential(tmp_path):
    d = tmp_path / "attempts"
    assert [fsutil.allocate_attempt(d)[0] for _ in range(3)] == ["001", "002", "003"]
    assert fsutil.latest_attempt(d) == "003"
    assert (d / "002").is_dir()


def test_fsutil_latest_attempt_empty(tmp_path):
    assert fsutil.latest_attempt(tmp_path / "none") is None


def test_fsutil_allocate_attempt_ignores_non_numbered_dirs(tmp_path):
    d = tmp_path / "attempts"
    (d / "notes").mkdir(parents=True)
    (d / "007").mkdir()
    assert fsutil.allocate_attempt(d)[0] == "008"


def test_fsutil_allocate_attempt_two_processes_no_collision(tmp_path):
    d = tmp_path / "attempts"
    n = 25
    code = WORKER.format(scripts=str(SCRIPTS), n=n)
    start = time.time() + 1.5
    procs = [
        subprocess.Popen([sys.executable, "-c", code, str(d), str(start)], stdout=subprocess.PIPE, text=True)
        for _ in range(2)
    ]
    outs = [p.communicate()[0].split() for p in procs]
    assert all(p.returncode == 0 for p in procs)
    allocated = outs[0] + outs[1]
    assert len(allocated) == 2 * n
    assert len(set(allocated)) == 2 * n  # no number handed out twice
    assert sorted(allocated) == [f"{i:03d}" for i in range(1, 2 * n + 1)]


def test_fsutil_allocate_attempt_limit(tmp_path):
    d = tmp_path / "attempts"
    (d / "999").mkdir(parents=True)
    with pytest.raises(ForgeError) as e:
        fsutil.allocate_attempt(d)
    assert e.value.code == "too_many_attempts"


def test_fsutil_atomic_write_replaces_and_leaves_no_temp(tmp_path):
    p = tmp_path / "sub" / "a.json"
    fsutil.atomic_write_json(p, {"a": 1})
    fsutil.atomic_write_json(p, {"a": 2, "k": "한글"})
    assert json.loads(p.read_text(encoding="utf-8")) == {"a": 2, "k": "한글"}
    assert [x.name for x in p.parent.iterdir()] == ["a.json"]


def test_fsutil_atomic_write_failure_keeps_old_file(tmp_path):
    p = tmp_path / "a.txt"
    fsutil.atomic_write_text(p, "old")
    with pytest.raises(TypeError):
        fsutil.atomic_write_bytes(p, "not bytes")  # type: ignore[arg-type]
    assert p.read_text() == "old"
    assert [x.name for x in tmp_path.iterdir()] == ["a.txt"]


def test_fsutil_sha256_helpers(tmp_path):
    p = tmp_path / "f"
    p.write_bytes(b"abc")
    expected = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert fsutil.sha256_bytes(b"abc") == expected
    assert fsutil.sha256_file(p) == expected


def test_fsutil_attempt_lock_busy_when_held(tmp_path):
    d = tmp_path / "001"
    d.mkdir()
    with fsutil.attempt_lock(d):
        code = (
            f"import sys; sys.path.insert(0, {str(SCRIPTS)!r})\n"
            "from sprite_forge.fsutil import attempt_lock\n"
            "from sprite_forge.errors import ForgeError\n"
            "try:\n"
            f"    with attempt_lock({str(d)!r}): print('acquired')\n"
            "except ForgeError as e: print(e.code)\n"
        )
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True).stdout.strip()
        assert out == "busy"
    with fsutil.attempt_lock(d):  # released afterwards
        pass
