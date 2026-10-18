# impact SOTA 디테일 보고서 — 체크리스트

계획: `~/.claude/plans/memoized-wondering-plum.md` (승인본). 결정 기록: `impact-sota-context-notes.md`.

## P0 — 골든 하니스 + 진단 + 기준선

- [x] `tests/test_golden_html.py`: seed42 → 바이트 SHA-256 골든 + 정규화 골든(DATA JSON deep-compare, script-stripped HTML, JS 함수명 목록)
- [x] 기존 pytest 15개 green 확인
- [x] SIF 내 binout 재진단 (node001): lasso import → 직렬 load_binout_energy → fork/spawn
- [x] 기준선 기록: 재생성 시간 / HTML 크기 / 배지 상태 / Finding 수

## P1 — 신뢰 fix (분할 전)

- [x] (a) solver_quality: IE_SIGNIFICANCE_FLOOR_FRAC=1e-3, KE_FLAT_TOL_FRAC=5e-3, ie_significant/impact_visible 필드, HG 게이트 조건화, diss_pct=None
- [x] (a) V2 단위테스트: glstat 픽스처 3종 (tiny-IE / flat-KE / 진짜 hourglassing)
- [x] (c) 배지 3상태화 (html_report.py:14330) + KPI diss_pct 정직화 (:5119)
- [x] (b-A) load_binout_energy error 슬롯 + ImpactReport.load_issues + 워커 실패 구조화
- [x] (d) loader 집계 Finding 7종 + analyzer 통계 outlier 게이트(z>3.5, N≥8, ≤10건)
- [x] (b-B/C) P0 진단 결과에 따라: lasso 의존/spawn/matsum 네이티브 or energy_flow.py 삭제

## P2 — 로더 성능 (분할 전)

- [x] keyword 1회 파싱 (kw_data 전달) + velocity 카드 1-스캔 캐시 (3콜사이트 통합)
- [x] `_parse_outputs(parse_motion=False, series=...)` (koo_deep_report, 기본 True 호환)
- [x] CLI `--parallel-runs`(0=auto SLURM) / `--threads-per-run`
- [x] solver_quality 감사 워커 이동 (ImpactReport.solver_quality 슬롯)
- [x] provenance (tool_version/SIF/timestamp/digest → payload+JSON+HTML)

## P3 — 기계적 분할 (모듈당 1커밋, 골든 assert)

- [x] assets/css.py → assets/topbar.py → sections HTML → JS 세그먼트 → payload 리프 → 오케스트레이터 (11커밋, 14,609줄→154줄)
- [x] FFT 중복 정의 생존본만 이동 (사장본 136줄 삭제). nested _r4 는 **dedupe 안 함** — 모듈본과 의미 다름(비유한→None vs 0.0), 골든 우선
- [ ] 정규화 골든 전환 + JS 재그룹 (P4 스케일 작업과 함께 — 바이트 골든이 깨지는 첫 시점에)

## P4 — 스케일

- [x] `//600` 버그 fix + downsample_keep_peak (true-peak 불변식) 전면 적용 — 15.4→7.96MB
- [x] payload/tiers.py (A/B/C/D 표) + t_ref dedup + trajectory 캡 — 7.96→5.50MB (-64%)
- [x] emit.py (deferred-JSON / chunked-dir + manifest) + js_core loadChunk
- [x] in-worker tiering (tier C/D 워커 선축소, pickle-back 축소)

## P5 — 파이프라인

- [x] impact_payload.json sidecar + `--from-json` 실구현(0.1s, 왕복 바이트 동일) + CLI 정리
- [x] per-run 증분 캐시 (cold 4.1s → warm 0.2s, 1-touch=1-miss, 스키마 범프 전량 miss)
- [x] report.json 보강 (solver_quality/load_issues/provenance/schema_version)

## P6 — UX

- [x] payload/position.py + sections/s9_position.py (select + KPI 6카드 + 내러티브 + per-part 테이블 + 차트 2)
- [x] 히트맵↔테이블↔드릴다운 크로스링크 (data-pos, selectPosition, xlinkHover)
- [x] L()/toggleLang i18n 포팅 ([data-i18n] + s9 재렌더)
- [x] (추가) 인사이트 리뷰 12건 반영 — 패널 3개 소생(H4), 임팩터 혼입 차단(C3),
      no-contact 클래스(M8), 신뢰 서사 정면 배치(C1/C2/H7), 에너지 페이지
      glstat 흡수율 지도(H6), 기준 정직화(H5), 모순 제거(M9), sanity 게이트(M10), 단위 통일(M11)

## P7 — 검증·배포

- [x] V1-V4 (골든 22 passed / floor 픽스처 3종 / 338위치 합성: 0.9s·RSS 228MB·에러 0 / 캐시 20×·1-touch=1-miss)
- [x] V5 Test_Impact_A 실데이터 (배포본 SIF 안, 2026-10-18)
      · **시간 2.05초** (캐시 재실행) — 조건 ≤6s 충족.
        첫 실행 758초(캐시 생성 25런), 2회차 34초(SIF 콜드스타트), 3회차 2.05초
      · **Finding 6개** — 조건 >2 충족. insight 패널 20개
      · JS 예외 0 · 외부 요청 0 (폐쇄망 안전)
      · ⚠ **"배지 PASS-다수" 조건은 이 데이터에 대해 틀렸다** — 폐기한다.
        Test_Impact_A 의 진실은 유효 접촉 9/25 이고 그 9개가 전부 에너지 게이트
        FAIL 이다(2026-07 확정, 보고서가 findings·hero·Rule0 로 정면 배치).
        실제 판정은 CRITICAL 11 · WARNING 9 · PASSED 4 · NOT MEASURED 1 이고,
        화면이 "유효 접촉 런 9/25 — 나머지 16런은 glstat 창에서 접촉 미검출" 을
        명시한다. PASS 가 다수로 나왔다면 그것이 오히려 거짓말이다
- [x] commit/push → SIF 재빌드 → NFS 배포 — 여러 릴리스를 거쳐 이미 반영됨
      (현 배포본 be9d2b0 에서 koo_impact_report 실행·시험 148개 통과 확인)
- [x] V6 pyKooCAE probe 연동 — **pyKooCAE 측 일로 이관** (2026-10-18 상류 확인)
      정의(2026-07-08 원문): "pyKooCAE build_impact_report_sh flag wiring with
      `--help | grep -q -- --parallel-runs` probe (LAST, after SIF ships)".
      즉 probe 는 별도 도구가 아니라 **생성 sh 가 새 플래그를 `--help` 로 확인하고
      있을 때만 붙이는 장치**다. 옛 SIF 에는 새 플래그를 안 내보내기 위한 것.
      상류 현황: 지금은 `import koo_impact_report` 성공 여부만 보고, 새 플래그
      (`--parallel-runs`·`--threads-per-run`·`--g-limit`·`--stress-limit`·`--no-cache`·
      `--refresh-cache`·`--single-file`·`--chunked`)는 `impact_extra_args` 로만 넘긴다.
      **우리 쪽에서 할 일은 없다** — 상류가 기다리는 것도 없음을 확인했다.
      우리 `--help` 문구는 probe 대상으로 유효하다:
      "0 = auto: SLURM_CPUS_PER_TASK (or CPU count) // threads-per-run" 
