"""video -> sprite conversion (docs/13): loop/one-shot selection, frame extraction, raw sheet. Clips are made by ffmpeg
from a synthetic character; tests needing ffmpeg skip when it is absent."""

import io
import shutil

import numpy as np
import pytest
from PIL import Image
from sprite_forge import video_loop as vl
from sprite_forge import video_sprite as vs
from sprite_forge.errors import EXIT_PRECONDITION, ForgeError
from sprite_forge.providers.fake_video import make_bobbing_mp4

KEY = "#FF00FF"
needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None, reason="ffmpeg missing")


def character_png(size=480) -> bytes:
    img = Image.new("RGB", (size, size), (255, 0, 255))
    px = img.load()
    for y in range(int(size * .25), int(size * .8)):
        for x in range(int(size * .38), int(size * .62)):
            px[x, y] = (30, 140, 220) if y < size * .5 else (200, 60, 40)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def clip(tmp_path):
    out = tmp_path / "clip.mp4"
    assert make_bobbing_mp4(character_png(), out, frames=48, period=16, fps=24)
    return out


def phase_thumbs(total, period):
    return [np.array([np.sin(2 * np.pi * i / period), np.cos(2 * np.pi * i / period), np.sin(4 * np.pi * i / period)])
            for i in range(total)]


# ---- video_loop ----------------------------------------------------------------------------------------------

def test_video_loop_finds_the_true_period():
    start, period = vl.select_loop(vl.distance_matrix(phase_thumbs(60, 20)), n=8)
    assert period == 20 and start + period < 60


def test_video_loop_does_not_mistake_one_and_a_half_cycles_for_a_period():
    _, period = vl.select_loop(vl.distance_matrix(phase_thumbs(30, 20)), n=8)
    assert period == 20


def test_video_loop_prefers_the_shortest_of_equally_good_periods():
    _, period = vl.select_loop(vl.distance_matrix(phase_thumbs(80, 16)), n=8)
    assert period == 16  # not 32 / 48


def test_video_loop_static_clip_stays_inside_the_clip():
    start, period = vl.select_loop(vl.distance_matrix([np.zeros(3)] * 30), n=8)
    assert 0 <= start and start + period < 30


def test_video_loop_short_clip_uses_all_of_it():
    assert vl.select_loop(vl.distance_matrix(phase_thumbs(6, 20)), n=8) == (0, 5)


def test_video_loop_oneshot_ends_where_the_clip_returns_to_the_first_pose():
    thumbs = [np.array([np.sin(np.pi * i / 29)]) for i in range(30)] + [np.array([0.0])] * 10  # up, down, then rests
    start, end = vl.select_oneshot(vl.distance_matrix(thumbs), n=8)
    assert start == 0 and end >= 29


def test_video_loop_oneshot_without_return_takes_the_whole_clip():
    thumbs = [np.array([i / 39]) for i in range(40)]
    assert vl.select_oneshot(vl.distance_matrix(thumbs), n=8) == (0, 39)


def test_video_loop_reduce_indices_loop_never_repeats_the_start():
    idx = vl.reduce_indices(3, 20, 8, loop=True)
    assert idx == [3, 6, 8, 11, 13, 16, 18, 21] and 3 + 20 not in idx


def test_video_loop_reduce_indices_oneshot_includes_both_ends():
    idx = vl.reduce_indices(0, 30, 4, loop=False)
    assert idx == [0, 10, 20, 30] and vl.reduce_indices(5, 9, 1, loop=True) == [5]


# ---- video_sprite --------------------------------------------------------------------------------------------

def test_video_sprite_first_frame_is_a_key_canvas_with_a_centred_character(tmp_path):
    ref = tmp_path / "ref.png"
    ref.write_bytes(character_png())
    out = vs.prepare_first_frame(ref, tmp_path / "first.png", KEY, size=512)
    arr = np.asarray(Image.open(out).convert("RGB"))
    assert arr.shape == (512, 512, 3) and tuple(arr[0, 0]) == (255, 0, 255) and tuple(arr[-1, -1]) == (255, 0, 255)
    ys, xs = np.where(np.abs(arr.astype(int) - [255, 0, 255]).sum(axis=-1) > 60)
    assert abs((ys.max() - ys.min() + 1) / 512 - 0.6) < 0.03
    assert abs((xs.min() + xs.max()) / 2 - 256) < 3 and abs((ys.min() + ys.max()) / 2 - 256) < 3


