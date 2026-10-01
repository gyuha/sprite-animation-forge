import json
import subprocess
import sys
import time

import pytest
from conftest import SCRIPTS

from sprite_forge import manifest as mf
from sprite_forge.errors import ForgeError

WORKER = """
import sys, time
sys.path.insert(0, {scripts!r})
from sprite_forge import manifest as mf
d, tag, start = sys.argv[1], sys.argv[2], float(sys.argv[3])
while time.time() < start:
    pass
for i in range({n}):
    mf.update(d, lambda m: m["actions"].__setitem__(f"{{tag}}{{i:02d}}", {{"kind": "body", "attempts": {{}}}}))
"""


def test_manifest_create_and_load(tmp_path):
    d = tmp_path / "hero"
    m = mf.create(d, "hero", {"view": "side"})
    assert m["character"] == "hero" and m["reference"] is None and m["actions"] == {}
    assert mf.load(d) == m
    with pytest.raises(ForgeError) as e:
        mf.create(d, "hero")
    assert e.value.code == "exists"


def test_manifest_load_missing_is_precondition_error(tmp_path):
    with pytest.raises(ForgeError) as e:
        mf.load(tmp_path / "nope")
    assert e.value.exit_code == 3 and e.value.code == "no_character"


def test_manifest_update_is_read_modify_write(tmp_path):
    d = tmp_path / "hero"
    mf.create(d, "hero")
    mf.update(d, lambda m: m["actions"].__setitem__("idle", {"kind": "body"}))
    mf.update(d, lambda m: m["actions"].__setitem__("walk", {"kind": "body"}))
    assert sorted(mf.load(d)["actions"]) == ["idle", "walk"]
    assert [p.name for p in d.iterdir() if p.name.startswith(".")] == []  # no temp leftovers


def test_manifest_update_failure_leaves_file_untouched(tmp_path):
    d = tmp_path / "hero"
    mf.create(d, "hero")
    before = (d / "manifest.json").read_bytes()

    def boom(m):
        m["actions"]["x"] = 1
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        mf.update(d, boom)
    assert (d / "manifest.json").read_bytes() == before


def test_manifest_two_processes_alternating_updates_lose_nothing(tmp_path):
    d = tmp_path / "hero"
    mf.create(d, "hero")
    n = 30
    code = WORKER.format(scripts=str(SCRIPTS), n=n)
    start = time.time() + 1.5
    procs = [subprocess.Popen([sys.executable, "-c", code, str(d), tag, str(start)]) for tag in ("a", "b")]
    for p in procs:
        assert p.wait() == 0
    actions = json.loads((d / "manifest.json").read_text())["actions"]
    assert len(actions) == 2 * n
    assert {f"a{i:02d}" for i in range(n)} | {f"b{i:02d}" for i in range(n)} == set(actions)


def test_manifest_unit_entry_defaults():
    m = {"actions": {}}
    e = mf.unit_entry(m, "walk/up", "body")
    assert e == {"kind": "body", "accepted_attempt": None, "forced": False, "attempts": {}}
    assert mf.unit_entry(m, "walk/up") is e
