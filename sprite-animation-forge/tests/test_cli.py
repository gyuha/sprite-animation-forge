import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from conftest import FORGE
from fixtures.synthetic.make import make_sheet
from PIL import Image

from sprite_forge import __version__


def test_cli_version_and_no_command():
    out = subprocess.run([sys.executable, str(FORGE), "--version"], capture_output=True, text=True)
    assert out.returncode == 0 and out.stdout.strip() == __version__
    out = subprocess.run([sys.executable, str(FORGE)], capture_output=True, text=True)
    assert out.returncode == 1 and json.loads(out.stdout)["error_code"] == "usage"


def test_cli_usage_error_is_json_exit_1(forge):
    code, out = forge.run("plan", "hero", "--bogus")
    assert code == 1 and out["error_code"] == "usage"
    code, out = forge.run("frobnicate")
    assert code == 1 and out["error_code"] == "usage"


def test_cli_init_creates_manifest(forge):
    out = forge.ok("init", "hero", "--view", "topdown", "--art-style", "pixel_art")
    assert out["character"] == "hero" and out["dir"] == str(forge.root / "hero")
    m = json.loads((forge.root / "hero" / "manifest.json").read_text())
    assert m["settings"] == {"view": "topdown", "art_style": "pixel_art", "asset_type": "character"}


def test_cli_init_twice_and_bad_id(forge):
    forge.ok("init", "hero")
    code, out = forge.run("init", "hero")
    assert code == 1 and out["error_code"] == "exists"
    code, out = forge.run("init", "Bad_ID")
    assert code == 1 and out["error_code"] == "invalid_character_id"


def test_cli_root_option_after_command_and_env(tmp_path):
    root = tmp_path / "r"
    out = subprocess.run([sys.executable, str(FORGE), "init", "hero", "--root", str(root), "--quiet"],
                         capture_output=True, text=True)
    assert out.returncode == 0 and (root / "hero" / "manifest.json").exists()
    env_root = tmp_path / "env"
    out = subprocess.run([sys.executable, str(FORGE), "init", "elf"], capture_output=True, text=True,
                         env={"SPRITE_FORGE_ROOT": str(env_root), "PATH": ""}, cwd=tmp_path)
    assert out.returncode == 0 and (env_root / "elf" / "manifest.json").exists()


def test_cli_quiet_silences_stderr(tmp_path):
    base = [sys.executable, str(FORGE), "--root", str(tmp_path)]
    loud = subprocess.run([*base, "init", "a"], capture_output=True, text=True)
    quiet = subprocess.run([*base, "--quiet", "init", "b"], capture_output=True, text=True)
    assert loud.stderr.strip() and quiet.stderr == ""


def test_cli_preconditions_exit_3(forge, raw_sheet):
    code, out = forge.run("plan", "ghost", "--actions", "idle")
    assert (code, out["error_code"]) == (3, "no_character")
    forge.ok("init", "hero")
    for args in (("import-raw", "hero", "idle", raw_sheet), ("process", "hero", "idle"), ("accept", "hero", "idle")):
        code, out = forge.run(*args)
        assert (code, out["error_code"]) == (3, "no_plan"), args
    forge.ok("plan", "hero", "--actions", "idle")
    code, out = forge.run("process", "hero", "idle")
    assert (code, out["error_code"]) == (3, "no_attempt")
    code, out = forge.run("accept", "hero", "idle")
    assert (code, out["error_code"]) == (3, "no_attempt")
    forge.ok("import-raw", "hero", "idle", raw_sheet)
    code, out = forge.run("accept", "hero", "idle")
    assert (code, out["error_code"]) == (3, "not_processed")


def test_cli_input_errors_exit_1(forge, tmp_path):
    forge.ok("init", "hero")
    forge.ok("plan", "hero", "--actions", "idle")
    junk = tmp_path / "junk.png"
    junk.write_text("not an image")
    for args, code_name in [
        (("import-raw", "hero", "idle", junk), "invalid_image"),
        (("import-raw", "hero", "idle", tmp_path / "missing.png"), "file_not_found"),
        (("import-raw", "hero", "walk", junk), "unknown_action"),
        (("reference", "import", "hero", junk), "invalid_image"),
        (("plan", "hero"), "invalid_params"),
        (("plan", "hero", "--actions", "idle", "--set", "idle.fps=0"), "invalid_params"),
        (("plan", "hero", "--actions", "idle", "--bundle", "npc"), "invalid_params"),
    ]:
        code, out = forge.run(*args)
        assert (code, out["error_code"]) == (1, code_name), args


