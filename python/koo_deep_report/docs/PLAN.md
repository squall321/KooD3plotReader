# single_analyzer 설계 계획

> **버전:** v1.0 (2026-03-04 — unified_analyzer JSON/CSV 포맷 검증 완료)
> **목적:** 단일 LS-DYNA 시뮬레이션 결과를 깊게 분석하여 HTML 보고서로 출력하는 독립 모듈

---

## 0. 설계 근거

### 실제 파일 현황

| 디렉토리 | 시뮬 유형 | 출력 파일 |
|---------|---------|---------|
| `battery_study/` | 배터리 압축·충격 | d3plot + glstat + binout |
| `cms_study/` | CMS 진동 | d3plot + glstat + binout |
| `warpage_study/` | 적층판 뒤틀림 | d3plot + glstat + binout |
| `ball_drop_test/` | 공 낙하 | d3plot + glstat + binout |
| `Tests/` (전각도) | 낙하 충격 | d3plot + glstat (binout 일부) |

**표준 세트:** d3plot + glstat + binout. glstat은 거의 항상 있음.

### 설계 원칙
- **Graceful Degradation** — 있는 파일로만 분석. 없으면 "데이터 없음" 표시.
- **unified_analyzer 위임** — d3plot 분석·렌더링은 C++ unified_analyzer에 위임. Python은 YAML 생성 + 결과 파싱만.
- **비교는 동일 모델 전제** — 부품 ID 동일 → 직접 매칭.

---

## 1. unified_analyzer 출력 포맷 (실측)

### analysis_result.json 스키마

```json
{
  "metadata": {
    "d3plot_path": "/data/.../d3plot",
    "analysis_date": "2026-03-04T07:51:27Z",
    "kood3plot_version": "1.0.0",
    "num_states": 99,
    "start_time": 0.0,
    "end_time": 2573.7,
    "analyzed_parts": [1, 2, 3]
  },
  "stress_history": [
    {
      "part_id": 1, "part_name": "Part_1",
      "quantity": "von_mises", "unit": "MPa",
      "num_points": 99,
      "global_max": 280.5, "global_min": 0.0, "time_of_max": 0.0025,
      "data": [
        {"time": 0.0, "max": 0.0, "min": 0.0, "avg": 0.0,
         "max_element_id": 1001, "min_element_id": 0}
      ]
    }
  ],
  "strain_history": [ /* stress_history와 동일 구조, quantity="eff_plastic_strain" */ ],
  "acceleration_history": [ /* d3plot에 nodal acc 있을 때만 */ ],
  "surface_analysis": [ /* surface_stress/surface_strain 잡 있을 때 */ ]
}
```

### Motion CSV (per-part)

경로: `<output_dir>/motion/part_<id>_motion.csv`

```
Time, Avg_Disp_X, Avg_Disp_Y, Avg_Disp_Z, Avg_Disp_Mag,
Avg_Vel_X, Avg_Vel_Y, Avg_Vel_Z, Avg_Vel_Mag,
Avg_Acc_X, Avg_Acc_Y, Avg_Acc_Z, Avg_Acc_Mag,
Max_Disp_Mag, Max_Disp_Node_ID
```

→ **JSON에는 응력·변형률만. 변위·속도는 CSV 전용.**
→ `d3plot_reader.py`는 `json: true, csv: true` 모두 활성화해야 함.

### analysis_jobs 타입별 출력

| `type` | JSON 키 | CSV |
|--------|---------|-----|
| `von_mises` | `stress_history[]` | — |
| `eff_plastic_strain` | `strain_history[]` | — |
| `part_motion` | (acceleration_history, d3plot acc 있을 때) | `motion/part_N_motion.csv` |
| `surface_stress` | `surface_analysis[]` | — |

---

## 2. 핵심 제약사항

### 2-1. Normal Termination 판단

```
Priority 1: glstat 마지막 50줄 — termination 키워드 검색
Priority 2: d3hsp "Normal termination" 검색 (보조)
Priority 3: 판단 불가 → d3plot 있으면 unknown으로 계속 진행
```

```python
# ★ 주의: replace(' ','') 후에는 \s+ 사용 불가
tail_nospace = tail.replace(' ', '').lower()
if 'normaltermination' in tail_nospace:
    return True, "glstat"
if 'errortermination' in tail_nospace:
    return False, "glstat"
```

### 2-2. binout 처리

```
1. lsda.py 존재 확인 (LSTC/Ansys 제공)
2. 있으면 → lsda.py 사용 (T3 티어)
3. 없으면 → 스킵, glstat으로 에너지 데이터 대체
```

