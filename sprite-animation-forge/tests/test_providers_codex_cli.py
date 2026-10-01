import json
import os
import subprocess
import threading
import time
from pathlib import Path

import pytest
from PIL import Image
from sprite_forge.providers import CodexCliProvider, GenerationRequest
from sprite_forge.providers.codex_cli import build_argv, render_instruction

FAKE = Path(__file__).resolve().parent / "fixtures" / "fake_codex" / "codex"
PROMPT = "draw a knight, 2x2 grid {not a format field}"


@pytest.fixture(autouse=True)
def _never_real_codex(monkeypatch, tmp_path):
    """Safety net: every process spawned here must be the fake (or an explicitly missing path)."""
    real_popen = subprocess.Popen
    allowed = {str(FAKE), str(tmp_path / "no-such-codex")}

    def guarded(argv, *a, **kw):
        assert argv[0] in allowed, f"refusing to run non-fake binary: {argv[0]}"
        return real_popen(argv, *a, **kw)

    monkeypatch.setattr(subprocess, "Popen", guarded)


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "codex_home"
    h.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(h))
    monkeypatch.setenv("SPRITE_FORGE_CODEX_BIN", str(FAKE))
    for k in list(os.environ):
        if k.startswith("FAKE_CODEX"):
            monkeypatch.delenv(k)
    return h


@pytest.fixture
def provider(home):
    p = CodexCliProvider()
    assert p.codex_bin == str(FAKE) and p.codex_home == home
    return p


def run(provider, tmp_path, monkeypatch, mode=None, refs=(), timeout_s=60, on_progress=None):
    if mode:
        monkeypatch.setenv("FAKE_CODEX_MODE", mode)
    out = tmp_path / "attempt"
    return provider.generate(GenerationRequest(PROMPT, list(refs), out, timeout_s), on_progress), out


def test_codex_cli_success(provider, tmp_path, monkeypatch):
    stages = []
    res, out = run(provider, tmp_path, monkeypatch, "success", on_progress=lambda s, p: stages.append(s))
    assert res.status == "succeeded" and res.error_code is None
    assert res.raw_path == out / "raw.png"
    with Image.open(res.raw_path) as im:
        assert im.format == "PNG"
    g = json.loads((out / "generation.json").read_text())
    assert g == res.meta
    assert g["provider"] == "codex-cli" and g["status"] == "succeeded"
    assert g["source_resolved_by"] == "rollout"
    assert g["revised_prompt"] == "Revised fake prompt #1"
    assert g["thread_id"] and g["exit_code"] == 0 and g["last_message"] == "DONE"
    assert g["usage"]["input_tokens"] == 144463
    assert g["raw"]["file"] == "raw.png" and g["raw"]["width"] > 0
    assert g["warnings"] == [] and g["argv"][-1] == "-"
    assert g["prompt_sha256"]
    for name in ("codex-events.jsonl", "codex-stderr.txt", "codex-last-message.txt"):
        assert (out / name).exists()
    assert stages[0] == "starting" and "session" in stages and "generating" in stages
    assert stages[-1] == "collecting"


def test_codex_cli_no_rollout(provider, tmp_path, monkeypatch):
    res, out = run(provider, tmp_path, monkeypatch, "no_rollout")
    assert res.status == "succeeded"
    assert res.meta["source_resolved_by"] == "glob"
    assert res.meta["revised_prompt"] is None


def test_codex_cli_no_image(provider, tmp_path, monkeypatch):
    res, out = run(provider, tmp_path, monkeypatch, "no_image")
    assert (res.status, res.error_code) == ("failed", "no_image")
    assert res.raw_path is None and not (out / "raw.png").exists()
    assert json.loads((out / "generation.json").read_text())["error_code"] == "no_image"


def test_codex_cli_multiple_images(provider, tmp_path, monkeypatch):
    res, out = run(provider, tmp_path, monkeypatch, "multiple_images")
    assert res.status == "succeeded"
    assert "multiple_images: 2" in res.meta["warnings"]
    assert res.meta["revised_prompt"] == "Revised fake prompt #2"
    newest = max((provider.codex_home / "generated_images" / res.meta["thread_id"]).glob("*.png"),
                 key=lambda p: p.stat().st_mtime)
    assert res.meta["source_image"] == str(newest)


def test_codex_cli_image_gen_failed(provider, tmp_path, monkeypatch):
    res, out = run(provider, tmp_path, monkeypatch, "image_gen_failed")
    assert (res.status, res.error_code) == ("failed", "image_gen_failed")
    assert "content policy" in res.error_message


def test_codex_cli_exit_1(provider, tmp_path, monkeypatch):
    res, out = run(provider, tmp_path, monkeypatch, "exit_1")
    assert (res.status, res.error_code) == ("failed", "codex_failed")
    assert "fake codex error line 25" in res.error_message
    assert "fake codex error line 5\n" not in res.error_message  # only the last 20 lines
    assert res.meta["exit_code"] == 1


