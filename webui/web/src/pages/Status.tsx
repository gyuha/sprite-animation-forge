/**
 * S7 상태. data-testid:
 *   status-check-<install|version|login|feature|home|python>   Codex 진단 항목 (data-ok=true|false). 실패하면 해결 명령과 복사 버튼:
 *     status-fix-<name>, status-copy-<name>
 *   status-video                    동영상 방식(선택) 연결 상태 (data-ok=true|false, 안 되어 있어도 오류 아님), 미연결 시 안내 status-video-hint
 *   status-recheck                  "다시 확인" — GET /api/health?refresh=1 (서버 60초 캐시 무시)
 *   status-contract-hint            검증 버전과 현재 Codex 버전이 다를 때: 계약 테스트 실행 안내 (status-copy-contract)
 *   status-server                   서버 연결 / 진행 중 작업 수
 *   usage-table, usage-row-<id>, usage-total   캐릭터별·전체 Codex 호출 수 / 입력·캐시·출력 토큰 (manifest.usage)
 *   usage-note                      서버가 기록하지 않아 표시할 수 없는 항목(평균 생성 시간) 안내
 */
import { useQueries } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Check, Copy, X } from 'lucide-react'
import { api } from '@/api/client'
import { useRecheckHealth } from '@/api/mutations'
import { qk, useCharacters, useHealth, useJobs, type CharacterDetail, type Health, type Usage } from '@/api/queries'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

interface Check { name: string; label: string; ok: boolean; detail: string; fix: string }

/** docs/03 11: one row per doctor check, with the command that fixes it. */
function doctorChecks(h: Health): Check[] {
  const c = h.codex
  const missingDeps = Object.entries(h.python).filter(([, v]) => v === null).map(([k]) => k)
  return [
    { name: 'install', label: 'Codex 설치', ok: c.installed, detail: c.version ?? '', fix: 'npm install -g @openai/codex' },
    { name: 'version', label: 'Codex 버전 (≥ 0.159.0)', ok: c.installed && c.version_ok, detail: c.version ?? '', fix: 'npm install -g @openai/codex@latest' },
    { name: 'login', label: '로그인', ok: c.logged_in, detail: c.auth ?? '', fix: 'codex login' },
    { name: 'feature', label: 'image_generation 기능', ok: c.image_generation, detail: '', fix: 'codex features enable image_generation' },
    { name: 'home', label: '저장 경로 ($CODEX_HOME)', ok: !h.warnings.some((w) => w.startsWith('codex_home_')), detail: c.codex_home ?? '', fix: 'mkdir -p ~/.codex' },
    { name: 'python', label: 'Python 의존성 (Pillow · NumPy · SciPy)', ok: missingDeps.length === 0, detail: missingDeps.length ? `없음: ${missingDeps.join(', ')}` : '', fix: 'uv sync' },
  ]
}

const copy = (text: string) => navigator.clipboard.writeText(text).then(() => toast.success('복사했습니다'), () => toast.error('복사하지 못했습니다'))
const CONTRACT_TEST = 'pytest -m live'
const n = (v: number) => v.toLocaleString('ko-KR')

function CopyButton({ text, testid }: { text: string; testid: string }) {
  return <Button size="xs" variant="outline" onClick={() => copy(text)} data-testid={testid}><Copy /> 복사</Button>
}

function Usage() {
  const characters = useCharacters()
  const ids = characters.data?.map((c) => c.id) ?? []
  const details = useQueries({
    queries: ids.map((id) => ({ queryKey: qk.character(id), queryFn: () => api<CharacterDetail>(`/api/characters/${id}`) })),
  })
  const rows = ids.map((id, i) => ({ id, usage: details[i].data?.manifest.usage as Usage | undefined }))
  const sum = (key: keyof Usage) => rows.reduce((t, r) => t + (r.usage?.[key] ?? 0), 0)
  return (
    <Card>
      <CardHeader><CardTitle>Codex 사용량</CardTitle></CardHeader>
      <CardContent className="space-y-2">
        {characters.isPending && <Skeleton className="h-24 w-full" />}
        {characters.isError && <p className="text-sm text-destructive">{characters.error.message}</p>}
        {characters.data && (
          <Table data-testid="usage-table">
            <TableHeader>
              <TableRow><TableHead>캐릭터</TableHead><TableHead className="text-right">호출 수</TableHead><TableHead className="text-right">입력 토큰</TableHead><TableHead className="text-right">(캐시)</TableHead><TableHead className="text-right">출력 토큰</TableHead></TableRow>
            </TableHeader>
            <TableBody>
              {rows.map(({ id, usage }) => (
                <TableRow key={id} data-testid={`usage-row-${id}`}>
                  <TableCell className="font-medium">{id}</TableCell>
                  <TableCell className="text-right">{n(usage?.codex_calls ?? 0)}</TableCell>
                  <TableCell className="text-right">{n(usage?.input_tokens ?? 0)}</TableCell>
                  <TableCell className="text-right">{n(usage?.cached_input_tokens ?? 0)}</TableCell>
                  <TableCell className="text-right">{n(usage?.output_tokens ?? 0)}</TableCell>
                </TableRow>
              ))}
              <TableRow className="font-semibold" data-testid="usage-total">
                <TableCell>전체</TableCell>
                <TableCell className="text-right">{n(sum('codex_calls'))}</TableCell>
                <TableCell className="text-right">{n(sum('input_tokens'))}</TableCell>
                <TableCell className="text-right">{n(sum('cached_input_tokens'))}</TableCell>
                <TableCell className="text-right">{n(sum('output_tokens'))}</TableCell>
              </TableRow>
            </TableBody>
          </Table>
        )}
        <p className="text-xs text-muted-foreground" data-testid="usage-note">평균 생성 시간은 서버가 캐릭터별로 집계하지 않아 표시하지 않습니다 (manifest.usage 에는 호출 수와 토큰만 있음).</p>
      </CardContent>
    </Card>
  )
}

