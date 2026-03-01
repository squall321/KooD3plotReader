# 전각도 낙하 시뮬레이션 데이터 구조

## 1. 데이터 파이프라인 개요

```
scenario.json                 시나리오 정의 (DOE 전략, 각도 소스, 물리 파라미터)
      │
      ▼
runner_config.json            실행 설정 (각도 목록, 환경 경로, 시뮬레이션 파라미터)
      │
      ▼
output/
├── simulation_index.json     실행 인덱스 (Run ID ↔ 폴더 매핑)
├── checkpoint.json           실행 진행 상태
└── Run_YYYYMMDD_HHMMSS_HASH/
    ├── DropSet.json          ★ 각 Run의 실제 낙하 조건 (각도, 높이, 파트 정보)
    ├── d3plot, d3plot01~NN   LS-DYNA 결과 데이터
    └── ...
      │
      ▼  (KooD3plotReader unified_analyzer --recursive)
analysis_results/
└── Run_YYYYMMDD_HHMMSS_HASH/    (output의 Run 폴더명과 1:1 대응)
    ├── analysis_result.json      종합 분석 결과
    ├── .analysis_info            분석 메타데이터
    ├── stress/                   von Mises 응력 CSV
    ├── strain/                   유효 소성 변형률 CSV
    ├── motion/                   변위/속도/가속도 CSV
    └── surface/                  (예약)
```

---

## 2. 입력 파일 구조

### 2.1 scenario.json

시뮬레이션 시나리오 최상위 정의. DOE 각도 생성 전략을 결정한다.

```json
{
  "project_name": "Test_001_Full26_1Step",
  "simulation_params": {
    "tFinal": 0.001,        // 시뮬레이션 종료 시간 (초)
    "dt": 0.000001,         // 시간 간격
    "height": 1500,         // 낙하 높이 (mm)
    "density": 7850,        // 재료 밀도 (kg/m³)
    "youngs_modulus": 2e11, // 영률 (Pa)
    "poisson_ratio": 0.3    // 포아송비
  },
  "scenarios": [{
    "scenario_name": "...",
    "template": "MinimumModel.k",    // LS-DYNA 키워드 파일
    "angle_source": {
      "source_type": "cuboid_geometry | fibonacci_lattice | case_txt_file",
      // source_type별 추가 설정 (아래 DOE 전략 참고)
    },
    "cumulative": {
      "num_steps": 1,                // 낙하 단계 수
      "mode_sequence": ["DROP"]      // 각 단계 모드
    }
  }]
}
```

### 2.2 runner_config.json

scenario.json을 기반으로 생성된 실행 설정. 모든 DOE 각도가 전개되어 있다.

```json
{
  "project": {
    "name": "Test_001_Full26_1Step",
    "model_file": "/data/Tests/.../MinimumModel.k",
    "output_dir": "/data/Tests/.../output",
    "index_file": "/data/Tests/.../output/simulation_index.json"
  },
  "scenario": {
    "id": "Full_26_Directions_Single_Drop_S001",
    "doe_count": 26,
    "doe_angles": {
      "1": {
        "1": {                         // step 번호
          "angle_name": "F1_Back",
          "roll": 0.0,
          "pitch": 0.0,
          "yaw": 0.0
        }
      },
      "2": { "1": { "angle_name": "F2_Front", "roll": 180.0, ... } },
      // ... doe_count개
    },
    "steps": [
      {
        "step_number": 1,
        "mode": "DROP",
        "angle": { "name": "...", "roll": ..., "pitch": ..., "yaw": ... },
        "doe_index": 18              // doe_angles 내 인덱스
      }
    ]
  },
  "simulation_params": { ... },      // scenario.json과 동일
  "execution": {
    "timeout_per_step_seconds": 7200,
    "retry_on_failure": true,
    "max_retries": 2
  }
}
```

### 2.3 simulation_index.json (output/ 내)

실행 중/후 생성되는 인덱스. Run ID와 폴더명을 매핑한다.

