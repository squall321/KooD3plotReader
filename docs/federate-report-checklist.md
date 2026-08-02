# Federate Report — 체크리스트

계획: `federate-report-plan.md`. 결정 기록: `federate-report-context-notes.md`.

## F1 — 기반 (config/adapters/models)

- [x] `koo_federate_report/config.py` — YAML 스키마 §0 로드/검증 (kind/baseline/reports/options/parts)
- [x] `adapters/impact.py` — impact_payload.json → RevisionBundle
- [x] `adapters/sphere.py` — sphere report.json → RevisionBundle
- [x] kind auto 판별 + 혼합 입력 에러 + schema_version/단위계 가드
- [x] 실데이터 로드 스모크 (impact 1쌍, sphere 1쌍)

## F2 — 파트 매칭

- [x] 매칭표(canonical: csv, `~`=부재) 파서
- [x] auto_match_identical + name_normalize (명시 > 암묵)
- [x] unmatched 정책 (show/hide/error) + 미매칭 목록 산출
- [x] pytest (충돌/부재/정규화 케이스)

## F3 — 비교 엔진

- [x] Δ vs baseline / WINNER / TREND(회귀 기울기) / SPREAD 필드 계산
- [x] 파트 추이 테이블 + rank bump + findings diff
- [x] trust_gate — no-contact/FAIL 셀 Δ '미판정'
- [x] (impact) behavior 전이 매트릭스 — no-contact↔접촉 전이가 헤드라인 승격
- [x] (impact) 유효 비교 교집합 KPI ("Δ 판정 가능 9/25"), 교집합 0 처리
- [x] (impact) (위치×파트) 매트릭스 Δ 히트맵 + energy Δ 스칼라(diss%/ke_retention)
- [x] (impact) face 불일치 = face 별 그룹 비교 + '비교 불가' 섹션
- [x] 손계산 픽스처 pytest (3리비전 × 4셀 전 수치 + behavior 전이 케이스)

## F4 — 리샘플

- [x] 구면 IDW 공통 Fibonacci 격자 + 실측/보간 마스크
- [x] impact XY nearest (허용 반경 = 격자 40%) / off 모드
- [x] 커버리지 KPI ("비교 가능 26/512")

## F5 — HTML 보고서

- [x] s2 UNROLLED PROFILE (주력) — baseline 심각도 정렬/카테고리 밴드/절대·Δ·log 토글
- [x] s1 KPI Δ 스트립 + 요약 내러티브 / s3 합성 지도 4종 + linked probe(프로파일과 공유)
- [x] s3 파트 추이(스파크라인) / s4 findings diff / s5 provenance 부록
- [x] N=2 뷰 자동 강등 (TREND 숨김), 소지도 썸네일=probe 링크
- [x] Playwright 콘솔 에러 0

## F6 — 골든·패키징

- [x] 합성 2·3리비전 결정적 골든 (seed 42 vs 7, 격자 상이 쌍 포함)
- [x] build_module.sh 4번째 wrapper + PYTHONPATH + SIF %post 테스트 라인
- [x] 문서/컨텍스트 노트 갱신

## 통합 (F6) — 2026-08-02

- [x] 엔진↔리포트 계약 불일치 3곳 교정 (findings_diff list / behavior_transitions
      per_rev / trust_ok·spread dict·part_matrix.rows·revisions.index)
- [x] `tests/test_contract_integration.py` — 계약 회귀 못박기 (5건)
- [x] 실데이터 3리비전 E2E + 독립 재계산 교차검증 (값/Δ%/winner 불일치 0)
- [x] Playwright — 9섹션, 지도 4×26셀, 매트릭스 626셀, probe 연동, 콘솔 에러 0
- [x] trust gate 양쪽 케이스 (전부 미판정 / 전부 판정) 정직 렌더
- [x] build_module.sh + SIF .def wrapper·PYTHONPATH·%post 테스트 배선
- [x] 결정성 2회 연속 동일, 91 passed, pyflakes 0

## 실데이터 결함 라운드 (2026-08-02)

- [x] findings 차분 안정 키 (이중 계상 / 과잉 병합 양쪽 방어) + 충돌 경고
- [x] WORST-REV 라벨 정정 (winner = 최악 인덱스)
- [x] 기하 파생 카테고리 (면/모서리/꼭짓점) — 구면 소계 소생
- [x] 참피크(리샘플 이전) 헤드라인 + 감쇠·실측률 노출 + 불변식
- [x] sphere acc 단위 G 정정 (기존 테스트가 버그를 잠그고 있었음)
- [x] 파트 빈 칸 이유 3분류 (absent / gated / no_metric)
- [x] 예제 resample idw → nearest + 실측률 0% 경고
- [x] 음수 지표 ERROR 경고 / 경계 입력 스윕 무크래시
- [x] 162 passed, pyflakes 0, Playwright 콘솔 에러 0 (impact·sphere 양쪽)
