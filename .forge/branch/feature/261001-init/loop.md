# LOOP — docs/ 설계 중 M4(Web API · Job 큐 · SSE)와 M5(React Web UI 화면 · Playwright 스모크)를 구현한다
started: 2026-10-01
replan-round: 0
replan-cap: 3
budget-tokens: none
budget-spent: 0 · since: 2026-10-01T12:30:00+0900
wall: none

## Stop-condition checks (ALL must pass)
모든 명령은 저장소 루트(`/Users/gyuha/workspace/sprite-animation-forge`)에서 실행한다. 검사는 `/tmp/forge-drive/checks2.py`가 실행하며, 엔드포인트 목록은 docs/10 §5.1을 스크립트에 고정해 둔다(구현 측이 약화할 수 없게).
- [ ] C1. 회귀 없음: `uv run pytest -m "not live" -q` → 종료 코드 0, `passed` ≥ 650, `failed`/`error` 0 (기존 M0~M3 586건 + 신규 API 테스트)
- [ ] C2. API 표면: `app.openapi()` 경로·메서드에 docs/10 §5.1 엔드포인트(health, presets, characters CRUD, reference upload/generate/select, identity analyze/get/put, plan get/put/post, prompt, generate, upload, attempts 목록·상세, process, accept, save-params, generate-all, export, export.zip, jobs 목록·상세·cancel, events, files)가 전부 존재 (누락 `[]`)
- [ ] C3. Job 큐·SSE·복구: `uv run pytest -q -k "jobs or sse or interrupted or cancel"` → 종료 코드 0, passed ≥ 10 (단일 워커 FIFO, 큐 순서, queued/running 취소, SSE 이벤트 순서, 기동 시 `interrupted`)
- [ ] C4. 서버 보안·계약: `uv run pytest -q -k "path_traversal or host_header or error_format or direction"` 중 web 테스트 → 종료 코드 0, passed ≥ 8 (`/files` 경로 탈출·심볼릭 링크 차단, Host 헤더 검증, 오류 형식, `?direction` 필수/409 mirrored_direction/accept 시 `derived`)
- [ ] C5. 프런트엔드 정적 검증: `pnpm --dir webui/web typecheck`, `pnpm --dir webui/web build`, `pnpm --dir webui/web test` 모두 종료 코드 0이고 Vitest passed ≥ 10; `webui/web/components.json` 존재; `src/components/ui/`에 docs/09 §9.5의 컴포넌트(button card badge tabs input textarea label select radio-group checkbox switch table collapsible slider toggle-group progress dialog alert-dialog alert popover tooltip skeleton scroll-area separator sonner) 전부 존재; `src/pages/`에 Dashboard·NewCharacter·Identity·Plan·Studio·Export·Status 7개, `src/components/`에 AnimationPlayer·GridOverlay·CompareSlider·QcPanel·RecommendationButtons·ReprocessPanel·AttemptStrip·JobProgress·JobTray·CodexStatusBadge·PaletteEditor·DropZone 12개 존재
- [ ] C6. E2E 스모크(가짜 codex): `pnpm --dir webui/web e2e` → 종료 코드 0, Playwright passed ≥ 3: (a) 이미지 업로드 → 번들 선택 → 전부 생성 → ZIP 다운로드가 **조작 4번**으로 끝남, (b) 재처리 슬라이더 변경 후 2초 안에 미리보기 갱신, (c) 서버를 생성 도중 재시작하면 UI가 `중단됨`을 표시하고 다시 생성 가능
- [ ] C7. 단일 실행 진입점: `uv run sprite-forge-web --help` 종료 코드 0, 서버는 `127.0.0.1`에만 바인딩(`0.0.0.0` 옵션 없음), `webui/web/dist` 빌드 후 서버가 `/`에서 SPA `index.html`을 서빙하는 테스트 통과

## Check progress (모든 stop-condition 실행 뒤 갱신)
- C1: fail ×0 · regressed: ×0 · last-evidence: "미실행" · tried:
- C2: fail ×0 · regressed: ×0 · last-evidence: "미실행" · tried:
- C3: fail ×0 · regressed: ×0 · last-evidence: "미실행" · tried:
- C4: fail ×0 · regressed: ×0 · last-evidence: "미실행" · tried:
- C5: fail ×0 · regressed: ×0 · last-evidence: "미실행" · tried:
- C6: fail ×0 · regressed: ×0 · last-evidence: "미실행" · tried:
- C7: fail ×0 · regressed: ×0 · last-evidence: "미실행" · tried:

## Authorized replan scope
- 실패한 stop-condition 검사에 직접 대응하는 fix-forward 작업만 자동 생성한다. 구현 대상은 `webui/`(server·web), 루트 `pyproject.toml`/`uv.lock`, `Taskfile.yml`, 필요 시 Core(`sprite-animation-forge/scripts/sprite_forge`)의 최소·하위 호환 변경으로 한정한다.
- 범위 제외(사용자 확정·가정): live Codex 호출이 필요한 모든 검증(실제 생성, `-m live`, M6 인수), Phase 2 이후, 인증·원격 공유·`0.0.0.0` 바인딩. 브라우저 알림(Notification) 권한 흐름은 sonner 토스트 대체 경로만 구현·검증한다. npm 패키지 설치(`pnpm install`, `shadcn add`, Playwright는 로컬 캐시된 chromium 사용)는 허용 범위다.
- always-halt action classes (safety wall — 기본 7종): prod data mutation/deletion · deploy/release/publish · outbound external comms (email · messaging · third-party write APIs) · irreversible VCS/file destruction (force-push · history rewrite · mass deletion) · financial/payment · secret/permission change · privacy-data exposure
- 추가 제한: push하지 않는다(commit만). 실제 `codex` 바이너리는 호출하지 않는다(가짜 codex만).

## Tasks
- forge-m4-app-core
- forge-m4-sync-endpoints
- forge-m4-jobs-sse
- forge-m5-frontend-foundation
- forge-m5-screens-setup
- forge-m5-studio
- forge-m5-export-status-batch
- forge-m5-e2e-smoke
