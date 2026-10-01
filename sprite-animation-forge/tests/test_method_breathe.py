"""Generation method per action (grid | breathe | video) and the deterministic breathing idle."""

import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pytest
from conftest import FORGE  # noqa: F401  (ensures the shared fixtures are importable)
from fixtures.synthetic.make import make_sheet
from PIL import Image

from sprite_forge import plan as plan_mod
from sprite_forge import prompt as pr
from sprite_forge import schemas
from sprite_forge.effects.breathe import breathe_frames, find_neck
from sprite_forge.errors import ForgeError

FAKE = Path(__file__).resolve().parent / "fixtures" / "fake_codex" / "codex"


def build(actions=("idle", "walk"), **kw):
    return plan_mod.build_plan("hero", list(actions), view="side", art_style="project_native",
                               has_reference=True, profile=None, **kw)


# ---- plan / schema ---------------------------------------------------------------------------

def test_method_defaults_to_grid_for_every_action():
    p = build()
    assert {a: v["method"] for a, v in p["actions"].items()} == {"idle": "grid", "walk": "grid"}
    schemas.validate("animation-plan", p)


def test_method_breathe_override_switches_to_a_single_still_and_six_frames():
    p = build(overrides=plan_mod.parse_overrides(["idle.method=breathe"]))
    idle = p["actions"]["idle"]
    assert (idle["method"], idle["grid"], idle["frames"]) == ("breathe", "1x1", 6)
    assert p["actions"]["walk"]["method"] == "grid"
    schemas.validate("animation-plan", p)


def test_method_breathe_keeps_an_explicit_frame_count():
    p = build(overrides=plan_mod.parse_overrides(["idle.method=breathe", "idle.frames=8"]))
    assert (p["actions"]["idle"]["frames"], p["actions"]["idle"]["grid"]) == (8, "1x1")


@pytest.mark.parametrize("raw,code", [("method=nope", "invalid_override"), ("method=", "invalid_override")])
def test_method_rejects_unknown_values(raw, code):
    with pytest.raises(ForgeError) as e:
        plan_mod.parse_overrides([f"idle.{raw}"])
    assert e.value.code == code


def test_method_video_is_unavailable_until_a_video_provider_is_connected():
    with pytest.raises(ForgeError) as e:
        build(overrides=plan_mod.parse_overrides(["walk.method=video"]))
    assert e.value.code == "method_unavailable" and e.value.exit_code == 3


def test_method_breathe_is_not_allowed_for_fx_actions():
    with pytest.raises(ForgeError) as e:
        build(("idle", "spark"), overrides=plan_mod.parse_overrides(
            ["spark.kind=fx", "spark.motion=sparks", "spark.method=breathe"]))
    assert e.value.code == "invalid_params"


# ---- breathe effect --------------------------------------------------------------------------

