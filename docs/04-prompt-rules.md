# 04. 프롬프트 규칙

## 1. 원칙

- **프롬프트는 코드가 조립한다.** Prompt Generator(`sprite_forge.prompt`)는 profile, plan, action, 선택적 추가 지시, 선택적 복구 코드를 받아 항상 같은 텍스트를 만든다(결정적). Agent나 사용자가 프롬프트 전체를 손으로 쓰지 않는다.
- **이미지 프롬프트는 영어로 쓴다.** 사용자가 한국어로 준 추가 지시는 그대로 `ADDITIONAL DIRECTION` 블록에 넣는다(모델이 이해함). 번역하지 않는다. 번역하면 결정성이 깨지기 때문이다.
- **프롬프트(prompt)와 지시문(instruction)을 구분한다.** 이 문서는 이미지 모델에 가는 프롬프트만 다룬다. Codex 에이전트에 주는 지시문은 [03](03-codex-image-provider.md) §5에 있다.
- 템플릿은 `sprite_forge/prompt_templates/*.txt`에 두고, 파일 내용이 바뀌면 버전(`action_prompt@N`)을 올린다. 버전은 `generation.json`에 기록한다.

---

## 2. 블록 구조

PRD §12 구조에 선택 블록 두 개(추가 지시, 복구)를 끼워 넣었다. **어겨서는 안 되는 규칙(일관성·grid·배경)을 마지막에 둔다.** 사용자 추가 지시가 grid나 배경 규칙을 덮어쓰지 못하게 하기 위해서다. 비어 있는 필드와 블록은 출력하지 않는다.

```
HEADER → REFERENCE IDENTITY → ART STYLE → CAMERA → ACTION(+FRAME SEQUENCE)
      → [ADDITIONAL DIRECTION] → [RECOVERY] → CONSISTENCY RULES → GRID RULES → BACKGROUND RULE → FOOTER
```

---

## 3. 블록 템플릿

### 3.1 HEADER

```text
Create a {rows}x{cols} sprite animation grid of a 2D game character: {action_title}, {frames} frames.
```

### 3.2 REFERENCE IDENTITY

`character-profile.json`의 필드로 채운다. reference 이미지가 첨부되지 않은 경우(Case B의 canonical 생성 단계)에는 이 블록 대신 캐릭터 설명을 쓴다.

```text
REFERENCE IDENTITY
Same character as the attached reference image (Image 1). Preserve exactly:
- silhouette: {silhouette}
- body proportions: {body_ratio}; head-to-body ratio: {head_ratio}
- hair: {hair}
- face: {face}; eyes: {eyes}
- clothing: {clothing}
- colors: primary {primary_colors}; secondary {secondary_colors}
- weapon: {weapon}
- accessories: {accessories}
- outline: {outline_style}; shading: {shading_style}
Only pose, limb position, body lean, facial expression, weapon motion and secondary motion (hair, cloth) may change.
Do not redesign, add, or remove any part of the character.
```

마지막 두 줄이 PRD §8의 "변경 가능한 것은 pose, limb position, body lean, facial expression, weapon motion, secondary motion뿐"을 강제한다.

### 3.3 ART STYLE

| `art_style` | 문구 |
|---|---|
| `project_native` / `auto`(reference 있음) | `Match the art style, line weight, and shading of the reference image exactly.` |
| `pixel_art` | `Crisp pixel art sprite, limited palette, hard pixel edges, no anti-aliasing, no blur, 1px dark outline.` |
| `retro_pixel` | `16-bit SNES-era pixel art sprite, limited palette, hard pixel edges, no anti-aliasing.` |
| `pixel_inspired` | `Pixel-art inspired 2D sprite, chunky readable shapes, clean edges, simple shading.` |
| `clean_hd` | `Clean HD 2D game sprite, crisp linework, cel shading, flat colors.` |

### 3.4 CAMERA

| view | facing 기본값 | 문구 |
|---|---|---|
| `side` | right | `Strict side view (profile), character facing right. Orthographic, no perspective.` |
| `topdown` | down | `Top-down RPG view from about 45 degrees above, character facing down toward the viewer.` |
| `3/4` | down-right | `Three-quarter view, character facing down-right.` |
| `front` | camera | `Front view, character facing the viewer.` |
| `rear` | away | `Rear view, character facing away from the viewer.` |

