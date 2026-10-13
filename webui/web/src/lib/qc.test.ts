import { describe, expect, it } from 'vitest'
import { GRADE_LABEL, QC_NAMES, REGENERATE_LABEL, REPROCESS_LABEL, describeResult, recommendationLabel } from './qc'

describe('motion QC presentation', () => {
  it('names the four motion items with a meaning for the tooltip', () => {
    for (const id of ['QC-10', 'QC-11', 'QC-12', 'QC-13']) expect(QC_NAMES[id].meaning.length).toBeGreaterThan(10)
  })

  it('describes their values', () => {
    expect(describeResult({ id: 'QC-10', grade: 'warn', value: 2.345 })).toBe('루프 이음새 비율 2.35')
    expect(describeResult({ id: 'QC-11', grade: 'pass', value: 0.724 })).toBe('실루엣 연속성 72%')
    expect(describeResult({ id: 'QC-12', grade: 'pass', value: 0.95 })).toBe('색 일관성 95%')
    expect(describeResult({ id: 'QC-13', grade: 'warn', value: 0.0033 })).toBe('움직임 크기 0.3%')
  })

  it('labels the skipped grade and the new recovery codes', () => {
    expect(GRADE_LABEL.skipped).toBe('해당 없음')
    expect(recommendationLabel({ type: 'regenerate', code: 'loop_closure' })).toBe(REGENERATE_LABEL.loop_closure)
    expect(recommendationLabel({ type: 'reprocess', code: 'align_per_frame' })).toBe(REPROCESS_LABEL.align_per_frame)
    expect(REGENERATE_LABEL.loop_closure).toContain('루프')
  })
})
