# 핫스팟 군집 — 기준량 확장 (von Mises → 주응력)

상위: [hotspot-cluster-plan.md](hotspot-cluster-plan.md) · 체크리스트: [hotspot-criterion-checklist.md](hotspot-criterion-checklist.md) · 노트: [hotspot-criterion-context-notes.md](hotspot-criterion-context-notes.md)

## 1. 요구

군집 기준량이 `von_mises` 고정이다. `max_principal`(σ1)·`min_principal`(σ3)으로도 군집해야 한다.
연성재는 von Mises, 취성재 인장 파손은 σ1, 압축·좌굴은 σ3 이 맞는 기준이다.

## 2. 부호 문제 — 그대로 확장하면 틀린다

| 기준 | 값 범위 | "뜨거운" 방향 | 시간축 극값 |
|---|---|---|---|
| `von_mises` | ≥ 0 | 큰 값 | max |
| `max_principal` | 부호 있음 | 큰 값 (인장) | max |
| `min_principal` | 부호 있음 | **작은 값 (압축)** | **min** |

현재 코드는 세 곳에서 "값 ≥ 0, 클수록 뜨거움" 을 전제한다.

1. **미기록 표식** `-DBL_MAX` + `if (v < 0) continue` — σ1 이 전부 압축인 파트, σ3 전체가 이 검사에 걸려 **요소가 통째로 사라진다**. → NaN 표식으로 교체.
2. **상위 N 선별** 내림차순 고정 → 기준별 방향.
3. **중심 가중** `Σ σ·V·x / Σ σ·V` — 음수 가중은 의미가 없다 → 심각도(hot 방향으로 양수화, 0 클램프) 가중.

## 3. 설계

- `HotspotCriterion { VonMises, MaxPrincipal, MinPrincipal }` + 문자열 왕복.
- 누적 패스 `accumulateElementExtremes(states, criteria)` — 기준별 (값, 시각, 변형률) 3배열.
  주응력은 σ1·σ3 둘 중 하나라도 요청되면 **한 번만** 고유값 분해.
- 변형률 짝: VM→등가변형률, σ1→ε1, σ3→ε3 (같은 시각). d3plot 변형률은 텐서 성분이라 고유값을 그대로 쓴다.
- `computeHotspotClusters` 는 **기준 하나**를 받는다(시그니처 유지, cfg.criterion 만 enum). 여러 기준은 호출부가 돌린다 → 결과 배열에 파트×기준 항목.
- JSON: 파트 항목에 `direction: "max"|"min"`, `strain_measure` 추가. `stress_max` 는 **뜨거운 방향의 극값**(σ3 이면 최솟값). 기존 필드명 유지.
- 설정: YAML `criterion: von_mises,max_principal` (쉼표 목록), CLI `--hotspot-criterion`, pyKooCAE `hotspot_criterion` (문자열 또는 배열).
- 기본값 `von_mises` 단독 → 기존 출력 **바이트 동일**.

## 4. 검증 기준

1. `von_mises` 기본 경로: `results/d3plot` JSON 골든 대비 바이트 동일 (`analysis_result_BEFORE.json`).
2. 기준값 함수: numpy `eigvalsh` 와 대조 (텐서 20종, 부호 혼합).
3. 누적 패스: 실덱 표본 요소 200개에 대해 전 상태를 numpy 로 재계산해 (극값, 시각) 일치.
4. σ3 군집: 합성 메시 — 음수 집중부 2개, 상위 N 이 가장 음수인 쪽을 고르고 순위·컷값·중심이 해석 답과 일치.
5. NaN 표식: 미기록 요소가 선별에서 제외되고, 음수 값은 제외되지 **않는다**.
6. 기존 시험 4종(geometry·hex_volume·principal·endtoend) 통과.
7. pyKooCAE 키 왕복 + 배포 SIF e2e.
