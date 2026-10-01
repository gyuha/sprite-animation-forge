# RUN — M4-c: Job 큐 · SSE · 생성 엔드포인트 · 기동 시 복구

서브에이전트 1개가 구현, 오케스트레이터가 DoD 재실행으로 확인.

## 슬라이스 결과
- S1 `jobs.py`(모델·FIFO 단일 워커·취소·상태 전이) — ✅ as planned
- S2 `sse.py` + `GET /api/events`, `/api/jobs*` — ✅ as planned
- S3 생성 엔드포인트 4종(reference/generate, identity/analyze, actions/*/generate, generate-all) — ✅ as planned (202 응답의 `attempt`는 null, 아래 참고)
- S4 기동 시 복구(`recovery.py`, running→interrupted, 죽은 PID `.lock` 정리) — ✅ as planned

## DoD baseline → after
- `webui/server/tests -k "jobs or sse or interrupted or cancel"`: 1 → 41 passed (≥12)
- 전체: 707 → 749 passed, 4 skipped, 2 deselected

## 판단·가정 (프런트가 알아야 함)
- Job JSON(모든 필드 항상 존재): id `job_<12hex>`, type, character, action|null, direction|null, attempt|null, state(queued|running|succeeded|failed|canceled|interrupted), stage(starting|session|generating|collecting|processing|qc), queue_position, created_at/started_at/finished_at, elapsed_s, expected_s(호출당 90), progress{done,total,current}, log(최근 50), result, error{code,message,detail}.
- SSE: 이벤트명 항상 `job`, `data`는 Job 스냅샷(log 제외) + `kind`(state|stage|log|update|queue|tick) + `message`(한국어 단계 문구) + `line`(log일 때). 전체 스냅샷이라 id로 upsert 가능. 연결 시 `: connected`, 15초마다 `: ping`. 재연결은 EventSource 백오프 후 `GET /api/jobs?active=1`로 재동기화(서버는 같은 boot 접두사의 `Last-Event-ID`에 한해 최대 500건 재전송).
- 202 본문 `{"job": Job, "attempt": null}` — Core가 attempt를 codex 락 안에서 할당하므로 요청 시점엔 미정(Job.attempt가 실행 시작 후 채워짐). 취소: queued 즉시, running은 SIGTERM→5초→SIGKILL(응답까지 최대 ~8초), identity_analyze는 running 취소 불가(409 `not_cancelable`).
- 배치: unit 순서는 Core `plan.units`(액션별 down→right→up, mirror 제외), 실패 unit은 `review`로 표시하고 계속, QC fail은 자동 재처리 최대 2회 → 재생성 `max_regenerations`. `interrupted` Job 상태는 정상 종료 시 queued/running 잔여분에만 사용, 크래시 후에는 attempt `generation_status: interrupted`로 복구(attempts 목록/상세, manifest, `status.units[].latest_generation_status`).
- 서버 테스트에서 lifespan(워커·복구)이 돌려면 `with client:` 필요 — `jc` 픽스처 사용. SSE 테스트는 TestClient가 스트리밍 불가라 실제 uvicorn 스레드 사용.
- 기존 테스트 1건 수정: `test_cli_process_is_deterministic`가 attempt 디렉터리 전 파일을 비교했는데 `.lock`에 PID가 기록되도록 Core(`fsutil.attempt_lock`)를 하위 호환 변경했으므로 `.lock`을 비교에서 제외(산출물 아님). 팩토리: `create_app(..., provider_factory=None)`. fake codex에 가산적 `FAKE_CODEX_DELAY_S` 추가.
