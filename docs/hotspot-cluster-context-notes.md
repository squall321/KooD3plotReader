# 핫스팟 군집 리포트 — 컨텍스트 노트

계획: [hotspot-cluster-plan.md](hotspot-cluster-plan.md) · 체크리스트: [hotspot-cluster-checklist.md](hotspot-cluster-checklist.md)

작업 중 내린 판단과 그 근거를 계속 덧붙인다. 다음 세션이 결정을 다시 유도하지 않도록.

---

## 2026-09-08 · 착수 전 조사

### 이미 있던 것 — 상위 백분위 추출

`src/query/ValueFilter.cpp` 에 `inTopPercentile(double)` / `inBottomPercentile` /
`betweenPercentiles` 가 이미 구현돼 있다. 요구사항의 "상위 X% 요소" 단계는
새로 만들 필요가 없을 가능성이 있다.

**단, 확인 필요** — 이 필터는 query 레이어(`D3plotQuery`)용이고,
analysis 레이어(`SinglePassAnalyzer`)와 자료 흐름이 다르다.
그대로 재사용할지, analysis 쪽에서 임계값만 따로 계산할지는 구현 시 판단한다.

### 없던 것 — 공간 군집화

`grep cluster` 로 잡히는 것은 `koo_impact_report/analyzer.py` 의
`compute_trajectory_clusters` 뿐이고, 이는 **충격체 궤적을 KMeans 로 묶는 것**이라
용도가 완전히 다르다. 재사용 불가.

또한 `koo_sphere_report` 의 "sphere" 는 **낙하 방향 구면 피복률**을 뜻하며
이번 작업의 "덩어리를 구로 근사" 와 무관하다. 이름이 겹쳐 혼동하기 쉬우니 주의.

### 요소 응력 접근 경로

`SinglePassAnalyzer.cpp:498` 부근.

```cpp
const auto& solid_data = state.solid_data;      // std::vector<double>
double vm = extractVonMises(solid_data, elem_idx);
auto tensor = extractStressTensor(solid_data, elem_idx);
```

solid 레이아웃 주석은 `SurfaceStrainAnalyzer.cpp:129` 에 있다.

```
sxx, syy, szz, sxy, syz, szx, eff_plastic, [exx, eyy, ezz, exy, eyz, ezx], ...
```

변형률은 대괄호 표기 = **선택적**이다. 덱에 따라 없을 수 있으므로
변형률 통계는 **부재 시 생략하고 그 사실을 출력에 남기는** 처리가 필요하다.
(있다고 가정하고 인덱싱하면 다른 값을 변형률로 보고하게 된다 — 조용한 오염)

### 요소별 전 시간 최대 — 현재 없음

현재 `SinglePassAnalyzer` 는 상태별로 순회하며 **파트 통계**(max/min/sum/count)와
**최대 요소 ID** 만 누적한다. 요소별 시계열 최대 배열은 유지하지 않는다.

군집화하려면 요소별 최대값 배열이 필요하다 → **추가해야 함**.

- 메모리: 요소 수 × 8바이트. 100만 요소 = 8 MB. 허용 범위로 보이나 실측 필요.
- 🔴 상태 루프가 OpenMP 로 **상태별 병렬**이다(`SinglePassAnalyzer.cpp:182`).
  요소별 최대 배열에 여러 상태가 동시에 쓰면 경쟁 상태가 된다.
  스레드별 로컬 배열 후 병합하거나 원자적 최대 연산이 필요하다.
  **이 지점을 놓치면 값이 간헐적으로 틀리고 재현이 어렵다.**

### 절점 좌표

`data/Mesh.hpp` 의 `std::vector<Node> nodes` + `std::vector<Element> solids`.
요소 중심은 구성 절점 좌표의 평균으로 낸다.

**변형 전 초기 좌표 기준**으로 할지 **변형 후**로 할지 결정 필요.
- 초기 좌표: 설계 도면과 대조하기 쉬움. 위치를 "파트 안 어디"로 말하기에 적합
- 변형 후: 실제 그 시점의 형상

요구가 "파트 내 좌하단 상하단" 이므로 **초기 좌표 기준**이 맞다고 판단.
변형이 큰 경우 차이가 날 수 있으므로 출력에 기준을 명시한다.

---

## 결정 대기 항목

### 요소 대표 크기 정의

거리 임계값을 "요소 대표 크기 × 배수" 로 잡기로 했는데, 대표 크기 정의가 미정.

| 후보 | 장점 | 단점 |
|---|---|---|
| 부피의 세제곱근 | 계산 단순, 왜곡 요소에 둔감 | 얇은 요소에서 과소평가 |
| 절점 간 평균 거리 | 직관적 | 계산량 증가 |
| 외접구 지름 | 최대 크기 보장 | 왜곡 요소에서 과대평가 |

구현 시 실덱으로 셋 다 재보고 결정한다. 잠정 1순위는 **부피의 세제곱근**.

### 상위 X% 의 기준 모집단

