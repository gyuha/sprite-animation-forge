# RUN — M5-d: S6 내보내기 · S7 상태 · 일괄 생성 흐름 · 오류 UX

서브에이전트 1개가 구현, 오케스트레이터가 DoD 재실행으로 확인. 브라우저 검증은 아직 없음(M5-e).

## 슬라이스 결과
- S1 Export·Status 화면 — ⚠ 파일 크기(바이트)·평균 생성 시간은 API에 데이터가 없어 제외(화면에 사유 표시)
- S2 일괄 생성 흐름(`lib/batch.ts` 상태 머신, BatchPanel, 자동 채택·재생성 한도·토스트·검토 필요·`중단됨`·취소) — ✅ as planned
- S3 7개 라우트 연결 테스트와 오류 UX(ServerBanner, JobFailedCard, 타임아웃 문구) — ✅ as planned

## DoD baseline → after
- typecheck/build exit 0, Vitest: 94 → 146 passed (신규 52, ≥8)
- `routes.test.tsx`가 7개 경로→페이지 컴포넌트 매핑 단언

## 판단·가정 (후속 task가 알아야 함)
- 최단 경로: Plan의 `generate-all`은 plan이 새것/수정됐으면 먼저 저장 후 batch 시작 → 검토 필요 0건이면 `/c/:cid/export`로 자동 이동(`state.autoExport`)하고 Export 페이지가 누락 없을 때 스스로 export 실행. 검토 필요가 있으면 Plan에 머물며 `go-export` CTA.
- 알림: 본 batch만 sonner 토스트(+ 이미 허용된 경우에만 Notification, 권한 요청 안 함). 서버 연결 끊김 배너는 SSE 끊김 또는 health `network_error`.
- Export 엔진 select는 표시용(서버 export는 엔진 인자 없음, phaser+generic 둘 다 생성). Status의 해결 명령 중 `codex features enable image_generation`은 **docs에 없는 추정 문구라 검증 필요**(`mkdir -p ~/.codex`, `uv sync`, `pytest -m live`도 에이전트 선택).
- 백엔드 한계: export 엔진 파라미터 없음·HEAD 미지원·파일 크기 없음, `manifest.usage`에 시간 없음, SSE 스냅샷에 `log` 없음(진행 중 unit 목록 미표시), 종료된 Job 조회 불가(새로고침 후 batch 결과·CTA 소실, Dashboard는 `next_step`으로 Export 접근 가능).
- data-testid는 Export/Status/Plan/Dashboard 페이지 파일 상단 주석에 전체 목록(주요: `export-run export-zip export-missing-alert generate-all auto-accept-switch max-regen-select batch-progress go-export job-cancel-<id> server-unreachable-banner status-recheck`).
