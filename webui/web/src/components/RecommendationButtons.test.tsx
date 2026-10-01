import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { RecommendationButtons } from './RecommendationButtons'
import { TooltipProvider } from '@/components/ui/tooltip'

const recs = [
  { type: 'reprocess', code: 'use_preserve', set: { scale_strategy: 'preserve' }, reason: 'fit 전략에서 body 축소', cost: '~2s' },
  { type: 'regenerate', code: 'character_small', reason: 'preserve로도 부족하면', cost: '~90s' },
  { type: 'force_accept', code: 'forced_accept', attempt: '002', cost: '0s' },
]

function setup(disabledReasons = {}) {
  const h = { onReprocess: vi.fn(), onRegenerate: vi.fn(), onForceAccept: vi.fn() }
  render(<TooltipProvider><RecommendationButtons recommendations={recs} {...h} disabledReasons={disabledReasons} /></TooltipProvider>)
  return h
}

describe('RecommendationButtons', () => {
  it('maps each kind to its action: reprocess(set) / regenerate(code) / force accept(attempt)', () => {
    const h = setup()
    fireEvent.click(screen.getByTestId('rec-reprocess-use_preserve'))
    fireEvent.click(screen.getByTestId('rec-regenerate-character_small'))
    fireEvent.click(screen.getByTestId('rec-force_accept-forced_accept'))
    expect(h.onReprocess).toHaveBeenCalledWith({ scale_strategy: 'preserve' })
    expect(h.onRegenerate).toHaveBeenCalledWith('character_small')
    expect(h.onForceAccept).toHaveBeenCalledWith('002')
  })

  it('shows the cost and disables a kind with its reason', () => {
    const h = setup({ regenerate: 'Codex를 사용할 수 없습니다' })
    expect(screen.getByTestId('rec-reprocess-use_preserve')).toHaveTextContent('~2s')
    const regen = screen.getByTestId('rec-regenerate-character_small')
    expect(regen).toBeDisabled()
    expect(regen.closest('[data-reason]')).toHaveAttribute('data-reason', 'Codex를 사용할 수 없습니다')
    fireEvent.click(regen)
    expect(h.onRegenerate).not.toHaveBeenCalled()
    expect(screen.getByTestId('rec-reprocess-use_preserve')).toBeEnabled()
  })
})
