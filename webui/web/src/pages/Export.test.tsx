import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { apiError, mockApi, renderRoute, renderWithClient } from '@/test-utils'
import Export from './Export'

const unit = (name: string, over: Record<string, unknown> = {}) => ({
  unit: name, action: name.split('/')[0], direction: name.includes('/') ? name.split('/')[1] : null,
  state: 'accepted', accepted_attempt: '001', qc_status: 'pass', score: 100, forced: false, ...over,
})
const detail = (units: object[], exports?: object) => ({
  character: { id: 'hero', next_step: 'export' }, manifest: { exports }, status: { has_reference: true, has_plan: true, units },
})
const exported = { phaser: { exported_at: '2026-10-01T00:00:00Z', files: { 'atlas/hero.png': 'sha256:abcdef0123456789', 'atlas/hero.json': 'sha256:1', 'animations.json': 'sha256:2' } } }
const meta = {
  cell: { w: 128, h: 128 }, origin: { x: 0.5, y: 0.921875 }, padding: 2, baseline_y: 118,
  actions: [
    { name: 'idle', direction: null, unit: 'idle', row: 0, frames: 4 },
    { name: 'walk', direction: null, unit: 'walk', row: 1, frames: 6 },
  ],
  texture: { file: 'hero.png', sha256: 'x', size: [782, 266] },
}
const routes = (units: object[], exp?: object, extra: Record<string, unknown> = {}) => ({
  'GET /api/characters/hero': detail(units, exp),
  'GET /files/hero/atlas/hero.meta.json': meta,
  ...extra,
})
const renderPage = () => renderRoute(<Export />, '/c/hero/export', '/c/:cid/export')
const bothAccepted = [unit('idle'), unit('walk')]

describe('Export', () => {
  it('warns about units that are not accepted and links each to its studio page', async () => {
    mockApi(routes([unit('idle'), unit('walk/up', { state: 'processed', accepted_attempt: null, qc_status: 'fail' }), unit('run', { state: 'pending', accepted_attempt: null, qc_status: null })]))
    renderPage()
    const alert = await screen.findByTestId('export-missing-alert')
    expect(alert).toHaveTextContent('2개')
    expect(screen.getByTestId('export-missing-link-walk/up')).toHaveAttribute('href', '/c/hero/studio/walk/up')
    expect(screen.getByTestId('export-missing-link-run')).toHaveAttribute('href', '/c/hero/studio/run')
  })

  it('shows no missing-actions alert when every unit is accepted', async () => {
    mockApi(routes(bothAccepted))
    renderPage()
    await screen.findByTestId('export-qc-row-idle')
    expect(screen.queryByTestId('export-missing-alert')).not.toBeInTheDocument()
  })

  it('offers the ZIP as a plain download link once exported, a disabled button before', async () => {
    mockApi(routes(bothAccepted, exported))
    renderPage()
    const zip = await screen.findByTestId('export-zip')
    expect(zip).toHaveAttribute('href', '/api/characters/hero/export.zip')
    expect(zip).toHaveAttribute('download')
  })

  it('disables the ZIP button until an export exists', async () => {
    mockApi(routes(bothAccepted))
    renderPage()
    await screen.findByTestId('export-qc-row-idle')
    expect(screen.getByTestId('export-zip')).toBeDisabled()
    expect(screen.queryByTestId('atlas-preview')).not.toBeInTheDocument()
  })

  it('POSTs the export and renders files, atlas size and a label per atlas row', async () => {
    const fetchMock = mockApi(routes(bothAccepted, undefined, {
      'POST /api/characters/hero/export': { files: ['animations.json', 'atlas/hero.json', 'atlas/hero.png', 'preview/idle.gif'], warnings: ['missing_actions: ["run"]'] },
    }))
    renderPage()
    await userEvent.click(await screen.findByTestId('export-run'))
    expect(await screen.findByTestId('export-file-atlas/hero.png')).toHaveAttribute('href', '/files/hero/atlas/hero.png')
    expect(screen.getByTestId('export-file-preview/idle.gif')).toBeInTheDocument()
    expect(await screen.findByTestId('atlas-info')).toHaveTextContent('782 × 266px')
    expect(screen.getByTestId('atlas-row-label-walk')).toHaveTextContent('walk')
    expect(screen.getByTestId('atlas-row-label-walk').style.top).toBe(`${((2 + 130) / 266) * 100}%`)
    expect(screen.queryByTestId('export-warnings')).not.toBeInTheDocument() // missing_actions has its own alert
    expect(fetchMock.mock.calls.some(([u, i]) => u === '/api/characters/hero/export' && i?.method === 'POST')).toBe(true)
  })

  it('reports a failed export', async () => {
    mockApi(routes(bothAccepted, undefined, { 'POST /api/characters/hero/export': apiError(412, 'precondition_failed', 'nothing to export') }))
    renderPage()
    await userEvent.click(await screen.findByTestId('export-run'))
    await waitFor(() => expect(screen.getByTestId('export-run')).toBeEnabled())
    expect(screen.queryByTestId('export-files')).not.toBeInTheDocument()
  })

  it('fills the Phaser snippet with the character id and the origin of meta.json, with a copy button', async () => {
    mockApi(routes(bothAccepted, exported))
    renderPage()
    const snippet = await screen.findByTestId('phaser-snippet')
    expect(snippet).toHaveTextContent("this.load.atlas('hero', 'assets/hero/atlas/hero.png', 'assets/hero/atlas/hero.json')")
    expect(snippet).toHaveTextContent('hero.setOrigin(0.5, 0.921875)')
    expect(snippet).toHaveTextContent("hero.play('hero-idle')")
    expect(screen.getByTestId('phaser-copy')).toBeInTheDocument()
    await userEvent.click(screen.getByTestId('export-engine'))
    await userEvent.click(await screen.findByRole('option', { name: 'Generic' }))
    expect(screen.queryByTestId('phaser-snippet')).not.toBeInTheDocument()
    expect(screen.getByTestId('generic-note')).toHaveTextContent('hero.generic.json')
  })

  it('highlights forced accepts in the QC table', async () => {
    mockApi(routes([unit('idle'), unit('walk', { forced: true, qc_status: 'fail', score: 60 })]))
    renderPage()
    expect(await screen.findByTestId('export-qc-row-walk')).toHaveAttribute('data-forced', 'true')
    expect(screen.getByTestId('export-forced-badge-walk')).toHaveTextContent('강제 채택')
    expect(screen.getByTestId('export-qc-row-idle')).toHaveAttribute('data-forced', 'false')
    expect(screen.queryByTestId('export-forced-badge-idle')).not.toBeInTheDocument()
  })

  it('exports on arrival from the batch CTA when nothing is missing', async () => {
    const fetchMock = mockApi(routes(bothAccepted, undefined, { 'POST /api/characters/hero/export': { files: ['atlas/hero.png'], warnings: [] } }))
    renderWithClient(
      <MemoryRouter initialEntries={[{ pathname: '/c/hero/export', state: { autoExport: true } }]}>
        <Routes><Route path="/c/:cid/export" element={<Export />} /></Routes>
      </MemoryRouter>,
    )
    expect(await screen.findByTestId('export-file-atlas/hero.png')).toBeInTheDocument()
    expect(fetchMock.mock.calls.filter(([, i]) => i?.method === 'POST')).toHaveLength(1)
  })

  it('links to the animation viewer', async () => {
    mockApi(routes(bothAccepted))
    renderPage()
    const link = await screen.findByTestId('export-view-link')
    expect(link).toHaveAttribute('href', '/c/hero/view')
    expect(link).toHaveTextContent('애니메이션 보기')
  })
})
