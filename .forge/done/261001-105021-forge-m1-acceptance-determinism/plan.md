<!-- forge-slug: forge-m1-acceptance-determinism -->
<!-- task: 6 -->
<!-- part: 6/12 -->
<!-- tdd: off -->
# M1-e: 결정성 · golden(skip) · 시나리오 1·2 (수동 raw)

## Goal / Non-goals
- Goal: docs/12 M1 5번과 "M1 완료"를 닫는다: 같은 입력 `process` 2회의 모든 출력 sha256 동일(`determinism`), golden 테스트(`tests/fixtures/codex-samples/`가 없으면 skip), 시나리오 1(idle 4프레임)·2(walk 6프레임)를 수동 raw 경로로 end-to-end 통과하는 `scenario_1`, `scenario_2` 테스트(docs/11 §5 통과 기준).
- Non-goals: generate 경로(M2), export(M3 — 시나리오 1의 export 단계는 여기서 제외하고 M3 acceptance에서 확장), live 샘플 기록.

## Source of truth
- Glossary terms: none
- Related ADRs: none (docs/11 §1·§3.2·§5, docs/12 M1)
- Definition of Done:
  - `uv run pytest -q -k determinism` → 종료 코드 0, passed ≥ 1 (baseline: 없음)
  - `uv run pytest -v -q -k "scenario_1 or scenario_2"` → `scenario_1`, `scenario_2` 각각 PASSED
  - 시나리오 1: `idle/frames/` 4장, `idle/sheet.png` 모서리 알파 0, `idle/qc-report.json` 스키마 통과
  - 시나리오 2: walk 처리 후 QC-01 pass, QC-02 ≤ 0.10, QC-03 ≤ 3px
  - golden 테스트는 샘플 디렉터리가 없을 때 skip 됨 (`-rs` 출력으로 skip 사유 확인)

## Work slices
- [ ] S1. determinism 테스트(전체 process 2회 해시 비교) — completion criterion: `-k determinism` 통과
- [ ] S2. golden 속성 테스트(샘플 없으면 skip) — completion criterion: skip 사유가 출력됨
- [ ] S3. `scenario_1`, `scenario_2` 수동 raw CLI end-to-end 테스트 — completion criterion: 두 테스트 PASSED (depends: S1)
