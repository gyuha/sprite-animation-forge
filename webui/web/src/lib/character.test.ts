import { describe, expect, it } from 'vitest'
import { slugify, uniqueId, validateCharacterId } from './character'

describe('character id', () => {
  it('accepts the CLI pattern and rejects everything else', () => {
    expect(validateCharacterId('hero-2')).toBeNull()
    expect(validateCharacterId('0wl')).toBeNull()
    for (const bad of ['', 'Hero', '-hero', 'my_hero', 'hé', 'a'.repeat(41)]) expect(validateCharacterId(bad)).not.toBeNull()
  })

  it('suggests a slug from the file name and appends -2 on a duplicate', () => {
    expect(slugify('My Hero (final).PNG')).toBe('my-hero-final')
    expect(slugify('용사.png')).toBe('')
    expect(uniqueId('hero', ['hero'])).toBe('hero-2')
    expect(uniqueId('hero', ['hero', 'hero-2'])).toBe('hero-3')
    expect(uniqueId('slime', ['hero'])).toBe('slime')
  })
})
