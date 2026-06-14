# KooD3plotReader 전체 상태 점검 및 보강 로드맵

> 작성: 2026-06-14
> 대상 파이프라인: kood3plot C++ 코어 → unified_analyzer → koo_deep/sphere/impact_report → post_analyze.sh → SmartTwinPostprocessor SIF
> 방법론: 8개 서브시스템 병렬 감사(70 gaps) → 완전성 비평 → 적대적 검토(challenge). draft는 "overwhelmingly accurate, 0 invented items"로 검증됨. 본 문서는 challenge 6개 보정을 반영한 최종본.
> 우선순위 원칙: **(1) 보고서 숫자 신뢰성 > 모든 것, (2) 회귀 방지 > 신규 기능, (3) 운영 사고 방지(배포/빌드) > 코드 미화**

---

## 1. 현재 상태 요약

| 영역 | 등급 | 핵심 리스크 한 줄 |
|------|:----:|------|
| C++ 코어 (reader/parser/analysis) | **C** | truncated d3plot 읽기를 성공으로 보고 → 잘린 시간이력 peak 값이 exit 0으로 출고 |
| C++ render + examples | **C** | LSPrePost/ffmpeg 서브프로세스 timeout 없음 + 렌더 산출물 검증 없음 → 누락이 조용히 갤러리 공백으로 |
| koo_impact_report | **C+** | 단위 자동검출·trust badge는 성숙하나, impactor radius를 변위 CSV에서 추출 → 질량/KE가 ~600배 오류로 출고 |
| koo_deep_report | **C** | pip 설치 불가(빌드 백엔드 오타), unified_analyzer 서브프로세스 timeout 없음, 테스트 0 |
| koo_sphere_report | **D** | 단위 검출 전무 + 9810 하드코딩 4곳 → SI deck 시 peak-G 1000배 오류, CSV 1개 깨지면 DOE 전체 리포트 crash |
| scripts + apptainer 배포 | **D** | %test가 실패 불가(set -e 없음) + 배포 스크립트가 24/24 노드 실패에도 "Complete!" exit 0 + 미고정 main clone |
| 테스트 + CI | **D** | CI 2개월째 red(win-x64), ctest 0개 실행(HDF5 게이트), 핵심 파서·리포트 회귀망 전무 |
| 레포 위생 + 문서 | **C** | README 6.5개월 stale(파이썬 파이프라인 미언급), fresh-clone SIF 빌드가 미추적 installed/lsprepost에 무가드 의존 |

**전체 진단:** 기능은 end-to-end로 동작하고 최근 방어 코딩 문화도 실재한다. 그러나 **"부분적으로 깨진 파이프라인이 운영자·Slurm·리포트 모두에게 정상(녹색)으로 보이는" 무성(silent) 실패 경로**가 모든 계층에 걸쳐 존재한다. 가장 심각한 것은 신뢰성 기능이 **좋은 런을 FAIL로 찍거나**(impact solver_quality 25/25 FAIL) **틀린 숫자를 신뢰성 있게 표시하는**(impactor mass ~600배) **신뢰 역전(trust inversion)** 현상이다.

---

## 2. 강점 (유지·확산할 것)

- **메모리 안전성:** C++ 코어 전체 RAII, raw `new`/`delete` 0건. 모든 버퍼 `std::vector`, 소유권 `unique`/`shared_ptr`.
- **모듈러 CMake:** 7개 계층 라이브러리 단방향 의존, 순환의존 회피가 의도적이고 코드 내 문서화됨.
- **포맷 견고성:** single/double × little/big-endian 4조합 자동 검출, LS-DYNA 매뉴얼 line 인용 + 경험적 검증된 버그 수정 in-code 기록.
- **impact 리포트의 trust 인프라:** glstat 기반 에너지 게이트, data-quality 배지, 단위 단일 출처(`unit_labels`) Python→JS 전파, `--units` override, lossless JSON. → **이 패턴이 sphere/deep로 확산되어야 할 모범.**
- **최근 검증 문화:** impact 통합 시 11-blocker adversarial audit(commit `bce8491`)을 Test_Impact_A 25런에 실제 수행.
- **즉시 활용 가능 회귀망 자산:** koo_impact_report 테스트 15개 통과(1.3s) + seedable `generate_sample.py`(deterministic DOE fixture 생성기).

