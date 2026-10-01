import pytest

from sprite_forge import plan as pl
from sprite_forge.errors import ForgeError


def mk(actions=("idle",), **kw):
    return pl.build_plan("hero", list(actions), **kw)


@pytest.mark.parametrize(
    "frames,grid",
    [(2, "1x2"), (3, "1x3"), (4, "2x2"), (5, "2x3"), (6, "2x3"), (7, "2x4"), (8, "2x4"), (9, "3x3"),
     (10, "3x4"), (12, "3x4"), (13, "4x4"), (16, "4x4")],
)
def test_plan_grid_table(frames, grid):
    assert pl.grid_for(frames) == grid


@pytest.mark.parametrize("frames", [0, 1, 17, 40])
def test_plan_grid_out_of_range_is_error(frames):
    with pytest.raises(ForgeError):
        pl.grid_for(frames)


@pytest.mark.parametrize(
    "action,frames,grid,loop,fps,anchor,scale,x_anchor",
    [
        ("idle", 4, "2x2", True, 6, "feet", "fit", "mass"),
        ("walk", 6, "2x3", True, 10, "feet", "fit", "mass"),
        ("run", 6, "2x3", True, 12, "feet", "fit", "mass"),
        ("attack", 6, "2x3", False, 12, "feet", "preserve", "feet"),
        ("shoot", 4, "2x2", False, 12, "feet", "preserve", "feet"),
        ("cast", 6, "2x3", False, 10, "feet", "preserve", "feet"),
        ("jump", 4, "2x2", False, 10, "feet", "fit", "mass"),
        ("fall", 2, "1x2", True, 8, "feet", "fit", "mass"),
        ("hurt", 4, "2x2", False, 10, "feet", "fit", "mass"),
        ("death", 8, "2x4", False, 8, "bottom", "preserve", "feet"),
    ],
)
def test_plan_presets_table(action, frames, grid, loop, fps, anchor, scale, x_anchor):
    a = mk([action])["actions"][action]
    assert (a["frames"], a["grid"], a["loop"], a["fps"]) == (frames, grid, loop, fps)
    assert (a["anchor"], a["scale_strategy"], a["x_anchor"], a["components"]) == (anchor, scale, x_anchor, "largest")


def test_plan_frames_override_recomputes_grid():
    a = mk(overrides=pl.parse_overrides(["idle.frames=8"]))["actions"]["idle"]
    assert (a["frames"], a["grid"]) == (8, "2x4")


def test_plan_explicit_grid_override_wins():
    a = mk(overrides=pl.parse_overrides(["idle.frames=4", "idle.grid=1x4"]))["actions"]["idle"]
    assert a["grid"] == "1x4"


def test_plan_override_takes_priority_over_preset():
    ov = pl.parse_overrides(["walk.fps=14", "walk.loop=false", "walk.anchor=bottom", "walk.scale_strategy=preserve"])
    a = mk(["walk"], overrides=ov)["actions"]["walk"]
    assert (a["fps"], a["loop"], a["anchor"], a["scale_strategy"]) == (14, False, "bottom", "preserve")


def test_plan_grid_too_small_for_frames_is_error():
    with pytest.raises(ForgeError):
        mk(overrides=pl.parse_overrides(["idle.frames=6", "idle.grid=2x2"]))


@pytest.mark.parametrize("item", ["idle", "idle.fps", "Idle.fps=3", "idle.nope=1", "idle.fps=x", "idle.loop=maybe"])
def test_plan_bad_override_syntax_is_error(item):
    with pytest.raises(ForgeError):
        pl.parse_overrides([item])


def test_plan_invalid_enum_override_rejected_by_schema():
    with pytest.raises(ForgeError) as e:
        mk(overrides=pl.parse_overrides(["idle.anchor=top"]))
    assert e.value.code == "invalid_params"


def test_plan_override_for_action_not_in_plan_is_error():
    with pytest.raises(ForgeError) as e:
        mk(["idle"], overrides=pl.parse_overrides(["walk.fps=3"]))
    assert e.value.code == "unknown_action"


