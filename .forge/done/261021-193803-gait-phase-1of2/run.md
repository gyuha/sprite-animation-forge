<!-- forge-slug: gait-phase-1of2 -->
# 실행 기록 — 걷기 균등 위상 1/2 (#41)

실행 방식: 슬라이스 4개가 직렬 의존이고 규모가 작아 워크플로 없이 메인 세션에서 직접 실행(TDD).

## 슬라이스 결과
- S1 QC-14(모양 편차·적용 규칙·임계값 0.30/0.45·`gait_phase` 권장·`workflow`가 방향으로 `gait_view` 전달) — ✅ 계획대로 (워크플로 연결 테스트는 변경 없이 red, 변경 후 green 확인)
- S2 walk 프롬프트 `action_prompt@5` — ⚠ 합의 문구의 위치 일부 이동(아래 2번)
- S3 docs/06·docs/04·references·웹 UI·전체 회귀 — ✅ 계획대로
- S4 Codex 5회 실측 — ⚠ 첫 시도 5회 전부 실패(아래 1번), 저장소 밖에서 재실행해 5/5 성공. **정면 이상 모양이 틀렸다는 증거 발견**(아래 3번)

## 완료 정의: 기준선 → 실행 후
- `uv run pytest -q -k gait_phase`: 0건 → **30 passed**
- `uv run pytest -m "not live" -q`: 1089 passed, 4 skipped → **1119 passed, 4 skipped** (기존 기대값은 약화하지 않음. 바뀐 것은 QC 항목 목록·매트릭스에 QC-14를 더한 것과 버전 문자열 `@4`→`@5`, walk 반복 줄 기대값)
- `sync_matrix.py`: 통과 → 통과 (회귀 가드)
- `grep -c "^| QC-14" docs/06-qc-and-recovery.md`: 0 → 2
- 웹 UI Vitest 215 → **216 passed**, typecheck 통과 → 통과, build 통과
- 실측: 5행 기록(아래 표)

## docs/06 매트릭스 ↔ `qc.py` 행 대조 (회고 forge-m1-qc 교훈)
| 프로필/액션 | `qc.py` | docs/06 §3 |
|---|---|---|
| locomotion walk | `apply` | walk만 적용 |
| locomotion idle | `ACTION_OVERRIDES` → `skip` | 미적용 |
| locomotion run | `ACTION_OVERRIDES` → `skip` | 미적용 |
| action·airborne·terminal·fx | `skip` | 미적용 |
일치. 추가로 `qc14()`는 `action != "walk"`이면 `not_applicable`(qc_profile=locomotion 사용자 액션 차단).

## 실측 (Codex 5회, `action_prompt@5`, 사본 캐릭터)
| 시도 | 시점 | 다리 신호 | QC-14 | 전체 QC | GIF |
|---|---|---|---|---|---|
| pink-2-gait walk 002 | 측면 | .514 .378 .423 .519 .382 .400 | **0.321 warn** | warn 92 | `sprites/pink-2-gait/walk/attempts/002/walk-check.gif` |
| pink-2-gait walk 003 | 측면 | .491 .356 .306 .574 .302 .385 | **0.307 warn** | warn 84 | `sprites/pink-2-gait/walk/attempts/003/walk-check.gif` |
| pink-gait walk/right 003 | 측면 | .532 .378 .360 .523 .342 .387 | **0.237 pass** | warn 92 | `sprites/pink-gait/walk/right/attempts/003/walk-check.gif` |
| pink-gait walk/up 002 | 후면 | .090 .082 .056 .090 .009 .065 | 0.898 fail | fail 75 | `sprites/pink-gait/walk/up/attempts/002/walk-check.gif` |
| pink-gait walk/down 002 | 정면 | .097 .009 .018 .100 .009 .009 | 1.000 fail | fail 75 | `sprites/pink-gait/walk/down/attempts/002/walk-check.gif` |

전체 5행 한눈에: `sprites/pink-2-gait/gait-check-contact.png` (행 순서 = 위 표).
비교 기준(이전 프롬프트 `@4`): 측면 0.49~0.83, 후면 0.91, 정면 0.51·0.80.

