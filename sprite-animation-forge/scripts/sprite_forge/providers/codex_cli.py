"""CodexCliProvider: image generation through ``codex exec`` (docs/03 sections 4-8, 15).

Notes / doc ambiguities:
- The instruction template is a module constant (version ``codex_instruction@1``), not a
  ``prompt_templates/`` file as docs/03 section 5 suggests.
- References are copied byte-for-byte to ``ref-NN.png``; the <=1024px / key-colour
  preprocessing of docs/03 section 10 belongs to the reference importer, not here.
- ``codex_version`` is ``null`` in generation.json (probing would cost an extra codex call).
- ``item.type == "error"`` events are never fatal (F16); they become warnings
  ``codex_error: <message>`` and a ``log`` progress event.
- A last message ``FAILED: ...`` means ``image_gen_failed`` unless the rollout confirms a
  completed image (rollout evidence wins over the free-text message).
- If no ``thread.started`` was seen, fall back to PNGs under ``generated_images/*/`` newer
  than the start time (docs/03 section 13).
- Statuses: ``succeeded`` | ``failed`` | ``timeout`` | ``canceled``; error_code equals the
  docs/03 section 8 code (``timeout``/``canceled`` repeat the status).
- Serialising calls process-wide (ADR-009) is the caller's job, not the provider's.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import threading
import time
from collections import deque
from pathlib import Path

from ..errors import ForgeError
from ..fsutil import atomic_write_json, sha256_bytes, sha256_file, utc_now
from .base import GenerationRequest, GenerationResult, ProgressFn, install_raw

INSTRUCTION_VERSION = "codex_instruction@1"
TESTED_VERSION = (0, 159, 2)
MIN_VERSION = (0, 159, 0)
KILL_GRACE_S = 5

_INSTRUCTION = """You are a non-interactive image generation worker for a sprite pipeline.

Do exactly this:
1. Call the built-in image_gen tool exactly once.
2. {refs_line}
3. Use the text between the PROMPT markers as the image_gen prompt, verbatim.
   Do not rewrite, shorten, translate, or add to it.
4. Do not run shell commands. Do not copy, move, edit, resize, or post-process any file.
5. After the tool returns, reply with the single word DONE.
   If the tool fails or refuses, reply with: FAILED: <short reason>

<<<PROMPT
{prompt}
PROMPT>>>
"""
_REFS_LINE = ("Pass the attached image(s) as referenced images. "
              "Image 1 is the strict character identity and style reference.")


def render_instruction(prompt: str, has_refs: bool) -> str:
    # str.replace-free formatting would choke on braces in the prompt, so format only the template.
    head, tail = _INSTRUCTION.split("{prompt}")
    return head.format(refs_line=_REFS_LINE if has_refs else "(No reference images are attached.)") + prompt + tail


def build_argv(codex_bin: str, out_dir: Path, refs: list[Path], reasoning_effort: str = "low") -> list[str]:
    """docs/03 section 4.1. ``-o <file>`` always sits between the last ``-i`` and the final ``-``."""
    argv = [codex_bin, "exec", "--json", "--skip-git-repo-check", "-s", "workspace-write",
            "-C", str(out_dir), "-c", f'model_reasoning_effort="{reasoning_effort}"']
    for r in refs:
        argv += ["-i", str(r)]
    return argv + ["-o", str(out_dir / "codex-last-message.txt"), "-"]


def _try_json(line: str):
    try:
        v = json.loads(line)
    except ValueError:
        return None
    return v if isinstance(v, dict) else None


def _tail(path: Path, n: int) -> str:
    try:
        with open(path, errors="replace") as f:
            return "".join(deque(f, maxlen=n)).strip()
    except OSError:
        return ""


def find_rollout_items(codex_home: Path, thread_id: str | None) -> list[dict]:
    """All ``image_gen.generation`` items of the thread's rollout (best effort, [] on any problem)."""
    if not thread_id:
        return []
    items: list[dict] = []
    for path in sorted(codex_home.glob(f"sessions/*/*/*/rollout-*-{thread_id}.jsonl")):
        try:
            with open(path, errors="replace") as f:
                for line in f:
                    ev = _try_json(line)
                    payload = ev.get("payload") if ev else None
                    item = payload.get("item") if isinstance(payload, dict) else None
                    if (isinstance(item, dict) and item.get("type") == "Extension"
                            and item.get("kind") == "image_gen.generation"):
                        items.append(item)
        except OSError:
            continue
    return items


