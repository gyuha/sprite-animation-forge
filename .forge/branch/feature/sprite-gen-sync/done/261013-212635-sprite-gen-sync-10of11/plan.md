<!-- forge-slug: sprite-gen-sync-10of11 -->
<!-- task: 39 -->
<!-- part: 10/11 -->
<!-- tdd: on -->
# sprite-gen 동기화 10/11: 원본 복원(source restoration)

## Goal / Non-goals
- Goal: 처리 과정(리샘플·보간)이 망가뜨린 셀을 **변경 불가 원본 프레임**에서 복원한다. (1) 처리된 셀의 알파 커버리지가 같은 원본 프레임의 커버리지에서 허용치(기본 8%) 이상 벗어나면 "손상"으로 판정. (2) 손상 셀은 원본 프레임을 `resample=coverage`로 다시 줄여 대체하되, 키 가드(키 색에 가까운 화소가 한 단계 이상 늘지 않음)를 지키고, 복원이 점프 지표를 악화시키면(보정이 없앤 점프를 되살림) 채택하지 않고 `regressed`로 기록. (3) `process.json`에 `restored: [{index, source_frame, reason}]` 출처 기록, 원본 프레임 파일은 attempt에 보존(`source-frames/`).
- Non-goals: 방향 세트·video-follow, 실제 영상 검증.

## Source of truth
- Glossary terms: 생성 방식 (method) in .forge/CONTEXT.md
- Related ADRs: ADR-007(sprite-gen은 Apache-2.0, 재구현·코드 복사 없음; 근거 문서: https://github.com/aldegad/sprite-gen 기준 7bbc435, 2026-10-13) — 관련 문서: docs/05 복원 절
- Definition of Done:
  - `uv run pytest -q -k sg_rife` passed ≥ 12 (누적, 이 작업이 ≥ 4 추가): 합성 손상(커버리지 12% 손실) 셀이 복원되어 커버리지 오차 ≤ 2%·키 가드 위반 0·점프를 되살리는 복원은 거부(regressed)·정상 셀은 손대지 않음(바이트 동일)·restored 출처 기록
  - 종단: 가짜 영상 provider 경로 attempt의 process.json에 restored 필드 규약 유지, 기존 `test_video_sprite.py` 통과
  - 기준선 가드(회귀 가드 — 사전부터 통과, 의도된 것): `comm -23 .forge/branch/feature/sprite-gen-sync/baseline-tests.txt <(uv run pytest -m "not live" --collect-only -q 2>/dev/null | grep '::' | sort) | wc -l` → 0
  - 매핑 표 갱신: `docs/14-sprite-gen-sync.md`에 이 작업이 반영한 sprite-gen 기능마다 (기능 → 구현 파일 → 테스트 ID) 행 추가, `uv run python sprite-animation-forge/tests/sync_matrix.py` exit 0 (모든 ID 실존·통과)
  - 테스트 파일명 규칙(체크 C7): 원본 복원 `test_sg_rife_restore.py` ≥ 4 (`-k "sg_rife and restore"`)
  - TDD 진행 (각 슬라이스는 실패 테스트부터)
  - 전체 회귀: `uv run pytest -m "not live" -q` 통과 (사전 baseline: 903 passed / 4 skipped)

## Work slices
- [ ] S1. 손상 판정과 복원 — 완료 기준: 관련 sg_rife 테스트 통과
- [ ] S2. 점프 악화 거부와 출처 기록 — 완료 기준: 관련 sg_rife 테스트 통과 (depends: S1)
- [ ] S3. 영상 attempt 종단 연결 — 완료 기준: 종단 테스트 통과 (depends: S2)
