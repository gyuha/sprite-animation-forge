# RUN — M5-a: 프런트엔드 기반

서브에이전트 1개가 구현, 오케스트레이터가 DoD 재실행으로 확인.

## 슬라이스 결과
- S1 Vite/React/TS/Tailwind v4/Router/Query 스캐폴드 + shadcn init·add(23종) — ✅ as planned (shadcn CLI 4.21.1이 비대화형으로 실행됨, 직접 작성한 컴포넌트 없음)
- S2 OpenAPI→`types.ts`(`pnpm gen:types`), `api/client.ts`·`queries.ts`·`sse.ts` + Vitest — ✅ as planned
- S3 `CodexStatusBadge`·`JobTray`·`JobProgress`·`AppLayout`, Taskfile 작업 — ✅ as planned

## DoD baseline → after
- `typecheck`, `build` exit 0, `test`: 0 → 18 passed (≥8, 파일 5개)
- `ls webui/web/src/components/ui | wc -l`: 0 → 26 (≥23, §9.5 23종 + toggle 등 의존 3개)
- `gen:types` 재실행 시 types.ts·openapi.json 체크섬 동일

## 판단·가정 (후속 화면 task가 알아야 함)
- API: `api<T>()`, `apiJson<T>(path,'POST'|'PUT',body)`, `ApiError{status,code,detail,message}`(네트워크 실패 status 0 `network_error`). 쿼리 키 `qk.*`(모두 `['characters', cid, ...]` 하위), 훅 `useHealth(60초+포커스) useCharacters useCharacter usePlan useIdentity useAttempts(cid,action,direction?) useJobs`. mutation 헬퍼는 아직 없음(각 화면 task가 추가).
- SSE: `useJobEvents()`는 `AppLayout`에서 1회 마운트, Job 스냅샷은 Query 캐시 `qk.jobs`, `succeeded` 시 `['characters',cid,'attempts']`(prefix)와 `['characters',cid]` 무효화, 재연결 1s→30s 백오프+`/api/jobs?active=1` 재동기화. Studio 라우트 `/c/:cid/studio/:action?`.
- `/api/health`, `/api/characters`, `/api/characters/{cid}` 응답은 백엔드가 `-> dict`라 OpenAPI 스키마가 없어 `queries.ts`에 수기 타입. `src/lib/utils.ts`는 shadcn 4.21 생성물 그대로(`cn` 패키지 re-export). 페이지 7개는 제목만 있는 placeholder(다음 task가 채움). `.gitignore`에 `webui/web/dist/` 추가, 개발 서버 포트 5173이 사용 중이면 5174로 올라감(무영향). `e2e` 스크립트/Playwright는 M5-e.
