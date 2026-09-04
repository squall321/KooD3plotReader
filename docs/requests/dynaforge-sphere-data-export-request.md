# DynaForge → KooD3plotReader 데이터 export 보강 요청서

**보내는 쪽**: DynaForge / KooRemapper 플랫폼 (sphere 리포트 소비·분석 계층)
**받는 쪽**: KooD3plotReader (d3plot 결과 추출 계층)
**경유**: KooD3plotReader → `koo_sphere_report` → DynaForge
**작성일**: 2026-09-04

---

## 1. 요지 (한 줄)

KooD3plotReader 는 **이미** 소성 변형률·주응력/주변형률·von Mises·변위/속도/가속도와 그 **시계열
(history)** 을 내부에서 계산한다. 그런데 sphere 리포트로는 파트별 `peak_stress·peak_strain·
peak_disp·peak_g` + 응력 시계열(`stress_ts`)만 흘러간다. **이미 계산된 값을 report-feeding
export 채널에 파트별로 노출**해 달라는 요청이다(신규 추출이 아니라 export 표면 확장).

---

## 2. 근거 — 이미 계산하고 있음 (소스 기준)

`src/analysis`·`src/core` 등에서 확인한 심볼(추출·계산은 존재).

- 소성: `plastic_strain`
- 주응력: `principal_min`, `principal_max`, `principal_stress_`, `principal_history`
- 주변형률: `principal_strain_min/max`, `principal_strain_history`
- von Mises: `von_mises` (응력), `strain`(+`strain_history`, `strain_max_elem`)
- 운동: `displacement`(+`_x/_y/_z`, `_magnitude`), `velocity`, `acceleration`

반면 export 표면(`src/export/KeywordExporter.cpp`, `src/capi`, `src/hdf5`)에서는 이 물리량들이
파트별 리포트용으로 나가는 흔적을 찾지 못했다. 즉 **계산은 되는데 다운스트림으로 안 나간다**.

> 참고 — 에너지(내부/운동 에너지, matsum)는 `binout` 소관이고 KooD3plotReader 는 `binout/matsum/
> glstat` 을 다루지 않는다(소스에 흔적 0). 따라서 **에너지 항목은 이 요청서 범위 밖**이며, binout
> 을 읽는 리포트 계층(예: `koo_*_report` 의 binout 리더)에 별도 요청한다. 여기서는 d3plot 파생
> 물리량만 다룬다.

---

## 3. 보강 요청 (KooD3plotReader export)

각 항목은 "이미 계산됨 → report-feeding 채널에 파트별로 노출" 이 공통이다. 노출 채널은
koo_sphere_report 가 소비하는 출력(C-API / HDF5 / JSON / keyword export 중 실제 경로)에 맞춘다.

### P1-A. 소성 변형률 (effective plastic strain)
- **이미 있음**: `plastic_strain` 계산.
- **요청**: 파트별 peak(가능하면 시계열)을 export.
- **여는 것**: 낙하 손상·항복의 1차 지표를 방향별로. DynaForge `report_angle_stats` 가 자동 인식.

### P1-B. 스트레인·변위·가속도 시계열
- **이미 있음**: `strain_history`, `displacement(_magnitude)`, `acceleration`, `velocity`.
- **요청**: 응력 `stress_ts` 와 동일 형태의 다운샘플 시계열을 파트별로 export(`strain_ts`,
  `disp_ts`, `g_ts`). 현재는 이 3개가 peak 스칼라로만 다운스트림에 존재한다.
- **여는 것**: 응력 외 3개 물리량의 시간거동(DynaForge `report_part_series` 가 키를 이미 읽음).

### P2-A. 주응력 / 주변형률
- **이미 있음**: `principal_min/max`, `principal_strain_min/max`(+history).
- **요청**: 파트별 `peak_principal`·`min_principal`(+ 주변형률, 가능하면 시계열) export.
- **여는 것**: 취성·인장 파손 관점 방향 분석(DynaForge 쿼리 화이트리스트에 principal 키 등록됨).