def figure(head=12, neck=4, torso=40, legs=24, w_head=22, w_neck=8, w_torso=30, w_leg=10):
    """RGBA figure with a clear neck bottleneck, drawn on a 64x96 canvas, feet at row 90."""
    a = np.zeros((96, 64, 4), np.uint8)
    y = 90 - legs - torso - neck - head

    def box(y0, h, w, color):
        a[y0:y0 + h, 32 - w // 2:32 + w // 2] = (*color, 255)

    box(y, head, w_head, (230, 190, 150))
    box(y + head, neck, w_neck, (230, 190, 150))
    box(y + head + neck, torso, w_torso, (60, 150, 70))
    box(y + head + neck + torso, legs, w_leg * 2 + 4, (40, 40, 160))
    return a, y


def mask(a):
    return a[..., 3] >= 64


def test_breathe_finds_the_neck_bottleneck():
    a, top = figure()
    row, found = find_neck(a)
    assert found and top + 12 <= row <= top + 12 + 4 + 1  # inside the narrow band under the head


def test_breathe_makes_n_frames_and_the_first_one_is_the_still():
    a, _ = figure()
    frames, info = breathe_frames(a, 6)
    assert len(frames) == 6 and info["found"] is True
    assert np.array_equal(frames[0], a)


def test_breathe_head_is_only_translated_never_resampled():
    a, top = figure()
    frames, info = breathe_frames(a, 6)
    neck = info["neck_row"]
    head0 = a[top:neck]
    for f in frames:
        rows = np.nonzero(mask(f).any(axis=1))[0]
        new_top = rows.min()
        assert np.array_equal(f[new_top:new_top + (neck - top)], head0)


def test_breathe_feet_stay_on_the_baseline_and_the_body_height_changes_within_the_amplitude():
    a, top = figure()
    frames, info = breathe_frames(a, 6, amplitude=0.04)
    feet = {int(np.nonzero(mask(f).any(axis=1))[0].max()) for f in frames}
    assert feet == {int(np.nonzero(mask(a).any(axis=1))[0].max())}
    heights = [int(np.ptp(np.nonzero(mask(f).any(axis=1))[0])) + 1 for f in frames]
    base = heights[0]
    assert max(heights) != min(heights)
    assert all(abs(h - base) <= max(2, round(0.04 * base) + 1) for h in heights)


def test_breathe_is_a_loop_with_a_single_breath_and_is_deterministic():
    a, _ = figure()
    f1, info = breathe_frames(a, 8)
    f2, _ = breathe_frames(a, 8)
    assert all(np.array_equal(x, y) for x, y in zip(f1, f2))
    h = [int(np.ptp(np.nonzero(mask(f).any(axis=1))[0])) for f in f1]
    assert abs(h[0] - h[-1]) <= info["dh"]  # the last frame is one sine step away from the still: a seamless loop


def test_breathe_falls_back_to_a_fixed_split_with_a_warning_when_there_is_no_neck():
    a = np.zeros((96, 64, 4), np.uint8)
    a[10:90, 20:44] = (200, 60, 60, 255)  # a plain block: no bottleneck
    row, found = find_neck(a)
    assert not found and 10 < row < 90
    frames, info = breathe_frames(a, 6)
    assert info["found"] is False and "neck_not_found" in info["warnings"] and len(frames) == 6


def test_breathe_never_moves_the_head_out_of_the_canvas():
    a = np.zeros((40, 64, 4), np.uint8)
    a[0:10, 25:39] = (230, 190, 150, 255)   # head touches the top row
    a[10:14, 29:35] = (230, 190, 150, 255)  # neck
    a[14:38, 20:44] = (60, 150, 70, 255)    # body
    frames, _ = breathe_frames(a, 6, amplitude=0.2)
    head_pixels = int((a[..., 0] == 230).sum()) - 4 * 6  # head only (the 4x6 neck is part of the squashed body)
    for f in frames:
        assert int((f[..., 0] == 230).sum()) >= head_pixels  # nothing of the head was pushed off the canvas


# ---- prompt ----------------------------------------------------------------------------------

def test_method_breathe_prompt_asks_for_one_still_pose_on_a_1x1_grid():
    p = build(overrides=plan_mod.parse_overrides(["idle.method=breathe"]))
    text = pr.build_prompt(p, {"identity": {}}, "idle").text
    assert text.splitlines()[0].startswith("Create a 1x1 ")
    assert "single" in text.lower() and "still" in text.lower()
    assert pr.validate_prompt(text) == []
    grid_text = pr.build_prompt(build(), {"identity": {}}, "idle").text
    assert "still pose" not in grid_text


# ---- end to end through the CLI with the fake codex -----------------------------------------

@pytest.fixture
def fake_env(tmp_path, monkeypatch):
    home = tmp_path / "codex_home"
    home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.setenv("SPRITE_FORGE_CODEX_BIN", str(FAKE))
    for k in [k for k in os.environ if k.startswith("FAKE_CODEX")]:
        monkeypatch.delenv(k)
    monkeypatch.setenv("FAKE_CODEX_IMAGE", "clean")
    return home


def test_method_breathe_end_to_end_generate_process_accept(forge, tmp_path, fake_env):
    ref = tmp_path / "ref.png"
    make_sheet("clean", rows=1, cols=1).save(ref)
    forge.ok("init", "hero")
    forge.ok("reference", "import", "hero", ref)
    forge.ok("identity", "analyze", "hero")
    forge.ok("plan", "hero", "--actions", "idle,walk", "--set", "idle.method=breathe")
    gen = forge.ok("generate", "hero", "idle")
    raw = Image.open(forge.root / "hero/idle/attempts/001/raw.png")
    assert raw.size[0] == raw.size[1]  # one still (1x1), not a 2x2 sheet
    out = forge.ok("process", "hero", "idle")
    pj = json.loads((forge.root / "hero/idle/attempts/001/process.json").read_text())
    assert pj["params"]["method"] == "breathe" and pj["params"]["frames"] == 6
    assert len(pj["derived"]["frames"]) == 6
    assert len(list((forge.root / "hero/idle/attempts/001/frames").glob("*.png"))) == 6
    sheet = Image.open(forge.root / "hero/idle/attempts/001/sheet.png")
    assert sheet.size[0] == 6 * 128
    assert out["qc"]["status"] in ("pass", "warn", "fail")
    forge.ok("accept", "hero", "idle")
    assert gen["status"] == "succeeded"
    # deterministic: a second process of the same attempt gives the same frames
    h1 = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (forge.root / "hero/idle/attempts/001/frames").glob("*.png")}
    forge.ok("process", "hero", "idle")
    h2 = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (forge.root / "hero/idle/attempts/001/frames").glob("*.png")}
    assert h1 == h2


def test_method_video_cli_reports_method_unavailable(forge):
    forge.ok("init", "hero")
    code, out = forge.run("plan", "hero", "--actions", "walk", "--set", "walk.method=video")
    assert (code, out["error_code"]) == (3, "method_unavailable")
