import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import type { JobSnapshot } from '@/api/sse'

const TYPE_LABEL: Record<JobSnapshot['type'], string> = {
  reference_generate: '레퍼런스 생성',
  identity_analyze: 'Identity 분석',
  action_generate: '액션 생성',
  batch_generate: '일괄 생성',
}

const STATE_LABEL: Record<JobSnapshot['state'], string> = {
  queued: '대기 중',
  running: '실행 중',
  succeeded: '완료',
  failed: '실패',
  canceled: '취소됨',
  interrupted: '중단됨',
}

export function jobTitle(job: JobSnapshot) {
  const target = [job.action, job.direction].filter(Boolean).join('/')
  return `${job.character} · ${TYPE_LABEL[job.type]}${target ? ` (${target})` : ''}`
}

/** Progress bar: batch progress (done/total) when known, else elapsed vs expected time; queue position while queued. */
export function JobProgress({ job }: { job: JobSnapshot }) {
  const queued = job.state === 'queued'
  let value = 0
  if (job.progress && job.progress.total > 0) value = (job.progress.done / job.progress.total) * 100
  else if (job.expected_s) value = Math.min(95, (job.elapsed_s / job.expected_s) * 100)
  else if (job.state === 'succeeded') value = 100

  return (
    <div className="space-y-1.5" data-testid={`job-${job.id}`}>
      <div className="flex items-center justify-between gap-2">
        <span className="truncate text-sm font-medium">{jobTitle(job)}</span>
        <Badge variant={job.state === 'failed' ? 'destructive' : 'secondary'}>
          {queued ? `대기 ${job.queue_position}번째` : STATE_LABEL[job.state]}
        </Badge>
      </div>
      <Progress value={value} aria-label="진행률" />
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>{job.message ?? job.stage ?? ''}</span>
        <span>
          {job.progress ? `${job.progress.done}/${job.progress.total}` : job.state === 'running' ? `${job.elapsed_s}초` : ''}
        </span>
      </div>
    </div>
  )
}
