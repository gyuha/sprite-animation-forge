import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { qk } from '@/api/queries'
import { makeClient, lastBody, mockApi, renderRoute } from '@/test-utils'
import { makeJob, makePlanResponse } from '@/test-fixtures'
import Studio from './Studio'

const ROUTE = '/c/:cid/studio/:action?/:direction?'
const params = {
  anchor: 'feet', x_anchor: 'mass', scale_strategy: 'fit',
  background: { t_in: 30, t_out: 90, despill: true, edge_band_px: 2 },
  components: { mode: 'largest', merge_gap_px: 13 }, margin: { top: 8, side: 8, bottom: 10 },
}
const derived = {
  baseline_y: 118, row_boundaries: [0, 100, 200], col_boundaries: [[0, 100, 200], [0, 100, 200]],
  frames: [{ index: 0, cell: [0, 0, 100, 100], bbox: [10, 10, 90, 90], anchor: [50, 90] }],
}
const recs = [
  { type: 'reprocess', code: 'use_preserve', set: { scale_strategy: 'preserve' }, reason: 'fit 전략에서 body 축소', cost: '~2s' },
  { type: 'regenerate', code: 'character_small', reason: '재생성', cost: '~90s' },
  { type: 'force_accept', code: 'forced_accept', attempt: '002', cost: '0s' },
]
const frameUrls = (base: string, v: string) => [0, 1, 2, 3].map((i) => `/files/hero/${base}/frames/00${i}.png?v=${v}${i}`)
const files = (base: string, v = 'a') => ({
  raw: `/files/hero/${base}/raw.png?v=r`, clean: `/files/hero/${base}/clean.png?v=${v}`, sheet: `/files/hero/${base}/sheet.png?v=${v}`, prompt: null, frames: frameUrls(base, v),
})
const qcReport = (status: string, withRecs = true) => ({
  status, score: status === 'fail' ? 75 : 96,
  results: [{ id: 'QC-02', grade: 'pass', value: 0.042 }, { id: 'QC-07', grade: status === 'fail' ? 'fail' : 'pass', value: 0.81 }],
  recommendations: withRecs ? recs : [],
})
const summary = (attempt: string, over = {}) => ({ attempt, accepted: false, sheet: null, recovery: [], qc_status: 'fail', score: 75, ...over })

/** Routes for one unit; `unit` is the path below /files (idle or idle/down), `q` the attempts URL suffix handled by mockApi's query stripping. */
function unitRoutes(opts: { view?: 'side' | 'topdown'; qc?: string; attempts?: ReturnType<typeof summary>[]; unit?: string; path?: string; extra?: Record<string, unknown> } = {}) {
  const { view = 'side', qc = 'fail', unit = 'idle', path = '/api/characters/hero/actions/idle', extra = {} } = opts
  const attempts = opts.attempts ?? [summary('001', { qc_status: qc })]
  const rows = view === 'topdown'
    ? [{ unit: 'idle/down', action: 'idle', direction: 'down', state: 'accepted', accepted_attempt: '001', qc_status: 'pass' },
       { unit: 'idle/up', action: 'idle', direction: 'up', state: 'pending', accepted_attempt: null, qc_status: null },
       { unit: 'idle/right', action: 'idle', direction: 'right', state: 'accepted', accepted_attempt: '001', qc_status: 'pass' },
       { unit: 'idle/left', action: 'idle', direction: 'left', state: 'mirrored', accepted_attempt: '001', qc_status: null, mirror_of: 'idle/right' }]
    : [{ unit: 'idle', action: 'idle', direction: null, state: 'processed', accepted_attempt: null, qc_status: qc }]
  return {
    'GET /api/characters/hero/plan': makePlanResponse(view),
    'GET /api/characters/hero': { character: { id: 'hero', next_step: 'generate' }, manifest: {}, status: { has_reference: true, has_plan: true, units: rows } },
    'GET /api/health': { ready: true, warnings: [], codex: {}, python: {} },
    'GET /api/jobs': { jobs: [] },
    [`GET ${path}/attempts`]: { action: 'idle', direction: null, unit, mirror_of: null, accepted_attempt: null, attempts },
    [`GET ${path}/attempts/001`]: {
      attempt: '001', unit, accepted: false, summary: attempts[0], generation: null, process: { params, derived }, qc: qcReport(qc), files: files(`${unit}/attempts/001`),
    },
    ...extra,
  }
}
const calls = (fetchMock: ReturnType<typeof mockApi>, method: string) =>
  fetchMock.mock.calls.filter(([, i]) => (i?.method ?? 'GET') === method).map(([u]) => String(u))
