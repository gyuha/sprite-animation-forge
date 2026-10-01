<!-- forge-slug: forge-m3-export -->
<!-- task: 11 -->
<!-- part: 11/12 -->
<!-- tdd: off -->
# M3-b: Atlas · Phaser JSON · animations.json · GIF · export 명령

## Goal / Non-goals
- Goal: docs/07, docs/12 M3 3번을 구현한다: `export/atlas.py`(배치 공식, 방향별 행·프레임 이름, mirror 프레임 포함, `atlas_too_large` 한도 계산), `export/phaser.py`(Phaser JSON Hash `hero.json`, `hero.meta.json`, `animations.json` 키 규칙), `export/gif.py`(프레임 지속 시간), 검증 로직, `forge.py export --engine phaser`(`atlas/`, `animations.json`, `preview/*.gif`, 캐릭터 단위 `qc-report.json`, `manifest.json` 갱신).
- Non-goals: Phaser 브라우저 스모크(Playwright/pnpm — 범위 제외). 대신 Phaser 3 JSON Hash 구조를 코드로 검증한다. Godot/Unity 등 Phase 2.

## Source of truth
- Glossary terms: none
- Related ADRs: none (docs/07, docs/01 ADR-011)
- Definition of Done:
  - `uv run pytest -q -k "export or atlas or phaser or gif"` → 종료 코드 0, passed ≥ 20 (baseline: 없음)
  - atlas 좌표·크기 공식 테스트, 이름 규칙, `animations.json`의 repeat(loop 여부), GIF 프레임 지속 시간, 4096 초과 시 `atlas_too_large`
  - 탑다운: `walk_down/up/right/left_*` 프레임 전부 atlas에 존재, `animations.json` 키 8개(idle·walk × 4방향), `left` 프레임은 `right`의 정확한 반전
  - `hero.json`의 모든 frame rect가 `hero.png` 경계 안, 프레임 이름이 `animations.json`에서 참조 가능, `hero.meta.json`의 origin 필드 존재
  - `python sprite-animation-forge/scripts/forge.py export <cid> --engine phaser` 가 합성 데이터로 실행되어 stdout JSON `{files, warnings}` 반환

## Work slices
- [ ] S1. `export/atlas.py` + 테스트 — completion criterion: atlas 테스트 통과
- [ ] S2. `export/phaser.py`(hero.json/meta/animations.json)와 검증 로직 — completion criterion: phaser·검증 테스트 통과 (depends: S1)
- [ ] S3. `export/gif.py` + `export` CLI 명령, manifest/qc-report 갱신 — completion criterion: gif·CLI export 테스트 통과 (depends: S2)
