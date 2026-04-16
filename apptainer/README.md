# KooD3plotReader — Apptainer 배포 가이드

LS-DYNA d3plot 후처리 전체 파이프라인을 Apptainer(Singularity) 이미지 하나로 패키징합니다.
Slurm 계산 노드에서 GPU/X11 없이 바로 job으로 던져서 전각도 낙하 분석, Deep Report,
단면 섹션뷰 렌더까지 전부 생성할 수 있습니다.

---

## 파일 구성

```
apptainer/
├── KooD3plotReader_headless.def    # Slurm 노드용 (GUI 없음, ~345MB)
├── KooD3plotReader_full.def        # 데스크탑/viz 노드용 (GUI 포함, ~500MB)
├── build.sh                        # 빌드 래퍼
├── examples/
│   ├── slurm_post_analyze.sh       # 단일 test_dir Slurm job
│   └── slurm_batch_array.sh        # 배열 job (여러 test_dir 병렬)
└── README.md                       # 이 파일
```

---

## 이미지 빌드

```bash
# 계산 노드용 (headless, GUI 제외)
./apptainer/build.sh headless
# → apptainer/kood3plot_headless.sif (~345MB)

# viz 노드용 (GUI 포함)
./apptainer/build.sh full
# → apptainer/kood3plot_full.sif (~500MB)

# 둘 다
./apptainer/build.sh both
```

빌드 시간: headless ~5분, full ~10분 (소스에서 전체 컴파일).

### SIF 파일 위치

| 단계 | 경로 |
|------|------|
| **빌드 직후** (프로젝트 내) | `<project_root>/apptainer/kood3plot_{headless,full}.sif` |
| **공유 배포 경로 (권장)** | `/opt/containers/kood3plot_{headless,full}.sif` |
| 개인/스크래치 공간 | 임의 (`--bind` 설정에 주의) |

빌드 후 공유 경로로 이동:

```bash
# 관리자 권한으로
sudo mkdir -p /opt/containers
sudo cp apptainer/kood3plot_headless.sif /opt/containers/
sudo cp apptainer/kood3plot_full.sif /opt/containers/

# 또는 NFS/공유 저장소에
cp apptainer/kood3plot_headless.sif /nfs/shared/containers/
```

이후 사용자는 다음 경로 중 하나에서 SIF를 참조:

```bash
# 방법 1: 환경변수 (스크립트에서)
SIF=/opt/containers/kood3plot_headless.sif
apptainer exec --bind /data "$SIF" post_analyze /data/test_001

# 방법 2: 절대 경로 직접
apptainer exec --bind /data /opt/containers/kood3plot_headless.sif post_analyze /data/test_001

# 방법 3: 모듈 시스템 (environment module / lmod)
module load kood3plot/2.3.1
post_analyze /data/test_001    # alias로 감싸진 상태
```

---

## Headless 이미지에서 지원되는 기능

Headless에서 **koo_viewer만 제외한 모든 것**이 돌아갑니다.
계산 노드처럼 GPU/X11이 없는 환경에서도 섹션뷰 렌더까지 완전히 동작합니다.

| 기능 | Headless | Full |
|------|:-------:|:----:|
| `unified_analyzer` (C++ 분석 엔진) | ✅ | ✅ |
| `koo_deep_report` (단일 시뮬 HTML) | ✅ | ✅ |
| `koo_sphere_report` (전각도 리포트) | ✅ | ✅ |
| `post_analyze` (파이프라인 오케스트레이션) | ✅ | ✅ |
| 소프트웨어 섹션뷰 (내장 래스터라이저) | ✅ | ✅ |
| **LSPrePost 섹션뷰 (drawcut+projectview)** | ✅ Xvfb 내장 | ✅ |
| 타겟 파트 fringe + 주변 파트컬러 | ✅ | ✅ |
| 등각 + clipplane 뷰 (3축) | ✅ | ✅ |
| ffmpeg H264 재압축 (~80% 절감) | ✅ | ✅ |
| `koo_viewer` 인터랙티브 GUI | ❌ | ✅ (X11 필요) |

> LSPrePost 섹션뷰는 컨테이너 안에서 자체 Xvfb virtual display를 띄우기 때문에,
> 노드의 X11/GPU 설치 여부와 무관하게 동작합니다.

