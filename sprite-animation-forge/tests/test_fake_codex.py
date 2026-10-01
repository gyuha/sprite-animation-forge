import base64
import io
import json
import os
import subprocess
from pathlib import Path

import pytest
from PIL import Image

FAKE = Path(__file__).resolve().parent / "fixtures" / "fake_codex" / "codex"
PROMPT = "You are a worker.\n<<<PROMPT\ndraw a knight\nPROMPT>>>\n"


@pytest.fixture
def env(tmp_path):
    home = tmp_path / "codex_home"
    home.mkdir()
    e = {k: v for k, v in os.environ.items() if not k.startswith("FAKE_CODEX")}
    e["CODEX_HOME"] = str(home)
    return e


def argv_for(tmp_path, refs=()):
    a = ["exec", "--json", "--skip-git-repo-check", "-s", "workspace-write",
         "-C", str(tmp_path), "-c", 'model_reasoning_effort="low"']
    for r in refs:
        a += ["-i", r]
    return a + ["-o", str(tmp_path / "codex-last-message.txt"), "-"]


def run(env, argv, stdin=PROMPT, mode=None, **extra):
    e = dict(env, **extra)
    if mode:
        e["FAKE_CODEX_MODE"] = mode
    return subprocess.run([str(FAKE), *argv], input=stdin, env=e, capture_output=True,
                          text=True, timeout=30)


def events(proc):
    return [json.loads(line) for line in proc.stdout.splitlines()]


def thread_id(proc):
    return events(proc)[0]["thread_id"]


def rollout_items(env, tid):
    files = list(Path(env["CODEX_HOME"]).glob(f"sessions/*/*/*/rollout-*-{tid}.jsonl"))
    assert len(files) == 1
    lines = [json.loads(x) for x in files[0].read_text().splitlines()]
    return [x["payload"]["item"] for x in lines if x["type"] == "event_msg"]


def images(env, tid):
    return sorted((Path(env["CODEX_HOME"]) / "generated_images" / tid).glob("exec-*.png"),
                  key=lambda p: p.stat().st_mtime)


def test_fake_codex_is_executable():
    assert os.access(FAKE, os.X_OK)
    assert FAKE.read_text().startswith("#!/usr/bin/env python3")


def test_fake_codex_success(env, tmp_path):
    ref = tmp_path / "ref-01.png"
    Image.new("RGB", (4, 4)).save(ref)
    p = run(env, argv_for(tmp_path, [str(ref)]))
    assert p.returncode == 0, p.stderr
    ev = events(p)
    assert [e["type"] for e in ev][:2] == ["thread.started", "turn.started"]
    assert ev[-1]["type"] == "turn.completed" and "usage" in ev[-1]
    assert any(e["type"] == "item.completed" and e["item"]["type"] == "agent_message" for e in ev)
    tid = thread_id(p)
    (img,) = images(env, tid)
    assert img.name.startswith("exec-") and Image.open(img).size == (512, 512)
    (item,) = rollout_items(env, tid)
    assert item["kind"] == "image_gen.generation" and item["status"] == "completed"
    assert item["savedPath"] == str(img) and item["failure"] is None
    assert item["revisedPrompt"]
    assert Image.open(io.BytesIO(base64.b64decode(item["result"]))).size == (512, 512)
    assert (tmp_path / "codex-last-message.txt").read_text() == "DONE"


def test_fake_codex_image_and_grid_selection(env, tmp_path):
    p = run(env, argv_for(tmp_path), FAKE_CODEX_IMAGE="native_alpha", FAKE_CODEX_GRID="2x3")
    (img,) = images(env, thread_id(p))
    im = Image.open(img)
    assert im.mode == "RGBA" and im.size == (768, 512)
    assert run(env, argv_for(tmp_path), FAKE_CODEX_IMAGE="bogus").returncode == 2


