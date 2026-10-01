/** Pure plan-form logic (S4): bundle expansion, draft -> request/plan, unit count and time estimate. */
import type { Presets } from '@/api/queries'
import type { components } from '@/api/types'

export type PlanCreateBody = components['schemas']['PlanCreate']
export type PlanDirection = 'down' | 'up' | 'right' | 'left'
/** The plan is an untyped dict in OpenAPI (docs/08 5.1 has the fields). */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type Plan = Record<string, any>

export const DIRECTIONS: { value: PlanDirection; label: string }[] = [
  { value: 'down', label: '앞 (down)' },
  { value: 'up', label: '뒤 (up)' },
  { value: 'right', label: '우 (right)' },
  { value: 'left', label: '좌 (left)' },
]
export const CUSTOM_BUNDLE = 'custom'
export const BUNDLE_LABELS: Record<string, string> = {
  'side-basic': '횡스크롤 기본',
  'side-action': '횡스크롤 액션',
  'topdown-rpg': '탑다운 RPG',
  npc: 'NPC',
  [CUSTOM_BUNDLE]: '직접',
}
export const CELL_OPTIONS = ['64x64', '96x96', '128x128', '192x192', '256x256']
export const SECONDS_PER_CALL = 90

export interface ActionValues { frames: number; fps: number; loop: boolean; grid: string }

export interface PlanDraft {
  bundle: string
  view: string
  actions: string[]
  /** only values the user changed (or, for an existing plan, the plan's own values) */
  edits: Record<string, Partial<ActionValues>>
  cell: string
  directions: PlanDirection[]
  mirror: boolean
}

const ALL_DIRECTIONS: PlanDirection[] = ['down', 'up', 'right', 'left']
const sameList = (a: string[], b: string[]) => a.length === b.length && a.every((x, i) => x === b[i])

/** Bundle name -> its actions (and the view it implies, if any). null for "직접" / unknown names. */
export function expandBundle(presets: Pick<Presets, 'bundles'>, bundle: string) {
  return presets.bundles[bundle] ?? null
}

/** The bundle whose action list equals `actions` (same order), else "직접". */
export function detectBundle(presets: Pick<Presets, 'bundles'>, actions: string[]) {
  return Object.keys(presets.bundles).find((b) => sameList(presets.bundles[b].actions, actions)) ?? CUSTOM_BUNDLE
}

export function defaultDirections(view: string): PlanDirection[] {
  return view === 'topdown' ? [...ALL_DIRECTIONS] : []
}

/** Switching the view resets direction/mirror to that view's defaults (topdown: 4 directions + mirror). */
export function withView(d: PlanDraft, view: string): PlanDraft {
  return { ...d, view, directions: defaultDirections(view), mirror: view === 'topdown' }
}

/** mirror (left <- right) only means something when both are generated directions. */
export const canMirror = (d: Pick<PlanDraft, 'directions'>) => d.directions.includes('left') && d.directions.includes('right')
export const effectiveMirror = (d: PlanDraft) => d.view === 'topdown' && d.mirror && canMirror(d)

const gridHolds = (grid: string, frames: number) => {
  const [r, c] = grid.split('x').map(Number)
  return r * c >= frames
}

export function actionValues(name: string, d: PlanDraft, presets: Presets): ActionValues {
  const base = presets.frame_presets[name] ?? { frames: 4, fps: 10, loop: false, grid: '2x2' }
  const e = d.edits[name] ?? {}
  const frames = e.frames ?? base.frames
  const grid = e.grid && gridHolds(e.grid, frames) ? e.grid : (presets.grids[String(frames)] ?? base.grid)
  return { frames, fps: e.fps ?? base.fps, loop: e.loop ?? base.loop, grid }
}

/** Codex-generated units: every action x every direction, minus the mirror-derived left. */
export function countUnits(d: PlanDraft): number {
  const perAction = Math.max(d.directions.length, 1) - (effectiveMirror(d) ? 1 : 0)
  return d.actions.length * perAction
}

export const estimateSeconds = (d: PlanDraft) => countUnits(d) * SECONDS_PER_CALL

export function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return [m ? `${m}분` : '', s || !m ? `${s}초` : ''].filter(Boolean).join(' ')
}

/** Body of POST /plan (first creation): the server builds the plan like the CLI. */
export function buildCreateRequest(d: PlanDraft, presets: Presets): PlanCreateBody {
  const set: string[] = []
  for (const name of d.actions) {
    const e = d.edits[name]
    if (!e) continue
    if (e.frames !== undefined) set.push(`${name}.frames=${e.frames}`)
    if (e.fps !== undefined) set.push(`${name}.fps=${e.fps}`)
    if (e.loop !== undefined) set.push(`${name}.loop=${e.loop}`)
    if (e.grid !== undefined) set.push(`${name}.grid=${actionValues(name, d, presets).grid}`)
  }
  const bundle = expandBundle(presets, d.bundle)
  const body: PlanCreateBody = { cell: d.cell, set, view: d.view as PlanCreateBody['view'] }
  if (bundle && sameList(bundle.actions, d.actions)) body.bundle = d.bundle
  else body.actions = d.actions
  if (d.view === 'topdown') {
    body.directions = ALL_DIRECTIONS.filter((x) => d.directions.includes(x))
    body.mirror = effectiveMirror(d)
  }
  return body
}

export function draftFromPlan(plan: Plan, presets: Presets): PlanDraft {
  const edits: PlanDraft['edits'] = {}
  for (const name of plan.order as string[]) {
    const { frames, fps, loop, grid } = plan.actions[name]
    edits[name] = { frames, fps, loop, grid }
  }
  return {
    bundle: detectBundle(presets, plan.order),
    view: plan.view,
    actions: plan.order,
    edits,
    cell: `${plan.cell.w}x${plan.cell.h}`,
    directions: plan.view === 'topdown' ? plan.directions : [],
    mirror: plan.mirror?.left === 'right',
  }
}

/** Body of PUT /plan: the stored plan with the draft's actions, values, cell, directions and mirror applied. */
export function applyDraftToPlan(plan: Plan, d: PlanDraft, presets: Presets): Plan {
  const [w, h] = d.cell.split('x').map(Number)
  const actions: Plan['actions'] = {}
  for (const name of d.actions) {
    const base = plan.actions[name] ?? presets.frame_presets[name]
    actions[name] = { ...base, ...actionValues(name, d, presets) }
  }
  return {
    ...plan,
    actions,
    order: d.actions,
    cell: { w, h },
    ...(d.view === 'topdown' ? { directions: ALL_DIRECTIONS.filter((x) => d.directions.includes(x)) } : {}),
    mirror: effectiveMirror(d) ? { left: 'right' } : {},
  }
}
