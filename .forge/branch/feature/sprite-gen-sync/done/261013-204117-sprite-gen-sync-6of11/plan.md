<!-- forge-slug: sprite-gen-sync-6of11 -->
<!-- task: 35 -->
<!-- part: 6/11 -->
<!-- tdd: on -->
# sprite-gen 동기화 6/11: 영상 프롬프트(시점별 걷기·달리기)와 첫 프레임 캔버스 여유

## Goal / Non-goals
- Goal: `build_video_prompt`를 시점별로 세분화한다: 걷기·달리기는 모두 "제자리에서 자연스럽게"(트레드밀) 문구, 앞/뒷모습(down/up) 걷기는 "작고 차분한 걸음, 발을 내차지 않음"과 걸음 방향 설명, 달리기 앞/뒷모습 방향 설명, 측면은 현행. 호출자가 직접 쓴 `motion`(걸음걸이)은 그대로 유지하고 덮어쓰지 않는다. 첫 프레임 캔버스: attack은 정지 그림 위 20% 여유, 넓은 형태(wide)는 35% 행, walk·run은 머리 위 여유 없음(`prepare_first_frame`에 액션별 여유 인자). `VIDEO_PROMPT_VERSION` 상승.
- Non-goals: 말 등 비인간 몸체 문구(--body-plan), 영상 해상도 옵션.

## Source of truth
- Glossary terms: 생성 방식 (method) in .forge/CONTEXT.md
- Related ADRs: ADR-007(sprite-gen은 Apache-2.0, 재구현·코드 복사 없음; 근거 문서: https://github.com/aldegad/sprite-gen 기준 7bbc435, 2026-10-13) — 관련 문서: docs/04-prompt-rules.md §9 갱신
- Definition of Done:
  - `uv run pytest -q -k sg_video` passed ≥ 6 (사전: 0건): 시점별 문구 포함/미포함(측면에 앞/뒷모습 문구 없음)·호출자 motion 보존·캔버스 여유 픽셀 검사(attack 위 여유 ≥ 20% ±2%p, walk 0)·버전 상승·기존 `video_sprite` 테스트 통과
  - 기준선 가드(회귀 가드 — 사전부터 통과, 의도된 것): `comm -23 .forge/branch/feature/sprite-gen-sync/baseline-tests.txt <(uv run pytest -m "not live" --collect-only -q 2>/dev/null | grep '::' | sort) | wc -l` → 0
  - 매핑 표 갱신: `docs/14-sprite-gen-sync.md`에 이 작업이 반영한 sprite-gen 기능마다 (기능 → 구현 파일 → 테스트 ID) 행 추가, `uv run python sprite-animation-forge/tests/sync_matrix.py` exit 0 (모든 ID 실존·통과)
  - 테스트 파일명 규칙(체크 C6): 이 작업의 테스트는 `test_sg_video_prompt.py` (≥ 4건; `-k "sg_video and video_prompt"`)
  - TDD 진행 (각 슬라이스는 실패 테스트부터)
  - 전체 회귀: `uv run pytest -m "not live" -q` 통과 (사전 baseline: 903 passed / 4 skipped)

## Work slices
- [ ] S1. 시점별 문구와 버전 — 완료 기준: 프롬프트 테스트 통과
- [ ] S2. 액션별 첫 프레임 여유 — 완료 기준: 캔버스 픽셀 검사 테스트 통과
