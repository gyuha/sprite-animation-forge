/** Pure helpers for batch_generate Jobs (docs/09 7, docs/10 2.4): status text, per-unit state, "needs review" list. */
import { isActive, type JobSnapshot } from '@/api/sse'

export interface BatchUnit {
  unit: string
  status: 'accepted' | 'review'
  qcStatus: string | null
  /** generation / processing error of a unit that was left for review */
  error: string | null
}

export interface BatchSummary {
  active: boolean
  /** "hero: 2/4 · walk 생성 중" */
  text: string
  /** 0-100 */
  percent: number
  done: number
  total: number
  accepted: number
  units: BatchUnit[]
  needsReview: string[]
}

interface ResultRow { unit: string; status: string; qc_status?: string | null; error?: { message?: string; code?: string } }

const LOG_LINE = /^(\S+): (accepted|review)$/

/** Finished units: the Job result lists all of them; a canceled/failed batch has none, but logged each unit as it finished. */
function unitsOf(job: JobSnapshot): BatchUnit[] {
  const rows = (job.result as { units?: ResultRow[] } | null)?.units
  if (Array.isArray(rows)) {
    return rows.map((r) => ({
      unit: r.unit,
      status: r.status === 'accepted' ? 'accepted' : 'review',
      qcStatus: r.qc_status ?? null,
      error: r.error ? (r.error.message ?? r.error.code ?? '오류') : null,
    }))
  }
  return (job.log ?? []).flatMap((l) => {
    const m = LOG_LINE.exec(l.text)
    return m ? [{ unit: m[1], status: m[2] as BatchUnit['status'], qcStatus: null, error: null }] : []
  })
}

export function summarizeBatch(job: JobSnapshot): BatchSummary {
  const units = unitsOf(job)
  const done = job.progress?.done ?? units.length
  const total = job.progress?.total ?? units.length
  const accepted = units.filter((u) => u.status === 'accepted').length
  const needsReview = units.filter((u) => u.status === 'review').map((u) => u.unit)
  const who = job.character

  let text: string
  switch (job.state) {
    case 'queued':
      text = `${who}: 대기 ${job.queue_position}번째`
      break
    case 'running':
      text = `${who}: ${done}/${total} · ${job.progress?.current ? `${job.progress.current} 생성 중` : '준비 중'}`
      break
    case 'succeeded':
      text = `${who}: 완료 · 채택 ${accepted}/${total}${needsReview.length ? ` · 검토 필요 ${needsReview.length}` : ''}`
      break
    case 'failed':
      text = `${who}: 실패 · ${done}/${total}`
      break
    case 'canceled':
      text = `${who}: 취소됨 · ${done}/${total} 완료`
      break
    case 'interrupted':
      text = `${who}: 중단됨 · ${done}/${total} 완료`
      break
  }
  const percent = job.state === 'succeeded' ? 100 : total > 0 ? Math.min(100, (done / total) * 100) : 0
  return { active: isActive(job), text, percent, done, total, accepted, units, needsReview }
}

/** The batch Job to show for a character: the running/queued one, else the most recently created. */
export function latestBatchJob(jobs: JobSnapshot[], cid: string): JobSnapshot | undefined {
  const mine = jobs.filter((j) => j.type === 'batch_generate' && j.character === cid)
  return mine.find(isActive) ?? [...mine].sort((a, b) => a.created_at.localeCompare(b.created_at)).at(-1)
}
