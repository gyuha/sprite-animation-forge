"""ManualUploadProvider: register an externally made raw sheet as ``raw.png`` (docs/01 section 4).

Notes: GenerationRequest has no source field, so the source file is a constructor argument.
Unreadable or non-image sources fail with ``invalid_image`` (no raw.png written).
"""

from __future__ import annotations

from pathlib import Path

from ..fsutil import atomic_write_json, sha256_bytes, utc_now
from .base import GenerationRequest, GenerationResult, ProgressFn, install_raw


class ManualUploadProvider:
    name = "manual"

    def __init__(self, source: Path | str):
        self.source = Path(source)

    def check(self) -> dict:
        return {"provider": self.name, "ready": True}

    def cancel(self) -> None:
        pass

    def generate(self, req: GenerationRequest, on_progress: ProgressFn | None = None) -> GenerationResult:
        out = Path(req.out_dir)
        out.mkdir(parents=True, exist_ok=True)
        started = utc_now()
        raw, code, message = None, None, None
        try:
            raw = install_raw(self.source, out / "raw.png")
        except Exception as e:  # missing file, not an image, truncated...
            code, message = "invalid_image", f"{self.source}: {e}"
        meta = {
            "schema_version": 1,
            "provider": self.name,
            "codex_version": None,
            "instruction_template_version": None,
            "prompt_template_version": None,
            "prompt_file": "prompt.txt" if (out / "prompt.txt").exists() else None,
            "prompt_sha256": sha256_bytes(req.prompt.encode("utf-8")),
            "references": [],
            "thread_id": None,
            "argv": None,
            "started_at": started,
            "finished_at": utc_now(),
            "duration_s": 0,
            "exit_code": None,
            "status": "failed" if code else "succeeded",
            "error_code": code,
            "error_message": message,
            "source_image": str(self.source),
            "source_resolved_by": None,
            "revised_prompt": None,
            "transparent_background": None,
            "raw": raw,
            "usage": None,
            "last_message": None,
            "warnings": [],
        }
        atomic_write_json(out / "generation.json", meta)
        if code:
            return GenerationResult("failed", None, code, message, meta)
        return GenerationResult("succeeded", out / "raw.png", meta=meta)
