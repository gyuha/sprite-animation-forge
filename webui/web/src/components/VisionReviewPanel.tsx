import { AlertTriangle, Check, Eye, X } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ReasonTooltip } from '@/components/ReasonTooltip'

/** vision-review.json `review` (schemas/vision-review.llm.schema.json): advisory, never part of the QC score. */
export interface VisionReview {
  loop: { ok: boolean; note: string }
  limbs: { ok: boolean; note: string }
  identity: { ok: boolean; note: string }
  overall: 'pass' | 'warn' | 'fail'
  summary: string
}

const CHECKS: { key: 'loop' | 'limbs' | 'identity'; label: string }[] = [
  { key: 'loop', label: '루프 연결' },
  { key: 'limbs', label: '팔다리 움직임' },
  { key: 'identity', label: '캐릭터 일관성' },
]
const OVERALL = { pass: '자연스러움', warn: '확인 필요', fail: '부자연스러움' } as const

interface Props {
  review: VisionReview | null | undefined
  busy: boolean
  disabledReason?: string | null
  onRun: () => void
}

/** "비전 심사": Codex looks at the frames (one call, ~1 minute) and says whether the motion reads naturally. Opt-in. */
export function VisionReviewPanel({ review, busy, disabledReason, onRun }: Props) {
  return (
    <section className="space-y-2" data-testid="vision-review">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold">비전 심사</h2>
        {review && (
          <Badge variant={review.overall === 'fail' ? 'destructive' : review.overall === 'pass' ? 'default' : 'secondary'}
            data-testid="vision-review-overall" data-overall={review.overall}>
            {OVERALL[review.overall]}
          </Badge>
        )}
      </div>
      {review && (
        <div className="space-y-1.5 text-sm" data-testid="vision-review-result">
          <ul className="space-y-1">
            {CHECKS.map(({ key, label }) => (
              <li key={key} className="flex items-start gap-2" data-testid={`vision-review-${key}`} data-ok={review[key].ok}>
                <span className="mt-0.5" role="img" aria-label={review[key].ok ? '문제 없음' : '문제 있음'}>
                  {review[key].ok ? <Check className="size-4 text-green-600" /> : <X className="size-4 text-destructive" />}
                </span>
                <span><span className="font-medium">{label}</span> · {review[key].note}</span>
              </li>
            ))}
          </ul>
          <p className="flex items-start gap-2 text-muted-foreground" data-testid="vision-review-summary">
            <AlertTriangle className="mt-0.5 size-4 shrink-0" /> {review.summary}
          </p>
        </div>
      )}
      <ReasonTooltip reason={disabledReason ?? null}>
        <Button variant="outline" size="sm" className="w-full" disabled={busy || !!disabledReason} onClick={onRun} data-testid="vision-review-button">
          <Eye /> {busy ? '심사 중...' : review ? '다시 심사' : '비전 심사 (Codex 1회)'}
        </Button>
      </ReasonTooltip>
      <p className="text-xs text-muted-foreground">참고용입니다. 점수에는 반영되지 않습니다.</p>
    </section>
  )
}
