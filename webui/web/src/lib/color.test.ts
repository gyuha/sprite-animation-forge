import { describe, expect, it } from 'vitest'
import { colorDistance, isHexColor, resolveKeyColor } from './color'

describe('key colour', () => {
  it('keeps magenta when no character colour is close to it', () => {
    expect(resolveKeyColor(['#C8281E', '#9A9CA0'])).toEqual({ key: '#FF00FF', conflict: 'none' })
  })

  it('switches to green when a colour is within 120 of magenta', () => {
    expect(colorDistance('#E000E0', '#FF00FF')).toBeLessThan(120)
    expect(resolveKeyColor(['#C8281E', '#E000E0'])).toEqual({ key: '#00FF00', conflict: 'magenta' })
  })

  it('keeps magenta with a warning when both keys conflict', () => {
    expect(resolveKeyColor(['#E000E0', '#10E010'])).toEqual({ key: '#FF00FF', conflict: 'both' })
  })

  it('ignores invalid hex strings like the server does', () => {
    expect(isHexColor('#12345')).toBe(false)
    expect(resolveKeyColor(['#zzzzzz', ''])).toEqual({ key: '#FF00FF', conflict: 'none' })
  })
})
