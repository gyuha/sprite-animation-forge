# RUN — 캐릭터 화면 탭 구성: 스튜디오 | 애니메이션 보기 | 내보내기

서브에이전트 1개가 구현, 오케스트레이터가 typecheck·build·Vitest·e2e를 재실행하고 스크린샷으로 확인.

## 슬라이스 결과
- S1 `CharacterLayout`(shadcn Tabs + 공통 레이아웃 라우트, 세 화면만), 내보내기 탭 비활성 규칙(전 유닛 채택·mirror는 accepted_attempt 필요·0유닛/로딩 중 비활성, 사유 tooltip "(n/m)"), 화면 안 중복 링크 3종 제거 + Vitest +14 — ✅ as planned
- S2 e2e: 제거된 링크 단계를 탭 클릭으로 교체 + 신규 2건(완료 캐릭터 탭 이동, 일부만 채택된 캐릭터에서 내보내기 탭 비활성→채택 후 활성) — ✅ as planned

## DoD baseline → after
- Vitest 177 → 191 passed(≥183), e2e 8 → 10 passed(≥9, 3회 연속 확인), typecheck·build exit 0, Python 751 passed 유지
- 신규 testid `character-tabs`·`tab-studio`·`tab-view`·`tab-export`(`data-disabled`) 존재(0건 → 존재). 제거한 3종 grep: "없음" 단언 5건 외 0건

## 판단·가정
- 비활성 내보내기 탭은 `<span aria-disabled data-disabled="true">`(링크 아님). `/c/:cid/export` 직접 접근은 막지 않고 페이지의 누락 경고가 안내(계획의 Non-goal).
- Studio 화면에 기존 `← green` 뒤로가기 링크가 남아 캐릭터 id가 두 번 보임(탭 바 머리글 + 링크) — 이번엔 손대지 않음.
- 부수 수정: 불안정하던 `Studio.test.tsx` 단축키 테스트를 모든 상호작용 뒤 단언을 `waitFor`로 감싸 안정화(원인: rAF 플레이어 재렌더와의 타이밍 경합). 5회 연속 전체 실행 통과. 프로덕션 코드 변경 없음.
