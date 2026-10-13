"""Edge-safe scale (docs/14 area B): alpha (coverage) and colour are resampled apart, so no edge pixel gets a colour its
neighbourhood does not have. ``legacy`` (premultiplied-alpha LANCZOS) stays available and byte-identical."""

import hashlib

import numpy as np
import pytest
from fixtures.synthetic.make import make_sheet
from PIL import Image
from scipy.ndimage import maximum_filter, minimum_filter
from sprite_forge.pipeline import PipelineError, round_half_up
from sprite_forge.pipeline.process import ProcessParams, process_sheet
from sprite_forge.pipeline.scale import resample

SCALES = (0.37, 0.5, 0.63, 0.81, 1.3)


def sprite():
    a = np.zeros((96, 80, 4), np.uint8)
    a[10:86, 14:66] = (150, 90, 60, 255)                                 # body
    a[10:86, 14:18] = (12, 10, 14, 255)                                  # dark outline
    a[10:14, 14:66] = (12, 10, 14, 255)
    a[30:44, 26:54] = (238, 232, 206, 255)                               # bright highlight
    a[50:58, 20:60] = (30, 120, 200, 255)                                # belt
    a[0:6, 38:42] = (240, 240, 240, 255)                                 # thin bright spike
    return a


def legacy_reference(rgba, scale, pixel_art):
    """The pre-change implementation, frozen: premultiplied alpha + LANCZOS (BOX for pixel art)."""
    h, w = rgba.shape[:2]
    size = (max(1, round_half_up(w * scale)), max(1, round_half_up(h * scale)))
    img = Image.fromarray(rgba, "RGBA").convert("RGBa").resize(size, Image.BOX if pixel_art else Image.LANCZOS)
    out = np.array(img.convert("RGBA"))
    if pixel_art:
        out[..., 3] = np.where(out[..., 3] >= 128, 255, 0)
        out[out[..., 3] == 0] = 0
    return out


def range_violations(src, out, tol=2):
    """Visible output pixels (alpha >= 1) whose colour is outside the min..max of the opaque source colours around them."""
    scale = out.shape[1] / src.shape[1]
    opaque = src[..., 3] > 0
    k = int(np.ceil(8 / scale)) | 1
    ys = np.clip(((np.arange(out.shape[0]) + 0.5) / (out.shape[0] / src.shape[0])).astype(int), 0, src.shape[0] - 1)
    xs = np.clip(((np.arange(out.shape[1]) + 0.5) / scale).astype(int), 0, src.shape[1] - 1)
    bad = np.zeros(out.shape[:2], bool)
    for c in range(3):
        ch = src[..., c].astype(int)
        hi = maximum_filter(np.where(opaque, ch, -1), size=k)[np.ix_(ys, xs)]
        lo = minimum_filter(np.where(opaque, ch, 999), size=k)[np.ix_(ys, xs)]
        o = out[..., c].astype(int)
        bad |= (out[..., 3] >= 1) & (hi >= 0) & ((o > hi + tol) | (o < lo - tol))
    return int(bad.sum())


@pytest.mark.parametrize("scale", SCALES)
def test_sg_resample_coverage_keeps_every_visible_colour_inside_its_neighbourhoods_range(scale):
    src = sprite()
    out = resample(src, scale, pixel_art=False, mode="coverage")
    assert (out[..., 3] > 0).sum() > 200
    assert range_violations(src, out) == 0


def test_sg_resample_the_legacy_filter_does_break_that_range_so_the_check_discriminates():
    src = sprite()
    assert all(range_violations(src, resample(src, s, pixel_art=False, mode="legacy")) > 0 for s in SCALES)


def test_sg_resample_coverage_leaves_no_colour_on_transparent_pixels_and_keeps_the_interior():
    src = sprite()
    out = resample(src, 0.5, pixel_art=False, mode="coverage")
    assert (out[out[..., 3] == 0][:, :3] == 0).all()  # canonical empty pixel
    assert tuple(out[12, 22]) == (150, 90, 60, 255)  # source (24..26, 44..46): deep inside the body, away from every edge
    assert out[..., 3].max() == 255


