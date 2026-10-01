"""Command-line interface (docs/02 section 9). ``scripts/forge.py`` just calls ``main``.

Contract: stdout carries exactly one JSON object; human logs go to stderr; exit codes 0 / 1
(argument or input error) / 2 (provider error) / 3 (missing precondition). QC failure is exit 0.
Errors print ``{"error_code": ..., "message": ...}``.

Adding a command: write ``@command("name", args=setup_fn)`` on a ``handler(args) -> dict`` below
(nested names like ``("reference", "import")`` are supported).

Notes on ambiguous spots
------------------------
* ``--root`` and ``--quiet`` are accepted before or after the sub-command; the root defaults to
  ``$SPRITE_FORGE_ROOT`` then ``./sprites`` (docs/08 section 2).
* ``plan`` prints the whole plan object under ``plan`` (not just its path).
* ``--direction left`` on a mirrored left exits 1 with ``error_code: mirrored_direction``.
* ``prompt`` returns ``{prompt, references_needed, warnings}`` and needs no profile; ``generate`` needs plan,
  reference and profile (exit 3 otherwise) and exits 2 with ``{error_code, message, attempt, unit, status}`` on a
  provider failure. ``--recovery`` is repeatable. ``doctor`` always exits 0.
* ``--help`` prints argparse help to stdout and exits 0; it is not a JSON command.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import traceback
from pathlib import Path

from . import __version__, generation, identity, vision, workflow
from . import manifest as mf
from .doctor import run_doctor
from .export import export_character
from .errors import EXIT_INVALID, ForgeError
from .plan import (
    BUNDLE_VIEW,
    build_plan,
    estimated_seconds,
    load_plan,
    parse_overrides,
    resolve_actions,
    save_plan,
)
from .prompt import build_prompt

CID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
ACTION_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
VIEWS = ("side", "topdown", "3/4", "front", "rear")
ASSET_TYPES = ("player", "npc", "character", "creature", "enemy")
ART_STYLES = ("auto", "pixel_art", "retro_pixel", "pixel_inspired", "clean_hd", "project_native")
DIRECTIONS = ("right", "left", "up", "down")

COMMANDS: dict[tuple, tuple] = {}
_quiet = False


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ForgeError("usage", message)


def command(*path, args=None):
    def register(handler):
        COMMANDS[path] = (handler, args)
        return handler

    return register


def log(msg: str) -> None:
    if not _quiet:
        print(msg, file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="forge.py")
    parser.add_argument("--root", help="output root (default $SPRITE_FORGE_ROOT or ./sprites)")
    parser.add_argument("--quiet", action="store_true", help="no human logs on stderr")
    parser.add_argument("--version", action="store_true", help="print the version and exit")
    sub = parser.add_subparsers(dest="command")
    shared = _Parser(add_help=False)
    shared.add_argument("--root", default=argparse.SUPPRESS)
    shared.add_argument("--quiet", action="store_true", default=argparse.SUPPRESS)
    groups: dict[str, argparse._SubParsersAction] = {}
    for path, (handler, setup) in COMMANDS.items():
        if len(path) == 1:
            p = sub.add_parser(path[0], parents=[shared], help=(handler.__doc__ or "").strip())
        else:
            if path[0] not in groups:
                g = sub.add_parser(path[0], parents=[shared])
                groups[path[0]] = g.add_subparsers(dest="subcommand")
            p = groups[path[0]].add_parser(path[1], parents=[shared], help=(handler.__doc__ or "").strip())
        if setup:
            setup(p)
        p.set_defaults(_handler=handler)
    return parser


# ---- helpers ------------------------------------------------------------------------------

def _root(args) -> Path:
    return Path(args.root or os.environ.get("SPRITE_FORGE_ROOT") or "./sprites")


def _cid(args) -> Path:
    if not CID_RE.match(args.cid):
        raise ForgeError("invalid_character_id", f"{args.cid!r} must match {CID_RE.pattern}")
    return _root(args) / args.cid


def _action(args) -> str:
    if not ACTION_RE.match(args.action):
        raise ForgeError("invalid_action", f"{args.action!r} must match {ACTION_RE.pattern}")
    return args.action


def _unit_args(p, with_attempt=False):
    p.add_argument("cid")
    p.add_argument("action")
    p.add_argument("--direction", choices=DIRECTIONS, help="required when the plan has 2+ directions")
    if with_attempt:
        p.add_argument("--attempt", help="attempt number NNN (default: latest)")


# ---- commands -----------------------------------------------------------------------------

def _init_args(p):
    p.add_argument("cid")
    p.add_argument("--view", choices=VIEWS, default="side")
    p.add_argument("--art-style", choices=ART_STYLES, default="auto")
    p.add_argument("--asset-type", choices=ASSET_TYPES, default="character")


@command("init", args=_init_args)
def cmd_init(args):
    """Create sprites/<cid>/manifest.json"""
    cd = _cid(args)
    mf.create(cd, args.cid, {"view": args.view, "art_style": args.art_style, "asset_type": args.asset_type})
    log(f"created {cd}")
    return {"character": args.cid, "dir": str(cd)}


def _ref_import_args(p):
    p.add_argument("cid")
    p.add_argument("file")


@command("reference", "import", args=_ref_import_args)
def cmd_reference_import(args):
    """Import a reference image (source, character.png, character-keyed.png)"""
    return workflow.import_reference(_cid(args), args.file)


def _plan_args(p):
    p.add_argument("cid")
    p.add_argument("--actions", help="comma separated action names")
    p.add_argument("--bundle", help="side-action | side-basic | topdown-rpg | npc")
    p.add_argument("--set", dest="sets", action="append", default=[], metavar="ACTION.KEY=VALUE")
    p.add_argument("--cell", default="128x128", help="WxH output cell")
    p.add_argument("--view", choices=VIEWS, help="override the view given at init")
    p.add_argument("--facing", help="representative facing (right|left|up|down|down-right|camera|away)")
    p.add_argument("--directions", help="comma separated, e.g. down,up,right,left")
    p.add_argument("--mirror", dest="mirror", action="store_const", const=True, default=None)
    p.add_argument("--no-mirror", dest="mirror", action="store_const", const=False)


@command("plan", args=_plan_args)
def cmd_plan(args):
    """Create animation-plan.json"""
    cd = _cid(args)
    m = mf.load(cd)
    settings = m.get("settings", {})
    names = resolve_actions(args.actions, args.bundle)
    for n in names:
        if not ACTION_RE.match(n):
            raise ForgeError("invalid_action", f"{n!r} must match {ACTION_RE.pattern}")
    view = args.view or settings.get("view", "side")
    notes = []
    if args.bundle in BUNDLE_VIEW and view != BUNDLE_VIEW[args.bundle]:
        notes.append(f"bundle {args.bundle} implies view={BUNDLE_VIEW[args.bundle]} (was {view})")
        view = BUNDLE_VIEW[args.bundle]
    profile_file = cd / "character-profile.json"
    profile = json.loads(profile_file.read_text(encoding="utf-8")) if profile_file.exists() else None
    dirs = [d.strip() for d in args.directions.split(",") if d.strip()] if args.directions else None
    plan = build_plan(
        args.cid, names, view=view, asset_type=settings.get("asset_type", "character"),
        art_style=settings.get("art_style", "auto"), has_reference=m["reference"] is not None,
        facing=args.facing, directions=dirs, mirror=args.mirror, cell=args.cell,
        overrides=parse_overrides(args.sets), profile=profile, assumptions=notes,
    )
    save_plan(cd, plan)
    mf.update(cd, lambda data: data.__setitem__("assumptions", plan["assumptions"]))
    return {"plan": plan, "estimated_seconds": estimated_seconds(plan)}


def _prompt_args(p):
    _unit_args(p)
    p.add_argument("--extra", help="free text for ADDITIONAL DIRECTION (max 500 chars)")
    p.add_argument("--recovery", action="append", default=[], metavar="CODE", help="recovery code (repeatable)")


@command("prompt", args=_prompt_args)
def cmd_prompt(args):
    """Print the action prompt (not saved)"""
    cd = _cid(args)
    mf.load(cd)
    pr = build_prompt(load_plan(cd), identity.load_profile(cd), _action(args), args.direction, args.extra, args.recovery)
    return {"prompt": pr.text, "references_needed": pr.references_needed, "warnings": pr.warnings}


def _generate_args(p):
    _prompt_args(p)
    p.add_argument("--timeout", type=int, default=300, help="seconds for the Codex call")


@command("generate", args=_generate_args)
def cmd_generate(args):
    """Generate a raw sheet with Codex as a new attempt"""
    cd = _cid(args)
    mf.load(cd)
    return generation.generate_unit(cd, load_plan(cd), identity.load_profile(cd), _action(args), args.direction,
                                    args.extra, args.recovery, args.timeout)  # method=video: video provider from env



def _review_args(p):
    _unit_args(p, with_attempt=True)
    p.add_argument("--timeout", type=int, default=300, help="seconds for the Codex call")


@command("review", args=_review_args)
def cmd_review(args):
    """Ask Codex to review a processed attempt's motion (advisory vision review)"""
    cd = _cid(args)
    mf.load(cd)
    return vision.review_attempt(cd, load_plan(cd), _action(args), args.direction, args.attempt, args.timeout)


