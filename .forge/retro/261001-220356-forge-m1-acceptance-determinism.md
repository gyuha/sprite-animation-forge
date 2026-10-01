# 2026-10-01 — 종료 조건 검사 스크립트의 실행 가능성: 작성 시점에 한 번 돌려 보지 않으면 거짓 실패가 난다

## Plan vs actual
- What went as planned: 결정성·golden(skip)·시나리오 1·2 테스트 추가, 프로덕션 변경 없음.
- Divergences: 이 task가 아니라 루프 계약 쪽 결함이 드러남 — C2/C6이 `pytest -v -q`로 PASSED 줄을 읽도록 쓰였지만 `-v`와 `-q`가 상쇄되어 줄이 안 나왔고, C5의 "복사본 안에서 uv run"은 의존성이 없어 의도대로 실행 불가였다. 둘 다 구현이 아닌 검사 문구 결함(합격선은 그대로 두고 명령만 정정).

## Learnings
- Do differently next time: fg-loop INQUIRY의 "검사는 faithful해야 한다" 외에 **runnable at authoring time**이 필요하다 — 계약을 쓸 때 각 검사 명령을 한 번 실행해 출력 형식(파싱할 줄이 나오는지)과 실행 환경(의존성)을 확인한다. 실패 상태에서의 출력("0 passed, rc=5")이 파싱 가능한지도 본다. 뷰어 루프에서는 "두 시점 비교"가 주기와 맞물려 거짓 실패를 낸 같은 계열의 결함이 있었다 → 움직임 검사는 다중 표본이 기본.

## Doc updates
- CONTEXT.md promotion: none
- ADR added: none
