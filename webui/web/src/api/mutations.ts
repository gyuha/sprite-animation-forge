/** Mutations for S1-S4. Invalidation follows docs/09 9.3; Job-starting calls also put the Job into the cache. */
import { useMutation, useQueryClient, type QueryClient } from '@tanstack/react-query'
import { api, apiJson } from './client'
import { actionPath, dirQuery, qk, type AttemptDetail, type AttemptList, type Direction, type Health, type IdentityResponse, type PlanResponse } from './queries'
import { mergeSetIntoParams, type ProcessSet } from '@/lib/reprocess'
import { upsertJob, type JobSnapshot } from './sse'
import type { components } from './types'

type Schemas = components['schemas']
export type CharacterCreate = Schemas['CharacterCreate']
export type PlanCreate = Schemas['PlanCreate']
export type JobCreated = Schemas['JobCreated']
export type ReferenceResponse = Schemas['ReferenceResponse']
export type AttemptResult = Schemas['AttemptResult']
export type PromptResponse = Schemas['PromptResponse']
export type AcceptResult = Schemas['AcceptResult']
export type SaveParamsResult = Schemas['SaveParamsResult']

const refreshCharacter = (qc: QueryClient, cid: string) => {
  qc.invalidateQueries({ queryKey: qk.character(cid), exact: true })
  qc.invalidateQueries({ queryKey: qk.characters, exact: true })
}

export function useCreateCharacter() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: CharacterCreate) =>
      apiJson<{ character: { id: string; created_at: string; next_step: string } }>('/api/characters', 'POST', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.characters, exact: true }),
  })
}

export function useUploadReference() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ cid, file }: { cid: string; file: File }) => {
      const form = new FormData()
      form.append('file', file)
      return api<ReferenceResponse>(`/api/characters/${cid}/reference`, { method: 'POST', body: form })
    },
    onSuccess: (_, { cid }) => refreshCharacter(qc, cid),
  })
}

export function useStartReferenceGenerate() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ cid, description, count }: { cid: string; description: string; count: number }) =>
      apiJson<JobCreated>(`/api/characters/${cid}/reference/generate`, 'POST', { description, count }),
    onSuccess: ({ job }) => upsertJob(qc, job),
  })
}

export function useSelectReference() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ cid, attempt }: { cid: string; attempt: string }) =>
      apiJson<ReferenceResponse>(`/api/characters/${cid}/reference/attempts/${attempt}/select`, 'POST'),
    onSuccess: (_, { cid }) => refreshCharacter(qc, cid),
  })
}

export function useStartIdentityAnalyze() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ cid, force = false }: { cid: string; force?: boolean }) =>
      apiJson<JobCreated>(`/api/characters/${cid}/identity/analyze`, 'POST', { force }),
    onSuccess: ({ job }) => upsertJob(qc, job),
  })
}

export function useSaveIdentity() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ cid, identity }: { cid: string; identity: Record<string, unknown> }) =>
      apiJson<IdentityResponse>(`/api/characters/${cid}/identity`, 'PUT', { identity }),
    onSuccess: (data, { cid }) => qc.setQueryData(qk.identity(cid), data),
  })
}

function usePlanMutation<V extends { cid: string }>(call: (v: V) => Promise<PlanResponse>) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: call,
    onSuccess: (data, { cid }) => {
      qc.setQueryData(qk.plan(cid), data)
      refreshCharacter(qc, cid)
    },
  })
}

/** First creation: the server builds the plan like the CLI `plan` command. */
export const useCreatePlan = () =>
  usePlanMutation(({ cid, body }: { cid: string; body: PlanCreate }) => apiJson<PlanResponse>(`/api/characters/${cid}/plan`, 'POST', body))

/** Saving an existing plan (whole document). */
export const useSavePlan = () =>
  usePlanMutation(({ cid, plan }: { cid: string; plan: PlanResponse['plan'] }) => apiJson<PlanResponse>(`/api/characters/${cid}/plan`, 'PUT', { plan }))

/** Target of every per-action call: `direction` is undefined for single-direction plans (no `?direction=`). */
export interface UnitTarget { cid: string; action: string; direction?: Direction }
const unitUrl = ({ cid, action, direction }: UnitTarget, tail: string) => `${actionPath(cid, action)}${tail}${dirQuery(direction)}`

