<!-- forge-slug: forge-m5-studio-entry-for-completed -->
<!-- task: 22 -->
<!-- tdd: off -->
# 완료된 캐릭터도 스튜디오로 들어갈 수 있게 진입 링크 추가

## Goal / Non-goals
- Goal: 모든 유닛이 채택된 캐릭터는 대시보드 카드가 곧바로 내보내기로 연결되고 스튜디오로 가는 길이 "미채택 유닛" 경고에만 있어서, 완료된 캐릭터를 고치러 스튜디오에 들어갈 수 없다. 스튜디오 화면 자체는 완료된 유닛에서도 정상 동작하므로(재생·재처리·다시 생성·채택 변경) 진입 경로만 추가한다: (1) 대시보드 카드에 "스튜디오 열기" 버튼(기존 "애니메이션 보기" 버튼 옆), (2) 캐릭터 안 상단 내비(`/c/:cid/*`)에 "스튜디오" 링크, (3) 내보내기 화면에 "스튜디오" 링크(누락 유닛이 없어도 항상 표시). 링크 대상은 `/c/:cid/studio`(기존 redirect가 첫 액션·대표 방향으로 보냄).
- Non-goals: 카드 본문 클릭 동작 변경(완료 시 계속 내보내기), 뷰어 타일 클릭→스튜디오 이동, 스튜디오 화면 기능 변경, 서버 변경.

## Source of truth
- Glossary terms: none
- Related ADRs: none (docs/09 §4 S1·S5·S6, 직전 retro `forge-m5-studio`·뷰어 작업의 진입 링크 구조)
- Definition of Done:
  - `pnpm --dir webui/web typecheck && build && test` 통과, Vitest passed ≥ 175 (baseline 171; 신규 ≥ 4: 카드 버튼 href·완료 캐릭터(next_step=export)에서도 표시·카드 본문 href는 export 유지, 내비 링크는 `/c/:cid/*`에서만 표시, 내보내기 링크는 누락 유닛 0건일 때도 표시)
  - `pnpm --dir webui/web e2e` passed ≥ 8 (baseline 7; 신규: 배치로 완료된 캐릭터에서 대시보드 `character-studio-<id>` → `studio-page`, 내비 `nav-studio` → `studio-page`, 내보내기 `export-studio-link` → `studio-page`)
  - 신규 data-testid `character-studio-<id>`, `nav-studio`, `export-studio-link`가 소스에 존재 (baseline: `grep -rc` 0건 — 순방향 검사)
  - 기존 Python 테스트 `uv run pytest -m "not live" -q` 751 passed 유지, 기존 data-testid(`character-card-<id>`, `character-view-<id>`, `nav-view`, `export-view-link`, `studio-view-link`) 불변

## Work slices
- [ ] S1. Dashboard 카드 "스튜디오 열기"(`character-studio-<id>`), AppLayout 내비 "스튜디오"(`nav-studio`), Export "스튜디오"(`export-studio-link`) 링크 + Vitest — completion criterion: 신규 Vitest ≥ 4 통과
- [ ] S2. Playwright 신규 테스트(완료 캐릭터에서 세 경로 모두 스튜디오 도달) — completion criterion: e2e passed ≥ 8 (depends: S1)
