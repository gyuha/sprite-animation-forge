<!-- forge-slug: forge-m3-skill-acceptance -->
<!-- task: 12 -->
<!-- part: 12/12 -->
<!-- tdd: off -->
# M3-c: SKILL.md · references · 인수 시나리오 3~6 · Skill 자급성

## Goal / Non-goals
- Goal: docs/02 §10·§11, docs/12 M3 4번과 "M3 완료"를 닫는다: `SKILL.md`(frontmatter name/description, Workflow, Rules — docs/02 §10 초안 기반), `references/` 7개 파일(animation-rules, prompt-rules, character-consistency, qc-rules, codex-image, phaser-export, examples), `LICENSE`, 인수 테스트 `scenario_3`(hero 번들 idle·walk·run·attack → export 산출물 구조), `scenario_4`, `scenario_5`, `scenario_6`(탑다운 4방향), 시나리오 1을 export까지 확장. 모두 가짜 codex 기반.
- Non-goals: live end-to-end(Claude Code에서 실제 실행), Phaser 브라우저 스모크, M4~M6.

## Source of truth
- Glossary terms: none
- Related ADRs: none (docs/02 §10·§11, docs/11 §5, docs/01 §6 SKILL 배포 단위)
- Definition of Done:
  - `uv run pytest -v -q -k scenario` → 종료 코드 0, `scenario_1`~`scenario_6` 각각 최소 1건 PASSED
  - 시나리오 6: `left`는 Codex 호출 없이(가짜 codex 호출 횟수로 확인) `right`의 정확한 가로 반전, `animations.json` 키 8개, 방향 간 `body_height` 차이 ≤ 10%
  - `SKILL.md`에 frontmatter `name:`·`description:` 존재, `references/`에 7개 파일 존재 (`ls sprite-animation-forge/references | wc -l` → 7, 이 plan 이전엔 0)
  - 자급성: `sprite-animation-forge/`를 임시 디렉터리로 복사해 복사본의 `scripts/forge.py`를 `uv run --project <저장소 루트> python <복사본>/scripts/forge.py --help` (저장소 밖 디렉터리에서 실행)로 실행했을 때 종료 코드 0이고 12개 명령(doctor init reference identity plan prompt generate import-raw process accept export status)이 모두 출력됨
  - 전체 `uv run pytest -m "not live" -q` 통과, passed ≥ 150

## Work slices
- [ ] S1. `SKILL.md`, `references/*.md` 7종, `LICENSE` — completion criterion: DoD의 파일·frontmatter 항목 충족
- [ ] S2. 시나리오 3·6 인수 테스트(가짜 codex 전체 흐름 + export) — completion criterion: `scenario_3`, `scenario_6` PASSED (depends: S1)
- [ ] S3. 시나리오 4·5·1(export 확장) 인수 테스트 — completion criterion: `scenario_1`, `scenario_4`, `scenario_5` PASSED
- [ ] S4. 자급성 테스트(복사본에서 CLI 실행)와 전체 스위트 개수 하한 확인 — completion criterion: 자급성·전체 스위트 DoD 충족 (depends: S2, S3)
