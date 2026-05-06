# Deep Report & Sphere Report 사용 가이드

KooD3plotReader는 LS-DYNA `d3plot` 결과로부터 두 가지 자동 보고서를 생성합니다.

| 도구 | 용도 | 입력 |
|------|------|------|
| **`koo_deep_report`** | **개별 시뮬 1건**의 상세 분석 — 응력/변형률/변위/모션 + 단면뷰 영상 | 단일 d3plot 시뮬 디렉토리 |
| **`koo_sphere_report`** | **다각도 드롭 테스트 N건**의 통합 — 구면 분포, Mollweide 투영, 파트별 통계 | 여러 d3plot 결과를 모은 루트 디렉토리 |

대부분의 사용자는 두 도구를 이렇게 결합합니다:
1. 시뮬 한 건당 `koo_deep_report` 실행 → 단면뷰 영상 + JSON
2. 모든 시뮬을 한 폴더에 모은 뒤 `koo_sphere_report` 실행 → 구면 통합 보고서

---

## 1. 환경 설정

### Apptainer/Singularity (권장 — Slurm/HPC)

```bash
# 빌드 (한 번만)
cd apptainer
./build.sh headless     # 800 MB SIF, GUI 없음

# 실행
apptainer exec --bind /data:/data SmartTwinPostprocessor.sif \
  python3 -m koo_deep_report ...
```

SIF에는 `unified_analyzer` 바이너리, LSPrePost 번들, Python 도구가 모두 포함되어 있어 추가 설치가 필요 없습니다.

### 로컬 Python (개발용)

```bash
# 빌드
cd build && cmake .. -DCMAKE_BUILD_TYPE=Release && make -j unified_analyzer

# 실행
PYTHONPATH=python/koo_deep_report python3 -m koo_deep_report ...
PYTHONPATH=python/koo_sphere_report python3 -m koo_sphere_report ...
```

---

## 2. `koo_deep_report` — 단일 시뮬 분석

### 기본 호출

```bash
python3 -m koo_deep_report /path/to/sim_dir -o /path/to/report
```

`sim_dir` 안에 `d3plot` 또는 `d3plot01` 등이 있어야 합니다. 출력은 `report` 디렉토리에 생성됩니다.

### 표준 옵션

```bash
python3 -m koo_deep_report /path/to/sim_dir \
  -o /path/to/report \
  --section-view \
  --section-view-backend software \
  --section-view-mode section \
  --no-render \
  --ua-threads 8
```

| 옵션 | 의미 |
|------|------|
| `--section-view` | 단면뷰 영상 생성 ON |
| `--section-view-backend {software,lsprepost}` | `software` = 자체 SW 뷰어 (HPC 추천) / `lsprepost` = LSPrePost (Xvfb 필요) |
| `--section-view-mode {section,section_3d,iso_surface}` | `section` = 2D cut / `section_3d` = 3D 반절단 / `iso_surface` = cut 없는 iso 외곽 |
| `--no-render` | 단순 angle render (별도 외곽 스냅샷) 끔 — section view만 만들 때 유용 |
| `--ua-threads N` | unified_analyzer OpenMP 스레드 |
| `--sv-threads N` | section view 동시 렌더 스레드 (기본 2) |
| `--render-threads N` | 외곽 스냅샷 동시 렌더 스레드 |

### Per-part 자동화 (기본 동작)

`--section-view-target-ids` 와 `--section-view-target-patterns` 둘 다 지정하지 않으면 **모든 파트가 자동으로 per-part 단면뷰 대상**이 됩니다. 즉:

```bash
# 자동 per-part: 모델의 N개 파트 모두에 대해 영상 생성
python3 -m koo_deep_report /path/sim -o report --section-view ...
# → renders/section_view_{field}_part_{1..N}_{x,y,z}/section_view.mp4
# → renders/section_view_{field}_{x,y,z}/section_view.mp4 (전체)
```

특정 파트만 보고 싶으면:

```bash
# 파트 ID 지정 → 해당 파트만 target (per-part 자동 OFF)
--section-view-target-ids 2 5 12

# 패턴 매칭 → 매칭된 파트들만 target
--section-view-target-patterns "*Rubber*" "*Frame*"

# 파트 ID 지정한 채로 그래도 per-part 강제 ON
--section-view-target-ids 2 --section-view-per-part

# 모든 파트 입력했지만 per-part 강제 OFF (한 영상에 다같이)
--no-section-view-per-part
```

### 단면뷰 모드별 사용 시점

| 모드 | 적합한 상황 |
|------|-----------|
| **`section`** (2D) | 응력/변형률 컨투어를 섹션 위치에서 정량적으로 확인 — 가장 흔한 모드 |
| **`section_3d`** | 3D 반절단으로 모델 구조를 보면서 컨투어 확인 |
| **`iso_surface`** | 단면 없이 파트 외곽의 컨투어 + BG 반투명 — 표면 응력 분포 |

`iso_surface` 추가 옵션:
```bash
--section-view-mode iso_surface --section-view-background-alpha 0.3
```

