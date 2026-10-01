# RUN — M1-b: 측정 · 스케일 · 정렬 · process 조합

서브에이전트 1개가 구현, 오케스트레이터가 DoD 재실행으로 확인.

## 슬라이스 결과
- S1 `pipeline/measure.py`(Layout, measure_frame, weak/strict feet, x anchor 3종) — ✅ as planned
- S2 `pipeline/scale.py`(fit·preserve·overflow·resample, profile 없으면 fit 대체+경고) — ✅ as planned
- S3 `pipeline/align.py`(place_frame, compose_sheet) — ✅ as planned
- S4 `pipeline/process.py`(`process_sheet`, 출력 4종) — ✅ as planned

## DoD baseline → after
- `-k "measure or scale or align or process"`: 0 → 57 passed (≥25)
- 전체 `-m "not live"`: 130 → 184 passed
- baseline_jitter 정렬 후 feet=118±0.5, wide_attack fit이 칸 안, sheet.png 모서리 알파 0: 테스트가 단언 (통과)

## 판단·가정 (후속 task가 알아야 함)
- 공개 API: `Layout`, `measure_frame`→`Measure`, `ScaleProfile(norm_scale, raw_cell_height, …)`, `choose_scale`, `overflow_px`, `resample`, `place_frame`, `compose_sheet`, `ProcessParams`(기본 2x3·6프레임·128셀·margin 8/8/10), `process_sheet(raw_path, out_dir, params, profile)`→`ProcessResult(data, frames, sheet, clean, warnings)`.
- process.json: schema_version 1, raw/params/derived(frames[] 포함)/outputs(sha256)/warnings. 타임스탬프·절대 경로 없음(결정성).
- feet_y는 배타적 하단(스캔 행+1). 빈 칸은 예외 없이 blank 프레임 + `empty_frame:<i>` 경고. 오버플로는 자르지 않고 `overflow:<i>` 경고.
- `thin_below_feet` 테스트는 컴포넌트 필터 전 셀에서 측정(필터가 1px 칼끝을 이미 삭제하기 때문). 리샘플 후 재측정 feet는 ±1px, 계산된 anchor_out은 ±0.5px 단언.
