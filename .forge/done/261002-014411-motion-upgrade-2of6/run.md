# RUN — 움직임 개선 2/6: 생성 방식(method) 필드와 호흡 idle(`breathe`)

TDD: `test_method_breathe.py`(17건)를 먼저 작성해 수집 오류(모듈 없음)로 빨간 상태를 확인한 뒤 구현. 오케스트레이터가 직접 구현.

## 슬라이스 결과
- S1 plan·스키마·CLI·API에 액션별 `method`(grid 기본·breathe·video): `--set <action>.method=`, 잘못된 값 `invalid_override`, fx에는 breathe 불가(`invalid_params`), `video`는 `method_unavailable`(exit 3, API 412 + `detail.reason`), `GET /api/presets`에 `methods{available, reason}` — ✅ as planned
- S2 `effects/breathe.py`: 목 병목 탐지(`find_neck`, 실패 시 몸 높이 30% 고정 분할 + `neck_not_found` 경고), 머리는 평행이동만, 몸통은 정수 행 매핑(끝점 보존)으로 늘이고 줄이기, 발 고정, 프레임 0 = 원본, 1주기 사인, 결정적 — ✅ as planned (눈 깜빡임은 제외, 아래 참고)
- S3 breathe 생성 경로: breathe 프롬프트(`action_still.txt`, 1x1·frames 1·"single still pose"), `pipeline/process.process_breathe`(1x1로 기존 파이프라인 처리 → N프레임 생성, process.json `params.method/breathe`·`derived.frames` N개), `workflow.process_attempt` 분기, 가짜 codex로 generate→process→accept 끝까지 — ✅ as planned
- S4 플랜 화면 "생성 방식" select(`action-method-<a>`; breathe 선택 시 frames 6·grid 1x1 고정, 동영상은 비활성 + `action-method-video-hint`로 사유 표시), e2e — ⚠ 사유를 tooltip이 아니라 select 아래 인라인 문구로 표시(비활성 SelectItem은 hover가 안 되어서)

## DoD baseline → after
- `-k "method or breathe"`: 0 → 23 passed (≥12; 신규 17 + 서버 5 + 기존 일치 일부)
- 전체 pytest 773 → 795 passed(4 skipped), Vitest 193 → 197, e2e 10 → 11, typecheck·build 통과
- 기존 테스트 수정 1건: `test_cli_plan_output_and_manifest_assumptions`의 기대 dict에 새로 항상 기록되는 `"method": "grid"` 키 추가(기대값 약화 아님)

## 판단·가정
- breathe 출력 프레임 수 = plan `frames`(기본 6, 1회 호흡 = 1루프). 진폭 기본 4%(몸통 높이 대비, 최소 1행)로 코드 상수이며 UI 노출 없음.
- 눈 깜빡임은 구현하지 않음: 임의 그림체에서 눈 영역 감지가 신뢰하기 어려워 계획의 "선택적" 항목을 보류(코드 주석에 명시). 필요하면 별도 작업.
- `PUT plan`의 "grid가 frames를 담아야 함" 검증은 breathe에서 제외(1x1 생성, N프레임 출력).
- 서버에서 `video` 가용성은 `plan.video_method_available()`(현재 False)로 판단 — #28에서 provider 연결 시 갱신.

## 실사용 확인
- `sprites/green`(읽기 전용)의 채택 idle 프레임에서 `breathe_frames`를 직접 적용: 3방향 모두 목 탐지 성공(neck_row 29/64px 셀), 6프레임 확인(`/tmp/breathe-green.png`: 머리 평행이동 + 몸통 신축). 64px 셀에서는 ±1px로 아주 미세함 — 큰 셀(128px 이상)에서 더 잘 보임.
- 실제 Codex로 확인: `forge.py plan <id> --actions idle --set idle.method=breathe` → `generate <id> idle`(1회 호출) → `process` → 뷰어에서 기존 4프레임 grid idle과 비교.
