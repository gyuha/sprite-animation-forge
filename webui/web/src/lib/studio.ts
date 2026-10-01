/** Pure helpers of the studio page: which directions/units exist and what is blocked (docs/09 4 S5, docs/10 5.1). */
import type { Direction } from '@/api/queries'
import type { Plan } from '@/lib/plan'

export const DIRECTION_ORDER: Direction[] = ['down', 'up', 'right', 'left']
export const DIRECTION_LABEL: Record<Direction, string> = { down: '앞', up: '뒤', right: '우', left: '좌' }

/** One row of GET /characters/{id} `status.units` (workflow.status_report). */
export interface UnitRow {
  unit: string
  action: string
  direction: string | null
  state: 'pending' | 'imported' | 'processed' | 'accepted' | 'mirrored'
  accepted_attempt: string | null
  qc_status: string | null
  mirror_of?: string
}

/** The plan's directions need the `?direction=` parameter only from two on. */
export const isMultiDirection = (plan: Plan) => (plan.directions as string[]).length >= 2

export function actionDirections(plan: Plan, action: string): Direction[] {
  const dirs: string[] = plan.actions[action]?.directions ?? plan.directions
  return DIRECTION_ORDER.filter((d) => dirs.includes(d))
}

/** Representative direction: the one new characters start with (plan.facing). */
export function representativeDirection(plan: Plan, action: string): Direction {
  const dirs = actionDirections(plan, action)
  return dirs.includes(plan.facing) ? plan.facing : dirs[0]
}

/** `left` derived from `right` by flipping (plan.mirror), as in core `units()`. */
export const isMirrored = (plan: Plan, action: string, direction?: Direction) =>
  direction === 'left' && plan.mirror?.left === 'right' && actionDirections(plan, action).includes('right')

export const unitKey = (action: string, direction?: Direction) => (direction ? `${action}/${direction}` : action)

/** Status icon of docs/09 S5: accepted, generating, needs review, mirror-derived, none. */
export function unitIcon(rows: (UnitRow | undefined)[], generating: boolean): '✓' | '●' | '⚠' | '↔' | '○' {
  if (generating) return '●'
  const known = rows.filter((r): r is UnitRow => !!r)
  if (rows.length === 1 && known[0]?.mirror_of) return '↔'
  if (known.length > 0 && known.length === rows.length && known.every((r) => r.state === 'accepted' || (r.state === 'mirrored' && r.accepted_attempt))) return '✓'
  if (known.some((r) => r.state === 'processed' && r.qc_status !== 'pass')) return '⚠'
  return '○'
}

/** Why "새로 생성" is unavailable, or null. First matching reason wins. */
export function generateBlockReason(o: {
  mirrored: boolean
  codexReady: boolean | undefined
  generating: boolean
  /** representative unit that must be accepted first, when this is another direction and it is not accepted yet */
  needsRepresentative: string | null
}): string | null {
  if (o.mirrored) return '좌측은 우측면을 좌우반전해 만든 결과라 따로 생성하지 않습니다'
  if (o.codexReady === false) return 'Codex를 사용할 수 없습니다 (상단 상태 배지 확인)'
  if (o.generating) return '이 항목은 이미 생성 중입니다'
  if (o.needsRepresentative) return `먼저 ${o.needsRepresentative}을(를) 채택하세요 (스케일·외형 기준)`
  return null
}

/** Label of the representative unit (first body action in plan order, facing direction) when it still has to be accepted. */
export function representativeBlock(plan: Plan, direction: Direction | undefined, rows: UnitRow[]): string | null {
  if (!direction || direction === plan.facing) return null
  const first = (plan.order as string[]).find((a) => (plan.actions[a].kind ?? 'body') === 'body' && actionDirections(plan, a).includes(plan.facing))
  if (!first) return null
  const row = rows.find((r) => r.unit === unitKey(first, plan.facing))
  return row && row.state !== 'accepted' ? `${DIRECTION_LABEL[plan.facing as Direction]}면 ${first}` : null
}

/** Page shortcuts must not fire while the user types, drags a slider, picks an option or works inside a dialog. */
export function ignoresShortcut(target: EventTarget | null, key: string): boolean {
  if (!(target instanceof HTMLElement)) return false
  const own = 'input,textarea,select,[contenteditable=""],[contenteditable="true"],[role=slider],[role=combobox],[role=listbox],[role=dialog],[role=alertdialog]'
  if (target.closest(own)) return true
  // Space on a focused button/link/tab already activates it
  return key === ' ' && !!target.closest('button,a,[role=tab]')
}