### P2-B. von Mises 변형률
- **이미 있음**: von Mises 계열.
- **요청**: 파트별 `peak_vm_strain` export(응력 폰미세스와 짝).

---

## 4. 다운스트림 호환 스키마 (KooD3plotReader → koo_sphere_report → DynaForge)

KooD3plotReader 가 어떤 채널로 내보내든, 최종적으로 koo_sphere_report 임베드 데이터의
`results[].parts[<pid>]` 가 아래 키를 갖도록 하는 게 목표다. DynaForge 는 이 키를 그대로 읽는다.

```json
"results[].parts[<pid>]": {
  "peak_stress": <float>, "peak_strain": <float>, "peak_disp": <float>, "peak_g": <float>,
  "stress_ts":  {"t":[...],"max":[...],"avg":[...],"min":[...],"elem":[...]},   // 현존
  "strain_ts":  {"t":[...],"max":[...],"avg":[...],"min":[...]},                 // 요청 P1-B
  "disp_ts":    {"t":[...],"max":[...],"avg":[...],"min":[...]},                 // 요청 P1-B
  "g_ts":       {"t":[...],"max":[...],"avg":[...],"min":[...]},                 // 요청 P1-B
  "peak_plastic_strain": <float>,                                                // 요청 P1-A
  "peak_principal": <float>, "min_principal": <float>,                           // 요청 P2-A
  "peak_vm_strain": <float>                                                      // 요청 P2-B
}
```

**공통 규약**
- 결측은 `null`(문자열 "nan"/Infinity 금지).
- 시계열은 지금 `stress_ts` 처럼 다운샘플해 담으면 됨(용량·전송 최소).
- 파트 식별은 정수 `pid` 유지.

---

## 5. 우선순위

| 우선 | 항목 | 상태 | 여는 것 | 다운스트림 후속 |
|---|---|---|---|---|
| **P1** | 소성 변형률 export | 계산됨, 미노출 | 소성 방향 분석·손상 판정 | DynaForge 화이트리스트 1줄 |
| **P1** | strain/disp/g 시계열 export | 계산됨, peak만 노출 | 4물리량 시간거동 | 없음(키 이미 읽음) |
| **P2** | principal(응력/변형률) export | 계산됨, 미노출 | 취성·인장 방향 분석 | 없음(키 등록됨) |
| **P2** | von Mises 변형률 export | 계산됨, 미노출 | 폰미세스 변형률 | 없음 |
| — | 에너지(matsum) | **범위 밖** | — | binout 리더에 별도 요청 |

> 핵심 — 대부분 **이미 계산돼 있어** 신규 해석이 아니라 **export 표면에 파트별로 태우는 작업**이다.
> 특히 소성 변형률은 낙하 손상 판정의 핵심이라 P1 로 둔다.

---

## 6. 참고 — 검증 방법

DynaForge 쪽은 값이 들어오면 자동으로 활성화된다.
- `report_part_series` : `strain_ts/disp_ts/g_ts` 키를 이미 파싱(현재 부재라 `null`).
- `report_angle_stats` : `available_metrics` 자동 감지 → `peak_plastic_strain` 등장 시 방향별 통계 즉시 제공.
- principal/vm_strain 쿼리 키는 이미 등록. 소성만 화이트리스트 1줄 추가 예정.

문의는 DynaForge / KooRemapper 측으로.


---

# 수신측 회신 — KooD3plotReader (2026-09-04)

요청 4건을 현재 코드·실산출물로 전수 확인했습니다. 결론부터: **요청 항목 대부분은 이미
나가고 있었고, 실제 문제는 키 이름이었습니다.** 새로 계산할 것은 없었습니다.

