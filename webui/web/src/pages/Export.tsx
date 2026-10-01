/**
 * S6 내보내기. data-testid:
 *   export-engine                   엔진 select 트리거 (Phaser 기본 / Generic). 서버 export 는 항상 두 형식을 모두 쓰므로 안내·스니펫만 바뀐다
 *   export-view-link                "애니메이션 보기" → /c/:id/view
 *   export-run                      "내보내기 실행" → POST /api/characters/:id/export
 *   export-warnings                 export 응답의 warnings (missing_actions 제외)
 *   export-missing-alert            누락 unit 경고. export-missing-link-<unit> = 해당 Studio 링크
 *   export-zip                      "ZIP 다운로드": <a href="/api/characters/:id/export.zip" download>. export 전에는 비활성 버튼
 *   export-files, export-file-<path>   파일별 개별 다운로드 링크 (예: export-file-atlas/hero.png)
 *   atlas-preview, atlas-info, atlas-row-label-<unit>   atlas 이미지 / 크기 / 행마다 unit 이름 (meta.json 의 row)
 *   export-qc-table, export-qc-row-<unit>(data-forced)   unit별 QC 요약. 강제 채택 행은 강조 + export-forced-badge-<unit>
 *   phaser-snippet, phaser-copy     Phaser 코드(id·origin 채움) / 복사 (엔진=Phaser 일 때)
 *   generic-note                    엔진=Generic 일 때 안내 (atlas/<id>.generic.json 링크)
 * 배치 완료 CTA(go-export)로 들어오면(location.state.autoExport) 누락 unit이 없을 때 내보내기를 자동 실행한다.
 */
import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { Copy } from 'lucide-react'
import { useExport } from '@/api/mutations'
import { useCharacter, useExportMeta } from '@/api/queries'
import { ReasonTooltip } from '@/components/ReasonTooltip'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { missingUnits, phaserSnippet, rowTopPercent, studioPath } from '@/lib/export'
import { STATUS_LABEL } from '@/lib/qc'
import type { UnitRow } from '@/lib/studio'

type Row = UnitRow & { forced?: boolean; score?: number | null }
interface ExportRecord { exported_at: string; files: Record<string, string> }

const STATE_LABEL: Record<UnitRow['state'], string> = { pending: '대기', imported: '가져옴', processed: '처리됨', accepted: '채택', mirrored: '반전 파생' }

