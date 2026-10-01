"""Sprite post-processing pipeline (docs/05).

Stages implemented so far: ``chroma`` (input validation, background removal),
``split`` (grid split), ``components`` (connected-component filter).
All stages are deterministic NumPy/SciPy code.
"""

from __future__ import annotations

import math


class PipelineError(Exception):
    """A pipeline failure with a stable machine-readable ``code`` (docs/05 section 2)."""

    def __init__(self, code: str, message: str = ""):
        super().__init__(f"{code}: {message}" if message else code)
        self.code = code


def round_half_up(x: float) -> int:
    """The single rounding rule of the pipeline: ``floor(x + 0.5)`` (docs/05 section 10)."""
    return math.floor(round(float(x), 4) + 0.5)