> `ls-dyna_database.txt` = d3plot/d3thdt 바이너리 포맷 스펙 (binout은 별도 LSDA 포맷).
> glstat/matsum/rcforc/rwforc는 ASCII → 직접 파서 작성 가능.

### 2-3. 렌더링

**Python이 렌더 로직을 재구현하지 않음.** C++에 완전한 구현 존재:
- `LSPrePostRenderer` — .cfile 생성 + LSPrePost 실행
- `GeometryAnalyzer` — bbox 계산, 단면 위치 자동 계산
- `UnifiedAnalyzerRender.cpp` — render_jobs 처리

→ `job_builder.py`가 render YAML 생성 → analysis_jobs와 **동일한 YAML**에 포함 → `unified_analyzer` 한 번 실행으로 분석 + 렌더 동시 처리.

```yaml
# d3plot_reader.py가 생성하는 통합 YAML
analysis_jobs:
  - {type: von_mises, parts: [], ...}
  - {type: eff_plastic_strain, parts: [], ...}
  - {type: part_motion, parts: [], ...}
render_jobs:                             # render 활성 시 추가
  - name: "section_z_center"
    type: section_view
    fringe: von_mises
    section: {axis: z, position: center}
    states: all
    output: {format: mp4, fps: 30}
  - name: "final_snapshot"
    type: section_view
    fringe: von_mises
    section: {axis: z, position: center}
    states: [-1]
    output: {format: png}
```

**참조:**
- `examples/config_examples/09_full_workflow.yaml`
- `src/analysis/UnifiedAnalyzerRender.cpp`
- `include/kood3plot/render/LSPrePostRenderer.h`

---

## 3. 파일 가용성 티어

| Tier | 조건 | 분석 가능 범위 |
|------|------|-------------|
| **T0** | glstat = Error termination | 스킵 |
| **T1** | d3plot만 | 응력·변형률·변위·가속도 |
| **T2** | + glstat | + 에너지 균형, 질량 이력 |
| **T3** | + binout (lsda.py) | + 접촉력·슬라이딩 에너지 |
| **T4** | + rcforc/rwforc/matsum | + 단면력·충격력·재료 에너지 |

리포트 헤더에 "분석 Tier: T2 (d3plot + glstat)" 명시.

---

## 4. 모듈 구조

```
python/single_analyzer/
├── single_analyzer/
│   ├── __init__.py
│   ├── __main__.py             # CLI 진입점
│   │
│   ├── core/
│   │   ├── sim_detector.py     # 파일 탐지·종료 판단·Tier 결정
│   │   ├── d3plot_reader.py    # unified_analyzer YAML 생성 + subprocess + JSON/CSV 파싱
│   │   ├── glstat_reader.py    # glstat ASCII 파서 (에너지·질량 이력)
│   │   ├── aux_reader.py       # rcforc, rwforc, matsum ASCII 파서 (Phase 1)
│   │   └── binout_reader.py    # lsda.py 래퍼 (없으면 None 반환, Phase 1)
│   │
│   ├── render/
│   │   └── job_builder.py      # 분석 결과 → render_jobs YAML 생성
│   │                           # (unified_analyzer에 위임, LSPrePost 직접 호출 없음)
│   │
│   ├── report/
│   │   ├── models.py           # SimInfo, D3plotResult, GlstatData, SingleResult
│   │   ├── html_report.py      # 단일 케이스 HTML
│   │   ├── batch_report.py     # 배치 요약 HTML (Phase 2)
│   │   └── compare_report.py   # 비교 HTML (Phase 3)
│   │
│   └── config/
│       └── default.yaml
│
├── docs/
│   ├── PLAN.md
│   └── USAGE.md
└── pyproject.toml
```

---

## 5. YAML 설정

```yaml
version: "1.0"

input:
  d3plot: ""                  # 필수: d3plot 파일 또는 시뮬 디렉토리
  keyword: auto               # .k/.dyn/.key 자동 탐색 (부품명용)

output:
  directory: "./single_report"
  html: "report.html"
  json: "result.json"         # compare 입력용

material:
  yield_stress: 0.0           # MPa (0=키워드 자동 파싱 시도)

analysis:
  parts:
    mode: all                 # all | pattern | list
    pattern: "*"
    list: []
    exclude: []

  quantities:
    von_mises: true
    eff_plastic_strain: true
    displacement: true
    velocity: true
    acceleration: true

render:
  enabled: true               # 기본 활성 (--no-render 로 끄기)
  lsprepost_path: auto
  per_part_render: false      # 부품별 단면 렌더 (많이 걸림)

  auto_render:                # 기본 생성 잡 (render_jobs로 변환)
    section_z_center: true    # Z축 center 단면 애니메이션
    final_snapshot: true      # 최종 state 스냅샷 (PNG)

report:
  lang: ko
  title: auto
  embed_renders: false        # false=링크, true=base64
```

