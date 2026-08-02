# Federate Report — 체크리스트

계획: `federate-report-plan.md`. 결정 기록: `federate-report-context-notes.md`.

## F1 — 기반 (config/adapters/models)

- [ ] `koo_federate_report/config.py` — YAML 스키마 §0 로드/검증 (kind/baseline/reports/options/parts)
- [ ] `adapters/impact.py` — impact_payload.json → RevisionBundle
- [ ] `adapters/sphere.py` — sphere report.json → RevisionBundle
- [ ] kind auto 판별 + 혼합 입력 에러 + schema_version/단위계 가드
- [ ] 실데이터 로드 스모크 (impact 1쌍, sphere 1쌍)

## F2 — 파트 매칭

- [ ] 매칭표(canonical: csv, `~`=부재) 파서
- [ ] auto_match_identical + name_normalize (명시 > 암묵)
- [ ] unmatched 정책 (show/hide/error) + 미매칭 목록 산출
- [ ] pytest (충돌/부재/정규화 케이스)

## F3 — 비교 엔진

- [ ] Δ vs baseline / WINNER / TREND(회귀 기울기) / SPREAD 필드 계산
- [ ] 파트 추이 테이블 + rank bump + findings diff
- [ ] trust_gate — no-contact/FAIL 셀 Δ '미판정'
- [ ] 손계산 픽스처 pytest (3리비전 × 4셀 전 수치)

## F4 — 리샘플

- [ ] 구면 IDW 공통 Fibonacci 격자 + 실측/보간 마스크
- [ ] impact XY nearest (허용 반경 = 격자 40%) / off 모드
- [ ] 커버리지 KPI ("비교 가능 26/512")

## F5 — HTML 보고서

- [ ] s2 UNROLLED PROFILE (주력) — baseline 심각도 정렬/카테고리 밴드/절대·Δ·log 토글
- [ ] s1 KPI Δ 스트립 + 요약 내러티브 / s3 합성 지도 4종 + linked probe(프로파일과 공유)
- [ ] s3 파트 추이(스파크라인) / s4 findings diff / s5 provenance 부록
- [ ] N=2 뷰 자동 강등 (TREND 숨김), 소지도 썸네일=probe 링크
- [ ] Playwright 콘솔 에러 0

## F6 — 골든·패키징

- [ ] 합성 2·3리비전 결정적 골든 (seed 42 vs 7, 격자 상이 쌍 포함)
- [ ] build_module.sh 4번째 wrapper + PYTHONPATH + SIF %post 테스트 라인
- [ ] 문서/컨텍스트 노트 갱신
