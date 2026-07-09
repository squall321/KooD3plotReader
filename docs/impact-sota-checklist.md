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

- [ ] `//600` 버그 fix + downsample_keep_peak (true-peak 불변식) 전면 적용
- [ ] payload/tiers.py (A/B/C/D 표) + t_ref dedup + trajectory 캡
- [ ] emit.py (deferred-JSON / chunked-dir + manifest) + js_core loadChunk
- [ ] in-worker tiering (pickle-back 축소)

## P5 — 파이프라인

- [ ] impact_payload.json sidecar + `--from-json` 실구현 + CLI 정리(--metric 등 제거)
- [ ] per-run 증분 캐시 (.impact_cache/v<N>/, fingerprint, --no-cache/--refresh-cache)
- [ ] report.json 보강 (solver_quality/load_issues/provenance/schema_version)

## P6 — UX

- [ ] payload/position.py + sections/s9_position.py (select + KPI + 내러티브 + per-part 테이블 + 차트)
- [ ] 히트맵↔테이블↔드릴다운 크로스링크 (pos_idx)
- [ ] L()/toggleLang i18n 포팅

## P7 — 검증·배포

- [ ] V1-V4 (골든/floor/300위치 합성/캐시)
- [ ] V5 Test_Impact_A 실데이터 (SIF 내, ≤6s, 배지 PASS-다수, Finding>2)
- [ ] commit/push → SIF 재빌드 → NFS 배포
- [ ] V6 pyKooCAE probe 연동 (마지막)
