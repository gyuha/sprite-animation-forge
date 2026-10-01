import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { qk } from '@/api/queries'
import { makeClient, mockApi, renderWithClient } from '@/test-utils'
import { waitFor } from '@testing-library/react'
import { makeJob } from '@/test-fixtures'
import { JobTray } from './JobTray'

function trayWith(jobs: ReturnType<typeof makeJob>[]) {
  const client = makeClient()
  client.setQueryData(qk.jobs, jobs)
  renderWithClient(<MemoryRouter><JobTray /></MemoryRouter>, client)
}

describe('JobTray', () => {
  it('lists active jobs with progress and queue position, hides finished ones', async () => {
    trayWith([
      makeJob({ id: 'job_run', state: 'running', stage: 'generating', message: '이미지 생성 중', elapsed_s: 30, expected_s: 60 }),
      makeJob({ id: 'job_q', state: 'queued', queue_position: 2, action: 'walk' }),
      makeJob({ id: 'job_b', type: 'batch_generate', state: 'running', progress: { done: 3, total: 4, current: 'walk' } }),
      makeJob({ id: 'job_done', state: 'succeeded' }),
    ])
    expect(screen.getByRole('button', { name: '작업 트레이' })).toHaveTextContent('3')
    await userEvent.click(screen.getByRole('button', { name: '작업 트레이' }))

    expect(screen.getByTestId('job-job_run')).toHaveTextContent('이미지 생성 중')
    expect(screen.getByTestId('job-job_run').querySelector('[role=progressbar]')).toBeInTheDocument()
    expect(screen.getByTestId('job-job_q')).toHaveTextContent('대기 2번째')
    expect(screen.getByTestId('job-job_b')).toHaveTextContent('3/4')
    expect(screen.queryByTestId('job-job_done')).not.toBeInTheDocument()
  })

  it('shows an empty message when nothing is active', async () => {
    trayWith([makeJob({ state: 'failed' })])
    await userEvent.click(screen.getByRole('button', { name: '작업 트레이' }))
    expect(screen.getByText('진행 중인 작업이 없습니다')).toBeInTheDocument()
  })

  it('cancels a running or queued job through POST /api/jobs/:id/cancel', async () => {
    const fetchMock = mockApi({ 'POST /api/jobs/job_b/cancel': { job: makeJob({ id: 'job_b', type: 'batch_generate', state: 'canceled' }) } })
    trayWith([
      makeJob({ id: 'job_b', type: 'batch_generate', state: 'running', progress: { done: 1, total: 4, current: 'walk' } }),
      makeJob({ id: 'job_id', type: 'identity_analyze', state: 'running' }),
    ])
    await userEvent.click(screen.getByRole('button', { name: '작업 트레이' }))
    expect(screen.getByTestId('job-job_b')).toHaveTextContent('hero: 1/4 · walk 생성 중')
    expect(screen.queryByTestId('job-cancel-job_id')).not.toBeInTheDocument() // a running identity analysis cannot be stopped
    await userEvent.click(screen.getByTestId('job-cancel-job_b'))
    await waitFor(() => expect(fetchMock.mock.calls.some(([u, i]) => u === '/api/jobs/job_b/cancel' && i?.method === 'POST')).toBe(true))
    await waitFor(() => expect(screen.queryByTestId('job-cancel-job_b')).not.toBeInTheDocument())
  })

  it('separates the jobs with dividers and ends with a link to the status page', async () => {
    trayWith([
      makeJob({ id: 'job_a', state: 'running' }),
      makeJob({ id: 'job_b', state: 'queued', queue_position: 1 }),
      makeJob({ id: 'job_c', state: 'queued', queue_position: 2 }),
    ])
    await userEvent.click(screen.getByRole('button', { name: '작업 트레이' }))
    expect(screen.getAllByTestId('job-divider')).toHaveLength(2) // between 3 jobs, none before the first
    const link = screen.getByTestId('job-tray-status-link')
    expect(link).toHaveAttribute('href', '/status')
    expect(link).toHaveTextContent('상태 보기')
    await userEvent.click(link)
    await waitFor(() => expect(screen.queryByTestId('job-tray-status-link')).not.toBeInTheDocument()) // popover closes on navigation
  })

  it('keeps the status link when nothing is active', async () => {
    trayWith([])
    await userEvent.click(screen.getByRole('button', { name: '작업 트레이' }))
    expect(screen.getByTestId('job-tray-status-link')).toHaveAttribute('href', '/status')
    expect(screen.queryByTestId('job-divider')).not.toBeInTheDocument()
  })
})
