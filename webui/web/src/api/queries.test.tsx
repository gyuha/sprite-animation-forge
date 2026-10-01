import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { HEALTH_REFETCH_MS, dirQuery, healthQueryOptions, qk, useAttempts, type Direction } from './queries'
import { mockApi, renderWithClient } from '@/test-utils'

describe('health polling', () => {
  it('polls every 60 s and refetches on window focus', () => {
    expect(HEALTH_REFETCH_MS).toBe(60_000)
    expect(healthQueryOptions.refetchInterval).toBe(60_000)
    expect(healthQueryOptions.refetchOnWindowFocus).toBe('always')
  })
})

describe('direction', () => {
  it('uses the server vocabulary (down|up|right|left) in URLs and query keys', () => {
    const all: Direction[] = ['down', 'up', 'right', 'left']
    expect(all.map((d) => dirQuery(d))).toEqual(['?direction=down', '?direction=up', '?direction=right', '?direction=left'])
    expect(dirQuery(undefined)).toBe('')
    expect(qk.attempts('hero', 'idle', 'down')).toEqual(['characters', 'hero', 'attempts', 'idle', 'down'])
    // @ts-expect-error the old front/back vocabulary no longer type-checks
    const old: Direction = 'front'
    expect(old).toBe('front')
  })

  it('useAttempts sends ?direction= only when a direction is given', async () => {
    const list = { action: 'idle', direction: 'down', unit: 'idle/down', mirror_of: null, accepted_attempt: null, attempts: [] }
    const fetchMock = mockApi({ 'GET /api/characters/hero/actions/idle/attempts': list })
    function Probe({ direction }: { direction?: Direction }) {
      return <p data-testid="unit">{useAttempts('hero', 'idle', direction).data?.unit}</p>
    }
    renderWithClient(<Probe direction="down" />)
    await screen.findByText('idle/down')
    expect(fetchMock.mock.calls.map(([u]) => String(u))).toEqual(['/api/characters/hero/actions/idle/attempts?direction=down'])
    fetchMock.mockClear()
    renderWithClient(<Probe />)
    await screen.findAllByText('idle/down')
    expect(fetchMock.mock.calls.map(([u]) => String(u))).toEqual(['/api/characters/hero/actions/idle/attempts'])
  })
})
