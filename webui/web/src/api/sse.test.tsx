import { act } from '@testing-library/react'
import { renderHook } from '@testing-library/react'
import { QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { makeClient } from '@/test-utils'
import { makeJob } from '@/test-fixtures'
import { qk } from './queries'
import { BACKOFF_MAX_MS, BACKOFF_START_MS, useJobEvents, type JobSnapshot } from './sse'

class FakeEventSource {
  static CLOSED = 2
  static instances: FakeEventSource[] = []
  readyState = 0
  onopen: (() => void) | null = null
  onerror: (() => void) | null = null
  listeners: Record<string, ((e: MessageEvent) => void)[]> = {}
  url: string
  constructor(url: string) { this.url = url; FakeEventSource.instances.push(this) }
  addEventListener(type: string, fn: (e: MessageEvent) => void) { (this.listeners[type] ??= []).push(fn) }
  close() { this.readyState = FakeEventSource.CLOSED }
  open() { this.readyState = 1; this.onopen?.() }
  emit(data: object) { this.listeners.job?.forEach((fn) => fn({ data: JSON.stringify(data) } as MessageEvent)) }
  fail() { this.readyState = FakeEventSource.CLOSED; this.onerror?.() }
}

const flush = () => act(async () => { await Promise.resolve() })
let fetchMock: ReturnType<typeof vi.fn>

function setup(active: JobSnapshot[] = []) {
  fetchMock = vi.fn(() => Promise.resolve(new Response(JSON.stringify({ jobs: active }))))
  vi.stubGlobal('fetch', fetchMock)
  const client = makeClient()
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>
  const hook = renderHook(() => useJobEvents(), { wrapper })
  return { client, hook, es: () => FakeEventSource.instances.at(-1)! }
}

beforeEach(() => {
  FakeEventSource.instances = []
  vi.stubGlobal('EventSource', FakeEventSource)
  vi.useFakeTimers()
})
afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('useJobEvents', () => {
  it('connects to /api/events and upserts job snapshots (kind/line stripped, log kept)', () => {
    const { client, es } = setup()
    expect(es().url).toBe('/api/events')
    const existing = makeJob({ log: [{ t: 't', level: 'info', text: 'hi' }] })
    client.setQueryData(qk.jobs, [existing])
    act(() => es().emit({ ...existing, log: undefined, stage: 'generating', kind: 'stage', message: '이미지 생성 중' }))
    act(() => es().emit({ ...makeJob({ id: 'job_2', state: 'queued', queue_position: 1 }), kind: 'state', line: { t: 'x', level: 'info', text: 'y' } }))
    const jobs = client.getQueryData<JobSnapshot[]>(qk.jobs)!
    expect(jobs).toHaveLength(2)
    expect(jobs[0]).toMatchObject({ id: 'job_1', stage: 'generating', message: '이미지 생성 중' })
    expect(jobs[0].log).toHaveLength(1)
    expect(jobs[1]).not.toHaveProperty('kind')
    expect(jobs[1]).not.toHaveProperty('line')
  })

  it('invalidates the character attempts and manifest queries when a job succeeds', () => {
    const { client, es } = setup()
    client.setQueryData(qk.attempts('hero', 'idle', 'right'), {})
    client.setQueryData(qk.character('hero'), {})
    client.setQueryData(qk.plan('hero'), {})
    client.setQueryData(qk.attempts('other', 'idle'), {})
    act(() => es().emit({ ...makeJob({ state: 'running' }), kind: 'state' }))
    expect(client.getQueryState(qk.attempts('hero', 'idle', 'right'))!.isInvalidated).toBe(false)
    act(() => es().emit({ ...makeJob({ state: 'succeeded' }), kind: 'state' }))
    expect(client.getQueryState(qk.attempts('hero', 'idle', 'right'))!.isInvalidated).toBe(true)
    expect(client.getQueryState(qk.character('hero'))!.isInvalidated).toBe(true)
    expect(client.getQueryState(qk.plan('hero'))!.isInvalidated).toBe(false)
    expect(client.getQueryState(qk.attempts('other', 'idle'))!.isInvalidated).toBe(false)
  })

  it('resyncs via /api/jobs?active=1 on open and replaces stale active jobs', async () => {
    const { client, es } = setup([makeJob({ id: 'job_9', state: 'running' })])
    client.setQueryData(qk.jobs, [makeJob({ id: 'job_old', state: 'running' }), makeJob({ id: 'job_done', state: 'failed' })])
    es().open()
    await flush()
    expect(fetchMock).toHaveBeenCalledWith('/api/jobs?active=1', undefined)
    expect(client.getQueryData<JobSnapshot[]>(qk.jobs)!.map((j) => j.id)).toEqual(['job_done', 'job_9'])
  })

  it('reconnects with exponential backoff after the stream is closed, then resyncs', async () => {
    const { es } = setup()
    es().open()
    await flush()
    fetchMock.mockClear()
    const first = es()

    first.fail()
    expect(FakeEventSource.instances).toHaveLength(1)
    act(() => { vi.advanceTimersByTime(BACKOFF_START_MS) })
    expect(FakeEventSource.instances).toHaveLength(2)

    es().fail() // second failure: delay doubled
    act(() => { vi.advanceTimersByTime(BACKOFF_START_MS) })
    expect(FakeEventSource.instances).toHaveLength(2)
    act(() => { vi.advanceTimersByTime(BACKOFF_START_MS) })
    expect(FakeEventSource.instances).toHaveLength(3)

    es().open()
    await flush()
    expect(fetchMock).toHaveBeenCalledWith('/api/jobs?active=1', undefined)
    expect(BACKOFF_MAX_MS).toBeGreaterThan(BACKOFF_START_MS)
  })

  it('leaves browser-managed retries alone (readyState CONNECTING) and closes on unmount', () => {
    const { es, hook } = setup()
    const s = es()
    s.readyState = 0
    s.onerror?.()
    act(() => { vi.advanceTimersByTime(BACKOFF_MAX_MS) })
    expect(FakeEventSource.instances).toHaveLength(1)
    hook.unmount()
    expect(s.readyState).toBe(FakeEventSource.CLOSED)
  })
})
