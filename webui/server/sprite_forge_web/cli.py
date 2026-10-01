"""``sprite-forge-web``: binds 127.0.0.1 by default. ``--host 0.0.0.0`` (or another address) is an explicit
opt-in: the server has no authentication, so anyone who can reach the port can use your Codex session."""

from __future__ import annotations

import argparse
import os
import sys

HOST = "127.0.0.1"
LOOPBACK = {"127.0.0.1", "localhost"}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sprite-forge-web", description="Sprite Animation Forge Web UI")
    p.add_argument("--host", default=os.environ.get("SPRITE_FORGE_HOST") or HOST,
                   help=f"bind address (default {HOST}; 0.0.0.0 exposes the server to the network, no auth)")
    p.add_argument("--port", type=int, default=int(os.environ.get("SPRITE_FORGE_PORT") or 8765))
    p.add_argument("--root", help="character root (default $SPRITE_FORGE_ROOT or ./sprites)")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    import uvicorn

    from .main import create_app

    exposed = args.host not in LOOPBACK
    if exposed:
        print(f"WARNING: binding {args.host}:{args.port} - no authentication, the Host header check is disabled; "
              "anyone who can reach this port can generate with your Codex login.", file=sys.stderr)
    # open SSE streams would otherwise keep a Ctrl-C shutdown waiting forever
    uvicorn.run(create_app(root=args.root, allow_any_host=exposed), host=args.host, port=args.port,
                timeout_graceful_shutdown=3)
    return 0
