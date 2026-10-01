# RUN — M5-e: Playwright E2E 스모크 · 단일 실행 · Taskfile

서브에이전트 1개가 구현, 오케스트레이터가 e2e를 재실행해 확인(4 passed, 잔류 프로세스 0).

## 슬라이스 결과
- S1 Playwright 설정·`fixtures.ts`(테스트별 임시 root/포트 서버, 프로세스 그룹+자손 SIGKILL로 fake codex 누수 방지)·globalSetup(build + 참조 PNG 생성, 바이너리 미커밋) — ✅ as planned
- S2 시나리오 (a) 4조작 ZIP — ✅ as planned (조작 계측: `userActions` 래퍼가 upload/select/click/download를 기록, 정확히 4건 단언; ZIP은 `zipfile.testzip()`과 atlas png/json·animations.json 포함 확인)
- S3 시나리오 (b) 재처리 2초 갱신(측정 424~436ms, 300ms 디바운스 포함), (c) 서버 SIGKILL 후 재기동 → `중단됨` 배지 → 재생성 성공 — ✅ as planned
- S4 정적 서빙 Python 테스트·Taskfile — ✅ (기존 `static_dist` 5건이 이미 커버해 추가 없음, Taskfile에 `e2e`·`test:all`)

## DoD baseline → after
- `pnpm --dir webui/web e2e`: 없음 → 4 passed (에이전트가 3회 연속 확인, 오케스트레이터 재실행도 통과)
- 전체 Python: 749 → 750 passed (fake codex 그리드 추론 테스트 +1), Vitest 146 passed
- `task --list`에 dev·build·e2e·test:all

## 판단·가정
- 프런트 변경 1건: `NewCharacter.pickImage`가 파일 선택 즉시 캐릭터 생성+업로드+분석+Plan 이동(docs/09 §121 "이미지 선택 = 만들기"), id가 파일명 기본 제안이고 유효할 때만. 아니면 "만들기" 버튼이 fallback. 이 변경이 없으면 조작이 5번이 됨(`NewCharacter.test.tsx` 2건 갱신).
- fake codex 가산 변경: `FAKE_CODEX_GRID` 미지정 시 프롬프트 GRID RULES의 `R rows x C columns`에서 격자를 읽음(액션별 격자가 다른 `npc` 번들용, env는 계속 우선).
- (b)(c)의 사전 설정은 API로, 검증 대상 흐름은 UI로 구동. (a)만 전 과정을 UI로.
- `e2e/` 디렉터리는 tsconfig typecheck 범위 밖이라 IDE에 `@types/node` 누락 진단이 보임(`pnpm typecheck`·build·vitest·e2e에는 영향 없음).