**방향이 여러 개인 plan**(탑다운 4방향, [02](02-skill-spec.md) §8.1)에서는 위 표의 view 문구 대신 unit의 방향에 맞는 문구를 CAMERA에 쓴다. view가 `topdown`일 때의 카메라 문구는 그대로 두고 facing 문장만 바뀐다.

| direction | facing 문장 |
|---|---|
| `down` | `character facing down toward the viewer. The front of the body, face and chest are visible.` |
| `up` | `character facing up, away from the viewer. Only the back of the head, back, and rear of the clothing are visible; the face is not visible.` |
| `right` | `character facing right, profile. Only the right side of the body is visible.` |
| `left` (`mirror={}`일 때만) | `character facing left, profile. Only the left side of the body is visible.` |

대표 방향이 아닌 unit에는 CAMERA 바로 뒤에 `DIRECTION REFERENCE` 블록을 넣고, 대표 방향의 **채택 결과 프레임 1장**(`frames/000.png`을 키 색 배경에 얹어 ~512px로 키운 것)을 추가 reference로 첨부한다. 포즈가 여러 개 담긴 sheet를 참조로 주면 방향 고정이 흐려진다는 sprite-gen의 실측을 따랐다.

```text
DIRECTION REFERENCE
- The second attached image shows one single pose of the same character from another direction.
- Keep the identical proportions, clothing, colors, equipment, and art style.
- Redraw only what the new facing direction reveals (for example the back of the cloak or the side profile). Do not redesign the character.
```

모션 라이브러리(§4)의 "front/back leg", "toward the front"는 화면 좌우가 아니라 **캐릭터가 향한 방향 기준**이다. 이를 ACTION 블록 첫머리에서 한 줄(`Describe all motion relative to the direction the character is facing.`)로 명시한다. `up`/`down`에서는 보행 시 다리가 화면의 위아래로 교차하는 형태가 되며, 이는 모델이 해석한다.

### 3.5 ACTION

모션 라이브러리(§4)의 문구를 넣는다. 모든 body 액션에 `Animate in place: the character does not travel across the cell.`를 붙인다. 게임에서 이동은 코드가 담당하기 때문이다.

```text
ACTION
{action_description}
Frame sequence:
1. {pose_1}
2. {pose_2}
...
{loop_line}
Animate in place: the character does not travel across the cell.
```

`walk`·`run`에는 `Animate in place` 뒤에 한 줄을 더 붙인다: `Show the {action} as if on a treadmill: the body stays in the same place in every cell, only the steps and the arm swing change.` 방향이 `down`·`up`(정면·후면)이면 `Seen from this angle, the steps pass beside each other under the body; the feet never cross.`도 붙인다. (sprite-gen의 동영상 프롬프트 실측 요령을 이미지 프롬프트에 의역해 옮긴 것이며, 이미지 생성에서 실제로 효과가 있는지는 실제 Codex로 비교해 확인해야 한다.)

`loop_line`은 loop 액션이면 `The last frame must flow seamlessly back into frame 1.`, 아니면 `This is a one-shot animation; frame {n} is the final pose.`이다. 단, 라이브러리 포즈를 쓰는 6프레임 walk는 §4의 walk 전용 3줄을 쓴다.

### 3.6 ADDITIONAL DIRECTION (선택)

Web UI의 "추가 지시" 입력이나 `--extra` 값을 그대로 넣는다. 최대 500자.

```text
ADDITIONAL DIRECTION
{extra}
```

### 3.7 RECOVERY (선택)

`--recovery <code>`로 지정한 복구 문구(§6)를 넣는다. 여러 개를 줄 수 있다.

### 3.8 CONSISTENCY RULES

```text
CONSISTENCY RULES
- Identical character scale and camera distance in every cell.
- The soles of the feet sit on the same horizontal baseline in every cell of a row.
- Same facing direction ({facing}) in every cell. (`{facing}`는 unit의 방향: 방향이 여러 개인 plan에서는 `down`/`up`/`right`/`left`)
- Full body visible in every cell. Nothing cropped.
```

### 3.9 GRID RULES

`margin_pct` 기본값은 8이고, 복구 코드 `edge_touch`가 붙으면 15로 올린다.

