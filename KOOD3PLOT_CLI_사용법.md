# KooD3plot CLI - 통합 명령줄 인터페이스 사용법

## 개요

`kood3plot_cli`는 LS-DYNA d3plot 파일을 처리하는 통합 CLI 도구입니다.
하나의 프로그램으로 데이터 추출, 렌더링, 배치 처리, 다중 실행 비교 등 모든 작업을 수행할 수 있습니다.

## 7가지 실행 모드

| 모드 | 설명 | 주요 용도 |
|------|------|----------|
| `query` | 데이터 추출 (기본값) | 응력, 변위 등 결과 데이터를 CSV/JSON/HDF5로 추출 |
| `render` | 단일 이미지 렌더링 | 특정 시점의 응력 분포 이미지 생성 |
| `batch` | 배치 렌더링 | JSON 설정 파일 기반 대량 렌더링 |
| `multisection` | 다중 단면 렌더링 | 여러 단면을 한번에 렌더링 |
| `autosection` | 자동 단면 생성 | X, Y, Z 축 중심 단면을 자동 생성하여 렌더링 |
| `multirun` | 다중 실행 비교 | 여러 시뮬레이션 결과를 병렬로 처리하고 비교 |
| `export` | LS-DYNA keyword 파일 내보내기 | 변형 노드 좌표, 변위, 응력을 .k 파일로 내보내기 |

## 설치 및 설정

### 1. 빌드 및 설치

```bash
cd /home/koopark/claude/KooD3plotReader/KooD3plotReader
./build.sh
```

빌드가 완료되면 `installed/` 디렉토리에 다음이 생성됩니다:
- `installed/bin/kood3plot_cli` - 통합 CLI 실행 파일
- `installed/lsprepost/` - LSPrePost 렌더링 엔진 (자동 복사됨)
- `installed/lib/` - 라이브러리 파일들
- `installed/include/` - 헤더 파일들

### 2. 환경 변수 설정 (선택)

```bash
# PATH에 추가하면 어디서든 실행 가능
export PATH=$PATH:/home/koopark/claude/KooD3plotReader/KooD3plotReader/installed/bin

# 라이브러리 경로 추가
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/home/koopark/claude/KooD3plotReader/KooD3plotReader/installed/lib
```

## 사용 예제

### 모드 1: query - 데이터 추출

**기본 사용법: von Mises 응력 추출**
```bash
kood3plot_cli --mode query -q von_mises results/d3plot -o stress.csv
```

**특정 부품의 변위 추출**
```bash
kood3plot_cli --mode query -q displacement -p Hood results/d3plot -o disp.csv
```

**시간 구간 선택 (0-100 state, 10 step씩)**
```bash
kood3plot_cli --mode query -q von_mises --first 0 --last 100 --step 10 \
  results/d3plot -o stress_subset.csv
```

**값 필터링 (500 MPa 이상만)**
```bash
kood3plot_cli --mode query -q von_mises --min 500 results/d3plot -o high_stress.csv
```

**JSON 형식으로 출력**
```bash
kood3plot_cli --mode query -q von_mises results/d3plot -o stress.json --format json
```

### 모드 2: render - 단일 이미지 렌더링

**등각투상(isometric) 뷰로 렌더링**
```bash
kood3plot_cli --mode render --view isometric results/d3plot -o result.png
```

**특정 뷰 각도로 렌더링**
```bash
# top, bottom, left, right, front, back, isometric 선택 가능
kood3plot_cli --mode render --view top results/d3plot -o top_view.png
```

**단면 뷰 렌더링 (Z=0 평면)**
```bash
kood3plot_cli --mode render --section-plane 0 0 0  0 0 1 results/d3plot -o section.png
#                                            ↑점(px,py,pz) ↑법선벡터(nx,ny,nz)
```

**애니메이션 생성 (MP4)**
```bash
kood3plot_cli --mode render --animate --render-output animation.mp4 results/d3plot
```

**다른 fringe 타입 사용**
```bash
# von_mises, displacement, stress_xx, stress_yy, stress_zz, effective_strain 등
kood3plot_cli --mode render --fringe displacement results/d3plot -o disp.png
```

### 모드 3: batch - 배치 렌더링

**설정 파일 기반 렌더링**
```bash
kood3plot_cli --mode batch --config render_config.json results/d3plot -o output.png
```

**render_config.json 예제:**
```json
{
  "analysis": {
    "data_path": "results/d3plot"
  },
  "fringe": {
    "type": "von_mises",
    "auto_range": true
  },
  "sections": [
    {
      "auto_mode": "single",
      "auto_params": {
        "orientation": "Z",
        "position": "center"
      }
    }
  ],
  "view": {
    "orientation": "iso"
  },
  "output": {
    "movie": true,
    "width": 1920,
    "height": 1080
  }
}
```

