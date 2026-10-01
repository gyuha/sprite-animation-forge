/** Mutations for S1-S4. Invalidation follows docs/09 9.3; Job-starting calls also put the Job into the cache. */
import { useMutation, useQueryClient, type QueryClient } from '@tanstack/react-query'
import { api, apiJson } from './client'
import { qk, type IdentityResponse, type PlanResponse } from './queries'
import { upsertJob } from './sse'
import type { components } from './types'

type Schemas = components['schemas']
export type CharacterCreate = Schemas['CharacterCreate']
export type PlanCreate = Schemas['PlanCreate']
export type JobCreated = Schemas['JobCreated']
export type ReferenceResponse = Schemas['ReferenceResponse']

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
