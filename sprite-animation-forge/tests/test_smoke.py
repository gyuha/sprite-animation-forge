import subprocess
import sys
from pathlib import Path

import sprite_forge

FORGE = Path(__file__).resolve().parents[1] / "scripts" / "forge.py"


def test_package_importable():
    assert sprite_forge.__version__


def test_forge_cli_runs_without_install():
    out = subprocess.run(
        [sys.executable, str(FORGE), "--version"], capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == sprite_forge.__version__


def test_live_marker_registered(pytestconfig):
    assert any(m.startswith("live") for m in pytestconfig.getini("markers"))
