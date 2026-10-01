"""Golden property tests on real Codex samples (docs/11 §3.2). Local-only; skipped when absent."""

from pathlib import Path

import numpy as np
import pytest

from sprite_forge import qc
from sprite_forge.pipeline.process import ProcessParams, process_sheet
from sprite_forge.pipeline.split import ideal_boundaries

SAMPLES_DIR = Path(__file__).resolve().parent / "fixtures" / "codex-samples"
SAMPLES = sorted(SAMPLES_DIR.glob("*.png")) if SAMPLES_DIR.is_dir() else []


def grid_for(path: Path) -> tuple[int, int, int]:
    """idle samples are 2x2 / 4 frames, anything else (walk) 2x3 / 6 frames."""
    return (2, 2, 4) if "idle" in path.stem else (2, 3, 6)


@pytest.fixture(params=SAMPLES or [None], ids=lambda p: p.name if p else "no-samples")
def processed(request, tmp_path):
    if request.param is None:
        pytest.skip(f"no local Codex samples in {SAMPLES_DIR} (record with `pytest -m live --record-samples`)")
    rows, cols, frames = grid_for(request.param)
    params = ProcessParams(rows=rows, cols=cols, frames=frames)
    return process_sheet(request.param, tmp_path / "out", params), params


def test_golden_background_estimate_near_key(processed):
    result, _ = processed
    assert result.data["derived"]["bg_distance_to_key"] < 15


def test_golden_background_removed(processed):
    result, _ = processed
    clean = result.clean
    for corner in (clean[0, 0], clean[0, -1], clean[-1, 0], clean[-1, -1]):
        assert corner[3] == 0
    fg = clean[clean[..., 3] > 0].astype(int)
    residue = np.minimum(fg[:, 0], fg[:, 2]) - fg[:, 1]
    assert not (residue > 40).any()


def test_golden_gutters_found_and_snapped_near_ideal(processed):
    result, params = processed
    d = result.data
    assert not any(f["gutter_missing"] for f in d["derived"]["frames"])
    h, w = d["raw"]["height"], d["raw"]["width"]
    for got, ideal in zip(d["derived"]["row_boundaries"], ideal_boundaries(params.rows, h)):
        assert abs(got - ideal) <= 0.06 * h
    for bounds in d["derived"]["col_boundaries"]:
        for got, ideal in zip(bounds, ideal_boundaries(params.cols, w)):
            assert abs(got - ideal) <= 0.06 * w


def test_golden_no_empty_used_cells(processed):
    result, params = processed
    assert not any(f["empty"] for f in result.data["derived"]["frames"])
    report = qc.run_qc(result, action="walk", params=params)
    qc05 = next(r for r in report["results"] if r["id"] == "QC-05")
    assert qc05["grade"] == "pass"
