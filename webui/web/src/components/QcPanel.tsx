import { AlertTriangle, Check, Info, Minus, X } from 'lucide-react'
import type { ReactNode } from 'react'
import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { GRADE_LABEL, QC_NAMES, STATUS_LABEL, describeResult, type Grade, type QcResult } from '@/lib/qc'
import { cn } from '@/lib/utils'

const ICON: Record<Grade, ReactNode> = {
  pass: <Check className="size-4 text-green-600" />,
  warn: <AlertTriangle className="size-4 text-amber-500" />,
  fail: <X className="size-4 text-destructive" />,
  info: <Info className="size-4 text-blue-500" />,
  not_run: <Minus className="size-4 text-muted-foreground" />,
}

interface Props { qc: { status: string; score: number; results: Record<string, unknown>[] } }

export function QcPanel({ qc }: Props) {
  const results = qc.results as unknown as QcResult[]
  return (
    <section className="space-y-3" data-testid="qc-panel">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold">품질 검사</h2>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground tabular-nums" data-testid="qc-score">{qc.score}점</span>
          <Badge variant={qc.status === 'fail' ? 'destructive' : qc.status === 'pass' ? 'default' : 'secondary'} data-testid="qc-status" data-status={qc.status}>
            {STATUS_LABEL[qc.status] ?? qc.status}
          </Badge>
        </div>
      </div>
      <ul className="space-y-1.5">
        {results.map((r) => (
          <li key={r.id} className={cn('flex items-start gap-2 text-sm', r.grade === 'not_run' && 'text-muted-foreground')} data-testid={`qc-item-${r.id}`} data-grade={r.grade}>
            <span className="mt-0.5" role="img" aria-label={GRADE_LABEL[r.grade]}>{ICON[r.grade]}</span>
            <span className="flex-1">{describeResult(r)}</span>
            <Tooltip>
              <TooltipTrigger asChild>
                <span className="cursor-help text-xs text-muted-foreground" data-testid={`qc-id-${r.id}`}>{r.id}</span>
              </TooltipTrigger>
              <TooltipContent>{QC_NAMES[r.id]?.meaning ?? r.id}</TooltipContent>
            </Tooltip>
          </li>
        ))}
      </ul>
    </section>
  )
}
