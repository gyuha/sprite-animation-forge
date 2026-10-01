import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { qk } from '@/api/queries'
import { makeClient, apiError, lastBody, mockApi, renderRoute } from '@/test-utils'
import { makePlanResponse, makePresets } from '@/test-fixtures'
import Plan from './Plan'

const identity = (colors: string[]) => ({ profile: { schema_version: 1, source: 'manual', edited_by_user: true, identity: { primary_colors: colors, secondary_colors: [] } } })

/** A character without a plan yet (GET /plan -> 412), view taken from its manifest settings. */
function routes(view: string, extra: Record<string, unknown> = {}) {
  return {
    'GET /api/presets': makePresets(),
    'GET /api/characters/hero': { character: { id: 'hero', next_step: 'plan' }, manifest: { settings: { view } }, status: { has_reference: true, has_plan: false, units: [] } },
    'GET /api/characters/hero/plan': apiError(412, 'no_plan', 'no plan'),
    'GET /api/characters/hero/identity': identity(['#C8281E']),
    'POST /api/characters/hero/plan': makePlanResponse(view === 'topdown' ? 'topdown' : 'side'),
    ...extra,
  }
}
const renderPage = (client?: ReturnType<typeof makeClient>) => renderRoute(<Plan />, '/c/hero/plan', '/c/:cid/plan', client)

