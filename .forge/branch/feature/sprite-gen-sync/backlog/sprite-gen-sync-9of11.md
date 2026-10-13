<!-- forge-slug: sprite-gen-sync-9of11 -->
<!-- task: 38 -->
<!-- part: 9/11 -->
<!-- tdd: on -->
# sprite-gen 동기화 9/11: RIFE 보간기 인터페이스·폴백·점프 보정·유령 프레임 검사

## Goal / Non-goals
- Goal: 선택적 프레임 보간(RIFE)을 **기본 경로를 깨지 않고** 붙인다. (1) `Interpolator` 인터페이스 `between(a, b, t) -> RGBA`와 `RifeNcnn` 구현(바이너리는 `SPRITE_FORGE_RIFE_BIN` 또는 PATH의 `rife-ncnn-vulkan`에서 찾음, 설치는 하지 않음). (2) `doctor`/`/api/health`에 `rife: {installed, bin}`(video 처럼 정보용, ready에 영향 없음). (3) **점프 보정**: 루프 안에서 인접 거리가 이상치인 프레임을 보간기가 있으면 이웃 두 프레임 사이에서 다시 만들고, 없으면 `rife_unavailable: cut as filmed` 경고로 원본 그대로 자른다. (4) **유령 프레임 검사**: 프레임 자신의 알파 커버리지로 두 그림이 겹친(cross-fade) 프레임을 판별해 `filmed-ghost`로 이름 붙이고, 깨끗한 이웃이 없으면 재촬영 사유(`retake: [...]`)로 기록. (5) 만든 프레임은 `made: [인덱스]`로 기록.
- Non-goals: RIFE 설치·다운로드, 실제 RIFE 실행 검증(이 환경에서 불가), 원본 복원(다음 작업).

## Source of truth
- Glossary terms: 생성 방식 (method) in .forge/CONTEXT.md
- Related ADRs: ADR-007(sprite-gen은 Apache-2.0, 재구현·코드 복사 없음; 근거 문서: https://github.com/aldegad/sprite-gen 기준 7bbc435, 2026-10-13) — 관련 문서: docs/13에 RIFE 선택 설치 안내(수동 설치 방법·확인 명령, 검증 안 된 부분은 확인 필요 표기)
- Definition of Done:
  - `uv run pytest -q -k sg_rife` passed ≥ 8 (사전: 0건): 바이너리 탐색 우선순위·미설치 폴백 경고·스텁 보간기로 점프 프레임이 이웃 사이 값으로 대체·유령 판별(두 실루엣 겹침 vs 정상)·깨끗한 이웃 없음 → retake 사유·`made` 기록·doctor/health 필드가 ready를 바꾸지 않음
  - RIFE 없는 환경에서 전체 테스트 통과: `env -u SPRITE_FORGE_RIFE_BIN uv run pytest -m "not live" -q` 통과
  - 기준선 가드(회귀 가드 — 사전부터 통과, 의도된 것): `comm -23 .forge/branch/feature/sprite-gen-sync/baseline-tests.txt <(uv run pytest -m "not live" --collect-only -q 2>/dev/null | grep '::' | sort) | wc -l` → 0
  - 매핑 표 갱신: `docs/14-sprite-gen-sync.md`에 이 작업이 반영한 sprite-gen 기능마다 (기능 → 구현 파일 → 테스트 ID) 행 추가, `uv run python sprite-animation-forge/tests/sync_matrix.py` exit 0 (모든 ID 실존·통과)
  - TDD 진행 (각 슬라이스는 실패 테스트부터)
  - 전체 회귀: `uv run pytest -m "not live" -q` 통과 (사전 baseline: 903 passed / 4 skipped)

## Work slices
- [ ] S1. 인터페이스·탐색·doctor — 완료 기준: 관련 sg_rife 테스트 통과
- [ ] S2. 점프 보정과 폴백 경고 — 완료 기준: 관련 sg_rife 테스트 통과 (depends: S1)
- [ ] S3. 유령 검사·재촬영 사유·made 기록 — 완료 기준: 관련 sg_rife 테스트 통과 (depends: S2)
