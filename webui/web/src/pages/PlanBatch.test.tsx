import { act, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { qk } from '@/api/queries'
import { apiError, lastBody, makeClientWithJobs, mockApi, renderRoute } from '@/test-utils'
import { makeJob, makePlanResponse, makePresets } from '@/test-fixtures'
import Plan from './Plan'

const health = (ready: boolean) => ({ ready, warnings: [], codex: { installed: true, version: '0.159.2', version_ok: true, logged_in: ready, auth: null, image_generation: true }, python: {} })
const batchJob = (over: Parameters<typeof makeJob>[0] = {}) => makeJob({ id: 'job_b', type: 'batch_generate', action: null, direction: null, ...over })
const reviewResult = { units: [{ unit: 'idle', status: 'accepted', attempt: '001', qc_status: 'pass' }, { unit: 'walk', status: 'review', attempt: '001', qc_status: 'fail' }], accepted: 1, review: 1 }

function routes(extra: Record<string, unknown> = {}, ready = true) {
  return {
    'GET /api/presets': makePresets(),
    'GET /api/characters/hero': { character: { id: 'hero', next_step: 'generate' }, manifest: { settings: { view: 'side' } }, status: { has_reference: true, has_plan: true, units: [] } },
    'GET /api/characters/hero/plan': makePlanResponse('side'),
    'GET /api/characters/hero/identity': { profile: { identity: { primary_colors: ['#C8281E'], secondary_colors: [] } } },
    'GET /api/health': health(ready),
    'POST /api/characters/hero/generate-all': { job: batchJob({ state: 'queued', queue_position: 1, progress: { done: 0, total: 2, current: null } }), attempt: null },
    ...extra,
  }
}
const renderPage = (client = makeClientWithJobs([])) => renderRoute(<Plan />, '/c/hero/plan', '/c/:cid/plan', client)
const postCount = (fetchMock: ReturnType<typeof mockApi>, path: string) =>
  fetchMock.mock.calls.filter(([u, i]) => u === path && i?.method === 'POST').length

describe('Plan batch generation', () => {
  it('starts generate-all with auto_accept on and max_regenerations 1 by default, without re-saving an unchanged plan', async () => {
    const fetchMock = mockApi(routes())
    renderPage()
    expect(await screen.findByTestId('auto-accept-switch')).toBeChecked()
    expect(screen.getByTestId('max-regen-select')).toHaveTextContent('1회')
    await userEvent.click(screen.getByTestId('generate-all'))
    await waitFor(() => expect(postCount(fetchMock, '/api/characters/hero/generate-all')).toBe(1))
    expect(lastBody(fetchMock, 'POST', '/api/characters/hero/generate-all')).toEqual({ auto_accept: true, max_regenerations: 1 })
    expect(fetchMock.mock.calls.some(([, i]) => i?.method === 'PUT')).toBe(false)
    expect(await screen.findByTestId('batch-panel')).toHaveAttribute('data-state', 'queued')
  })

  it('sends auto_accept=false and the chosen max_regenerations', async () => {
    const fetchMock = mockApi(routes())
    renderPage()
    await userEvent.click(await screen.findByTestId('auto-accept-switch'))
    await userEvent.click(screen.getByTestId('max-regen-select'))
    await userEvent.click(await screen.findByRole('option', { name: '2회' }))
    await userEvent.click(screen.getByTestId('generate-all'))
    await waitFor(() => expect(postCount(fetchMock, '/api/characters/hero/generate-all')).toBe(1))
    expect(lastBody(fetchMock, 'POST', '/api/characters/hero/generate-all')).toEqual({ auto_accept: false, max_regenerations: 2 })
  })

  it('creates the plan first when none is saved yet', async () => {
    const fetchMock = mockApi(routes({
      'GET /api/characters/hero/plan': apiError(412, 'no_plan', 'no plan'),
      'POST /api/characters/hero/plan': makePlanResponse('side'),
    }))
    renderPage()
    await userEvent.click(await screen.findByTestId('generate-all'))
    await waitFor(() => expect(postCount(fetchMock, '/api/characters/hero/generate-all')).toBe(1))
    expect(postCount(fetchMock, '/api/characters/hero/plan')).toBe(1)
  })

  it('shows progress, the status text and a cancel button for the running batch', async () => {
    const fetchMock = mockApi(routes({ 'POST /api/jobs/job_b/cancel': { job: batchJob({ state: 'canceled' }) } }))
    renderPage(makeClientWithJobs([batchJob({ progress: { done: 2, total: 4, current: 'walk' } })]))
    expect(await screen.findByTestId('batch-status')).toHaveTextContent('hero: 2/4 · walk 생성 중')
    expect(screen.getByTestId('batch-progress')).toHaveAttribute('data-percent', '50')
    expect(screen.getByTestId('generate-all')).toBeDisabled()
    await userEvent.click(screen.getByTestId('job-cancel-job_b'))
    await waitFor(() => expect(postCount(fetchMock, '/api/jobs/job_b/cancel')).toBe(1))
    expect(await screen.findByTestId('batch-status')).toHaveTextContent('취소됨')
    expect(screen.queryByTestId('job-cancel-job_b')).not.toBeInTheDocument()
  })

  it('lists accepted vs 검토 필요 units and offers the way to the export when finished', async () => {
    mockApi(routes())
    renderPage(makeClientWithJobs([batchJob({ state: 'succeeded', progress: { done: 2, total: 2, current: null }, result: reviewResult })]))
    expect(await screen.findByTestId('batch-unit-idle')).toHaveAttribute('data-state', 'accepted')
    expect(screen.getByTestId('batch-unit-walk')).toHaveAttribute('data-state', 'review')
    expect(screen.getByTestId('batch-review-link-walk')).toHaveAttribute('href', '/c/hero/studio/walk')
    expect(screen.queryByTestId('batch-review-link-idle')).not.toBeInTheDocument()
    expect(screen.getByTestId('go-export')).toHaveAttribute('href', '/c/hero/export')
  })

  it('goes to the export by itself when a batch started here ends with nothing to review', async () => {
    mockApi(routes())
    const client = makeClientWithJobs([])
    renderPage(client)
    await userEvent.click(await screen.findByTestId('generate-all'))
    await screen.findByTestId('batch-panel')
    act(() => {
      client.setQueryData(qk.jobs, [batchJob({
        state: 'succeeded', progress: { done: 2, total: 2, current: null },
        result: { units: reviewResult.units.map((u) => ({ ...u, status: 'accepted' })), accepted: 2, review: 0 },
      })])
    })
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/c/hero/export'))
  })

  it('stays on the plan when a batch started here needs review', async () => {
    mockApi(routes())
    const client = makeClientWithJobs([])
    renderPage(client)
    await userEvent.click(await screen.findByTestId('generate-all'))
    await screen.findByTestId('batch-panel')
    act(() => {
      client.setQueryData(qk.jobs, [batchJob({ state: 'succeeded', progress: { done: 2, total: 2, current: null }, result: reviewResult })])
    })
    expect(await screen.findByTestId('go-export')).toBeInTheDocument()
    expect(screen.queryByTestId('location')).not.toBeInTheDocument()
  })

  it('shows 중단됨 for a batch interrupted by a server restart and can start it again', async () => {
    const fetchMock = mockApi(routes())
    renderPage(makeClientWithJobs([batchJob({ state: 'interrupted', progress: { done: 1, total: 4, current: 'walk' } })]))
    expect(await screen.findByTestId('batch-interrupted')).toHaveTextContent('중단됨')
    await userEvent.click(screen.getByTestId('batch-restart'))
    await waitFor(() => expect(postCount(fetchMock, '/api/characters/hero/generate-all')).toBe(1))
  })

  it('shows the failure card with the stderr tail behind "자세히"', async () => {
    mockApi(routes())
    renderPage(makeClientWithJobs([batchJob({ state: 'failed', error: { code: 'codex_failed', message: 'codex exited 1\nboom', detail: { stderr_tail: 'line1\nboom' } } })]))
    expect(await screen.findByTestId('job-failed')).toHaveTextContent('codex exited 1')
    expect(screen.queryByTestId('job-failed-details')).not.toBeInTheDocument()
    await userEvent.click(screen.getByTestId('job-failed-details-toggle'))
    expect(screen.getByTestId('job-failed-details')).toHaveTextContent('line1')
  })

  it('disables "전부 생성" with a reason while Codex is not ready', async () => {
    mockApi(routes({}, false))
    renderPage()
    await waitFor(() => expect(screen.getByTestId('generate-all')).toBeDisabled())
    expect(screen.getByTestId('generate-all').closest('[data-reason]')).toHaveAttribute('data-reason', expect.stringContaining('Codex'))
  })
})