@pytest.mark.parametrize("mutate", [
    lambda a: a[1:],                                       # no 'exec'
    lambda a: a[:-1],                                      # no final '-'
    lambda a: [x for x in a if x != "--json"],
    lambda a: a[:a.index("-C")] + a[a.index("-C") + 2:],   # no -C
    lambda a: a[:-3] + ["-"],                              # no -o
    lambda a: a[:-3] + ["-i", "x.png", "-"],               # '-' directly after -i
], ids=["no_exec", "no_dash", "no_json", "no_C", "no_o", "dash_after_i"])
def test_fake_codex_argv_violations_exit_2(env, tmp_path, mutate):
    p = run(env, mutate(argv_for(tmp_path)))
    assert p.returncode == 2 and p.stdout == ""


@pytest.mark.parametrize("stdin", ["no markers", "<<<PROMPT only", "only PROMPT>>>", ""])
def test_fake_codex_prompt_markers_missing_exit_2(env, tmp_path, stdin):
    p = run(env, argv_for(tmp_path), stdin=stdin)
    assert p.returncode == 2
    assert not (Path(env["CODEX_HOME"]) / "generated_images").exists()


def test_fake_codex_requires_codex_home(env, tmp_path):
    env = {k: v for k, v in env.items() if k != "CODEX_HOME"}
    assert run(env, argv_for(tmp_path)).returncode == 2


def test_fake_codex_unknown_mode_exit_2(env, tmp_path):
    assert run(env, argv_for(tmp_path), mode="nope").returncode == 2


def test_fake_codex_no_rollout(env, tmp_path):
    p = run(env, argv_for(tmp_path), mode="no_rollout")
    assert p.returncode == 0
    assert len(images(env, thread_id(p))) == 1
    assert not list(Path(env["CODEX_HOME"]).glob("sessions/**/*.jsonl"))


def test_fake_codex_no_image(env, tmp_path):
    p = run(env, argv_for(tmp_path), mode="no_image")
    assert p.returncode == 0 and events(p)[-1]["type"] == "turn.completed"
    assert not (Path(env["CODEX_HOME"]) / "generated_images").exists()
    assert not list(Path(env["CODEX_HOME"]).glob("sessions/**/*.jsonl"))


def test_fake_codex_multiple_images(env, tmp_path):
    p = run(env, argv_for(tmp_path), mode="multiple_images")
    tid = thread_id(p)
    imgs, items = images(env, tid), rollout_items(env, tid)
    assert len(imgs) == 2 and len(items) == 2
    assert items[-1]["savedPath"] == str(imgs[-1])  # last item == newest mtime


def test_fake_codex_image_gen_failed(env, tmp_path):
    p = run(env, argv_for(tmp_path), mode="image_gen_failed")
    assert p.returncode == 0
    tid = thread_id(p)
    (item,) = rollout_items(env, tid)
    assert item["failure"] and item["savedPath"] is None
    assert images(env, tid) == []
    assert (tmp_path / "codex-last-message.txt").read_text().startswith("FAILED:")


def test_fake_codex_exit_1(env, tmp_path):
    p = run(env, argv_for(tmp_path), mode="exit_1")
    assert p.returncode == 1
    assert "fake codex error line 25" in p.stderr
    assert not (Path(env["CODEX_HOME"]) / "generated_images").exists()


def test_fake_codex_hang_is_killable(env, tmp_path):
    e = dict(env, FAKE_CODEX_MODE="hang")
    proc = subprocess.Popen([str(FAKE), *argv_for(tmp_path)], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=e, text=True)
    proc.stdin.write(PROMPT)
    proc.stdin.close()
    assert json.loads(proc.stdout.readline())["type"] == "thread.started"
    with pytest.raises(subprocess.TimeoutExpired):
        proc.wait(timeout=2)
    proc.terminate()
    assert proc.wait(timeout=5) != 0
    proc.stdout.close()
    proc.stderr.close()


def test_fake_codex_invalid_png(env, tmp_path):
    p = run(env, argv_for(tmp_path), mode="invalid_png")
    (img,) = images(env, thread_id(p))
    with pytest.raises(Exception):
        Image.open(img).load()


def test_fake_codex_config_warnings(env, tmp_path):
    p = run(env, argv_for(tmp_path), mode="config_warnings")
    assert p.returncode == 0
    errs = [e for e in events(p) if e["type"] == "item.completed" and e["item"]["type"] == "error"]
    assert len(errs) == 2
    assert len(images(env, thread_id(p))) == 1
