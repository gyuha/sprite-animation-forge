<!-- forge-slug: sprite-gen-sync-5of11 -->
<!-- task: 34 -->
<!-- part: 5/11 -->
<!-- tdd: on -->
# sprite-gen 동기화 5/11: 공격 머리 위 여유·앞/뒷모습 유지·손잡이 방향

## Goal / Non-goals
- Goal: (1) **머리 위 여유**: attack·jump 계열 액션의 프롬프트와 plan 여백이 머리 위 공간을 더 준다(공격은 셀 높이의 20% 안팎, 다른 액션은 현행) — 정확한 수치는 우리 plan 여백(px) 체계로 환산해 docs에 근거와 함께 기록. (2) **앞/뒷모습 유지**: view가 front/rear(또는 down/up 방향)인 정지·액션 프롬프트에 "다른 그림에서 다시 그려도 정면/뒷면을 유지하고 3/4로 돌리지 않는다" 문구. (3) **손잡이 방향**: plan 필드 `handed`(`none` 기본 | `left` | `right`) — 한쪽 손 소지품이 있으면 좌우 미러를 자동으로 끄고(plan note로 알림) 왼쪽 방향은 직접 생성하며 프롬프트에 "소지품이 {손}에 있고 보는 쪽에서 가까운/먼 쪽"을 말한다. `none`이면 기존 프롬프트와 바이트 동일.
- Non-goals: 소지품 자동 감지(identity가 이미 경고만 함), 손잡이 검사용 비전 확인.

## Source of truth
- Glossary terms: 생성 방식 (method) in .forge/CONTEXT.md
- Related ADRs: ADR-007(sprite-gen은 Apache-2.0, 재구현·코드 복사 없음; 근거 문서: https://github.com/aldegad/sprite-gen 기준 7bbc435, 2026-10-13) — 관련 문서: docs/04-prompt-rules.md, docs/02-skill-spec.md plan 필드 갱신, 스키마 `animation-plan.schema.json`
- Definition of Done:
  - `uv run pytest -q -k sg_image` passed ≥ 12 (누적, 이 작업이 ≥ 7 추가): 공격 여유 수치·앞/뒷모습 문구(front/rear/down/up에서만)·handed별 미러 해제와 방향 목록·`handed=none` 프롬프트 바이트 동일(기존 스냅샷 변경 0)·스키마 검증·서버 PUT 검증
  - 플랜 화면: 손잡이 선택 Vitest ≥ 1, `pnpm --dir webui/web typecheck && pnpm --dir webui/web test` 통과
  - 기준선 가드(회귀 가드 — 사전부터 통과, 의도된 것): `comm -23 .forge/branch/feature/sprite-gen-sync/baseline-tests.txt <(uv run pytest -m "not live" --collect-only -q 2>/dev/null | grep '::' | sort) | wc -l` → 0
  - 매핑 표 갱신: `docs/14-sprite-gen-sync.md`에 이 작업이 반영한 sprite-gen 기능마다 (기능 → 구현 파일 → 테스트 ID) 행 추가, `uv run python sprite-animation-forge/tests/sync_matrix.py` exit 0 (모든 ID 실존·통과)
  - TDD 진행 (각 슬라이스는 실패 테스트부터)
  - 전체 회귀: `uv run pytest -m "not live" -q` 통과 (사전 baseline: 903 passed / 4 skipped)

## Work slices
- [ ] S1. 머리 위 여유 — 완료 기준: 관련 sg_image 테스트 통과
- [ ] S2. 앞/뒷모습 유지 문구 — 완료 기준: 관련 sg_image 테스트 통과
- [ ] S3. handed plan 필드·미러·프롬프트·스키마 — 완료 기준: 관련 테스트와 스냅샷 불변 통과 (depends: S2)
- [ ] S4. 플랜 화면 선택 — 완료 기준: Vitest 통과 (depends: S3)
