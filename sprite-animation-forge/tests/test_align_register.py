"""align=register (shared placement, upper-body registration, linear-drift removal) vs align=per_frame (legacy)."""
import hashlib

import numpy as np
import pytest
from PIL import Image

from fixtures.synthetic.make import make_sheet
from sprite_forge.pipeline.process import ProcessParams, process_sheet

KEY = (255, 0, 255)
CELL = 240  # raw cell px
BODY = (60, 150, 70)


def figure_sheet(path, rows=2, cols=3, n=6, torso_dx=None, torso_dy=None, leg_h=None, feet_y=None):
    """A figure per cell: head + torso (rigid) + two legs whose length alternates. Offsets are per frame (raw px)."""
    img = Image.new("RGB", (cols * CELL, rows * CELL), KEY)
    a = np.array(img)
    for i in range(n):
        r, c = divmod(i, cols)
        ox, oy = c * CELL, r * CELL
        dx = (torso_dx or [0] * n)[i]
        dy = (torso_dy or [0] * n)[i]
        lh = (leg_h or [50] * n)[i]
        cx, top = ox + CELL // 2 + dx, oy + 60 + dy
        a[top - 28 : top, cx - 14 : cx + 14] = BODY            # head
        a[top : top + 70, cx - 24 : cx + 24] = (200, 60, 60)     # torso
        a[top + 70 : top + 70 + lh, cx - 22 : cx - 6] = (40, 40, 160)   # leg 1
        a[top + 70 : top + 70 + max(20, 100 - lh), cx + 6 : cx + 22] = (40, 40, 160)  # leg 2 (opposite phase)
    Image.fromarray(a).save(path)


def upper_centroid(frame):
    """Centroid of the red torso pixels (the rigid part of the synthetic figure), unaffected by leg length."""
    torso = (frame[..., 3] >= 64) & (frame[..., 0] > 150) & (frame[..., 1] < 110)
    ys, xs = np.nonzero(torso)
    return float(xs.mean()), float(ys.mean())


def run(tmp_path, align, **kw):
    figure_sheet(tmp_path / "raw.png", **{k: kw.pop(k) for k in list(kw) if k in ("torso_dx", "torso_dy", "leg_h")})
    p = ProcessParams(align=align, **kw)
    return process_sheet(tmp_path / "raw.png", tmp_path / f"out-{align}", p)


def spread(values):
    return max(values) - min(values)


LEGS = [50, 80, 50, 80, 50, 80]  # legs alternate, so the mass centroid and feet line move while the torso stays


def test_align_register_keeps_torso_still_when_only_limbs_move(tmp_path):
    reg = run(tmp_path, "register", leg_h=LEGS)
    per = run(tmp_path, "per_frame", leg_h=LEGS)
    reg_x = spread([upper_centroid(f)[0] for f in reg.frames])
    reg_y = spread([upper_centroid(f)[1] for f in reg.frames])
    per_y = spread([upper_centroid(f)[1] for f in per.frames])
    assert reg_x <= 1.5 and reg_y <= 1.5
    assert per_y > reg_y + 2  # legacy pins the (moving) feet line, so the torso bobs up and down


def test_align_register_preserves_deliberate_bob(tmp_path):
    bob = [0, -6, -10, -6, 0, 4]
    reg = run(tmp_path, "register", torso_dy=bob)
    ys = [upper_centroid(f)[1] for f in reg.frames]
    assert spread(ys) >= 0.5 * (max(bob) - min(bob))  # the bob survives (scaled), it is not registered away


def test_align_register_removes_linear_drift_only(tmp_path):
    drift = [0, 4, 8, 12, 16, 20]
    reg = run(tmp_path, "register", torso_dx=drift)
    xs = [upper_centroid(f)[0] for f in reg.frames]
    assert spread(xs) <= 3  # 20 raw px of drift gone (legacy would also centre each frame; here the line is removed)
    assert abs(np.mean(xs) - 64) <= 3  # shared placement centres the action


def test_align_register_airborne_keeps_the_vertical_arc(tmp_path):
    arc = [0, -16, -30, -30, -16, 0]  # raw px, up is negative
    reg = run(tmp_path, "register", torso_dy=arc, preserve_vertical=True)
    per = run(tmp_path, "per_frame", torso_dy=arc)
    ys_reg = [upper_centroid(f)[1] for f in reg.frames]
    ys_per = [upper_centroid(f)[1] for f in per.frames]
    scale = reg.data["derived"]["scale"]
    assert spread(ys_reg) >= 0.9 * 30 * scale
    assert spread(ys_per) < 0.3 * spread(ys_reg)  # per_frame flattens the arc (feet pinned)


@pytest.mark.parametrize("variant,digest", [
    ("clean", "a8a56adc8aa2321b80a583b37e3d5b43d7382dc1992c0d1133a95c9acf1eb4a9"),
    ("baseline_jitter", "a8a56adc8aa2321b80a583b37e3d5b43d7382dc1992c0d1133a95c9acf1eb4a9"),
    ("wide_attack", "a3b7b081ed50f5f8fe005413b72ee577cc19f69de969cc6339e14c3e5092b57f"),
])
def test_align_register_per_frame_is_byte_identical_to_the_legacy_output(tmp_path, variant, digest):
    make_sheet(variant, 2, 3, (256, 256)).save(tmp_path / "raw.png")
    process_sheet(tmp_path / "raw.png", tmp_path / "out", ProcessParams(align="per_frame"))
    assert hashlib.sha256((tmp_path / "out" / "sheet.png").read_bytes()).hexdigest() == digest  # pinned before the change


def test_align_register_is_the_default_recorded_and_deterministic(tmp_path):
    assert ProcessParams().align == "register"
    outs = []
    for k in range(2):
        figure_sheet(tmp_path / "raw.png", leg_h=LEGS)
        res = process_sheet(tmp_path / "raw.png", tmp_path / f"o{k}", ProcessParams())
        assert res.data["params"]["align"] == "register"
        outs.append({n: h for n, h in res.data["outputs"].items()})
    assert outs[0] == outs[1]


def test_align_register_rejects_unknown_mode(tmp_path):
    figure_sheet(tmp_path / "raw.png")
    with pytest.raises(Exception):
        process_sheet(tmp_path / "raw.png", tmp_path / "o", ProcessParams(align="nope"))


def test_align_register_non_feet_anchors_fall_back_to_per_frame(tmp_path):
    figure_sheet(tmp_path / "raw.png", leg_h=LEGS)
    a = process_sheet(tmp_path / "raw.png", tmp_path / "a", ProcessParams(align="register", anchor="bottom"))
    b = process_sheet(tmp_path / "raw.png", tmp_path / "b", ProcessParams(align="per_frame", anchor="bottom"))
    assert a.data["outputs"]["sheet.png"] == b.data["outputs"]["sheet.png"]