```json
{
  "project": "Test_001_Full26_1Step",
  "scenarios": [{
    "id": "Full_26_Directions_Single_Drop_S001",
    "doe_count": 26,
    "total_runs": 26,
    "status": "completed",
    "runs": {
      "Test_001_..._DOE002_S001_DROP_...": {
        "run_id": "20260207_211809_6cf7fb",
        "status": "completed",
        "folder": "Run_20260207_211809_6cf7fb",
        "mode": "DROP",
        "condition": "C1_Back_Right_Top",     // ⚠️ 현재 버그: 모든 Run에 동일값
        "completed_at": "2026-02-07T21:24:46"
      }
    }
  }]
}
```

> **주의**: `condition` 필드가 현재 모든 Run에 동일한 값으로 기록되는 버그가 있음.
> 실제 각도 정보는 **각 Run 폴더의 DropSet.json**에서 읽어야 한다.

### 2.4 DropSet.json (각 Run 폴더 내)

**각 Run의 실제 낙하 조건을 담고 있는 핵심 파일.**
Run 폴더 ↔ 각도 매핑의 유일한 신뢰 소스.

```json
{
  "run_id": "20260207_211809_06e06e",
  "stage": "Step1",
  "model_name": "Test_001_Full26_1Step",
  "scenario_mode": "DropAttitude",
  "initial_conditions": {
    "orientation_euler_deg": {
      "pitch": 90.0,            // 오일러각 (도)
      "roll": 0.0,
      "yaw": 0.0
    },
    "drop_height": 1500.0,      // mm
    "velocity": [0, 0, 0],
    "angular_velocity": [0, 0, 0]
  },
  "model": {
    "parts": {                   // Part ID → 이름 매핑
      "1": "Front\\Metal",
      "2": "Front\\Wall",
      // ...
    },
    "contact_graph": { ... }     // 접촉 정의
  }
}
```

---

## 3. 분석 결과 구조

### 3.1 analysis_result.json

각 Run별 종합 분석 결과. stress, strain, motion 데이터의 시계열 요약.

```json
{
  "metadata": {
    "d3plot_path": "/data/.../output/Run_.../d3plot",
    "analysis_date": "2026-02-08T05:55:00Z",
    "kood3plot_version": "1.0.0",
    "num_states": 992,           // 시간 스텝 수
    "start_time": 0.0,           // 초
    "end_time": 0.001,
    "analyzed_parts": [1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 18, 19]
  },
  "stress_history": [
    {
      "part_id": 1,
      "part_name": "Part_1",
      "quantity": "von_mises",
      "unit": "MPa",
      "num_points": 992,
      "global_max": 461.20,      // 전체 시간 중 최대값
      "global_min": 0.0,
      "time_of_max": 0.00078,    // 최대값 발생 시간
      "data": [
        {
          "time": 0.0,
          "max": 0.0,             // 해당 시간의 파트 내 최대
          "min": 0.0,             // 해당 시간의 파트 내 최소
          "avg": 0.0,             // 해당 시간의 파트 내 평균
          "max_element_id": 1,    // 최대값 요소 ID
          "min_element_id": 0
        },
        // ... 992개
      ]
    }
    // ... 분석 대상 파트 수만큼
  ],
  "strain_history": [ /* 동일 구조 */ ],
  "acceleration_history": [],
  "surface_analysis": {}
}
```

### 3.2 CSV 파일 포맷

#### stress/part_N_von_mises.csv
```
Time,Max_von_mises,Min_von_mises,Avg_von_mises,Max_Element_ID,Min_Element_ID
0.000000,0.000000,0.000000,0.000000,1,0
0.000001,0.038530,0.000000,0.000578,32694,0
...
```

#### strain/part_N_eff_plastic_strain.csv
```
Time,Max_eff_plastic_strain,Min_eff_plastic_strain,Avg_eff_plastic_strain,Max_Element_ID,Min_Element_ID
0.000000,0.000000,0.000000,0.000000,33854,0
0.000001,0.000000,-0.000001,-0.000000,33855,0
...
```

#### motion/part_N_motion.csv
```
Time,Avg_Disp_X,Avg_Disp_Y,Avg_Disp_Z,Avg_Disp_Mag,Avg_Vel_X,Avg_Vel_Y,Avg_Vel_Z,Avg_Vel_Mag,Avg_Acc_X,Avg_Acc_Y,Avg_Acc_Z,Avg_Acc_Mag,Max_Disp_Mag,Max_Disp_Node_ID
0.000000,22.000000,41.000000,-1.350000,46.549141,0.000000,...
```

