<!-- forge-slug: motion-upgrade-1of6 -->
<!-- task: 24 -->
<!-- part: 1/6 -->
<!-- tdd: on -->
# 움직임 개선 1/6: 정렬 방식 개선 (공통 배치 기본값, 지금 방식은 옵션)

## Goal / Non-goals
- Goal: 지금 정렬은 프레임마다 발 높이를 기준선에, 무게중심을 칸 중앙에 따로 맞춰서 걷기에서 몸이 미끄러지고 점프 궤적이 눌린다. 새 기본값 `align=register`: 상체(위쪽 약 65%) 알파 겹침이 최대가 되는 프레임 간 정수 이동량으로 액션 전체를 등록하고, 몸 중심의 선형 드리프트만 제거한 뒤 액션 전체에 공통 배치(스케일·기준선 오프셋 1회)를 적용한다. airborne 액션(jump·fall)은 세로 이동을 보존(기준선은 액션 첫 프레임 기준). 지금 방식은 `align=per_frame`으로 그대로 선택 가능. airborne 프롬프트의 "모든 칸에서 발바닥이 같은 기준선" 문장 제거(프롬프트 버전 올림). QC-03을 "발 접지 미끄러짐"(register에서는 접지 프레임들의 발 위치 흔들림, per_frame에서는 기존 정의) 지표로 의미 수정. 재처리 패널·CLI `--set align=…`·API process `set`에서 선택 가능.
- Non-goals: 생성 방식(method) 필드, 호흡 idle, 새 QC 점수 항목, 프롬프트의 다른 문구 변경, 이미 채택된 결과 자동 재처리.

## Source of truth
- Glossary terms: none (생성 방식은 다음 작업)
- Related ADRs: none (근거: aldegad/sprite-gen `register_row_frames` 상체 65% 등록, video-pipeline "--anchor feet는 선형 드리프트만 제거" — 아이디어만 재구현, 코드 복사 없음 / ADR-007 원칙)
- Definition of Done:
  - TDD: 각 슬라이스의 실패 테스트를 먼저 작성하고 통과시킨다
  - `uv run pytest -q -k "align and register"` passed ≥ 6 (baseline: 0건 — 순방향): 합성 `baseline_jitter`/걷기 다리 위상 시트에서 register가 상체 위치를 프레임 간 ±1px 이내로 유지하면서 다리 위상의 상하 움직임을 보존, 선형 드리프트 제거, jump 합성 시트에서 세로 궤적(최고점-최저점 차) 보존, per_frame 선택 시 기존 결과와 바이트 동일
  - 기본값이 register: `ProcessParams().align == "register"`, `process.json.params.align` 기록, 결정성(같은 입력 2회 sha256 동일) 유지
  - 기존 `uv run pytest -m "not live" -q` 751 passed 유지 — 기존 정렬 기대값 테스트는 `align=per_frame`을 명시하도록만 바꾸고 기대값은 약화하지 않는다
  - QC-03 의미 변경과 프롬프트 airborne 문장 제거가 테스트로 단언되고 프롬프트 스냅샷 갱신·`PROMPT_TEMPLATE_VERSION` 상승
  - 재처리 패널 align select(`reprocess-align`)와 Vitest ≥ 1, `pnpm --dir webui/web typecheck/build/test`·`e2e` 통과(Vitest 191·e2e 10 유지 이상)
  - 실사용 확인 방법을 run.md에 기록: `sprites/green` 사본에서 walk·attack을 register/per_frame으로 재처리해 뷰어에서 비교

## Work slices
- [ ] S1. `pipeline/align.py`에 register(상체 등록·선형 드리프트 제거·공통 배치)와 airborne 세로 보존 + `ProcessParams.align` + 테스트 — completion criterion: `-k "align and register"` ≥ 6 passed
- [ ] S2. QC-03 의미 수정, airborne 프롬프트 기준선 문장 제거(버전 상승·스냅샷) — completion criterion: 해당 qc·prompt 테스트 통과 (depends: S1)
- [ ] S3. CLI·API `set align`, 재처리 패널 select + 테스트, 전체 회귀 — completion criterion: 전체 pytest·Vitest·e2e 통과 (depends: S2)
