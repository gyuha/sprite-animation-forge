import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { TooltipProvider } from '@/components/ui/tooltip'
import { VisionReviewPanel, type VisionReview } from './VisionReviewPanel'

const review: VisionReview = {
  loop: { ok: true, note: '이어짐' }, limbs: { ok: false, note: '3번째 프레임에서 다리가 겹침' },
  identity: { ok: true, note: '같은 캐릭터' }, overall: 'warn', summary: '3번째 프레임의 다리를 확인하세요.',
}
const view = (props: Partial<React.ComponentProps<typeof VisionReviewPanel>> = {}) =>
  render(<TooltipProvider><VisionReviewPanel review={undefined} busy={false} onRun={vi.fn()} {...props} /></TooltipProvider>)

describe('VisionReviewPanel', () => {
  it('offers the review as an explicit, advisory action when there is no result yet', async () => {
    const onRun = vi.fn()
    view({ onRun })
    expect(screen.queryByTestId('vision-review-result')).not.toBeInTheDocument()
    expect(screen.getByTestId('vision-review-button')).toHaveTextContent('비전 심사')
    expect(screen.getByText(/점수에는 반영되지 않습니다/)).toBeInTheDocument()
    await userEvent.click(screen.getByTestId('vision-review-button'))
    expect(onRun).toHaveBeenCalledTimes(1)
  })

  it('shows each check with its note, the overall verdict and the summary, and offers a re-run', () => {
    view({ review })
    expect(screen.getByTestId('vision-review-overall')).toHaveAttribute('data-overall', 'warn')
    expect(screen.getByTestId('vision-review-loop')).toHaveAttribute('data-ok', 'true')
    expect(screen.getByTestId('vision-review-limbs')).toHaveAttribute('data-ok', 'false')
    expect(screen.getByTestId('vision-review-limbs')).toHaveTextContent('3번째 프레임에서 다리가 겹침')
    expect(screen.getByTestId('vision-review-summary')).toHaveTextContent('다리를 확인하세요')
    expect(screen.getByTestId('vision-review-button')).toHaveTextContent('다시 심사')
  })

  it('is disabled while a review runs and when Codex is unavailable', () => {
    view({ busy: true })
    expect(screen.getByTestId('vision-review-button')).toBeDisabled()
    expect(screen.getByTestId('vision-review-button')).toHaveTextContent('심사 중')
  })

  it('shows the reason when disabled', () => {
    view({ disabledReason: 'Codex를 사용할 수 없습니다' })
    expect(screen.getByTestId('vision-review-button')).toBeDisabled()
    expect(document.querySelector('[data-reason="Codex를 사용할 수 없습니다"]')).not.toBeNull()
  })
})