| 컬럼 | 단위 | 설명 |
|------|------|------|
| Time | 초 | 시뮬레이션 시간 |
| Avg_Disp_X/Y/Z | mm | 파트 평균 변위 |
| Avg_Disp_Mag | mm | 변위 크기 |
| Avg_Vel_X/Y/Z | mm/s | 파트 평균 속도 |
| Avg_Vel_Mag | mm/s | 속도 크기 |
| Avg_Acc_X/Y/Z | mm/s² | 파트 평균 가속도 |
| Avg_Acc_Mag | mm/s² | 가속도 크기 |
| Max_Disp_Mag | mm | 파트 내 최대 변위 |
| Max_Disp_Node_ID | - | 최대 변위 노드 ID |

### 3.3 .analysis_info

```
d3plot_path: /data/Tests/.../output/Run_.../d3plot
config_file: /data/Tests/.../common_analysis.yaml
analyzed_at: Sun Feb  8 05:55:01 2026
```

---

## 4. Run 폴더 ↔ 각도 매핑 방법

Run 폴더명(`Run_YYYYMMDD_HHMMSS_HASH`)은 타임스탬프 기반이라 각도 정보를 직접 포함하지 않는다.

### 매핑 절차

```
1. output/Run_XXX/DropSet.json 읽기
   → initial_conditions.orientation_euler_deg에서 roll, pitch, yaw 추출

2. runner_config.json의 doe_angles에서 동일한 (roll, pitch, yaw) 검색
   → angle_name (예: "F1_Back", "E03_Back_Top") 획득

3. analysis_results/Run_XXX/ 와 output/Run_XXX/ 는 폴더명 동일
   → 분석 결과를 각도에 연결
```

### Test_001 전체 매핑 (26개)

| Run 폴더 | Roll | Pitch | Yaw | 각도 이름 | 분류 |
|----------|------|-------|-----|-----------|------|
| Run_20260207_211809_27e4e2 | 0.0 | 0.0 | 0.0 | F1_Back | Face |
| Run_20260207_211809_6cf7fb | 180.0 | 0.0 | 0.0 | F2_Front | Face |
| Run_20260207_211809_8ab7ef | 0.0 | -90.0 | 0.0 | F3_Right | Face |
| Run_20260207_211809_06e06e | 0.0 | 90.0 | 0.0 | F4_Left | Face |
| Run_20260207_212423_0d4013 | 90.0 | 0.0 | 0.0 | F5_Top | Face |
| Run_20260207_212430_5c2c4c | -90.0 | 0.0 | 0.0 | F6_Bottom | Face |
| Run_20260207_212447_f1e2c8 | 0.0 | -45.0 | 0.0 | E01_Back_Right | Edge |
| Run_20260207_212447_835331 | 0.0 | 45.0 | 0.0 | E02_Back_Left | Edge |
| Run_20260207_213047_1fcce3 | 45.0 | 0.0 | 0.0 | E03_Back_Top | Edge |
| Run_20260207_213047_908ec1 | -45.0 | 0.0 | 0.0 | E04_Back_Bottom | Edge |
| Run_20260207_213101_97370a | 180.0 | 45.0 | 0.0 | E05_Front_Right | Edge |
| Run_20260207_213106_e0a55f | 180.0 | -45.0 | 0.0 | E06_Front_Left | Edge |
| Run_20260207_213653_6305d9 | 135.0 | 0.0 | 0.0 | E07_Front_Top | Edge |
| Run_20260207_213659_96dcab | -135.0 | 0.0 | 0.0 | E08_Front_Bottom | Edge |
| Run_20260207_213703_ee6f6d | 90.0 | -45.0 | 0.0 | E09_Right_Top | Edge |
| Run_20260207_213719_8eccd1 | -90.0 | -45.0 | 0.0 | E10_Right_Bottom | Edge |
| Run_20260207_214302_3dbc00 | 90.0 | 45.0 | 0.0 | E11_Left_Top | Edge |
| Run_20260207_214307_9016de | -90.0 | 45.0 | 0.0 | E12_Left_Bottom | Edge |
| Run_20260207_214315_de6bf0 | 45.0 | -45.0 | 0.0 | C1_Back_Right_Top | Corner |
| Run_20260207_214324_78508a | -45.0 | -45.0 | 0.0 | C2_Back_Right_Bottom | Corner |
| Run_20260207_215034_106636 | 45.0 | 45.0 | 0.0 | C3_Back_Left_Top | Corner |
| Run_20260207_215039_309a70 | -45.0 | 45.0 | 0.0 | C4_Back_Left_Bottom | Corner |
| Run_20260207_215041_053ba9 | 135.0 | 45.0 | 0.0 | C5_Front_Right_Top | Corner |
| Run_20260207_215049_50109b | -135.0 | 45.0 | 0.0 | C6_Front_Right_Bottom | Corner |
| Run_20260207_215828_acd6fd | 135.0 | -45.0 | 0.0 | C7_Front_Left_Top | Corner |
| Run_20260207_215836_049513 | -135.0 | -45.0 | 0.0 | C8_Front_Left_Bottom | Corner |