---

## 3. 보강 로드맵

### Phase 1 — 즉시 (1~2주): 신뢰성 직결 critical/high + quick wins

> 배치 원칙: **숫자 신뢰성(1-1 ~ 1-4) → 가용성/무성실패(1-5 ~ 1-9) → 위생 quick win(1-10, 1-11)**. challenge 보정에 따라 sphere 단위 1000배 오류를 number-trust 그룹(1-4)으로 상향했다.

#### 1-1. impactor radius를 변위 CSV에서 추출하는 버그 제거 — 질량/KE ~600배 오류  `[CRITICAL]`
- **왜:** 출고된 Test_Impact_A 리포트가 8mm 강구(진짜 질량 ~1.7e-5 tonne)를 67mm 구(9.92e-3 tonne)로, KE를 ~600배로 표시. 런간 불일치는 stdout WARN으로만 흐르고 리포트에는 0 finding. 신뢰성 제품에서 "신뢰성 있게 틀린 숫자"는 최악.
- **무엇을:** `_bbox_from_d3plot_part()`가 `Max_Disp_Mag`를 radius로 쓰는 경로 제거. `step_config.txt`의 `Type,Sphere`/`Dimension,8`를 plumbing(이미 `run['config']`에 파싱됨)하여 실제 지오메트리로 대체. 추출 불가 시 'IMPACTOR MASS UNKNOWN' 배지가 실제 발화하도록 (`mass>0`이면 안 뜨는 현 조건 수정).
- **근거:** `loader.py:625-650`(Max_Disp_Mag→radius), `loader.py:1383-1388`(rho·V fallback), `loader.py:1645`(config 이미 파싱), `src/analysis/MotionAnalyzer.cpp:164-183`; 산출물 `impact_report.json` `impactor.mass_override=0.009919`
- **공수:** 2~3일

#### 1-2. solver_quality trust badge가 검증된 25런 전부 FAIL로 찍는 버그  `[CRITICAL]`
- **왜:** `ie_peak=1.6e-05`(수치상 0)에 대해 `hg_frac=hg_peak/ie_peak=54.5%` → 모든 런이 ≥20% FAIL 게이트에 걸려 헤드라인 배지가 **25/25 FAIL**. 정작 진짜 이상(KE가 전 구간 201.486 고정 = glstat에 충돌이 안 보임)은 미발화. 좋은 런에 늑대를 외치고 진짜 이상엔 침묵 → 사용자가 배지를 무시하게 됨.
- **무엇을:** ① HG/SL 게이트에 significance floor 추가(`ie_peak < ke_initial`의 ~0.1%이면 HG_frac 게이트 skip) — **시간 단위**. ② 별도로 'KE 변화 없음 / 충돌이 glstat 윈도우에 안 보임' 명시 플래그 추가 — no-impact-in-window 검출 로직이라 **~1일**. (challenge 보정: 두 작업 공수 분리)
- **근거:** `solver_quality.py:199-201`(floor 없는 hg_frac), `:243-248`(임계 상수); glstat raw: cycle 1과 40404에서 `ke=2.01486E+02`, `vz=-2.82322E+02` 동일
- **공수:** 시간~일 단위

#### 1-3. truncated/corrupt d3plot 읽기를 성공으로 보고하는 무성 실패  `[CRITICAL]`
- **왜:** 52파일 중 30번째가 손상되어도 부분 state 벡터를 반환하고 체크마크 + exit 0. 잘린 시간 윈도우에서 나온 peak stress/displacement가 정상 리포트로 출고. 다운스트림 검사는 `empty()`뿐.
- **무엇을:** `read_all_states`가 family file 중간 실패 시 status를 반환(또는 throw)하게 하고, unified_analyzer가 nonzero exit. 가능하면 expected-state-count cross-check(family size 또는 termination time 대비).
- **근거:** `src/D3plotReader.cpp:126-130`(catch→break→partial return), `:305-314`(parallel WARNING 후 continue), `src/parsers/StateDataParser.cpp:68-70`, `src/analysis/UnifiedAnalyzer.cpp:62-66`
- **공수:** 2~3일

