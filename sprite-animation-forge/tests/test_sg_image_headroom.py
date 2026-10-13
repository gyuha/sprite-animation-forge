"""Head-room for actions that reach above the standing head (docs/14 area B): the grid rules ask for 20% empty cell height above
the head for attack and jump; other actions are untouched."""

import pytest
from sprite_forge import plan as plan_mod
from sprite_forge import prompt as pr


def prompt_of(action, **kw):
    plan = plan_mod.build_plan("hero", [action], view="side", art_style="project_native", has_reference=True, profile=None)
    return pr.build_prompt(plan, None, action, **kw)


def grid_rules(text):
    return text.split("GRID RULES\n")[1].split("\n\n")[0]


@pytest.mark.parametrize("action", ["attack", "jump"])
def test_sg_image_headroom_actions_ask_for_twenty_percent_above_the_head(action):
    res = prompt_of(action)
    rules = grid_rules(res.text)
    assert "at least 20% of the cell height empty above the head of the standing character" in rules
    assert "Leave at least 8% empty background margin" in rules  # the side margin rule is still there and still validated
    assert pr.validate_prompt(res.text) == []


@pytest.mark.parametrize("action", ["idle", "walk", "run", "hurt", "death"])
def test_sg_image_headroom_other_actions_have_no_head_room_line(action):
    assert "above the head" not in prompt_of(action).text


def test_sg_image_headroom_survives_the_edge_touch_recovery_margin():
    rules = grid_rules(prompt_of("attack", recovery=["edge_touch"]).text)
    assert "Leave at least 15% empty background margin" in rules and "at least 20% of the cell height" in rules
