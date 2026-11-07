# v43 배포 기록 (2026-11-04)

소스 `eccde7f` · VERSION 각인 `eccde7f`.
빌드·배포는 상류(pykoocae-53), 검증은 우리.

## 배포 지점 — 네 곳 동일 (직접 sha256 대조)
`94b98c4625302372fcfa50ed6561a618ae2a0c0c255347007a9733943e591a7c`
- 빌드 원본 `apptainer/` · `/data/SmartTwinPostprocessor` ·
  헤드 `/opt/apptainers` · `compute-node-images`
- GUI `a6b95a766d1c2265…`
- 롤백: `/opt/apptainers/SmartTwinPostprocessor_backup_20261104_090503.sif`
  (v42 `1a6e0933…`, 대조 확인)

## 검증 — `.work/deploy_v43/verify_v43.sh` **16/16 ✓**
같은 스크립트로 v42 는 **13 ✗** (known-bad 대조).

| 묶음 | 항목 |
|---|---|
| 각인·CLI | VERSION `eccde7f` · `--parallel-runs` · `--yield-map` · `yield_map` 모듈 |
| 코드 | 캐시 스키마 4 · `scalars_only` · `_flow_pass1` · 적재 손실 보고 · 온톨로지 자체 생성 · JS `isNum`/`safetyFactor`/`hs3dPick` |
| 실덱 100런 | `flow 1패스: 워커 4개로 100런` · `시계열 보유 60/100` · 사이드카 칸(내부 키 누출 0) · CWD 무오염 |

실덱은 `/data/Tests/Test_005_Fibonacci_100` 을 **읽기만** 했다 (입력은 링크,
캐시는 `.work` 안). 원본 무수정.

## 이번 판 sphere 변화
| 커밋 | |
|---|---|
| `845e3ab` | 적재 손실 사유별 보고 · 전멸 시 exit 3 · 깨진 DropSet 이 캠페인을 못 죽이게 |
| `99c1047` | 파트별 항복 한계 + **SI 덱에서 틀리던 안전율 수정** |
| `2eeb7c0` | 흐름 캐시 스키마 4 · 화면 안전율을 분석기와 일치 |
| `e9d841d` | 2패스 축약 표식(`scalars_only`·`dropped`·`energy_flows_reduced`) |
| `752c7e6` | `end_time`·`tool_commit`·`part_id` |
| `c8bd2d7` | 온톨로지 꾸러미 자체 생성 |
| `77ba4e9` | `--from-json` 왕복 칸 보존 |
| `eccde7f` | `-j/--parallel-runs` |

## 🔴 배포 뒤 알아야 할 것
1. **첫 실행은 흐름 캐시를 한 번 다시 짓는다** (스키마 3→4). 100런 기준 순차
   35초 · `-j8` 14초. 두 번째부터 캐시 적중.
2. **SI 덱 캠페인의 CRITICAL 수가 줄어든다.** `--yield-stress`(MPa)를 덱 단위
   응력과 바로 비교하던 것을 고쳤다 — ton-mm-s 덱은 변화 없다.
3. **사이징 틈.** v43 부터 `--parallel-runs` 가 `--help` 에 보여 상류가 새 공식을
   쓰는데, `SPHERE_NEW_MEM_PER_WORKER_GB` 2 → 0.5 GB 는 Pre v131 에 들어간다.
   그 사이 979런이면 `6 + 16×2 = 38 GB` 를 잡는다(실측으론 ~5 GB 면 충분).
   위험하진 않고 대기만 길어진다.

## 실측 (별도 문서 `measurement.md`)
워커 RSS 최대 298 MB · 2패스 축약 run 당 0.98 MB ·
M3_P2 환산 85 GB → 5.2 GB.

---

## v44 (`e86fd1b`, 2026-11-06) — sphere 무회귀 확인

v44 는 렌더·그림·온톨로지 쪽 판이고 **`koo_sphere_report` 변경 0건**이다
(`binout_reader`·`contact_map`·`energy_flow_builder` 도 0건). 흐름 캐시 스키마는
4 그대로라 **v44 에서 캐시 재생성은 일어나지 않는다.**

회귀 확인: 실덱 `Test_005_Fibonacci_100` 100런의 **정규화 사이드카가 v43 과
바이트 동일(차이 0)**. 배포 지점 `a1ca45cc` 세 곳 일치, v43 백업 `94b98c46`.

### 🔴 검증 전제가 틀렸던 것 — 호스트 `~/.local` 가림
v44 굽기가 `%test` 에서 pyvista 없음으로 실패하면서 드러났다.
SIF 안에서 `lasso`·`numpy`·`rich`·`yaml`·`pyvista`·`PIL`·`matplotlib` 이
**전부 `/home/koopark/.local/`** 에서 잡히고 있었다. 호스트 홈이 바인드돼
SIF 안 패키지를 **가린다.**