def _import_raw_args(p):
    _unit_args(p)
    p.add_argument("file")


@command("import-raw", args=_import_raw_args)
def cmd_import_raw(args):
    """Register an external raw sheet as a new attempt"""
    cd = _cid(args)
    mf.load(cd)
    return workflow.import_raw(cd, load_plan(cd), _action(args), args.direction, args.file)


def _process_args(p):
    _unit_args(p, with_attempt=True)
    p.add_argument("--set", dest="sets", action="append", default=[], metavar="KEY=VALUE")


@command("process", args=_process_args)
def cmd_process(args):
    """Process an attempt (chroma, split, align) and run QC"""
    cd = _cid(args)
    mf.load(cd)
    return workflow.process_attempt(cd, load_plan(cd), _action(args), args.direction, args.attempt, args.sets)


@command("accept", args=lambda p: _unit_args(p, with_attempt=True))
def cmd_accept(args):
    """Accept an attempt: copy it to the unit directory (derives left from right when mirrored)"""
    cd = _cid(args)
    mf.load(cd)
    return workflow.accept_attempt(cd, load_plan(cd), _action(args), args.direction, args.attempt)


@command("status", args=lambda p: p.add_argument("cid"))
def cmd_status(args):
    """Per-unit state, accepted attempt and QC summary"""
    return workflow.status_report(_cid(args))


