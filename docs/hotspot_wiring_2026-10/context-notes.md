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