def test_video_sprite_first_frame_rejects_an_empty_reference(tmp_path):
    ref = tmp_path / "blank.png"
    Image.new("RGB", (64, 64), (255, 0, 255)).save(ref)
    with pytest.raises(ForgeError) as e:
        vs.prepare_first_frame(ref, tmp_path / "f.png", KEY)
    assert e.value.code == "invalid_image"


@needs_ffmpeg
def test_video_sprite_extract_frames_reports_every_frame_and_the_fps(clip, tmp_path):
    frames, fps = vs.extract_frames(clip, tmp_path / "frames")
    assert len(frames) == 48 and fps == 24


@needs_ffmpeg
def test_video_sprite_loop_sheet_has_grid_geometry_and_a_clean_key_background(clip, tmp_path):
    frames, _ = vs.extract_frames(clip, tmp_path / "frames")
    sheet, info = vs.build_raw_sheet(frames, 8, 2, 4, KEY, loop=True, cell=128)
    assert sheet.size == (4 * 128, 2 * 128) and info["selected"] == "loop"
    assert abs(info["span"] - 16) <= 1 and len(info["indices"]) == 8
    arr = np.asarray(sheet)
    for r in range(2):
        for c in range(4):
            assert tuple(arr[r * 128, c * 128]) == (255, 0, 255)  # cell corner is exactly the key colour
    assert (np.abs(arr.astype(int) - [255, 0, 255]).sum(axis=-1) > 60).sum() > 8 * 500  # characters are present


@needs_ffmpeg
def test_video_sprite_oneshot_sheet(clip, tmp_path):
    frames, _ = vs.extract_frames(clip, tmp_path / "frames")
    _, info = vs.build_raw_sheet(frames, 6, 2, 3, KEY, loop=False, cell=128)
    assert info["selected"] == "oneshot" and info["start"] == 0 and info["indices"][0] == 0


@needs_ffmpeg
def test_video_sprite_sheet_must_fit_the_grid(clip, tmp_path):
    frames, _ = vs.extract_frames(clip, tmp_path / "frames")
    with pytest.raises(ForgeError) as e:
        vs.build_raw_sheet(frames, 9, 2, 4, KEY, loop=True)
    assert e.value.code == "invalid_params"


@needs_ffmpeg
def test_video_sprite_garbage_clip_is_a_decode_error(tmp_path):
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 40)
    with pytest.raises(ForgeError) as e:
        vs.extract_frames(bad, tmp_path / "frames")
    assert e.value.code == "video_decode_failed"


def test_video_sprite_without_ffmpeg_is_a_precondition_error(monkeypatch, tmp_path):
    monkeypatch.setattr(vs.shutil, "which", lambda name: None)
    with pytest.raises(ForgeError) as e:
        vs.extract_frames(tmp_path / "x.mp4", tmp_path / "frames")
    assert e.value.code == "ffmpeg_missing" and e.value.exit_code == EXIT_PRECONDITION


# ---- end to end: CLI generate (fake video provider) -> process -> accept -------------------------------------

import json  # noqa: E402
import os  # noqa: E402
from pathlib import Path  # noqa: E402

from fixtures.synthetic.make import make_sheet  # noqa: E402
from sprite_forge import plan as plan_mod  # noqa: E402
from sprite_forge import prompt as pr  # noqa: E402

FAKE = Path(__file__).resolve().parent / "fixtures" / "fake_codex" / "codex"


@pytest.fixture
def video_env(tmp_path, monkeypatch):
    home = tmp_path / "codex_home"
    home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.setenv("SPRITE_FORGE_CODEX_BIN", str(FAKE))
    for k in [k for k in os.environ if k.startswith("FAKE_CODEX")]:
        monkeypatch.delenv(k)
    monkeypatch.setenv("FAKE_CODEX_IMAGE", "clean")
    monkeypatch.setenv("SPRITE_FORGE_VIDEO_PROVIDER", "fake")