### 모드 4: multisection - 다중 단면 렌더링

여러 단면을 한 번에 렌더링합니다.

```bash
kood3plot_cli --mode multisection --config sections.json results/d3plot -o output.png
```

**sections.json 예제 (3개 단면):**
```json
{
  "sections": [
    {
      "auto_mode": "single",
      "auto_params": {"orientation": "X", "position": "center"}
    },
    {
      "auto_mode": "single",
      "auto_params": {"orientation": "Y", "position": "center"}
    },
    {
      "auto_mode": "single",
      "auto_params": {"orientation": "Z", "position": "center"}
    }
  ],
  "fringe": {"type": "von_mises", "auto_range": true},
  "output": {"movie": true}
}
```

출력 파일:
- `output_section_0.mp4` - X축 중심 단면
- `output_section_1.mp4` - Y축 중심 단면
- `output_section_2.mp4` - Z축 중심 단면

### 모드 5: autosection - 자동 단면 생성

설정 파일 없이 X, Y, Z 축의 중심 단면을 자동으로 생성합니다.

```bash
kood3plot_cli --mode autosection results/d3plot -o auto.png
```

**애니메이션으로 생성**
```bash
kood3plot_cli --mode autosection --animate results/d3plot -o auto.mp4
```

**다른 fringe 타입으로**
```bash
kood3plot_cli --mode autosection --fringe displacement results/d3plot -o disp_auto.png
```

출력 파일:
- `auto_auto_0.png` - X축 중심 단면
- `auto_auto_1.png` - Y축 중심 단면
- `auto_auto_2.png` - Z축 중심 단면

### 모드 6: multirun - 다중 실행 비교

여러 시뮬레이션 결과를 병렬로 처리하고 비교합니다.

**기본 사용법 (4개 스레드)**
```bash
kood3plot_cli --mode multirun \
  --run-config run1.json \
  --run-config run2.json \
  --run-config run3.json \
  --threads 4 \
  --comparison-output comparison_results/ \
  results/d3plot
```

**각 run config JSON 예제 (run1.json):**
```json
{
  "fringe": {
    "type": "von_mises",
    "auto_range": true
  },
  "sections": [
    {
      "auto_mode": "single",
      "auto_params": {
        "orientation": "Z",
        "position": "center"
      }
    }
  ],
  "output": {
    "movie": true
  }
}
```

**출력 결과:**
```
comparison_results/
├── run_0/
│   └── section_0.mp4
├── run_1/
│   └── section_0.mp4
├── run_2/
│   └── section_0.mp4
├── comparison_report.txt   # 텍스트 비교 보고서
└── results.csv              # CSV 결과 요약
```

**비교 보고서 예제:**
```
Multi-Run Comparison Report
Total Runs: 3
Successful: 3
Failed: 0

Run ID: run_0
  Status: SUCCESS
  Time: 45.23 seconds
  Generated Files: 1
    - comparison_results/run_0/section_0.mp4

Run ID: run_1
  Status: SUCCESS
  Time: 44.87 seconds
  ...
```

## 고급 사용법

### 1. 상세 정보 출력 (-v, --verbose)

```bash
kood3plot_cli --mode render -v results/d3plot -o output.png
```

진행 상황과 상세 로그가 출력됩니다.

### 2. 파일 정보 확인

```bash
# d3plot 파일 기본 정보
kood3plot_cli --info results/d3plot

# 포함된 부품 목록
kood3plot_cli --list-parts results/d3plot
```

### 3. LSPrePost 경로 지정

기본적으로 `installed/lsprepost/lspp412_mesa`를 사용하지만, 다른 경로 지정 가능:

```bash
kood3plot_cli --mode render --lsprepost-path /custom/path/lsprepost \
  results/d3plot -o output.png
```

### 4. 템플릿 사용 (query 모드)

```bash
# 사용 가능한 템플릿 목록
kood3plot_cli --list-templates

# 템플릿으로 쿼리 실행
kood3plot_cli --template max_stress_history results/d3plot -o stress_history.csv
```

## 모드 7: export - LS-DYNA keyword 파일 내보내기

d3plot 결과 데이터를 LS-DYNA keyword 파일 (.k)로 내보냅니다.

### 기본 사용법: 변형된 노드 좌표 내보내기

```bash
# 마지막 state의 변형된 노드 좌표
kood3plot_cli --mode export results/d3plot -o deformed.k
```

### 지원 포맷

| 포맷 | 설명 | 옵션 값 |
|------|------|---------|
| NODE_DEFORMED | 변형된 노드 좌표 | `deformed` (기본값) |
| NODE_DISPLACEMENT | 노드 변위 | `displacement` |
| INITIAL_VELOCITY | 초기 속도 | `velocity` |
| INITIAL_STRESS_SOLID | 솔리드 초기 응력 | `stress` |
| ELEMENT_STRESS_CSV | 요소 응력 CSV | `stress_csv` |

