# RUN — 움직임 개선 1/6: 정렬 방식 개선 (공통 배치 기본값, 지금 방식은 옵션)

TDD: 테스트 10건(`test_align_register.py`)을 먼저 작성해 빨간 상태(9 failed)를 확인한 뒤 구현. 서브에이전트 위임이 거절되어 오케스트레이터가 직접 구현.

## 슬라이스 결과
- S1 `pipeline/register.py`(상체 65% 마스크·겹침 최대 이동량 탐색(2x 서브샘플→±2px 정밀)·선형 드리프트만 제거·공통 배치), `ProcessParams.align`(기본 `register`)·`preserve_vertical`, `align.place_frame`/`scale.fit_scale`/`overflow_px`에 명시 앵커 지원 — ✅ as planned
- S2 QC-03 의미 변경(register: 하위 절반(접지) 프레임들의 strict feet 편차 `mode: contact_slip`, 점프·낙하 vertical 보존이면 `skipped(vertical_preserved)`, per_frame은 기존 정의), recovery에 `align_per_frame` 우선 권장, airborne 프롬프트의 "같은 기준선" 문장 제거 + `PROMPT_TEMPLATE_VERSION` action_prompt@2(스냅샷은 버전 줄만 변경) — ✅ as planned
- S3 `workflow._ENUMS`에 `align`(CLI `--set align=`·API process `set`), `plan.is_airborne`/`process_params`, 재처리 패널 select `reprocess-align`("공통 배치 (기본)"/"프레임별 (이전 방식)") — ✅ as planned

## DoD baseline → after
- `-k "align and register"`: 0 → 12 passed (≥6). per_frame은 기존 산출물과 바이트 동일(합성 3종 sha256을 변경 전에 고정해 단언)
- 전체 pytest 751 → 773 passed, 4 skipped; Vitest 191 → 193; e2e 10 → 10; typecheck·build 통과
- 기존 테스트 수정 2건(기대값 불변, `align="per_frame"` 명시만): `test_process_baseline_jitter_frames_end_on_baseline`, `test_qc_integration_baseline_jitter_passes_qc03` — 둘 다 "프레임별 발 고정"이라는 이전 방식 자체를 검증. 대응하는 register 동작(접지 흔들림 보고)은 신규 테스트로 추가. 패널·Studio 테스트의 기대 `set`에 `align` 키 추가(전체 파라미터 전송 계약 유지).

## 판단·가정
- 셀 경계는 gutter 스냅으로 프레임마다 몇 px 움직이므로 register는 공칭 슬롯 좌표(이상적 경계 기준)로 계산하고 셀 좌표로 되돌림(이걸 빼면 합성 드리프트 테스트가 8px 어긋났음).
- 상체 컷은 액션의 중앙값 bbox 높이 기준(다리 길이가 바뀌어도 같은 몸 높이 잘림).
- anchor가 feet가 아니면(`bottom`/`center`, death 등) register는 per_frame으로 대체되고 process.json `params.align`에는 실제 적용된 값이 기록됨.
- 알려진 한계: register는 모델이 그린 접지(세로 흔들림)를 보존하므로 `baseline_jitter` 같은 생성은 QC-03이 fail로 보고하고 recovery가 `align=per_frame` 재처리를 먼저 권장.

## 실사용 확인 (sprites/green 사본, 읽기 전용; 윗몸 중심 x/y 및 발 y의 프레임 간 변동폭 px, per_frame → register)
- walk/down: x 0.1→0.1, y 0.6→1.6, 발 0→1 / walk/right: x 0.2→2.4, y 1.5→1.9 / attack/right: x 7.2→3.3 / idle/down: x 0.6→2.5
- 해석: 이 샘플은 per_frame 결과가 이미 안정적이라 정렬 변경만으로는 개선이 뚜렷하지 않음(공격 x만 개선, idle·walk/right는 오히려 2px 정도 증가). "부자연스러움"의 주원인은 정렬이 아니라 생성된 포즈 자체일 가능성이 큼 → 다음 작업들(호흡 idle, 움직임 점수, 프롬프트)과 사람 눈 비교 필요. 사용자가 뷰어에서 보고 별로면 기본값을 per_frame으로 되돌리는 것은 한 줄(`ProcessParams.align`)이며 근거 수치는 위와 같음.
- 직접 확인 방법: `sprites/green` 사본에서 `forge.py process green walk --direction down --set align=register|per_frame` 후 애니메이션 뷰어에서 비교.
