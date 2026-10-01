"""Writes a deterministic single-character reference PNG (the synthetic generator of the Python tests).

Usage: uv run python webui/web/e2e/make_reference.py <out.png>
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "sprite-animation-forge" / "tests" / "fixtures" / "synthetic"))

from make import make_sheet  # noqa: E402

Path(sys.argv[1]).write_bytes(make_sheet("clean", rows=1, cols=1).png_bytes())
