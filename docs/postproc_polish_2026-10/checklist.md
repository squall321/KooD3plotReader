# 후처리 마감 보완 — 체크리스트

전부 완료 (2026-10-18). 결정 이력: [context-notes.md](context-notes.md)

## ① null 가드 (sphere 탭 3개) — `fc875f5`
- [x] 재현 — 파트 지표가 부분 null 인 캠페인에서 탭 3개 예외 확인
      (Statistics 3617:146 · Part Analysis 4264:124 · Render Export 5441:256)
- [x] `renderStatistics` · `buildStressEnvelopeSVG` · `reDrawMiniMollweide` 가드
      (`isNum` / `onlyNums` / `fxd`)
- [x] **집계에서 미계측 제외** — null 을 0 으로 세면 평균이 조용히 깎인다.
      절반이 미계측인 배열에서 112.0 → 56.0 (50% 희석). ①의 예외보다 이쪽이 나쁘다
- [x] verify: 보고서 재생성 17탭 **JS 예외 0**, 미계측 '—' 46곳
- [x] 시험 `test_null_guard.py` 10건 — 수정 전 코드로 돌리면 **10건 전부 FAIL**

## ② batch --config — `4faaede`
- [x] 경고가 아니라 **적용하도록 고쳤다** — `run_batch` 가
      `_apply_config_to_args` 를 안 불러 설정 파일 전체가 무음 무시됐다
      (`__main__.py` 903줄이 이미 같은 부류의 복제 함정을 경고하고 있었다)
- [x] 설정의 d3plot 경로는 batch 에서 안 쓰인다 — 버리되 한 줄로 알린다
- [x] verify: 실제 CLI 로 설정의 `output.directory` 적용 확인
      (전이면 CWD 의 `./single_report`)
- [x] 시험 `test_batch_config.py` 4건 — 수정 전 2건 FAIL · deep 100 통과

## ③ 단면 뷰 — `9947ab5`
- [x] (a) `output_dir` 상대경로를 **해석 출력 폴더 기준**으로 (절대경로는 그대로).
      `part_section_renders` 는 이미 같은 규칙이었다 — 맞췄다
- [x] (a) verify: CWD 를 `/home/koopark` 로 두고 실행 → PNG 400개가 출력 폴더에만,
      CWD 는 깨끗. 로그의 Done 줄도 절대경로로 바뀜
- [x] (b) 기본 절단면이 핫스팟을 비켜가는 문제 — **문서화에 그치지 않고
      `center_mode: peak` 선택지를 넣었다.** 기본값은 `aabb`(종전 동작)
- [x] (b) 실측 근거: 400상태 덱에서 AABB z=-10.025 vs σ_vm 피크(310.4 @state22)
      z=-2.300 — **7.7mm 비켜 감.** AABB 단면은 점 몇 개뿐인 거의 빈 화면인데
      컬러바는 310.4 를 띄워 "여긴 괜찮네" 로 읽힌다 (frame_0022: 5.3KB vs 31.7KB)
- [x] (b) CLI `--section-view-center {aabb,peak}` 로 노출 (숨은 YAML 키 금지)
- [x] (b) 오타는 경고 후 aabb — 조용히 떨어지면 빈 화면을 받고도 모른다
- [x] 시험 C++ 12건 + python 3건 — 전부 통과

## ④ 캔버스 호버 — `4b04c1f`
- [x] 마우스 올린 위치의 군집 판독 (각도·파트·기준량·순위·척도값·요소수·반경)
- [x] 겹치면 앞쪽(큰 z)을 집는다 · 작은 군집도 최소 반경으로 집힌다
- [x] 값이 없으면 0 이 아니라 '미계측' (①과 같은 규칙)
- [x] verify: 26각도 651군집 실조작 —
      `C7_Front_Left_Top · 파트 23 · von_mises · #1 / 응력 최대: 0.769 /
      요소 36 · 포함반경 32.1`.
      빈 자리 none · 드래그 중 none · 컨투어 모드에서도 집힘 ·
      파트 전체 해제 시 집기 목록 0 · 가장자리 툴팁 접힘 · **JS 예외 0**
- [x] 시험 `test_hotspot_hover.py` 7건 — 수정 전 7건 전부 FAIL · sphere 137 통과

## 남은 것
- [ ] push (미push 커밋 4개) · SIF 재빌드 · 4개 배포 지점 — 사용자 확인 필요
