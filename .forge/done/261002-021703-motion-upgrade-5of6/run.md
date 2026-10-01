# 실행 기록 — 움직임 개선 5/6: 동영상 provider + API 연결 안내 (task #28)

## 한 일
- `providers/video_base.py`: `VideoRequest/VideoResult/VideoProvider`, `is_mp4`(ftyp).
- `providers/xai_video.py`: 인증(auth.json → XAI_API_KEY, 주입 토큰), POST 생성 → request_id 폴링 → mp4 다운로드(서명 URL에는 토큰 미전송) → ftyp 검증 → 원자 저장, 429/5xx 지수 백오프(3회), 취소·타임아웃. `transport` 주입형(stdlib urllib 기본, 신규 의존성 없음).
- `providers/fake_video.py`(`FakeXaiTransport`: ok/fail/pending/rate_limit/bad_file/unauthorized), `video_factory.make_video_provider` (`SPRITE_FORGE_VIDEO_PROVIDER=fake` 오프라인용).
- `plan.video_method_available()` → provider 연결 여부로 전환(연결되면 plan에서 method=video 허용; 변환은 #29).
- doctor·`/api/health`에 `video` 필드 (ready/warnings에는 영향 없음), 상태 화면 "동영상 방식 (선택)" 카드.
- `docs/13-video-api-setup.md` + docs/README 목록, live 테스트 `test_live_video_contract.py`(collect-only 확인).
- conftest(코어·서버)에 실제 xAI 인증 격리 autouse 픽스처.

## 검증
- pytest 876 passed, Vitest 210 passed(+2), typecheck OK, e2e 11 passed. `-k video_provider` 17건. 실제 xAI 호출 0회.

## 주의 / 미검증
- xAI 엔드포인트·모델명(`grok-imagine-video-1.5`)·요청 필드(`image.url`, `last_image`)·응답 필드(`request_id`, `status: done`, `video.url`)·`auth.json` 키 이름은 sprite-gen 참고 기억 기반, 실계정 미검증 [낮음]. docs/13에 "확인 필요"로 표기, live 테스트로 확인 필요.
- `video_method_available()`이 true가 되면 plan이 method=video를 받지만 생성은 아직 불가(#29에서 구현). 그 사이 키를 연결해 둔 사용자가 video를 고르면 generate 단계에서 막혀야 함 → #29에서 처리.
