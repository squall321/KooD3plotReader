# 핫스팟 군집 리포트 — 사용법

파트 내 상위 백분위 요소를 공간 군집화해 **덩어리 단위**로 보고한다.
최대 요소 하나로는 알 수 없는 것을 답한다.

- 응력 집중이 **한 곳에 뭉쳐** 있는가, **여러 군데 흩어져** 있는가
- 각 집중부가 파트 안 **어디에**, **얼마나 큰 범위로** 있는가
- 그 범위의 **평균 수준**은 얼마인가 (최댓값 하나는 특이점일 수 있다)

설계 배경은 [hotspot-cluster-plan.md](hotspot-cluster-plan.md),
구현 판단 근거는 [hotspot-cluster-context-notes.md](hotspot-cluster-context-notes.md).

---

## 1. CLI 로 쓰기

```bash
python3 -m koo_deep_report <run_dir> -o <report_dir> \
    --hotspot-clusters \
    --hotspot-top-percent 3.0 \
    --hotspot-distance-factor 1.5 \
    --hotspot-min-elements 5 \
    --hotspot-max-clusters 20
```

| 옵션 | 기본값 | 뜻 |
|---|---|---|
| `--hotspot-clusters` | 꺼짐 | 활성화 |
| `--hotspot-top-percent` | 5.0 | 파트별 상위 백분위 (%) |
| `--hotspot-distance-factor` | 1.5 | 거리 임계 = 이 값 × 파트 대표 요소 크기 |
| `--hotspot-min-elements` | 5 | 이 개수 미만 덩어리는 노이즈로 버림 |
| `--hotspot-max-clusters` | 20 | 파트당 보고 최대 덩어리 수 (0 = 무제한) |
| `--hotspot-criterion` | `von_mises` | 선별 기준량. `von_mises` · `max_principal` · `min_principal`, 쉼표로 여러 개 |

## 2. 설정 파일로 쓰기

`--config` YAML 에 **루트 섹션**으로 적는다. 들여쓰기 블록이어야 한다.

```yaml
hotspot_clusters:
  enabled: true
  top_percent: 3.0
  distance_factor: 1.5
  min_elements: 5
  max_clusters: 20
  criterion: [von_mises, min_principal]   # 쉼표 문자열도 됨
```

CLI 인자가 설정 파일보다 우선한다.

### 기준량

| 기준 | 뽑는 것 | 뜨거운 방향 | `stress_max` |
|---|---|---|---|
| `von_mises` | 등가응력 집중 (연성 항복) | 큰 값 | 최댓값 |
| `max_principal` | σ1 집중 = **인장** (취성 균열) | 큰 값 | 최댓값 (부호 있음) |
| `min_principal` | σ3 집중 = **압축** (눌림·좌굴) | **작은 값** | **최솟값** (음수) |

여러 개를 주면 결과 배열에 **파트×기준** 항목이 각각 들어간다. 항목의 `criterion`·`direction`
으로 구분한다. 시간축 극값은 von Mises·σ1 이 max, σ3 이 **min** 이고, 짝 변형률도 같은 시각의
등가변형률 / ε1 / ε3 이다(`strain_measure`). 주응력은 σ1·σ3 중 하나라도 요청되면 요소·상태당
한 번만 분해하므로 둘 다 켜도 비용은 한 번이다.

## 3. pyKooCAE scenario.json 에서 쓰기

`deep_extra_args` 로 통과시킨다.

```json
"postprocess": {
  "enabled": true,
  "auto_deep": true,
  "sif_path": "/opt/apptainers/SmartTwinPostprocessor.sif",
  "deep_extra_args": [
    "--hotspot-clusters",
    "--hotspot-top-percent", "3.0",
    "--hotspot-min-elements", "5"
  ]
}
```

⚠️ **새 옵션이 든 SIF 를 노드에 배포한 뒤에만** 넣을 것.
구버전 SIF 면 argparse 가 `unrecognized arguments` 로 exit 2 를 내고,
`deep_report.sh` 가 `set -e` 라 리포트가 통째로 생성되지 않는다.

배포 확인은 노드에서 한 줄이면 된다.

```bash
apptainer exec <sif> python3 -m koo_deep_report --help | grep hotspot
```

---

## 4. 출력

`analysis_result.json` 에 `hotspot_clusters` 배열로 들어간다.

```json
"hotspot_clusters": [
  {
    "part_id": 23,
    "part_name": "Part_23",
    "criterion": "von_mises",
    "direction": "max",
    "strain_measure": "equivalent",
    "top_percent": 3.00000000,
    "threshold_value": 312.40000000,
    "element_size_ref": 0.28000000,
    "distance_threshold": 0.42000000,
    "element_count_total": 15230,
    "element_count_selected": 456,
    "element_count_clustered": 441,
    "strain_available": true,
    "clusters": [
      {
        "rank": 1,
        "element_count": 47,
        "center": [12.34000000, -5.67000000, 1.02000000],
        "radius_enclosing": 1.21000000,
        "radius_rms": 0.63000000,
        "volume": 0.94000000,
        "stress_mean": 381.20000000,
        "stress_max": 452.70000000,
        "strain_available": true,
        "strain_mean": 0.01210000,
        "strain_max": 0.01980000,
        "peak_element_id": 100234,
        "peak_time": 0.00135000
      }
    ]
  }
]
```