---

## 6. HTML 리포트 탭

데이터 없는 탭은 숨김:

| 탭 | 이름 | 데이터 소스 | 표시 조건 |
|----|------|-----------|---------|
| 0 | **Overview** | metadata + 요약 | 항상 |
| 1 | **응력·변형률** | stress_history, strain_history (JSON) | T1+ |
| 2 | **운동** | part_N_motion.csv | T1+ |
| 3 | **부품 Deep Dive** | 모든 JSON+CSV, 부품 선택 | T1+ |
| 4 | **에너지** | glstat | T2+ |
| 5 | **접촉·단면력** | rcforc/rwforc/sleout | T4+ |
| 6 | **렌더 갤러리** | renders/ 폴더 | 렌더 완료 시 |
| 7 | **시스템 정보** | 파일 목록, Tier, 실행 로그 | 항상 |

### 탭별 내용 정의

**Tab 0 — Overview**
- KPI 카드: 피크 응력, 피크 변형률, 피크 가속도, 에너지 비율
- 분석 Tier 배지, 정상 종료 여부
- 부품 응력 순위 Top 5 (인라인 막대)

**Tab 1 — 응력·변형률**
- 부품별 global_max 순위 막대 차트 (응력 / 변형률)
- 선택 부품의 max/avg 시계열 (Plotly)
- 소스: `stress_history[]`, `strain_history[]` (JSON)

**Tab 2 — 운동**
- 부품별 Max_Disp_Mag 순위 막대 차트
- 선택 부품의 Avg_Disp_Mag, Avg_Vel_Mag 시계열
- 소스: `motion/part_N_motion.csv`

**Tab 3 — 부품 Deep Dive**
- 부품 선택기 (드롭다운)
- 선택 부품의 **모든 물리량 통합**: 응력 + 변형률 + 변위 + 속도 + 가속도 시계열 한 화면
- Safety Factor (yield_stress 지정 시)
- 피크 Element ID, 피크 Node ID 표시
- 이 탭만으로 해당 부품의 거동 전체를 파악 가능하게

**Tab 4 — 에너지 (glstat)**
- 전체 에너지 / 운동 에너지 / 내부 에너지 / 시간 이력 그래프
- 에너지 비율 (internal/total) — 1.0에서 크게 벗어나면 경고
- 질량 이력 (질량 추가 있으면 경고)
- 소스: `glstat_reader.py`

**Tab 5 — 접촉·단면력 (rcforc 등)**
- 인터페이스별 접촉력 시계열
- 소스: `aux_reader.py` (Phase 1)

**Tab 6 — 렌더 갤러리**
- renders/ 폴더의 mp4/png 파일 목록
- mp4: video 태그로 인라인 재생
- png: lightbox 갤러리

**Tab 7 — 시스템 정보**
- 분석 파일 목록 (존재/부재 표시)
- unified_analyzer 버전, 실행 시간
- Tier 결정 근거

---

## 7. CLI

```bash
# 단일 모드 (렌더 기본 활성)
single_analyzer /path/to/sim_dir
single_analyzer /path/to/d3plot

# 옵션
single_analyzer /path/to/sim_dir \
  --config my.yaml \
  --yield-stress 275 \
  --parts 1 5 15 \
  --part-pattern "BATT*" \
  --no-render \
  --label "Case A" \
  --output ./my_report

# 배치 모드 (Phase 2)
single_analyzer batch /data/battery_study \
  --output ./reports \
  --skip-existing \
  --no-render \
  --yield-stress 250 \
  --threads 4

# 비교 모드 (동일 모델, Phase 3)
single_analyzer compare \
  case_base/result.json \
  case_rib/result.json \
  case_rib_fill/result.json \
  --output compare.html \
  --labels "Base,+Rib,+Rib+Fill" \
  --ref 0
```

---

## 8. sim_detector.py

