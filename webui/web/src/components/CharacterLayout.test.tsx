import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { act, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { mockApi, renderWithClient } from '@/test-utils'
import CharacterLayout from './CharacterLayout'

const unit = (name: string, over: Record<string, unknown> = {}) => ({
  unit: name, action: name.split('/')[0], direction: null, state: 'accepted', accepted_attempt: '001', qc_status: 'pass', score: 100, forced: false, ...over,
})
const pending = (name: string) => unit(name, { state: 'pending', accepted_attempt: null, qc_status: null })
const detail = (units: object[]) => ({ character: { id: 'hero' }, manifest: {}, status: { has_reference: true, has_plan: true, units } })

function renderAt(path: string, units: object[]) {
  mockApi({ 'GET /api/characters/hero': detail(units) })
  return renderWithClient(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route element={<CharacterLayout />}>
          <Route path="/c/:cid/studio/:action?/:direction?" element={<p>studio</p>} />
          <Route path="/c/:cid/view" element={<p>view</p>} />
          <Route path="/c/:cid/export" element={<p>export</p>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
}
const all = [unit('idle'), unit('walk')]

describe('CharacterLayout', () => {
  it('renders the three tabs with their hrefs', async () => {
    renderAt('/c/hero/studio/idle', all)
    expect(screen.getByTestId('character-tabs')).toBeInTheDocument()
    expect(screen.getByTestId('tab-studio')).toHaveAttribute('href', '/c/hero/studio')
    expect(screen.getByTestId('tab-view')).toHaveAttribute('href', '/c/hero/view')
    await waitFor(() => expect(screen.getByTestId('tab-export')).toHaveAttribute('href', '/c/hero/export'))
    expect(screen.getByTestId('tab-studio')).toHaveTextContent('스튜디오')
    expect(screen.getByTestId('tab-view')).toHaveTextContent('애니메이션 보기')
    expect(screen.getByTestId('tab-export')).toHaveTextContent('내보내기')
  })

  it.each([
    ['/c/hero/studio/walk', 'tab-studio'],
    ['/c/hero/view', 'tab-view'],
    ['/c/hero/export', 'tab-export'],
  ])('marks the tab of %s as the selected one', async (path, selected) => {
    renderAt(path, all)
    await waitFor(() => expect(screen.getByTestId('tab-export')).toHaveAttribute('data-disabled', 'false'))
    for (const id of ['tab-studio', 'tab-view', 'tab-export']) {
      expect(screen.getByTestId(id)).toHaveAttribute('aria-selected', String(id === selected))
      expect(screen.getByTestId(id)).toHaveAttribute('data-state', id === selected ? 'active' : 'inactive')
    }
  })

  it('disables export with the n/m reason while a unit is not adopted, and does not navigate', async () => {
    renderAt('/c/hero/view', [unit('idle'), pending('walk'), pending('run')])
    const tab = await screen.findByTestId('tab-export')
    await waitFor(() => expect(tab.closest('[data-reason]')).toHaveAttribute('data-reason', '스튜디오에서 모든 유닛을 채택하면 활성화됩니다 (1/3)'))
    expect(tab).toHaveAttribute('data-disabled', 'true')
    expect(tab).not.toHaveAttribute('href')
    await userEvent.click(tab)
    expect(screen.getByText('view')).toBeInTheDocument()
    act(() => tab.closest<HTMLElement>('[data-reason]')!.focus())
    expect((await screen.findAllByText(/모든 유닛을 채택하면 활성화됩니다 \(1\/3\)/)).length).toBeGreaterThan(0)
  })

  it('enables export when every unit is adopted, mirror-derived ones included', async () => {
    renderAt('/c/hero/studio', [unit('idle/right'), unit('idle/left', { state: 'mirrored' })])
    await waitFor(() => expect(screen.getByTestId('tab-export')).toHaveAttribute('data-disabled', 'false'))
    expect(screen.getByTestId('tab-export')).toHaveAttribute('href', '/c/hero/export')
    await userEvent.click(screen.getByTestId('tab-export'))
    expect(await screen.findByText('export')).toBeInTheDocument()
  })

  it('keeps export disabled for a mirrored unit without an accepted attempt', async () => {
    renderAt('/c/hero/studio', [unit('idle/right'), unit('idle/left', { state: 'mirrored', accepted_attempt: null })])
    await waitFor(() => expect(screen.getByTestId('tab-export').closest('[data-reason]')).toHaveAttribute('data-reason', expect.stringContaining('(1/2)')))
    expect(screen.getByTestId('tab-export')).toHaveAttribute('data-disabled', 'true')
  })

  it('keeps export disabled with zero units and while loading', async () => {
    renderAt('/c/hero/studio', [])
    expect(screen.getByTestId('tab-export')).toHaveAttribute('data-disabled', 'true') // still loading: no flash of enabled
    await waitFor(() => expect(screen.getByTestId('tab-export').closest('[data-reason]')).toHaveAttribute('data-reason', expect.stringContaining('(0/0)')))
    expect(screen.getByTestId('tab-export')).toHaveAttribute('data-disabled', 'true')
  })
})
