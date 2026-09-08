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
- [ ] `AnalysisResult` 에 `std::vector<PartHotspotResult> hotspot_clusters` 추가
- [ ] JSON 직렬화 (`AnalysisResult.hpp` 의 기존 직렬화 패턴 따름)

## C. 계산 핵심

- [x] 요소 부피·도심 정확 계산 — tet 닫힌식 / 그 외 등매개 2×2×2 가우스
- [x] 등가응력·등가변형률 (편차 텐서 정의)
- [x] 대표 요소 크기 (부피 중앙값)
- [x] 거리 임계 단일연결 군집화 (공간격자 + Union-Find, 기대 O(n))
- [x] 기하·군집 단위 검증 13항목 전부 해석해 대조 통과
- [ ] 요소별 **전 시간 최대** von Mises 누적 (현재는 파트 통계만 유지 → 배열 추가)
  - [ ] 메모리 영향 측정 — 요소 수 × 8바이트, 대형 모델에서 허용 범위인지
- [ ] 요소 중심 좌표 계산 (절점 평균) — 초기 형상 기준
- [ ] 파트별 상위 X% 임계값 산출
- [ ] 거리 임계값 결정 — 요소 대표 크기 × 배수
- [ ] 단일 연결 군집화 (공간 격자 기반 이웃 탐색 — O(n²) 회피)
- [ ] 최소 크기 미달 덩어리 제거
- [ ] 덩어리별 통계 — 가중 중심 · 포함 반경 · RMS 반경 · 응력/변형률 평균·최대
- [ ] 피크 요소 ID + 피크 시각 기록
- [ ] 최대 응력 내림차순 정렬

## D. 배선

- [ ] `AnalysisConfig` 에 옵션 추가 — 활성화 · 백분위 · 거리배수 · 최소크기 · 기준량
- [ ] YAML/설정 파서 배선 (`UnifiedConfigParser`)
- [ ] `koo_deep_report` CLI 인자 추가 (`--hotspot-clusters` 등)
- [ ] pyKooCAE `PostprocessShellGenerator` 쪽 전달 확인 — `deep_extra_args` 로 통과 가능

## E. 검증

- [ ] 합성 덱 — 2개 덩어리 인위 생성, 중심·개수 일치 확인
- [ ] 경계 — 상위 X% 0개 / 전부 한 덩어리 / 최소크기 미달만
- [ ] 회귀 — 기존 `analysis_result.json` 타 필드 불변 (필드 추가만) 증명
- [ ] 실덱 — 단면 뷰 컨투어와 육안 대조
- [ ] 성능 — 요소 수십만 규모 분석 시간 증가폭 측정
- [ ] 빌드 통과 (CMake)

## F. 마감

- [ ] 사용법 문서 (`docs/Reports_Usage.md` 또는 신규)
- [ ] 커밋 (의미 단위 분할)
- [ ] pyKooCAE 측에 사용법 전달 — scenario.json `deep_extra_args` 예시 포함

---

## 진행 상태

| 단계 | 상태 |
|---|---|
| A 조사 | **완료 (7/7)** |
| B 자료구조 | 완료 (JSON 직렬화 제외) |
| C 계산 핵심 | 진행 중 — 기하·군집 완료, 시간축 누적/통계 남음 |
| D 배선 | 미착수 |
| E 검증 | 미착수 |
| F 마감 | 미착수 |