---

## 기본 실행

### 1. 전체 파이프라인 한 번에

```bash
apptainer exec --bind /data:/data \
    kood3plot_headless.sif \
    post_analyze /data/drop_test_001 \
    --threads 4 \
    --yield-stress 250 \
    --section-view --section-view-backend lsprepost
```

**자동 실행 순서:**

```
Step 1: unified_analyzer --recursive
        → /data/drop_test_001/analysis_results/Run_*/
           ├── analysis_result.json
           ├── stress/*.csv
           ├── strain/*.csv
           └── motion/*.csv

Step 2: koo_deep_report batch
        → /data/drop_test_001/deep_reports/Run_*/
           ├── result.json
           ├── report.html          # 단일 낙하 deep HTML
           └── renders/*.mp4        # LSPrePost 섹션뷰 MP4들

Step 3: koo_sphere_report
        → /data/drop_test_001/report.html   # 전각도 sphere 리포트
        → /data/drop_test_001/sphere_report.json
```

### 2. 개별 도구 호출

```bash
# 단일 d3plot 분석만
apptainer exec --bind /data:/data kood3plot_headless.sif \
    unified_analyzer --config config.yaml

# 단일 시뮬 deep 리포트만
apptainer exec --bind /data:/data kood3plot_headless.sif \
    koo_deep_report /data/sim/d3plot --output /data/sim/report

# 이미 추출된 analysis_results/ 로 sphere 리포트만
apptainer exec --bind /data:/data kood3plot_headless.sif \
    koo_sphere_report --test-dir /data/drop_test_001 \
                      --yield-stress 250
```

### 3. 이미지 정보 확인

```bash
apptainer run kood3plot_headless.sif
# VERSION 정보 + 사용법 출력
```

---

## Slurm Job 제출

### 패턴 A: 단일 test_dir

`apptainer/examples/slurm_post_analyze.sh`

```bash
sbatch apptainer/examples/slurm_post_analyze.sh /data/drop_test_001

# 환경변수로 옵션 전달
YIELD=250 \
EXTRA="--section-view --section-view-backend lsprepost --section-view-per-part" \
SIF=/opt/containers/kood3plot_headless.sif \
    sbatch apptainer/examples/slurm_post_analyze.sh /data/drop_test_001
```

### 패턴 B: 배열 Job (여러 test_dir 병렬)

`apptainer/examples/slurm_batch_array.sh`

```bash
# 1) 처리할 test_dir 목록 작성
ls -d /data/tests/drop_test_* > test_dirs.txt

# 2) 배열 job 제출 — 동시 4개씩, 총 20개
sbatch --array=0-19%4 apptainer/examples/slurm_batch_array.sh
```

### 권장 리소스 설정

| 데이터 규모 | CPU | RAM | 시간 |
|-------------|-----|-----|------|
| < 100 states, < 1M 요소 | 4 | 8 GB | 30분 |
| 100–500 states, 1–5M 요소 | 4 | 16 GB | 1–2시간 |
| 500+ states, 5M+ 요소 | 8 | 32 GB | 2–4시간 |
| 전각도 200방향 DOE | 4 (배열×10) | 16 GB | ~4시간 |

> 병렬은 Slurm 배열로 주는 것이 안전합니다. `--sv-threads 4` 같은
> 단일 job 내 병렬은 메모리를 여러 배 쓰기 때문에 노드 OOM 위험이 있습니다.

---

## 주요 CLI 옵션

### `post_analyze <test_dir> [options]`

| 옵션 | 설명 |
|------|------|
| `--threads N` | 각 단계의 스레드 수 |
| `--yield-stress MPa` | 안전계수 계산용 항복응력 |
| `--deep-only` | Step 2만 실행 (unified_analyzer 스킵) |
| `--sphere-only` | Step 1+3만 실행 (deep 스킵) |
| `--force` | 기존 결과 무시하고 재계산 |
| `--section-view` | 단면 섹션뷰 활성화 |
| `--section-view-backend {lsprepost,software}` | 렌더 백엔드 (기본: `lsprepost`) |
| `--section-view-per-part` | 파트별 개별 섹션뷰 생성 |
| `--section-view-axes x y z` | 렌더할 축 선택 |
| `--section-view-fields von_mises strain` | 필드 선택 |

