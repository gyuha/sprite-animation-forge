"""Vision review of an attempt: contact sheet -> Codex (read-only, --output-schema) -> vision-review.json."""

import json
import os
from pathlib import Path

import numpy as np
import pytest
from conftest import FORGE  # noqa: F401
from fixtures.synthetic.make import make_sheet
from PIL import Image

from sprite_forge import schemas, vision
from sprite_forge.errors import ForgeError

FAKE = Path(__file__).resolve().parent / "fixtures" / "fake_codex" / "codex"


@pytest.fixture(autouse=True)
def fake_env(tmp_path, monkeypatch):
    home = tmp_path / "codex_home"
    home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.setenv("SPRITE_FORGE_CODEX_BIN", str(FAKE))
    for k in [k for k in os.environ if k.startswith("FAKE_CODEX")]:
        monkeypatch.delenv(k)


def processed(forge, tmp_path):
    ref = tmp_path / "ref.png"
    make_sheet("clean", rows=1, cols=1).save(ref)
    forge.ok("init", "hero")
    forge.ok("reference", "import", "hero", ref)
    forge.ok("plan", "hero", "--actions", "walk")
    raw = tmp_path / "walk.png"
    make_sheet("clean", rows=2, cols=3).save(raw)
    forge.ok("import-raw", "hero", "walk", raw)
    forge.ok("process", "hero", "walk")
    return forge.root / "hero"


# ---- contact sheet ---------------------------------------------------------------------------

def test_vision_review_contact_sheet_lays_the_frames_out_in_one_row(tmp_path):
    frames = []
    for i in range(4):
        f = np.zeros((32, 32, 4), np.uint8)
        f[8:24, 4 + i * 4 : 16 + i * 4] = (200, 60, 60, 255)
        frames.append(f)
        Image.fromarray(f, "RGBA").save(tmp_path / f"{i:03d}.png")
    out = vision.contact_sheet(sorted(tmp_path.glob("*.png")), tmp_path / "contact-sheet.png")
    img = Image.open(out)
    assert img.height < img.width and img.width >= 4 * 32  # a row, frames not shrunk below their size
    assert img.mode == "RGB"  # composited on a neutral background: the reviewer sees no transparency artefacts


def test_vision_review_contact_sheet_is_limited_in_width(tmp_path):
    for i in range(12):
        Image.fromarray(np.full((256, 256, 4), 255, np.uint8), "RGBA").save(tmp_path / f"{i:03d}.png")
    img = Image.open(vision.contact_sheet(sorted(tmp_path.glob("*.png")), tmp_path / "c.png"))
    assert img.width <= vision.MAX_SHEET_WIDTH


# ---- review through the fake codex -----------------------------------------------------------

def test_vision_review_writes_a_schema_valid_vision_review_json(forge, tmp_path):
    cd = processed(forge, tmp_path)
    out = forge.ok("review", "hero", "walk")
    assert out["attempt"] == "001" and out["unit"] == "walk"
    doc = json.loads((cd / "walk/attempts/001/vision-review.json").read_text())
    schemas.validate("vision-review", doc)
    assert doc["review"]["overall"] in ("pass", "warn", "fail") and doc["frames"] == 6
    assert set(doc["review"]) >= {"loop", "limbs", "identity", "overall", "summary"}
    assert (cd / "walk/attempts/001/contact-sheet.png").exists()
    assert out["review"] == doc["review"]


def test_vision_review_records_codex_usage(forge, tmp_path):
    cd = processed(forge, tmp_path)
    forge.ok("review", "hero", "walk")
    assert json.loads((cd / "manifest.json").read_text())["usage"]["codex_calls"] == 1


def test_vision_review_invalid_reply_is_an_error_and_writes_nothing(forge, tmp_path, monkeypatch):
    cd = processed(forge, tmp_path)
    monkeypatch.setenv("FAKE_CODEX_MODE", "invalid_json")
    code, out = forge.run("review", "hero", "walk")
    assert (code, out["error_code"]) == (2, "invalid_review")
    assert not (cd / "walk/attempts/001/vision-review.json").exists()


def test_vision_review_needs_a_processed_attempt(forge, tmp_path):
    forge.ok("init", "hero")
    forge.ok("plan", "hero", "--actions", "walk")
    raw = tmp_path / "walk.png"
    make_sheet("clean", rows=2, cols=3).save(raw)
    forge.ok("import-raw", "hero", "walk", raw)
    code, out = forge.run("review", "hero", "walk")  # imported, never processed: no frames to show
    assert (code, out["error_code"]) == (3, "not_processed")


def test_vision_review_prompt_names_the_loop_and_the_frame_count():
    text = vision.instruction(frames=6, loop=True, action="walk")
    assert "6 frames" in text and "loop" in text.lower() and "do not generate images" in text.lower()
    assert "loops" not in vision.instruction(frames=4, loop=False, action="attack").lower().replace("does not loop", "")


def test_vision_review_is_a_known_job_type_and_schema_exists():
    assert schemas.load_schema("vision-review")["title"]
    assert schemas.load_schema("vision-review.llm")["required"]