#### 1-4. koo_sphere_report 단위 검출 전무 + 9810 하드코딩 → peak-G 1000배 오류  `[CRITICAL · number-trust]`
- **왜:** 9810 하드코딩 4곳 → SI deck이면 peak-G 1000배 오류 무경고(pyKooCAE에서 막 겪은 실패 모드). sphere는 D등급이며 이는 silent-wrong number이므로, challenge 보정에 따라 가용성 항목(1-5/1-6)보다 위에 배치. **숫자 신뢰성 우선 원칙 적용.**
- **무엇을:** ① 9810 리터럴 4곳을 단일 `MotionData.G_FACTOR`로 수렴(즉시 quick win), ② impact의 `_detect_unit_system` 백포트(전면 백포트는 Phase 3-1 라이브러리 수렴과 연계, Phase 1은 검출+red badge만).
- **근거:** 9810 리터럴 `models.py:120`, `from_json.py:27`, `report/json_report.py:93`, `report/html_report.py:118`
- **공수:** 시간~일 단위

#### 1-5. read_all_states_parallel가 num_threads 무시 — 52파일 OOM 근본 원인  `[HIGH]`
- **왜:** `num_threads`는 계산·출력만 되고 미사용. 52파일이 51개 동시 스레드를 spawn하며 각자 full state 벡터를 동시 적재. `--ua-threads` workaround는 분석 단계만 제한하고 정작 OOM을 낸 읽기 단계는 무제한.
- **무엇을:** counting semaphore 또는 chunked launch로 `num_threads` 준수(~20줄).
- **근거:** `src/D3plotReader.cpp:143-167`(param 계산만), `:277-279`(family file 전부 무제한 launch)
- **공수:** 시간 단위

#### 1-6. 서브프로세스 timeout 전무 (C++ render + 모든 Python 래퍼) — 통합 처리  `[HIGH]`
- **왜:** LSPrePost/ffmpeg(`waitpid(...,0)`)와 unified_analyzer(`subprocess.run` no timeout) 모두 무한 대기. 노드에서 하나만 wedge돼도 전체 DOE post-processing이 walltime까지 동결, Xvfb 누수. 동일 결함이 4개 위치에 반복.
- **무엇을:** (a) C++: LSPrePost `sh -c`에 `timeout <N>` 래핑(`LSPrePostRenderer.cpp:342-346`), (b) Python: `subprocess.run`에 `timeout=`(기본 수 시간) 추가 후 `TimeoutExpired`→기존 RuntimeError 경로로 변환(`d3plot_reader.py:174`, impact 동일).
- **근거:** `src/render/LSPrePostRenderer.cpp:417`, `koo_deep_report/core/d3plot_reader.py:174-178`
- **공수:** 시간 단위(4곳 합산)

#### 1-7. 렌더 산출물 검증 없음 + 렌더 실패가 exit code에 미반영  `[HIGH]`
- **왜:** LSPrePost batch는 movie 실패에도 exit 0. "Created:" 로그는 exit code만으로 찍히고 `fs::exists` 미검증, `main()`은 "Some render jobs failed" 출력 후에도 return 0. → 다운스트림 Python 리포트에서 누락 영상이 조용히 갤러리 공백으로.
- **무엇을:** `processRenderJobs` 각 렌더 후 산출물 존재+>1KB 검증(`LSPrePostRenderer.cpp:1060` 패턴 복사) 후 "Created:" 로그. 렌더 실패 시 unified_analyzer nonzero exit 또는 `render_status.json` 기록.
- **근거:** `examples/unified_analyzer.cpp:910-919, 977, 480`, `src/analysis/UnifiedAnalyzerRender.cpp:685-689`
- **공수:** 시간 단위

#### 1-8. koo_sphere_report: CSV 1개 깨지면 DOE 전체 리포트 crash  `[HIGH]`
- **왜:** OOM/walltime kill로 truncated CSV 1개 → `float(row[...])` ValueError가 수백 런 리포트 생성을 abort.
- **무엇을:** `load_simulation_result` 호출을 try/except로 감싸 런 이름 로깅 + 기존 `failed_runs` 집계로 라우팅. (단위 절반은 1-4로 분리됨)
- **근거:** `koo_sphere_report/loader.py:142-157, 367-373`
- **공수:** 시간 단위

