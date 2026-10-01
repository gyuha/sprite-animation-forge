"""Command-level error with a stable machine-readable code and a CLI exit code (docs/02 9.1)."""

from __future__ import annotations

EXIT_INVALID = 1  # argument / input validation
EXIT_PROVIDER = 2  # image provider error (later tasks)
EXIT_PRECONDITION = 3  # missing reference / plan / accepted attempt


class ForgeError(Exception):
    def __init__(self, code: str, message: str = "", exit_code: int = EXIT_INVALID):
        super().__init__(f"{code}: {message}" if message else code)
        self.code = code
        self.message = message
        self.exit_code = exit_code
