<!-- forge-slug: motion-upgrade-5of6 -->
<!-- task: 28 -->
<!-- part: 5/6 -->
<!-- tdd: on -->
# 움직임 개선 5/6: 동영상 provider (xAI Grok Imagine) + API 연결 안내

## Goal / Non-goals
- Goal: `providers/video_base.py`의 `VideoProvider` 인터페이스(요청: 첫 프레임 이미지·선택적 마지막 프레임 고정·프롬프트·길이·해상도·출력 경로 / 결과: status·mp4 경로·error_code·meta, check/cancel), 테스트용 가짜 동영상 provider(가짜 HTTP 서버 또는 주입 가능한 transport로 xAI API 응답 흉내: 생성 요청 → 폴링 → mp4 다운로드, 실패·타임아웃·429 재시도 모드), xAI 구현 `providers/xai_video.py`(`POST https://api.x.ai/v1/videos/generations`·`GET /v1/videos/{id}` 폴링, 인증: `~/.grok/auth.json` 우선 → `XAI_API_KEY`, 모델명·엔드포인트는 설정값, mp4 `ftyp` 검증·원자적 저장, 레이트 리밋 고려), doctor/`/api/health`에 동영상 연결 상태(`video: {provider, configured, auth}`) 추가, 상태 화면 표시. `docs/13-video-api-setup.md`: 무엇을 가입하고(SuperGrok 또는 xAI 콘솔), 키 발급·`grok` CLI 설치·`grok login`·환경 변수·확인 명령(`forge.py doctor`)·비용 주의·문제 해결을 단계별로 안내(공식 문서 링크, 확인 안 된 수치는 "확인 필요"로 표기).
- Non-goals: 동영상→스프라이트 변환(다음 작업), `method=video` 활성화, 다른 동영상 provider 구현, 실제 xAI 호출 테스트(`@pytest.mark.live`로 작성만).

## Source of truth
- Glossary terms: 생성 방식 (method)
- Related ADRs: none (근거: sprite-gen gen/video.py — xAI 엔드포인트·인증 우선순위·폴링·ftyp 검증 개념; 재구현, 코드 복사 없음. 모델명·가격은 공식 문서로 확인 필요)
- Definition of Done:
  - TDD 진행
  - `uv run pytest -q -k "video_provider or xai"` passed ≥ 10 (baseline 0 — 순방향): 성공·폴링·실패·타임아웃·429 재시도·잘못된 mp4·인증 우선순위·키 없음 시 `configured: false`, doctor·health 필드, live 테스트는 collect-only
  - 상태 화면 동영상 연결 표시 Vitest ≥ 1, 전체 회귀 통과
  - `docs/13-video-api-setup.md` 존재, `docs/README.md` 문서 목록에 추가, 각 단계에 확인 명령 포함
  - 실제 키 없이 모든 테스트 통과, 실제 xAI 호출 0회

## Work slices
- [ ] S1. `VideoProvider` 인터페이스 + 가짜 provider — completion criterion: 인터페이스 테스트 통과
- [ ] S2. xAI 구현(인증·생성·폴링·다운로드·재시도) — completion criterion: 가짜 transport 테스트 통과 (depends: S1)
- [ ] S3. doctor·health·상태 화면 연결 상태 + live 테스트(collect-only) — completion criterion: 테스트 통과 (depends: S2)
- [ ] S4. API 연결 안내 문서 — completion criterion: 문서 존재·목록 반영
