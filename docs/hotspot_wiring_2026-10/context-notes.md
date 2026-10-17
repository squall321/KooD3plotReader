# 핫스팟 배선 — 결정과 근거

## 2026-10-16 조사

**요청서의 :681 지적은 반만 맞다.** `_parse_config_yaml` 이 `criterion`·`criteria` 둘 다
받아 `criterion` 으로 합친다(`__main__.py:403`). 실제 결함은 두 가지 —
값을 3종으로 검증해 7종을 거절하는 것, 블록 목록(`criteria:` 아래 `- a` 줄)은
줄 단위 파서가 콜론 없는 줄로 보고 **조용히 버리는** 것.

**거절이 늦다.** `_build_hotspot_config` 가 `run_analysis(...)` 의 인자 자리에서 불려,
glstat·binout 을 다 읽은 뒤에야 rc=1 이 난다. 큰 덱이면 수 분 뒤다.

**batch 는 `--config` 를 적용하지 않는다.** `_apply_config_to_args` 는 `run_single`
에서만 불린다. batch 파서에도 `--config` 가 있으니 사용자는 적용된다고 믿는다.
이번에 고치지 않는다 — 고치면 YAML 의 다른 키(`render_jobs:` 부재 → `no_render` 등)가
batch 동작을 바꾼다. 따로 알린다.

**다른 소비자는 이미 일반적이다.** `campaign_metrics` 는 기준 이름을 그대로 통과시키고
`_CLUSTER_METRICS` 에 `mean_timemax` 가 있다. `koo_scatter_report --criterion` 도 자유 문자열.

## 왜 capabilities 에서 읽나
이번 결함의 뿌리는 같은 목록이 두 곳(C++ 파서·파이썬 튜플)에 있었던 것이다.
엔진에 기준을 더한 커밋(f686483·81304f8)이 파이썬 쪽을 몰랐다. 실행할 바로 그 바이너리에
묻으면 배포 조합이 어떻든 맞다. 별칭은 capabilities 가 내지 않으므로 파이썬 표를 두되,
C++ `parseHotspotCriterion` 소스와 대조하는 시험으로 어긋남을 잡는다.

## 2026-10-16 구현 — 결정과 확인

**수정 전 동작 (옛 코드로 직접 돌려 확인)** — `criteria:` 아래 `- min_principal` 블록 목록은
경고 없이 **von_mises 로 바뀌어** 돌았다. 거절보다 나쁜 무음 오답이다. `max_shear` 는 거절,
`time_aggregate` 는 "알 수 없는 키 무시", `--hotspot-time-aggregate` 는 argparse 거절.

**엔진 YAML 은 블록 목록을 받지 않는다** — 직접 돌려 보니 `[config] 경고: 블록 리스트 문법
미지원 — '- max_shear' 무시됨` 을 내고 von_mises 로 돈다. 경고가 있으니 무음은 아니다.
deep report 는 엔진에 늘 쉼표 형식(`criterion: a,b`)으로 넘기므로 영향 없다. 엔진은 고치지 않았다.

**time_aggregate 는 기본값이면 엔진 YAML 에 쓰지 않는다** — 그 키를 모르는 옛 엔진이
"알 수 없는 키" 경고를 내기 때문. 기본이 아닌 값은 capabilities 검사에서 이미 걸러진다.

**배치의 이른 검증 주석을 고쳤다** — 처음엔 "모든 케이스가 각각 실패" 라고 적었는데,
`run_one_safe` 는 `except Exception` 이라 SystemExit 을 못 잡고 배치 전체가 첫 케이스에서 멈춘다.

**별칭 대조 시험이 헛돌지 않음을 확인** — 파이썬 표에서 `p1` 을 빼자 시험이 실패했다.
C++ 소스에서 뽑은 별칭 30개(표준 이름 7 포함).

**독립 검증** — 깨끗한 솔리드 덱(`/data/koopark/deep_report_timetest`, 400상태)에서
max_shear·x_tension·z_tension 의 파트 극값(`value_extreme`)을 lasso 로 따로 계산해 60건 대조,
최대 상대오차 3.5e-10, 파트별 요소 수도 일치(`.work/hotspot_wiring/indep_crit_check.py`).
case_01 은 lasso 가 두꺼운 셸 덱을 잘못 읽어 대조에 못 쓴다.
`mean_timemax` 는 군집 멤버가 JSON 에 없어 독립 계산을 못 했다 — 정의상 불변식
`mean_timemax ≤ stress_mean` 만 확인(case_01 62/62, 위반 0).