class CodexCliProvider:
    name = "codex-cli"

    def __init__(self, codex_bin: str | None = None, codex_home: Path | str | None = None,
                 reasoning_effort: str = "low"):
        self.codex_bin = codex_bin or os.environ.get("SPRITE_FORGE_CODEX_BIN") or "codex"
        self.codex_home = Path(codex_home or os.environ.get("CODEX_HOME") or Path.home() / ".codex")
        self.reasoning_effort = reasoning_effort
        self._proc: subprocess.Popen | None = None
        self._stopped_reason: str | None = None

    # -- doctor -----------------------------------------------------------------------
    def _run(self, *args: str) -> tuple[int, str]:
        proc = subprocess.run([self.codex_bin, *args], capture_output=True, text=True, timeout=20,
                              env=self._env(), stdin=subprocess.DEVNULL)
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")

    def check(self) -> dict:
        """Install/auth/feature status (docs/03 section 11). Never raises."""
        info = {"installed": False, "version": None, "tested_version": ".".join(map(str, TESTED_VERSION)),
                "version_ok": False, "logged_in": False, "auth": None, "image_generation": False,
                "codex_home": str(self.codex_home), "ready": False}
        try:
            code, text = self._run("--version")
            m = re.search(r"(\d+)\.(\d+)\.(\d+)", text)
            if code != 0:
                return info
            info["installed"] = True
            if m:
                ver = tuple(int(x) for x in m.groups())
                info["version"] = ".".join(m.groups())
                info["version_ok"] = ver >= MIN_VERSION
            code, text = self._run("login", "status")
            if code == 0 and "Logged in" in text:
                info["logged_in"] = True
                m = re.search(r"Logged in using (.+)", text)
                info["auth"] = m.group(1).strip() if m else None
            code, text = self._run("features", "list")
            for line in text.splitlines():
                cols = line.split()
                if cols and cols[0] == "image_generation":
                    info["image_generation"] = cols[-1].lower() == "true"
        except (OSError, subprocess.SubprocessError):
            pass
        info["ready"] = bool(info["installed"] and info["version_ok"] and info["logged_in"]
                             and info["image_generation"] and self.codex_home.is_dir())
        return info

    # -- generation -------------------------------------------------------------------
    def _env(self) -> dict:
        return {**os.environ, "CODEX_HOME": str(self.codex_home)}

    def generate(self, req: GenerationRequest, on_progress: ProgressFn | None = None) -> GenerationResult:
        out = Path(req.out_dir).resolve()
        out.mkdir(parents=True, exist_ok=True)
        if len(req.reference_images) > 2:
            raise ForgeError("too_many_references", "at most 2 reference images are supported")
        emit = on_progress or (lambda stage, payload: None)

        refs, ref_meta = [], []
        for i, src in enumerate(req.reference_images, 1):
            dst = out / f"ref-{i:02d}.png"
            shutil.copy2(src, dst)
            refs.append(dst)
            ref_meta.append({"file": dst.name, "source": str(src), "sha256": sha256_file(dst)})

        argv = build_argv(self.codex_bin, out, refs, self.reasoning_effort)
        state = {"thread_id": None, "usage": None, "warnings": [], "exit_code": None,
                 "started_at": utc_now(), "t0": time.time()}
        self._stopped_reason = None

        outcome = self._run_process(argv, req, out, state, emit)
        if outcome is None:
            outcome = self._collect(out, state)
        return self._finish(req, out, argv, ref_meta, state, outcome)

    def _run_process(self, argv, req, out: Path, state: dict, emit):
        """Run codex, stream events. Returns a failure tuple or None when exit 0."""
        timer = None
        try:
            with open(out / "codex-events.jsonl", "w") as ev_log, open(out / "codex-stderr.txt", "w") as err_log:
                try:
                    proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err_log,
                                            text=True, encoding="utf-8", errors="replace", shell=False,
                                            env=self._env(), start_new_session=True)
                except (FileNotFoundError, PermissionError) as e:
                    return ("failed", "codex_not_installed", f"codex executable not found: {self.codex_bin} ({e})")
                self._proc = proc
                emit("starting", {})
                timer = threading.Timer(req.timeout_s, self._stop, args=("timeout",))
                timer.daemon = True
                timer.start()
                try:
                    proc.stdin.write(render_instruction(req.prompt, bool(req.reference_images)))
                    proc.stdin.close()
                except (BrokenPipeError, OSError):
                    pass  # process died early; exit code / stderr will explain
                started_generating = False
                for line in proc.stdout:
                    ev_log.write(line)
                    ev_log.flush()
                    ev = _try_json(line)
                    if ev:
                        started_generating = self._on_event(ev, state, emit, started_generating)
                state["exit_code"] = proc.wait()
        finally:
            if timer:
                timer.cancel()
            if self._stopped_reason:
                self._signal_group(signal.SIGKILL)  # sweep leftovers of the process group
            self._proc = None

        reason = self._stopped_reason
        if reason == "timeout":
            return ("timeout", "timeout", f"codex did not finish within {req.timeout_s}s")
        if reason == "canceled":
            return ("canceled", "canceled", "canceled by user")
        if state["exit_code"] != 0:
            return ("failed", "codex_failed",
                    f"codex exited with {state['exit_code']}\n{_tail(out / 'codex-stderr.txt', 20)}")
        return None

    @staticmethod
    def _on_event(ev: dict, state: dict, emit, started_generating: bool) -> bool:
        typ = ev.get("type", "")
        item = ev.get("item") if isinstance(ev.get("item"), dict) else {}
        if typ == "thread.started":
            state["thread_id"] = ev.get("thread_id")
            emit("session", {"thread_id": state["thread_id"]})
        elif typ.startswith("item."):
            if item.get("type") == "error":
                if typ == "item.completed":
                    msg = str(item.get("message", ""))
                    state["warnings"].append(f"codex_error: {msg}")
                    emit("log", {"level": "warning", "message": msg})
            else:
                payload = {"item_type": item.get("type")}
                if typ == "item.completed" and item.get("type") == "agent_message":
                    payload["message"] = item.get("text", "")
                if not started_generating or "message" in payload:
                    emit("generating", payload)
                started_generating = True
        elif typ == "turn.completed":
            state["usage"] = ev.get("usage")
            emit("collecting", {"usage": state["usage"]})
        return started_generating

    def _collect(self, out: Path, state: dict):
        """Two-stage result collection (docs/03 section 6.1). Returns failure tuple or success dict."""
        last_message = ""
        try:
            last_message = (out / "codex-last-message.txt").read_text(errors="replace").strip()
        except OSError:
            pass
        state["last_message"] = last_message

        items = find_rollout_items(self.codex_home, state["thread_id"])
        completed = [it for it in items if it.get("status") == "completed"]
        state["revised_prompt"] = completed[-1].get("revisedPrompt") if completed else None
        state["transparent_background"] = completed[-1].get("transparentBackground") if completed else None
        if not completed:
            failure = next((it["failure"] for it in reversed(items) if it.get("failure")), None)
            if failure is None and last_message.startswith("FAILED:"):
                failure = last_message
            if failure is not None:
                return ("failed", "image_gen_failed", str(failure))

        src, resolved_by, count = None, None, 0
        saved = [Path(it["savedPath"]) for it in completed if it.get("savedPath")]
        saved = [p for p in saved if p.is_file()]
        if saved:
            src, resolved_by, count = saved[-1], "rollout", len(saved)
        else:
            pngs = self._glob_pngs(state)
            if pngs:
                src, resolved_by, count = pngs[-1], "glob", len(pngs)
        if src is None:
            return ("failed", "no_image", "codex finished but no generated image was found")
        if count > 1:
            state["warnings"].append(f"multiple_images: {count}")
        return {"src": src, "resolved_by": resolved_by}

    def _glob_pngs(self, state: dict) -> list[Path]:
        root = self.codex_home / "generated_images"
        tid = state["thread_id"]
        if tid:
            found = list((root / tid).glob("*.png"))
        else:
            found = [p for p in root.glob("*/*.png") if p.stat().st_mtime >= state["t0"] - 1]
        return sorted(found, key=lambda p: (p.stat().st_mtime, p.name))

    def _finish(self, req, out: Path, argv, ref_meta, state, outcome) -> GenerationResult:
        status, code, message, raw, src, resolved_by = "succeeded", None, None, None, None, None
        if isinstance(outcome, tuple):
            status, code, message = outcome
        else:
            src, resolved_by = outcome["src"], outcome["resolved_by"]
            try:
                raw = install_raw(src, out / "raw.png")
            except Exception as e:
                status, code, message = "failed", "invalid_image", f"{src}: {e}"
                (out / "raw.png").unlink(missing_ok=True)
                src, resolved_by = None, None
        meta = {
            "schema_version": 1,
            "provider": self.name,
            "codex_version": None,
            "instruction_template_version": INSTRUCTION_VERSION,
            "prompt_template_version": None,
            "prompt_file": "prompt.txt" if (out / "prompt.txt").exists() else None,
            "prompt_sha256": sha256_bytes(req.prompt.encode("utf-8")),
            "references": ref_meta,
            "thread_id": state["thread_id"],
            "argv": argv,
            "started_at": state["started_at"],
            "finished_at": utc_now(),
            "duration_s": round(time.time() - state["t0"]),
            "exit_code": state["exit_code"],
            "status": status,
            "error_code": code,
            "error_message": message,
            "source_image": str(src) if src else None,
            "source_resolved_by": resolved_by,
            "revised_prompt": state.get("revised_prompt") if src else None,
            "transparent_background": state.get("transparent_background") if src else None,
            "raw": raw,
            "usage": state["usage"],
            "last_message": state.get("last_message"),
            "warnings": state["warnings"],
        }
        atomic_write_json(out / "generation.json", meta)
        return GenerationResult(status, out / "raw.png" if raw else None, code, message, meta)

    # -- stop / cancel ----------------------------------------------------------------
    def _signal_group(self, sig) -> None:
        proc = self._proc
        if proc is None:
            return
        try:
            os.killpg(proc.pid, sig)  # session leader: pgid == pid
        except (ProcessLookupError, PermissionError):
            pass

    def _stop(self, reason: str) -> None:
        proc = self._proc
        if proc is None or proc.poll() is not None:
            return
        self._stopped_reason = reason
        self._signal_group(signal.SIGTERM)
        t = threading.Timer(KILL_GRACE_S, lambda: proc.poll() is None and self._signal_group(signal.SIGKILL))
        t.daemon = True
        t.start()

    def cancel(self) -> None:
        self._stop("canceled")
