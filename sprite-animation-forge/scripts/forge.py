#!/usr/bin/env python3
"""Single CLI entry point (stub). Runs without pip install by extending sys.path."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import sprite_forge  # noqa: E402


def main(argv: list[str]) -> int:
    if argv == ["--version"]:
        print(sprite_forge.__version__)
        return 0
    print("forge.py: no commands implemented yet (use --version)", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
