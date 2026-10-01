import { ListTodo } from 'lucide-react'
import { useJobs } from '@/api/queries'
import { isActive, type JobSnapshot } from '@/api/sse'
import { CancelJobButton } from '@/components/CancelJobButton'
import { JobProgress } from '@/components/JobProgress'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { ScrollArea } from '@/components/ui/scroll-area'

/** Running jobs first, then the queue in queue order. */
function byOrder(a: JobSnapshot, b: JobSnapshot) {
  return (a.state === 'running' ? 0 : a.queue_position) - (b.state === 'running' ? 0 : b.queue_position)
}

export function JobTray() {
  const { data } = useJobs()
  const jobs = ((data ?? []) as JobSnapshot[]).filter(isActive).sort(byOrder)

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" aria-label="작업 트레이">
          <ListTodo />
          작업
          {jobs.length > 0 && <Badge>{jobs.length}</Badge>}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-96 p-3">
        {jobs.length === 0 ? (
          <p className="text-sm text-muted-foreground">진행 중인 작업이 없습니다</p>
        ) : (
          <ScrollArea className="max-h-80">
            <ul className="space-y-3 pr-3">
              {jobs.map((job) => (
                <li key={job.id} className="space-y-1.5">
                  <JobProgress job={job} />
                  <CancelJobButton job={job} />
                </li>
              ))}
            </ul>
          </ScrollArea>
        )}
      </PopoverContent>
    </Popover>
  )
}
