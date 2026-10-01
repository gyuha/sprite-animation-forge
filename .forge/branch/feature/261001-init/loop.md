# LOOP — 만들어진 캐릭터의 애니메이션을 한눈에 재생해 확인하는 "애니메이션 뷰어" 화면을 추가한다
started: 2026-10-01
replan-round: 0
replan-cap: 3
budget-tokens: none
budget-spent: 0 · since: 2026-10-01T21:10:00+0900
wall: none

## Stop-condition checks (ALL must pass)
모든 명령은 저장소 루트(`/Users/gyuha/workspace/sprite-animation-forge`)에서 실행하며 `/tmp/forge-drive/checks3.py`가 수행한다(구현 측이 약화할 수 없게 검사 코드는 저장소 밖에 둔다).
- [ ] C1. 회귀 없음: `uv run pytest -m "not live" -q` → 종료 코드 0, `passed` ≥ 750, `failed`/`error` 0
- [ ] C2. 프런트 정적 검증: `pnpm --dir webui/web typecheck`·`build`·`test` 모두 종료 코드 0, Vitest passed ≥ 160(기존 146 + 뷰어 신규 ≥ 14), `src/pages/Viewer.tsx` 존재, `routes.tsx`에 `/c/:cid/view` 라우트 존재
- [ ] C3. E2E(가짜 codex): `pnpm --dir webui/web e2e` → 종료 코드 0, Playwright passed ≥ 6(기존 4 + 신규 ≥ 2). 신규는 (a) 배치로 만든 캐릭터의 뷰어에서 모든 unit 타일이 **실제로 재생**됨: 타일 수 == 채택 unit 수, 각 타일 캔버스에 투명하지 않은 픽셀이 그려져 있고, 일정 시간 안에 `data-frame`이 바뀜(정지 이미지가 아님), (b) 대시보드 카드·내보내기·스튜디오에서 뷰어로 이동하는 링크가 동작함
- [ ] C4. 실제 데이터 검증(읽기 전용): `sprites/green`(20 unit 채택, 탑다운 5액션×4방향)을 `--root sprites`로 서버에 띄워 Playwright(chromium)로 `/c/green/view`를 열었을 때 타일 20개(+각 액션·방향 라벨), 모든 타일 캔버스에 불투명 픽셀이 존재하고 1.5초 안에 모든 타일의 `data-frame`이 최소 1회 변하며 콘솔 오류 0건, `left`(mirror) 타일 포함. 스크린샷을 `/tmp/viewer-green.png`로 저장해 사람이 확인 가능
- [ ] C5. 미채택·누락 처리: Vitest 또는 E2E로, 채택되지 않은 unit은 재생 타일 대신 "미채택"(스튜디오로 이동하는 링크) 플레이스홀더로 표시됨을 검증(`data-testid="viewer-tile-missing-<unit>"`)

## Check progress (모든 stop-condition 실행 뒤 갱신)
- C1: fail ×0 · regressed: ×0 · last-evidence: "미실행" · tried:
- C2: fail ×0 · regressed: ×0 · last-evidence: "미실행" · tried:
- C3: fail ×0 · regressed: ×0 · last-evidence: "미실행" · tried:
- C4: fail ×0 · regressed: ×0 · last-evidence: "미실행" · tried:
- C5: fail ×0 · regressed: ×0 · last-evidence: "미실행" · tried:

## Authorized replan scope
- 실패한 stop-condition 검사에 직접 대응하는 fix-forward 작업만 자동 생성한다. 구현 대상은 `webui/web/`(뷰어 페이지·컴포넌트·라우트·링크·테스트·e2e), 필요 시 `webui/server/`의 하위 호환 최소 변경(예: 읽기 전용 응답 필드 추가), `Taskfile.yml`로 한정한다.
- 범위 제외: GIF/영상 내보내기 기능 추가, 편집·재생성 기능 변경, Core(`sprite_forge`) 변경, `sprites/` 실제 데이터 수정(C4는 읽기 전용).
- always-halt action classes (safety wall — 기본 7종): prod data mutation/deletion · deploy/release/publish · outbound external comms (email · messaging · third-party write APIs) · irreversible VCS/file destruction (force-push · history rewrite · mass deletion) · financial/payment · secret/permission change · privacy-data exposure
- 추가 제한: push하지 않는다(commit만). 실제 `codex`는 호출하지 않는다. `sprites/` 아래 파일을 쓰지 않는다.

## Tasks
- forge-m5-animation-viewer
