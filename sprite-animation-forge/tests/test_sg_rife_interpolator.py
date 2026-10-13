"""Optional frame interpolation (docs/14 area D): finding the binary, wrapping it, and repairing jump frames with it. Nothing
here needs a real RIFE: a fake binary and scripted interpolators stand in for it; every default path works without one."""

import os
import stat
import sys
from pathlib import Path

import numpy as np
import pytest
from sg_clips import clip
from sprite_forge import doctor
from sprite_forge import interpolate as ip
from sprite_forge import video_repair as vr
from sprite_forge import video_sprite as vs
from sprite_forge.errors import ForgeError

FAKE = Path(__file__).resolve().parent / "fixtures" / "fake_rife" / "fake_rife.py"


@pytest.fixture
def fake_bin(tmp_path):
    """An executable named rife-ncnn-vulkan that runs the fake."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    exe = bindir / "rife-ncnn-vulkan"
    exe.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{FAKE}" "$@"\n')
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    return exe


@pytest.fixture(autouse=True)
def no_real_rife(monkeypatch):
    monkeypatch.delenv("SPRITE_FORGE_RIFE_BIN", raising=False)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")  # a real rife-ncnn-vulkan on the developer's PATH must not leak in


# ---- finding the binary ----------------------------------------------------------------------------------------

def test_sg_rife_interpolator_none_found_is_reported_not_raised():
    assert ip.find_rife() == {"installed": False, "bin": None, "source": None}
    assert ip.find_interpolator() is None


def test_sg_rife_interpolator_the_env_path_wins_over_path(tmp_path, fake_bin, monkeypatch):
    other = tmp_path / "other"
    other.mkdir()
    (other / "rife-ncnn-vulkan").write_text("#!/bin/sh\nexit 0\n")
    (other / "rife-ncnn-vulkan").chmod(0o755)
    monkeypatch.setenv("PATH", f"{other}:/usr/bin:/bin")
    assert ip.find_rife()["source"] == "path"
    monkeypatch.setenv("SPRITE_FORGE_RIFE_BIN", str(fake_bin))
    found = ip.find_rife()
    assert found == {"installed": True, "bin": str(fake_bin), "source": "env"}


def test_sg_rife_interpolator_an_env_path_that_is_not_runnable_is_ignored(tmp_path, fake_bin, monkeypatch):
    monkeypatch.setenv("SPRITE_FORGE_RIFE_BIN", str(tmp_path / "missing"))
    monkeypatch.setenv("PATH", f"{fake_bin.parent}:/usr/bin:/bin")
    assert ip.find_rife()["source"] == "path"


def test_sg_rife_interpolator_doctor_reports_it_and_it_never_blocks_ready(fake_bin, monkeypatch):
    before = doctor.run_doctor()
    assert before["rife"]["installed"] is False and not any("rife" in w for w in before["warnings"])
    monkeypatch.setenv("SPRITE_FORGE_RIFE_BIN", str(fake_bin))
    after = doctor.run_doctor()
    assert after["rife"]["installed"] is True and after["ready"] == before["ready"] and after["warnings"] == before["warnings"]


# ---- the wrapper (alpha is interpolated as a second, grey image) ------------------------------------------------

def sprite(color, x0, alpha=255):
    a = np.zeros((40, 40, 4), np.uint8)
    a[10:30, x0:x0 + 10] = (*color, alpha)
    return a


def test_sg_rife_interpolator_wraps_the_binary_colour_and_coverage_apart(fake_bin, tmp_path, monkeypatch):
    log = tmp_path / "argv.log"
    monkeypatch.setenv("FAKE_RIFE_LOG", str(log))
    rife = ip.RifeNcnn(str(fake_bin))
    a, b = sprite((200, 40, 40), 4), sprite((200, 40, 40), 8)  # the boxes overlap: 8..14 is solid in both
    out = rife.between(a, b, 0.5)
    assert out.shape == a.shape and out.dtype == np.uint8
    expected_alpha = np.rint((a[..., 3].astype(float) + b[..., 3]) / 2)
    assert np.abs(out[..., 3].astype(float) - expected_alpha).max() <= 1  # coverage came from the grey run
    assert (out[out[..., 3] == 0][:, :3] == 0).all()  # no colour where there is no coverage
    solid = out[..., 3] == 255
    assert solid.any() and (np.abs(out[solid][:, :3].astype(int) - (200, 40, 40)).max() <= 2)  # the body's own colour, not black
    runs = log.read_text().splitlines()
    assert len(runs) == 2 and all(" -s 0.5" in r and "-0 " in r and "-1 " in r and "-o " in r for r in runs)


def test_sg_rife_interpolator_faint_coverage_is_dropped_so_no_halo_is_invented(fake_bin):
    a = np.zeros((20, 20, 4), np.uint8)
    b = np.zeros((20, 20, 4), np.uint8)
    b[5:15, 5:15] = (90, 90, 90, 2)  # almost invisible: half of 2 is 1/255, under MIN_COVERAGE
    out = ip.RifeNcnn(str(fake_bin)).between(a, b, 0.5)
    assert out[..., 3].max() == 0 and not out.any()


def test_sg_rife_interpolator_a_binary_that_runs_and_fails_is_an_error(fake_bin, monkeypatch):
    monkeypatch.setenv("FAKE_RIFE_FAIL", "1")
    with pytest.raises(ForgeError) as e:
        ip.RifeNcnn(str(fake_bin)).between(sprite((1, 2, 3), 4), sprite((1, 2, 3), 14), 0.5)
    assert e.value.code == "rife_failed" and "vkCreateInstance" in e.value.message


# ---- jump frames ----------------------------------------------------------------------------------------------

class Midpoint:
    """A scripted interpolator: the pixelwise middle of its two neighbours (recording what it was asked for)."""

    name = "midpoint"

    def __init__(self):
        self.calls = []

    def between(self, a, b, t=0.5):
        self.calls.append((a, b, t))
        return np.rint((a.astype(float) + b.astype(float)) / 2).astype(np.uint8)


def frames_of(paths):
    return [vs._rgba(p) for p in paths]


@pytest.fixture
def smooth(tmp_path):
    return frames_of(clip(tmp_path, 12, 12))


@pytest.fixture
def jumpy(tmp_path):
    return frames_of(clip(tmp_path, 12, 12, lift=lambda i: 70 if i == 6 else 0))  # frame 6: the whole body is somewhere else


def test_sg_rife_interpolator_a_smooth_loop_has_no_jump(smooth):
    assert vr.find_jumps(smooth) == []
    frames, report = vr.repair_jumps(smooth, Midpoint(), "auto")
    assert report["applied"] is False and report["jumps"] == [] and all(np.array_equal(a, b) for a, b in zip(frames, smooth))


def test_sg_rife_interpolator_the_odd_frame_is_remade_from_its_neighbours(jumpy):
    assert [j["frame"] for j in vr.find_jumps(jumpy)] == [6]
    stub = Midpoint()
    frames, report = vr.repair_jumps(jumpy, stub, "auto")
    assert report["applied"] is True and report["made"] == [6] and report["unmade"] == []
    assert np.array_equal(stub.calls[0][0], jumpy[5]) and np.array_equal(stub.calls[0][1], jumpy[7]) and stub.calls[0][2] == 0.5
    assert np.array_equal(frames[6], np.rint((jumpy[5].astype(float) + jumpy[7]) / 2).astype(np.uint8))
    assert all(np.array_equal(frames[i], jumpy[i]) for i in range(12) if i != 6)  # the rest stay the video's own
    assert vr.find_jumps(frames) == []  # and the loop plays smoother


def test_sg_rife_interpolator_a_repair_that_does_not_help_is_not_kept(jumpy):
    class Garbage(Midpoint):
        def between(self, a, b, t=0.5):
            return np.full_like(a, 255)  # a solid white box: the jump gets worse

    frames, report = vr.repair_jumps(jumpy, Garbage(), "auto")
    assert report["applied"] is False and report["made"] == [] and len(report["unmade"]) == 1
    assert {"frame", "score"} <= set(report["unmade"][0]) and report["unmade"][0]["frame"] == 6 and np.array_equal(frames[6], jumpy[6])


def test_sg_rife_interpolator_at_most_three_frames_are_made_per_loop(tmp_path):
    frames = frames_of(clip(tmp_path, 12, 12, lift=lambda i: 70 if i in (2, 5, 8, 11) else 0))
    _, report = vr.repair_jumps(frames, Midpoint(), "auto")
    assert len(report["made"]) <= vr.MAX_REPAIRS == 3


def test_sg_rife_interpolator_without_rife_auto_cuts_as_filmed_with_a_warning(jumpy):
    frames, report = vr.repair_jumps(jumpy, None, "auto", discover=lambda: None)
    assert report["applied"] is False and report["why"] == "rife_not_found" and report["made"] == []
    assert any(w.startswith("rife_unavailable") for w in report["warnings"])
    assert all(np.array_equal(a, b) for a, b in zip(frames, jumpy))


def test_sg_rife_interpolator_on_demands_rife_and_off_never_looks_for_it(jumpy):
    with pytest.raises(ForgeError) as e:
        vr.repair_jumps(jumpy, None, "on", discover=lambda: None)
    assert e.value.code == "rife_missing" and e.value.exit_code == 3

    def boom():
        raise AssertionError("discover must not run when repair is off")

    _, report = vr.repair_jumps(jumpy, None, "off", discover=boom)
    assert report["applied"] is False and report["why"] == "off"


def test_sg_rife_interpolator_rife_is_only_looked_for_when_a_frame_is_to_be_made(smooth):
    calls = []
    vr.repair_jumps(smooth, None, "auto", discover=lambda: calls.append(1))
    assert calls == []


def test_sg_rife_interpolator_a_found_rife_that_fails_is_an_error_in_every_mode(jumpy):
    class Broken(Midpoint):
        def between(self, a, b, t=0.5):
            raise ForgeError("rife_failed", "vkCreateInstance failed")

    for mode in ("auto", "on"):
        with pytest.raises(ForgeError) as e:
            vr.repair_jumps(jumpy, Broken(), mode)
        assert e.value.code == "rife_failed"


def test_sg_rife_interpolator_the_sheet_reports_the_repair_and_still_works_without_rife(tmp_path):
    paths = clip(tmp_path, 15, 12, lift=lambda i: 70 if i == 6 else 0)  # the only well-closing cut (period 12) holds the displaced frame
    sheet, info = vs.build_raw_sheet(paths, 6, 2, 3, "#FF00FF", True, cell=96, repair="auto", interpolator=Midpoint())
    assert info["jump_repair"]["applied"] is True and info["jump_repair"]["made_source"] and info["made"]
    sheet2, plain = vs.build_raw_sheet(paths, 6, 2, 3, "#FF00FF", True, cell=96, repair="off")
    assert plain["jump_repair"]["why"] == "off" and plain["made"] == [] and sheet.size == sheet2.size


def test_sg_rife_interpolator_a_loop_too_short_to_judge_is_left_alone(tmp_path):
    frames = frames_of(clip(tmp_path, 6, 6, lift=lambda i: 70 if i == 3 else 0))
    out, report = vr.repair_jumps(frames, Midpoint(), "auto")
    assert report["why"] == "cut_too_short" and report["jumps"] == [] and report["applied"] is False
    assert all(np.array_equal(a, b) for a, b in zip(out, frames))
