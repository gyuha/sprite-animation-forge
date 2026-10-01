/**
 * S5 액션 스튜디오. 경로 /c/:cid/studio/:action/:direction? (방향은 plan에 방향이 2개 이상일 때만; 모든 API 호출에 ?direction= 포함).
 * data-testid (Playwright 등이 의존한다):
 *   studio-page                     화면 루트
 *   action-tab-<action>             상단 액션 탭 (data-icon = ✓ ● ⚠ ○)
 *   direction-tabs                  방향 탭 영역 — plan 방향이 2개 이상일 때만 렌더링
 *   direction-tab-<down|up|right|left>   방향 탭 (mirror 파생 left 는 data-icon="↔")
 *   mirror-notice, mirror-separate  mirror left 탭: 읽기 전용 안내 / 플랜 화면으로 가는 "별도로 생성" 링크
 *   extra-input, extra-count        추가 지시 textarea(≤500자) / 글자 수
 *   prompt-button, prompt-dialog, prompt-text, prompt-copy   프롬프트 보기 버튼 / 모달 / 본문 / 복사
 *   generate-button                 "새로 생성" (비활성이면 사유가 tooltip, 부모 span[data-reason])
 *   upload-button, upload-input     직접 업로드 버튼 / 숨은 file input
 *   job-<jobId>                     진행 중 Job (JobProgress)
 *   job-failed, retry-button        마지막 Job이 실패했을 때의 카드 / 다시 시도
 *   interrupted-notice, regenerate-button   선택한 시도가 중단됨일 때 안내 / 다시 생성
 *   view-tab-raw|clean|frames       보기 탭 (원본+격자 / 배경 제거 / 프레임)
 *   grid-overlay, compare-slider, frame-grid, frame-<i>   보기 탭 내용 / 프레임 썸네일(클릭 시 그 프레임에서 정지)
 *   preview-canvas                  플레이어 canvas. data-version(프레임 파일 해시, 재처리가 끝나면 바뀜), data-frame, data-playing, data-overlays
 *   player-play, player-prev, player-next, player-fps, player-scale-<1|2|4>, player-bg-<checker|dark|light|green>,
 *   player-overlay-<baseline|anchor|bbox|onion>   플레이어 컨트롤
 *   attempt-strip, attempt-<NNN>, attempt-qc-<NNN>, accepted-badge-<NNN>, interrupted-badge-<NNN>   시도 기록
 *   accept-button, accept-confirm, accept-cancel   채택 / QC fail 확인 다이얼로그 버튼
 *   qc-panel, qc-status(data-status), qc-score, qc-item-<QC-ID>(data-grade), qc-id-<QC-ID>
 *   recommendations, rec-<reprocess|regenerate|force_accept>-<code>   권장 조치 버튼
 *   reprocess-panel, reprocess-toggle, reprocess-<anchor|x_anchor|scale_strategy|components>(select),
 *   reprocess-<t_in|t_out|edge_band_px|merge_gap_px|margin_top|margin_side|margin_bottom>(slider; -value = 현재 값),
 *   reprocess-despill, reprocess-reset, reprocess-save
 * 단축키: Space 재생/정지, ←/→ 프레임 이동(정지), O 어니언, G 새로 생성, A 채택. 입력창·슬라이더·다이얼로그에서는 무시.
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { ArrowLeft, Copy, Upload } from 'lucide-react'
import {
  useAcceptAttempt, useGenerateAction, usePreviewPrompt, useProcessAttempt, useSaveParams, useUploadRaw, type UnitTarget,
} from '@/api/mutations'
import { useAttempt, useAttempts, useCharacter, useHealth, useJobs, usePlan, type Direction } from '@/api/queries'
import { isActive, type JobSnapshot } from '@/api/sse'
import { AnimationPlayer, type Overlay } from '@/components/AnimationPlayer'
import { AttemptStrip } from '@/components/AttemptStrip'
import { CompareSlider } from '@/components/CompareSlider'
import { GridOverlay } from '@/components/GridOverlay'
import { JobProgress } from '@/components/JobProgress'
import { QcPanel } from '@/components/QcPanel'
import { ReasonTooltip } from '@/components/ReasonTooltip'
import { RecommendationButtons } from '@/components/RecommendationButtons'
import { ReprocessPanel } from '@/components/ReprocessPanel'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import type { Plan } from '@/lib/plan'
import { stepFrame } from '@/lib/player'
import { valuesFromParams, valuesToSet, type ProcessSet } from '@/lib/reprocess'
import {
  DIRECTION_LABEL, actionDirections, generateBlockReason, ignoresShortcut, isMirrored, isMultiDirection, representativeBlock,
  representativeDirection, unitIcon, unitKey, type UnitRow,
} from '@/lib/studio'

export const MAX_EXTRA_CHARS = 500
const PIXEL_STYLES = ['pixel_art', 'retro_pixel']
const MIRROR_REASON = '좌측은 우측면을 좌우반전해 만든 읽기 전용 결과입니다'

const toastError = (e: Error) => toast.error(e.message)
const studioPath = (cid: string, action: string, direction?: Direction) => `/c/${cid}/studio/${action}${direction ? `/${direction}` : ''}`

interface QcReport { status: string; score: number; results: Record<string, unknown>[]; recommendations: Record<string, unknown>[] }

export default function Studio() {
  const { cid = '', action, direction } = useParams()
  const navigate = useNavigate()
  const plan = usePlan(cid)
  const character = useCharacter(cid)
  const health = useHealth()
  const jobs = useJobs()

  if (plan.isPending) return <Skeleton className="h-96 w-full" />
  if (plan.isError) {
    return (
      <Alert variant="destructive">
        <AlertTitle>플랜을 불러올 수 없습니다</AlertTitle>
        <AlertDescription>
          {plan.error.message} <Link className="underline" to={`/c/${cid}/plan`}>플랜 화면으로</Link>
        </AlertDescription>
      </Alert>
    )
  }

  const p = plan.data.plan as Plan
  const order = p.order as string[]
  const multi = isMultiDirection(p)
  if (!action || !p.actions[action]) return <Navigate to={studioPath(cid, order[0], multi ? representativeDirection(p, order[0]) : undefined)} replace />
  const dirs = actionDirections(p, action)
  if (multi && !dirs.includes(direction as Direction)) return <Navigate to={studioPath(cid, action, representativeDirection(p, action))} replace />
  const dir = multi ? (direction as Direction) : undefined

  const rows = (character.data?.status.units ?? []) as unknown as UnitRow[]
  const unitJobs = ((jobs.data ?? []) as JobSnapshot[]).filter((j) => j.character === cid && j.type === 'action_generate')
  const generating = (a: string, d?: Direction) => unitJobs.some((j) => isActive(j) && j.action === a && (!d || j.direction === d))
  const rowOf = (a: string, d?: Direction) => rows.find((r) => r.unit === unitKey(a, d))
  const thisJobs = unitJobs.filter((j) => j.action === action && (j.direction ?? undefined) === dir)

  const goAction = (a: string) => {
    const d = dir && actionDirections(p, a).includes(dir) ? dir : multi ? representativeDirection(p, a) : undefined
    navigate(studioPath(cid, a, d))
  }

  return (
    <div className="space-y-4" data-testid="studio-page">
      <div className="flex items-center gap-3">
        <Button asChild variant="ghost" size="sm"><Link to="/"><ArrowLeft /> {cid}</Link></Button>
        <Tabs value={action} onValueChange={goAction}>
          <TabsList>
            {order.map((a) => {
              const icon = unitIcon(actionDirections(p, a).map((d) => rowOf(a, multi ? d : undefined)), generating(a))
              return (
                <TabsTrigger key={a} value={a} data-testid={`action-tab-${a}`} data-icon={icon}>
                  {a} <span aria-hidden>{icon}</span>
                </TabsTrigger>
              )
            })}
          </TabsList>
        </Tabs>
      </div>
      {multi && (
        <Tabs value={dir} onValueChange={(d) => navigate(studioPath(cid, action, d as Direction))} data-testid="direction-tabs">
          <TabsList>
            {dirs.map((d) => {
              const icon = unitIcon([rowOf(action, d)], generating(action, d))
              return (
                <TabsTrigger key={d} value={d} data-testid={`direction-tab-${d}`} data-icon={icon}>
                  {DIRECTION_LABEL[d]} <span aria-hidden>{icon}</span>
                </TabsTrigger>
              )
            })}
          </TabsList>
        </Tabs>
      )}
      <Workspace
        key={unitKey(action, dir)}
        cid={cid}
        plan={p}
        action={action}
        direction={dir}
        rows={rows}
        codexReady={health.data?.ready}
        activeJob={thisJobs.find(isActive)}
        lastJob={[...thisJobs].sort((a, b) => a.created_at.localeCompare(b.created_at)).at(-1)}
      />
    </div>
  )
}

interface WorkspaceProps {
  cid: string
  plan: Plan
  action: string
  direction?: Direction
  rows: UnitRow[]
  codexReady?: boolean
  activeJob?: JobSnapshot
  lastJob?: JobSnapshot
}

/** Everything below the tabs for one (action, direction) unit; remounted per unit so its local state starts fresh. */
function Workspace({ cid, plan, action, direction, rows, codexReady, activeJob, lastJob }: WorkspaceProps) {
  const target: UnitTarget = { cid, action, direction }
  const act = plan.actions[action]
  const mirrored = isMirrored(plan, action, direction)

  const attemptsQ = useAttempts(cid, action, direction)
  const attempts = attemptsQ.data?.attempts ?? []
  const [pick, setPick] = useState<string | null>(null)
  const selected = mirrored ? null : attempts.some((a) => a.attempt === pick) ? pick : (attemptsQ.data?.accepted_attempt ?? attempts.at(-1)?.attempt ?? null)
  const detailQ = useAttempt(cid, action, selected, direction)
  const detail = detailQ.data
  const summary = attempts.find((a) => a.attempt === selected)
  const interrupted = summary?.generation_status === 'interrupted'
  const qc = (interrupted ? null : detail?.qc) as QcReport | null | undefined

  // A finished generation adds an attempt: jump to it (the first load must not override the accepted default).
  const latest = attempts.at(-1)?.attempt ?? null
  const seenLatest = useRef<string | null | undefined>(undefined)
  useEffect(() => {
    if (!attemptsQ.data) return
    if (seenLatest.current !== undefined && latest && latest !== seenLatest.current) setPick(latest)
    seenLatest.current = latest
  }, [attemptsQ.data, latest])

  const mirrorRow = rows.find((r) => r.unit === unitKey(action, direction))
  const mirrorReady = mirrored && mirrorRow?.state === 'mirrored' && !!mirrorRow.accepted_attempt
  const mirrorFrames = useMemo(
    () => (mirrorReady ? Array.from({ length: act.frames as number }, (_, i) => `/files/${cid}/${action}/left/frames/${String(i).padStart(3, '0')}.png`) : []),
    [mirrorReady, cid, action, act.frames],
  )
  const frames = mirrored ? mirrorFrames : (interrupted ? [] : (detail?.files.frames ?? []))
  const derived = detail?.process?.derived as Record<string, unknown> | undefined

  const [frame, setFrame] = useState(0)
  const [playing, setPlaying] = useState(true)
  const [overlays, setOverlays] = useState<Overlay[]>([])
  const [view, setView] = useState(mirrored ? 'frames' : 'raw')
  const [extra, setExtra] = useState('')
  const [promptText, setPromptText] = useState<{ prompt: string; warnings: string[] } | null>(null)
  const [panelEpoch, setPanelEpoch] = useState(0)
  const generateRef = useRef<HTMLButtonElement>(null)
  const acceptRef = useRef<HTMLButtonElement>(null)
  const uploadRef = useRef<HTMLInputElement>(null)

  const processM = useProcessAttempt()
  const acceptM = useAcceptAttempt()
  const saveM = useSaveParams()
  const promptM = usePreviewPrompt()
  const generateM = useGenerateAction()
  const uploadM = useUploadRaw()

  const generateReason = generateBlockReason({
    mirrored,
    codexReady,
    generating: !!activeJob,
    needsRepresentative: representativeBlock(plan, direction, rows),
  })
  const reprocessReason = mirrored ? MIRROR_REASON : interrupted ? '중단된 시도는 처리할 수 없습니다' : null
  const acceptReason = mirrored ? MIRROR_REASON : null

  const generate = (recovery: string[] = []) => generateM.mutate({ ...target, extra, recovery }, { onError: toastError })
  const reprocess = (set: ProcessSet, done?: () => void) =>
    selected && processM.mutate({ ...target, attempt: selected, set }, { onSuccess: done, onError: toastError })
  const accept = (attempt: string | null | undefined, force: boolean) =>
    attempt && acceptM.mutate({ ...target, attempt, force }, { onSuccess: () => toast.success(`${attempt} 채택했습니다`), onError: toastError })
  const currentValues = valuesFromParams(detail?.process?.params as Record<string, unknown> | undefined)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey || ignoresShortcut(e.target, e.key)) return
      const step = (d: number) => {
        setPlaying(false)
        setFrame((f) => stepFrame(f, d, frames.length))
      }
      if (e.key === ' ') {
        e.preventDefault()
        setPlaying((v) => !v)
      } else if (e.key === 'ArrowLeft') step(-1)
      else if (e.key === 'ArrowRight') step(1)
      else if (e.key.toLowerCase() === 'o') setOverlays((o) => (o.includes('onion') ? o.filter((x) => x !== 'onion') : [...o, 'onion']))
      else if (e.key.toLowerCase() === 'g') generateRef.current?.click()
      else if (e.key.toLowerCase() === 'a') acceptRef.current?.click()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [frames.length])

  const showPrompt = () =>
    promptM.mutate({ ...target, extra }, { onSuccess: (r) => setPromptText({ prompt: r.prompt, warnings: r.warnings }), onError: toastError })

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[260px_minmax(0,1fr)_280px]">
      <section className="space-y-4" data-testid="generate-panel">
        <h2 className="text-sm font-semibold">생성</h2>
        <div className="space-y-1">
          <label htmlFor="extra-input" className="text-sm">추가 지시 (선택)</label>
          <Textarea id="extra-input" data-testid="extra-input" rows={4} maxLength={MAX_EXTRA_CHARS} value={extra} disabled={mirrored} onChange={(e) => setExtra(e.target.value)} />
          <p className="text-right text-xs text-muted-foreground" data-testid="extra-count">{extra.length} / {MAX_EXTRA_CHARS}</p>
        </div>
        <Button variant="outline" className="w-full" disabled={mirrored || promptM.isPending} onClick={showPrompt} data-testid="prompt-button">프롬프트 보기</Button>
        <ReasonTooltip reason={generateReason}>
          <Button className="w-full" ref={generateRef} disabled={!!generateReason || generateM.isPending} onClick={() => generate()} data-testid="generate-button">
            새로 생성 ~90s
          </Button>
        </ReasonTooltip>
        <input
          ref={uploadRef}
          type="file"
          accept="image/png,image/jpeg,image/webp"
          className="hidden"
          data-testid="upload-input"
          onChange={(e) => {
            const file = e.target.files?.[0]
            e.target.value = ''
            if (file) uploadM.mutate({ ...target, file }, { onSuccess: () => toast.success('업로드한 이미지를 처리했습니다'), onError: toastError })
          }}
        />
        <ReasonTooltip reason={mirrored ? MIRROR_REASON : null}>
          <Button variant="secondary" className="w-full" disabled={mirrored || uploadM.isPending} onClick={() => uploadRef.current?.click()} data-testid="upload-button">
            <Upload /> 직접 업로드
          </Button>
        </ReasonTooltip>
        {activeJob && <JobProgress job={activeJob} />}
        {!activeJob && lastJob?.state === 'failed' && (
          <Alert variant="destructive" data-testid="job-failed">
            <AlertTitle>생성에 실패했습니다</AlertTitle>
            <AlertDescription>
              <p>{lastJob.error?.message ?? lastJob.error?.code ?? '알 수 없는 오류'}</p>
              <Button size="sm" variant="outline" className="mt-2" disabled={!!generateReason} onClick={() => generate()} data-testid="retry-button">다시 시도</Button>
            </AlertDescription>
          </Alert>
        )}
      </section>

      <section className="min-w-0 space-y-4">
        {mirrored && (
          <Alert data-testid="mirror-notice">
            <AlertTitle>우측면을 좌우반전한 결과입니다</AlertTitle>
            <AlertDescription>
              {mirrorReady ? '읽기 전용입니다.' : '우측면을 채택하면 자동으로 만들어집니다.'}{' '}
              <Link className="underline" to={`/c/${cid}/plan`} data-testid="mirror-separate">별도로 생성 (플랜에서 mirror 해제)</Link>
            </AlertDescription>
          </Alert>
        )}
        {interrupted && (
          <Alert variant="destructive" data-testid="interrupted-notice">
            <AlertTitle>중단됨</AlertTitle>
            <AlertDescription>
              서버가 재시작되어 이 시도의 생성이 중단되었습니다.
              <Button size="sm" variant="outline" className="ml-3" disabled={!!generateReason} onClick={() => generate()} data-testid="regenerate-button">다시 생성</Button>
            </AlertDescription>
          </Alert>
        )}
        {frames.length > 0 && (
          <AnimationPlayer
            frames={frames}
            fps={act.fps}
            loop={act.loop}
            cell={plan.cell}
            baselineY={derived?.baseline_y as number | undefined}
            pixelated={PIXEL_STYLES.includes(plan.art_style)}
            playing={playing}
            onPlayingChange={setPlaying}
            frame={frame}
            onFrameChange={setFrame}
            overlays={overlays}
            onOverlaysChange={setOverlays}
            dimmed={processM.isPending}
          />
        )}
        {frames.length > 0 && (
          <Tabs value={view} onValueChange={setView}>
            <TabsList>
              {!mirrored && <TabsTrigger value="raw" data-testid="view-tab-raw">원본+격자</TabsTrigger>}
              {!mirrored && <TabsTrigger value="clean" data-testid="view-tab-clean">배경 제거</TabsTrigger>}
              <TabsTrigger value="frames" data-testid="view-tab-frames">프레임</TabsTrigger>
            </TabsList>
            {detail?.files.raw && (
              <TabsContent value="raw"><GridOverlay src={detail.files.raw} derived={derived} /></TabsContent>
            )}
            {detail?.files.raw && detail.files.clean && (
              <TabsContent value="clean"><CompareSlider original={detail.files.raw} clean={detail.files.clean} /></TabsContent>
            )}
            <TabsContent value="frames">
              <div className="flex flex-wrap gap-2" data-testid="frame-grid">
                {frames.map((url, i) => (
                  <button
                    key={url}
                    type="button"
                    className="rounded border bg-muted p-0.5 data-[active=true]:ring-2 data-[active=true]:ring-primary"
                    data-active={i === frame}
                    aria-label={`프레임 ${i}`}
                    data-testid={`frame-${i}`}
                    onClick={() => { setPlaying(false); setFrame(i) }}
                  >
                    <img src={url} alt="" className="size-16 object-contain" />
                  </button>
                ))}
              </div>
            </TabsContent>
          </Tabs>
        )}
        {frames.length === 0 && !mirrored && !interrupted && !attemptsQ.isPending && attempts.length === 0 && (
          <p className="text-sm text-muted-foreground">아직 결과가 없습니다. "새로 생성"을 누르거나 직접 업로드하세요.</p>
        )}
        <AttemptStrip attempts={attempts} selected={selected} onSelect={setPick} onAccept={(force) => accept(selected, force)} acceptDisabledReason={acceptReason} acceptRef={acceptRef} />
      </section>

      <aside className="space-y-5">
        {qc && <QcPanel qc={qc} />}
        {qc && (
          <RecommendationButtons
            recommendations={qc.recommendations}
            onReprocess={(set) => reprocess({ ...valuesToSet(currentValues), ...set }, () => setPanelEpoch((n) => n + 1))}
            onRegenerate={(code) => generate([code])}
            onForceAccept={(attempt) => accept(attempt ?? selected, true)}
            disabledReasons={{ reprocess: reprocessReason, regenerate: generateReason, force_accept: acceptReason }}
          />
        )}
        {(mirrored || detail) && !interrupted && (
          <ReprocessPanel
            key={`${selected}:${panelEpoch}`}
            initial={currentValues}
            planDefaults={{ anchor: act.anchor, x_anchor: act.x_anchor, scale_strategy: act.scale_strategy, components: act.components }}
            onApply={(set) => reprocess(set)}
            onSaveDefaults={(set) => saveM.mutate({ ...target, set }, { onSuccess: () => toast.success('이 설정을 플랜에 저장했습니다'), onError: toastError })}
            busy={processM.isPending}
            disabledReason={reprocessReason}
          />
        )}
      </aside>

      <Dialog open={promptText !== null} onOpenChange={(o) => !o && setPromptText(null)}>
        <DialogContent className="max-w-3xl" data-testid="prompt-dialog">
          <DialogHeader>
            <DialogTitle>프롬프트 미리보기</DialogTitle>
            <DialogDescription>{action}{direction ? ` / ${direction}` : ''} · 읽기 전용</DialogDescription>
          </DialogHeader>
          {promptText?.warnings.map((w) => <p key={w} className="text-sm text-amber-600">{w}</p>)}
          <pre className="max-h-96 overflow-auto rounded-md bg-muted p-3 text-xs whitespace-pre-wrap" data-testid="prompt-text">{promptText?.prompt}</pre>
          <Button variant="outline" className="self-end" onClick={() => navigator.clipboard.writeText(promptText?.prompt ?? '').then(() => toast.success('복사했습니다'))} data-testid="prompt-copy">
            <Copy /> 복사
          </Button>
        </DialogContent>
      </Dialog>
    </div>
  )
}