const renderStudio = (path: string, client = makeClient()) => renderRoute(<Studio />, path, ROUTE, client)
const canvas = () => screen.findByTestId('preview-canvas')

describe('Studio direction tabs', () => {
  it('has none for a single-direction plan and sends no ?direction=', async () => {
    const fetchMock = mockApi(unitRoutes())
    renderStudio('/c/hero/studio/idle')
    await canvas()
    expect(screen.getByTestId('action-tab-walk')).toBeInTheDocument()
    expect(screen.queryByTestId('direction-tabs')).not.toBeInTheDocument()
    expect(calls(fetchMock, 'GET').filter((u) => u.includes('direction'))).toEqual([])
  })

  it('shows them for 2+ directions, opens the representative one and puts ?direction= on every action call', async () => {
    const fetchMock = mockApi(unitRoutes({
      view: 'topdown', unit: 'idle/down', path: '/api/characters/hero/actions/idle',
      extra: { 'POST /api/characters/hero/actions/idle/generate': { job: makeJob({ direction: 'down' }), attempt: null } },
    }))
    renderStudio('/c/hero/studio/idle')
    expect(await screen.findByTestId('direction-tabs')).toBeInTheDocument()
    for (const d of ['down', 'up', 'right', 'left']) expect(screen.getByTestId(`direction-tab-${d}`)).toBeInTheDocument()
    expect(screen.getByTestId('direction-tab-down')).toHaveAttribute('data-state', 'active')
    expect(screen.getByTestId('direction-tab-left')).toHaveAttribute('data-icon', '↔')
    await canvas()
    const gets = calls(fetchMock, 'GET').filter((u) => u.includes('/actions/idle/'))
    expect(gets.length).toBeGreaterThan(1)
    expect(gets.every((u) => u.endsWith('?direction=down'))).toBe(true)

    await userEvent.click(screen.getByTestId('generate-button'))
    await waitFor(() => expect(calls(fetchMock, 'POST')).toEqual(['/api/characters/hero/actions/idle/generate?direction=down']))
    expect(lastBody(fetchMock, 'POST', '/api/characters/hero/actions/idle/generate')).toEqual({ extra: null, recovery: [] })
    expect(await screen.findByTestId('job-job_1')).toBeInTheDocument()
  })

  it('mirror-derived left: generation, upload, reprocess and accept are disabled with a reason and the flipped frames are shown read-only', async () => {
    mockApi(unitRoutes({
      view: 'topdown', attempts: [],
      extra: { 'GET /api/characters/hero/actions/idle/attempts': { action: 'idle', direction: 'left', unit: 'idle/left', mirror_of: 'idle/right', accepted_attempt: null, attempts: [] } },
    }))
    renderStudio('/c/hero/studio/idle/left')
    expect(await screen.findByTestId('mirror-notice')).toHaveTextContent('우측면을 좌우반전한 결과입니다')
    const player = await canvas()
    expect(player).toHaveAttribute('data-frame-count', '4')
    for (const id of ['generate-button', 'upload-button', 'prompt-button', 'accept-button', 'reprocess-save']) {
      if (id === 'reprocess-save') await userEvent.click(screen.getByTestId('reprocess-toggle'))
      const el = screen.getByTestId(id)
      expect(el, id).toBeDisabled()
    }
    expect(screen.getByTestId('generate-button').closest('[data-reason]')).toHaveAttribute('data-reason', expect.stringContaining('좌우반전'))
    expect(screen.getByTestId('accept-button').closest('[data-reason]')).toBeInTheDocument()
    expect(screen.queryByTestId('qc-panel')).not.toBeInTheDocument()
  })
})

