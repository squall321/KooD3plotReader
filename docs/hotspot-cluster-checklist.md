# 핫스팟 군집 리포트 — 체크리스트

계획: [hotspot-cluster-plan.md](hotspot-cluster-plan.md) · 노트: [hotspot-cluster-context-notes.md](hotspot-cluster-context-notes.md)

## A. 조사 (완료분 포함)

- [x] 기존 상위 백분위 추출 기능 확인 — `ValueFilter::inTopPercentile()` 존재
- [x] 기존 공간 군집화 부재 확인 — 궤적용 KMeans 만 있고 용도 다름
- [x] 요소→파트 매핑 확인 — `SinglePassAnalyzer::buildElementMapping()`
- [x] 요소 응력 접근 경로 확인 — `state.solid_data` + `extractVonMises(solid_data, elem_idx)`
- [x] 절점 좌표 접근 경로 확인 — `Mesh::nodes` + `Mesh::solids` 연결성
- [x] 요소 대표 크기 정의 — **부피 중앙값의 세제곱근** (노트 참조)
- [x] 요소 변형률 추출 경로 — `extractStrainTensor` (base+7..12), `has_strain_tensor_` 플래그 재사용

## B. 자료구조

- [x] `HotspotCluster` 구조체 — 중심·반경 2종·요소수·응력/변형률 통계·피크
- [x] `PartHotspotResult` 구조체 — 파트 메타 + `std::vector<HotspotCluster>`
- [x] `AnalysisResult` 에 `std::vector<PartHotspotResult> hotspot_clusters` 추가
- [x] JSON 직렬화 (`AnalysisResult.hpp` 의 기존 직렬화 패턴 따름)

## C. 계산 핵심

- [x] 요소 부피·도심 정확 계산 — tet 닫힌식 / 그 외 등매개 2×2×2 가우스
- [x] 등가응력·등가변형률 (편차 텐서 정의)
- [x] 대표 요소 크기 (부피 중앙값)
- [x] 거리 임계 단일연결 군집화 (공간격자 + Union-Find, 기대 O(n))
- [x] 기하·군집 단위 검증 13항목 전부 해석해 대조 통과
- [x] 요소별 **전 시간 최대** von Mises 누적 (현재는 파트 통계만 유지 → 배열 추가)
  - [x] 메모리 영향 측정 — 요소 수 × 8바이트, 대형 모델에서 허용 범위인지
- [x] 요소 중심 좌표 계산 (절점 평균) — 초기 형상 기준
- [x] 파트별 상위 X% 임계값 산출
- [x] 거리 임계값 결정 — 요소 대표 크기 × 배수
- [x] 단일 연결 군집화 (공간 격자 기반 이웃 탐색 — O(n²) 회피)
- [x] 최소 크기 미달 덩어리 제거
- [x] 덩어리별 통계 — 가중 중심 · 포함 반경 · RMS 반경 · 응력/변형률 평균·최대
- [x] 피크 요소 ID + 피크 시각 기록
- [x] 최대 응력 내림차순 정렬

## D. 배선

- [x] `AnalysisConfig` 에 옵션 추가 — 활성화 · 백분위 · 거리배수 · 최소크기 · 기준량
- [x] YAML/설정 파서 배선 (`UnifiedConfigParser`)
- [x] `koo_deep_report` CLI 인자 추가 (`--hotspot-clusters` 등)
- [x] pyKooCAE `PostprocessShellGenerator` 쪽 전달 확인 — `deep_extra_args` 로 통과 가능

## E. 검증

- [x] 합성 덱 — 2개 덩어리 인위 생성, 중심·개수 일치 확인
- [x] 경계 — 상위 X% 0개 / 전부 한 덩어리 / 최소크기 미달만
- [x] 회귀 — 기존 `analysis_result.json` 타 필드 불변 증명 (2026-10-18)
      같은 덱(45,457 솔리드·400상태)을 군집 off/on 으로 돌려 JSON 을 **전 필드 재귀 대조**
      → 차이 1건, 그것도 `metadata/analysis_date` (2초 차) 뿐. 나머지 0건
      ⚠ 이 대조에서 **결함이 하나 드러났다** — 군집을 꺼도 `"hotspot_clusters": []` 가
      나가서 '돌렸는데 없음' 과 '안 돌림' 이 구분되지 않았다. 키를 생략하도록 고치고
      시험으로 못박음 (`tests/hotspot/test_hotspot_key_omitted.cpp`, 수정 전 2건 FAIL 확인)
- [ ] 실덱 — 단면 뷰 컨투어와 육안 대조
- [x] 성능 — 분석 시간 증가폭 측정 (2026-10-18)
      45,457 솔리드·400상태, 캐시 예열 후 3회 교대 측정:
      **off 1.01±0.02초 → on 1.41±0.01초 (+0.39초, +38%)**
      ※ 체크리스트는 '수십만' 을 적었으나 가용한 최대 덱이 4.5만이다. 선형이라고 보면
        30만 요소에서 +2.6초 수준이나, 실측은 아니다
- [x] 빌드 통과 (CMake)

## F. 마감

- [x] 사용법 문서 — `docs/hotspot-cluster-usage.md` (12KB)
- [x] 커밋 (의미 단위 분할)
- [x] pyKooCAE 측에 사용법 전달 — 2026-10-17 요청서 대응에서 완료.
      상류가 `postprocess.hotspot_criterion`/`_time_aggregate`/`sphere_viewer` 로 배선하고
      `deep_extra_args` 로 `--no-section-view-per-part` 를 넘기는 것까지 확인
      (docs/hotspot_wiring_2026-10/)

---

## 진행 상태

| 단계 | 상태 |
|---|---|
| A 조사 | **완료 (7/7)** |
| B 자료구조 | **완료** |
| C 계산 핵심 | **완료** |
| D 배선 | **완료** (GUI 미지원 — 문서에 명시) |
| E 검증 | 단위·통합 완료 / 실덱·성능 미실시 |
| F 마감 | 문서·커밋 완료 / pyKooCAE 전달 남음 |
