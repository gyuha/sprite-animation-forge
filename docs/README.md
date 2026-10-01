# sprite-animation-forge 개발 문서

`PRD.md`(v0.1 Draft)를 구현 가능한 수준으로 구체화한 개발 문서 모음이다. PRD에 없던 두 가지 요구사항을 **핵심 요구사항**으로 추가했다.

1. **이미지 생성은 Codex CLI(`codex exec` + 내장 `image_gen`)를 사용한다.** API 키 없이 ChatGPT OAuth 로그인만으로 동작한다.
2. **Web UI를 제공해 이미지 생성을 쉽게 만든다.** 레퍼런스 업로드 → 액션 선택 → 생성 → 미리보기/QC → 채택 → Phaser 내보내기까지 브라우저에서 끝낸다.

Codex CLI 연동 방식은 추측이 아니라 **2026-09-30에 로컬 `codex-cli 0.159.2`로 실제 이미지를 두 장 생성해 검증한 결과**를 바탕으로 작성했다. 상세 내용은 [03-codex-image-provider.md](03-codex-image-provider.md)에 있다.

---

## 문서 목록

| # | 문서 | 내용 | 주 독자 |
|---|---|---|---|
| 01 | [architecture.md](01-architecture.md) | 시스템 구조, 계층, 기술 스택, 저장소 구조, ADR | 전원 |
| 02 | [skill-spec.md](02-skill-spec.md) | SKILL.md 설계, Agent 워크플로, 파라미터 추론, 프레임 프리셋, CLI 계약 | Skill 개발 |
| 03 | [codex-image-provider.md](03-codex-image-provider.md) | **Codex CLI 이미지 생성 어댑터 (실측 검증)** | Backend |
| 04 | [prompt-rules.md](04-prompt-rules.md) | 프롬프트 블록 구조, 액션별 모션 라이브러리, 복구용 프롬프트 | Skill / Backend |
| 05 | [sprite-pipeline.md](05-sprite-pipeline.md) | 크로마키, 프레임 분리, 컴포넌트 검출, 스케일, 정렬 알고리즘 | Core |
| 06 | [qc-and-recovery.md](06-qc-and-recovery.md) | QC 항목·임계값·적용 범위, 자동 복구 규칙 | Core |
| 07 | [export.md](07-export.md) | Atlas 조립, Phaser JSON, animations.json, GIF | Core |
| 08 | [data-model.md](08-data-model.md) | 출력 디렉터리 구조, JSON 스키마, 불변성 규칙 | 전원 |
| 09 | [web-ui.md](09-web-ui.md) | **Web UI 화면 설계, 사용자 흐름, 와이어프레임** | Frontend |
| 10 | [backend-api.md](10-backend-api.md) | REST/SSE API, Job 큐, 상태 전이 | Backend / Frontend |
| 11 | [testing.md](11-testing.md) | 테스트 전략, 픽스처, MVP 인수 테스트 | 전원 |
| 12 | [roadmap.md](12-roadmap.md) | 마일스톤, 작업 분해, 검증 기준, 리스크, 미결 사항 | 전원 |

## 읽는 순서

처음 합류한 개발자는 전체 구조를 먼저 잡고, 담당 영역 문서로 내려가는 순서를 권장한다. Codex 연동은 모든 생성 경로의 전제이므로 담당 영역과 무관하게 먼저 읽는다.

```
README → 01 architecture → 03 codex-image-provider → 08 data-model → (담당 영역 문서) → 12 roadmap
                                                                    ├─ Core:     05 → 06 → 07
                                                                    ├─ Skill:    02 → 04
                                                                    └─ Web UI:   09 → 10
```

---

## 핵심 결정 요약

