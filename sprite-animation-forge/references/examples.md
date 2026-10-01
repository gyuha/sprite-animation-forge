# Examples

Four typical requests, the commands to run, and the plan `forge.py plan` produced (verified against the
implemented CLI; `plan` stdout is `{"plan": {...}, "estimated_seconds": N}`). Fields shared by all plans:
`schema_version 1`, `cell 128x128`, `margin {top 8, side 8, bottom 10}`, `key_color #FF00FF`, `engine phaser`,
`facing`/`directions`/`mirror` by view. After `plan`, print plan + assumptions + time and continue.

## 1. "Make idle, walk, run and attack for this character" (image attached, side scroller)
```bash
python scripts/forge.py doctor
python scripts/forge.py init hero --view side --asset-type player --art-style project_native
python scripts/forge.py reference import hero ./knight.png
python scripts/forge.py identity analyze hero
python scripts/forge.py plan hero --actions idle,walk,run,attack      # estimated_seconds: 360
# per action: generate -> process -> accept   (idle first)
python scripts/forge.py generate hero idle && python scripts/forge.py process hero idle && python scripts/forge.py accept hero idle
python scripts/forge.py export hero --engine phaser
```
Plan (abridged): `asset_type player`, `view side`, `facing right`, `directions [right]`, `mirror {}`,
`art_style project_native`, `order [idle, walk, run, attack]`, `assumptions ["view=side"]`, actions:
```json
{ "idle":   { "frames": 4, "grid": "2x2", "loop": true,  "fps": 6,  "anchor": "feet", "scale_strategy": "fit",      "x_anchor": "mass", "components": "largest" },
  "walk":   { "frames": 6, "grid": "2x3", "loop": true,  "fps": 10, "anchor": "feet", "scale_strategy": "fit",      "x_anchor": "mass", "components": "largest" },
  "run":    { "frames": 6, "grid": "2x3", "loop": true,  "fps": 12, "anchor": "feet", "scale_strategy": "fit",      "x_anchor": "mass", "components": "largest" },
  "attack": { "frames": 6, "grid": "2x3", "loop": false, "fps": 12, "anchor": "feet", "scale_strategy": "preserve", "x_anchor": "feet", "components": "largest" } }
```
Result: `atlas/hero.png|json`, `animations.json` with keys `idle, walk, run, attack`, `preview/*.gif`.

## 2. "Animations for a side-scrolling action game" (image attached, no action list)
No action list but a purpose: use the `side-action` bundle.
```bash
python scripts/forge.py init knight --view side --art-style project_native
python scripts/forge.py plan knight --bundle side-action              # estimated_seconds: 720
```
Plan: `order [idle, walk, run, jump, fall, attack, hurt, death]`, `directions [right]`, `assumptions ["view=side"]`.
Per action (frames, grid, fps, loop, anchor, scale_strategy): idle 4/2x2/6/loop/feet/fit; walk 6/2x3/10/loop/feet/fit;
run 6/2x3/12/loop/feet/fit; jump 4/2x2/10/once/feet/fit; fall 2/1x2/8/loop/feet/fit;
attack 6/2x3/12/once/feet/preserve; hurt 4/2x2/10/once/feet/fit; death 8/2x4/8/once/bottom/preserve.
Eight sequential generations: tell the user the 12-minute estimate up front.

## 3. "Top-down RPG character, all four directions, only the death animation facing down"
```bash
python scripts/forge.py init rpg --view topdown --art-style project_native
python scripts/forge.py identity analyze rpg        # after reference import
python scripts/forge.py plan rpg --bundle topdown-rpg --set death.directions=down   # estimated_seconds: 1170
# multi-direction plan: --direction on every command; generate down, right, up (never left)
python scripts/forge.py generate rpg idle --direction down
python scripts/forge.py process rpg idle --direction down
python scripts/forge.py accept rpg idle --direction down
python scripts/forge.py generate rpg idle --direction right     # accept right -> left is derived (flip)
python scripts/forge.py generate rpg idle --direction up
```
Plan: `view topdown`, `facing down`, `directions [down, up, right, left]`, `mirror {"left": "right"}`,
`order [idle, walk, attack, hurt, death]`, `assumptions ["view=topdown"]`; idle 4/2x2, walk 6/2x3,
attack 6/2x3 (preserve), hurt 4/2x2, death 8/2x4 (anchor bottom, preserve) with `"directions": ["down"]`.
Calls: 4 actions x 3 + 1 = 13 (`left` flips are free) = 1170 s. Export: keys `idle_down|up|right|left`,
`walk_*`, `attack_*`, `hurt_*`, `death_down`; frames `walk_left_0...`. If the character holds a weapon in one
hand, add `--no-mirror` to `plan` and generate `left` too.

## 4. "A pixel-art merchant NPC, a bearded old man with a green apron" (text only, Case B)
Neither image nor plan details but a description: do not ask anything; make the reference first.
```bash
python scripts/forge.py init merchant --view side --asset-type npc --art-style pixel_art
python scripts/forge.py reference generate merchant --description "bearded old merchant, green apron, pixel art" --count 2
python scripts/forge.py reference select merchant 001      # pick the better candidate (attempts under reference/attempts/)
python scripts/forge.py identity analyze merchant
python scripts/forge.py plan merchant --bundle npc          # estimated_seconds: 180
```
Plan: `asset_type npc`, `view side`, `facing right`, `art_style pixel_art`, `order [idle, walk]`,
`assumptions ["view=side"]`, idle 4/2x2/6 loop, walk 6/2x3/10 loop (both fit, anchor feet, x_anchor mass).
Then generate/process/accept idle and walk, `export merchant --engine phaser`, and report that the reference
was generated from the description and which candidate was chosen.

## Final report template
```
Character: hero  |  view: side  |  actions: idle walk run attack
Files: sprites/hero/atlas/hero.png, atlas/hero.json, animations.json, preview/*.gif
QC: idle pass, walk pass, run warn (QC-02 0.07), attack pass
Forced accepts: none   Failures: none
Assumptions: view=side; art_style=project_native (reference provided)
Usage: see references/phaser-export.md
```
