# RUN — M3-b: Atlas · Phaser JSON · animations.json · GIF · export 명령

서브에이전트 1개가 구현, 오케스트레이터가 DoD 재실행으로 확인. Phaser 브라우저 스모크는 범위 제외(대신 `validate.py` 코드 검증).

## 슬라이스 결과
- S1 `export/atlas.py`(행 단위 배치·프레임 이름·`atlas_too_large`·`cell_mismatch`) — ✅ as planned
- S2 `export/phaser.py`(JSON Hash + meta + generic + animations.json) · `export/validate.py` — ✅ as planned
- S3 `export/gif.py` + `export` CLI, character qc-report·manifest 갱신 — ✅ as planned

## DoD baseline → after
- `-k "export or atlas or phaser or gif"`: 0 → 36 passed (≥20, 전부 신규)
- 전체: 544 → 580 passed, 4 skipped, 2 deselected
- 단언: 4액션×6프레임@128 → 782×522, side-action 8×8 → 1042×1042, topdown-rpg@128 → 1042×2602 / @256 → `atlas_too_large`, `left`==`right` 정확 반전, animations.json 8키, 손상 atlas 검증 실패

## 판단·가정
- 출력: `atlas/<cid>.{png,json,generic.json,meta.json}`, `animations.json`, `preview/<key>.gif`, character `qc-report.json`(`actions{unit:{attempt,status,score}}`, `forced_accepts`), manifest `exports.phaser{exported_at, files{path:sha256}}`. `.export.new/`에 쓰고 검증 후 이동 → 실패 시 `atlas/` 미잔존.
- 채택된 unit만 행/키로 포함, mirror unit은 source 채택 시 채택으로 간주. 채택 0건이면 `nothing_to_export`(exit 3), 일부 누락은 `missing_actions: [...]` 경고.
- `origin = {x:0.5, y: baseline/cell_h}` (118/128 → 0.921875), baseline은 scale profile → 없으면 cell_h−margin.
- GIF 지속시간은 Python `round`(8fps → 120ms, 문서의 130ms와 반올림 차이), Pillow가 동일 연속 프레임을 병합해 GIF 프레임 수가 액션보다 적을 수 있음. `hero.meta/generic`의 JSON 스키마 파일은 없어 코드로 필수 필드 검증.
- `meta.actions[]`에 `direction`, `unit`, mirror 행은 `mirror_of` 추가.
