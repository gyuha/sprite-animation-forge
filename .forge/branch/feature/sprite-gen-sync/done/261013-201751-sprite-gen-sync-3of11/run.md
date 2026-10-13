# 실행 기록 — sprite-gen 동기화 3/11: 이미지 가장자리 안전 스케일 (task #32)

## 한 일
- 현상 측정(빨강): 합성 스프라이트(배율 0.37~1.3)에서 기존 프리멀티플라이드 LANCZOS는 단색 블록에서도 가장자리 색이 6단계 어긋나고, 알파 1~2 화소에 `(255,0,0)` 같은 엉뚱한 색이 생김 — 5개 배율 모두에서 "주변 색 범위 ±2" 위반이 있음.
- `pipeline/scale.py`: `_resample_coverage`(알파는 LANCZOS, 색은 알파 가중 평균 BILINEAR — 음수 가중치 없음 → 주변 색의 볼록 결합이라 범위를 벗어날 수 없음, 알파 0이면 RGB 0), `resample(..., mode="legacy")`(함수 기본은 legacy 유지, 픽셀 아트는 모드와 무관).
- `ProcessParams.resample_mode`(기본 `coverage`, `legacy`는 이전 출력과 바이트 동일), 검증(`invalid_params`), `process.json` `params.resample_mode` 기록, `align.place_frame(resample_mode=)`, 재처리 `set` 키(`workflow._ENUMS`).
- UI: 재처리 패널에 "축소 방식" 선택. 기본값(`coverage`)은 전송하지 않음(서버 기본값과 같음).
- docs/05 §7.3, docs/14 영역 B 행 4개.

## 검증
- 신규 `sg_resample` 27건(Core 25 · 서버 2) + Vitest +1. 전체 pytest 968 passed, 기준선 ID 누락 0, Vitest 213, e2e 12.
- 결정성·골든·sha 핀: `test_align_register_per_frame_is_byte_identical…`가 `ProcessParams(align="per_frame")`만으로는 새 기본값 때문에 달라져 `resample_mode="legacy"`를 함께 지정하게 고쳤다(**기대 해시 3개는 그대로**, diff는 인자 1줄). 대조 테스트(`legacy`는 같은 입력에서 범위 위반)로 검사가 판별력이 있음을 확인.

## 계약과 다르게 한 것 (사유)
- 파라미터 이름을 계획의 `resample`이 아닌 `resample_mode`로: `process.json`의 `params.resample`이 이미 필터 이름(`lanczos`/`box`)이고 기준선 테스트(`test_process`)가 이를 단언한다.
- UI의 `resample_mode`는 선택 필드: 필수로 두면 기준선 Vitest의 정확한 전송 객체 단언을 고쳐야 한다. 기본값이면 생략해도 의미가 같다.

## 학습 / 주의
- 측정 도구(주변 색 범위 창)의 첫 버전은 창이 작아 경계에서 오탐(999)이 나왔다. 창은 `ceil(8/scale)`.
- 기본값이 바뀌므로 이미 처리된 attempt를 재처리하면 새 방식으로 다시 그려진다(뷰어·내보내기 결과가 가장자리에서 약간 달라짐). 기존 결과를 유지하려면 `--set resample_mode=legacy`.
- 실제 Codex 시트에서 체감 차이는 미검증 [낮음]: 합성 데이터로 범위 위반 0을 보였을 뿐이다.
