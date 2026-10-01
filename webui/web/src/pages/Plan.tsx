/**
 * S4 애니메이션 플랜. data-testid:
 *   bundle-<name>                   번들 라디오 (side-basic, side-action, topdown-rpg, npc, custom)
 *   action-check-<action>           액션 체크박스
 *   action-toggle-<action>          액션 행 펼치기 버튼
 *   action-frames-<action>, action-fps-<action>, action-loop-<action>, action-grid-<action>   펼친 행의 편집 컨트롤
 *   action-method-<action>          생성 방식 select(격자 grid · 호흡 breathe · 동영상 video). video 는 API 가 연결되지 않으면 비활성이고
 *                                   action-method-video-hint 에 사유가 표시된다. breathe 는 정지 1장을 만들어 호흡 프레임을 생성(1x1)
 *   plan-view                       view select 트리거 (이미 저장된 플랜이면 비활성)
 *   plan-cell                       출력 cell select 트리거
 *   direction-controls              방향 선택 영역 — view=topdown 일 때만 렌더링됨
 *   direction-down|up|right|left    방향 체크박스
 *   mirror-switch                   좌측면 "우측면 반전" 스위치 (topdown 에서만 존재)
 *   mirror-off-note                 mirror 를 껐을 때의 예상 시간 증가 안내
 *   asymmetry-badge                 서버 plan.assumptions 에 "비대칭" 경고가 있을 때
 *   plan-estimate                   "생성할 액션 N개 · 예상 약 …" 문구
 *   key-color-alert                 키 색 충돌 경고(캐릭터 색이 magenta 와 가까움)
 *   plan-identity-link              Identity 화면 링크
 *   plan-save                       저장 (플랜이 없으면 POST, 있으면 PUT)
 *   plan-continue                   저장 후 스튜디오(/c/:id/studio/:action)로 이동
 *   generate-all                    "전부 생성" (주 버튼): 플랜 저장 → POST generate-all. Codex 미준비/진행 중이면 비활성(사유 tooltip)
 *   auto-accept-switch              자동 채택 (기본 켬) → body.auto_accept
 *   max-regen-select                재생성 한도 0|1|2 (기본 1) 트리거 → body.max_regenerations
 *   batch-panel(data-state)         이 캐릭터의 일괄 Job 패널 (BatchPanel). 안의 testid:
 *     batch-status, batch-progress(data-percent), job-cancel-<jobId>, batch-units, batch-unit-<unit>(data-state=accepted|review),
 *     batch-review-link-<unit>, batch-interrupted, batch-restart, job-failed, go-export
 *   이 화면에서 시작한 일괄 생성이 검토 필요 없이 끝나면 자동으로 /c/:id/export 로 이동한다(state.autoExport).
 */
import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { ChevronDown } from 'lucide-react'
import { useCreatePlan, useGenerateAll, useSavePlan } from '@/api/mutations'
import { useCharacter, useHealth, useIdentity, useJobs, usePlan, usePresets, type PlanResponse, type Presets } from '@/api/queries'
import { isActive, type JobSnapshot } from '@/api/sse'
import { ApiError } from '@/api/client'
import { BatchPanel } from '@/components/BatchPanel'
import { ReasonTooltip } from '@/components/ReasonTooltip'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import { latestBatchJob, summarizeBatch } from '@/lib/batch'
import { VIEW_OPTIONS } from '@/lib/character'
import { resolveKeyColor } from '@/lib/color'
import {
  BREATHE_FRAMES, BUNDLE_LABELS, CELL_OPTIONS, CUSTOM_BUNDLE, DIRECTIONS, actionValues, applyDraftToPlan, buildCreateRequest, canMirror,
  countUnits, draftFromPlan, effectiveMirror, estimateSeconds, expandBundle, formatDuration, withView,
  type ActionValues, type GenerationMethod, type PlanDraft, type PlanDirection,
} from '@/lib/plan'

const message = (e: unknown) => (e instanceof Error ? e.message : String(e))