```text
GRID RULES
- {rows} rows x {cols} columns = {cells} equal cells. Frames read left-to-right, top-to-bottom.
- Exactly one complete character per cell.
- Leave at least {margin_pct}% empty background margin on every side of every cell.
- No part of the character, weapon, or effect may cross into another cell.
- No grid lines, borders, separators, labels, or numbers.
{if empty_cells}- Use only the first {frames} cells. Leave the last {empty_cells} cell(s) completely empty (background only).{/if}
```

### 3.10 BACKGROUND RULE

```text
BACKGROUND RULE
- Fill the entire background with flat, solid {key_name} {key_hex}.
- No gradient, texture, vignette, floor, ground line, drop shadow, or cast shadow.
- Do not use {key_name} or similar hues anywhere on the character.
```

`key_name`은 `#FF00FF` → `magenta`, `#00FF00` → `pure green`.

### 3.11 FOOTER

```text
No text. No watermark. No UI.
```

---

## 4. 모션 라이브러리

기본 프레임 수(02 §5.1)에 대한 포즈 목록이다. 사용자가 프레임 수를 바꾸면 포즈 목록 대신 일반 규칙을 쓴다.

- loop 액션: `{frames} evenly spaced poses covering one full {action} cycle.`
- one-shot 액션: `{frames} evenly spaced poses from {start_pose} to {end_pose}.` (`start_pose`/`end_pose`는 아래 표의 첫·마지막 포즈)

### idle — 4 frames, loop

`Idle breathing animation. Subtle motion only; the silhouette barely changes.`

1. neutral stance, weight centered
2. inhale: chest and shoulders rise very slightly
3. top of the breath; hair and cloth settle
4. exhale, returning toward frame 1

### walk — 6 frames, loop

`Walk cycle. Arms swing opposite to the legs. Body bobs slightly.`

1. contact: left foot forward, heel on the ground; right foot back on its toes; right arm forward, left arm back; legs at their widest
2. down: weight settles onto the bent left leg, body lowest; right foot lifts off and starts swinging forward; legs half as wide as in frame 1; arms swinging back toward the sides
3. up: right foot swings just past the left leg, off the ground; left leg straightens, body highest; legs half as wide as in frame 1; left arm slightly forward, right arm slightly back
4. contact: frame 1 with left and right swapped (right foot forward, left arm forward)
5. down: frame 2 with left and right swapped
6. up: frame 3 with left and right swapped; it leads into frame 1 and is not the same pose as frame 1

걷기는 **균등 위상**(`.forge/CONTEXT.md`)으로 정의한다. 6프레임이 각각 1/6 주기씩 나아가도록 2번은 60°(down), 3번은 120°(up) 자세다. 예전 순서 `contact → down → passing`은 고전 걷기의 `up`을 빼서 위상 간격이 1/8·1/8·2/8이 되었고, passing에서 다음 contact로 두 배를 건너뛰었다. 다리는 화면 앞뒤가 아니라 **캐릭터 자신의 left/right**로 부른다. 측면·정면·후면에서 같은 문구로 통하고, 4~6번이 1~3번의 복사가 아니라는 것을 말로 강제하기 위해서다. 이 포즈 목록을 쓸 때(walk, 6프레임, `poses` 지정 없음)는 반복 줄도 walk 전용 3줄(`action_loop_line.txt [loop_walk]`)로 바뀐다. 결과는 QC-14(docs/06)가 잰다.

### run — 6 frames, loop

`Run cycle. Body leans forward about 10-15 degrees. Strong arm swing.`

1. contact: front foot strikes the ground under the body
2. push-off: back leg drives, body low
3. flight: both feet off the ground, legs spread
4. contact (opposite leg)
5. push-off (opposite leg)
6. flight (opposite legs)

### attack — 6 frames, one-shot (근접 무기)

`Melee attack with the {weapon}. Feet stay planted.`

1. ready stance, weapon held
2. anticipation: wind up, weapon pulled back
3. swing: weapon moving fast toward the front
4. impact: weapon fully extended toward the front
5. follow-through
6. recovery: returning to the ready stance

### shoot — 4 frames, one-shot

`Ranged attack with the {weapon}. No muzzle flash or projectile in this sheet.`

1. aim
2. fire: small recoil
3. recoil recovery
4. settle back to aim

### cast — 6 frames, one-shot

`Spell cast. No large magic effects in this sheet; hands may glow faintly.`

