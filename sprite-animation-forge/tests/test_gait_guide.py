"""Gait guide (forge task #42): a deterministic stick-figure sheet laid out like the walk's grid, one evenly timed pose per
cell, attached as the second reference of a side-view walk so the model sees the poses instead of only reading them."""

import json
import os
from pathlib import Path

import numpy as np
import pytest
from fixtures.synthetic.make import make_sheet
from PIL import Image
from scipy import ndimage
from test_prompt import PROFILE, SNAP_DIR, side_plan, topdown_plan

from sprite_forge import gait_guide as gg
from sprite_forge import prompt as pr
from sprite_forge import qc_motion as qm

FAKE = Path(__file__).resolve().parent / "fixtures" / "fake_codex" / "codex"
KEY = "#FF00FF"
KEY_RGB = (255, 0, 255)


def cells(img, rows=2, cols=3):
    a = np.asarray(img.convert("RGB"))
    h, w = a.shape[0] // rows, a.shape[1] // cols
    return [a[r * h:(r + 1) * h, c * w:(c + 1) * w] for r in range(rows) for c in range(cols)]


def figure_mask(cell):
    return np.any(cell != KEY_RGB, axis=2)


# ---- the image -------------------------------------------------------------------------------

def test_gait_guide_is_deterministic_and_sized_like_the_grid():
    a, b = gg.make_gait_guide(KEY, 2, 3, 6), gg.make_gait_guide(KEY, 2, 3, 6)
    assert a.tobytes() == b.tobytes()
    assert a.size == (3 * gg.CELL, 2 * gg.CELL) and a.mode == "RGB"


def test_gait_guide_has_one_stick_figure_per_cell_on_the_key_colour():
    for i, cell in enumerate(cells(gg.make_gait_guide(KEY, 2, 3, 6))):
        mask = figure_mask(cell)
        assert ndimage.label(mask)[1] == 1, i
        assert mask.mean() < 0.2, i                                      # thin lines on a key canvas
        assert tuple(cell[0, 0]) == KEY_RGB and tuple(cell[-1, -1]) == KEY_RGB, i  # no border, no grid line


def test_gait_guide_uses_only_the_key_colour_and_three_grays():
    colours = {tuple(c) for c in np.asarray(gg.make_gait_guide(KEY, 2, 3, 6)).reshape(-1, 3)}
    assert colours == {KEY_RGB, gg.LEFT_RGB, gg.RIGHT_RGB, gg.BODY_RGB}


def test_gait_guide_draws_the_left_limbs_dark_and_the_right_limbs_light_in_every_cell():
    for i, cell in enumerate(cells(gg.make_gait_guide(KEY, 2, 3, 6))):
        flat = {tuple(c) for c in cell.reshape(-1, 3)}
        assert gg.LEFT_RGB in flat and gg.RIGHT_RGB in flat, i
    assert sum(gg.LEFT_RGB) < sum(gg.BODY_RGB) < sum(gg.RIGHT_RGB)


def test_gait_guide_poses_are_themselves_evenly_timed():
    frames = []
    for cell in cells(gg.make_gait_guide(KEY, 2, 3, 6)):
        rgba = np.zeros((*cell.shape[:2], 4), np.uint8)
        rgba[..., :3] = cell
        rgba[..., 3] = np.where(figure_mask(cell), 255, 0)
        frames.append(rgba)
    value = qm.gait_phase_deviation(frames, "side")
    assert value is not None and value < 0.1


def test_gait_guide_frame_one_has_the_left_foot_forward_and_frame_four_the_right():
    c1, c4 = cells(gg.make_gait_guide(KEY, 2, 3, 6))[0], cells(gg.make_gait_guide(KEY, 2, 3, 6))[3]

    def lowest_x(cell, rgb):
        ys, xs = np.nonzero(np.all(cell == rgb, axis=2))
        return xs[ys == ys.max()].mean()

    assert lowest_x(c1, gg.LEFT_RGB) > lowest_x(c1, gg.RIGHT_RGB)  # facing right: forward = larger x
    assert lowest_x(c4, gg.RIGHT_RGB) > lowest_x(c4, gg.LEFT_RGB)


