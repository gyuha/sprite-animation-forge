# 실행 기록 — sprite-gen 동기화 8/11: 영상 발 디딤 시작·점프 지표·루프 리포트 (task #37)

## 한 일
- `video_gait.py`(신규): `leg_signal`(하체 40%에서 — 측면은 두 다리 폭, 앞/뒷모습은 좌우 발 높이 차), `foot_strike_start`(반 주기 안·클립 안에서 가장 가까운 "발이 닿은" 프레임으로 시작 이동, 신호 변화가 작으면 `none`), `jolt_metrics`(몸 전체 질량 중심 궤적의 2차 차분 크기, 루프를 닫아서 ÷ 피사체 키 / 머리 중심 최대 이동폭), `jolt_warning`, `foot_view`(looping walk·run 단일 방향만 측면/앞뒤).
- `build_raw_sheet(foot=)`: 컷 시작 이동 후 `start_foot_source`·`foot_shift`·`jolt_index`·`head_move`를 info(→`video-meta.json`)에 기록하고 `seam_pop`은 이동 후 컷으로 계산. 생성 시 `foot_view`를 전달.
- plan `max_jolt`(float, 스키마·`_coerce`·override 키), `workflow.process_attempt`가 영상 attempt를 (재)처리할 때 한도를 넘으면 `process.json` `warnings`에 `jolt_exceeded: …` 추가(한도가 없으면 경고 없음, 한도를 지우고 재처리하면 사라짐).
- 서버: attempt 상세에 `video_meta`(video-meta.json), OpenAPI 타입 재생성. docs/13 §7.1, docs/14 영역 C 행 3개.
- 테스트 도우미 `sg_clips.py`(합성 걷기·앞모습 걷기·다리 없는 몸) — `test_sg_video_loop.py`의 도우미를 옮겨 공유.

## 검증
- `video_foot` 13건(Core 11 + 서버 2). 전체 pytest 1055 passed, 기준선 ID 누락 0, Vitest 215, e2e 12, typecheck OK. C6(`video_prompt` 18 · `video_loop` 14 · `video_foot` 13) 통과.

## 계약과 다르게 한 것 (사유)
- 계획의 "QC 경고"를 **처리 경고(`process.json` warnings)** 로 구현: 새 QC 항목(QC-14)을 만들면 기준선 테스트의 QC id 목록 단언을 고쳐야 한다. 경고는 attempt 상세 `process.warnings`로 이미 노출된다.
- 계획의 "다리가 없는 몸" 판정을 상대 변화율로: 첫 구현(절대 폭 범위)은 4%만 찌그러지는 슬라임을 "다리 있음"으로 판정했다 — 합성 클립으로 발견. 측면은 하체 폭의 변화율(평균 대비 15%), 앞/뒷모습은 키의 4%.
- "점프 지표"의 몸통 중심: 몸통 띠(고정 행 범위)의 무게중심은 몸이 통째로 위아래로 움직여도 거의 안 변해 구분력이 없었다(측정) → 전체 질량 중심으로. 머리는 각 프레임 자신의 상단 20% 띠.
- 계획 DoD의 "정지한 걷기의 jolt ≈ 0" 단언은 과한 기대였다: 팔다리가 겹치고 벌어지면 질량 중심이 자연히 ~0.02 흔들린다. 지표의 역할(튐 구분: 튀는 이동 0.15 ≈ 7배)에 맞는 단언으로 고침.

## 학습 / 주의
- 모든 임계값(15%·4%·0.02·0.15)은 합성 클립 기준 [낮음]. `max_jolt`의 권장값(문서에는 0.08 예시)은 실제 xAI 클립으로 정해야 한다.
- 발 디딤 시작은 *단일 방향*에서만 쓰며, sprite-gen의 "방향 세트에서 같은 쪽 발" 정렬과 `--foot` 지정은 채택하지 않았다(미채택 표 대상).
- 실제 영상에서 하체 40% 영역이 망토·치마 등을 포함하면 `legs_spread`가 흔들릴 수 있다 — 실사용 확인 항목.