1. ready stance
2. gather: hands draw in toward the chest
3. raise: arms lift
4. channel: peak pose
5. release: hands thrust forward
6. recover

### jump — 4 frames, one-shot

`Jump take-off, animated in place.`

1. crouch: anticipation, knees bent
2. take-off: legs extending, arms swinging up
3. rising: knees tucked
4. apex: body stretched, legs slightly bent

### fall — 2 frames, loop

`Falling while airborne, animated in place.`

1. arms raised, legs slightly bent, cloth fluttering up
2. same pose, cloth and hair in a different flutter position

### hurt — 4 frames, one-shot

`Hit reaction from the front.`

1. flinch at the moment of the hit
2. maximum recoil, leaning back
3. recovering balance
4. back to a guarded stance

### death — 8 frames, one-shot

`Death animation, falling backward. The final frame lies on the ground.`

1. hit
2. stagger backward
3. knees buckle
4. falling backward
5. hitting the ground
6. small bounce
7. settling
8. lying still

---

## 5. Case B: Canonical Reference 프롬프트

텍스트만 주어진 경우 먼저 기준 캐릭터 1장을 만든다. 생성 결과는 1x1 grid로 보고 같은 크로마키 파이프라인을 거쳐 `reference/character.png`가 된다. 후보를 여러 장 원하면(`--count 2..4`) 같은 프롬프트로 각각 별도 호출한다.

```text
Create a single full-body 2D game character for use as a sprite reference.
Character: {description}
{art_style_line}
{camera_line}
Neutral standing pose, arms relaxed, any weapon held naturally at the side.
The character is centered and fills about 75% of the image height, with empty margin on every side.
Full body visible, nothing cropped.
Fill the entire background with flat, solid magenta #FF00FF. No gradient, floor, or shadow.
Do not use magenta or similar hues anywhere on the character.
No text. No watermark.
```

---

## 6. 복구 문구

[06-qc-and-recovery.md](06-qc-and-recovery.md)의 recovery가 `regenerate`를 권장할 때 붙이는 코드와 문구다.

| 코드 | 원인 QC | 추가 문구 | 파라미터 변경 |
|---|---|---|---|
| `edge_touch` | QC-01 | `The previous attempt crossed cell borders. Keep a wide empty margin around the character in every cell.` | `margin_pct` 8 → 15 |
| `scale_drift` | QC-02 | `The previous attempt changed the character size between cells. Draw the character at exactly the same size in every cell; the top of the head and the soles of the feet line up across each row.` | — |
| `character_small` | QC-07 | `Keep the body the same size as in the reference image. The weapon may extend toward the cell edge but the body must not shrink.` | 해당 액션 `scale_strategy=preserve` |
| `fx_in_body` | QC-01/02 (FX 원인 추정 시) | `Body and weapon only. No slash trails, motion blur, sparks, magic effects, projectiles, or impact effects.` | — |
| `empty_frame` | QC-05 | `Every one of the {frames} used cells must contain the character.` | — |
| `duplicate_frames` | QC-06 | `Each frame must show a clearly different pose following the frame sequence.` | — |
| `bg_mismatch` | QC-09 | `The background must be one flat solid {key_name} {key_hex} across the whole image.` | — |
| `identity_drift` | (사용자 수동) | `The previous attempt drifted from the reference design. Match the reference exactly, especially: {fields}.` | — |

---

## 7. 조립 예시 (walk)

T2 실측에 쓴 캐릭터(빨간 후드 기사)를 가정해 profile 값을 채운 예시다. profile의 색상 hex 값은 설명용이며 실측값이 아니다.

