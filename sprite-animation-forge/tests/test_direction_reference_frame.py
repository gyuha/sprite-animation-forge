"""Prompt/reference improvements: the direction reference is ONE adopted frame (not the whole raw sheet), walk/run
get in-place + no-crossing wording, many-frame actions warn."""

import json
import os
from pathlib import Path

import numpy as np
import pytest
from conftest import FORGE  # noqa: F401
from fixtures.synthetic.make import make_sheet
from PIL import Image

from sprite_forge import plan as plan_mod
from sprite_forge import prompt as pr

FAKE = Path(__file__).resolve().parent / "fixtures" / "fake_codex" / "codex"
PROFILE = {"identity": {"silhouette": "x"}}


def build(actions, view="side", **kw):
    return plan_mod.build_plan("hero", list(actions), view=view, art_style="project_native", has_reference=True,
                               profile=None, **kw)


# ---- prompt wording --------------------------------------------------------------------------

@pytest.mark.parametrize("action", ["walk", "run"])
def test_prompt_locomotion_is_described_as_walking_in_place(action):
    text = pr.build_prompt(build((action,)), PROFILE, action).text
    assert "as if on a treadmill" in text
    assert pr.validate_prompt(text) == []


@pytest.mark.parametrize("action", ["idle", "attack", "hurt", "jump"])
def test_prompt_treadmill_wording_is_only_for_walk_and_run(action):
    assert "treadmill" not in pr.build_prompt(build((action,)), PROFILE, action).text


@pytest.mark.parametrize("direction,crossing", [("down", True), ("up", True), ("right", False)])
def test_prompt_front_and_back_walks_forbid_crossing_feet(direction, crossing):
    p = build(("walk",), view="topdown")
    text = pr.build_prompt(p, PROFILE, "walk", direction).text
    assert ("never cross" in text) is crossing


def test_prompt_side_view_walk_has_no_crossing_rule():
    assert "never cross" not in pr.build_prompt(build(("walk",)), PROFILE, "walk").text


def test_prompt_direction_reference_block_talks_about_one_pose():
    assert "single pose" in pr._template("direction_reference.txt")


# ---- plan warning ----------------------------------------------------------------------------

def test_plan_warns_about_actions_with_eight_or_more_frames():
    p = build(("walk", "death"))  # death defaults to 8 frames
    assert any(n.startswith("frames_many: death") for n in p["assumptions"])
    assert not any("walk" in n and n.startswith("frames_many") for n in p["assumptions"])
    q = build(("walk",), overrides=plan_mod.parse_overrides(["walk.frames=7"]))
    assert not any(n.startswith("frames_many") for n in q["assumptions"])


# ---- the reference image itself --------------------------------------------------------------

@pytest.fixture(autouse=True)
def fake_env(tmp_path, monkeypatch):
    home = tmp_path / "codex_home"
    home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.setenv("SPRITE_FORGE_CODEX_BIN", str(FAKE))
    for k in [k for k in os.environ if k.startswith("FAKE_CODEX")]:
        monkeypatch.delenv(k)


def adopted_topdown(forge, tmp_path):
    ref = tmp_path / "ref.png"
    make_sheet("clean", rows=1, cols=1).save(ref)
    forge.ok("init", "hero", "--view", "topdown")
    forge.ok("reference", "import", "hero", ref)
    forge.ok("identity", "analyze", "hero")
    forge.ok("plan", "hero", "--actions", "walk")
    raw = tmp_path / "walk.png"
    make_sheet("clean", rows=2, cols=3).save(raw)
    forge.ok("import-raw", "hero", "walk", raw, "--direction", "down")
    forge.ok("process", "hero", "walk", "--direction", "down")
    forge.ok("accept", "hero", "walk", "--direction", "down")
    return forge.root / "hero"


def test_direction_reference_is_a_single_frame_on_the_key_colour(forge, tmp_path):
    cd = adopted_topdown(forge, tmp_path)
    forge.ok("generate", "hero", "walk", "--direction", "up")
    adir = cd / "walk/up/attempts/001"
    ref = Image.open(adir / "ref-02.png")
    assert ref.mode == "RGB" and max(ref.size) >= 256  # big enough for the model to read
    px = np.array(ref)
    assert tuple(px[0, 0]) == (255, 0, 255) and tuple(px[-1, -1]) == (255, 0, 255)  # flat key background
    foreground = np.any(px != (255, 0, 255), axis=2)
    cols = np.nonzero(foreground.any(axis=0))[0]
    assert (cols.max() - cols.min()) < 0.6 * ref.width  # one figure, not a row/grid of figures
    gen = json.loads((adir / "generation.json").read_text())
    assert gen["references"][1]["source"] == "walk/down/frames/000.png"


def test_direction_reference_needs_the_adopted_frames(forge, tmp_path):
    cd = adopted_topdown(forge, tmp_path)
    import shutil
    shutil.rmtree(cd / "walk/down/frames")  # accepted raw sheet alone is no longer enough
    code, out = forge.run("generate", "hero", "walk", "--direction", "up")
    assert (code, out["error_code"]) == (3, "no_direction_reference")
