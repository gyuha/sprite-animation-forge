# RUN — M3-c: SKILL.md · references · 인수 시나리오 3~6 · Skill 자급성

서브에이전트 1개가 구현, 오케스트레이터가 DoD 재실행으로 확인. 프로덕션 코드 변경 없음(버그 미발견).

## 슬라이스 결과
- S1 `SKILL.md`, `references/` 7종(영문, 실제 CLI `--help`로 플래그 검증), `LICENSE`(MIT) — ✅ as planned
- S2 시나리오 3(hero 번들 4액션 fake generate→export)·6(탑다운 4방향, left는 Codex 호출 없음) — ✅ as planned
- S3 시나리오 1 export 확장 · 4·5(기존 test_recovery.py에 이미 `scenario_4/5` 이름으로 존재) — ✅ as planned
- S4 자급성 테스트(복사본 forge.py 실행, `sprite_forge.__file__`이 복사본 경로임을 단언) · 전체 스위트 — ✅ as planned

## DoD baseline → after
- `uv run pytest -v -k scenario`: 6건(1·2·4·5) → 11건, scenario_1~6 전부 PASSED
- `ls sprite-animation-forge/references | wc -l`: 0 → 7
- 전체 `-m "not live"`: 580 → 586 passed, 4 skipped, 2 deselected (≥150)

## 판단·가정
- fake_codex에 가산적 `FAKE_CODEX_CALL_LOG`(이미지 생성 호출 1건당 1줄) 추가 + 테스트. 시나리오 6은 정확히 6회 호출, `left` 생성은 `mirrored_direction`으로 거부되고 로그 불변.
- 시나리오 6의 body_height 비교는 프레임 alpha bbox와 `character-scale-profile.json` 대비(≤10%).
- `PRD.md`가 저장소에 없어 examples.md의 "PRD §27" 예시 4종은 docs/02 §7·§9.3·§8.1 기반 대표 요청으로 작성(plan 출력은 실제 실행 결과).
- `--art-style`은 `init`에만 있고 `plan`에는 없어 SKILL.md/examples는 `init`에서 설정.
- Phaser 브라우저 스모크는 범위 제외 — export의 구조 검증과 프레임·이름·경계 단언이 대체.
- 이전 task(M3-b) 후속 수정: GIF 지속시간 반올림을 docs/05 §10 규칙(`floor(x+0.5)`)으로 통일(커밋 a646c02, 8fps → 130ms). 아카이브된 M3-b run.md의 "120ms" 서술은 이 수정 이전 상태.
