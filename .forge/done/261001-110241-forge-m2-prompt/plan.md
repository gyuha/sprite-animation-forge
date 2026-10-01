<!-- forge-slug: forge-m2-prompt -->
<!-- task: 8 -->
<!-- part: 8/12 -->
<!-- tdd: off -->
# M2-b: 프롬프트 생성기와 템플릿

## Goal / Non-goals
- Goal: docs/04를 구현한다: `prompt.py` + `prompt_templates/*.txt`(HEADER, REFERENCE IDENTITY, ART STYLE, CAMERA(방향별 문구), ACTION(모션 라이브러리 전 액션), ADDITIONAL DIRECTION, RECOVERY, CONSISTENCY RULES, GRID RULES, BACKGROUND RULE, FOOTER), Case B canonical reference 프롬프트, 복구 문구, `DIRECTION REFERENCE` 블록과 대표 방향 sheet 추가 첨부, 템플릿 버전 기록, §8 검증 규칙.
- Non-goals: identity 분석, provider 호출, CLI(M2-c).

## Source of truth
- Glossary terms: none
- Related ADRs: none (docs/04, docs/11 §4 prompt 행)
- Definition of Done:
  - `uv run pytest -q -k prompt` → 종료 코드 0, passed ≥ 20 (baseline: 없음)
  - docs/04 §8 규칙 전부가 각각 테스트로 존재(금지 규칙 위반 시 예외 또는 검증 실패)
  - 스냅샷 테스트: walk(side), idle(topdown down/up/right)의 조립 결과가 스냅샷과 일치하고 템플릿 버전이 기록됨
  - 복구 코드별(`edge_touch`, `scale_drift` 등) 문구·margin 변화 테스트
  - 모션 라이브러리가 docs/04 §4의 액션 전부(idle·walk·run·attack·shoot·cast·jump·fall·hurt·death)를 포함

## Work slices
- [ ] S1. 블록 템플릿과 `prompt.py` 조립(HEADER~FOOTER) — completion criterion: 조립·규칙 테스트 통과
- [ ] S2. 모션 라이브러리·복구 문구·Case B — completion criterion: 액션별·복구 테스트 통과 (depends: S1)
- [ ] S3. 방향 CAMERA/DIRECTION REFERENCE, 스냅샷 테스트 — completion criterion: 스냅샷 테스트 통과 (depends: S1)
