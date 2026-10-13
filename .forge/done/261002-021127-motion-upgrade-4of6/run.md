# 실행 기록 — 움직임 개선 4/6: 프롬프트·참조 이미지 개선 (task #27)

## 한 일
- S1 방향 참조 단일 프레임화: `generation.direction_reference_image` — 대표 방향 채택 `frames/000.png` 1장을 512px 근방으로 확대(NEAREST)해 키 색 배경에 합성. `generation.json`의 참조 source는 `<unit>/frames/000.png`로 기록. 서버 `POST .../generate` 선행 조건도 `raw.png` → `frames/000.png`로 변경.
- S2 문구: walk/run에 "treadmill"(제자리) 줄, 앞/뒷모습(down/up)에 발 교차 금지 줄 추가. 프레임 8 이상(`MANY_FRAMES`)이면 `frames_many:` 가정 경고. `PROMPT_TEMPLATE_VERSION=action_prompt@3`, docs/04 갱신, 스냅샷 4개 재생성.
- S3 스튜디오: attempt 요약에 `prompt_version`(generation.json의 `prompt_template_version`) 추가, `attempt-prompt-version-<NNN>` 표시, Vitest 1건.

## 검증
- pytest 858 passed(4 skipped), Vitest 208 passed(+1), typecheck/build OK, e2e 11 passed.

## 주의 / 미검증
- walk/run "treadmill" 문구와 발 교차 금지는 sprite-gen의 *영상* 프롬프트 실측에서 가져온 것이라 *이미지* 생성에서의 효과는 미검증 [낮음].
- 계획의 "다리 지칭 단어 금지 규칙(validate_prompt)"은 구현하지 않음: 라이브러리 포즈 문구(예: walk 포즈)가 다리를 명시하므로 금지하면 기존 문구와 충돌. 문구만 개선.
- 실사용 확인: 실제 Codex로 `walk`(down/right)를 @2(git stash 전)와 @3로 각각 생성해 `attempt-prompt-version`과 QC-10~12 점수를 비교.
