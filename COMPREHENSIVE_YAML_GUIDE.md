# Comprehensive YAML Configuration Guide

## 개요

KooD3plot V4는 이제 **comprehensive YAML 설정**을 완전히 지원합니다!

원래 KooDynaPostProcessor에서 사용하던 상세한 YAML 설정 파일을 그대로 사용할 수 있으며, 다음과 같은 기능이 추가되었습니다:

- ✅ **Analysis 설정**: run_ids, LSPrePost 경로/옵션, cache 경로
- ✅ **Fringe 설정**: Colormap 지원 (rainbow, jet, grayscale)
- ✅ **Output 설정**: Movie/Images/Data extraction/Comparison 상세 제어
- ✅ **Processing 설정**: Parallel/Cache/Memory/Retry 옵션
- ✅ **Logging 설정**: Level, File, Console 출력 제어
- ✅ **Notification 설정**: Email, Slack (구조만 정의, 구현은 향후)

## 사용법

### 1. YAML 파일 자동 감지

CLI는 파일 확장자를 보고 자동으로 JSON/YAML을 감지합니다:

```bash
# YAML 파일 (.yaml 또는 .yml)
kood3plot_cli --mode batch --config render_config.yaml results/d3plot -o output.mp4

# JSON 파일 (.json)
kood3plot_cli --mode batch --config render_config.json results/d3plot -o output.mp4
```

### 2. 기본 YAML 설정 예제

```yaml
# 최소한의 설정
analysis:
  data_path: "./results"

fringe:
  type: "von_mises"
  auto_range: true

output:
  movie:
    enabled: true

sections:
  - auto_mode: "single"
    auto_params:
      orientation: "Z"
      position: "center"
```

### 3. Comprehensive YAML 설정 예제

```yaml
# 모든 옵션을 포함한 comprehensive 설정
analysis:
  run_ids:
    - "run_001"
    - "run_002"
    - "run_003"
  data_path: "./data/simulations"
  output_path: "./output/section_analysis"
  cache_path: "./cache"
  lsprepost:
    executable: "lspp412"
    options: "-nographics"
    timeout: 3600  # seconds

fringe:
  type: "von_mises"
  range:
    min: 0.0
    max: 500.0
  auto_range: true
  colormap: "rainbow"  # rainbow, jet, grayscale

output:
  movie:
    enabled: true
    resolution: [1920, 1080]
    fps: 30
    codec: "h264"

  images:
    enabled: true
    format: "png"
    resolution: [1920, 1080]
    timesteps: "all"

  data:
    enabled: true
    format: "json"
    include:
      - "stress"
      - "strain"
      - "displacement"

  comparison:
    enabled: true
    baseline: "run_001"
    generate_html: true
    generate_csv: true
    include_plots: true

view:
  orientation: "iso"
  zoom_factor: 1.0
  auto_fit: true

processing:
  parallel:
    enabled: true
    max_threads: 8

  cache:
    enabled: true
    cache_bounding_boxes: true
    cache_sections: true

  memory:
    max_memory_mb: 16384
    chunk_size: 1000000
    cleanup_threshold: 0.8

  retry:
    enabled: true
    max_attempts: 3
    delay_seconds: 5

logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR
  file: "./logs/section_analysis.log"
  console: true

sections:
  - auto_mode: "single"
    auto_params:
      orientation: "Z"
      position: "center"
```

## 주요 설정 옵션 설명

### Analysis Section

- **run_ids**: 처리할 실행 ID 목록
- **data_path**: d3plot 파일이 있는 경로
- **output_path**: 출력 파일을 저장할 경로
- **cache_path**: 캐시 파일 저장 경로
- **lsprepost**: LSPrePost 실행 설정
  - **executable**: 실행 파일 경로
  - **options**: 실행 옵션 (예: `-nographics`)
  - **timeout**: 실행 제한 시간 (초)

### Fringe Section

