/** Pure logic of the animation viewer (docs/09 5): frame URLs, tile layout from plan + status, shared-clock frames. */
import type { Direction } from '@/api/queries'
import type { Plan } from '@/lib/plan'
import { frameAt } from '@/lib/player'
import { DIRECTION_LABEL, actionDirections, isMultiDirection, unitKey, type UnitRow } from '@/lib/studio'

export const SPEEDS = [0.5, 1, 2] as const
export const SCALES = [1, 2, 3, 4] as const

/**
 * `/files/<cid>/<unit>/frames/NNN.png`. The mirror-derived `left` unit lives at the same layout (`<action>/left/frames`).
 * `version` (the accepted attempt) becomes `?v=` so a newly accepted attempt is never served from the browser cache.
 */
export const frameUrl = (cid: string, unit: string, index: number, version?: string | null) =>
  `/files/${cid}/${unit}/frames/${String(index).padStart(3, '0')}.png${version ? `?v=${version}` : ''}`

export const frameUrls = (cid: string, unit: string, count: number, version?: string | null) =>
  Array.from({ length: count }, (_, i) => frameUrl(cid, unit, i, version))

export interface Tile {
  unit: string
  action: string
  direction?: Direction
  /** "walk · 앞 (down)" or just the action name for single-direction plans */
  label: string
  /** playable: accepted (or mirror-derived from an accepted right); missing: nothing to play yet */
  state: 'playable' | 'missing'
  frames: number
  fps: number
  loop: boolean
  /** frame image URLs, empty for missing tiles */
  urls: string[]
}

export interface TileRow { action: string; tiles: Tile[] }

const DIRECTION_NAME: Record<Direction, string> = {
  down: `${DIRECTION_LABEL.down} (down)`, up: `${DIRECTION_LABEL.up} (up)`, right: `${DIRECTION_LABEL.right} (right)`, left: `${DIRECTION_LABEL.left} (left)`,
}

/** accepted units, and mirror-derived units whose source is accepted (they carry its accepted_attempt). */
export const isPlayable = (row: UnitRow | undefined) =>
  !!row && (row.state === 'accepted' || (row.state === 'mirrored' && !!row.accepted_attempt))

/** Rows = actions in plan order; columns = the action's directions (down, up, right, left). Single-direction plans: one tile per action. */
export function buildTiles(cid: string, plan: Plan, rows: UnitRow[]): TileRow[] {
  const multi = isMultiDirection(plan)
  return (plan.order as string[]).map((action) => {
    const act = plan.actions[action]
    const dirs: (Direction | undefined)[] = multi ? actionDirections(plan, action) : [undefined]
    return {
      action,
      tiles: dirs.map((direction) => {
        const unit = unitKey(action, direction)
        const row = rows.find((r) => r.unit === unit)
        const playable = isPlayable(row)
        return {
          unit, action, direction,
          label: direction ? `${action} · ${DIRECTION_NAME[direction]}` : action,
          state: playable ? 'playable' : 'missing',
          frames: act.frames as number, fps: act.fps as number, loop: !!act.loop,
          urls: playable ? frameUrls(cid, unit, act.frames as number, row!.accepted_attempt) : [],
        } satisfies Tile
      }),
    }
  })
}

export const playableCount = (rows: TileRow[]) => rows.reduce((n, r) => n + r.tiles.filter((t) => t.state === 'playable').length, 0)

/** Where a missing tile sends the user: the studio of that unit (direction only for multi-direction plans). */
export const studioHref = (cid: string, tile: Pick<Tile, 'action' | 'direction'>) => `/c/${cid}/studio/${unitKey(tile.action, tile.direction)}`

/**
 * Frame of one tile at `elapsedMs` of the single shared viewer clock, at `speed`x.
 * Same semantics as the studio player's `frameAt`: loop actions repeat; one-shot actions play once, rest on the last
 * frame for ONE_SHOT_HOLD_MS (player.ts) and then repeat, so every tile keeps moving in the viewer.
 * All tiles read the same elapsed time, so equal-length actions stay in lockstep.
 */
export const tileFrame = (elapsedMs: number, fps: number, frameCount: number, loop: boolean, speed: number) =>
  frameAt(elapsedMs * speed, fps, frameCount, loop)
