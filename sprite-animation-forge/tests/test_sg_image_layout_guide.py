"""Layout guide + safe area for single-still generation (docs/14 area B): the guide image is a flat key canvas with a safe-area
outline and head / feet lines; the still prompt gives the same numbers and attaches the guide as the second reference."""

import json
import os
from pathlib import Path

import numpy as np
import pytest
from fixtures.synthetic.make import make_sheet
from PIL import Image
from sprite_forge import layout_guide as lg
from sprite_forge import plan as plan_mod
from sprite_forge import prompt as pr

FAKE = Path(__file__).resolve().parent / "fixtures" / "fake_codex" / "codex"
KEY = "#FF00FF"
SNAP = Path(__file__).resolve().parent / "snapshots" / "idle_breathe_guide.txt"


def breathe_plan(view="side", **kw):
    return plan_mod.build_plan("hero", ["idle"], view=view, art_style="project_native", has_reference=True, profile=None,
                               overrides=plan_mod.parse_overrides(["idle.method=breathe"]), **kw)


def rows_with(img, predicate):
    return [y for y in range(img.shape[0]) if predicate(img[y])]


def test_sg_image_guide_is_a_key_canvas_with_a_safe_outline_and_head_and_feet_lines():
    img = np.asarray(lg.make_layout_guide(KEY, 8, 512).convert("RGB"))
    key = np.array([255, 0, 255])
    assert img.shape == (512, 512, 3) and (img[0, 0] == key).all() and (img[-1, -1] == key).all()
    not_key = lambda row: (row != key).any(axis=1)  # noqa: E731
    drawn = rows_with(img, lambda r: not_key(r).any())
    band = lambda y: [v for v in drawn if abs(v - y) <= 1]  # noqa: E731
    top, bottom, crown, floor = (round(512 * p / 100) for p in (8, 92, 16, 84))
    assert band(top) and band(bottom) and band(crown) and band(floor)
    assert min(drawn) >= top - 2 and max(drawn) <= bottom + 2  # nothing outside the safe area
    inner = [v for v in drawn if top + 3 < v < bottom - 3 and abs(v - crown) > 2 and abs(v - floor) > 2]
    assert len(inner) == 0 or all(not_key(img[v]).sum() <= 6 for v in inner)  # between the lines only the outline's sides


def test_sg_image_guide_head_and_feet_lines_span_the_safe_box_and_outline_differs_from_them():
    img = np.asarray(lg.make_layout_guide(KEY, 8, 512).convert("RGB"))
    crown_y, floor_y = round(512 * 16 / 100), round(512 * 84 / 100)
    x0, x1 = round(512 * 8 / 100), round(512 * 92 / 100)
    assert (img[crown_y, x0 + 4:x1 - 3] == lg.LINE_RGB).all() and (img[floor_y, x0 + 4:x1 - 3] == lg.LINE_RGB).all()
    assert tuple(img[round(512 * 8 / 100), 256]) == lg.OUTLINE_RGB and lg.OUTLINE_RGB != lg.LINE_RGB
    assert lg.LINE_RGB != (255, 0, 255) and lg.OUTLINE_RGB != (255, 0, 255)


def test_sg_image_guide_is_deterministic_and_follows_the_margin():
    a, b = lg.make_layout_guide(KEY, 8, 256), lg.make_layout_guide(KEY, 8, 256)
    assert a.tobytes() == b.tobytes()
    assert lg.safe_area(8) == (8, 92, 16, 84) and lg.safe_area(15) == (15, 85, 30, 70)
    wide = np.asarray(lg.make_layout_guide(KEY, 15, 512).convert("RGB"))
    assert (wide[round(512 * 30 / 100), 256] == lg.LINE_RGB).all()


def test_sg_image_still_prompt_gives_the_safe_area_numbers_and_asks_for_the_guide_as_the_second_image():
    res = pr.build_prompt(breathe_plan(), None, "idle")
    assert res.references_needed == ["character", "layout_guide"] and res.template_version == pr.STILL_PROMPT_VERSION
    assert "LAYOUT GUIDE" in res.text and "8% to 92%" in res.text and "16% from the top" in res.text and "84% from the top" in res.text
    assert "second attached image" in res.text and "Never draw" in res.text
    assert pr.validate_prompt(res.text) == [] and "layout_guide_skipped" not in res.warnings


def test_sg_image_edge_touch_recovery_widens_the_safe_area_in_the_prompt_and_in_the_guide():
    res = pr.build_prompt(breathe_plan(), None, "idle", recovery=["edge_touch"])
    assert "15% to 85%" in res.text and "30% from the top" in res.text and "70% from the top" in res.text


def test_sg_image_a_grid_prompt_is_unchanged_and_has_no_guide():
    plan = plan_mod.build_plan("hero", ["idle"], view="side", art_style="project_native", has_reference=True, profile=None)
    res = pr.build_prompt(plan, None, "idle")
    assert res.references_needed == ["character"] and "LAYOUT GUIDE" not in res.text
    assert res.template_version == pr.PROMPT_TEMPLATE_VERSION


def test_sg_image_a_still_that_already_has_two_references_skips_the_guide_with_a_warning():
    plan = breathe_plan("topdown", directions=["down", "right", "up", "left"], mirror=True)
    res = pr.build_prompt(plan, None, "idle", "right")
    assert res.references_needed[0] == "character" and len(res.references_needed) == 2 and res.references_needed[1].startswith("direction:")
    assert "layout_guide_skipped" in res.warnings and "LAYOUT GUIDE" not in res.text
    assert res.template_version == pr.PROMPT_TEMPLATE_VERSION  # the old still prompt, byte for byte


def test_sg_image_still_prompt_snapshot():
    body = f"# template_version: {pr.STILL_PROMPT_VERSION}\n{pr.build_prompt(breathe_plan(), None, 'idle').text}"
    if os.environ.get("UPDATE_SNAPSHOTS") == "1":
        SNAP.write_text(body, encoding="utf-8")
    assert SNAP.exists(), "missing snapshot; run with UPDATE_SNAPSHOTS=1"
    assert SNAP.read_text(encoding="utf-8") == body


# ---- attached through the codex provider (fake codex) ------------------------------------------------------

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


def test_sg_image_generate_attaches_the_guide_as_the_second_reference_for_a_still(hero):
    hero.ok("plan", "hero", "--actions", "idle,walk", "--set", "idle.method=breathe")
    out = hero.ok("generate", "hero", "idle")
    adir = hero.root / "hero/idle/attempts" / out["attempt"]
    assert sorted(p.name for p in adir.glob("ref-*.png")) == ["ref-01.png", "ref-02.png"]
    key_hex = json.loads((hero.root / "hero/animation-plan.json").read_text())["key_color"]
    expected = lg.make_layout_guide(key_hex, 8, lg.GUIDE_SIZE).convert("RGB")
    assert Image.open(adir / "ref-02.png").convert("RGB").tobytes() == expected.tobytes()
    gen = json.loads((adir / "generation.json").read_text())
    assert [r["source"] for r in gen["references"]] == ["reference/character-keyed.png", "layout-guide"]
    assert gen["prompt_template_version"] == pr.STILL_PROMPT_VERSION and "LAYOUT GUIDE" in (adir / "prompt.txt").read_text()


def test_sg_image_generate_attaches_one_reference_for_a_grid_action(hero):
    hero.ok("plan", "hero", "--actions", "idle,walk", "--set", "idle.method=breathe")
    out = hero.ok("generate", "hero", "walk")
    adir = hero.root / "hero/walk/attempts" / out["attempt"]
    assert [p.name for p in adir.glob("ref-*.png")] == ["ref-01.png"]
