import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { api } from './client'
import type { components } from './types'

export type Job = components['schemas']['Job']
export type PlanResponse = components['schemas']['PlanResponse']
export type IdentityResponse = components['schemas']['IdentityResponse']
export type AttemptList = components['schemas']['AttemptList']
export type AttemptDetail = components['schemas']['AttemptDetail']
export type AttemptSummary = components['schemas']['AttemptSummary']
/** Server directions (routes/deps.py `Direction`). */
export type Direction = 'down' | 'up' | 'right' | 'left'

export const actionPath = (cid: string, action: string) => `/api/characters/${cid}/actions/${action}`
/** `?direction=` is sent only for plans with 2+ directions (docs/10 5.1); callers pass undefined otherwise. */
export const dirQuery = (direction?: Direction) => (direction ? `?direction=${direction}` : '')

// The server declares these responses as plain dicts, so OpenAPI has no schema; typed by hand from routes/health.py
// and routes/characters.py.
export interface Health {
  ready: boolean
  warnings: string[]
  codex: { installed: boolean; version: string | null; tested_version?: string; codex_home?: string; version_ok: boolean; logged_in: boolean; auth: string | null; image_generation: boolean }
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
/** manifest.usage (docs/08 5): accumulated Codex calls and tokens of one character. */
export interface Usage { codex_calls: number; input_tokens: number; cached_input_tokens: number; output_tokens: number }
/** atlas/<cid>.meta.json (docs/07 6): what the export screen needs for the atlas preview and the Phaser snippet. */
export interface ExportMeta {
  cell: { w: number; h: number }
  origin: { x: number; y: number }
  padding: number
  baseline_y: number
  actions: { name: string; direction: string | null; unit: string; row: number; frames: number }[]
  texture: { file: string; sha256: string; size: [number, number] }
}

// GET /api/presets (routes/presets.py), also an untyped dict.
export interface ActionPreset { frames: number; grid: string; loop: boolean; fps: number; anchor: string; scale_strategy: string; x_anchor: string; components: string }
export interface Presets {
  frame_presets: Record<string, ActionPreset>
  bundles: Record<string, { actions: string[]; view: string | null }>
  grids: Record<string, string>
  views: string[]
  asset_types: string[]
  art_styles: string[]
  directions: string[]
}

/** Query keys. Everything of a character lives under ['characters', cid, ...] (see sse.ts for invalidation). */
export const qk = {
  health: ['health'] as const,
  jobs: ['jobs'] as const,
  characters: ['characters'] as const,
  character: (cid: string) => ['characters', cid] as const,
  plan: (cid: string) => ['characters', cid, 'plan'] as const,
  exportMeta: (cid: string) => ['characters', cid, 'export-meta'] as const,
  identity: (cid: string) => ['characters', cid, 'identity'] as const,
  attemptsOf: (cid: string) => ['characters', cid, 'attempts'] as const,
  attempts: (cid: string, action: string, direction?: Direction) => ['characters', cid, 'attempts', action, direction ?? null] as const,
  attempt: (cid: string, action: string, direction: Direction | undefined, aid: string) =>
    ['characters', cid, 'attempts', action, direction ?? null, aid] as const,
}

export const HEALTH_REFETCH_MS = 60_000

export const healthQueryOptions = {
  queryKey: qk.health,
  queryFn: () => api<Health>('/api/health'),
  refetchInterval: HEALTH_REFETCH_MS,
  refetchOnWindowFocus: 'always' as const,
}

export const useHealth = () => useQuery(healthQueryOptions)

export const usePresets = () => useQuery({ queryKey: ['presets'], queryFn: () => api<Presets>('/api/presets'), staleTime: Infinity })

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
    queryFn: () => api<AttemptList>(`${actionPath(cid, action)}/attempts${dirQuery(direction)}`),
    placeholderData: keepPreviousData,
  })

/** One attempt with its files, process.json and qc-report.json. `aid` null = nothing selected yet. */
export const useAttempt = (cid: string, action: string, aid: string | null, direction?: Direction) =>
  useQuery({
    queryKey: qk.attempt(cid, action, direction, aid ?? ''),
    queryFn: () => api<AttemptDetail>(`${actionPath(cid, action)}/attempts/${aid}${dirQuery(direction)}`),
    enabled: aid !== null,
  })

export const fetchActiveJobs = () => api<{ jobs: Job[] }>('/api/jobs?active=1').then((r) => r.jobs)

/** Job snapshots kept in the Query cache; sse.ts upserts them. Initial value = currently active jobs. */
export const useJobs = () => useQuery({ queryKey: qk.jobs, queryFn: fetchActiveJobs, staleTime: Infinity })

/** Export meta (origin, atlas size, rows); read only once an export exists. */
export const useExportMeta = (cid: string, enabled: boolean) =>
  useQuery({ queryKey: qk.exportMeta(cid), queryFn: () => api<ExportMeta>(`/files/${cid}/atlas/${cid}.meta.json`), enabled })
