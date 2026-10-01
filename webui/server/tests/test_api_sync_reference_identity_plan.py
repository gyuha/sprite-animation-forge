"""Synchronous API: reference, identity, plan (docs/10 5.1-5.2)."""

import json

import pytest

from .api_sync_helpers import char_url, err, image_bytes, make_character, make_plan, png_file

GOOD_IDENTITY = {
    "silhouette": "slim", "body_ratio": "6 heads", "head_ratio": "1/6", "hair": "short brown", "face": "round",
    "eyes": "dark", "clothing": "red tunic", "primary_colors": ["#CC2222"], "secondary_colors": [],
    "weapon": "sword", "accessories": [], "outline_style": "thin", "shading_style": "flat",
    "camera_angle": "side", "orientation": "right",
}


@pytest.fixture
def hero(client):
    return make_character(client)


def test_api_sync_reference_upload_png(client, hero, root):
    r = client.post(char_url(hero, "/reference"), files=png_file(image_bytes("PNG")))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["reference"] == "reference/source.png" and body["selected_attempt"] is None
    assert body["bg_removed"] in (True, False)
    for key in ("source", "character", "keyed"):
        assert body["files"][key].startswith(f"/files/hero/reference/") and "?v=" in body["files"][key]
    assert client.get(body["files"]["character"]).status_code == 200
    assert json.loads((root / "hero/manifest.json").read_text())["reference"]["source"] == "reference/source.png"


@pytest.mark.parametrize("fmt,suffix", [("JPEG", ".jpg"), ("WEBP", ".webp")])
def test_api_sync_reference_upload_other_formats(client, hero, fmt, suffix):
    r = client.post(char_url(hero, "/reference"), files=png_file(image_bytes(fmt), "pic.bin"))
    assert r.status_code == 200, r.text
    assert r.json()["reference"] == f"reference/source{suffix}"


def test_api_sync_reference_rejects_gif(client, hero):
    body = err(client.post(char_url(hero, "/reference"), files=png_file(image_bytes("GIF"))), 400, "invalid_image")
    assert body["detail"]["reason"] == "unsupported_format"


def test_api_sync_reference_rejects_undecodable(client, hero):
    err(client.post(char_url(hero, "/reference"), files=png_file(b"not an image at all")), 400, "invalid_image")
    truncated = image_bytes("PNG", (200, 200))[:80]
    err(client.post(char_url(hero, "/reference"), files=png_file(truncated)), 400, "invalid_image")


def test_api_sync_reference_rejects_oversize(client, hero):
    big = b"\x89PNG" + b"0" * (20 * 1024 * 1024)
    err(client.post(char_url(hero, "/reference"), files=png_file(big)), 413, "file_too_large")


def test_api_sync_reference_twice_and_unknown_character(client, hero):
    assert client.post(char_url(hero, "/reference"), files=png_file(image_bytes("PNG"))).status_code == 200
    err(client.post(char_url(hero, "/reference"), files=png_file(image_bytes("PNG"))), 409, "already_exists")
    err(client.post(char_url("ghost", "/reference"), files=png_file(image_bytes("PNG"))), 404, "not_found")
    assert client.post(char_url(hero, "/reference")).status_code == 422  # no multipart file


def test_api_sync_reference_select_candidate(client, hero, root):
    err(client.post(char_url(hero, "/reference/attempts/001/select")), 404, "not_found")
    cand = root / "hero/reference/attempts/001"
    cand.mkdir(parents=True)
    (cand / "raw.png").write_bytes(image_bytes("PNG", (128, 128)))
    r = client.post(char_url(hero, "/reference/attempts/001/select"))
    assert r.status_code == 200, r.text
    assert r.json()["selected_attempt"] == "001" and r.json()["reference"] == "reference/attempts/001/raw.png"
    assert client.get(r.json()["files"]["keyed"]).status_code == 200


def test_api_sync_identity_get_put(client, hero, root):
    assert client.get(char_url(hero, "/identity")).json() == {"profile": None}
    r = client.put(char_url(hero, "/identity"), json={"identity": GOOD_IDENTITY})
    assert r.status_code == 200, r.text
    profile = r.json()["profile"]
    assert profile["edited_by_user"] is True and profile["source"] == "manual"
    assert client.get(char_url(hero, "/identity")).json()["profile"] == profile
    assert json.loads((root / "hero/character-profile.json").read_text()) == profile