```python
@dataclass
class SimInfo:
    path: Path
    d3plot: Path | None
    glstat: Path | None
    binout: Path | None
    matsum: Path | None
    rcforc: Path | None
    rwforc: Path | None
    keyword: Path | None

    normal_termination: bool | None   # None = 판단 불가 (계속 진행)
    termination_source: str           # "glstat" | "d3hsp" | "unknown"
    tier: int                         # 0~4

    @property
    def can_analyze(self) -> bool:
        # T0(명확한 오류종료)만 스킵. unknown이면 계속.
        return self.d3plot is not None and self.normal_termination is not False

    @property
    def can_analyze_energy(self) -> bool:
        return self.glstat is not None


def check_termination(sim_dir: Path) -> tuple[bool | None, str]:
    glstat = sim_dir / "glstat"
    if glstat.exists():
        tail = _read_tail(glstat, n=50)
        tail_ns = tail.replace(' ', '').lower()
        if 'normaltermination' in tail_ns:
            return True, "glstat"
        if 'errortermination' in tail_ns:
            return False, "glstat"

    d3hsp = sim_dir / "d3hsp"
    if d3hsp.exists():
        content = d3hsp.read_text(errors='ignore')
        if "Normal termination" in content:
            return True, "d3hsp"
        if "Error termination" in content:
            return False, "d3hsp"

    return None, "unknown"
```

---

## 9. d3plot_reader.py

```python
def run_analysis(sim_info: SimInfo, config: Config) -> D3plotResult:
    """
    1. analysis_jobs + render_jobs 통합 YAML 생성
    2. unified_analyzer subprocess 실행 (한 번)
    3. analysis_result.json 파싱 → stress/strain/acc 데이터
    4. motion/part_N_motion.csv 파싱 → displacement/velocity 데이터
    5. renders/ 폴더 스캔 → 렌더 파일 목록
    """
    yaml_path = build_analysis_yaml(sim_info, config)
    run_unified_analyzer(yaml_path)
    return parse_outputs(config.output_dir)


def build_analysis_yaml(sim_info: SimInfo, config: Config) -> Path:
    """
    analysis_jobs: von_mises + eff_plastic_strain + part_motion (항상)
    render_jobs: job_builder.py가 생성 (config.render.enabled 시)
    """


@dataclass
class D3plotResult:
    # JSON에서
    metadata: dict                   # num_states, start/end_time, analyzed_parts
    stress: list[PartTimeSeries]     # stress_history[]
    strain: list[PartTimeSeries]     # strain_history[]
    acceleration: list[PartTimeSeries]  # acceleration_history[] (있을 때)
    # CSV에서
    motion: dict[int, MotionData]    # part_id → motion CSV 데이터
    # 렌더
    render_files: list[Path]         # renders/ 폴더 파일 목록


@dataclass
class PartTimeSeries:
    part_id: int
    part_name: str
    quantity: str
    unit: str
    global_max: float
    global_min: float
    time_of_max: float
    data: list[dict]  # [{time, max, min, avg, max_element_id}]


@dataclass
class MotionData:
    part_id: int
    t: list[float]
    disp_mag: list[float]
    vel_mag: list[float]
    acc_mag: list[float]
    max_disp_mag: list[float]
    max_disp_node: list[int]
```

---

## 10. glstat_reader.py

```python
@dataclass
class GlstatData:
    normal_termination: bool | None
    t: list[float]
    total_energy: list[float]
    kinetic_energy: list[float]
    internal_energy: list[float]
    hourglass_energy: list[float]
    mass: list[float]
    energy_ratio: list[float]    # internal/total (1.0 기준, ±5% 경고)


def parse_glstat(path: Path) -> GlstatData | None:
    """
    glstat은 수백 KB ASCII. 전체 읽고 블록 파싱.
    블록 패턴: "gt = <time>  time step = ..."
    각 블록에서 kinetic/internal/total energy, mass 추출.
    마지막 50줄에서 termination 판단 (replace spaces, lowercase).
    실패해도 None 반환, 오류 없음.
    """
```

---

## 11. 출력 결과 JSON (compare 입력용)

```json
{
  "schema": "single_analyzer/1.0",
  "label": "Base Case",
  "tier": 2,
  "metadata": {
    "d3plot_path": "/path/to/d3plot",
    "project_name": "battery_study/case_01",
    "normal_termination": true,
    "termination_source": "glstat",
    "num_states": 99, "t_end": 2573.7,
    "num_parts": 3
  },
  "summary": {
    "peak_stress_global": 280.5,
    "peak_stress_part_id": 1,
    "peak_strain_global": 0.018,
    "peak_disp_global": 85.2,
    "energy_ratio_min": 0.997
  },
  "parts": {
    "1": {
      "name": "Part_1",
      "peak_stress": 280.5, "time_of_peak_stress": 0.0025,
      "peak_strain": 0.018,
      "peak_disp_mag": 85.2,
      "peak_acc_mag": 5200.0,
      "safety_factor": 0.98
    }
  },
  "glstat": {
    "t": [...], "total_energy": [...], "kinetic_energy": [...],
    "internal_energy": [...], "energy_ratio": [...]
  }
}
```