def test_sg_resample_coverage_has_no_key_colour_fringe_when_transparent_pixels_carry_the_key():
    img = np.zeros((40, 40, 4), dtype=np.uint8)
    img[:] = (255, 0, 255, 0)
    img[10:30, 10:30] = (20, 200, 20, 255)
    out = resample(img, 0.5, pixel_art=False, mode="coverage")
    visible = out[out[..., 3] > 0]
    assert visible[:, 0].max() <= 22 and visible[:, 2].max() <= 22


@pytest.mark.parametrize("scale", (0.37, 0.5, 0.7, 1.0, 1.3))
@pytest.mark.parametrize("pixel_art", (False, True))
def test_sg_resample_legacy_is_byte_identical_to_the_frozen_implementation(scale, pixel_art):
    src = sprite()
    assert np.array_equal(resample(src, scale, pixel_art, mode="legacy"), legacy_reference(src, scale, pixel_art))
    assert np.array_equal(resample(src, scale, pixel_art), legacy_reference(src, scale, pixel_art))  # the function default


def test_sg_resample_pixel_art_ignores_the_mode():
    src = sprite()
    assert np.array_equal(resample(src, 0.7, True, mode="coverage"), legacy_reference(src, 0.7, True))


def test_sg_resample_size_rule_is_the_same_in_both_modes():
    img = np.full((5, 5, 4), 255, dtype=np.uint8)
    for mode in ("coverage", "legacy"):
        assert resample(img, 0.5, False, mode=mode).shape[:2] == (3, 3) and resample(img, 0.01, False, mode=mode).shape[:2] == (1, 1)


def test_sg_resample_is_deterministic():
    src = sprite()
    assert resample(src, 0.37, False, mode="coverage").tobytes() == resample(src, 0.37, False, mode="coverage").tobytes()


PINS = [("clean", "a8a56adc8aa2321b80a583b37e3d5b43d7382dc1992c0d1133a95c9acf1eb4a9"),
        ("wide_attack", "a3b7b081ed50f5f8fe005413b72ee577cc19f69de969cc6339e14c3e5092b57f")]


@pytest.mark.parametrize("variant,digest", PINS)
def test_sg_resample_process_with_legacy_reproduces_the_pinned_sheet_bytes(tmp_path, variant, digest):
    make_sheet(variant, 2, 3, (256, 256)).save(tmp_path / "raw.png")
    res = process_sheet(tmp_path / "raw.png", tmp_path / "out", ProcessParams(align="per_frame", resample_mode="legacy"))
    assert hashlib.sha256((tmp_path / "out" / "sheet.png").read_bytes()).hexdigest() == digest
    assert res.data["params"]["resample_mode"] == "legacy" and res.data["params"]["resample"] == "lanczos"


def test_sg_resample_coverage_is_the_default_recorded_and_changes_only_the_edges(tmp_path):
    assert ProcessParams().resample_mode == "coverage"
    make_sheet("clean", 2, 3, (256, 256)).save(tmp_path / "raw.png")
    new = process_sheet(tmp_path / "raw.png", tmp_path / "new", ProcessParams())
    old = process_sheet(tmp_path / "raw.png", tmp_path / "old", ProcessParams(resample_mode="legacy"))
    assert new.data["params"]["resample_mode"] == "coverage"
    assert old.sheet.shape == new.sheet.shape and not np.array_equal(old.sheet, new.sheet)
    solid_old, solid_new = old.sheet[..., 3] == 255, new.sheet[..., 3] == 255
    assert abs(int(solid_old.sum()) - int(solid_new.sum())) <= 0.03 * int(solid_old.sum())  # same silhouette, only edges differ


def test_sg_resample_an_unknown_mode_is_rejected(tmp_path):
    make_sheet("clean", 2, 3, (256, 256)).save(tmp_path / "raw.png")
    with pytest.raises(PipelineError) as e:
        process_sheet(tmp_path / "raw.png", tmp_path / "out", ProcessParams(resample_mode="sharp"))
    assert e.value.code == "invalid_params"
