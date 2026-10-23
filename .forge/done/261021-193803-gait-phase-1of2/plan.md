<!-- forge-slug: gait-phase-1of2 -->
<!-- task: 41 -->
<!-- part: 1/2 -->
<!-- tdd: on -->
# 걷기 균등 위상 1/2: 걸음 위상 QC(QC-14)와 균등 위상 걷기 프롬프트

## 목표 / 비목표
- 목표: grid로 만든 걷기가 프레임마다 고르게 나아가지 않는다(위상 간격 불균등, 순서 뒤섞임, 팔·다리 박자 불일치). (1) 이를 결정적으로 재는 **QC-14 "걸음 위상"**을 추가해 나쁜 시트를 fail로 걸러 재생성·최선 시도 선택에 연결하고, (2) walk 6프레임 프롬프트를 **균등 위상** 자세 정의로 바꾼 뒤, (3) 실제 Codex로 5회 생성해 효과를 수치와 눈으로 확인한다.
- 근거(그릴링 중 실측, 2026-10-15):
  - 기존 걷기 8건의 다리 신호(`video_gait.leg_signal`). 사용자 눈 판정에서 자연스러운 것은 green up 1건뿐이었다(다리 신호 범위 0.022라 판독 불가 구간).
  - 부자연 7건의 모양 편차는 pink-2 0.83, pink up 0.91, pink down 0.80, pink right/002 0.60, green right 0.52, green down 0.51, pink right/001 0.49였다.
  - 처음 생각한 "반 주기 불일치" 지표는 pink down(0.20)·pink right/001(0.31)을 놓쳐 버렸다.
  - 프롬프트 결함: 기존 walk 순서 `contact → down → passing`은 위상 간격이 1/8·1/8·2/8로, passing→contact에서 두 배를 건너뛴다(`up` 누락).
- 비목표:
  - run 등 다른 액션의 문구·QC. run은 실측 표본이 0건이다.
  - walk 6프레임이 아닌 프레임 수. 일반 규칙이 이미 "evenly spaced poses"라고 말한다.
  - 자동 재정렬(D). 7건 × 120가지 순서를 전수 계산했지만 fail에서 벗어난 것이 0/7이었다. 원인이 순서가 아니라 그림 내용이고, 다리 신호로는 60°와 120°가 같은 값이라 구분할 수 없다. 그래서 제외한다.
  - 자세 가이드 이미지. 2/2 파트에서 다룬다.
  - docs/06에 QC-10~13 행이 원래부터 빠져 있는 문제. 기존 결함이며 이번에는 QC-14만 추가한다.
  - 이미 채택된 결과의 자동 재처리.

## 기준 문서(Source of truth)
- 용어집: 걸음 위상(gait phase)·균등 위상 — `.forge/CONTEXT.md`
- 관련 ADR: 없음
- QC-14 정의(합의):
  - 적용 대상: `walk` + loop만 적용하고, 다른 액션은 `skipped`(not_applicable)로 둔다.
  - 신호: `leg_signal(frames, view)`를 쓴다. view는 측면이 `side`, down/up이 `front`이다.
  - 판독 불가: 신호 변화가 기존 `MIN_SPREAD_CHANGE`(측면)·`MIN_LEG_RANGE`(정면) 미만이면 `skipped`(`no_gait`)로 처리한다.
  - 값 = 정규화한 신호 `(s−min)/(max−min)`와 이상 모양 사이 편차의 최댓값을, 순환 이동 N가지 중 가장 작은 것으로 취한다. 이상 모양은 측면이 `|cos(2πi/N)|`, 정면이 `|sin(2πi/N)|`를 같은 방식으로 정규화한 것이다(N=6이면 측면 `1,0,0,1,0,0`, 정면 `0,1,1,0,1,1`).
  - 등급: warn ≥ 0.30, fail ≥ 0.45.
  - fail이면 재생성 권장 코드 `gait_phase`를 붙인다(기존 일괄 생성 재시도와 `select_best_attempt` 점수에 그대로 연결된다).
- 프롬프트(합의 문구, `motion_library.txt`의 `[walk]`):
  ```
  Walk cycle with evenly timed steps: every frame moves the stride forward by the same amount (one sixth of the cycle). Each arm swings opposite to its leg. Body bobs slightly.
  1. contact: left foot forward, heel on the ground; right foot back on its toes; right arm forward, left arm back; legs at their widest
  2. down: weight settles onto the bent left leg, body lowest; right foot lifts off and starts swinging forward; legs half as wide as in frame 1; arms swinging back toward the sides
  3. up: right foot swings just past the left leg, off the ground; left leg straightens, body highest; legs half as wide as in frame 1; left arm slightly forward, right arm slightly back
  4. contact: frame 1 with left and right swapped (right foot forward, left arm forward)
  5. down: frame 2 with left and right swapped
  6. up: frame 3 with left and right swapped; it leads into frame 1 and is not the same pose as frame 1
  Frames 4-6 are frames 1-3 with left and right swapped, legs and arms both; they are not copies.
  ```
  - walk 전용 반복 줄: `Frame 6 leads into frame 1 one even step later, just as frame 3 leads into frame 4.`
  - 다른 loop 액션의 반복 줄은 바꾸지 않는다.
  - `gait_phase` 복구 문구: 균등 진행, 4~6번은 좌우를 바꾼 것, 6번은 1번과 다른 자세.
  - `PROMPT_TEMPLATE_VERSION`을 `action_prompt@4`에서 `@5`로 올린다.
