<!-- forge-slug: forge-m0-scaffold-fake-codex -->
<!-- task: 1 -->
<!-- part: 1/12 -->
<!-- tdd: off -->
# M0: 저장소 뼈대와 가짜 codex

## Goal / Non-goals
- Goal: docs/12 M0의 2·3번을 구현한다. uv 프로젝트와 `sprite-animation-forge/` 디렉터리 뼈대, pytest 설정(`live` 마커 포함), 합성 시트 생성기(`tests/fixtures/synthetic/make.py`, docs/11 §3.1 변형 15종), 가짜 codex(`tests/fixtures/fake_codex/codex`, docs/11 §3.3·docs/03 §2·§6·§7).
- Non-goals: 스파이크 S-1~S-10(live Codex 필요), `webui/` 디렉터리와 Web UI/API, 파이프라인·provider 구현 코드.

## Source of truth
- Glossary terms: none
- Related ADRs: none (docs/01 §6 저장소 구조, §10 ADR-006·007, docs/11 §3, docs/03 §2·§6·§7)
- Definition of Done:
  - `uv run pytest -m "not live" -q` → 종료 코드 0 (뼈대 스모크 테스트 포함, baseline: pyproject 없음 → 실패)
  - `ls sprite-animation-forge/scripts/sprite_forge/__init__.py sprite-animation-forge/scripts/forge.py` 둘 다 존재 (baseline: 없음)
  - 합성 시트 변형 15종(clean, model_like_bg, shifted_gutters, narrow_gutter, edge_touch, scale_drift_12, baseline_jitter, empty_cell, specks, detached_sword, thin_below_feet, pinkish_character, native_alpha, wide_attack, asymmetric_right)을 각각 생성해 PNG로 열리고, 각 칸의 bbox·feet 좌표가 함께 반환됨을 `uv run pytest -q -k synthetic` 이 확인 (≥15 passed). 같은 시드로 2회 생성한 바이트가 동일.
  - 가짜 codex: `FAKE_CODEX_MODE` 9종 각각의 동작을 `uv run pytest -q -k fake_codex` 가 검증 (≥9 passed): argv 순서 위반 시 exit 2, `<<<PROMPT`/`PROMPT>>>` 누락 시 exit 2, `success`에서 `$CODEX_HOME/generated_images/<thread_id>/exec-<uuid>.png`와 rollout JSONL 작성, 나머지 모드는 docs/11 §3.3 표의 동작.
  - `pyproject.toml`에 pytest `markers`로 `live` 등록, `testpaths`가 `sprite-animation-forge/tests`, 기본은 `-m "not live"` 와 동일하게 live 제외 (확인: `uv run pytest --markers | grep live`)

## Work slices
- [ ] S1. 루트 `pyproject.toml`(Python ≥3.11, Pillow·NumPy·SciPy·jsonschema, dev: pytest), `uv.lock`, `.gitignore`(sprites/, codex-samples/, .venv 등), `sprite-animation-forge/` 디렉터리 뼈대(`scripts/forge.py` 스텁, `scripts/sprite_forge/__init__.py`, `schemas/`, `references/`, `tests/`) — completion criterion: `uv sync` 성공, `uv run pytest -q` 가 종료 코드 0
- [ ] S2. 합성 시트 생성기 `tests/fixtures/synthetic/make.py` (15종, 결정적, bbox·feet 반환) + 테스트 — completion criterion: DoD의 synthetic 항목 통과 (depends: S1)
- [ ] S3. 가짜 codex `tests/fixtures/fake_codex/codex`(실행 권한, 9모드) + 테스트 — completion criterion: DoD의 fake_codex 항목 통과 (depends: S2)
