import { screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { qk, type Health } from '@/api/queries'
import { makeClient, renderWithClient } from '@/test-utils'
import { CodexStatusBadge } from './CodexStatusBadge'

afterEach(() => vi.unstubAllGlobals())

const health = (ready: boolean): Health => ({
  ready,
  warnings: ready ? [] : ['codex_not_logged_in: run `codex login`'],
  codex: { installed: true, version: '0.159.0', version_ok: true, logged_in: ready, auth: null, image_generation: true },
  python: {},
})

function badgeWith(data?: Health) {
  const client = makeClient()
  if (data) client.setQueryData(qk.health, data)
  return renderWithClient(<CodexStatusBadge />, client)
}

describe('CodexStatusBadge', () => {
  it('shows ready', () => {
    badgeWith(health(true))
    expect(screen.getByText('Codex 준비됨')).toBeInTheDocument()
  })

  it('shows not ready', () => {
    badgeWith(health(false))
    expect(screen.getByText('Codex 미준비')).toBeInTheDocument()
  })

  it('shows loading while the first request is pending', () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})))
    badgeWith()
    expect(screen.getByText('Codex 확인 중')).toBeInTheDocument()
  })

  it('shows an error when /api/health fails', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new TypeError('down'))))
    badgeWith()
    expect(await screen.findByText('상태 확인 실패')).toBeInTheDocument()
  })
})