def test_gait_guide_facing_left_is_the_mirror_image():
    right, left = gg.make_gait_guide(KEY, 2, 3, 6), gg.make_gait_guide(KEY, 2, 3, 6, facing="left")
    for r, l in zip(cells(right), cells(left)):
        assert np.array_equal(r[:, ::-1], l)


# ---- when it is attached ---------------------------------------------------------------------

def test_gait_guide_a_side_walk_attaches_it_as_the_second_image():
    res = pr.build_prompt(side_plan("walk"), PROFILE, "walk")
    assert res.references_needed == ["character", "gait_guide"]
    assert "GAIT GUIDE" in res.text and "second attached image" in res.text and "Never draw" in res.text
    assert res.template_version == pr.GAIT_PROMPT_VERSION and pr.validate_prompt(res.text) == []
    assert "gait_guide_skipped" not in res.warnings


def test_gait_guide_is_skipped_with_a_warning_when_two_references_are_already_needed():
    res = pr.build_prompt(topdown_plan("idle", "walk"), PROFILE, "walk", "right")
    assert res.references_needed[1].startswith("direction:") and len(res.references_needed) == 2
    assert "gait_guide_skipped" in res.warnings
    before = (SNAP_DIR / "walk_topdown_right_action_prompt_5.txt").read_text(encoding="utf-8")
    assert res.text == before and res.template_version == pr.PROMPT_TEMPLATE_VERSION  # byte for byte as in part 1/2


@pytest.mark.parametrize("direction", ["down", "up"])
def test_gait_guide_front_and_back_walks_get_none(direction):
    plan = topdown_plan("walk")
    res = pr.build_prompt(plan, PROFILE, "walk", direction)
    assert "gait_guide" not in res.references_needed and "GAIT GUIDE" not in res.text
    assert "gait_guide_skipped" not in res.warnings


@pytest.mark.parametrize("action", ["run", "idle", "attack"])
def test_gait_guide_other_actions_get_none(action):
    res = pr.build_prompt(side_plan(action), PROFILE, action)
    assert "gait_guide" not in res.references_needed and "GAIT GUIDE" not in res.text


def test_gait_guide_a_walk_with_another_frame_count_gets_none():
    plan = side_plan("walk")
    plan["actions"]["walk"].update(frames=8, grid="2x4")
    res = pr.build_prompt(plan, PROFILE, "walk")
    assert "gait_guide" not in res.references_needed and res.template_version == pr.PROMPT_TEMPLATE_VERSION


# ---- attached through the codex provider (fake codex) ----------------------------------------

@pytest.fixture
def hero(forge, tmp_path, monkeypatch):
    home = tmp_path / "codex_home"
    home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.setenv("SPRITE_FORGE_CODEX_BIN", str(FAKE))
    for k in [k for k in os.environ if k.startswith("FAKE_CODEX")]:
        monkeypatch.delenv(k)
    monkeypatch.setenv("FAKE_CODEX_IMAGE", "clean")
    ref = tmp_path / "ref.png"
    make_sheet("clean", rows=1, cols=1).save(ref)
    forge.ok("init", "hero")
    forge.ok("reference", "import", "hero", ref)
    forge.ok("identity", "analyze", "hero")
    return forge


def test_gait_guide_generate_attaches_the_guide_for_a_side_walk(hero):
    hero.ok("plan", "hero", "--actions", "idle,walk")
    out = hero.ok("generate", "hero", "walk")
    adir = hero.root / "hero/walk/attempts" / out["attempt"]
    assert sorted(p.name for p in adir.glob("ref-*.png")) == ["ref-01.png", "ref-02.png"]
    plan = json.loads((hero.root / "hero/animation-plan.json").read_text())
    act = plan["actions"]["walk"]
    rows, cols = (int(x) for x in act["grid"].split("x"))
    expected = gg.make_gait_guide(plan["key_color"], rows, cols, act["frames"], facing=plan["facing"])
    assert Image.open(adir / "ref-02.png").convert("RGB").tobytes() == expected.tobytes()
    gen = json.loads((adir / "generation.json").read_text())
    assert [r["source"] for r in gen["references"]] == ["reference/character-keyed.png", "gait-guide"]
    assert gen["prompt_template_version"] == pr.GAIT_PROMPT_VERSION and "GAIT GUIDE" in (adir / "prompt.txt").read_text()
