# RUN — M1-c: QC 엔진 (QC-01~07, 09)

서브에이전트 1개가 구현, 오케스트레이터가 검토 후 docs/06 매트릭스와 어긋난 한 곳을 직접 수정.

## 슬라이스 결과
- S1 QC-01~06, 09 지표·임계값 — ✅ as planned
- S2 적용 매트릭스·등급·점수·`qc-report` 생성·QC-07 입력 계약 — ⚠ idle의 QC-06 등급을 매트릭스에 맞게 `info`로 수정(에이전트는 전 액션 warn으로 구현했었음)
- S3 process 산출물 통합 테스트(edge_touch/scale_drift_12/empty_cell/baseline_jitter) — ✅ as planned (edge_touch는 2x2 격자에서 단언)

## DoD baseline → after
- `-k "qc and not recovery"`: 0 → 53 passed (≥25)
- 전체 `-m "not live"`: 184 → 237 passed
- 항목별 경계값 상·하, 적용 매트릭스(death/jump QC-02 제외), 변형별 fail 항목: 테스트가 단언 (통과)

## 판단·가정 (후속 task가 알아야 함)
- 공개 API: `run_qc(process_result_or_data, frames, action, params, profile, *, attempt, loop, qc_profile)`→dict, `select_best_attempt`, `score_for`(100−25·fail−8·warn), `applicability`, `dhash`.
- 리포트: schema_version 1, action/attempt/status/score/frames, `checks`, `results[{id, grade(pass|warn|fail|info|skipped|not_run), value, limit, reason?}]`, `per_frame`, `recommendations: []`(recovery.py가 채움). 타임스탬프 없음 — 필요하면 CLI 계층에서 추가.
- QC-06: idle → info, 그 외 warn. QC-08은 `not_run`. QC-07은 profile 없으면 `skipped(no_profile)`.
- edge_touch 통합 테스트는 2x2에서 수행: 2x3에서는 분리기의 ±6% 스냅이 실제 gutter를 찾아 시트가 깨끗해짐(픽스처·분리기 특성, QC 버그 아님).
