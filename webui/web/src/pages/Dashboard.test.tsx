import { MemoryRouter } from 'react-router-dom'
import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { mockApi } from '@/test-utils'
import { renderWithClient } from '@/test-utils'
import Dashboard from './Dashboard'

const health = (ready: boolean) => ({
  ready, warnings: ready ? [] : ['codex: not logged in'],
  codex: { installed: true, version: '0.1', version_ok: true, logged_in: ready, auth: null, image_generation: true }, python: {},
})
const card = (id: string, over = {}) => ({
  id, created_at: '', updated_at: '', settings: {}, has_reference: true, has_plan: true, units_total: 4, units_accepted: 3, next_step: 'generate', ...over,
})

const renderDashboard = () => renderWithClient(<MemoryRouter><Dashboard /></MemoryRouter>)

describe('Dashboard', () => {
  it('renders a card per character with progress and next step, no banner when Codex is ready', async () => {
    mockApi({
      'GET /api/health': health(true),
      'GET /api/characters': { characters: [card('hero'), card('slime', { units_accepted: 5, units_total: 5, next_step: 'export' }), card('npc1', { has_plan: false, units_total: 0, units_accepted: 0, next_step: 'plan' })] },
    })
    renderDashboard()
    expect(await screen.findByTestId('character-card-hero')).toHaveTextContent('3/4')
    expect(screen.getByTestId('character-card-hero')).toHaveAttribute('href', '/c/hero/studio')
    expect(screen.getByTestId('character-next-slime')).toHaveTextContent('내보내기')
    expect(screen.getByTestId('character-card-npc1')).toHaveAttribute('href', '/c/npc1/plan')
    expect(screen.getByTestId('character-progress-hero')).toBeInTheDocument()
    expect(screen.queryByTestId('codex-not-ready-banner')).not.toBeInTheDocument()
    expect(screen.getByTestId('new-character-button')).toHaveAttribute('href', '/new')
  })

  it('shows the warning banner with the doctor warnings when Codex is not ready', async () => {
    mockApi({ 'GET /api/health': health(false), 'GET /api/characters': { characters: [card('hero')] } })
    renderDashboard()
    const banner = await screen.findByTestId('codex-not-ready-banner')
    expect(banner).toHaveTextContent('codex: not logged in')
    expect(banner).toHaveTextContent('codex login')
    expect(screen.getByTestId('copy-codex-login')).toBeInTheDocument()
  })

  it('shows the empty state when there are no characters', async () => {
    mockApi({ 'GET /api/health': health(true), 'GET /api/characters': { characters: [] } })
    renderDashboard()
    expect(await screen.findByTestId('dashboard-empty')).toHaveTextContent('끌어다 놓거나')
  })
})
