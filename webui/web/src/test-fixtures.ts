import type { JobSnapshot } from '@/api/sse'

export function makeJob(over: Partial<JobSnapshot> = {}): JobSnapshot {
  return {
    id: 'job_1', type: 'action_generate', character: 'hero', action: 'idle', direction: 'right', state: 'running',
    created_at: '2026-10-01T00:00:00Z', elapsed_s: 0, queue_position: 0, log: [], ...over,
  }
}
