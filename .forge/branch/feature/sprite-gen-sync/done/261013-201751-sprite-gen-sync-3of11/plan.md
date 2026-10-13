<!-- forge-slug: sprite-gen-sync-3of11 -->
<!-- task: 32 -->
<!-- part: 3/11 -->
<!-- tdd: on -->
# sprite-gen 동기화 3/11: 이미지 가장자리 안전 스케일(밝은 테두리·녹색 번짐 방지)

## Goal / Non-goals
- Goal: 스케일 단계가 셀을 줄일 때 **알파(커버리지)와 색을 따로** 리샘플해 가장자리에 밝은 테두리·키 색 번짐이 생기지 않게 한다(색은 불투명 화소만으로 가중, 알파는 별도 필터). `ProcessParams.resample = "coverage" | "legacy"`; `legacy`는 현재 동작과 **바이트 동일**. 기본값은 `coverage`이되 기존 sha256 핀 테스트가 `legacy`를 명시해 기대값 변경 없이 통과해야 한다(기본값 변경으로 달라진 기대값이 있으면 목록으로 run.md에 기록). 재처리 UI의 `set` 키(`resample`)와 `process.json` 기록을 포함한다.
- Non-goals: 스케일 전략(fit/preserve) 변경, 영상 경로 전용 복원(별도 작업).

## Source of truth
- Glossary terms: 생성 방식 (method) in .forge/CONTEXT.md
- Related ADRs: ADR-007(sprite-gen은 Apache-2.0, 재구현·코드 복사 없음; 근거 문서: https://github.com/aldegad/sprite-gen 기준 7bbc435, 2026-10-13) — 관련 문서: docs/05-sprite-pipeline.md 스케일 절 갱신
- Definition of Done:
  - `uv run pytest -q -k sg_resample` passed ≥ 6 (사전: 0건). 핵심 단언: 합성 키 색 스프라이트(어두운 몸통·밝은 하이라이트·날카로운 가장자리)를 비정수 배율로 줄여도 알파>0 화소의 각 채널이 원본 불투명 색 범위 ±2 안 — **legacy는 같은 입력에서 이 단언을 위반함을 보이는 대조 테스트 포함**(빨강→초록 증명)
  - `legacy` 바이트 동일: 기존 골든·결정성 sha 핀 테스트가 기대값 수정 없이 통과 (`git diff feature/xai-video -- sprite-animation-forge/tests | grep -c '^-.*sha256'` → 0)
  - 결정성: `uv run pytest -q -k determinism` 통과
  - 기준선 가드(회귀 가드 — 사전부터 통과, 의도된 것): `comm -23 .forge/branch/feature/sprite-gen-sync/baseline-tests.txt <(uv run pytest -m "not live" --collect-only -q 2>/dev/null | grep '::' | sort) | wc -l` → 0
  - 매핑 표 갱신: `docs/14-sprite-gen-sync.md`에 이 작업이 반영한 sprite-gen 기능마다 (기능 → 구현 파일 → 테스트 ID) 행 추가, `uv run python sprite-animation-forge/tests/sync_matrix.py` exit 0 (모든 ID 실존·통과)
  - TDD 진행 (각 슬라이스는 실패 테스트부터)
  - 전체 회귀: `uv run pytest -m "not live" -q` 통과 (사전 baseline: 903 passed / 4 skipped)

## Work slices
- [ ] S1. 리샘플 분리 구현과 `resample` 파라미터 — 완료 기준: sg_resample 테스트 통과
- [ ] S2. 기존 핀을 legacy로 고정하고 기본값 전환 — 완료 기준: 골든·결정성 통과, 기대값 diff 0 (depends: S1)
- [ ] S3. process.json·재처리 set·문서 — 완료 기준: 관련 서버·Vitest 테스트 통과 (depends: S2)