파트별로 계산할지, 전체 모델 기준으로 할지.

요구("그 파트 내에 상위 x퍼센트")는 **파트별**이 맞다. 다만 파트 간 위험도 비교가
필요해지면 전체 기준도 필요할 수 있어, 옵션으로 열어 두되 기본은 파트별로 한다.


---

## 2026-09-08 · 기하 계산 — 검증이 잡은 실질 결함

### 결정: 5-사면체 분해를 재사용하지 않는다

기존 `UnifiedAnalyzer.cpp` 의 `computeSolidVolume` 은 hex 를 5개 사면체로 쪼개
합산한다. **면이 평면일 때만 정확**하고, 실제 메시의 뒤틀린 육면체에서는 근사다.

실측(뒤틀린 hex 1개):

| 방식 | 부피 | 오차 |
|---|---|---|
| 등매개 2×2×2 가우스 | 1.06775 | — (정확) |
| 5-사면체 분해 | 0.986667 | **−7.59 %** |

2점 가우스가 3점·5점 결과와 **부동소수 오차 0** 으로 일치함을 확인해
"정확하다"는 주장을 실증했다(det(J) 는 각 변수 2차, x·det(J) 는 3차,
n점 가우스는 2n−1 차까지 정확 → 2점이면 충분).

### 🔴 tet 은 가우스로 풀면 안 된다 — 실덱이 쓰는 패턴 때문

LS-DYNA 는 사면체를 절점이 겹친 hex8 로 싣는데, **패턴에 따라 결과가 갈린다.**

| 패턴 | 가우스 결과 |
|---|---|
| `(A,B,C,C, D,D,D,D)` | 정확 |
| `(A,A,B,C, D,D,D,D)` | 정확 |
| `(A,B,C,D, D,D,D,D)` | **정확히 참값의 1/2** |

마지막 패턴은 밑면 사각형이 비평면인데 꼭짓점이 밑면 모서리와 겹쳐
기하가 모호하다 — 등매개 사상의 상이 사면체를 절반만 덮는다.

**그런데 실덱이 바로 이 패턴을 쓴다.** `Examples/MinimumModel.k` 확인 결과.

```
4615   10228    4616    9439    9439    9439    9439    9439
```

요소 유형 분포 — 총 43,657 개 중

- tet(4고유) **33,241 (76.1 %)**
- hex(8고유) 10,400 (23.8 %)
- wedge(6고유) 16 (0.0 %)

**분기 없이 가우스만 썼으면 전체 요소의 76% 가 부피 절반으로 계산되고,
부피 가중 평균 응력·중심 좌표·반경이 전부 조용히 틀어졌을 것이다.**
결과는 그럴듯하게 나오고 검출되지 않는다.

→ **고유 절점 수로 분기.** 4고유는 사면체 닫힌 해석식
(V = (1/6)|(b−a)·[(c−a)×(d−a)]|, 도심 = 네 꼭짓점 평균) 을 쓴다. 둘 다 정확하다.
5/6/7/8 고유는 가우스 — 사각뿔·쐐기·육면체 모두 해석해와 일치 확인.

### 검증 자산

`tests/hotspot/test_hotspot_geometry.cpp` — 13개 항목 전부 해석해 대조.
정육면체 / 직육면체 / 평행육면체 / 뒤틀린 육면체 / tet 두 패턴 / 쐐기 /
사각뿔 / 완전축퇴 / 등가응력·변형률 / 대표크기 / 군집화 4종.

빌드·실행:
```
g++ -std=c++17 -O2 -I include \
    tests/hotspot/test_hotspot_geometry.cpp src/analysis/HotspotClusterAnalyzer.cpp \
    -o /tmp/test_hotspot && /tmp/test_hotspot
```

### 확정된 세부 결정

- **대표 요소 크기** = 부피 **중앙값**의 세제곱근. 평균은 소수의 큰 요소에
  끌려가 임계 거리를 부풀리고 서로 다른 덩어리를 붙인다.
- **등가변형률** = `sqrt( (2/3)·e'_ij e'_ij )`. d3plot 변형률은 텐서 성분이므로
  공학전단 규약을 쓰면 안 된다. 단축 비압축에서 ε_eq = ε_axial 로 검증.
- **군집화** = 균일 공간 격자(셀 = 임계값) + Union-Find. 임계 거리 이내 이웃은
  반드시 27셀 안에 있으므로 전쌍 비교(O(n²)) 없이 기대 O(n).


---

## 2026-09-08 · 통합 — 조사가 잡은 함정과 실측 결함

병렬 조사(5개 에이전트)로 통합 지점을 훑고 순차 통합했다. 조사가 잡은 것 중
**놓쳤으면 조용히 틀어졌을** 항목만 남긴다.

### 🔴 요소 연결성은 절점 ID 가 아니라 내부 1-based 인덱스

