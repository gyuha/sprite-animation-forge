"""Acceptance scenarios 1, 3, 6 end-to-end through export, plus Skill self-containment (docs/11 section 5).

Every Codex call goes through the fake codex (SPRITE_FORGE_CODEX_BIN); live runs stay in test_live_contract.py.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from fixtures.synthetic.make import make_sheet
from PIL import Image

from sprite_forge import schemas

FAKE = Path(__file__).resolve().parent / "fixtures" / "fake_codex" / "codex"
SKILL_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SKILL_DIR.parent
GRIDS = {"idle": "2x2", "walk": "2x3", "run": "2x3", "attack": "2x3"}


@pytest.fixture(autouse=True)
def fake_env(tmp_path, monkeypatch):
    home = tmp_path / "codex_home"
    home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.setenv("SPRITE_FORGE_CODEX_BIN", str(FAKE))
    for k in [k for k in os.environ if k.startswith("FAKE_CODEX")]:
        monkeypatch.delenv(k)
    monkeypatch.setenv("FAKE_CODEX_CALL_LOG", str(tmp_path / "codex_calls.log"))
    return home


def codex_calls(tmp_path) -> int:
    log = tmp_path / "codex_calls.log"
    return len(log.read_text().splitlines()) if log.exists() else 0


def start(forge, tmp_path, *init_args):
    ref = tmp_path / "ref.png"
    make_sheet("clean", rows=1, cols=1, cell_size=(300, 300)).save(ref)
    forge.ok("init", "hero", *init_args)
    forge.ok("reference", "import", "hero", ref)
    forge.ok("identity", "analyze", "hero")


def run_unit(forge, monkeypatch, action, *direction):
    """generate (fake codex) -> process -> accept for one unit; returns the process and accept outputs."""
    monkeypatch.setenv("FAKE_CODEX_GRID", GRIDS[action])
    assert forge.ok("generate", "hero", action, *direction)["status"] == "succeeded"
    processed = forge.ok("process", "hero", action, *direction)
    return processed, forge.ok("accept", "hero", action, *direction)


def frame_names(atlas_json):
    return set(atlas_json["frames"])


def test_scenario_1_idle_export_through_fake_codex(forge, tmp_path, monkeypatch):
    start(forge, tmp_path)
    forge.ok("plan", "hero", "--actions", "idle")
    processed, accepted = run_unit(forge, monkeypatch, "idle")
    assert processed["qc"]["status"] in ("pass", "warn") and accepted["accepted"] == "001"
    out = forge.ok("export", "hero", "--engine", "phaser")
    assert out["warnings"] == []

    cd = forge.root / "hero"
    idle = cd / "idle"
    assert sorted(p.name for p in (idle / "frames").glob("*.png")) == [f"{i:03d}.png" for i in range(4)]
    sheet = Image.open(idle / "sheet.png").convert("RGBA")
    w, h = sheet.size
    assert all(sheet.getpixel(xy)[3] == 0 for xy in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)))
    assert (cd / "preview/idle.gif").exists()
    schemas.validate("qc-report", json.loads((idle / "qc-report.json").read_text()))
    assert json.loads((cd / "animations.json").read_text())["idle"]["frames"] == [f"idle_{i}" for i in range(4)]


def test_scenario_3_hero_bundle_export_phaser(forge, tmp_path, monkeypatch):
    start(forge, tmp_path)
    plan = forge.ok("plan", "hero", "--actions", "idle,walk,run,attack")["plan"]
    for action in plan["order"]:
        run_unit(forge, monkeypatch, action)
    assert codex_calls(tmp_path) == 4
    out = forge.ok("export", "hero", "--engine", "phaser")
    assert out["warnings"] == []

    cd = forge.root / "hero"
    for rel in ("atlas/hero.png", "atlas/hero.json", "atlas/hero.generic.json", "atlas/hero.meta.json",
                "animations.json", "qc-report.json", "manifest.json"):
        assert (cd / rel).exists(), rel
    atlas_json = json.loads((cd / "atlas/hero.json").read_text())
    anims = json.loads((cd / "animations.json").read_text())
    assert list(anims) == ["idle", "walk", "run", "attack"]
    expected = {"idle": 4, "walk": 6, "run": 6, "attack": 6}
    names = frame_names(atlas_json)
    assert len(names) == sum(expected.values())
    for action, n in expected.items():
        assert anims[action]["frames"] == [f"{action}_{i}" for i in range(n)]
        assert anims[action]["repeat"] == (0 if action == "attack" else -1)
        assert (cd / f"preview/{action}.gif").exists()
    assert names == {f for a in anims.values() for f in a["frames"]}
    tex = Image.open(cd / "atlas/hero.png")
    assert list(tex.size) == [atlas_json["meta"]["size"]["w"], atlas_json["meta"]["size"]["h"]]
    for fr in atlas_json["frames"].values():
        r = fr["frame"]
        assert r["x"] + r["w"] <= tex.size[0] and r["y"] + r["h"] <= tex.size[1]
    schemas.validate("qc-report", json.loads((cd / "idle/qc-report.json").read_text()))
    root_qc = json.loads((cd / "qc-report.json").read_text())
    assert set(root_qc["actions"]) == set(expected) and root_qc["forced_accepts"] == []
    schemas.validate("manifest", json.loads((cd / "manifest.json").read_text()))


def unit_body_heights(frames_dir: Path) -> list[int]:
    heights = []
    for p in sorted(frames_dir.glob("[0-9]*.png")):
        box = Image.open(p).convert("RGBA").getchannel("A").point(lambda a: 255 if a >= 128 else 0).getbbox()
        heights.append(box[3] - box[1])
    return heights


def test_scenario_6_topdown_4_directions_export(forge, tmp_path, monkeypatch):
    start(forge, tmp_path, "--view", "topdown")
    plan = forge.ok("plan", "hero", "--actions", "idle,walk")["plan"]
    assert plan["directions"] == ["down", "up", "right", "left"] and plan["mirror"] == {"left": "right"}
    generated = 0
    for action in ("idle", "walk"):
        for direction in ("down", "up", "right"):
            _, accepted = run_unit(forge, monkeypatch, action, "--direction", direction)
            generated += 1
            assert accepted["unit"] == f"{action}/{direction}"
            if direction == "right":
                assert accepted["mirrored"] == [f"{action}/left"]
    # left never reached Codex: one call per generate, none for the mirrored direction
    assert generated == 6 and codex_calls(tmp_path) == generated
    code, err = forge.run("generate", "hero", "walk", "--direction", "left")
    assert code == 1 and err["error_code"] == "mirrored_direction"
    assert codex_calls(tmp_path) == generated

    out = forge.ok("export", "hero", "--engine", "phaser")
    assert out["warnings"] == []
    cd = forge.root / "hero"

    for action in ("idle", "walk"):
        right = sorted((cd / action / "right/frames").glob("[0-9]*.png"))
        left = sorted((cd / action / "left/frames").glob("[0-9]*.png"))
        assert len(right) == len(left) > 0
        for r, l in zip(right, left):
            ra = np.array(Image.open(r).convert("RGBA"))
            assert np.array_equal(np.array(Image.open(l).convert("RGBA")), np.fliplr(ra))
        assert json.loads((cd / action / "left/mirror.json").read_text())["source"] == "right"
        assert not (cd / action / "left/attempts").exists()

    atlas_json = json.loads((cd / "atlas/hero.json").read_text())
    names = frame_names(atlas_json)
    for d in ("down", "up", "right", "left"):
        assert {f"walk_{d}_{i}" for i in range(6)} <= names
        assert {f"idle_{d}_{i}" for i in range(4)} <= names
    assert len(names) == 4 * (4 + 6)
    anims = json.loads((cd / "animations.json").read_text())
    assert sorted(anims) == sorted(f"{a}_{d}" for a in ("idle", "walk") for d in ("down", "up", "right", "left"))
    assert len(anims) == 8
    assert anims["walk_left"]["frames"] == [f"walk_left_{i}" for i in range(6)]
    for key in ("idle_down", "walk_up"):
        assert (cd / f"preview/{key}.gif").exists()

    # one shared scale profile: per-direction median body height stays within 10 percent
    profile = json.loads((cd / "character-scale-profile.json").read_text())
    medians = {d: float(np.median(unit_body_heights(cd / "walk" / d / "frames"))) for d in ("down", "up", "right", "left")}
    assert (max(medians.values()) - min(medians.values())) / max(medians.values()) <= 0.10, medians
    for m in medians.values():
        assert abs(m - profile["body_height"]) / profile["body_height"] <= 0.10, (m, profile["body_height"])


def test_skill_self_contained_copy_runs_cli(tmp_path):
    copy = tmp_path / "skill_copy"
    shutil.copytree(SKILL_DIR, copy, ignore=shutil.ignore_patterns("__pycache__", "tests", ".pytest_cache"))
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    forge_py = copy / "scripts" / "forge.py"
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    commands = ("doctor", "init", "reference", "identity", "plan", "prompt", "generate", "import-raw",
                "process", "accept", "export", "status")

    # run the COPIED forge.py in-process (runpy) so we can report where sprite_forge was imported from
    runner = (
        "import runpy, sys\n"
        f"sys.argv = [{str(forge_py)!r}, '--help']\n"
        "code = 0\n"
        f"try: runpy.run_path({str(forge_py)!r}, run_name='__main__')\n"
        "except SystemExit as e: code = e.code or 0\n"
        "import sprite_forge\n"
        "print('SPRITE_FORGE_FILE=' + sprite_forge.__file__)\n"
        "sys.exit(code)\n"
    )
    proc = subprocess.run([sys.executable, "-c", runner], cwd=outside, env=env, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    loaded = next(ln for ln in proc.stdout.splitlines() if ln.startswith("SPRITE_FORGE_FILE="))
    assert Path(loaded.split("=", 1)[1]).resolve().is_relative_to(copy.resolve())
    for cmd in commands:
        assert cmd in proc.stdout, cmd

    # the documented invocation: uv run --project <repo root> python <copy>/scripts/forge.py --help
    if shutil.which("uv"):
        helped = subprocess.run(["uv", "run", "--project", str(REPO_ROOT), "python", str(forge_py), "--help"],
                                cwd=outside, env=env, capture_output=True, text=True)
        assert helped.returncode == 0, helped.stderr
        for cmd in commands:
            assert cmd in helped.stdout, cmd


def test_skill_package_files():
    text = (SKILL_DIR / "SKILL.md").read_text()
    assert text.startswith("---\n")
    front = text.split("---\n", 2)[1]
    assert "name: sprite-animation-forge" in front and "description:" in front
    assert sorted(p.name for p in (SKILL_DIR / "references").iterdir()) == sorted([
        "animation-rules.md", "prompt-rules.md", "character-consistency.md", "qc-rules.md",
        "codex-image.md", "phaser-export.md", "examples.md"])
    assert (SKILL_DIR / "LICENSE").read_text().startswith("MIT License")
