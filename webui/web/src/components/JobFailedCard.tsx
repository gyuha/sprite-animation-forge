import type { ReactNode } from 'react'
import type { JobSnapshot } from '@/api/sse'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { describeJobError } from '@/lib/jobError'

/** docs/09 8: red card with the summary and, behind "자세히", the last 20 stderr lines. `children` = retry action. */
export function JobFailedCard({ job, children }: { job: JobSnapshot; children?: ReactNode }) {
  const { summary, stderrTail } = describeJobError(job.error)
  return (
    <Alert variant="destructive" data-testid="job-failed">
      <AlertTitle>생성에 실패했습니다</AlertTitle>
      <AlertDescription>
        <p>{summary}</p>
        {stderrTail && (
          <Collapsible>
            <CollapsibleTrigger className="text-xs underline" data-testid="job-failed-details-toggle">자세히</CollapsibleTrigger>
            <CollapsibleContent>
              <pre className="mt-1 max-h-48 overflow-auto rounded bg-muted p-2 text-xs whitespace-pre-wrap text-foreground" data-testid="job-failed-details">{stderrTail}</pre>
            </CollapsibleContent>
          </Collapsible>
        )}
        {children}
      </AlertDescription>
    </Alert>
  )
}
