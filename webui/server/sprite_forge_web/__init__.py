"""Web UI backend. Makes the Core package ``sprite_forge`` importable (same sys.path trick as forge.py, docs/01 §6)."""

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[3] / "sprite-animation-forge" / "scripts"
if _SCRIPTS.is_dir() and str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
