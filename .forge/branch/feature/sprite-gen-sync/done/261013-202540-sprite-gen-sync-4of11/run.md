# 실행 기록 — sprite-gen 동기화 4/11: 이미지 레이아웃 가이드와 안전 영역 (task #33)

## 한 일
- `layout_guide.py`(신규): 키 색 정사각 캔버스에 안전 영역 윤곽(`m%`~`100-m%`)·머리 선(`2m%`)·발 선(`100-2m%`)을 그린 결정적 RGB 이미지. `safe_area(margin_pct)`.
- `prompt.py`: `LAYOUT GUIDE` 블록(템플릿 `layout_guide.txt`)을 **정지 1장(`method=breathe`)** 프롬프트에 추가 — 안전 영역·머리 선·발 선을 %로 명시하고 가이드의 선·윤곽을 그리지 말라고 못 박음. 참조 역할 `layout_guide`(두 번째 이미지). 이미 참조가 2장이면(다중 방향의 비대표 방향) 가이드를 생략하고 `layout_guide_skipped` 경고, 프롬프트는 이전과 바이트 동일. `PromptResult.margin_pct`(가이드 이미지와 문장이 같은 여백 사용, `edge_touch`면 15).
- `generation.py`: 가이드를 임시 파일로 만들어 두 번째 참조로 첨부, `generation.json` 참조에 `layout-guide` 기록. 서버 `routes/generate.py`가 `layout_guide` 역할을 방향 참조로 오인하지 않게(`startswith("direction:")`) 수정 — 안 고치면 정지 생성이 `IndexError`.
- 프롬프트 버전: 가이드를 붙인 정지는 `still_prompt@1`, 그 외는 `action_prompt@3` 그대로. docs/04 §10, docs/14 영역 B 행 4개, 스냅샷 `idle_breathe_guide.txt` 신규.

## 검증
- `sg_image` 12건(`layout_guide` 12: Core 10 · 서버 2). 전체 pytest 980 passed, 기준선 ID 누락 0, Vitest 213, e2e 12. 기존 프롬프트 스냅샷은 하나도 바뀌지 않음(격자 프롬프트 불변).

## 계약과 다르게 한 것 (사유)
- 계획은 "`PROMPT_TEMPLATE_VERSION` 상승"이었으나 기준선 테스트 3곳이 `action_prompt@3`을 단언하므로(`test_prompt`·`test_codex_commands`) 전역 버전은 올리지 않고 가이드 정지 프롬프트에만 별도 버전 `still_prompt@1`을 붙였다. 격자 프롬프트 텍스트는 바뀌지 않았으므로 버전을 올릴 사유도 없다.
- **체크 강화(완화 아님)**: 이 작업 직후 C5가 #34의 기능 없이 개수(≥12)만으로 통과하는 허점이 드러나, C5·C6·C7에 하위 기능별 선택자(`layout_guide`·`headroom`·`view_keep`·`handed` 등)와 파일명 규칙을 추가하고 남은 계획서 DoD에 반영했다. 백로그 소진 전에는 미완 체크를 pending으로 기록한다.

## 학습 / 주의
- 개수 기준 체크는 "다른 기능의 테스트가 많아서" 통과할 수 있다 → 하위 기능별 선택자가 필요.
- 가이드가 실제 Codex 결과의 크기·위치 정확도를 높이는지는 미검증 [낮음] — 가이드 이미지와 문장이 올바르게 첨부되는지만 확인했다. 모델이 가이드 선을 결과에 그려 넣을 위험이 있어 프롬프트에 금지 문구를 넣었으나 실제 동작은 모른다.