| 결정 | 내용 | 근거 문서 |
|---|---|---|
| 이미지 생성 | `codex exec`를 subprocess로 호출, 결과는 `$CODEX_HOME/generated_images/<thread_id>/`에서 수집 | 03 |
| 공용 코어 | Skill 스크립트와 Web UI 서버가 같은 Python 패키지 `sprite_forge`를 사용 | 01 |
| Web UI 스택 | FastAPI(Python) + React/Vite/TypeScript + shadcn/ui, `127.0.0.1` 전용 | 01, 09, 10 |
| 저장소 | DB 없음. 파일 시스템(`sprites/<character>/`)이 유일한 상태 저장소 | 08 |
| Grid 표기 | `RxC` = 행(rows) × 열(cols). `2x3` = 2행 3열 | 02, 05 |
| 크로마키 | 요청 색(#FF00FF)이 아니라 **테두리에서 샘플링한 실제 배경색** 기준으로 키잉 | 05 |
| 비파괴 | `raw.png`는 불변. 모든 생성은 `attempts/NNN/`에 누적 | 08 |
| 구현 방식 | PRD §37 Option A(재구현). upstream 코드 복사 없음 | 01 |

---

## PRD 해석 및 충돌 해소

PRD 내부에 서로 다른 값이나 모호한 정의가 있어 아래와 같이 확정했다. 구현 중 이 표와 PRD가 다르면 **이 표가 우선**한다.

| # | PRD 위치 | 문제 | 확정 내용 |
|---|---|---|---|
| 1 | §16 vs §18 | feet Y 예시가 112와 118로 다름 | `baseline = cell_h - margin_bottom`. 기본값 cell 128, margin_bottom 10 → **118** |
| 2 | §23 vs §39 | 출력 구조가 다름(profile 위치, GIF 위치, qc-report 위치) | **§39(최종 MVP 정의)를 기준**으로 하고 §23의 액션별 세부 파일을 흡수. [08-data-model.md](08-data-model.md) 참고 |
| 3 | §10, §14 | `2x3`이 행×열인지 열×행인지 불명 | **행×열(RxC)**. 6프레임 기본 `2x3` = 2행 3열 |
| 4 | §5.1 vs §10 | `fall`이 지원 액션인데 프리셋 없음 | fall: 2 frames, `1x2`, loop=Yes, fps 8 추가 |
| 5 | §13 | tolerance 20 (#FF00FF 기준) | 실측 결과 모델이 정확한 #FF00FF를 내지 않음(배경 평균 약 (248, 4, 249), 모서리는 #FF00FF와 거리 최대 약 44). 샘플링 배경색 기준 `t_in=30`, `t_out=90` 램프로 변경 |
| 6 | §19 QC-02 | 스케일 편차를 어떻게 재는지, 어떤 액션에 적용하는지 불명 | death(누운 자세)·jump(웅크림)처럼 실루엣 높이가 원래 변하는 액션은 제외. 적용 매트릭스는 [06](06-qc-and-recovery.md) |
| 7 | §19 QC-03 | 정렬에 쓴 값으로 정렬 후 다시 재면 정의상 항상 0 | 정렬용 feet line(약한 임계)과 다른 추정기(강한 임계 feet line)로 정렬 후 교차 검증 |
| 8 | §19 QC-06 | idle은 원래 프레임 간 차이가 작아 중복 판정이 잦음 | QC-06은 `warn` 등급(실패 아님) |
| 9 | §26 | `project_native` 정의 없음 | "reference 이미지의 스타일을 그대로 따름"으로 정의. reference가 있으면 `auto`와 동일 |
| 10 | §29 | 단계별 스크립트 8개 | 단계 로직은 패키지 모듈로 두고, Agent용 진입점은 `scripts/forge.py` 하나로 통합(ADR-006) |

---

## PRD 섹션 추적표

| PRD 섹션 | 구현 문서 |
|---|---|
| §4 제품 목표, §9 Animation Planning, §10 Frame Preset, §26 파라미터, §27 사용 예 | 02 |
| §8 Identity Lock, §12 Prompt Generation | 04, 03(분석 호출) |
| §13 배경, §14 분리, §15 컴포넌트, §16 정렬, §17 스케일, §18 스케일 프로파일 | 05 |
| §19–§21 QC·복구, §22 Body/FX 분리 | 06 |
| §23 출력 구조, §31 재현성·비파괴 | 08 |
| §24–§25 Export | 07 |
| §28 Architecture, §29 저장소, §30 기술, §36–§37 upstream·라이선스 | 01 |
| §30 Image Generation (provider 추상화) | 03 |
| §32 MVP 성공 기준 | 11, 12 |
| §33–§34 Phase 2/3, §35 Non-Goals | 12 |
| (신규) Codex CLI 연동 | 03 |
| (신규) Web UI | 09, 10 |

---

## 용어

| 용어 | 정의 |
|---|---|
| Character | 하나의 캐릭터. `sprites/<character_id>/` 디렉터리 하나에 대응 |
| Canonical Reference | 모든 액션 생성에 첨부하는 기준 캐릭터 이미지(`reference/character.png`) |
| Identity Profile | reference에서 추출한 외형 속성(`character-profile.json`) |
| Action | idle, walk 같은 애니메이션 1종 |
| Attempt | 한 액션에 대한 1회 생성(또는 수동 업로드) 결과. `attempts/NNN/` |
| Accepted Attempt | 사용자가(또는 Agent가) 채택한 attempt. 액션 디렉터리 최상위로 복사됨 |
| Raw Sheet | 이미지 모델이 만든 원본 grid 이미지(`raw.png`, 불변) |
| Cell | grid의 한 칸. raw cell(생성 이미지 기준)과 target cell(출력 기준, 기본 128×128)을 구분 |
| Baseline | 출력 cell에서 발이 놓이는 Y 좌표 |
| Key Color | 크로마키 배경색. 기본 #FF00FF, 팔레트 충돌 시 #00FF00 |
| Job | Web UI 서버가 비동기로 수행하는 작업(생성, 분석, 일괄 생성, 내보내기) |
