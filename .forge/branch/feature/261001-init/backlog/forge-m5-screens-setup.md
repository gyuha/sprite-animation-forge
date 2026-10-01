<!-- forge-slug: forge-m5-screens-setup -->
<!-- task: 17 -->
<!-- part: 5/8 -->
<!-- tdd: off -->
# M5-b: S1 대시보드 · S2 새 캐릭터 · S3 Identity · S4 플랜 (탑다운 방향 UI 포함)

## Goal / Non-goals
- Goal: docs/09 §4 S1~S4, §3.1·§3.2, §6 일부. `Dashboard`(캐릭터 카드·Codex 배지·미준비 배너), `NewCharacter`(탭 A 이미지 업로드 `DropZone` / 탭 B 텍스트→후보 생성, view·스타일 select), `Identity`(필드 편집, `PaletteEditor`, 분석 중 skeleton), `Plan`(번들 radio, 액션 체크, 액션 행 collapsible, 출력 cell select, 키 색 충돌 경고, **방향 선택·mirror 스위치(탑다운)**). docs의 화면 명세·문구를 따른다.
- Non-goals: 스튜디오(M5-c), 내보내기/상태/일괄 생성(M5-d).

## Source of truth
- Glossary terms: none
- Related ADRs: none (docs/09 §3-§4, §8)
- Definition of Done:
  - `pnpm --dir webui/web typecheck`·`build`·`test` 통과, Vitest passed ≥ 18 (누적; 신규 ≥ 10: DropZone 형식·크기 검증, 번들→액션 전개, 키 색 경고, 방향/mirror 토글이 plan 요청 본문에 반영, 폼 검증 등)
  - `src/pages/{Dashboard,NewCharacter,Identity,Plan}.tsx`와 `DropZone.tsx`·`PaletteEditor.tsx` 존재
  - 탑다운 view 선택 시 방향 선택·mirror 스위치가 보이고 side에서는 숨겨짐 (테스트가 단언)
  - 기존 Python 테스트 전부 통과 유지

## Work slices
- [ ] S1. Dashboard + Codex 미준비 배너 — completion criterion: 렌더·상태 테스트 통과
- [ ] S2. NewCharacter(DropZone, 탭 A/B) — completion criterion: 업로드 검증 테스트 통과 (depends: S1)
- [ ] S3. Identity(PaletteEditor)·Plan(번들·방향·mirror·키 색 경고) — completion criterion: plan 요청 본문 테스트 통과 (depends: S2)
