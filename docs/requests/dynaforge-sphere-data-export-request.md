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