def ready(forge, tmp_path, *sets):
    ref = tmp_path / "ref.png"
    make_sheet("clean", rows=1, cols=1).save(ref)
    forge.ok("init", "hero")
    forge.ok("reference", "import", "hero", ref)
    forge.ok("identity", "analyze", "hero")
    args = ["plan", "hero", "--actions", "idle,walk"]
    for s in sets:
        args += ["--set", s]
    forge.ok(*args)


@needs_ffmpeg
def test_video_sprite_generate_writes_a_complete_attempt_then_processes_and_accepts(forge, tmp_path, video_env):
    ready(forge, tmp_path, "walk.method=video", "walk.frames=6")
    out = forge.ok("generate", "hero", "walk")
    adir = forge.root / "hero/walk/attempts/001"
    assert out["status"] == "succeeded"
    for name in ("raw.mp4", "raw.png", "first-frame.png", "video-meta.json", "generation.json", "prompt.txt"):
        assert (adir / name).is_file(), name
    gen = json.loads((adir / "generation.json").read_text())
    assert gen["method"] == "video" and gen["prompt_template_version"] == pr.VIDEO_PROMPT_VERSION
    meta = json.loads((adir / "video-meta.json").read_text())
    assert meta["selected"] == "loop" and len(meta["indices"]) == 6 and meta["pinned_last_frame"] is False
    assert not (adir / ".clip-frames").exists()
    res = forge.ok("process", "hero", "walk")
    assert res["qc"]["status"] in ("pass", "warn", "fail")
    assert len(list((adir / "frames").glob("*.png"))) == 6
    forge.ok("accept", "hero", "walk")


@needs_ffmpeg
def test_video_sprite_idle_pins_the_last_frame(forge, tmp_path, video_env):
    ready(forge, tmp_path, "idle.method=video")
    forge.ok("generate", "hero", "idle")
    meta = json.loads((forge.root / "hero/idle/attempts/001/video-meta.json").read_text())
    assert meta["pinned_last_frame"] is True


def test_video_sprite_generate_without_a_connected_provider_is_method_unavailable(forge, tmp_path, video_env, monkeypatch):
    ready(forge, tmp_path, "walk.method=video")
    monkeypatch.delenv("SPRITE_FORGE_VIDEO_PROVIDER")
    code, out = forge.run("generate", "hero", "walk")
    assert (code, out["error_code"]) == (3, "method_unavailable")
    assert not (forge.root / "hero/walk/attempts").exists()


def test_video_sprite_missing_ffmpeg_marks_the_attempt_failed(forge, tmp_path, video_env, monkeypatch):
    ready(forge, tmp_path, "walk.method=video")
    monkeypatch.setenv("PATH", str(tmp_path))  # nothing runnable
    code, out = forge.run("generate", "hero", "walk")
    assert (code, out["error_code"]) == (2, "ffmpeg_missing") and out["attempt"] == "001"
    assert json.loads((forge.root / "hero/manifest.json").read_text())["actions"]["walk"]["attempts"]["001"]["generation_status"] == "failed"


def test_video_sprite_multi_direction_plans_cannot_use_video(forge, tmp_path, video_env):
    forge.ok("init", "hero")
    code, out = forge.run("plan", "hero", "--actions", "walk", "--view", "topdown", "--set", "walk.method=video")
    assert (code, out["error_code"]) == (1, "invalid_params")


def test_video_sprite_prompt_has_motion_loop_and_background_rules_but_no_grid():
    p = plan_mod.build_plan("hero", ["walk", "idle"], view="side", art_style="project_native", has_reference=True,
                            profile=None, overrides=plan_mod.parse_overrides([]))
    text = pr.build_video_prompt(p, None, "walk", "slow").text
    assert "seamless loop" in text and "#FF00FF" in text and "static" in text and "ADDITIONAL DIRECTION\nslow" in text
    assert "grid" not in text.lower()
    assert "returns to the starting pose" in pr.build_video_prompt(
        {**p, "actions": {**p["actions"], "walk": {**p["actions"]["walk"], "loop": False}}}, None, "walk").text