describe('Studio vision review', () => {
  const review = { schema_version: 1, attempt: '001', unit: 'idle', frames: 4, review: {
    loop: { ok: true, note: '이어짐' }, limbs: { ok: true, note: '번갈아 움직임' }, identity: { ok: true, note: '일치' }, overall: 'pass', summary: '자연스럽습니다.' } }

  it('starts the advisory review as a Job for the selected attempt', async () => {
    const fetchMock = mockApi(unitRoutes({ extra: { 'POST /api/characters/hero/actions/idle/attempts/001/review': { job: makeJob({ type: 'vision_review', direction: null }), attempt: null } } }))
    renderStudio('/c/hero/studio/idle')
    await userEvent.click(await screen.findByTestId('vision-review-button'))
    await waitFor(() => expect(calls(fetchMock, 'POST')).toEqual(['/api/characters/hero/actions/idle/attempts/001/review']))
    expect(await screen.findByTestId('job-job_1')).toHaveTextContent('비전 심사')
  })

  it('shows a saved review from the attempt detail', async () => {
    const base = unitRoutes()
    const detail = base['GET /api/characters/hero/actions/idle/attempts/001'] as Record<string, unknown>
    mockApi({ ...base, 'GET /api/characters/hero/actions/idle/attempts/001': { ...detail, vision_review: review } })
    renderStudio('/c/hero/studio/idle')
    expect(await screen.findByTestId('vision-review-overall')).toHaveAttribute('data-overall', 'pass')
    expect(screen.getByTestId('vision-review-summary')).toHaveTextContent('자연스럽습니다.')
  })

  it('is not offered for a mirror-derived direction', async () => {
    mockApi(unitRoutes({
      view: 'topdown', attempts: [],
      extra: { 'GET /api/characters/hero/actions/idle/attempts': { action: 'idle', direction: 'left', unit: 'idle/left', mirror_of: 'idle/right', accepted_attempt: null, attempts: [] } },
    }))
    renderStudio('/c/hero/studio/idle/left')
    await canvas()
    expect(screen.queryByTestId('vision-review-button')).not.toBeInTheDocument()
  })
})

describe('Studio shortcuts', () => {
  it('Space toggles playback and arrows step frames, but typing in the extra-instruction textarea triggers nothing', async () => {
    const fetchMock = mockApi(unitRoutes({ qc: 'pass' }))
    renderStudio('/c/hero/studio/idle')
    const player = await canvas()
    expect(player).toHaveAttribute('data-playing', 'true')
    await userEvent.keyboard(' ')
    await waitFor(() => expect(player).toHaveAttribute('data-playing', 'false'))
    // the rAF clock may already have advanced before the pause under load, so step relative to the paused frame
    const paused = Number(player.getAttribute('data-frame'))
    const count = Number(player.getAttribute('data-frame-count'))
    const stepped = String((paused + 1) % count)
    await userEvent.keyboard('{ArrowRight}')
    await waitFor(() => expect(player).toHaveAttribute('data-frame', stepped))

    await userEvent.click(screen.getByTestId('extra-input'))
    await userEvent.keyboard(' g a o{ArrowLeft}')
    await waitFor(() => expect(screen.getByTestId('extra-input')).toHaveValue(' g a o'))
    await waitFor(() => expect(screen.getByTestId('extra-count')).toHaveTextContent('6 / 500'))
    await new Promise((r) => setTimeout(r, 50)) // let the rAF player settle before asserting that nothing happened
    expect(player).toHaveAttribute('data-playing', 'false') // space typed in the textarea did not toggle
    expect(player).toHaveAttribute('data-frame', stepped) // nor did the arrow key
    expect(player).toHaveAttribute('data-overlays', '') // 'o' did not toggle onion
    expect(calls(fetchMock, 'POST')).toEqual([]) // 'g' did not start a generation, 'a' did not accept
  })

  it('G starts a generation and A accepts (through the confirmation) when focus is on the page', async () => {
    const fetchMock = mockApi(unitRoutes({ extra: { 'POST /api/characters/hero/actions/idle/generate': { job: makeJob({ direction: null }), attempt: null } } }))
    renderStudio('/c/hero/studio/idle')
    await canvas()
    await waitFor(() => expect(screen.getByTestId('generate-button')).toBeEnabled())
    await userEvent.keyboard('a')
    expect(await screen.findByTestId('accept-confirm')).toBeInTheDocument() // QC failed: confirmation first
    await userEvent.click(screen.getByTestId('accept-cancel'))
    await waitFor(() => expect(screen.queryByTestId('accept-confirm')).not.toBeInTheDocument())
    await userEvent.keyboard('g')
    await waitFor(() => expect(calls(fetchMock, 'POST')).toEqual(['/api/characters/hero/actions/idle/generate']))
  })
})