def test_plan_custom_action_needs_motion():
    with pytest.raises(ForgeError):
        mk(["victory_pose"])
    a = mk(["victory_pose"], overrides=pl.parse_overrides(["victory_pose.motion=raises both arms"]))["actions"]["victory_pose"]
    assert a["motion"] == "raises both arms" and a["qc_profile"] == "action" and a["frames"] == 4


def test_plan_fx_action_defaults():
    ov = pl.parse_overrides(["slash_fx.kind=fx", "slash_fx.motion=white crescent"])
    a = mk(["slash_fx"], overrides=ov)["actions"]["slash_fx"]
    assert (a["kind"], a["anchor"], a["x_anchor"], a["components"], a["qc_profile"]) == ("fx", "center", "bbox", "all", "fx")


def test_plan_bundles_expand():
    assert pl.resolve_actions(None, "side-action") == ["idle", "walk", "run", "jump", "fall", "attack", "hurt", "death"]
    assert pl.resolve_actions(None, "side-basic") == ["idle", "walk", "run", "attack"]
    assert pl.resolve_actions(None, "topdown-rpg") == ["idle", "walk", "attack", "hurt", "death"]
    assert pl.resolve_actions(None, "npc") == ["idle", "walk"]
    p = mk(pl.resolve_actions(None, "side-basic"))
    assert p["order"] == ["idle", "walk", "run", "attack"] and list(p["actions"]) == p["order"]


def test_plan_actions_and_bundle_errors():
    with pytest.raises(ForgeError):
        pl.resolve_actions("idle", "npc")
    with pytest.raises(ForgeError):
        pl.resolve_actions(None, "nope")
    with pytest.raises(ForgeError):
        pl.resolve_actions(None, None)
    with pytest.raises(ForgeError):
        pl.resolve_actions("idle,idle", None)


def profile(primary=(), secondary=(), **extra):
    ident = {"primary_colors": list(primary), "secondary_colors": list(secondary), "weapon": "", "clothing": "",
             "accessories": []}
    ident.update(extra)
    return {"identity": ident}


def test_plan_key_color_default_is_magenta():
    assert mk(profile=profile(["#C8281E"]))["key_color"] == "#FF00FF"
    assert mk()["key_color"] == "#FF00FF"


def test_plan_key_color_conflict_switches_to_green_with_note():
    p = mk(profile=profile(["#E65AC8"], ["#202020"]))
    assert p["key_color"] == "#00FF00"
    assert any("#00FF00" in a for a in p["assumptions"])


def test_plan_key_color_secondary_conflict_also_switches():
    assert mk(profile=profile(["#202020"], ["#FF00FF"]))["key_color"] == "#00FF00"


def test_plan_key_color_both_conflict_keeps_magenta_and_warns():
    p = mk(profile=profile(["#FF00FF", "#00FF00"]))
    assert p["key_color"] == "#FF00FF"
    assert any("key_color" in a for a in p["assumptions"])


def test_plan_art_style_auto_resolution():
    assert mk(has_reference=True)["art_style"] == "project_native"
    assert mk(has_reference=False)["art_style"] == "clean_hd"
    assert mk(art_style="pixel_art", has_reference=True)["art_style"] == "pixel_art"


def test_plan_cell_override():
    assert mk(cell="256x256")["cell"] == {"w": 256, "h": 256}
    with pytest.raises(ForgeError):
        mk(cell="big")


def test_plan_side_view_defaults_single_direction_no_mirror():
    p = mk()
    assert (p["view"], p["facing"], p["directions"], p["mirror"]) == ("side", "right", ["right"], {})


def test_plan_topdown_defaults_four_directions_with_mirror():
    p = mk(view="topdown")
    assert p["facing"] == "down"
    assert p["directions"] == ["down", "up", "right", "left"]
    assert p["mirror"] == {"left": "right"}


def test_plan_direction_no_mirror_option():
    p = mk(view="topdown", mirror=False)
    assert p["mirror"] == {}
    assert [u["mirrored"] for u in pl.units(p)] == [False] * 4


