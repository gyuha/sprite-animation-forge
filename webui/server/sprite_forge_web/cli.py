"""``sprite-forge-web``: runs the server bound to 127.0.0.1 only. There is deliberately no ``--host`` option."""

from __future__ import annotations

import argparse
import os

HOST = "127.0.0.1"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sprite-forge-web", description=f"Sprite Animation Forge Web UI (binds {HOST} only)")
    p.add_argument("--port", type=int, default=int(os.environ.get("SPRITE_FORGE_PORT") or 8765))
    p.add_argument("--root", help="character root (default $SPRITE_FORGE_ROOT or ./sprites)")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    import uvicorn

    from .main import create_app

    uvicorn.run(create_app(root=args.root), host=HOST, port=args.port)
    return 0
