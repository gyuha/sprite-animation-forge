# 실행 기록 — sprite-gen 동기화 5/11: 공격 머리 위 여유·앞/뒷모습 유지·손잡이 방향 (task #34)

## 한 일
- **머리 위 여유**: `attack`·`jump`(fx 제외)의 GRID RULES에 "셀 높이의 20%를 머리 위에 비워 둔다" 줄(`grid_headroom.txt`, `HEADROOM_PCT`). 옆 여백 규칙(8%/복구 시 15%)과 `validate_prompt`는 그대로 통과. plan 여백(px)은 바꾸지 않음 — 후처리가 bbox에 `fit` 배율로 맞추므로 여유는 *생성 쪽* 문제(근거는 docs/04 §11).
- **앞/뒷모습 유지**: 방향이 `down`/`up`이면(topdown·front·rear) CONSISTENCY RULES에 "3/4로 돌리지 말고 이 방향을 유지" 줄(`view_keep.txt`). 측면(`right`/`left`)은 줄 없음.
- **손잡이**: plan 선택 필드 `handed`(`none`|`left`|`right`, 없으면 none → 기존 plan JSON과 바이트 동일). 값이 있으면 좌우 미러를 끄고(`mirror: {}`, plan note) 왼쪽을 별도 unit으로 생성, `--mirror` 명시와 충돌하면 `invalid_params`. 프롬프트는 측면에서 "그 손이 보는 쪽에서 가까운/먼 팔"(오른쪽을 보는 측면은 캐릭터의 오른팔이 가까움 — 기존 camera 문구 "facing right ... right side visible"과 일치), 앞/뒷모습에서 "이미지의 어느 쪽"(정면이면 좌우 반전)을 말함(`handed.txt`). CLI `plan --handed`, 스키마, 서버 PlanCreate·PUT 검증, 계획 화면 "손잡이" 선택.
- **프롬프트 버전 `action_prompt@3` → `@4`** (템플릿 텍스트가 바뀌었으므로 docs/04 §1 규칙대로).
- docs/04 §11, docs/02, docs/14 영역 B 행 4개, OpenAPI 타입 재생성.

## 검증
- `sg_image` 42건(layout_guide 12 · headroom 8 · view_keep 6 · handed 16 — 파라미터화 포함). 전체 pytest 1010 passed, 기준선 ID 누락 0, Vitest 215(+2), e2e 12, typecheck OK.

## 계약과 다르게 한 것 (사유)
- 기준선 테스트 **기대값 변경 3곳**: 버전 문자열 `"action_prompt@3"` → `"@4"`(`test_prompt` 2곳, `test_codex_commands` 1곳). 버전을 올리지 않으면 텍스트가 바뀐 프롬프트의 추적이 깨진다(계획의 "버전 상승"). 테스트 ID(이름)는 그대로라 C1 통과.
- 스냅샷 4개 재생성 — diff는 헤더의 버전 줄 4개와 `idle_topdown_down/up`에 추가된 앞/뒷모습 유지 줄 2개뿐(`git diff`로 확인). 측면 걷기·`right`는 헤더만 바뀜.
- 계획 문구의 "공격 20%"는 `attack`·`jump`에 적용. `shoot`·`cast`는 근거 없이 넣지 않음.
- UI의 `handed`는 `PlanDraft`의 선택 필드(기본 none이면 요청에 안 실음) — 기존 Vitest의 정확한 요청 본문 단언을 건드리지 않기 위함.

## 학습 / 주의
- 손잡이 가까운/먼 팔 판정은 우리 camera 문구(오른쪽을 보는 측면은 "오른쪽 몸이 보임")와 일관되게 유도했지만 실제 Codex가 그 문장을 지키는지는 미검증 [낮음].
- 이미 만든 기존 캐릭터 plan에는 `handed`가 없으므로 영향 없음. 비대칭 캐릭터는 plan 화면에서 지정해야 효과가 있다.