### 필요한 입력 디렉토리 구조

```
<test_dir>/
├── runner_config.json         # KooChainRun이 생성한 DOE 정의
├── common_analysis.yaml       # unified_analyzer 설정
└── output/                    # LS-DYNA 실행 결과
    ├── Run_F_top/
    │   ├── DropSet.json
    │   └── d3plot, d3plot01, ...
    ├── Run_E_left_top/
    └── ...
```

---

## Apptainer 내부 구조

```
/opt/kood3plot/
├── bin/
│   ├── unified_analyzer       # C++ 분석 엔진
│   ├── koo_deep_report        # Python wrapper
│   ├── koo_sphere_report      # Python wrapper
│   ├── post_analyze           # Bash 오케스트레이션
│   └── koo_viewer             # GUI 뷰어 (full 이미지만)
├── python/
│   ├── koo_deep_report/       # Python 패키지 소스
│   └── koo_sphere_report/
├── lsprepost/                 # LSPrePost 번들 (자동 감지)
└── VERSION                    # 빌드 정보
```

**환경변수 (자동 설정):**

```bash
PATH=/opt/kood3plot/bin:$PATH
PYTHONPATH=/opt/kood3plot/python/koo_deep_report:...
KOOD3PLOT_HOME=/opt/kood3plot
LSPREPOST_PATH=/opt/kood3plot/lsprepost
OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK:-4}
```

---

## 바인드 마운트 가이드

```bash
# 기본 (데이터만)
apptainer exec --bind /data:/data kood3plot_headless.sif post_analyze /data/...

# 스크래치 디렉토리도 추가
apptainer exec --bind /data:/data,/scratch:/scratch \
    kood3plot_headless.sif post_analyze /data/...

# GUI 필요 시 (full 이미지, viz 노드)
apptainer exec --nv --bind /tmp/.X11-unix,/data:/data \
    kood3plot_full.sif koo_viewer sphere /data/drop_test_001
```

---

## 배포 가이드 (다른 프로젝트에서 사용)

### 1. SIF 파일을 공유 저장소에 배포

```bash
# 빌드한 이미지 → 공유 경로로 복사
cp apptainer/kood3plot_headless.sif /opt/containers/
```

### 2. Module 파일 (선택)

`/opt/modulefiles/kood3plot/2.3.1.lua`:

```lua
whatis("KooD3plotReader Post-Processing")
local sif = "/opt/containers/kood3plot_headless.sif"
set_alias("unified_analyzer",  "apptainer exec --bind /data " .. sif .. " unified_analyzer")
set_alias("koo_deep_report",   "apptainer exec --bind /data " .. sif .. " koo_deep_report")
set_alias("koo_sphere_report", "apptainer exec --bind /data " .. sif .. " koo_sphere_report")
set_alias("post_analyze",      "apptainer exec --bind /data " .. sif .. " post_analyze")
```

```bash
module load kood3plot/2.3.1
post_analyze /data/drop_test_001  # apptainer 없이 직접 호출한 것처럼 보임
```

---

## 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| `Failed to create GLFW window` | Full 이미지의 koo_viewer를 X11 없는 노드에서 실행 | Headless 이미지 사용 또는 viz 노드에서 실행 |
| `No space left on device` | `/tmp` 공간 부족 (LSPrePost 임시 파일) | `APPTAINER_TMPDIR=/scratch/tmp` 설정 |
| `binding /data failed` | 노드에 `/data` 없음 | 실제 경로로 `--bind <host>:<container>` |
| LSPrePost 렌더 빈 영상 | Xvfb 충돌 (드묾) | `post_analyze --section-view-backend software` 로 전환 |
| `unified_analyzer: killed` | OOM | Slurm `--mem` 늘리거나 `--threads` 줄이기 |

---

## 참고

- **빌드 스크립트**: `scripts/build_module.sh` — SIF 없이 네이티브 설치도 가능
- **사용 매뉴얼 전체**: 프로젝트 루트의 `STATUS.md`
- **KooChainRun 연계**: KooChainRun이 `output/Run_*/d3plot`을 생성하면,
  여기서 곧바로 `post_analyze`로 연결됩니다
