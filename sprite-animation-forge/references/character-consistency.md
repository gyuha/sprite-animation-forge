# Character consistency

## Identity Lock
`identity analyze <cid>` asks Codex to describe the reference (read-only vision call, no image generation)
and writes `character-profile.json`: silhouette, body_ratio, head_ratio, hair, face, eyes, clothing,
primary/secondary colors (hex), weapon, accessories, outline_style, shading_style, camera_angle,
orientation. Every action prompt embeds it as REFERENCE IDENTITY and attaches
`reference/character-keyed.png` as `Image 1`.

- Allowed to change per frame: pose, limb position, body lean, facial expression, weapon motion,
  secondary motion (hair, cloth).
- Never allowed: redesign, adding or removing parts, color/outfit changes, art style drift.
- Fix a wrong profile by editing `character-profile.json` (sets `edited_by_user`); `identity analyze` then
  refuses to overwrite it without `--force`. `--empty` writes an all-unknown profile without calling Codex.
- If a generated action drifts from the reference, regenerate with `--recovery identity_drift` (or add
  `--extra` naming the drifting parts). Do not patch pixels.

## Directions (topdown)
- Reference and identity are for the representative `facing` (topdown: `down`). If the user's image shows
  a back or side, give `plan --facing` to match; do not guess from the picture.
- Order per action: `down`, then `right`, then `up`; the first accepted `idle/down` defines the scale
  profile. Later directions attach the accepted representative unit's raw sheet as `Image 2`; generating
  a non-representative direction before the representative one is accepted fails with
  `no_direction_reference` (exit 3).
- `left` is the exact horizontal flip of `right` (written on `accept` of `right`, `left/mirror.json` records
  the source). Do not call generate/process/accept for it (`mirrored_direction` error).
- The flip turns a right-handed weapon into a left-handed one. If the identity profile mentions one-sided
  weapon, shoulder armor or asymmetric clothing (plan `assumptions` carries a warning), tell the user and
  prefer `plan --no-mirror` so `left` is generated normally.

## Scale
One `character-scale-profile.json` per character (from the first accepted body action). QC-02 and QC-07 of
all later actions and directions compare against its `body_height`; `preserve` uses its `norm_scale`.
