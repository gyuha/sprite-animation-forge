import { MemoryRouter } from 'react-router-dom'
import { act, fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { makePlanResponse } from '@/test-fixtures'
import { jsonResponse, mockApi, renderRoute, renderWithClient } from '@/test-utils'
import Dashboard from './Dashboard'
import Studio from './Studio'
import Viewer from './Viewer'

const row = (unit: string, state: string, accepted: string | null = '001') => ({
  unit, action: unit.split('/')[0], direction: unit.split('/')[1] ?? null, state, accepted_attempt: accepted, qc_status: 'pass',
})
const detail = (units: object[]) => ({ character: { id: 'hero', next_step: 'generate' }, manifest: {}, status: { has_reference: true, has_plan: true, units } })
const sideUnits = [row('idle', 'accepted'), row('walk', 'pending', null)]
const topdownUnits = [row('idle/down', 'accepted'), row('idle/up', 'pending', null), row('idle/right', 'accepted'), row('idle/left', 'mirrored')]
const routes = (units: object[], view: 'side' | 'topdown' = 'side') => ({
  'GET /api/characters/hero/plan': makePlanResponse(view),
  'GET /api/characters/hero': detail(units),
})
const renderViewer = () => renderRoute(<Viewer />, '/c/hero/view', '/c/:cid/view')
const tiles = () => document.querySelectorAll('canvas[data-testid^="viewer-tile-"]')

/** Replaces requestAnimationFrame by a queue the test steps by hand, so the shared clock is deterministic. */
function manualRaf() {
  const queue = new Map<number, FrameRequestCallback>()
  let id = 0
  vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => { queue.set(++id, cb); return id })
  vi.stubGlobal('cancelAnimationFrame', (i: number) => { queue.delete(i) })
  const t0 = performance.now()
  return {
    pending: () => queue.size,
    /** runs the queued frame at `ms` after t0 */
    at: (ms: number) => act(() => { const cbs = [...queue.values()]; queue.clear(); cbs.forEach((cb) => cb(t0 + ms)) }),
  }
}

afterEach(() => vi.restoreAllMocks())

describe('Viewer tiles', () => {
  it('renders a canvas tile per accepted unit and a placeholder with a studio link for a pending one', async () => {
    mockApi(routes(sideUnits))
    renderViewer()
    const idle = await screen.findByTestId('viewer-tile-idle')
    expect(idle.tagName).toBe('CANVAS')
    expect(idle).toHaveAttribute('data-unit', 'idle')
    expect(idle).toHaveAttribute('data-frame', '0')
    expect(idle).toHaveAttribute('data-frame-count', '4')
    const missing = screen.getByTestId('viewer-tile-missing-walk')
    expect(missing).toHaveTextContent('미채택')
    expect(missing.querySelector('a')).toHaveAttribute('href', '/c/hero/studio/walk')
    expect(tiles()).toHaveLength(1)
  })

  it('is not painted without a 2d context (jsdom) but still exposes its structure', async () => {
    mockApi(routes(sideUnits))
    renderViewer()
    expect(await screen.findByTestId('viewer-tile-idle')).toHaveAttribute('data-painted', 'false')
  })

  it('lays a topdown character out per action with Korean direction labels and mirrored left playable', async () => {
    mockApi(routes(topdownUnits, 'topdown'))
    renderViewer()
    await screen.findByTestId('viewer-tile-idle/down')
    expect([...tiles()].map((c) => c.getAttribute('data-unit'))).toEqual(['idle/down', 'idle/right', 'idle/left'])
    expect(screen.getByTestId('viewer-tile-missing-idle/up')).toHaveTextContent('idle · 뒤 (up)')
    expect(screen.getByTestId('viewer-tile-missing-walk/down').querySelector('a')).toHaveAttribute('href', '/c/hero/studio/walk/down')
    expect(screen.getByTestId('viewer-frame-idle/left')).toHaveTextContent('1 / 4')
  })

  it('shows the empty state without a plan or without accepted units', async () => {
    mockApi({ 'GET /api/characters/hero/plan': jsonResponse({ error: { code: 'not_found', message: 'no plan', detail: {} } }, 404), 'GET /api/characters/hero': detail([]) })
    const first = renderViewer()
    expect(await screen.findByTestId('viewer-empty')).toHaveTextContent('플랜')
    first.unmount()
    mockApi(routes([row('idle', 'pending', null), row('walk', 'processed', null)]))
    renderViewer()
    expect(await screen.findByTestId('viewer-empty')).toHaveTextContent('채택된 액션이 없습니다')
    expect(tiles()).toHaveLength(0)
  })
})

