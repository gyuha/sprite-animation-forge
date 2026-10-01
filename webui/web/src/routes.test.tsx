import { RouterProvider, createMemoryRouter, matchRoutes } from 'react-router-dom'
import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mockApi, renderWithClient } from '@/test-utils'
import Dashboard from '@/pages/Dashboard'
import Export from '@/pages/Export'
import Identity from '@/pages/Identity'
import NewCharacter from '@/pages/NewCharacter'
import Plan from '@/pages/Plan'
import Status from '@/pages/Status'
import Studio from '@/pages/Studio'
import Viewer from '@/pages/Viewer'
import { routes } from './routes'

/** The page component rendered for a URL (inside the AppLayout route). */
function pageAt(url: string) {
  const match = matchRoutes(routes, url)?.at(-1)
  return { type: (match?.route.element as { type: unknown } | undefined)?.type, params: match?.params }
}

describe('routes', () => {
  // AppLayout mounts the SSE hook and the toaster; jsdom has neither EventSource nor matchMedia
  beforeEach(() => {
    vi.stubGlobal('EventSource', class { close() {} addEventListener() {} onopen = null; onerror = null })
    vi.stubGlobal('matchMedia', () => ({ matches: false, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {} }))
  })

  it.each([
    ['/', Dashboard],
    ['/new', NewCharacter],
    ['/c/hero/identity', Identity],
    ['/c/hero/plan', Plan],
    ['/c/hero/studio', Studio],
    ['/c/hero/studio/walk', Studio],
    ['/c/hero/studio/walk/up', Studio],
    ['/c/hero/view', Viewer],
    ['/c/hero/export', Export],
    ['/status', Status],
  ])('%s renders the right page', (url, page) => {
    expect(pageAt(url).type).toBe(page)
  })

  it('passes the character id and studio params through', () => {
    expect(pageAt('/c/hero/studio/walk/up').params).toMatchObject({ cid: 'hero', action: 'walk', direction: 'up' })
  })

  it('has no route for unknown paths', () => {
    expect(pageAt('/nope').type).toBeUndefined()
  })

  it.each([
    ['/c/hero/studio/idle', true],
    ['/c/hero/view', true],
    ['/c/hero/export', true],
    ['/c/hero/identity', false],
    ['/c/hero/plan', false],
    ['/', false],
  ])('%s shows the character tab bar: %s', async (url, shown) => {
    mockApi({ 'GET /api/health': { ready: true, warnings: [], codex: {}, python: {} }, 'GET /api/jobs': { jobs: [] } })
    renderWithClient(<RouterProvider router={createMemoryRouter(routes, { initialEntries: [url] })} />)
    await screen.findByText('Sprite Animation Forge')
    if (shown) expect(await screen.findByTestId('character-tabs')).toBeInTheDocument()
    else expect(screen.queryByTestId('character-tabs')).toBeNull()
  })
})