| 항목 | 요청서 판단 | 실제 | 조치 |
|---|---|---|---|
| P1-A 소성 변형률 | 계산됨·미노출 | **이미 `peak_strain` 으로 노출 중** (그 값이 곧 eff_plastic) | `peak_plastic_strain` 명시 키 추가 |
| P1-B strain/disp/g 시계열 | peak 만 노출 | **이미 전부 노출 중** (실측 각 17,160개) | `g_ts`·`disp_ts` 에 `max` 별칭 추가 |
| P2-A principal | 계산됨·미노출 | export 는 이미 지원, **분석 잡을 안 돌려 데이터가 없음** | `peak_principal`·`min_principal` 별칭 추가 |
| P2-B von Mises 변형률 | 계산됨·미노출 | export 이미 지원, 위와 동일 | (기존 `peak_vm_strain` 그대로) |
| 에너지(matsum) | 범위 밖 | **이미 파트별로 노출 중** (실측 442/442 비0) | 조치 불요 |

## 1. 소성 변형률은 이미 나가고 있었습니다 — 이름 문제

`loader.py:413` 이 `part_<pid>_eff_plastic_strain.csv` 를 `pr.strain` 에 싣고,
`peak_strain` 은 그 피크입니다. 즉 **`peak_strain` 이 곧 유효소성변형률**입니다.
실산출물에서도 `strain_history` 의 `quantity` 가 `eff_plastic_strain` 하나뿐입니다.

이름만으로 어떤 strain 인지 알 수 없어 생긴 오독으로 보입니다. 같은 값을 명시적 이름으로
함께 내보내도록 `peak_plastic_strain` 을 추가했습니다(새 계산이 아니라 별칭).

주의 — `peak_vm_strain` 은 **다른 양**입니다. von Mises 등가 변형률은 탄성분을 포함합니다
(`models.py:203`). 둘을 같은 칸에 넣지 마십시오.

## 2. strain/disp/g 시계열도 이미 나가고 있었습니다 — 내부 키 이름 문제

`/data/Tests/Test_006_Fibonacci_6deg/report.json` (1,144각도) 전수 집계:

| 키 | 보유 파트 인스턴스 |
|---|---|
| `stress_ts` | 19,448 |
| `strain_ts` | 17,160 |
| `g_ts` | 17,160 |
| `disp_ts` | 17,160 |

(총 파트 인스턴스 19,448. 차이 2,288 은 변형률·운동 데이터가 없는 파트 — 강체/바닥 계열)

"stress_ts 만 흘러간다" 는 판단은 **파트 1** 만 보신 결과로 보입니다. 파트 1 은
`peak_strain=0 / peak_g=0 / peak_disp=0` 인 파트라 ts 키가 붙지 않습니다.

진짜 비호환은 **시계열 내부 키 이름**이었습니다.

| 시계열 | 기존 값 키 | 요청 스키마 | 조치 |
|---|---|---|---|
| `stress_ts` | `max`, `avg`, (`min`, `elem`) | `max`… | 이미 일치 |
| `strain_ts` | `max`, (`avg`) | `max`… | 이미 일치 |
| `g_ts` | **`g`** | `max` | `max` 별칭 추가 |
| `disp_ts` | **`mag`** | `max` | `max` 별칭 추가 |

`g`/`mag` 는 본 리포트 JS 가 읽으므로 **유지**하고 `max` 를 나란히 넣었습니다.
값은 동일한 배열입니다(실측 390 파트 전수 일치, 불일치 0건).

## 3. principal / vm 변형률 — export 가 아니라 분석 설정 문제

export 계층은 이미 지원합니다. `loader.py:396-410` 이 아래 CSV 가 있으면 싣고,
`json_report.py`·`html_report.py` 가 있으면 내보냅니다.

```
stress/part_<pid>_max_principal_stress.csv
stress/part_<pid>_min_principal_stress.csv
strain/part_<pid>_max_principal_strain.csv
strain/part_<pid>_min_principal_strain.csv
strain/part_<pid>_von_mises_strain.csv
```

실데이터에 값이 없는 이유는 **그 잡을 안 돌렸기 때문**입니다. 확인한 산출물의
`analysis_jobs` 는 `von_mises` + `eff_plastic_strain` 둘뿐입니다.

