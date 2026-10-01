"""Live contract test for the xAI video provider (docs/13). NEVER part of the default run and it costs money:
run on purpose with ``uv run pytest -m live -k video`` after connecting credentials (``grok login`` / ``XAI_API_KEY``)."""

import os

import pytest
from PIL import Image
from sprite_forge.providers import VideoRequest, XaiVideoProvider
from sprite_forge.providers.video_base import is_mp4

pytestmark = pytest.mark.live
_REAL_ENV = {k: os.environ.get(k) for k in ("SPRITE_FORGE_GROK_AUTH", "XAI_API_KEY")}  # before conftest isolates them


@pytest.fixture(autouse=True)
def _only_when_selected(request, monkeypatch):
    expr = request.config.getoption("markexpr") or ""
    if "live" not in expr or "not live" in expr:
        pytest.skip("live tests run only with `-m live`")
    for k, v in _REAL_ENV.items():
        monkeypatch.delenv(k, raising=False)
        if v is not None:
            monkeypatch.setenv(k, v)
    if not XaiVideoProvider().check()["configured"]:
        pytest.skip("no xAI credentials (docs/13-video-api-setup.md)")


def test_live_one_video_generation_contract(tmp_path):
    first = tmp_path / "first.png"
    Image.new("RGB", (512, 512), (0, 255, 0)).save(first)
    res = XaiVideoProvider().generate(VideoRequest("a small green square gently pulsing", first, tmp_path / "v.mp4",
                                                   duration_s=2, resolution="480p"))
    assert res.status == "succeeded", (res.error_code, res.error_message)
    assert is_mp4(res.video_path.read_bytes())
