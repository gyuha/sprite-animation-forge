# 실행 기록 — 움직임 개선 6/6: 동영상 → 스프라이트 변환과 method=video 활성화 (task #29)

## 한 일
- `video_loop.py`: 거리 행렬, 루프 선택(3프레임 창 이음새 + 최단 주기 우선 → 반주기·1.5주기 오인 방지), one-shot 복귀 구간, N프레임 균등 축소(round_half_up).
- `video_sprite.py`: 첫 프레임 캔버스(키 색, 캐릭터 가운데 ~60%), ffmpeg/ffprobe 프레임 추출(`ffmpeg_missing`·`video_decode_failed`), 프레임별 배경 정규화(테두리 색 추정 → 알파 0 영역을 정확한 키 색으로) 후 plan 격자에 맞춘 `raw.png` 시트 조립 → 기존 파이프라인(chroma→split→scale→align(register)→QC)이 그대로 처리.
- `generation.generate_unit`: `method=video` 분기(`_generate_video_unit`). attempt 파일: `prompt.txt`, `first-frame.png`, `raw.mp4`, `video-meta.json`(선택 인덱스·fps·고정 여부), `raw.png`, `generation.json`(method=video, `video_prompt@1`). Codex 락은 attempt 할당 때만 잡음(영상 생성 중 Codex 호출 비차단). idle·one-shot은 마지막 프레임 고정.
- `prompt.build_video_prompt` + 템플릿 2개, docs/04 §9.
- plan: `method=video`는 방향이 둘 이상이면 `invalid_params`(서버 PUT도 동일).
- 서버: Job이 영상 provider 사용(취소 전파·진행 메시지), `generate`/`generate-all`이 단위별 필요 provider만 요구(영상 단위는 Codex 불필요), `/files`에 `.mp4`, AttemptFiles.video.
- UI: 플랜 video 옵션(연결·단일 방향일 때만 활성, 사유 표시), 스튜디오 "생성된 동영상 보기" 링크.
- 가짜 provider가 실제 mp4를 생성(`make_bobbing_mp4`: 첫 프레임이 상하·상체 좌우로 흔들림) → CLI·Job·배치·e2e가 오프라인으로 전 구간 실행.

## 검증
- pytest 903 passed (video_sprite/video_loop 23건, video_provider 18건), Vitest 212, typecheck OK, e2e 12 passed(신규 video.spec). 실제 xAI 호출 0회.

## 주의 / 미검증
- 실제 xAI 클립의 품질·배경 안정성은 미검증 [낮음]. 배경 정규화는 테두리 색 중앙값을 배경으로 가정하므로 영상 배경이 흔들리면 알파가 지저분할 수 있음 — 그때는 `process --set t_in/t_out`.
- 주기 검출 임계(SEAM_SLACK 1.25, 창 3프레임)는 합성 클립으로만 보정됨 [낮음]. 실제 걷기 클립으로 `video-meta.json`의 `span`·`indices`를 확인할 것.
- 방향 2개 이상(탑다운 등) 플랜은 video 불가(첫 프레임이 방향을 고정). 필요하면 방향별 정지 이미지를 Codex로 먼저 만든 뒤 영상화하는 후속 작업 필요.
- 영상 방식은 `recovery` 코드(프롬프트 복구 문구)를 사용하지 않음 — 일괄 생성의 재생성은 같은 프롬프트로 다시 요청.
- 비용: 호출당 과금(가격 확인 필요). 일괄 생성은 영상 단위마다 1회 호출하므로 먼저 단일 액션으로 확인.

## 실사용 확인 방법
1. docs/13 따라 키 연결 → `forge.py doctor`의 `video.configured: true`.
2. `uv run pytest -m live -k video`(비용 발생, 2초·480p 1건)로 API 계약 확인.
3. 플랜 화면에서 walk를 `동영상 (API)`로 → 스튜디오 생성 → 클립 링크·`video-meta.json` 확인 → 같은 캐릭터의 grid walk와 뷰어에서 비교.
