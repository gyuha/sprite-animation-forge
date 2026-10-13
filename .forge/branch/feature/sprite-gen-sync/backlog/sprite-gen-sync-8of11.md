<!-- forge-slug: sprite-gen-sync-8of11 -->
<!-- task: 37 -->
<!-- part: 8/11 -->
<!-- tdd: on -->
# sprite-gen 동기화 8/11: 영상 발 디딤 시작·점프 지표·루프 리포트

## Goal / Non-goals
- Goal: (1) **발 디딤 시작**: 걷기·달리기 루프를 발이 땅에 닿는 프레임에서 시작하도록 시작 위치를 옮긴다. 신호는 시점별: 측면은 하체 영역의 두 다리 사이 가로 간격 최대 시점, 앞/뒷모습은 하체 아래 가장자리 높이 최저점 — 다리가 없는 몸이면 `start_foot_source: none`으로 건너뛴다. (2) **점프 지표(jolt index)**: 몸통 중심 궤적의 2차 차분 평균을 키 높이로 나눈 값과 머리 움직임을 모든 걷기에 기록, 기본은 게이트 없음(`max_jolt` plan 값이 있을 때만 QC 경고). (3) `video-meta.json`에 위 값과 선택 근거를 모아 기록하고 스튜디오 attempt 상세 API가 노출한다.
- Non-goals: 방향 세트 정렬, 발 지정 CLI(--foot), RIFE.

## Source of truth
- Glossary terms: 생성 방식 (method) in .forge/CONTEXT.md
- Related ADRs: ADR-007(sprite-gen은 Apache-2.0, 재구현·코드 복사 없음; 근거 문서: https://github.com/aldegad/sprite-gen 기준 7bbc435, 2026-10-13) — 관련 문서: docs/13, docs/06 QC 경고 항목 안내
- Definition of Done:
  - `uv run pytest -q -k sg_video` passed ≥ 14 (누적, 이 작업이 ≥ 2 이상 추가해 합계 ≥ 14): 합성 보행 클립에서 시작 프레임이 발 디딤 프레임(허용 ±1)·다리 없는 몸 건너뜀·jolt 값이 매끈한 클립 < 튀는 클립·`max_jolt` 초과 시에만 경고·video-meta 필드 존재
  - API: attempt 상세에 `video_meta` 포함 서버 테스트 통과, `pnpm --dir webui/web typecheck` 통과 (타입 재생성)
  - 기준선 가드(회귀 가드 — 사전부터 통과, 의도된 것): `comm -23 .forge/branch/feature/sprite-gen-sync/baseline-tests.txt <(uv run pytest -m "not live" --collect-only -q 2>/dev/null | grep '::' | sort) | wc -l` → 0
  - 매핑 표 갱신: `docs/14-sprite-gen-sync.md`에 이 작업이 반영한 sprite-gen 기능마다 (기능 → 구현 파일 → 테스트 ID) 행 추가, `uv run python sprite-animation-forge/tests/sync_matrix.py` exit 0 (모든 ID 실존·통과)
  - TDD 진행 (각 슬라이스는 실패 테스트부터)
  - 전체 회귀: `uv run pytest -m "not live" -q` 통과 (사전 baseline: 903 passed / 4 skipped)

## Work slices
- [ ] S1. 발 디딤 신호와 시작 이동 — 완료 기준: 관련 sg_video 테스트 통과
- [ ] S2. jolt 지표와 선택 게이트 — 완료 기준: 관련 sg_video 테스트 통과
- [ ] S3. video-meta 기록과 API 노출 — 완료 기준: 서버 테스트·typecheck 통과 (depends: S1, S2)
