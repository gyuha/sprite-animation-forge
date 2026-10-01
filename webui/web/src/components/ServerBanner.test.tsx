import { act, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { setConnected } from '@/api/sse'
import { mockApi, renderWithClient } from '@/test-utils'
import { ServerBanner } from './ServerBanner'

const health = { ready: true, warnings: [], codex: { installed: true, version: '0.159.2', version_ok: true, logged_in: true, auth: null, image_generation: true }, python: {} }

afterEach(() => act(() => setConnected(true)))

describe('ServerBanner', () => {
  it('is hidden while the server answers and the event stream is up', async () => {
    mockApi({ 'GET /api/health': health })
    renderWithClient(<ServerBanner />)
    await new Promise((r) => setTimeout(r, 20))
    expect(screen.queryByTestId('server-unreachable-banner')).not.toBeInTheDocument()
  })

  it('appears when /api/health cannot be reached', async () => {
    vi.stubGlobal('fetch', () => Promise.reject(new TypeError('Failed to fetch')))
    renderWithClient(<ServerBanner />)
    expect(await screen.findByTestId('server-unreachable-banner')).toHaveTextContent('서버에 연결할 수 없습니다')
    expect(screen.getByTestId('server-unreachable-banner')).toHaveTextContent('자동으로 다시 연결')
  })

  it('appears while the event stream is down and disappears when it reconnects', async () => {
    mockApi({ 'GET /api/health': health })
    renderWithClient(<ServerBanner />)
    act(() => setConnected(false))
    expect(await screen.findByTestId('server-unreachable-banner')).toBeInTheDocument()
    act(() => setConnected(true))
    expect(screen.queryByTestId('server-unreachable-banner')).not.toBeInTheDocument()
  })
})
