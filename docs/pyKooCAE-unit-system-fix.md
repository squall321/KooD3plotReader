# pyKooCAE — Unit-system Mismatch 버그 진단 + 수정 제안

작성일: 2026-06-01
대상 프로젝트: **pyKooCAE** (host: `/home/koopark/serviceApptainers/appt313/opt/pyKooCAE/`)
배포 sif: `SmartTwinPreprocessor.sif` (md5 `fb77b5ba7bf77f42bec501dc3a0e5ac7`, 2026-05-31 빌드)
진단 데이터셋: `/data/koopark/Test_Impact_A/` (25-위치 DOE 부분충격, cumulative mode)

---

## 1. 한 줄 요약

`CumulativeScenarioRunner.py:1227-1229` 가 **KooMeshModifier 가 인식하지 못하는 키 이름**으로
step_config 를 작성한다. 그 결과 **사용자의 모든 density / Young's modulus / Poisson 입력값이 silent
하게 무시되고**, KooMeshModifier 의 hardcoded SI default (`ρ=7800, E=2.07e11`) 가 ton-mm-s
단위계 deck 의 `*MAT_ELASTIC_TITLE ImpactorMaterial` 카드에 그대로 쓰여 단위 혼용 deck 이 생성된다.

deck 의 다른 부품(*MAT 23–27)은 ton-mm-s (ρ ≈ 2.8e-9 ton/mm³, E ≈ MPa) 이지만 impactor MAT 29 만
SI 형식 (ρ = 7800, E = 2.07e11) — LSDYNA 가 그 값을 그대로 사용해 impactor effective mass 가
약 10¹² 배 비현실적으로 크고, 결과 d3plot 의 peak stress / acceleration 도 비물리.

P0 수정 (키 이름 1줄) 하나만 적용해도 cumulative DOE 의 단위 혼용 문제 100 % 해결.

---

## 2. 사용자 영향 (사례: Test_Impact_A)

| 측정값 | 잘못된 단위 혼용 deck 의 시뮬 결과 |
|---|---|
| WORST PEAK G (HTML 보고서) | 6,351 G (deck 결함 효과로 비현실적 spike) |
| WORST σ (HTML 보고서) | 85 GPa (강철 항복 250 MPa 의 약 340 배) |
| d3hsp impactor mass | 0.5e-4 tonne (mesh 사이즈와 부정합) |

호스트 측 후처리 (koo_impact_report) 의 단위 라벨링은 정확하므로 화면 표시는 그럴듯해 보이지만,
**시뮬 결과 자체가 잘못된 물리** 라는 점이 본 버그의 본질.

---

## 3. 진단 경로 — 어떻게 키 이름 mismatch 라고 결론지었나

### 3.1 KooMeshModifier 가 인식하는 키 (binary strings 추출)

노드 sif 안 `KooMeshModifier.bin` 의 strings 에서 발견된 step_config 입력 식별자:

```
aDensityImpactor          aDensityImpactorFront        aDensityWall
aPoissonRatioImpactor     aPoissonRatioImpactorFront   aPoissonRatioWall
aMaterialIDImpactor       aMaterialIDImpactorFront     aMaterialIDWall
aCreateSphereImpactorPart aCreateCylinderImpactorPart  aCreateWallPart
aImpactorMaterial         aImpactorMaterialFront
aRigidWall                aRigidWallPlanar             aRigidWallPlanarID
a_hardcoded_defaults                                   ← hardcoded default 가 존재함을 시사
```

→ KooMeshModifier 가 step_config 의 라인을 파싱할 때 기대하는 키는
**`DensityImpactor`, `YoungsModulusImpactor`, `PoissonRatioImpactor`**.

### 3.2 두 Runner 의 출력 키 비교

| Runner | 사용된 키 | KooMeshModifier 매칭? |
|---|---|---|
| `DropWeightImpactWorkflow.py:533-535` | `DensityImpactor` / `YoungsModulusImpactor` / `PoissonRatioImpactor` | ✅ |
| **`CumulativeScenarioRunner.py:1227-1229`** | **`Density` / `YoungsModulus` / `PoissonRatio`** | ❌ silent miss |