```text
Create a 2x3 sprite animation grid of a 2D game character: walk cycle, 6 frames.

REFERENCE IDENTITY
Same character as the attached reference image (Image 1). Preserve exactly:
- silhouette: small chibi knight with a tall pointed hood and a long tattered cape
- body proportions: short and stocky; head-to-body ratio: about 1:2.5
- face: hidden by a steel visor helmet with three vertical slits
- clothing: red pointed hood, red scarf-cape, steel plate armor, beige tunic with red stripes, brown belt with pouch
- colors: primary #C8281E, #9A9CA0; secondary #E8D2A8, #6B3F1F
- weapon: sheathed sword with a gold pommel, worn on the back
- outline: dark brown outline; shading: soft painted cel shading
Only pose, limb position, body lean, facial expression, weapon motion and secondary motion (hair, cloth) may change.
Do not redesign, add, or remove any part of the character.

Match the art style, line weight, and shading of the reference image exactly.

Strict side view (profile), character facing right. Orthographic, no perspective.

GAIT GUIDE
- The second attached image is a gait guide, not a character: a flat magenta #FF00FF sheet laid out like this grid, with one gray stick figure per cell showing the pose of that frame.
- In every stick figure the dark gray arm and leg are the character's left arm and leg, the light gray ones the right arm and leg.
- Give the character in each cell the same leg and arm positions as the stick figure in the same cell; keep the character's own design and proportions.
- Never draw the stick figures, their gray lines or the guide's colors in the result.

ACTION
Walk cycle. Arms swing opposite to the legs. Body bobs slightly.
Frame sequence:
1. contact: left foot forward, heel on the ground; right foot back on its toes; right arm forward, left arm back; legs at their widest
2. down: weight settles onto the bent left leg, body lowest; right foot lifts off and starts swinging forward; legs half as wide as in frame 1; arms swinging back toward the sides
3. up: right foot swings just past the left leg, off the ground; left leg straightens, body highest; legs half as wide as in frame 1; left arm slightly forward, right arm slightly back
4. contact: frame 1 with left and right swapped (right foot forward, left arm forward)
5. down: frame 2 with left and right swapped
6. up: frame 3 with left and right swapped; it leads into frame 1 and is not the same pose as frame 1
Every frame moves the stride forward by the same amount: one sixth of the cycle. Each arm swings opposite to its leg.
Frames 4-6 are frames 1-3 with left and right swapped, legs and arms both; they are not copies.
Frame 6 leads into frame 1 one even step later, just as frame 3 leads into frame 4.
Animate in place: the character does not travel across the cell.
Show the walk as if on a treadmill: the body stays in the same place in every cell, only the steps and the arm swing change.

CONSISTENCY RULES
- Identical character scale and camera distance in every cell.
- The soles of the feet sit on the same horizontal baseline in every cell of a row.
- Same facing direction (right) in every cell.
- Full body visible in every cell. Nothing cropped.

GRID RULES
- 2 rows x 3 columns = 6 equal cells. Frames read left-to-right, top-to-bottom.
- Exactly one complete character per cell.
- Leave at least 8% empty background margin on every side of every cell.
- No part of the character, weapon, or effect may cross into another cell.
- No grid lines, borders, separators, labels, or numbers.

BACKGROUND RULE
- Fill the entire background with flat, solid magenta #FF00FF.
- No gradient, texture, vignette, floor, ground line, drop shadow, or cast shadow.
- Do not use magenta or similar hues anywhere on the character.

No text. No watermark. No UI.
```

---

## 8. 검증 규칙

Prompt Generator 단위 테스트는 다음을 보장한다.

- 같은 입력이면 바이트 단위로 같은 출력(결정성)
- 빈 profile 필드는 줄 자체가 빠진다(`- hair: ` 같은 빈 줄 없음)
- `ADDITIONAL DIRECTION`은 항상 `CONSISTENCY RULES`보다 앞에 온다
- `frames < rows × cols`면 빈 칸 규칙이 들어간다
- 복구 코드 `edge_touch`면 margin 문구가 15%가 된다
- 전체 길이 6,000자 이하

---

## 9. 동영상 방식(`method=video`) 프롬프트

동영상 방식은 격자 시트 프롬프트(§3)를 쓰지 않는다. 동영상 모델은 **첫 프레임 이미지**(키 색 캔버스에 캐릭터를 가운데 약 60% 높이로 배치한 `first-frame.png`)를 움직이므로, 프롬프트에는 동작·반복·배경 규칙만 들어간다. 생성기는 `prompt.build_video_prompt`, 템플릿은 `prompt_templates/video.txt`·`video_loop_line.txt`, 버전은 `video_prompt@2`(`generation.json`의 `prompt_template_version`)이다.

```
Animate this exact character in place: <title>.
<motion description (MOTION_LIBRARY 또는 plan의 motion)>
<loop 줄: 같은 포즈로 끝나는 이음새 없는 반복 | 한 번 수행 후 시작 포즈로 복귀>
정지 카메라(줌·팬·컷 없음), 캐릭터는 제자리, 키 색 배경은 모든 프레임에서 평평하게 유지, 디자인·색·비율·화풍은 첫 프레임과 동일
[ADDITIONAL DIRECTION <extra>]
```