describe('Viewer controls', () => {
  const bothAccepted = [row('idle', 'accepted'), row('walk', 'accepted')]

  it('pauses and resumes the shared clock with the play-all button', async () => {
    const raf = manualRaf()
    mockApi(routes(bothAccepted))
    renderViewer()
    const play = await screen.findByTestId('viewer-play-all')
    expect(play).toHaveAttribute('data-playing', 'true')
    expect(raf.pending()).toBe(1)
    await raf.at(450)
    expect(screen.getByTestId('viewer-tile-idle')).toHaveAttribute('data-frame', '2') // 6 fps
    expect(screen.getByTestId('viewer-tile-walk')).toHaveAttribute('data-frame', '4') // 10 fps, same clock
    fireEvent.click(play)
    expect(play).toHaveAttribute('data-playing', 'false')
    expect(screen.getByTestId('viewer-grid')).toHaveAttribute('data-playing', 'false')
    expect(raf.pending()).toBe(0)
    expect(screen.getByTestId('viewer-tile-idle')).toHaveAttribute('data-frame', '2')
    fireEvent.click(play)
    expect(raf.pending()).toBe(1)
  })

  it('drives every tile from ONE requestAnimationFrame loop', async () => {
    const raf = manualRaf()
    mockApi(routes(topdownUnits, 'topdown'))
    renderViewer()
    await screen.findByTestId('viewer-tile-idle/down')
    expect(raf.pending()).toBe(1)
    await raf.at(300)
    expect(raf.pending()).toBe(1)
  })

  it('applies the speed to the frame computation', async () => {
    const raf = manualRaf()
    mockApi(routes(bothAccepted))
    renderViewer()
    await screen.findByTestId('viewer-tile-idle')
    await userEvent.click(screen.getByTestId('viewer-speed-2'))
    expect(screen.getByTestId('viewer-grid')).toHaveAttribute('data-speed', '2')
    await raf.at(200) // 400 ms of animation at 2x: idle 2.4 -> frame 2
    expect(screen.getByTestId('viewer-tile-idle')).toHaveAttribute('data-frame', '2')
  })

  it('scales the canvas display size, not its pixels', async () => {
    mockApi(routes(bothAccepted))
    renderViewer()
    const idle = await screen.findByTestId('viewer-tile-idle')
    expect(idle).toHaveStyle({ width: '256px', height: '256px' })
    await userEvent.click(screen.getByTestId('viewer-scale-4'))
    expect(idle).toHaveStyle({ width: '512px', height: '512px' })
    expect(idle).toHaveAttribute('width', '128')
    expect(screen.getByTestId('viewer-grid')).toHaveAttribute('data-scale', '4')
  })

  it('switches the background', async () => {
    mockApi(routes(bothAccepted))
    renderViewer()
    await screen.findByTestId('viewer-tile-idle')
    await userEvent.click(screen.getByTestId('viewer-bg-green'))
    expect(screen.getByTestId('viewer-grid')).toHaveAttribute('data-bg', 'green')
    expect(screen.getByTestId('viewer-tile-idle').parentElement).toHaveStyle({ backgroundColor: 'rgb(47, 125, 74)' })
  })
})

describe('Viewer zoom dialog', () => {
  it('opens a large player for the clicked tile', async () => {
    mockApi(routes([row('idle', 'accepted'), row('walk', 'accepted')]))
    renderViewer()
    await userEvent.click(await screen.findByTestId('viewer-tile-walk'))
    const dialog = await screen.findByTestId('viewer-zoom-dialog')
    expect(dialog).toHaveTextContent('walk')
    expect(screen.getByTestId('preview-canvas')).toHaveAttribute('data-frame-count', '6')
    expect(screen.getByTestId('player-fps-value')).toHaveTextContent('10fps')
    await userEvent.click(screen.getByTestId('player-next'))
    await waitFor(() => expect(screen.getByTestId('preview-canvas')).toHaveAttribute('data-frame', '1'))
  })
})

describe('entry links', () => {
  it('Dashboard cards link to the viewer', async () => {
    mockApi({
      'GET /api/health': { ready: true, warnings: [], codex: {}, python: {} },
      'GET /api/jobs': { jobs: [] },
      'GET /api/characters': { characters: [{ id: 'hero', created_at: '', updated_at: '', settings: {}, has_reference: false, has_plan: true, units_total: 2, units_accepted: 1, next_step: 'generate' }] },
    })
    renderWithClient(<MemoryRouter><Dashboard /></MemoryRouter>)
    expect(await screen.findByTestId('character-view-hero')).toHaveAttribute('href', '/c/hero/view')
    expect(screen.getByTestId('character-view-hero')).toHaveTextContent('애니메이션 보기')
    expect(screen.getByTestId('character-card-hero')).toHaveAttribute('href', '/c/hero/studio')
  })

  it('Studio links to the viewer', async () => {
    mockApi({
      ...routes(sideUnits),
      'GET /api/health': { ready: true, warnings: [], codex: {}, python: {} },
      'GET /api/jobs': { jobs: [] },
      'GET /api/characters/hero/actions/idle/attempts': { action: 'idle', direction: null, unit: 'idle', mirror_of: null, accepted_attempt: null, attempts: [] },
    })
    renderRoute(<Studio />, '/c/hero/studio/idle', '/c/:cid/studio/:action?/:direction?')
    expect(await screen.findByTestId('studio-view-link')).toHaveAttribute('href', '/c/hero/view')
  })
})
