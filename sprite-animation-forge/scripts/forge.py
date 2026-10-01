#!/usr/bin/env python3
"""Single CLI entry point (docs/02 section 9). Runs without pip install by extending sys.path."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sprite_forge.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