- `idle`과 one-shot 액션은 마지막 프레임도 첫 프레임으로 고정해 요청한다(provider가 지원하는 경우). walk/run 같은 반복 액션은 고정하지 않고 주기 검출로 이음새를 고른다.
- 방향이 둘 이상인 plan에서는 쓸 수 없다(`invalid_params`): 클립은 첫 프레임이 향한 방향을 바꾸지 못한다.
- 클립 → `raw.png` 변환 규칙(주기·구간 선택, N프레임 축소, 배경 정규화)은 `video_loop.py`·`video_sprite.py` 모듈 docstring에 있다. 변환 결과 시트는 기존 파이프라인(§5 docs/05)을 그대로 거친다.

---

## 10. 레이아웃 가이드와 안전 영역 (정지 1장 생성)

`method=breathe`처럼 **정지 1장**을 만들 때는 두 번째 참조 이미지로 레이아웃 가이드를 붙인다(`layout_guide.make_layout_guide`). 키 색 정사각 캔버스에 (1) 안전 영역 윤곽(가로·세로 `m%`~`100-m%`), (2) 머리 선(위에서 `2m%`), (3) 발 선(위에서 `100-2m%`)을 그린 이미지다. `m`은 프롬프트의 여백 수치와 같다(기본 8, `edge_touch` 복구 시 15). 프롬프트에는 같은 수치를 문장으로 적고(`LAYOUT GUIDE` 블록: "second attached image is a layout guide ... 8% to 92% ... 16% from the top ... 84% from the top"), 가이드의 선과 윤곽을 결과에 그리지 말라고 못 박는다.

- 참조 이미지는 최대 2장이므로 이미 2장이 필요한 정지(다중 방향 플랜의 비대표 방향)에는 가이드를 붙이지 않고 `layout_guide_skipped` 경고를 낸다. 이때 프롬프트는 이전과 바이트 동일하다.
- 가이드를 붙인 정지 프롬프트의 버전은 `still_prompt@1`, 그 외는 `action_prompt@5`이다(`generation.json`의 `prompt_template_version`).
- `generation.json`의 참조에는 `layout-guide`가 기록되고, attempt 폴더의 `ref-02.png`가 그 이미지다.

### 10.1 자세 가이드 (측면 6프레임 걷기)

라이브러리 포즈를 쓰는 **6프레임 walk**(`grid`, `poses` 지정 없음)를 **측면(right·left)**으로 만들 때는 두 번째 참조 이미지로 **자세 가이드**(`.forge/CONTEXT.md`)를 붙인다(`gait_guide.make_gait_guide`). 격자와 같은 칸 배치(칸당 256px)의 키 색 시트에, 칸마다 그 프레임의 균등 위상 자세를 막대 인형으로 그린다. 1번은 왼발이 앞인 접지, 4번은 좌우를 바꾼 접지이고, 팔은 같은 쪽 다리와 반대로 흔든다. 캐릭터의 **왼쪽 팔다리는 짙은 회색, 오른쪽은 옅은 회색**, 머리·몸통은 중간 회색이며, 안티앨리어싱 없이 이 세 회색과 키 색만 쓴다. 몸 높이는 레이아웃 가이드의 머리 선·발 선(위에서 16%·84%)을 따른다. 왼쪽을 보는 방향은 칸마다 좌우 반전한다.

- 흔드는 다리는 무릎을 굽히지 않고 **발만 살짝 든다**. 정강이를 굽히면 발이 옆으로 움직여 다리 폭이 `|cos|` 모양에서 벗어나고, 가이드 자신이 QC-14 0.31을 받는다. 지금 그림은 QC-14 < 0.1(테스트로 고정).
- 프롬프트에는 `GAIT GUIDE` 블록(레이아웃 가이드 자리)을 넣어 칸별 자세만 따르고 막대 인형·회색 선·가이드 색을 결과에 그리지 말라고 못 박는다.
- 참조가 이미 2장인 경우(다중 방향 플랜의 비대표 측면 방향)는 붙이지 않고 `gait_guide_skipped` 경고를 낸다. 프롬프트는 `action_prompt@5`와 바이트 동일하다. 정면·후면 걷기와 다른 액션에는 붙이지 않는다(경고 없음).
- 가이드를 붙인 프롬프트의 버전은 `gait_prompt@1`, `generation.json`의 참조에는 `gait-guide`가 기록되고 `ref-02.png`가 그 이미지다.

