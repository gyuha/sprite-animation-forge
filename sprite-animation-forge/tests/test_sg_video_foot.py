"""Foot-strike start, jolt index and the loop report (docs/14 area C). Synthetic clips; the generate/process tests need ffmpeg."""

import json
import math
import os
import shutil
from pathlib import Path

import numpy as np
import pytest
from fixtures.synthetic.make import make_sheet
from sg_clips import blob, clip, clip_of, walker, walker_front
from sprite_forge import plan as plan_mod
from sprite_forge import schemas
from sprite_forge import video_gait as vg
from sprite_forge import video_sprite as vs
from sprite_forge.errors import ForgeError

FAKE = Path(__file__).resolve().parent / "fixtures" / "fake_codex" / "codex"
needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None, reason="ffmpeg missing")


def frames_of(paths):
    return [vs._rgba(p) for p in paths]


# ---- foot strike ---------------------------------------------------------------------------------------------

def test_sg_video_foot_side_view_starts_on_the_frame_where_the_legs_are_furthest_apart(tmp_path):
    frames = frames_of(clip(tmp_path, 48, 12))  # legs spread most at phase pi/2 and 3pi/2: frames 3, 9, 15 ...
    new, source = vg.foot_strike_start(frames, 0, 12, "side")
    assert source == "legs_spread" and abs(new - 3) <= 1
    new, _ = vg.foot_strike_start(frames, 7, 12, "side")  # the nearest strike to where the cut began
    assert abs(new - 9) <= 1


def test_sg_video_foot_front_view_starts_where_both_feet_are_down(tmp_path):
    frames = frames_of(clip_of(walker_front, tmp_path, 48, 12))  # both feet down at phase 0 and pi: frames 0, 6, 12 ...
    new, source = vg.foot_strike_start(frames, 2, 12, "front")
    assert source == "legs_lift" and abs(new - 0) <= 1


def test_sg_video_foot_a_body_without_legs_is_skipped_and_the_cut_is_left_alone(tmp_path):
    frames = frames_of(clip_of(blob, tmp_path, 48, 12))
    assert vg.foot_strike_start(frames, 3, 12, "side") == (3, "none")
    assert vg.foot_strike_start(frames, 3, 12, "front") == (3, "none")


def test_sg_video_foot_the_shifted_cut_always_fits_inside_the_clip(tmp_path):
    frames = frames_of(clip(tmp_path, 20, 12))  # little room after the cut
    new, _ = vg.foot_strike_start(frames, 6, 12, "side")
    assert 0 <= new and new + 12 <= len(frames) - 1


def test_sg_video_foot_the_sheet_starts_on_the_strike_and_reports_where_it_read_it(tmp_path):
    paths = clip(tmp_path, 48, 12)
    _, info = vs.build_raw_sheet(paths, 6, 2, 3, "#FF00FF", True, cell=96, foot="side")
    assert info["start_foot_source"] == "legs_spread" and abs(info["indices"][0] - 3) <= 1 and info["foot_shift"] >= 1
    _, plain = vs.build_raw_sheet(paths, 6, 2, 3, "#FF00FF", True, cell=96)
    assert plain["start_foot_source"] is None and plain["indices"][0] == plain["start"]


# ---- jolt index -----------------------------------------------------------------------------------------------

