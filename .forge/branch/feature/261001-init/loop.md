# LOOP — docs/ 설계 중 M0~M3(Core 파이프라인 · Codex provider(가짜 codex) · 복구 · Export · SKILL.md)를 구현한다
started: 2026-10-01
replan-round: 0
replan-cap: 3
budget-tokens: none
budget-spent: 0 · since: 2026-10-01T10:13:50+0900
wall: none

## Stop-condition checks (ALL must pass)
모든 명령은 저장소 루트(`/Users/gyuha/workspace/sprite-animation-forge`)에서 실행한다.
- [x] C1. `uv run pytest -m "not live" -q` → 종료 코드 0, `passed` ≥ 150, `failed`/`error` 0 (개수 하한은 빈 테스트로 통과하는 것을 막는 장치)
- [ ] C2. 인수 시나리오 6종(docs/11 §5의 1~6)이 각각 테스트로 존재하고 통과한다: `uv run pytest -v -q -k "scenario" 2>&1` 출력에 `scenario_1`~`scenario_6` 각각이 `PASSED`로 최소 1건, 종료 코드 0 (시나리오 1·2·6 = 수동 raw/가짜 codex로 CLI end-to-end, 3 = hero 번들 export 산출물 구조 검증, 4 = QC-07 preserve > fit 대조, 5 = 복구 권장 1순위 3종)
- [ ] C3. 결정성: `uv run pytest -q -k determinism` → 종료 코드 0, `passed` ≥ 1 (같은 입력 `process` 2회의 모든 출력 sha256 동일)
- [ ] C4. 스키마: `uv run pytest -q -k schema` → 종료 코드 0, `passed` ≥ 5 (animation-plan · character-profile · character-scale-profile · qc-report · manifest 산출물이 `schemas/*.schema.json` 검증을 통과)
- [ ] C5. Skill 배포 단위 자급성: `sprite-animation-forge/`를 임시 디렉터리에 복사한 뒤 복사본의 `scripts/forge.py`를 저장소 환경으로 실행(`uv run --project <저장소 루트> python <복사본>/scripts/forge.py --help`, 실행 위치는 저장소 밖 임의 디렉터리)했을 때 종료 코드 0이고 출력에 `doctor init reference identity plan prompt generate import-raw process accept export status` 12개 명령이 모두 있으며, `SKILL.md`에 frontmatter `name:`·`description:`이 있고 `references/`에 7개 파일(animation-rules, prompt-rules, character-consistency, qc-rules, codex-image, phaser-export, examples)이 모두 존재
- [ ] C6. 가짜 codex provider 계약: `uv run pytest -q -k "codex_cli"` → 종료 코드 0, docs/11 §3.3의 9개 모드(success·no_rollout·no_image·multiple_images·image_gen_failed·exit_1·hang·invalid_png·config_warnings) 각각에 대응하는 테스트가 `PASSED` (`-v` 출력에서 모드 이름 9개 모두 확인)

## Check progress (모든 stop-condition 실행 뒤 갱신)
- C1: pass ×0 · regressed: ×0 · last-evidence: "pytest not-live rc=0 passed=237" · tried:
- C2: fail ×4 · regressed: ×0 · last-evidence: "scenario rc=5 passed=0 missing=[1, 2, 3, 4, 5, 6]" · tried:
- C3: fail ×4 · regressed: ×0 · last-evidence: "determinism rc=5 passed=0" · tried:
- C4: fail ×4 · regressed: ×0 · last-evidence: "schema rc=5 passed=0" · tried:
- C5: fail ×4 · regressed: ×0 · last-evidence: "help rc=2 missing=['doctor', 'init', 'reference', 'identity', 'plan', 'prompt', 'generate', 'import-raw', 'process', 'accept', 'export', 'status']; skill_frontmatter=False missing_refs=['animation-rules', 'prompt-rules', 'character-consistency', 'qc-rules', 'codex-image', 'phaser-export', 'examples']" · tried:
- C6: fail ×4 · regressed: ×0 · last-evidence: "codex_cli rc=5 passed=0 missing_modes=['success', 'no_rollout', 'no_image', 'multiple_images', 'image_gen_failed', 'exit_1', 'hang', 'invalid_png', 'config_warnings']" · tried:

## Authorized replan scope
- 실패한 stop-condition 검사에 직접 대응하는 fix-forward 작업만 자동 생성한다. 구현 대상은 `pyproject.toml`, `sprite-animation-forge/`(Core 패키지·스키마·테스트·SKILL.md·references), `uv.lock`, 테스트 픽스처 생성 코드로 한정한다.
- 범위 제외(Non-goals, 사용자 확정): Web UI·Web API(M4·M5), live Codex 호출이 필요한 모든 검증(M0 스파이크 S-1~S-10, `-m live` 계약 테스트, M6 인수, `--record-samples` golden), Phaser 브라우저 스모크(Playwright/pnpm 필요), Phase 2 이후 백로그. live·스파이크는 가짜 codex로만 검증하며, 문서의 live 항목은 구현하되 `@pytest.mark.live`로 표시해 기본 실행에서 제외한다.
- always-halt action classes (safety wall — 기본 7종): prod data mutation/deletion · deploy/release/publish · outbound external comms (email · messaging · third-party write APIs) · irreversible VCS/file destruction (force-push · history rewrite · mass deletion) · financial/payment · secret/permission change · privacy-data exposure
- 추가 제한: 이 루프는 push하지 않는다(commit만). 실제 `codex` 바이너리를 호출하는 테스트는 실행하지 않는다.

## Tasks
- forge-m0-scaffold-fake-codex
- forge-m1-bg-split-components
- forge-m1-measure-scale-align-process
- forge-m1-qc
- forge-m1-state-plan-cli
- forge-m1-acceptance-determinism
- forge-m2-codex-provider
- forge-m2-prompt
- forge-m2-identity-reference-cli
- forge-m3-scale-profile-recovery
- forge-m3-export
- forge-m3-skill-acceptance
