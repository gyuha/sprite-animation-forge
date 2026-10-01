"""Server test fixtures. ``client`` = TestClient on a fresh tmp root with the FAKE codex (never the real one).

* ``root``: tmp character root.  ``make_client(**create_app_kwargs)``: build another client (own static_dir, clock...).
* ``api``-level tests use Host ``127.0.0.1:8765`` (TestClient's default ``testserver`` is rejected by the guard).
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sprite_forge_web.main import create_app

FAKE_CODEX = Path(__file__).resolve().parents[3] / "sprite-animation-forge" / "tests" / "fixtures" / "fake_codex" / "codex"
BASE = "http://127.0.0.1:8765"


@pytest.fixture(autouse=True)
def fake_codex_env(monkeypatch, tmp_path):
    monkeypatch.setenv("SPRITE_FORGE_CODEX_BIN", str(FAKE_CODEX))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex_home"))
    (tmp_path / "codex_home").mkdir()
    monkeypatch.setenv("FAKE_CODEX_DOCTOR", "ok")


@pytest.fixture
def root(tmp_path):
    return tmp_path / "sprites"


@pytest.fixture
def make_client(root):
    def make(**kw):
        kw.setdefault("root", root)
        kw.setdefault("static_dir", None)
        return TestClient(create_app(**kw), base_url=BASE)

    return make


@pytest.fixture
def client(make_client):
    return make_client()


@pytest.fixture
def jc(make_client):
    """TestClient entered as a context manager: runs the lifespan (startup recovery + the job worker)."""
    with make_client() as c:
        yield c
