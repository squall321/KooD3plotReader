# 핫스팟 배선 — 엔진의 기준 7종·시간 집계를 koo_deep_report 로

작성 2026-10-16 · 요청서 `docs/requests/hotspot-wiring-request-2026-10-16.md` (pykoocae-53)

## 1. 무엇이 막혔나 (현재 코드로 확인)

| 위치 | 상태 |
|---|---|
| 엔진 `unified_analyzer --capabilities` | 기준 7종 · time_aggregate 3종 — **된다** |
| `__main__.py` `_HOTSPOT_CRITERIA` | 3종뿐 → `max_shear` 등 rc=1 거절 (실측 재현) |
| `__main__.py` `_build_hotspot_config` | `time_aggregate` 를 넘기는 길 없음 |
| `d3plot_reader._build_yaml` | `time_aggregate` 를 엔진 YAML 에 안 씀 |
| YAML `hotspot_clusters.criteria` | 키는 받지만(:403) 블록 목록(`- a`)은 조용히 버림 |
| 거절 시점 | glstat·binout 을 다 읽은 뒤 (늦음) |
| HTML 핫스팟 탭 | 새 기준은 이름 그대로 나오지만 라벨·짝 변형률 라벨 없음, `mean_timemax` 안 보임 |

## 2. 어떻게 고치나

1. 허용 목록은 **실행할 엔진의 `--capabilities`** 에서 읽는다 (기준·시간 집계 둘 다).
   못 읽으면(바이너리 없음·옛 바이너리) 정적 7종·3종으로 대신하고 한 줄 알린다.
   별칭은 엔진 `parseHotspotCriterion` 과 같은 표 — 어긋나지 않게 C++ 소스와 대조하는 시험.
2. `--hotspot-time-aggregate {elemmax_then_mean,mean_then_timemax,both}` + YAML `time_aggregate`.
   `_build_hotspot_config` → `_build_yaml` → 엔진. single·batch 둘 다 같은 헬퍼.
3. YAML `criterion`·`criteria` 둘 다, 쉼표·`[a, b]`·블록 목록 모두.
4. 검증을 분석 시작 전으로 당긴다 (single·batch 모두).
5. HTML — 기준 라벨 4종, 짝 변형률 라벨, `mean_timemax` 열(있을 때만).
6. `--help` 갱신 (MCP 도구 설명의 원천).

## 3. 범위 밖

- sphere 리포트가 군집을 **그리는** 것은 §2(3D 인벨롭 G2)에서 한다 — 지금은 수집만 한다.
- batch 가 `--config` 를 아예 적용하지 않는 기존 결함 — 기록만 (다른 키의 batch 동작이 바뀜).

## 4. 검증

- 단위: 별칭·거절·시간집계·YAML 3형식·엔진 YAML 방출·capabilities 대조·C++ 별칭 대조
- 수정 전 코드에서 새 시험이 FAIL 하는지 먼저 본다
- e2e: `case_01_phase1_stacked_tier-1` 에 `--hotspot-criterion max_shear,x_tension --hotspot-time-aggregate both`
  → JSON 에 두 기준 항목 + `mean_timemax`, HTML 탭 JS 예외 0
- `mean_timemax` 값은 독립 계산과 대조 (항상 ≤ `stress_mean` 이어야 함 — 엔진 주석)