`KooChainRun submit --mode cumulative` (default) 흐름이 `CumulativeScenarioRunner` 거치므로
**모든 cumulative DOE 가 영향받음**. Test_Impact_A 도 cumulative mode.

### 3.3 검증 — step_config 와 deck 출력의 동시 확인

`runner_config.json` 의 `simulation_params.impact` 를 ton-mm-s 값으로 수정 후 DOE 재실행:

- **step_config 출력**: `Density,7.85e-09`, `YoungsModulus,201000.0` ← 우리 수정값 정확히 전파됨
- **deck 출력**: `*MAT_ELASTIC_TITLE ImpactorMaterial \n 29 7.800e+03 2.070e+11 3.000e-01` ← 여전히 hardcoded SI

→ step_config 의 `Density,...` 라인이 KooMeshModifier 에 도달했지만 인식되지 않고 무시됨.
KooMeshModifier 는 자체 hardcoded SI default 만 사용.

이게 키 이름 mismatch 라는 결정적 증거.

---

## 4. 수정 제안

### 🔴 P0 — step_config 키 이름 일치 (Critical, 1줄짜리 fix)

**파일**: `Runner/CumulativeScenarioRunner.py`

**위치**: `_build_step_config()` 안 `mode == "IMPACT"` 분기의 step_config 템플릿 (lines 1227-1229)

**진단**: 키 이름이 KooMeshModifier 가 기대하는 것과 다름. impactor MAT 의 모든 사용자 입력값이
silent 손실되고 hardcoded SI default 가 deck 에 쓰임.

**패치 (P0a — 키 이름 만)**:

```diff
--- a/Runner/CumulativeScenarioRunner.py
+++ b/Runner/CumulativeScenarioRunner.py
@@ -1224,9 +1224,9 @@ Type,{impact_params.get('type', 'Sphere')}
 Dimension,{impact_params.get('dimension', 0.008)}
 MeshSize,{impact_params.get('mesh_size', 0.001)}
 DimensionDamper,{dim_damper_str}
-Density,{impact_params.get('density', 7800)}
-YoungsModulus,{impact_params.get('youngs_modulus', 201e9)}
-PoissonRatio,{impact_params.get('poisson_ratio', 0.3)}
+DensityImpactor,{impact_params.get('density', 7.85e-9)}
+YoungsModulusImpactor,{impact_params.get('youngs_modulus', 2.01e5)}
+PoissonRatioImpactor,{impact_params.get('poisson_ratio', 0.3)}
 tFinal,{impact_params.get('tFinal', 0.001)}
 dt,{impact_params.get('dt', 1e-6)}
 OffsetDistance,{impact_params.get('offset_distance', 0.00001)}
```

근거:
- `DropWeightImpactWorkflow.py:533-535` 가 이미 정확한 키 이름 사용 — 동일 형식 적용
- default 값도 ton-mm-s 단위계로 변경 (자세한 이유는 P1)

---

### 🟡 P1 — Wall MAT 카드 키 누락

**파일**: `Runner/CumulativeScenarioRunner.py`

**위치**: 동일 IMPACT 분기, 1232 줄 직후 (`OffsetDistance,...` 다음, `**EndDropWeightImpactTest` 전)

**진단**: `CumulativeScenarioRunner` 가 만드는 step_config 에는 wall (drop surface) 관련 라인이
**전혀 없음**. KooMeshModifier 의 `aDensityWall / aYoungsModulusWall / aPoissonRatioWall` 키는
값을 못 받아 hardcoded SI default 사용 → deck 의 `*MAT_RIGID_TITLE WallMaterial` 가
`1.000e+03 1.000e+10` (SI 형식) 으로 출력됨.

> 참고: `WallMaterial` 가 `*MAT_RIGID` 라 dynamic 영향은 적지만 contact penalty 결정에는 들어감.
> 일관성을 위해 같이 ton-mm-s 형식으로.

**패치**:

