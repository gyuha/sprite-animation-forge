"""CLI commands that call Codex: identity analyze, reference generate/select, generate, prompt, doctor.

Every call goes through the fake codex (SPRITE_FORGE_CODEX_BIN); the autouse fixture guarantees that no test
in this file can reach a real binary.
"""

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from conftest import FORGE
from fixtures.synthetic.make import make_sheet
from PIL import Image

from sprite_forge import schemas
from sprite_forge.fsutil import file_lock

FAKE = Path(__file__).resolve().parent / "fixtures" / "fake_codex" / "codex"


@pytest.fixture(autouse=True)
def fake_env(tmp_path, monkeypatch):
    home = tmp_path / "codex_home"
    home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.setenv("SPRITE_FORGE_CODEX_BIN", str(FAKE))
    for k in [k for k in os.environ if k.startswith("FAKE_CODEX")]:
        monkeypatch.delenv(k)
    return home


@pytest.fixture
def ref_png(tmp_path):
    path = tmp_path / "knight.png"
    make_sheet("clean", rows=1, cols=1).save(path)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def manifest(forge, cid="hero"):
    return json.loads((forge.root / cid / "manifest.json").read_text())


def ready(forge, ref_png, *plan_args, view="side"):
    """init + reference import + identity analyze + plan (idle by default)."""
    forge.ok("init", "hero", "--view", view)
    forge.ok("reference", "import", "hero", ref_png)
    forge.ok("identity", "analyze", "hero")
    forge.ok("plan", "hero", *(plan_args or ("--actions", "idle")))
    return forge.root / "hero"


def accept_unit(forge, tmp_path, action, direction):
    raw = tmp_path / f"{action}_{direction}.png"
    make_sheet("clean", rows=2, cols=3).save(raw)
    forge.ok("import-raw", "hero", action, raw, "--direction", direction)
    forge.ok("process", "hero", action, "--direction", direction)
    return forge.ok("accept", "hero", action, "--direction", direction)


# ---- identity ---------------------------------------------------------------------------------

def test_identity_analyze_writes_schema_valid_profile(forge, ref_png):
    forge.ok("init", "hero")
    forge.ok("reference", "import", "hero", ref_png)
    out = forge.ok("identity", "analyze", "hero")
    cd = forge.root / "hero"
    profile = json.loads((cd / "character-profile.json").read_text())
    assert out == {"profile": profile}
    schemas.validate("character-profile", profile)
    assert profile["source"] == "codex-analysis" and profile["edited_by_user"] is False
    assert profile["identity"]["primary_colors"] == ["#C8281E", "#9A9CA0"]
    schemas.validate("character-profile.llm", json.loads((cd / "reference/identity-raw.json").read_text()))
    assert manifest(forge)["usage"]["codex_calls"] == 1


def test_identity_analyze_without_reference_exits_3(forge):
    forge.ok("init", "hero")
    code, out = forge.run("identity", "analyze", "hero")
    assert code == 3 and out["error_code"] == "no_reference"
    code, out = forge.run("identity", "analyze", "ghost")
    assert code == 3 and out["error_code"] == "no_character"


@pytest.mark.parametrize("mode, error_code", [("invalid_json", "invalid_profile"), ("bad_schema", "invalid_profile"),
                                              ("exit_1", "codex_failed")])
def test_identity_analyze_failures_exit_2_and_write_nothing(forge, ref_png, monkeypatch, mode, error_code):
    forge.ok("init", "hero")
    forge.ok("reference", "import", "hero", ref_png)
    monkeypatch.setenv("FAKE_CODEX_MODE", mode)
    code, out = forge.run("identity", "analyze", "hero")
    assert code == 2 and out["error_code"] == error_code
    assert not (forge.root / "hero" / "character-profile.json").exists()


def test_identity_analyze_codex_missing_exits_2(forge, ref_png, tmp_path, monkeypatch):
    forge.ok("init", "hero")
    forge.ok("reference", "import", "hero", ref_png)
    monkeypatch.setenv("SPRITE_FORGE_CODEX_BIN", str(tmp_path / "no-such-codex"))
    code, out = forge.run("identity", "analyze", "hero")
    assert code == 2 and out["error_code"] == "codex_not_installed"


