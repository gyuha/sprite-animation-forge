import { useEffect } from 'react'
import { useQueryClient, type QueryClient } from '@tanstack/react-query'
import { fetchActiveJobs, qk, type Job } from './queries'

/** Job snapshot as sent on the wire: Job + `message` (Korean stage text). `kind` and `line` are stripped. */
export type JobSnapshot = Job & { message?: string }

const FINISHED: Job['state'][] = ['succeeded', 'failed', 'canceled', 'interrupted']
export const isActive = (job: Job) => !FINISHED.includes(job.state)

export const BACKOFF_START_MS = 1_000
export const BACKOFF_MAX_MS = 30_000

export function upsertJob(qc: QueryClient, snap: JobSnapshot) {
  qc.setQueryData<JobSnapshot[]>(qk.jobs, (old = []) => {
    const i = old.findIndex((j) => j.id === snap.id)
    if (i < 0) return [...old, snap]
    const next = [...old]
    next[i] = { ...old[i], ...snap } // snapshots carry no `log`; keep what we have
    return next
  })
  if (snap.state === 'succeeded') {
    qc.invalidateQueries({ queryKey: qk.attemptsOf(snap.character) })
    qc.invalidateQueries({ queryKey: qk.character(snap.character), exact: true }) // manifest
  }
}

/** After (re)connect events are not replayed: re-read the active jobs and merge them over the cached ones. */
export async function resyncJobs(qc: QueryClient) {
  const active = await fetchActiveJobs()
  qc.setQueryData<JobSnapshot[]>(qk.jobs, (old = []) => {
    const ids = new Set(active.map((j) => j.id))
    // cached jobs that look active but are no longer reported as active finished while we were away
    return [...old.filter((j) => !ids.has(j.id) && !isActive(j)), ...active]
  })
}

/** One EventSource per tab (mount once, in the app layout). */
export function useJobEvents() {
  const qc = useQueryClient()
  useEffect(() => {
    let es: EventSource | null = null
    let timer: ReturnType<typeof setTimeout> | undefined
    let delay = BACKOFF_START_MS
    let stopped = false

    const connect = () => {
      es = new EventSource('/api/events')
      es.onopen = () => {
        delay = BACKOFF_START_MS
        resyncJobs(qc).catch(() => {})
      }
      es.addEventListener('job', (e) => {
        try {
          const { kind: _kind, line: _line, ...snap } = JSON.parse((e as MessageEvent<string>).data)
          upsertJob(qc, snap as JobSnapshot)
        } catch {
          // malformed frame: ignore
        }
      })
      es.onerror = () => {
        // CONNECTING: the browser retries by itself (onopen resyncs). CLOSED (e.g. HTTP error): retry with backoff.
        if (stopped || !es || es.readyState !== EventSource.CLOSED) return
        es.close()
        timer = setTimeout(connect, delay)
        delay = Math.min(delay * 2, BACKOFF_MAX_MS)
      }
    }
    connect()
    return () => {
      stopped = true
      clearTimeout(timer)
      es?.close()
    }
  }, [qc])
}
