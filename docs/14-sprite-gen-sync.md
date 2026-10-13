# 14. sprite-gen 동기화 기록

[aldegad/sprite-gen](https://github.com/aldegad/sprite-gen)(Apache-2.0)의 2026-09-30 ~ 2026-10-13 변경(v2.12 → 2.44+, 기준 커밋 `7bbc435`)을 이 프로젝트에 **재구현**해 반영한 범위와 근거를 적는다. 코드는 복사하지 않고 문서·동작 사양을 읽어 우리 구조(Python Core + 결정적 후처리)에 맞게 다시 썼다(ADR-007). 상수와 문구는 우리 합성 데이터로 측정하거나 의역했다.

이 표는 검사 도구가 읽는다. 모든 행의 테스트 ID가 실제로 존재하고 통과해야 하며(`uv run python sprite-animation-forge/tests/sync_matrix.py`), 작업이 끝나는 시점에는 영역 A~D가 모두 채워지고 미채택 항목이 사유와 함께 있어야 한다(`--final`).

> 한계: 이 표의 테스트는 **합성 데이터에서 기능이 올바르게 동작하는지**만 증명한다. 실제 Codex·xAI·RIFE로 만든 결과가 더 자연스러워졌는지는 증명하지 않는다.

## 채택

### A. 영상 공급자 견고성

| sprite-gen 기능 | 구현 | 테스트 ID |
|---|---|---|
| 하나의 마감 시간이 폴링·대기·각 읽기를 제한 (남은 시간만 기다림, 마감에 닿는 대기는 시작하지 않음) | `providers/xai_video.py` `_once`·`_wait`·`_finish` | `sprite-animation-forge/tests/test_sg_provider.py::test_sg_provider_one_deadline_bounds_every_call_and_names_the_request`, `sprite-animation-forge/tests/test_sg_provider.py::test_sg_provider_no_wait_is_started_that_would_reach_the_deadline` |
| 완료 후 다운로드 실패는 재시도, 계속 실패하면 request_id와 함께 미완료로 종료 (다른 상태 코드는 재시도 없음) | `providers/xai_video.py` `_deliver`·`_download` | `sprite-animation-forge/tests/test_sg_provider.py::test_sg_provider_download_is_retried_then_succeeds`, `sprite-animation-forge/tests/test_sg_provider.py::test_sg_provider_download_still_failing_ends_unfinished_on_the_request_id`, `sprite-animation-forge/tests/test_sg_provider.py::test_sg_provider_a_download_refused_with_another_status_is_not_retried` |
| 완료인데 url이 없는 응답은 미완료로 종료 | `providers/xai_video.py` `_deliver` | `sprite-animation-forge/tests/test_sg_provider.py::test_sg_provider_done_without_a_url_ends_unfinished` |
| 잘리거나 JSON이 아닌 폴링, 429/5xx, 전송 오류는 같은 id로 다시 묻고 대기를 두 배로 | `providers/xai_video.py` `_finish` | `sprite-animation-forge/tests/test_sg_provider.py::test_sg_provider_an_unreadable_poll_is_asked_again_on_the_same_id`, `sprite-animation-forge/tests/test_sg_provider.py::test_sg_provider_poll_wait_doubles_while_polls_fail` |
| 폴링에서 인증이 거절돼도 request_id를 남김 | `providers/xai_video.py` `_finish` | `sprite-animation-forge/tests/test_sg_provider.py::test_sg_provider_credentials_rejected_on_a_poll_keep_the_request_id` |
| 오류 본문의 키·Bearer·URL 서명 마스킹 (자르기 전에 마스킹, 키 모양이 아닌 자격 증명도) | `providers/redact.py` | `sprite-animation-forge/tests/test_sg_provider.py::test_sg_provider_masks_keys_bearer_tokens_and_signatures`, `sprite-animation-forge/tests/test_sg_provider.py::test_sg_provider_the_credential_is_masked_even_when_it_has_no_key_shape`, `sprite-animation-forge/tests/test_sg_provider.py::test_sg_provider_masks_before_it_cuts_so_no_half_key_survives`, `sprite-animation-forge/tests/test_sg_provider.py::test_sg_provider_error_messages_never_carry_the_credential` |
| 거절 줄 형식 `<사유> (HTTP n) code=<코드>: <본문>`과 content policy 표시 | `providers/redact.py` `refusal_line`·`provider_code`, `xai_video.py` `_deliver` | `sprite-animation-forge/tests/test_sg_provider.py::test_sg_provider_a_refusal_line_names_the_status_and_the_providers_code`, `sprite-animation-forge/tests/test_sg_provider.py::test_sg_provider_a_moderated_clip_says_content_policy_and_is_not_resumable`, `sprite-animation-forge/tests/test_sg_provider.py::test_sg_provider_provider_code_reads_both_error_shapes` |
| `video-resume`: 끝나지 못한 생성을 request_id로 다시 묻기 (제출 없이, 재과금 없이, 같은 attempt 완료) | `generation.py` `resume_video_unit`, `providers/xai_video.py` `resume`, `cli.py` `resume` | `sprite-animation-forge/tests/test_sg_provider.py::test_sg_provider_resume_polls_and_downloads_without_submitting`, `sprite-animation-forge/tests/test_sg_provider.py::test_sg_provider_resume_that_runs_out_of_time_keeps_the_request_resumable`, `sprite-animation-forge/tests/test_sg_provider.py::test_sg_provider_resume_without_credentials_refuses_and_names_the_id`, `sprite-animation-forge/tests/test_sg_provider_resume.py::test_sg_provider_resume_finishes_the_same_attempt_without_a_second_submission`, `sprite-animation-forge/tests/test_sg_provider_resume.py::test_sg_provider_resume_cli_finishes_the_attempt_then_process_and_accept_work` |
| 요청이 수락되면 request_id를 attempt에 기록(`video-request.json`), 전달되면·제공자가 실패하면 지움, 인증 거절이면 보존 | `generation.py` `_generate_video_unit`·`_assemble_video_attempt` | `sprite-animation-forge/tests/test_sg_provider_resume.py::test_sg_provider_resume_an_unfinished_generation_leaves_the_request_id_to_resume`, `sprite-animation-forge/tests/test_sg_provider_resume.py::test_sg_provider_resume_after_the_provider_itself_failed_is_not_offered`, `sprite-animation-forge/tests/test_sg_provider_resume.py::test_sg_provider_resume_that_is_refused_credentials_keeps_the_id` |
| 이어받을 수 없는 attempt는 거부(영상 방식 아님·없는 attempt·이미 완료) | `generation.py` `resume_video_unit` | `sprite-animation-forge/tests/test_sg_provider_resume.py::test_sg_provider_resume_refuses_what_is_not_an_unfinished_video_attempt`, `sprite-animation-forge/tests/test_sg_provider_resume.py::test_sg_provider_resume_cli_reports_a_missing_request_as_a_precondition` |
| 서버: 이어받기 Job (영상 provider만 필요, 후처리·QC까지) | `routes/generate.py` `resume_attempt`, `job_tasks.py` `video_resume` | `webui/server/tests/test_sg_provider_resume_api.py::test_sg_provider_resume_api_finishes_the_attempt_as_a_job_without_codex`, `webui/server/tests/test_sg_provider_resume_api.py::test_sg_provider_resume_api_refuses_what_cannot_be_resumed`, `webui/server/tests/test_sg_provider_resume_api.py::test_sg_provider_resume_api_needs_a_connected_video_provider` |

### B. 이미지 경로 품질

| sprite-gen 기능 | 구현 | 테스트 ID |
|---|---|---|

### C. 영상 프롬프트·루프 선택

| sprite-gen 기능 | 구현 | 테스트 ID |
|---|---|---|

### D. RIFE 보정·복원

| sprite-gen 기능 | 구현 | 테스트 ID |
|---|---|---|

## 미채택

| 항목 | 사유 |
|---|---|
