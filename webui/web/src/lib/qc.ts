/** QC report presentation (docs/06 2, 6). The server types results/recommendations as plain dicts. */

export type Grade = 'pass' | 'warn' | 'fail' | 'info' | 'not_run'
export interface QcResult { id: string; grade: Grade; value?: number; message?: string }
export type RecommendationType = 'reprocess' | 'regenerate' | 'force_accept'
export interface Recommendation {
  type: RecommendationType
  code: string
  set?: Record<string, string | number | boolean>
  attempt?: string
  reason?: string
  cost?: string
}

export const QC_NAMES: Record<string, { name: string; meaning: string }> = {
  'QC-01': { name: '경계 침범', meaning: '캐릭터가 칸 경계에서 잘렸거나 출력 cell을 벗어남' },
  'QC-02': { name: '크기 변화', meaning: '프레임마다 캐릭터 키가 다른 정도 (최대-최소)/중앙값' },
  'QC-03': { name: '발 위치', meaning: '프레임 간 발 기준선 편차(px)' },
  'QC-04': { name: '가로 중심', meaning: '정렬에 쓰지 않은 가로 지표의 편차' },
  'QC-05': { name: '빈 프레임', meaning: '칸에 전경 픽셀이 거의 없음' },
  'QC-06': { name: '중복 프레임', meaning: '인접 프레임이 거의 같음 (동작이 너무 작음)' },
  'QC-07': { name: '캐릭터 크기', meaning: 'idle 기준 캐릭터 높이 대비 비율' },
  'QC-08': { name: 'Reference 일관성', meaning: '아직 자동 검사하지 않음 (직접 확인)' },
  'QC-09': { name: '배경 키 일치', meaning: '생성된 배경색과 키 색의 거리' },
}

export const GRADE_LABEL: Record<Grade, string> = { pass: '통과', warn: '검토', fail: '실패', info: '참고', not_run: '미실행' }
export const STATUS_LABEL: Record<string, string> = { pass: '통과', warn: '검토 필요', fail: '실패' }

const pct = (v: number) => `${Math.round(v * 100)}%`

/** One human-readable line per result ("크기 변화 7%"); the server's own message wins when present. */
export function describeResult(r: QcResult): string {
  const name = QC_NAMES[r.id]?.name ?? r.id
  if (r.message) return r.message
  if (r.value === undefined) return name
  switch (r.id) {
    case 'QC-02': return `${name} ${pct(r.value)}`
    case 'QC-03': return `${name} 편차 ${r.value}px`
    case 'QC-04': return `${name} 편차 ${Math.round(r.value * 10) / 10}px`
    case 'QC-07': return `${name} idle 대비 ${pct(r.value)}`
    default: return `${name} ${r.value}`
  }
}

export const REPROCESS_LABEL: Record<string, string> = {
  use_preserve: '크기 유지로 재처리',
  use_fit: '맞춤 크기로 재처리',
  anchor_bottom: '기준점을 바닥으로 재처리',
  tighter_merge: '조각 병합 거리를 줄여 재처리',
}
export const REGENERATE_LABEL: Record<string, string> = {
  empty_frame: '빈 칸 없이 재생성',
  edge_touch: '여백을 늘려 재생성',
  character_small: '몸 크기 유지 문구로 재생성',
  fx_in_body: '이펙트를 분리해 재생성',
  scale_drift: '크기 일정하게 재생성',
  bg_mismatch: '배경색 지정으로 재생성',
  duplicate_frames: '동작을 크게 재생성',
  identity_drift: '외형 유지 문구로 재생성',
}

export function recommendationLabel(r: Recommendation): string {
  if (r.type === 'force_accept') return '강제 채택'
  return (r.type === 'reprocess' ? REPROCESS_LABEL : REGENERATE_LABEL)[r.code] ?? (r.type === 'reprocess' ? '재처리' : '재생성')
}
