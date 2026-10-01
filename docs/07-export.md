# 07. 내보내기 (Atlas · Phaser · GIF)

## 1. 개요

`export`는 채택된 액션들을 하나의 texture atlas로 조립하고, 게임 엔진용 메타데이터와 미리보기 GIF를 만든다. 입력은 액션 디렉터리 최상위(채택된 attempt의 복사본)의 `frames/`뿐이다. attempts 디렉터리는 읽지 않는다.

목표는 PRD §39 그대로다. 결과 디렉터리를 **Phaser 프로젝트의 assets 폴더에 복사하면 바로 쓸 수 있어야 한다.**

```
채택된 frames/ 수집 → atlas 배치·합성 → hero.png + hero.json(Phaser) + hero.generic.json + hero.meta.json
                                   → animations.json → preview/*.gif → 루트 qc-report.json → manifest.json 갱신
```

---

## 2. 선행 조건

| 조건 | 미충족 시 |
|---|---|
| plan의 모든 액션이 채택됨(방향이 여러 개면 모든 unit, `walk/up` 형식) | 채택된 unit만 내보내고 `warnings`에 `missing_actions: [...]` |
| 모든 액션의 cell 크기가 같음 | 오류 `cell_mismatch` (MVP는 캐릭터당 단일 cell 크기) |
| 강제 채택(forced accept)된 액션 | 내보내되 루트 `qc-report.json`의 `forced_accepts`에 기록 |

---

## 3. Atlas 배치

MVP는 단순하고 결정적인 **행 단위 배치**를 쓴다. 액션 하나(방향이 여러 개인 plan에서는 unit 하나, 예: `walk/up`)가 한 행이다. 트리밍·회전·빈 공간 채우기(bin packing)는 하지 않는다. 텍스처가 조금 커지는 대신 디버깅이 쉽고, 모든 프레임이 같은 크기라 원점 처리가 단순하다.

- 행 순서: plan의 `order` (body 액션 먼저, FX는 그 뒤). 방향이 여러 개면 액션 안에서 `down, up, right, left` 순
- 프레임 위치: `x = pad + i × (CW + pad)`, `y = pad + row × (CH + pad)`
- `pad = 2`px (선형 필터링 시 이웃 프레임 색이 번지는 것을 방지)
- 텍스처 크기: `W = pad + max_frames × (CW + pad)`, `H = pad + rows × (CH + pad)`
- 최대 크기: 가로·세로 각각 4096px. 초과하면 오류 `atlas_too_large` (다중 atlas는 Phase 2)

예: 액션 4개, 최대 6프레임, cell 128 → `782 × 522`.

`side-action` 번들(액션 8개, 최대 8프레임) → `1042 × 1042`. 4096 한도까지 여유가 크다.

**탑다운 4방향**은 행이 방향 수만큼 늘어난다. mirror로 파생된 `left`도 **실제 프레임으로 atlas에 포함**한다(게임 코드에서 `setFlipX`를 따로 다루지 않아도 되도록. 대신 텍스처가 커진다). cell 128 기준 최대 행 수는 `⌊(4096 − 2) / 130⌋ = 31`, cell 256은 `⌊4094 / 258⌋ = 15`다. `topdown-rpg`(5액션 × 4방향 = 20행)는 128에서 `1042 × 2602`로 들어가지만 256에서는 `atlas_too_large`다. 다중 atlas는 Phase 2이므로 MVP에서는 액션·방향을 줄이거나 cell을 128로 쓴다.

---

## 4. `atlas/hero.json` (Phaser JSON Hash)

Phaser `this.load.atlas()`가 읽는 JSON Hash 형식이다. 프레임 이름은 PRD §25를 따라 `<action>_<index>`(0부터)다. 방향이 2개 이상인 plan에서는 `<action>_<direction>_<index>`(예: `walk_up_3`)다.

```json
{
  "frames": {
    "idle_0": {
      "frame": { "x": 2, "y": 2, "w": 128, "h": 128 },
      "rotated": false,
      "trimmed": false,
      "spriteSourceSize": { "x": 0, "y": 0, "w": 128, "h": 128 },
      "sourceSize": { "w": 128, "h": 128 },
      "anchor": { "x": 0.5, "y": 0.921875 }
    },
    "idle_1": {
      "frame": { "x": 132, "y": 2, "w": 128, "h": 128 },
      "rotated": false,
      "trimmed": false,
      "spriteSourceSize": { "x": 0, "y": 0, "w": 128, "h": 128 },
      "sourceSize": { "w": 128, "h": 128 },
      "anchor": { "x": 0.5, "y": 0.921875 }
    }
  },
  "meta": {
    "app": "sprite-animation-forge",
    "version": "0.1.0",
    "image": "hero.png",
    "format": "RGBA8888",
    "size": { "w": 782, "h": 522 },
    "scale": "1"
  }
}
```