**HTML** — 두 덱 모두 기준 라벨·짝 변형률 라벨·동시각 평균 열이 나오고 JS 예외 0
(case_01 은 기준 2 × 항목 39개 전부 2D·3D 로 그려 봄).

## 2026-10-17 배포 — 릴리스 절차에 구멍이 있었다

`scripts/deploy_from_sif.sh` 는 NFS 배포 디렉토리(`/data/SmartTwinPostprocessor`)만
갱신한다. 그런데 **실제 소비자는 노드 로컬 `/opt/apptainers/SmartTwinPostprocessor.sif`
를 본다** — KooChainRun 자동 후처리의 `DEFAULT_SIF_PATH`, smarttwin-tool 템플릿의
`STMC_POST_SIF`, 그리고 우리 문서 `docs/hotspot-cluster-usage.md:83` 의 `sif_path` 다.
`/opt` 는 노드 로컬이라 NFS 로 같이 바뀌지 않는다.

그래서 "배포 완료" 를 알린 시점에 호스트는 `be9d2b0`, 노드가 실제로 실행하는 이미지는
`3992a94`(10/2) 였다. 세 대 모두 확인했다 — 헤드·node001·node002 가 전부 601e9d86.
**검증이 NFS 쪽만 봐서 통과했다.** `verify_deploy.sh` 도 `/opt/apptainers` 를 안 본다.

pykoocae-53 이 지적해서 알았다. 받은 지적을 그대로 믿지 않고 세 대의 sha256 을 직접
찍어 확인한 뒤 교체했다(`.work/deploy_2026-10/deploy_nodes.sh` — 백업 후 임시파일 +
원자적 mv). 교체 뒤 노드에서 VERSION·capabilities·번들까지 확인했다.

**다음 릴리스 때 할 것** — `deploy_from_sif.sh` 나 `verify_deploy.sh` 가
`/opt/apptainers` 를 함께 보도록 넣어야 한다. 지금은 별도 스크립트라 또 빠뜨리기 쉽다.

## 종결 — 저쪽 e2e 가 설계 결정 셋을 그대로 확인해 줬다 (2026-10-17)

pykoocae-53 의 배포본 e2e 결과가 우리 결정과 하나씩 맞물린다.

| 관측 | 대응하는 결정 |
|---|---|
| 대조군(시간집계 기본)에서 `mean_timemax` 0개 | 기본값이면 엔진 YAML 에 `time_aggregate` 를 쓰지 않는다 (옛 엔진의 '알 수 없는 키' 경고 방지) |
| `both` 에서 65/65 군집에 `mean_timemax` | `_build_hotspot_config` → `_build_yaml` → 엔진 전달 경로 정상 |
| `max_shear` 의 `stress_mean` 이 두 실행에서 23/23 동일 | 시간집계를 더해도 기존 값은 건드리지 않는다 |
| 부등식 위반 0/65·0/58 | `mean_timemax ≤ stress_mean` (HotspotClusterAnalyzer.hpp:180) |

우리 쪽 검증은 군집 멤버가 JSON 에 없어 `mean_timemax` 를 독립 계산하지 못하고 불변식만
봤는데, 저쪽이 **실해석 결과 2경로 × 123군집**에서 같은 불변식을 다시 확인해 줬다.

**유의** — 저쪽 캠페인 시험(잡 1214)은 LS-DYNA 라이선스가 2026-10-16 부터 만료라
솔버 자리에 지난 실해석 결과를 링크하는 대역 스크립트를 썼다. **후처리 배선만 본
시험이다.** 솔버까지 도는 경로는 라이선스 복구 뒤 다시 봐야 한다.

## 구역 뷰가 캠페인 시간을 먹는다 (2026-10-17 관측)

저쪽 잡 1214 가 40분 time_limit 에 걸려 구역 뷰 **16/23 파트**에서 멈췄다. 핫스팟 배선과는
무관하다(판정 근거인 `analysis_result.json` 은 분석 단계에서 이미 완성된다). 다만 운영
정보로 적어 둔다 — **파트별 구역 뷰는 기본 ON 이고 파트 수에 비례한다.**

줄이는 수단은 이미 있다:
- `--no-section-view-per-part` — 파트별 렌더를 끈다 (가장 큰 절감)
- `--section-view-target-ids ID…` / `--section-view-target-patterns "*PKG*"` — 볼 파트만
  (타겟을 지정하면 파트별 렌더가 자동으로 꺼진다)
- `--sv-threads N` — 병렬 렌더러 수, 기본 2