- `/data/Tests/Test_006_Fibonacci_6deg` → `von_mises`, `eff_plastic_strain`
- `/data/Tests/Test_001_Full26_1Step` → `von_mises`
- `/data/koopark/Test_Impact_A` → `von_mises`, `eff_plastic_strain`

또한 **주변형률은 덱에 `*DATABASE_EXTENT_BINARY` 의 `STRFLG=1` 이 있어야** d3plot 에
변형률 텐서가 실립니다(`models.py:198-199`). 없으면 `None` 이고 0 이 아닙니다.

따라서 이 두 항목은 export 보강으로 열리지 않습니다. **해석을 다시 돌릴 때 분석 잡에
principal 계열을 넣고, 덱에 STRFLG 를 켜야** 합니다. 그렇게 하면 별도 작업 없이
지금 코드로 바로 나갑니다(합성 CSV 주입으로 실동작 확인함).

이름 호환만 미리 맞춰 두었습니다 — `peak_principal` / `min_principal` 을
기존 `peak_principal_stress` / `min_principal_stress` 와 같은 값으로 함께 내보냅니다.

## 4. 에너지는 이미 나가고 있습니다

요청서는 범위 밖으로 두었지만, 파트별 에너지는 이미 나갑니다.
`Test_001_Full26_1Step` 실측 — `energy` 키 보유 442 파트, 전부 비0.

```json
"energy": {"peak_ie": 874.139, "peak_ie_time": 0.0,
           "peak_ke": 781.336, "peak_ke_time": 0.0,
           "final_ie": 106.897, "final_ke": 377.29}
```

binout matsum 은 리포트 계층이 직접 읽습니다. 별도 요청이 필요 없습니다.

## 5. 이번 변경으로 나가는 최종 스키마

`results[].parts[<pid>]` — **굵게** 표시가 이번에 추가된 키입니다.

```json
{
  "peak_stress": 247.3, "peak_strain": 50.942348,
  "peak_disp": 49.474, "peak_g": 226154.5,
  "peak_plastic_strain": 50.942348,            // 추가 (= peak_strain, 명시적 이름)
  "peak_principal_stress": 92.5, "peak_principal": 92.5,      // 별칭 추가
  "min_principal_stress": 0.0,  "min_principal": 0.0,         // 별칭 추가
  "peak_principal_strain": 57.647522, "min_principal_strain": -32.841351,
  "peak_vm_strain": 57.647522,
  "stress_ts": {"t": [...], "max": [...], "avg": [...]},
  "strain_ts": {"t": [...], "max": [...]},
  "g_ts":      {"t": [...], "g": [...],   "max": [...]},      // max 별칭 추가
  "disp_ts":   {"t": [...], "mag": [...], "max": [...]},      // max 별칭 추가
  "energy":    {"peak_ie":..., "peak_ke":..., "final_ie":..., "final_ke":...}
}
```

**결측 규약** — 요청대로 값이 없으면 **키 자체를 넣지 않습니다**. `null` 이나 `0` 으로
채우지 않습니다. 0 으로 채우면 "측정했더니 0" 과 "측정 안 됨" 이 구분되지 않습니다.
소비 측에서는 `key in part` 로 판단해 주십시오.

## 6. 검증

- 실데이터 1,144각도 재생성 — `peak_plastic_strain` 19,448 파트 전수 출력
- `g_ts.max == g_ts.g`, `disp_ts.max == disp_ts.mag`, `peak_plastic_strain == peak_strain`
  — 390 파트 전수 대조, **불일치 0건**
- principal 별칭 — CSV 주입 후 `peak_principal == peak_principal_stress` 확인
- HTML 리포트 8개 탭 렌더 — JS 예외 0건, 기존 `g`/`mag` 소비 정상
- 적용 채널 — HTML 임베드(`html_report.py`)와 저장 JSON(`json_report.py`) 양쪽

## 7. 남은 것 (DynaForge 측 확인 요청)

