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
자리는 lasso-python 2.0.3 배치를 따른 것이고 실덱 검증이 없다.


### v53 — `873a153..c19be5e` (21커밋) · **회귀 불요** (2026-11-22, 배포 전 판정)

묵은 결함 정리. **이번 판은 성격이 다르다** — v52 까지는 sphere 가 읽는 값이 안
바뀌었지만, v53 은 **일부 덱에서 실제로 바뀐다.** 그래도 내 캠페인은 비켜간다.
훑기 결과를 받아 적지 않고 **덱 머리말을 직접 읽어** 판정했다.

| 상류 항목 | sphere 에 걸리나 |
|---|---|
| ① 솔리드 적분점 **여덟 자리** 덱의 파트 이력 → 적분점 극값 | **걸릴 수 있는 유일한 항목.** 내 캠페인은 전부 **한 자리** → 해당 없음 |
| ② 겉면 응력·변형률 = 값 실린 적분점 평균 텐서 | sphere 는 `surface/` 를 **안 읽는다** (`loader.py` 참조 0건) |
| ③ 겉면 변형률 침식 면 제외 · 전멸 시 NaN | 같음 — 안 읽는다 |
| ④ `parts` · `deep --parts` 가 이제 실제로 먹는다 | sphere 는 `parts` 를 **분석기에 안 넘긴다**(읽기만 한다). `post_analyze.sh --parts` 는 **직접 넘길 때만** 걸리고 기준 캠페인 YAML 에 `parts:` 가 없다 |
| ⑤ deep 의 `global_unmeasured` → None | deep 쪽 · 현 자료에 없는 잠복 꼴 |
| ⑥ 단면 렌더(SW · LS-PrePost) | sphere 에 **렌더 경로가 없다** |

**①을 구조로 못박은 근거.** sphere 캠페인 셋의 d3plot 머리말을 직접 읽었다 —
`Test_005_Fibonacci_100` · `Test_001_Full26_1Step` · `Test_006_Fibonacci_6deg`
모두 **`NV3D=13` = `7 + NEIPH(6)` → 적분점 한 자리**, `nel8=45,457` ·
**`nel2=0`(빔 없음)** · **`nel4=0`(셸 없음)**. 여덟 자리(`8 × (7+NEIPH)` = 104)가
아니므로 ①은 **훑기 결과와 무관하게** 걸릴 수가 없다. 도구 `.work/v53_check/nv3d.py`.

**다음 판부터 ①을 매번 다시 재야 한다.** 「전에 안 걸렸으니 이번에도」 가 안 통한다 —
캠페인 덱이 바뀌면(적분점 여덟 자리 솔리드, 또는 빔이 든 덱) 그 순간 걸린다.
덱 머리말 한 줄로 끝나는 확인이니 거르지 않는다.

**④는 남에게 걸릴 수 있다.** 그동안 `--parts` 를 넘기고도 **말없이 무시돼** 전 파트를
받던 캠페인이 있었다면, v53 부터는 실제로 줄어든다. 내 캠페인은 아니지만, 다른
캠페인을 돌리는 쪽은 자기 설정을 봐야 한다.

**정정 받음.** 위 「빔 값의 근거 한계」 에 적었던 `lasso 2.2.6` 은 틀렸다 —
설치된 판은 **`lasso-python 2.0.3`** 이다(SIF 안에서 확인). bf 지적.


### v54 — `9b3c081..da81ad3` · **회귀 불요** (판정은 **배포 뒤**, 2026-11-23)

**이 판은 배포 요청이 제 쪽을 거치지 않았다.** 배포·확인이 끝난 뒤 알림으로 알았고,
그래서 아래 판정은 소급이다. 통로가 깨끗해서 결과적으로 문제는 없었지만,
원장에 사실대로 적는다 — 관례는 **굽기 전** 판정이다.

| 통로 | 결과 |
|---|---|
| 1 `koo_sphere_report` | 0건 |
| 2 의존 다섯 | 0건 |
| 3 `ontology/` 전체 | 0건 |
| 4 분석기 산출(파트 CSV · `analysis_result.json`) | **0건** — 바뀐 C++ 일곱은 전부 렌더·단면렌더다 |

