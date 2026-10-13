<!-- forge-slug: motion-upgrade-3of6 -->
<!-- task: 26 -->
<!-- part: 3/6 -->
<!-- tdd: on -->
# 움직임 개선 3/6: 움직임 품질 점수(QC)와 비전 심사

## Goal / Non-goals
- Goal: 결정적 움직임 지표를 QC 항목으로 추가한다 — 루프 이음새 비율(loop 액션: 마지막→첫 프레임 거리 ÷ 인접 프레임 평균 거리, 경고/실패 임계 문서화, 2.0 기준), 실루엣 드리프트(dHash 유사도 하한), 색 드리프트(RGB 히스토그램 교차 하한), 움직임 유무(인접 프레임 차이가 너무 작으면 정지 열 — idle/breathe는 적용 매트릭스로 완화). 실패 시 recovery 권장 조치(재생성 + 해당 프롬프트 힌트 코드)와 일괄 생성 재시도에 연결. 스튜디오에 "비전 심사" 버튼: 현재 attempt 프레임을 이어 붙인 contact sheet를 Codex(`codex exec -i`, read-only, 기존 provider 바이너리·락 규칙)에 보내 루프 연속성·다리 교차·정체성 유지를 JSON으로 판정받아 attempt에 `vision-review.json` 저장·QC 패널에 표시(점수에는 반영하지 않음, 자동 실행 안 함, Job으로 실행).
- Non-goals: 후보 자동 다중 생성, 프레임 조합 UI, QC-08 점수화.

## Source of truth
- Glossary terms: none
- Related ADRs: none (근거: sprite-gen qa/inspect·score·loop.py 지표 개념, qa-motion.md 비전 심사 — 재구현)
- Definition of Done:
  - TDD 진행
  - `uv run pytest -q -k "motion_qc or vision_review"` passed ≥ 12 (baseline 0 — 순방향): 각 지표 경계값(바로 위·아래), 합성 변형(정지 열·드리프트·이음새 불량)에서 해당 항목 fail, 적용 매트릭스, 권장 조치 매핑, 일괄 생성 재시도 연동, 가짜 codex로 비전 심사 Job → `vision-review.json` 스키마 검증·잘못된 JSON 응답 처리
  - qc-report 스키마 갱신, 기존 QC 테스트 유지(기존 항목 번호·의미 불변, 신규는 새 ID)
  - 스튜디오 "비전 심사" 버튼(`vision-review-button`)·결과 표시 Vitest ≥ 3, 전체 Vitest·e2e 통과
  - 실사용 확인 방법 기록(실제 walk에서 점수와 비전 심사 결과가 눈으로 본 문제와 맞는지)

## Work slices
- [ ] S1. 움직임 지표 4종 + 적용 매트릭스 + qc-report 스키마 — completion criterion: 지표 단위 테스트 통과
- [ ] S2. recovery·일괄 생성 재시도 연결 — completion criterion: 연동 테스트 통과 (depends: S1)
- [ ] S3. 비전 심사(Core·CLI `review`·API Job·스튜디오 버튼) — completion criterion: 가짜 codex 통합·Vitest 통과
