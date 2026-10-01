import { fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { qk } from '@/api/queries'
import { makeJob } from '@/test-fixtures'
import { lastBody, makeClient, mockApi, renderRoute } from '@/test-utils'
import NewCharacter from './NewCharacter'

const renderPage = (client?: Parameters<typeof renderRoute>[3]) => renderRoute(<NewCharacter />, '/new', '/new', client)

describe('NewCharacter', () => {
  beforeEach(() => {
    URL.createObjectURL = vi.fn(() => 'blob:preview')
    URL.revokeObjectURL = vi.fn()
  })

  it('validates the character id like the CLI and gates the create button', async () => {
    mockApi({ 'GET /api/characters': { characters: [] } })
    renderPage()
    const id = screen.getByTestId('new-character-id')
    const png = new File(['x'], 'hero.png', { type: 'image/png' })
    fireEvent.change(screen.getByTestId('dropzone-input'), { target: { files: [png] } })
    expect(id).toHaveValue('hero') // suggested from the file name
    expect(screen.getByTestId('create-from-image')).toBeEnabled()

    await userEvent.clear(id)
    await userEvent.type(id, 'My_Hero')
    expect(screen.getByTestId('new-character-id-error')).toHaveTextContent('영문 소문자')
    expect(screen.getByTestId('create-from-image')).toBeDisabled()
  })

  it('suggests -2 when the file name slug is already taken', async () => {
    mockApi({ 'GET /api/characters': { characters: [{ id: 'hero' }] } })
    const client = makeClient()
    client.setQueryData(qk.characters, [{ id: 'hero' }])
    renderPage(client)
    fireEvent.change(screen.getByTestId('dropzone-input'), { target: { files: [new File(['x'], 'hero.png', { type: 'image/png' })] } })
    expect(screen.getByTestId('new-character-id')).toHaveValue('hero-2')
  })

  it('creates the character, uploads the reference, starts the analysis and moves on to the plan', async () => {
    const fetchMock = mockApi({
      'GET /api/characters': { characters: [] },
      'POST /api/characters': { character: { id: 'hero', created_at: '', next_step: 'reference' } },
      'POST /api/characters/hero/reference': { reference: 'reference/source.png', bg_removed: true, files: {} },
      'POST /api/characters/hero/identity/analyze': { job: makeJob({ id: 'job_a', type: 'identity_analyze', character: 'hero', action: null, direction: null }) },
    })
    renderPage()
    fireEvent.change(screen.getByTestId('dropzone-input'), { target: { files: [new File(['x'], 'hero.png', { type: 'image/png' })] } })
    await userEvent.click(screen.getByTestId('create-from-image'))

    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/c/hero/plan'))
    expect(lastBody(fetchMock, 'POST', '/api/characters')).toEqual({ id: 'hero', view: 'side', art_style: 'project_native', asset_type: 'character' })
    const upload = fetchMock.mock.calls.find(([u]) => u === '/api/characters/hero/reference')![1]!.body as FormData
    expect((upload.get('file') as File).name).toBe('hero.png')
    expect(fetchMock.mock.calls.map(([u]) => u)).toContain('/api/characters/hero/identity/analyze')
  })
})
