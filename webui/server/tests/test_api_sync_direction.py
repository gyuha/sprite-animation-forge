"""``?direction=`` rules of the synchronous action endpoints (docs/10 5.1, docs/02 8.1)."""

import json

import pytest

from .api_sync_helpers import char_url, err, make_character, make_plan, png_file, sheet_png, upload_raw

ACT = "/actions/walk"


@pytest.fixture
def topdown(client):
    make_character(client, view="topdown")
    make_plan(client, view="topdown")  # directions down/up/right/left, mirror left<-right
    return client


def _calls(client):
    u = char_url("hero", ACT)
    return {
        "prompt": lambda **p: client.post(u + "/prompt", params=p),
        "upload": lambda **p: client.post(u + "/upload", params=p, files=png_file(sheet_png())),
        "attempts": lambda **p: client.get(u + "/attempts", params=p),
        "attempt": lambda **p: client.get(u + "/attempts/001", params=p),
        "process": lambda **p: client.post(u + "/attempts/001/process", params=p),
        "accept": lambda **p: client.post(u + "/attempts/001/accept", params=p),
        "save-params": lambda **p: client.post(u + "/save-params", params=p, json={"set": {"anchor": "feet"}}),
    }


@pytest.mark.parametrize("name", ["prompt", "upload", "attempts", "attempt", "process", "accept", "save-params"])
def test_api_sync_direction_required_with_multiple_directions(topdown, name):
    body = err(_calls(topdown)[name](), 400, "direction_required")
    assert body["message"]


def test_api_sync_direction_invalid_values(topdown):
    assert _calls(topdown)["prompt"](direction="sideways").status_code == 422
    plan = topdown.get(char_url("hero", "/plan")).json()["plan"]
    assert plan["directions"] == ["down", "up", "right", "left"]


def test_api_sync_direction_unit_paths(topdown, root):
    r = upload_raw(topdown, direction="down")
    assert r.status_code == 200, r.text
    assert r.json()["unit"] == "walk/down" and r.json()["files"]["sheet"].startswith("/files/hero/walk/down/attempts/001/")
    assert (root / "hero/walk/down/attempts/001/raw.png").exists()
    lst = topdown.get(char_url("hero", ACT + "/attempts"), params={"direction": "down"}).json()
    assert lst["direction"] == "down" and lst["unit"] == "walk/down" and len(lst["attempts"]) == 1
    assert topdown.get(char_url("hero", ACT + "/attempts"), params={"direction": "up"}).json()["attempts"] == []
    pr = topdown.post(char_url("hero", ACT + "/prompt"), params={"direction": "up"})
    assert pr.status_code == 200, pr.text


@pytest.mark.parametrize("name", ["prompt", "upload", "process", "accept"])
def test_api_sync_direction_mirrored_left_is_409(topdown, name):
    err(_calls(topdown)[name](direction="left"), 409, "mirrored_direction")


def test_api_sync_direction_mirrored_left_read_only(topdown):
    lst = topdown.get(char_url("hero", ACT + "/attempts"), params={"direction": "left"})
    assert lst.status_code == 200 and lst.json()["attempts"] == [] and lst.json()["mirror_of"] == "walk/right"
    err(topdown.get(char_url("hero", ACT + "/attempts/001"), params={"direction": "left"}), 404, "not_found")
    assert _calls(topdown)["save-params"](direction="left").status_code == 200


def test_api_sync_direction_accept_right_derives_left(topdown, root):
    sheet = sheet_png("asymmetric_right")
    r = upload_raw(topdown, direction="right", data=sheet)
    assert r.status_code == 200, r.text
    out = topdown.post(char_url("hero", ACT + "/attempts/001/accept"), params={"direction": "right"}, json={"force": True})
    assert out.status_code == 200, out.text
    assert out.json()["derived"] == ["walk/left"] and out.json()["unit"] == "walk/right"
    assert json.loads((root / "hero/walk/left/mirror.json").read_text()) == {"source": "right", "attempt": "001"}
    assert (root / "hero/walk/left/frames/000.png").exists()
    # accepting a non-right direction derives nothing
    upload_raw(topdown, direction="down")
    down = topdown.post(char_url("hero", ACT + "/attempts/001/accept"), params={"direction": "down"}, json={"force": True})
    assert down.json()["derived"] == []
    # the derived left shows as mirrored in the plan units
    units = {u["unit"]: u for u in topdown.get(char_url("hero", "/plan")).json()["units"]}
    assert units["walk/left"]["mirrored"] is True and units["walk/right"]["mirrored"] is False


def test_api_sync_direction_unknown_action_and_character(topdown):
    err(topdown.post(char_url("hero", "/actions/nope/prompt"), params={"direction": "down"}), 404, "not_found")
    err(topdown.get(char_url("ghost", ACT + "/attempts"), params={"direction": "down"}), 404, "not_found")


def test_api_sync_direction_ignored_for_single_direction_plan(client):
    make_character(client)
    make_plan(client)
    assert client.post(char_url("hero", ACT + "/prompt"), params={"direction": "up"}).status_code == 200
    r = upload_raw(client, direction="left")
    assert r.status_code == 200 and r.json()["unit"] == "walk"
    assert client.get(char_url("hero", ACT + "/attempts"), params={"direction": "right"}).json()["unit"] == "walk"


def test_api_sync_direction_action_subset_rejected(client):
    make_character(client, view="topdown")
    make_plan(client, actions=["walk", "death"], view="topdown", set=["death.directions=down"])
    err(client.post(char_url("hero", "/actions/death/prompt"), params={"direction": "up"}), 400, "invalid_direction")
    assert client.post(char_url("hero", "/actions/death/prompt"), params={"direction": "down"}).status_code == 200
