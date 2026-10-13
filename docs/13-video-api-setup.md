# 13. 동영상 방식 API 연결 안내 (xAI Grok Imagine)

동영상 방식(`method=video`)은 **선택 기능**이다. 이미지 방식(`grid`, `breathe`)만 쓴다면 이 문서는 필요 없다. 이 문서는 xAI의 Grok Imagine 영상 생성을 연결하는 순서를 단계별로 안내한다. 연결 상태가 `configured: true`가 되면 플랜에서 `method=video`를 고를 수 있다(영상 → 스프라이트 변환은 별도 작업에서 구현).

> **확인 필요 표기**: 엔드포인트·모델명·응답 필드·가격·이용 한도는 sprite-gen(Apache-2.0) 구현을 참고해 정리한 값이며 이 저장소에서 실제 계정으로 검증하지 못했다. "확인 필요"가 붙은 항목은 연결 후 `live` 테스트(5단계)로 먼저 확인한다. 설정값(모델명 등)은 환경 변수로 바꿀 수 있다.

연결 순서와 각 단계의 확인 명령은 다음과 같다.

```
1 계정·결제 → 2 인증 정보 준비 → 3 환경 확인(doctor) → 4 (선택) ffmpeg 설치 → 5 live 테스트(비용 발생)
        ↓ 각 단계가 실패하면 6 문제 해결
```

## 1. 계정과 결제

두 경로 중 하나면 된다.

| 경로 | 준비물 | 비고 |
|---|---|---|
| xAI API 키 | <https://console.x.ai> 에서 가입 → API Keys 생성 | 종량제 결제 수단 필요 (가격 확인 필요) |
| `grok` CLI 로그인 | SuperGrok 구독 + `grok` CLI | 로그인 정보가 `~/.grok/auth.json`에 저장됨 (파일 형식 확인 필요) |

- 공식 문서: <https://docs.x.ai> (영상 생성 항목의 모델명·가격·길이 제한을 확인한다).
- 영상 생성은 호출당 비용이 든다. 테스트 전에 콘솔의 사용량·한도 화면 위치를 먼저 확인한다.

## 2. 인증 정보 준비

이 프로그램은 인증 정보를 **`~/.grok/auth.json` → `XAI_API_KEY` 환경 변수** 순서로 찾는다.

```bash
# (A) API 키
export XAI_API_KEY="xai-..."          # 셸 프로필에 넣거나 task dev 실행 셸에서 설정

# (B) grok CLI (설치 방법은 공식 안내 확인 필요)
grok login                            # 브라우저 로그인 → ~/.grok/auth.json 생성
```

- `auth.json`에서는 `api_key`, `apiKey`, `key`, `access_token`, `token` 중 먼저 발견되는 문자열 필드를 쓴다. 형식이 다르면 `XAI_API_KEY`를 쓰거나 `SPRITE_FORGE_GROK_AUTH=<경로>`로 다른 파일을 지정한다.
- 키는 저장소·로그·`manifest.json`에 기록되지 않는다. `generation.json`에는 인증 출처(`grok_auth_json`/`env`)만 남는다.
- 확인: 아래 3단계.

## 3. 연결 확인 (`doctor`)

```bash
uv run python sprite-animation-forge/scripts/forge.py doctor
```

출력 JSON의 `video`를 본다.

```json
"video": {"provider": "xai", "configured": true, "auth": "env", "model": "grok-imagine-video-1.5"}
```

- `configured: true` → 연결됨. `false` → 2단계로 돌아간다.
- 영상 방식이 연결되지 않아도 `ready`와 `warnings`는 달라지지 않는다.
- Web UI는 **상태** 화면의 "동영상 방식 (선택)" 카드에서 같은 정보를 보여 준다("다시 확인"으로 새로 고침).
- 서버를 켠 셸에서 환경 변수를 바꿨다면 서버를 다시 시작한다.

## 4. ffmpeg 설치 (영상 → 프레임 변환용)

영상에서 프레임을 뽑을 때 `ffmpeg`가 필요하다(변환 기능 구현 후 사용).

```bash
brew install ffmpeg        # macOS
ffmpeg -version            # 확인
```

