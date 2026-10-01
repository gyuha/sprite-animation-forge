<!-- forge-slug: forge-m5-e2e-smoke -->
<!-- task: 20 -->
<!-- part: 8/8 -->
<!-- tdd: off -->
# M5-e: Playwright E2E 스모크 · 단일 실행(dist 서빙) · Taskfile

## Goal / Non-goals
- Goal: docs/12 M5 검증 3항목, docs/11 §2·§6, docs/09 §9.6. Playwright(webServer: 임시 root + 가짜 codex로 FastAPI 기동, dist 서빙)로: (a) 이미지 업로드 → 번들 선택 → 전부 생성 → ZIP 다운로드가 **조작 4번**으로 끝남(조작 정의를 테스트 주석에 명시, 클릭/업로드/선택 횟수를 계측), (b) 재처리 슬라이더 변경 후 2초 안에 미리보기 갱신, (c) 서버를 생성 도중 재시작해도 UI가 `중단됨`을 표시하고 다시 생성 가능. `uv run sprite-forge-web`가 빌드된 dist를 `/`에서 서빙하는 테스트(Python), `Taskfile.yml`의 `dev`(서버+Vite 동시), `build`, `e2e`, `web:test` 작업. 로컬에 캐시된 Playwright chromium 사용(`pnpm exec playwright install`은 필요 시에만).
- Non-goals: Phaser 브라우저 스모크, live Codex, CI 구성.

## Source of truth
- Glossary terms: none
- Related ADRs: none (docs/12 M5 검증, docs/11 §2)
- Definition of Done:
  - `pnpm --dir webui/web e2e` → 종료 코드 0, Playwright passed ≥ 3 (위 (a)(b)(c) 각각)
  - (a)는 업로드 1 + 번들 선택 1 + 전부 생성 1 + ZIP 다운로드 1 = 4번의 사용자 조작임을 계측으로 단언
  - (b)는 슬라이더 변경 시각 → 미리보기 이미지 `src`(또는 해시) 변경까지 < 2000ms를 측정해 단언
  - (c)는 가짜 codex `hang` 모드로 생성 중 서버 프로세스를 kill→재기동한 뒤 `중단됨` 배지 확인, 이어서 재생성 성공
  - `uv run pytest -q -k "static_dist or sprite_forge_web_cli"` 통과, `task --list`에 dev·build·e2e 포함
  - 기존 Python 테스트·Vitest 전부 통과 유지

## Work slices
- [ ] S1. Playwright 설정·webServer(가짜 codex, 임시 root, dist 서빙) 헬퍼 — completion criterion: 빈 스모크(홈 로드)가 통과
- [ ] S2. 시나리오 (a) 4조작 ZIP — completion criterion: (a) passed (depends: S1)
- [ ] S3. 시나리오 (b) 재처리 2초 갱신, (c) 재시작 `중단됨` — completion criterion: (b)(c) passed (depends: S1)
- [ ] S4. 정적 서빙 Python 테스트·Taskfile 작업 — completion criterion: static_dist 테스트 통과, `task --list` 확인 (depends: S2, S3)
