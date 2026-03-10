# 전각도 낙하 시뮬레이션 통합 분석 시스템 기술 문서

**KooD3plotReader / DropAnalysis Pipeline**
작성일: 2026-03-09 | 버전: 1.0

---

## 목차

1. [시스템 개요](#1-시스템-개요)
2. [파이프라인 아키텍처](#2-파이프라인-아키텍처)
3. [DOE 전략](#3-doe-전략)
4. [Step 1 — unified_analyzer](#4-step-1--unified_analyzer)
5. [Step 2 — koo_report](#5-step-2--koo_report)
6. [Step 3 — 단면 렌더링](#6-step-3--단면-렌더링)
7. [통합 실행 스크립트](#7-통합-실행-스크립트-analyze_and_reportsh)
8. [디렉토리 구조](#8-디렉토리-구조)
9. [HTML 리포트 구조](#9-html-리포트-구조-11개-탭)
10. [수학적 기반](#10-수학적-기반)
11. [설정 파일](#11-설정-파일)
12. [성능 가이드](#12-성능-가이드)
13. [사용 예시](#13-사용-예시)

---

## 1. 시스템 개요

전각도 낙하 분석 시스템은 LS-DYNA 낙하 시뮬레이션 결과를 구 전체 방향에 대해 자동으로 분석하고 시각화하는 통합 파이프라인이다. 표준적인 26방향(IEC 60068-2-31) 또는 Fibonacci 격자 기반 N방향(100~1,144점)으로 낙하 자세를 정의하고, 각 방향별로 응력·변형률·가속도·운동량을 추출한 뒤, 전체 결과를 구면 등적도(Mollweide) 투영으로 시각화하여 취약 방향을 직관적으로 파악한다.

### 핵심 특징

| 항목 | 내용 |
|------|------|
| 지원 DOE | 26방향 큐보이드, Fibonacci N점 (100/500/1,144) |
| 분석 도구 | unified_analyzer (C++17, OpenMP) |
| 리포트 도구 | koo_report (Python, 11탭 HTML) |
| 렌더링 | LSPrePost 배치 모드 (MP4/PNG) |
| 시각화 | Mollweide 등적도 투영 + 구면 IDW 보간 |
| 자동화 | analyze_and_report.sh (3단계 파이프라인) |

---

## 2. 파이프라인 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                    LS-DYNA 시뮬레이션                         │
│          (외부 실행 — 본 시스템 범위 밖)                      │
│                                                              │
│  DOE: 26방향 큐보이드 / Fibonacci N점                         │
│  출력: output/Run_NNN/d3plot + DropSet.json                  │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│              Step 1: unified_analyzer (C++)                  │
│                                                              │
│  입력:  output/Run_NNN/d3plot (배치, 재귀 탐색)              │
│  처리:  응력·변형률·가속도·운동량 추출 (멀티스레드)            │
│  출력:  analysis_results/Run_NNN/                            │
│         ├── analysis_result.json                             │
│         ├── stress/part_NNN.csv                              │
│         ├── strain/part_NNN.csv                              │
│         └── motion/part_NNN.csv                              │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│              Step 2: koo_report (Python)                     │
│                                                              │
│  입력:  analysis_results/ + runner_config.json               │
│  처리:  집계 → 구면 보간 → Mollweide 투영                     │
│  출력:  report.html (11탭 대화형 리포트)                     │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼ (선택)
┌─────────────────────────────────────────────────────────────┐
│              Step 3: 단면 영상 렌더링                         │
│                                                              │
│  입력:  render_config.yaml (리포트 Render Export 탭 생성)    │
│  처리:  LSPrePost 배치 모드 (cfile 자동 생성)                 │
│  출력:  renders/ *.mp4 / *.png                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. DOE 전략

### 3.1 26방향 큐보이드 (IEC 60068-2-31)

표준 낙하 시험 방향을 직육면체로 정의한다.

| 분류 | 개수 | 설명 |
|------|------|------|
| 면 (Face) | 6 | ±X, ±Y, ±Z |
| 모서리 (Edge) | 12 | 두 면의 교선 방향 |
| 꼭짓점 (Corner) | 8 | 세 면의 교점 방향 |
| **합계** | **26** | |

### 3.2 Fibonacci 격자 (N점 균등 분포)

황금비(φ ≈ 1.618)를 이용한 준균등 구면 점 분포.

```
θ_i = arccos(1 - 2i / (N-1))
φ_i = 2π · i / φ
```

| 설정 | 점 수 | 적용 |
|------|-------|------|
| F100 | 100 | 초기 스크리닝 |
| F500 | 500 | 상세 분석 |
| F1144 | 1,144 | 정밀 취약 방향 탐색 |

Fibonacci 방식은 26방향 대비 방향 편향이 없고, 극점 집중 현상이 없으며, 임의의 N으로 확장 가능하다.

---

## 4. Step 1 — unified_analyzer

### 4.1 역할

LS-DYNA d3plot 바이너리에서 파트별 응력, 변형률, 운동량, 가속도 시계열을 추출하여 JSON + CSV로 저장한다.

### 4.2 실행 방법

```bash
# 기본 실행 (재귀 탐색 + skip-existing)
unified_analyzer \
  --recursive output/ \
  --config common_analysis.yaml \
  --output analysis_results/ \
  --skip-existing

# 강제 전체 재분석
unified_analyzer \
  --recursive output/ \
  --config common_analysis.yaml \
  --output analysis_results/
```

### 4.3 주요 옵션

| 옵션 | 설명 |
|------|------|
| `--recursive <dir>` | 하위 디렉토리에서 d3plot 재귀 탐색 |
| `--config <yaml>` | 분석 설정 파일 |
| `--output <dir>` | 결과 출력 루트 디렉토리 |
| `--skip-existing` | `analysis_result.json`이 있으면 건너뜀 |
| `--threads <N>` | 병렬 스레드 수 (기본: CPU 코어 수) |
| `--render-only` | 렌더링만 수행 (분석 건너뜀) |

### 4.4 분석 항목

| 항목 | 키 | 단위 |
|------|-----|------|
| Von Mises 응력 | `stress_history` | MPa |
| 유효 소성 변형률 | `strain_history` | - |
| 평균 변위 | `motion_analysis.avg_displacement` | mm |
| 평균 가속도 | `acceleration_history` | m/s² |
| 최대 변위 | `motion_analysis.max_displacement` | mm |
| 요소 품질 (선택) | `element_quality` | - |

### 4.5 출력 구조

```
analysis_results/
└── Run_001/
    ├── analysis_result.json     ← 요약 메트릭 (모든 파트)
    ├── stress/
    │   ├── all_stress.csv       ← 전체 응력 시계열
    │   └── part_001.csv
    ├── strain/
    │   └── part_001.csv
    ├── motion/
    │   └── part_001_motion.csv
    └── quality/                 ← --element-quality 시
        └── part_0_quality.csv
```

### 4.6 analysis_result.json 구조

```json
{
  "metadata": {
    "d3plot_path": "/data/.../d3plot",
    "num_parts": 5,
    "num_states": 52,
    "analysis_time": "2026-03-09T01:00:00"
  },
  "stress_history": [
    {
      "part_id": 1,
      "part_name": "Housing",
      "quantity": "von_mises",
      "global_max": 312.5,
      "data": [{"time": 0.0, "max": 0.0, "avg": 0.0}, ...]
    }
  ],
  "strain_history": [...],
  "motion_analysis": [...],
  "element_quality": [...]
}
```

---

## 5. Step 2 — koo_report

### 5.1 역할

모든 Run의 `analysis_result.json`을 집계하고, 방향별 취약성을 구면 투영 지도로 시각화하여 대화형 HTML 리포트를 생성한다.

### 5.2 실행 방법

```bash
# 기본 실행
python3 -m koo_report --test-dir /data/Tests/Test_001

# 항복응력 지정 (안전계수 계산)
python3 -m koo_report \
  --test-dir /data/Tests/Test_001 \
  --yield-stress 275 \
  --output report.html

# 시계열 해상도 조정 (대용량 케이스)
python3 -m koo_report \
  --test-dir /data/Tests/Test_006 \
  --ts-points 15
```

### 5.3 주요 옵션

| 옵션 | 설명 |
|------|------|
| `--test-dir <path>` | 테스트 루트 디렉토리 |
| `--yield-stress <MPa>` | 항복응력 (안전계수 탭 활성화) |
| `--output <path>` | 출력 HTML 경로 (기본: `<test-dir>/report.html`) |
| `--ts-points <N>` | 시계열 출력 포인트 수 (0=자동) |

### 5.4 입력 파일

| 파일 | 위치 | 내용 |
|------|------|------|
| `runner_config.json` | `<test-dir>/` | 방향 정의 (Euler 각도 → Run 번호 매핑) |
| `scenario.json` | `<test-dir>/` | DOE 전략, 낙하 높이, 재료 정보 |
| `DropSet.json` | `output/Run_NNN/` | 파트 정의, 초기 조건 |
| `analysis_result.json` | `analysis_results/Run_NNN/` | 분석 결과 |

### 5.5 runner_config.json 예시

```json
{
  "doe_strategy": "fibonacci",
  "n_directions": 1144,
  "runs": [
    {
      "run_id": 1,
      "run_dir": "Run_001",
      "orientation": {"roll": 0.0, "pitch": 0.0, "yaw": 0.0},
      "drop_height_mm": 1200,
      "surface": "concrete"
    },
    ...
  ]
}
```

### 5.6 자동 생성 Findings

koo_report는 다음 조건을 자동 탐지하여 Summary에 표시한다.

| 조건 | 메시지 |
|------|--------|
| 항복응력 초과 | `N개 방향에서 항복 감지 (SF < 1.0)` |
| 안전계수 < 1.5 | `N개 방향 안전계수 경고` |
| 가속도 > 5,000 G | `과도 충격 감지` |
| 구면 커버리지 < 80% | `DOE 커버리지 부족` |

---

## 6. Step 3 — 단면 렌더링

### 6.1 역할

HTML 리포트에서 취약 방향을 선택하고, 해당 방향의 d3plot 파일에 대해 LSPrePost 배치 렌더링으로 단면 응력 영상(MP4/PNG)을 생성한다.

### 6.2 Render Export 워크플로우

1. `report.html` → **Render Export 탭** 열기
2. Mollweide 지도에서 취약 방향 클릭 선택
3. 단면 축(X/Y/Z), 단면 위치, Fringe 종류 설정
4. **YAML 다운로드** → `render_config.yaml` 저장
5. 렌더링 실행:

```bash
analyze_and_report.sh /data/Tests/Test_001 \
  --render-only \
  --render-config render_config.yaml
```

### 6.3 render_config.yaml 구조

```yaml
version: "2.0"
performance:
  lsprepost_path: "/installed/lsprepost/lsprepost"
  render_threads: 1

render_jobs:
  - name: "Run_005_F6_Bottom_Z_Section"
    input: "/data/Tests/Test_001/output/Run_005/d3plot"
    output_prefix: "renders/Run_005_z_section"
    fringe: von_mises
    section_planes:
      - axis: Z
        position: 0.5
    view: iso
    width: 1920
    height: 1080
    fps: 30
    format: mp4
```

### 6.4 지원 Fringe 종류

| Fringe | LSPrePost ID | 단위 |
|--------|-------------|------|
| von_mises | 9 | MPa |
| eff_plastic_strain | 7 | - |
| displacement | 20 | mm |
| stress_xx/yy/zz | 1/2/3 | MPa |
| principal_stress_1 | 14 | MPa |
| shell_thickness | 67 | mm |

### 6.5 단면 지원

| 축 | 동작 | 비고 |
|----|------|------|
| Z | drawcut + genselect 선택 fringe | Mesa 완전 지원 |
| X / Y | 전체 fringe (drawcut 없음) | Mesa OpenGL 제한 |

---

## 7. 통합 실행 스크립트: analyze_and_report.sh

### 7.1 위치

```
scripts/analyze_and_report.sh
```

### 7.2 사용법

```bash
analyze_and_report.sh <test-dir> [옵션]
```

### 7.3 전체 옵션

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--config <yaml>` | `<test-dir>/common_analysis.yaml` | 분석 설정 파일 |
| `--threads <N>` | 4 | 분석 병렬 스레드 수 |
| `--force-reanalyze` | (해제) | 기존 결과 무시하고 전체 재분석 |
| `--yield-stress <MPa>` | 0 (비활성) | 항복응력 (안전계수 탭 활성화) |
| `--ts-points <N>` | 0 (자동) | 시계열 해상도 |
| `--output <path>` | `<test-dir>/report.html` | HTML 출력 경로 |
| `--no-report` | (해제) | 분석만 수행 |
| `--no-analyze` / `--report-only` | (해제) | 리포트만 재생성 |
| `--render-config <yaml>` | (없음) | 렌더 설정 파일 |
| `--render-only` | (해제) | 렌더링만 수행 |

### 7.4 실행 흐름

```
[Step 1] unified_analyzer --recursive output/ ...
         └─ d3plot 개수 확인 → 신규만 분석 (--skip-existing)
         └─ 분석 결과: analysis_results/Run_NNN/

[Step 2] koo_report --test-dir . --yield-stress ...
         └─ HTML 리포트 생성: report.html

[Step 3] (선택) unified_analyzer --config render_job_NNN.yaml --render-only
         └─ YAML 분할 (PyYAML) → 순차 실행
         └─ 출력: renders/*.mp4
```

---

## 8. 디렉토리 구조

```
Test_001_Full26_1Step/
│
├── scenario.json               # DOE 전략, 낙하 높이, 재료
├── runner_config.json          # Euler 각도 → Run 번호 매핑
├── common_analysis.yaml        # unified_analyzer 설정
│
├── output/                     # LS-DYNA 시뮬레이션 출력
│   ├── Run_001/
│   │   ├── d3plot             # 바이너리 결과 (메인)
│   │   ├── d3plot01           # 결과 파일 패밀리
│   │   ├── DropSet.json       # 초기 조건, 파트 목록
│   │   ├── glstat             # 글로벌 에너지 통계
│   │   └── binout0000         # 접촉·슬라이딩 이력
│   ├── Run_002/
│   └── ... Run_026/
│
├── analysis_results/           # unified_analyzer 출력
│   ├── Run_001/
│   │   ├── analysis_result.json
│   │   ├── stress/
│   │   ├── strain/
│   │   └── motion/
│   └── ... Run_026/
│
├── report.html                 # koo_report 출력 (11탭 HTML)
├── report.json                 # JSON 데이터 익스포트
│
└── renders/                    # (선택) LSPrePost 렌더링 출력
    ├── Run_005_z_section.mp4
    └── Run_012_x_section.mp4
```

---

## 9. HTML 리포트 구조 (11개 탭)

koo_report가 생성하는 HTML은 단일 파일(self-contained)로, 모든 데이터가 JavaScript 변수로 임베드되어 외부 서버 없이 브라우저에서 동작한다.

| 탭 번호 | 탭 이름 | 주요 내용 |
|---------|---------|---------|
| 0 | **Overview** | 프로젝트 요약, DOE 전략, 자동 Findings, 시뮬레이션 파라미터 |
| 1 | **Mollweide Map** | 구면 취약성 지도 (등적도 투영), 3D 글로브 회전 뷰 |
| 2 | **Time History** | 방향·파트별 응력/변형률/G/변위 시계열 차트 |
| 3 | **Part Risk** | 파트 × 방향 위험 행렬 (히트맵) |
| 4 | **Heatmap** | 파트 × 방향 다중 물리량 히트맵 (드롭다운 전환) |
| 5 | **Directional** | 방향 분류별 비교 (face/edge/corner/fibonacci) |
| 6 | **Failure** | 항복·파손 위험 필터링 (항복응력 지정 시 활성) |
| 7 | **Statistics** | 파트별 분포 (히스토그램, 박스플롯, CoV) |
| 8 | **Impact Analysis** | 충격 펄스 분석 (펄스 폭, 임펄스, SRS, CAI 지수) |
| 9 | **Part Analysis** | 파트 심층 분석 (KPI, 취약 방향 지도, 분포) |
| 10 | **Advanced** | 충격 응답 스펙트럼 (SRS), CAI 복합 지수 |
| 11 | **Render Export** | Mollweide 각도 선택 → render_config.yaml 자동 생성 |

### 탭 11 — Render Export 상세

Render Export 탭은 다음 UI를 제공한다:

- **미니 Mollweide 지도**: 클릭으로 취약 방향 선택 (복수 선택 가능)
- **단면 설정**: 축(X/Y/Z), 위치(center/25%/50%/75%/min/max)
- **Fringe 선택**: Von Mises, 소성변형률, 변위 등
- **렌더 설정**: 해상도, FPS, 포맷(MP4/PNG)
- **YAML 다운로드**: 선택 내용 기반 `render_config.yaml` 자동 생성

---

## 10. 수학적 기반

### 10.1 Euler 각도 → 방향 벡터

```
Rz(yaw) · Ry(pitch) · Rx(roll) · [0, 0, -1]ᵀ = (dx, dy, dz)
```

낙하 방향은 중력 방향(-Z)을 초기 벡터로 하여 회전한다.

### 10.2 방향 벡터 → 구면 좌표

```
λ = atan2(dx, -dz)        # 경도 [-π, π]
φ = arcsin(dy)             # 위도 [-π/2, π/2]
```

### 10.3 Mollweide 투영 (Newton-Raphson)

```
2θ + sin(2θ) = π · sin(φ)    [Newton-Raphson으로 θ 수치해]

x = (2√2 / π) · λ · cos(θ)
y = √2 · sin(θ)
```

등적 투영이므로 지도상 면적은 구면 면적에 비례한다. 즉, 지도에서 30%가 빨간색이면 전체 방향의 30%에서 취약하다는 의미로 직독이 가능하다.

### 10.4 구면 IDW 보간

이산된 시뮬레이션 방향에서 연속 등고선을 생성하기 위해 대권 거리 기반 IDW를 사용한다.

```
d_ij = 2 · arcsin(√(sin²(Δφ/2) + cos(φ_i)·cos(φ_j)·sin²(Δλ/2)))  [Haversine]

w_ij = 1 / d_ij^p      (p = 3.5)

σ(q) = Σ(w_ij · σ_j) / Σ(w_ij)
```

유클리드 거리 대신 대권 거리를 사용하여 극점 왜곡을 방지한다.

---

## 11. 설정 파일

### 11.1 common_analysis.yaml

```yaml
version: "2.0"
output:
  json: true
  csv: true
performance:
  threads: 4
  verbose: false

analysis_jobs:
  - name: All Parts Stress
    type: von_mises
    parts: []                # 빈 배열 = 전 파트
    output_prefix: "stress/all"

  - name: All Parts Strain
    type: eff_plastic_strain
    parts: []
    output_prefix: "strain/all"

  - name: All Parts Motion
    type: part_motion
    parts: []
    quantities: [avg_displacement, avg_velocity, avg_acceleration, max_displacement]
    output_prefix: "motion/all"

  # 요소 품질 분석 (선택)
  # - name: Element Quality
  #   type: element_quality
  #   parts: []
  #   output_prefix: "quality/all"
```

### 11.2 analysis_jobs 타입 목록

| 타입 | 설명 |
|------|------|
| `von_mises` | Von Mises 응력 시계열 |
| `eff_plastic_strain` | 유효 소성 변형률 시계열 |
| `part_motion` | 변위·속도·가속도 운동량 |
| `surface_stress` | 표면 응력 분포 |
| `element_quality` | 요소 품질 (AR, Jacobian, Warpage, Skewness) |

---

## 12. 성능 가이드

### 12.1 분석 (unified_analyzer)

| 케이스 | d3plot 수 | 추천 스레드 | 예상 RAM | 예상 시간 |
|--------|----------|-----------|---------|---------|
| 26방향 | 26 | 4 | ~3 GB | 5~15분 |
| F100 | 100 | 4~8 | ~8 GB | 20~40분 |
| F500 | 500 | 8 | ~30 GB | 2~4시간 |
| F1144 | 1,144 | 8~16 | ~64 GB | 4~8시간 |

> **주의**: 32스레드 병렬 읽기 시 OOM 발생 가능. 128 GB 시스템에서 VM 실행 중이면 `--threads 4` 권장.

### 12.2 리포트 생성 (koo_report)

| ts-points | HTML 크기 | 생성 시간 |
|-----------|---------|---------|
| 0 (자동) | 20~100 MB | 10~60초 |
| 10 | 5~15 MB | 5~15초 |
| 30 | 15~40 MB | 10~30초 |

대용량(F1144) 케이스에서는 `--ts-points 10~20`을 권장한다.

### 12.3 렌더링 (LSPrePost)

| 항목 | 값 |
|------|-----|
| 단면 영상 1개 | 10~30초 |
| 병렬 실행 | 지원 안 함 (LSPrePost 단일 인스턴스) |
| 최소 요구 사항 | OpenGL 지원 디스플레이 또는 Mesa 오프스크린 |

---

## 13. 사용 예시

### 예시 A: 26방향 큐보이드 표준 분석

```bash
# 분석 + 리포트
analyze_and_report.sh /data/Tests/Test_001_Full26 \
  --yield-stress 275

# 리포트만 재생성 (분석 건너뜀)
analyze_and_report.sh /data/Tests/Test_001_Full26 \
  --report-only \
  --yield-stress 275
```

### 예시 B: Fibonacci 1,144점 대용량 분석

```bash
# 메모리 절약: 4스레드 + 시계열 경량화
analyze_and_report.sh /data/Tests/Test_006_F1144 \
  --threads 4 \
  --yield-stress 310 \
  --ts-points 15

# 강제 재분석 (기존 결과 삭제 없이)
analyze_and_report.sh /data/Tests/Test_006_F1144 \
  --force-reanalyze \
  --threads 4
```

### 예시 C: 단면 렌더링

```bash
# 1. report.html → Render Export 탭에서 YAML 다운로드

# 2. 렌더링 실행
analyze_and_report.sh /data/Tests/Test_001 \
  --render-only \
  --render-config ~/Downloads/render_config.yaml

# 출력: renders/*.mp4
```

### 예시 D: 여러 테스트 배치 처리

```bash
for test in Test_001 Test_002 Test_003; do
  echo "=== $test ==="
  analyze_and_report.sh /data/Tests/$test \
    --threads 4 \
    --yield-stress 275 \
    --ts-points 20
done
```

### 예시 E: 요소 품질 포함 분석

```bash
# common_analysis.yaml에 element_quality job 추가 후:
analyze_and_report.sh /data/Tests/Test_001 \
  --config my_config_with_quality.yaml \
  --yield-stress 275
```

---

## 부록: 도구 위치

| 도구 | 위치 |
|------|------|
| unified_analyzer (빌드) | `build/examples/unified_analyzer` |
| unified_analyzer (설치) | `installed/bin/unified_analyzer` |
| koo_report (Python) | `python/koo_report/` |
| koo_report (바이너리) | `installed/bin/koo_report` |
| single_analyzer (Python) | `python/single_analyzer/` |
| LSPrePost (Linux) | `installed/lsprepost/lsprepost` |
| LSPrePost (Windows) | `installed/lsprepost_win64/lsprepost.exe` |
| 분석 스크립트 | `scripts/analyze_and_report.sh` |
| LSPrePost 다운로드 (Linux) | `scripts/download_lsprepost.sh` |
| LSPrePost 다운로드 (Windows) | `scripts/download_lsprepost.bat` |

---

*KooD3plotReader Project — Internal Technical Documentation*
