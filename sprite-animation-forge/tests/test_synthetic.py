import io

import numpy as np
import pytest
from PIL import Image

from fixtures.synthetic.make import VARIANTS, make_sheet

GRIDS = [(2, 2), (2, 3)]


def foreground_mask(sheet) -> np.ndarray:
    arr = np.asarray(sheet.image)
    if sheet.image.mode == "RGBA":
        return arr[..., 3] > 0
    # model_like_bg drifts up to ~15 from the key color; characters are far away
    ref = np.array(sheet.key_color if sheet.variant != "model_like_bg" else (245, 8, 246))
    dist = np.sqrt(((arr.astype(int) - ref) ** 2).sum(axis=-1))
    return dist > 60


def test_variant_list_has_15():
    assert len(VARIANTS) == 15 and len(set(VARIANTS)) == 15


@pytest.mark.parametrize("variant", VARIANTS)
def test_synthetic_png_opens_and_ground_truth(variant):
    sheet = make_sheet(variant, rows=2, cols=3)
    img = Image.open(io.BytesIO(sheet.png_bytes()))
    img.load()
    assert img.size == (3 * 256, 2 * 256)
    assert sheet.grid == (2, 3) and len(sheet.cells) == 6
    assert img.mode == ("RGBA" if variant == "native_alpha" else "RGB")

    fg = foreground_mask(sheet)
    covered = np.zeros_like(fg)
    for c in sheet.cells:
        if c.empty:
            assert c.feet is None
            continue
        x0, y0, x1, y1 = c.bbox
        # bbox is tight: every side has foreground; and it contains the feet x
        assert fg[y0:y1, x0].any() and fg[y0:y1, x1 - 1].any()
        assert fg[y0, x0:x1].any() and fg[y1 - 1, x0:x1].any()
        fx, fy = c.feet
        assert x0 <= fx < x1 and fg[fy - 1, x0:x1].any()
        if variant != "thin_below_feet":
            assert y1 == fy and not fg[fy, x0:x1].any()
        covered[y0:y1, x0:x1] = True
        for sx0, sy0, sx1, sy1 in c.extras.get("specks", []):
            covered[sy0:sy1, sx0:sx1] = True
    assert not (fg & ~covered).any(), "foreground outside all recorded boxes"


@pytest.mark.parametrize("variant", VARIANTS)
@pytest.mark.parametrize("grid", GRIDS)
def test_synthetic_deterministic(variant, grid):
    a = make_sheet(variant, *grid, seed=7)
    b = make_sheet(variant, *grid, seed=7)
    assert a.png_bytes() == b.png_bytes()
    assert [c.bbox for c in a.cells] == [c.bbox for c in b.cells]


def test_synthetic_variant_properties():
    s = make_sheet("clean")
    assert s.key_color == (255, 0, 255)
    assert tuple(s.image.getpixel((0, 0))) == (255, 0, 255)
    assert len({(c.bbox[2] - c.bbox[0], c.bbox[3] - c.bbox[1]) for c in s.cells}) == 1

    m = make_sheet("model_like_bg")
    assert tuple(m.image.getpixel((256, 256))) in {(250, 3, 250), (249, 4, 250), (249, 4, 249)}
    assert tuple(m.image.getpixel((0, 0))) == (240, 13, 242)

    sg = make_sheet("shifted_gutters")
    assert sg.col_edges[1] == 256 + round(0.04 * 512)

    ng = make_sheet("narrow_gutter")
    left, right = ng.cell(0, 0).bbox, ng.cell(0, 1).bbox
    assert right[0] - left[2] == 20

    assert make_sheet("edge_touch").cell(0, 0).bbox[2] > 256
    h = [c.bbox[3] - c.bbox[1] for c in make_sheet("scale_drift_12").cells]
    assert max(h) / min(h) == pytest.approx(1.12, abs=0.03)
    sj = make_sheet("baseline_jitter", 1, 6)
    ys = [c.feet[1] for c in sj.cells]
    assert max(ys) - min(ys) == 30
    assert [c.empty for c in make_sheet("empty_cell").cells] == [False, False, False, True]
    assert all(len(c.extras["specks"]) == 5 for c in make_sheet("specks").cells)
    ds = make_sheet("detached_sword").cells[0]
    assert ds.extras["sword_bbox"][0] - ds.extras["body_bbox"][2] == 6
    tf = make_sheet("thin_below_feet").cells[0]
    assert tf.bbox[3] == tf.feet[1] + 12
    assert (230, 90, 200) in {tuple(p) for p in np.asarray(make_sheet("pinkish_character").image).reshape(-1, 3)}
    na = make_sheet("native_alpha")
    assert na.key_color is None and na.image.getpixel((0, 0))[3] == 0
    wa = make_sheet("wide_attack").cells[0]
    assert wa.bbox[2] - wa.bbox[0] > 0.7 * 256 * 0.8


def test_synthetic_configurable_grid_and_cell_size():
    s = make_sheet("clean", rows=3, cols=4, cell_size=(160, 192))
    assert s.image.size == (640, 576) and len(s.cells) == 12
    assert s.cell(2, 3).rect == (480, 384, 640, 576)


def test_synthetic_asymmetric_right_not_mirror_symmetric():
    s = make_sheet("asymmetric_right", 1, 1)
    arr = np.asarray(s.image)
    assert not np.array_equal(arr, arr[:, ::-1])
