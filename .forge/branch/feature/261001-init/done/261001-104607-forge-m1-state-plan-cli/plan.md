<!-- forge-slug: forge-m1-state-plan-cli -->
<!-- task: 5 -->
<!-- part: 5/12 -->
<!-- tdd: off -->
# M1-d: fsutil · manifest · 스키마 · plan · forge.py CLI (수동 raw 경로)

## Goal / Non-goals
- Goal: docs/08, docs/02 §5·§8·§9, docs/12 M1 3·4번을 구현한다: `fsutil.py`(attempt 번호 동시 할당, 파일 락, 원자적 쓰기, sha256), `manifest.py`(원자적 교체, 동시 쓰기 손실 없음), `schemas/*.schema.json`(animation-plan, character-profile, character-scale-profile, qc-report, manifest), `plan.py`(프리셋·`fall` 추가·grid 계산 RxC·번들·override·키 색 충돌 전환·방향 `directions`/`mirror`), `forge.py` 명령 `init / reference import / plan / import-raw / process / accept / status` (stdout JSON 하나, 종료 코드 0/1/2/3), 방향 지원: unit 경로 `<action>/<direction>`, `--direction`, `right` 채택 시 `left` 좌우반전 파생, `--direction left` → `mirrored_direction` 오류.
- Non-goals: generate/prompt/identity/doctor/export 명령(이후 plan), 실제 provider 호출.

## Source of truth
- Glossary terms: none
- Related ADRs: none (docs/01 ADR-004·006·011, docs/08, docs/02 §5·§8.1·§9, README PRD 충돌 해소)
- Definition of Done:
  - `uv run pytest -q sprite-animation-forge/tests -k "fsutil or manifest or plan or cli or direction or schema"` → 종료 코드 0, passed ≥ 30 (baseline: 없음)
  - attempt 번호를 프로세스 2개가 동시에 할당해도 충돌 없음, manifest를 프로세스 2개가 번갈아 갱신해도 손실 없음 (테스트 단언)
  - `plan`: 프레임 수 → grid 표(4→2x2, 6→2x3, 8→2x4, fall 2→1x2), override 우선, 키 색 충돌 시 green 전환, 번들 전개
  - 산출 JSON(plan, manifest, qc-report, 빈 character-profile/scale-profile 예시)이 `schemas/*.schema.json` 검증 통과 (`-k schema` ≥ 5 passed)
  - CLI: 각 명령 stdout이 파싱 가능한 JSON 한 개, `--direction left` 호출이 종료 코드와 `mirrored_direction`을 반환, `right` 채택 후 `left` 프레임이 `asymmetric_right` 픽스처의 정확한 가로 반전과 픽셀 일치하고 baseline·발 위치 유지
  - `python sprite-animation-forge/scripts/forge.py init`·`plan`·`import-raw`·`process`·`accept`·`status` 가 임시 root에서 합성 시트로 끝까지 실행됨

## Work slices
- [ ] S1. `fsutil.py`, `manifest.py` + 동시성 테스트 — completion criterion: fsutil·manifest 테스트 통과
- [ ] S2. `schemas/*.schema.json` 5종 + 스키마 검증 테스트 — completion criterion: `-k schema` ≥5 passed (depends: S1)
- [ ] S3. `plan.py`(프리셋·grid·번들·방향·mirror) + 테스트 — completion criterion: plan·direction 테스트 통과 (depends: S2)
- [ ] S4. `forge.py` 명령 7종과 방향/mirror 파생 + CLI 테스트 — completion criterion: CLI·direction 테스트 통과 (depends: S3)
