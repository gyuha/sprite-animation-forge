/** Wording of a failed Job (docs/09 8): summary for the red card and the stderr tail behind "자세히". */
import type { Job } from '@/api/queries'

export const STDERR_LINES = 20

export function describeJobError(error: Job['error'] | undefined): { summary: string; stderrTail: string | null } {
  if (!error) return { summary: '알 수 없는 오류', stderrTail: null }
  if (error.code === 'timeout') return { summary: '생성 시간이 5분을 넘었습니다', stderrTail: null }
  const tail = (error.detail as { stderr_tail?: string } | undefined)?.stderr_tail
  const lines = tail ? tail.split('\n').filter(Boolean).slice(-STDERR_LINES).join('\n') : ''
  return { summary: error.message.split('\n')[0] || error.code, stderrTail: lines || null }
}
