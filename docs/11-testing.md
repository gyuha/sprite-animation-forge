# 11. 테스트 전략

## 1. 원칙

- **Codex 없이 전체 테스트가 돈다.** 가짜 `codex` 실행 파일이 [03](03-codex-image-provider.md)에 정리한 이벤트·파일 형식을 흉내 내고, 합성 시트를 결과 이미지로 쓴다. 실제 Codex 호출 테스트는 `-m live`로 명시할 때만 실행한다(느리고 사용량을 소모하므로).
- **후처리는 정답을 아는 입력으로 검증한다.** 코드로 그린 합성 시트는 bbox·feet 위치를 정확히 알기 때문에 수치로 단언할 수 있다.
- **실제 모델 출력으로도 검증한다.** 합성 시트는 모델 특유의 문제(정확하지 않은 배경색, 좁은 gutter, 모서리 음영)를 재현하지 못한다. 단, 실제 생성 이미지는 저장소에 커밋하지 않고 각자 로컬에 기록해 쓴다(§3.2).
- **결정성은 테스트로 증명한다.** 같은 입력을 두 번 처리해 모든 출력 해시를 비교한다.

---

## 2. 테스트 계층

| 계층 | 대상 | 도구 | 실행 시점 |
|---|---|---|---|
| 단위 | 파이프라인 단계, QC 지표, 프롬프트 조립, plan 계산 | pytest | 항상 |
| Golden | 로컬에 기록한 실제 Codex 출력의 처리 결과 | pytest | 로컬 샘플이 있을 때(없으면 skip) |
| 결정성 | 전체 `process` 2회 실행 해시 비교 | pytest | 항상 |
| 스키마 | 모든 JSON 산출물 ↔ `schemas/*.json` | pytest + jsonschema | 항상 |
| Provider | `CodexCliProvider` ↔ 가짜 codex | pytest | 항상 |
| CLI | `forge.py` 명령별 stdout JSON·종료 코드 | pytest (subprocess) | 항상 |
| API | FastAPI 엔드포인트, Job 큐, SSE | pytest + httpx | 항상 |
| 프론트엔드 단위 | 플레이어 타이밍, 오버레이 좌표 변환 | Vitest | 항상 |
| E2E 스모크 | Web UI 주요 흐름(가짜 codex 사용) | Playwright | 항상 |
| Phaser 스모크 | export 결과를 실제 Phaser에서 로드 | Playwright | 항상 |
| Live 계약 | 실제 Codex 1회 생성 | pytest `-m live` | Codex 업데이트 후, 릴리스 전 |

---

## 3. 픽스처

### 3.1 합성 시트 생성기

`tests/fixtures/synthetic/make.py`가 테스트 실행 시 결정적으로 생성한다(바이너리를 저장소에 넣지 않음). 캐릭터는 몸통(타원) + 머리(원) + 다리 두 개(사각형)로 그리고, 각 칸의 bbox와 feet 좌표를 함께 반환한다.

| 변형 | 목적 |
|---|---|
| `clean` | 정확한 #FF00FF 배경, 등분된 칸, 일정한 크기 |
| `model_like_bg` | 배경 (250, 3, 250) + 모서리로 갈수록 (240, 13, 242)까지 어두워지는 비네팅(실측 재현) |
| `shifted_gutters` | 칸 경계를 이상적 위치에서 ±4% 이동 |
| `narrow_gutter` | gutter 폭 20px (T2 수준) |
| `edge_touch` | 한 칸의 캐릭터가 경계를 넘음 |
| `scale_drift_12` | 프레임별 높이 ±6% (드리프트 12%) |
| `baseline_jitter` | 프레임별 feet Y ±15px (정렬 후 0이어야 함) |
| `empty_cell` | 한 칸 비움 |
| `specks` | 칸마다 3×3 잡티 5개 (largest 모드로 제거돼야 함) |
| `detached_sword` | body와 6px 떨어진 칼 (largest 모드에서 유지돼야 함) |
| `thin_below_feet` | feet 아래로 1px 폭 칼끝 (feet line이 무시해야 함) |
| `pinkish_character` | 캐릭터에 (230, 90, 200) 포함 (키 색 충돌 규칙) |
| `native_alpha` | 진짜 투명 배경 RGBA |
| `wide_attack` | 칼을 앞으로 길게 뻗음 (fit vs preserve 비교) |
| `asymmetric_right` | 오른쪽 옆모습(무기를 한쪽에만 듦). 좌우반전 파생 결과가 정확히 가로 반전이고 baseline·발 위치가 유지되는지 확인 |

### 3.2 실제 Codex 샘플 (golden, 로컬 전용)

실제 생성 이미지는 장당 1.5–2MB이고 생성할 때마다 내용이 달라지므로 **저장소에 커밋하지 않는다.** 필요한 개발자가 로컬에서 만들어 쓴다.

