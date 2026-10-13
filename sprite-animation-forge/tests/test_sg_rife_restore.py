"""Restoring a damaged made frame from its source (docs/14 area D). A frame the interpolator made can come out melted; its source
frame (the one it replaced) is restored in its place - but only where that keeps the key guard and does not bring the jump back."""

import json
import math
import os
import shutil
from pathlib import Path

import numpy as np
import pytest
from fixtures.synthetic.make import make_sheet
from sg_clips import clip, walker
from sprite_forge import video_repair as vr
from sprite_forge import video_restore as rs
from sprite_forge import video_sprite as vs

KEY = (255, 0, 255)
FAKE = Path(__file__).resolve().parent / "fixtures" / "fake_codex" / "codex"
needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None, reason="ffmpeg missing")


def frames_of(paths):
    return [vs._rgba(p) for p in paths]


@pytest.fixture
def smooth(tmp_path):
    return frames_of(clip(tmp_path, 12, 12))


def melted(frame):
    """A made frame that lost its lower half (a limb RIFE could not follow)."""
    out = frame.copy()
    out[frame.shape[0] // 2 + 20:] = 0
    return out


def test_sg_rife_restore_a_cell_is_damaged_past_the_coverage_tolerance(smooth):
    src = smooth[3]
    assert rs.damage(melted(src), src) >= rs.DAMAGE_TOL
    slight = src.copy()
    slight[..., 3][:6] = 0  # a few rows of the sprite's very top gone: well under 8 %
    assert rs.damage(slight, src) < rs.DAMAGE_TOL and rs.damage(src, src) == 0


def test_sg_rife_restore_a_melted_made_frame_is_restored_from_its_source(smooth):
    made = list(smooth)
    made[3] = melted(smooth[3])
    out, report = rs.restore_made_frames(made, smooth, [3], KEY)
    assert [r["frame"] for r in report["restored"]] == [3] and report["restored"][0]["reason"] == "coverage_deviation"
    assert report["restored"][0]["deviation"] >= rs.DAMAGE_TOL and report["regressed"] == []
    assert np.array_equal(out[3], smooth[3]) and all(np.array_equal(out[i], made[i]) for i in range(12) if i != 3)


def test_sg_rife_restore_a_made_frame_that_is_close_to_its_source_is_left_alone(smooth):
    made = list(smooth)
    made[5] = smooth[5].copy()
    made[5][..., 3][:4] = 0
    out, report = rs.restore_made_frames(made, smooth, [5], KEY)
    assert report["restored"] == [] and report["regressed"] == [] and np.array_equal(out[5], made[5])


def test_sg_rife_restore_a_source_that_would_bring_the_jump_back_is_refused(tmp_path):
    jump = frames_of(clip(tmp_path, 12, 12, lift=lambda i: 70 if i == 6 else 0))  # frame 6 as filmed: displaced
    repaired, report = vr.repair_jumps(jump, Mid(), "auto")
    assert report["made"] == [6]
    out, restore = rs.restore_made_frames(repaired, jump, [6], KEY)
    assert restore["restored"] == [] and np.array_equal(out[6], repaired[6])  # the source is the very frame that jumped
    refused = restore["regressed"]  # the average differs from the source's area by 30 %, so the source IS a candidate ...
    assert len(refused) == 1 and refused[0]["reason"] == "restores_jump" and refused[0]["deviation"] >= rs.DAMAGE_TOL
    assert refused[0]["odd_before"] == 0.0 and refused[0]["odd_after"] > 50  # ... and bringing the jump back is refused


class Mid:
    name = "mid"

    def between(self, a, b, t=0.5):
        return np.rint((a.astype(float) + b.astype(float)) / 2).astype(np.uint8)


def test_sg_rife_restore_a_source_with_key_tint_is_refused_by_the_key_guard(smooth):
    tinted = smooth[3].copy()
    body = tinted[..., 3] >= 128
    tinted[..., :3][body] = (250, 10, 250)  # the whole body is the key colour: restoring it would deliver the spill
    made = list(smooth)
    made[3] = melted(smooth[3])
    out, report = rs.restore_made_frames(made, [*smooth[:3], tinted, *smooth[4:]], [3], KEY)
    assert report["restored"] == [] and report["regressed"] == [{"frame": 3, "reason": "key_guard", "deviation": report["regressed"][0]["deviation"]}]
    assert np.array_equal(out[3], made[3])


def test_sg_rife_restore_the_key_excess_counts_opaque_pixels_near_the_key(smooth):
    assert rs.key_excess(smooth[3], KEY) == 0
    tinted = smooth[3].copy()
    tinted[..., :3][tinted[..., 3] >= 128] = (250, 10, 250)
    assert rs.key_excess(tinted, KEY) == int((tinted[..., 3] >= 128).sum())


def test_sg_rife_restore_the_sheet_keeps_the_source_frames_and_reports_the_restore(tmp_path):
    clip_dir = tmp_path / "clip"
    clip_dir.mkdir()
    paths = clip(clip_dir, 15, 12, lift=lambda i: 70 if i == 6 else 0)
    src_dir = tmp_path / "source-frames"
    _, info = vs.build_raw_sheet(paths, 6, 2, 3, "#FF00FF", True, cell=96, repair="auto", interpolator=Mid(), source_dir=src_dir)
    assert {"restored", "restore_regressed"} <= set(info) and info["restored"] == []
    files = sorted(p.name for p in src_dir.glob("*.png"))
    assert len(files) == 6 and files[0].startswith("00-")  # one per sheet frame: <sheet position>-<source frame>.png


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
def test_sg_rife_restore_a_video_attempt_keeps_its_source_frames_and_process_json_carries_the_restore_field(hero):
    hero.ok("plan", "hero", "--actions", "walk", "--set", "walk.method=video", "--set", "walk.frames=6")
    hero.ok("generate", "hero", "walk")
    adir = hero.root / "hero/walk/attempts/001"
    assert len(list((adir / "source-frames").glob("*.png"))) == 6
    meta = json.loads((adir / "video-meta.json").read_text())
    assert meta["restored"] == [] and "restore_regressed" in meta
    hero.ok("process", "hero", "walk")
    assert json.loads((adir / "process.json").read_text())["restored"] == []
    meta["restored"] = [{"frame": 3, "source_frame": 3, "reason": "coverage_deviation", "deviation": 0.2}]
    (adir / "video-meta.json").write_text(json.dumps(meta))
    hero.ok("process", "hero", "walk")
    assert json.loads((adir / "process.json").read_text())["restored"] == meta["restored"]
