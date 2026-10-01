import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, ListTodo } from 'lucide-react'
import { useJobs } from '@/api/queries'
import { isActive, type JobSnapshot } from '@/api/sse'
import { CancelJobButton } from '@/components/CancelJobButton'
import { JobProgress } from '@/components/JobProgress'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'

/** Running jobs first, then the queue in queue order. */
function byOrder(a: JobSnapshot, b: JobSnapshot) {
  return (a.state === 'running' ? 0 : a.queue_position) - (b.state === 'running' ? 0 : b.queue_position)
}

export function JobTray() {
  const { data } = useJobs()
  const jobs = ((data ?? []) as JobSnapshot[]).filter(isActive).sort(byOrder)
  const [open, setOpen] = useState(false)

  return (
    <Popover open={open} onOpenChange={setOpen}>
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
            <ul className="pr-3">
              {jobs.map((job, i) => (
                <li key={job.id}>
                  {i > 0 && <Separator className="my-3" data-testid="job-divider" />}
                  <div className="space-y-1.5">
                    <JobProgress job={job} />
                    <CancelJobButton job={job} />
                  </div>
                </li>
              ))}
            </ul>
          </ScrollArea>
        )}
        <Separator data-testid="job-tray-divider" />
        <Link to="/status" onClick={() => setOpen(false)} className="flex items-center justify-end gap-1 text-sm text-muted-foreground hover:text-foreground" data-testid="job-tray-status-link">
          상태 보기 <ArrowRight className="size-3.5" />
        </Link>
      </PopoverContent>
    </Popover>
  )
}
