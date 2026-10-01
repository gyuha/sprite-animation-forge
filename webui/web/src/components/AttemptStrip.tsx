import { useState, type Ref } from 'react'
import { Check } from 'lucide-react'
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ScrollArea, ScrollBar } from '@/components/ui/scroll-area'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { ReasonTooltip } from '@/components/ReasonTooltip'
import type { AttemptSummary } from '@/api/queries'
import { cn } from '@/lib/utils'

interface Props {
  attempts: AttemptSummary[]
  selected: string | null
  onSelect: (attempt: string) => void
  /** force=true only after the user confirmed the QC-fail dialog */
  onAccept: (force: boolean) => void
  /** why accepting is unavailable (mirror tab ...) */
  acceptDisabledReason?: string | null
  /** lets the page-level `A` shortcut press the button (and so go through the same confirmation) */
  acceptRef?: Ref<HTMLButtonElement>
}

const qcVariant = (s?: string | null) => (s === 'fail' ? 'destructive' : s === 'pass' ? 'default' : 'secondary')

export function AttemptStrip({ attempts, selected, onSelect, onAccept, acceptDisabledReason, acceptRef }: Props) {
  const [confirming, setConfirming] = useState(false)
  const current = attempts.find((a) => a.attempt === selected)
  const interrupted = current?.generation_status === 'interrupted'
  const reason = acceptDisabledReason ?? (!current ? '채택할 시도가 없습니다' : interrupted ? '중단된 시도는 채택할 수 없습니다' : null)

  const accept = () => (current?.qc_status === 'fail' ? setConfirming(true) : onAccept(false))

  return (
    <section className="space-y-2" data-testid="attempt-strip">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold">시도 기록</h2>
        <ReasonTooltip reason={reason}>
          <Button size="sm" disabled={!!reason || current?.accepted} ref={acceptRef} onClick={accept} data-testid="accept-button">
            <Check /> {current?.accepted ? '채택됨' : '이 시도 채택'}
          </Button>
        </ReasonTooltip>
      </div>
      <ScrollArea className="w-full whitespace-nowrap">
        <div className="flex gap-2 pb-3">
          {attempts.length === 0 && <p className="text-sm text-muted-foreground">아직 시도가 없습니다</p>}
          {attempts.map((a) => {
            const hint = [a.extra && `추가 지시: ${a.extra}`, a.recovery.length > 0 && `복구: ${a.recovery.join(', ')}`].filter(Boolean).join('\n')
            const item = (
              <button
                type="button"
                className={cn('flex w-28 shrink-0 flex-col items-start gap-1 rounded-md border p-2 text-left text-sm', a.attempt === selected && 'border-primary ring-2 ring-primary/30')}
                onClick={() => onSelect(a.attempt)}
                aria-pressed={a.attempt === selected}
                data-testid={`attempt-${a.attempt}`}
              >
                <span className="flex w-full items-center justify-between font-medium">
                  {a.attempt}
                  {a.accepted && <Badge data-testid={`accepted-badge-${a.attempt}`}>✓ 채택</Badge>}
                </span>
                {a.generation_status === 'interrupted' ? (
                  <Badge variant="destructive" data-testid={`interrupted-badge-${a.attempt}`}>중단됨</Badge>
                ) : (
                  <Badge variant={qcVariant(a.qc_status)} data-testid={`attempt-qc-${a.attempt}`}>
                    {a.qc_status ?? '처리 전'}{a.score != null && ` ${a.score}`}
                  </Badge>
                )}
              </button>
            )
            return hint ? (
              <Tooltip key={a.attempt}>
                <TooltipTrigger asChild>{item}</TooltipTrigger>
                <TooltipContent className="whitespace-pre-line">{hint}</TooltipContent>
              </Tooltip>
            ) : (
              <div key={a.attempt}>{item}</div>
            )
          })}
        </div>
        <ScrollBar orientation="horizontal" />
      </ScrollArea>
      <AlertDialog open={confirming} onOpenChange={setConfirming}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>품질 검사 실패 항목이 있습니다</AlertDialogTitle>
            <AlertDialogDescription>그래도 채택할까요?</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="accept-cancel">취소</AlertDialogCancel>
            <AlertDialogAction onClick={() => onAccept(true)} data-testid="accept-confirm">그래도 채택</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  )
}