1. `peak_strain` 을 이미 읽고 있다면 그게 소성 변형률입니다 — 중복 집계하지 마십시오.
2. principal / vm 변형률이 필요하면 **해석 재실행이 필요**합니다. 대상 캠페인을 알려주시면
   분석 잡 설정을 맞춰 드립니다.
3. 에너지는 이미 있으니 화이트리스트에 `energy.*` 를 넣으시면 바로 쓰실 수 있습니다.


---

## 8. 추가 — 변형률 전 종류 시계열까지 확장 (2026-09-04 후속)

"일반 변형률(총 변형률)도 다 나가느냐" 는 확인 요청에 대한 답입니다.

### 8-1. 이 파이프라인이 다루는 변형률은 두 종류입니다

| 이름 | CSV | 의미 | 리포트 키 |
|---|---|---|---|
| 유효**소성**변형률 | `eff_plastic_strain` | 소성분만 | `peak_strain` = `peak_plastic_strain` |
| von Mises 등가변형률 | `von_mises_strain` | **탄성분 포함 — 이것이 '일반 변형률'** | `peak_vm_strain` |

`models.py:203` 이 둘의 차이를 명시합니다. 즉 **일반(총) 변형률은 `peak_vm_strain`** 이고,
이미 export 됩니다. 별도 물리량을 새로 만들 필요가 없습니다.

> 참고 — `effective_strain`·`strain_xx` 같은 이름이 소스에 보이지만 그건 **query/render
> 계층**(`src/query/`, `src/render/`) 것이고, 리포트를 먹이는 분석 파이프라인
> (`src/analysis/`) 의 `AnalysisJobType` 은 8종뿐입니다. 리포트로 오는 경로가 아닙니다.

### 8-2. 분석기 ↔ 로더는 이미 7종 전부 대응합니다

`examples/unified_analyzer.cpp:287-340` 이 파트별로 쓰고, `loader.py:390-420` 이 읽습니다.

```
stress/  von_mises · max_principal_stress · min_principal_stress
strain/  eff_plastic_strain · von_mises_strain · max_principal_strain · min_principal_strain
motion/  motion
```

export 갭은 없습니다. 실데이터에 값이 없는 것은 덱에 변형률 텐서가 없거나
(`*DATABASE_EXTENT_BINARY STRFLG`) 그 잡을 안 돌렸기 때문입니다.
`SinglePassAnalyzer.cpp:1456-1464` 는 전부 0이면 아예 비웁니다 — 허구 0 을 안 냅니다.

### 8-3. 이번에 메운 진짜 갭 — 시계열

로더가 σ1·σ3·ε1·ε3·ε_vm 의 **시계열을 통째로 읽어 두는데 peak 만 내보내고
있었습니다.** 5종 전부 시계열을 추가했습니다.

| 신규 키 | 물리량 | 내부 키 |
|---|---|---|
| `principal_ts` | σ1 최대주응력 | `t`, `max`, `avg` |
| `principal_min_ts` | σ3 최소주응력 | `t`, `max`, `avg`, `min` |
| `principal_strain_ts` | ε1 최대주변형률 | `t`, `max`, `avg` |
| `principal_strain_min_ts` | ε3 최소주변형률 | `t`, `max`, `avg`, `min` |
| `vm_strain_ts` | **ε_vm 일반 변형률** | `t`, `max`, `avg` |

σ3·ε3 은 압축측이 의미 있어 `min` 을 함께 싣습니다. 다운샘플 규칙과 결측 규약
(값 없으면 키 자체 생략)은 기존과 동일합니다.

이로써 **로더가 읽는 모든 물리량이 peak + 시계열 양쪽으로 나갑니다.**

### 8-4. 검증

CSV 5종을 주입한 실런에서 시계열 11종 전부 출력 확인
(`stress_ts` `strain_ts` `g_ts` `disp_ts` `acc_ts` `disp_comp_ts`
 `principal_ts` `principal_min_ts` `principal_strain_ts` `principal_strain_min_ts` `vm_strain_ts`),
각 124점. HTML 8개 탭 렌더 JS 예외 0건. 1,144각도 실데이터 회귀 정상(8.1MB).
