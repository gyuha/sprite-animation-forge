<!-- forge-slug: motion-upgrade-4of6 -->
<!-- task: 27 -->
<!-- part: 4/6 -->
<!-- tdd: on -->
# 움직임 개선 4/6: 프롬프트·참조 이미지 개선

## Goal / Non-goals
- Goal: (1) 다중 방향 plan의 방향 참조를 "대표 방향 시트 전체"에서 "대표 방향 채택 결과의 단일 프레임 1장"(채택 frames 중 지정 인덱스, 기본 0)으로 교체(참조 이미지 상한 2장 유지). (2) 걷기·달리기 ACTION 문구 개선: 다리를 직접 지칭하지 않고, 제자리 동작 표현("as if on a treadmill" 계열 — 실측 요령의 의역), 앞/뒷모습 걷기에서 발을 교차하지 않도록 지시. (3) 프레임 수 8 이상 액션에 경고(plan 응답 warnings·플랜 화면 표시). (4) `PROMPT_TEMPLATE_VERSION` 상승, attempt의 `generation.json`에 프롬프트 버전 기록(이미 있으면 사용)하고 스튜디오 attempt 목록에 버전 표시(`attempt-prompt-version-<NNN>`).
- Non-goals: 레이아웃 가이드 이미지, 1×N 띠 생성, 다른 액션 문구 대폭 변경.

## Source of truth
- Glossary terms: none
- Related ADRs: none (근거: sprite-gen directional-anchor-workflow "다중 포즈 시트를 앵커로 쓰면 방향 고정이 흐려짐", video MOTION_TEXT 실측 요령 — 문구는 의역)
- Definition of Done:
  - TDD 진행
  - `uv run pytest -q -k "prompt or direction_reference"` 통과, 신규 ≥ 6 (baseline: 단일 프레임 참조 테스트 0건 — 순방향): 다중 방향 generate가 `ref-02.png`로 단일 프레임을 첨부(크기 = cell 크기 계열, 시트 아님), 걷기·달리기 문구 스냅샷, 다리 지칭 단어 금지 규칙(`validate_prompt`), 8프레임 경고
  - 스냅샷 갱신·버전 상승, 기존 테스트 유지
  - 스튜디오 버전 표시 Vitest ≥ 1, 전체 Vitest·e2e 통과
  - 실사용 확인 방법 기록(실제 Codex로 walk 이전/새 버전 비교)

## Work slices
- [ ] S1. 방향 참조 단일 프레임화 + 테스트 — completion criterion: direction_reference 테스트 통과
- [ ] S2. 걷기·달리기 문구, 금지 규칙, 8프레임 경고, 버전 상승 — completion criterion: prompt 테스트·스냅샷 통과
- [ ] S3. 스튜디오 프롬프트 버전 표시 — completion criterion: Vitest 통과 (depends: S2)
