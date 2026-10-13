"""Handedness (docs/14 area B): a character with an item in one hand keeps it there. The plan's ``handed`` turns the left/right
mirror off (a mirrored view would put the item in the other hand) and the prompt says which hand holds it."""

import json

import pytest
from sprite_forge import plan as plan_mod
from sprite_forge import prompt as pr
from sprite_forge import schemas
from sprite_forge.errors import ForgeError

TOPDOWN = dict(view="topdown", art_style="project_native", has_reference=True, profile=None)


def topdown(**kw):
    return plan_mod.build_plan("hero", ["walk"], **TOPDOWN, **kw)


def consistency(text):
    return text.split("CONSISTENCY RULES\n")[1].split("\n\n")[0]


def test_sg_image_handed_turns_the_mirror_off_and_left_becomes_a_generated_unit():
    plain, handed = topdown(), topdown(handed="right")
    assert plain["mirror"] == {"left": "right"} and "handed" not in plain  # absent = none; existing plans are unchanged
    assert handed["mirror"] == {} and handed["handed"] == "right"
    assert any("손잡이" in n for n in handed["assumptions"])
    schemas.validate("animation-plan", handed)
    left = [u for u in plan_mod.units(handed) if u["direction"] == "left"]
    assert left and not left[0]["mirrored"]
    assert [u for u in plan_mod.units(plain) if u["direction"] == "left"][0]["mirrored"]


def test_sg_image_handed_none_is_the_plain_plan_and_an_explicit_mirror_conflicts():
    assert topdown(handed="none") == topdown()
    with pytest.raises(ForgeError) as e:
        topdown(handed="left", mirror=True)
    assert e.value.code == "invalid_params" and "handed" in e.value.message
    assert topdown(handed="left", mirror=False)["mirror"] == {}
    with pytest.raises(ForgeError):
        topdown(handed="both")


def test_sg_image_handed_schema_rejects_an_unknown_value():
    plan = topdown(handed="right")
    plan["handed"] = "both"
    with pytest.raises(Exception):  # jsonschema.ValidationError
        schemas.validate("animation-plan", plan)


@pytest.mark.parametrize("handed,direction,expect", [
    ("right", "right", "nearer to the viewer"), ("right", "left", "farther from the viewer"),
    ("left", "left", "nearer to the viewer"), ("left", "right", "farther from the viewer"),
])
def test_sg_image_handed_profile_views_name_the_near_or_far_arm(handed, direction, expect):
    text = pr.build_prompt(topdown(handed=handed), None, "walk", direction).text
    line = [ln for ln in consistency(text).splitlines() if "held in the character's" in ln][0]
    assert f"{handed} hand" in line and expect in line and pr.validate_prompt(text) == []


@pytest.mark.parametrize("handed,direction,side", [("right", "down", "left"), ("left", "down", "right"),
                                                   ("right", "up", "right"), ("left", "up", "left")])
def test_sg_image_handed_front_and_back_views_name_the_side_of_the_image(handed, direction, side):
    text = pr.build_prompt(topdown(handed=handed), None, "walk", direction).text
    line = [ln for ln in consistency(text).splitlines() if "held in the character's" in ln][0]
    assert f"{handed} hand" in line and f"on the {side} side of the image" in line


def test_sg_image_handed_without_the_field_the_prompt_has_no_hand_line():
    for direction in ("right", "down"):
        assert "held in the character's" not in pr.build_prompt(topdown(), None, "walk", direction).text


def test_sg_image_handed_cli_plan_option(forge):
    forge.ok("init", "hero", "--view", "topdown")
    out = forge.ok("plan", "hero", "--actions", "walk", "--handed", "left")
    plan = json.loads((forge.root / "hero/animation-plan.json").read_text())
    assert plan["handed"] == "left" and plan["mirror"] == {} and out
    assert forge.run("plan", "hero", "--actions", "walk", "--handed", "both")[0] == 1
    forge.ok("plan", "hero", "--actions", "walk", "--handed", "none")
    assert "handed" not in json.loads((forge.root / "hero/animation-plan.json").read_text())