즉 v43 의 16/16 검증도 **호스트 패키지로 돈 것**이었다 — "이 호스트에서 되더라"
를 본 것이지 "노드에서 도는 판" 을 본 게 아니다.

`PYTHONNOUSERSITE=1` 로 걷으면
| | |
|---|---|
| `lasso`·`numpy`·`rich`·`yaml` | **SIF 안에 있다** — 가려졌을 뿐 |
| `pyvista`·`PIL`·`matplotlib` | **없었다** (v44 def 에서 고정 설치로 추가) |

**sphere 는 안전하다** — SIF 자체 패키지로 돌려도 결과가 완전히 동일하다.
그래도 앞으로 **배포 판정은 `--no-home` / `PYTHONNOUSERSITE=1` 로** 한다.
상류도 판정기를 그렇게 바꿨다.

빌드 시점 `%test` 는 호스트 홈을 안 본다(근거: 검사가 import 이고 v44 가 거기서
실패했다. `%test` 에 `set -e` 도 있어 실패가 빌드를 막는다). v43 이 통과한 것은
홈 때문이 아니라 **그림 의존성 검사가 v44 에서 새로 들어갔기** 때문이다.

### 도구
`.work/deploy_v44/sphere_regress.sh <sif> <꼬리표>` — 같은 덱을 돌려 사이드카를
정규화 비교한다(`test_dir`·`generated_at`·`tool_builds` 제외, 부동소수 9자리).
**같은 SIF 두 번 돌려 차이 0 인 것을 먼저 확인**하고 쓴다 — 정규화가 비결정적이면
헛경보를 낸다.

---

## v45 (`5e589fb`) · v46 (`229806e`) — sphere 회귀

### v45 — 회귀 **생략**, 근거 있음
sphere 가 `koo_deep_report` 에서 쓰는 것은 다섯이다 —
`core.binout_reader` · `core.contact_map` · `core.contact_metrics` ·
`core.energy_flow_builder` · `ontology.emit`.
v45 가 바꾼 파일에 **이 다섯이 하나도 없다.** `job_builder` 는 sphere 가 안 쓰고
(참조 0곳), `AnalysisTypes.hpp` 변경도 `bool zoom_crop` 하나로 렌더 설정이지
`analysis_result.json` 꼴이 아니다. → 돌릴 이유가 없어 돌리지 않았다.
배포 지점 `b273f5a9` 세 곳 일치만 확인.

### v46 — 회귀 **통과** (`bbd1d1dc`, GUI `96659d89`)
`07d3e96`(ontology.emit 꾸러미 warnings)이 들어가는 판이라 돌렸다.
배포 여섯 지점(헤드리스·GUI × `/opt`·`/data`·compute-node-images) 모두 일치,
v45 백업 `b273f5a9` 확인.

| | 결과 |
|---|---|
| sphere 사이드카 | **차이 0** — 실덱 100런 정규화 바이트 동일 |
| 꾸러미 | 변동값만(`produced_at`·`created_utc`·`version`), 객체 4088·단위 동일 |

### 🔴 "키가 없다" 를 두 가지로 갈라 본 것
정상 캠페인에서는 v45·v46 **둘 다 `warnings` 키가 없다.** 거기서 멈추면
**"변경이 안 실렸다"** 와 **"없으면 키를 안 만드는 규약"** 을 구분할 수 없다.
그래서 덱(`.k`)·binout 이 없는 4런 캠페인을 **링크 없이 합성**해 태웠다.

| | 정상 캠페인 | 덱 없는 캠페인 |
|---|---|---|
| v45 | 키 없음 | **키 없음** |
| v46 | 키 없음 | **1건** |

v46 이 낸 사유 —
`덱(.k)을 찾지 못했다(output/Run_000) — 재질 · 초기 속도 · 접촉 없이 지었다`

읽을 게 다 있으면 키를 안 만들고, 못 읽으면 무엇을 왜 못 담았는지 적는다.
**기능이 있다는 것과 도는 것은 다르다** — 없는 쪽을 일부러 만들어야 갈린다.

### 성능 수치 읽을 때 주의
v46 회귀가 111.3초로 기준선(51.7초)의 두 배였는데 **성능 회귀가 아니다** —
같은 시각 상류가 deep 런(한 번에 7 GB)을 돌려 생긴 경합이다. 사이드카가 바이트
동일한 것이 그 근거다. 사이징 수치는 한가할 때 잰 50초대를 쓴다.
