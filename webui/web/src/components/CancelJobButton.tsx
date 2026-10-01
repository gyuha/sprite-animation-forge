import { toast } from 'sonner'
import { useCancelJob } from '@/api/mutations'
import { isActive, type JobSnapshot } from '@/api/sse'
import { Button } from '@/components/ui/button'

/** Cancel for a queued/running Job. A running identity_analyze cannot be stopped (409), so no button. */
export function CancelJobButton({ job }: { job: JobSnapshot }) {
  const cancel = useCancelJob()
  if (!isActive(job) || (job.type === 'identity_analyze' && job.state === 'running')) return null
  return (
    <Button
      size="xs"
      variant="outline"
      disabled={cancel.isPending}
      data-testid={`job-cancel-${job.id}`}
      onClick={() => cancel.mutate(job.id, { onError: (e) => toast.error(e.message) })}
    >
      {cancel.isPending ? '취소 중…' : '취소'}
    </Button>
  )
}
