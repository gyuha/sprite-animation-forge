import { Link } from 'react-router-dom'
import type { JobSnapshot } from '@/api/sse'
import { CancelJobButton } from '@/components/CancelJobButton'
import { JobFailedCard } from '@/components/JobFailedCard'
import { ReasonTooltip } from '@/components/ReasonTooltip'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { summarizeBatch } from '@/lib/batch'

/**
 * Progress and result of one batch_generate Job (docs/09 7): status text, progress bar, cancel, per-unit result list
 * (accepted / 검토 필요 with a link to the studio), "중단됨" notice and the way on to the export screen.
 */
export function BatchPanel({ job, onRestart, restartReason }: { job: JobSnapshot; onRestart: () => void; restartReason: string | null }) {
  const s = summarizeBatch(job)
  const restart = (
    <div className="mt-2">
      <ReasonTooltip reason={restartReason}>
        <Button size="sm" variant="outline" disabled={!!restartReason} onClick={onRestart} data-testid="batch-restart">다시 생성</Button>
      </ReasonTooltip>
    </div>
  )
  return (
    <section className="space-y-3 rounded-lg border p-4" data-testid="batch-panel" data-state={job.state}>
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-medium" data-testid="batch-status">{s.text}</p>
        <CancelJobButton job={job} />
      </div>
      <Progress value={s.percent} aria-label="일괄 생성 진행률" data-testid="batch-progress" data-percent={Math.round(s.percent)} />

      {job.state === 'interrupted' && (
        <Alert variant="destructive" data-testid="batch-interrupted">
          <AlertTitle>중단됨</AlertTitle>
          <AlertDescription>서버가 재시작되어 일괄 생성이 중단되었습니다. 끝난 액션은 그대로 유지됩니다.{restart}</AlertDescription>
        </Alert>
      )}
      {job.state === 'failed' && <JobFailedCard job={job}>{restart}</JobFailedCard>}
      {job.state === 'canceled' && <p className="text-sm text-muted-foreground">취소했습니다. 끝난 액션은 그대로 유지됩니다.</p>}

      {s.units.length > 0 && (
        <ul className="divide-y rounded-md border text-sm" data-testid="batch-units">
          {s.units.map((u) => (
            <li key={u.unit} className="flex items-center gap-3 px-3 py-1.5" data-testid={`batch-unit-${u.unit}`} data-state={u.status}>
              <span className="w-24 font-medium">{u.unit}</span>
              {u.status === 'accepted' ? <Badge>채택됨</Badge> : <Badge variant="destructive">검토 필요</Badge>}
              {u.error && <span className="truncate text-xs text-muted-foreground">{u.error}</span>}
              {u.status === 'review' && (
                <Link className="ml-auto underline" to={`/c/${job.character}/studio/${u.unit}`} data-testid={`batch-review-link-${u.unit}`}>스튜디오에서 확인</Link>
              )}
            </li>
          ))}
        </ul>
      )}

      {job.state === 'succeeded' && (
        <Button asChild data-testid="go-export">
          <Link to={`/c/${job.character}/export`} state={{ autoExport: true }}>내보내기로 이동 →</Link>
        </Button>
      )}
    </section>
  )
}
