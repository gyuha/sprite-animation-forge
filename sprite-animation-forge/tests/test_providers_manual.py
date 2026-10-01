import json

import pytest
from PIL import Image
from sprite_forge.providers import GenerationRequest, ManualUploadProvider


def test_manual_registers_raw(tmp_path):
    src = tmp_path / "external.png"
    Image.new("RGB", (30, 20), (255, 0, 255)).save(src)
    out = tmp_path / "attempts" / "001"
    res = ManualUploadProvider(src).generate(GenerationRequest("p", [], out))
    assert res.status == "succeeded" and res.raw_path == out / "raw.png"
    assert (out / "raw.png").read_bytes() == src.read_bytes()
    g = json.loads((out / "generation.json").read_text())
    assert g["provider"] == "manual" and g["source_image"] == str(src)
    assert g["thread_id"] is None and g["argv"] is None and g["codex_version"] is None
    assert g["raw"]["width"] == 30 and g["raw"]["height"] == 20 and g["status"] == "succeeded"


def test_manual_converts_non_png(tmp_path):
    src = tmp_path / "external.jpg"
    Image.new("RGB", (16, 16), (10, 20, 30)).save(src)
    res = ManualUploadProvider(src).generate(GenerationRequest("p", [], tmp_path / "o"))
    assert res.status == "succeeded"
    with Image.open(res.raw_path) as im:
        assert im.format == "PNG"


@pytest.mark.parametrize("content", [b"not an image", None])
def test_manual_invalid_image(tmp_path, content):
    src = tmp_path / "bad.png"
    if content is not None:
        src.write_bytes(content)
    out = tmp_path / "o"
    res = ManualUploadProvider(src).generate(GenerationRequest("p", [], out))
    assert (res.status, res.error_code) == ("failed", "invalid_image")
    assert not (out / "raw.png").exists()
    assert json.loads((out / "generation.json").read_text())["error_code"] == "invalid_image"