describe('Studio actions', () => {
  it('accepting a QC-failed attempt asks first and then POSTs force:true', async () => {
    const fetchMock = mockApi(unitRoutes({ extra: { 'POST /api/characters/hero/actions/idle/attempts/001/accept': { accepted: '001', unit: 'idle', forced: true, derived: [], scale_profile_updated: false, requalified_actions: [] } } }))
    renderStudio('/c/hero/studio/idle')
    await canvas()
    await userEvent.click(await screen.findByTestId('accept-button'))
    expect(calls(fetchMock, 'POST')).toEqual([])
    await userEvent.click(await screen.findByTestId('accept-confirm'))
    await waitFor(() => expect(calls(fetchMock, 'POST')).toEqual(['/api/characters/hero/actions/idle/attempts/001/accept']))
    expect(lastBody(fetchMock, 'POST', '/api/characters/hero/actions/idle/attempts/001/accept')).toEqual({ force: true })
  })

  it('the reprocess recommendation POSTs process with the set and refreshes the preview from the response', async () => {
    const processed = { attempt: '001', unit: 'idle', qc: qcReport('warn', false), files: files('idle/attempts/001', 'b'), derived }
    const fetchMock = mockApi(unitRoutes({
      extra: {
        'POST /api/characters/hero/actions/idle/attempts/001/process': processed,
      },
    }))
    renderStudio('/c/hero/studio/idle')
    const player = await canvas()
    const before = player.getAttribute('data-version')
    await userEvent.click(await screen.findByTestId('rec-reprocess-use_preserve'))
    await waitFor(() => expect(player.getAttribute('data-version')).not.toBe(before))
    expect(player.getAttribute('data-version')).toContain('b0') // preview now uses the new file hashes, from the response alone
    expect(lastBody(fetchMock, 'POST', '/api/characters/hero/actions/idle/attempts/001/process')).toEqual({
      set: { align: 'register', anchor: 'feet', x_anchor: 'mass', scale_strategy: 'preserve', components: 'largest', merge_gap_px: 13, t_in: 30, t_out: 90, despill: true, edge_band_px: 2, margin_top: 8, margin_side: 8, margin_bottom: 10 },
    })
    expect(screen.getByTestId('qc-status')).toHaveAttribute('data-status', 'warn')
    expect(calls(fetchMock, 'GET').filter((u) => u.endsWith('/attempts/001'))).toHaveLength(1) // no refetch needed
  })

  it('regenerate and force-accept recommendations hit generate (recovery code) and accept (force, recommended attempt)', async () => {
    const fetchMock = mockApi(unitRoutes({
      extra: {
        'POST /api/characters/hero/actions/idle/generate': { job: makeJob({ direction: null }), attempt: null },
        'POST /api/characters/hero/actions/idle/attempts/002/accept': { accepted: '002', unit: 'idle', forced: true, derived: [], scale_profile_updated: false, requalified_actions: [] },
      },
    }))
    renderStudio('/c/hero/studio/idle')
    await userEvent.type(await screen.findByTestId('extra-input'), '칼을 크게')
    await waitFor(() => expect(screen.getByTestId('rec-regenerate-character_small')).toBeEnabled())
    await userEvent.click(screen.getByTestId('rec-regenerate-character_small'))
    await waitFor(() => expect(calls(fetchMock, 'POST')).toEqual(['/api/characters/hero/actions/idle/generate']))
    expect(lastBody(fetchMock, 'POST', '/api/characters/hero/actions/idle/generate')).toEqual({ extra: '칼을 크게', recovery: ['character_small'] })
    await userEvent.click(screen.getByTestId('rec-force_accept-forced_accept'))
    await waitFor(() => expect(calls(fetchMock, 'POST')).toContain('/api/characters/hero/actions/idle/attempts/002/accept'))
    expect(lastBody(fetchMock, 'POST', '/api/characters/hero/actions/idle/attempts/002/accept')).toEqual({ force: true })
  })

  it('a slider change reprocesses after the debounce and the preview picks up the new hashes', async () => {
    const processed = { attempt: '001', unit: 'idle', qc: qcReport('pass', false), files: files('idle/attempts/001', 'c'), derived }
    const fetchMock = mockApi(unitRoutes({ extra: { 'POST /api/characters/hero/actions/idle/attempts/001/process': processed } }))
    renderStudio('/c/hero/studio/idle')
    const player = await canvas()
    const before = player.getAttribute('data-version')
    await userEvent.click(await screen.findByTestId('reprocess-toggle'))
    fireEvent.keyDown(within(screen.getByTestId('reprocess-margin_top')).getByRole('slider'), { key: 'ArrowRight' })
    expect(calls(fetchMock, 'POST')).toEqual([]) // debounced
    await waitFor(() => expect(calls(fetchMock, 'POST')).toHaveLength(1))
    expect(lastBody(fetchMock, 'POST', '/api/characters/hero/actions/idle/attempts/001/process').set).toMatchObject({ margin_top: 9, margin_side: 8 })
    await waitFor(() => expect(player.getAttribute('data-version')).not.toBe(before))
  })

  it('an interrupted attempt shows 중단됨 and can be regenerated', async () => {
    const interrupted = summary('001', { generation_status: 'interrupted', qc_status: null, score: null })
    const fetchMock = mockApi(unitRoutes({
      attempts: [interrupted],
      extra: {
        'GET /api/characters/hero/actions/idle/attempts/001': {
          attempt: '001', unit: 'idle', accepted: false, summary: interrupted, generation: null, process: null, qc: null,
          files: { raw: null, clean: null, sheet: null, prompt: null, frames: [] },
        },
        'POST /api/characters/hero/actions/idle/generate': { job: makeJob({ direction: null }), attempt: null },
      },
    }))
    renderStudio('/c/hero/studio/idle')
    expect(await screen.findByTestId('interrupted-badge-001')).toHaveTextContent('중단됨')
    expect(screen.getByTestId('interrupted-notice')).toBeInTheDocument()
    expect(screen.queryByTestId('preview-canvas')).not.toBeInTheDocument()
    await userEvent.click(screen.getByTestId('regenerate-button'))
    await waitFor(() => expect(calls(fetchMock, 'POST')).toEqual(['/api/characters/hero/actions/idle/generate']))
  })

  it('disables generation with a reason while Codex is not ready', async () => {
    mockApi(unitRoutes({ extra: { 'GET /api/health': { ready: false, warnings: ['not logged in'], codex: {}, python: {} } } }))
    renderStudio('/c/hero/studio/idle')
    await canvas()
    await waitFor(() => expect(screen.getByTestId('generate-button')).toBeDisabled())
    expect(screen.getByTestId('generate-button').closest('[data-reason]')).toHaveAttribute('data-reason', expect.stringContaining('Codex'))
  })

  it('shows the prompt in a dialog', async () => {
    const fetchMock = mockApi(unitRoutes({ extra: { 'POST /api/characters/hero/actions/idle/prompt': { prompt: 'PROMPT BODY', references_needed: ['character'], warnings: [] } } }))
    renderStudio('/c/hero/studio/idle')
    await userEvent.type(await screen.findByTestId('extra-input'), 'bigger')
    await userEvent.click(screen.getByTestId('prompt-button'))
    expect(await screen.findByTestId('prompt-text')).toHaveTextContent('PROMPT BODY')
    expect(lastBody(fetchMock, 'POST', '/api/characters/hero/actions/idle/prompt')).toEqual({ extra: 'bigger', recovery: [] })
  })

  it('selects the latest attempt after a generation finished', async () => {
    const client = makeClient()
    mockApi(unitRoutes({ attempts: [summary('001', { accepted: true, qc_status: 'pass' })] }))
    renderStudio('/c/hero/studio/idle', client)
    await screen.findByTestId('attempt-001')
    expect(screen.getByTestId('attempt-001')).toHaveAttribute('aria-pressed', 'true') // accepted one is the default
    client.setQueryData(qk.attempts('hero', 'idle'), { action: 'idle', direction: null, unit: 'idle', mirror_of: null, accepted_attempt: '001', attempts: [summary('001', { accepted: true }), summary('002')] })
    await waitFor(() => expect(screen.getByTestId('attempt-002')).toHaveAttribute('aria-pressed', 'true'))
  })
})
