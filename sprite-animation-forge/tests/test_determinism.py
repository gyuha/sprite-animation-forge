"""Determinism: the same raw sheet processed twice yields byte-identical outputs (docs/11 §2, docs/05 §10)."""

import hashlib
from pathlib import Path

import pytest
from conftest import Forge
from fixtures.synthetic.make import make_sheet

from sprite_forge.pipeline.process import ProcessParams, process_sheet
from sprite_forge.pipeline.scale import ScaleProfile

VARIANTS = ("clean", "model_like_bg", "wide_attack", "asymmetric_right")
STRATEGIES = ("fit", "preserve")
PROFILE = ScaleProfile(norm_scale=0.4)
OUTPUT_GLOBS = ("clean.png", "frames/*.png", "sheet.png", "process.json", "qc-report.json")


def digests(directory: Path) -> dict[str, str]:
    files = sorted(p for pattern in OUTPUT_GLOBS for p in directory.glob(pattern))
    return {str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


@pytest.mark.parametrize("strategy", STRATEGIES)
@pytest.mark.parametrize("variant", VARIANTS)
def test_determinism_process_sheet_twice(tmp_path, variant, strategy):
    raw = tmp_path / "raw.png"
    make_sheet(variant, rows=2, cols=3, cell_size=(256, 256)).save(raw)
    params = ProcessParams(scale_strategy=strategy)
    for name in ("a", "b"):
        process_sheet(raw, tmp_path / name, params, PROFILE)
    first, second = digests(tmp_path / "a"), digests(tmp_path / "b")
    assert set(first) == {"clean.png", "sheet.png", "process.json", *(f"frames/{i:03d}.png" for i in range(6))}
    assert first == second


@pytest.mark.parametrize("variant", VARIANTS)
def test_determinism_cli_two_roots(forge, tmp_path, variant):
    raw = tmp_path / "raw.png"
    make_sheet(variant, rows=2, cols=3, cell_size=(256, 256)).save(raw)
    other = Forge(tmp_path / "sprites2")
    for f in (forge, other):
        f.ok("init", "hero")
        f.ok("plan", "hero", "--actions", "walk")
        f.ok("import-raw", "hero", "walk", raw)
        f.ok("process", "hero", "walk")
    a = digests(forge.root / "hero/walk/attempts/001")
    b = digests(other.root / "hero/walk/attempts/001")
    assert "qc-report.json" in a and a == b


def test_determinism_cli_two_attempts(forge, raw_sheet):
    forge.ok("init", "hero")
    forge.ok("plan", "hero", "--actions", "walk")
    forge.ok("import-raw", "hero", "walk", raw_sheet)
    forge.ok("import-raw", "hero", "walk", raw_sheet)
    forge.ok("process", "hero", "walk", "--attempt", "001")
    forge.ok("process", "hero", "walk", "--attempt", "002")
    attempts = forge.root / "hero/walk/attempts"
    first = digests(attempts / "001")
    assert "qc-report.json" in first
    # qc-report.json carries the attempt id, so compare it without that field
    second = digests(attempts / "002")
    assert {k: v for k, v in first.items() if k != "qc-report.json"} == {
        k: v for k, v in second.items() if k != "qc-report.json"}