/** Number input that keeps what the user types (so clearing/retyping works) and commits only in-range integers. */
function NumberField({ value, min, max, onCommit, ...props }: {
  value: number; min: number; max: number; onCommit: (n: number) => void; id: string; 'data-testid': string
}) {
  const [text, setText] = useState<string | null>(null)
  const n = Number(text)
  const invalid = text !== null && !(text !== '' && Number.isInteger(n) && n >= min && n <= max)
  return (
    <Input
      {...props}
      type="number"
      min={min}
      max={max}
      value={text ?? value}
      aria-invalid={invalid}
      onChange={(e) => {
        setText(e.target.value)
        const v = Number(e.target.value)
        if (e.target.value !== '' && Number.isInteger(v) && v >= min && v <= max) onCommit(v)
      }}
      onBlur={() => setText(null)}
    />
  )
}

function ActionRow({ name, draft, presets, onToggle, onEdit }: {
  name: string
  draft: PlanDraft
  presets: Presets
  onToggle: (on: boolean) => void
  onEdit: (patch: Partial<ActionValues>) => void
}) {
  const on = draft.actions.includes(name)
  const v = actionValues(name, draft, presets)
  const methods = presets.methods ?? { grid: { available: true, reason: null }, breathe: { available: true, reason: null }, video: { available: false, reason: '동영상 API가 연결되지 않았습니다' } }
  const changeMethod = (method: GenerationMethod) =>
    onEdit(method === 'breathe' ? { method, frames: BREATHE_FRAMES, grid: '1x1' }
      : { method, frames: presets.frame_presets[name]?.frames ?? v.frames, grid: presets.frame_presets[name]?.grid ?? v.grid })
  const grids = [...new Set(Object.values(presets.grids))].filter((g) => {
    const [r, c] = g.split('x').map(Number)
    return r * c >= v.frames
  })
  return (
    <Collapsible className="rounded-lg border">
      <div className="flex items-center gap-3 px-3 py-2">
        <Checkbox id={`action-${name}`} checked={on} data-testid={`action-check-${name}`} onCheckedChange={(c) => onToggle(c === true)} />
        <Label htmlFor={`action-${name}`} className="w-16 font-medium">{name}</Label>
        <span className="text-sm text-muted-foreground">
          {v.method === 'breathe' ? '호흡 · ' : ''}{v.frames}프레임 · {v.grid} · {v.fps}fps · {v.loop ? '반복' : '1회'}
        </span>
        {on && (
          <CollapsibleTrigger asChild>
            <Button variant="ghost" size="icon-sm" className="ml-auto" aria-label={`${name} 설정 펼치기`} data-testid={`action-toggle-${name}`}>
              <ChevronDown />
            </Button>
          </CollapsibleTrigger>
        )}
      </div>
      {on && (
        <CollapsibleContent className="grid gap-4 border-t px-3 py-3 sm:grid-cols-5">
          <div className="space-y-1.5">
            <Label>생성 방식</Label>
            <Select value={v.method} onValueChange={(m) => changeMethod(m as GenerationMethod)}>
              <SelectTrigger className="w-full" data-testid={`action-method-${name}`}><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="grid">격자 (기본)</SelectItem>
                <SelectItem value="breathe">호흡 (정지 1장)</SelectItem>
                <SelectItem value="video" disabled={!methods.video.available}>동영상 (API)</SelectItem>
              </SelectContent>
            </Select>
            {!methods.video.available && (
              <p className="text-xs text-muted-foreground" data-testid={`action-method-video-hint`}>동영상: {methods.video.reason}</p>
            )}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={`frames-${name}`}>frames (2–16)</Label>
            <NumberField id={`frames-${name}`} min={2} max={16} value={v.frames} data-testid={`action-frames-${name}`}
              onCommit={(frames) => onEdit({ frames })} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={`fps-${name}`}>fps (1–60)</Label>
            <NumberField id={`fps-${name}`} min={1} max={60} value={v.fps} data-testid={`action-fps-${name}`}
              onCommit={(fps) => onEdit({ fps })} />
          </div>
          <div className="space-y-1.5">
            <Label>grid</Label>
            <Select value={v.grid} disabled={v.method === 'breathe'} onValueChange={(grid) => onEdit({ grid })}>
              <SelectTrigger className="w-full" data-testid={`action-grid-${name}`}><SelectValue /></SelectTrigger>
              <SelectContent>{grids.map((g) => <SelectItem key={g} value={g}>{g}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="flex items-end gap-2 pb-1.5">
            <Checkbox id={`loop-${name}`} checked={v.loop} data-testid={`action-loop-${name}`} onCheckedChange={(c) => onEdit({ loop: c === true })} />
            <Label htmlFor={`loop-${name}`}>반복 (loop)</Label>
          </div>
        </CollapsibleContent>
      )}
    </Collapsible>
  )
}

function PlanEditor({ cid, presets, plan, initial, keyColors }: {
  cid: string
  presets: Presets
  plan: PlanResponse | null
  initial: PlanDraft
  keyColors: string[]
}) {
  const navigate = useNavigate()
  const createPlan = useCreatePlan()
  const savePlan = useSavePlan()
  const [draft, setDraft] = useState(initial)
  const health = useHealth()
  const jobs = useJobs()
  const generateAll = useGenerateAll()
  const [autoAccept, setAutoAccept] = useState(true)
  const [maxRegen, setMaxRegen] = useState('1')
  const [startedId, setStartedId] = useState<string | null>(null) // batch started from this screen
  const batch = latestBatchJob((jobs.data ?? []) as JobSnapshot[], cid)

  const saved = plan !== null // an existing plan is saved with PUT and keeps its view
  const allActions = [...Object.keys(presets.frame_presets), ...draft.actions.filter((a) => !(a in presets.frame_presets))]
  const topdown = draft.view === 'topdown'
  const keyColor = resolveKeyColor(keyColors)
  const cells = CELL_OPTIONS.includes(draft.cell) ? CELL_OPTIONS : [...CELL_OPTIONS, draft.cell]
  const asymmetric = (plan?.plan.assumptions as string[] | undefined)?.some((a) => a.includes('비대칭'))

  const patch = (p: Partial<PlanDraft>) => setDraft((d) => ({ ...d, ...p }))
  const edit = (name: string, e: Partial<ActionValues>) => setDraft((d) => ({ ...d, edits: { ...d.edits, [name]: { ...d.edits[name], ...e } } }))

  function pickBundle(bundle: string) {
    const b = expandBundle(presets, bundle)
    if (!b) return patch({ bundle })
    const next = { ...draft, bundle, actions: b.actions }
    setDraft(b.view && !saved ? withView(next, b.view) : next)
  }

  function toggleAction(name: string, on: boolean) {
    patch({ bundle: CUSTOM_BUNDLE, actions: on ? [...draft.actions, name] : draft.actions.filter((a) => a !== name) })
  }

  function toggleDirection(d: PlanDirection, on: boolean) {
    patch({ directions: on ? [...draft.directions, d] : draft.directions.filter((x) => x !== d) })
  }

  const persist = () =>
    saved
      ? savePlan.mutateAsync({ cid, plan: applyDraftToPlan(plan.plan, draft, presets) })
      : createPlan.mutateAsync({ cid, body: buildCreateRequest(draft, presets) })

  async function save(thenGo: boolean) {
    try {
      const res = await persist()
      toast.success('플랜을 저장했습니다')
      if (thenGo) navigate(`/c/${cid}/studio/${(res.plan.order as string[])[0]}`)
    } catch (e) {
      toast.error(message(e))
    }
  }

  /** "전부 생성": the server needs the plan, so an unsaved or edited draft is saved first. */
  async function startBatch() {
    try {
      if (!saved || JSON.stringify(draft) !== JSON.stringify(initial)) await persist()
      const { job } = await generateAll.mutateAsync({ cid, auto_accept: autoAccept, max_regenerations: Number(maxRegen) })
      setStartedId(job.id)
    } catch (e) {
      toast.error(message(e))
    }
  }

  // Shortest path (docs/09 3.1): a batch started here that ended with nothing to review goes straight on to the export.
  useEffect(() => {
    if (batch && batch.id === startedId && batch.state === 'succeeded' && summarizeBatch(batch).needsReview.length === 0) {
      navigate(`/c/${cid}/export`, { state: { autoExport: true } })
    }
  }, [batch, startedId, cid, navigate])

  const invalid = draft.actions.length === 0 || (topdown && draft.directions.length === 0)
  const pending = createPlan.isPending || savePlan.isPending || generateAll.isPending
  const batchActive = !!batch && isActive(batch)
  const generateReason = batchActive ? '이미 일괄 생성이 진행 중입니다' : health.data?.ready === false ? 'Codex를 사용할 수 없습니다 (상단 상태 배지 확인)' : null

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">액션 계획 · {cid}</h1>
        <Button variant="outline" size="sm" asChild><Link to={`/c/${cid}/identity`} data-testid="plan-identity-link">캐릭터 정보 (Identity)</Link></Button>
      </div>

      {keyColor.conflict !== 'none' && (
        <Alert data-testid="key-color-alert">
          <AlertTitle>키 색 충돌</AlertTitle>
          <AlertDescription>
            {keyColor.conflict === 'magenta'
              ? '캐릭터 색이 magenta(#FF00FF)와 가까워 배경 키를 green(#00FF00)으로 바꿉니다.'
              : '캐릭터 색이 magenta·green 모두와 가깝습니다. magenta를 유지하지만 배경 제거 품질이 떨어질 수 있습니다.'}
          </AlertDescription>
        </Alert>
      )}

      <section className="space-y-2">
        <Label>번들</Label>
        <RadioGroup className="flex flex-wrap gap-4" value={draft.bundle} onValueChange={pickBundle}>
          {[...Object.keys(presets.bundles), CUSTOM_BUNDLE].map((b) => (
            <div key={b} className="flex items-center gap-2">
              <RadioGroupItem id={`bundle-${b}`} value={b} data-testid={`bundle-${b}`} />
              <Label htmlFor={`bundle-${b}`}>{BUNDLE_LABELS[b] ?? b}</Label>
            </div>
          ))}
        </RadioGroup>
      </section>

      <section className="space-y-2">
        {allActions.map((name) => (
          <ActionRow key={name} name={name} draft={draft} presets={presets} onToggle={(on) => toggleAction(name, on)} onEdit={(e) => edit(name, e)} />
        ))}
      </section>

      <section className="flex flex-wrap gap-6">
        <div className="space-y-1.5">
          <Label>출력 cell</Label>
          <Select value={draft.cell} onValueChange={(cell) => patch({ cell })}>
            <SelectTrigger className="w-36" data-testid="plan-cell"><SelectValue /></SelectTrigger>
            <SelectContent>{cells.map((c) => <SelectItem key={c} value={c}>{c.replace('x', ' x ')}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label>view</Label>
          <Select value={draft.view} disabled={saved} onValueChange={(v) => setDraft((d) => withView(d, v))}>
            <SelectTrigger className="w-44" data-testid="plan-view"><SelectValue /></SelectTrigger>
            <SelectContent>{VIEW_OPTIONS.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}</SelectContent>
          </Select>
        </div>
      </section>

      {topdown && (
        <section className="space-y-3 rounded-lg border p-4" data-testid="direction-controls">
          <Label>방향</Label>
          <div className="flex flex-wrap items-center gap-5">
            {DIRECTIONS.map(({ value, label }) => (
              <div key={value} className="flex items-center gap-2">
                <Checkbox id={`dir-${value}`} checked={draft.directions.includes(value)} data-testid={`direction-${value}`}
                  onCheckedChange={(c) => toggleDirection(value, c === true)} />
                <Label htmlFor={`dir-${value}`}>{label}</Label>
                {value === 'left' && (
                  <>
                    <Switch id="mirror" checked={effectiveMirror(draft)} disabled={!canMirror(draft)} data-testid="mirror-switch"
                      onCheckedChange={(mirror) => patch({ mirror })} />
                    <Label htmlFor="mirror" className="text-muted-foreground">우측면 반전</Label>
                  </>
                )}
              </div>
            ))}
          </div>
          {canMirror(draft) && !effectiveMirror(draft) && (
            <p className="text-sm text-muted-foreground" data-testid="mirror-off-note">
              반전을 끄면 좌측면을 별도로 생성하므로 예상 시간이 늘어납니다.
            </p>
          )}
          <p className="text-sm text-muted-foreground">캐릭터마다 좌우가 다를 수 있습니다(무기를 한 손에만 듦 등). 그럴 때는 반전을 끄세요.</p>
          {asymmetric && <Badge variant="destructive" data-testid="asymmetry-badge">비대칭일 수 있습니다</Badge>}
        </section>
      )}

      <section className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm" data-testid="plan-estimate">
          생성할 액션 {draft.actions.length}개 · {countUnits(draft)}개 unit · 예상 약 {formatDuration(estimateSeconds(draft))}
        </p>
        <div className="flex gap-2">
          <Button variant="outline" disabled={invalid || pending} data-testid="plan-save" onClick={() => save(false)}>저장</Button>
          <Button variant="outline" disabled={invalid || pending} data-testid="plan-continue" onClick={() => save(true)}>저장 후 스튜디오 →</Button>
          <ReasonTooltip reason={generateReason}>
            <Button disabled={invalid || pending || !!generateReason} data-testid="generate-all" onClick={startBatch}>전부 생성</Button>
          </ReasonTooltip>
        </div>
      </section>

      <section className="flex flex-wrap items-center gap-6">
        <div className="flex items-center gap-2">
          <Switch id="auto-accept" checked={autoAccept} data-testid="auto-accept-switch" onCheckedChange={setAutoAccept} />
          <Label htmlFor="auto-accept">자동 채택 (QC 통과·경고면 바로 채택)</Label>
        </div>
        <div className="flex items-center gap-2">
          <Label>재생성 한도</Label>
          <Select value={maxRegen} onValueChange={setMaxRegen}>
            <SelectTrigger className="w-20" data-testid="max-regen-select"><SelectValue /></SelectTrigger>
            <SelectContent>{['0', '1', '2'].map((n) => <SelectItem key={n} value={n}>{n}회</SelectItem>)}</SelectContent>
          </Select>
        </div>
      </section>

      {batch && <BatchPanel job={batch} onRestart={startBatch} restartReason={generateReason} />}
    </div>
  )
}

export default function Plan() {
  const { cid = '' } = useParams()
  const presets = usePresets()
  const plan = usePlan(cid)
  const character = useCharacter(cid)
  const identity = useIdentity(cid)

  const noPlan = plan.error instanceof ApiError && plan.error.status === 412
  if (plan.isError && !noPlan) {
    return <Alert variant="destructive"><AlertTitle>플랜을 불러오지 못했습니다</AlertTitle><AlertDescription>{plan.error.message}</AlertDescription></Alert>
  }
  if (presets.isError) {
    return <Alert variant="destructive"><AlertTitle>프리셋을 불러오지 못했습니다</AlertTitle><AlertDescription>{presets.error.message}</AlertDescription></Alert>
  }
  if (!presets.data || (plan.isPending && !noPlan) || character.isPending) return <Skeleton className="mx-auto h-64 max-w-4xl" />

  const planData = plan.data ?? null
  const view = String((character.data?.manifest.settings as Record<string, string> | undefined)?.view ?? 'side')
  const bundle = view === 'topdown' ? 'topdown-rpg' : 'side-basic'
  const initial: PlanDraft = planData
    ? draftFromPlan(planData.plan, presets.data)
    : withView(
        { bundle, view, actions: presets.data.bundles[bundle]?.actions ?? [], edits: {}, cell: '128x128', directions: [], mirror: false },
        view,
      )
  const p = identity.data?.profile?.identity as { primary_colors?: string[]; secondary_colors?: string[] } | undefined
  const keyColors = [...(p?.primary_colors ?? []), ...(p?.secondary_colors ?? [])]

  return <PlanEditor cid={cid} presets={presets.data} plan={planData} initial={initial} keyColors={keyColors} />
}