---

## 12. 기존 모듈 재활용

| 기존 | 재활용 방식 |
|------|-----------|
| `unified_analyzer` 바이너리 | analysis + render YAML → subprocess 한 번 실행 |
| `koo_report` CSS 변수 | `:root` 변수 복사 (동일 다크 테마) |
| `koo_report` JS 유틸 | `valueToColor()`, Plotly 패턴 복사 |
| `koo_report/models.py` | `TimeSeriesData` 등 필요한 것만 복사 |

**독립성 유지:** koo_report import 없음.

---

## 13. 출력 구조

```
single_report/
├── report.html              # 메인 (자기완결형)
├── result.json              # compare 입력용
├── analysis_result.json     # unified_analyzer 원본 (보관)
├── motion/                  # unified_analyzer 생성 CSV
│   ├── part_1_motion.csv
│   └── ...
├── analysis.log
└── renders/
    ├── section_z_center.mp4
    └── final_snapshot.png
```

---

## 14. 구현 Phase

### Phase 0 — MVP (렌더 포함)

**목표:** `single_analyzer /data/battery_study/case_01` → `report.html` (탭 0~4, 6, 7)

```
[ ] sim_detector.py — 종료 판단 + 파일 목록 + Tier 결정
[ ] glstat_reader.py — 에너지 이력 + 종료 판단
[ ] render/job_builder.py — section_z_center + final_snapshot render_jobs 생성
[ ] d3plot_reader.py — 통합 YAML 생성 + unified_analyzer 실행 + JSON/CSV 파싱
[ ] report/models.py — SimInfo, D3plotResult, GlstatData, SingleResult
[ ] report/html_report.py — 탭 0~4, 6, 7
[ ] __main__.py — 단일 모드 CLI (--no-render, --yield-stress, --output, --label)
[ ] installed/bin/single_analyzer 심볼릭 링크
```

**완료 기준:**
```bash
single_analyzer /data/battery_study/case_06_phase3_wound_tier-1
# → ./single_report/report.html 생성
# → 탭 0~4(glstat 있으면), 6(렌더 있으면), 7 동작
```

### Phase 1 — 보조 파일 (T3~T4)

```
[ ] aux_reader.py — rcforc, rwforc, matsum, sleout ASCII 파서
[ ] binout_reader.py — lsda.py 래퍼
[ ] 탭 5 (접촉·단면력) 추가
```

### Phase 2 — 배치 모드

```
[ ] batch 서브커맨드
[ ] report/batch_report.py
[ ] --threads N (multiprocessing.Pool)
[ ] failed_cases.txt 생성
```

### Phase 3 — 비교 모드

```
[ ] compare 서브커맨드
[ ] report/compare_report.py
    [ ] Tab 0: 요약 비교 테이블 + delta %
    [ ] Tab 1: 부품별 피크 비교 차트
    [ ] Tab 2: 에너지 시계열 오버레이
    [ ] Tab 3: 스냅샷 나란히 비교 (렌더 있을 때)
    [ ] Tab 4: 기준 대비 delta 히트맵 (개선/악화 Top 10)
```

---

## 15. 실행 흐름도

### 단일 모드 (Phase 0)

```
sim_dir
  │
  ├─ sim_detector
  │   ├─ check_termination() → glstat 우선 (공백 제거 후 소문자 매칭)
  │   └─ find_files() → SimInfo (Tier 결정)
  │
  ├─ [T0: Error termination] → 스킵 + 메시지
  │
  ├─ glstat_reader (T2+)
  │   └─ GlstatData (에너지, 질량, 에너지 비율)
  │
  ├─ job_builder (render enabled 시)
  │   └─ render_jobs[] 생성
  │
  ├─ d3plot_reader
  │   ├─ analysis_jobs + render_jobs → 통합 YAML
  │   ├─ unified_analyzer subprocess (한 번)
  │   ├─ analysis_result.json 파싱 → stress/strain/acc
  │   └─ motion/part_N_motion.csv 파싱 → displacement/velocity
  │
  ├─ result.json 저장 (compare 입력용)
  │
  └─ html_report
      └─ report.html (데이터 있는 탭만)
```
