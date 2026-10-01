<!-- forge-slug: forge-m4-jobs-sse -->
<!-- task: 15 -->
<!-- part: 3/8 -->
<!-- tdd: off -->
# M4-c: Job 큐 · SSE · 생성 엔드포인트 · 기동 시 복구

## Goal / Non-goals
- Goal: docs/10 §2·§3·§5.1(Job 계열)·§6·§8, docs/12 M4 2·3·4번. 단일 워커 FIFO 큐(`asyncio.to_thread`), Job 상태 전이(queued/running/succeeded/failed/canceled/interrupted), 취소(queued 제거, running은 `provider.cancel()`), `queue_position`, SSE `/api/events`(이벤트 순서·재연결용 id), `GET /api/jobs`(`?active=1`)·`/jobs/{jid}`·`/jobs/{jid}/cancel`, Job 엔드포인트 `reference/generate`·`identity/analyze`·`actions/{action}/generate`·`generate-all`(방향이 여러 개면 `down → right → up` 순, mirror 파생 unit 제외, batch가 워커 점유), 기동 시 running Job → `interrupted` 복구와 manifest 반영. 모두 가짜 codex로 검증.
- Non-goals: 프런트엔드, 실제 Codex.

## Source of truth
- Glossary terms: none
- Related ADRs: none (docs/10 §2·§3·§6, docs/01 ADR-009)
- Definition of Done:
  - `uv run pytest -q -k "jobs or sse or interrupted or cancel"` 중 web 테스트 → 종료 코드 0, passed ≥ 12 (baseline: 없음)
  - 큐 FIFO·동시 실행 1개, queued 취소·running 취소(프로세스 종료 확인), SSE 이벤트 순서(queued→running→progress→succeeded), 서버 재기동 시 `interrupted` 표시 후 재생성 가능
  - `generate-all`의 unit 순서와 mirror 제외, 실패 unit이 있어도 다음 진행하는 정책(docs/09 §7 확인) 테스트
  - 기존 테스트 전부 통과 유지

## Work slices
- [ ] S1. Job 모델·큐·워커·취소·상태 전이·이벤트 버스 — completion criterion: 큐·취소 테스트 통과
- [ ] S2. SSE 엔드포인트와 Job 조회·취소 API — completion criterion: sse 테스트 통과 (depends: S1)
- [ ] S3. 생성 계열 엔드포인트 4종(generate·analyze·reference generate·generate-all) — completion criterion: 가짜 codex 통합 테스트 통과 (depends: S2)
- [ ] S4. 기동 시 복구(`interrupted`) — completion criterion: interrupted 테스트 통과 (depends: S3)
