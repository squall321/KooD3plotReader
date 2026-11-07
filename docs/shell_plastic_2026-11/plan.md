# 계획 — 셸 파트 이력 · 핫스팟 소성 기준 (2026-11-07)

## 왜

사용자 결정(11-07, 미뤄 둔 항목) — ① 분석기에 셸 이력 추가 ② 핫스팟 소성 기준 추가 + 기본 켬 ③ mini26 DropSet 24개 복원(완료).

- **①** `SinglePassAnalyzer` 의 파트별 이력(응력 · 변형률 7종)은 솔리드 요소만 돈다. `buildElementMapping` 이 `solid_parts` 만 보고,
  상태마다 `solid_data` 가 비면 바로 돌아간다. 그래서 셸 · 두꺼운 셸 파트(하우징 · 브래킷 · PCB 박판)는 deep 표에 「계산 안 됨」으로
  나오고, 그림 자동 선택 · 온톨로지 · 캠페인 리포트에서 빠진다(로드맵 3-3).
- **②** 핫스팟 군집의 선별값이 응력 7종뿐이다(`HotspotClusterAnalyzer.cpp:816`). 소성 변형률 ε_p 와 소성일 밀도 w_p 는 요소마다 이미
  계산해(`plasticStrainMax` · `plasticWorkDensity`) 파트 소성역 요약에만 쓴다. 응력 상위 5% 밖의 소성 영역은 군집이 되지 않는다.

## 무엇을

### ② 핫스팟 소성 기준 (먼저 — 작고 독립)
- `HotspotCriterion` 에 `PlasticStrain`(7) · `PlasticWork`(8), 슬롯 9, 이름 `plastic_strain` · `plastic_work`.
- 요소 값은 기존 배열을 그대로 쓴다(새로 계산하지 않는다). 시각은 ε_p 최대가 처음 난 시각, w_p 는 누적이라 마지막 상태 시각.
- 선별은 같은 「상위 p%」 규칙이되, 값이 항복 임계(`yield_eps_threshold`, 기본 0) 이하인 요소는 순위에서 뺀다. 탄성 덱에서 전부 0 인
  요소의 상위 5% 를 군집으로 만들지 않기 위해서다.
- 2패스(`max_t(mean_e)`)는 plastic_strain 만 한다(상태별 ε_p 가 있다). plastic_work 는 상태별 누적값이 없어 기존 「미제공」 표식.
- 기본 기준 `von_mises` → `von_mises` + `plastic_strain`. ε_p 가 없거나 전부 임계 이하면 그 기준 항목은 생기지 않는다.
- 소비자(뷰어 · 리포트 · 온톨로지)의 기준 이름표 · 단위(ε_p 무차원, w_p 는 응력 단위 = 에너지/부피).

### ① 셸 파트 이력
- 셸 배치 해석(IOSHL · MAXINT · NEIPS · ISTRN · 두께 위치 · DCOMP=2 건너뛰기)을 `accumulateLayeredExtremes` 에서 떼어 공용 도우미로 둔다.
  같은 규칙을 두 곳에 베끼지 않는다(과거에 이 배치를 틀린 적이 있다).
- `buildElementMapping` — 셸 · 두꺼운 셸 요소 → 파트를 만들고 `part_ids_` 에 합친다. 파트별 요소 종류를 기록해 결과에 `element_type` 으로 싣는다.
- 상태마다 솔리드 루프 뒤에 셸 · 두꺼운 셸 루프를 돈다. 요소 값은 층(적분점) 최대 — von Mises · σ1 최대 · σ3 최소 · ε_p 최대.
  변형률 텐서(ISTRN)는 안쪽 · 바깥쪽 면 중 극값. 삭제 요소는 뺀다. `solid_data` 가 비어도 셸이 있으면 돈다.
- 평균은 요소 값(층 최대)의 산술 평균 — 솔리드와 같은 규칙.
- 파이썬 — deep 표의 「계산 안 됨(셸)」 → 값과 「층 최대」 표기, 그림 자동 선택 후보, 소비자 점검 결과에 따른 캠페인 · 온톨로지.

## 검증
- ② `case_dent_center_tetfill`(STRFLG, 요소 86,352) — 응력 상위 5% 밖의 소성 영역이 plastic_strain 군집으로 잡히는지,
  독립 계산(요소 ε_p 최대의 상위 p%)과 선별 요소가 같은지. 탄성 덱에서 plastic 항목이 생기지 않는지.
- ① 셸 d3plot 3개(`/data/warpage_study/case_shell`, `/data/battery_study/case_dent_stacked_shell_airbag`,
  `/data/battery_study/test_em_B_tshell_randles` 두꺼운 셸) — lasso 로 같은 상태의 층별 von Mises 최대를 따로 계산해 파트 최대와 대조.
  솔리드 모델(Test_006)은 기존 출력과 값이 같아야 한다(회귀).
- C++ 시험(tests/) · 파이썬 시험 · post_analyze 셸 시험 전부.

## 순서
1. ② → 시험 → 커밋.
2. ① C++ → 시험 · 실데이터 대조 → 커밋.
3. 파이썬 소비자 → 시험 → 커밋.
4. 전체 시험 · 사용자 보고. push · 배포는 사용자 승인 뒤.

## 위험
- ① 은 분석 산출물을 바꾼다. 솔리드만 있는 모델은 그대로여야 하고, 셸 모델은 파트가 는다. 캠페인 리포트의 최악 파트 순위가 셸을 넣어
  바뀔 수 있다 — 소비자 점검에서 확인해 사용자에게 알린다.
- 메모리는 늘지 않는다(이미 읽은 `shell_data` 를 쓴다). 계산 시간만 는다.
- ② 의 기본 켬은 핫스팟을 켠 실행의 군집 목록 · 뷰어 기준 탭을 늘린다.
