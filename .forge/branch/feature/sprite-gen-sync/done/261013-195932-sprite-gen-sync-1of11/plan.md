<!-- forge-slug: sprite-gen-sync-1of11 -->
<!-- task: 30 -->
<!-- part: 1/11 -->
<!-- tdd: on -->
# sprite-gen 동기화 1/11: 영상 공급자 견고성(마감·다운로드·마스킹·거절 사유)와 매핑 표 도구

## Goal / Non-goals
- Goal: `providers/xai_video.py`를 sprite-gen v2.12~2.44의 영상 공급자 수정에 맞춰 보강하고, 이후 모든 작업이 쓰는 매핑 표 도구를 만든다. (1) **마감 시간 하나**: 제출→폴링→다운로드 전체가 `timeout_s` 하나에 묶이고, 각 transport 호출은 `min(자기 제한, 남은 시간)`만 기다린다(주입 가능한 `clock`). (2) 완료(`done`) 후 다운로드 실패(비200·전송 오류·mp4 아님)는 재시도 후 `error_code=video_unfinished` + `meta.request_id`로 끝난다. 완료인데 url이 없는 응답도 같다. 잘린·깨진·JSON 아닌 폴링 응답은 같은 id로 다시 묻는다(마감까지). (3) **마스킹**: 오류 메시지의 API 키(`xai-…`, `_`·`-` 뒤 포함), `Bearer <값>`, URL 서명(`X-Amz-Signature`·`sig=`)을 가린 *뒤에* 길이를 자른다. (4) **거절 사유**: 오류 본문의 provider 코드를 메시지에 넣고 content policy면 그렇게 말하며 `(HTTP n)`을 붙인다. (5) 매핑 표 도구 `tests/sync_matrix.py` + `docs/14-sprite-gen-sync.md` 뼈대.
- Non-goals: request_id 재개 명령(다음 작업), 실제 xAI 호출, 다른 공급자.

## Source of truth
- Glossary terms: 생성 방식 (method) in .forge/CONTEXT.md
- Related ADRs: ADR-007(sprite-gen은 Apache-2.0, 재구현·코드 복사 없음; 근거 문서: https://github.com/aldegad/sprite-gen 기준 7bbc435, 2026-10-13) — 관련 문서: docs/13-video-api-setup.md; sprite-gen docs의 video 공급자 절(읽기만, 코드 복사 없음)
- Definition of Done:
  - `uv run pytest -q -k sg_provider` passed ≥ 8 (사전: 0건 수집 — 순방향 검사). 마감 시간·다운로드 재시도·id 종료·깨진 폴링 재질문·마스킹 3종·거절 사유를 가짜 transport로 단언
  - `uv run python sprite-animation-forge/tests/sync_matrix.py` exit 0, 사전: 파일 없음으로 실패(순방향). 표에 영역 A 행 ≥ 4, 미채택 표 존재
  - 빨강→초록 증명: 마스킹·마감 테스트 각각 수정 전 코드에서 실패하는 것을 먼저 확인해 run.md에 기록
  - TDD 진행 (각 슬라이스는 실패 테스트부터)
  - 전체 회귀: `uv run pytest -m "not live" -q` 통과 (사전 baseline: 903 passed / 4 skipped)

## Work slices
- [ ] S1. 매핑 표 도구와 docs/14 뼈대 — 완료 기준: sync_matrix.py가 존재하는 ID만 통과시키고 없는 ID·빈 영역을 실패시키는 테스트 통과
- [ ] S2. 마감 시간 하나와 다운로드·깨진 응답 처리 — 완료 기준: 해당 sg_provider 테스트 통과 (depends: S1)
- [ ] S3. 마스킹과 거절 사유 — 완료 기준: 해당 sg_provider 테스트 통과 (depends: S1)
