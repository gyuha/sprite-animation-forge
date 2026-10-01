import { MemoryRouter } from 'react-router-dom'
import { act, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { qk } from '@/api/queries'
import { makeJob } from '@/test-fixtures'
import { makeClientWithJobs, renderWithClient } from '@/test-utils'
import { BatchNotifier } from './BatchNotifier'

const { toast } = vi.hoisted(() => ({
  toast: Object.assign(vi.fn(), { success: vi.fn(), warning: vi.fn(), error: vi.fn(), info: vi.fn() }),
}))
vi.mock('sonner', () => ({ toast, Toaster: () => null }))

const batch = (over = {}) => makeJob({ id: 'job_b', type: 'batch_generate', action: null, direction: null, progress: { done: 1, total: 2, current: 'walk' }, ...over })
const done = { state: 'succeeded', progress: { done: 2, total: 2, current: null }, result: { units: [{ unit: 'idle', status: 'accepted' }, { unit: 'walk', status: 'accepted' }] } } as const

function setup(jobs: ReturnType<typeof batch>[]) {
  const client = makeClientWithJobs(jobs)
  renderWithClient(<MemoryRouter><BatchNotifier /></MemoryRouter>, client)
  // Query Cache notifies its observers on a timer, so let it run
  return (next: ReturnType<typeof batch>[]) =>
    act(async () => {
      client.setQueryData(qk.jobs, next)
      await new Promise((r) => setTimeout(r, 0))
    })
}

afterEach(() => vi.clearAllMocks())

describe('BatchNotifier', () => {
  it('toasts once, with an export action, when a running batch succeeds', async () => {
    const update = setup([batch()])
    expect(toast.success).not.toHaveBeenCalled()
    await update([batch(done)])
    await update([batch(done)])
    expect(toast.success).toHaveBeenCalledTimes(1)
    expect(toast.success).toHaveBeenCalledWith('hero: 완료 · 채택 2/2', expect.objectContaining({ action: expect.objectContaining({ label: '내보내기로 이동' }) }))
  })

  it('warns when units need review, errors on failure, and stays quiet for batches that were already finished', async () => {
    const update = setup([batch({ id: 'old', state: 'succeeded' })])
    await update([batch({ id: 'old', state: 'succeeded' }), batch({ id: 'a' })])
    await update([batch({ id: 'old', state: 'succeeded' }), batch({ id: 'a', state: 'succeeded', progress: { done: 2, total: 2, current: null }, result: { units: [{ unit: 'idle', status: 'review' }] } })])
    expect(toast.warning).toHaveBeenCalledTimes(1)
    expect(toast.warning.mock.calls[0][0]).toContain('검토 필요 1')
    await update([batch({ id: 'b' })])
    await update([batch({ id: 'b', state: 'failed' })])
    expect(toast.error).toHaveBeenCalledTimes(1)
    expect(toast.success).not.toHaveBeenCalled()
  })

  it('shows a system notification only when the permission is already granted, and never asks', async () => {
    const notify = vi.fn()
    const request = vi.fn()
    vi.stubGlobal('Notification', Object.assign(notify, { permission: 'default', requestPermission: request }))
    const update = setup([batch()])
    await update([batch(done)])
    expect(notify).not.toHaveBeenCalled()

    ;(Notification as unknown as { permission: string }).permission = 'granted'
    await update([batch({ id: 'b2' })])
    await update([batch({ id: 'b2', ...done })])
    expect(notify).toHaveBeenCalledTimes(1)
    expect(request).not.toHaveBeenCalled()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