---

## 5. DOE 전략 비교

| 항목 | Test_001 | Test_005 | Test_006 |
|------|----------|----------|----------|
| 전략 | Cuboid Geometry | Fibonacci Lattice | Fibonacci Lattice |
| 각도 수 | 26 | 100 | 1,146 |
| 소스 | cuboid_geometry (F6+E12+C8) | fibonacci_lattice (N=100) | case_txt_file (.txt) |
| 각도 이름 | F1_Back, E01_..., C1_... | P0001~P0100 | P0001~P1146 |
| 낙하 단계 | 1 | 1 | 1 |
| 각도 포맷 | roll, pitch, yaw (deg) | roll, pitch, yaw (deg) | roll, pitch, yaw (deg) |
| d3plot 수 | 26 | 100 | 194 (일부 실행) |
| 특징 | 직육면체의 면/모서리/꼭짓점 | 구면 균일 분포 | 6도 간격 고밀도 |

### Cuboid Geometry (26 방향)
- 6 Faces: 직육면체의 6개 면 중심 방향
- 12 Edges: 인접 면 사이의 모서리 방향 (45도)
- 8 Corners: 3면이 만나는 꼭짓점 방향

### Fibonacci Lattice (구면 균일 분포)
- 피보나치 수열 기반 구면 점 분포
- N이 클수록 구면 커버리지 증가
- 모든 방향이 대략 동일한 입체각을 커버

---

## 6. 파트 목록

MinimumModel.k 기준 (모든 Test에서 동일 모델 사용).

| Part ID | 이름 | 분류 | 분석 대상 |
|---------|------|------|-----------|
| 1 | Front\Metal | Front | Stress |
| 2 | Front\Wall | Front | Stress |
| 3 | PCB\PCB | PCB | - |
| 4 | PKG\PKG 1 | PKG | Stress, Strain, Motion |
| 5 | PKG\PKG 3 | PKG | Stress, Strain, Motion |
| 6 | PKG\PKG 4 | PKG | Stress, Strain, Motion |
| 7 | PKG\PKG 5 | PKG | Stress, Strain, Motion |
| 8 | PKG\PKG 6 | PKG | Stress, Strain, Motion |
| 9 | PKG\PKG 7 | PKG | Stress, Strain, Motion |
| 10 | PKG\PKG 8 | PKG | Stress, Strain, Motion |
| 11 | PKG\PKG 9 | PKG | Stress, Strain, Motion |
| 12 | PKG\PKG 10 | PKG | Stress, Strain, Motion |
| 13 | PKG\PKG 11 | PKG | Stress, Strain, Motion |
| 14 | PKG\PKG 2 | PKG | Stress, Strain, Motion |
| 15 | SUBPCB\SUBPBA | SUBPCB | - |
| 16 | PKG\SUBPKG | PKG | Stress, Strain, Motion |
| 17 | PKG\SUBPKG2 | PKG | Stress, Strain, Motion |
| 18 | PKG\Motor | PKG | Stress, Strain, Motion |
| 19 | PKG\SUBPKG3 | PKG | Stress, Strain, Motion |
| 20 | Bond\Bond | Bond | - |
| 21 | Display\Display | Display | - |
| 22 | Geom\솔리드 | Geom | - |
| 23 | (이름 없음) | - | - |

