import { describe, expect, it } from 'vitest'
import { describeJobError } from './jobError'

describe('describeJobError', () => {
  it('uses the 5 minute copy for a timeout', () => {
    expect(describeJobError({ code: 'timeout', message: 'codex did not finish within 300s', detail: {} }).summary).toBe('생성 시간이 5분을 넘었습니다')
  })

  it('keeps only the last 20 stderr lines', () => {
    const lines = Array.from({ length: 30 }, (_, i) => `line ${i + 1}`)
    const { summary, stderrTail } = describeJobError({ code: 'codex_failed', message: 'codex exited 1\nline 1', detail: { stderr_tail: lines.join('\n') } })
    expect(summary).toBe('codex exited 1')
    expect(stderrTail?.split('\n')).toEqual(lines.slice(10))
  })

  it('falls back for other errors', () => {
    expect(describeJobError({ code: 'image_gen_failed', message: 'no image', detail: {} })).toEqual({ summary: 'no image', stderrTail: null })
    expect(describeJobError(null).summary).toBe('알 수 없는 오류')
  })
})
