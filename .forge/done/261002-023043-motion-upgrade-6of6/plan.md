<!-- forge-slug: motion-upgrade-6of6 -->
<!-- task: 29 -->
<!-- part: 6/6 -->
<!-- tdd: on -->
# 움직임 개선 6/6: 동영상 → 스프라이트 변환과 `method=video` 활성화

## Goal / Non-goals
- Goal: `video` 생성 방식을 연결된 동영상 provider가 있을 때 선택 가능하게 한다. 흐름: 첫 프레임 준비(대표 방향 채택 idle 프레임 또는 reference를 액션별 여백 캔버스에 배치, 배경을 순수 키 색으로 칠함; idle·one-shot은 마지막 프레임을 첫 프레임으로 고정) → 동영상 생성(provider) → `ffmpeg`/`ffprobe`로 전체 프레임 추출(실제 fps) → 루프 구간 선택(loop 액션: 썸네일 거리 행렬로 주기·이음새 순위, 1.5주기 오인 방지 규칙; one-shot: 처음~복귀 구간) → plan의 `frames` 수로 균등 축소 → 프레임별 크로마 배경 제거(테두리에서 키 색 감지) → 공통 정렬(1/6의 register, 선형 드리프트만 제거) → 기존 attempt 구조로 저장(`raw.mp4`, `video-meta.json`, frames/sheet/process.json/qc-report) → QC·채택·뷰어·export 그대로. CLI `generate`·API generate Job·일괄 생성에서 `method=video` 처리, 플랜 화면 select의 video 옵션 활성(연결 시), 스튜디오 attempt에 동영상 미리보기 링크.
- Non-goals: 다른 동영상 provider, 프레임 보간(RIFE 등), 동영상 편집·연장 API, 배경 매팅 모델.

## Source of truth
- Glossary terms: 생성 방식 (method)
- Related ADRs: none (근거: sprite-gen video-pipeline·video/loop.py — 캔버스 패딩·키 정규화·first=last 고정·주기/이음새 루프 선택·선형 드리프트 개념; 재구현)
- Definition of Done:
  - TDD 진행
  - `uv run pytest -q -k "video_sprite or video_loop"` passed ≥ 12 (baseline 0 — 순방향): 합성 동영상(테스트가 ffmpeg로 생성하는 키 색 배경 위 주기 운동 클립)에서 주기 검출·이음새 비율·N프레임 축소·배경 제거 결과(모서리 알파 0)·정렬·attempt 파일 구성, one-shot 구간 선택, ffmpeg 부재 시 `ffmpeg_missing` 오류, provider 미연결 시 `method_unavailable`, 가짜 동영상 provider로 CLI·API Job·일괄 생성 끝까지
  - 플랜 화면 video 옵션 활성/비활성 Vitest ≥ 2, e2e ≥ 1(가짜 동영상 provider로 video 생성→채택→뷰어 재생), 전체 회귀 통과
  - 실사용 확인 방법 기록(xAI 키 연결 후 walk를 grid/video로 만들어 뷰어 비교, 예상 비용 확인 절차)

## Work slices
- [ ] S1. 첫 프레임 캔버스 준비 + 프레임 추출(ffmpeg) — completion criterion: 테스트 통과
- [ ] S2. 루프/구간 선택 + N프레임 축소 + 배경 제거 + 정렬 → attempt 저장 — completion criterion: video_sprite 테스트 통과 (depends: S1)
- [ ] S3. `method=video` 활성화(CLI·API·일괄 생성·플랜 화면·스튜디오 미리보기) + e2e — completion criterion: Vitest·e2e 통과 (depends: S2)
