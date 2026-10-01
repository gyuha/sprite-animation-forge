# RUN — 애니메이션 뷰어

서브에이전트 1개가 구현, 오케스트레이터가 stop-condition 검사 스크립트(저장소 밖)로 확인하고 스크린샷을 직접 확인.

## 슬라이스 결과
- S1 `lib/viewer.ts`(프레임 URL·타일 배치·공유 시계 `tileFrame`) + Vitest — ✅ as planned
- S2 `Viewer.tsx`(`/c/:cid/view`: 공유 rAF 시계, 캔버스 타일, 전체 재생/속도/배율/배경, 확대 dialog, "미채택" 플레이스홀더) + 진입 링크(Dashboard 카드·내비·Export·Studio) — ✅ as planned (Dashboard 카드는 `<a>` 중첩 방지를 위해 div로 감싸고 버튼을 분리, `character-card-<id>`·href 불변)
- S3 Playwright 신규 3건(`e2e/viewer.spec.ts`: 측면 npc 재생·픽셀·프레임 변화·zoom, 탑다운 4방향+mirror left, 진입 링크) — ✅ as planned

## DoD baseline → after
- Vitest 146 → 171 passed, e2e 4 → 7 passed(3회 연속 에이전트 확인), Python 750 → 751 passed
- 실제 데이터 `sprites/green`(읽기 전용): 타일 20/20, 불투명 픽셀 20/20, 2.75초 샘플링에서 프레임이 2종 이상 바뀐 타일 20/20, left(mirror) 포함, 콘솔 오류 0 — 스크린샷 `/tmp/viewer-green.png`로 육안 확인(5액션×4방향 격자, 선명, 겹침/빈 타일 없음)

## 판단·가정
- 검사 스크립트 정정(내 쪽 결함): C4 "프레임이 바뀜"을 두 시점 비교로 구현했더니 주기와 표본 간격이 맞물려 12/20만 감지됨 → 250ms 간격 10회 표본에서 서로 다른 프레임이 2종 이상인지로 변경(기준 강화 방향, 합격선 약화 아님). 구현은 수정하지 않음.
- one-shot 액션은 마지막 프레임을 400ms 유지 후 반복(뷰어용). 속도 변경 시 누적 시간에 배율이 곱해져 프레임이 점프함(재생 중 배속 변경 한정).
- `canvas[data-testid^="viewer-tile-"]`로 세야 재생 타일만 집계(`viewer-tile-missing-*`도 접두사 공유).
- 서버·Core 변경 없음. 1440px에서 격자가 화면 왼쪽 절반만 채움(의도적으로 유지).
- 직전 요청들의 미커밋 변경(Taskfile·--host·vite 프록시)은 계약 커밋 `9d6e69e`에 함께 들어감.