def test_codex_cli_hang_timeout(provider, tmp_path, monkeypatch):
    pids = []
    real = subprocess.Popen

    def spy(argv, *a, **kw):
        p = real(argv, *a, **kw)
        pids.append(p.pid)
        return p

    monkeypatch.setattr(subprocess, "Popen", spy)  # wraps the guard; still goes through it
    t0 = time.time()
    res, out = run(provider, tmp_path, monkeypatch, "hang", timeout_s=2)
    assert time.time() - t0 < 15
    assert (res.status, res.error_code) == ("timeout", "timeout")
    assert res.raw_path is None
    assert len(pids) == 1
    with pytest.raises(ProcessLookupError):
        os.kill(pids[0], 0)  # reaped: the fake is gone
    with pytest.raises(ProcessLookupError):
        os.killpg(pids[0], 0)  # and so is its whole process group
    assert json.loads((out / "generation.json").read_text())["status"] == "timeout"


def test_codex_cli_invalid_png(provider, tmp_path, monkeypatch):
    res, out = run(provider, tmp_path, monkeypatch, "invalid_png")
    assert (res.status, res.error_code) == ("failed", "invalid_image")
    assert not (out / "raw.png").exists()


def test_codex_cli_config_warnings(provider, tmp_path, monkeypatch):
    stages = []
    res, out = run(provider, tmp_path, monkeypatch, "config_warnings", on_progress=lambda s, p: stages.append(s))
    assert res.status == "succeeded"  # error items are not fatal (F16)
    assert len([w for w in res.meta["warnings"] if w.startswith("codex_error:")]) == 2
    assert stages.count("log") == 2


def test_codex_cli_references_and_argv(provider, tmp_path, monkeypatch):
    refs = []
    for i in range(2):
        p = tmp_path / f"r{i}.png"
        Image.new("RGB", (8, 8), (i, 0, 0)).save(p)
        refs.append(p)
    res, out = run(provider, tmp_path, monkeypatch, "success", refs=refs)
    assert res.status == "succeeded"
    assert [r["file"] for r in res.meta["references"]] == ["ref-01.png", "ref-02.png"]
    argv = res.meta["argv"]
    assert argv.count("-i") == 2
    vals = [argv[i + 1] for i, a in enumerate(argv) if a == "-i"]
    assert [Path(v).name for v in vals] == ["ref-01.png", "ref-02.png"]


@pytest.mark.parametrize("n_refs", [0, 1, 2])
def test_codex_cli_argv_construction(tmp_path, n_refs):
    refs = [tmp_path / f"ref-0{i + 1}.png" for i in range(n_refs)]
    argv = build_argv("codex", tmp_path, refs)
    assert argv[-1] == "-" and argv[-3] == "-o" and argv[1] == "exec"
    assert argv.count("-i") == n_refs
    for i, a in enumerate(argv):
        if a == "-i":
            assert argv[i + 1] != "-" and not argv[i + 1].startswith("-")
    assert all(isinstance(a, str) for a in argv)  # list, no shell string


def test_codex_cli_no_shell(provider, tmp_path, monkeypatch):
    seen = {}
    real = subprocess.Popen

    def spy(argv, *a, **kw):
        seen.update(argv=argv, kw=kw)
        return real(argv, *a, **kw)

    monkeypatch.setattr(subprocess, "Popen", spy)
    run(provider, tmp_path, monkeypatch, "success")
    assert isinstance(seen["argv"], list) and not seen["kw"].get("shell")
    assert seen["kw"]["start_new_session"] is True


def test_codex_cli_instruction_template():
    text = render_instruction("hello {x}", has_refs=True)
    assert "<<<PROMPT\nhello {x}\nPROMPT>>>" in text and "Image 1 is the strict" in text
    assert "referenced images" not in render_instruction("p", has_refs=False)


def test_codex_cli_cancel(provider, tmp_path, monkeypatch):
    results = []
    started = threading.Event()

    def on_progress(stage, payload):
        if stage == "session":
            started.set()

    t = threading.Thread(target=lambda: results.append(run(provider, tmp_path, monkeypatch, "hang", on_progress=on_progress)))
    t.start()
    assert started.wait(15)
    pid = provider._proc.pid
    provider.cancel()
    t.join(15)
    assert not t.is_alive()
    res, out = results[0]
    assert (res.status, res.error_code) == ("canceled", "canceled")
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def test_codex_cli_check_missing(tmp_path, home):
    p = CodexCliProvider(codex_bin=str(tmp_path / "no-such-codex"))
    info = p.check()
    assert info["installed"] is False and info["ready"] is False
    assert info["logged_in"] is False and info["image_generation"] is False
    res = p.generate(GenerationRequest("x", [], tmp_path / "o", 5))
    assert (res.status, res.error_code) == ("failed", "codex_not_installed")
    assert (tmp_path / "o" / "generation.json").exists()
