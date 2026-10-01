/**
 * S2 새 캐릭터. data-testid:
 *   tab-image / tab-text            탭 A(이미지로 시작) / 탭 B(설명으로 시작) 트리거
 *   dropzone, dropzone-input,       DropZone 영역 / <input type=file> / 미리보기 / 검증 오류 문구
 *   dropzone-preview, dropzone-error
 *   new-character-id                캐릭터 id 입력 (오류 문구: new-character-id-error)
 *   new-view, new-art-style         view / 스타일 select 트리거
 *   create-from-image               탭 A 만들기 버튼 (생성 → 업로드 → identity 분석 시작 → /c/:id/plan)
 *   new-description, new-count      탭 B 설명 textarea / 후보 수 select 트리거
 *   generate-candidates             탭 B 후보 생성 버튼
 *   candidate-<attempt>             후보 카드 (aria-pressed 로 선택 표시)
 *   candidate-proceed               "이 캐릭터로 진행" 버튼
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import {
  useCreateCharacter, useSelectReference, useStartIdentityAnalyze, useStartReferenceGenerate, useUploadReference,
} from '@/api/mutations'
import { useCharacters, useJobs } from '@/api/queries'
import { isActive } from '@/api/sse'
import { DropZone } from '@/components/DropZone'
import { JobProgress } from '@/components/JobProgress'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { ART_STYLE_OPTIONS, VIEW_OPTIONS, slugify, uniqueId, validateCharacterId } from '@/lib/character'
import { SECONDS_PER_CALL, formatDuration } from '@/lib/plan'
import { cn } from '@/lib/utils'

type View = (typeof VIEW_OPTIONS)[number]['value']
type ArtStyle = (typeof ART_STYLE_OPTIONS)[number]['value']

const message = (e: unknown) => (e instanceof Error ? e.message : String(e))

export default function NewCharacter() {
  const navigate = useNavigate()
  const characters = useCharacters()
  const jobs = useJobs()
  const createCharacter = useCreateCharacter()
  const uploadReference = useUploadReference()
  const generateReference = useStartReferenceGenerate()
  const selectReference = useSelectReference()
  const analyze = useStartIdentityAnalyze()

  const [id, setId] = useState('')
  const [idTouched, setIdTouched] = useState(false)
  const [view, setView] = useState<View>('side')
  const [artStyle, setArtStyle] = useState<ArtStyle>('project_native')
  const [file, setFile] = useState<File | null>(null)
  const [description, setDescription] = useState('')
  const [count, setCount] = useState('2')
  const [createdId, setCreatedId] = useState<string | null>(null)
  const [jobId, setJobId] = useState<string | null>(null)
  const [candidate, setCandidate] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const idError = id ? validateCharacterId(id) : null
  const idValid = !!id && !idError

  async function ensureCharacter(cid = id) {
    if (createdId === cid) return // a retry after a later step failed must not create it twice
    await createCharacter.mutateAsync({ id: cid, view, art_style: artStyle, asset_type: 'character' })
    setCreatedId(cid)
  }

  /** Analysis needs Codex; if it cannot start the user continues and edits the identity by hand. */
  async function startAnalyze(cid = id) {
    try {
      await analyze.mutateAsync({ cid })
    } catch (e) {
      toast.warning(`Identity 분석을 시작하지 못했습니다: ${message(e)}`)
    }
  }

  async function run(step: () => Promise<void>) {
    setBusy(true)
    try {
      await step()
    } catch (e) {
      toast.error(message(e))
    } finally {
      setBusy(false)
    }
  }

  const createFromImage = (cid = id, image = file!) =>
    run(async () => {
      await ensureCharacter(cid)
      await uploadReference.mutateAsync({ cid, file: image })
      await startAnalyze(cid)
      navigate(`/c/${cid}/plan`)
    })

  /** Picking an image is itself "만들기" (docs/09 3.1) while the id is the untouched suggestion; otherwise the button creates. */
  function pickImage(f: File) {
    setFile(f)
    if (idTouched) return
    const suggested = uniqueId(slugify(f.name), characters.data?.map((c) => c.id) ?? [])
    setId(suggested)
    if (!validateCharacterId(suggested)) void createFromImage(suggested, f)
  }

  const generateCandidates = () =>
    run(async () => {
      await ensureCharacter()
      setCandidate(null)
      const { job } = await generateReference.mutateAsync({ cid: id, description, count: Number(count) })
      setJobId(job.id)
    })

  const proceed = () =>
    run(async () => {
      await selectReference.mutateAsync({ cid: id, attempt: candidate! })
      await startAnalyze()
      navigate(`/c/${id}/plan`)
    })

  const job = jobs.data?.find((j) => j.id === jobId)
  const attempts = ((job?.result?.attempts ?? []) as { attempt: string; status: string }[]).filter((a) => a.status === 'succeeded')

  const commonFields = (
    <div className="grid gap-4 sm:grid-cols-3">
      <div className="space-y-1.5 sm:col-span-3">
        <Label htmlFor="new-character-id">이름 (character id)</Label>
        <Input
          id="new-character-id"
          data-testid="new-character-id"
          value={id}
          placeholder="hero"
          aria-invalid={!!idError}
          onChange={(e) => { setId(e.target.value); setIdTouched(true) }}
        />
        {idError && <p role="alert" className="text-sm text-destructive" data-testid="new-character-id-error">{idError}</p>}
      </div>
      <div className="space-y-1.5">
        <Label>view</Label>
        <Select value={view} onValueChange={(v) => setView(v as View)}>
          <SelectTrigger className="w-full" data-testid="new-view"><SelectValue /></SelectTrigger>
          <SelectContent>{VIEW_OPTIONS.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}</SelectContent>
        </Select>
      </div>
      <div className="space-y-1.5">
        <Label>스타일</Label>
        <Select value={artStyle} onValueChange={(v) => setArtStyle(v as ArtStyle)}>
          <SelectTrigger className="w-full" data-testid="new-art-style"><SelectValue /></SelectTrigger>
          <SelectContent>{ART_STYLE_OPTIONS.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}</SelectContent>
        </Select>
      </div>
    </div>
  )

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-2xl font-semibold">새 캐릭터</h1>
      <Tabs defaultValue="image">
        <TabsList>
          <TabsTrigger value="image" data-testid="tab-image">이미지로 시작</TabsTrigger>
          <TabsTrigger value="text" data-testid="tab-text">설명으로 시작</TabsTrigger>
        </TabsList>

        <TabsContent value="image" className="space-y-4">
          <DropZone
            disabled={busy}
            onFile={pickImage}
          />
          {commonFields}
          <Button disabled={!file || !idValid || busy} onClick={() => createFromImage()} data-testid="create-from-image">
            {busy ? '만드는 중…' : '만들기'}
          </Button>
        </TabsContent>

        <TabsContent value="text" className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="new-description">캐릭터 설명</Label>
            <Textarea
              id="new-description"
              data-testid="new-description"
              value={description}
              placeholder="빨간 두건을 쓴 작은 기사, 강철 갑옷, 등에 검"
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          {commonFields}
          <div className="space-y-1.5">
            <Label>후보 수</Label>
            <Select value={count} onValueChange={setCount}>
              <SelectTrigger className="w-24" data-testid="new-count"><SelectValue /></SelectTrigger>
              <SelectContent>{['1', '2', '3', '4'].map((n) => <SelectItem key={n} value={n}>{n}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <Button
            disabled={!description.trim() || !idValid || busy || (!!job && isActive(job))}
            onClick={generateCandidates}
            data-testid="generate-candidates"
          >
            후보 생성 (약 {formatDuration(Number(count) * SECONDS_PER_CALL)})
          </Button>

          {job && isActive(job) && <JobProgress job={job} />}
          {job?.state === 'failed' && (
            <Alert variant="destructive"><AlertTitle>후보 생성에 실패했습니다</AlertTitle><AlertDescription>{job.error?.message}</AlertDescription></Alert>
          )}
          {attempts.length > 0 && (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                {attempts.map((a) => (
                  <button
                    key={a.attempt}
                    type="button"
                    aria-pressed={candidate === a.attempt}
                    data-testid={`candidate-${a.attempt}`}
                    onClick={() => setCandidate(a.attempt)}
                    className={cn('rounded-lg border-2 bg-muted p-2', candidate === a.attempt ? 'border-primary' : 'border-transparent')}
                  >
                    <img src={`/files/${createdId}/reference/attempts/${a.attempt}/raw.png`} alt={`후보 ${a.attempt}`} className="aspect-square w-full object-contain" />
                  </button>
                ))}
              </div>
              <Button disabled={!candidate || busy} onClick={proceed} data-testid="candidate-proceed">이 캐릭터로 진행</Button>
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
