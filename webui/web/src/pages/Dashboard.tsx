/**
 * S1 대시보드. data-testid:
 *   new-character-button        "새 캐릭터" 버튼
 *   codex-not-ready-banner      Codex 미준비 경고 배너 (health.ready=false 일 때만)
 *   copy-codex-login            `codex login` 복사 버튼
 *   dashboard-empty             캐릭터가 하나도 없을 때의 빈 상태
 *   character-card-<id>         캐릭터 카드(링크)
 *   character-view-<id>         카드 아래 "애니메이션 보기" 버튼(/c/<id>/view)
 *   character-progress-<id>     채택 unit 진행 막대
 *   character-next-<id>         다음 할 일 배지
 *   character-batch-<id>        진행 중인 일괄 생성 문구 ("hero: 2/4 · walk 생성 중") + 진행 막대(data-percent)
 */
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { AlertTriangle, Play, Plus } from 'lucide-react'
import { useCharacters, useHealth, useJobs, type CharacterCard } from '@/api/queries'
import { isActive, type JobSnapshot } from '@/api/sse'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Skeleton } from '@/components/ui/skeleton'
import { summarizeBatch } from '@/lib/batch'

const NEXT_STEP: Record<CharacterCard['next_step'], { label: string; to: (id: string) => string }> = {
  reference: { label: 'reference 필요', to: () => '/new' },
  plan: { label: '플랜 필요', to: (id) => `/c/${id}/plan` },
  generate: { label: '생성 필요', to: (id) => `/c/${id}/studio` },
  export: { label: '✓ 내보내기 가능', to: (id) => `/c/${id}/export` },
}

function CodexBanner({ warnings }: { warnings: string[] }) {
  const copy = () => navigator.clipboard.writeText('codex login').then(() => toast.success('복사했습니다'), () => toast.error('복사하지 못했습니다'))
  return (
    <Alert className="border-yellow-500/50 bg-yellow-50 text-yellow-900 dark:bg-yellow-950/30 dark:text-yellow-200" data-testid="codex-not-ready-banner">
      <AlertTriangle />
      <AlertTitle>Codex를 사용할 수 없습니다</AlertTitle>
      <AlertDescription className="space-y-2">
        <ul className="list-disc pl-4">
          {warnings.map((w) => <li key={w}>{w}</li>)}
        </ul>
        <p>
          터미널에서 <code className="rounded bg-muted px-1">codex login</code> 을 실행한 뒤 다시 확인하세요. 이미지 업로드 경로는 계속 사용할 수 있습니다.
        </p>
        <Button size="sm" variant="outline" onClick={copy} data-testid="copy-codex-login">명령 복사</Button>
      </AlertDescription>
    </Alert>
  )
}

function BatchLine({ job }: { job: JobSnapshot }) {
  const s = summarizeBatch(job)
  return (
    <div className="space-y-1" data-testid={`character-batch-${job.character}`} data-percent={Math.round(s.percent)}>
      <p className="text-xs">{s.text}</p>
      <Progress value={s.percent} aria-label={`${job.character} 일괄 생성 진행률`} />
    </div>
  )
}

function CharacterCardView({ c, batch }: { c: CharacterCard; batch?: JobSnapshot }) {
  const next = NEXT_STEP[c.next_step]
  const pct = c.units_total ? (c.units_accepted / c.units_total) * 100 : 0
  return (
    <div className="flex flex-col gap-2">
    <Link to={next.to(c.id)} className="flex-1" data-testid={`character-card-${c.id}`}>
      <Card className="h-full transition-colors hover:bg-muted/50">
        <CardHeader>
          <CardTitle>{c.id}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {c.has_reference && (
            <img src={`/files/${c.id}/reference/character.png`} alt={`${c.id} reference`} className="h-32 w-full rounded bg-muted object-contain" />
          )}
          <Progress value={pct} aria-label={`${c.id} 진행률`} data-testid={`character-progress-${c.id}`} />
          {batch && <BatchLine job={batch} />}
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">{c.units_accepted}/{c.units_total} 채택</span>
            <Badge variant={c.next_step === 'export' ? 'default' : 'secondary'} data-testid={`character-next-${c.id}`}>{next.label}</Badge>
          </div>
        </CardContent>
      </Card>
    </Link>
    <Button asChild variant="outline" size="sm">
      <Link to={`/c/${c.id}/view`} data-testid={`character-view-${c.id}`}><Play /> 애니메이션 보기</Link>
    </Button>
    </div>
  )
}

export default function Dashboard() {
  const characters = useCharacters()
  const health = useHealth()
  const jobs = useJobs()
  const batches = ((jobs.data ?? []) as JobSnapshot[]).filter((j) => j.type === 'batch_generate' && isActive(j))
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">캐릭터</h1>
        <Button asChild data-testid="new-character-button">
          <Link to="/new"><Plus /> 새 캐릭터</Link>
        </Button>
      </div>

      {health.data && !health.data.ready && <CodexBanner warnings={health.data.warnings} />}

      {characters.isPending && <Skeleton className="h-48 w-full" />}
      {characters.isError && (
        <Alert variant="destructive"><AlertTitle>캐릭터 목록을 불러오지 못했습니다</AlertTitle><AlertDescription>{characters.error.message}</AlertDescription></Alert>
      )}
      {characters.data?.length === 0 && (
        <Card data-testid="dashboard-empty">
          <CardContent className="space-y-3 py-10 text-center">
            <p className="text-muted-foreground">캐릭터 이미지를 끌어다 놓거나, 설명으로 새 캐릭터를 만드세요</p>
            <Button asChild variant="outline"><Link to="/new">새 캐릭터 만들기</Link></Button>
          </CardContent>
        </Card>
      )}
      {!!characters.data?.length && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {characters.data.map((c) => <CharacterCardView key={c.id} c={c} batch={batches.find((j) => j.character === c.id)} />)}
        </div>
      )}
    </div>
  )
}
