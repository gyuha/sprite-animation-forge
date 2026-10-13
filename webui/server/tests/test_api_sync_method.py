"""Generation method per action over the API: presets, plan POST/PUT, unavailable video."""

from .api_sync_helpers import char_url, err, make_character


def test_api_sync_presets_list_the_generation_methods_and_video_is_unavailable(client):
    methods = client.get("/api/presets").json()["methods"]
    assert methods["grid"]["available"] and methods["breathe"]["available"]
    assert methods["video"]["available"] is False and methods["video"]["reason"]


def test_api_sync_plan_post_with_breathe_method(client):
    make_character(client)
    r = client.post(char_url("hero", "/plan"), json={"actions": ["idle", "walk"], "set": ["idle.method=breathe"]})
    assert r.status_code == 200, r.text
    acts = r.json()["plan"]["actions"]
    assert (acts["idle"]["method"], acts["idle"]["grid"], acts["idle"]["frames"]) == ("breathe", "1x1", 6)
    assert acts["walk"]["method"] == "grid"


def test_api_sync_plan_post_video_method_is_a_precondition_failure(client):
    make_character(client)
    r = client.post(char_url("hero", "/plan"), json={"actions": ["walk"], "set": ["walk.method=video"]})
    body = err(r, 412, "precondition_failed")
    assert body["detail"]["reason"] == "method_unavailable"


def test_api_sync_plan_post_rejects_unknown_method(client):
    make_character(client)
    r = client.post(char_url("hero", "/plan"), json={"actions": ["walk"], "set": ["walk.method=teleport"]})
    assert r.status_code == 400


def test_api_sync_plan_put_accepts_a_breathe_action_whose_frames_exceed_its_1x1_grid(client):
    make_character(client)
    plan = client.post(char_url("hero", "/plan"), json={"actions": ["idle"], "set": ["idle.method=breathe"]}).json()["plan"]
    plan["actions"]["idle"]["frames"] = 8
    r = client.put(char_url("hero", "/plan"), json={"plan": plan})
    assert r.status_code == 200, r.text
    assert r.json()["plan"]["actions"]["idle"]["frames"] == 8
