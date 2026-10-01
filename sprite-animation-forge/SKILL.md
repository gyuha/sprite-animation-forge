---
name: sprite-animation-forge
description: >
  Create game-ready 2D character sprite animations (idle, walk, run, attack, jump, hurt, death...)
  from a character image or a text description. Generates each action separately with the Codex
  image_gen tool, removes the chroma background, aligns feet, normalizes scale, runs automated QC,
  and exports PNG frames, sprite sheets, GIF previews and a Phaser atlas + animations.json.
  Use when the user asks for 2D game character sprite animations, sprite sheets or a Phaser atlas
  from a reference image or a description.
  Triggers: "sprite sheet", "sprite animation", "game character animation", "Phaser atlas",
  "스프라이트", "캐릭터 애니메이션", "게임용 애니메이션", "idle/walk/run 만들어줘".
---

# sprite-animation-forge

Philosophy: the image model draws; deterministic scripts split, align, verify and package.
Never draw or edit sprite pixels yourself (no PIL drawing, no SVG). Use `scripts/forge.py` only.
`scripts/forge.py` is relative to THIS skill's directory. Run it from the user's project directory
so outputs go to `./sprites/` there (`--root <dir>` or `$SPRITE_FORGE_ROOT` to change it).
Every command prints exactly one JSON object on stdout. Exit codes: 0 ok (QC failure is still 0; read
`qc.status`), 1 bad arguments, 2 image provider error (`error_code`), 3 missing prerequisite.

## Workflow
1. `python scripts/forge.py doctor` — stop and tell the user what to fix if `ready` is false
   (error codes: references/codex-image.md).
2. `init <cid> [--view ...] [--art-style ...] [--asset-type ...]`. Case A (image given):
   `reference import <cid> <file>`. Case B (text only): `reference generate <cid> --description "..."`
   then `reference select <cid> <NNN>`. Ask a question ONLY if there is neither an image nor a description.
3. `identity analyze <cid>`.
4. Infer actions/view/style/directions (references/animation-rules.md; do not ask what can be inferred)
   and run `plan <cid> --actions a,b,c` or `--bundle <name>`. Print the plan, the assumptions and the
   estimated time (`estimated_seconds`), then continue without waiting. Make idle first if the plan
   lacks it and a scale reference is needed; export only what the user asked for.
5. For each unit in plan order (idle first; for multi-direction plans `down`, `right`, `up` per action,
   add `--direction <d>` to every command; `left` is derived from `right` and must not be generated):
   `generate` → `process` → read `qc.status`.
   - pass/warn → `accept`.
   - fail → apply the FIRST item of `qc.recommendations`:
     `reprocess` → `process --set <key>=<value>` (from its `set`), max 2 per action;
     `regenerate` → `generate --recovery <code>` then `process`, max 2 per action;
     `force_accept` (budget exhausted, the CLI counts it for you) → `accept --attempt <its attempt>` and
     record the failure in your report.
6. `export <cid> --engine phaser`.
7. Report: output paths (`atlas/`, `animations.json`, `preview/`), per-action QC status
   (`status <cid>`), assumptions, forced accepts and failures, and how to use the files
   (references/phaser-export.md).

## Rules
- One action per generation. Never request a mixed-action sheet.
- Never overwrite raw.png. Every generation is a new attempt; `generate` is slow (about 90 s) and runs
  one at a time.
- If running inside Codex and you call image_gen yourself, register the image with `import-raw`.
- Do not edit prompts by hand: use `--extra "<text>"` (max 500 chars) and `--recovery <code>` only.
- Details: references/animation-rules.md, references/prompt-rules.md, references/character-consistency.md,
  references/qc-rules.md, references/codex-image.md, references/phaser-export.md, references/examples.md.
