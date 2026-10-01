<!-- forge-slug: forge-m4-sync-endpoints -->
<!-- task: 14 -->
<!-- part: 2/8 -->
<!-- tdd: off -->
# M4-b: 동기 엔드포인트 (reference · identity · plan · attempts · process · accept · export)

## Goal / Non-goals
- Goal: docs/10 §5.1·§5.2 중 동기 엔드포인트 전부를 Core 함수 호출로 구현한다: reference 업로드(multipart, PNG/JPEG/WebP·20MB·Pillow 디코드)와 후보 select, identity GET/PUT(스키마 검증), plan GET/PUT/POST, 프롬프트 미리보기, 수동 raw 업로드→attempt+자동 처리, attempts 목록·상세, 재처리, 채택(`derived`), save-params, export, `export.zip`. 탑다운 `?direction=` 규칙(2개 이상이면 필수, mirror `left`는 409 `mirrored_direction`, `right` accept 시 `derived: ["walk/left"]`).
- Non-goals: Job(생성·분석)과 SSE(M4-c), 프런트엔드.

## Source of truth
- Glossary terms: none
- Related ADRs: none (docs/10 §5·§7, docs/02 §8.1)
- Definition of Done:
  - `uv run pytest -q -k "api_sync or direction"` 중 web 테스트 → 종료 코드 0, passed ≥ 25 (baseline: 없음)
  - 모든 엔드포인트의 정상·오류 경로 테스트(업로드 형식/크기 거부, 스키마 위반 PUT 422 등)
  - `?direction` 필수/불필요 규칙, 409 `mirrored_direction`, accept 응답의 `derived`
  - export 후 `export.zip`이 `atlas/*`, `animations.json`, `preview/*`를 포함
  - 기존 테스트 전부 통과 유지

## Work slices
- [ ] S1. reference·identity·plan 엔드포인트 — completion criterion: 해당 API 테스트 통과
- [ ] S2. prompt·upload·attempts·process·accept·save-params(방향 규칙 포함) — completion criterion: 해당 테스트 통과 (depends: S1)
- [ ] S3. export·export.zip — completion criterion: export 테스트 통과 (depends: S2)
