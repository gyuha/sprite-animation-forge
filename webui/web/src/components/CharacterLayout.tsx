/**
 * 캐릭터 화면 공통 레이아웃: 스튜디오 | 애니메이션 보기 | 내보내기 탭 (Identity·Plan 에는 쓰지 않는다).
 * data-testid: character-tabs (탭 바 컨테이너), tab-studio, tab-view, tab-export (비활성이면 data-disabled="true", 이동하지 않음; 활성이면 "false").
 * 내보내기 탭은 모든 유닛이 채택(accepted, 또는 accepted_attempt 가 있는 mirrored)되었을 때만 활성화된다. 로딩 중·유닛 0개면 비활성.
 */
import { Link, Outlet, useLocation, useParams } from 'react-router-dom'
import { useCharacter } from '@/api/queries'
import { ReasonTooltip } from '@/components/ReasonTooltip'
import type { UnitRow } from '@/lib/studio'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'

const adopted = (u: UnitRow) => u.state === 'accepted' || (u.state === 'mirrored' && !!u.accepted_attempt)

export default function CharacterLayout() {
  const { cid = '' } = useParams()
  const { pathname } = useLocation()
  const character = useCharacter(cid)
  const units = (character.data?.status.units ?? []) as unknown as UnitRow[]
  const done = units.filter(adopted).length
  const exportEnabled = units.length > 0 && done === units.length
  const current = pathname.endsWith('/export') ? 'export' : pathname.endsWith('/view') ? 'view' : 'studio'
  const reason = character.isPending
    ? '캐릭터 상태를 불러오는 중입니다'
    : `스튜디오에서 모든 유닛을 채택하면 활성화됩니다 (${done}/${units.length})`

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-4">
        <h1 className="text-lg font-semibold">{cid}</h1>
        <Tabs value={current} data-testid="character-tabs">
          <TabsList>
            <TabsTrigger value="studio" asChild><Link to={`/c/${cid}/studio`} data-testid="tab-studio">스튜디오</Link></TabsTrigger>
            <TabsTrigger value="view" asChild><Link to={`/c/${cid}/view`} data-testid="tab-view">애니메이션 보기</Link></TabsTrigger>
            {exportEnabled ? (
              <TabsTrigger value="export" asChild><Link to={`/c/${cid}/export`} data-testid="tab-export" data-disabled="false">내보내기</Link></TabsTrigger>
            ) : (
              <ReasonTooltip reason={reason}>
                <TabsTrigger value="export" asChild disabled>
                  <span data-testid="tab-export" data-disabled="true" aria-disabled="true" className="cursor-not-allowed opacity-50">내보내기</span>
                </TabsTrigger>
              </ReasonTooltip>
            )}
          </TabsList>
        </Tabs>
      </div>
      <Outlet />
    </div>
  )
}
