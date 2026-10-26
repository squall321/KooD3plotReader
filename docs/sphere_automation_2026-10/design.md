# sphere_report 자동화 수정 — 설계 (2026-10-26, **착수 전 / 사용자 승인 대기**)

상류(pykoocae-53) 요청. 계기는 M3_P2 979런이 **24h TIMEOUT · MaxRSS 84.7 GB**
를 친 것. pyKooCAE 쪽(sbatch 사이징·`--help` 탐지·KMM yield 맵 생성)은 그쪽,
koo_sphere_report 쪽 셋이 우리 몫. 상류와 왕복해 **설계는 확정**, 코드는 미착수.

## (2) 로딩 실패를 조용히 넘기지 않는다
`--test-dir` 에서 `analysis_results` 에 `Run_*` 가 있는데 `successful_runs == 0`
이면 **사유를 stderr 에 적고 exit 3**. (실제 원인이었던
`output/Run_*/DropSet.json` 누락 건수 등). 부분 손실(적재 < `Run_*` 수)이면
개수를 적은 경고 한 줄. — 이 저장소 "무음 실패 금지" 규칙과 같은 방향.

## (3) `--parallel-runs N` + **2패스 메모리 축약** (같은 릴리스에)

### 상류 원안의 문제 — 메모리가 안 줄어든다
원안은 "병렬 선행 패스로 캐시를 채우고 기존 순차 루프를 돈다" 였다. 그러면
24h 는 풀리지만 **84.7 GB 는 그대로**다. `loader.py:1077-1081` 이 모든 run 의
흐름을 동시에 들고 그대로 반환하기 때문이다.
```python
if g:
    energy_flows[sr.run_folder] = g     # 979개가 전부 쌓인다
```
0.087 GB × 979 = **85.2 GB** ← 측정 84.7 GB 와 일치. 봉우리는 캐시 생성 비용이
아니라 **최종 누적분**이다.

### 확정안 — 캐시를 두 번 쓴다
흐름 소비처가 넷인데 **시계열이 필요한 건 하나뿐**이다.
| 소비처 | 범위 | 필요한 것 |
|---|---|---|
| `_compact_energy_flows` | **상위 60개만** (`_FLOW_DETAIL_LIMIT = 60`) | 시계열 |
| `_contact_profile` | 전 각도 | 파트쌍 스칼라 pf/ti/tw |
| `_contact_trust` | 전 각도 | `contact_metrics` 요약 |
| `_attach_part_energy` | 전 각도 | 파트별 IE/KE (sr 에 부착) |

게다가 상위 60개 선정 기준이 `max(edge.peak_force)` — **스칼라**라 적재 중 계산된다.

- **1패스(병렬, ProcessPoolExecutor)**: 흐름 생성 → 캐시 기록 → **스칼라만 남기고
  전체 dict 폐기**. 워커는 큰 것을 반환하지 않는다.
- **2패스**: 스칼라로 순위 → 상위 60개만 **캐시에서** 재적재(히트라 재파싱 없음).

### 실측 (mini26, 캐시 26건)
| | run 당 |
|---|---|
| 전체 dict | **0.60 MB** (RSS 증가 교차확인 0.7 MB) |
| 스칼라만 | **0.0005 MB** |
| **축약 배수** | **1266×** |

⚠ 절대값은 전이 안 된다(mini26 은 작은 모델, M3_P2 는 87 MB/run). **전이되는 건
구조** — 덩치는 전부 시계열 배열, 스칼라는 파트·엣지 개수만큼의 숫자.

M3_P2 대입: 스칼라 0.07 GB + 상세 60×87 MB 5.2 GB = **≈ 5.3 GB** (85 GB → 16배↓)

상류 사이징은 실측 전까지 `6 GB + W × 2 GB` 유지(보수적). (3) 구현 후 **워커 RSS
와 1패스 run 당 시간**을 실캠페인에서 재서 전달.

## (4) 파트별 항복응력