#### 1-9. binout 파싱이 21/25 production 런에서 실패했는데 모두 OK로 보고  `[HIGH]`
- **왜:** ProcessPoolExecutor 워커 내 pandas circular import("partially initialized module pandas")로 matsum 질량 유도·rcforc 마스크가 무력화 → 깨진 rho·V 경로(1-1) 강제. 그런데 `n_failed=0`, 리포트 무플래그(energy-flow 배지가 solver_quality 존재 시 억제됨).
- **무엇을:** 부모 프로세스에서 pandas pre-import 또는 spawn context 사용. binout-parse 실패 카운트를 stdout WARN→리포트 Finding으로 승격.
- **근거:** `/tmp/test_impact_a_e2e.log`(binout parse failed 21회), `loader.py:1780-1790`, `html_report.py:14323-14335`(배지 억제)
- **공수:** 시간 단위

#### 1-10. 배포·빌드 운영 사고 방지 (묶음 — 모두 quick win)  `[HIGH]`
- **왜:** 부분 실패가 운영자에게 녹색으로 보이는 운영 사고 경로들.
- **무엇을:**
  - `.def` `%test` 첫 줄에 `set -e` (현재 마지막 echo가 항상 exit status → 크래시 도구 출고 전력 있음 = 우리가 막 겪은 deep_report `%` 버그). 두 def 모두.
  - `deploy_compute_images.sh`: pipeline subshell 카운터를 for-loop+process substitution으로 교체, SUCCESS/FAIL 출력, SUCCESS ≠ 노드수면 exit 1. ("24/24 실패에도 Complete! exit 0" 제거 — 우리가 막 겪은 silent failure)
  - `post_analyze.sh`: 요약 후 `_fail`/`_deep_fail` > 0이면 exit 1, Step 3의 `> /dev/null 2>&1`를 `tee .../deep_report.log`로 교체.
  - SIF 소스 핀: `git clone --depth 1 --branch <tag-or-sha>`를 build.sh가 local HEAD에서 주입 + `local HEAD != origin/main` 시 경고. (현재 미고정 main clone → 빌드 비재현)
  - `build_module.sh` 끝에 wrapper smoke test: `for b in koo_deep/sphere/impact_report; do bin/$b --help >/dev/null; done` (% 포맷 크래시를 빌드 시 잡았을 것).
- **근거:** `SmartTwinPostprocessor.def:92`, GUI def:72; `deploy_compute_images.sh:125-128, 232-236`; `post_analyze.sh:470, 645, 656`; `SmartTwinPostprocessor.def:49`
- **공수:** 시간 단위(전부)

#### 1-11. 단위 라벨 신뢰성 quick fix (C++ + impact HTML)  `[MEDIUM]`
- **왜:** C++가 stress를 무조건 "MPa"로 하드코딩, impact HTML이 단위 검출 실패 시 9810으로 나눠 가짜 "G" 표시. 막 겪은 mixed-unit 사고와 직결.
- **무엇을:** (a) C++ `unit="MPa"`를 config 공급 문자열(기본 empty/'model units')로 교체 3줄, (b) impact HTML에 UNITS 배지 추가(검출 id+근거, unknown이면 red) + acc 라벨이 비면 9810 나눗셈 중단하고 raw+명시 unit id 표시.
- **근거:** `src/analysis/SinglePassAnalyzer.cpp:379, 391, 396`; impact `html_report.py:14511-14517`(9810 legacy default)
- **공수:** 시간 단위