- `anchor`는 발 위치 원점이다: `x = 0.5`, `y = baseline_y / CH = 118 / 128 = 0.921875`.
- Phaser의 atlas 파서는 프레임의 `anchor` 필드를 custom pivot으로 인식해 스프라이트 원점을 자동 설정한다 [높음: M3에서 Phaser 4.2.1(Playwright 스모크, `webui/web/e2e/phaser-smoke.spec.ts`)로 확인 — `setOrigin` 없이 만든 `idle_0` 스프라이트의 원점이 (0.5, 0.921875)였다]. 그래도 §7 예시처럼 사용 코드에서 `setOrigin`을 명시하는 것을 권장한다(Phaser 버전·로더에 따라 `anchor` 지원이 달라질 수 있어 어느 쪽이든 안전하다).

---

## 5. `animations.json`

PRD §25 형식을 그대로 쓴다. 필드를 추가하지 않는다. 추가 정보는 `hero.meta.json`에 둔다.

```json
{
  "idle":   { "frames": ["idle_0", "idle_1", "idle_2", "idle_3"], "frameRate": 6, "repeat": -1 },
  "walk":   { "frames": ["walk_0", "walk_1", "walk_2", "walk_3", "walk_4", "walk_5"], "frameRate": 10, "repeat": -1 },
  "run":    { "frames": ["run_0", "run_1", "run_2", "run_3", "run_4", "run_5"], "frameRate": 12, "repeat": -1 },
  "attack": { "frames": ["attack_0", "attack_1", "attack_2", "attack_3", "attack_4", "attack_5"], "frameRate": 12, "repeat": 0 }
}
```

`repeat`는 loop 액션이면 `-1`, 아니면 `0`이다.

방향이 2개 이상인 plan에서는 unit마다 항목이 하나 생기고 키가 `<action>_<direction>`이다. 필드는 추가하지 않는다.

```json
{
  "walk_down":  { "frames": ["walk_down_0", "walk_down_1", "walk_down_2", "walk_down_3", "walk_down_4", "walk_down_5"], "frameRate": 10, "repeat": -1 },
  "walk_up":    { "frames": ["walk_up_0", "walk_up_1", "walk_up_2", "walk_up_3", "walk_up_4", "walk_up_5"], "frameRate": 10, "repeat": -1 },
  "walk_right": { "frames": ["walk_right_0", "walk_right_1", "walk_right_2", "walk_right_3", "walk_right_4", "walk_right_5"], "frameRate": 10, "repeat": -1 },
  "walk_left":  { "frames": ["walk_left_0", "walk_left_1", "walk_left_2", "walk_left_3", "walk_left_4", "walk_left_5"], "frameRate": 10, "repeat": -1 }
}
```

---

## 6. `atlas/hero.meta.json`

엔진 무관 부가 정보다. 코드에서 원점·baseline을 계산하거나 도구가 결과를 추적할 때 쓴다.

```json
{
  "schema_version": 1,
  "character": "hero",
  "generator": { "name": "sprite-animation-forge", "version": "0.1.0" },
  "cell": { "w": 128, "h": 128 },
  "baseline_y": 118,
  "origin": { "x": 0.5, "y": 0.921875 },
  "padding": 2,
  "view": "side",
  "facing": "right",
  "actions": [
    { "name": "idle", "row": 0, "frames": 4, "fps": 6, "loop": true, "attempt": "001", "qc": "pass" },
    { "name": "walk", "row": 1, "frames": 6, "fps": 10, "loop": true, "attempt": "001", "qc": "pass" }
  ],
  "texture": { "file": "hero.png", "sha256": "…", "size": [782, 522] }
}
```

PRD §23의 `hero.meta.json`에 해당한다.

---

## 7. Phaser 사용 예

결과 디렉터리를 `public/assets/hero/`로 복사했다고 가정한다. 애니메이션 key는 게임 전체에서 공유되므로 캐릭터 id를 접두사로 붙인다.

```js
// preload
this.load.atlas('hero', 'assets/hero/atlas/hero.png', 'assets/hero/atlas/hero.json');
this.load.json('hero-anims', 'assets/hero/animations.json');

// create
const defs = this.cache.json.get('hero-anims');
for (const [name, def] of Object.entries(defs)) {
  this.anims.create({
    key: `hero-${name}`,
    frames: def.frames.map((frame) => ({ key: 'hero', frame })),
    frameRate: def.frameRate,
    repeat: def.repeat,
  });
}

const hero = this.add.sprite(200, 300, 'hero', 'idle_0');
hero.setOrigin(0.5, 118 / 128);   // hero.meta.json 의 origin. 발이 (200, 300)에 놓임
hero.play('hero-idle');
```

