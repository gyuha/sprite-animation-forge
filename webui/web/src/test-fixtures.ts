import type { Presets } from '@/api/queries'
import type { JobSnapshot } from '@/api/sse'

export function makeJob(over: Partial<JobSnapshot> = {}): JobSnapshot {
  return {
    id: 'job_1', type: 'action_generate', character: 'hero', action: 'idle', direction: 'right', state: 'running',
    created_at: '2026-10-01T00:00:00Z', elapsed_s: 0, queue_position: 0, log: [], ...over,
  }
}

export function makePresets(): Presets {
  const p = (frames: number, loop: boolean, fps: number, grid: string) =>
    ({ frames, loop, fps, grid, anchor: 'feet', scale_strategy: 'fit', x_anchor: 'mass', components: 'largest' })
  return {
    frame_presets: { idle: p(4, true, 6, '2x2'), walk: p(6, true, 10, '2x3'), run: p(6, true, 12, '2x3'), attack: p(6, false, 12, '2x3'), hurt: p(4, false, 10, '2x2'), death: p(8, false, 8, '2x4') },
    bundles: {
      'side-basic': { actions: ['idle', 'walk', 'run', 'attack'], view: null },
      'topdown-rpg': { actions: ['idle', 'walk', 'attack', 'hurt', 'death'], view: 'topdown' },
      npc: { actions: ['idle', 'walk'], view: null },
    },
    grids: { '2': '1x2', '4': '2x2', '6': '2x3', '8': '2x4', '9': '3x3', '16': '4x4' },
    views: ['side', 'topdown'], asset_types: ['character'], art_styles: ['auto'], directions: ['right', 'left', 'up', 'down'],
    methods: { grid: { available: true, reason: null }, breathe: { available: true, reason: null }, video: { available: false, reason: '동영상 API가 연결되지 않았습니다' } },
  }
}

/** A stored plan as returned by GET /plan (docs/08 5.1), for the given view. */
export function makePlanResponse(view: 'side' | 'topdown' = 'side') {
  const act = (frames: number, fps: number, loop: boolean, grid: string) =>
    ({ frames, grid, loop, fps, anchor: 'feet', scale_strategy: 'fit', x_anchor: 'mass', components: 'largest' })
  const topdown = view === 'topdown'
  return {
    plan: {
      schema_version: 1, character: 'hero', asset_type: 'character', view, facing: topdown ? 'down' : 'right',
      directions: topdown ? ['down', 'up', 'right', 'left'] : ['right'], mirror: topdown ? { left: 'right' } : {},
      art_style: 'project_native', cell: { w: 128, h: 128 }, margin: { top: 8, side: 8, bottom: 10 }, key_color: '#FF00FF', engine: 'phaser',
      actions: { idle: act(4, 6, true, '2x2'), walk: act(6, 10, true, '2x3') }, order: ['idle', 'walk'], assumptions: [],
    },
    estimated_seconds: 180,
    units: [],
  }
}
