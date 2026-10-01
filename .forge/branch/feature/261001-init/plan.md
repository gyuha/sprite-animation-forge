<!-- forge-slug: forge-m5-character-tabs -->
<!-- task: 23 -->
<!-- tdd: off -->
# 캐릭터 화면 탭 구성: 스튜디오 | 애니메이션 보기 | 내보내기

## Goal / Non-goals
- Goal: 캐릭터를 열면 세 화면(`/c/:cid/studio…`, `/c/:cid/view`, `/c/:cid/export`)에 공통 탭 바 `스튜디오 | 애니메이션 보기 | 내보내기`가 나오게 한다. 현재 화면의 탭이 선택 상태이고 탭 클릭이 화면 이동이다. **내보내기 탭은 스튜디오에서 모든 유닛이 채택(mirror 파생 포함)된 경우에만 활성화**되고, 비활성이면 사유 tooltip("스튜디오에서 모든 유닛을 채택하면 활성화됩니다 (n/m)")을 보인다. 탭 바는 공통 레이아웃 라우트로 구현해 세 화면이 공유한다. 화면 안에 흩어져 있던 중복 이동 링크(`export-view-link`, `export-studio-link`, `studio-view-link`)는 제거한다. 대시보드 카드의 "애니메이션 보기"·"스튜디오 열기" 버튼, Plan의 `go-export` CTA·"저장 후 스튜디오" 버튼, 일괄 생성 완료 시 export 자동 이동은 그대로 둔다. Identity·Plan 화면에는 탭 바를 넣지 않는다.
- Non-goals: 각 화면의 기능 변경, 내보내기 비활성 상태에서의 URL 직접 접근 차단(페이지는 열리고 기존 누락 경고가 안내), 서버 변경, 내비 헤더 변경.

## Source of truth
- Glossary terms: none
- Related ADRs: none (docs/09 §4 S5·S6, 직전 사용자 피드백으로 상단 내비의 스튜디오·애니메이션·상태·새 캐릭터 링크 제거)
- Definition of Done:
  - `pnpm --dir webui/web typecheck && build && test` 통과, Vitest passed ≥ 183 (baseline 177; 신규 ≥ 6: 탭 3개 렌더·현재 탭 선택 상태, 내보내기 탭 비활성(미채택 있음)+사유 tooltip의 n/m, 활성(전부 채택·mirror 포함), 탭 링크 href, 세 화면에서만 탭 바가 보이고 Identity·Plan에는 없음, 제거된 testid 3종이 더 이상 없음)
  - `pnpm --dir webui/web e2e` passed ≥ 9 (baseline 8; 신규 ≥ 1: 완료된 캐릭터에서 탭으로 세 화면을 오가며 현재 탭 표시, 일부만 채택된 캐릭터에서 내보내기 탭이 비활성이고 마지막 유닛 채택 후 활성) — 기존 e2e 중 제거된 링크를 쓰던 단계는 탭 클릭으로 교체
  - 신규 testid `character-tabs`, `tab-studio`, `tab-view`, `tab-export`(비활성 시 `data-disabled="true"`)가 소스에 존재 (baseline: 0건 — 순방향 검사)
  - `grep -rn "export-view-link\|export-studio-link\|studio-view-link" webui/web/src webui/web/e2e` → 테스트의 "없음" 단언 외 0건 (baseline: 소스 3곳+테스트 다수 — 제거 확인)
  - `uv run pytest -m "not live" -q` 751 passed 유지, 대시보드 카드 버튼 testid(`character-view-<id>`, `character-studio-<id>`)·`go-export` 불변

## Work slices
- [ ] S1. 공통 레이아웃 라우트 `CharacterLayout`(탭 바 + Outlet; shadcn tabs 사용, 내보내기 비활성 규칙·tooltip) + routes.tsx 재구성 + 화면 안 중복 링크 제거 + Vitest — completion criterion: 신규 Vitest ≥ 6 통과, 제거 grep 확인
- [ ] S2. Playwright: 기존 e2e의 제거 링크 단계를 탭 클릭으로 교체 + 신규 탭/활성화 시나리오 — completion criterion: e2e passed ≥ 9 (depends: S1)
