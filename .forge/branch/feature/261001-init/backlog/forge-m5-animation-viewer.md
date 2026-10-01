<!-- forge-slug: forge-m5-animation-viewer -->
<!-- task: 21 -->
<!-- tdd: off -->
# 애니메이션 뷰어: 캐릭터의 모든 액션·방향을 한 화면에서 재생

## Goal / Non-goals
- Goal: 사용자가 만들어진 캐릭터의 애니메이션을 화면에서 바로 볼 수 없다는 문제를 해결한다. 새 라우트 `/c/:cid/view`의 `Viewer` 페이지: 채택된 모든 unit(액션×방향)을 타일 격자로 동시에 재생(탑다운이면 행=액션, 열=down/up/right/left, 측면이면 액션별 타일), 공통 컨트롤(전체 재생/일시정지, 속도 0.5x/1x/2x, 배율 1x~4x, 배경 checker/dark/light/green), 타일 클릭 시 확대 dialog(큰 플레이어, 프레임 이동, fps), 단일 rAF 시계로 타일 다수를 부드럽게 구동, 프레임은 채택 결과 `/files/<cid>/<unit>/frames/NNN.png?v=…`(mirror `left`는 `<action>/left/frames`), loop/one-shot은 plan 값 따름, 미채택 unit은 "미채택" 플레이스홀더 + 스튜디오 링크. 진입 경로: Dashboard 카드의 "애니메이션 보기", 상단/캐릭터 내비, Export·Studio 화면의 링크.
- Non-goals: GIF 생성, 편집/재생성, Core 변경, 서버 신규 엔드포인트(기존 plan·status·files로 충분하면 추가하지 않는다).

## Source of truth
- Glossary terms: none
- Related ADRs: none (docs/09 §5 애니메이션 플레이어, §9.1 shadcn 규칙)
- Definition of Done:
  - `pnpm --dir webui/web typecheck && build && test` 통과, Vitest passed ≥ 160 (baseline 146; 신규 ≥ 14: 프레임 URL 생성(일반/mirror), plan→타일 배치(탑다운 행·열/측면), 미채택 플레이스홀더, 공유 시계 프레임 계산(loop/one-shot/속도 배율), 컨트롤 상태, 확대 dialog, 링크 존재 등)
  - `pnpm --dir webui/web e2e` passed ≥ 6 (baseline 4; 신규: 배치 생성 캐릭터의 뷰어에서 타일 수 == unit 수, 캔버스에 불투명 픽셀, `data-frame` 변화; 진입 링크들)
  - 실제 데이터 `sprites/green`(읽기 전용)으로 `/c/green/view` 타일 20개·불투명 픽셀·프레임 변화·콘솔 오류 0 (오케스트레이터 검사)
  - 기존 `uv run pytest -m "not live" -q` 750 passed 유지

## Work slices
- [ ] S1. `lib/viewer.ts`(프레임 URL·타일 배치·공유 시계 계산 순수 함수) + Vitest — completion criterion: 순수 로직 테스트 통과
- [ ] S2. `Viewer.tsx`(타일 격자·컨트롤·확대 dialog·미채택 플레이스홀더, data-testid `viewer-page viewer-tile-<unit> viewer-tile-missing-<unit> viewer-play-all viewer-speed-<x> viewer-scale-<n> viewer-bg-<name> viewer-zoom-dialog`; 타일 캔버스는 `data-frame`·`data-unit`·`data-painted` 노출) + 라우트 + 진입 링크(Dashboard 카드 `character-view-<id>`, 캐릭터 내비, Export·Studio 링크) — completion criterion: 컴포넌트 테스트 통과 (depends: S1)
- [ ] S3. Playwright 신규 테스트 2건 이상(재생 검증, 진입 링크) — completion criterion: e2e passed ≥ 6 (depends: S2)
