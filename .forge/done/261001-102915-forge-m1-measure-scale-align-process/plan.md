<!-- forge-slug: forge-m1-measure-scale-align-process -->
<!-- task: 3 -->
<!-- part: 3/12 -->
<!-- tdd: off -->
# M1-b: 측정 · 스케일 · 정렬 · process 조합

## Goal / Non-goals
- Goal: docs/05 §6~§11을 구현한다: `measure.py`(bbox, weak/strict feet line, x anchor 3종, body_height), `scale.py`(fit·preserve, 리샘플, 넘침 감지, profile 없으면 fit 대체), `align.py`(baseline 정렬, 정수 오프셋, 합성), `process.py`(단계 조합, `clean.png`·`frames/`·`sheet.png`·`process.json` 출력, 결정성 규칙).
- Non-goals: QC(다음 plan), CLI, Character Scale Profile 생성(M3). preserve 배율은 profile을 입력으로 받는 함수 시그니처만 갖춘다.

## Source of truth
- Glossary terms: none
- Related ADRs: none (docs/05 §6~§11, docs/11 §4 measure·scale·align 행, README PRD 충돌 해소 #1·#7)
- Definition of Done:
  - `uv run pytest -q sprite-animation-forge/tests -k "measure or scale or align or process"` → 종료 코드 0, passed ≥ 25 (baseline: 없음)
  - `thin_below_feet`에서 weak feet line이 가는 칼끝을 무시 (테스트 단언), x anchor 3종 계산
  - `wide_attack`에서 fit이 anchor 기준 여유로 계산되어 모든 프레임이 칸 안에 들어감, preserve 공식 단위 테스트, profile 없으면 fit 대체
  - `baseline_jitter` 입력을 정렬한 뒤 모든 프레임 feet이 baseline(기본 cell 128, margin_bottom 10 → 118) ±0.5px, 오프셋은 정수
  - `process`가 `clean.png`, `frames/*.png`, `sheet.png`, `process.json`을 쓰고 `sheet.png` 모서리 알파가 0

## Work slices
- [ ] S1. `pipeline/measure.py` + 테스트 — completion criterion: measure 테스트 통과
- [ ] S2. `pipeline/scale.py` + 테스트 — completion criterion: scale 테스트 통과 (depends: S1)
- [ ] S3. `pipeline/align.py` + 테스트 — completion criterion: align 테스트 통과 (depends: S2)
- [ ] S4. `pipeline/process.py` 조합과 출력 파일 — completion criterion: process 테스트 통과 (depends: S3)