**분석 대상 패턴**:
- `PKG*` → Part 4~14, 16~19 (15개): Stress + Strain + Motion
- `Front*` → Part 1, 2 (2개): Stress only

---

## 7. Test별 현황 요약

| Test | 시나리오 | DOE 수 | d3plot | analysis_results | 상태 |
|------|----------|--------|--------|------------------|------|
| Test_001_Full26_1Step | Cuboid 26방향 1회 낙하 | 26 | 26 | 26 | 분석 완료 |
| Test_002_Full26_3Step | Cuboid 26방향 3회 연속 낙하 | 26 | 0 | - | 미실행 |
| Test_003_6Faces_Cyclic | 6면 순환 낙하 | 6 | 0 | - | 미실행 |
| Test_004_Pitching_Sweep | 피칭 스위프 | 다수 | 0 | - | 미실행 |
| Test_005_Fibonacci_100 | Fibonacci 100방향 | 100 | 100 | - | 실행 완료, 분석 대기 |
| Test_006_Fibonacci_6deg | Fibonacci 6도 간격 | 1,146 | 194 | - | 일부 실행 |
| Test_007_Fibonacci_2deg | Fibonacci 2도 간격 | 다수 | 0 | - | 미실행 |

---

## 8. 디렉토리 구조 전체

```
/data/Tests/
├── Test_001_Full26_1Step/
│   ├── scenario.json              시나리오 정의
│   ├── runner_config.json         실행 설정 (DOE 각도 전개)
│   ├── MinimumModel.k             LS-DYNA 모델 파일
│   ├── common_analysis.yaml       분석 설정 (unified_analyzer용)
│   ├── run_analysis.sh            분석 실행 스크립트
│   ├── output/
│   │   ├── simulation_index.json  실행 인덱스
│   │   ├── checkpoint.json        체크포인트
│   │   └── Run_*/                 시뮬레이션 결과 (26개)
│   │       ├── DropSet.json       ★ 낙하 조건
│   │       ├── d3plot             결과 데이터
│   │       └── ...
│   └── analysis_results/          분석 결과 (26개)
│       └── Run_*/
│           ├── analysis_result.json
│           ├── stress/*.csv
│           ├── strain/*.csv
│           └── motion/*.csv
├── Test_002_Full26_3Step/         (동일 구조, output 미생성)
├── Test_003_6Faces_Cyclic/
├── Test_004_Pitching_Sweep/
├── Test_005_Fibonacci_100/
├── Test_006_Fibonacci_6deg/
└── Test_007_Fibonacci_2deg/
```

---

## 9. 핵심 정보 접근 경로 요약

| 정보 | 파일 경로 | 키/필드 |
|------|-----------|---------|
| DOE 각도 목록 | `runner_config.json` | `.scenario.doe_angles` |
| Run별 실제 각도 | `output/Run_*/DropSet.json` | `.initial_conditions.orientation_euler_deg` |
| Run 폴더 목록 | `output/simulation_index.json` | `.scenarios[0].runs[*].folder` |
| Run 상태 | `output/simulation_index.json` | `.scenarios[0].runs[*].status` |
| 파트 이름 | `output/Run_*/DropSet.json` | `.model.parts` |
| 시뮬레이션 파라미터 | `runner_config.json` | `.simulation_params` |
| 응력 최대값 | `analysis_results/Run_*/analysis_result.json` | `.stress_history[*].global_max` |
| 응력 시계열 | `analysis_results/Run_*/stress/part_N_von_mises.csv` | CSV |
| 변형률 시계열 | `analysis_results/Run_*/strain/part_N_eff_plastic_strain.csv` | CSV |
| 모션 시계열 | `analysis_results/Run_*/motion/part_N_motion.csv` | CSV |
| 분석 설정 | `common_analysis.yaml` | YAML |
