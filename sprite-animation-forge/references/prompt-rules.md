# Prompt rules (what the generator does; you never hand-write prompts)

`forge.py prompt <cid> <action> [--direction d] [--extra T] [--recovery CODE]` prints the exact prompt
(not saved); `generate` builds the same text, saves it as `attempts/NNN/prompt.txt` and records the
template version (`action_prompt@N`) in `generation.json`. Same input gives byte-identical output.

## Block order
```
HEADER -> REFERENCE IDENTITY -> ART STYLE -> CAMERA -> [DIRECTION REFERENCE] -> ACTION (+ FRAME SEQUENCE)
  -> [ADDITIONAL DIRECTION] -> [RECOVERY] -> CONSISTENCY RULES -> GRID RULES -> BACKGROUND RULE -> FOOTER
```
Hard rules (consistency, grid, background) come last so extra text cannot override them. Empty profile
fields and blocks are omitted. Prompts are English; Korean `--extra` text goes in verbatim (do not translate).

## What each block enforces
- REFERENCE IDENTITY: silhouette, proportions, hair/face, clothing, colors, weapon, accessories, outline and
  shading from `character-profile.json`; only pose, limb position, body lean, expression, weapon motion and
  secondary motion may change.
- CAMERA: view-specific text. For multi-direction plans the unit's direction text is used
  (`down` front visible, `up` back only, `right` right profile, `left` left profile when `mirror` is off).
  Non-representative units attach the representative direction's sheet as `Image 2` (DIRECTION REFERENCE).
- ACTION: pose list from the motion library, "Animate in place", loop or one-shot line.
- GRID RULES: `R rows x C columns`, one character per cell, >= 8% empty margin (15% with `edge_touch`),
  no lines or labels, unused cells empty.
- BACKGROUND RULE: flat solid key color (`#FF00FF` magenta; `#00FF00` green if the palette conflicts), no
  gradient, floor or shadow, key hue never on the character.
- FOOTER: `No text. No watermark. No UI.`

## `--extra`
Free text for ADDITIONAL DIRECTION, max 500 characters (e.g. `--extra "oversized greatsword"`). Use it only
for user-requested style or motion details.

## Recovery codes (`--recovery`, repeatable)
| Code | Cause | Added text / effect |
|---|---|---|
| `edge_touch` | QC-01 | wide empty margin (margin_pct 8 -> 15) |
| `scale_drift` | QC-02 | same character size in every cell |
| `character_small` | QC-07 | keep body size as in the reference; action goes to `preserve` |
| `fx_in_body` | QC-01/02 with FX | body and weapon only, no trails/sparks/effects |
| `empty_frame` | QC-05 | every used cell must contain the character |
| `duplicate_frames` | QC-06 | each frame a clearly different pose |
| `bg_mismatch` | QC-09 | one flat key-colored background everywhere |
| `identity_drift` | manual | match the reference exactly |

Motion library (default frame counts): idle breathing; walk contact/down/passing x2 sides; run with 10-15
degree forward lean, contact/push-off/flight; attack ready/anticipation/swing/impact/follow-through/recovery
(feet planted); shoot aim/fire/recoil/settle; cast gather/raise/channel/release; jump crouch/take-off/rising/apex;
fall 2 flutter poses; hurt flinch/recoil/recover/guard; death hit/stagger/buckle/fall/ground/bounce/settle/still.
Custom frame counts get generic "N evenly spaced poses" wording.
