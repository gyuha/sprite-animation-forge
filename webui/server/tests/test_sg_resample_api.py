"""Reprocess `set` accepts the scale edge mode (docs/14 area B): the default is recorded, legacy is selectable."""

import pytest

from .api_sync_helpers import char_url, err, make_character, make_plan, upload_raw

ACT = "/actions/walk"


@pytest.fixture
def uploaded(client):
    make_character(client)
    make_plan(client)
    r = upload_raw(client)
    assert r.status_code == 200, r.text
    return r.json()


def process(client, **set_):
    return client.post(char_url("hero", ACT + "/attempts/001/process"), json={"set": set_})


def mode_of(client):
    return client.get(char_url("hero", ACT + "/attempts/001")).json()["process"]["params"]["resample_mode"]


def test_sg_resample_api_the_default_mode_is_recorded_and_legacy_can_be_chosen(client, uploaded):
    assert mode_of(client) == "coverage"
    first = client.get(char_url("hero", ACT + "/attempts/001")).json()["files"]["sheet"]
    assert process(client, resample_mode="legacy").status_code == 200
    assert mode_of(client) == "legacy"
    assert client.get(char_url("hero", ACT + "/attempts/001")).json()["files"]["sheet"] != first  # different edge pixels
    assert process(client).status_code == 200 and mode_of(client) == "coverage"  # no set -> back to the default


def test_sg_resample_api_an_unknown_mode_is_an_invalid_param(client, uploaded):
    err(process(client, resample_mode="sharp"), 400, "invalid_param")