def test_plan_direction_explicit_mirror_needs_left_and_right():
    with pytest.raises(ForgeError):
        mk(view="topdown", directions=["down", "up"], mirror=True)
    assert mk(view="topdown", directions=["down", "up"])["mirror"] == {}


def test_plan_direction_facing_follows_directions_and_validates():
    assert mk(view="topdown", directions=["up", "right"])["facing"] == "up"
    with pytest.raises(ForgeError):
        mk(view="topdown", directions=["up", "right"], facing="down")


def test_plan_direction_action_subset():
    p = mk(["idle", "death"], view="topdown", overrides=pl.parse_overrides(["death.directions=down"]))
    assert p["actions"]["death"]["directions"] == ["down"]
    assert [u["unit"] for u in pl.units(p) if u["action"] == "death"] == ["death/down"]
    with pytest.raises(ForgeError):
        mk(["idle"], view="side", overrides=pl.parse_overrides(["idle.directions=down"]))


def test_plan_direction_mirror_needs_right_in_action_directions():
    with pytest.raises(ForgeError):
        mk(["idle"], view="topdown", overrides=pl.parse_overrides(["idle.directions=down,left"]))


def test_plan_direction_units_generation_order_and_estimate():
    p = mk(["idle", "walk"], view="topdown")
    us = pl.units(p)
    assert [u["unit"] for u in us[:4]] == ["idle/down", "idle/right", "idle/up", "idle/left"]
    assert [u["mirrored"] for u in us[:4]] == [False, False, False, True]
    assert pl.estimated_seconds(p) == 6 * 90
    assert pl.estimated_seconds(mk(["idle", "walk"])) == 2 * 90


def test_plan_direction_topdown_rpg_call_count():
    p = mk(pl.resolve_actions(None, "topdown-rpg"), view="topdown")
    assert pl.estimated_seconds(p) == 15 * 90  # docs/02 7: 15 calls, 22m30s


def test_plan_direction_mirror_asymmetry_warning():
    p = mk(view="topdown", profile=profile(weapon="sword held in the right hand"))
    assert any("비대칭" in a for a in p["assumptions"])
    assert not any("비대칭" in a for a in mk(view="topdown", mirror=False, profile=profile(weapon="right-hand sword"))["assumptions"])


def test_plan_resolve_unit_single_direction():
    p = mk(["walk"])
    assert pl.resolve_unit(p, "walk", None) == ("walk", "right", False)
    assert pl.resolve_unit(p, "walk", "right") == ("walk", "right", False)
    with pytest.raises(ForgeError) as e:
        pl.resolve_unit(p, "walk", "up")
    assert e.value.code == "invalid_direction"


def test_plan_direction_resolve_unit_multi_direction_rules():
    p = mk(["walk", "death"], view="topdown", overrides=pl.parse_overrides(["death.directions=down"]))
    assert pl.resolve_unit(p, "walk", "up") == ("walk/up", "up", False)
    for direction, code in [(None, "direction_required"), ("left", "mirrored_direction")]:
        with pytest.raises(ForgeError) as e:
            pl.resolve_unit(p, "walk", direction)
        assert e.value.code == code
    with pytest.raises(ForgeError) as e:
        pl.resolve_unit(p, "death", "up")
    assert e.value.code == "invalid_direction"
    with pytest.raises(ForgeError) as e:
        pl.resolve_unit(p, "run", "up")
    assert e.value.code == "unknown_action"


def test_plan_direction_left_allowed_when_mirror_off():
    p = mk(["walk"], view="topdown", mirror=False)
    assert pl.resolve_unit(p, "walk", "left") == ("walk/left", "left", False)


def test_plan_process_params_from_plan():
    p = mk(["attack"], cell="256x256", profile=profile(["#E65AC8"]))
    pp = pl.process_params(p, "attack")
    assert (pp.rows, pp.cols, pp.frames, pp.cell_w, pp.cell_h) == (2, 3, 6, 256, 256)
    assert pp.key_color == (0, 255, 0)
    assert (pp.anchor, pp.x_anchor, pp.scale_strategy) == ("feet", "feet", "preserve")