```diff
--- a/Runner/CumulativeScenarioRunner.py
+++ b/Runner/CumulativeScenarioRunner.py
@@ -1230,6 +1230,9 @@ PoissonRatioImpactor,{impact_params.get('poisson_ratio', 0.3)}
 tFinal,{impact_params.get('tFinal', 0.001)}
 dt,{impact_params.get('dt', 1e-6)}
 OffsetDistance,{impact_params.get('offset_distance', 0.00001)}
+DensityWall,{wall_params.get('density', 1.0e-9)}
+YoungsModulusWall,{wall_params.get('youngs_modulus', 1.0e4)}
+PoissonRatioWall,{wall_params.get('poisson_ratio', 0.3)}
 **EndDropWeightImpactTest
 *End
 """
```

그리고 `wall_params` 를 `simulation_params` 에서 받는 부분 함수 상단에 추가:

```python
wall_params = sim_params.get("wall", {})  # 없으면 빈 dict (default 적용)
```

근거: `DropWeightImpactWorkflow.py:544-552` 가 이미 동일 패턴 사용.

---

### 🟡 P1 — Runner default 값이 SI 단위계 (영향 파일 3개)

**진단**: 사용자가 `scenario.json` 에 density/youngs_modulus 를 명시하지 않으면 Runner 가 `.get(key, DEFAULT)` 의 fallback 사용.
세 곳 모두 default 가 SI (`7850`, `200e9`) 인데, 같은 함수의 다른 라인 `g = 9810  # mm/s²` 는 ton-mm-s 가정 — **함수 안 단위계 불일치**.

#### P1a — `Runner/CumulativeScenarioRunner.py:1227-1229`

P0 패치에 포함됨 (default 값 변경: `7800` → `7.85e-9`, `201e9` → `2.01e5`).

#### P1b — `Runner/DropWeightImpactWorkflow.py:482-547`

```diff
--- a/Runner/DropWeightImpactWorkflow.py
+++ b/Runner/DropWeightImpactWorkflow.py
@@ -479,10 +479,13 @@ def build_drop_weight_impact_config(...):
     imp_type = impactor.get("type", "Sphere")
     imp_radius = impactor.get("radius", 5.0)
     imp_height = impactor.get("height", 100)
-    imp_density = impactor.get("density", 7850)
-    imp_E = impactor.get("youngs_modulus", 200e9)
+    # Solver unit system: [tonne, mm, s, MPa] — `g = 9810 mm/s²` 도 그 단위계.
+    # 강철 ref: ρ = 7.85e-9 tonne/mm³, E = 2.0e5 MPa.
+    imp_density = impactor.get("density", 7.85e-9)
+    imp_E = impactor.get("youngs_modulus", 2.0e5)
     imp_nu = impactor.get("poisson_ratio", 0.3)
@@ -545,9 +548,9 @@ def build_drop_weight_impact_config(...):
     wall = sim_params.get("wall", {})
-    wall_E = wall.get("youngs_modulus", 200e9)
+    wall_E = wall.get("youngs_modulus", 1.0e4)            # MPa
     wall_nu = wall.get("poisson_ratio", 0.3)
-    wall_density = wall.get("density", 7850)
+    wall_density = wall.get("density", 1.0e-9)            # tonne/mm³
```

#### P1c — `Runner/StepConfigBuilder.py:42-43`

```diff
--- a/Runner/StepConfigBuilder.py
+++ b/Runner/StepConfigBuilder.py
@@ -39,8 +39,10 @@ def build_drop_attitude_config(sim_params, ...):
     tFinal = sim_params.get("tFinal", 0.005)
     dt = sim_params.get("dt", 0.000001)
-    density = sim_params.get("density", 7850)
-    youngs_modulus = sim_params.get("youngs_modulus", 200000000000)
+    # Solver unit system: [tonne, mm, s, MPa] — height(mm), tFinal(s).
+    # 강철 ref: ρ = 7.85e-9, E = 2.0e5.
+    density = sim_params.get("density", 7.85e-9)
+    youngs_modulus = sim_params.get("youngs_modulus", 2.0e5)
     poisson_ratio = sim_params.get("poisson_ratio", 0.3)
     sim_height = sim_params.get("height", 1500)
```

---

### 🟢 P2 — KooMeshModifier 의 silent fallback 개선

