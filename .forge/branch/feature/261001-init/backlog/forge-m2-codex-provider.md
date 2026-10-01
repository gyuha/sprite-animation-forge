<!-- forge-slug: forge-m2-codex-provider -->
<!-- task: 7 -->
<!-- part: 7/12 -->
<!-- tdd: off -->
# M2-a: provider 추상화와 CodexCliProvider (가짜 codex)

## Goal / Non-goals
- Goal: docs/01 §4, docs/03 §4·§6~§8·§15를 구현한다: `providers/base.py`(GenerationRequest/Result/ImageProvider), `providers/manual.py`, `providers/codex_cli.py`(`codex exec` 인자 구성 `-C -i -o … -` 순서, stdin 지시문 `<<<PROMPT … PROMPT>>>`, JSONL 이벤트 파싱, 2단계 결과 수집(rollout → glob), 진행 이벤트 매핑, 에러 분류, 타임아웃·취소, `generation.json` 기록, `shell=False`).
- Non-goals: 실제 codex 호출, prompt/identity(다음 plan), `doctor`·`generate` CLI(M2-c).

## Source of truth
- Glossary terms: none
- Related ADRs: none (docs/01 ADR-001·009, docs/03, docs/11 §3.3·§4 providers.codex_cli 행)
- Definition of Done:
  - `uv run pytest -v -q -k codex_cli` → 종료 코드 0, 가짜 codex 9모드(success·no_rollout·no_image·multiple_images·image_gen_failed·exit_1·hang·invalid_png·config_warnings) 각각에 대응하는 테스트가 PASSED (baseline: 없음)
  - `success`: `status=succeeded`, `source_resolved_by=rollout`; `no_rollout`: `glob`, `revised_prompt=null`; `multiple_images`: 마지막 선택 + `warnings`에 `multiple_images: 2`; `hang`: 2초 타임아웃 후 `timeout` 이고 자식 프로세스 종료를 확인
  - argv 구성 테스트: `-i` 뒤에 `-` 가 없고 마지막 인자가 `-`
  - `cancel()` 이 실행 중 프로세스를 종료
  - `ManualUploadProvider`가 외부 raw를 `raw.png`로 등록하고 `generation.json(provider=manual)` 기록

## Work slices
- [ ] S1. `providers/base.py`, `providers/manual.py` + 테스트 — completion criterion: manual provider 테스트 통과
- [ ] S2. `providers/codex_cli.py`(호출·수집·에러 분류·타임아웃·취소·generation.json) — completion criterion: 9모드 테스트 PASSED (depends: S1)
