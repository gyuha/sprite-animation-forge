import { describe, expect, it } from 'vitest'
import { ONE_SHOT_HOLD_MS, alphaBBox, frameAt, framesVersion, originFor, stepFrame } from './player'

describe('frameAt', () => {
  it('loops: advances every 1000/fps ms and wraps around', () => {
    const at = (t: number) => frameAt(t, 10, 4, true) // 100 ms per frame
    expect([at(0), at(99), at(100), at(350), at(399)]).toEqual([0, 0, 1, 3, 3])
    expect([at(400), at(520), at(1000)]).toEqual([0, 1, 2])
  })

  it('one-shot: holds the last frame for 400 ms, then repeats', () => {
    const at = (t: number) => frameAt(t, 10, 4, false)
    expect(at(399)).toBe(3)
    expect(at(399 + ONE_SHOT_HOLD_MS - 1)).toBe(3) // still resting on the last frame
    expect(at(400 + ONE_SHOT_HOLD_MS)).toBe(0) // next cycle starts
    expect(at(400 + ONE_SHOT_HOLD_MS + 100)).toBe(1)
  })

  it('follows fps changes and keeps the current frame when the origin is recomputed', () => {
    expect(frameAt(500, 10, 8, true)).toBe(5)
    expect(frameAt(500, 20, 8, true)).toBe(10 % 8)
    for (const fps of [3, 12, 30]) expect(frameAt(originFor(3, fps), fps, 6, true)).toBe(3)
  })

  it('is safe for 0-1 frames', () => {
    expect(frameAt(1234, 12, 1, true)).toBe(0)
    expect(frameAt(1234, 12, 0, false)).toBe(0)
  })
})

describe('player helpers', () => {
  it('stepFrame wraps both ways', () => {
    expect(stepFrame(0, -1, 6)).toBe(5)
    expect(stepFrame(5, 1, 6)).toBe(0)
  })

  it('alphaBBox finds the opaque pixels (end exclusive) and null for an empty image', () => {
    const data = new Uint8ClampedArray(4 * 4 * 4)
    for (const [x, y] of [[1, 1], [2, 2]]) data[(y * 4 + x) * 4 + 3] = 255
    expect(alphaBBox(data, 4, 4)).toEqual([1, 1, 3, 3])
    expect(alphaBBox(new Uint8ClampedArray(16), 2, 2)).toBeNull()
  })

  it('framesVersion changes when any frame hash changes', () => {
    const a = ['/files/h/idle/attempts/001/frames/000.png?v=aaa', '/files/h/idle/attempts/001/frames/001.png?v=bbb']
    expect(framesVersion(a)).toBe('aaa.bbb')
    expect(framesVersion([a[0], a[1].replace('bbb', 'ccc')])).not.toBe(framesVersion(a))
  })
})
