import pytest
from fastapi.testclient import TestClient

from sprite_forge_web.main import create_app


@pytest.fixture
def app(root):
    return create_app(root=root, static_dir=None)


@pytest.mark.parametrize("host", ["127.0.0.1", "127.0.0.1:8765", "localhost", "localhost:3000", "LOCALHOST:8765"])
def test_host_header_allowed(app, host):
    r = TestClient(app, base_url="http://127.0.0.1:8765").get("/api/presets", headers={"Host": host})
    assert r.status_code == 200


@pytest.mark.parametrize("host", ["evil.com", "evil.com:8765", "127.0.0.1.evil.com", "localhost.evil.com:80",
                                  "0.0.0.0:8765", "testserver", "127.0.0.1:abc", "[::1]:8765", ""])
def test_host_header_rejected(app, host):
    r = TestClient(app, base_url="http://127.0.0.1:8765").get("/api/presets", headers={"Host": host})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden_host"


def test_host_header_applies_to_files_and_post(app):
    c = TestClient(app, base_url="http://127.0.0.1:8765")
    assert c.get("/files/hero/manifest.json", headers={"Host": "evil.com"}).status_code == 403
    assert c.post("/api/characters", json={"id": "a"}, headers={"Host": "evil.com"}).status_code == 403


def test_host_header_guard_disabled_when_exposed(root):
    app = create_app(root=root, static_dir=None, allow_any_host=True)
    c = TestClient(app, base_url="http://127.0.0.1:8765")
    assert c.get("/api/presets", headers={"Host": "192.168.0.5:8765"}).status_code == 200