export default function Export() {
  const { cid = '' } = useParams()
  const autoExport = (useLocation().state as { autoExport?: boolean } | null)?.autoExport === true
  const character = useCharacter(cid)
  const exportM = useExport()
  const [engine, setEngine] = useState('phaser')
  const [result, setResult] = useState<{ files: string[]; warnings: string[] } | null>(null)

  const rows = (character.data?.status.units ?? []) as unknown as Row[]
  const missing = missingUnits(rows)
  const record = (character.data?.manifest.exports as { phaser?: ExportRecord } | undefined)?.phaser
  const exported = !!record || !!result
  const meta = useExportMeta(cid, exported).data

  const run = () =>
    exportM.mutate(cid, {
      onSuccess: (r) => { setResult(r); toast.success('내보냈습니다') },
      onError: (e) => toast.error(e.message),
    })

  const autoRan = useRef(false)
  useEffect(() => {
    if (autoExport && character.data && missing.length === 0 && !autoRan.current) {
      autoRan.current = true
      run()
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoExport, character.data])

  if (character.isPending) return <Skeleton className="mx-auto h-64 max-w-4xl" />
  if (character.isError) {
    return <Alert variant="destructive"><AlertTitle>캐릭터를 불러오지 못했습니다</AlertTitle><AlertDescription>{character.error.message}</AlertDescription></Alert>
  }

  const files = result?.files ?? Object.keys(record?.files ?? {}).sort()
  const warnings = (result?.warnings ?? []).filter((w) => !w.startsWith('missing_actions'))
  const hash = record?.files[`atlas/${cid}.png`]?.replace('sha256:', '').slice(0, 12) ?? record?.exported_at ?? 'new'
  const copy = (text: string) => navigator.clipboard.writeText(text).then(() => toast.success('복사했습니다'), () => toast.error('복사하지 못했습니다'))
  const nothingAccepted = rows.every((r) => r.state !== 'accepted')

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">내보내기 · {cid}</h1>
        <div className="flex items-center gap-3">
          <Button asChild variant="outline"><Link to={`/c/${cid}/view`} data-testid="export-view-link">애니메이션 보기</Link></Button>
          <Label>엔진</Label>
          <Select value={engine} onValueChange={setEngine}>
            <SelectTrigger className="w-32" data-testid="export-engine"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="phaser">Phaser</SelectItem>
              <SelectItem value="generic">Generic</SelectItem>
            </SelectContent>
          </Select>
          <ReasonTooltip reason={nothingAccepted ? '채택된 액션이 없습니다' : null}>
            <Button disabled={exportM.isPending || nothingAccepted} onClick={run} data-testid="export-run">내보내기 실행</Button>
          </ReasonTooltip>
        </div>
      </div>

      {missing.length > 0 && (
        <Alert className="border-yellow-500/50 bg-yellow-50 text-yellow-900 dark:bg-yellow-950/30 dark:text-yellow-200" data-testid="export-missing-alert">
          <AlertTitle>채택되지 않은 액션이 {missing.length}개 있습니다</AlertTitle>
          <AlertDescription>
            <p>이 액션은 atlas에 들어가지 않습니다. 스튜디오에서 생성·채택하세요.</p>
            <ul className="mt-1 flex flex-wrap gap-3">
              {missing.map((r) => (
                <li key={r.unit}>
                  <Link className="underline" to={studioPath(cid, r.unit)} data-testid={`export-missing-link-${r.unit}`}>{r.unit}</Link>
                </li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}
      {warnings.length > 0 && (
        <Alert data-testid="export-warnings"><AlertTitle>경고</AlertTitle><AlertDescription>{warnings.join(' · ')}</AlertDescription></Alert>
      )}

      <section className="space-y-3">
        <h2 className="font-semibold">QC 요약</h2>
        <Table data-testid="export-qc-table">
          <TableHeader>
            <TableRow><TableHead>unit</TableHead><TableHead>상태</TableHead><TableHead>QC</TableHead><TableHead>점수</TableHead><TableHead>채택본</TableHead><TableHead /></TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((r) => (
              <TableRow key={r.unit} data-testid={`export-qc-row-${r.unit}`} data-forced={!!r.forced} className={r.forced ? 'bg-destructive/10' : undefined}>
                <TableCell className="font-medium">{r.unit}</TableCell>
                <TableCell>{STATE_LABEL[r.state]}</TableCell>
                <TableCell>{r.qc_status ? (STATUS_LABEL[r.qc_status] ?? r.qc_status) : '-'}</TableCell>
                <TableCell>{r.score ?? '-'}</TableCell>
                <TableCell>{r.accepted_attempt ?? '-'}</TableCell>
                <TableCell>{r.forced && <Badge variant="destructive" data-testid={`export-forced-badge-${r.unit}`}>강제 채택</Badge>}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </section>

      {exported && (
        <section className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="font-semibold">결과 파일</h2>
            <Button asChild data-testid="export-zip">
              <a href={`/api/characters/${cid}/export.zip`} download={`${cid}.zip`}>ZIP 다운로드</a>
            </Button>
          </div>
          {meta && (
            <p className="text-sm text-muted-foreground" data-testid="atlas-info">
              atlas {meta.texture.size[0]} × {meta.texture.size[1]}px · cell {meta.cell.w} × {meta.cell.h} · origin ({meta.origin.x}, {meta.origin.y})
            </p>
          )}
          <div className="relative w-full overflow-hidden rounded border bg-muted" data-testid="atlas-preview">
            <img src={`/files/${cid}/atlas/${cid}.png?v=${hash}`} alt={`${cid} atlas`} className="w-full" style={{ imageRendering: 'pixelated' }} />
            {meta?.actions.map((a) => (
              <span key={a.unit} className="absolute left-1 rounded bg-black/70 px-1 text-xs text-white" style={{ top: `${rowTopPercent(meta, a.row)}%` }} data-testid={`atlas-row-label-${a.unit}`}>
                {a.unit}
              </span>
            ))}
          </div>
          <ul className="grid gap-1 text-sm sm:grid-cols-2" data-testid="export-files">
            {files.map((f) => (
              <li key={f}>
                <a className="underline" href={`/files/${cid}/${f}`} download={f.split('/').pop()} data-testid={`export-file-${f}`}>{f}</a>
              </li>
            ))}
          </ul>
        </section>
      )}
      {!exported && (
        <ReasonTooltip reason="먼저 내보내기를 실행하세요">
          <Button disabled data-testid="export-zip">ZIP 다운로드</Button>
        </ReasonTooltip>
      )}

      {exported && meta && engine === 'phaser' && (
        <section className="space-y-2">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">Phaser 사용 예</h2>
            <Button size="sm" variant="outline" onClick={() => copy(phaserSnippet(cid, meta))} data-testid="phaser-copy"><Copy /> 복사</Button>
          </div>
          <pre className="overflow-auto rounded-md bg-muted p-3 text-xs" data-testid="phaser-snippet">{phaserSnippet(cid, meta)}</pre>
          <p className="text-sm text-muted-foreground">픽셀 아트 스타일이면 게임 설정에 <code>pixelArt: true</code>를 두세요.</p>
        </section>
      )}
      {exported && engine === 'generic' && (
        <p className="text-sm text-muted-foreground" data-testid="generic-note">
          엔진 무관 형식은 <a className="underline" href={`/files/${cid}/atlas/${cid}.generic.json`} download>atlas/{cid}.generic.json</a> 입니다 (같은 {cid}.png를 참조).
        </p>
      )}
    </div>
  )
}
