import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { api } from './client'
import type { components } from './types'

export type Job = components['schemas']['Job']
export type PlanResponse = components['schemas']['PlanResponse']
export type IdentityResponse = components['schemas']['IdentityResponse']
export type AttemptList = components['schemas']['AttemptList']
export type Direction = 'left' | 'right' | 'front' | 'back'

// The server declares these responses as plain dicts, so OpenAPI has no schema; typed by hand from routes/health.py
// and routes/characters.py.
export interface Health {
  ready: boolean
  warnings: string[]
  codex: { installed: boolean; version: string | null; version_ok: boolean; logged_in: boolean; auth: string | null; image_generation: boolean }
  python: Record<string, string | null>
}
export interface CharacterCard {
  id: string
  created_at: string
  updated_at: string
  settings: Record<string, string>
  has_reference: boolean
  has_plan: boolean
  units_total: number
  units_accepted: number
  next_step: 'reference' | 'plan' | 'generate' | 'export'
}
export interface CharacterDetail {
  character: { id: string; next_step: CharacterCard['next_step'] }
  manifest: Record<string, unknown>
  status: { has_reference: boolean; has_plan: boolean; units: Record<string, unknown>[] }
}

/** Query keys. Everything of a character lives under ['characters', cid, ...] (see sse.ts for invalidation). */
export const qk = {
  health: ['health'] as const,
  jobs: ['jobs'] as const,
  characters: ['characters'] as const,
  character: (cid: string) => ['characters', cid] as const,
  plan: (cid: string) => ['characters', cid, 'plan'] as const,
  identity: (cid: string) => ['characters', cid, 'identity'] as const,
  attemptsOf: (cid: string) => ['characters', cid, 'attempts'] as const,
  attempts: (cid: string, action: string, direction?: Direction) => ['characters', cid, 'attempts', action, direction ?? null] as const,
}

export const HEALTH_REFETCH_MS = 60_000

export const healthQueryOptions = {
  queryKey: qk.health,
  queryFn: () => api<Health>('/api/health'),
  refetchInterval: HEALTH_REFETCH_MS,
  refetchOnWindowFocus: 'always' as const,
}

export const useHealth = () => useQuery(healthQueryOptions)

export const useCharacters = () =>
  useQuery({ queryKey: qk.characters, queryFn: () => api<{ characters: CharacterCard[] }>('/api/characters').then((r) => r.characters) })

export const useCharacter = (cid: string) =>
  useQuery({ queryKey: qk.character(cid), queryFn: () => api<CharacterDetail>(`/api/characters/${cid}`) })

export const usePlan = (cid: string) =>
  useQuery({ queryKey: qk.plan(cid), queryFn: () => api<PlanResponse>(`/api/characters/${cid}/plan`) })

export const useIdentity = (cid: string) =>
  useQuery({ queryKey: qk.identity(cid), queryFn: () => api<IdentityResponse>(`/api/characters/${cid}/identity`) })

export const useAttempts = (cid: string, action: string, direction?: Direction) =>
  useQuery({
    queryKey: qk.attempts(cid, action, direction),
    queryFn: () =>
      api<AttemptList>(`/api/characters/${cid}/actions/${action}/attempts${direction ? `?direction=${direction}` : ''}`),
    placeholderData: keepPreviousData,
  })

export const fetchActiveJobs = () => api<{ jobs: Job[] }>('/api/jobs?active=1').then((r) => r.jobs)

/** Job snapshots kept in the Query cache; sse.ts upserts them. Initial value = currently active jobs. */
export const useJobs = () => useQuery({ queryKey: qk.jobs, queryFn: fetchActiveJobs, staleTime: Infinity })