def test_cli_reference_import_outputs(forge, tmp_path):
    forge.ok("init", "hero")
    ref = tmp_path / "knight.png"
    make_sheet("clean", rows=1, cols=1, cell_size=(300, 400)).save(ref)
    out = forge.ok("reference", "import", "hero", ref)
    assert out == {"reference": "reference/source.png", "bg_removed": True}
    rd = forge.root / "hero" / "reference"
    assert (rd / "source.png").read_bytes() == ref.read_bytes()
    char = np.array(Image.open(rd / "character.png"))
    assert char.shape[2] == 4 and char[0, 0, 3] == 0 and char[..., 3].max() == 255
    keyed = Image.open(rd / "character-keyed.png")
    assert keyed.mode == "RGB" and keyed.getpixel((0, 0)) == (255, 0, 255) and max(keyed.size) <= 1024
    m = json.loads((forge.root / "hero" / "manifest.json").read_text())
    assert m["reference"]["source"] == "reference/source.png" and len(m["reference"]["source_sha256"]) == 64
    code, out = forge.run("reference", "import", "hero", ref)
    assert (code, out["error_code"]) == (1, "reference_exists")


def test_cli_reference_import_downscales_keyed_and_keeps_native_alpha(forge, tmp_path):
    forge.ok("init", "hero")
    big = Image.new("RGBA", (2000, 1000), (0, 0, 0, 0))
    big.paste((200, 40, 30, 255), (800, 300, 1200, 800))
    ref = tmp_path / "big.webp"
    big.save(ref, lossless=True)
    out = forge.ok("reference", "import", "hero", ref)
    assert out["bg_removed"] is False and out["reference"] == "reference/source.webp"
    assert Image.open(forge.root / "hero/reference/character.png").size == (2000, 1000)
    assert Image.open(forge.root / "hero/reference/character-keyed.png").size == (1024, 512)


def test_cli_plan_output_and_manifest_assumptions(forge):
    forge.ok("init", "hero")
    out = forge.ok("plan", "hero", "--actions", "idle,fall", "--cell", "256x256", "--set", "fall.fps=9")
    assert out["estimated_seconds"] == 180
    plan = out["plan"]
    assert plan["actions"]["fall"] == {"method": "grid", "frames": 2, "grid": "1x2", "loop": True, "fps": 9, "anchor": "feet",
                                       "scale_strategy": "fit", "x_anchor": "mass", "components": "largest"}
    assert plan["cell"] == {"w": 256, "h": 256}
    on_disk = json.loads((forge.root / "hero/animation-plan.json").read_text())
    assert on_disk == plan
    m = json.loads((forge.root / "hero/manifest.json").read_text())
    assert m["assumptions"] == plan["assumptions"]


def test_cli_plan_uses_character_profile_for_key_color(forge):
    forge.ok("init", "hero")
    prof = {"schema_version": 1, "source": "manual", "edited_by_user": True,
            "identity": {"primary_colors": ["#E65AC8"], "secondary_colors": []}}
    (forge.root / "hero/character-profile.json").write_text(json.dumps(prof))
    assert forge.ok("plan", "hero", "--actions", "idle")["plan"]["key_color"] == "#00FF00"


def test_cli_plan_bundle_topdown_rpg_sets_view_and_directions(forge):
    forge.ok("init", "hero")
    out = forge.ok("plan", "hero", "--bundle", "topdown-rpg")
    plan = out["plan"]
    assert plan["view"] == "topdown" and plan["directions"] == ["down", "up", "right", "left"]
    assert out["estimated_seconds"] == 15 * 90


def test_cli_end_to_end_manual_path(forge, tmp_path):
    ref = tmp_path / "ref.png"
    make_sheet("clean", rows=1, cols=1, cell_size=(300, 300)).save(ref)
    raw = tmp_path / "raw.png"
    make_sheet("clean", rows=2, cols=3, cell_size=(256, 256)).save(raw)
    forge.ok("init", "hero")
    forge.ok("reference", "import", "hero", ref)
    forge.ok("plan", "hero", "--actions", "idle,walk", "--set", "idle.frames=6")
    assert forge.ok("import-raw", "hero", "walk", raw) == {"attempt": "001", "unit": "walk"}
    assert forge.ok("import-raw", "hero", "walk", raw)["attempt"] == "002"
    out = forge.ok("process", "hero", "walk", "--attempt", "001")
    assert out["attempt"] == "001" and out["qc"]["status"] in ("pass", "warn", "fail")
    assert isinstance(out["qc"]["failed"], list) and out["qc"]["recommendations"] == []
    cd = forge.root / "hero"
    a1 = cd / "walk/attempts/001"
    assert sorted(p.name for p in a1.iterdir() if not p.name.startswith(".")) == [
        "clean.png", "frames", "generation.json", "process.json", "qc-report.json", "raw.png", "sheet.png"]
    assert len(list((a1 / "frames").iterdir())) == 6
    gen = json.loads((a1 / "generation.json").read_text())
    assert gen["provider"] == "manual" and gen["raw"]["sha256"] and gen["codex_version"] is None
    assert (a1 / "raw.png").read_bytes() == raw.read_bytes()

    out = forge.ok("process", "hero", "walk")  # latest = 002
    assert out["attempt"] == "002"
    out = forge.ok("accept", "hero", "walk", "--attempt", "001")
    assert out == {"accepted": "001", "unit": "walk", "forced": False, "mirrored": []}
    for name in ("raw.png", "clean.png", "sheet.png", "process.json", "qc-report.json"):
        assert (cd / "walk" / name).read_bytes() == (a1 / name).read_bytes()
    assert sorted(p.name for p in (cd / "walk/frames").iterdir()) == [f"{i:03d}.png" for i in range(6)]
    assert json.loads((cd / "character-scale-profile.json").read_text())["reference_action"] == "walk"  # first body accept (M3-a)

    status = forge.ok("status", "hero")
    rows = {r["unit"]: r for r in status["units"]}
    assert rows["walk"]["state"] == "accepted" and rows["walk"]["accepted_attempt"] == "001"
    assert rows["walk"]["attempts"] == 2 and rows["walk"]["latest_attempt"] == "002"
    assert rows["idle"]["state"] == "pending"
    m = json.loads((cd / "manifest.json").read_text())
    walk = m["actions"]["walk"]
    assert walk["accepted_attempt"] == "001" and set(walk["attempts"]) == {"001", "002"}
    assert walk["attempts"]["001"]["qc_status"] in ("pass", "warn", "fail") and walk["attempts"]["001"]["provider"] == "manual"


