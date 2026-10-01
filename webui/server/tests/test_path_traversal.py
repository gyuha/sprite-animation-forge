import os

import pytest


@pytest.fixture
def char(root):
    cd = root / "hero"
    (cd / "walk" / "attempts").mkdir(parents=True)
    (cd / "manifest.json").write_text('{"character": "hero"}')
    (cd / "walk" / "sheet.png").write_bytes(b"\x89PNG-fake")
    (cd / "notes.exe").write_text("x")
    (root / "secret.json").write_text('{"secret": true}')
    (root / "other").mkdir()
    (root / "other" / "manifest.json").write_text("{}")
    return cd


def test_path_traversal_normal_file_ok(client, char):
    r = client.get("/files/hero/manifest.json")
    assert r.status_code == 200 and r.json() == {"character": "hero"}
    r = client.get("/files/hero/walk/sheet.png")
    assert r.status_code == 200 and r.content == b"\x89PNG-fake"


def test_path_traversal_cache_headers(client, char):
    assert client.get("/files/hero/manifest.json").headers["cache-control"] == "no-cache"
    r = client.get("/files/hero/manifest.json?v=abc")
    assert r.headers["cache-control"] == "public, max-age=31536000, immutable"


@pytest.mark.parametrize("path", [
    "/files/hero/%2e%2e/secret.json",
    "/files/hero/%2E%2E/%2e%2e/secret.json",
    "/files/hero/..%2fsecret.json",
    "/files/hero/%2e%2e%2fsecret.json",
    "/files/hero/..%5csecret.json",
    "/files/hero//etc/passwd",
    "/files/hero/%2fetc/passwd",
    "/files/hero/manifest.json%00.png",
    "/files/..%2f/secret.json",
    "/files/%2e%2e/secret.json",
])
def test_path_traversal_rejected(client, char, path):
    r = client.get(path)
    assert r.status_code in (400, 404), (path, r.status_code)
    assert "secret" not in r.text


def test_path_traversal_literal_dotdot_unnormalized(client, char):
    # httpx collapses literal ".." in client-side URLs; force the raw path onto the wire
    req = client.build_request("GET", "/files/hero/x")
    req.url = req.url.copy_with(raw_path=b"/files/hero/../secret.json")
    r = client.send(req)
    assert r.status_code in (400, 404)
    assert "secret" not in r.text


def test_path_traversal_symlink_file_outside(client, char, root, tmp_path):
    outside = tmp_path / "outside.json"
    outside.write_text('{"x": 1}')
    os.symlink(outside, char / "link.json")
    assert client.get("/files/hero/link.json").status_code == 404


def test_path_traversal_symlink_dir_outside(client, char, root, tmp_path):
    outdir = tmp_path / "outdir"
    outdir.mkdir()
    (outdir / "a.json").write_text("{}")
    os.symlink(outdir, char / "linkdir")
    assert client.get("/files/hero/linkdir/a.json").status_code == 404


def test_path_traversal_symlink_inside_ok(client, char):
    os.symlink(char / "manifest.json", char / "alias.json")
    assert client.get("/files/hero/alias.json").status_code == 200


def test_path_traversal_symlinked_cid_dir_blocked(client, root, tmp_path):
    outdir = tmp_path / "elsewhere"
    outdir.mkdir()
    (outdir / "manifest.json").write_text("{}")
    root.mkdir(exist_ok=True)
    os.symlink(outdir, root / "evil")
    assert client.get("/files/evil/manifest.json").status_code == 404


def test_path_traversal_extension_and_missing(client, char):
    assert client.get("/files/hero/notes.exe").status_code == 404
    assert client.get("/files/hero/nope.png").status_code == 404
    assert client.get("/files/hero/walk").status_code == 404
    assert client.get("/files/ghost/manifest.json").status_code == 404


def test_path_traversal_invalid_cid(client, char):
    assert client.get("/files/Hero/manifest.json").status_code == 404
    assert client.get("/files/.../manifest.json").status_code == 404
    body = client.get("/files/Hero/manifest.json").json()
    assert body["error"]["code"] == "not_found"