- **type**: Fringe 타입 (모든 타입은 LSPrePost와 완전히 호환됩니다)

  **응력 성분 (Stress Components)**:
  - `x_stress`, `stress_xx`, `sigma_xx`: X 응력 (LSPrePost ID: 1)
  - `y_stress`, `stress_yy`, `sigma_yy`: Y 응력 (LSPrePost ID: 2)
  - `z_stress`, `stress_zz`, `sigma_zz`: Z 응력 (LSPrePost ID: 3)
  - `xy_stress`, `stress_xy`, `sigma_xy`: XY 응력 (LSPrePost ID: 4)
  - `yz_stress`, `stress_yz`, `sigma_yz`: YZ 응력 (LSPrePost ID: 5)
  - `zx_stress`, `xz_stress`, `stress_xz`: ZX/XZ 응력 (LSPrePost ID: 6)

  **변형률 (Strain)**:
  - `effective_plastic_strain`, `plastic_strain`: 유효 소성 변형률 (LSPrePost ID: 7)
  - `effective_strain`: 유효 변형률 (LSPrePost ID: 80)
  - `x_strain`, `strain_xx`: X 변형률 (LSPrePost ID: 57)
  - `y_strain`, `strain_yy`: Y 변형률 (LSPrePost ID: 58)
  - `z_strain`, `strain_zz`: Z 변형률 (LSPrePost ID: 59)
  - `xy_strain`, `strain_xy`: XY 변형률 (LSPrePost ID: 60)
  - `yz_strain`, `strain_yz`: YZ 변형률 (LSPrePost ID: 61)
  - `zx_strain`, `xz_strain`: ZX/XZ 변형률 (LSPrePost ID: 62)
  - `principal_strain_1`: 주변형률 1 (LSPrePost ID: 77)
  - `principal_strain_2`: 주변형률 2 (LSPrePost ID: 78)
  - `principal_strain_3`: 주변형률 3 (LSPrePost ID: 79)

  **압력 및 응력 지표 (Pressure & Stress Measures)**:
  - `pressure`: 압력 (LSPrePost ID: 8)
  - `von_mises`, `von_mises_stress`: von Mises 응력 (LSPrePost ID: 9) - 기본값
  - `max_shear_stress`: 최대 전단응력 (LSPrePost ID: 13)
  - `principal_stress_1`, `principal_1`: 주응력 1 (LSPrePost ID: 14)
  - `principal_stress_2`, `principal_2`: 주응력 2 (LSPrePost ID: 15)
  - `principal_stress_3`, `principal_3`: 주응력 3 (LSPrePost ID: 16)

  **변위 (Displacement)**:
  - `x_displacement`, `displacement_x`, `disp_x`: X 변위 (LSPrePost ID: 17)
  - `y_displacement`, `displacement_y`, `disp_y`: Y 변위 (LSPrePost ID: 18)
  - `z_displacement`, `displacement_z`, `disp_z`: Z 변위 (LSPrePost ID: 19)
  - `result_displacement`, `displacement`: 합성 변위 (LSPrePost ID: 20)

  **속도 및 가속도 (Velocity & Acceleration)**:
  - `result_acceleration`, `acceleration`: 합성 가속도 (LSPrePost ID: 23)
  - `result_velocity`, `velocity`: 합성 속도 (LSPrePost ID: 24)

  **기타 (Others)**:
  - `hourglass_energy_density`: Hourglass 에너지 밀도 (LSPrePost ID: 43)
  - `shell_thickness`, `thickness`: 쉘 두께 (LSPrePost ID: 67)
  - `triaxiality`: 삼축응력도 (LSPrePost ID: 520)
  - `normalized_mean_stress`: 정규화 평균응력 (LSPrePost ID: 521)
  - `strain_energy_density`: 변형률 에너지 밀도 (LSPrePost ID: 524)
  - `volumetric_strain`: 체적 변형률 (LSPrePost ID: 529)
  - `signed_von_mises`: 부호 있는 von Mises (LSPrePost ID: 530)

- **range**: 수동 범위 설정
  - **min**: 최소값
  - **max**: 최대값
- **auto_range**: 자동 범위 설정 (true/false)
- **colormap**: 컬러맵 선택
  - `rainbow`: 무지개 (기본값)
  - `jet`: Jet 컬러맵
  - `grayscale`: 흑백

### Output Section

#### Movie Settings
- **enabled**: 동영상 출력 활성화
- **resolution**: 해상도 [width, height]
- **fps**: 프레임 레이트
- **codec**: 코덱 (h264, wmv, avi)

#### Images Settings
- **enabled**: 이미지 출력 활성화
- **format**: 이미지 형식 (png, jpg, bmp)
- **resolution**: 해상도
- **timesteps**: "all" 또는 특정 timestep 목록

#### Data Extraction
- **enabled**: 데이터 추출 활성화
- **format**: 출력 형식 (json, csv, hdf5)
- **include**: 추출할 데이터 타입
  - `stress`: 응력 데이터
  - `strain`: 변형률 데이터
  - `displacement`: 변위 데이터

#### Comparison
- **enabled**: 비교 분석 활성화
- **baseline**: 기준 실행 ID
- **generate_html**: HTML 보고서 생성
- **generate_csv**: CSV 결과 생성
- **include_plots**: 플롯 포함

