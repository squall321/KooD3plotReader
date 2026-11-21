# 판 올릴 때 sphere 회귀가 필요한가 — 판정 원장

상류(pykoocae 세션)가 판을 굽기 전에 "sphere 회귀 필요한가" 를 묻는다.
이 파일은 **그 판정을 어떻게 재는지** 와 판별 기록을 남긴다.
v41~v51 판정은 메시지로만 보내 근거가 남지 않았다 — v52 부터 여기에 적는다.

## 재는 법 — 통로 넷을 다 본다

상류가 알려주는 범위는 **Python 모듈 기준**이다. 그것만으로는 모자라다.
sphere 로 들어오는 통로는 넷이고, 넷을 다 막아야 "불요" 다.

1. **`python/koo_sphere_report` 자체** — `git diff --stat <범위> -- python/koo_sphere_report`
2. **의존 다섯** — `koo_deep_report` 의
   `core/{binout_reader,contact_map,contact_metrics,energy_flow_builder}.py` · `ontology/emit.py`
3. **전이 의존** — `emit` 은 `package.py` 를 import 하고, 런타임에 `sphere.py`·`impact.py` 를
   부른다. **`ontology/` 디렉터리 전체**를 봐야 한다. `emit.py` 하나만 보면 놓친다.
4. **생산물 키(`analysis_result.json`)** — C++ 이 새 키를 적으면 모듈이 안 바뀌어도
   sphere 가 읽는 것이 바뀐다. sphere 가 실제로 읽는 자리를 코드로 확인한다
   (문서에 적힌 키 ≠ 읽는 코드가 있는 키).

### 통로 4 에서 헷갈리기 쉬운 자리

- sphere 는 **`stress_history` 를 안 읽는다**. `DATA_STRUCTURE.md` 에 적혀 있지만
  `koo_sphere_report/` 안의 참조는 0건이다. 문서만 보고 "읽는다" 고 판단하면 틀린다.
- sphere 가 읽는 `element_type` 은 **`hotspot_clusters[]` 항목의 것 하나**다
  (`report/html_report.py:481` → `meta["et"]`). `PartTimeSeriesStats.element_type`
  (= `stress_history` 쪽)과 **다른 필드**다. 이름이 같아서 섞기 쉽다.
- 같은 파일이 바뀌었다고 겹친 게 아니다. `UnifiedConfigParser.cpp` 는
  render job 분기(~924행)와 `hotspot_clusters` 분기(~985행)가 한 파일에 있다.
  **분기까지 내려가 봐야** 한다.

### 왜 상류 발표를 그대로 믿지 않는가

**v47 에서 발표 범위가 틀렸다** — `f218f49` 가 내 `report/html_report.py` 를
51줄 바꿨는데 범위에 없었다. 그 뒤로 매 판 내 경로로 직접 잰다.
상류를 의심하는 게 아니라, 남의 작업이 내 파일을 스치는 걸 남이 알기 어렵다.

## 기록

### v52 — `226eca7..d2f0d6b` · **회귀 불요** (2026-11-21)

빔 파트 응력 이력 + `--view-fit target`. 발표 범위가 **정확했고**, 통로 넷 모두 막혀 있었다.

| 통로 | 결과 |
|---|---|
| 1 `koo_sphere_report` | 0건 |
| 2 의존 다섯 | 0건 |
| 3 `ontology/` 전체 | 0건 (`package`·`sphere`·`vocabulary` 포함) |
| 4 `stress_history` (빔이 들어간 블록) | sphere 참조 **0건** — 통로 자체가 없다 |
| 4 `hotspot_clusters[].element_type` | 생산 코드(`UnifiedAnalyzer.cpp`) 0건. `UnifiedConfigParser.cpp` +27 은 render job 분기. `AnalysisResult.hpp` 2줄은 주석뿐 |
| 솔리드 전용 덱 | `element_type` 을 비었을 때 안 쓰는 설계 → 기준 캠페인 출력 종전과 같음 |

**앞으로 걸릴 자리.** 빔은 지금 스냅샷에서 빠져 있어 안 겹쳤다. 나중에
**핫스팟 군집이 빔을 품으면** sphere 는 `"beam"` 을 `meta["et"]` 로 그대로 싣고
솔리드와 같은 자로 세운다 — 적분점 극값을 요소 표면값처럼 읽는 꼴이다.
그때는 sphere 쪽 표식을 같이 고쳐야 한다. 상류에 통보를 요청해 두었다.

**배포 확인(11-21 11:4x UTC).** 상류 주장(헤드리스 `75b03b9d` · GUI `992a0a64`,
네 곳 같음)을 직접 세어 **여덟 모두 일치**했다 — `/opt/apptainers`,
`/data/SmartTwinPostprocessor`, `KooSlurmInstallAutomationRefactory/apptainer/compute-node-images`,
빌드 원본 `apptainer/`. SIF 안(`--no-home` · `PYTHONNOUSERSITE=1`) 에서 각인 `d2f0d6b`,
sphere 임포트 6/6, 흐름 캐시 schema 4, `--parallel-runs`·`--yield-map`·`--viewer`·`--hotspot-part`
노출 확인. **노드 로컬 `/opt/apptainers`(node001·002·viz)는 여전히 옛 판** — VM 셋 다
응답 없음. 네 지점은 전부 이 머신이라, 노드는 뜨는 대로 따로 바꿔야 한다.
