# RUN — M2-c: identity · reference generate/select · doctor/generate/prompt CLI

서브에이전트 1개가 구현, 오케스트레이터가 DoD 재실행으로 확인. 실제 codex 미호출(fake만), live 테스트 2건은 collect-only.

## 슬라이스 결과
- S1 `identity.py` + `identity analyze` (`--output-schema` 용 `character-profile.llm.schema.json` 신규) — ✅ as planned
- S2 `reference generate/select` — ✅ as planned
- S3 `doctor`, `prompt`, `generate` + `test_live_contract.py` — ✅ as planned (`generation.py`, `doctor.py` 모듈 추가)

## DoD baseline → after
- `-k "identity or reference or doctor or generate or prompt_cmd"`: 0 → 46 passed (신규 36 + 기존 일치 10)
- `pytest -m live --collect-only`: 2건 수집(실행 안 함), 기본 실행에서 제외(2 deselected)
- 전체: 488 → 524 passed, 4 skipped, 2 deselected

## 판단·가정 (후속 task가 알아야 함)
- fake_codex 확장(가산적): `--output-schema` 지원, 모드 `invalid_json`/`bad_schema`, 프로브 `--version`/`login status`/`features list`(`FAKE_CODEX_DOCTOR`=ok|logged_out|image_disabled|old_version). 기존 모드·테스트 유지.
- CLI 출력: `doctor`→`{codex, python, warnings, ready}`(항상 exit 0), `generate`→`{attempt, unit, status}`(실패 exit 2 + error_code/attempt/unit/status), `prompt`→`{prompt, references_needed, warnings}`. 선행 조건 부재는 exit 3(no_reference/no_profile/no_direction_reference 등). `ForgeError.extra`로 실패 JSON에 추가 필드.
- ADR-009 락: `<root>/.codex.lock` flock — generate/reference generate/identity analyze 전부 직렬화.
- 가정: `edited_by_user: true` 프로필은 `--force` 없이 덮어쓰지 않음(`profile_edited`), `identity analyze --empty` 추가(분석 실패 시 막다른 길 방지 — docs/03 §9 근거), 방향 reference는 대표 방향 accepted raw.png를 리사이즈 없이 사용, reference attempt는 manifest 미기재, `generate`는 login 사전 점검 없음, doctor 60초 캐시는 Web 서버 몫.
- live 계약 테스트는 실제 codex로 실행된 적 없음.