## 5. 실제 호출 확인 (비용 발생)

```bash
uv run pytest -m live -k video -q
```

작은 2초·480p 영상 1건을 실제로 생성한다. 통과하면 모델명·엔드포인트·응답 형식이 맞는 것이다. 실패하면 메시지의 `error_code`를 6단계 표에서 찾는다.

설정 변경(필요할 때만):

| 환경 변수 | 기본값 | 용도 |
|---|---|---|
| `SPRITE_FORGE_XAI_VIDEO_MODEL` | `grok-imagine-video-1.5` (확인 필요) | 모델명 |
| `SPRITE_FORGE_XAI_BASE_URL` | `https://api.x.ai` | API 주소 |
| `SPRITE_FORGE_GROK_AUTH` | `~/.grok/auth.json` | 인증 파일 경로 |
| `SPRITE_FORGE_VIDEO_PROVIDER` | `xai` | `fake`면 네트워크 없이 가짜 응답(테스트·시연용) |

## 6. 문제 해결

| `error_code` | 뜻 | 조치 |
|---|---|---|
| `video_not_configured` | 인증 정보를 못 찾음 | 2단계, 서버 재시작 |
| `video_auth_failed` | 401/403 | 키 만료·권한 확인, `grok login` 재실행 |
| `video_request_failed` | 그 외 HTTP 오류 (429 한도 초과 포함, 자동 재시도 3회 후 실패) | 콘솔의 한도·잔액 확인, 잠시 후 재시도 |
| `video_unfinished` | 클립은 만들어졌는데(과금 가능) 내려받지 못했거나 완료 응답에 주소가 없음. 오류 줄에 `request_id`가 남음 | 재과금 없이 이어받기: `uv run python sprite-animation-forge/scripts/forge.py resume <캐릭터> <액션> --attempt <NNN>` (Web API는 `POST …/attempts/{aid}/resume`). 같은 attempt가 완료되고 새 attempt는 만들어지지 않는다 |
| `video_content_policy` | 서버가 콘텐츠 정책으로 거절 | 프롬프트·첫 프레임을 바꿔 다시 시도 |
| `video_failed` | 서버가 생성 실패/만료 보고 | 프롬프트 변경(콘텐츠 정책 가능), 재시도 |
| `video_timeout` | 제한 시간(기본 600초) 내 미완료 | 재시도, 해상도 낮추기 |
| `video_bad_response` / `video_bad_file` | 응답·파일 형식이 예상과 다름 | API 변경 가능성 — 5단계 live 테스트 결과를 이슈로 남긴다 |

## 참고

- 구현: `sprite_forge/providers/video_base.py`(인터페이스), `xai_video.py`(xAI), `fake_video.py`(테스트용 가짜 transport).
- 설계 근거: 생성 방식(method)은 `.forge/CONTEXT.md`, 참고 구현은 <https://github.com/aldegad/sprite-gen>(Apache-2.0, 코드 복사 없이 재구현).

## 7. 루프 선택 (영상 → 프레임)

영상에서 뽑은 프레임으로 plan의 프레임 수만큼 고르는 규칙이다(`video_loop.py`·`video_sprite.py`). 결과는 attempt의 `video-meta.json`에 남는다.

