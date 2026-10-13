"""Plan API: ``handed`` turns the left/right mirror off, is validated on create and on PUT."""

from .api_sync_helpers import char_url, err, make_character, make_plan


def topdown_plan(client, **body):
    make_character(client, "hero", view="topdown")
    return make_plan(client, "hero", actions=["walk"], view="topdown", **body)


def test_sg_image_handed_api_create_turns_the_mirror_off_and_left_is_generated(client):
    plain = topdown_plan(client)
    assert plain["plan"]["mirror"] == {"left": "right"} and "handed" not in plain["plan"]
    body = make_plan(client, "hero", actions=["walk"], view="topdown", handed="right")
    assert body["plan"]["handed"] == "right" and body["plan"]["mirror"] == {}
    left = [u for u in body["units"] if u["direction"] == "left"]
    assert left and left[0]["mirrored"] is False


def test_sg_image_handed_api_rejects_an_unknown_hand_and_a_mirror_conflict(client):
    topdown_plan(client)
    err(client.post(char_url("hero", "/plan"), json={"actions": ["walk"], "view": "topdown", "handed": "both"}), 422, "validation_error")
    err(client.post(char_url("hero", "/plan"), json={"actions": ["walk"], "view": "topdown", "handed": "left", "mirror": True}),
        400, "invalid_param")


def test_sg_image_handed_api_put_refuses_a_handed_plan_that_still_mirrors(client):
    plan = topdown_plan(client)["plan"]
    plan["handed"] = "left"  # mirror is still {"left": "right"}
    err(client.put(char_url("hero", "/plan"), json={"plan": plan}), 400, "invalid_param")
    plan["mirror"] = {}
    r = client.put(char_url("hero", "/plan"), json={"plan": plan})
    assert r.status_code == 200 and r.json()["plan"]["handed"] == "left"
