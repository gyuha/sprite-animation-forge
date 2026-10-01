# RUN — M2-a: provider 추상화와 CodexCliProvider (가짜 codex)

서브에이전트 1개가 구현, 오케스트레이터가 DoD 재실행으로 확인. 실제 codex 바이너리는 호출하지 않음(테스트는 Popen을 감싸 fake 경로만 허용).

## 슬라이스 결과
- S1 `providers/base.py`(요청/결과/Protocol + `install_raw`), `providers/manual.py` — ✅ as planned
- S2 `providers/codex_cli.py`(argv·JSONL·2단계 수집·에러 분류·타임아웃/취소(프로세스 그룹)·generation.json) — ✅ as planned

## DoD baseline → after
- `-k codex_cli`: 0 → 17 passed (9모드 각각 PASSED + argv/no-shell/지시문/cancel/check)
- 전체: 370 → 391 passed, 4 skipped
- hang: 2초 타임아웃 후 `timeout`, PID·프로세스 그룹 종료 확인

## 판단·가정
- API: `CodexCliProvider(codex_bin=None, codex_home=None, reasoning_effort="low")` (env `SPRITE_FORGE_CODEX_BIN`, `CODEX_HOME`), `generate/check/cancel`, `build_argv`, `render_instruction`, `find_rollout_items`; `ManualUploadProvider(source)`.
- generation.json은 성공·실패 모두 기록(docs/03 §6.3 키). 로그는 `codex-events.jsonl`, `codex-stderr.txt`, `codex-last-message.txt`.
- error_code: codex_not_installed · codex_failed · timeout · canceled · image_gen_failed · no_image · invalid_image, 참조 3장 이상은 `too_many_references`.
- 지시문 템플릿은 모듈 상수(`codex_instruction@1`). 참조 이미지 축소/키 색 전처리는 reference importer 몫. `codex_version`은 null(추가 호출 회피), `check()`는 버전 반환.
- 한계: `check()`의 `--version`/`login status`/`features list` 파싱은 fake가 지원하지 않아 codex 부재 경로만 테스트됨. ADR-009(전역 동시 1개)는 호출자 책임.
