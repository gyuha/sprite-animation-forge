import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { mockApi, renderWithClient } from '@/test-utils'
import Status from './Status'

const health = (over: { codex?: object; warnings?: string[]; python?: object } = {}) => ({
  ready: true, warnings: over.warnings ?? [],
  codex: { installed: true, version: '0.159.2', tested_version: '0.159.2', version_ok: true, logged_in: true, auth: 'ChatGPT', image_generation: true, codex_home: '/home/u/.codex', ...over.codex },
  python: over.python ?? { pillow: '11', numpy: '2', scipy: '1' },
})
const detail = (usage: object) => ({ character: { id: 'x', next_step: 'plan' }, manifest: { usage }, status: { has_reference: true, has_plan: false, units: [] } })
const card = (id: string) => ({ id, created_at: '', updated_at: '', settings: {}, has_reference: true, has_plan: true, units_total: 1, units_accepted: 0, next_step: 'generate' })

function routes(h: unknown) {
  return {
    'GET /api/health': h,
    'GET /api/jobs': { jobs: [] },
    'GET /api/characters': { characters: [card('hero'), card('slime')] },
    'GET /api/characters/hero': detail({ codex_calls: 7, input_tokens: 800000, cached_input_tokens: 700000, output_tokens: 5000 }),
    'GET /api/characters/slime': detail({ codex_calls: 3, input_tokens: 200000, cached_input_tokens: 100000, output_tokens: 1000 }),
  }
}

describe('Status', () => {
  it('marks failing doctor checks with the fix command and a copy button', async () => {
    const writeText = vi.fn(() => Promise.resolve())
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    mockApi(routes(health({ codex: { logged_in: false, auth: null }, warnings: ['codex_not_logged_in: run `codex login`'] })))
    renderWithClient(<Status />)
    const login = await screen.findByTestId('status-check-login')
    expect(login).toHaveAttribute('data-ok', 'false')
    expect(screen.getByTestId('status-fix-login')).toHaveTextContent('codex login')
    expect(screen.getByTestId('status-check-install')).toHaveAttribute('data-ok', 'true')
    expect(screen.queryByTestId('status-fix-install')).not.toBeInTheDocument()
    await userEvent.click(screen.getByTestId('status-copy-login'))
    expect(writeText).toHaveBeenCalledWith('codex login')
  })

  it('"다시 확인" bypasses the cache with refresh=1 and shows the new result', async () => {
    let calls = 0
    const fetchMock = mockApi({ ...routes(null), 'GET /api/health': () => health(calls++ === 0 ? { codex: { logged_in: false } } : {}) })
    renderWithClient(<Status />)
    expect(await screen.findByTestId('status-check-login')).toHaveAttribute('data-ok', 'false')
    expect(fetchMock.mock.calls.filter(([u]) => String(u).includes('refresh=1'))).toHaveLength(0)

    await userEvent.click(screen.getByTestId('status-recheck'))
    await waitFor(() => expect(screen.getByTestId('status-check-login')).toHaveAttribute('data-ok', 'true'))
    expect(fetchMock.mock.calls.filter(([u]) => u === '/api/health?refresh=1')).toHaveLength(1)
  })

  it('suggests the contract test when the Codex version differs from the tested one', async () => {
    mockApi(routes(health({ codex: { version: '0.160.0' } })))
    renderWithClient(<Status />)
    expect(await screen.findByTestId('status-contract-hint')).toHaveTextContent('pytest -m live')
  })

  it('has no contract hint when the versions match', async () => {
    mockApi(routes(health()))
    renderWithClient(<Status />)
    await screen.findByTestId('status-check-login')
    expect(screen.queryByTestId('status-contract-hint')).not.toBeInTheDocument()
  })

  it('sums Codex usage per character and in total', async () => {
    mockApi(routes(health()))
    renderWithClient(<Status />)
    await waitFor(() => expect(screen.getByTestId('usage-row-slime')).toHaveTextContent('3'))
    expect(screen.getByTestId('usage-row-hero')).toHaveTextContent('800,000')
    expect(screen.getByTestId('usage-total')).toHaveTextContent('10')
    expect(screen.getByTestId('usage-total')).toHaveTextContent('1,000,000')
    expect(screen.getByTestId('usage-total')).toHaveTextContent('6,000')
  })
})