| 항목 | 동작 | `video-meta.json` 필드 |
|---|---|---|
| 느린 걷기 재탐색 | 첫 탐색의 이음새가 "닫히지 않으면"(이음새 ≥ 보통 한 스텝의 60% 또는 동작 범위의 절반도 못 덮음) 썸네일을 8×8로 줄이고 2프레임 창으로 클립 길이까지 다시 찾는다. 뚜렷이 나을 때만 채택 | `research: "wider"` |
| 크기 고정 | 첫 프레임 대비 피사체 높이가 4% 넘게 변하면(카메라 쪽으로 걷는 클립 등) 모든 프레임의 피사체를 첫 프레임 높이로 되돌린다. 아래 가운데를 기준으로 확대하고 캔버스를 넓혀 머리가 잘리지 않는다 | `size_hold: {applied, max_ratio}` |
| 2주기 의심 | 고른 컷이 1/2·1/3 길이에서도 잘 닫히면 "2·3주기가 들어 있을 수 있음"으로 **기록만** 한다(픽셀의 말만 믿고 자르지 않음). 사용자가 `cycles=N`으로 알려 주면 한 주기만 자른다 | `cycles_suspected` |
| 유지 그림 | 같은 그림을 2~3프레임씩 보여 주는 클립은 그림 단위로 읽는다(고른 프레임이 같은 그림의 중복이 되지 않음) | `held: {ratio, drawings}` |
| 이음새 튐 | 닫는 한 프레임 스텝 ÷ 컷 안의 가장 큰 정상 스텝(프레임 위쪽 절반에서). ≈1이면 정상, 훨씬 크면 튐. 위쪽을 읽을 수 없으면 `null` | `seam_pop`, `seam_ratio` |
| 명시 길이 창 | plan 액션의 `min_len`·`max_len`(원본 프레임 수)이 모든 경로(첫 탐색·재탐색)에서 주기의 범위를 제한한다 | — |

plan 액션 키: `cycles`(1~4), `min_len`, `max_len` — `plan --set walk.cycles=2 --set walk.max_len=40`처럼 쓴다.

### 7.1 걷기·달리기 리포트 (발 디딤·점프 지표)

looping 걷기·달리기(단일 방향)는 컷의 시작을 발이 땅에 닿는 프레임으로 옮기고(허용: 반 주기 안, 클립 안), 몸이 얼마나 튀는지 기록한다. 모두 `video-meta.json`에 남고 스튜디오 attempt 상세 API(`video_meta`)가 노출한다.

| 필드 | 뜻 |
|---|---|
| `start_foot_source` | `legs_spread`(측면: 두 다리가 가장 벌어진 프레임) · `legs_lift`(앞/뒷모습: 두 발 높이가 같은 프레임) · `none`(다리가 없는 몸 — 하체 폭이 평균의 15% 넘게 변하지 않거나 발 높이 차이가 키의 4% 미만) · `null`(걷기·달리기가 아님). `none`이면 시작은 그대로다 |
| `foot_shift` | 시작을 옮긴 프레임 수 |
| `jolt_index` | 몸 전체 질량 중심 궤적의 2차 차분 크기 평균(루프를 닫아서) ÷ 피사체 키. 합성 클립 기준 정지한 걷기 ≈ 0.02, 매끈한 상하 움직임 ≈ 0.015, 프레임마다 튀는 움직임 ≈ 0.15 (실제 클립 값은 미검증) |
| `head_move` | 머리 중심의 최대 이동폭 ÷ 키 |

plan `max_jolt`를 지정하면(`--set walk.max_jolt=0.08`) 처리(`process`)할 때 지표가 그 값을 넘으면 `process.json`의 `warnings`에 `jolt_exceeded: …`가 들어간다. 지정하지 않으면 경고는 없다(게이트 없음). QC 항목이 아니라 처리 경고다.

## 8. 프레임 보간(RIFE) — 선택