`Element::node_ids` 값은 d3plot IX8 워드를 무변환으로 담은 것이다
(GeometryParser.cpp:105). 규격서도 "the node numbers are the LS-DYNA internal
numbers" 라고 못박는다. 유일하게 옳은 변환은 `mesh.nodes[node_ids[n] - 1]`.

**그런데 저장소에 두 관례가 공존한다.**

- 옳음 — SurfaceExtractor / SectionClipper / SectionViewRenderer (`nid-1`)
- 틀림 — UnifiedAnalyzer::NodeIndexResolver / NodalAverager / BoundingBox
  (`real_node_ids` 역맵)

실덱 `results/d3plot` 실측: 연결성 값 집합은 정확히 {1..29624} 인데
`real_node_ids` 는 인덱스 28293 부터 29625..30955 로 비항등이라,
역맵 관례는 **1000 요소(2.2%)의 8절점 전부를 MISS 로 떨궈 조용히 사라진다.**
`real_node_ids` 가 항등인 덱에서는 두 관례가 같은 답을 내므로 테스트가 통과한다.

→ 핫스팟은 `nid-1` 만 쓴다. **역맵 관례를 쓰는 기존 3곳은 별건 결함으로 남는다.**

### 🔴 computeSolidVolumeAndCentroid 는 Node 통째 복사를 요구한다

축퇴 판정이 좌표가 아니라 `p[i].id` 비교다. 좌표만 채운 Node 를 넘기면
8개 id 가 같아져 nu=1 → false 반환 → 요소가 통계에서 사라진다.
반드시 `p[n] = mesh.nodes[idx];` 로 복사하고, 변형 좌표를 쓸 때도 id 는 살린 채
x/y/z 만 덮어쓴다.

### 🔴 상위 X% 를 "컷 이상 전부" 로 뽑으면 안 된다

처음엔 N번째 큰 값을 임계값으로 잡고 `v >= threshold` 로 걸렀는데,
**배경 응력이 균일하면 N번째 값이 배경값과 같아져 전 요소가 통과한다.**
실측: 180 요소에서 상위 5% 를 뽑았더니 180개 전부 선별.

→ **정확히 N개**를 고른다(`nth_element` + 동점은 요소 인덱스 오름차순으로
결정적 처리). 같은 입력이 항상 같은 결과를 내야 재현성이 성립한다.

### 성질 — top_percent 는 실제 집중 범위에 맞춰야 한다

N 이 진짜 핫한 요소 수보다 크면 배경 요소가 딸려 들어와 덩어리에 붙고
평균이 희석된다. 이건 결함이 아니라 "상위 X%" 의 정의상 성질이다.
시험 [7] 이 이 성질을 명시적으로 고정한다. 문서·CLI 도움말에 경고를 넣었다.

### 요소별 시간축 최대 — 2차 패스로

상태 루프에 이미 `#pragma omp parallel for` 가 걸려 있어(cpp:91, cpp:184),
그 안에서 요소별 배열을 갱신하면 여러 상태가 같은 elem_idx 를 동시에 써
데이터 경쟁이 된다. 이 빌드의 OpenMP 는 4.5 라 `omp atomic compare` 도 없다.

→ 기존 `extractPeakElementTensors` 선례대로 **buildResult 이후 2차 패스**에서
**elem_idx 로 병렬화**한다. 각 스레드가 자기 요소만 쓰므로 경쟁이 원천적으로 없다.
세 진입점(analyzeParallel / analyzeWithStates / analyzeLegacy) 모두에 배선했다 —
하나라도 빠지면 그 경로에서만 배열이 비는 무음 누락이 된다.

미기록 요소는 **0 이 아니라 -DBL_MAX** 로 둔다. 0 으로 두면 '응력 0 인 요소' 와
구분되지 않는다.

### CLI — 중복 블록과 2차 패스 함정

`run_single()` 과 `_run_one()`(batch) 에 설정 구성 블록이 복제돼 있어
한쪽만 고치면 batch 에서 무음 무시된다 → `_build_hotspot_config()` 헬퍼로 뽑아
양쪽에서 부른다.

YAML 블록은 `render_only=False` 인 1차 패스에만 방출한다. 2차 렌더 패스에도
넣으면 분석이 두 번 돌아 시간만 배가 되고 산출물은 갱신되지 않는다(무증상 낭비).

키 이름에 `parts:` / `threads:` 를 쓰지 않는다 — 이 저장소의 일부 소비자가
문서 전체를 정규식으로 훑어 전역 설정을 가로챈다. 실검증으로 충돌 없음 확인.

### 범위 밖으로 남긴 것

- **GUI(`gui/app.py` build_yaml`)는 핫스팟 블록을 생성하지 않는다.**
  기존 `section_view` 도 같은 상태(파서에는 있으나 GUI 로는 못 만듦)라
  같은 수준으로 두고 문서에 명시한다.
- `deleted_solids` 는 파서가 한 번도 채우지 않아 침식 요소 필터가 무효다(기존 결함).
- `real_node_ids` 역맵을 쓰는 3곳(UnifiedAnalyzer / NodalAverager / BoundingBox).