바뀐 C++: `UnifiedAnalyzerRender.cpp` · `LSPrePostRenderer.cpp` ·
`TargetFringeRange.{h,cpp}` · `NodalAverager.{hpp,cpp}` ·
`ShellLayerLayout.hpp`(신규). 마지막 것은 셸 층 배치라 파트 CSV 에 닿을 수 있어
포함 관계를 확인했다 — **`render/` · `section_render/` 에서만 쓰이고**
`SinglePassAnalyzer` · `unified_analyzer.cpp` · `UnifiedAnalyzer.cpp` 어디에도
들어가지 않는다. 더해 내 캠페인 셋은 `nel4=0`(셸 없음)이다.

### 대기 중인 로컬 커밋 `6d4e947` (deep `_aggregate` 0.0 → None) · **통로 없음**

파트에 없는 시계열을 0.0 대신 None 으로 두고 `result.json` 의 `peak_strain` ·
`peak_acc_mag` 를 null 로 내는 변경. **sphere 에 통로가 없다.**

- `_aggregate` 는 `koo_deep_report/__main__.py` 에 있다 — **sphere 가 import 하는
  다섯에 없다**(`core/{binout_reader,contact_map,contact_metrics,energy_flow_builder}` ·
  `ontology/emit`).
- **sphere 는 deep 의 `result.json` 을 읽지 않는다.** 읽는 것은
  `analysis_results/<run>/analysis_result.json`(`loader.py:694`)과 파트별 CSV 다.
- sphere 에도 `peak_strain` 이 있지만 **출처가 다르다** —
  `part_<pid>_eff_plastic_strain.csv`(`json_report.py:166` 주석에 명시).
  이름이 같아서 섞기 쉬운 자리다.
- sphere 쪽은 이미 None 을 제대로 다룬다(`analyzer.py:134` ·
  `terminal.py:80` 의 `is not None` 검사, `json_report.py:172` 의 "실제로 실린
  값에만 별칭을 건다").


### v55 — `0bf9ae9..a42043b` (3커밋) · **회귀 불요** (2026-11-23, 굽기 전 판정)

**처음으로 통로가 비어 있지 않았던 판이다.** 상류가 후보를 스스로 짚어 왔고
(`a42043b` 가 세트 리포트 피크를 바꿀 수 있다 · 내 `html_report.py:344` 가 그걸
읽는다), 실제로 **내 캠페인에 set_reports 가 있었다** — `Test_006_Fibonacci_6deg`
에 12개(`Test_005` · `Test_001` 은 0). "세트가 없다" 로 끝낼 수 없었다.

**갈림은 `set_type` 이 아니라 `metric_source` 다.** 바뀐 두 분기가 거기 걸려 있다.

- 세그먼트: `sr.metric_source == "segments" && !sr.parent_elem_idx.empty() && nv3d >= 7`
  (`UnifiedAnalyzer.cpp:1601`)
- 절점: `sr.metric_source == "nodes" && !sr.resolved_node_idx.empty()`

내 세트 12개는 **`set_type = part` · `metric_source` 없음 ·
`resolved_parts = [2,3,15]`** 이다. 둘 다 아니라 **바뀐 루프가 돌지 않는다.**
그래서 「피크가 지운 부모의 0 이나 −1 이던 세트라면 바뀐다」 는 조건은
**따질 필요조차 없다** — 파트 세트는 그 경로를 타지 않는다.

더해 세그먼트 CSV 의 상태별 행이 바뀌는 것도 안 닿는다 —
`_set_report_payload`(`html_report.py:803`)는 **`metrics.json` 만 스캔**하고
세그먼트 CSV 를 읽지 않는다.

나머지 둘: `fb89eb6`(part_section_renders) → sphere 에 렌더 경로 없음.
`ac69f81`(D3plotWriter, `MAXINT < -10000` 삭제 표) → 작성기는 시험 전용.

**다음에 다시 재야 하는 조건.** 세그먼트 세트나 절점 세트를 쓰는 sphere 캠페인이
생기면 이 판정은 무효다. 지금은 파트 세트뿐이라 비켜갔을 뿐이다.

**덱 성질 기록.** 캠페인 셋 모두 `MAXINT = -10003` → **삭제 표가 있는 덱**이다
(`nel8=45,457` · `nel2=0` · `nel4=0` · `NV3D=13`). 침식이 실제로 일어나는 덱이라,
지운 요소를 다루는 변경은 앞으로도 통로 후보로 본다.