#### 1-12. 위생 quick wins (묶음)  `[LOW]`
- koo_deep_report `pyproject.toml:3` `setuptools.backends.legacy:build` → `setuptools.build_meta` (현재 pip install 불가) + gui extra 선언.
- `git gc --aggressive --prune=now` (.git 481M→~30M, 무위험).
- `git rm --cached` 50MB example HTML + nuitka crash dump + tracked ELF 바이너리 + ignore와 충돌하는 tracked 파일들; `.gitignore`에 추가.
- impact `html_report.py`의 verbatim 중복 블록 `_fft_dominant_freq`/`_downsample_spectrum`/`_build_fft_payload` 제거(~140줄, 둘째 사본이 첫째를 shadow — 정의 1341/1393/1409 vs 1478/1530/1546, Python은 마지막 정의 유지).
- `--faces` 필터 후로 empty-result exit-2 guard 이동(face 오타가 mock 리포트 exit 0 내는 것 차단).
- 죽은 CLI 옵션 정리: `--from-json`(108-115, exit 2)은 유일한 진짜 미구현 stub → 구현 or 제거. `--metric`(`__main__.py:57`, default="peak_g")은 **parsed-but-ignored**(absent 아님), `--severity-weight`/`--compare-faces`도 동일 → 와이어링 대신 제거. (challenge 보정 ①⑥)
- **공수:** 합산 시간 단위

---

### Phase 2 — 단기 (1~2개월): 회귀 방지 인프라

#### 2-1a. CI 신호 즉시 복구  `[CRITICAL · Phase 1 승격 가능]`
- **왜:** CI가 2개월째 red(win-x64 Build C++) → main 회귀가 불가시. "회귀 방지 > 신규 기능" 원칙상 2개월 red CI는 1줄 수정 quick win이므로 사실상 Phase 1 우선. (challenge 보정 ②)
- **무엇을:** win-x64에 `continue-on-error: true`(또는 제거)로 즉시 신호 복구. PyInstaller 단계의 `|| { echo ::warning }` swallow 제거.
- **근거:** `.github/workflows/build.yml`; GitHub API: `bce8491..f1b0ffa` 전부 failure, 마지막 green `f42b8f6`
- **공수:** 시간 단위

#### 2-1b. ctest 실질화
- **왜:** ctest는 HDF5 게이트로 0개 실행되어 녹색이어도 의미 없음.
- **무엇을:** (a) 기존 5개 C++ 테스트 실행파일을 `add_test()` 등록(HDF5 밖으로) + ctest에 `--no-tests=error`, (b) linux job에 pytest 단계 추가(`pytest python/koo_impact_report/tests` — 15개 1.3s 이미 통과).
- **근거:** `tests/CMakeLists.txt:51, 68`, `.github/workflows/build.yml`(HDF5=OFF, no pytest)
- **공수:** 일 단위

#### 2-2. 숫자 회귀 골든 하니스 (C++ + 리포트 양 계층)
- **왜:** `analysis_result.json` 숫자가 Samsung drop/impact 의사결정을 좌우하는데 아무것도 핀하지 않음. 모든 fix가 단일 데이터셋에 수동 검증됨 — unit-mismatch 류 버그를 회귀 시점에 잡을 망 없음.
- **무엇을:**
  - C++: 작은 d3plot fixture(수 MB, 수 state) 커밋 → 고정 YAML로 unified_analyzer 실행 → golden JSON과 비교(float 상대오차 ~1e-6, count/ID exact, `metadata.date`·절대경로 무시)하는 CTest.
  - 리포트: `generate_sample.py --seed 42` 결정적 DOE로 load+analyze+generate_html 실행 → 예외 없음, `is_mock=False`, KPI 키 안정성, golden 수치 요약 assert. **(이 단일 테스트가 1-1·1-2·payload-schema 회귀를 모두 잡았을 것.)**
- **근거:** `python/koo_impact_report/tests/generate_sample.py`(46KB seedable), `analysis_result.json` 안정 스키마; 현재 golden/comparator repo 내 0건
- **공수:** 일 단위(양쪽). **fixture는 2-3과 공유 전제**(미공유 시 fixture 저작 비용이 long pole — challenge 보정 ⑤)

#### 2-3. d3plot 바이너리 reader/parser 회귀 테스트 (history of bugs 있는 최고위험 코드)
- **왜:** BinaryReader, ControlDataParser, GeometryParser, StateDataParser에 테스트 0. 과거 word-order 버그가 모든 변위/속도를 조용히 망쳤던 코드(`StateDataParser.cpp:231-242` 문서화됨). d3plot 의존 테스트는 데이터 없으면 'SKIPPED' return true로 CI 무커버.
- **무엇을:** 2-2의 golden fixture를 재사용해 byte-exact parse assertion 추가. skip-as-failure 시맨틱을 CI에 도입.
- **근거:** `tests/test_time_history.cpp:121-128`(open 실패→SKIPPED return true), `tests/CMakeLists.txt`(파서 테스트 0)
- **공수:** 일 단위 (fixture 2-2와 공유 시)

