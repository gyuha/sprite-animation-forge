# RUN — M4-a: FastAPI 앱 골격 · 오류 형식 · 파일 서빙 보안 · 진입점

서브에이전트 1개가 구현, 오케스트레이터가 DoD 재실행으로 확인.

## 슬라이스 결과
- S1 uv 워크스페이스 멤버 `webui/server`(sprite_forge_web, 엔트리 `sprite-forge-web`), 앱 팩토리, 오류 형식, Host 검증 — ✅ as planned
- S2 health(doctor 60초 캐시)·presets·characters — ✅ as planned
- S3 `/files` 보안과 정적 dist 서빙 — ✅ as planned

## DoD baseline → after
- `-k "api_core or error_format or path_traversal or host_header"`: 0 → 66 passed (≥10)
- `uv run sprite-forge-web --help` exit 0, `--host 0.0.0.0` → "unrecognized arguments"(옵션 부재)
- 전체: 586 → 657 passed, 4 skipped, 2 deselected (서버 테스트 71건 신규)

## 판단·가정 (후속 task가 알아야 함)
- 서버 테스트는 `webui/server/tests/`(`__init__.py` 필수 — 없으면 conftest 모듈명 충돌). fixtures: `make_client(**create_app_kwargs)`, `client`, `root`; TestClient 기본 host `testserver`는 Host 가드가 거부하므로 반드시 이 픽스처 사용. 가짜 codex·CODEX_HOME은 autouse.
- `create_app(root=None, static_dir=DEFAULT_STATIC_DIR, health_ttl=60.0, clock=...)`, 모듈 레벨 `app`. 라우터 추가: `routes/<x>.py`에 `router` → `main.py`의 `ROUTERS`에 등록, `deps.char_dir(request, cid)`.
- 오류 JSON `{"error": {"code","message","detail"}}`; Core 오류코드→HTTP 변환표는 `errors.py`(exit 3→412, exit 2→502 등). docs/10에 §5.2 presets 형상이 없어 자체 설계(테스트 포함). 파일 서빙은 `.png .gif .json .txt .jsonl`만. Host는 호스트명만 비교(포트 불문), `[::1]` 거부.
- `uv sync`에 `sprite-forge-web`이 dev 그룹으로 설치(워크스페이스).
