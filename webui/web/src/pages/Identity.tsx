/**
 * S3 캐릭터 정보(Identity). data-testid:
 *   identity-skeleton               분석 Job 실행 중 필드 대신 보이는 skeleton
 *   identity-field-<key>            텍스트 필드 (silhouette, body_ratio, head_ratio, hair, face, eyes, clothing, weapon,
 *                                   accessories, outline_style, shading_style, camera_angle, orientation)
 *   identity-primary-colors[-input-<i>|-add|-remove-<i>]     주 색상 PaletteEditor
 *   identity-secondary-colors[-input-<i>|-add|-remove-<i>]   보조 색상 PaletteEditor
 *   identity-key-color              배경 키 색 안내 (충돌 시 경고 문구)
 *   identity-analyze                "분석"/"다시 분석" 버튼 (직접 수정한 프로필이면 덮어쓰기 확인 대화상자)
 *   identity-analyze-confirm        덮어쓰기 확인 버튼
 *   identity-save                   저장 (PUT)
 *   identity-save-next              저장 후 플랜으로 이동
 */
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { useSaveIdentity, useStartIdentityAnalyze } from '@/api/mutations'
import { useIdentity, useJobs } from '@/api/queries'
import { isActive } from '@/api/sse'
import { PaletteEditor } from '@/components/PaletteEditor'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '@/components/ui/alert-dialog'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { isHexColor, resolveKeyColor } from '@/lib/color'

type IdentityForm = {
  silhouette: string; body_ratio: string; head_ratio: string; hair: string; face: string; eyes: string; clothing: string
  primary_colors: string[]; secondary_colors: string[]; weapon: string; accessories: string[]
  outline_style: string; shading_style: string; camera_angle: string; orientation: string
}

const EMPTY: IdentityForm = {
  silhouette: '', body_ratio: '', head_ratio: '', hair: '', face: '', eyes: '', clothing: '', primary_colors: [], secondary_colors: [],
  weapon: '', accessories: [], outline_style: '', shading_style: '', camera_angle: '', orientation: '',
}

type TextKey = { [K in keyof IdentityForm]: IdentityForm[K] extends string ? K : never }[keyof IdentityForm]
const FIELDS: { key: TextKey; label: string; long?: boolean }[] = [
  { key: 'silhouette', label: '실루엣', long: true },
  { key: 'body_ratio', label: '비율' },
  { key: 'head_ratio', label: '머리 비율' },
  { key: 'hair', label: '머리카락' },
  { key: 'face', label: '얼굴', long: true },
  { key: 'eyes', label: '눈' },
  { key: 'clothing', label: '의상', long: true },
  { key: 'weapon', label: '무기', long: true },
]
const STYLE_FIELDS: { key: TextKey; label: string }[] = [
  { key: 'outline_style', label: '외곽선' },
  { key: 'shading_style', label: '음영' },
  { key: 'camera_angle', label: '카메라 각도' },
  { key: 'orientation', label: '방향' },
]

const message = (e: unknown) => (e instanceof Error ? e.message : String(e))