### 입력
KMM 이 DropSet.json 에 추가 (`model.parts` 는 불변 — 옛 도구 무영향):
```json
"model": {"part_yield": {
  "unit": "MPa" | "Pa" | null,
  "parts": {"<pid>": {"yield": <덱 단위>, "source": "MAT_024 SIGY" | ..., "mid": <int>}}
}}
```
첫 DropSet.json 에서 기본 읽기(경로 배선 불요). `--yield-map FILE` 은 명시적
덮어쓰기 — **MPa 가 아니라 덱 단위**로 통일(두 경로 규약이 다르면 SI 덱에서
1e6 배 어긋난다).

### 🔴 환산하지 않는다 — 이 결정이 핵심
이 도구는 **응력을 환산하지 않는다.** 단위 검출은 G 환산과 라벨에만 쓰이고
`peak_stress` 는 덱 단위 그대로다 (`tests/test_sidecar_units.py` 가 못박음).
안전계수는 **비율**이라 양쪽이 덱 단위면 약분된다 — 환산 자체가 불필요하다.

넣으면 오히려 위험하다. 검출(`loader.py:225-298`)은 **미검출로 떨어지는 경로가
넷**(밀도 못 읽음 / koo_impact_report 임포트 실패 / 밀도 애매 / ENDTIM 수상).
지금은 그 불확실성이 peak-G·라벨에만 머무는데, 안전계수 경로에 넣으면
"검출 실패 → 1e6 배 틀린 SF" 로 번진다.

### `--yield-stress` 폴백 해석 (우리가 정한 것)
**MPa 유지** — 사람이 넣는 재료 물성이다. 덱 단위로 재해석하면 SI 덱에서
"350 Pa" 가 된다.
| 상황 | 동작 |
|---|---|
| `part_yield` 에 있는 파트 | 덱 단위끼리 비교, **환산 없음** — 검출과 무관하게 동작 |
| 맵에 없고 단위 검출됨 | `--yield-stress`(MPa) → 덱 단위 환산 후 비교 |
| 맵에 없고 **단위 미검출** | **비교 생략** + 건너뛴 파트 수·사유(`UNIT_NOTE`)·해결법 |

`G_FACTOR` 는 미검출이어도 직전 값으로 계속 환산하는데 여기서 다르게 가는 이유 —
peak-G 는 **보여 주는 값**이라 가정을 적고 보여 주는 게 낫지만, 항복 초과는
CRITICAL 이 붙는 **합부 판정**이다. 틀린 CRITICAL·놓친 CRITICAL 은 설계 결정을
오도한다. 보여 주는 값과 판정하는 값은 다르게 다룬다.

### 맵 위생 검사
관측 `peak_stress` 분포와 대조해 맵의 yield 가 전부 몇 자릿수 아래면
"응력이 아닌 값일 수 있다" 경고 + 보고서 표기. 재료 지식을 박지 않고 **자릿수만**
본다. 계기는 상류가 찾은 KMM 버그(`*MAT_PIECEWISE_LINEAR_PLASTICITY` 비-`_TITLE`
변종에서 EPS/ES 뒤바뀜 — 뒤바뀐 맵이 오면 yield 가 변형률(0.01)로 들어와 거의
모든 각도가 CRITICAL 로 뜬다). KMM 수정과 별개로 **판이 섞일 때**를 위해 둔다.

## 🔴 함께 고칠 기존 결함 — 지금도 틀리고 있다
`analyzer.py:105-141`
```python
yield_stress = report.yield_stress          # --yield-stress, 도움말 "(MPa)"
if yield_stress > 0 and worst_stress > yield_stress:   # worst_stress 는 덱 단위
    sf = yield_stress / worst_stress
    detail=f"Peak {worst_stress:.1f} MPa at ..."       # 덱 단위인데 MPa 라고 찍는다
```
SI 덱에서 `--yield-stress 350` → 350 을 2.7e8 Pa 와 비교해 `sf ≈ 1.3e-6`,
화면엔 "Peak 270000000.0 MPa". 항복 판정과 안전계수가 통째로 무의미한데 경고가
없다. M3_P2 의 `YIELD_STRESS=350` 고정은 ton-mm-s 덱이라 **우연히** 맞았을 뿐.

## 착수 순서
(2) → (4, 위 단위 결함 포함) → (3). (3) 뒤에 워커 RSS 실측 → 상류 전달 → v42.