**파일**: KooMeshModifier 본체 (호스트 소스 위치는 사용자가 알 가능성)

**진단**: 인식 안 되는 키 (`Density,...` 같은 옛 형식) 를 만나면 silent 하게 hardcoded default 사용.
사용자는 본인 입력이 반영됐는지 알 길 없음 — 본 버그가 수개월간 발견 안 된 원인.

**제안**:
1. 인식 안 된 key 를 만나면 stderr 에 warning:
   `[KooMeshModifier] WARN: unknown step_config key 'Density' (did you mean 'DensityImpactor'?)`
2. 또는: 인식된 dim/material 키가 0 개면 raise (silent default 전체 금지)
3. binary 안 `a_hardcoded_defaults` 의 default 값 들도 ton-mm-s 단위계로 변경 (현재 SI 추정)
   - 강철: ρ = 7.85e-9 tonne/mm³, E = 2.0e5 MPa, ν = 0.3
   - wall: ρ = 1.0e-9 tonne/mm³, E = 1.0e4 MPa

---

### 🟢 P2 — `scenario.json` 의 `unit_system` 필드 신설

**파일**: `Runner/*` (입력 파싱 측), 그리고 사용자 문서

**진단**: `scenario.json` 의 `simulation_params.impact` 가 어느 단위계 (SI / ton-mm-s / ton-mm-ms) 인지
명시 안 됨. 사용자가 어느 단위로 입력해야 하는지 모호 → 본 버그의 root cause.

Test_Impact_A 의 실제 scenario.json (수정 전):
```json
"impact": {
  "dimension": 0.008,        // m → SI (혹은 그냥 라벨 없는 숫자)
  "mesh_size": 0.001,        // m → SI
  "height": 0.5,             // m → SI
  "density": 7800,           // kg/m³ → SI
  "youngs_modulus": 201000000000,  // Pa → SI
  ...
}
```

사용자는 SI 입력 의도였는데 deck 는 ton-mm-s. 변환이 길이만 일어나고 ρ/E 는 그대로 → 단위 혼용.

**제안**:

```json
{
  "simulation_params": {
    "unit_system": "ton-mm-s",   // ← 신규: SI | ton-mm-s | ton-mm-ms
    "impact": {
      "density": 7.85e-9,
      "youngs_modulus": 2.01e5,
      ...
    },
    "wall": {                    // ← 신규: 명시적 wall 입력
      "density": 1.0e-9,
      "youngs_modulus": 1.0e4,
      "poisson_ratio": 0.3
    }
  }
}
```

Runner 가:
- `unit_system` 누락 시 raise (silent fallback 금지)
- 명시된 `unit_system` 과 deck 단위계가 다르면 자동 변환 후 step_config 작성

---

### 🟢 P3 — 길이는 자동 변환되지만 ρ/E 는 변환 안 됨 (inconsistency)

**진단**: 현재 KooMeshModifier 동작:
- `Dimension,0.008` (m 입력) → mesh 노드 좌표 8 mm (자동 변환 ✓)
- `Density,7800` (kg/m³) → deck *MAT 카드 `7800` 그대로 (ton/mm³ 로 해석되어 비현실) ❌

**제안**:
- P2 의 `unit_system` 필드 도입 후
- 모든 dimensional quantity (길이, 시간, 질량 밀도, 응력, 가속도) 에 일관 변환

또는 (간단히):
- 모든 입력을 ton-mm-s (= deck 단위계) 로 받기. SI 입력 거부 또는 명시적 변환 후 호출.

---

## 5. 검증 절차 (P0 적용 후)

1. **호스트 .py 수정** (P0a 패치만)
2. **SIF 재빌드**: `KooSlurmInstallAutomationRefactory/apptainer/build.sh` 또는 동등 흐름
3. **노드 배포**: `/opt/apptainers/SmartTwinPreprocessor.sif` 갱신
4. **Test_Impact_A 시범**:
   ```bash
   cd /data/koopark/Test_Impact_A
   # scenario.json 의 simulation_params.impact 에 ton-mm-s 값 (또는 unit_system 필드)
   # runner_config 재생성
   rm runner_config.json
   /data/SmartTwinPreprocessor/bin/KooChainRun prepare scenario.json
   # 1 DOE 만 재실행
   /data/SmartTwinPreprocessor/bin/KooChainRun rerun --does 1 --force --cleanup-stale
   ```
