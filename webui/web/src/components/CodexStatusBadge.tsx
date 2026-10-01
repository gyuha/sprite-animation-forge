import { useHealth } from '@/api/queries'
import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'

export function CodexStatusBadge() {
  const { data, isPending, isError } = useHealth()

  let label = 'Codex 준비됨'
  let variant: 'default' | 'secondary' | 'destructive' = 'default'
  let hint = data?.codex.version ? `Codex ${data.codex.version}` : ''
  if (isPending) {
    label = 'Codex 확인 중'
    variant = 'secondary'
  } else if (isError) {
    label = '상태 확인 실패'
    variant = 'destructive'
    hint = '서버의 /api/health에 연결할 수 없습니다'
  } else if (!data.ready) {
    label = 'Codex 미준비'
    variant = 'destructive'
    hint = data.warnings.join('\n')
  }

  const badge = <Badge variant={variant}>{label}</Badge>
  if (!hint) return badge
  return (
    <Tooltip>
      <TooltipTrigger asChild>{badge}</TooltipTrigger>
      <TooltipContent className="whitespace-pre-line">{hint}</TooltipContent>
    </Tooltip>
  )
}
