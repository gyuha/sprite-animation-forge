"""Front / back views keep their view (docs/14 area B): a prompt for a down/up facing says not to turn toward a three-quarter angle."""

import pytest
from sprite_forge import plan as plan_mod
from sprite_forge import prompt as pr

KEEP = "do not turn the body toward a three-quarter angle"


def consistency(text):
    return text.split("CONSISTENCY RULES\n")[1].split("\n\n")[0]


@pytest.mark.parametrize("direction", ["down", "up"])
def test_sg_image_view_keep_topdown_down_and_up_say_to_keep_the_facing(direction):
    plan = plan_mod.build_plan("hero", ["walk"], view="topdown", art_style="project_native", has_reference=True, profile=None)
    text = pr.build_prompt(plan, None, "walk", direction).text
    assert KEEP in consistency(text) and pr.validate_prompt(text) == []


@pytest.mark.parametrize("view", ["front", "rear"])
def test_sg_image_view_keep_front_and_rear_views_say_it_too(view):
    plan = plan_mod.build_plan("hero", ["idle"], view=view, art_style="project_native", has_reference=True, profile=None)
    assert KEEP in consistency(pr.build_prompt(plan, None, "idle").text)


@pytest.mark.parametrize("direction", ["right", "left"])
def test_sg_image_view_keep_profile_facings_do_not_get_the_line(direction):
    plan = plan_mod.build_plan("hero", ["walk"], view="topdown", art_style="project_native", has_reference=True, profile=None,
                               mirror=False)  # without the mirror, left is a generated direction too
    assert KEEP not in pr.build_prompt(plan, None, "walk", direction).text
    side = plan_mod.build_plan("hero", ["walk"], view="side", art_style="project_native", has_reference=True, profile=None)
    assert KEEP not in pr.build_prompt(side, None, "walk").text