5. **검증**: 새 Run 디렉토리의 `DropWeightImpactTestSet.k` 에서
   ```
   *MAT_ELASTIC_TITLE
   ImpactorMaterial
           29 7.850e-09 2.010e+05 3.000e-01     ← ton-mm-s 형식 (이게 나와야 fix 성공)
   ```
   `WallMaterial` 도 동일 (`1.000e-09 1.000e+04`).

6. **물리적 sanity**: d3plot 분석 시
   - WORST PEAK G: 정상 폰 drop 범위 (예 500–3000 G)
   - WORST σ: PCB 부품 허용 범위 (예 50–250 MPa)

---

## 6. 부수 발견 + 작업 흔적 (참고용)

### 6.1 본 진단 과정에서 변경된 사용자 데이터

| 위치 | 변경 내용 | 백업 |
|---|---|---|
| `/data/koopark/Test_Impact_A/output/Run_*/DropWeightImpactTestSet.k` (76 파일) | impactor/wall MAT SI → ton-mm-s sed | `/data/koopark/Test_Impact_A/.deck_unit_fix_backup/` |
| `/data/Tests/Test_*/**/*.k` + `/data/koopark/Test_*/**/*.k` (4025 파일) | 동일 sed 일괄 | `/data/.deck_unit_fix_backup_2026-05-31/` (17 GB) |
| `/data/koopark/Test_Impact_A/scenario.json` | `simulation_params.impact.density/E` SI → ton-mm-s | `*.unit_fix_bak` |
| `/data/koopark/Test_Impact_A/runner_config.json` | scenario.json 재생성 | `*.unit_fix_bak` |
| `/home/koopark/serviceApptainers/appt313/opt/pyKooCAE/Runner/DropWeightImpactWorkflow.py` | P1b default 수정 | `*.unit_fix_bak` |
| `/home/koopark/serviceApptainers/appt313/opt/pyKooCAE/Runner/StepConfigBuilder.py` | P1c default 수정 | `*.unit_fix_bak` |

위 모든 변경은 SIF 안 KooMeshModifier 가 호스트 .py 와 deck 의 단위를 무시하기 때문에 효과 없음.
**P0 fix + SIF 재빌드 후 원상 복구 가능**:

```bash
# 원본 deck 복원
rsync -a /data/.deck_unit_fix_backup_2026-05-31/Tests/ /data/Tests/
rsync -a /data/.deck_unit_fix_backup_2026-05-31/koopark/ /data/koopark/
# 호스트 .py 복원
mv /home/koopark/serviceApptainers/appt313/opt/pyKooCAE/Runner/DropWeightImpactWorkflow.py{.unit_fix_bak,}
mv /home/koopark/serviceApptainers/appt313/opt/pyKooCAE/Runner/StepConfigBuilder.py{.unit_fix_bak,}
```

### 6.2 Test_Impact_A 의 추가 Run 디렉토리

DOE001 시범 재실행 도중 생성된 부수 디렉토리:

- `Run_pre_unit_fix_DOE001_Run_20260528_173737_ab610c/` — 원본 옛 SI 시뮬 결과 (보존)
- `Run_pre_scenario_fix_DOE001_*` — job 228 (scenario.json fix 전)
- `Run_pre_rc_fix_*` — job 233 (runner_config 추가 fix 전)
- `Run_cancelled_*` — job 234 cancel 흔적
- `Run_20260601_090728_3e71ee/` — job 239 (최종 시도, deck 여전히 SI)

P0 fix + SIF 재빌드 후 25 DOE 모두 재실행하면 이 부수 디렉토리들 정리 가능.

### 6.3 다른 testset 도 동일 영향

cumulative mode 사용하는 모든 testset 동일 영향:

- 부분 충격 (Impactor/Wall): `Test_Impact_A`, `Test_DWI`, `Test_DropWeight_Validation`,
  `Test_010_Sequential_Quick`, `Test_Postprocess_v14`, `Test_Postprocess_v15_SeparateJob`
