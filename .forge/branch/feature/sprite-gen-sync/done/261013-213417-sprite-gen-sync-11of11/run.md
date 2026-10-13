# 실행 기록 — sprite-gen 동기화 11/11: 미채택 표·README·문서 정리와 최종 회귀 (task #40)

## 한 일
- `docs/14-sprite-gen-sync.md`: 미채택 표 9행(pixel-draw · 방향 세트 정렬 · video-follow · --body-plan · rife install · 원본 복원의 영수증·산출물 체계 · 손잡이 비전 검사 · 영상 연장·편집 · 격자 아닌 시트 레이아웃) 각각 사유, 기준 커밋(`7bbc435`, 2026-10-13)과 재구현 원칙은 문서 머리말, **사용자 확인 절차**(이 표의 테스트가 증명하지 못하는 것: 실제 Codex·xAI·RIFE 비교) 추가.
- `docs/README.md` 목록에 14 추가·13 설명 갱신, `docs/13` 낡은 표현("별도 작업에서 구현", "변환 기능 구현 후 사용") 정리, 루트 `README.md`에 "생성 방식(method)" 절(grid/breathe/video 표, 영상 연결·`resume`·sprite-gen 재구현 출처)과 문서 표 2행, `--handed` 예시 한 줄.

## 검증 (최종 회귀)
- `sync_matrix.py --final` 통과: 영역 A 11 · B 12 · C 13 · D 10행, 미채택 9행, 기준 sha 기재.
- C1~C9 전부 통과: pytest 1089 passed(4 skipped, 기준선 903 → +186), 기준선 ID 907개 모두 수집, Vitest 215, e2e 12, typecheck OK, `sg_provider` 33 · `sg_resample` 27 · `sg_image` 42 · `sg_video` 45 · `sg_rife` 34, main·origin/main·feature/xai-video 불변.

## 계약과 다르게 한 것 (사유)
- 계획의 "`grep -c 'method' README.md` ≥ 1"은 절 제목 한 줄로 충족(1건). 내용은 표로 풀어 썼다.
- 이 작업 자체의 DoD 체크는 위 마지막 회귀로 대체했다(별도 e2e 신규 없음 — 영상 e2e는 #29에서, 이번 동기화의 UI 변경은 Vitest로 검증).

## 학습 / 주의
- 개수 기준 체크는 하위 기능별 선택자 없이는 다른 기능의 테스트가 채워 줄 수 있다(#33 직후 C5로 확인, 체크 강화). 다음에 무인 구동 체크를 설계할 때는 처음부터 기능별 선택자를 둘 것.
- 이번 구동의 모든 임계값(루프·발 디딤·점프·유령·복원)은 합성 데이터 보정 [낮음]. 첫 실사용 때 `video-meta.json`을 보고 조정.