걷기·달리기 루프에서 영상 모델이 한 프레임만 몸을 엉뚱한 곳에 그리면(점프 프레임) 모든 정지 화면은 멀쩡한데 재생하면 덜컥거린다. 그런 프레임을 **이웃 두 프레임 사이로 다시 만드는** 데 광학 흐름 보간기 [rife-ncnn-vulkan](https://github.com/nihui/rife-ncnn-vulkan)을 쓴다. **선택 기능**이고, 없어도 모든 경로가 동작한다(아래 표).

### 설치와 확인 (자동 설치는 하지 않는다)

```bash
# 1) 릴리스를 직접 받아 풀고(공식 저장소 Releases, 모델 폴더 rife-v4.6 포함) 실행 파일 위치를 알려 준다
export SPRITE_FORGE_RIFE_BIN=/path/to/rife-ncnn-vulkan      # 또는 PATH에 rife-ncnn-vulkan
export SPRITE_FORGE_RIFE_MODEL=/path/to/rife-v4.6            # 선택: 모델 폴더 (실행 파일 옆의 기본 모델을 쓰면 생략)

# 2) 확인
uv run python sprite-animation-forge/scripts/forge.py doctor     # "rife": {"installed": true, "bin": "...", "source": "env"}
```

- 찾는 순서: `SPRITE_FORGE_RIFE_BIN`(실행 가능한 파일) → `PATH`의 `rife-ncnn-vulkan`. `doctor`·`/api/health`의 `rife`는 정보용이라 없어도 `ready`·`warnings`가 달라지지 않는다.
- **확인 필요**: 이 저장소는 실제 RIFE를 실행해 보지 못했다. 호출 인자(`-0 -1 -o -s [-m]`)와 모델 폴더 규약은 공식 문서·sprite-gen 설명 기준이며, 첫 사용 때 `forge.py generate`가 `rife_failed`로 끝나면 바이너리를 직접 실행해 인자를 확인한다(호출은 `interpolate.RifeNcnn._argv` 한 곳). 문서의 맥(Apple GPU)·리눅스(llvmpipe) 속도 수치는 sprite-gen 측정값이며 이 저장소 측정이 아니다.

### 동작: plan `repair` (걷기·달리기 루프에만 적용)

| `repair` | RIFE 있음 | RIFE 없음 |
|---|---|---|
| `auto`(기본) | 점프 프레임이 있으면 다시 만든다 | 원본 그대로 자르고 `video-meta.json`·`process.json` 경고에 `rife_unavailable: …`. **RIFE는 프레임을 만들어야 할 때만 찾는다**(매끈한 걷기는 찾지도 않음) |
| `on` | 위와 같음 | `rife_missing` 오류(종료 코드 3) |
| `off` | 보정 안 함 | 보정 안 함 |

RIFE가 **있는데 실패하면**(Vulkan을 못 여는 바이너리 등) 모든 모드에서 `rife_failed` 오류다 — 경고로 두면 고장난 설치가 숨는다.

판정과 보정 규칙(`video_repair.py`):
- 줄이기 *전의 조밀한 컷*(≥ 12프레임)에서 읽는다. 6~8프레임으로 줄인 시퀀스는 너무 성겨 정상 걷기도 점수가 높다. 컷이 12프레임보다 짧으면 시도하지 않는다(`jump_repair.why: cut_too_short`).
- 점프 프레임 = 두 이웃 사이 거리는 작은데 자기와 이웃 사이 거리는 큰 프레임(프리멀티플라이 RGBA 기준 `(d₁+d₂)/max(d_이웃간, 0.5×보통 스텝) ≥ 2.5`, 그리고 보통 스텝의 1.2배 넘게 어긋남). 스윙의 극점은 걸리지 않는다.
- 다시 만든 프레임은 컷의 최악 점수가 90% 아래로 내려갈 때만 채택한다(원본 상자·기준으로 측정). 아니면 `jump_repair.unmade`에 남기고 원본을 둔다. 루프당 최대 3프레임.
- RIFE는 알파를 모르므로 한 프레임을 두 이미지(색 — 몸의 자기 색을 투명 영역으로 번지게 한 것 / 커버리지 — 회색 이미지)로 따로 보간해 합친다. 커버리지 2/255 미만은 버려 흐린 후광이 생기지 않는다.

### 유령 프레임

영상 모델이 두 포즈를 겹친 프레임(크로스페이드)을 내놓는 경우가 있다. 크로마 알파는 키 색 배경에서 포화돼 이런 프레임도 불투명해 보이므로 **키 색까지의 거리**로 "반쯤만 있는 화소" 비율을 잰다(정상 프레임 ≈ 0, 두 포즈를 섞은 프레임 0.3~0.5). 보통 비율의 1.8배 이상이고 0.12 이상이면 유령이다.

- 옆의 깨끗한 프레임이 있으면 그 프레임에 자리를 내준다(이전 우선, 없으면 다음). `video-meta.json`의 `ghost.given_way`.
- 옆에 깨끗한 프레임이 없으면 그대로 두고 **재촬영 사유** `filmed-ghost`를 `retake`에 남기며 처리 경고 `retake: filmed-ghost (frame N)`가 생긴다.
- 다시 만든(보간) 프레임이 두 그림을 크로스페이드하면 측정해 `jump_repair.crossfade`에 이름만 붙이고 버리지 않는다.
