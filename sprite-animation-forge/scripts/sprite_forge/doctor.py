"""``doctor``: pre-flight report (docs/03 11). Never raises; a missing codex is a report, not an error.

``run_doctor(provider=None) -> {codex, python, warnings, ready}``
``codex`` is ``CodexCliProvider.check()`` minus its ``ready`` key (that moves to the top level, which also
requires the Python dependencies). ``python`` maps pillow / numpy / scipy to a version string or ``null``.

Notes on ambiguous spots
------------------------
* ``warnings`` is a list of ``"<code>: <message>"`` strings; docs/03 11 only says "warnings".
* The 60 s result cache of docs/03 11 belongs to the Web server; the one-shot CLI does not cache.
"""

from __future__ import annotations

import importlib
import os

from .providers import CodexCliProvider
from .providers.codex_cli import TESTED_VERSION

DEPS = (("pillow", "PIL"), ("numpy", "numpy"), ("scipy", "scipy"))


def _version(module: str) -> str | None:
    try:
        return str(importlib.import_module(module).__version__)
    except Exception:  # missing or broken install
        return None


def run_doctor(provider=None) -> dict:
    provider = provider or CodexCliProvider()
    codex = provider.check()
    codex_ready = codex.pop("ready")
    python = {name: _version(module) for name, module in DEPS}

    warnings = []
    if not codex["installed"]:
        warnings.append(f"codex_not_installed: {provider.codex_bin!r} not runnable; npm install -g @openai/codex")
    else:
        if not codex["version_ok"]:
            warnings.append(f"codex_version_too_old: {codex['version']} (need >= 0.159.0)")
        elif codex["version"] and tuple(int(x) for x in codex["version"].split(".")[:2]) != TESTED_VERSION[:2]:
            warnings.append(f"codex_version_untested: {codex['version']} (tested {codex['tested_version']})")
        if not codex["logged_in"]:
            warnings.append("codex_not_logged_in: run `codex login`")
        if not codex["image_generation"]:
            warnings.append("image_generation_disabled: enable the image_generation feature in Codex")
    home = provider.codex_home
    if not home.is_dir():
        warnings.append(f"codex_home_missing: {home}")
    elif not os.access(home, os.W_OK):
        warnings.append(f"codex_home_not_writable: {home}")
    warnings += [f"python_dependency_missing: {name}" for name, v in python.items() if v is None]

    return {"codex": codex, "python": python, "warnings": warnings,
            "ready": bool(codex_ready and all(python.values()))}
