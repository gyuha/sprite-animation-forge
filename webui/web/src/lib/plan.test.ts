import { describe, expect, it } from 'vitest'
import { makePresets } from '@/test-fixtures'
import {
  actionValues, buildCreateRequest, countUnits, detectBundle, estimateSeconds, expandBundle, formatDuration, withView, type PlanDraft,
} from './plan'

const presets = makePresets()
const draft = (over: Partial<PlanDraft> = {}): PlanDraft => ({
  bundle: 'side-basic', view: 'side', actions: ['idle', 'walk', 'run', 'attack'], edits: {}, cell: '128x128', directions: [], mirror: false, ...over,
})

describe('bundle expansion', () => {
  it('expands a bundle to its actions and implied view; "custom" expands to nothing', () => {
    expect(expandBundle(presets, 'side-basic')).toEqual({ actions: ['idle', 'walk', 'run', 'attack'], view: null })
    expect(expandBundle(presets, 'topdown-rpg')?.view).toBe('topdown')
    expect(expandBundle(presets, 'custom')).toBeNull()
  })

  it('detects the bundle from an action list, order sensitive, else custom', () => {
    expect(detectBundle(presets, ['idle', 'walk'])).toBe('npc')
    expect(detectBundle(presets, ['walk', 'idle'])).toBe('custom')
  })
})

describe('units and estimate', () => {
  it('counts one unit per action for single-direction views', () => {
    expect(countUnits(draft())).toBe(4)
    expect(estimateSeconds(draft())).toBe(360)
  })

  it('topdown: 4 directions with mirror generate 3 per action, without mirror 4', () => {
    const topdown = withView(draft({ actions: ['idle', 'walk'] }), 'topdown')
    expect(countUnits(topdown)).toBe(6)
    expect(countUnits({ ...topdown, mirror: false })).toBe(8)
    expect(countUnits({ ...topdown, directions: ['down', 'up'], mirror: true })).toBe(4)
  })

  it('formats durations in Korean', () => {
    expect(formatDuration(270)).toBe('4분 30초')
    expect(formatDuration(360)).toBe('6분')
    expect(formatDuration(45)).toBe('45초')
  })
})

describe('buildCreateRequest', () => {
  it('sends the bundle name when the actions are exactly the bundle, plus only the edited --set values', () => {
    const body = buildCreateRequest(draft({ edits: { walk: { frames: 8, loop: false } } }), presets)
    expect(body).toEqual({ cell: '128x128', view: 'side', bundle: 'side-basic', set: ['walk.frames=8', 'walk.loop=false'] })
  })

  it('sends explicit actions once the selection differs from the bundle, and no directions for non-topdown views', () => {
    const body = buildCreateRequest(draft({ bundle: 'custom', actions: ['idle', 'death'] }), presets)
    expect(body.actions).toEqual(['idle', 'death'])
    expect(body.bundle).toBeUndefined()
    expect(body.directions).toBeUndefined()
    expect(body.mirror).toBeUndefined()
  })

  it('topdown sends directions in generation order and the effective mirror', () => {
    const d = withView(draft({ bundle: 'topdown-rpg', actions: ['idle', 'walk', 'attack', 'hurt', 'death'] }), 'topdown')
    expect(buildCreateRequest(d, presets)).toMatchObject({ bundle: 'topdown-rpg', directions: ['down', 'up', 'right', 'left'], mirror: true })
    // left unchecked: mirror cannot apply even though the switch value is still true
    expect(buildCreateRequest({ ...d, directions: ['down', 'right'] }, presets)).toMatchObject({ directions: ['down', 'right'], mirror: false })
  })
})

describe('generation method (grid | breathe | video)', () => {
  it('defaults to grid and keeps the preset grid', () => {
    expect(actionValues('idle', draft(), presets)).toMatchObject({ method: 'grid', frames: 4, grid: '2x2' })
  })

  it('breathe generates one still (1x1) and defaults to six output frames, unless frames are edited', () => {
    expect(actionValues('idle', draft({ edits: { idle: { method: 'breathe' } } }), presets)).toMatchObject({ method: 'breathe', frames: 6, grid: '1x1' })
    expect(actionValues('idle', draft({ edits: { idle: { method: 'breathe', frames: 8 } } }), presets)).toMatchObject({ frames: 8, grid: '1x1' })
  })

  it('sends method through --set (never for grid) and no grid override for breathe', () => {
    const body = buildCreateRequest(draft({ edits: { idle: { method: 'breathe', grid: '2x2' }, walk: { method: 'grid', fps: 12 } } }), presets)
    expect(body.set).toEqual(['idle.method=breathe', 'walk.fps=12'])
  })
})