def test_sg_video_foot_a_smooth_bounce_has_a_lower_jolt_than_a_jerky_one(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    smooth = frames_of(clip(tmp_path / "a", 48, 12, lift=lambda i: round(10 * abs(math.sin(math.pi * i / 12)))))
    jerky = frames_of(clip(tmp_path / "b", 48, 12, lift=lambda i: 14 * (i % 2)))
    a, b = vg.jolt_metrics(smooth, 0, 12), vg.jolt_metrics(jerky, 0, 12)
    assert 0 <= a["jolt_index"] < 0.5 * b["jolt_index"] and b["jolt_index"] > 0
    assert set(a) == {"jolt_index", "head_move"} and a["head_move"] >= 0


def test_sg_video_foot_a_steady_walker_stays_far_below_a_jerky_one(tmp_path):
    # limbs that overlap and part move the centre of mass a little (~0.02); a body that jumps frame to frame is ~7x that
    (tmp_path / "j").mkdir()
    steady = vg.jolt_metrics(frames_of(clip(tmp_path, 48, 12)), 0, 12)["jolt_index"]
    jerky = vg.jolt_metrics(frames_of(clip(tmp_path / "j", 48, 12, lift=lambda i: 14 * (i % 2))), 0, 12)["jolt_index"]
    assert steady < 0.05 and jerky > 3 * steady


def test_sg_video_foot_the_gate_warns_only_when_a_limit_is_set_and_exceeded():
    assert "jolt_exceeded" in vg.jolt_warning({"jolt_index": 0.02}, 0.01)
    assert vg.jolt_warning({"jolt_index": 0.02}, 0.05) is None
    assert vg.jolt_warning({"jolt_index": 0.02}, None) is None  # no gate by default
    assert vg.jolt_warning({"jolt_index": None}, 0.01) is None and vg.jolt_warning(None, 0.01) is None


def test_sg_video_foot_plan_accepts_a_jolt_limit():
    plan = plan_mod.build_plan("hero", ["walk"], view="side", art_style="project_native", has_reference=True, profile=None,
                               overrides=plan_mod.parse_overrides(["walk.max_jolt=0.02"]))
    assert plan["actions"]["walk"]["max_jolt"] == 0.02
    schemas.validate("animation-plan", plan)
    with pytest.raises(ForgeError):
        plan_mod.parse_overrides(["walk.max_jolt=fast"])


# ---- through generate / process (fake video provider) ---------------------------------------------------------

@pytest.fixture
def hero(forge, tmp_path, monkeypatch):
    home = tmp_path / "codex_home"
    home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.setenv("SPRITE_FORGE_CODEX_BIN", str(FAKE))
    for k in [k for k in os.environ if k.startswith("FAKE_CODEX")]:
        monkeypatch.delenv(k)
    monkeypatch.setenv("FAKE_CODEX_IMAGE", "clean")
    monkeypatch.setenv("SPRITE_FORGE_VIDEO_PROVIDER", "fake")
    ref = tmp_path / "ref.png"
    make_sheet("clean", rows=1, cols=1).save(ref)
    forge.ok("init", "hero")
    forge.ok("reference", "import", "hero", ref)
    forge.ok("identity", "analyze", "hero")
    return forge


@needs_ffmpeg
def test_sg_video_foot_generate_records_the_loop_report_in_video_meta(hero):
    hero.ok("plan", "hero", "--actions", "walk", "--set", "walk.method=video", "--set", "walk.frames=6")
    hero.ok("generate", "hero", "walk")
    meta = json.loads((hero.root / "hero/walk/attempts/001/video-meta.json").read_text())
    for key in ("start_foot_source", "foot_shift", "jolt_index", "head_move", "research", "seam_ratio", "seam_pop", "size_hold", "held"):
        assert key in meta, key


@needs_ffmpeg
def test_sg_video_foot_process_warns_about_the_jolt_only_when_the_plan_sets_a_limit(hero):
    hero.ok("plan", "hero", "--actions", "walk", "--set", "walk.method=video", "--set", "walk.frames=6", "--set", "walk.max_jolt=0")
    hero.ok("generate", "hero", "walk")
    hero.ok("process", "hero", "walk")
    process = json.loads((hero.root / "hero/walk/attempts/001/process.json").read_text())
    assert any(w.startswith("jolt_exceeded") for w in process["warnings"])
    hero.ok("plan", "hero", "--actions", "walk", "--set", "walk.method=video", "--set", "walk.frames=6")
    hero.ok("process", "hero", "walk")
    process = json.loads((hero.root / "hero/walk/attempts/001/process.json").read_text())
    assert not any(w.startswith("jolt_exceeded") for w in process["warnings"])
