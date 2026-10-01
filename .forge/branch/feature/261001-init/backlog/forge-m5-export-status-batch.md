<!-- forge-slug: forge-m5-export-status-batch -->
<!-- task: 19 -->
<!-- part: 7/8 -->
<!-- tdd: off -->
# M5-d: S6 내보내기 · S7 상태 · 일괄 생성 흐름 · 오류 UX

## Goal / Non-goals
- Goal: docs/09 §4 S6·S7, §7(일괄 생성), §8(오류·예외 UX), docs/12 M5 4·5번. `Export`(엔진 select, 누락 액션 alert, QC 요약 table, export 실행, ZIP 다운로드), `Status`(Codex 상태 카드, 서버/Job 상태), 일괄 생성 흐름(`generate-all` 호출, 진행 progress, 자동 채택 switch, 액션별 `max_regenerations`, 완료 sonner 토스트(Notification 권한 없을 때), 실패 unit은 "검토 필요"로 두고 진행, 서버 재시작 후 `중단됨` 표시와 재생성 버튼), 전역 오류 UX.
- Non-goals: Playwright 시나리오(M5-e).

## Source of truth
- Glossary terms: none
- Related ADRs: none (docs/09 §4 S6-S7, §7, §8)
- Definition of Done:
  - `pnpm --dir webui/web typecheck`·`build`·`test` 통과, Vitest passed ≥ 40 (누적; 신규 ≥ 8: 누락 액션 경고, ZIP 링크, 배치 진행 상태 머신, 자동 채택 정책, `중단됨` 표시, 오류 정규화 UX 등)
  - `src/pages/{Export,Status}.tsx` 존재, 7개 페이지 전부 라우트에 연결(`routes.tsx` 테스트로 7개 경로 단언)
  - 기존 Python 테스트 전부 통과 유지

## Work slices
- [ ] S1. Export·Status 화면 — completion criterion: 해당 Vitest 통과
- [ ] S2. 일괄 생성 흐름(진행·자동 채택·토스트·검토 필요·`중단됨`) — completion criterion: 배치 상태 머신 테스트 통과 (depends: S1)
- [ ] S3. 7개 라우트 연결 확인과 오류 UX — completion criterion: routes 테스트 통과 (depends: S2)
