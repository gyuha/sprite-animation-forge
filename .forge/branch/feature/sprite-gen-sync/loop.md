# LOOP — sprite-gen(aldegad, 2026-09-30~10-13 변경 v2.12→2.44+) 4개 영역을 재구현해 feature/sprite-gen-sync에 반영
started: 2026-10-13
replan-round: 0
replan-cap: 3
budget-tokens: none
budget-spent: 0 · since: 2026-10-13T10:46:31Z
retro: skip
wall: none

## Stop-condition checks (ALL must pass)
- [x] C1. 기준선 보존 + 회귀 없음: `uv run pytest -m "not live" -q` 통과, 그리고 `comm -23 .forge/branch/feature/sprite-gen-sync/baseline-tests.txt <(uv run pytest -m "not live" --collect-only -q 2>/dev/null | grep '::' | sort) | wc -l` → 0 (기준선 907개 ID가 모두 여전히 수집됨; 승인된 이름 변경은 아래 Authorized scope에 기록)
- [x] C2. 프런트엔드: `pnpm --dir webui/web typecheck && pnpm --dir webui/web test && pnpm --dir webui/web e2e` 통과, Vitest ≥ 212, e2e ≥ 12
- [x] C3. 영상 공급자 견고성: `uv run pytest -q -k sg_provider` passed ≥ 12 (사전: 0건 수집). 마감 시간 하나가 폴링·다운로드·각 읽기를 제한 / 다운로드·완료 응답 이상 시 request_id로 종료 / request_id 재개(CLI+서버) / 오류 본문 키·Bearer·서명 마스킹 / 거절 사유(코드·content policy) 표시
- [x] C4. 이미지 가장자리 스케일: `uv run pytest -q -k sg_resample` passed ≥ 6 (사전: 0건). 합성 키 색 스프라이트를 비정수 배율로 줄여도 불투명 출력 픽셀이 원본 색 범위(채널별 ±2)를 벗어나지 않음, 옛 방식(legacy)은 옵션으로 기존 sha256 핀과 바이트 동일
- [ ] C5. 이미지 경로: `uv run pytest -q -k sg_image` passed ≥ 12 (사전: 0건). 레이아웃 가이드(머리·바닥선, 가이드 이미지 픽셀 검사)·안전 영역 수치 프롬프트·공격 머리 위 여유·앞/뒷모습 유지·손잡이 방향(좌측 직접 생성, 미러 해제)
- [ ] C6. 영상 프롬프트·루프: `uv run pytest -q -k sg_video` passed ≥ 14 (사전: 0건). 시점별 걷기·달리기 문구, 캔버스 여유, 느린 걷기 재탐색, 크기 고정, 2주기 계수, 유지 그림 판정, 이음새 튐, 발 디딤 시작, 점프 지표를 합성 클립으로 검증
- [ ] C7. RIFE·복원: `uv run pytest -q -k sg_rife` passed ≥ 12 (사전: 0건). 보간기 인터페이스·미설치 폴백(경고 후 원본 절단)·점프 보정·유령 프레임 검사·재촬영 사유·원본 복원을 스텁 보간기로 검증. 실제 RIFE 없이 전체 테스트 통과
- [ ] C8. 매핑 표: `uv run python sprite-animation-forge/tests/sync_matrix.py --final` exit 0 — docs/14-sprite-gen-sync.md의 모든 (sprite-gen 기능 → 구현 → 테스트 ID)가 실제 존재·통과하고, 영역 A~D마다 ≥1행, 미채택 표는 사유와 함께 비어 있지 않음 (사전: 파일 없음)
- [x] C9. 브랜치 불변: `[ "$(git rev-parse main)" = d2346aac544661f2a44596a9c7ed1e2e6541b5b4 ] && [ "$(git rev-parse origin/main)" = d2346aac544661f2a44596a9c7ed1e2e6541b5b4 ] && [ "$(git rev-parse feature/xai-video)" = b2db9fb47f949c729a1992fd65387bc1f7dd017a ] && [ "$(git branch --show-current)" = feature/sprite-gen-sync ]` exit 0 (회귀 가드: 사전부터 통과)

## Check progress
- C1: pass ×0 · regressed: ×0 · last-evidence: "968 passed, 4 skipped, 3 deselected, 1 warning in 184.59s (0:03:04); missing baseline ids=0"
- C2: pass ×0 · regressed: ×0 · last-evidence: "vitest=213 e2e=12"
- C3: pass ×0 · regressed: ×0 · last-evidence: "-k sg_provider: passed=33 (need >= 12) rc=0"
- C4: pass ×0 · regressed: ×0 · last-evidence: "-k sg_resample: passed=27 (need >= 6) rc=0"
- C5: pending ×0 · regressed: ×0 · last-evidence: "-k sg_image: passed=0 (need >= 12) rc=5"
- C6: pending ×0 · regressed: ×0 · last-evidence: "-k sg_video: passed=0 (need >= 14) rc=5"
- C7: pending ×0 · regressed: ×0 · last-evidence: "-k sg_rife: passed=0 (need >= 12) rc=5"
- C8: pending ×0 · regressed: ×0 · last-evidence: "rows: {'A': 11, 'B': 4, 'C': 0, 'D': 0} not adopted: 0 | ERROR area C: no rows | ERROR area D: no rows | ERROR not-adopted table has 0 complete rows, need >= 5"
- C9: pass ×0 · regressed: ×0 · last-evidence: "branches unchanged"

## Authorized replan scope
- 위 체크에 직접 연결되는 repo 내부 코드·테스트·문서 변경만 (sprite-animation-forge/, webui/, docs/, README.md, .forge 계획·기록). 실패 체크마다 수정 계획을 자동 생성할 수 있다.
- 옛 동작은 옵션으로 보존한다(align=per_frame, resample=legacy). 기존 테스트의 기대값 변경은 새 기본값 도입으로 불가피한 경우만 허용하고 run.md에 사유를 적는다. 테스트 삭제·이름 변경 금지(필요 시 이 목록에 승인 기록: 없음).
- 실제 xAI·Codex 호출 금지(live 테스트는 collect-only), RIFE 바이너리 설치·외부 다운로드 금지, push 금지, main·feature/xai-video 변경 금지, sprite-gen 코드 복사 금지(Apache-2.0이라도 ADR-007대로 문서 읽고 재구현, 상수·문구는 측정·의역).
- always-halt action classes (safety wall — default set): prod data mutation/deletion · deploy/release/publish · outbound external comms (email · messaging · third-party write APIs) · irreversible VCS/file destruction (force-push · history rewrite · mass deletion) · financial/payment · secret/permission change · privacy-data exposure
- 미채택(사유 기록 대상, docs/14): pixel-draw(Anthropic API 키 필요·유료), 방향 세트 정렬·video-set-sheet(영상은 단일 방향만), video-follow(부드러운 부위 추종), --body-plan(말 등 비인간), `rife install` 자동 설치(외부 다운로드 금지)

## Tasks
- sprite-gen-sync-1of11
- sprite-gen-sync-2of11
- sprite-gen-sync-3of11
- sprite-gen-sync-4of11
- sprite-gen-sync-5of11
- sprite-gen-sync-6of11
- sprite-gen-sync-7of11
- sprite-gen-sync-8of11
- sprite-gen-sync-9of11
- sprite-gen-sync-10of11
- sprite-gen-sync-11of11