### Processing Section

#### Parallel Processing
- **enabled**: 병렬 처리 활성화
- **max_threads**: 최대 스레드 수

#### Cache
- **enabled**: 캐싱 활성화
- **cache_bounding_boxes**: Bounding box 캐싱
- **cache_sections**: Section 데이터 캐싱

#### Memory Management
- **max_memory_mb**: 최대 메모리 사용량 (MB)
- **chunk_size**: 청크 크기 (노드 개수)
- **cleanup_threshold**: 정리 임계값 (0.0-1.0)

#### Retry Settings
- **enabled**: 재시도 활성화
- **max_attempts**: 최대 재시도 횟수
- **delay_seconds**: 재시도 간 대기 시간 (초)

### Logging Section

- **level**: 로그 레벨 (DEBUG, INFO, WARNING, ERROR)
- **file**: 로그 파일 경로
- **console**: 콘솔 출력 활성화

### Sections Section

- **auto_mode**: 자동 단면 생성 모드
  - `manual`: 수동 정의
  - `single`: 단일 위치
  - `even_spaced`: 균등 간격
  - `uniform_spacing`: 균일 간격
  - `standard_3`: 표준 3단면 (25%, 50%, 75%)
  - `offset_edges`: 가장자리에서 오프셋

- **auto_params**: 자동 생성 파라미터
  - **orientation**: 방향 (X, Y, Z)
  - **position**: 위치
    - `center`: 중심 (50%)
    - `quarter_1`: 1/4 위치 (25%)
    - `quarter_3`: 3/4 위치 (75%)
    - `edge_min`: 최소 가장자리 (0%)
    - `edge_max`: 최대 가장자리 (100%)
    - `custom`: 사용자 정의

## 실전 예제

### 예제 1: 기본 렌더링

```bash
# YAML 설정 파일 사용
kood3plot_cli --mode batch --config my_config.yaml results/d3plot -o output.mp4
```

### 예제 2: 다중 실행 비교

```bash
# 3개의 실행을 병렬로 비교
kood3plot_cli --mode multirun \
  --run-config baseline.yaml \
  --run-config design_A.yaml \
  --run-config design_B.yaml \
  --threads 4 \
  --comparison-output comparison/ \
  results/d3plot
```

### 예제 3: 자동 단면 생성

```bash
# YAML에 sections 정의 불필요
kood3plot_cli --mode autosection results/d3plot -o auto.png
```

## 기존 KooDynaPostProcessor 설정 파일 사용

기존 KooDynaPostProcessor의 YAML 설정 파일을 거의 그대로 사용할 수 있습니다!

```bash
# 기존 설정 파일 복사
cp references/configs/section_analysis_config.yaml my_config.yaml

# KooD3plot CLI로 실행
kood3plot_cli --mode batch --config my_config.yaml results/d3plot -o output.mp4
```

**참고**: 일부 고급 기능 (orientations의 여러 positions, 복잡한 sections 정의 등)은 현재 부분적으로 지원됩니다. 핵심 기능은 모두 작동합니다.

## 제한 사항

현재 버전에서 **지원되지 않는** 기능:

1. **Sections의 Orientations**: 복잡한 nested orientations 구조는 아직 완전히 파싱되지 않음
2. **Custom Section Planes**: base_point와 normal_vector를 사용한 사용자 정의 단면
3. **Environment Variables**: `${VAR_NAME}` 구문
4. **Wildcards/Ranges in run_ids**: `run_*` 또는 `baseline_[1-5]` 형식
5. **Notification**: Email/Slack 알림 (구조만 정의됨)

이러한 기능들은 향후 업데이트에서 추가될 예정입니다.

## 문제 해결

### YAML 파싱 오류

```bash
# verbose 모드로 상세 오류 확인
kood3plot_cli --mode batch --config my_config.yaml -v results/d3plot

# 오류 발생 시 getLastError() 메시지 확인
Error details: YAML parsing error: ...
```

### JSON/YAML 선택

```bash
# 명시적으로 확장자 사용
my_config.yaml  # YAML 파서 사용
my_config.json  # JSON 파서 사용
```

## 참조

- 기본 YAML 예제: `test_comprehensive.yaml`
- 원본 설정 예제: `references/configs/section_analysis_config.yaml`
- 실제 데이터 예제: `references/configs/real_data_single_run.yaml`
- API 문서: `USAGE.md`
- CLI 사용법: `KOOD3PLOT_CLI_사용법.md`

---

**KooD3plot V4** - Comprehensive YAML Configuration Support