describe('Plan', () => {
  it('hides direction and mirror controls for the side view', async () => {
    mockApi(routes('side'))
    renderPage()
    await screen.findByTestId('bundle-side-basic')
    expect(screen.queryByTestId('direction-controls')).not.toBeInTheDocument()
    expect(screen.queryByTestId('mirror-switch')).not.toBeInTheDocument()
    expect(screen.getByTestId('plan-estimate')).toHaveTextContent('생성할 액션 4개 · 4개 unit · 예상 약 6분')
  })

  it('shows them after choosing the topdown bundle and hides them again for a side bundle', async () => {
    mockApi(routes('side'))
    renderPage()
    await userEvent.click(await screen.findByTestId('bundle-topdown-rpg'))
    expect(screen.getByTestId('direction-controls')).toBeInTheDocument()
    expect(screen.getByTestId('mirror-switch')).toBeChecked()
    expect(screen.getByTestId('plan-estimate')).toHaveTextContent('15개 unit · 예상 약 22분 30초')
    expect(screen.getByTestId('plan-view')).toHaveTextContent('topdown')
  })

  it('shows direction controls from the start for a topdown character', async () => {
    mockApi(routes('topdown'))
    renderPage()
    expect(await screen.findByTestId('direction-controls')).toBeInTheDocument()
    expect(screen.getByTestId('bundle-topdown-rpg')).toBeChecked()
  })

  it('POSTs the topdown directions and mirror=true by default', async () => {
    const fetchMock = mockApi(routes('topdown'))
    renderPage()
    await userEvent.click(await screen.findByTestId('plan-save'))
    await waitFor(() => expect(fetchMock.mock.calls.some(([, i]) => i?.method === 'POST')).toBe(true))
    expect(lastBody(fetchMock, 'POST', '/api/characters/hero/plan')).toEqual({
      bundle: 'topdown-rpg', cell: '128x128', set: [], view: 'topdown', directions: ['down', 'up', 'right', 'left'], mirror: true,
    })
  })

  it('reflects the mirror switch and an unchecked direction in the POST body', async () => {
    const fetchMock = mockApi(routes('topdown'))
    renderPage()
    await userEvent.click(await screen.findByTestId('mirror-switch'))
    expect(screen.getByTestId('mirror-off-note')).toHaveTextContent('예상 시간이 늘어납니다')
    expect(screen.getByTestId('plan-estimate')).toHaveTextContent('20개 unit')
    await userEvent.click(screen.getByTestId('direction-up'))
    await userEvent.click(screen.getByTestId('plan-save'))
    await waitFor(() => expect(fetchMock.mock.calls.some(([, i]) => i?.method === 'POST')).toBe(true))
    expect(lastBody(fetchMock, 'POST', '/api/characters/hero/plan')).toMatchObject({ directions: ['down', 'right', 'left'], mirror: false })
  })

  it('sends edited frames through --set and explicit actions when the selection leaves the bundle', async () => {
    const fetchMock = mockApi(routes('side'))
    renderPage()
    await userEvent.click(await screen.findByTestId('action-check-run')) // uncheck run -> custom
    expect(screen.getByTestId('bundle-custom')).toBeChecked()
    await userEvent.click(screen.getByTestId('action-toggle-walk'))
    const frames = screen.getByTestId('action-frames-walk')
    await userEvent.clear(frames)
    await userEvent.type(frames, '8')
    expect(screen.getByTestId('action-frames-walk')).toHaveValue(8)
    await userEvent.click(screen.getByTestId('plan-save'))
    await waitFor(() => expect(fetchMock.mock.calls.some(([, i]) => i?.method === 'POST')).toBe(true))
    expect(lastBody(fetchMock, 'POST', '/api/characters/hero/plan')).toMatchObject({ actions: ['idle', 'walk', 'attack'], set: ['walk.frames=8'], view: 'side' })
  })

  it('offers a generation method per action: breathe is POSTed, video is disabled with its reason', async () => {
    const fetchMock = mockApi(routes('side'))
    renderPage()
    await userEvent.click(await screen.findByTestId('action-toggle-idle'))
    expect(screen.getByTestId('action-method-idle')).toHaveTextContent('격자')
    expect(screen.getByTestId('action-method-video-hint')).toHaveTextContent('동영상 API가 연결되지 않았습니다')
    await userEvent.click(screen.getByTestId('action-method-idle'))
    expect(await screen.findByRole('option', { name: '동영상 (API)' })).toHaveAttribute('aria-disabled', 'true')
    await userEvent.click(screen.getByRole('option', { name: '호흡 (정지 1장)' }))
    expect(screen.getByTestId('action-grid-idle')).toBeDisabled() // a still is always 1x1
    expect(screen.getByTestId('action-frames-idle')).toHaveValue(6)
    await userEvent.click(screen.getByTestId('plan-save'))
    await waitFor(() => expect(fetchMock.mock.calls.some(([, i]) => i?.method === 'POST')).toBe(true))
    expect(lastBody(fetchMock, 'POST', '/api/characters/hero/plan').set).toContain('idle.method=breathe')
  })

  it('warns when a character colour conflicts with the magenta key colour', async () => {
    mockApi(routes('side', { 'GET /api/characters/hero/identity': identity(['#E000E0']) }))
    renderPage()
    expect(await screen.findByTestId('key-color-alert')).toHaveTextContent('green')
  })

  it('does not warn without a conflict', async () => {
    mockApi(routes('side'))
    renderPage()
    await screen.findByTestId('bundle-side-basic')
    expect(screen.queryByTestId('key-color-alert')).not.toBeInTheDocument()
  })

  it('saves an existing plan with PUT (mirror off, view kept) and goes to the studio', async () => {
    const stored = makePlanResponse('topdown')
    const fetchMock = mockApi(routes('topdown', {
      'GET /api/characters/hero/plan': stored,
      'PUT /api/characters/hero/plan': stored,
    }))
    renderPage()
    await userEvent.click(await screen.findByTestId('mirror-switch'))
    expect(screen.getByTestId('plan-view')).toBeDisabled()
    await userEvent.click(screen.getByTestId('plan-continue'))

    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/c/hero/studio/idle'))
    const body = lastBody(fetchMock, 'PUT', '/api/characters/hero/plan')
    expect(body.plan.mirror).toEqual({})
    expect(body.plan.directions).toEqual(['down', 'up', 'right', 'left'])
    expect(body.plan.view).toBe('topdown')
    expect(body.plan.order).toEqual(['idle', 'walk'])
    expect(fetchMock.mock.calls.some(([, i]) => i?.method === 'POST')).toBe(false)
  })

  it('stores the saved plan in the query cache', async () => {
    mockApi(routes('side'))
    const client = makeClient()
    renderPage(client)
    await userEvent.click(await screen.findByTestId('plan-save'))
    await waitFor(() => expect(client.getQueryData(qk.plan('hero'))).toBeDefined())
    expect(within(document.body).getByTestId('plan-save')).toBeEnabled()
  })
})
