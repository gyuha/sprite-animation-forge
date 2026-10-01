import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { REPROCESS_DEBOUNCE_MS, ReprocessPanel } from './ReprocessPanel'
import { valuesFromParams } from '@/lib/reprocess'

const params = {
  anchor: 'feet', x_anchor: 'mass', scale_strategy: 'fit',
  background: { t_in: 30, t_out: 90, despill: true, edge_band_px: 2 },
  components: { mode: 'largest', merge_gap_px: 13 }, margin: { top: 8, side: 8, bottom: 10 },
}
const initial = valuesFromParams(params)
const planDefaults = { anchor: 'feet', x_anchor: 'mass', scale_strategy: 'fit', components: 'largest' }

const thumb = (key: string) => within(screen.getByTestId(`reprocess-${key}`)).getByRole('slider')
const press = (key: string, k: string, times = 1) => { for (let i = 0; i < times; i++) fireEvent.keyDown(thumb(key), { key: k }) }

describe('ReprocessPanel', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('waits 300 ms after the last change, then applies once with every parameter', () => {
    const onApply = vi.fn()
    render(<ReprocessPanel initial={initial} planDefaults={planDefaults} onApply={onApply} onSaveDefaults={vi.fn()} defaultOpen />)
    press('merge_gap_px', 'ArrowRight')
    act(() => { vi.advanceTimersByTime(REPROCESS_DEBOUNCE_MS - 1) })
    expect(onApply).not.toHaveBeenCalled()
    press('merge_gap_px', 'ArrowRight') // restarts the timer
    act(() => { vi.advanceTimersByTime(REPROCESS_DEBOUNCE_MS - 1) })
    expect(onApply).not.toHaveBeenCalled()
    act(() => { vi.advanceTimersByTime(1) })
    expect(onApply).toHaveBeenCalledTimes(1)
    expect(onApply).toHaveBeenCalledWith({
      align: 'register', anchor: 'feet', x_anchor: 'mass', scale_strategy: 'fit', components: 'largest', merge_gap_px: 15,
      t_in: 30, t_out: 90, despill: true, edge_band_px: 2, margin_top: 8, margin_side: 8, margin_bottom: 10,
    })
  })

  it('keeps t_in below t_out: raising t_in past t_out pushes t_out up', () => {
    const onApply = vi.fn()
    render(<ReprocessPanel initial={{ ...initial, t_in: 89 }} planDefaults={planDefaults} onApply={onApply} onSaveDefaults={vi.fn()} defaultOpen />)
    press('t_in', 'ArrowRight', 2)
    expect(screen.getByTestId('reprocess-t_in-value')).toHaveTextContent('91')
    expect(screen.getByTestId('reprocess-t_out-value')).toHaveTextContent('92')
  })

  it('highlights plan-level values that differ and saves only those four on "기본값으로 저장"', () => {
    const onSave = vi.fn()
    render(<ReprocessPanel initial={{ ...initial, scale_strategy: 'preserve' }} planDefaults={planDefaults} onApply={vi.fn()} onSaveDefaults={onSave} defaultOpen />)
    expect(screen.getByTestId('reprocess-scale_strategy').closest('[data-changed]')).toHaveAttribute('data-changed', 'true')
    expect(screen.getByTestId('reprocess-anchor').closest('[data-changed]')).toHaveAttribute('data-changed', 'false')
    fireEvent.click(screen.getByTestId('reprocess-save'))
    expect(onSave).toHaveBeenCalledWith({ anchor: 'feet', x_anchor: 'mass', scale_strategy: 'preserve', components: 'largest' })
  })

  it('disables every control with a reason (mirror tab)', () => {
    render(<ReprocessPanel initial={initial} planDefaults={planDefaults} onApply={vi.fn()} onSaveDefaults={vi.fn()} disabledReason="읽기 전용" defaultOpen />)
    expect(screen.getByTestId('reprocess-save')).toBeDisabled()
    expect(screen.getByTestId('reprocess-despill')).toBeDisabled()
    expect(screen.getByTestId('reprocess-anchor')).toBeDisabled()
    expect(within(screen.getByTestId('reprocess-t_in')).getByRole('slider')).toHaveAttribute('data-disabled')
  })

  it('offers the alignment mode: shared placement is the default, per-frame is the previous behaviour', () => {
    const onApply = vi.fn()
    render(<ReprocessPanel initial={initial} planDefaults={planDefaults} onApply={onApply} onSaveDefaults={vi.fn()} defaultOpen />)
    expect(screen.getByTestId('reprocess-align')).toHaveTextContent('공통 배치')
    expect(screen.getByTestId('reprocess-align').closest('[data-changed]')).toHaveAttribute('data-changed', 'false')
  })

  it('marks align as changed and sends it with every parameter when the previous mode is chosen', () => {
    const onApply = vi.fn()
    render(<ReprocessPanel initial={{ ...initial, align: 'per_frame' }} planDefaults={planDefaults} onApply={onApply} onSaveDefaults={vi.fn()} defaultOpen />)
    expect(screen.getByTestId('reprocess-align')).toHaveTextContent('프레임별')
    expect(screen.getByTestId('reprocess-align').closest('[data-changed]')).toHaveAttribute('data-changed', 'true')
    press('merge_gap_px', 'ArrowRight')
    act(() => { vi.advanceTimersByTime(REPROCESS_DEBOUNCE_MS) })
    expect(onApply).toHaveBeenCalledWith(expect.objectContaining({ align: 'per_frame' }))
  })
})
