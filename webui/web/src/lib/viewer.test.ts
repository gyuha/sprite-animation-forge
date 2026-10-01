import { describe, expect, it } from 'vitest'
import { makePlanResponse } from '@/test-fixtures'
import type { UnitRow } from './studio'
import { buildTiles, frameUrl, frameUrls, isPlayable, playableCount, studioHref, tileFrame } from './viewer'

const row = (unit: string, state: UnitRow['state'], accepted: string | null = '001'): UnitRow => ({
  unit, action: unit.split('/')[0], direction: unit.split('/')[1] ?? null, state, accepted_attempt: accepted, qc_status: null,
})
const side = makePlanResponse('side').plan
const topdown = makePlanResponse('topdown').plan

describe('frame URLs', () => {
  it('pads the index to three digits and appends ?v= only with a version', () => {
    expect(frameUrl('hero', 'idle', 3)).toBe('/files/hero/idle/frames/003.png')
    expect(frameUrl('hero', 'walk/down', 12, '002')).toBe('/files/hero/walk/down/frames/012.png?v=002')
    expect(frameUrl('hero', 'idle', 0, null)).toBe('/files/hero/idle/frames/000.png')
  })

  it('lists one URL per frame, mirror left included', () => {
    expect(frameUrls('hero', 'idle', 2, '001')).toEqual(['/files/hero/idle/frames/000.png?v=001', '/files/hero/idle/frames/001.png?v=001'])
    expect(frameUrl('hero', 'idle/left', 1, '001')).toBe('/files/hero/idle/left/frames/001.png?v=001')
  })
})

describe('buildTiles', () => {
  it('makes one tile per action for a single-direction plan, in plan order', () => {
    const tiles = buildTiles('hero', side, [row('idle', 'accepted'), row('walk', 'processed', null)])
    expect(tiles.map((r) => r.action)).toEqual(['idle', 'walk'])
    expect(tiles.map((r) => r.tiles.length)).toEqual([1, 1])
    expect(tiles[0].tiles[0]).toMatchObject({ unit: 'idle', label: 'idle', state: 'playable', frames: 4, fps: 6, loop: true })
    expect(tiles[0].tiles[0].urls[0]).toBe('/files/hero/idle/frames/000.png?v=001')
    expect(tiles[1].tiles[0]).toMatchObject({ unit: 'walk', state: 'missing', urls: [] })
  })

  it('lays a topdown plan out as rows = actions, columns = down/up/right/left', () => {
    const tiles = buildTiles('hero', topdown, [
      row('idle/down', 'accepted'), row('idle/up', 'pending', null), row('idle/right', 'accepted'), row('idle/left', 'mirrored'),
    ])
    expect(tiles.map((r) => r.tiles.map((t) => t.unit))).toEqual([
      ['idle/down', 'idle/up', 'idle/right', 'idle/left'],
      ['walk/down', 'walk/up', 'walk/right', 'walk/left'],
    ])
    expect(tiles[0].tiles.map((t) => t.state)).toEqual(['playable', 'missing', 'playable', 'playable'])
    expect(tiles[0].tiles[0].label).toBe('idle · 앞 (down)')
    expect(tiles[0].tiles[3].urls[0]).toBe('/files/hero/idle/left/frames/000.png?v=001')
    expect(playableCount(tiles)).toBe(3)
  })

  it('treats units without a status row as missing', () => {
    expect(playableCount(buildTiles('hero', side, []))).toBe(0)
  })

  it('links missing tiles to their studio page, with the direction only for multi-direction plans', () => {
    const [idle] = buildTiles('hero', topdown, [])
    expect(studioHref('hero', idle.tiles[1])).toBe('/c/hero/studio/idle/up')
    expect(studioHref('hero', buildTiles('hero', side, [])[1].tiles[0])).toBe('/c/hero/studio/walk')
  })
})

describe('isPlayable', () => {
  it('accepts accepted units and mirror-derived units with a source attempt only', () => {
    expect(isPlayable(row('idle', 'accepted'))).toBe(true)
    expect(isPlayable(row('idle/left', 'mirrored'))).toBe(true)
    expect(isPlayable(row('idle/left', 'mirrored', null))).toBe(false)
    expect(isPlayable(row('idle', 'processed'))).toBe(false)
    expect(isPlayable(undefined)).toBe(false)
  })
})

describe('tileFrame (shared clock)', () => {
  it('advances by fps and repeats a loop action', () => {
    expect(tileFrame(0, 10, 4, true, 1)).toBe(0)
    expect(tileFrame(150, 10, 4, true, 1)).toBe(1)
    expect(tileFrame(390, 10, 4, true, 1)).toBe(3)
    expect(tileFrame(410, 10, 4, true, 1)).toBe(0)
  })

  it('holds the last frame of a one-shot action, then repeats it', () => {
    expect(tileFrame(390, 10, 4, false, 1)).toBe(3)
    expect(tileFrame(700, 10, 4, false, 1)).toBe(3)
    expect(tileFrame(810, 10, 4, false, 1)).toBe(0)
  })

  it('scales elapsed time by the speed', () => {
    expect(tileFrame(150, 10, 4, true, 2)).toBe(3)
    expect(tileFrame(150, 10, 4, true, 0.5)).toBe(0)
  })

  it('keeps single-frame or zero-fps actions on frame 0', () => {
    expect(tileFrame(999, 10, 1, true, 1)).toBe(0)
    expect(tileFrame(999, 0, 4, true, 1)).toBe(0)
  })
})
