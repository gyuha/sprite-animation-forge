"""Video prompts by view and the first-frame canvas by action (docs/14 area C)."""

import io
import os
import shutil
from pathlib import Path

import numpy as np
import pytest
from fixtures.synthetic.make import make_sheet
from PIL import Image
from sprite_forge import plan as plan_mod
from sprite_forge import prompt as pr
from sprite_forge import video_sprite as vs

FAKE = Path(__file__).resolve().parent / "fixtures" / "fake_codex" / "codex"
needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None, reason="ffmpeg missing")
KEY = "#FF00FF"
CALM = "small, calm steps"


@pytest.fixture(autouse=True)
def video_provider(monkeypatch):
    monkeypatch.setenv("SPRITE_FORGE_VIDEO_PROVIDER", "fake")  # a plan may only choose method=video when a provider is connected


def video_prompt(action="walk", view="side", sets=(), direction=None, **kw):
    plan = plan_mod.build_plan("hero", [action], view=view, art_style="project_native", has_reference=True, profile=None,
                               directions=[direction] if direction else None,
                               overrides=plan_mod.parse_overrides([f"{action}.method=video", *sets]), **kw)
    return pr.build_video_prompt(plan, None, action)


def test_sg_video_prompt_version_is_bumped():
    assert pr.VIDEO_PROMPT_VERSION == "video_prompt@2" and video_prompt().template_version == "video_prompt@2"


@pytest.mark.parametrize("action", ["walk", "run"])
def test_sg_video_prompt_walk_and_run_move_in_place_like_on_a_treadmill_in_every_view(action):
    for view, direction in (("side", None), ("front", None), ("rear", None), ("topdown", "down"), ("topdown", "up")):
        text = video_prompt(action, view, direction=direction).text
        assert "as if on a treadmill" in text and "ground does not scroll" in text, (view, direction)


def test_sg_video_prompt_side_views_have_no_front_or_back_gait_line():
    text = video_prompt("walk", "side").text
    assert CALM not in text and "toward the viewer" not in text and "away from the viewer" not in text


@pytest.mark.parametrize("view,direction,words", [("front", None, "toward the viewer"), ("topdown", "down", "toward the viewer"),
                                                  ("rear", None, "away from the viewer"), ("topdown", "up", "away from the viewer")])
def test_sg_video_prompt_front_and_back_walks_take_small_calm_steps_and_say_which_way(view, direction, words):
    text = video_prompt("walk", view, direction=direction).text
    assert CALM in text and "never kick out" in text and words in text


@pytest.mark.parametrize("view,direction,words", [("front", None, "toward the viewer"), ("rear", None, "away from the viewer")])
def test_sg_video_prompt_front_and_back_runs_say_which_way(view, direction, words):
    text = video_prompt("run", view, direction=direction).text
    assert words in text and "legs stay under the body" in text


def test_sg_video_prompt_a_callers_own_gait_is_kept_and_not_overridden():
    own = "a heavy limping walk, dragging the left foot"
    text = video_prompt("walk", "front", sets=[f"walk.motion={own}"]).text
    assert own in text and CALM not in text  # the caller's gait stands alone ...
    assert "as if on a treadmill" in text     # ... but it still happens in place


@pytest.mark.parametrize("action", ["attack", "idle", "hurt"])
def test_sg_video_prompt_other_actions_get_no_locomotion_lines(action):
    text = video_prompt(action, "front").text
    assert "treadmill" not in text and CALM not in text


# ---- first-frame canvas -----------------------------------------------------------------------------------

def character_png(tmp_path, size=480):
    img = Image.new("RGB", (size, size), (255, 0, 255))
    px = img.load()
    for y in range(int(size * .2), int(size * .85)):
        for x in range(int(size * .38), int(size * .62)):
            px[x, y] = (30, 140, 220) if y < size * .5 else (200, 60, 40)
    path = tmp_path / "ref.png"
    img.save(path)
    return path


def margins(path):
    arr = np.asarray(Image.open(path).convert("RGB")).astype(int)
    ys, xs = np.where(np.abs(arr - [255, 0, 255]).sum(axis=-1) > 60)
    h = arr.shape[0]
    return ys.min() / h, (h - 1 - ys.max()) / h, (ys.max() - ys.min() + 1) / h


def test_sg_video_prompt_canvas_layouts_by_action():
    assert vs.canvas_layout("walk") == vs.canvas_layout("run") == (0.06, 0.80)
    assert vs.canvas_layout("attack") == vs.canvas_layout("jump") == (0.30, 0.55)
    assert vs.canvas_layout("idle") is None and vs.canvas_layout("custom") is None


def test_sg_video_prompt_attack_canvas_keeps_head_room_and_walk_canvas_does_not(tmp_path):
    ref = character_png(tmp_path)
    top_a, bottom_a, fill_a = margins(vs.prepare_first_frame(ref, tmp_path / "a.png", KEY, size=512, layout=vs.canvas_layout("attack")))
    top_w, bottom_w, fill_w = margins(vs.prepare_first_frame(ref, tmp_path / "w.png", KEY, size=512, layout=vs.canvas_layout("walk")))
    assert top_a >= 0.28 and abs(fill_a - 0.55) <= 0.03 and bottom_a >= 0.10          # room above the head for a raised weapon
    assert top_w <= 0.08 and abs(fill_w - 0.80) <= 0.03 and bottom_w >= 0.10         # no extra head-room; the walker is bigger
    assert top_a > top_w + 0.2


def test_sg_video_prompt_the_default_canvas_is_unchanged_and_keeps_the_character_inside(tmp_path):
    ref = character_png(tmp_path)
    top, bottom, fill = margins(vs.prepare_first_frame(ref, tmp_path / "d.png", KEY, size=512))
    assert abs(top - 0.2) <= 0.02 and abs(bottom - 0.2) <= 0.02 and abs(fill - 0.6) <= 0.02
    for action in ("walk", "attack"):  # nothing is clipped at any edge
        out = vs.prepare_first_frame(ref, tmp_path / f"{action}.png", KEY, size=512, layout=vs.canvas_layout(action))
        arr = np.asarray(Image.open(out).convert("RGB")).astype(int)
        edge = np.concatenate([arr[0], arr[-1], arr[:, 0], arr[:, -1]])
        assert (np.abs(edge - [255, 0, 255]).sum(axis=-1) <= 60).all()


@needs_ffmpeg
def test_sg_video_prompt_generate_uses_the_actions_canvas(forge, tmp_path, monkeypatch):
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
    forge.ok("plan", "hero", "--actions", "walk,attack", "--set", "walk.method=video", "--set", "attack.method=video",
             "--set", "walk.frames=6", "--set", "attack.frames=6")
    forge.ok("generate", "hero", "walk")
    forge.ok("generate", "hero", "attack")
    top_w = margins(forge.root / "hero/walk/attempts/001/first-frame.png")[0]
    top_a = margins(forge.root / "hero/attack/attempts/001/first-frame.png")[0]
    assert top_w <= 0.10 and top_a >= 0.26