### 축 / 필드 / 시리즈 제한

```bash
--section-view-axes z              # Z축만 (기본은 x y z 모두)
--section-view-fields von_mises    # VM만 (기본은 von_mises strain 둘다)
                                   # choices: von_mises eps strain displacement pressure max_shear
```

### 옵션 전체 목록

```bash
python3 -m koo_deep_report --help
```

### 출력 구조

```
output_dir/
├── report.html                ← 메인 HTML (모든 영상 임베드)
├── result.json                ← 요약 JSON
├── analysis_result.json       ← unified_analyzer 원본
├── stress/                    ← VM, principal stress CSV (파트별)
├── strain/                    ← Effective plastic strain CSV
├── motion/                    ← 평균/최대 변위, 속도, 가속도 CSV
├── surface/                   ← (있으면) 표면 응력
└── renders/
    ├── section_view_{field}_{x,y,z}/section_view.mp4    ← 전체 단면
    └── section_view_{field}_part_{i}_{x,y,z}/section_view.mp4  ← 파트별
```

`report.html`을 브라우저에서 열거나 HTTP 서버로 띄워 확인하면 됩니다.

```bash
cd output_dir && python3 -m http.server 8000
# http://localhost:8000/report.html
```

### 처리 시간 / 용량 가이드

(ex01_hex8 minimum model: 976 elements, 152 states, 24 영상 기준)

| 환경 | 시간 | 출력 용량 |
|------|------|-----------|
| 로컬 8 core / 32 GB | ~2-3분 | ~5 MB |
| 서버 128 core / 1.5 TB | ~30초 | ~5 MB |

대형 모델 (2M elements, 100 parts):
- 128 core 서버: **5-10분 / 시뮬**
- 출력: **300-500 MB / 시뮬**

대형 모델은 처음에 작은 subset으로 검증 후 풀 렌더 권장:
```bash
# 1차 검증
--section-view-target-ids 5 12 27 --section-view-axes z --section-view-fields von_mises

# OK면 풀 렌더
# (target IDs 빼면 자동 per-part 풀 모드)
```

### 배치 모드 (다중 시뮬)

```bash
python3 -m koo_deep_report batch /root/dir \
  --threads 8 \
  --skip-existing \
  --section-view --section-view-backend software ...
```

`/root/dir` 아래의 모든 d3plot 시뮬을 자동 탐색해서 각각 보고서를 생성합니다. `--threads N`은 동시에 처리할 시뮬 수입니다 (각 시뮬은 sv-threads 만큼 추가 병렬).

128 core 서버에서: `--threads 8 --sv-threads 8` → 64 core 활용 (sweet spot).

---

## 3. `koo_sphere_report` — 다각도 드롭 통합 보고서

다각도(보통 162방향) 드롭 테스트의 통합 분석을 합니다. 입력은 **이미 deep_report로 분석된 시뮬들의 루트 디렉토리**입니다.

### 기본 호출

```bash
python3 -m koo_sphere_report --test-dir /path/to/test_root -o /path/to/report.html
```

`test_root` 구조 (deep_report 결과들이 모여있어야 함):
```
test_root/
├── analysis_results/              ← 자동 생성되거나 기존
│   ├── 001_angle_phi0_theta30/
│   │   └── result.json (또는 analysis_result.json)
│   ├── 002_angle_phi45_theta60/
│   │   └── ...
│   └── ...
└── (또는 직접 d3plot 시뮬 폴더들이 있어도 됨)
```

### 입력 모드

```bash
# 1) d3plot 모드: 시뮬 결과로부터 새로 분석
python3 -m koo_sphere_report --test-dir /path/to/test_root -o report.html

# 2) JSON 재생성 모드: 기존 report.json만 다시 HTML로
python3 -m koo_sphere_report --from-json /path/to/old_report.json -o new_report.html
```

### 표준 옵션

| 옵션 | 의미 |
|------|------|
| `--test-dir DIR` | 시뮬 결과 루트 (필수, JSON 모드와 배타) |
| `--from-json FILE` | 기존 JSON에서 재생성 (필수, d3plot 모드와 배타) |
| `--output FILE`, `-o FILE` | HTML 출력 경로 (기본: `report.html`) |
| `--json FILE` | JSON 출력 경로 |
| `--format html json terminal` | 출력 형식 선택 (기본: html + terminal) |
| `--terminal-only` | 터미널 출력만 (파일 미생성) |
| `--yield-stress MPa` | 항복 응력 — 안전계수 계산용 |
| `--ts-points N` | 차트당 시간 시리즈 포인트 (0 = auto) |

### 출력 구조

```
report.html              ← 통합 보고서 (Mollweide 분포, 파트별 통계, 시간 시리즈)
report.json              ← 머신 가독 결과 (재생성 가능)
```

HTML 보고서 주요 탭:
- **Sphere View** — Fibonacci 격자 162점에 대한 응력/변형률 분포 (구면 IDW 보간)
- **Mollweide Projection** — 위 분포를 등면적 투영으로 평면화
- **Per-Part Stats** — 파트별 응력/변형률/변위 통계 (모든 각도 통합)
- **Time Series** — 대표 케이스별 시간 시리즈 차트
- **Worst Cases** — 가장 위험한 각도 N개 하이라이트

