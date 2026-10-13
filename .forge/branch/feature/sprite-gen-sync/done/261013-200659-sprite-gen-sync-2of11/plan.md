<!-- forge-slug: sprite-gen-sync-2of11 -->
<!-- task: 31 -->
<!-- part: 2/11 -->
<!-- tdd: on -->
# sprite-gen 동기화 2/11: 영상 request_id 재개(CLI·서버)

## Goal / Non-goals
- Goal: 끝나지 못한 영상 생성을 **재과금 없이** 이어받는다. 요청이 수락되면 즉시 attempt에 `video-request.json`(request_id·provider·model·제출 시각 제외한 파라미터)을 쓰고, `video_unfinished`·인증 거절로 끝나도 파일을 남긴다. `VideoProvider`에 `resume(request_id, out_path, timeout_s, on_progress)`(제출 없이 폴링·다운로드만)를 추가하고 xAI·가짜 provider가 구현한다. Core `generation.resume_video_unit`과 CLI `forge.py resume <cid> <action> [--direction] --attempt NNN`, 서버 `POST …/attempts/{aid}/resume`(202 Job)을 만든다. 성공하면 같은 attempt가 `succeeded`가 되고 이후 변환(raw.png 조립)은 기존과 같다.
- Non-goals: 스튜디오 UI 버튼(서버·CLI까지), 영상 아닌 attempt의 재개, 실제 xAI 호출.

## Source of truth
- Glossary terms: 생성 방식 (method) in .forge/CONTEXT.md
- Related ADRs: ADR-007(sprite-gen은 Apache-2.0, 재구현·코드 복사 없음; 근거 문서: https://github.com/aldegad/sprite-gen 기준 7bbc435, 2026-10-13) — 관련 문서: docs/13-video-api-setup.md 문제 해결 표에 재개 안내 추가
- Definition of Done:
  - `uv run pytest -q -k sg_provider` passed ≥ 12 (누적, 이 작업 직전 ≥ 8 → 이 작업이 ≥ 4 추가): 재개 성공·제출 없이 폴링만 수행(가짜 transport 호출 로그에 POST 없음)·video-request.json 존재/삭제 조건·인증 거절 시 id 보존·비영상 attempt 재개 거부·서버 202 Job 끝까지
  - CLI 종단: 가짜 provider를 `pending` 상태에서 중단시킨 attempt를 `forge.py resume`로 완료시키는 테스트 통과 (사전: 명령 없음 — 순방향)
  - 매핑 표 갱신: `docs/14-sprite-gen-sync.md`에 이 작업이 반영한 sprite-gen 기능마다 (기능 → 구현 파일 → 테스트 ID) 행 추가, `uv run python sprite-animation-forge/tests/sync_matrix.py` exit 0 (모든 ID 실존·통과)
  - TDD 진행 (각 슬라이스는 실패 테스트부터)
  - 전체 회귀: `uv run pytest -m "not live" -q` 통과 (사전 baseline: 903 passed / 4 skipped)

## Work slices
- [ ] S1. provider `resume` 인터페이스와 video-request.json — 완료 기준: 단위 테스트 통과
- [ ] S2. Core·CLI resume — 완료 기준: CLI 종단 테스트 통과 (depends: S1)
- [ ] S3. 서버 엔드포인트와 Job — 완료 기준: 서버 테스트 통과, OpenAPI 타입 재생성 후 `pnpm --dir webui/web typecheck` 통과 (depends: S2)
