<!-- forge-slug: forge-m2-identity-reference-cli -->
<!-- task: 9 -->
<!-- part: 9/12 -->
<!-- tdd: off -->
# M2-c: identity · reference generate/select · doctor/generate/prompt CLI

## Goal / Non-goals
- Goal: docs/03 §9~§11, docs/02 §9, docs/12 M2 3·4번을 구현한다: `identity.py`(`--output-schema` JSON 추출·검증, `character-profile.json`), `forge.py` 명령 `identity analyze`, `reference generate/select`, `doctor`(버전·로그인·기능 점검 JSON), `prompt`, `generate`(attempt 생성, provider 오류 시 종료 코드 2와 `error_code`), `SPRITE_FORGE_CODEX_BIN` 환경 변수 지원.
- Non-goals: 실제 codex 호출. live 계약 테스트는 `@pytest.mark.live`로 작성만 하고 실행하지 않는다(`-m live` 제외).

## Source of truth
- Glossary terms: none
- Related ADRs: none (docs/03 §9~§11, docs/02 §9)
- Definition of Done:
  - `uv run pytest -q -k "identity or reference or doctor or generate or prompt_cmd"` → 종료 코드 0, passed ≥ 15 (baseline: 없음)
  - 가짜 codex로 `identity analyze`가 `character-profile.json`을 만들고 스키마 검증 통과
  - 가짜 codex로 `generate`가 `attempts/NNN/{prompt.txt, raw.png, generation.json}`을 만들고, `no_image` 등 실패 모드는 종료 코드 2 + `error_code` JSON
  - `doctor`가 codex 부재 시 파싱 가능한 JSON을 반환(크래시 없음)
  - live 마커 테스트가 존재하고 `uv run pytest -m live --collect-only -q`에 수집되지만 기본 실행에서는 제외됨

## Work slices
- [ ] S1. `identity.py` + `identity analyze` — completion criterion: identity 테스트 통과
- [ ] S2. `reference generate/select` — completion criterion: reference 테스트 통과 (depends: S1)
- [ ] S3. `doctor`, `prompt`, `generate` 명령 + live 마커 계약 테스트 — completion criterion: 해당 CLI 테스트 통과, live 테스트가 수집만 됨 (depends: S2)