#### 2-4. BinaryReader 읽기 검증 헬퍼
- **왜:** `read_int`/`read_float`/`*_array`가 read 성공·gcount·bounds 미검사(`read_double`만 검사). short read가 미초기화 stack 값/부분 벡터를 에러 없이 반환. `read_float_array`는 sibling이 'critical'이라 주석한 `file_.clear()`도 누락 → 이전 EOF가 후속 read를 오염.
- **무엇을:** bounds+gcount 검증 후 short read에 throw하는 `checked_read()` 헬퍼 추가, 5개 미검사 메서드를 경유시키고 누락된 `file_.clear()` 추가.
- **근거:** `src/core/BinaryReader.cpp:189-212, 214-252, 297-323, 325-366`(미검사), `:260-263`(read_double만 검사)
- **공수:** 일 단위

#### 2-5. 무성 데이터 저하 경로를 가시화
- **왜:** 0 MPa peak로 렌더되는 부품이 가시적 경고보다 나쁨(trust 제품에서). deep/impact 양쪽에 무로그 데이터 드롭 경로 존재.
- **무엇을:** (a) impact: stdout-only WARN(impactor mass mismatch `loader.py:1919`, binout-fail count)을 리포트 Finding으로 승격, (b) deep: `_parse_motion_csv`의 None-on-OSError(`d3plot_reader.py:539-540`)·best-effort 렌더 RuntimeError swallow(`:148-149`)·`_parse_series` 0.0 default(`:493-502`)에 최소 로그/플래그 추가.
- **근거:** 위 file:line
- **공수:** 시간~일 단위

#### 2-6. 산출물 provenance 임베드 (재현·감사 가능성)
- **왜:** 어떤 리포트도 tool version/git commit/timestamp/input hash 미포함. 6개월 후 어느 코드가 만든 리포트인지 추적 불가, `--from-json` 재생성 미구현(유일한 재렌더가 ~16분 d3plot 재적재).
- **무엇을:** impact JSON+HTML meta에 `__version__`, SIF 내 `$KOOD3PLOT_HOME/VERSION` 내용, ISO timestamp, d3plot/.k 입력 sha256 임베드(~30줄). deep의 미populate된 `kood3plot_version` 슬롯 채우기.
- **근거:** `impact_report.json`(version/date 키 0), `json_report.py:31-76`, deep `html_report.py:1961`; `build_module.sh:339-348`(VERSION 이미 컨테이너 내 존재)
- **공수:** 일 단위

#### 2-7. 운영 안전성 묶음 (Phase 1에서 못 끝낸 days급)
- **왜:** 중단 시 데이터 손상·자원 누수.
- **무엇을:** (a) `run_step_sphere` symlink-swap을 `trap 'restore' EXIT INT TERM`로 보호(중단 시 `analysis_results` dangling 방지) — 근본은 koo_sphere_report에 `--analysis-dir` 플래그 추가해 swap 제거, (b) impact loader의 mkdtemp 4곳을 try/finally `shutil.rmtree`로 정리(`--keep-workdir` debug 예외), (c) `SLURM_CPUS_PER_TASK`에서 `parallel_runs`/`threads` 유도(현재 4×2 하드코딩).
- **근거:** `post_analyze.sh:504-543`(trap 없음), `loader.py:941,1118,1354,1767`(mkdtemp, rmtree 0건), impact `__main__.py:137-139`
- **공수:** 일 단위

#### 2-8. 문서 정합화
- **왜:** README 6.5개월 stale(파이썬 패키지·orchestrator·SIF 미언급, 'yourusername' URL). fresh-clone SIF 빌드가 미추적 installed/lsprepost에 무가드 의존 → 불투명 에러.
- **무엇을:** (a) README 상단 30줄을 실제 파이프라인 한 문단으로 재작성 + URL 수정, (b) apptainer/README에 3줄 prerequisite(`download_lsprepost.sh`, push-before-build) + build.sh에 installed/lsprepost 존재 체크, (c) `docs/LSPrePost_Batch_Quirks.md` 작성(single-state movie segfault, keep_allcut crash, mesa wrapper 요구 — 현재 agent memory에만 존재).
- **근거:** `README.md`(grep koo_*=0), `SmartTwinPostprocessor.def:33,49`, `build.sh`(lsprepost 미언급)
- **공수:** 시간~일 단위