- 기록: `uv run pytest -m live --record-samples` → idle 2x2(텍스트만), walk 2x3(idle 첫 칸을 reference로 첨부) 두 장을 `tests/fixtures/codex-samples/`에 저장
- 이 디렉터리는 `.gitignore` 대상이다
- 샘플이 없으면 golden 테스트는 skip한다

생성할 때마다 그림이 다르므로 golden 테스트는 특정 좌표가 아니라 **속성**을 검사한다.

| 검사 | 기준 |
|---|---|
| 배경 추정 | 샘플 배경색과 키 색의 거리 < 15 |
| 배경 제거 | 처리 후 네 모서리 알파 0, 전경 픽셀에 magenta 잔여(`min(R,B) − G > 40`) 없음 |
| grid 분리 | 모든 내부 경계에서 gutter 발견(`gutter_missing` 없음), 스냅된 경계가 이상적 경계의 ±6% 이내 |
| 프레임 | 사용 칸 전부 비어 있지 않음(QC-05 pass) |

참고로 2026-09-30 검증 샘플(T1 idle 2x2, T2 walk 2x3, 둘 다 1254×1254)의 실측값은 다음과 같았다. 위 기준은 이 값을 근거로 정했다.

| 샘플 | 배경색(테두리 중앙값) | #FF00FF와 거리 | 행 gutter | 열 gutter |
|---|---|---:|---|---|
| T1 | (251, 3, 250) | 7.1 | 585–664 | 479–766 |
| T2 | (246, 5, 248) | 12.4 | 586–645 | 405–429, 799–845 |

### 3.3 가짜 codex

`tests/fixtures/fake_codex/codex`는 실행 권한이 있는 Python 스크립트다. 테스트는 `SPRITE_FORGE_CODEX_BIN`을 이 파일로, `CODEX_HOME`을 임시 디렉터리로 지정한다.

동작:

1. argv를 파싱해 `-C`, `-i`, `-o`와 마지막 `-`를 확인한다(순서 규칙 위반 시 exit 2 — [03](03-codex-image-provider.md) §4.1 규칙 테스트).
2. stdin을 끝까지 읽어 지시문에 `<<<PROMPT`와 `PROMPT>>>`가 있는지 확인한다.
3. [03](03-codex-image-provider.md) §2 F8·F16 형식의 JSONL 이벤트(`thread.started` → `turn.started` → `item.*` → `turn.completed`)를 새 `thread_id`로 만들어 stdout에 출력한다.
4. `$CODEX_HOME/generated_images/<thread_id>/exec-<uuid>.png`에 합성 시트(§3.1)를 쓴다. 어떤 변형을 쓸지는 `FAKE_CODEX_IMAGE` 환경 변수로 지정한다.
5. `$CODEX_HOME/sessions/YYYY/MM/DD/rollout-…-<thread_id>.jsonl`에 `image_gen.generation` 항목을 쓴다.

```
argv 검증 → stdin 지시문 검증 → JSONL 이벤트 출력(새 thread_id) → generated_images/<thread_id>/에 합성 PNG 쓰기 → rollout 쓰기 → exit 0
     ↓ 규칙 위반                                        (FAKE_CODEX_MODE에 따라 단계 생략·변형)
   exit 2
```

`FAKE_CODEX_MODE` 환경 변수로 실패 상황을 만든다.

| 모드 | 동작 | 기대 결과 |
|---|---|---|
| `success` | 위 전부 | `succeeded`, `source_resolved_by=rollout` |
| `no_rollout` | 5번 생략 | `succeeded`, `source_resolved_by=glob`, `revised_prompt=null` |
| `no_image` | 4·5번 생략 | `no_image` |
| `multiple_images` | 이미지 2장 저장, rollout에 2개 항목 | 마지막 것 선택, `warnings`에 `multiple_images: 2` |
| `image_gen_failed` | rollout `failure`에 사유 | `image_gen_failed` |
| `exit_1` | stderr 출력 후 exit 1 | `codex_failed`, stderr tail 포함 |
| `hang` | 이벤트 일부 출력 후 무한 대기 | 타임아웃(테스트에서는 2초) → `timeout`, 프로세스 종료 확인 |
| `invalid_png` | PNG가 아닌 바이트 저장 | `invalid_image` |
| `config_warnings` | 시작 시 `item.type=error` 2개 출력 | 성공(오류로 취급하지 않음) |

---

## 4. 모듈별 주요 테스트