export default function Identity() {
  const { cid = '' } = useParams()
  const navigate = useNavigate()
  const identity = useIdentity(cid)
  const jobs = useJobs()
  const save = useSaveIdentity()
  const analyze = useStartIdentityAnalyze()
  const [draft, setDraft] = useState<IdentityForm | null>(null)
  const [accessoriesText, setAccessoriesText] = useState<string | null>(null) // raw text, so a trailing comma survives typing

  const profile = identity.data?.profile
  const form: IdentityForm = draft ?? { ...EMPTY, ...(profile?.identity as Partial<IdentityForm> | undefined) }
  const set = <K extends keyof IdentityForm>(key: K, value: IdentityForm[K]) => setDraft({ ...form, [key]: value })

  const analyzing = !!jobs.data?.some((j) => j.type === 'identity_analyze' && j.character === cid && isActive(j))
  const colorsValid = [...form.primary_colors, ...form.secondary_colors].every(isHexColor)
  const keyColor = resolveKeyColor([...form.primary_colors, ...form.secondary_colors])

  async function startAnalyze() {
    try {
      await analyze.mutateAsync({ cid, force: true })
      setDraft(null)
      setAccessoriesText(null)
    } catch (e) {
      toast.error(message(e))
    }
  }

  async function saveForm(next: boolean) {
    try {
      await save.mutateAsync({ cid, identity: form })
      setDraft(null)
      setAccessoriesText(null)
      toast.success('저장했습니다')
      if (next) navigate(`/c/${cid}/plan`)
    } catch (e) {
      toast.error(message(e))
    }
  }

  const analyzeLabel = profile && profile.source !== 'empty' ? '다시 분석' : '분석'
  const analyzeButton = (
    <Button variant="outline" disabled={analyzing} data-testid="identity-analyze" onClick={profile?.edited_by_user ? undefined : startAnalyze}>
      {analyzing ? '분석 중…' : analyzeLabel}
    </Button>
  )

  return (
    <div className="mx-auto grid max-w-5xl gap-6 md:grid-cols-[16rem_1fr]">
      <div className="space-y-3">
        <h1 className="text-2xl font-semibold">캐릭터 정보</h1>
        <img
          src={`/files/${cid}/reference/character.png`}
          alt={`${cid} reference`}
          className="w-full rounded-lg border bg-[repeating-conic-gradient(#e5e7eb_0%_25%,#fff_0%_50%)] bg-[length:16px_16px] object-contain"
        />
      </div>

      <div className="space-y-4">
        {identity.isError ? (
          <Alert variant="destructive"><AlertTitle>캐릭터 정보를 불러오지 못했습니다</AlertTitle><AlertDescription>{identity.error.message}</AlertDescription></Alert>
        ) : identity.isPending || analyzing ? (
          <div className="space-y-3" data-testid="identity-skeleton">
            {Array.from({ length: 8 }, (_, i) => <Skeleton key={i} className="h-9 w-full" />)}
          </div>
        ) : (
          <>
            {FIELDS.map(({ key, label, long }) => (
              <div key={key} className="space-y-1.5">
                <Label htmlFor={`identity-${key}`}>{label}</Label>
                {long ? (
                  <Textarea id={`identity-${key}`} data-testid={`identity-field-${key}`} rows={2} value={form[key]} onChange={(e) => set(key, e.target.value)} />
                ) : (
                  <Input id={`identity-${key}`} data-testid={`identity-field-${key}`} value={form[key]} onChange={(e) => set(key, e.target.value)} />
                )}
              </div>
            ))}
            <div className="space-y-1.5">
              <Label htmlFor="identity-accessories">액세서리 (쉼표로 구분)</Label>
              <Input
                id="identity-accessories"
                data-testid="identity-field-accessories"
                value={accessoriesText ?? form.accessories.join(', ')}
                onChange={(e) => {
                  setAccessoriesText(e.target.value)
                  set('accessories', e.target.value.split(',').map((s) => s.trim()).filter(Boolean))
                }}
              />
            </div>
            <div className="space-y-1.5">
              <Label>주 색상</Label>
              <PaletteEditor label="주 색상" testId="identity-primary-colors" colors={form.primary_colors} onChange={(c) => set('primary_colors', c)} />
            </div>
            <div className="space-y-1.5">
              <Label>보조 색상</Label>
              <PaletteEditor label="보조 색상" testId="identity-secondary-colors" colors={form.secondary_colors} onChange={(c) => set('secondary_colors', c)} />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              {STYLE_FIELDS.map(({ key, label }) => (
                <div key={key} className="space-y-1.5">
                  <Label htmlFor={`identity-${key}`}>{label}</Label>
                  <Input id={`identity-${key}`} data-testid={`identity-field-${key}`} value={form[key]} onChange={(e) => set(key, e.target.value)} />
                </div>
              ))}
            </div>
            <p className="text-sm text-muted-foreground">이 내용이 모든 생성 프롬프트에 들어갑니다. 영어 짧은 구문으로 적어 주세요.</p>
            <p className="text-sm" data-testid="identity-key-color">
              {keyColor.conflict === 'none' && `ⓘ 배경 키 색: magenta (${keyColor.key}) — 충돌 없음`}
              {keyColor.conflict === 'magenta' && '⚠ 캐릭터 색이 magenta와 가까워 배경 키를 green(#00FF00)으로 바꿉니다'}
              {keyColor.conflict === 'both' && '⚠ 캐릭터 색이 magenta·green 모두와 가깝습니다. magenta(#FF00FF)를 유지하지만 배경 제거 품질이 떨어질 수 있습니다'}
            </p>
          </>
        )}

        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="ghost" asChild><Link to={`/c/${cid}/plan`}>플랜으로</Link></Button>
          {profile?.edited_by_user ? (
            <AlertDialog>
              <AlertDialogTrigger asChild>{analyzeButton}</AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>다시 분석할까요?</AlertDialogTitle>
                  <AlertDialogDescription>직접 수정한 내용이 분석 결과로 덮어써집니다.</AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>취소</AlertDialogCancel>
                  <AlertDialogAction data-testid="identity-analyze-confirm" onClick={startAnalyze}>다시 분석</AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          ) : (
            analyzeButton
          )}
          <Button variant="outline" disabled={analyzing || !colorsValid || save.isPending} data-testid="identity-save" onClick={() => saveForm(false)}>저장</Button>
          <Button disabled={analyzing || !colorsValid || save.isPending} data-testid="identity-save-next" onClick={() => saveForm(true)}>저장 후 다음 →</Button>
        </div>
      </div>
    </div>
  )
}
