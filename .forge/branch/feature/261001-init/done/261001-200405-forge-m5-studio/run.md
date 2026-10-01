# RUN — M5-c: S5 액션 스튜디오

서브에이전트 1개가 구현, 오케스트레이터가 DoD 재실행으로 확인. 브라우저 검증은 아직 없음(M5-e E2E가 보강).

## 슬라이스 결과
- S1 AnimationPlayer·GridOverlay·CompareSlider + 순수 로직(`lib/player.ts`, `lib/grid.ts`) — ✅ as planned
- S2 QcPanel·RecommendationButtons·ReprocessPanel·AttemptStrip (+ReasonTooltip) — ✅ as planned
- S3 Studio 페이지 조립(액션/방향/보기 탭, 프롬프트 dialog, 단축키, SSE 무효화) — ✅ as planned (미구현 목록은 아래)

## DoD baseline → after
- typecheck/build exit 0, Vitest: 58 → 94 passed (신규 36, ≥12)
- 방향 탭은 plan 방향 ≥2일 때만, 모든 호출에 `?direction=` 포함, mirror `left` 탭의 생성·재처리·채택 비활성+사유 tooltip — 테스트 단언
- `Direction` 타입 결함(`front|back`) → `down|up|right|left` 수정(+테스트)

## 판단·가정 (후속 task가 알아야 함)
- 중요: 서버 process의 `set`은 이전 재처리 위에 누적되지 않고 plan 값 위에 적용됨 → UI(패널·권장 조치)는 항상 12개 키 전체를 보냄(요청 본문 테스트로 고정).
- Playwright용 관측점: `preview-canvas`의 `data-version`(프레임 URL `?v=` 해시 결합)이 재처리 완료 시 바뀜. data-testid 전체 목록은 `Studio.tsx` 상단 주석(주요: `studio-page action-tab-<a> direction-tab-<d> generate-button attempt-<NNN> accept-button accept-confirm reprocess-<param> reprocess-save preview-canvas qc-panel rec-<type>-<code> interrupted-badge-<NNN> regenerate-button`).
- 라우트 `/c/:cid/studio/:action?/:direction?`, 없으면 첫 액션/대표 방향으로 redirect. 단축키: Space, ←/→, O, G, A(입력류·슬라이더·다이얼로그 포커스 시 무시).
- mirror `left`는 `/files/<cid>/<action>/left/frames/NNN.png`를 plan 프레임 수로 추정해 읽기 전용 표시(서버 GET attempts가 빈 목록+`mirror_of`만 반환하기 때문).
- 제외: idle 오버레이·창 맞춤 배율, 사용자 지정 배경색, QC 문제 프레임 테두리, prompt dialog 블록 색, Job 취소 버튼, 4방향 비교 보기, "별도로 생성"(mirror 해제 — Plan 화면 링크만).
- 백엔드 한계: `qc.results/recommendations/derived`와 status units가 OpenAPI에서 dict로 타입 없음 → 프런트 수기 타입(`lib/qc.ts`, `lib/grid.ts`, `lib/studio.ts`), mirror `left` 파일은 `?v=` 없이 `no-cache`.