| 모듈 | 테스트 |
|---|---|
| `plan` | 프리셋 적용, frames → grid 표, 사용자 override 우선, 키 색 충돌 시 green 전환, 번들 전개 |
| `prompt` | [04](04-prompt-rules.md) §8 규칙 전부, 복구 코드별 문구·margin 변화, 스냅샷 테스트(템플릿 버전 고정) |
| `chroma` | 배경색 추정(비네팅 포함), 램프 경계값, despill이 빨간색을 바꾸지 않음, native alpha 감지 |
| `split` | 이상적 경계, gutter 스냅(포함·근접·없음), 행 띠별 세로 경계, 빈 칸 무시 |
| `components` | 잡티 제거, 떨어진 칼 유지, all 모드 |
| `measure` | feet line이 가는 칼끝 무시, strict feet line, x anchor 3종 |
| `scale` | fit이 anchor 기준 여유로 계산됨(`wide_attack`에서 칸 안에 들어감), preserve 공식, profile 없을 때 fit 대체, 넘침 감지 |
| `align` | 모든 프레임 feet이 baseline ±0.5px, 정수 오프셋 |
| `qc` | 항목별 경계값(바로 아래·위), 적용 매트릭스, 점수 계산, 권장 조치 우선순위 |
| `export` | atlas 좌표·크기 공식, 이름 규칙, animations.json repeat, GIF 프레임 지속 시간, 4096 초과 오류 |
| `manifest` | 동시 쓰기(프로세스 2개가 번갈아 갱신해도 손실 없음), 원자적 교체 |
| `fsutil` | attempt 번호 동시 할당 충돌 없음 |
| `providers.codex_cli` | §3.3 모드 전부, argv 구성(`-i` 뒤에 `-` 없음), 취소 |
| Web API | 모든 엔드포인트 정상·오류 경로, 큐 순서, 취소, SSE 이벤트 순서, 기동 시 `interrupted` 표시, `/files` 경로 탈출 차단 |

---

## 5. MVP 인수 테스트

PRD §32 시나리오를 자동 테스트로 옮긴다. 가짜 codex 버전은 항상 돌고, live 버전은 릴리스 전에 한 번 돌린다.

| 시나리오 | 절차 | 통과 기준 |
|---|---|---|
| 1. idle 4프레임 | `init → reference import → plan --actions idle → generate → process → accept → export` | `idle/frames/` 4장, `idle/sheet.png` 투명(모서리 알파 0), `preview/idle.gif`, `idle/qc-report.json` 스키마 통과 |
| 2. walk 6프레임 | 시나리오 1 후 walk | QC-01 pass, QC-02 ≤ 0.10, QC-03 ≤ 3px. live에서는 사람이 정체성 유지를 확인(Web UI idle 겹쳐 보기) |
| 3. Hero bundle | idle·walk·run·attack 생성 후 `export --engine phaser` | `atlas/hero.png`·`hero.json`·`animations.json` 존재, Phaser 스모크 통과(§6) |
| 4. 긴 칼 attack | `wide_attack` 합성 시트(가짜) / live는 "oversized greatsword" 추가 지시 | preserve 적용 시 QC-07 ≥ 0.85. 같은 입력을 fit으로 처리하면 QC-07이 더 낮게 나옴(대조군) |
| 6. 탑다운 4방향 (PRD 외 추가) | `init --view topdown → plan --actions idle,walk → down·up·right 각각 generate/process/accept → export` | `left`는 Codex 호출 없이 `right`의 정확한 가로 반전(픽셀 단위 일치). atlas에 `walk_down/up/right/left_*` 프레임 전부 존재. `animations.json` 키 8개(idle·walk × 4방향). Phaser 스모크에서 `walk_left`를 포함한 전 애니메이션 재생. 방향 간 `body_height` 차이 ≤ 10% |
| 5. QC 실패 복구 | `edge_touch`·`scale_drift_12`·`wide_attack(fit)` 시트 | 각각 권장 조치 1순위가 재생성 `edge_touch` / 재생성 `scale_drift` / 재처리 `use_preserve`. Skill 모드 CLI 흐름에서 예산 내 복구 또는 강제 채택 기록 |

---

## 6. Phaser 스모크 테스트

`tests/phaser-smoke/index.html`은 export 결과를 불러와 Phaser 씬을 만드는 최소 페이지다. Playwright가 이 페이지를 열고 다음을 확인한다.

- 콘솔 오류 없음
- `textures.exists('hero')`가 true이고 `hero.json`의 모든 프레임 이름이 존재
- `animations.json`의 모든 애니메이션이 `anims.create` 후 `anims.exists`로 확인되고, 프레임 수가 일치
- 스프라이트를 `idle_0`으로 만들었을 때 원점이 `hero.meta.json`의 `origin`과 같음(`anchor` 필드 동작 확인, [07](07-export.md) §4)

Phaser는 `webui/web`의 devDependency로 설치한 버전을 쓴다.

---

## 7. 실행 명령

```bash
uv run pytest                          # 전체 (live 제외)
uv run pytest -m live                  # 실제 Codex 계약 테스트 (약 2–3분, 사용량 소모)
uv run pytest -k determinism           # 결정성만
pnpm --dir webui/web test              # Vitest
pnpm --dir webui/web e2e               # Playwright (Web UI 스모크 + Phaser 스모크)
```

CI를 구성할 경우 `-m live`는 제외한다. live 테스트는 로그인된 로컬 환경에서만 실행한다.