def test_identity_edited_profile_is_preserved_unless_forced(forge, ref_png):
    cd = ready(forge, ref_png)
    path = cd / "character-profile.json"
    profile = json.loads(path.read_text())
    profile["edited_by_user"] = True
    profile["identity"]["hair"] = "braided"
    path.write_text(json.dumps(profile))
    code, out = forge.run("identity", "analyze", "hero")
    assert code == 1 and out["error_code"] == "profile_edited"
    assert json.loads(path.read_text())["identity"]["hair"] == "braided"
    out = forge.ok("identity", "analyze", "hero", "--force")
    assert out["profile"]["edited_by_user"] is False and out["profile"]["identity"]["hair"] == ""


def test_identity_empty_flag_needs_no_codex(forge, ref_png, tmp_path, monkeypatch):
    forge.ok("init", "hero")
    monkeypatch.setenv("SPRITE_FORGE_CODEX_BIN", str(tmp_path / "no-such-codex"))
    out = forge.ok("identity", "analyze", "hero", "--empty")
    assert out["profile"]["source"] == "empty"
    schemas.validate("character-profile", out["profile"])


# ---- reference generate / select --------------------------------------------------------------

def test_reference_generate_creates_attempts(forge):
    forge.ok("init", "hero", "--art-style", "pixel_art")
    out = forge.ok("reference", "generate", "hero", "--description", "a red hooded knight", "--count", "2")
    assert out == {"attempts": [{"attempt": "001", "status": "succeeded"}, {"attempt": "002", "status": "succeeded"}]}
    for n in ("001", "002"):
        d = forge.root / "hero/reference/attempts" / n
        assert (d / "raw.png").exists() and (d / "generation.json").exists()
        assert "a red hooded knight" in (d / "prompt.txt").read_text()
        assert json.loads((d / "generation.json").read_text())["references"] == []
    assert manifest(forge)["reference"] is None  # nothing is canonical until `reference select`
    assert manifest(forge)["usage"]["codex_calls"] == 2


def test_reference_generate_validates_input(forge):
    forge.ok("init", "hero")
    code, out = forge.run("reference", "generate", "hero", "--description", "x", "--count", "5")
    assert code == 1 and out["error_code"] == "usage"
    code, out = forge.run("reference", "generate", "hero", "--description", "  ")
    assert code == 1 and out["error_code"] == "invalid_params"
    code, out = forge.run("reference", "generate", "ghost", "--description", "x")
    assert code == 3 and out["error_code"] == "no_character"


def test_reference_generate_all_failed_exits_2_with_attempts(forge, monkeypatch):
    forge.ok("init", "hero")
    monkeypatch.setenv("FAKE_CODEX_MODE", "no_image")
    code, out = forge.run("reference", "generate", "hero", "--description", "a knight", "--count", "2")
    assert code == 2 and out["error_code"] == "no_image"
    assert [a["status"] for a in out["attempts"]] == ["failed", "failed"]


def test_reference_select_makes_attempt_canonical(forge):
    forge.ok("init", "hero")
    forge.ok("reference", "generate", "hero", "--description", "a knight", "--count", "2")
    out = forge.ok("reference", "select", "hero", "002")
    cd = forge.root / "hero"
    assert out["reference"] == "reference/attempts/002/raw.png" and out["selected_attempt"] == "002"
    assert (cd / "reference/character.png").exists() and (cd / "reference/character-keyed.png").exists()
    ref = manifest(forge)["reference"]
    assert ref == {"mode": "generated_image", "source": "reference/attempts/002/raw.png",
                   "source_sha256": sha(cd / "reference/attempts/002/raw.png"), "selected_attempt": "002"}
    schemas.validate("manifest", manifest(forge))
    # the selected reference unlocks identity analyze
    forge.ok("identity", "analyze", "hero")


def test_reference_select_unknown_attempt_exits_3(forge):
    forge.ok("init", "hero")
    for bad in ("001", "1", "../x"):
        code, out = forge.run("reference", "select", "hero", bad)
        assert code == 3 and out["error_code"] == "no_attempt"


