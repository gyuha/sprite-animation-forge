"""A single still (method=breathe) generated through the server attaches the layout guide; the generate route does not mistake
the guide for a direction reference."""

from .api_sync_helpers import char_url
from .jobs_helpers import post_generate, ready_character, wait_job


def test_sg_image_guide_api_prompt_preview_lists_the_guide_and_generate_runs(jc, root):
    ready_character(jc, root, "hero", actions=("idle",), sets=["idle.method=breathe"])
    preview = jc.post(char_url("hero", "/actions/idle/prompt"), json={}).json()
    assert preview["references_needed"] == ["character", "layout_guide"] and "LAYOUT GUIDE" in preview["prompt"]
    job = wait_job(jc, post_generate(jc, action="idle")["job"]["id"])
    assert job["state"] == "succeeded", job
    adir = root / "hero/idle/attempts/001"
    assert sorted(p.name for p in adir.glob("ref-*.png")) == ["ref-01.png", "ref-02.png"]


def test_sg_image_guide_api_a_grid_action_still_needs_one_reference(jc, root):
    ready_character(jc, root, "hero", actions=("idle",))
    preview = jc.post(char_url("hero", "/actions/idle/prompt"), json={}).json()
    assert preview["references_needed"] == ["character"] and "LAYOUT GUIDE" not in preview["prompt"]
