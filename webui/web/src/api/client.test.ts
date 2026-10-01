import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, api } from './client'

afterEach(() => vi.unstubAllGlobals())

const stubFetch = (res: Response | Error) =>
  vi.stubGlobal('fetch', vi.fn(() => (res instanceof Error ? Promise.reject(res) : Promise.resolve(res))))

describe('api client error normalization', () => {
  it('parses the server error JSON into ApiError', async () => {
    stubFetch(new Response(
      JSON.stringify({ error: { code: 'precondition_failed', message: 'reference 이미지가 없습니다', detail: { missing: 'reference' } } }),
      { status: 412 },
    ))
    const err = await api('/api/x').catch((e) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(err).toMatchObject({ status: 412, code: 'precondition_failed', message: 'reference 이미지가 없습니다', detail: { missing: 'reference' } })
  })

  it('maps a non-JSON error body to http_<status>', async () => {
    stubFetch(new Response('<html>Bad Gateway</html>', { status: 502, statusText: 'Bad Gateway' }))
    const err = await api('/api/x').catch((e) => e)
    expect(err).toMatchObject({ status: 502, code: 'http_502', message: 'Bad Gateway' })
  })

  it('maps FastAPI 422 validation bodies', async () => {
    stubFetch(new Response(JSON.stringify({ detail: [{ msg: 'bad' }] }), { status: 422 }))
    const err = await api('/api/x').catch((e) => e)
    expect(err).toMatchObject({ status: 422, code: 'validation_error', detail: [{ msg: 'bad' }] })
  })

  it('rejects a 200 response that is not JSON', async () => {
    stubFetch(new Response('hello', { status: 200 }))
    await expect(api('/api/x')).rejects.toMatchObject({ code: 'invalid_response' })
  })

  it('turns a network failure into network_error with status 0', async () => {
    stubFetch(new TypeError('Failed to fetch'))
    const err = await api('/api/x').catch((e) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(err).toMatchObject({ status: 0, code: 'network_error' })
  })

  it('returns parsed JSON on success', async () => {
    stubFetch(new Response(JSON.stringify({ ok: 1 }), { status: 200 }))
    expect(await api('/api/x')).toEqual({ ok: 1 })
  })
})
