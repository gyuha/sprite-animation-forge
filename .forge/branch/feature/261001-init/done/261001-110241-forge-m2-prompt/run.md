# RUN — M2-b: 프롬프트 생성기와 템플릿

서브에이전트 1개가 구현, 오케스트레이터가 DoD 재실행으로 확인.

## 슬라이스 결과
- S1 블록 템플릿 20개 + `prompt.py` 조립(HEADER~FOOTER)·`validate_prompt` — ✅ as planned
- S2 모션 라이브러리 10액션·복구 문구 8코드·Case B — ✅ as planned
- S3 방향 CAMERA / DIRECTION REFERENCE, 스냅샷 4종 — ✅ as planned

## DoD baseline → after
- `-k prompt`: 0 → 101 passed (≥20; 기존 테스트 일부 포함)
- 전체: 391 → 488 passed, 4 skipped(기존 golden skip)
- docs/04 §7 walk 예시와 byte 단위 일치 테스트(docs/ 없으면 skip), 스냅샷은 기본 assert + `UPDATE_SNAPSHOTS=1` 재생성

## 판단·가정 (후속 task가 알아야 함)
- API: `PROMPT_TEMPLATE_VERSION="action_prompt@1"`, `build_prompt(plan, profile, action, direction=None, extra=None, recovery=(), *, identity_fields=(), margin_pct=8)`→`PromptResult(text, template_version, references_needed, warnings)`, `build_canonical_prompt`, `validate_prompt`, `direction_reference_unit`, `reference_images_needed`, `RECOVERY_CODES`(edge_touch, scale_drift, character_small, fx_in_body, empty_frame, duplicate_frames, bg_mismatch, identity_drift), `RECOVERY_PARAM_CHANGES`.
- `references_needed`: 항상 `["character"]`, 다중 방향 plan에서 대표 방향이 아닌 방향은 `direction:<unit>`(예 `direction:idle/down`) 추가. `character_small`의 `scale_strategy=preserve`는 호출자가 적용(`RECOVERY_PARAM_CHANGES`).
- 단일 방향 plan은 docs/04 §7 예시와 같게 "facing 기준 모션" 줄을 생략(2+ 방향에서만 출력). RECOVERY 제목/accessories 줄은 docs 부재분을 보충.
- 템플릿 버전은 수동 상수 — 변경 시 스냅샷 테스트가 drift를 잡음.
