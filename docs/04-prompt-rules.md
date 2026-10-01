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

`loop_line`은 loop 액션이면 `The last frame must flow seamlessly back into frame 1.`, 아니면 `This is a one-shot animation; frame {n} is the final pose.`이다.

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
- Same facing direction ({facing}) in every cell.
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

1. contact: front leg extended, heel touching the ground, back leg behind
2. down: weight shifts onto the front leg, body at its lowest
3. passing: back leg passes the supporting leg, body at its highest
4. contact (opposite leg): other leg now in front, heel touching the ground
5. down (opposite leg)
6. passing (opposite leg)

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

ACTION
Walk cycle. Arms swing opposite to the legs. Body bobs slightly.
Frame sequence:
1. contact: front leg extended, heel touching the ground, back leg behind
2. down: weight shifts onto the front leg, body at its lowest
3. passing: back leg passes the supporting leg, body at its highest
4. contact (opposite leg): other leg now in front, heel touching the ground
5. down (opposite leg)
6. passing (opposite leg)
The last frame must flow seamlessly back into frame 1.
Animate in place: the character does not travel across the cell.

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