# ---- generate ---------------------------------------------------------------------------------

def test_generate_happy_path_creates_attempt_files(forge, ref_png):
    cd = ready(forge, ref_png)
    out = forge.ok("generate", "hero", "idle")
    assert out == {"attempt": "001", "unit": "idle", "status": "succeeded"}
    adir = cd / "idle/attempts/001"
    for name in ("prompt.txt", "raw.png", "generation.json", "ref-01.png", "codex-events.jsonl",
                 "codex-stderr.txt", "codex-last-message.txt"):
        assert (adir / name).exists(), name
    gen = json.loads((adir / "generation.json").read_text())
    assert gen["status"] == "succeeded" and gen["provider"] == "codex-cli"
    assert gen["prompt_template_version"] == "action_prompt@3" and gen["prompt_file"] == "prompt.txt"
    assert gen["prompt_sha256"] == sha(adir / "prompt.txt")
    assert [r["source"] for r in gen["references"]] == ["reference/character-keyed.png"]
    assert gen["references"][0]["sha256"] == sha(cd / "reference/character-keyed.png")
    assert "idle" in (adir / "prompt.txt").read_text().lower()
    ent = manifest(forge)["actions"]["idle"]["attempts"]["001"]
    assert ent["provider"] == "codex-cli" and ent["generation_status"] == "succeeded" and ent["qc_status"] is None
    schemas.validate("manifest", manifest(forge))
    # the generated attempt flows into the existing pipeline unchanged
    assert forge.ok("process", "hero", "idle")["attempt"] == "001"
    assert forge.ok("accept", "hero", "idle")["accepted"] == "001"
    assert forge.ok("generate", "hero", "idle")["attempt"] == "002"


@pytest.mark.parametrize("mode, error_code", [
    ("no_image", "no_image"), ("image_gen_failed", "image_gen_failed"), ("exit_1", "codex_failed"),
    ("invalid_png", "invalid_image"),
])
def test_generate_provider_failure_exits_2_with_error_code(forge, ref_png, monkeypatch, mode, error_code):
    cd = ready(forge, ref_png)
    monkeypatch.setenv("FAKE_CODEX_MODE", mode)
    code, out = forge.run("generate", "hero", "idle")
    assert code == 2
    assert out["error_code"] == error_code and out["attempt"] == "001" and out["status"] == "failed"
    adir = cd / "idle/attempts/001"
    assert (adir / "prompt.txt").exists() and not (adir / "raw.png").exists()
    assert json.loads((adir / "generation.json").read_text())["error_code"] == error_code
    assert manifest(forge)["actions"]["idle"]["attempts"]["001"]["generation_status"] == "failed"
    # a failed attempt does not block the next one
    monkeypatch.setenv("FAKE_CODEX_MODE", "success")
    assert forge.ok("generate", "hero", "idle")["attempt"] == "002"


def test_generate_timeout_exits_2(forge, ref_png, monkeypatch):
    ready(forge, ref_png)
    monkeypatch.setenv("FAKE_CODEX_MODE", "hang")
    code, out = forge.run("generate", "hero", "idle", "--timeout", "1")
    assert code == 2 and out["error_code"] == "timeout" and out["status"] == "timeout"
    assert manifest(forge)["actions"]["idle"]["attempts"]["001"]["generation_status"] == "timeout"


def test_generate_codex_missing_exits_2(forge, ref_png, tmp_path, monkeypatch):
    ready(forge, ref_png)
    monkeypatch.setenv("SPRITE_FORGE_CODEX_BIN", str(tmp_path / "no-such-codex"))
    code, out = forge.run("generate", "hero", "idle")
    assert code == 2 and out["error_code"] == "codex_not_installed"


