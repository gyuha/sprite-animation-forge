<!-- forge-slug: sprite-gen-sync-7of11 -->
<!-- task: 36 -->
<!-- part: 7/11 -->
<!-- tdd: on -->
# sprite-gen 동기화 7/11: 영상 루프 선택 개선(느린 걷기·크기 고정·2주기·유지 그림·이음새 튐)

## Goal / Non-goals
- Goal: `video_loop.py`·`video_sprite.py`의 루프 선택을 강화한다. (1) **느린 걷기 재탐색**: 주기를 못 찾으면 썸네일을 줄이고 창을 늘려 다시 찾는다. (2) **크기 고정**: 주기 탐색 전에 각 프레임의 피사체 높이를 첫 프레임에 맞춘다(카메라 쪽으로 걷는 클립도 루프를 찾음). 되키울 때는 머리를 자르지 않고 폭을 넓힌다. (3) **2주기 계수**: 주기 p가 p/2에서도 이음새가 좋으면 "2주기 의심"으로 기록(`cycles_suspected`)하고 plan의 `cycles`(미지정=의심만 기록, 자르지는 않음)로만 확정한다. (4) **유지 그림(held drawings)**: 인접 프레임이 거의 같은 구간이 2~3프레임씩 반복되는 클립은 그림 단위로 중복 제거 후 선택하고 `held_drawings`·초당 그림 수를 기록. (5) **이음새 튐(seam pop)**: 닫는 이음새의 한 프레임 점프를 `seam_pop`로 기록, 상단을 읽을 수 없으면(알파 비어 있음) 건너뜀. (6) plan의 명시 길이 창(`min_len`/`max_len`)이 모든 경로에서 우선.
- Non-goals: 발 디딤 시작과 점프 지표(다음 작업), RIFE 보정, 실제 영상.

## Source of truth
- Glossary terms: 생성 방식 (method) in .forge/CONTEXT.md
- Related ADRs: ADR-007(sprite-gen은 Apache-2.0, 재구현·코드 복사 없음; 근거 문서: https://github.com/aldegad/sprite-gen 기준 7bbc435, 2026-10-13) — 관련 문서: docs/13-video-api-setup.md 루프 선택 절, docs/05 영상 절
- Definition of Done:
  - `uv run pytest -q -k sg_video` passed ≥ 12 (누적, 이 작업이 ≥ 6 추가): 합성 클립으로 느린 걷기(주기 ≈ 클립 2/3) 검출·크기가 변하는 클립의 크기 고정(출력 높이 편차 ≤ 3%)·2주기 클립 의심 계수·유지 그림 클립 중복 제거·seam_pop 기록과 상단 비어 있을 때 건너뜀·명시 창 우선
  - 기존 `test_video_sprite.py`·`test_video_provider.py` 무변경 통과 (`git diff feature/xai-video --stat -- sprite-animation-forge/tests/test_video_sprite.py` 삭제 줄 0)
  - 기준선 가드(회귀 가드 — 사전부터 통과, 의도된 것): `comm -23 .forge/branch/feature/sprite-gen-sync/baseline-tests.txt <(uv run pytest -m "not live" --collect-only -q 2>/dev/null | grep '::' | sort) | wc -l` → 0
  - 매핑 표 갱신: `docs/14-sprite-gen-sync.md`에 이 작업이 반영한 sprite-gen 기능마다 (기능 → 구현 파일 → 테스트 ID) 행 추가, `uv run python sprite-animation-forge/tests/sync_matrix.py` exit 0 (모든 ID 실존·통과)
  - TDD 진행 (각 슬라이스는 실패 테스트부터)
  - 전체 회귀: `uv run pytest -m "not live" -q` 통과 (사전 baseline: 903 passed / 4 skipped)

## Work slices
- [ ] S1. 느린 걷기 재탐색과 크기 고정 — 완료 기준: 관련 sg_video 테스트 통과
- [ ] S2. 2주기 계수와 명시 창 — 완료 기준: 관련 sg_video 테스트 통과 (depends: S1)
- [ ] S3. 유지 그림과 seam_pop 기록 — 완료 기준: 관련 sg_video 테스트 통과 (depends: S1)
