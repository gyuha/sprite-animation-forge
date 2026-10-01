import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { useJobs } from '@/api/queries'
import { isActive, type JobSnapshot } from '@/api/sse'
import { summarizeBatch } from '@/lib/batch'

/**
 * docs/09 7: when a batch Job we saw running finishes, show a toast (with a link to the export screen) and, only if the
 * browser permission is already granted, a system notification. Never asks for permission. Renders nothing.
 */
export function BatchNotifier() {
  const { data } = useJobs()
  const navigate = useNavigate()
  const wasActive = useRef(new Map<string, boolean>())

  useEffect(() => {
    for (const job of (data ?? []) as JobSnapshot[]) {
      if (job.type !== 'batch_generate') continue
      const before = wasActive.current.get(job.id)
      wasActive.current.set(job.id, isActive(job))
      if (!before || isActive(job)) continue

      const { text, needsReview } = summarizeBatch(job)
      if (job.state === 'succeeded') {
        const show = needsReview.length ? toast.warning : toast.success
        show(text, { action: { label: '내보내기로 이동', onClick: () => navigate(`/c/${job.character}/export`) } })
      } else if (job.state === 'canceled') toast.info(text)
      else toast.error(text)
      if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
        new Notification('Sprite Animation Forge', { body: text })
      }
    }
  }, [data, navigate])

  return null
}
