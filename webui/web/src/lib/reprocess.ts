/** Reprocess parameters (docs/09 6): process.json `params` <-> panel values <-> POST /process `set`. */

export type SetValue = string | number | boolean
export type ProcessSet = Record<string, SetValue>
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Params = Record<string, any>

export interface ReprocessValues {
  anchor: string
  x_anchor: string
  scale_strategy: string
  components: string
  merge_gap_px: number
  t_in: number
  t_out: number
  despill: boolean
  edge_band_px: number
  margin_top: number
  margin_side: number
  margin_bottom: number
}

/** Keys the plan stores per action; only these can be saved with save-params (routes/actions.py SAVEABLE). */
export const PLAN_KEYS = ['anchor', 'x_anchor', 'scale_strategy', 'components'] as const

export const ENUMS = {
  anchor: ['feet', 'bottom', 'center'],
  x_anchor: ['mass', 'feet', 'bbox'],
  scale_strategy: ['fit', 'preserve'],
  components: ['largest', 'all'],
} as const

export const SLIDERS: { key: keyof ReprocessValues & string; label: string; min: number; max: number }[] = [
  { key: 't_in', label: '배경 허용치 (안쪽)', min: 0, max: 120 },
  { key: 't_out', label: '배경 허용치 (바깥쪽)', min: 30, max: 200 },
  { key: 'edge_band_px', label: '가장자리 정리 (px)', min: 0, max: 4 },
  { key: 'merge_gap_px', label: '조각 병합 거리 (px)', min: 0, max: 64 },
  { key: 'margin_top', label: '여백 위', min: 0, max: 32 },
  { key: 'margin_side', label: '여백 옆', min: 0, max: 32 },
  { key: 'margin_bottom', label: '여백 아래', min: 0, max: 32 },
]

/** Panel values from process.json `params` (the server records resolved values, e.g. merge_gap_px). */
export function valuesFromParams(p: Params | null | undefined): ReprocessValues {
  return {
    anchor: p?.anchor ?? 'feet',
    x_anchor: p?.x_anchor ?? 'mass',
    scale_strategy: p?.scale_strategy ?? 'fit',
    components: p?.components?.mode ?? 'largest',
    merge_gap_px: p?.components?.merge_gap_px ?? 12,
    t_in: p?.background?.t_in ?? 30,
    t_out: p?.background?.t_out ?? 90,
    despill: p?.background?.despill ?? true,
    edge_band_px: p?.background?.edge_band_px ?? 2,
    margin_top: p?.margin?.top ?? 8,
    margin_side: p?.margin?.side ?? 8,
    margin_bottom: p?.margin?.bottom ?? 10,
  }
}

/**
 * Every value, not only the changed ones: the server applies `set` on top of the plan's settings (not on top of the
 * previous reprocess), so a partial set would silently drop earlier tweaks.
 */
export const valuesToSet = (v: ReprocessValues): ProcessSet => ({ ...v })

/** Apply a patch and keep t_in < t_out (the server pipeline requires it); the control just edited wins. */
export function patchValues(v: ReprocessValues, patch: Partial<ReprocessValues>): ReprocessValues {
  const next = { ...v, ...patch }
  if (next.t_in >= next.t_out) {
    if ('t_in' in patch) next.t_out = next.t_in + 1
    else next.t_in = next.t_out - 1
  }
  return next
}

/** process.json params after a successful `set` (the process response does not repeat them). */
export function mergeSetIntoParams(params: Params | undefined, set: ProcessSet): Params {
  const p: Params = { ...params, background: { ...params?.background }, components: { ...params?.components }, margin: { ...params?.margin } }
  for (const [k, v] of Object.entries(set)) {
    if (k === 'components') p.components.mode = v
    else if (k === 'merge_gap_px') p.components.merge_gap_px = v
    else if (k === 't_in' || k === 't_out' || k === 'despill' || k === 'edge_band_px') p.background[k] = v
    else if (k.startsWith('margin_')) p.margin[k.slice(7)] = v
    else p[k] = v
  }
  return p
}
