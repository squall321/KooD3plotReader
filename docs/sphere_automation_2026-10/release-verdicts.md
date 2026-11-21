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
4. **분석기 산출 폴더 전체** — `analysis_result.json` 의 키뿐 아니라 **파트별 CSV 가
   새로 생기는지까지** 본다. sphere 는 JSON 만 읽지 않는다. 모듈도 JSON 키도 안
   바뀌었는데 **sphere 가 읽는 값이 생길 수 있다.**
   `loader.py` `load_simulation_result()` 는 `metadata.analyzed_parts` 의 **파트
   번호마다** `stress/part_{pid}_von_mises.csv`(726행) ·
   `…_max_principal_stress.csv`(732) · `…_min_principal_stress.csv`(735) ·
   `strain/part_{pid}_eff_plastic_strain.csv`(748) 를 **있으면 읽는다**(`exists()`).
   파일이 생기는 순간 값이 실린다 — 아무 코드도 안 바뀌어도.

### 통로 4 에서 헷갈리기 쉬운 자리

- sphere 는 **`stress_history` 키를 안 읽는다**(`koo_sphere_report/` 참조 0건).
  **그런데 거기서 "통로가 없다" 로 가면 틀린다** — 같은 값이 **파트별 CSV** 로 들어온다.
  나는 v52 판정에서 바로 이걸 틀렸다(아래 정정). `grep <키>` 가 0건인 것은
  "그 키를 안 읽는다" 까지만 말해 준다. **파일 시스템 경로도 세어야 한다.**
- CSV 에는 **요소 종류 열이 없다.** sphere 는 그 파트가 빔인 줄 모른다.
  deep 은 `stress_history[].element_type` 으로 「빔 · 적분점 최대」 표식을 달지만,
  sphere 의 CSV 경로에는 그 정보가 오지 않는다.
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
| 4 `stress_history` **키** | sphere 참조 0건 — 이 키로는 안 들어온다 |
| 4 **파트별 CSV** | ⚠️ **통로가 있다** — 아래 정정 참조. 결론은 그대로 |
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


#### 정정 (11-21, bf 지적) — 「통로 자체가 없다」 가 틀렸다

위 판정에서 `stress_history` 키의 sphere 참조가 0건인 것을 보고 **「빔 값이
sphere 로 올 길이 없다」 로 결론**했다. 키는 맞지만 결론이 틀렸다.
**sphere 는 파트 응력을 JSON 이 아니라 파트별 CSV 로 읽는다.**

기전 (`/data/koopark/Post_v52/{v51,v52b}/ua_eb` 산출물로 확인).

- `analyzed_parts` 는 **두 판 모두 `[1,2,3,4]`** — 빔 파트 4 가 v51 에도 있었다.
  `UnifiedAnalyzer.cpp`(v52 변경 0건)가 이 목록을 `stress ∪ strain ∪ motion`
  합집합으로 세우고, **운동 작업이 이미 빔을 넣고 있었다.**
- v51 산출에는 `part_4_*.csv` 가 **없다** → sphere 의 `exists()` 가 거짓 → `None`.
- v52 산출에는 **넷이 생긴다**(`von_mises` · `max_principal_stress` ·
  `min_principal_stress` · `eff_plastic_strain`) → `exists()` 가 참 → **값이 실린다.**
  bf 실측: 파트 4 응력 피크 `999.5647325`, 파트 1~3 은 두 판이 같음.
- 까닭은 v52 가 빔 이력을 `result.stress_history` · `max_principal_history` 에
  합치고(`mergeBeamResults`), CSV 내보내기 루프
  (`examples/unified_analyzer.cpp:300`)가 그 이력을 **요소 종류를 가리지 않고**
  순회하기 때문이다.

**「회귀 불요」 는 그대로 선다** — 통로가 있다는 것과 이번 판에 걸렸다는 것은 다르다.

- 적분점 응력이 없는 덱의 산출 폴더는 v51 과 **바이트까지 같다**(각인 셋 제외).
  bf 가 판정 꾸러미 다섯 덱(Test_006 170 · DynaAnalysis 28 · case_shell 6 ·
  두꺼운 셸 283 · airbag 487 파일)을 CSV 까지 맞대 **어긋난 것 0**.
- `/data` 2,476 폴더 중 BEAMIP > 0 인 덱은 **ElasticBeam 하나**뿐이고 sphere
  캠페인이 아니다. 기준 캠페인(솔리드 전용)에는 해당이 없다.

**아직 아무도 안 돌려 본 자리.** 적분 빔(BEAMIP > 0)이 든 덱으로 캠페인을 돌리면
v52 부터 그 빔 파트의 σ_vm · σ1 · σ3 · ε_p 가 sphere 에 실린다
(`models.py:268` peak_stress → `json_report.py:162` · `html_report.py:232`).
**CSV 에 요소 종류 열이 없어 sphere 는 그게 빔인 줄 모른다** — 적분점 극값을
솔리드 표면값과 같은 자로 세우고, 항복 한계가 있으면 **안전율까지 그 자로 낸다.**
`stress_ts.elem` 의 번호는 빔 요소 번호다. 그런 캠페인이 생기면 sphere 쪽 표식과
안전율 적용을 먼저 고쳐야 한다.

**빔 값 자체의 근거 한계**(bf). 유일한 실덱 ElasticBeam 의 전단 · 소성 워드가
전부 0 이라, 값으로 확인된 것은 **축응력 · 축변형률 자리뿐**이다. 전단 · 소성
자리는 lasso 2.2.6 배치를 따른 것이고 실덱 검증이 없다.