def test_generate_missing_preconditions_exit_3(forge, ref_png):
    forge.ok("init", "hero")
    code, out = forge.run("generate", "hero", "idle")
    assert (code, out["error_code"]) == (3, "no_plan")
    forge.ok("plan", "hero", "--actions", "idle")
    code, out = forge.run("generate", "hero", "idle")
    assert (code, out["error_code"]) == (3, "no_reference")
    forge.ok("reference", "import", "hero", ref_png)
    code, out = forge.run("generate", "hero", "idle")
    assert (code, out["error_code"]) == (3, "no_profile")
    code, out = forge.run("generate", "ghost", "idle")
    assert (code, out["error_code"]) == (3, "no_character")
    assert not (forge.root / "hero/idle/attempts").exists()  # nothing was allocated


def test_generate_rejects_unknown_action_and_bad_recovery(forge, ref_png):
    ready(forge, ref_png)
    code, out = forge.run("generate", "hero", "walk")
    assert code == 1 and out["error_code"] == "unknown_action"
    code, out = forge.run("generate", "hero", "idle", "--recovery", "nonsense")
    assert code == 1 and out["error_code"] == "invalid_params"
    assert not (forge.root / "hero/idle/attempts").exists()


def test_generate_extra_and_recovery_are_in_prompt_and_manifest(forge, ref_png):
    cd = ready(forge, ref_png)
    forge.ok("generate", "hero", "idle", "--extra", "hold the sword high", "--recovery", "edge_touch")
    assert "hold the sword high" in (cd / "idle/attempts/001/prompt.txt").read_text()
    ent = manifest(forge)["actions"]["idle"]["attempts"]["001"]
    assert ent["extra"] == "hold the sword high" and ent["recovery"] == ["edge_touch"]


def test_generate_direction_required_and_mirrored_left_rejected(forge, ref_png):
    ready(forge, ref_png, "--actions", "walk", view="topdown")
    code, out = forge.run("generate", "hero", "walk")
    assert code == 1 and out["error_code"] == "direction_required"
    code, out = forge.run("generate", "hero", "walk", "--direction", "left")
    assert code == 1 and out["error_code"] == "mirrored_direction"


def test_generate_direction_reference_attached_for_non_representative_direction(forge, ref_png, tmp_path):
    cd = ready(forge, ref_png, "--actions", "walk", view="topdown")
    # representative direction (down): only the keyed character is attached
    code, out = forge.run("generate", "hero", "walk", "--direction", "up")
    assert (code, out["error_code"]) == (3, "no_direction_reference")  # walk/down is not accepted yet
    assert not (cd / "walk/up/attempts").exists()
    forge.ok("generate", "hero", "walk", "--direction", "down")
    down = json.loads((cd / "walk/down/attempts/001/generation.json").read_text())
    assert [r["file"] for r in down["references"]] == ["ref-01.png"]
    accept_unit(forge, tmp_path, "walk", "down")

    assert forge.ok("generate", "hero", "walk", "--direction", "up")["unit"] == "walk/up"
    adir = cd / "walk/up/attempts/001"
    gen = json.loads((adir / "generation.json").read_text())
    assert [r["file"] for r in gen["references"]] == ["ref-01.png", "ref-02.png"]
    assert [r["source"] for r in gen["references"]] == ["reference/character-keyed.png", "walk/down/frames/000.png"]
    assert gen["argv"].count("-i") == 2 and gen["argv"][gen["argv"].index("-i") + 1].endswith("ref-01.png")
    assert sha(adir / "ref-02.png") != sha(cd / "walk/down/raw.png")  # one adopted frame, not the whole raw sheet (see test_direction_reference_frame)
    assert "DIRECTION REFERENCE" in (adir / "prompt.txt").read_text()
    assert "DIRECTION REFERENCE" not in (cd / "walk/down/attempts/001/prompt.txt").read_text()


def test_generate_calls_are_serialised_by_codex_lock(forge, ref_png):
    cd = ready(forge, ref_png)
    lock = forge.root / ".codex.lock"
    with file_lock(lock):
        proc = subprocess.Popen([sys.executable, str(FORGE), "--root", str(forge.root), "--quiet", "generate", "hero", "idle"],
                                stdout=subprocess.PIPE, text=True)
        time.sleep(1.5)
        assert proc.poll() is None, "generate must wait while another Codex call holds the lock"
        assert not (cd / "idle/attempts").exists()
    out, _ = proc.communicate(timeout=60)
    assert proc.returncode == 0 and json.loads(out)["attempt"] == "001"


