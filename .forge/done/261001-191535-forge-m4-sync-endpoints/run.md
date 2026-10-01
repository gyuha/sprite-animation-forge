# RUN — M4-b: 동기 엔드포인트

서브에이전트 1개가 구현, 오케스트레이터가 DoD 재실행으로 확인.

## 슬라이스 결과
- S1 reference·identity·plan 엔드포인트 — ✅ as planned
- S2 prompt·upload·attempts·process·accept·save-params(방향 규칙) — ✅ as planned
- S3 export·export.zip — ✅ as planned

## DoD baseline → after
- `webui/server/tests -k "api_sync or direction"`: 0 → 50 passed (≥25)
- 전체: 657 → 707 passed, 4 skipped, 2 deselected

## 판단·가정 (후속 task가 알아야 함)
- 응답은 Pydantic 모델로 타입화(OpenAPI→TS 생성에 사용). 오류 `{error:{code,message,detail}}`, 방향: 2+ 방향 plan에서 `?direction` 필수(누락 400 `direction_required`), mirror `left`의 prompt/upload/process/accept는 409 `mirrored_direction`, GET attempts는 200 빈 목록+`mirror_of`.
- accept: QC fail은 `force:true` 없으면 409 `qc_failed`(라우트에서 검사), 응답 `{accepted, unit, forced, derived, scale_profile_updated, requalified_actions: []}`.
- 업로드 초과 413 `file_too_large`(docs 미정의), reference 중복 409. save-params는 plan에 필드가 있는 4개(anchor, x_anchor, scale_strategy, components)만 허용.
- ZIP: `atlas/*`, `animations.json`, `preview/*` flat(qc-report/manifest 제외 — docs/07 §11 근거). `PUT plan`이 Core의 private `plan._profile_colors`를 호출. 테스트 import용으로 pytest pythonpath에 `sprite-animation-forge/tests` 추가.
