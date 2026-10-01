# Phaser export and usage

`export <cid> --engine phaser` packs all accepted units into `<root>/<cid>/`:
```
atlas/<cid>.png  atlas/<cid>.json (Phaser JSON Hash)  atlas/<cid>.generic.json  atlas/<cid>.meta.json
animations.json  preview/<action>.gif  qc-report.json  manifest.json
```
stdout: `{files: [...], warnings: [...]}`. A warning `missing_actions: [...]` means some units were not accepted
(only accepted units are exported). Errors: `cell_mismatch` (all actions need the same cell size),
`atlas_too_large` (> 4096 px; fewer actions/directions or cell 128). The result is validated (frame rects,
names, frame counts, schemas, sha256) before the files are swapped in. Minimum files for a game:
`atlas/<cid>.png`, `atlas/<cid>.json`, `animations.json`.

Frame names: `<action>_<index>` (0-based), e.g. `walk_3`. With 2+ directions: `<action>_<direction>_<index>`,
e.g. `walk_up_3`, and `animations.json` keys are `<action>_<direction>`. Entries are
`{frames: [...], frameRate, repeat}` with `repeat` -1 for loops and 0 for one-shots. Row `i` of the atlas is
one unit; padding is 2 px; the `left` direction is real frames (no `setFlipX` needed). Origin (foot point):
`x = 0.5`, `y = baseline_y / cell_h` (e.g. 118/128 = 0.921875), also in `<cid>.meta.json` as `origin`.
GIF previews: one per unit (`preview/<action>_<direction>.gif` when directional), loop forever.

## Phaser 3/4 usage (assets copied to `public/assets/hero/`)
```js
// preload
this.load.atlas('hero', 'assets/hero/atlas/hero.png', 'assets/hero/atlas/hero.json');
this.load.json('hero-anims', 'assets/hero/animations.json');

// create
const defs = this.cache.json.get('hero-anims');
for (const [name, def] of Object.entries(defs)) {
  this.anims.create({
    key: `hero-${name}`,
    frames: def.frames.map((frame) => ({ key: 'hero', frame })),
    frameRate: def.frameRate,
    repeat: def.repeat,
  });
}
const hero = this.add.sprite(200, 300, 'hero', 'idle_0');
hero.setOrigin(0.5, 118 / 128);   // origin from hero.meta.json; feet land on (200, 300)
hero.play('hero-idle');
```
- Pixel-art styles: set `pixelArt: true` in the game config.
- Side view only generates the right-facing direction: face left with `hero.setFlipX(true)`.
- Topdown (4 directions) needs no flip; pick the key by movement:
```js
let facing = 'down';
function update(vx, vy) {
  if (vx || vy) facing = Math.abs(vx) > Math.abs(vy) ? (vx > 0 ? 'right' : 'left') : (vy > 0 ? 'down' : 'up');
  hero.play(`hero-${vx || vy ? 'walk' : 'idle'}_${facing}`, true);
}
```
The animation key is global to the game, so prefix it with the character id (`hero-idle`).
