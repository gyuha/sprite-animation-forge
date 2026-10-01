<!-- forge-slug: forge-m1-qc -->
<!-- task: 4 -->
<!-- part: 4/12 -->
<!-- tdd: off -->
# M1-c: QC 엔진 (QC-01~07, 09)

## Goal / Non-goals
- Goal: docs/06 §1~§4를 구현한다: `qc.py`에 QC 항목(QC-01~07, 09)·임계값·액션별 적용 매트릭스, `qc-report.json` 형식(액션별), 점수 계산, 최선 attempt 선택. 판정 등급 pass/warn/fail.
- Non-goals: 권장 조치·복구(`recovery.py`, M3), Character Scale Profile 생성(M3). QC-07은 profile이 주어졌을 때만 계산하고 없으면 `skipped`로 기록하는 입력 계약만 구현한다. QC-08(Phase 2) 제외.

## Source of truth
- Glossary terms: none
- Related ADRs: none (docs/06, README PRD 충돌 해소 #6·#7·#8, docs/11 §4 qc 행)
- Definition of Done:
  - `uv run pytest -q sprite-animation-forge/tests -k "qc and not recovery"` → 종료 코드 0, passed ≥ 25 (baseline: 없음)
  - 항목별 경계값 테스트: 임계값 바로 아래·위에서 판정이 갈린다
  - 적용 매트릭스: death·jump는 QC-02 제외, idle의 QC-06은 `warn` 등급, 비적용 항목은 `skipped`
  - `edge_touch`·`scale_drift_12`·`empty_cell`·`baseline_jitter` 합성 시트의 `process` 결과를 QC에 넣으면 각각 해당 항목이 fail
  - `qc-report.json`이 doc 08 §5.6의 형식과 일치(스키마 파일은 다음 plan에서 추가되므로 여기서는 필수 키 단언)

## Work slices
- [ ] S1. QC 항목 지표와 임계값(QC-01~06, 09) — completion criterion: 항목별 경계값 테스트 통과
- [ ] S2. 적용 매트릭스·등급·점수·`qc-report` 생성, QC-07 입력 계약 — completion criterion: 매트릭스·점수 테스트 통과 (depends: S1)
- [ ] S3. process 산출물과 연결하는 통합 테스트(합성 시트 변형 → qc) — completion criterion: 변형별 fail 항목 단언 통과 (depends: S2)