## 계획과 달라진 점
1. **Codex가 이 저장소의 forge 상태를 읽고 생성을 거부**(S4 첫 시도). Codex 이미지 provider는 `-C <attempt 폴더>`로 실행되는데, 사본을 `sprites/` 안에 두었더니 Codex 쪽 forge 플러그인이 `.forge/running.md`(이 실행의 진행 표시)를 보고 "진행 중인 task 41을 먼저 닫을까요?"라고 묻고 이미지 없이 끝났다(5회 모두 `image_gen_failed`/`no_image`, 각 1턴 소비). 사본을 저장소 밖 `/tmp/gait-sprites`에 만들어 재실행해 5/5 성공했고, 결과를 `sprites/`로 옮겼다. **사용자 실사용에도 해당**: 이 저장소에 forge 작업이 진행 중이면 grid 생성이 같은 이유로 실패할 수 있다.
2. **합의 문구 위치**: 라이브러리 `[walk]`의 설명 줄은 동영상 프롬프트(`build_video_prompt`)와 공유되고 프레임 수가 6이 아닐 때도 쓰인다. 그래서 설명 줄은 그대로 두고, 6프레임 전용 문장(`one sixth of the cycle`, `Each arm swings opposite to its leg`, `Frames 4-6 … not copies`, 반복 줄)을 walk 전용 반복 줄 `[loop_walk]`로 옮겼다. 포즈 6줄은 합의 그대로. 동영상 프롬프트는 바뀌지 않았다.
3. **QC-14 정면 이상 모양이 반대일 가능성 (중요)**. 계획은 정면 이상 모양을 `|sin|`(접지에서 두 발 높이가 같음)으로 정했다. 그런데 새 정면 걷기(5행)를 보면 접지 프레임(f1·f4)에서 카메라 쪽으로 내딛은 발이 화면에서 **더 낮아** 두 발 높이 차가 가장 크다. 즉 정면도 측면처럼 `|cos|`가 맞다. 두 가정으로 다시 계산하면:
   | 표본 | `|sin|`(현재) | `|cos|` |
   |---|---|---|
   | 새 정면 down | 1.00 | **0.10** |
   | 새 후면 up | 0.90 | 0.90 |
   | 이전 pink down(사용자 판정: 부자연) | 0.80 | 0.20 |
   | 이전 green down(부자연) | 0.51 | 0.51 |
   | 이전 pink up(부자연) | 0.91 | 0.91 |
   `|cos|`로 바꾸면 새 정면이 pass가 되지만 이전 pink down(부자연)도 pass가 된다. 어느 쪽이 맞는지는 사람의 눈 판정이 필요해 실행 중에 바꾸지 않았다.
4. 복구 문구 `gait_phase`를 프레임 수에 무관하게 썼다("second half … first half"). 합의안의 "frames 4-6"은 6프레임에서만 맞아서다.
5. 기존 결함 발견(손대지 않음): docs/06 §2·§3에 QC-10~13 행이 없고, `references/prompt-rules.md` 복구 표에 `loop_closure`가 없다.

## 사람 확인(UAT) — 2026-10-18
| 시도 | 눈 판정 | QC-14 |
|---|---|---|
| pink-2 측면 002 | 부자연 | 0.321 warn |
| pink-2 측면 003 | 부자연 | 0.307 warn |
| pink right 003 | **자연** | 0.237 pass |
| pink up 002 | 부자연 | 0.898 fail |
| pink down 002 | 부자연 | 1.000 fail |

- 결론: 프롬프트(A)는 일부만 효과가 있다(측면 0/4 → 1/3 자연, 정면·후면 0/2). 2/2(자세 가이드)로 넘어가는 근거가 된다.
- 정면 이상 모양: 정면 down이 부자연으로 판정되어 `|cos|`로 바꾸자는 가설(위 3번)은 **기각**한다. 현재 `|sin|`을 유지한다.
- 임계값: 0.31~0.32(부자연)는 warn에 그쳐 자동 재시도로 이어지지 않는다. fail을 0.30으로 내리는 안은 사용자가 이번에는 채택하지 않았다(표본 3건). 회고 후보로 남긴다.