- 전각도 낙하 (RigidWall): `Test_001_Full26_1Step`, `Test_005/006/007_Fibonacci_*`,
  `Test_FullAngle_RW`

P0 fix 후 모두 자동 정정.

---

## 7. 제안 commit 메시지 초안

```
fix(Runner): step_config 키 이름을 KooMeshModifier 인식 형식으로 일치

CumulativeScenarioRunner._build_step_config() 의 IMPACT 분기가
KooMeshModifier 가 인식하지 못하는 키 이름을 사용하고 있었음.

  변경 전: Density,...  YoungsModulus,...  PoissonRatio,...
  변경 후: DensityImpactor,...  YoungsModulusImpactor,...  PoissonRatioImpactor,...

KooMeshModifier 는 매칭 실패 시 hardcoded SI default
(ρ=7800 kg/m³, E=2.07e11 Pa) 를 silent 하게 사용함. 이게 ton-mm-s
단위계 deck 의 *MAT_ELASTIC_TITLE ImpactorMaterial 카드에 그대로
들어가 단위 혼용 deck 이 생성되고, LSDYNA 가 impactor mass 를 약
10^12 배 비현실적으로 큰 값으로 해석해 결과 d3plot 의 응력/가속도가
비물리적 spike 값으로 출력되어 왔음.

DropWeightImpactWorkflow.py:533-535 는 이미 정확한 키
(DensityImpactor / YoungsModulusImpactor / PoissonRatioImpactor)
사용 중이므로 동일 형식으로 통일.

추가로 default 값을 ton-mm-s 단위계로 변경:
  - density:        7800 (kg/m³, SI) → 7.85e-9 (tonne/mm³)
  - youngs_modulus: 201e9 (Pa, SI)   → 2.01e5 (MPa)
이는 같은 함수의 `g = 9810  # mm/s²` 라인 (ton-mm-s 가정) 과 일관.

영향: cumulative mode 의 모든 DOE — Test_Impact_A,
Test_DropWeight_Validation, Test_DWI, Test_010_*, Test_Postprocess_*,
Test_FullAngle_RW, Fibonacci 전각도 낙하 시리즈 (Test_001/005/006/007).

검증: docs/pyKooCAE-unit-system-fix.md §5 참조.
```

---

## 8. 변경 우선순위 표

| ID | 위치 | 영향 | 작업 비용 |
|---|---|---|---|
| P0 | `CumulativeScenarioRunner.py:1227-1229` | cumulative DOE 단위 혼용 100 % 해결 | 1 줄 fix + SIF 재빌드 |
| P1a | (P0 에 포함) | (P0 와 함께) | — |
| P1b | `DropWeightImpactWorkflow.py:482-547` | non-cumulative 단일 DOE | 4 줄 fix |
| P1c | `StepConfigBuilder.py:42-43` | DROP_ATTITUDE (전각도 낙하 별도 흐름) | 2 줄 fix |
| P2 | KooMeshModifier silent fallback 경고 | 향후 유사 버그 조기 발견 | 중간 |
| P2 | `unit_system` 필드 도입 | 단위 혼용 원천 차단 | 큼 (스키마 변경) |
| P3 | 일관 단위 변환 | 사용자 입력 자유도 ↑ | 큼 |

**최소 출시 게이트**: P0 + SIF 재빌드 1회. 그것만으로 본 cumulative DOE 단위 혼용 문제 해결.

---

## 9. 본 문서 작성 환경

- 진단 일자: 2026-05-31 ~ 2026-06-01
- 진단 도구: bash, ssh, apptainer exec, strings, md5sum, grep
- 진단 데이터셋: `/data/koopark/Test_Impact_A/`, `/data/Tests/Test_006_Fibonacci_6deg/`
- 호스트 pyKooCAE git HEAD: `e5050ac` (2026-04-12 commit `0df8f3a` 이후의 작업)
- 호스트 pyKooCAE working tree dirty 파일 (본 진단과 무관):
  Vibration/CAEManager 측 사용자의 다른 작업으로 보임 — 그대로 둠.
