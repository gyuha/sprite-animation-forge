import { describe, expect, it } from 'vitest'
import { HEALTH_REFETCH_MS, healthQueryOptions } from './queries'

describe('health polling', () => {
  it('polls every 60 s and refetches on window focus', () => {
    expect(HEALTH_REFETCH_MS).toBe(60_000)
    expect(healthQueryOptions.refetchInterval).toBe(60_000)
    expect(healthQueryOptions.refetchOnWindowFocus).toBe('always')
  })
})