@command("doctor")
def cmd_doctor(args):
    """Check codex install / login / image feature and Python dependencies (always exit 0)"""
    return run_doctor()


def _export_args(p):
    p.add_argument("cid")
    p.add_argument("--engine", choices=("phaser",), default="phaser")


@command("export", args=_export_args)
def cmd_export(args):
    """Build atlas/, animations.json, preview/*.gif and the character qc-report.json from accepted units"""
    cd = _cid(args)
    mf.load(cd)
    return export_character(cd, args.engine)


def _ref_generate_args(p):
    p.add_argument("cid")
    p.add_argument("--description", required=True, help="character description")
    p.add_argument("--count", type=int, default=1, choices=range(1, 5), metavar="1..4")
    p.add_argument("--timeout", type=int, default=300, help="seconds per Codex call")


@command("reference", "generate", args=_ref_generate_args)
def cmd_reference_generate(args):
    """Generate canonical reference candidates from a description (Case B)"""
    return generation.generate_reference(_cid(args), args.description, args.count, args.timeout)


def _ref_select_args(p):
    p.add_argument("cid")
    p.add_argument("attempt", help="reference attempt number NNN")


@command("reference", "select", args=_ref_select_args)
def cmd_reference_select(args):
    """Make a generated reference attempt the canonical reference"""
    return generation.select_reference(_cid(args), args.attempt)


def _identity_args(p):
    p.add_argument("cid")
    p.add_argument("--timeout", type=int, default=300, help="seconds for the Codex call")
    p.add_argument("--force", action="store_true", help="overwrite a profile edited by the user")
    p.add_argument("--empty", action="store_true", help="write an all-unknown profile without calling Codex")


@command("identity", "analyze", args=_identity_args)
def cmd_identity_analyze(args):
    """Analyze the reference with Codex and write character-profile.json"""
    cd = _cid(args)
    if args.empty:
        return identity.write_empty(cd, args.force)
    return identity.analyze(cd, args.timeout, args.force)


# ---- entry point --------------------------------------------------------------------------

def _emit(obj) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main(argv: list[str]) -> int:
    global _quiet
    try:
        args = build_parser().parse_args(argv)
        _quiet = bool(args.quiet)
        if args.version:
            print(__version__)
            return 0
        handler = getattr(args, "_handler", None)
        if handler is None:
            raise ForgeError("usage", "no command given; commands: " + ", ".join(" ".join(p) for p in COMMANDS))
        _emit(handler(args))
        return 0
    except ForgeError as exc:
        _emit({"error_code": exc.code, "message": exc.message, **exc.extra})
        return exc.exit_code
    except Exception as exc:  # unexpected: still one JSON object on stdout
        traceback.print_exc()
        _emit({"error_code": "internal_error", "message": f"{type(exc).__name__}: {exc}"})
        return EXIT_INVALID
