# Animation rules: inference, presets, bundles

User-given values always win. Record every inferred value in the plan `assumptions` and your report.
`forge.py plan` applies the presets below; override with `--set <action>.<key>=<value>`
(keys: frames, grid, loop, fps, anchor, x_anchor, scale_strategy, components, directions, ...).

## Parameter inference
| Parameter | Default | Rule |
|---|---|---|
| asset_type (`init --asset-type`) | character | player/hero -> `player`; enemy/monster/boss -> `enemy`; npc/merchant/villager -> `npc`; non-humanoid -> `creature` |
| view (`init --view`, `plan --view`) | side | side-scroller/platformer -> `side`; top-down/field RPG -> `topdown`; isometric/3/4 -> `3/4`; front -> `front`; rear -> `rear` |
| facing | by view | side `right`, topdown `down`, 3/4 `down-right`, front `camera`, rear `away` (representative direction; if the supplied image shows a back/side, pass `--facing` accordingly) |
| directions | by view | side `[right]`; topdown `[down, up, right, left]`; others `[facing]` |
| mirror | topdown: `{left: right}` | `plan --no-mirror` generates `left` with Codex instead (use when the weapon/clothing is asymmetric) |
| frames | preset | "N frames" -> N, range 2-16 (`--set walk.frames=8`) |
| art_style (`init --art-style`) | auto | reference given -> `project_native`; "pixel" -> `pixel_art`; "16-bit"/retro/SNES -> `retro_pixel`; otherwise `clean_hd` |
| cell (`plan --cell`) | 128x128 | "HD"/high-res -> `256x256` (atlas limit is 4096 px; many rows may fail with `atlas_too_large`) |
| engine | phaser | generic JSON is always written; godot/unity are out of scope (generate generic only and say so) |

## Action presets
| Action | Frames | Grid | Loop | FPS | anchor | scale_strategy | x_anchor |
|---|---:|---|---|---:|---|---|---|
| idle | 4 | 2x2 | yes | 6 | feet | fit | mass |
| walk | 6 | 2x3 | yes | 10 | feet | fit | mass |
| run | 6 | 2x3 | yes | 12 | feet | fit | mass |
| attack | 6 | 2x3 | no | 12 | feet | preserve | feet |
| shoot | 4 | 2x2 | no | 12 | feet | preserve | feet |
| cast | 6 | 2x3 | no | 10 | feet | preserve | feet |
| jump | 4 | 2x2 | no | 10 | feet | fit | mass |
| fall | 2 | 1x2 | yes | 8 | feet | fit | mass |
| hurt | 4 | 2x2 | no | 10 | feet | fit | mass |
| death | 8 | 2x4 | no | 8 | bottom | preserve | feet |

Grid for custom frame counts: 2 -> 1x2, 3 -> 1x3, 4 -> 2x2, 5-6 -> 2x3, 7-8 -> 2x4, 9 -> 3x3,
10-12 -> 3x4, 13-16 -> 4x4 (reading order left-to-right, top-to-bottom; unused cells stay empty; no 1xN rows
for N >= 4). Long weapons, big capes or wide poses in the description: put that action on `preserve`.

## Bundles (`plan --bundle <name>`)
| Bundle | Trigger | Actions |
|---|---|---|
| side-action | "for a side-scrolling action game" | idle, walk, run, jump, fall, attack, hurt, death |
| side-basic | "basic animations", "game animations" | idle, walk, run, attack |
| topdown-rpg | "top-down RPG" (view topdown, 4 directions) | idle, walk, attack, hurt, death |
| npc | "NPC", "merchant" | idle, walk |

`--actions` and `--bundle` are mutually exclusive. Time estimate: 90 s per Codex call; a topdown action is
3 calls (down, up, right; `left` is a free flip). Reduce cost with `--set death.directions=down`.

## Order and the scale reference
The first accepted body action becomes the Character Scale Profile (`character-scale-profile.json`), so
generate idle first (for multi-direction plans the representative direction, e.g. `idle/down`, first).
All directions share one profile.
