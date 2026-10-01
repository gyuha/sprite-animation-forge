# RUN — M0: 저장소 뼈대와 가짜 codex

서브에이전트 1개가 plan 전체를 구현했고, 오케스트레이터가 DoD 명령을 직접 재실행해 확인했다.

## 슬라이스 결과
- S1 pyproject(uv, `package=false`)·`uv.lock`·`.gitignore`·`sprite-animation-forge/` 뼈대 — ✅ as planned
- S2 합성 시트 생성기 15종(`make_sheet(variant, rows, cols, cell_size, seed)` → `SyntheticSheet`) — ✅ as planned
- S3 가짜 codex 9모드 — ✅ as planned (docs에 없는 `FAKE_CODEX_GRID` 환경 변수 추가)

## DoD baseline → after
- `uv run pytest -m "not live" -q`: pyproject 없음 → 75 passed
- 뼈대 파일 존재: 없음 → 둘 다 존재
- `-k synthetic`: 0 → 49 passed (변형 15종 + 결정성)
- `-k fake_codex`: 0 → 23 passed (9모드 + argv/PROMPT 위반 exit 2)
- `pytest --markers | grep live`: 없음 → live 마커 등록

## 판단·가정 (후속 task가 알아야 함)
- 합성 API: `from fixtures.synthetic.make import make_sheet, VARIANTS` (pytest가 `tests/`를 sys.path에 올림).
- `Cell.bbox`는 x1/y1 배타, 잡티 제외. `feet` = (다리 사이 x 중심, 다리 아래 첫 행).
- 가짜 codex는 `CODEX_HOME` 미설정 시 exit 2 (실제 홈 보호). argv는 `exec --json -C -o … -` 필수, `-o` 가 `-` 바로 앞.
- 실제 `codex` 바이너리는 호출하지 않았다.
