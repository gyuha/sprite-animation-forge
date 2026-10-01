# RUN — M1-e: 결정성 · golden(skip) · 시나리오 1·2 (수동 raw)

서브에이전트 1개가 테스트만 추가(프로덕션 코드 변경 없음, 버그 발견 없음), 오케스트레이터가 DoD 재실행으로 확인.

## 슬라이스 결과
- S1 `tests/test_determinism.py` 13건(process_sheet 2회×변형 4×전략 2, CLI 2 root, CLI 2 attempt) — ✅ as planned
- S2 `tests/test_golden.py` 4건(샘플 없으면 skip) — ✅ as planned (실제 샘플 부재로 skip만 실행됨)
- S3 `tests/test_acceptance_manual.py` `scenario_1`, `scenario_2` — ✅ as planned (export 제외)

## DoD baseline → after
- `-k determinism`: 0 → 13 passed
- `-k "scenario_1 or scenario_2"`: 0 → 2 passed
- `-rs -k golden`: 4 skipped, 사유 "no local Codex samples in …/codex-samples (record with `pytest -m live --record-samples`)"
- 전체: 355 → 370 passed, 4 skipped

## 판단·가정
- golden 테스트는 파일명에 "idle"이 있으면 2x2/4프레임, 아니면 2x3/6프레임으로 가정. 합성 `model_like_bg`로 임시 검증했을 때 배경 거리가 ≈20.3으로 임계(15)를 넘었으나, 이는 합성 모서리 음영 때문이고 실측값(7.1/12.4)은 임계 안이라 임계값 15는 문서대로 유지(golden은 실제 샘플 전용).
- 2 attempt 비교는 qc-report.json(attempt id 포함) 제외.
- 체크 스크립트 정정: C2/C6 `-v -q`는 상쇄되어 PASSED 줄이 안 나오므로 `-v`로 실행(체크 의미 불변, loop.md 문구 동일 정정).
