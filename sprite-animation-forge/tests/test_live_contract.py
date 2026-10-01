"""Live contract tests against the REAL Codex CLI (docs/03 section 13, docs/12 M2). Slow, consume plan usage.

Never part of the default run (``addopts = -m 'not live'``). Run on purpose with ``uv run pytest -m live``;
each test additionally skips unless ``live`` was explicitly selected, so a stray ``-m ""`` cannot spend usage.
"""

import json
import shutil
import subprocess
import sys

import pytest
from conftest import FORGE
from PIL import Image

from sprite_forge.providers import CodexCliProvider, GenerationRequest

pytestmark = pytest.mark.live


@pytest.fixture(autouse=True)
def _only_when_selected(request, monkeypatch):
    expr = request.config.getoption("markexpr") or ""
    if "live" not in expr or "not live" in expr:
        pytest.skip("live tests run only with `-m live`")
    if shutil.which("codex") is None:
        pytest.skip("codex is not installed")
    monkeypatch.delenv("SPRITE_FORGE_CODEX_BIN", raising=False)  # the real binary, real CODEX_HOME


def test_live_doctor_reports_ready_codex(tmp_path):
    proc = subprocess.run([sys.executable, str(FORGE), "--root", str(tmp_path), "doctor"],
                          capture_output=True, text=True, timeout=120)
    out = json.loads(proc.stdout)
    assert proc.returncode == 0
    assert out["codex"]["installed"] and out["codex"]["version_ok"]
    assert out["codex"]["logged_in"] and out["codex"]["image_generation"]
    assert out["ready"] is True, out["warnings"]


def test_live_one_generation_contract(tmp_path):
    """Thread id from JSONL, rollout item, generated_images/<thread_id>/, decodable raw.png (docs/03 section 13)."""
    prompt = ("Create a single full-body 2D game character, a small red-hooded knight, neutral pose, centered. "
              "Fill the entire background with flat, solid magenta #FF00FF. No text. No watermark.")
    res = CodexCliProvider().generate(GenerationRequest(prompt, [], tmp_path / "attempt", timeout_s=300))
    assert res.status == "succeeded", (res.error_code, res.error_message)
    meta = res.meta
    assert meta["thread_id"] and meta["exit_code"] == 0
    assert meta["source_resolved_by"] in ("rollout", "glob")
    assert meta["revised_prompt"] is not None, "rollout image_gen.generation item not found (internal format changed?)"
    with Image.open(res.raw_path) as im:
        im.verify()
    assert (tmp_path / "attempt" / "codex-events.jsonl").stat().st_size > 0