캠페인 time_limit 을 잡을 때 이 비용을 빼놓고 계산하면 후처리가 통째로 잘린다.

**⚠ 상류가 이 플래그 이름을 문자열로 통과시킨다.** KooChainRun 은 전용 키를 만들지 않고
`postprocess.deep_extra_args` 로 `--no-section-view-per-part` 를 그대로 넘긴다
(pyKooCAE 2f15806). 즉 `--section-view-*` 플래그 이름을 바꾸면 **상류에서 조용히 깨진다** —
argparse 가 거절해 rc≠0 이 나긴 하지만, 그 실패가 캠페인 로그 안에 묻힌다.
이름을 바꿀 일이 생기면 pykoocae-53 에 먼저 알릴 것. (`--hotspot-*` 와 `--viewer` 는
전용 키로 배선돼 있어 사정이 다르다.)

## 릴리스 배포 지점이 하나가 아니다 — 전체 그림 (2026-10-17)

`/opt/apptainers` 건에 이어 pykoocae-53 이 두 가지를 더 짚었고, **직접 확인해 보니 맞다.**
한 릴리스가 닿아야 할 곳이 최소 넷이다.

| 배포 지점 | 무엇이 쓰나 | 우리 절차 | 이번 상태 |
|---|---|---|---|
| `/data/SmartTwinPostprocessor` (NFS) | 호스트 CLI·tar | `deploy_from_sif.sh` ✅ | be9d2b0 |
| 노드 로컬 `/opt/apptainers/*.sif` | KooChainRun `DEFAULT_SIF_PATH`, smarttwin-tool `STMC_POST_SIF` | **없음** | 수동 교체함 (7142a658) |
| `KooSlurmInstallAutomationRefactory/apptainer/compute-node-images/` | `deploy_apptainers.sh` 의 **원본** — 노드 재설치·viz 복귀 때 여기서 깔린다 | **없음** | 아직 601e9d86 (10-02) — 저쪽이 교체 중 |
| GUI 변종 `SmartTwinPostprocessorGUI.sif` | GUI 사용자 | **없음** (우리는 headless 만 빌드) | 76ae3a4b (10-02) — 저쪽이 빌드 중 |

**노드 로컬만 고친 것으로는 부족했다.** `compute-node-images` 가 옛 판이면 노드를 재설치하는
순간 되돌아간다. 즉 내 2026-10-17 교체는 **다음 재설치까지만 유효한 임시 조치**였다.

**GUI 는 아예 빼먹었다.** `apptainer/build.sh` 는 `headless|full|both` 를 받는데 나는
headless 만 돌렸다. GUI def 는 별도 `Bootstrap: docker` 이고 같은 저장소를 clone 하므로
Plotly 번들은 자동으로 실리지만, 내가 headless def 에만 넣은 `%test` 번들 검사가 없다.

**표준 파이프라인의 Phase 3 는 쓰면 안 된다 (확인함).**
`serviceApptainers/BuildSmartTwinPostprocessorOnly.sh` 의 패키지 목록은 5개로
`koo_scatter_report` 가 빠져 있다. 우리 배포본은 6개이고 `env.sh` 도 6개를 담는다.
그 스크립트의 호스트 재동기화를 돌리면 `env.sh` 가 5개로 되돌아가 koo_scatter_report 가
import 안 된다. pykoocae-53 이 그래서 Phase 3 를 건너뛴 것이고, 판단이 맞다.

**해야 할 일** — `deploy_from_sif.sh`/`verify_deploy.sh` 가 위 네 지점을 모두 다루거나,
최소한 **검증이 네 곳을 전부 보게** 해야 한다. 지금은 NFS 만 보고 "전부 일치" 를 출력하므로
반쯤 배포된 상태가 통과한다. 표준 스크립트의 패키지 목록 차이도 상류에 고쳐야 한다.

## GUI 빌드가 깨진 이유 — 움직이는 의존성 (2026-10-17)

pykoocae-53 의 GUI SIF 빌드가 `koo_viewer` 컴파일에서 멈췄다.

```
DeepReportTabQuality.cpp:51: error: 'ImGuiSelectableFlags_DontClosePopups' was not declared
                                     did you mean 'ImGuiSelectableFlags_NoAutoClosePopups'?
```

**우리 코드는 안 바뀌었다.** 그 줄은 a760b2a(04-04)부터 그대로이고 10-02 GUI 빌드는
통과했다. 바뀐 것은 의존성이다 — `viewer/CMakeLists.txt` 가 ImGui 를 `GIT_TAG docking`,
ImPlot 을 `GIT_TAG master` 로 받았다. **브랜치는 움직인다.** 그 사이 ImGui 가 1.91 에서
이름을 바꾼 옛 상수의 호환 별칭을 지웠다.