def test_api_sync_identity_put_schema_violation_422(client, hero, root):
    bad = {**GOOD_IDENTITY, "primary_colors": ["red"]}
    del bad["hair"]
    body = err(client.put(char_url(hero, "/identity"), json={"identity": bad}), 422, "validation_error")
    assert len(body["detail"]["errors"]) >= 2
    assert not (root / "hero/character-profile.json").exists()
    err(client.put(char_url("ghost", "/identity"), json={"identity": GOOD_IDENTITY}), 404, "not_found")


def test_api_sync_plan_post_get(client, hero):
    created = make_plan(client, actions=None, bundle="side-basic")
    assert created["plan"]["order"] == ["idle", "walk", "run", "attack"]
    assert created["estimated_seconds"] == 360 and len(created["units"]) == 4
    assert client.get(char_url(hero, "/plan")).json() == created
    custom = make_plan(client, actions=["idle", "fall"], set=["fall.fps=9"], cell="256x256")
    assert custom["plan"]["cell"] == {"w": 256, "h": 256} and custom["plan"]["actions"]["fall"]["fps"] == 9


def test_api_sync_plan_errors(client, hero):
    err(client.get(char_url(hero, "/plan")), 412, "precondition_failed")
    err(client.post(char_url(hero, "/plan"), json={}), 400, "invalid_param")
    err(client.post(char_url(hero, "/plan"), json={"bundle": "nope"}), 400, "invalid_param")
    err(client.post(char_url(hero, "/plan"), json={"actions": ["xyzzy"]}), 400, "invalid_param")  # custom needs motion
    err(client.post(char_url("ghost", "/plan"), json={"actions": ["idle"]}), 404, "not_found")
    assert client.post(char_url(hero, "/plan"), json={"actions": ["idle"], "view": "bogus"}).status_code == 422


def test_api_sync_plan_post_directions_and_mirror(client, hero):
    plan = make_plan(client, view="topdown", directions=["down", "right", "left"], mirror=True)["plan"]
    assert plan["mirror"] == {"left": "right"} and plan["directions"] == ["down", "right", "left"]


def test_api_sync_plan_put_recomputes_grid(client, hero, root):
    plan = make_plan(client, actions=["walk", "idle"])["plan"]
    plan["actions"]["walk"]["frames"] = 8  # grid stays 2x3 -> recomputed
    plan["actions"]["idle"]["frames"] = 9
    plan["actions"]["idle"]["grid"] = "3x3"  # explicit grid changed too -> kept
    r = client.put(char_url(hero, "/plan"), json={"plan": plan})
    assert r.status_code == 200, r.text
    saved = r.json()["plan"]["actions"]
    assert saved["walk"]["grid"] == "2x4" and saved["idle"]["grid"] == "3x3"
    assert json.loads((root / "hero/animation-plan.json").read_text())["actions"]["walk"]["grid"] == "2x4"
    plan["actions"]["walk"]["frames"] = 4
    plan["actions"]["walk"]["grid"] = "1x2"  # explicit but too small
    err(client.put(char_url(hero, "/plan"), json={"plan": plan}), 400, "invalid_param")


def test_api_sync_plan_put_recomputes_key_color(client, hero):
    plan = make_plan(client)["plan"]
    assert plan["key_color"] == "#FF00FF"
    ident = {**GOOD_IDENTITY, "primary_colors": ["#FF00FF"]}
    assert client.put(char_url(hero, "/identity"), json={"identity": ident}).status_code == 200
    plan["key_color"] = "#FF00FF"
    r = client.put(char_url(hero, "/plan"), json={"plan": plan})
    assert r.json()["plan"]["key_color"] == "#00FF00"


def test_api_sync_plan_put_errors(client, hero):
    plan = make_plan(client)["plan"]
    body = err(client.put(char_url(hero, "/plan"), json={"plan": {**plan, "view": "bogus"}}), 422, "validation_error")
    assert body["detail"]["errors"]
    err(client.put(char_url(hero, "/plan"), json={"plan": {**plan, "character": "other"}}), 400, "invalid_param")
    err(client.put(char_url(hero, "/plan"), json={"plan": {**plan, "order": []}}), 400, "invalid_param")
    err(client.put(char_url(hero, "/plan"), json={"plan": {**plan, "mirror": {"left": "right"}}}), 400, "invalid_param")
    err(client.put(char_url("ghost", "/plan"), json={"plan": plan}), 404, "not_found")
