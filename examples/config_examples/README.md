# KooD3plot YAML 설정 예제 모음

이 디렉토리에는 KooD3plot 통합 분석 시스템을 위한 YAML 설정 예제 파일들이 포함되어 있습니다.

## 예제 파일 목록

### 분석 전용 (Analysis Only)

| 파일 | 설명 | 분석 유형 |
|------|------|----------|
| `01_stress_only.yaml` | Von Mises 응력 분석 | `von_mises` |
| `02_strain_only.yaml` | 유효 소성 변형률 분석 | `eff_plastic_strain` |
| `03_motion_analysis.yaml` | 운동 분석 (변위/속도/가속도) | `part_motion` |
| `04_surface_stress.yaml` | 방향 기반 표면 응력 | `surface_stress` |
| `05_surface_strain.yaml` | 방향 기반 표면 변형률 | `surface_strain` |
| `06_comprehensive_analysis.yaml` | 복합 분석 (여러 quantity) | `comprehensive` |

### 렌더링 전용 (Rendering Only)

| 파일 | 설명 | 렌더링 유형 |
|------|------|-----------|
| `07_section_views.yaml` | 다양한 단면뷰 | 위치별 단면 |
| `08_multi_fringe.yaml` | 다중 Fringe 타입 | von_mises, strain, pressure 등 |

### 통합 워크플로우 (Full Workflow)

| 파일 | 설명 | 시나리오 |
|------|------|---------|
| `09_full_workflow.yaml` | 분석 + 렌더링 통합 | 자동차 전면 충돌 |
| `10_drop_test.yaml` | 낙하 시험 분석 | 전자제품 낙하 |

---

## 사용법

### 기본 실행
```bash
# 설정 파일로 분석 실행
./unified_analyzer --config examples/config_examples/01_stress_only.yaml

# 스레드 수 지정
./unified_analyzer --config config.yaml --threads 8
```

### 분석만 실행 (렌더링 제외)
```bash
./unified_analyzer --config 09_full_workflow.yaml --analysis-only
```

### 렌더링만 실행 (분석 제외)
```bash
./unified_analyzer --config 09_full_workflow.yaml --render-only
```

### 새 설정 파일 생성
```bash
./unified_analyzer --generate-config > my_config.yaml
```

---

## 분석 유형 설명

### 1. von_mises
Von Mises 등가 응력을 분석합니다.
```yaml
- name: "Stress Analysis"
  type: von_mises
  parts: [1, 2, 3]  # 비어있으면 모든 파트
  output_prefix: "stress"
```

### 2. eff_plastic_strain
유효 소성 변형률을 분석합니다.
```yaml
- name: "Strain Analysis"
  type: eff_plastic_strain
  parts: []
  output_prefix: "strain"
```

### 3. part_motion
파트의 운동(변위, 속도, 가속도)을 분석합니다.
```yaml
- name: "Motion Analysis"
  type: part_motion
  parts: [100, 101]
  quantities:
    - avg_displacement
    - avg_velocity
    - avg_acceleration
    - max_displacement
  output_prefix: "motion"
```

### 4. surface_stress
특정 방향을 바라보는 표면의 응력을 분석합니다.
```yaml
- name: "Bottom Surface"
  type: surface_stress
  parts: []
  surface:
    direction: [0, 0, -1]  # 법선 방향
    angle: 45.0            # 허용 각도
  output_prefix: "bottom"
```

### 5. surface_strain
특정 방향을 바라보는 표면의 변형률을 분석합니다.
```yaml
- name: "Surface Strain"
  type: surface_strain
  parts: [1, 2]
  surface:
    direction: [0, 0, 1]
    angle: 45.0
  output_prefix: "surface_strain"
```

### 6. comprehensive
하나의 파트에서 여러 분석을 동시에 수행합니다.
```yaml
- name: "Full Analysis"
  type: comprehensive
  parts: [1, 2, 3]
  quantities:
    - von_mises
    - eff_plastic_strain
    - avg_velocity
  output_prefix: "full"
```

---

## 렌더링 유형 설명

### 1. section_view
단일 단면뷰를 렌더링합니다.
```yaml
- name: "Z Section"
  type: section_view
  fringe: von_mises
  section:
    axis: z
    position: center  # 또는 0.5 (normalized), edge_min, edge_max
  states: all         # 또는 [0, 100, -1] (특정 state)
  output:
    format: mp4
    filename: "section.mp4"
    fps: 30
    resolution: [1920, 1080]
```

### 2. multi_section
여러 위치의 단면을 동시에 렌더링합니다.
```yaml
- name: "Multi Sections"
  type: multi_section
  fringe: von_mises
  sections:
    - axis: z
      positions: [0.25, 0.5, 0.75]
  states: all
  output:
    format: mp4
    filename: "multi_section.mp4"
```

---

## Fringe 타입

| 타입 | 설명 |
|-----|------|
| `von_mises` | Von Mises 등가 응력 |
| `eff_plastic_strain` | 유효 소성 변형률 |
| `pressure` | 압력 (양: 인장, 음: 압축) |
| `max_principal` | 최대 주응력 |
| `min_principal` | 최소 주응력 |
| `displacement_mag` | 변위 크기 |
| `velocity_mag` | 속도 크기 |

---

## Section Position 옵션

| 값 | 설명 |
|----|------|
| `center` | 중앙 (자동) |
| `edge_min` | 최소 경계 |
| `edge_max` | 최대 경계 |
| `quarter1` | 25% 위치 |
| `quarter3` | 75% 위치 |
| `0.0 ~ 1.0` | 정규화된 위치 |
| `절대값` | 절대 좌표 |

---

## 주의사항

1. **파트 ID**: `parts: []`는 모든 파트를 의미합니다.
2. **State 인덱스**: `-1`은 마지막 state를 의미합니다.
3. **Fringe Range**: `max: 0`은 자동 범위를 의미합니다.
4. **출력 경로**: 상대 경로는 `output.directory` 기준입니다.

---

## 참고 문서

- [UNIFIED_YAML_CONFIG_PLAN.md](../../UNIFIED_YAML_CONFIG_PLAN.md) - 상세 구현 계획
- [UNIFIED_YAML_PROGRESS.md](../../UNIFIED_YAML_PROGRESS.md) - 구현 진행 상황
- [COMPREHENSIVE_YAML_GUIDE.md](../../COMPREHENSIVE_YAML_GUIDE.md) - 기존 가이드
