import json
from copy import deepcopy

import numpy as np
import pytest
from fixtures.synthetic.make import make_sheet
from PIL import Image

from sprite_forge import plan as pl
from sprite_forge import schemas
from sprite_forge.errors import ForgeError
from sprite_forge.export import atlas as at
from sprite_forge.export import gif as gf
from sprite_forge.export import phaser as ph
from sprite_forge.export.validate import validate_export

# ---- helpers ------------------------------------------------------------------------------


def make_plan(actions, cell="128x128", **kw):
    return pl.build_plan("hero", actions, cell=cell, **kw)


def fake_frames(plan, skip=()):
    """unit -> RGBA frames of the plan cell size; every frame has a distinct colour."""
    w, h = plan["cell"]["w"], plan["cell"]["h"]
    out, n = {}, 0
    for u in at.export_units(plan):
        if u["unit"] in skip:
            continue
        frames = []
        for _ in range(plan["actions"][u["action"]]["frames"]):
            n += 1
            frames.append(Image.new("RGBA", (w, h), (n % 256, (n // 256) % 256, 7, 255)))
        out[u["unit"]] = frames
    return out


def build_all(plan):
    atlas = at.build_atlas(plan, fake_frames(plan))
    origin = ph.origin_for(118, atlas.cell[1])
    info = {r["unit"]: {"attempt": "001", "qc": "pass"} for r in atlas.rows}
    return (atlas, origin, ph.phaser_json(atlas, origin, "hero.png"), ph.animations_json(plan, atlas),
            ph.generic_json(plan, atlas, origin, "hero.png"),
            ph.meta_json(plan, atlas, origin, 118, "0" * 64, "hero.png", info))


def sheet_for(path, frames):
    rows, cols = {4: (2, 2), 6: (2, 3)}[frames]
    make_sheet("asymmetric_right", rows=rows, cols=cols, cell_size=(256, 256)).save(path)


def accept(forge, tmp_path, unit_args, frames):
    raw = tmp_path / f"raw_{unit_args[0]}_{'_'.join(unit_args[1:]) or 'x'}.png"
    sheet_for(raw, frames)
    forge.ok("import-raw", "hero", unit_args[0], raw, *unit_args[1:])
    forge.ok("process", "hero", unit_args[0], *unit_args[1:])
    return forge.ok("accept", "hero", unit_args[0], *unit_args[1:])


@pytest.fixture
def side_hero(forge, tmp_path):
    forge.ok("init", "hero")
    forge.ok("plan", "hero", "--actions", "idle,walk")
    accept(forge, tmp_path, ["idle"], 4)
    accept(forge, tmp_path, ["walk"], 6)
    return forge


@pytest.fixture
def topdown_hero(forge, tmp_path):
    forge.ok("init", "hero", "--view", "topdown")
    forge.ok("plan", "hero", "--actions", "idle,walk")
    for d in ("down", "up", "right"):
        accept(forge, tmp_path, ["idle", "--direction", d], 4)
        accept(forge, tmp_path, ["walk", "--direction", d], 6)
    return forge


def rgba(path):
    return np.array(Image.open(path).convert("RGBA"))


# ---- atlas --------------------------------------------------------------------------------


def test_atlas_size_formula_docs_examples():
    assert at.atlas_size(128, 128, 4, 6) == (782, 522)
    assert at.atlas_size(128, 128, 8, 8) == (1042, 1042)
    assert at.atlas_size(128, 128, 20, 8) == (1042, 2602)


def test_atlas_basic_bundle_is_782x522():
    plan = make_plan(["idle", "walk", "run", "attack"])
    atlas = at.build_atlas(plan, fake_frames(plan))
    assert atlas.size == (782, 522) == atlas.image.size


def test_atlas_side_action_bundle_is_1042x1042():
    plan = make_plan(pl.BUNDLES["side-action"])
    assert at.build_atlas(plan, fake_frames(plan)).size == (1042, 1042)


def test_atlas_topdown_rpg_128_fits_and_256_is_too_large():
    plan = make_plan(pl.BUNDLES["topdown-rpg"], view="topdown")
    atlas = at.build_atlas(plan, fake_frames(plan))
    assert atlas.size == (1042, 2602) and len(atlas.rows) == 20
    big = make_plan(pl.BUNDLES["topdown-rpg"], view="topdown", cell="256x256")
    with pytest.raises(ForgeError) as e:
        at.build_atlas(big, fake_frames(big))
    assert e.value.code == "atlas_too_large"


def test_atlas_limit_is_4096_inclusive():
    assert at.atlas_size(128, 128, 31, 2) == (262, 4032)
    assert at.atlas_size(256, 256, 15, 2) == (518, 3872)
    for args in ((128, 128, 32, 2), (256, 256, 16, 2), (128, 128, 1, 32)):
        with pytest.raises(ForgeError) as e:
            at.atlas_size(*args)
        assert e.value.code == "atlas_too_large"


def test_atlas_frame_positions_and_pixels():
    plan = make_plan(["idle", "walk"])
    frames = fake_frames(plan)
    atlas = at.build_atlas(plan, frames)
    by_name = {e["name"]: e for e in atlas.entries}
    assert (by_name["idle_0"]["x"], by_name["idle_0"]["y"]) == (2, 2)
    assert (by_name["idle_1"]["x"], by_name["idle_1"]["y"]) == (132, 2)
    assert (by_name["walk_5"]["x"], by_name["walk_5"]["y"]) == (2 + 5 * 130, 2 + 130)
    arr = np.array(atlas.image)
    for e in atlas.entries:
        got = arr[e["y"]:e["y"] + e["h"], e["x"]:e["x"] + e["w"]]
        assert np.array_equal(got, np.array(frames[e["unit"]][e["index"]]))
    assert arr[0, 0, 3] == 0 and arr[2 + 128, 2, 3] == 0  # padding stays transparent


def test_atlas_row_order_body_before_fx_and_directions():
    plan = make_plan(["slash_fx", "walk", "idle"], view="topdown",
                     overrides={"slash_fx": {"kind": "fx", "motion": "a slash"}})
    units = [u["unit"] for u in at.export_units(plan)]
    assert units == [f"{a}/{d}" for a in ("walk", "idle", "slash_fx") for d in ("down", "up", "right", "left")]


def test_atlas_frame_naming_rules():
    assert at.frame_name("walk", None, 5, False) == "walk_5"
    assert at.frame_name("walk", "up", 3, True) == "walk_up_3"
    side = make_plan(["idle"])
    assert [e["name"] for e in at.build_atlas(side, fake_frames(side)).entries] == [f"idle_{i}" for i in range(4)]
    top = make_plan(["idle"], view="topdown")
    names = {e["name"] for e in at.build_atlas(top, fake_frames(top)).entries}
    assert names == {f"idle_{d}_{i}" for d in ("down", "up", "right", "left") for i in range(4)}


def test_atlas_cell_mismatch():
    plan = make_plan(["idle"])
    frames = fake_frames(plan)
    frames["idle"][2] = Image.new("RGBA", (64, 128))
    with pytest.raises(ForgeError) as e:
        at.build_atlas(plan, frames)
    assert e.value.code == "cell_mismatch"


def test_atlas_skips_units_without_frames():
    plan = make_plan(["idle", "walk"])
    atlas = at.build_atlas(plan, fake_frames(plan, skip={"idle"}))
    assert [r["unit"] for r in atlas.rows] == ["walk"] and atlas.size == (782, 132)


# ---- phaser json / animations -------------------------------------------------------------


def test_phaser_json_hash_shape_and_anchor():
    plan = make_plan(["idle", "walk"])
    atlas, origin, phaser, *_ = build_all(plan)
    assert origin == {"x": 0.5, "y": 0.921875}
    f = phaser["frames"]["idle_1"]
    assert f == {"frame": {"x": 132, "y": 2, "w": 128, "h": 128}, "rotated": False, "trimmed": False,
                 "spriteSourceSize": {"x": 0, "y": 0, "w": 128, "h": 128}, "sourceSize": {"w": 128, "h": 128},
                 "anchor": {"x": 0.5, "y": 0.921875}}
    assert phaser["meta"]["image"] == "hero.png" and atlas.size == (782, 262)
    assert phaser["meta"]["size"] == {"w": atlas.size[0], "h": atlas.size[1]}
    assert phaser["meta"]["format"] == "RGBA8888" and phaser["meta"]["scale"] == "1"


def test_phaser_animations_repeat_and_frame_rate():
    plan = make_plan(["idle", "walk", "attack"])
    _, _, _, anims, *_ = build_all(plan)
    assert anims["idle"] == {"frames": [f"idle_{i}" for i in range(4)], "frameRate": 6, "repeat": -1}
    assert anims["walk"]["frameRate"] == 10 and anims["walk"]["repeat"] == -1
    assert anims["attack"] == {"frames": [f"attack_{i}" for i in range(6)], "frameRate": 12, "repeat": 0}
    assert all(set(a) == {"frames", "frameRate", "repeat"} for a in anims.values())


def test_phaser_animations_follow_plan_overrides():
    plan = make_plan(["walk"], overrides=pl.parse_overrides(["walk.loop=false", "walk.fps=7"]))
    _, _, _, anims, *_ = build_all(plan)
    assert anims["walk"]["repeat"] == 0 and anims["walk"]["frameRate"] == 7


def test_phaser_topdown_has_eight_animation_keys_with_left_frames():
    plan = make_plan(["idle", "walk"], view="topdown")
    atlas, _, phaser, anims, generic, meta = build_all(plan)
    assert set(anims) == {f"{a}_{d}" for a in ("idle", "walk") for d in ("down", "up", "right", "left")}
    assert len(anims) == 8
    for d in ("down", "up", "right", "left"):
        assert anims[f"walk_{d}"]["frames"] == [f"walk_{d}_{i}" for i in range(6)]
        assert all(n in phaser["frames"] for n in anims[f"walk_{d}"]["frames"])
    assert {m["direction"] for m in meta["actions"]} == {"down", "up", "right", "left"}


def test_phaser_meta_json_fields():
    plan = make_plan(["idle", "walk"])
    atlas, origin, _, _, generic, meta = build_all(plan)
    assert meta["character"] == "hero" and meta["cell"] == {"w": 128, "h": 128}
    assert meta["baseline_y"] == 118 and meta["origin"] == {"x": 0.5, "y": 118 / 128}
    assert meta["padding"] == 2 and meta["view"] == "side" and meta["facing"] == "right"
    assert meta["actions"][1] == {"name": "walk", "direction": None, "unit": "walk", "row": 1, "frames": 6,
                                  "fps": 10, "loop": True, "attempt": "001", "qc": "pass"}
    assert meta["texture"] == {"file": "hero.png", "sha256": "0" * 64, "size": [782, 262]}
    assert generic["frames"][0] == {"name": "idle_0", "action": "idle", "direction": None, "index": 0,
                                    "x": 2, "y": 2, "w": 128, "h": 128}
    assert generic["animations"]["idle"] == {"frames": [f"idle_{i}" for i in range(4)], "fps": 6, "loop": True}


# ---- validation ---------------------------------------------------------------------------


def test_phaser_validation_accepts_a_good_export():
    plan = make_plan(["idle", "walk"], view="topdown")
    atlas, _, phaser, anims, generic, meta = build_all(plan)
    validate_export(plan, atlas.size, phaser, anims, generic, meta)


def _corrupt(mutate):
    plan = make_plan(["idle", "walk"])
    atlas, _, phaser, anims, generic, meta = build_all(plan)
    phaser, anims, generic, meta = map(deepcopy, (phaser, anims, generic, meta))
    mutate(phaser, anims, generic, meta)
    with pytest.raises(ForgeError) as e:
        validate_export(plan, atlas.size, phaser, anims, generic, meta)
    assert e.value.code == "export_validation_failed"
    return "; ".join(e.value.extra["problems"])


def test_phaser_validation_catches_rect_outside_texture():
    msg = _corrupt(lambda p, a, g, m: p["frames"]["walk_5"]["frame"].update(x=900))
    assert "outside" in msg


def test_phaser_validation_catches_negative_rect():
    assert "outside" in _corrupt(lambda p, a, g, m: p["frames"]["idle_0"]["frame"].update(y=-1))


def test_phaser_validation_catches_overlap():
    msg = _corrupt(lambda p, a, g, m: p["frames"]["idle_1"]["frame"].update(x=100))
    assert "overlaps" in msg


def test_phaser_validation_catches_dangling_animation_reference():
    msg = _corrupt(lambda p, a, g, m: a["walk"]["frames"].append("walk_99"))
    assert "walk_99" in msg


def test_phaser_validation_catches_frame_count_mismatch():
    def drop(p, a, g, m):
        a["idle"]["frames"].pop()
        m["actions"][0]["frames"] = 3
    assert "plan frames=4" in _corrupt(drop)


def test_phaser_validation_catches_missing_meta_origin():
    assert "origin" in _corrupt(lambda p, a, g, m: m.pop("origin"))


# ---- gif ----------------------------------------------------------------------------------


def _gif_frames(data):
    import io

    im = Image.open(io.BytesIO(data))
    out = []
    for i in range(im.n_frames):
        im.seek(i)
        out.append(im.info["duration"])
    return im, out


def test_gif_frame_duration_rule():
    assert [gf.frame_duration_ms(f) for f in (6, 10, 12, 24, 60)] == [170, 100, 80, 40, 20]


def test_gif_frames_durations_loop_and_last_hold():
    frames = [Image.new("RGBA", (16, 16), (i * 40, 20, 200, 255)) for i in range(4)]
    im, durations = _gif_frames(gf.render_gif(frames, 12))
    assert durations == [80, 80, 80, 80 + 400]
    assert im.info["loop"] == 0 and im.size == (16, 16)


def test_gif_is_deterministic_and_binarizes_alpha():
    a = Image.new("RGBA", (8, 8), (255, 0, 0, 255))
    a.putpixel((0, 0), (255, 0, 0, 127))  # below 128 -> transparent
    a.putpixel((1, 0), (255, 0, 0, 128))  # at 128 -> opaque
    data = gf.render_gif([a, a.copy()], 10)
    assert data == gf.render_gif([a, a.copy()], 10)
    import io

    first = Image.open(io.BytesIO(data)).convert("RGBA")
    assert first.getpixel((0, 0))[3] == 0 and first.getpixel((1, 0))[3] == 255


# ---- CLI export ---------------------------------------------------------------------------


def test_export_cli_side_end_to_end(side_hero):
    out = side_hero.ok("export", "hero", "--engine", "phaser")
    assert out["warnings"] == []
    assert out["files"] == ["animations.json", "atlas/hero.generic.json", "atlas/hero.json", "atlas/hero.meta.json",
                            "atlas/hero.png", "preview/idle.gif", "preview/walk.gif", "qc-report.json"]
    cd = side_hero.root / "hero"
    assert all((cd / f).is_file() for f in out["files"])
    assert not (cd / ".export.new").exists()
    assert Image.open(cd / "atlas/hero.png").size == (2 + 6 * 130, 2 + 2 * 130)
    phaser = json.loads((cd / "atlas/hero.json").read_text())
    anims = json.loads((cd / "animations.json").read_text())
    meta = json.loads((cd / "atlas/hero.meta.json").read_text())
    assert set(anims) == {"idle", "walk"} and len(phaser["frames"]) == 10
    assert meta["origin"] == {"x": 0.5, "y": 0.921875} and meta["baseline_y"] == 118
    scale = json.loads((cd / "character-scale-profile.json").read_text())
    assert meta["baseline_y"] == scale["baseline_y"]
    # pixel content of the atlas equals the accepted frames
    arr = rgba(cd / "atlas/hero.png")
    f = phaser["frames"]["walk_3"]["frame"]
    assert np.array_equal(arr[f["y"]:f["y"] + f["h"], f["x"]:f["x"] + f["w"]], rgba(cd / "walk/frames/003.png"))


def test_export_cli_manifest_hashes_and_texture_sha(side_hero):
    import hashlib

    out = side_hero.ok("export", "hero")
    cd = side_hero.root / "hero"
    m = json.loads((cd / "manifest.json").read_text())
    schemas.validate("manifest", m)
    files = m["exports"]["phaser"]["files"]
    assert sorted(files) == out["files"]
    for rel, digest in files.items():
        assert digest == "sha256:" + hashlib.sha256((cd / rel).read_bytes()).hexdigest()
    meta = json.loads((cd / "atlas/hero.meta.json").read_text())
    assert meta["texture"]["sha256"] == files["atlas/hero.png"].split(":")[1]


def test_export_cli_character_qc_report(side_hero):
    side_hero.ok("export", "hero")
    rep = json.loads((side_hero.root / "hero/qc-report.json").read_text())
    schemas.validate("qc-report", rep)
    assert rep["character"] == "hero" and set(rep["actions"]) == {"idle", "walk"}
    assert rep["actions"]["idle"]["attempt"] == "001" and rep["forced_accepts"] == []
    assert rep["status"] in ("pass", "warn")


def test_export_cli_is_deterministic(side_hero):
    side_hero.ok("export", "hero")
    cd = side_hero.root / "hero"
    first = {p.name: p.read_bytes() for d in ("atlas", "preview") for p in (cd / d).iterdir()}
    side_hero.ok("export", "hero")
    assert first == {p.name: p.read_bytes() for d in ("atlas", "preview") for p in (cd / d).iterdir()}


def test_export_cli_missing_actions_warning(forge, tmp_path):
    forge.ok("init", "hero")
    forge.ok("plan", "hero", "--actions", "idle,walk")
    accept(forge, tmp_path, ["idle"], 4)
    out = forge.ok("export", "hero")
    assert out["warnings"] == ['missing_actions: ["walk"]']
    anims = json.loads((forge.root / "hero/animations.json").read_text())
    assert list(anims) == ["idle"] and "preview/walk.gif" not in out["files"]


def test_export_cli_nothing_accepted_is_precondition_error(forge):
    forge.ok("init", "hero")
    forge.ok("plan", "hero", "--actions", "idle")
    code, out = forge.run("export", "hero")
    assert code == 3 and out["error_code"] == "nothing_to_export"


def test_export_cli_without_plan_or_character(forge):
    code, out = forge.run("export", "ghost")
    assert code == 3 and out["error_code"] == "no_character"
    forge.ok("init", "hero")
    code, out = forge.run("export", "hero")
    assert code == 3 and out["error_code"] == "no_plan"


def test_export_cli_forced_accept_is_recorded(forge, tmp_path):
    raw = tmp_path / "empty.png"
    make_sheet("empty_cell", rows=2, cols=3, cell_size=(256, 256)).save(raw)
    forge.ok("init", "hero")
    forge.ok("plan", "hero", "--actions", "walk")
    forge.ok("import-raw", "hero", "walk", raw)
    forge.ok("process", "hero", "walk")
    assert forge.ok("accept", "hero", "walk")["forced"] is True
    out = forge.ok("export", "hero")
    rep = json.loads((forge.root / "hero/qc-report.json").read_text())
    assert rep["forced_accepts"] == ["walk"] and rep["status"] == "fail"
    assert rep["actions"]["walk"]["status"] == "fail" and out["warnings"] == []


def test_export_cli_topdown_end_to_end_left_is_flipped_right(topdown_hero):
    out = topdown_hero.ok("export", "hero")
    assert out["warnings"] == [] and len(out["files"]) == 6 + 8  # atlas x4, animations, qc-report + 8 gifs
    cd = topdown_hero.root / "hero"
    assert sorted(p.name for p in (cd / "preview").iterdir()) == sorted(
        f"{a}_{d}.gif" for a in ("idle", "walk") for d in ("down", "up", "right", "left"))
    phaser = json.loads((cd / "atlas/hero.json").read_text())
    anims = json.loads((cd / "animations.json").read_text())
    assert len(anims) == 8
    assert Image.open(cd / "atlas/hero.png").size == (2 + 6 * 130, 2 + 8 * 130)
    arr = rgba(cd / "atlas/hero.png")

    def cell(name):
        f = phaser["frames"][name]["frame"]
        return arr[f["y"]:f["y"] + f["h"], f["x"]:f["x"] + f["w"]]

    for i in range(6):
        for d in ("down", "up", "right", "left"):
            assert f"walk_{d}_{i}" in phaser["frames"]
        assert np.array_equal(cell(f"walk_left_{i}"), np.fliplr(cell(f"walk_right_{i}")))
        assert not np.array_equal(cell(f"walk_left_{i}"), cell(f"walk_right_{i}"))
    meta = json.loads((cd / "atlas/hero.meta.json").read_text())
    left = next(a for a in meta["actions"] if a["unit"] == "walk/left")
    assert left["mirror_of"] == "walk/right" and left["attempt"] == "001"
    rep = json.loads((cd / "qc-report.json").read_text())
    assert len(rep["actions"]) == 8 and rep["actions"]["walk/left"]["attempt"] == "001"


def test_export_cli_topdown_missing_direction_warns(forge, tmp_path):
    forge.ok("init", "hero", "--view", "topdown")
    forge.ok("plan", "hero", "--actions", "walk")
    accept(forge, tmp_path, ["walk", "--direction", "down"], 6)
    out = forge.ok("export", "hero")
    assert out["warnings"] == ['missing_actions: ["walk/up", "walk/right", "walk/left"]']
    assert list(json.loads((forge.root / "hero/animations.json").read_text())) == ["walk_down"]


def test_export_cli_atlas_too_large_leaves_no_outputs(forge, tmp_path):
    forge.ok("init", "hero", "--view", "topdown")
    forge.ok("plan", "hero", "--actions", "walk", "--cell", "2200x128")
    # fabricate an accepted unit whose frames match the huge cell
    cd = forge.root / "hero"
    for d in ("down", "up", "right", "left"):
        (cd / "walk" / d / "frames").mkdir(parents=True)
        for i in range(6):
            Image.new("RGBA", (2200, 128), (1, 2, 3, 255)).save(cd / "walk" / d / "frames" / f"{i:03d}.png")
        (cd / "walk" / d / "qc-report.json").write_text(json.dumps({"status": "pass", "score": 100, "results": []}))
    from sprite_forge import manifest as mf

    def accept_all(m):
        for d in ("down", "up", "right", "left"):
            m["actions"][f"walk/{d}"] = {"kind": "body", "accepted_attempt": "001", "forced": False, "attempts": {}}

    mf.update(cd, accept_all)
    code, out = forge.run("export", "hero")
    assert code == 1 and out["error_code"] == "atlas_too_large"
    assert not (cd / "atlas").exists() and not (cd / ".export.new").exists()