같은 파일에서 GLFW 는 `3.4`, nlohmann_json 은 `v3.11.3` 으로 **이미 태그 고정**이었다.
ImGui·ImPlot 만 예외였던 것이다 — 규약이 있었는데 두 곳이 빠져 있었다.

**둘 다 했다.** 상수만 바꾸면 다음에 다른 이름이 깨진다(저쪽 지적).
- ImGui → `v1.92.9b-docking`, ImPlot → `v1.0` 으로 고정
- 상수 → `ImGuiSelectableFlags_NoAutoClosePopups` (1.91 부터 존재하므로 고정 버전과 맞다)

**빌드로 확인했다** — 루트에서 `-DKOOD3PLOT_BUILD_VIEWER=ON` 으로 `koo_viewer` 를 실제로
세웠다(rc=0, 8.6MB). 받아온 판은 IMGUI_VERSION 1.92.9b · IMPLOT_VERSION 1.0 이고 다른
ImGui/ImPlot 관련 오류·경고는 없다. 고쳤다고 말만 하고 넘겼으면 저쪽이 같은 자리에서
한 번 더 멈췄을 것이다.

GUI def 에도 headless 와 같은 Plotly 번들 `%test` 검사를 넣었다 — 저쪽이 한 번에
빌드할 수 있게 같은 커밋에 담았다.

## 릴리스 최종 상태 — 네 지점 전부 닫힘 (2026-10-17)

`/opt/apptainers` → `compute-node-images` → GUI 변종까지, 빠졌던 배포 지점이 모두 메워졌다.
**직접 여섯 곳의 sha256 을 찍어 확인했다.**

| 위치 | headless | GUI |
|---|---|---|
| 저장소 `apptainer/` | `7142a658c67e` | `1a22ebe2caf1` |
| `/data/SmartTwinPostprocessor` | 〃 | 〃 |
| `compute-node-images` (노드 재설치 원본) | 〃 | 〃 |
| 헤드 `/opt/apptainers` | 〃 | 〃 |
| node001 `/opt/apptainers` | 〃 | 〃 |
| node002 `/opt/apptainers` | 〃 | 〃 |

GUI 안에서도 확인 — VERSION `672e835` · Plotly 번들 3개 · `--hotspot-time-aggregate` ·
`--viewer {canvas,plotly}` · 엔진 기준 7종 · `koo_viewer` 존재.

**커밋이 둘이다 — 의도한 것이다.** headless `be9d2b0` / GUI `672e835`. 둘 사이 변경은
뷰어 빌드 설정·상수·GUI def 뿐이고, 저쪽이 `/opt/kood3plot/python` 272개 파일 sha256 이
두 SIF에서 **전부 같음**을 확인했다. 같은 입력·같은 인자로 GUI 안 koo_deep_report 를
돌려 헤드리스 결과와 46항목·값 260개 상대차 0 도 확인했다. 검증 끝난 헤드리스를 버리고
재빌드하느니 커밋 차이를 남기는 쪽을 택했다.

**저쪽 검증 방식이 본받을 만하다** — 판정기를 **옛 GUI(3992a94)로 먼저 돌려 전 항목
FAIL 을 확인한 뒤** 새 GUI 에 썼다. '시험이 실패할 수 있는가' 를 먼저 본 것이고,
이 저장소가 반복해 밟았던 '헛도는 시험' 을 막는 정확한 절차다.

남은 것: viz-node001/002 가 내려가 있어 복귀 시 `deploy_apptainers.sh` 로 깔린다
(원본이 이제 맞으므로 새 판이 간다).

## 상류 표준 스크립트 — 하나는 고쳐졌고 하나는 남았다 (2026-10-17)

**고쳐짐** — `serviceApptainers/BuildSmartTwinPostprocessorOnly.sh` 의 `POST_PYPKGS` 가
6개가 됐다(`koo_scatter_report` 추가, 사용자 승인·`.bak_20261017` 백업). 직접 확인했다.
저쪽이 Phase 3 블록만 떼어 임시 폴더에서 돌려, 고친 판은 `env.sh` 6개 순서까지 우리
호스트와 같고 고치기 전 판은 같은 하네스에서 FAIL 임을 확인했다. 이제 그 스크립트의
Phase 3 를 써도 우리 배포본이 깨지지 않는다.