export default function Status() {
  const health = useHealth()
  const jobs = useJobs()
  const recheck = useRecheckHealth()
  const h = health.data
  const active = jobs.data?.filter((j) => j.state === 'queued' || j.state === 'running').length ?? 0
  const versionDiffers = !!h?.codex.version && !!h.codex.tested_version && h.codex.version !== h.codex.tested_version

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">상태</h1>
        <Button variant="outline" disabled={recheck.isPending} onClick={() => recheck.mutate(undefined, { onError: (e) => toast.error(e.message) })} data-testid="status-recheck">
          다시 확인
        </Button>
      </div>

      <Card>
        <CardHeader><CardTitle>Codex 진단</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          {health.isPending && <Skeleton className="h-32 w-full" />}
          {health.isError && <p className="text-sm text-destructive">{health.error.message}</p>}
          {h && doctorChecks(h).map((c) => (
            <div key={c.name} className="flex flex-wrap items-center gap-3 rounded-md border px-3 py-2 text-sm" data-testid={`status-check-${c.name}`} data-ok={c.ok}>
              {c.ok ? <Check className="size-4 text-green-600" aria-label="통과" /> : <X className="size-4 text-destructive" aria-label="실패" />}
              <span className="font-medium">{c.label}</span>
              <span className="text-muted-foreground">{c.detail}</span>
              {!c.ok && (
                <span className="ml-auto flex items-center gap-2">
                  <code className="rounded bg-muted px-1.5 py-0.5" data-testid={`status-fix-${c.name}`}>{c.fix}</code>
                  <CopyButton text={c.fix} testid={`status-copy-${c.name}`} />
                </span>
              )}
            </div>
          ))}
          {h && h.warnings.length > 0 && <ul className="list-disc pl-5 text-xs text-muted-foreground">{h.warnings.map((w) => <li key={w}>{w}</li>)}</ul>}
        </CardContent>
      </Card>

      {versionDiffers && h && (
        <Alert data-testid="status-contract-hint">
          <AlertTitle>계약 테스트를 실행하세요</AlertTitle>
          <AlertDescription>
            <p>검증된 Codex 버전은 {h.codex.tested_version}, 현재는 {h.codex.version} 입니다. 업데이트 후에는 실제 Codex로 한 번 확인해야 합니다.</p>
            <div className="mt-2 flex items-center gap-2">
              <code className="rounded bg-muted px-1.5 py-0.5">{CONTRACT_TEST}</code>
              <CopyButton text={CONTRACT_TEST} testid="status-copy-contract" />
            </div>
          </AlertDescription>
        </Alert>
      )}

      {h?.video && (
        <Card>
          <CardHeader><CardTitle>동영상 방식 (선택)</CardTitle></CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="flex flex-wrap items-center gap-3 rounded-md border px-3 py-2" data-testid="status-video" data-ok={h.video.configured}>
              {h.video.configured ? <Check className="size-4 text-green-600" aria-label="연결됨" /> : <X className="size-4 text-muted-foreground" aria-label="연결 안 됨" />}
              <span className="font-medium">{h.video.provider}</span>
              <span className="text-muted-foreground">{h.video.configured ? `연결됨 (${h.video.auth})` : '연결 안 됨'}</span>
            </div>
            {!h.video.configured && (
              <p className="text-xs text-muted-foreground" data-testid="status-video-hint">
                이미지 방식만 쓸 거라면 필요 없습니다. 동영상 방식을 쓰려면 docs/13-video-api-setup.md 를 따라 연결하세요.
              </p>
            )}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader><CardTitle>서버</CardTitle></CardHeader>
        <CardContent className="text-sm" data-testid="status-server">
          {health.isError ? '서버에 연결할 수 없습니다' : `연결됨 · 진행 중인 작업 ${active}개`}
        </CardContent>
      </Card>

      <Usage />
    </div>
  )
}
