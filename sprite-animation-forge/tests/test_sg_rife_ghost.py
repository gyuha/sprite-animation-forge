"""Filmed ghosts and made-frame cross-fades (docs/14 area D). A ghost is two poses laid over each other in ONE frame; on a
key background it shows as colour pulled towards the key, so it is read on the distance from the key."""

import json
import math
import os
import shutil
from pathlib import Path

import numpy as np
import pytest
from fixtures.synthetic.make import make_sheet
from PIL import Image
from sg_clips import walker
from sprite_forge import video_ghost as vg
from sprite_forge import video_repair as vr
from sprite_forge import video_sprite as vs

KEY = (255, 0, 255)
FAKE = Path(__file__).resolve().parent / "fixtures" / "fake_codex" / "codex"
needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None, reason="ffmpeg missing")


def phase(i, total=12):
    return 2 * math.pi * i / total


def crisp_clip(tmp_path, total=12, ghosts=()):
    """A 12-frame walk where the frames in ``ghosts`` are a 50/50 blend of two poses a quarter cycle apart."""
    paths = []
    for i in range(total):
        img = Image.blend(walker(phase(i)), walker(phase(i + 3)), 0.5) if i in ghosts else walker(phase(i))
        p = tmp_path / f"{i:04d}.png"
        img.save(p)
        paths.append(p)
    return paths


def frames_of(paths):
    return [vs._rgba(p) for p in paths]


def test_sg_rife_ghost_a_cross_faded_frame_is_named_and_crisp_frames_are_not(tmp_path):
    (tmp_path / "g").mkdir()
    assert vg.ghost_frames(frames_of(crisp_clip(tmp_path)), KEY) == []
    flagged = vg.ghost_frames(frames_of(crisp_clip(tmp_path / "g", ghosts=(6,))), KEY)
    assert [g["frame"] for g in flagged] == [6] and flagged[0]["share"] >= 0.12 and flagged[0]["ratio"] >= 1.8


def test_sg_rife_ghost_a_ghost_is_given_way_to_the_clean_frame_beside_it(tmp_path):
    frames = frames_of(crisp_clip(tmp_path, ghosts=(6,)))
    out, report = vg.give_way(frames, KEY)
    assert report["given_way"] == [{"frame": 6, "replaced_by": 5}] and report["retake"] == []
    assert np.array_equal(out[6], frames[5]) and all(np.array_equal(out[i], frames[i]) for i in range(12) if i != 6)


def test_sg_rife_ghost_a_ghost_with_no_clean_frame_beside_it_is_a_retake_reason(tmp_path):
    frames = frames_of(crisp_clip(tmp_path, ghosts=(5, 6, 7)))
    out, report = vg.give_way(frames, KEY)
    assert report["retake"] == [{"reason": "filmed-ghost", "frame": 6}]  # 5 and 7 each have a clean frame beside them, 6 has none
    assert {g["frame"] for g in report["given_way"]} == {5, 7} and np.array_equal(out[6], frames[6])


def test_sg_rife_ghost_a_clip_where_most_frames_are_ghosts_is_not_judged(tmp_path):
    frames = frames_of(crisp_clip(tmp_path, ghosts=tuple(range(8))))  # the typical share is high: nothing stands out
    assert vg.ghost_frames(frames, KEY) == []


class Averager:
    name = "average"

    def between(self, a, b, t=0.5):
        return np.rint((a.astype(float) + b.astype(float)) / 2).astype(np.uint8)


class Keeper:
    name = "keeper"

    def between(self, a, b, t=0.5):
        return a.copy()  # a crisp frame: no cross-fade


def jumpy(tmp_path):
    paths = []
    for i in range(12):
        p = tmp_path / f"{i:04d}.png"
        walker(phase(i), lift=70 if i == 6 else 0).save(p)
        paths.append(p)
    return frames_of(paths)


def test_sg_rife_ghost_a_made_frame_that_cross_fades_is_measured_and_kept(tmp_path):
    frames = jumpy(tmp_path)
    out, report = vr.repair_jumps(frames, Averager(), "auto")
    named = vg.crossfade(out, report["made"])
    assert report["made"] == [6] and [c["frame"] for c in named] == [6] and named[0]["share"] >= vg.CROSSFADE_MIN
    assert report["applied"] is True  # named, not rejected


def test_sg_rife_ghost_a_crisp_made_frame_is_not_named(tmp_path):
    out, report = vr.repair_jumps(jumpy(tmp_path), Keeper(), "auto")
    assert vg.crossfade(out, report["made"]) == [] or not report["made"]


def test_sg_rife_ghost_the_sheet_gives_a_ghost_way_and_reports_it(tmp_path):
    paths = crisp_clip(tmp_path, total=15, ghosts=(4,))
    for i in (12, 13, 14):  # three more frames so the 12-frame cut closes
        walker(phase(i)).save(tmp_path / f"{i:04d}.png")
    _, info = vs.build_raw_sheet(sorted(tmp_path.glob("*.png")), 6, 2, 3, "#FF00FF", True, cell=96)
    assert info["ghost"]["given_way"] == [{"frame": 4, "replaced_by": 3}] and info["retake"] == []


def test_sg_rife_ghost_three_ghosts_in_a_row_name_a_retake_and_warn(tmp_path):
    crisp_clip(tmp_path, total=12, ghosts=(4, 5, 6))
    for i in (12, 13, 14):
        walker(phase(i)).save(tmp_path / f"{i:04d}.png")
    _, info = vs.build_raw_sheet(sorted(tmp_path.glob("*.png")), 6, 2, 3, "#FF00FF", True, cell=96)
    assert info["retake"] == [{"reason": "filmed-ghost", "frame": 5}]
    assert any(w == "retake: filmed-ghost (frame 5)" for w in info["warnings"])


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
def test_sg_rife_ghost_process_surfaces_the_clips_warnings(hero):
    hero.ok("plan", "hero", "--actions", "walk", "--set", "walk.method=video", "--set", "walk.frames=6")
    hero.ok("generate", "hero", "walk")
    meta_path = hero.root / "hero/walk/attempts/001/video-meta.json"
    meta = json.loads(meta_path.read_text())
    assert {"ghost", "retake", "jump_repair", "made", "warnings"} <= set(meta)
    meta["warnings"] = ["retake: filmed-ghost (frame 3)", "rife_unavailable: 1 jump(s) not repaired, the loop is cut as filmed"]
    meta_path.write_text(json.dumps(meta))
    hero.ok("process", "hero", "walk")
    warnings = json.loads((hero.root / "hero/walk/attempts/001/process.json").read_text())["warnings"]
    assert "retake: filmed-ghost (frame 3)" in warnings and any(w.startswith("rife_unavailable") for w in warnings)
