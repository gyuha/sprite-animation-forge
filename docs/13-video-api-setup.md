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
| `video_failed` | 서버가 생성 실패/만료 보고 | 프롬프트 변경(콘텐츠 정책 가능), 재시도 |
| `video_timeout` | 제한 시간(기본 600초) 내 미완료 | 재시도, 해상도 낮추기 |
| `video_bad_response` / `video_bad_file` | 응답·파일 형식이 예상과 다름 | API 변경 가능성 — 5단계 live 테스트 결과를 이슈로 남긴다 |

## 참고

- 구현: `sprite_forge/providers/video_base.py`(인터페이스), `xai_video.py`(xAI), `fake_video.py`(테스트용 가짜 transport).
- 설계 근거: 생성 방식(method)은 `.forge/CONTEXT.md`, 참고 구현은 <https://github.com/aldegad/sprite-gen>(Apache-2.0, 코드 복사 없이 재구현).
