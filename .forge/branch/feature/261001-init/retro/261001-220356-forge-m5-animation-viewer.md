# 2026-10-01 — 애니메이션 뷰어: 움직임 검사는 다중 표본, 그리고 git add -A의 범위

## Plan vs actual
- What went as planned: `/c/:cid/view` 타일 격자(공유 rAF 시계), 진입 링크, Vitest +25, e2e +3, 실제 `sprites/green` 20/20 타일 확인.
- Divergences: (1) C4의 "프레임이 바뀜"을 1.5초 간격 두 표본으로 비교해 12/20만 감지 — 주기와 표본 간격이 맞물려 같은 프레임에서 만난 것. 구현은 정상이었고 검사가 틀렸음(250ms×10 표본으로 교체). (2) 계약 커밋에서 `git add -A`가 직전 요청들의 미커밋 변경(Taskfile, `--host`, vite 프록시)까지 쓸어 담아 커밋 메시지가 내용과 어긋남 → amend로 메시지 보정.

## Learnings
- Do differently next time: 시간에 따라 변하는 값을 검사할 때는 두 시점 비교 대신 여러 표본의 서로 다른 값 개수를 본다. 루프 시작 전에 워킹트리가 깨끗하지 않으면(`git status`) 계약 커밋 전에 그 변경을 먼저 별도 커밋하거나 `git add`를 경로로 한정한다 — fg-loop의 driveCommit 진입 검사와 같은 원칙을 수동 커밋에도 적용.

## Doc updates
- CONTEXT.md promotion: none
- ADR added: none
