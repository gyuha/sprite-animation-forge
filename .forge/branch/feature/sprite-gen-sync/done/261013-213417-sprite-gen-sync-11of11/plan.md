<!-- forge-slug: sprite-gen-sync-11of11 -->
<!-- task: 40 -->
<!-- part: 11/11 -->
<!-- tdd: on -->
# sprite-gen 동기화 11/11: 미채택 표·README·문서 정리와 최종 회귀

## Goal / Non-goals
- Goal: 매핑 표를 완성하고 문서를 정리한다. `docs/14-sprite-gen-sync.md`에 (a) 영역 A~D 채택 행 전체 (b) **미채택 표**(pixel-draw · 방향 세트 정렬/video-set-sheet · video-follow · --body-plan · `rife install` — 각각 사유) (c) 참고한 sprite-gen 기준 시점(커밋 sha 7bbc435, 2026-10-13)과 재구현 원칙(ADR-007, 코드 복사 없음)을 적는다. `docs/README.md` 목록과 루트 `README.md`에 생성 방식(grid/breathe/video)·영상 방식 연결·이번 동기화 요약을 반영하고, docs/04·05·13의 stale 표현을 정리한다.
- Non-goals: 새 기능, 실제 Codex·xAI·RIFE 사용 확인(사용자 몫으로 run.md에 절차만 기록).

## Source of truth
- Glossary terms: 생성 방식 (method) in .forge/CONTEXT.md
- Related ADRs: ADR-007(sprite-gen은 Apache-2.0, 재구현·코드 복사 없음; 근거 문서: https://github.com/aldegad/sprite-gen 기준 7bbc435, 2026-10-13) — 관련 문서: docs/README.md, README.md, docs/04·05·13
- Definition of Done:
  - `uv run python sprite-animation-forge/tests/sync_matrix.py` exit 0: 영역 A~D 각 ≥ 1행, 미채택 표 ≥ 5행(사유 비어 있지 않음), 기준 sha 기재 (`grep -c 7bbc435 docs/14-sprite-gen-sync.md` ≥ 1)
  - `grep -c '14-sprite-gen-sync' docs/README.md` ≥ 1, `grep -c 'method' README.md` ≥ 1 (README에 생성 방식 절, 사전: 0)
  - 최종 회귀: `uv run pytest -m "not live" -q` 통과 + `pnpm --dir webui/web typecheck && pnpm --dir webui/web test && pnpm --dir webui/web e2e` 통과
  - 기준선 가드(회귀 가드 — 사전부터 통과, 의도된 것): `comm -23 .forge/branch/feature/sprite-gen-sync/baseline-tests.txt <(uv run pytest -m "not live" --collect-only -q 2>/dev/null | grep '::' | sort) | wc -l` → 0
  - TDD 진행 (각 슬라이스는 실패 테스트부터)
  - 전체 회귀: `uv run pytest -m "not live" -q` 통과 (사전 baseline: 903 passed / 4 skipped)

## Work slices
- [ ] S1. 매핑 표 완성·미채택 표·기준 시점 — 완료 기준: sync_matrix.py exit 0
- [ ] S2. README·docs 정리 — 완료 기준: grep 항목 통과 (depends: S1)
- [ ] S3. 최종 회귀와 사용자 확인 절차 기록 — 완료 기준: 전체 테스트·e2e 통과 (depends: S2)
