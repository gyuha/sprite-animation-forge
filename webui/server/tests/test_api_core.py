import pytest

from sprite_forge_web.main import app, create_app


def test_api_core_module_app_openapi():
    paths = app.openapi()["paths"]
    for p in ("/api/health", "/api/presets", "/api/characters", "/api/characters/{cid}"):
        assert p in paths


def test_api_core_health_ready(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ready"] is True and body["codex"]["installed"] is True


def test_api_core_health_cache_and_refresh(make_client, monkeypatch):
    now = [100.0]
    client = make_client(clock=lambda: now[0])
    assert client.get("/api/health").json()["ready"] is True
    monkeypatch.setenv("FAKE_CODEX_DOCTOR", "logged_out")
    assert client.get("/api/health").json()["codex"]["logged_in"] is True  # cached
    assert client.get("/api/health?refresh=1").json()["codex"]["logged_in"] is False
    monkeypatch.setenv("FAKE_CODEX_DOCTOR", "ok")
    now[0] += 59
    assert client.get("/api/health").json()["codex"]["logged_in"] is False  # still cached
    now[0] += 2
    assert client.get("/api/health").json()["codex"]["logged_in"] is True  # expired


def test_api_core_presets(client):
    body = client.get("/api/presets").json()
    assert body["frame_presets"]["walk"] == {
        "frames": 6, "loop": True, "fps": 10, "anchor": "feet", "scale_strategy": "fit",
        "x_anchor": "mass", "components": "largest", "grid": "2x3",
    }
    assert body["bundles"]["topdown-rpg"] == {"actions": ["idle", "walk", "attack", "hurt", "death"], "view": "topdown"}
    assert "side" in body["views"] and "down" in body["directions"]


def test_api_core_characters_empty(client):
    assert client.get("/api/characters").json() == {"characters": []}


def test_api_core_character_create_list_get(client, root):
    r = client.post("/api/characters", json={"id": "hero", "view": "side", "asset_type": "player"})
    assert r.status_code == 201
    ch = r.json()["character"]
    assert ch["id"] == "hero" and ch["next_step"] == "reference" and ch["created_at"]
    assert (root / "hero" / "manifest.json").is_file()

    cards = client.get("/api/characters").json()["characters"]
    assert [c["id"] for c in cards] == ["hero"]
    assert cards[0]["has_reference"] is False and cards[0]["next_step"] == "reference"

    d = client.get("/api/characters/hero").json()
    assert d["manifest"]["character"] == "hero" and d["manifest"]["settings"]["asset_type"] == "player"
    assert d["status"]["has_plan"] is False and d["status"]["units"] == []


def test_api_core_character_detail_with_plan_status(client, root):
    from sprite_forge.plan import build_plan, save_plan

    client.post("/api/characters", json={"id": "hero"})
    cd = root / "hero"
    save_plan(cd, build_plan("hero", ["idle", "walk"], view="side", asset_type="character", art_style="auto",
                             has_reference=False))
    d = client.get("/api/characters/hero").json()
    assert [u["action"] for u in d["status"]["units"]] == ["idle", "walk"]
    assert all(u["state"] == "pending" for u in d["status"]["units"])


def test_api_core_character_create_duplicate_409(client):
    client.post("/api/characters", json={"id": "hero"})
    r = client.post("/api/characters", json={"id": "hero"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "already_exists"


@pytest.mark.parametrize("bad", ["Hero", "../x", "-a", "a" * 41, "has space", ""])
def test_api_core_character_create_invalid_id(client, bad):
    r = client.post("/api/characters", json={"id": bad})
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_character_id"


def test_api_core_character_get_missing_404(client):
    r = client.get("/api/characters/nobody")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


def test_api_core_list_ignores_stray_dirs(client, root):
    client.post("/api/characters", json={"id": "hero"})
    (root / "junk").mkdir()
    (root / "Bad_Name").mkdir()
    assert [c["id"] for c in client.get("/api/characters").json()["characters"]] == ["hero"]


def test_api_core_factory_default_root_env(monkeypatch, tmp_path):
    monkeypatch.setenv("SPRITE_FORGE_ROOT", str(tmp_path / "envroot"))
    assert create_app().state.root == tmp_path / "envroot"


def test_api_core_cli_has_no_host_option(capsys):
    from sprite_forge_web.cli import build_parser

    with pytest.raises(SystemExit) as e:
        build_parser().parse_args(["--host", "0.0.0.0"])
    assert e.value.code == 2
    assert build_parser().parse_args([]).port == 8765
