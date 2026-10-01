<!-- forge-slug: forge-m4-app-core -->
<!-- task: 13 -->
<!-- part: 1/8 -->
<!-- tdd: off -->
# M4-a: FastAPI 앱 골격 · 오류 형식 · 파일 서빙 보안 · 진입점

## Goal / Non-goals
- Goal: docs/10 §1·§4·§5.1(health·presets·characters)·§7·§8, docs/01 §9, docs/12 M4 1번. uv 워크스페이스 멤버 `webui/server`(패키지 `sprite_forge_web`, 엔트리 `sprite-forge-web`)에 FastAPI 앱, 공통 오류 형식, `GET /api/health`(doctor 60초 캐시·`?refresh=1`), `GET /api/presets`, `GET/POST /api/characters`, `GET /api/characters/{cid}`, `GET /files/{cid}/{path}`(경로 정규화·`..`·심볼릭 링크 탈출 차단), Host 헤더 검증(`127.0.0.1`/`localhost`만), `127.0.0.1:8765` 전용 바인딩, `webui/web/dist` 정적 서빙(SPA fallback), 테스트 클라이언트 픽스처(가짜 codex·임시 root).
- Non-goals: Job 큐·SSE(M4-c), 나머지 동기 엔드포인트(M4-b), 프런트엔드.

## Source of truth
- Glossary terms: none
- Related ADRs: none (docs/01 ADR-002·008, docs/10 §1·§4·§7·§8)
- Definition of Done:
  - `uv run pytest -q -k "api_core or error_format or path_traversal or host_header"` → 종료 코드 0, passed ≥ 10 (baseline: 없음)
  - `uv run sprite-forge-web --help` 종료 코드 0, `--host` 옵션이 `0.0.0.0`을 거부(또는 옵션 부재)
  - 경로 탈출(`..`, 인코딩된 `%2e%2e`, 절대 경로, 심볼릭 링크)이 404/400, 정상 파일은 200
  - 기존 `uv run pytest -m "not live" -q` 586 passed 유지

## Work slices
- [ ] S1. uv 워크스페이스·`webui/server` 패키지·엔트리·pytest 설정(pythonpath), 앱 팩토리, 오류 형식, Host 검증 — completion criterion: 오류 형식·Host 테스트 통과
- [ ] S2. health(doctor 캐시)·presets·characters 엔드포인트 — completion criterion: 해당 API 테스트 통과 (depends: S1)
- [ ] S3. `/files` 보안과 정적 dist 서빙 — completion criterion: path_traversal 테스트 통과 (depends: S1)
