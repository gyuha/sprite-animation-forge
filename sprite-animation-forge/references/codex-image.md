# Codex image generation

`generate`, `reference generate` and `identity analyze` call the Codex CLI (`codex exec`, ChatGPT login, no
API key). Run `forge.py doctor` first; it always exits 0 and prints
`{codex: {installed, version, tested_version, version_ok, logged_in, auth, image_generation, codex_home},
python: {...}, warnings: [...], ready}`. If `ready` is false, stop and relay the `warnings` fix.

| error_code | Meaning | What to do |
|---|---|---|
| `codex_not_installed` | no `codex` executable | `npm install -g @openai/codex`, retry |
| `codex_not_logged_in` | not logged in | user runs `codex login`, retry |
| `image_generation_disabled` | feature flag off | enable `image_generation` in Codex, retry |
| `timeout` | exceeded `--timeout` (default 300 s) | retry, optionally with a larger `--timeout` |
| `codex_failed` | exit code != 0 (stderr in `codex-stderr.txt`) | read the message, retry; usage-limit errors land here |
| `image_gen_failed` | refused/failed (policy etc.) | change `--extra` wording, retry |
| `no_image` | exit 0 but no PNG found | retry |
| `invalid_image` | output is not a decodable image | retry |

Provider errors exit 2 with JSON containing `error_code`, `attempt` and `status`; the failed attempt is kept
(`generation.json`) and does not block the next one. Retry a failed generation at most twice, then tell the
user instead of looping. Calls are slow (about 80-90 s each) and consume the user's ChatGPT plan usage; run
them strictly one after another.

Other CLI errors: `no_reference`, `no_plan`, `no_profile` (run `identity analyze`), `direction_required`,
`mirrored_direction`, `no_direction_reference`, `no_attempt`, `not_processed`, `invalid_override`.

## Running inside Codex (import-raw)
If you are the Codex agent and generate an image yourself with the built-in image_gen tool, do not copy it
into the tree by hand. Register it: `python scripts/forge.py import-raw <cid> <action> <file>
[--direction d]` creates a new attempt (`provider: manual`), then `process` and `accept` as usual. The same
command registers sheets produced elsewhere. The sheet must follow the prompt's grid (R x C cells, flat
key-color background, one pose per cell); use `forge.py prompt` to get the exact text.