**⚠ 남아 있음 — `serviceApptainers/BuildAll.sh` 의 Post 동기화(Phase 4)는 패키지 둘만 다룬다.**
88~91행이 `koo_deep_report` 와 `koo_sphere_report` 만 `rsync` 한다 (반복문이 아니라
하드코딩이다. 직접 확인). 통합 빌드로 릴리스하면 **`koo_impact_report` ·
`koo_federate_report` · `koo_custom_report` · `koo_scatter_report` 넷이 옛 판으로 남는다.**
우리 패키지 6개 중 4개다. 조용히 묵는다 — 에러가 안 난다.

저쪽이 사용자에게 보고했고 고치지는 않았다. **BuildAll.sh 로 Post 를 릴리스하지 말 것.**
우리 절차(`deploy_from_sif.sh`)나 `BuildSmartTwinPostprocessorOnly.sh` 를 쓸 것.

## deploy_from_sif.sh 가 공개 인터페이스가 됐다 (2026-10-17, 사용자 결정)

serviceApptainers 의 두 표준 빌드(`BuildAll.sh` · `BuildSmartTwinPostprocessorOnly.sh`)가
호스트 동기화를 **우리 `scripts/deploy_from_sif.sh` 호출 한 줄**로 바꿨다. 동기화가 세 벌로
따로 놀며 어긋났기 때문이다 — 통합은 패키지 2개·`make_stl` 누락, 단독은 `koo_dyna_diag`·
`koodyna` 누락, 둘 다 VERSION 미처리.

**그래서 이 스크립트는 이제 바꾸기 전에 상류에 알려야 한다.** 계약 셋을 스크립트 머리말에
못박았고, 지금 지켜지는지 실제로 돌려 확인했다:
① 위치 인자 `<sif> <배포 디렉토리>` ② 대화형 입력 없음 ③ 실패 시 exit≠0
(인자 없이 호출·없는 SIF 둘 다 exit 1 확인. `set -euo pipefail` + `die()`).

**미결 항목 #1 의 설계가 좁혀졌다.** 네 지점 검증을 넣을 때 **노드 배포는 여기서 하면 안
된다** — 상류 표준 빌드가 `deploy_apptainers.sh` 로 따로 하므로 겹친다. '검증만' 넣거나
옵션 뒤에 둘 것(상류 요청). 애초에 내가 필요하다고 본 것도 "검증이 네 곳을 보게" 였으니
방향은 같다.

상류가 바꾼 것: 헤드리스 SIF 의 `/data` 복사는 표준 스크립트에서 빠졌고(우리 스크립트가
백업·설치한다), tar 에 VERSION 이 들어갔고(우리 v39 와 같게), GUI·compute-node-images
복사는 그대로다. `lsprepost` 는 우리 방침대로 보존된다(현재 호스트와 SIF 판이 바이트 동일).

## --all-sites 를 기본이 아니라 옵션으로 둔 이유 (2026-10-17)

배포 지점 넷을 검증이 다 보게 하는 게 목표였지만, **기본 검사에 넣으면 안 된다.**
상류 표준 빌드 순서가

  ① SIF 빌드 → ② GUI·이미지 복사 → ③ deploy_from_sif.sh(→ verify_deploy.sh) → ④ tar → ⑤ Drive·메일

이고 **노드 배포는 ⑤ 뒤에 따로** 돈다. 기본 검사가 노드 일치를 요구하면 모든 표준 빌드가
③에서 exit≠0 으로 멈추고 tar·메일도 못 나간다. 상류가 미리 짚어 줘서 피했다 —
안 그랬으면 "검증을 강화" 하면서 남의 릴리스를 전부 깨뜨릴 뻔했다.

**sha256 으로 본다, VERSION 이 아니라.** 지점에 놓인 것은 SIF 파일 자체이고 같은 커밋을
두 번 빌드해도 바이트는 다르다 — "실제로 배포된 그 파일인가" 를 물어야 한다. VERSION 은
그걸 구분하지 못한다(실제로 headless be9d2b0 / GUI 672e835 처럼 커밋이 갈려 있기도 하다).

**검증한 것**
- 기본 경로 출력이 변경 전과 **바이트 동일** — 상류가 거는 계약(종료 코드)도 그대로
- 정상 상태 `--all-sites` rc=0, GUI SIF 로도 동작
- 음성 대조 4종 전부 rc=1 — 원본이 다른 판 / 원본 없음 / 없는 노드 / SIF 인자 누락
  (특히 첫째가 핵심이다. 이번에 실제로 났던 상태 — 노드는 맞는데 재설치 원본만 옛 판 — 를 잡는다)