- 완료 정의(Definition of Done):
  - TDD: 각 슬라이스의 실패 테스트를 먼저 작성하고 통과시킨다.
  - `uv run pytest -q -k gait_phase` passed ≥ 14 (사전 상태 2026-10-15: `1096 deselected`, 0건 — 순방향 검사). 다음을 단언해야 한다:
    - 합성 균등 위상 걷기(측면·정면)가 pass인지
    - 시작 프레임을 옮긴 균등 걷기가 pass인지(순환 불변)
    - f6 접지(pink-2 형태)와 정면 접지 연속(pink down 형태)이 fail인지
    - warn·fail 경계값의 바로 위·아래 등급
    - 다리 없는 몸과 신호 범위 미달이 `skipped`인지
    - run·idle이 `skipped`인지
    - fail일 때 `gait_phase` 권장이 붙는지
    - **회귀 eval**: 기록된 실측 다리 신호 7건(위 근거의 배열을 테스트에 그대로 넣음)이 모두 ≥ 0.45이고, green up 배열은 판독 불가인지
    - walk 프롬프트(측면 right)에 새 문구 3개(`one sixth of the cycle`, `not the same pose as frame 1`, `they are not copies`)가 있고 `passing:`이 없으며, 버전이 `action_prompt@5`인지
    - run 프롬프트가 변경 전과 바이트 단위로 같은지
  - `uv run pytest -m "not live" -q` 전부 통과 (사전 상태: 1089 passed, 4 skipped — 회귀 가드라서 미리 통과하는 것이 정상이다). 기존 테스트의 기대값은 약화하지 않는다. `walk_side` 스냅샷과 docs/04 §7 예시는 같이 갱신한다(`test_prompt_snapshot_walk_side_matches_docs_example`가 둘이 같은지 강제한다).
  - `uv run python sprite-animation-forge/tests/sync_matrix.py` 통과 (사전 상태: 통과 — 회귀 가드).
  - docs/06 §2 검사 표와 §3 적용 매트릭스에 QC-14 행을 넣고, `qc.py`의 `MATRIX`/적용 규칙과 **행 단위로 대조**한 결과를 run.md에 적는다. 이것은 회고 `forge-m1-qc`의 교훈이다(사전 상태: `grep -c "^| QC-14" docs/06-qc-and-recovery.md` → 0).
  - 웹 UI: `QC_NAMES['QC-14']`와 `REGENERATE_LABEL.gait_phase`를 추가하고 Vitest를 1건 이상 추가한다. `pnpm --dir webui/web test`(사전 상태: 215 passed)·`typecheck`(사전 상태: 통과)·`build`가 모두 통과해야 한다.
  - **실측(Codex 5회)**:
    - `sprites/pink-2`를 `sprites/pink-2-gait`로, `sprites/pink`를 `sprites/pink-gait`로 복사한다. 원본은 건드리지 않는다.
    - 생성 대상: `forge.py generate pink-2-gait walk` ×2, `generate pink-gait walk --direction right|up|down` 각 1회.
    - run.md 표에 시도마다 다음을 기록한다: QC-14 값·등급, 다리 신호 배열, 전체 QC 상태, 6프레임 GIF 경로.
    - 생성이 실패하면(Codex 오류) 그 사실과 오류 코드를 그대로 적는다.
  - **사람 확인(UAT)**: 사용자가 5건을 눈으로 자연/부자연 판정하고, 판정과 QC-14 값을 run.md에 같이 남긴다. 판정에 따른 처리는 다음과 같다.
    - 자연스러운데 QC-14가 fail이면 임계값 재보정이 필요하다는 사실을 기록하고, 2/2 파트 앞에 재보정 작업을 넣는다.
    - 부자연스러우면 A만으로 부족하다는 근거로 2/2 파트로 넘어간다.

## 작업 슬라이스
- [ ] S1. `qc_motion`에 걸음 위상 편차 함수(신호 배열 → 값/None, 프레임 → 값/None)와 `qc.py` QC-14(적용 규칙·임계값), qc-report 스키마 확인, `recovery.py` `gait_phase` 권장, 그리고 테스트 — 완료 기준: QC 쪽 `-k gait_phase` 테스트(실측 신호 eval 포함) 통과
- [ ] S2. `motion_library.txt` `[walk]` 교체, walk 전용 반복 줄, `recovery.txt`의 `gait_phase` 문구와 `RECOVERY_CODES`, 버전 `@5`, `walk_side` 스냅샷·docs/04 §4·§7 갱신 — 완료 기준: 프롬프트 쪽 `-k gait_phase` 테스트와 기존 `test_prompt` 통과 (depends: S1)
- [ ] S3. docs/06 QC-14 행(표·매트릭스) 및 MATRIX와의 행 대조, 웹 UI `QC_NAMES`·`REGENERATE_LABEL` + Vitest, 전체 회귀(pytest·Vitest·typecheck·build) — 완료 기준: 위 완료 정의의 회귀 명령이 모두 통과 (depends: S2)
- [ ] S4. 사본 캐릭터에서 Codex 5회 실측, run.md에 결과 표 작성 — 완료 기준: run.md에 5행(또는 실패 사유)이 있고 각 행에 QC-14 값·GIF 경로가 있다 (depends: S3)