/** Reprocess: the response (qc, file hashes, derived) is written straight into the attempt caches (docs/09 9.3). */
export function useProcessAttempt() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ attempt, set, ...t }: UnitTarget & { attempt: string; set: ProcessSet }) =>
      apiJson<AttemptResult>(unitUrl(t, `/attempts/${attempt}/process`), 'POST', { set }),
    onSuccess: (res, { attempt, set, cid, action, direction }) => {
      qc.setQueryData<AttemptDetail>(qk.attempt(cid, action, direction, attempt), (old) =>
        old && {
          ...old,
          qc: res.qc,
          files: res.files,
          process: { ...old.process, params: mergeSetIntoParams(old.process?.params as Record<string, unknown>, set), derived: res.derived },
        })
      qc.setQueryData<AttemptList>(qk.attempts(cid, action, direction), (old) =>
        old && {
          ...old,
          attempts: old.attempts.map((a) => (a.attempt === attempt ? { ...a, qc_status: res.qc.status, score: res.qc.score, sheet: res.files.sheet } : a)),
        })
      qc.invalidateQueries({ queryKey: qk.character(cid), exact: true })
    },
  })
}

/** Accept (force = accept despite QC fail). Refreshes character/plan state and the attempt lists (a right accept derives left). */
export function useAcceptAttempt() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ attempt, force = false, ...t }: UnitTarget & { attempt: string; force?: boolean }) =>
      apiJson<AcceptResult>(unitUrl(t, `/attempts/${attempt}/accept`), 'POST', { force }),
    onSuccess: (_, { cid }) => {
      refreshCharacter(qc, cid)
      qc.invalidateQueries({ queryKey: qk.plan(cid), exact: true })
      qc.invalidateQueries({ queryKey: qk.attemptsOf(cid) })
    },
  })
}

/** "기본값으로 저장": writes anchor/x_anchor/scale_strategy/components into the plan's action. */
export function useSaveParams() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ set, ...t }: UnitTarget & { set: Record<string, string> }) =>
      apiJson<SaveParamsResult>(unitUrl(t, '/save-params'), 'POST', { set }),
    onSuccess: (_, { cid }) => qc.invalidateQueries({ queryKey: qk.plan(cid), exact: true }),
  })
}

export const usePreviewPrompt = () =>
  useMutation({
    mutationFn: ({ extra, recovery = [], ...t }: UnitTarget & { extra?: string; recovery?: string[] }) =>
      apiJson<PromptResponse>(unitUrl(t, '/prompt'), 'POST', { extra: extra || null, recovery }),
  })

export function useGenerateAction() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ extra, recovery = [], ...t }: UnitTarget & { extra?: string; recovery?: string[] }) =>
      apiJson<JobCreated>(unitUrl(t, '/generate'), 'POST', { extra: extra || null, recovery }),
    onSuccess: ({ job }) => upsertJob(qc, job),
  })
}

/** Manual raw sheet upload; the server processes it right away (same QC as a generated attempt). */
export function useUploadRaw() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ file, ...t }: UnitTarget & { file: File }) => {
      const form = new FormData()
      form.append('file', file)
      return api<AttemptResult & { unit: string }>(unitUrl(t, '/upload'), { method: 'POST', body: form })
    },
    onSuccess: (_, { cid, action, direction }) => {
      qc.invalidateQueries({ queryKey: qk.attempts(cid, action, direction) })
      refreshCharacter(qc, cid)
    },
  })
}

/** "전부 생성": one batch Job for every unit without an accepted attempt (docs/09 7). */
export function useGenerateAll() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ cid, auto_accept, max_regenerations }: { cid: string; auto_accept: boolean; max_regenerations: number }) =>
      apiJson<JobCreated>(`/api/characters/${cid}/generate-all`, 'POST', { auto_accept, max_regenerations }),
    onSuccess: ({ job }) => upsertJob(qc, job),
  })
}

export function useCancelJob() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (jid: string) => apiJson<{ job: JobSnapshot }>(`/api/jobs/${jid}/cancel`, 'POST'),
    onSuccess: ({ job }) => upsertJob(qc, job),
  })
}

/** Writes atlas/preview/animations.json; the manifest (`exports`) and the export meta become stale. */
export function useExport() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (cid: string) => apiJson<{ files: string[]; warnings: string[] }>(`/api/characters/${cid}/export`, 'POST'),
    onSuccess: (_, cid) => {
      qc.invalidateQueries({ queryKey: qk.character(cid), exact: true })
      qc.invalidateQueries({ queryKey: qk.exportMeta(cid) })
    },
  })
}

/** "다시 확인": bypasses the server's 60 s doctor cache (`?refresh=1`) and replaces the cached health. */
export function useRecheckHealth() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api<Health>('/api/health?refresh=1'),
    onSuccess: (data) => qc.setQueryData(qk.health, data),
  })
}
