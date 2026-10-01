<!-- forge-slug: forge-m5-frontend-foundation -->
<!-- task: 16 -->
<!-- part: 4/8 -->
<!-- tdd: off -->
# M5-a: 프런트엔드 기반 (Vite · React · TS · Tailwind · shadcn/ui · API 클라이언트 · SSE · 공통 컴포넌트)

## Goal / Non-goals
- Goal: docs/09 §9, docs/12 M5 1번. `webui/web`에 Vite+React+TypeScript, Tailwind, React Router, TanStack Query, `shadcn init`(`components.json`, `@` 별칭), docs/09 §9.5의 shadcn 컴포넌트 전부 설치(`shadcn add`), OpenAPI→`types.ts` 생성 스크립트(`pnpm gen:types`, 서버에서 openapi.json 덤프), `api/client.ts`·`queries.ts`·`sse.ts`(EventSource+재연결), 라우팅(7개 화면 라우트, 화면 본문은 빈 껍데기 허용), 공통 컴포넌트 `CodexStatusBadge`·`JobTray`·`JobProgress`, `pnpm dev` 프록시(`/api`,`/files`→8765), 스크립트 `typecheck`·`build`·`test`(Vitest)·`e2e`(placeholder 허용 안 됨 — e2e는 M5-e에서), Taskfile `dev`/`web:*` 작업 추가.
- Non-goals: 화면 본문(M5-b~d), Playwright 시나리오.

## Source of truth
- Glossary terms: none
- Related ADRs: none (docs/09 §9, docs/01 ADR-010)
- Definition of Done:
  - `pnpm --dir webui/web typecheck`, `build`, `test` 종료 코드 0, Vitest passed ≥ 8 (API 클라이언트 에러 정규화, SSE 훅 재연결, Job 트레이 렌더링, Codex 배지 상태 등)
  - `webui/web/components.json` 존재, `src/components/ui/`에 §9.5 컴포넌트 23종 전부 존재: `ls webui/web/src/components/ui | wc -l` ≥ 23
  - `types.ts`가 서버 OpenAPI에서 생성됨(`pnpm gen:types` 재실행 후 diff 없음)
  - 기존 Python 테스트 전부 통과 유지

## Work slices
- [ ] S1. Vite/React/TS/Tailwind/라우터/Query 스캐폴드 + shadcn init·add 전체 — completion criterion: typecheck·build 통과, ui 컴포넌트 존재
- [ ] S2. OpenAPI→types 생성, `api/client.ts`·`queries.ts`·`sse.ts` + Vitest — completion criterion: Vitest 통과 (depends: S1)
- [ ] S3. `CodexStatusBadge`·`JobTray`·`JobProgress`, 레이아웃 셸, Taskfile 작업 — completion criterion: 컴포넌트 테스트 통과 (depends: S2)
