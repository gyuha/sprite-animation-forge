# RUN — M1-a: 배경 제거 · grid 분리 · 컴포넌트 필터

서브에이전트 1개가 구현, 오케스트레이터가 DoD 재실행으로 확인.

## 슬라이스 결과
- S1 `pipeline/chroma.py`(검증·배경 추정·알파 램프·despill·키 충돌·native alpha) — ✅ as planned
- S2 `pipeline/split.py`(이상적 경계·gutter 스냅·행 띠별 경계·빈 칸) — ✅ as planned
- S3 `pipeline/components.py`(largest/all, 잡티 제거) — ⚠ `detached_sword` 테스트는 cell 384px로 실행 (아래 판단 참고)

## DoD baseline → after
- `-k "chroma or split or components"`: 0 → 55 passed (≥25)
- 전체 `-m "not live"`: 75 → 130 passed
- model_like_bg 배경 거리·모서리 알파·magenta 잔여, despill/키 전환/native alpha, gutter ±6%, specks/detached_sword: 각각 테스트가 단언 (전부 통과)

## 판단·가정 (후속 task가 알아야 함)
- 공개 API: `validate_input`, `remove_background`→`ChromaResult(rgba, mode, key_color, bg_color, ...)`, `split_grid(alpha, rows, cols)`→`SplitResult`(row_boundaries, col_boundaries[행별], cells[CellRect(rect 배타 끝, gutter_missing, empty)]), `select_cells`, `crop`, `filter_components(rgba_cell, mode, merge_gap_px=None, min_area_px=16)`→`ComponentResult`. `PipelineError(code)`, `round_half_up`.
- gutter = 알파 정확히 0인 연속 라인, 스냅 창 = floor(6%), 스냅 위치 = gutter 중심(창 안으로 clamp).
- docs/05 §5의 `merge_gap_px = max(4, round(0.02×RH))`를 그대로 구현. 합성 `detached_sword`의 6px 간격은 256px 칸(gap 5)에서는 병합되지 않아, 테스트는 384px 칸(gap 8)에서 유지됨을 단언하고 gap=5 에서는 제거됨을 대조로 단언. 실제 raw 칸(~600px, gap 12~13)에는 영향 없음 — 문서 공식 변경이 아닌 픽스처 크기 선택.
- 키 충돌: #FF00FF·#00FF00 모두 프로필 색과 거리 ≤120이면 magenta 유지 + 경고.