### 다양한 내보내기 옵션

```bash
# 노드 변위로 내보내기
kood3plot_cli --mode export --export-format displacement results/d3plot -o disp.k

# 응력 데이터 CSV로 내보내기
kood3plot_cli --mode export --export-format stress_csv results/d3plot -o stress.csv

# 특정 state 범위 내보내기 (0~100번 state, 10 step씩)
kood3plot_cli --mode export --first 0 --last 100 --step 10 results/d3plot -o states.k

# 모든 state를 개별 파일로 내보내기
kood3plot_cli --mode export --export-all results/d3plot -o state.k
# 출력: state_0001.k, state_0002.k, ...

# 모든 state를 단일 파일로 결합
kood3plot_cli --mode export --export-combined results/d3plot -o combined.k
```

### 출력 파일 예제 (NODE_DEFORMED)

```
*KEYWORD
$# LS-DYNA Keyword File - State Export
$# Generated by KooD3plot
$# Time: 0.0100000 sec
$
*NODE
$#   nid               x               y               z
       1       12.345678        5.678901        3.456789
       2       15.678901        8.901234        6.789012
...
*END
```

---

## 실전 활용 예제

### 사례 1: 충돌 시뮬레이션 분석

```bash
# 1. 전체 데이터에서 최대 응력 부위 찾기
kood3plot_cli --mode query -q von_mises --min 500 crash.d3plot -o high_stress.csv

# 2. 중심 단면에서 응력 분포 시각화
kood3plot_cli --mode autosection --animate --fringe von_mises \
  crash.d3plot -o crash_sections.mp4

# 3. 시간에 따른 변위 추출
kood3plot_cli --mode query -q displacement --first 0 --last -1 --step 5 \
  crash.d3plot -o displacement_history.csv
```

### 사례 2: 설계 변경안 비교

```bash
# 3가지 설계안을 병렬로 렌더링하고 비교
kood3plot_cli --mode multirun \
  --run-config design_baseline.json \
  --run-config design_A.json \
  --run-config design_B.json \
  --threads 3 \
  --comparison-output design_comparison/ \
  baseline.d3plot

# 결과를 CSV로 확인
cat design_comparison/results.csv
```

### 사례 3: 보고서용 이미지 생성

```bash
# 여러 각도의 고품질 이미지 생성
for view in top bottom left right front back iso; do
  kood3plot_cli --mode render --view $view --fringe von_mises \
    results.d3plot -o report_${view}.png
done
```

## 문제 해결

### 1. "LSPrePost not found" 오류

```bash
# LSPrePost 경로 확인
ls -la installed/lsprepost/

# 경로 직접 지정
kood3plot_cli --mode render --lsprepost-path installed/lsprepost/lspp412_mesa \
  results/d3plot -o output.png
```

### 2. "Cannot open d3plot file" 오류

```bash
# 파일 존재 확인
ls -la results/d3plot

# 절대 경로로 시도
kood3plot_cli --mode query /full/path/to/results/d3plot -o output.csv
```

### 3. 라이브러리 로딩 오류

```bash
# LD_LIBRARY_PATH 설정
export LD_LIBRARY_PATH=installed/lib:$LD_LIBRARY_PATH
export LD_LIBRARY_PATH=installed/lsprepost/lib:$LD_LIBRARY_PATH
```

## 성능 최적화

### Multi-run 모드 스레드 수 조정

```bash
# CPU 코어 수 확인
nproc

# 최적 스레드 수는 보통 CPU 코어 수와 동일
kood3plot_cli --mode multirun --threads $(nproc) ...
```

### 배치 처리 시 메모리 관리

대용량 d3plot 파일 처리 시:
- 불필요한 state는 `--first`, `--last`, `--step`으로 제한
- Multi-run 시 스레드 수를 줄여 메모리 사용량 감소

## 참고 자료

- **전체 옵션 확인:** `kood3plot_cli --help`
- **예제 프로그램:** `installed/bin/examples/v4_render/`
- **추가 문서:** `USAGE.md`, `README.md`

## 버전 정보

- **KooD3plot CLI Version:** 3.0.0 (2025-11-22)
- **KooD3plot Library Version:** 4.0
- **V3 Query System:** ✓ Fluent API 쿼리
- **V4 Render System:** ✓ LSPrePost 통합
- **Multi-run 병렬 처리:** ✓ 지원
- **자동 단면 생성:** ✓ 지원
- **Export System:** ✓ LS-DYNA .k 파일 내보내기
- **출력 포맷:** CSV, JSON, HDF5
