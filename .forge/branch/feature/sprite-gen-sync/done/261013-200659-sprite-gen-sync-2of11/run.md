# 실행 기록 — sprite-gen 동기화 2/11: 영상 request_id 재개 (task #31)

## 한 일
- `generation.py`: 영상 attempt 생성을 생성/조립/실패 처리로 분리. 요청이 수락되면(`submitted` 진행 이벤트) 즉시 `video-request.json`(request_id·provider·model·길이·해상도·마지막 프레임 고정 여부) 기록. 끝나지 못한 종료(`meta.unfinished`)면 보존하고 오류 `extra`에 `request_id`·`resumable=true`, 제공자가 직접 실패(`video_failed`·정책 거절)면 지움. 전달되면 지움. 신규 `resume_video_unit`(제출 없이 `provider.resume` → 같은 조립 경로).
- `providers/xai_video.py` `resume`, `video_base.VideoProvider.resume`, 가짜 provider가 제출 없는 새 프로세스에서도 실제 클립(내장 합성 캐릭터)을 돌려줌.
- CLI `forge.py resume <cid> <action> --attempt NNN [--timeout]`. 서버 `POST …/attempts/{aid}/resume`(202 Job, 영상 provider만 필요, 후처리·QC까지, 요청 없으면 412, 없는 attempt 404). Job 타입은 기존 `action_generate`를 재사용(UI 타입 변경 없음).
- 테스트 공용 도우미 `tests/sg_helpers.py`(가짜 시계·스크립트 transport) 분리. docs/10·13·14 갱신, OpenAPI 타입 재생성.

## 검증
- `sg_provider` 33건(이번 작업에서 +13: provider 3 · Core/CLI 7 · 서버 3). 전체 pytest 941 passed, 기준선 ID 누락 0, Vitest 212, e2e 12, typecheck OK.

## 계약과 다르게 한 것 (사유)
- `generation_status`는 provider 결과 상태 그대로(`timeout`) — 이미지 경로의 기존 규약과 같아서 `failed`로 바꾸지 않음. 계획 문구의 "비영상 attempt 재개 거부"는 에러 코드 `not_resumable`로 구현.
- 스튜디오 UI의 "이어받기" 버튼은 계획의 비목표대로 만들지 않음. 지금은 CLI·API로만 가능(사용자가 알아야 할 공백).

## 학습 / 주의
- 플랜에서 `method=video`를 고르려면 영상 provider가 연결돼 있어야 해서 테스트 픽스처가 `SPRITE_FORGE_VIDEO_PROVIDER=fake`를 먼저 켜야 한다.
- 실제 xAI에서 재개가 동작하는지(폴링 URL 수명, request_id 유효 기간)는 미검증 [낮음]. sprite-gen은 "새 URL을 받으려고 다시 폴링"하는 방식이라 같은 가정을 씀.
