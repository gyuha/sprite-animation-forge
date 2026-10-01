import { Button } from '@/components/ui/button'
import { ReasonTooltip } from '@/components/ReasonTooltip'
import { recommendationLabel, type Recommendation, type RecommendationType } from '@/lib/qc'

interface Props {
  recommendations: Record<string, unknown>[]
  onReprocess: (set: NonNullable<Recommendation['set']>) => void
  onRegenerate: (code: string) => void
  onForceAccept: (attempt?: string) => void
  /** Why a kind of action is unavailable right now (mirror tab, no Codex, job running ...); disables those buttons. */
  disabledReasons?: Partial<Record<RecommendationType, string | null>>
}

/** qc.recommendations in the server's order: reprocess runs now, regenerate starts a Job, force_accept accepts despite fail. */
export function RecommendationButtons({ recommendations, onReprocess, onRegenerate, onForceAccept, disabledReasons = {} }: Props) {
  const recs = recommendations as unknown as Recommendation[]
  if (recs.length === 0) return null
  const run = (r: Recommendation) => {
    if (r.type === 'reprocess') onReprocess(r.set ?? {})
    else if (r.type === 'regenerate') onRegenerate(r.code)
    else onForceAccept(r.attempt)
  }
  return (
    <section className="space-y-2" data-testid="recommendations">
      <h2 className="text-sm font-semibold">권장 조치</h2>
      {recs.map((r) => {
        const reason = disabledReasons[r.type]
        return (
          <div key={`${r.type}-${r.code}`} className="space-y-0.5">
            <ReasonTooltip reason={reason}>
              <Button variant="outline" size="sm" className="h-auto w-full justify-between whitespace-normal py-1.5 text-left" disabled={!!reason} onClick={() => run(r)} data-testid={`rec-${r.type}-${r.code}`}>
                <span>{recommendationLabel(r)}</span>
                {r.cost && <span className="text-xs text-muted-foreground">{r.cost}</span>}
              </Button>
            </ReasonTooltip>
            {r.reason && <p className="px-1 text-xs text-muted-foreground">{r.reason}</p>}
          </div>
        )
      })}
    </section>
  )
}
