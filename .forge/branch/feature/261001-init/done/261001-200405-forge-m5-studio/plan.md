<!-- forge-slug: forge-m5-studio -->
<!-- task: 18 -->
<!-- part: 6/8 -->
<!-- tdd: off -->
# M5-c: S5 액션 스튜디오 (플레이어 · 오버레이 · QC · 권장 조치 · 재처리 · attempt 기록)

## Goal / Non-goals
- Goal: docs/09 §4 S5, §5, §6, §3.3, §8, docs/12 M5 3번. `Studio` 화면: 상단 액션 탭(+방향 탭), 보기 탭(원본+격자/배경 제거/프레임), `AnimationPlayer`(캔버스, fps·배율·배경·오버레이 토글, 프레임 타이밍), `GridOverlay`(raw 위 경계·bbox·anchor SVG, 좌표 변환), `CompareSlider`, `QcPanel`(QC ID tooltip), `RecommendationButtons`(권장 조치 → 재처리/재생성 실행), `ReprocessPanel`(slider 변경 후 응답으로 캐시 직접 갱신), `AttemptStrip`(채택 ✓·fail 채택 시 alert-dialog 확인), 프롬프트 dialog, 단축키(입력창 포커스 시 무시), Job SSE 완료 시 쿼리 무효화(docs/09 §9.3).
- Non-goals: 내보내기·상태·일괄 생성(M5-d), E2E(M5-e).

## Source of truth
- Glossary terms: none
- Related ADRs: none (docs/09 §4 S5, §5, §6, §9.3)
- Definition of Done:
  - `pnpm --dir webui/web typecheck`·`build`·`test` 통과, Vitest passed ≥ 30 (누적; 신규 ≥ 12: 플레이어 프레임 타이밍·루프/one-shot, GridOverlay 좌표 변환, 재처리 슬라이더 디바운스+요청 본문, 권장 조치→API 호출 매핑, fail 채택 확인 다이얼로그, 단축키 입력창 무시 등)
  - `src/pages/Studio.tsx`와 AnimationPlayer·GridOverlay·CompareSlider·QcPanel·RecommendationButtons·ReprocessPanel·AttemptStrip 존재
  - 방향이 2개 이상인 plan에서 방향 탭이 보이고 API 호출에 `?direction=`가 포함, mirror `left` 탭은 생성·재처리 버튼이 비활성(사유 tooltip) (테스트가 단언)
  - 기존 Python 테스트 전부 통과 유지

## Work slices
- [ ] S1. AnimationPlayer·GridOverlay·CompareSlider(순수 로직 Vitest 포함) — completion criterion: 플레이어·좌표 테스트 통과
- [ ] S2. QcPanel·RecommendationButtons·ReprocessPanel·AttemptStrip — completion criterion: 요청 본문·다이얼로그 테스트 통과 (depends: S1)
- [ ] S3. Studio 페이지 조립(액션/방향/보기 탭, 프롬프트 dialog, 단축키, SSE 무효화) — completion criterion: 방향 탭·단축키 테스트 통과 (depends: S2)
