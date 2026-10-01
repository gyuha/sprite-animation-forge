import pytest


@pytest.fixture
def dist(tmp_path):
    d = tmp_path / "dist"
    (d / "assets").mkdir(parents=True)
    (d / "index.html").write_text("<html>SPA</html>")
    (d / "assets" / "app.js").write_text("console.log(1)")
    return d


def test_static_dist_index_and_asset(make_client, dist):
    c = make_client(static_dir=dist)
    assert "SPA" in c.get("/").text
    assert c.get("/assets/app.js").text == "console.log(1)"


def test_static_dist_spa_fallback(make_client, dist):
    c = make_client(static_dir=dist)
    r = c.get("/characters/hero/actions/walk")
    assert r.status_code == 200 and "SPA" in r.text


def test_static_dist_api_and_files_not_swallowed(make_client, dist):
    c = make_client(static_dir=dist)
    r = c.get("/api/nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
    assert c.get("/files/hero/manifest.json").status_code == 404
    assert c.get("/api/presets").status_code == 200


def test_static_dist_no_escape(make_client, dist, tmp_path):
    (tmp_path / "secret.txt").write_text("secret")
    c = make_client(static_dir=dist)
    for p in ("/../secret.txt", "/%2e%2e/secret.txt", "/assets/..%2f..%2fsecret.txt"):
        assert "secret" not in c.get(p).text


def test_static_dist_missing_dir_is_api_only(make_client, tmp_path):
    c = make_client(static_dir=tmp_path / "nodist")
    assert c.get("/").status_code == 404
    assert c.get("/api/presets").status_code == 200