### 처리 시간

162방향 시뮬 통합 (각 시뮬은 deep_report 사전 처리 가정):
- 통합 분석: ~10-30초
- HTML 생성: ~3-5초
- JSON: 약 5-50 MB (시뮬 수에 따라)

---

## 4. 통합 워크플로우 (162-angle drop test)

```bash
# Step 1: 모든 각도 시뮬 결과를 deep_report로 처리 (배치)
apptainer exec --bind /data:/data SmartTwinPostprocessor.sif \
  python3 -m koo_deep_report batch /data/drop_test/runs \
  -o /data/drop_test/reports \
  --threads 8 --sv-threads 8 \
  --section-view --section-view-backend software \
  --section-view-mode section --skip-existing

# 각 angle별로 reports/{angle}/report.html, result.json 생성됨

# Step 2: 통합 sphere report
apptainer exec --bind /data:/data SmartTwinPostprocessor.sif \
  python3 -m koo_sphere_report \
  --test-dir /data/drop_test/reports \
  -o /data/drop_test/sphere_report.html \
  --json /data/drop_test/sphere_report.json \
  --yield-stress 350

# Step 3: 보고서 확인
firefox /data/drop_test/sphere_report.html  # 또는 HTTP 서버
```

128 core 서버 162-angle 처리 예상 시간:
- Deep reports (162개): 8 시뮬 동시 × 5분 = **약 1.5-2시간**
- Sphere report 통합: **약 10-30초**

---

## 5. 흔한 문제 / FAQ

### Q. `--section-view` 켰는데 영상이 안 만들어져요
- `--section-view-backend lsprepost`인데 Xvfb가 없으면 실패합니다. 헤드리스 환경에선 `--section-view-backend software`를 권장.
- LSPrePost 백엔드는 SIF 안에 번들되어 있고 Xvfb를 자동 띄우니 SIF 안에서는 OK.

### Q. 영상이 깨져 보이거나 메쉬가 이상해요
- d3plot reader 버그가 IT=10 (mass scaling) 데이터셋에서 NND를 잘못 계산하던 적이 있었습니다 (commit `52d0bef`에서 수정). 이전 commit 또는 이전 SIF를 쓰고 있다면 업데이트 필요.
- States 수와 timing이 정상인지 확인:
  ```bash
  unified_analyzer --config test.yaml | grep "States analyzed\|Time range"
  # States analyzed: 152
  # Time range: 0 to 0.015   ← 단조 증가하는 정상값
  ```

### Q. 컬러바에 표시되는 값이 항상 0..max만 나와요
- YAML 설정에서 `global_range: true`이면 모든 frame 통틀어 max를 사용합니다. 더 dynamic한 컨투어를 원하면 `global_range: false`로 바꾸면 frame별 자동 range.

### Q. 대형 모델인데 메모리 부족
- 현재 구현은 모든 state를 메모리에 로드합니다. 2M elements × 150 states면 ~20GB 필요.
- 1.5 TB 메모리 서버에서는 문제없지만, 32 GB 등 작은 시스템에선 부분 axes/fields/parts로 나눠 실행해야 합니다.

### Q. SIF에 새 코드 변경이 반영되었는지 어떻게 확인?
```bash
apptainer exec apptainer/SmartTwinPostprocessor.sif \
  unified_analyzer --version | head -3
# 또는 NND 수정 검증:
# States analyzed = 152가 나오면 (이전 99) 최신 SIF
```

### Q. 영상이 너무 느리게 만들어집니다
- `--sv-threads`를 늘리세요 (기본 2 → CPU core 수의 50%까지).
- 축이나 필드를 줄이세요 (`--section-view-axes z` `--section-view-fields von_mises`).
- supersampling YAML로 직접 1~2로 조절 가능 (낮을수록 빠르고 품질 ↓).

---

## 6. 참고 문서

- 단일 시뮬 deep_report 상세 기획: [`python/koo_deep_report/docs/PLAN.md`](../python/koo_deep_report/docs/PLAN.md)
- 다각도 sphere_report 기획: [`python/koo_sphere_report/REPORT_PLAN.md`](../python/koo_sphere_report/REPORT_PLAN.md)
- 데이터 구조: [`python/koo_sphere_report/DATA_STRUCTURE.md`](../python/koo_sphere_report/DATA_STRUCTURE.md)
- Mollweide / Fibonacci 수학: [`python/koo_sphere_report/docs/fibonacci_mollweide_analysis.md`](../python/koo_sphere_report/docs/fibonacci_mollweide_analysis.md)
- 단면뷰 렌더 export 상세: [`python/koo_sphere_report/docs/RENDER_EXPORT.md`](../python/koo_sphere_report/docs/RENDER_EXPORT.md)
- D3plot reader 기술: [`docs/SingleAnalyzer_TechReport.md`](SingleAnalyzer_TechReport.md)
