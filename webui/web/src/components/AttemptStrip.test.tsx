import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { AttemptStrip } from './AttemptStrip'
import type { AttemptSummary } from '@/api/queries'
import { TooltipProvider } from '@/components/ui/tooltip'

const att = (attempt: string, over: Partial<AttemptSummary> = {}): AttemptSummary =>
  ({ attempt, accepted: false, sheet: null, recovery: [], qc_status: 'pass', score: 95, ...over })

function setup(attempts: AttemptSummary[], selected: string) {
  const h = { onSelect: vi.fn(), onAccept: vi.fn() }
  render(<TooltipProvider><AttemptStrip attempts={attempts} selected={selected} {...h} /></TooltipProvider>)
  return h
}

describe('AttemptStrip', () => {
  it('accepts a passing attempt directly, without force', () => {
    const h = setup([att('001')], '001')
    fireEvent.click(screen.getByTestId('accept-button'))
    expect(h.onAccept).toHaveBeenCalledWith(false)
  })

  it('asks for confirmation when QC failed and only then accepts with force', async () => {
    const h = setup([att('001', { qc_status: 'fail', score: 75 })], '001')
    fireEvent.click(screen.getByTestId('accept-button'))
    expect(h.onAccept).not.toHaveBeenCalled()
    expect(await screen.findByText('품질 검사 실패 항목이 있습니다')).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('accept-confirm'))
    expect(h.onAccept).toHaveBeenCalledWith(true)
  })

  it('cancelling the dialog accepts nothing', async () => {
    const h = setup([att('001', { qc_status: 'fail' })], '001')
    fireEvent.click(screen.getByTestId('accept-button'))
    fireEvent.click(await screen.findByTestId('accept-cancel'))
    await waitFor(() => expect(screen.queryByTestId('accept-confirm')).not.toBeInTheDocument())
    expect(h.onAccept).not.toHaveBeenCalled()
  })

  it('shows ✓ for the accepted attempt, 중단됨 for an interrupted one (not acceptable), and selects on click', () => {
    const h = setup([att('001', { accepted: true }), att('002', { generation_status: 'interrupted', qc_status: null, score: null })], '002')
    expect(screen.getByTestId('accepted-badge-001')).toBeInTheDocument()
    expect(screen.getByTestId('interrupted-badge-002')).toHaveTextContent('중단됨')
    expect(screen.queryByTestId('attempt-qc-002')).not.toBeInTheDocument()
    expect(screen.getByTestId('accept-button')).toBeDisabled()
    fireEvent.click(screen.getByTestId('attempt-001'))
    expect(h.onSelect).toHaveBeenCalledWith('001')
  })
})
