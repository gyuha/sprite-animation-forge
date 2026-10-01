<!-- forge-slug: forge-m3-scale-profile-recovery -->
<!-- task: 10 -->
<!-- part: 10/12 -->
<!-- tdd: off -->
# M3-a: Character Scale Profile · QC-07 · preserve · recovery

## Goal / Non-goals
- Goal: docs/06 §5~§6, docs/05 §7.2, docs/12 M3 1·2번을 구현한다: Character Scale Profile(첫 body 액션 `accept` 시 `character-scale-profile.json` 생성), QC-07(profile 기반 스케일 일관성), preserve 배율 적용, `recovery.py`(QC 결과 → 우선순위 권장 조치 목록, 복구 예산).
- Non-goals: 권장 조치의 자동 실행(Agent/사용자가 결정), FX 자동 분리(Phase 2).

## Source of truth
- Glossary terms: none
- Related ADRs: none (docs/06 §5·§6, docs/11 §5 시나리오 4·5)
- Definition of Done:
  - `uv run pytest -q -k "scale_profile or recovery or qc07 or preserve"` → 종료 코드 0, passed ≥ 15 (baseline: 없음)
  - 시나리오 4 대조: `wide_attack`을 preserve로 처리하면 QC-07 ≥ 0.85, 같은 입력을 fit으로 처리하면 QC-07이 preserve보다 낮음 (테스트 단언)
  - 시나리오 5: `edge_touch`·`scale_drift_12`·`wide_attack(fit)` 합성 입력의 권장 조치 1순위가 각각 재생성 `edge_touch` / 재생성 `scale_drift` / 재처리 `use_preserve`
  - 복구 예산 소진 시 강제 채택 권장 기록
  - `character-scale-profile.json`이 스키마 검증 통과, 첫 body 액션 accept에서만 생성

## Work slices
- [ ] S1. Character Scale Profile 생성(accept 연동)과 preserve 배율 연결 — completion criterion: profile·preserve 테스트 통과
- [ ] S2. QC-07 구현과 대조 테스트(시나리오 4) — completion criterion: `wide_attack` 대조 단언 통과 (depends: S1)
- [ ] S3. `recovery.py` 권장 조치와 예산(시나리오 5) — completion criterion: 1순위 조치 3종 일치 (depends: S2)
