import json
import subprocess
import sys
from pathlib import Path

import pytest
from fixtures.synthetic.make import make_sheet

FORGE = Path(__file__).resolve().parents[1] / "scripts" / "forge.py"
SCRIPTS = FORGE.parent


class Forge:
    """Runs scripts/forge.py in a subprocess against a tmp --root."""

    def __init__(self, root: Path):
        self.root = root

    def run(self, *args, expect=None):
        proc = subprocess.run(
            [sys.executable, str(FORGE), "--root", str(self.root), "--quiet", *map(str, args)],
            capture_output=True, text=True,
        )
        lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
        assert len(lines) == 1, f"stdout must be one JSON object: {proc.stdout!r} / {proc.stderr}"
        out = json.loads(lines[0])
        assert isinstance(out, dict)
        if expect is not None:
            assert proc.returncode == expect, (proc.returncode, out, proc.stderr)
        return proc.returncode, out

    def ok(self, *args):
        return self.run(*args, expect=0)[1]


@pytest.fixture
def forge(tmp_path):
    return Forge(tmp_path / "sprites")


@pytest.fixture
def raw_sheet(tmp_path):
    path = tmp_path / "raw_asym.png"
    make_sheet("asymmetric_right", rows=2, cols=3, cell_size=(256, 256)).save(path)
    return path