`clusters` 는 **뜨거운 순**(max 방향은 내림차순, `min_principal` 은 오름차순)이고 `rank` 는 1부터다.

| 필드 | 뜻 |
|---|---|
| `direction` | `"max"` \| `"min"`. `min` 이면 `stress_max`·`strain_max`·`threshold_value` 가 **최솟값** |
| `center` | 심각도×부피 가중 중심(von Mises 는 응력×부피와 동일). **초기 형상 기준** (설계 도면과 대조하기 위함) |
| `radius_enclosing` | 중심에서 구성 요소의 **최원 절점**까지. 덩어리의 실제 크기 |
| `radius_rms` | 부피 가중 RMS 반경. **뭉침 정도** — 포함 반경보다 훨씬 작으면 한 점에 집중 |
| `stress_mean` / `strain_mean` | **부피 가중** 평균. 산술평균이 아니다 |
| `element_count_selected` | 상위 백분위로 뽑힌 요소 수 |
| `element_count_clustered` | 그중 최소 크기 필터를 통과해 덩어리에 든 요소 수 |

`strain_available: false` 면 덱에 변형률 텐서가 없는 것이다
(`ISTRN = 0`). 이때 `strain_*` 필드는 출력되지 않는다.

---

## 5. 🔴 top_percent 를 실제 집중 범위에 맞춰야 한다

**상위 X% 는 "값이 컷 이상인 것 전부" 가 아니라 정확히 N개다.**
N 이 진짜 집중된 요소 수보다 크면 **배경 요소가 딸려 들어와 덩어리에 붙고
평균이 희석된다.**

예 — 요소 180개인 파트에서 실제 집중부가 3개뿐인데 `top_percent: 5` 를 주면
9개가 뽑히고, 그중 6개가 배경이다. 배경이 집중부에 인접해 있으면 같은 덩어리로
묶여 `stress_mean` 이 크게 낮아진다.

권장 절차.

1. 먼저 단면 뷰나 파트 통계로 **집중 범위가 대략 몇 %인지** 본다
2. 그 값에 맞춰 `top_percent` 를 잡는다 (보통 1~5%)
3. `element_count_selected` 와 `element_count_clustered` 를 보고,
   `stress_mean` 이 `stress_max` 에 비해 지나치게 낮으면 `top_percent` 를 줄인다

## 6. distance_factor 감

거리 임계 = `distance_factor × 파트 대표 요소 크기`이고, 대표 크기는 **요소 특성 길이 L 의 대표값**이다.

| 요소 | L | 대표 크기 |
|---|---|---|
| 솔리드 육면체·쐐기 | 면내 크기 `√(V / h_min)` (h_min = 대면 도심 간 최소 거리) | `∛median(L³)` |
| 솔리드 사면체·사각뿔 | `∛V` | 〃 |
| 두꺼운 셸 | `√(V / h_min)` | `median(L)` |
| 셸 | `√A` | `√median(A)` |

정육면체·사면체 메시에서는 예전 정의(부피 중앙값의 세제곱근)와 같은 값이다.
🔴 예전 정의는 **한 층 벽돌로 메시한 얇은 판**(PCB·인터포저)에서 임계가 면내 간격보다
작아져 맞닿은 요소도 묶지 못했다 — 0.4 mm 판 파트에서 인접 핫스팟 7요소가 덩어리 0 으로
사라진 것을 실측했다. 면내 크기를 쓰도록 고쳤다.

| 값 | 효과 |
|---|---|
| 1.0 미만 | 인접 요소도 안 묶임 — 덩어리가 잘게 쪼개진다 |
| **1.5** (기본) | 면·모서리로 붙은 요소는 묶고, 한 칸 건너뛴 것은 분리 |
| 3.0 이상 | 떨어진 집중부가 하나로 합쳐진다 |

메시 밀도가 다른 파트에도 자동으로 적응한다(절대 길이가 아니라 요소 크기 배수).

---

## 7. 제한 사항

| 항목 | 상태 |
|---|---|
| 솔리드 요소 | 지원 |
| 셸·두꺼운 셸 | 지원 — 적분점 층 중 가장 뜨거운 층, 면적×두께 가중 |
| 기준량 | von Mises · σ1 · σ3 (변형률 기준 군집은 미지원) |
| 시각별 군집 추적 | 미지원 — 전 시간 최대 기준 한 번만 |
| **GUI YAML 생성** | **미지원** — `gui/app.py` 는 이 블록을 만들지 않는다 (기존 `section_view` 와 같은 수준) |
| 자연어 구역 라벨 | 미지원 — 상대 좌표까지만 제공 |

## 8. 검증

```bash
cd <repo-root>
g++ -std=c++17 -O2 -I include \
    tests/hotspot/test_hotspot_endtoend.cpp \
    src/analysis/HotspotClusterAnalyzer.cpp src/data/Mesh.cpp \
    -o /tmp/t && /tmp/t

# 기준량(σ1·σ3) — 부호·방향·NaN 표식
g++ -std=c++17 -O2 -I include \
    tests/hotspot/test_hotspot_criterion.cpp \
    src/analysis/HotspotClusterAnalyzer.cpp src/data/Mesh.cpp \
    -o /tmp/tc && /tmp/tc
```

나머지 시험은 [tests/hotspot/README.md](../tests/hotspot/README.md) 참조.