def test_cli_process_set_override_and_invalid_set(forge, raw_sheet):
    forge.ok("init", "hero")
    forge.ok("plan", "hero", "--actions", "walk")
    forge.ok("import-raw", "hero", "walk", raw_sheet)
    forge.ok("process", "hero", "walk", "--set", "anchor=bottom", "--set", "components=all")
    pj = json.loads((forge.root / "hero/walk/attempts/001/process.json").read_text())
    assert pj["params"]["anchor"] == "bottom" and pj["params"]["components"]["mode"] == "all"
    for bad in ("anchor=top", "nonsense=1", "fps"):
        code, out = forge.run("process", "hero", "walk", "--set", bad)
        assert (code, out["error_code"]) == (1, "invalid_override"), bad


def test_cli_process_align_set_defaults_to_register_and_accepts_per_frame(forge, raw_sheet):
    forge.ok("init", "hero")
    forge.ok("plan", "hero", "--actions", "walk,jump")
    forge.ok("import-raw", "hero", "walk", raw_sheet)
    forge.ok("process", "hero", "walk")
    pj = lambda n: json.loads((forge.root / f"hero/walk/attempts/{n}/process.json").read_text())["params"]  # noqa: E731
    assert pj("001")["align"] == "register" and pj("001")["align_vertical"] == "normalize"
    forge.ok("process", "hero", "walk", "--set", "align=per_frame")
    assert pj("001")["align"] == "per_frame"
    code, out = forge.run("process", "hero", "walk", "--set", "align=nope")
    assert (code, out["error_code"]) == (1, "invalid_override")
    forge.ok("import-raw", "hero", "jump", raw_sheet)
    forge.ok("process", "hero", "jump")
    jump = json.loads((forge.root / "hero/jump/attempts/001/process.json").read_text())["params"]
    assert jump["align"] == "register" and jump["align_vertical"] == "preserve"  # airborne keeps its vertical travel


def test_cli_process_is_deterministic(forge, raw_sheet):
    forge.ok("init", "hero")
    forge.ok("plan", "hero", "--actions", "walk")
    forge.ok("import-raw", "hero", "walk", raw_sheet)
    forge.ok("process", "hero", "walk")
    d = forge.root / "hero/walk/attempts/001"
    skip = ("generation.json", ".lock")  # .lock holds the owner PID of the last process run (docs/10 6)
    first = {p.name: p.read_bytes() for p in d.glob("*.*") if p.name not in skip}
    forge.ok("process", "hero", "walk")
    assert first == {p.name: p.read_bytes() for p in d.glob("*.*") if p.name not in skip}


def test_cli_accept_failing_qc_marks_forced(forge, tmp_path):
    raw = tmp_path / "empty.png"
    make_sheet("empty_cell", rows=2, cols=3, cell_size=(256, 256)).save(raw)
    forge.ok("init", "hero")
    forge.ok("plan", "hero", "--actions", "walk")
    forge.ok("import-raw", "hero", "walk", raw)
    out = forge.ok("process", "hero", "walk")
    assert out["qc"]["status"] == "fail" and "QC-05" in out["qc"]["failed"]
    assert forge.ok("accept", "hero", "walk")["forced"] is True
    m = json.loads((forge.root / "hero/manifest.json").read_text())
    assert m["actions"]["walk"]["forced"] is True
    assert forge.ok("status", "hero")["units"][0]["qc_status"] == "fail"


def test_cli_import_raw_converts_non_png(forge, tmp_path):
    jpg = tmp_path / "raw.jpg"
    make_sheet("clean", rows=2, cols=3, cell_size=(256, 256)).image.save(jpg, quality=95)
    forge.ok("init", "hero")
    forge.ok("plan", "hero", "--actions", "walk")
    forge.ok("import-raw", "hero", "walk", jpg)
    assert Image.open(forge.root / "hero/walk/attempts/001/raw.png").format == "PNG"


def test_cli_status_without_plan(forge):
    forge.ok("init", "hero")
    out = forge.ok("status", "hero")
    assert out == {"character": "hero", "has_reference": False, "has_plan": False, "units": []}
