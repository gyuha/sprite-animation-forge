# 실행 기록 — sprite-gen 동기화 9/11: RIFE 보간기 인터페이스·폴백·점프 보정·유령 프레임 검사 (task #38)

## 한 일
- `interpolate.py`(신규): `Interpolator` 인터페이스, `find_rife`(`SPRITE_FORGE_RIFE_BIN` → PATH의 `rife-ncnn-vulkan`, 실행 불가 경로는 무시, 설치하지 않음), `RifeNcnn.between`(색 — 몸의 자기 색을 투명 영역으로 번지게 한 RGB — 과 커버리지 — 회색 이미지 — 를 **따로 두 번** 보간해 합침, 커버리지 2/255 미만은 버림, 실행 실패는 `rife_failed`). `doctor`/`/api/health`에 `rife`(정보용, ready·경고 불변).
- `video_repair.py`(신규): 점프 프레임 판정 `odd_scores`·`find_jumps`, `repair_jumps(mode=auto|on|off)` — 줄이기 **전의 조밀한 컷**에서, 이웃 사이로 다시 만들고 최악 점수가 90% 아래로 내려갈 때만 채택(원본 상자·기준으로 측정), 루프당 ≤3, 컷이 12프레임 미만이면 시도 안 함. RIFE는 프레임을 만들어야 할 때만 찾음. 없으면 auto=경고 후 원본 절단 / on=`rife_missing`(종료 코드 3) / off=찾지도 않음, 있는데 실패하면 모든 모드에서 오류.
- `video_ghost.py`(신규): 영상이 낸 유령(크로스페이드) 프레임 — 키 색까지의 거리로 "반쯤 있는 화소" 비율(`soft_share`)을 재서 깨끗한 이웃에 자리를 내주고(`given_way`), 없으면 재촬영 사유 `filmed-ghost`(`retake`) + 경고. 다시 만든 프레임의 크로스페이드는 이름만 붙이고 유지(`crossfade`).
- `build_raw_sheet(repair=, interpolator=)`: 유령 → 점프 보정 → 시트 순서, `video-meta.json`에 `ghost`·`retake`·`jump_repair`·`made`·`warnings`. 처리(`process`)는 클립의 `warnings`를 `process.json`에 올림(점프 지표 경고와 같은 경로). plan `repair` 키(스키마·override). 테스트 환경은 실제 RIFE를 안 보도록 `SPRITE_FORGE_RIFE_BIN` 격리.
- docs/13 §8(설치·확인·동작표·판정 규칙·유령), docs/14 영역 D 행 6개, `Health.rife` 타입.

## 검증
- `sg_rife` 26건(interpolator 17 · ghost 9), 가짜 바이너리(`fixtures/fake_rife`)로 호출 계약(`-0 -1 -o -s`)과 색/커버리지 분리를 검증. 전체 pytest 1081 passed, 기준선 ID 누락 0, Vitest 215, e2e 12, typecheck OK. **실제 RIFE는 실행하지 못했다.**

## 계약과 다르게 한 것 (사유)
- 점프 판정을 "스텝 점수 ≥ 1.4"가 아니라 **"이웃과 동떨어진 프레임"(odd-one-out)** 으로: 합성 걷기에서 정상 스텝이 보통의 0.35~2.5배로 흔들려 스텝 비율은 모든 걷기를 오탐했다. 커버리지(알파)만으로는 좌우 대칭 교차에서 오탐해 프리멀티플라이 RGBA 거리로, 성긴 시퀀스(6프레임/주기)에서는 정상 스윙도 2.6점이라 **조밀한 컷에서 판정**하고 12프레임 미만은 시도하지 않는다. 모두 측정으로 확인한 뒤 바꿈.
- 유령 판정을 알파 대신 **키 색 거리**로: 크로마 알파는 `t_out=90`에서 포화해 섞은 프레임도 불투명으로 보여 알파 기반은 0이었다.
- 계획의 "재촬영 사유" 기록은 `video-meta.json`의 `retake` + 처리 경고로. 스튜디오 UI 표시는 만들지 않음(API 상세 `process.warnings`·`video_meta`로 이미 노출).
- 설치 자동화(`rife install`)와 sprite-gen의 "방향 세트 사이클 정렬"은 채택하지 않음(미채택 표).

## 학습 / 주의
- 합성 걷기는 직사각형 팔다리라 실제 걷기보다 훨씬 대칭적이다 [낮음]. 임계값(2.5·1.2·0.5·0.9·12프레임·0.12·1.8·0.08)은 합성 데이터로만 보정했고, 실제 xAI 클립에서는 `video-meta.json`의 `jump_repair.jumps`·`ghost`를 보고 조정해야 한다.
- 호출 인자(`-s` 등)와 모델 폴더 규약은 문서 기준이며 미검증. 호출은 `RifeNcnn._argv` 한 곳.
- 크로스페이드 임계(0.08)는 알파 중간 대역 비율 — 실제 RIFE 결과의 가장자리 안티앨리어싱 기저값(미측정)이 이보다 높으면 오탐 가능.
