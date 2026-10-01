<!-- forge-slug: forge-m1-bg-split-components -->
<!-- task: 2 -->
<!-- part: 2/12 -->
<!-- tdd: off -->
# M1-a: 배경 제거 · grid 분리 · 컴포넌트 필터

## Goal / Non-goals
- Goal: docs/05 §2~§5를 구현한다: 입력 검증, `pipeline/chroma.py`(테두리 샘플링 배경색 추정, 알파 램프 t_in=30/t_out=90, despill, 키 색 충돌 규칙, native alpha 감지), `pipeline/split.py`(이상적 경계, gutter 스냅, 행 띠별 세로 경계, 사용할 칸), `pipeline/components.py`(largest/all 모드, 잡티 제거, 떨어진 칼 유지).
- Non-goals: measure/scale/align/process(다음 plan), QC, CLI.

## Source of truth
- Glossary terms: none
- Related ADRs: none (docs/05, docs/11 §4 chroma·split·components 행, README PRD 충돌 해소 #5)
- Definition of Done:
  - `uv run pytest -q sprite-animation-forge/tests -k "chroma or split or components"` → 종료 코드 0, passed ≥ 25 (baseline: 해당 테스트 없음)
  - 합성 `model_like_bg`에서 추정 배경색과 (250,3,250)의 거리 < 15, 처리 후 네 모서리 알파 0, 전경에 magenta 잔여(`min(R,B)−G>40`) 없음 (테스트가 단언)
  - despill이 빨간색 픽셀 값을 바꾸지 않음, `pinkish_character`에서 키 색이 #00FF00으로 전환, `native_alpha`는 키잉을 건너뜀 (테스트가 단언)
  - `shifted_gutters`·`narrow_gutter` 분리 경계가 이상적 경계 ±6% 이내, `empty_cell` 칸은 무시됨 (테스트가 단언)
  - `specks`는 잡티가 제거되고 `detached_sword`는 largest 모드에서 유지됨 (테스트가 단언)

## Work slices
- [ ] S1. `pipeline/chroma.py` + 테스트 — completion criterion: chroma 테스트 전부 통과
- [ ] S2. `pipeline/split.py` + 테스트 — completion criterion: split 테스트 전부 통과
- [ ] S3. `pipeline/components.py` + 테스트 — completion criterion: components 테스트 전부 통과
