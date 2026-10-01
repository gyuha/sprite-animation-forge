import pytest
from fastapi.testclient import TestClient

from sprite_forge.errors import ForgeError
from sprite_forge_web.errors import forge_to_api
from sprite_forge_web.main import create_app


def assert_shape(body):
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "detail"}
    assert isinstance(body["error"]["detail"], dict)


def test_error_format_validation_422(client):
    r = client.post("/api/characters", json={"view": "side"})
    assert r.status_code == 422
    assert_shape(r.json())
    assert r.json()["error"]["code"] == "validation_error"
    assert r.json()["error"]["detail"]["errors"][0]["loc"][-1] == "id"


def test_error_format_validation_bad_enum(client):
    r = client.post("/api/characters", json={"id": "a", "view": "nope"})
    assert r.status_code == 422
    assert_shape(r.json())


def test_error_format_unknown_route_404(client):
    r = client.get("/api/nope")
    assert r.status_code == 404
    assert_shape(r.json())
    assert r.json()["error"]["code"] == "not_found"


def test_error_format_method_not_allowed(client):
    r = client.delete("/api/health")
    assert r.status_code == 405
    assert_shape(r.json())


def test_error_format_domain_404(client):
    r = client.get("/api/characters/ghost")
    assert_shape(r.json())
    assert r.status_code == 404


@pytest.mark.parametrize("code,exit_code,status,api_code", [
    ("no_character", 3, 404, "not_found"),
    ("exists", 1, 409, "already_exists"),
    ("busy", 1, 409, "busy"),
    ("invalid_params", 1, 400, "invalid_param"),
    ("invalid_image", 1, 400, "invalid_image"),
    ("no_reference", 3, 412, "precondition_failed"),
    ("no_plan", 3, 412, "precondition_failed"),
    ("codex_failed", 2, 502, "codex_failed"),
])
def test_error_format_forge_error_mapping(code, exit_code, status, api_code):
    e = forge_to_api(ForgeError(code, "msg", exit_code))
    assert (e.status, e.code, e.message) == (status, api_code, "msg")


def test_error_format_forge_error_handler_body(root):
    app = create_app(root=root, static_dir=None)

    @app.get("/boom")
    def boom():
        raise ForgeError("no_reference", "reference 이미지가 없습니다", 3, {"missing": "reference"})

    r = TestClient(app, base_url="http://127.0.0.1:8765").get("/boom")
    assert r.status_code == 412
    assert r.json() == {"error": {"code": "precondition_failed", "message": "reference 이미지가 없습니다",
                                  "detail": {"missing": "reference", "reason": "no_reference"}}}