---

### Phase 3 — 중기 (분기): 구조 개선

#### 3-1. sphere/impact 포크 수렴 — 공유 라이브러리 추출
- **왜:** 같은 스켈레톤의 완전 분기 포크(loader 389 vs 1986줄, html_report 4448 vs 14562줄). glstat 파서가 두 번 독립 구현(divergent parsing이 trust badge 먹임). impact의 모든 하드닝(단위 검출, energy_flow, solver_quality)이 sphere에 invisible — 단위 비대칭(1-4)의 구조적 원인.
- **무엇을:** 공유 코어 추출(단위 검출, glstat 파서, CSV 로더, peak 추출). sphere를 그 위에 재구축하여 solver-quality 게이트·단위 검출을 DROP DOE에도 제공.
- **근거:** diff line counts; `koo_deep_report/core/glstat_reader.py:20` vs `koo_impact_report/solver_quality.py:90`(중복 parse_glstat)
- **공수:** 주 단위

#### 3-2. impact html_report.py 14,562줄 모놀리스 분할
- **왜:** 패키지의 73%가 한 파일. payload 빌드·mock·8개 분석 섹션·거대 JS 문자열 혼재. 측정 가능한 decay(verbatim 중복 — Phase 1-12에서 즉시 제거)는 reviewable size 초과의 전형적 실패 모드. 다음 audit이 14K줄을 grep해야 함.
- **무엇을:** payload builder / section renderers / JS asset를 모듈 분리(테스트 가능 단위로). Phase 2-2 골든 테스트로 분할 안전성 보장.
- **근거:** `wc -l html_report.py = 14562`
- **공수:** 주 단위

#### 3-3. shell element 통계 + erosion 플래그 파싱
- **왜:** (a) SinglePassAnalyzer가 solid만 분석, shell(브래킷·PCB·박판 하우징)은 무경고 누락 — 소비자가 'shell 저응력'과 '미분석'을 구분 불가. (b) DELNN(erosion) 플래그 파서가 빈 stub이라 eroded element가 post-deletion 값(보통 0)으로 part 통계를 오염.
- **무엇을:** `buildElementMapping`에 shell_parts 추가(또는 최소한 미분석 part 명시 경고). `parse_deletion_data` 구현하여 `deleted_*` 벡터 채우고 분석 루프에서 제외.
- **근거:** `SinglePassAnalyzer.cpp:341-368`(solid-only, shell_data 0회), `StateDataParser.cpp:513-517`(stub)
- **공수:** 주 단위(shell), 일 단위(erosion)

#### 3-4. 메모리 경계 — 스트리밍 또는 single-precision 저장
- **왜:** 모든 state를 RAM 적재 후 분석 + StateData가 single-precision 원본도 double로 저장(메모리 2배). ~1M 노드 폰 모델 ×1000 state = 수십 GB. StreamingQuery(1024줄)가 존재하나 production 경로 미사용.
- **무엇을:** single-precision 원본은 float로 저장(절반) 또는 state-by-state 스트리밍으로 unified_analyzer 경로 전환.
- **근거:** `UnifiedAnalyzer.cpp:62`, `StateData.hpp:16-27`, `src/query/StreamingQuery.cpp`(미사용)
- **공수:** 주 단위

#### 3-5. 빌드/배포 견고화
- **왜:** (a) `-march=native` Release가 SIF에 들어가 구형 CPU 노드에서 SIGILL 위험, (b) 버전 아티팩트·롤백 경로 없음(불변 SIF 이름 in-place overwrite — 회귀 시 롤백 불가), (c) HAS_RENDER ifdef가 installed 라이브러리를 외부 consumer에게 link-broken으로.
- **무엇을:** (a) `-march=native`를 CMake 옵션(SIF/CI 기본 OFF) 뒤로, `KOOD3PLOT_HAS_RENDER`를 `target_compile_definitions`로, (b) 아티팩트를 `SmartTwinPostprocessor-<version+commit>.sif` + 'current' symlink, N-1 보존, (c) render 심볼 export 정리(또는 명시적 비-export).
- **근거:** `CMakeLists.txt:146, 366`; `deploy_compute_images.sh:179-181`; nm: `processRenderJobs`는 exe에만, `UnifiedAnalyzer.cpp:172`의 U `processSectionViews`
- **공수:** 일~주 단위

