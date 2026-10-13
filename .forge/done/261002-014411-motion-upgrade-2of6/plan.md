<!-- forge-slug: motion-upgrade-2of6 -->
<!-- task: 25 -->
<!-- part: 2/6 -->
<!-- tdd: on -->
# 움직임 개선 2/6: 생성 방식(method) 필드와 호흡 idle(`breathe`)

## Goal / Non-goals
- Goal: 액션마다 plan에 `method`(`grid` 기본·`breathe`·`video`)를 둔다(스키마·`plan.py` 기본값 grid·CLI `--set <action>.method=`·API plan POST/PUT·플랜 화면 액션 행의 "생성 방식" select). `video`는 이번엔 자리만: 선택 불가(UI 비활성+사유 "동영상 API가 연결되지 않았습니다", CLI/API는 `method_unavailable` 오류). `breathe`(idle 및 body 액션에 허용, 기본 권장은 idle): 생성은 정지 포즈 1장(1x1, 기존 Codex provider·프롬프트에 "single still pose" 변형), 후처리에서 결정적 호흡 변형으로 프레임을 만든다 — 목(가장 좁은 수평 구간)으로 머리와 몸통을 나누고 머리는 그대로, 몸통만 정수 행 매핑으로 미세 수직 스케일(호흡 1회 6프레임, 기본 1회, 진폭 파라미터), 선택적 눈 깜빡임(끝 근처, 이후 2프레임 이상 뜬 눈 — 눈 영역 감지 실패 시 깜빡임 생략+경고). 결과는 기존 attempt 구조(frames/sheet/process.json/qc-report)로 저장되어 QC·채택·뷰어·export가 그대로 동작.
- Non-goals: 동영상 생성, 새 QC 점수, 프롬프트의 다른 개선, 프레임 조합 UI.

## Source of truth
- Glossary terms: 생성 방식 (method) — `.forge/CONTEXT.md`
- Related ADRs: none (근거: sprite-gen `effects/breathe.py` 개념 — 정지 1장 + 목 경계 고정 머리 + 정수 행 매핑, 6프레임/호흡; 재구현)
- Definition of Done:
  - TDD 진행
  - `uv run pytest -q -k "method or breathe"` passed ≥ 12 (baseline: 0건 — 순방향; `method` 키워드가 기존 테스트에 걸리면 신규만 집계): 스키마 method enum, plan 기본 grid·override, video 선택 시 `method_unavailable`, breathe 결과 프레임 수(6×호흡 수)·머리 영역 픽셀이 모든 프레임에서 원본과 동일·몸통 높이가 정해진 진폭 안에서 변함·결정성, 목 감지 실패 시 안전한 대체(전체 균일 변형 금지가 아닌 경고+깜빡임 없이 진행 — 테스트로 동작 고정), 가짜 codex로 `generate --method breathe`/API generate 흐름 끝까지
  - 플랜 화면 method select(`action-method-<a>`, video 옵션 비활성 사유 tooltip) Vitest ≥ 3, e2e ≥ 1(breathe idle 생성→채택→뷰어 재생)
  - 기존 테스트 전부 유지(grid 기본이라 기존 동작 불변), typecheck/build 통과
  - 실사용 확인 방법을 run.md에 기록(실제 Codex로 idle을 grid/breathe 각각 생성해 뷰어 비교)

## Work slices
- [ ] S1. method 필드(스키마·plan·CLI·API·검증·video 비활성) + 테스트 — completion criterion: method 테스트 통과
- [ ] S2. `effects/breathe.py`(목 감지·호흡 변형·깜빡임) + 테스트 — completion criterion: breathe 단위 테스트 통과
- [ ] S3. breathe 생성 경로(정지 1장 프롬프트·provider 호출·attempt 저장·process 연결) — completion criterion: 가짜 codex 통합 테스트 통과 (depends: S1, S2)
- [ ] S4. 플랜 화면 select + e2e — completion criterion: Vitest·e2e 통과 (depends: S3)
