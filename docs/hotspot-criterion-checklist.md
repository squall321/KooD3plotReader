# 기준량 확장 — 체크리스트

계획: [hotspot-criterion-plan.md](hotspot-criterion-plan.md)

## A. 골든
- [x] 수정 전 `results/d3plot` von_mises JSON 확보

## B. 코어
- [x] `HotspotCriterion` enum + 파싱/이름/방향 헬퍼
- [x] 미기록 표식 `-DBL_MAX` → NaN (분석기·군집·e2e·기존 시험)
- [x] `accumulateElementExtremes` — 기준별 3배열, 주응력 1회 분해, 변형률 짝
- [x] `computeHotspotClusters` — 방향별 선별·컷값·정렬·중심 가중
- [x] JSON `direction`/`strain_measure`
- [x] `UnifiedAnalyzer` 기준 루프 · `UnifiedConfigParser` `criterion:` · 설정 구조체 2곳

## C. 파이썬/pyKooCAE
- [x] `koo_deep_report --hotspot-criterion` + YAML 병합 + `_build_yaml`
- [x] pyKooCAE `hotspot_criterion` 키 · 문서 · 테스트

## D. 검증
- [x] 기존 시험 4종 통과
- [x] 신규 `test_hotspot_criterion.cpp` (부호·NaN·방향)
- [x] numpy 대조 (기준값 · 누적 극값)
- [x] 골든 바이트 동일
- [x] 변형률 있는 실덱으로 ε1/ε3 짝 확인
- [x] diff 자가 검토 (경고 중복 1건 수정)

## E. 마감
- [x] 문서 `hotspot-cluster-usage.md`
- [x] 커밋(78b9a55 · pyKooCAE 20cb381) · 후처리 SIF v31 · 전처리 SIF v92 · node001 배포 + 배포 SIF e2e(case_01 3기준)
