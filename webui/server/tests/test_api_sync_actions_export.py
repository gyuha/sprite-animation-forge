"""Synchronous API: prompt, upload, attempts, process, accept, save-params, export, export.zip."""

import io
import json
import zipfile

import pytest

from .api_sync_helpers import char_url, err, image_bytes, make_character, make_plan, png_file, sheet_png, upload_raw

ACT = "/actions/walk"


@pytest.fixture
def hero(client):
    make_character(client)
    make_plan(client)
    return "hero"


@pytest.fixture
def uploaded(client, hero):
    r = upload_raw(client)
    assert r.status_code == 200, r.text
    return r.json()


def test_api_sync_prompt_preview(client, hero):
    r = client.post(char_url(hero, ACT + "/prompt"), json={"extra": "swing wider", "recovery": ["edge_touch"]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "swing wider" in body["prompt"] and body["references_needed"] == ["character"]
    assert isinstance(body["warnings"], list)
    assert client.post(char_url(hero, ACT + "/prompt")).status_code == 200  # body optional


def test_api_sync_prompt_errors(client, hero):
    err(client.post(char_url(hero, "/actions/nope/prompt")), 404, "not_found")
    err(client.post(char_url(hero, ACT + "/prompt"), json={"recovery": ["bogus"]}), 400, "invalid_param")
    err(client.post(char_url(hero, ACT + "/prompt"), json={"extra": "x" * 501}), 400, "invalid_param")
    err(client.post(char_url("ghost", ACT + "/prompt")), 404, "not_found")
    make_character(client, "bare")
    err(client.post(char_url("bare", ACT + "/prompt")), 412, "precondition_failed")


def test_api_sync_upload_creates_attempt_with_qc(client, hero, uploaded, root):
    assert uploaded["attempt"] == "001" and uploaded["unit"] == "walk"
    assert uploaded["qc"]["status"] in ("pass", "warn", "fail") and "recommendations" in uploaded["qc"]
    files = uploaded["files"]
    assert len(files["frames"]) == 6 and files["sheet"].startswith("/files/hero/walk/attempts/001/sheet.png?v=")
    assert client.get(files["raw"]).status_code == 200 and client.get(files["frames"][0]).status_code == 200
    assert "row_boundaries" in uploaded["derived"] and (root / "hero/walk/attempts/001/qc-report.json").exists()
    assert upload_raw(client).json()["attempt"] == "002"


def test_api_sync_upload_errors(client, hero):
    err(upload_raw(client, data=b"garbage"), 400, "invalid_image")
    err(upload_raw(client, data=image_bytes("GIF")), 400, "invalid_image")
    err(upload_raw(client, data=b"\x89PNG" + b"0" * (20 * 1024 * 1024)), 413, "file_too_large")
    err(upload_raw(client, action="nope"), 404, "not_found")
    err(upload_raw(client, cid="ghost"), 404, "not_found")
    assert client.get(char_url(hero, ACT + "/attempts")).json()["attempts"] == []


def test_api_sync_upload_unprocessable_sheet_keeps_attempt(client, hero):
    r = upload_raw(client, data=image_bytes("PNG", (8, 8)))
    assert r.status_code >= 400 and r.json()["error"]["detail"]["attempt"] == "001"
    assert [a["attempt"] for a in client.get(char_url(hero, ACT + "/attempts")).json()["attempts"]] == ["001"]


def test_api_sync_attempts_list_and_detail(client, hero, uploaded):
    upload_raw(client)
    lst = client.get(char_url(hero, ACT + "/attempts")).json()
    assert lst["unit"] == "walk" and lst["accepted_attempt"] is None and lst["mirror_of"] is None
    assert [a["attempt"] for a in lst["attempts"]] == ["001", "002"]
    first = lst["attempts"][0]
    assert first["provider"] == "manual" and first["qc_status"] == uploaded["qc"]["status"] and not first["accepted"]
    d = client.get(char_url(hero, ACT + "/attempts/001")).json()
    assert d["generation"]["provider"] == "manual" and d["process"]["derived"] and d["qc"]["status"] == first["qc_status"]
    assert d["files"]["clean"] and d["summary"]["attempt"] == "001"


def test_api_sync_attempt_not_found(client, hero, uploaded):
    err(client.get(char_url(hero, ACT + "/attempts/009")), 404, "not_found")
    err(client.get(char_url(hero, ACT + "/attempts/abc")), 404, "not_found")
    err(client.get(char_url(hero, "/actions/nope/attempts")), 404, "not_found")
    err(client.get(char_url("ghost", ACT + "/attempts")), 404, "not_found")
    err(client.post(char_url(hero, ACT + "/attempts/009/process")), 404, "not_found")
    err(client.post(char_url(hero, ACT + "/attempts/009/accept")), 404, "not_found")


def test_api_sync_process_reprocess_updates_files_and_qc(client, hero, uploaded):
    r = client.post(char_url(hero, ACT + "/attempts/001/process"), json={"set": {"anchor": "bottom", "margin_top": 30, "t_in": 34, "despill": False}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["attempt"] == "001" and body["qc"]["results"] and len(body["files"]["frames"]) == 6
    assert body["files"]["sheet"] != uploaded["files"]["sheet"]  # new content hash
    assert body["derived"]["frames"]
    detail = client.get(char_url(hero, ACT + "/attempts/001")).json()
    assert detail["process"]["params"]["anchor"] == "bottom" and detail["process"]["params"]["background"]["t_in"] == 34
    assert client.post(char_url(hero, ACT + "/attempts/001/process")).status_code == 200  # no body -> plan defaults


def test_api_sync_process_invalid_params(client, hero, uploaded):
    for bad in ({"anchor": "top"}, {"t_in": "abc"}, {"bogus": 1}):
        err(client.post(char_url(hero, ACT + "/attempts/001/process"), json={"set": bad}), 400, "invalid_param")
    assert client.post(char_url(hero, ACT + "/attempts/001/process"), json={"set": {"anchor": [1]}}).status_code == 422


def test_api_sync_accept_idle_writes_scale_profile(client, root):
    make_character(client)
    make_plan(client, actions=["idle", "walk"])
    assert client.post(char_url("hero", "/actions/idle/upload"), files=png_file(sheet_png(rows=2, cols=2))).status_code == 200
    r = client.post(char_url("hero", "/actions/idle/attempts/001/accept"), json={"force": True})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["accepted"] == "001" and out["derived"] == [] and out["scale_profile_updated"] is True
    assert out["requalified_actions"] == []
    assert (root / "hero/character-scale-profile.json").exists() and (root / "hero/idle/frames/000.png").exists()
    lst = client.get(char_url("hero", "/actions/idle/attempts")).json()
    assert lst["accepted_attempt"] == "001" and lst["attempts"][0]["accepted"] is True
    again = client.post(char_url("hero", "/actions/idle/attempts/001/accept"), json={"force": True}).json()
    assert again["scale_profile_updated"] is False  # same content


def test_api_sync_accept_without_body_and_manifest(client, hero, uploaded, root):
    r = client.post(char_url(hero, ACT + "/attempts/001/accept"))
    assert r.status_code == 200, r.text
    assert json.loads((root / "hero/manifest.json").read_text())["actions"]["walk"]["accepted_attempt"] == "001"


def test_api_sync_accept_qc_fail_needs_force(client, hero):
    r = upload_raw(client, data=sheet_png("scale_drift_12"))
    assert r.json()["qc"]["status"] == "fail"
    body = err(client.post(char_url(hero, ACT + "/attempts/001/accept"), json={"force": False}), 409, "qc_failed")
    assert body["detail"]["attempt"] == "001"
    out = client.post(char_url(hero, ACT + "/attempts/001/accept"), json={"force": True}).json()
    assert out["forced"] is True


def test_api_sync_save_params_persists_in_plan(client, hero, root):
    r = client.post(char_url(hero, ACT + "/save-params"), json={"set": {"anchor": "bottom", "scale_strategy": "preserve"}})
    assert r.status_code == 200, r.text
    assert r.json()["settings"]["anchor"] == "bottom"
    saved = json.loads((root / "hero/animation-plan.json").read_text())["actions"]["walk"]
    assert saved["anchor"] == "bottom" and saved["scale_strategy"] == "preserve"
    assert client.get(char_url(hero, "/plan")).json()["plan"]["actions"]["walk"]["anchor"] == "bottom"
    upload_raw(client)  # the next process uses the saved default
    detail = client.get(char_url(hero, ACT + "/attempts/001")).json()
    assert detail["process"]["params"]["anchor"] == "bottom"


def test_api_sync_save_params_errors(client, hero):
    body = err(client.post(char_url(hero, ACT + "/save-params"), json={"set": {"t_in": "30"}}), 400, "invalid_param")
    assert "t_in" in body["message"]
    err(client.post(char_url(hero, ACT + "/save-params"), json={"set": {"anchor": "top"}}), 422, "validation_error")
    err(client.post(char_url(hero, "/actions/nope/save-params"), json={"set": {"anchor": "feet"}}), 404, "not_found")
    assert client.post(char_url(hero, ACT + "/save-params"), json={}).status_code == 422


def test_api_sync_export_and_zip(client, hero, uploaded, root):
    err(client.post(char_url(hero, "/export")), 412, "precondition_failed")
    err(client.get(char_url(hero, "/export.zip")), 412, "precondition_failed")
    assert client.post(char_url(hero, ACT + "/attempts/001/accept"), json={"force": True}).status_code == 200
    r = client.post(char_url(hero, "/export"))
    assert r.status_code == 200, r.text
    assert "atlas/hero.png" in r.json()["files"] and r.json()["warnings"] == []
    z = client.get(char_url(hero, "/export.zip"))
    assert z.status_code == 200 and z.headers["content-type"] == "application/zip"
    assert z.headers["content-disposition"] == 'attachment; filename="hero.zip"'
    names = set(zipfile.ZipFile(io.BytesIO(z.content)).namelist())
    assert {"atlas/hero.png", "atlas/hero.json", "atlas/hero.meta.json", "animations.json", "preview/walk.gif"} <= names
    assert not any(n.startswith(("walk/", "attempts")) or n in ("manifest.json",) for n in names)
    err(client.get(char_url("ghost", "/export.zip")), 404, "not_found")
    err(client.post(char_url("ghost", "/export")), 404, "not_found")


def test_api_sync_export_warns_missing_actions(client):
    make_character(client)
    make_plan(client, actions=["idle", "walk"])
    client.post(char_url("hero", "/actions/idle/upload"), files=png_file(sheet_png(rows=2, cols=2)))
    client.post(char_url("hero", "/actions/idle/attempts/001/accept"), json={"force": True})
    r = client.post(char_url("hero", "/export"))
    assert r.status_code == 200 and r.json()["warnings"] == ['missing_actions: ["walk"]']