---

## 11. 머리 위 여유 · 앞/뒷모습 유지 · 손잡이 (`action_prompt@4`)

`action_prompt@3`에서 `@4`로 올리며 세 가지가 프롬프트에 들어갔다. 해당하지 않는 프롬프트(예: 측면 걷기·idle)는 버전 줄 말고는 이전과 같다.

| 항목 | 조건 | 들어가는 줄 (위치) |
|---|---|---|
| 머리 위 여유 | 액션이 `attack`·`jump` (`kind=fx` 제외) | GRID RULES: `Leave at least 20% of the cell height empty above the head of the standing character: raised arms, weapons and jumps need that room.` 옆 여백 규칙(8%·복구 시 15%)은 그대로 둔다 |
| 앞/뒷모습 유지 | 방향이 `down` 또는 `up` (topdown의 두 방향, front·rear 시점) | CONSISTENCY RULES: `Keep exactly this facing in every cell; do not turn the body toward a three-quarter angle.` 다른 그림에서 다시 그려도 정면·뒷면이 3/4로 돌아가지 않게 한다 |
| 손잡이 | plan에 `handed: "left"\|"right"` | CONSISTENCY RULES: 측면(`right`/`left`)은 소지품 손이 **보는 쪽에서 가까운 팔인지 먼 팔인지**(오른쪽을 보는 측면은 캐릭터의 오른팔이 가깝다), 앞/뒷모습(`down`/`up`)은 그 손이 **이미지의 어느 쪽**에 있는지(정면이면 좌우가 뒤집힌다) |

머리 위 여유가 plan 여백(px)을 바꾸지 않는 이유: 후처리는 측정한 bbox에 맞춰 `fit` 배율로 셀 안에 넣으므로, 생성된 시트에 머리 위 공간이 더 있어도 출력 셀의 여백 체계(`margin.top` 8px)는 그대로다. 여유는 *생성 쪽*의 문제(팔·무기가 칸 위로 잘리지 않게)다.

`handed`: plan의 선택 필드(`none` | `left` | `right`, 없으면 `none`). 값이 있으면 좌우 미러(`mirror: {"left": "right"}`)를 끄고 왼쪽 방향을 별도 unit으로 생성한다(미러하면 소지품이 반대 손으로 옮겨지기 때문). `--mirror`를 명시하면 오류(`invalid_params`)다. CLI `plan --handed left|right|none`, 계획 화면의 "손잡이" 선택이 같은 값을 쓴다.

### 9.1 시점별 걷기·달리기와 첫 프레임 캔버스 (`video_prompt@2`)

- **제자리**: 걷기·달리기는 모든 시점에서 "트레드밀처럼 제자리에서 자연스럽게, 바닥은 흐르지 않는다" 줄이 들어간다(`video_locomotion.txt`의 `inplace`).
- **앞/뒷모습 걸음 문구**: 방향이 `down`이면 "작고 차분한 걸음, 발을 카메라 쪽으로 내차지 않음, 몸은 곧게 카메라와 정면, 곧장 viewer 쪽으로", `up`이면 "…발을 옆으로 내차지 않음…곧장 viewer에게서 멀어짐". 달리기는 "다리가 몸 아래에 머문다"와 방향. 측면은 이 줄이 없다.
- **호출자의 걸음걸이**: plan 액션에 `motion`을 직접 쓰면 그 문구가 그대로 쓰이고 위 걸음 문구는 붙이지 않는다(제자리 줄은 유지).
- **첫 프레임 캔버스**(`video_sprite.canvas_layout`): 위 여백·캐릭터 높이(캔버스 비율) — walk·run `(0.06, 0.80)`(머리 위 여유 없이 크게), attack·jump `(0.30, 0.55)`(든 무기를 위한 머리 위 공간), 그 외는 가운데 60%(기존). 값은 우리 합성 캐릭터로 잘림 없음을 확인한 것이며 sprite-gen의 수치와 같지는 않다(그쪽은 정지 그림 위 20% 행을 따로 확장).