- 픽셀 아트 스타일이면 게임 설정에 `pixelArt: true`를 둔다.
- 왼쪽을 볼 때는 `hero.setFlipX(true)`. side view는 오른쪽 방향만 생성한다(좌우 반전은 엔진이 처리).
- 탑다운 4방향 plan은 `left`까지 atlas에 들어 있어 `setFlipX`가 필요 없다. 이동 방향에 따라 애니메이션 key만 고른다.

```js
// 탑다운: 마지막으로 바라본 방향('down' | 'up' | 'right' | 'left')을 기억해 idle/walk key를 고른다
let facing = 'down';
function update(vx, vy) {
  if (vx || vy) facing = Math.abs(vx) > Math.abs(vy) ? (vx > 0 ? 'right' : 'left') : (vy > 0 ? 'down' : 'up');
  hero.play(`hero-${vx || vy ? 'walk' : 'idle'}_${facing}`, true);
}
```

---

## 8. Generic 출력

엔진 무관 JSON이다(PRD §25 Generic). 같은 `hero.png`를 참조하므로 PNG를 중복 저장하지 않는다. 파일명은 PRD의 `sprite.json` 대신 `atlas/hero.generic.json`으로 한다(캐릭터 여러 개를 한 폴더에 둘 때 충돌 방지).

```json
{
  "schema_version": 1,
  "image": "hero.png",
  "cell": { "w": 128, "h": 128 },
  "origin": { "x": 0.5, "y": 0.921875 },
  "frames": [
    { "name": "idle_0", "action": "idle", "direction": null, "index": 0, "x": 2, "y": 2, "w": 128, "h": 128 }
  ],
  "animations": {
    "idle": { "frames": ["idle_0", "idle_1", "idle_2", "idle_3"], "fps": 6, "loop": true }
  }
}
```

---

## 9. 미리보기 GIF

`preview/<action>.gif`를 액션마다 만든다(PRD §39). 방향이 2개 이상인 plan에서는 unit마다 `preview/<action>_<direction>.gif`다.

| 항목 | 규칙 |
|---|---|
| 프레임 지속 시간 | `round(1000 / fps / 10) × 10` ms. GIF 시간 해상도가 10ms 단위이기 때문(예: 12fps → 80ms) |
| 반복 | 모든 GIF는 무한 반복(`loop=0`). 미리보기 목적이므로 one-shot 액션도 반복하되, 마지막 프레임을 400ms 더 보여준다 |
| 투명도 | GIF는 1비트 투명만 지원하므로 `alpha ≥ 128`을 불투명으로 이진화. 가장자리가 거칠어지는 것은 GIF 형식의 한계 |
| 색상 | 프레임별 `quantize(colors=255, method=MEDIANCUT)`, 투명 인덱스 1개 예약, `disposal=2` |

Web UI는 GIF 대신 PNG 프레임을 캔버스로 재생한다(반투명 가장자리 유지). GIF는 문서·메신저 공유용이다.

---

## 10. 검증

export 마지막에 다음을 검사하고, 하나라도 실패하면 오류로 끝낸다(결과 파일은 임시 디렉터리에 쓰고 검증 통과 후 원자적으로 교체).

| 검사 | 내용 |
|---|---|
| 프레임 사각형 | 모든 `frame`이 텍스처 범위 안에 있고 서로 겹치지 않음 |
| 이름 | 프레임 이름이 유일하고 `animations.json`의 모든 참조가 `hero.json`에 존재 |
| 수량 | 액션별 프레임 수 = plan의 `frames` |
| 스키마 | `hero.meta.json`, `hero.generic.json`, `qc-report.json`, `manifest.json`을 스키마로 검증 |
| 해시 | 모든 출력의 sha256을 manifest에 기록 |

---

## 11. 최종 출력 구조

PRD §39 구조에 액션별 세부 파일(§23)을 흡수한 형태다. 전체 디렉터리 규칙은 [08-data-model.md](08-data-model.md)에 있다.

```text
hero/
├── idle/ walk/ run/ attack/        # 채택본 (raw.png, clean.png, sheet.png, qc-report.json, frames/) + attempts/
├── preview/
│   ├── idle.gif
│   ├── walk.gif
│   ├── run.gif
│   └── attack.gif
├── atlas/
│   ├── hero.png
│   ├── hero.json                   # Phaser JSON Hash
│   ├── hero.generic.json
│   └── hero.meta.json
├── animations.json
├── character-profile.json
├── character-scale-profile.json
├── qc-report.json                  # 캐릭터 단위 집계
└── manifest.json
```

Phaser 프로젝트에 필요한 최소 파일은 `atlas/hero.png`, `atlas/hero.json`, `animations.json` 세 개다. Web UI의 "내보내기 ZIP"은 이 세 파일과 `atlas/hero.meta.json`, `preview/`만 담는다(attempts 제외).