# ---- prompt -----------------------------------------------------------------------------------

def test_prompt_cmd_prints_prompt_without_saving(forge, ref_png):
    cd = ready(forge, ref_png)
    out = forge.ok("prompt", "hero", "idle")
    assert out["references_needed"] == ["character"] and out["warnings"] == []
    assert out["prompt"].startswith("Create a 2x2 sprite animation grid") and "#FF00FF" in out["prompt"]
    assert "steel visor" in out["prompt"]  # identity from character-profile.json
    assert not (cd / "idle/attempts").exists()
    assert manifest(forge)["usage"]["codex_calls"] == 1  # only the identity call


def test_prompt_cmd_extra_and_recovery(forge, ref_png):
    ready(forge, ref_png)
    out = forge.ok("prompt", "hero", "idle", "--extra", "slow breathing", "--recovery", "edge_touch")
    assert "ADDITIONAL DIRECTION" in out["prompt"] and "slow breathing" in out["prompt"]
    assert "RECOVERY" in out["prompt"]
    code, out = forge.run("prompt", "hero", "idle", "--recovery", "bogus")
    assert code == 1 and out["error_code"] == "invalid_params"


def test_prompt_cmd_direction_lists_direction_reference(forge, ref_png):
    ready(forge, ref_png, "--actions", "idle,walk", view="topdown")
    assert forge.ok("prompt", "hero", "walk", "--direction", "down")["references_needed"] == ["character"]
    out = forge.ok("prompt", "hero", "walk", "--direction", "up")
    assert out["references_needed"] == ["character", "direction:idle/down"]
    assert "DIRECTION REFERENCE" in out["prompt"]
    code, out = forge.run("prompt", "hero", "walk")
    assert code == 1 and out["error_code"] == "direction_required"


def test_prompt_cmd_needs_plan_but_not_profile(forge):
    forge.ok("init", "hero")
    code, out = forge.run("prompt", "hero", "idle")
    assert (code, out["error_code"]) == (3, "no_plan")
    forge.ok("plan", "hero", "--actions", "idle")
    assert "REFERENCE IDENTITY" in forge.ok("prompt", "hero", "idle")["prompt"]


# ---- doctor -----------------------------------------------------------------------------------

def test_doctor_codex_absent_is_valid_json_exit_0(forge, tmp_path, monkeypatch):
    monkeypatch.setenv("SPRITE_FORGE_CODEX_BIN", str(tmp_path / "no-such-codex"))
    code, out = forge.run("doctor")
    assert code == 0
    assert out["codex"]["installed"] is False and out["codex"]["version"] is None
    assert out["ready"] is False
    assert any(w.startswith("codex_not_installed") for w in out["warnings"])
    assert set(out["python"]) == {"pillow", "numpy", "scipy"} and all(out["python"].values())


def test_doctor_ready_with_fake_codex(forge, fake_env):
    out = forge.ok("doctor")
    assert out["codex"] == {"installed": True, "version": "0.159.2", "tested_version": "0.159.2", "version_ok": True,
                            "logged_in": True, "auth": "ChatGPT", "image_generation": True,
                            "codex_home": str(fake_env)}
    assert out["ready"] is True and out["warnings"] == []


@pytest.mark.parametrize("state, field, warning", [
    ("logged_out", "logged_in", "codex_not_logged_in"),
    ("image_disabled", "image_generation", "image_generation_disabled"),
    ("old_version", "version_ok", "codex_version_too_old"),
])
def test_doctor_reports_problems_as_warnings(forge, monkeypatch, state, field, warning):
    monkeypatch.setenv("FAKE_CODEX_DOCTOR", state)
    out = forge.ok("doctor")
    assert out["codex"][field] is False and out["ready"] is False
    assert any(w.startswith(warning) for w in out["warnings"])


def test_doctor_missing_codex_home_warns(forge, tmp_path, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "absent"))
    out = forge.ok("doctor")
    assert out["ready"] is False and any(w.startswith("codex_home_missing") for w in out["warnings"])
