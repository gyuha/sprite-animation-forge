import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { makeJob } from '@/test-fixtures'
import { lastBody, makeClientWithJobs, mockApi, renderRoute } from '@/test-utils'
import Identity from './Identity'

const identity = {
  silhouette: 'small knight', body_ratio: 'stocky', head_ratio: '1:2.5', hair: '', face: 'visor', eyes: '', clothing: 'red hood',
  primary_colors: ['#C8281E', '#9A9CA0'], secondary_colors: ['#E8D2A8'], weapon: 'sword', accessories: ['pouch'],
  outline_style: 'dark', shading_style: 'cel', camera_angle: 'side view', orientation: 'facing right',
}
const profile = (extra = {}) => ({ profile: { schema_version: 1, source: 'codex-analysis', edited_by_user: false, identity, ...extra } })
const renderPage = (client?: ReturnType<typeof makeClientWithJobs>) => renderRoute(<Identity />, '/c/hero/identity', '/c/:cid/identity', client)

describe('Identity', () => {
  it('PUTs the edited identity and goes to the plan on "저장 후 다음"', async () => {
    const fetchMock = mockApi({
      'GET /api/characters/hero/identity': profile(),
      'PUT /api/characters/hero/identity': profile({ edited_by_user: true }),
    })
    renderPage()
    const silhouette = await screen.findByTestId('identity-field-silhouette')
    expect(silhouette).toHaveValue('small knight')
    await userEvent.clear(silhouette)
    await userEvent.type(silhouette, 'tall knight')
    await userEvent.type(screen.getByTestId('identity-field-accessories'), ', cape')
    await userEvent.click(screen.getByTestId('identity-secondary-colors-add'))
    await userEvent.click(screen.getByTestId('identity-save-next'))

    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/c/hero/plan'))
    expect(lastBody(fetchMock, 'PUT', '/api/characters/hero/identity')).toEqual({
      identity: { ...identity, silhouette: 'tall knight', accessories: ['pouch', 'cape'], secondary_colors: ['#E8D2A8', '#000000'] },
    })
  })

  it('disables saving while a colour is not #RRGGBB', async () => {
    mockApi({ 'GET /api/characters/hero/identity': profile() })
    renderPage()
    const first = await screen.findByTestId('identity-primary-colors-input-0')
    await userEvent.type(first, 'x')
    expect(screen.getByTestId('identity-save')).toBeDisabled()
    expect(screen.getByTestId('identity-save-next')).toBeDisabled()
  })

  it('shows a skeleton instead of the fields while the analyze job runs', async () => {
    mockApi({ 'GET /api/characters/hero/identity': profile() })
    renderPage(makeClientWithJobs([makeJob({ type: 'identity_analyze', character: 'hero', state: 'running', action: null, direction: null })]))
    expect(await screen.findByTestId('identity-skeleton')).toBeInTheDocument()
    expect(screen.queryByTestId('identity-field-silhouette')).not.toBeInTheDocument()
    expect(screen.getByTestId('identity-analyze')).toBeDisabled()
  })

  it('warns when a character colour is close to the magenta key colour', async () => {
    mockApi({ 'GET /api/characters/hero/identity': profile() })
    renderPage()
    expect(await screen.findByTestId('identity-key-color')).toHaveTextContent('충돌 없음')
    await userEvent.click(screen.getByTestId('identity-secondary-colors-add'))
    const added = screen.getByTestId('identity-secondary-colors-input-1')
    await userEvent.clear(added)
    await userEvent.type(added, '#E000E0')
    expect(screen.getByTestId('identity-key-color')).toHaveTextContent('green')
  })
})
