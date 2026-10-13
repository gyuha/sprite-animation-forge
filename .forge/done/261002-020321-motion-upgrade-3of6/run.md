# RUN — 움직임 개선 3/6: 움직임 품질 점수(QC)와 비전 심사

TDD: `test_motion_qc.py`(수집 오류 = 빨간 상태 확인)·`test_vision_review.py`를 먼저 작성한 뒤 구현. 오케스트레이터가 직접 구현.

## 슬라이스 결과
- S1 `qc_motion.py`(32x32 프리멀티 알파 썸네일 지표) + QC 항목 4종: QC-10 루프 이음새 비율(warn >2.0 / fail >3.5, 반복 액션만), QC-11 실루엣 연속성(인접 프레임 알파 마스크 IoU 최솟값; locomotion warn <0.55 / fail <0.35, action·airborne는 <0.30 warn만, terminal은 info), QC-12 색 일관성(히스토그램 교차 최솟값 warn <0.80 / fail <0.60), QC-13 움직임 크기(warn <0.008, **warn만**; idle·breathe는 info). 적용 매트릭스·qc-report 스키마(ID 패턴 그대로)·`skipped(not_loop)` — ✅ as planned (QC-11 지표와 QC-13 등급은 아래 판단 참고)
- S2 recovery: QC-10 fail → 재생성 `loop_closure`(신규 프롬프트 코드·문구), QC-11/12 fail → 재생성 `identity_drift`. 일괄 생성은 실패한 시도의 재생성 권장 코드를 다음 재시도의 recovery로 전달(기존에는 항상 빈 목록이었음) — ✅ as planned
- S3 비전 심사: `vision.py`(contact sheet → Codex read-only `--output-schema`, 참조 이미지 2번째 첨부, `invalid_review` 시 아무것도 쓰지 않음), CLI `review`, 스키마 `vision-review(.llm).schema.json`, API Job `vision_review`(취소 불가, `POST …/attempts/{aid}/review`, 처리된 프레임 없으면 412) + attempt 상세 `vision_review` 필드, 스튜디오 "비전 심사" 패널(`vision-review-button`, 결과·요약, 참고용 문구), QC-10~13 라벨·툴팁, 가짜 codex 확장 — ✅ as planned

## DoD baseline → after
- `-k "motion_qc or vision_review or regenerate_codes"`: 0 → 49 passed (≥12). 전체 pytest 795 → 844 passed, Vitest 197 → 207, e2e 11, typecheck·build 통과.
- 기존 테스트 수정(기대값 추가, 약화 없음): QC 적용 매트릭스(death/fx의 새 skip 항목), 결과 ID 범위 QC-01~13, "clean은 QC-06만 warn" → 합성 clean(프레임 동일)은 QC-06·QC-13이 warn(점수 84), 프롬프트 복구 코드 표에 `loop_closure`.

## 판단·가정
- **QC-13을 fail이 아닌 warn으로 제한**: 처음엔 fail이었으나 합성 `clean`(프레임 전부 동일)이 모든 곳에서 fail로 번져 테스트 16건이 깨졌고, 정지 프레임은 QC-06이 이미 알림. 의도적으로 미세한 움직임이 채택을 막으면 안 된다고 판단.
- **QC-11은 dHash 대신 마스크 IoU**: dHash는 값 범위가 지나치게 좁음(완전히 떨어진 두 덩어리도 0.72). 실제 `green` 데이터에서 IoU로 임계값 보정.
- 임계값은 8개 샘플(`green`)로만 보정했으므로 다른 캐릭터에서 재조정이 필요할 수 있음.
- 비전 심사는 점수·status에 반영하지 않고 자동 실행하지 않음(Job으로 버튼에서만).

## ⚠ 중요한 발견 (정렬 기본값 register)
- `sprites/green` 사본을 **새 기본값(register)으로 재처리**해 새 QC를 돌리면: idle 3방향의 QC-13 움직임 크기가 0.04~0.05(이전 per_frame으로 저장된 프레임은 0.014), QC-11 최솟값 0.60~0.67(이전 0.93), walk/up QC-11 0.446 → warn. 즉 register는 모델이 프레임마다 그린 위치 흔들림을 그대로 보존해 **idle·walk에서는 per_frame보다 프레임 간 흔들림이 큼**(#24의 윗몸 변동폭 측정 idle 0.6→2.5px, walk/right 0.2→2.4px와 일치). attack만 7.2→3.3px로 개선.
- 따라서 register를 기본값으로 둔 결정(질문 3)은 이 실측과 어긋날 가능성이 있음. 사람 눈 비교 후 기본값을 per_frame으로 되돌리거나(한 줄: `ProcessParams.align`) 액션별 기본값을 두는 것을 사용자가 결정해야 함.

## 실사용 확인
- 실제 Codex로: `forge.py review <cid> walk` 또는 스튜디오의 "비전 심사" 버튼 → `vision-review.json`. QC-10~13 값이 눈으로 본 문제와 맞는지 비교.
