# RUN — 완료된 캐릭터도 스튜디오로 들어갈 수 있게 진입 링크 추가

워크플로 없이 오케스트레이터가 직접 처리(링크 3개 + 테스트, 소규모).

## 슬라이스 결과
- S1 Dashboard 카드 "스튜디오 열기"(`character-studio-<id>`), AppLayout 내비 "스튜디오"(`nav-studio`, `/c/:cid/*`에서만), Export "스튜디오"(`export-studio-link`, 누락 유닛 없어도 항상) + Vitest 5건(`src/studio-entry.test.tsx`) — ✅ as planned
- S2 Playwright `e2e/studio-entry.spec.ts`: 배치로 완료된 캐릭터에서 세 경로 모두 `studio-page` 도달, 채택 배지·생성 버튼 활성까지 확인 — ✅ as planned

## DoD baseline → after
- Vitest: 171 → 176 passed (≥175), typecheck·build exit 0
- e2e: 7 → 8 passed (≥8)
- 신규 testid 3종 소스 존재: 0건 → 3종 (forward check)
- Python: 751 passed 유지, 기존 testid(`character-card-<id>`·`character-view-<id>`·`nav-view`·`export-view-link`·`studio-view-link`) 불변(카드 본문 href는 완료 시 export 유지 — 테스트가 단언)

## 판단·가정·막힌 곳
- 첫 시도에서 Dashboard가 통째로 깨짐: `Clapperboard` import를 넣는 sed가 macOS sed 문법 오류로 조용히 실패(앞선 명령 체인이 `;`가 아니라 개행이라 오류 후에도 진행) → typecheck 오류 + 기존 Dashboard 테스트 8건 실패로 즉시 발견, import를 직접 수정해 해결.
- AppLayout을 렌더하는 신규 테스트는 jsdom에 `EventSource`·`matchMedia`가 없어 테스트 안에서 스텁(기존 test-setup은 건드리지 않음).
- 서버·Core 변경 없음.

## 후속 변경 (사용자 피드백, 같은 task 안에서 정정)
- 상단 내비의 "새 캐릭터"(대시보드에 같은 버튼이 있음)와 캐릭터 화면의 "스튜디오"·"애니메이션" 링크(`nav-studio`·`nav-view`)를 제거. 진입 경로는 대시보드 카드 버튼 2개와 내보내기 화면 링크(`export-studio-link`·`export-view-link`), 스튜디오의 `studio-view-link`로 유지. 계획의 DoD 중 "내비 링크" 항목은 사용자 결정으로 폐기(테스트는 "내비에 없음"을 단언하도록 교체).
- 재확인: Vitest 175 passed(≥175), e2e 8 passed, typecheck exit 0.
