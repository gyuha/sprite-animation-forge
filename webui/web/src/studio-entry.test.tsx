import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AppLayout from '@/components/AppLayout'
import Dashboard from '@/pages/Dashboard'
import Export from '@/pages/Export'
import { mockApi, renderWithClient } from '@/test-utils'

const base = {
  'GET /api/health': { ready: true, warnings: [], codex: {}, python: {} },
  'GET /api/jobs': { jobs: [] },
}
const card = (next_step: string, accepted: number) => ({
  id: 'hero', created_at: '', updated_at: '', settings: {}, has_reference: false, has_plan: true, units_total: 2, units_accepted: accepted, next_step,
})
const unit = (name: string) => ({ unit: name, action: name, direction: null, state: 'accepted', accepted_attempt: '001', qc_status: 'pass', score: 100, forced: false })
const detail = { character: { id: 'hero', next_step: 'export' }, manifest: {}, status: { has_reference: true, has_plan: true, units: [unit('idle'), unit('walk')] } }

describe('studio entry for completed characters', () => {
  it('Dashboard: a finished character still gets a studio button while the card keeps leading to export', async () => {
    mockApi({ ...base, 'GET /api/characters': { characters: [card('export', 2)] } })
    renderWithClient(<MemoryRouter><Dashboard /></MemoryRouter>)
    expect(await screen.findByTestId('character-studio-hero')).toHaveAttribute('href', '/c/hero/studio')
    expect(screen.getByTestId('character-studio-hero')).toHaveTextContent('스튜디오 열기')
    expect(screen.getByTestId('character-card-hero')).toHaveAttribute('href', '/c/hero/export')
  })

  it('Dashboard: the studio button is also there while generation is still pending', async () => {
    mockApi({ ...base, 'GET /api/characters': { characters: [card('generate', 0)] } })
    renderWithClient(<MemoryRouter><Dashboard /></MemoryRouter>)
    expect(await screen.findByTestId('character-studio-hero')).toHaveAttribute('href', '/c/hero/studio')
  })

  // AppLayout mounts the SSE hook and the toaster; jsdom has neither EventSource nor matchMedia
  beforeEach(() => {
    vi.stubGlobal('EventSource', class { close() {} addEventListener() {} onopen = null; onerror = null })
    vi.stubGlobal('matchMedia', () => ({ matches: false, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {} }))
  })

  const renderLayout = (path: string) =>
    renderWithClient(
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route element={<AppLayout />}>
            <Route path="/" element={<p>home</p>} />
            <Route path="/c/:cid/export" element={<p>export</p>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    )

  it('nav: only the character list is linked (no status, new-character or per-character links)', async () => {
    mockApi({ ...base, 'GET /api/characters': { characters: [] } })
    renderLayout('/c/hero/export')
    await screen.findByText('export')
    const nav = screen.getByRole('navigation')
    expect(nav).toHaveTextContent('캐릭터')
    expect(nav).not.toHaveTextContent('상태') // the status page is reached from the job tray's footer link
    expect(nav).not.toHaveTextContent('새 캐릭터')
    expect(screen.queryByTestId('nav-studio')).toBeNull()
    expect(screen.queryByTestId('nav-view')).toBeNull()
  })

  it('Export: the studio link is shown even when no unit is missing', async () => {
    mockApi({ 'GET /api/characters/hero': detail })
    renderWithClient(
      <MemoryRouter initialEntries={['/c/hero/export']}>
        <Routes><Route path="/c/:cid/export" element={<Export />} /></Routes>
      </MemoryRouter>,
    )
    expect(await screen.findByTestId('export-studio-link')).toHaveAttribute('href', '/c/hero/studio')
    expect(screen.queryByTestId('export-missing-alert')).toBeNull()
  })
})