---

## 4. 명시적으로 하지 않을 것 (YAGNI)

| 감사 항목 | 안 하는 이유 |
|---|---|
| **Windows 365일 build-expiry kill-switch 제거** | low severity, Linux/SIF 운영 경로와 무관. 의도적 라이선싱일 수 있음. 단, exit code를 분석 실패와 구분되게 하는 것만 Phase 3 곁다리로 고려. |
| **고아 example .cpp 6개 + 40개 debug 바이너리 대청소** | 빌드 시간 외 운영 영향 없음. `-DKOOD3PLOT_BUILD_DEV_EXAMPLES=OFF` 게이트 한 줄만 여유 시. 트리 미화 자체는 우선순위 낮음. |
| **PNG/JPG 렌더 포맷 실제 구현** | LSPrePost batch가 movie-only라 구조적 제약. 무성 MP4 대신 경고/에러만(Phase 1-7 묶음에 한 줄), 실제 PNG 파이프라인 신규 구축은 수요 불명. |
| **ffmpeg zoom-crop 휴리스틱 완전 재작성** | colormap/레이아웃 가정이 깨지면 silent-wrong이나, fallback 시 `_zoom_fallback` 접미사/WARNING만 추가하면 신뢰 위험 제거됨. 범용 fringe 검출 엔진은 과투자. |
| **deploy 스크립트 3중 사본을 별도 repo에서 통합** | 다른 프로젝트 소유. 이 repo의 fix는 canonical 사본 1곳에만 반영하고 나머지 retire 권고만. 크로스-repo 리팩터는 본 로드맵 범위 밖. |
| **D3plotReader lazy cache thread-safety 강제** | latent(현재 per-file reader라 race 미발생). once_flag/mutex + "one thread per reader" 헤더 주석만(저비용)이면 충분. 전면 동기화는 불필요. |
| **DOE multi-face 경로 production 검증 빌드** | 현재 모든 실검증이 single-face. 합성 데이터 circular validation은 위험하나, 실제 multi-face deck이 들어올 때 검증하는 게 옳음. **단** face가 seed로 force-relabel되는 버그(`loader.py:1842,1851`)는 multi-velocity-direction DOE 들어오면 무성 오류이므로 1-1 plumbing 시 face 재유도만 같이 처리. |
| **죽은 CLI 옵션 와이어링** | `--metric`/`--severity-weight`/`--compare-faces`는 parsed-but-ignored. 미사용 광고 옵션은 제거가 정답(구현이 아님). Phase 1-12에 CLI 정리로 포함, 신규 기능 구축은 안 함. |

---

## 부록 — 우선 착수 권장 순서 (숫자 신뢰성 우선)

가장 적은 노력으로 가장 큰 trust 위험을 제거하는 순서:

1. **1-10 + 2-1a** (운영 사고 방지 + CI 신호 복구) — 모두 시간 단위, 즉시. 우리가 직접 겪은 silent-failure(deploy "Complete!", %test 통과한 크래시 도구)를 막는다.
2. **1-2 ① + 1-4 ①** (solver_quality floor + 9810 단일화) — 시간 단위. 잘못된 배지·1000배 오류 제거.
3. **1-1** (impactor radius) — 2~3일. ~600배 질량/KE 오류 = 최대 trust 위험.
4. **1-3** (truncated d3plot) — 2~3일. 잘린 시간이력 peak 출고 차단.
5. **2-2** (골든 하니스) — 위 fix들이 회귀하지 않도록 망 설치. 이후 모든 작업의 안전판.

> 본 로드맵은 8개 서브시스템 병렬 감사(70 gaps) + 적대적 검토로 도출되었으며, 모든 항목은 file:line 근거를 가진다. 감사 raw 결과는 workflow `wf_a92e8d29-940` 참조.
