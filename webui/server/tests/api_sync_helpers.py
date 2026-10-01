"""Shared helpers for the synchronous-API tests (synthetic sheets via the skill's fixtures package)."""

import io

from fixtures.synthetic.make import make_sheet
from PIL import Image


def sheet_png(variant="clean", rows=2, cols=3) -> bytes:
    return make_sheet(variant, rows=rows, cols=cols, cell_size=(256, 256)).png_bytes()


def image_bytes(fmt: str, size=(64, 64)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (200, 30, 30)).save(buf, format=fmt)
    return buf.getvalue()


def png_file(data: bytes, name="x.png"):
    return {"file": (name, data, "application/octet-stream")}


def char_url(cid="hero", tail=""):
    return f"/api/characters/{cid}{tail}"


def make_character(client, cid="hero", **settings):
    r = client.post("/api/characters", json={"id": cid, **settings})
    assert r.status_code == 201, r.text
    return cid


def make_plan(client, cid="hero", **body):
    body.setdefault("actions", ["walk"])
    r = client.post(char_url(cid, "/plan"), json=body)
    assert r.status_code == 200, r.text
    return r.json()


def upload_raw(client, action="walk", cid="hero", data=None, **params):
    return client.post(char_url(cid, f"/actions/{action}/upload"), params=params,
                       files=png_file(data if data is not None else sheet_png()))


def err(resp, status, code):
    assert resp.status_code == status, resp.text
    body = resp.json()["error"]
    assert body["code"] == code, body
    return body
