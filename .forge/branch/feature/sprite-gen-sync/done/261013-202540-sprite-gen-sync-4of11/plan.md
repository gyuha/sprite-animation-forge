<!-- forge-slug: sprite-gen-sync-4of11 -->
<!-- task: 33 -->
<!-- part: 4/11 -->
<!-- tdd: on -->
# sprite-gen 동기화 4/11: 이미지 레이아웃 가이드와 안전 영역

## Goal / Non-goals
- Goal: 정지 1장 생성(`breathe` 정지, 단일 프레임 생성)에 **레이아웃 가이드 이미지**를 두 번째 참조로 붙인다: 키 색 정사각 캔버스에 안전 영역(여백 한 칸 안쪽) 상자, 머리(crown) 선, 바닥(floor) 선을 그린 이미지. 프롬프트에는 안전 영역을 **행·열 수치**로 말하고(예: "keep the body inside rows a–b, columns c–d; feet on row b"), 가이드 이미지가 무엇을 뜻하는지 한 줄 설명을 넣는다. 가이드는 임시 파일로 만들고 `generation.json`의 references에 `layout-guide`로 기록한다. 격자(grid) 방식은 영향 없음.
- Non-goals: grid 시트에 가이드 첨부, 가이드 스타일 옵션, 실제 Codex 호출.

## Source of truth
- Glossary terms: 생성 방식 (method) in .forge/CONTEXT.md
- Related ADRs: ADR-007(sprite-gen은 Apache-2.0, 재구현·코드 복사 없음; 근거 문서: https://github.com/aldegad/sprite-gen 기준 7bbc435, 2026-10-13) — 관련 문서: docs/04-prompt-rules.md §3 갱신(가이드 문구), PROMPT_TEMPLATE_VERSION 상승
- Definition of Done:
  - `uv run pytest -q -k sg_image` passed ≥ 5 (사전: 0건): 가이드 이미지 픽셀 검사(머리·바닥선이 안전 상자 안쪽 한 칸 지점의 정해진 행에 있고 배경은 정확히 키 색), breathe 정지 생성에 이미지 2장 첨부(가짜 codex 호출 로그), grid 생성은 1장 유지, 프롬프트 스냅샷에 행·열 수치, generation.json 기록
  - 프롬프트 스냅샷 갱신 후 `UPDATE_SNAPSHOTS` 없이 `uv run pytest -q -k prompt` 통과
  - 기준선 가드(회귀 가드 — 사전부터 통과, 의도된 것): `comm -23 .forge/branch/feature/sprite-gen-sync/baseline-tests.txt <(uv run pytest -m "not live" --collect-only -q 2>/dev/null | grep '::' | sort) | wc -l` → 0
  - 매핑 표 갱신: `docs/14-sprite-gen-sync.md`에 이 작업이 반영한 sprite-gen 기능마다 (기능 → 구현 파일 → 테스트 ID) 행 추가, `uv run python sprite-animation-forge/tests/sync_matrix.py` exit 0 (모든 ID 실존·통과)
  - TDD 진행 (각 슬라이스는 실패 테스트부터)
  - 전체 회귀: `uv run pytest -m "not live" -q` 통과 (사전 baseline: 903 passed / 4 skipped)

## Work slices
- [ ] S1. 가이드 이미지 생성 함수 — 완료 기준: 픽셀 검사 테스트 통과
- [ ] S2. 프롬프트 수치·설명 줄과 버전 상승, 스냅샷 — 완료 기준: prompt 테스트 통과 (depends: S1)
- [ ] S3. breathe 정지 생성에 첨부·기록 — 완료 기준: 가짜 codex 호출 로그 테스트 통과 (depends: S2)
