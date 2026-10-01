# RUN — M3-a: Character Scale Profile · QC-07 · preserve · recovery

서브에이전트 1개가 구현, 오케스트레이터가 DoD 재실행으로 확인.

## 슬라이스 결과
- S1 Character Scale Profile(`workflow.build_scale_profile`, accept 시 첫 body unit/대표 방향에서만 생성, manifest `scale_profile`) + preserve 배선 확인 — ✅ as planned
- S2 QC-07 대조(시나리오 4) — ✅ as planned (preserve QC-07 1.0, fit 0.6091)
- S3 `recovery.py` 권장 조치·예산·force_accept(시나리오 5) — ✅ as planned

## DoD baseline → after
- `-k "scale_profile or recovery or qc07 or preserve"`: 36(기존 일치) → 56 passed (신규 20)
- 전체: 524 → 544 passed, 4 skipped, 2 deselected
- 시나리오 4: preserve ≥0.85 / fit <0.85·preserve 미만 단언 통과. 시나리오 5 1순위 3종(regenerate edge_touch / regenerate scale_drift / reprocess `set=={"scale_strategy":"preserve"}`) 통과

## 판단·가정 (후속 task가 알아야 함)
- API: `recovery.recommend(qc_report, process_data, params, budget_state)`, `attach`, `budget_state`; 권장 항목 `{type, action(=type), code, set?, attempt?, reason, qc_id, priority, cost}`, 재처리 코드 `use_preserve|use_fit|anchor_bottom|tighter_merge`, 재생성 코드는 docs/04 복구 코드, 소진 시 `force_accept(code=forced_accept)`. `run_qc`는 불변(결정적), `process_attempt`가 `recovery.attach` 호출.
- 기존 테스트 1줄 수정: `test_cli_end_to_end_manual_path`가 "accept 후 scale-profile 없음"을 단언하던 M1 시점 동작 → 이제 첫 accept(walk)에서 profile 생성되므로 `reference_action == "walk"` 단언. 이 task의 요구된 동작 변경이며 임계값/기대치 약화 아님.
- 시나리오 4 설정: clean 2x2 idle accept 후 wide_attack 2x3을 preserve/fit로 처리. preserve에서는 합성 칼이 출력 cell보다 넓어 QC-01(b) fail → 권장 `regenerate fx_in_body`, `reprocess use_fit` (docs/05 §7.2와 일치). 시나리오 5의 `scale_drift_12`는 walk(2x3)로, `edge_touch`는 2x2 idle로 실행(attack은 QC-02가 warn만).
- 가정: 권장은 fail 등급만, QC-01(b)·fit은 docs 표에 없어 `regenerate edge_touch`, `center_x`=median mass_cx·`feet_y`=median weak feet_y, 기준 액션 재채택 시 다른 액션 QC 재계산은 미구현(docs는 "표시"만 요구).
