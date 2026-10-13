# sprite-animation-forge

캐릭터 이미지 한 장(또는 텍스트 설명)에서 **게임용 2D 스프라이트 애니메이션**(idle·walk·run·attack·jump·hurt·death …)을 만들어 주는 도구입니다. 이미지 생성은 [Codex CLI](https://github.com/openai/codex)의 내장 `image_gen`을 쓰므로 **API 키 없이 ChatGPT 로그인만으로** 동작합니다.

핵심 원칙은 한 줄입니다: **이미지 모델은 그리고, 결정적 스크립트가 자르고·정렬하고·검증하고·묶습니다.** 픽셀을 직접 그리거나 고치지 않으며, 같은 입력이면 같은 결과가 나옵니다.

## 무엇을 하나

액션마다 시트(격자 이미지)를 한 장씩 생성하고, 후처리와 자동 품질 검사(QC)를 거쳐 채택한 결과만 내보냅니다. 각 단계는 CLI·Web UI·에이전트 Skill 어디서든 같은 Core를 호출합니다.

```
참조 이미지 → 캐릭터 분석 → 계획(액션·격자) → 생성(Codex) → 후처리 → QC → 채택 → 내보내기
```

- **후처리:** 크로마키 배경 제거, 프레임 분리, 컴포넌트 검출, 스케일 정규화, 발 기준 정렬
- **QC:** 프레임 수·빈 프레임·접지·잘림 등 자동 검사와 실패 시 복구 권장(재처리/재생성)
- **내보내기:** 프레임 PNG, 스프라이트 시트, GIF 미리보기, Phaser atlas + `animations.json`, 캐릭터 QC 리포트

## 생성 방식 (method)

액션마다 plan에 하나가 정해진다. 기본은 `grid`이고, 나머지는 선택이다.

| 방식 | 하는 일 | 필요한 것 |
|---|---|---|
| `grid` (기본) | 격자 시트 한 장을 Codex로 생성 → 후처리 | Codex 로그인 |
| `breathe` | 정지 1장(레이아웃 가이드 첨부) + 결정적 호흡 변형, idle 전용 | Codex 로그인 |
| `video` | 첫 프레임에서 영상을 생성한 뒤 프레임 추출·루프 선택·정렬로 스프라이트 변환 (단일 방향 플랜만) | xAI 키(또는 `grok login`), ffmpeg, 선택: RIFE |

영상 방식은 [연결 안내](docs/13-video-api-setup.md)를 따라 키를 연결하고 `forge.py doctor`에서 `video.configured: true`를 확인한 뒤 쓴다. 끝나지 못한 영상 생성은 `forge.py resume <캐릭터> <액션> --attempt NNN`으로 재과금 없이 이어받는다. 사용한 이미지·영상 생성 기법은 [sprite-gen](https://github.com/aldegad/sprite-gen)(Apache-2.0)의 동작을 읽고 **재구현**한 것이며, 반영 범위와 미채택 사유는 [`docs/14`](docs/14-sprite-gen-sync.md)에 있다.

## 구성

| 구성 요소 | 위치 | 역할 |
|---|---|---|
| Core + CLI | `sprite-animation-forge/scripts/` | 파이프라인·QC·내보내기. 모든 명령이 JSON 한 줄을 출력 (`forge.py`) |
| Skill | `sprite-animation-forge/SKILL.md` | 에이전트가 CLI를 올바른 순서로 쓰게 하는 지침 |
| Web 서버 | `webui/server/` | FastAPI. REST + SSE, 작업(Job) 큐 |
| Web UI | `webui/web/` | React SPA. 생성·미리보기·QC·채택·뷰어·내보내기 |
| 문서 | `docs/` | 설계 문서 (아래 참고) |

## 요구 사항

- Python 3.11 이상, [uv](https://docs.astral.sh/uv/)
- Node.js와 [pnpm](https://pnpm.io/) (Web UI)
- Codex CLI 0.159.0 이상, `codex login` 완료, `image_generation` 기능 활성 (검증 버전 0.159.2)
- 선택: [Task](https://taskfile.dev/) — 아래 명령을 짧게 쓰기 위한 러너

사전 점검은 `doctor`로 합니다. 문제가 있으면 원인과 해결 명령이 JSON에 나옵니다.

```bash
uv sync
task doctor        # 또는: uv run python sprite-animation-forge/scripts/forge.py doctor
```

## 빠른 시작

### Web UI

개발 모드는 서버(8765)와 Vite(5273)를 함께 띄웁니다. 같은 네트워크의 다른 기기에서는 `http://<내 IP>:5273`으로도 접속됩니다.

```bash
task sync          # uv sync + pnpm install
task dev           # http://localhost:5273  (Ctrl-C로 둘 다 종료)
```

프로덕션 빌드를 서버 하나로 서빙하려면 `task start` (http://127.0.0.1:8765)를 씁니다.

화면 흐름은 다음과 같습니다. 새 캐릭터를 만들고 참조 이미지를 올리면 계획 화면에서 액션을 고르고, 스튜디오에서 액션별로 생성·검토·채택한 뒤 뷰어로 움직임을 확인하고 내보냅니다.

```
대시보드 → 참조·캐릭터 분석 → 계획 → 스튜디오(생성·QC·채택) → 애니메이션 보기 → 내보내기
```

### CLI

결과는 `./sprites/<캐릭터 id>/`에 쌓입니다(`--root` 또는 `$SPRITE_FORGE_ROOT`로 변경). 모든 명령은 stdout에 JSON 한 개를 출력하고, 종료 코드는 0 성공(QC 실패도 0, `qc.status` 확인) · 1 인자 오류 · 2 생성 오류 · 3 선행 조건 누락입니다.

```bash
F="uv run python sprite-animation-forge/scripts/forge.py"

$F init hero --view side
$F reference import hero ./hero.png        # 텍스트만 있으면: reference generate → reference select
$F identity analyze hero
$F plan hero --actions idle,walk,attack
$F generate hero walk                      # Codex로 새 attempt 생성
$F process hero walk                       # 후처리 + QC
$F accept hero walk                        # 마음에 들면 채택
# 한쪽 손에 무기를 든 캐릭터는 계획에 손을 알려 준다(좌측면을 반전하지 않고 직접 생성): plan hero --handed right
$F export hero                             # atlas / animations.json / GIF
```

`status`로 단위별 상태를, `prompt`로 생성될 프롬프트를 미리 볼 수 있습니다. 다른 도구로 만든 시트는 `import-raw`로 가져와 같은 후처리·QC를 태울 수 있습니다. 전체 명령은 `forge.py --help`를 보세요.

### 에이전트 Skill

`sprite-animation-forge/` 디렉터리가 Skill 하나입니다. "스프라이트 만들어 줘", "idle/walk/run 애니메이션" 같은 요청에 `SKILL.md`의 워크플로를 따라 CLI를 호출합니다. 에이전트는 픽셀을 직접 그리지 않고 `forge.py`만 사용합니다.

## 개발

| 작업 | 명령 |
|---|---|
| Python 전체 테스트 (live 제외, 약 2분) | `task test` |
| 빠른 단위·파이프라인 테스트 | `task test:quick` |
| Web API 서버 테스트 | `task test:server` |
| 프런트엔드 테스트 / 타입 검사 | `task web:test` / `task web:typecheck` |
| E2E (Playwright, 가짜 codex) | `task e2e` |
| 전부 | `task test:all` |
| 서버 OpenAPI → TS 타입 재생성 | `task gen:types` |
| 실제 Codex 계약 테스트 | `task test:live` (사용량 소모) |

- 기본 테스트는 **가짜 codex**(`tests/fixtures/fake_codex`)를 쓰므로 로그인·네트워크·사용량이 필요 없습니다. 실제 Codex를 부르는 `live` 테스트는 `-m live`를 명시했을 때만 돕니다.
- 결과는 결정적입니다(반올림 규칙 포함). 파이프라인을 바꾸면 결정성·골든 테스트가 깨지는지 먼저 확인하세요.
- Task 없이 쓰려면 `Taskfile.yml`의 각 작업이 실행하는 명령을 그대로 쓰면 됩니다.

## 문서

설계 문서는 [`docs/README.md`](docs/README.md)에서 시작하세요. 처음이라면 `01 architecture → 03 codex-image-provider → 08 data-model` 순서를 권합니다.

| 문서 | 내용 |
|---|---|
| [01 architecture](docs/01-architecture.md) | 구조·계층·기술 스택 |
| [03 codex-image-provider](docs/03-codex-image-provider.md) | Codex 이미지 생성 어댑터 (실측 검증) |
| [04 prompt-rules](docs/04-prompt-rules.md) | 프롬프트 구조와 액션별 모션 라이브러리 |
| [05 sprite-pipeline](docs/05-sprite-pipeline.md) | 크로마키·분리·스케일·정렬 알고리즘 |
| [06 qc-and-recovery](docs/06-qc-and-recovery.md) | QC 항목·임계값·자동 복구 |
| [07 export](docs/07-export.md) | atlas·Phaser JSON·GIF |
| [09 web-ui](docs/09-web-ui.md), [10 backend-api](docs/10-backend-api.md) | 화면 설계와 REST/SSE API |
| [11 testing](docs/11-testing.md) | 테스트 전략 |
| [13 video-api-setup](docs/13-video-api-setup.md) | 동영상 방식 연결, 루프 선택, RIFE 보정 (선택) |
| [14 sprite-gen-sync](docs/14-sprite-gen-sync.md) | sprite-gen 변경 반영 기록과 미채택 사유 |

## 라이선스

[MIT](sprite-animation-forge/LICENSE)
