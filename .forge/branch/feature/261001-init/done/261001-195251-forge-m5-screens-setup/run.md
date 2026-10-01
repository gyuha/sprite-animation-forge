# RUN — M5-b: S1 대시보드 · S2 새 캐릭터 · S3 Identity · S4 플랜

서브에이전트 1개가 구현, 오케스트레이터가 DoD 재실행으로 확인. 브라우저/실서버 검증은 아직 없음(모의 fetch Vitest만) — M5-e E2E가 보강.

## 슬라이스 결과
- S1 Dashboard + Codex 미준비 배너 — ✅ as planned (QC 요약·idle 애니메이션 썸네일은 API 부재로 제외)
- S2 NewCharacter(DropZone, 탭 A/B) — ⚠ 탭 B 후보는 Job 완료 시 한 번에 표시(후보 목록 API 없음), facing select·붙여넣기·배경 제거 비교 제외
- S3 Identity(PaletteEditor)·Plan(번들·방향·mirror·키 색 경고) — ⚠ 커스텀 액션·액션별 방향 override·max_regenerations/자동 채택은 제외(M5-d에서 일괄 생성 쪽)

## DoD baseline → after
- typecheck/build exit 0, Vitest: 18 → 58 passed (신규 40, ≥10)
- 방향·mirror 컨트롤은 topdown에서만 노출, plan 요청 본문(POST: bundle/actions/set/cell/view/directions/mirror)에 반영 — 테스트 단언

## 판단·가정 (후속 task가 알아야 함)
- `api/mutations.ts`: useCreateCharacter, useUploadReference, useStartReferenceGenerate, useSelectReference, useStartIdentityAnalyze, useSaveIdentity, useCreatePlan, useSavePlan. `usePresets` 추가. `sse.ts`: identity_analyze 성공 시 identity 쿼리 무효화.
- plan 저장: plan 없음(GET 412) → POST, 있으면 전체 PUT(뷰 select는 plan 존재 후 비활성). POST는 기존 plan을 덮어쓰는 서버 동작을 UI가 회피.
- data-testid(Playwright가 사용): Dashboard `new-character-button codex-not-ready-banner character-card-<id>`, NewCharacter `tab-image tab-text dropzone dropzone-input new-character-id new-view create-from-image new-description new-count generate-candidates candidate-<attempt> candidate-proceed`, Identity `identity-analyze identity-save identity-field-<key>`, Plan `bundle-<id> action-check-<a> plan-view plan-cell direction-controls direction-<d> mirror-switch plan-estimate key-color-alert plan-save plan-continue` (페이지 파일 상단 주석에 전체 목록).
- **알려진 결함(M5-c에서 수정)**: `src/api/queries.ts`의 `Direction` 타입이 `'left'|'right'|'front'|'back'`인데 서버는 `down|up|right|left` → Studio에서 수정 필요. 백엔드 한계: `/api/characters` 카드에 QC/썸네일 없음, reference 후보 목록 API 없음(새로고침 시 탭 B 상태 유실).
