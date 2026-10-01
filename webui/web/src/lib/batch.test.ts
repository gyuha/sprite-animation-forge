import { describe, expect, it } from 'vitest'
import { makeJob } from '@/test-fixtures'
import { latestBatchJob, summarizeBatch } from './batch'

const batch = (over: Parameters<typeof makeJob>[0] = {}) => makeJob({ id: 'job_b', type: 'batch_generate', action: null, direction: null, ...over })
const rows = [
  { unit: 'idle', status: 'accepted', attempt: '001', qc_status: 'pass' },
  { unit: 'walk', status: 'review', attempt: '002', qc_status: 'fail' },
  { unit: 'run', status: 'review', attempt: null, qc_status: null, error: { code: 'timeout', message: 'codex did not finish within 300s' } },
]

describe('summarizeBatch', () => {
  it('describes a running batch as "hero: 2/4 · walk 생성 중"', () => {
    const s = summarizeBatch(batch({ progress: { done: 2, total: 4, current: 'walk' } }))
    expect(s.text).toBe('hero: 2/4 · walk 생성 중')
    expect(s.percent).toBe(50)
    expect(s.active).toBe(true)
  })

  it('says queue position while queued', () => {
    expect(summarizeBatch(batch({ state: 'queued', queue_position: 2 })).text).toBe('hero: 대기 2번째')
  })

  it('lists per-unit results and the units that need review once finished', () => {
    const s = summarizeBatch(batch({ state: 'succeeded', progress: { done: 3, total: 3, current: null }, result: { units: rows, accepted: 1, review: 2 } }))
    expect(s.text).toBe('hero: 완료 · 채택 1/3 · 검토 필요 2')
    expect(s.needsReview).toEqual(['walk', 'run'])
    expect(s.units.map((u) => u.status)).toEqual(['accepted', 'review', 'review'])
    expect(s.units[2].error).toBe('codex did not finish within 300s')
    expect(s.percent).toBe(100)
    expect(s.active).toBe(false)
  })

  it('shows a canceled batch with the units it logged before the cancel', () => {
    const log = [{ t: '', level: 'info', text: 'idle: accepted' }, { t: '', level: 'warning', text: 'walk: review' }, { t: '', level: 'info', text: '이미지 생성 중' }]
    const s = summarizeBatch(batch({ state: 'canceled', progress: { done: 2, total: 4, current: 'run' }, log }))
    expect(s.text).toBe('hero: 취소됨 · 2/4 완료')
    expect(s.units.map((u) => `${u.unit}:${u.status}`)).toEqual(['idle:accepted', 'walk:review'])
    expect(s.needsReview).toEqual(['walk'])
  })

  it('marks a batch stopped by a server restart as 중단됨', () => {
    const s = summarizeBatch(batch({ state: 'interrupted', progress: { done: 1, total: 4, current: 'walk' } }))
    expect(s.text).toBe('hero: 중단됨 · 1/4 완료')
    expect(s.active).toBe(false)
  })
})

describe('latestBatchJob', () => {
  it('prefers the active batch, else the newest one, and ignores other characters and job types', () => {
    const old = batch({ id: 'old', state: 'succeeded', created_at: '2026-10-01T00:00:00Z' })
    const newer = batch({ id: 'new', state: 'failed', created_at: '2026-10-01T01:00:00Z' })
    const other = batch({ id: 'other', character: 'slime', state: 'running' })
    const single = makeJob({ id: 'single', state: 'running' })
    expect(latestBatchJob([old, newer, other, single], 'hero')?.id).toBe('new')
    expect(latestBatchJob([old, newer, batch({ id: 'live', state: 'queued' })], 'hero')?.id).toBe('live')
    expect(latestBatchJob([single], 'hero')).toBeUndefined()
  })
})
