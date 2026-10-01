# RUN — M1-d: fsutil · manifest · 스키마 · plan · forge.py CLI

서브에이전트 1개가 구현, 오케스트레이터가 DoD 재실행으로 확인.

## 슬라이스 결과
- S1 `fsutil.py`(attempt 동시 할당·락·원자적 쓰기·sha256), `manifest.py`(락 + read-modify-write) — ✅ as planned
- S2 `schemas/*.schema.json` 5종 + `schemas.py` 검증 — ✅ as planned
- S3 `plan.py`(프리셋·fall·RxC grid·번들·override·키 색 전환·방향/mirror) — ✅ as planned
- S4 `cli.py`/`workflow.py` + `forge.py` 명령 7종(init, reference import, plan, import-raw, process, accept, status) — ✅ as planned (`left` 파생·`mirrored_direction` 포함)

## DoD baseline → after
- `-k "fsutil or manifest or plan or cli or direction or schema"`: 0 → 122 passed (≥30)
- `-k schema`: 0 → 13 passed (≥5)
- 전체 `-m "not live"`: 237 → 355 passed (CLI subprocess 테스트로 약 30초)
- 동시 할당/갱신 손실 없음, plan 표, `asymmetric_right` 반전 픽셀 일치, `--direction left` 오류: 테스트가 단언 (통과)

## 판단·가정 (후속 task가 알아야 함)
- CLI 확장: `cli.py`에서 `@command("name", args=setup_fn)` 로 `handler(args)->dict` 등록 (중첩 이름 `("reference","import")` 가능). stdout JSON 1개, 오류는 `{error_code, message}`, 종료 코드 1/3 (2는 provider용 예약).
- 디렉터리: `<root>/<cid>/{manifest.json, animation-plan.json, reference/…, <unit>/attempts/NNN/{raw.png, generation.json, clean.png, frames/, sheet.png, process.json, qc-report.json}}`. unit = `<action>` (방향 1개) 또는 `<action>/<direction>`. mirror `left`는 `mirror.json {source, attempt}`만 갖고 attempts 없음.
- `process_attempt`가 `character-scale-profile.json`이 있으면 읽어 preserve/QC-07에 사용 → M3-a는 `accept_attempt` 끝(manifest 갱신 뒤)에서 파일을 쓰면 됨.
- manifest에 `settings`(init 옵션) 추가, 같은 reference 재import는 `reference_exists`, QC fail attempt를 accept하면 `forced: true`.
- 프리셋에 없는 액션은 `--set A.motion=…` 필요(기본 4프레임 2x2, qc_profile=action/fx). mirror 중간 전환(docs/02 §8.1 "중간에 바꾸기")은 미구현 — plan 재실행은 plan 파일만 교체.
- `--view/--facing` 옵션은 docs 외 소규모 추가. front→[down], rear→[up], 3/4→[right] 로 매핑.
