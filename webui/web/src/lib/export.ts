/** Pure helpers of the export screen (docs/07 7, docs/09 4 S6). */
import type { ExportMeta } from '@/api/queries'
import type { UnitRow } from '@/lib/studio'

/** Units that are neither accepted nor mirror-derived yet: they are missing from the atlas. */
export const missingUnits = (rows: UnitRow[]) => rows.filter((r) => r.state !== 'accepted' && r.state !== 'mirrored')

/** Studio path of a unit key ("walk" or "walk/up"). */
export const studioPath = (cid: string, unit: string) => `/c/${cid}/studio/${unit}`

/** `my-hero` -> `my_hero`: character ids may contain `-`, JS identifiers may not. */
const identifier = (cid: string) => (/^\d/.test(cid) ? `_${cid}` : cid).replace(/-/g, '_')

/** docs/07 7 with the character id and the origin of `<cid>.meta.json` filled in. */
export function phaserSnippet(cid: string, meta: ExportMeta): string {
  const first = meta.actions[0]
  const key = first ? (first.direction ? `${first.name}_${first.direction}` : first.name) : 'idle'
  const v = identifier(cid)
  const lines = [
    '// preload',
    `this.load.atlas('${cid}', 'assets/${cid}/atlas/${cid}.png', 'assets/${cid}/atlas/${cid}.json');`,
    `this.load.json('${cid}-anims', 'assets/${cid}/animations.json');`,
    '',
    '// create',
    `const defs = this.cache.json.get('${cid}-anims');`,
    'for (const [name, def] of Object.entries(defs)) {',
    '  this.anims.create({',
    `    key: \`${cid}-\${name}\`,`,
    `    frames: def.frames.map((frame) => ({ key: '${cid}', frame })),`,
    '    frameRate: def.frameRate,',
    '    repeat: def.repeat,',
    '  });',
    '}',
    '',
    `const ${v} = this.add.sprite(200, 300, '${cid}', '${key}_0');`,
    `${v}.setOrigin(${meta.origin.x}, ${meta.origin.y});   // ${cid}.meta.json 의 origin. 발이 (200, 300)에 놓임`,
    `${v}.play('${cid}-${key}');`,
  ]
  if (meta.actions.some((a) => a.direction)) {
    lines.push(
      '',
      '// 탑다운: 마지막으로 바라본 방향을 기억해 idle/walk key를 고른다',
      "let facing = 'down';",
      'function update(vx, vy) {',
      "  if (vx || vy) facing = Math.abs(vx) > Math.abs(vy) ? (vx > 0 ? 'right' : 'left') : (vy > 0 ? 'down' : 'up');",
      `  ${v}.play(\`${cid}-\${vx || vy ? 'walk' : 'idle'}_\${facing}\`, true);`,
      '}',
    )
  }
  return lines.join('\n')
}

/** Label position of an atlas row in percent of the atlas image height (row-major layout, docs/07 3). */
export function rowTopPercent(meta: ExportMeta, row: number): number {
  return ((meta.padding + row * (meta.cell.h + meta.padding)) / meta.texture.size[1]) * 100
}
