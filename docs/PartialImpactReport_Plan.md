# Partial Impact Report — 계획안 v2 (KooImpactReport)

> **전위치 부분 충격(Ball / Cylinder Drop Weight Impact)** 시뮬레이션 결과를
> **"자세(Face) × 충격위치(XY) × 부품"** 3차원 페어 관점에서 동적으로 보여주는
> 단일 파일 HTML 리포트.

- 작성: 2026-05-26 (v2 — pyKooCAE 도메인 분석 반영)
- 대상: LS-DYNA explicit impactor DOE 후처리 (pyKooCAE `drop_weight_impact` 모드)
- 관련: koo_sphere_report (전각도 자세) · koo_deep_report (단일 분석) · koo_d3plot_reader (코어)
- 상위 시스템: pyKooCAE / KooChainRun / KooMeshModifier (자동 모델 생성)

## v1 → v2 주요 변경 (pyKooCAE 분석 결과)
- **다면(multi-face) 충격** 차원 추가 — F1(후면)·F2(전면)·F3~F6 자세별 부분 충격을 통합 분석
- **임팩터 비대칭 형상** 지원 — Cylinder의 front_radius/outer_radius/back_radius 별도 처리
- **3가지 generation_mode** — DampingSpring / OutsideRigidPart / OutsideRigidElement 시각화
- **boundary_distance** + **OffsetDistance** 메타데이터 표시
- **part_center DOE** + **누적 충격(cumulative)** 시나리오 호환
- pyKooCAE `scenario.json` / `step_config` 포맷 정확히 매핑

## v2 → v3 주요 변경 (스마트폰 도메인 + Impact Inspector)

본 보고서는 스마트폰 부분 충격(drop test) 후처리를 **시그니처 도메인**으로 확정한다.
스마트폰은 현실적으로 Front(F2)·Back(F1) 두 면이 압도적 다수의 사용자 손상 케이스를 차지하며,
측면·상단·하단은 단일 면 충격으로 보기 어렵다(낙하 시 모서리·꼭짓점 충격이 더 우세).
따라서 **기본 분석 구성을 Bi-Face(F1+F2)로 축소**하고, 그 대신 페이지 2를
"여러 미니 히트맵"이 아닌 **하나의 큰 Impact Inspector** 컴포넌트로 재설계한다.

- **Bi-Face 기본화**: 기본 분석은 **Front(F2) + Back(F1)** 2면. 6면(F1~F6) 데이터 모델·로더는 그대로 유지되지만
  더 이상 기본값이 아니며, 측면·상하단(F3~F6)은 "스마트폰 외 디바이스용 옵션"으로 격하.
- **Page 2 패러다임 전환 — Impact Inspector**: "부품 × 자세 mini-heatmap small-multiples" 와
  "ALL face compare grid" 는 모두 제거. 대신 **위치 중심(position-centric)** 의 단일 큰 캔버스로,
  배경 = 디바이스 외곽 + 부품 footprint **외곽선만**, 전경 = 충격 위치 점(색 = max 응답),
  **호버 시 모든 부품 외곽선이 그 충격에 대한 자기 응답값으로 fill** 되어 사이드 패널에 부품 순위가 즉시 표시.
  분석가는 첫 5초에 "어디가 위험" + "그 위치가 어느 부품들을 어떤 비율로 위협" 을 동시 파악한다.
- **Cube Net 은퇴**: Page 1에서 6면 펼침도(Cube Net)는 2 face 만 다룰 때 오버킬이라 제거.
  대신 **Bi-Face Split** (좌 Front · 우 Back 두 큰 패널 + 선택적 Δ Map) 으로 교체.
- **샘플 데이터셋 축소**: P0b 기본 샘플 110 runs → **50 runs (F1 25 + F2 25)** 로 단축.
  MVP 일정도 ~10주에서 ~9주로 단축.

> 핵심 인사이트: "면 정보가 많이 나와서 보는게 뭔가 인사이트 있는건지 모르겠어. … 그림은 때린 위치고,
> 나오는건 패키지 응력. 패키지 크기로 외곽라인만 잡아줘도 대충 때린 위치와 실제 응력 스케일이 보인다."
> — 사용자 의도 = **공간 매칭이 정보다**. 그래서 mini-heatmap 12개 대신 footprint outline 1장.

---

## 1. 문제 정의

### 1.1 분석 시나리오
- 디바이스 평면(XY) 상의 **N개의 격자 위치**에서 동일한 임팩터(공 또는 실린더)가
  Z방향으로 부딪힘 → 각 위치마다 1개의 LS-DYNA run.
- 임팩터: 강체(rigid) 또는 변형체. 사양:
  - **Ball**: 직경 D, 질량 m, 초기 속도 v₀ (자유낙하 or 강제 가속)
  - **Cylinder**: 반경 R, 길이 L, 질량 m, 충격 방향, 단부 접촉(편심 가능)
- 디바이스: M개의 부품(PCB, PKG, Motor, Housing 등)으로 구성된 다중부품 모델.

### 1.2 핵심 분석 질문 (Report가 답해야 할 5가지)
| # | 질문 | 시각화 | 위치 |
|---|---|---|---|
| Q1 | 어디를 때렸을 때 디바이스 전체가 가장 위험한가? | XY 글로벌 위험맵 | Page 1 |
| Q2 | 각 부품은 **어느 위치 공격에 취약**한가? | 부품별 XY 히트맵 (small-multiples) | Page 2 |
| Q3 | 한 위치 공격 시 **어느 부품들이 동시에** 영향을 받나? | 위치 → 부품 사이드바 / 링크된 하이라이트 | Page 2 |
| Q4 | (위치, 부품) 쌍의 응답 시간이력은? | 시간이력 envelope + worst-case overlay | Page 3 |
| Q5 | 어떤 위치는 안전한가? 즉 "통과" 영역은? | XY safety map (반전 색상) | Page 1 / 3 |

### 1.3 데이터 차원
- **Impact positions**: 격자 N = nx × ny (예: 10×10 = 100, 또는 적응형 N)
- **Parts**: M (예: 20)
- **Metrics per pair**: Peak G, Peak Stress, Peak Strain, Peak Displacement
- **Time history per pair**: T 시간점 × 4 메트릭
- **메모리 추정** (예: N=100, M=20, T=21):
  - 4D 스칼라 매트릭스 (100 × 20 × 4) = 8 K floats ≈ 64 KB
  - 시계열 (100 × 20 × 21 × 4) = 168 K floats ≈ 1.3 MB
  - 위치 메타 + 부품 메타 = 수 KB
  - 단일 HTML 출력 예상: **2~5 MB** (sphere_report의 1/10 수준)

---

## 2. 입력 데이터 명세

### 2.1 디렉토리 구조 (DOE 결과 표준)
```
Tests/ImpactTest_002_BallD25_XYgrid_10x10/
├── doe_config.json                # DOE 메타데이터
├── impactor_spec.json             # 임팩터 사양
├── device_layout.json             # 디바이스 XY footprint
├── Run_20260520_xxx_pos_x010_y020/
│   ├── d3plot                      # LS-DYNA 결과
│   ├── analysis_result.json        # koo_deep_report 추출 결과
│   └── csv/                        # peak G/stress/strain 시계열
├── Run_..._pos_x010_y040/
└── ...
```

### 2.2 `doe_config.json` 스키마
```json
{
  "doe_type": "xy_grid",            // "xy_grid" | "xy_adaptive" | "xy_random"
  "grid": {
    "x_min": -50.0, "x_max": 50.0, "nx": 10,
    "y_min": -50.0, "y_max": 50.0, "ny": 10,
    "z_impact_height": 5.0          // 충격 직전 임팩터 위치
  },
  "impactor": "ball_D25_m100g_v3ms",
  "device": "PKG_Model_v2",
  "total_positions": 100,
  "units": {"length": "mm", "mass": "g", "velocity": "mm/s"}
}
```

### 2.3 `impactor_spec.json` 스키마
```json
{
  "type": "ball",                   // "ball" | "cylinder"
  "ball":     {"diameter": 25.0, "mass": 100.0, "material": "steel"},
  "cylinder": {"radius": 12.5, "length": 30.0, "mass": 100.0, "axis": "z"},
  "initial_velocity": 3000.0,       // mm/s (또는 자유낙하 높이)
  "drop_height": 458.7,
  "contact_type": "automatic_surface_to_surface"
}
```

### 2.4 `device_layout.json` 스키마 (시각화용 디바이스 외곽)
```json
{
  "bounding_box": {"x_min":-60, "x_max":60, "y_min":-40, "y_max":40},
  "outline_xy": [[-60,-40], [60,-40], [60,40], [-60,40]],   // 디바이스 외곽 폴리곤
  "parts": [
    {
      "id": 1, "name": "PCB\\Main",
      "footprint": [[-30,-20],[30,-20],[30,20],[-30,20]],  // XY 평면 투영
      "z_range": [0.5, 1.5]
    },
    ...
  ]
}
```

### 2.5 각 Run의 `analysis_result.json` (재사용 — koo_deep_report와 동일)
- `parts[part_id].peak_g`, `peak_stress`, `peak_strain`, `peak_disp`
- `parts[part_id].stress_ts = {t: [...], max: [...]}`

---

## 3. 출력 보고서 구조 (단일 파일, 3페이지)

### 디자인 컨셉
- **다크 톤 Bloomberg / 과학논문 하이브리드** (sphere_report dynamic과 동일)
- **단일 HTML 파일**, 외부 의존성 0
- 1280×800 데스크탑 기준, 반응형
- 모노스페이스 숫자, 작은 폰트, 데이터 밀도 최대

### 페이지 흐름
1. **METHOD + OVERVIEW** — 임팩터 사양·DOE·글로벌 위험맵·KPI
2. **TRANSFER MAPS** — 부품별 XY 히트맵 small-multiples (핵심 페이지)
3. **PAIR DYNAMICS + VERDICT** — 위치×부품 매트릭스·시간이력·결론

---

## 4. Page 1 — METHODOLOGY + OVERVIEW

### 4.1 헤더 라인
- 좌측 헤드라인: "XY 부분 충격 — Pair-wise 전수 해석"
- 우측: **WORST CELL** (가장 위험한 격자 셀) 좌표·부품·값

### 4.2 메소드 밴드 (4 패널)

#### Panel A: IMPACTOR SPEC (col-3)
```
TYPE       Ball
Ø          25 mm
mass       100 g
v₀         3.0 m/s
KE         0.45 J
material   Rigid Steel
```
+ 임팩터 3D 미니 캔버스 (회전 또는 정적 와이어프레임)

#### Panel B: DEVICE LAYOUT (col-3)
- 디바이스 XY 평면 투영 SVG (외곽 폴리곤 + 부품 footprint 컬러)
- 격자 점 (impact positions) overlay

#### Panel C: DOE GRID (col-3)
```
TYPE       XY uniform grid
NX × NY    10 × 10
Δx / Δy    11.1 mm / 8.9 mm
N total    100 positions
Coverage   device + margin 10 mm
```
+ 격자 미니맵

#### Panel D: PIPELINE (col-3)
DOE GEN → SOLVE × N → EXTRACT → 2D PROJECT → REPORT
(sphere_report와 동일 스타일의 SVG 다이어그램, 단 Mollweide 대신 "2D heatmap")

### 4.3 KPI 스트립 (8 셀)
- N positions (예: 100)
- M parts (예: 20)
- Pair count (N × M = 2000)
- Worst pair G
- Worst pair stress
- Critical pairs (≥thresh)
- Safe positions (모든 부품이 thresh 이하)
- Worst position score

### 4.4 글로벌 위험맵 (Global Risk Map) — col-7
**XY 히트맵**: 각 셀의 색 = 그 위치 충격 시 디바이스 내 **최대 위험 메트릭**
- 좌측: device 외곽 폴리곤 (라이트 그레이 fill)
- 부품 footprint 점선 overlay
- 격자 셀 색상: viridis-like (낮음 파랑 → 높음 빨강)
- 상위 1% 셀에 **펄스링** 애니메이션 (killer position)
- 컬러바 + 가로축/세로축 mm 눈금
- **호버 시**: 그 위치 X/Y/모든 부품의 응답 작은 패널 표시

### 4.5 글로벌 분포 + 상관매트릭스 — col-5
- 위치별 worst 응답 히스토그램 (30 bin)
- 4×4 Pearson 상관 매트릭스 (G/Stress/Strain/Disp)
- 위치별 worst 응답 분포의 P5/P25/P50/P75/P95 박스플롯 1줄

### 4.6 Top-K Positions 표 (col-12)
| 순위 | 위치 ID | X (mm) | Y (mm) | Max G | Driving Part | Affected Parts (n≥threshold) |
|---|---|---|---|---|---|---|

상위 12개 위치, 행 호버 시 글로벌 위험맵에서 해당 셀 하이라이트 (linked view).

---

## 5. Page 2 — TRANSFER MAPS (보고서의 심장)

### 5.1 헤더
- 타이틀: "어디를 때리면 어느 부품이 깨지는가 — Per-Part Vulnerability Maps"
- 서브: "XY 격자 N 위치 × M 부품 = N·M pair, 부품별 공간 응답 함수"

### 5.2 컨트롤 바
- **메트릭 토글**: Peak G | Peak Stress | Peak Strain | Peak Disp
- **스케일 토글**: linear | log | percentile rank
- **정렬 토글**: severity (max) | anisotropy (CoV) | impact-area (count)
- **검색**: 부품명 필터

### 5.3 **부품별 XY 히트맵 그리드 (Small-multiples)** — 핵심 시각화
- M개 부품을 4×N 그리드로 배치 (반응형)
- 각 타일:
  - 200×140 px SVG
  - 디바이스 외곽 점선
  - **자기 부품 footprint를 흰색 외곽선**으로 강조 (부품이 어디 있는지)
  - **격자 셀 색상**: 그 임팩트 위치에 대한 해당 부품 응답 (Peak G 등)
  - 자기 부품의 **wt-mean 임팩트 위치** (가중 중심) 표시 = ★
  - **최악 임팩트 위치** = ✕ 마커
  - 헤더: 부품 이름 (id) + max 값
  - 푸터: CoV (이방성) + 영향 셀 수
- 각 타일을 클릭 → 페이지 3으로 점프하면서 해당 부품의 시간이력 영역에 자동 스크롤·하이라이트

### 5.4 영향 매트릭스 (Influence Matrix) — col-12 압축
- **행 = 임팩트 위치 (top-20 위험순)**
- **열 = 부품 (정렬 가능)**
- **셀 = 응답값** (heatmap 컬러 인코딩 + 마우스오버 시 정확한 수치)
- **양옆 마진**: 행/열 합계 바 (각 위치의 총 영향 / 각 부품의 누적 피해)
- 양방향 정렬 가능 (Excel pivot 느낌)
- 부품 그룹으로 컬럼 묶음 (PCB / PKG / Housing)

### 5.5 위치 → 부품 다이어그램 (Linked highlighting)
- 디바이스 XY 평면 한 개
- 슬라이더로 위치 ID 선택 (또는 마우스로 격자 셀 클릭)
- 그 위치에서 빨간 점 표시 + 영향받는 부품들 footprint에 강도 비례 그라데이션
- **방사형 막대 차트** 동심원: 각 막대 = 부품, 길이 = 응답 크기
- 한 번의 view로 "이 위치 한 방에 어떤 부품들이 깨지나" 즉시 파악

---

## 6. Page 3 — PAIR DYNAMICS + VERDICT

### 6.1 시간이력 envelope small-multiples
- 상위 12 부품 × worst position 페어
- 각 미니차트:
  - 회색 띠: 모든 N 위치에 대한 P5~P95 응답 영역
  - 흰 선: P50 중앙값
  - 빨강 선: worst position의 worst-case 곡선
  - x축: 0~T ms, y축: 응답값
- 시간 축의 worst-case 곡선이 envelope를 크게 벗어나는 시점 = 극단 임팩트 효과 시작점

### 6.2 다기준 Verdict 매트릭스 — col-7
| Part | Class | Max G | Stress | Strain | Disp | CoV | Influence Area | Failure Mode |
|---|---|---|---|---|---|---|---|---|
| PCB\Main | CRITICAL | 1.45 MG | 5.7 GPa | 0.42% | 65 mm | 0.78 | 23/100 | 방향성 충격 |

새 컬럼 **Influence Area** = 임계치 이상으로 응답하는 위치 수.
- 크면 = 어디를 때려도 영향받음 (전반 약화)
- 작으면 = 특정 위치만 영향 (국소 취약)

### 6.3 위치별 Verdict 카드 — col-5
- 상위 위험 위치 6개를 카드로
- 각 카드: 위치 좌표 + 미니맵(그 위치만 강조) + 영향 부품 리스트 + 결론
- "이 위치를 어떻게 보호할 것인가" 권고

### 6.4 권장 액션 (자동 도출)
1. 가장 위험한 위치 좌표 → **해당 영역에 완충재 / 보강 구조 검토**
2. 다중 부품 영향 위치 → **하중 분산 설계** 권고
3. 단일 부품 취약 → **그 부품 자체의 보강**
4. 외곽 모서리 hot spot → **모서리 곡률·완충 강화**
5. 시뮬레이션 vs 실측 비교 권장 위치 (P50 envelope 벗어남 큰 위치)

---

## 7. 동적 인터랙션 사양

### 7.1 Linked Highlighting (반드시)
- **Page 1 글로벌 위험맵 셀 클릭** → Page 2 모든 부품 히트맵의 해당 셀 동시 점등
- **Page 2 부품 타일 클릭** → Page 3 시간이력 자동 스크롤·하이라이트
- **Page 3 Verdict 행 클릭** → Page 2 해당 부품 타일로 스크롤·점등

### 7.2 Filter / Brush
- 메트릭 토글이 모든 페이지의 시각화에 일괄 적용
- 임계치 슬라이더: critical/warning 라인을 실시간 조정

### 7.3 Replay (선택 기능)
- 격자 위치를 1~N 순회 자동 재생 → 위치별 응답이 글로벌맵에서 펄스
- 부품별 작은 카드에 응답값 실시간 카운트업
- "Watch the impact propagate across the device" 효과

### 7.4 Export
- 현재 뷰 PNG 캡쳐 버튼 (canvas/SVG → blob)
- 표 데이터 CSV 다운로드 (matrix 전체)
- URL hash로 (메트릭, 정렬, 선택 부품) 상태 저장 → 공유

---

## 8. 핵심 알고리즘 / 계산

### 8.1 위치별 worst-across-parts 응답
```python
for pos_i in positions:
    for metric in [g, stress, strain, disp]:
        global_worst[pos_i][metric] = max(parts[p][pos_i][metric] for p in parts)
```

### 8.2 부품별 spatial transfer map
```python
for part_j in parts:
    map_xy[part_j] = reshape(
        [parts[part_j][pos_i][metric] for pos_i in positions],
        (ny, nx)
    )
```

### 8.3 영향 면적 (Influence Area)
```python
threshold = percentile(all_values, 75)
influence_area[part] = count(map_xy[part] > threshold)
```

### 8.4 가중 임팩트 중심 (centroid)
부품별 응답 가중 평균 위치 — 부품의 "약점 위치" 직관적 표현.
```python
weights = map_xy[part]
cx = sum(weights * X_grid) / sum(weights)
cy = sum(weights * Y_grid) / sum(weights)
```

### 8.5 이방성 / 집중도
- **CoV** = σ/μ (sphere_report와 동일)
- **Concentration index** = max / mean (한 점에 집중되는 정도)

### 8.6 Pair severity score
표준화된 종합 점수:
```
score = 0.4 · (G/G_max) + 0.3 · (σ/σ_max) + 0.2 · (ε/ε_max) + 0.1 · (d/d_max)
```
(가중치는 yaml로 조정 가능)

---

## 9. 구현 계획

### 9.1 Python 패키지 신설: `koo_impact_report`
```
python/koo_impact_report/
├── koo_impact_report/
│   ├── __init__.py
│   ├── __main__.py            # CLI
│   ├── models.py              # ImpactReport, ImpactPosition, PairResult
│   ├── loader.py              # doe_config + per-run analysis_result.json 로딩
│   ├── analyzer.py            # influence area, centroid, severity score
│   ├── report/
│   │   ├── html_report.py     # 메인 HTML 생성기
│   │   ├── json_report.py
│   │   └── terminal.py
│   └── geometry/
│       └── device_outline.py  # 디바이스 footprint 추출 (d3plot mesh → XY 폴리곤)
├── tests/
│   ├── test_loader.py
│   ├── test_analyzer.py
│   └── test_geometry.py
├── docs/
│   ├── USAGE.md
│   └── XY_GRID_DOE.md
├── REPORT_PLAN.md             # 이 문서의 요약본
└── pyproject.toml
```

### 9.2 CLI 인터페이스
```bash
koo_impact_report \
    --test-dir Tests/ImpactTest_002 \
    --output report.html \
    --metric peak_stress \
    --threshold-critical 1000 \
    --threshold-warning 300 \
    --yield-stress 800
```

### 9.3 재사용
- **loader 패턴**: koo_sphere_report와 동일
- **html_report 구조**: dynamic 다이제스트 스타일 (다크 톤, 3페이지)
- **deep_report 의존**: 각 run의 analysis_result.json 생성은 기존 koo_deep_report 사용
- **mesh footprint**: KooD3plotReader 코어 라이브러리에서 부품 XY 투영 추출

### 9.4 단계별 마일스톤
| Phase | 산출물 | 기간 |
|---|---|---|
| P0 | DOE 표준 스키마 확정 + 샘플 데이터 생성 | 1주 |
| P1 | 패키지 골격 + loader + 단위 테스트 | 1주 |
| P2 | analyzer (스칼라 매트릭스 + 통계) | 0.5주 |
| P3 | HTML report Page 1 (METHOD + OVERVIEW) | 1주 |
| P4 | Page 2 (TRANSFER MAPS - 핵심) + linked highlighting | 1.5주 |
| P5 | Page 3 (시간이력 envelope + Verdict) | 1주 |
| P6 | 인터랙션 (linked, filter, replay) | 1주 |
| P7 | SIF 통합 + 문서 + 예제 | 0.5주 |
| **합계** | **MVP 완성** | **~7주** |

---

## 10. 시각화 구성 비교: Sphere vs Partial Impact

| 항목 | KooSphereReport | KooImpactReport (신규) |
|---|---|---|
| 데이터 차원 | 1146 방향 (구면) | N × M 격자 (XY 평면) |
| 메인 투영 | Mollweide 등적 | XY heatmap (직접 2D) |
| 부품 표현 | 부품별 mini Mollweide | 부품별 mini XY heatmap (footprint 강조) |
| 위치-부품 결합 | 부품 mini-map의 점 색상 | XY 매트릭스 + linked highlighting |
| 핵심 페이지 | Directional Anatomy | **Transfer Maps** |
| 검증 질문 | "어느 방향에서 안전한가?" | "어디를 때리면 안전한가?" |
| 시간이력 | sphere_report와 동일 (envelope + worst) | 동일 |
| Verdict | 부품별 다기준 분류 | 부품별 + 위치별 둘 다 |

→ **두 도구는 자매 관계**. 입력 데이터의 도메인(각도 vs 좌표)만 다르고 시각 패턴은 90% 공유.

---

## 11. 핵심 동적 UI 컴포넌트 (디자인 모형)

### 11.1 부품별 mini XY heatmap (Page 2 small-multiple 1개 셀)
```
┌─────────────────────────────┐
│ PCB\Main · #3   max 1.4 GPa │  ← 헤더
│ ┌─────────────────────────┐ │
│ │      [device outline]    │ │
│ │   ┌──────────────┐       │ │
│ │   │ [color cells] │ ✕    │ │  ← ✕ = worst impact
│ │   │  [for grid]   │      │ │  ← ★ = response centroid
│ │   │   ★          │       │ │
│ │   └──────────────┘       │ │
│ └─────────────────────────┘ │
│ CoV 0.78 · 23/100 cells     │  ← 푸터
└─────────────────────────────┘
```

### 11.2 Influence Matrix (Page 2)
```
                 PCB  PKG  HSG  MTR  · · ·   합계
Pos_x05_y08  ▓▓▓▓ ▓▓░░ ▓░░░ ▓▓▓░         12.4
Pos_x05_y10  ▓▓▓░ ▓▓▓▓ ▓▓░░ ▓▓░░         11.2
Pos_x07_y08  ░▓▓▓ ▓▓▓▓ ▓░░░ ▓▓▓░         10.8
   ⋮
합계         8.5  9.1  4.2  6.7
```

### 11.3 위치 클릭 → 방사형 부품 영향 차트 (Page 2)
```
        PCB
         │
         │ ░░▓▓
   HSG ──┼── PKG
         │
        MTR
```

---

## 12. 열린 이슈 / 의사결정 필요

1. **그리드 vs 적응형 샘플링** — XY 균일 격자만 지원 vs Fibonacci-style 적응형(위험 영역 fine sampling). MVP는 균일 격자, 추후 적응형 추가.
2. **임팩터 방향** — Z축 충격만 vs 임의 각도. MVP는 -Z 충격, 각도는 미래 확장.
3. **편심 충격 (cylinder)** — 실린더 임팩터가 비스듬히 떨어지는 경우. 시각화 시 임팩터 부착 자세까지 표시 vs 단순 위치 점으로 압축.
4. **다중 임팩터 비교** — Ball Ø25 vs Ball Ø50 등 여러 임팩터 결과를 한 리포트에 묶는 멀티-DOE 모드. P7 이후 확장.
5. **3D 단면 뷰 통합** — Page 3에 deep_report의 section view MP4 임베드 옵션. 단일 파일 정책과 충돌 → 외부 폴더 링크로 처리.
6. **Yield stress · Safety Factor** — sphere_report와 동일 방식 채택 (사용자 입력 + 자동 컬러 임계).
7. **다국어** — 한/영 toggleLang 함수 sphere_report에서 그대로 이식.

---

## 13. 다음 액션

1. 이 계획안 사용자 검토 → 의사결정 항목 (12절) 확정
2. 샘플 DOE 데이터셋 1개 준비 (10×10 격자, ball Ø25, 강체 디바이스 mock 모델)
3. P1 시작: 패키지 골격 + loader + 단위 테스트
4. P3-P4 MVP HTML 생성 → 사용자 demo
5. 피드백 반영 후 P5-P7 완성

---

### 참고 자료

- [koo_sphere_report/REPORT_PLAN.md](../python/koo_sphere_report/REPORT_PLAN.md)
- [docs/Reports_Usage.md](Reports_Usage.md)
- [Test_006_SphereDrop_Report.html](../Test_006_SphereDrop_Report.html) (다이나믹 다이제스트 디자인 레퍼런스)
- [presentation_2_pack/presentation.html](../presentation_2_pack/presentation.html) (소개 자료 톤)

---

## 14. pyKooCAE 실제 도메인 매핑 (v2 추가)

### 14.1 진짜 시나리오 — `drop_weight_impact` (DWI)

pyKooCAE의 [drop_weight_impact](https://github.com/pyKooCAE)는 다음 단계로 구성:

```
scenario.json (사용자 입력)
  ↓
KooChainRun prepare → ImpactPositionSource (위치 DOE 생성)
  ↓
step_config × N (위치별 LS-DYNA 설정 텍스트)
  ↓
KooChainRun submit → Slurm Array Job × N
  ↓
LS-DYNA 실행 × N (DROP_WEIGHT_IMPACT_TEST 모드)
  ↓
KooChainRun collect → 위치별 d3plot/csv 결과
  ↓
[NEW] koo_impact_report → 단일 HTML 리포트
```

### 14.2 임팩터 형상 — pyKooCAE 실제 스키마

#### Sphere
```json
{
  "type": "Sphere",
  "radius": 5.0,         // mm
  "height": 100,         // 자유낙하 높이 (mm) → v=sqrt(2gh)
  "density": 7850,       // kg/m³
  "youngs_modulus": 2e11,
  "poisson_ratio": 0.3
}
```

#### Cylinder — **비대칭 형상**
```json
{
  "type": "Cylinder",
  "front_radius": 3.0,    // 충돌 접촉면 반경 (작음)
  "outer_radius": 6.0,    // 본체 외경
  "front_height": 5.0,    // 앞부분 길이
  "back_height": 10.0,    // 뒷부분 길이
  "back_radius": 6.0,     // 뒷부분 반경
  "height": 150,
  "density": 7850
}
```
실린더는 **앞쪽이 가늘고 뒤쪽이 굵은 텀블러 형상** — 펜/볼펜 끝/송곳 같은
국소 응력 집중 시뮬레이션용. Sphere가 균등 분포 충격이라면,
Cylinder는 **국소 펀치(punch) 효과** 검증.

### 14.3 generation_mode — 모델 경계 조건 3종

pyKooCAE가 부분 충격을 "그 위치에 집중"시키기 위해 모델 외곽을 처리하는 방식:

| 모드 | 의미 | 적용 |
|---|---|---|
| `DampingSpring` (기본) | 외곽 노드에 댐핑 스프링 부여 — 반사파 흡수 | 일반 부품 단품 충격 |
| `OutsideRigidPart` | 충격점 주변을 제외한 외곽 파트를 강체화 | 큰 어셈블리에서 국소 검증 |
| `OutsideRigidElement` | 요소 단위로 외곽 강체화 (더 정밀) | 복잡 메시 / 다중 부품 경계 |

추가 파라미터:
- `boundary_distance` — 충격점 기준 강체화 반경 (mm), `OutsideRigid*` 모드 전용
- `offset_distance` — 임팩터-모델 초기 간격 (mm, 기본 0.05)
- `wall` — 바닥판 물성 (E/ν/ρ)

이 메타데이터는 **Page 1 메소드 밴드에 시각화** 필요 — 사용자가 "어떤 경계조건으로 분석했는지" 즉시 알 수 있어야 함.

### 14.4 위치 DOE 모드 6종

| `locations.mode` | 설명 | 시각화 |
|---|---|---|
| `grid` (nx×ny) | 균등 격자 — bbox 자동/수동 | XY 격자점 |
| `grid_spacing` | 간격 지정 (Δx, Δy) | 동일 |
| `manual` / `list` | 좌표 직접 지정 | 임의 산점 |
| `lhs` | Latin Hypercube Sampling | 준균등 산점 |
| `part_center` | 특정 파트(pids) 중심 기준 격자 | 파트별 클러스터 |
| `txt` (`piMode=txt`) | 외부 파일 좌표 | 임의 |

→ Report Page 1의 "DOE GRID" 패널은 mode에 따라 격자/산점/클러스터 표시 형태 분기.

### 14.5 step_config 출력 포맷 (참고)

각 위치 1개의 LS-DYNA 작업은 다음 텍스트 config로 표현:
```
*Inputfile
<model.k>
*RunDirectoryMode,True,<output>/results/dwi_0001
*Info,DWI,Case0001
*Mode
DROP_WEIGHT_IMPACT_TEST,1
**DropWeightImpactTest,1
TFinal,0.001
DT,0.000001
LocationX,15.5
LocationY,-23.0
Height,100
InitialVelocityZ,-1400.7
ImpactorType,Sphere
ImpactorDimension,5.0
DensityImpactor,7850
YoungsModulusImpactor,2.0e11
GenerationMode,DampingSpring
OffsetDistance,0.05
YoungsModulusWall,2.0e11
**EndDropWeightImpactTest
```

리포트 로더는 **manifest.json** (전체 위치 메타) + 각 run의 `analysis_result.json`을 결합해 데이터 모델을 구성.

---

## 15. Bi-Face 부분 충격 (Smartphone 전용 기본 구성)

### 15.1 사용자의 진짜 요구

> **"전면 충격 후면 충격도 따져야해 ㅋㅋ"**

= 동일 디바이스를 **Front(F2)·Back(F1) 두 자세**로 세워놓고, 각 자세에서
   드러난 면 위에 XY 격자 부분 충격을 수행한 데이터를 **하나의 리포트**에서 통합 분석.

스마트폰 도메인에서는 측면·상단·하단(F3~F6) 단일 면 충격은 현실성이 떨어지므로
**Bi-Face(F1+F2)** 가 기본. 6면(F1~F6)을 모두 다루는 기능은 비스마트폰 디바이스용 옵션으로 잔류.

### 15.2 자세(Face) 분류 — cuboid 26 표준 (참고)

pyKooCAE의 `MODE_CONDITION_Reference.md`에서 정의된 표준 (smartphone 기본은 F1·F2만 사용):

| 코드 | 면 | Roll | Pitch | Yaw | smartphone 기본 |
|---|---|---|---|---|---|
| **F1** | Back (후면) | 0° | 0° | 0° | ✅ 기본 |
| **F2** | Front (전면) | 180° | 0° | 0° | ✅ 기본 |
| F3 | Right (우측면) | 0° | -90° | 0° | 옵션 (smartphone 외 디바이스용) |
| F4 | Left (좌측면) | 0° | 90° | 0° | 옵션 (smartphone 외 디바이스용) |
| F5 | Top (상단) | 90° | 0° | 0° | 옵션 (smartphone 외 디바이스용) |
| F6 | Bottom (하단) | -90° | 0° | 0° | 옵션 (smartphone 외 디바이스용) |

확장 시: E1~E12 (12 모서리) · C1~C8 (8 꼭짓점) 까지. 단 본 보고서는 **면 부분 충격에 집중** —
edge/corner는 임팩터가 미끄러져 부분 충격으로 보기 어려움.

### 15.3 데이터 차원 — Bi-Face DOE (smartphone 기본)

```
F (자세 2: F1·F2) × Position (위치 N) × Part (부품 M) → 응답 (G, σ, ε, d)
```

예시 (스마트폰 5×5 격자):
- F1 (후면) × 5×5 격자 = 25 위치
- F2 (전면) × 5×5 격자 = 25 위치
- 합계 50 시뮬레이션
- 부품 12개 → 50 × 12 = **600 pair**

자세마다 격자 수가 다를 수도 있음(face_grid 별도):
- F1: 5×5 = 25 또는 7×13 = 91 (대형 모델)
- F2: 5×5 = 25 또는 7×13 = 91

6-face 분석(옵션)이 켜진 경우에만 F3~F6이 추가됨.

### 15.4 디렉토리 구조 v2 — Bi-Face 기본

```
Tests/ImpactTest_004_MultiFace/
├── scenario.json                  # 전체 시나리오 (bi-face 설정)
├── manifest.json                  # 전체 (face, position) 매핑
├── F1_back/
│   ├── face_config.json           # 그 면의 자세 행렬 + bbox
│   ├── Run_001_pos_x010_y020/
│   ├── Run_002_pos_x020_y020/
│   └── ...
└── F2_front/
    ├── face_config.json
    ├── Run_001_pos_x010_y020/
    └── ...
# (옵션) F3_right / F4_left / F5_top / F6_bottom — 비스마트폰 디바이스에서만 추가됨
```

### 15.5 scenario.json v2 — multi-face 지원 (제안)

```json
{
  "project_name": "MultiFaceImpactTest",
  "mode": "drop_weight_impact_multiface",
  "model_file": "device.k",
  "output_dir": "mf_output",

  "simulation_params": {
    "tFinal": 0.001,
    "dt": 0.000001,
    "impactor": { "type": "Sphere", "radius": 5.0, "height": 100, ... },

    "faces": [
      {
        "code": "F1",
        "name": "Back",
        "orientation": {"roll": 0, "pitch": 0, "yaw": 0},
        "locations": {"mode": "grid", "x_count": 7, "y_count": 13, "margin": 0.9}
      },
      {
        "code": "F2",
        "name": "Front",
        "orientation": {"roll": 180, "pitch": 0, "yaw": 0},
        "locations": {"mode": "grid", "x_count": 7, "y_count": 13, "margin": 0.9}
      },
      {
        "code": "F5",
        "name": "Top",
        "orientation": {"roll": 90, "pitch": 0, "yaw": 0},
        "locations": {"mode": "grid", "x_count": 7, "y_count": 3, "margin": 0.85}
      }
    ],

    "generation_mode": "DampingSpring",
    "boundary_distance": 0.0,
    "offset_distance": 0.05
  }
}
```

`faces` 배열의 각 항목 = 한 자세 + 그 면의 XY 그리드. 모든 face의 시뮬을 순회 실행 후 통합 리포트.

---

## 16. 리포트 구조 v3 — Bi-Face + Impact Inspector (시그니처)

본 v3에서는 Page 2가 보고서의 **시그니처 컴포넌트** 인 **Impact Inspector** 로 재설계된다.
Cube Net과 부품×자세 mini-heatmap 매트릭스는 모두 제거되었다.

### 16.1 페이지 흐름 (smartphone 기준)

3 페이지 구조는 유지, 콘텐츠 재구성:

| 페이지 | 핵심 | 변경 |
|---|---|---|
| **01 OVERVIEW** | Bi-Face Split + KPI + 임팩터 spec | Cube Net 제거 → Bi-Face Split 로 대체 |
| **02 IMPACT INSPECTOR** | 단일 메인 뷰 — 호버 인터랙션 중심 | 12 mini-heatmap, compare grid 모두 제거 |
| **03 VERDICT + ENERGY FLOW** | 기존 유지 | face 컬럼 2값(F1/F2)으로 단순화 |

### 16.2 Page 1 — Bi-Face Split + Methodology

#### A. Method 밴드 (4 컴팩트 패널, 기존 유지)

기존 §4의 4-패널 method strip(분석 시나리오 / 임팩터 spec / 생성 모드 / DOE 격자 요약)
은 그대로 상단 col-12 strip 으로 유지.

#### B. **Bi-Face Split** (col-12, Cube Net 대체)

좌·우 두 큰 패널로 Front · Back을 동시에 비교:

```
┌──── FRONT (F2) ────────────────┐ ┌──── BACK (F1) ─────────────────┐
│  max G: 1.45 MG  ▌ driving:    │ │  max G: 0.87 MG  ▌ driving:    │
│  PCB\Main (15,-23)             │ │  Motor (-8,12)                 │
│                                │ │                                │
│  ┌──────────────────────────┐  │ │  ┌──────────────────────────┐  │
│  │  디바이스 외곽선          │  │ │  │  디바이스 외곽선          │  │
│  │  + 부품 footprint 외곽선  │  │ │  │  + 부품 footprint 외곽선  │  │
│  │  + 충격 위치 점          │  │ │  │  + 충격 위치 점          │  │
│  │    (색 = max 응답)       │  │ │  │    (색 = max 응답)       │  │
│  │  + ✕ worst 마커          │  │ │  │  + ✕ worst 마커          │  │
│  └──────────────────────────┘  │ │  └──────────────────────────┘  │
└────────────────────────────────┘ └────────────────────────────────┘
```

각 패널 상단에 **max G / driving part** 강조 라벨. 두 면이 즉시 비교됨.

#### C. Per-face KPI 표 (col-12, 2행)

| Face | N positions | Max G | Worst position | Driving Part | Risk Score |
|---|---|---|---|---|---|
| F1 Back | 25 | 0.87 MG | (-8, 12) | Motor | 7.1/10 |
| F2 Front | 25 | 1.45 MG | (15, -23) | PCB\Main | 9.2/10 |

행 호버 → Bi-Face Split 의 해당 면 패널 외곽선 펄스.

#### D. **Δ Map (선택 col-12)**: BACK − FRONT 차이맵

같은 정규화 좌표(u,v) 상에서 (BACK 응답) − (FRONT 응답) 차이를 한 장의 발산색(red↔blue) 맵으로:

- 양수(빨강): BACK 충격이 더 위험한 위치
- 음수(파랑): FRONT 충격이 더 위험한 위치
- 0 부근(흰색): 두 면이 비슷한 위험도

→ "어느 면을 우선 보강할지" 한 장으로 정답.

#### E. Top-K worst pairs 표 (col-12)

전체 50 run × 12 부품 = 600 pair 중 응답이 큰 상위 K (예: 20) 페어를 정렬하여 표시.
각 행: Face / (X,Y) / Part / Max G / σ / ε / d / 시간이력 미니 sparkline.

### 16.3 Page 2 — IMPACT INSPECTOR (메인 컴포넌트)

**페이지 대부분을 차지하는 단일 큰 컴포넌트**. 이 보고서의 시그니처.

```
┌──── 컨트롤 바 ─────────────────────────────────┐
│ Face: [FRONT|BACK]    Metric: G|σ|ε|d           │
│ 정렬: max|first-engage  Threshold: [─slider─]   │
└─────────────────────────────────────────────────┘

┌──── FRONT IMPACT 메인 캔버스 ────┐ ┌── 사이드 패널 ──┐
│                                  │ │                 │
│  [디바이스 외곽선]                │ │ HOVERED:        │
│                                  │ │ P_F03 (15,-10)  │
│  [부품 외곽선들 — 실제 크기/위치] │ │                 │
│  ┌──────┐  ┌─────────┐  ┌─┐      │ │ Top affected:   │
│  │ Mot  │  │ PCB\Main│  │I│      │ │ ▓▓▓ PCB 1.2MG  │
│  └──────┘  └─────────┘  └─┘      │ │ ▓▓░ PKG 0.8MG  │
│                                  │ │ ▓░░ IC 0.6MG   │
│  • • • • • • [⊙ HOVER]• • •     │ │ ░░░ Frame 0.1MG│
│  • • • • • • • • • • • •         │ │                 │
│  • • • • • • • • • • • •         │ │ [시간 이력      │
│                                  │ │  mini chart]    │
└──────────────────────────────────┘ └─────────────────┘
```

#### 동작 사양

- **정적 배경**: 디바이스 외곽 + 부품 footprints는 항상 회색 외곽선으로만 표시 (true-to-scale, 실제 크기·위치)
- **충격 위치 점**: 모든 충격 위치를 점으로 표시. **점의 색 = 그 충격의 글로벌 max 응답** (선택된 Metric 기준)
- **마우스 호버 시**:
  - 호버 점에 빨간 펄스링 표시
  - 모든 부품 외곽선이 **그 충격에 대한 자기 응답값으로 fill** (단색 채움 또는 그라데이션)
  - 사이드 패널에 부품 순위 표 (Top 12, 응답값 막대 + 수치)
  - 사이드 패널 하단에 그 (위치, top-part) 페어의 **시간 이력 미니차트** 표시
- **호버 해제**: 부품은 회색 외곽선으로 즉시 복귀
- **클릭 = pin**: 호버를 떼도 그 상태가 유지됨. 다시 클릭하면 해제. (분석가가 차분히 사이드 패널을 들여다볼 수 있게)
- **Face 토글**: FRONT ↔ BACK 한 클릭으로 전환. 같은 인스펙터 UI가 반대 면 데이터를 보여줌
- **Threshold slider**: 일정 응답값 이하의 점은 회색/투명 처리해서 "위험 점들" 만 부각

#### 보조 컴포넌트 — Influence Matrix (단순화 형태로 잔류)

페이지 하단 보조:
- **행** = 위치 (상위 10개; 응답값 큰 순)
- **열** = 부품 (M개)
- **셀** = 응답값 (히트맵)
- 행 호버 → Impact Inspector 의 그 점이 펄스
- 셀 클릭 → 그 (위치, 부품) 페어의 시간이력으로 Page 3 점프

> 12 mini-heatmap small-multiples (구 §16.3 Mode A) 와 ALL face compare grid (구 Mode B) 는 **모두 제거**.

### 16.4 Page 3 — VERDICT + ENERGY FLOW

#### Verdict 매트릭스 (face 컬럼은 [F2|F1] 2값)

| Part | Face | X (mm) | Y (mm) | Max G | σ | ε | d | CoV | Influence Area | Failure Mode |
|---|---|---|---|---|---|---|---|---|---|---|

옵션: Face 컬럼 대신 **Δ (BACK−FRONT)** 컬럼을 두어 면별 응답차를 한 행에 압축.

#### Per-face Verdict 카드 (NEW, 2개)

- **F2 FRONT 카드**: 그 face의 worst 위치 + 영향받는 부품 리스트 + 권고
- **F1 BACK 카드**: 동일 구조
- 예: "F2 전면 충격은 PCB\Main을 ___% 영구 변형 → 보강 필요"

#### 통합 권장 액션 v3

1. **양 면에 공통 취약 부품** → 부품 자체 보강 (이 부품을 더 단단하게)
2. **한 면에서만 위험한 부품** → 그 면 외부 케이스/완충재 보강
3. **두 면 모두 안전한 위치** → 그 영역은 더 가볍게 설계 가능 (cost/weight 절감 기회)
4. **Cylinder vs Sphere 비교** (있는 경우) → 임팩터 타입별 위험 분포 차이

#### Energy Flow 섹션 (기존 §22 그대로 통합)

Sankey + Time-Force Heatmap + Force-Directed Live Graph 는 face와 무관하므로
Bi-Face 전환의 영향을 받지 않음. F1 / F2 case 별로 동일 분석을 토글로 전환.

---

## 17. 데이터 모델 v2 (Python dataclass 초안)

```python
@dataclass
class FaceOrientation:
    code: str               # "F1" ~ "F6"
    name: str               # "Back" / "Front" / ...
    roll: float
    pitch: float
    yaw: float

@dataclass
class ImpactPosition:
    pos_id: str             # "F1_P_001_001"
    face: str               # "F1"
    x: float
    y: float
    run_dir: Path

@dataclass
class ImpactorSpec:
    type: str               # "Sphere" | "Cylinder"
    radius: float           # Sphere or Cylinder.front_radius
    height: float           # drop height (mm)
    velocity: float         # auto computed
    density: float
    youngs_modulus: float
    # cylinder-only
    front_radius: float | None = None
    outer_radius: float | None = None
    front_height: float | None = None
    back_height: float | None = None
    back_radius: float | None = None
    @property
    def kinetic_energy(self) -> float:
        mass = self.density * self.volume  # 자동 계산
        return 0.5 * mass * self.velocity ** 2

@dataclass
class PairResult:
    face: str
    position: ImpactPosition
    part_id: int
    peak_g: float
    peak_stress: float
    peak_strain: float
    peak_disp: float
    stress_ts: TimeSeriesData

@dataclass
class ImpactReport:
    project_name: str
    impactor: ImpactorSpec
    generation_mode: str
    boundary_distance: float
    offset_distance: float
    faces: list[FaceOrientation]
    positions_by_face: dict[str, list[ImpactPosition]]
    parts: list[PartInfo]
    results: list[PairResult]                       # face × pos × part
    findings: list[Finding]
```

---

## 18. 핵심 시각화 알고리즘 v2

### 18.1 자세별 Risk Score
```python
for face in faces:
    g_vals = [r.peak_g for r in results if r.face == face.code]
    face_risk_score[face] = (
        0.5 * (max(g_vals) / G_GLOBAL_MAX) +
        0.3 * (np.percentile(g_vals, 95) / G_GLOBAL_MAX) +
        0.2 * (sum(1 for g in g_vals if g > THRESH) / len(g_vals))
    ) * 10  # 0~10 점수
```

### 18.2 자세 무관 공통 위험 부품
```python
# 모든 face에서 critical인 부품
for part in parts:
    face_max = {f.code: max_g_for(part, f.code) for f in faces}
    if all(v > CRIT_THRESH for v in face_max.values()):
        part.tag = "universally_critical"
    elif any(v > CRIT_THRESH for v in face_max.values()):
        weakest_face = max(face_max, key=face_max.get)
        part.tag = f"face_specific:{weakest_face}"
```

### 18.3 큐브 펼침도 좌표 변환 (DEPRECATED in v3)

> v3에서 Cube Net 컴포넌트가 Bi-Face Split 으로 교체되어 본 함수는 **6-face 옵션 모드에서만** 사용됨.
> Bi-Face(F1+F2) 기본 구성에서는 사용하지 않음.

```python
# 6면 큐브 네트 (cross 형태) — 6-face 옵션 전용 (smartphone 기본 Bi-Face에서는 미사용)
def cube_net_layout(W, H, cell_w, cell_h):
    cx = W / 2
    cy = H / 2
    return {
        "F1": (cx - cell_w/2, cy - cell_h/2),         # 중앙 후면
        "F2": (cx + 3*cell_w/2, cy - cell_h/2),       # 우측 전면
        "F3": (cx + cell_w/2, cy - cell_h/2),         # 우측 면
        "F4": (cx - 3*cell_w/2, cy - cell_h/2),       # 좌측 면
        "F5": (cx - cell_w/2, cy - 3*cell_h/2),       # 상단
        "F6": (cx - cell_w/2, cy + cell_h/2),         # 하단
    }
```

### 18.4 자세별 데이터 정규화
서로 다른 자세는 디바이스 bbox·격자가 다를 수 있음 →
**정규화 좌표** (u, v) ∈ [0,1] 변환하여 비교 가능:
```python
u = (x - bbox_x_min) / (bbox_x_max - bbox_x_min)
v = (y - bbox_y_min) / (bbox_y_max - bbox_y_min)
```
부품 footprint도 같은 변환으로 표시 → cube net의 모든 면이 같은 단위 사각형.

---

## 19. CLI v2

```bash
koo_impact_report \
    --test-dir Tests/ImpactTest_004_MultiFace \
    --output report.html \
    --metric peak_stress \
    --threshold-critical 1000 \
    --yield-stress 800 \
    --faces F1,F2,F5 \                  # 일부만 분석 (기본: 발견된 전부)
    --compare-faces \                   # ALL 모드 강제 활성
    --severity-weight g=0.5,s=0.3,e=0.2 # 종합 점수 가중치
```

호환 모드:
- `--from-json report.json` — 재생성 (sphere_report와 동일)
- `--legacy-singleface` — v1 호환 모드 (단일 face만)

---

## 20. 마일스톤 v3 — Bi-Face + Impact Inspector

| Phase | 산출물 | 기간 |
|---|---|---|
| P0 | scenario.json v3 스키마 + **샘플 50 runs (F1×25 + F2×25)** | 1주 |
| P1 | loader (pyKooCAE manifest 매핑, bi-face) + 단위 테스트 | 1주 |
| P2 | analyzer (face × position × part 통계) | 0.5주 |
| P3 | HTML Page 1 + **Bi-Face Split** + Δ Map + 임팩터 형상 viz | 1주 |
| P4 | HTML Page 2 — **Impact Inspector** (호버 인터랙션, 부품 footprint outline, 사이드 패널) | 1.5주 |
| P5 | HTML Page 3 + per-face verdict (2개 카드) | 1주 |
| P6 | Linked highlighting (Page1 Δ Map ↔ Inspector ↔ Verdict) | 1주 |
| P7 | pyKooCAE 통합 + SIF 빌드 + 예제 + 문서 | 1주 |
| **합계** | **MVP** | **~9주** |

v2 대비 변동:
- P0b 샘플 데이터 110 runs → **50 runs** (bi-face 만 필요)
- P3 Cube Net 제거 → Bi-Face Split + Δ Map 로 1주로 단축
- P4 Multi-Face Transfer Maps (2주) → **Impact Inspector** (1.5주). 시각화 단순 + 단일 컴포넌트라 일정 단축
- P5 3D matrix → 2-face verdict 카드 단순화
- 전체 MVP ~10주 → **~9주**

---

## 21. 우선순위 결정 — 사용자 확인 필요

> v3 업데이트: q1은 **Bi-Face(F1+F2)를 MVP 기본 구성으로 확정** (스마트폰 도메인 결정).
> Cube Net 관련 의사결정 항목들은 §16 재설계로 무효화되어 제거. q2는 그대로 유지.

`q2`: 임팩터 형상은 **Sphere만 우선** vs **Cylinder까지 동시**?
→ 권장: Sphere 먼저 (Cylinder는 비대칭 형상 시각화 추가 작업 필요)

`q3`: generation_mode 별 결과 비교가 분석 범위에 들어가나?
→ 같은 위치에서 3가지 mode를 모두 돌려서 비교? 아니면 단일 mode만 보여줌?

`q4`: pyKooCAE의 누적(cumulative) 모드와 결합 — 같은 위치에 N번 반복 충격? 보고서가 이 누적 영향도 표시?

`q5`: 디바이스 외곽 폴리곤(`device_layout.json`)을 어떻게 얻나?
→ 자동 추출 (d3plot mesh → XY 투영) vs 사용자 제공 vs k파일 *NODE 파싱?

(v3 신규)

`q11`: Impact Inspector 의 부품 fill 컬러맵 기준은?
- (a) **절대값 기준** (MPa / G 등 물리 단위) — 면 간 / 위치 간 직접 비교 가능
- (b) **호버 위치 내부 정규화** (그 위치에서 가장 큰 부품 = 1.0, 나머지 비율) — 그 위치 내 상대 영향도가 강조됨

→ 권장: **기본 = 절대값**, 토글로 정규화 모드 제공 (분석가가 의도에 따라 전환)

`q12`: **Δ Map (BACK − FRONT)** 의 위상은?
- (a) Page 1 의 **메인 컴포넌트** 로 승격 (Bi-Face Split 옆/아래 큰 col-12 차지)
- (b) Page 1 의 **옵션 보조 컴포넌트** (접혀 있다가 사용자가 펼침)

→ 권장: 초기엔 (b) 보조, 사용자 피드백 후 (a) 승격 검토. "면을 한 장으로 결판내는" 강력한 슬라이드라 데모용으로 가치 높음.

이 항목들에 대한 답이 정해지면 P0 (DOE 표준) 진입 가능.

---

## 22. 에너지 전달 동적 시각화 — Energy Flow Dynamics (v3 핵심 추가)

> **컨셉:** 임팩터의 운동에너지가 디바이스의 어느 부품을 거쳐 어떻게 전파되는지를
> **시간에 따라 변하는 지식그래프(knowledge graph)** 로 모사한다.
> 노드 = 부품(+ 임팩터), 엣지 = 부품 간 접촉 인터페이스. 엣지 가중치 = 누적 임펄스/접촉력.
> 노드 색·크기 = 내부에너지·응력 상태.

### 22.1 핵심 관찰

부분 충격은 본질적으로 **에너지 전달 문제**다:

```
임팩터 KE(t=0) → 1차 접촉 부품 → 2차 부품 → ... → 종료 시 분포된 에너지
                  내부에너지↑       전달↑              내부 + 소성 + sliding + hourglass
```

기존 리포트가 **"부품 X의 최대 응력값"** 같은 *결과 스냅샷* 위주라면,
이 시각화는 **"임팩트 KE가 어떤 경로로 흘러가는지"** *프로세스 동영상*을 보여준다.

### 22.2 필요한 데이터 소스 — 모두 이미 존재

| 데이터 | 출처 | 의미 |
|---|---|---|
| **글로벌 에너지** | `binout` → glstat | KE, IE, sliding, hourglass, 외부 일 |
| **부품별 내부에너지** | `binout` → matsum | 각 part의 IE(t), KE(t) |
| **접촉 인터페이스별 힘** | `binout` → rcforc | contact_id별 F(t), 양/음 방향 |
| **임팩터 운동에너지** | matsum의 임팩터 part | KE_impactor(t) |
| **응력/변형** | d3plot | 시각적 상태 보강용 |

→ 모두 [koo_deep_report/core/](../python/koo_deep_report/koo_deep_report/core/)에 이미 리더 존재:

- [glstat_reader.py](../python/koo_deep_report/koo_deep_report/core/glstat_reader.py)
- [binout_reader.py](../python/koo_deep_report/koo_deep_report/core/binout_reader.py)

### 22.3 핵심 전처리 — Contact Auto-Decomposition (이미 구현됨)

LS-DYNA 표준 `*CONTACT_AUTOMATIC_SINGLE_SURFACE`는 모든 부품을 한 contact_id로 묶음 →
이러면 rcforc가 부품 간 분리되지 않음 → 엣지가 안 생김.

해결: **KooMeshModifier의 `CONTACT_AUTO_DECOMPOSITION` 모드**가
하나의 단일면 접촉을 자동으로 **N개의 페어별 접촉**으로 분해.

```
*Mode
CONTACT_AUTO_DECOMPOSITION,1
**ContactAutoDecomposition,1
*SearchMarginX,1.5
*SearchMarginY,1.5
*SearchMarginZ,1.5
*ContactKeyword
*CONTACT_AUTOMATIC_SINGLE_SURFACE_ID
... (기존 단일 접촉 정의)
**EndContactAutoDecomposition
*End
```

결과:

- 페어 (part_i, part_j)당 별도 contact_id 부여
- rcforc.csv가 contact_id별로 분리된 F(t) 출력
- → 이를 graph edge time series로 직접 매핑 가능

**파이프라인에 추가할 단계** (DWI 워크플로 직전):

```
prepare → CONTACT_AUTO_DECOMPOSITION 적용 → submit → collect → energy graph 추출
```

### 22.4 데이터 모델 — Energy Graph

```python
@dataclass
class EnergyNode:
    node_id: str            # "impactor" | part_id (str)
    name: str
    is_impactor: bool = False
    kinetic_ts: list[float] = field(default_factory=list)    # KE(t)
    internal_ts: list[float] = field(default_factory=list)   # IE(t)
    times: list[float] = field(default_factory=list)

@dataclass
class EnergyEdge:
    src: str                # node_id (energy donor)
    dst: str                # node_id (energy receiver)
    contact_id: int
    times: list[float]
    force_mag_ts: list[float]    # |F|(t)
    impulse_cum_ts: list[float]  # ∫|F| dt   누적 임펄스
    work_cum_ts: list[float]     # ∫F·v dt   누적 일 (방향 고려)
    peak_force: float
    total_impulse: float
    total_work: float

@dataclass
class EnergyGraphFrame:
    """단일 시간 t의 그래프 스냅샷."""
    t: float
    nodes: dict[str, dict]       # node_id → {ke, ie, total, stress_avg}
    edges: dict[tuple, dict]     # (src,dst) → {force, impulse_inc, active}

@dataclass
class EnergyFlow:
    """한 case의 전체 에너지 전달 데이터."""
    impactor_ke_initial: float
    impactor_ke_final: float
    energy_dissipated: float
    nodes: list[EnergyNode]
    edges: list[EnergyEdge]
    frames: list[EnergyGraphFrame]    # T 타임스텝
    propagation_order: list[tuple]    # [(node, t_first_engaged), ...]
    depth_map: dict[str, int]         # impactor=0, 1차=1, 2차=2 ...
```

### 22.5 시각화 1 — Force-Directed Energy Graph (라이브 그래프)

페이지 3 (또는 신규 페이지 04)에 큰 캔버스로 배치.

#### 레이아웃

- 임팩터 노드: 가운데 또는 한쪽 끝 고정
- 부품 노드: D3-style force simulation으로 자동 배치
  - 또는 deterministic: depth_map 기준 동심원 (impactor=0, 1차 접촉=1, 2차=2)
- **노드 시각 인코딩:**
  - 크기 = `IE(t)` (내부에너지)
  - 색 = `stress_avg(t)` (파랑 → 빨강)
  - 외곽 펄스링 = 그 순간 active contact 있을 때
- **엣지 시각 인코딩:**
  - 두께 = `impulse_cum(t)` (누적 임펄스)
  - 색 = current force direction (push/pull)
  - 흐르는 입자(particle flow) 애니메이션 = 방향성 표현
  - 펄스 = 그 순간 활성화된 contact

#### 동적 인터랙션

- **타임 스크러버** (페이지 하단 슬라이더): t = 0 ~ T까지 드래그
- **재생 버튼**: 0.5×/1×/2× 속도로 자동 재생
- **노드 클릭** → 그 부품의 IE(t)·KE(t) 라인차트 사이드 패널
- **엣지 클릭** → 그 인터페이스의 F(t)·임펄스 누적 차트
- **에너지 추적**: 한 노드 선택 → 그 노드로 흘러 들어오는/나가는 엣지만 강조

### 22.6 시각화 2 — Sankey 다이어그램 (누적 에너지 흐름)

```
[Impactor KE]    ──→  [Top Plate IE]   ──→  [Frame IE]   ──→  [PCB IE]
   100 J            65 J              30 J            8 J
                  ──→  [Damping]  20 J
                  ──→  [Sliding loss]  15 J
                            ──→  [Hourglass]  3 J
                            ──→  [Heat]  2 J
```

- 좌측: 임팩터 KE 입력
- 우측: 최종 분포 (각 부품 IE + 소산 채널)
- 두께 = 에너지 양
- 시간 매개: 슬라이더로 t 선택 → 그 시점까지의 누적 흐름
- **에너지 보존 막대**: KE_initial = IE_total + dissipation + KE_remaining 검증

### 22.7 시각화 3 — Energy Propagation Cone (전파 원뿔)

```
        t=0.1ms       t=0.3ms       t=0.5ms       t=1.0ms
         (ring 1)     (ring 2)      (ring 3)       (ring 4)
                                              ┌──[PCB]──┐
                                  ┌──[Frame]──┤
                       ┌──[Top]──┤              └──[IC]──┘
   [Impactor]──────────┤              └──[Mid]──┐
                       └──[Side]──┐              └──[Conn]─┐
                                  └──[Wall]──────────────┘
```

- X축 = 시간
- Y축 = 부품을 **첫 접촉 시점 순** 정렬
- 각 부품 행에 그 시점의 IE 값을 색상 코딩한 띠
- 임팩터로부터의 "전파 깊이"(graph distance) 별 그룹 컬러 밴드
- **한눈에 "에너지가 어떤 순서로 어디까지 도달하는지" 파악**

### 22.8 시각화 4 — Energy Budget Sunburst (계층 파이)

```
              KE_initial 100 J (impactor)
                       │
        ┌──────────────┼──────────────┐
        │              │              │
   IE 70 J         dissipated 25 J   KE_left 5 J
   ┌────┼────┐         │
   │    │    │    sliding 15
  Top  Frm  PCB   hourglass 5
   40   20   10   heat 5
```

- 중심 = 임팩터 초기 KE
- 1차 링 = 주요 분배 (디바이스 IE / 소산 / 잔존 KE)
- 2차 링 = 디바이스 부품별 분배
- 시간 슬라이더 또는 종료시점 고정
- **클릭 → drill-down**: 한 부품 클릭 시 그 부품과 연결된 모든 엣지의 누적 work 분포

### 22.9 시각화 5 — Time-Force Heatmap Matrix

```
              t=0  0.1  0.2  0.3  0.4  0.5 ... 1.0 ms
edge_imp→top  ▓▓▓ ▓▓▓ ▓▓░ ░░░ ░░░ ░░░     ░░░
edge_top→frm  ░░░ ░▓▓ ▓▓▓ ▓▓▓ ▓▓░ ░░░     ░░░
edge_frm→pcb  ░░░ ░░░ ░░░ ░▓▓ ▓▓▓ ▓▓▓     ░▓░
edge_frm→ic   ░░░ ░░░ ░░░ ░░▓ ▓▓▓ ▓▓░     ░░░
edge_pcb→cap  ░░░ ░░░ ░░░ ░░░ ░▓▓ ▓▓▓     ░░░
```

- 행 = 각 엣지(부품 쌍)
- 열 = 시간
- 셀 색 = `|F|(t)` 또는 instantaneous power = F·v
- 행 정렬 = first-engage 시점 (위→아래로 전파 순서)
- **"몇 마이크로초 후에 어디까지 진동이 전파됐는가"** 정량 파악

### 22.10 시각화 6 — 3D Device + Floating Edges (선택, P+1)

가장 야심찬 옵션:

- 디바이스의 실제 3D 메시 (단순화 wireframe)
- 부품 footprint 컬러로 IE(t) 인코딩
- 부품 간 활성 contact 위에 **공중에 떠 있는 빛나는 선** (엣지) 그리고 그 위에 입자 흐름
- 임팩터는 실제 위치에서 떨어지는 애니메이션 → 첫 접촉 → 충격파가 방사
- **"임팩트 머신의 실제 모습"** 같은 직관적 시각

→ MVP에는 무리, P+1 phase로 미룸. Three.js + d3plot 메시 임포트 필요.

### 22.11 핵심 알고리즘

#### A. 엣지 임펄스 계산

```python
for contact_id, force_ts in rcforc_data.items():
    src_part, dst_part = contact_metadata[contact_id]
    F_mag = np.linalg.norm(force_ts[['fx','fy','fz']], axis=1)
    impulse_cum = np.cumsum(F_mag * dt)
    edge = EnergyEdge(src=src_part, dst=dst_part, contact_id=contact_id, ...)
```

#### B. 노드 IE/KE 시계열

```python
for part_id in parts:
    matsum_part = matsum_reader.get_part(part_id)
    node.internal_ts = matsum_part['internal_energy']
    node.kinetic_ts  = matsum_part['kinetic_energy']
```

#### C. 전파 깊이 (BFS from impactor)

```python
def compute_depth(graph):
    depth = {impactor.id: 0}
    queue = [impactor.id]
    edges_by_node = group_edges_by_node(graph)
    while queue:
        node = queue.pop(0)
        for neighbor in edges_by_node[node]:
            if neighbor not in depth:
                depth[neighbor] = depth[node] + 1
                queue.append(neighbor)
    return depth
```

#### D. 첫 접촉 시점 (first engage time)

```python
def first_engage_time(edge, threshold=1e-3):
    for t, f in zip(edge.times, edge.force_mag_ts):
        if f > threshold:
            return t
    return None
```

#### E. 에너지 보존 검증

```python
def verify_energy_conservation(flow):
    ke_init = flow.impactor_ke_initial
    ke_final = sum(n.kinetic_ts[-1] for n in flow.nodes)
    ie_final = sum(n.internal_ts[-1] for n in flow.nodes)
    dissipated = glstat['sliding'][-1] + glstat['hourglass'][-1]
    residual = ke_init - ke_final - ie_final - dissipated
    return {
        'ke_init': ke_init,
        'residual_pct': residual / ke_init * 100,    # < 5% 권장
    }
```

#### F. 노드 좌표 자동 배치 — 깊이 동심원

```python
def layout_nodes(depth_map, max_depth):
    positions = {impactor.id: (0, 0)}
    by_depth = defaultdict(list)
    for n, d in depth_map.items():
        by_depth[d].append(n)
    for d, nodes in by_depth.items():
        if d == 0: continue
        radius = 100 * d
        for i, n in enumerate(nodes):
            angle = 2*pi*i/len(nodes) + offset
            positions[n] = (radius*cos(angle), radius*sin(angle))
    return positions
```

### 22.12 페이지 통합 — Page 03 또는 신규 04 ENERGY FLOW

3페이지 압축 정책에 따라 **단일 페이지에 5개 viz 통합**:

```
┌─────────────────────────────────────────────────────────┐
│ 04 ENERGY FLOW · 시간에 따른 에너지 전달 동역학            │
├──────────────────────────────┬──────────────────────────┤
│ A. Force-Directed Live Graph │ B. Energy Budget Sunburst│
│    (메인, 큰 캔버스)          │    (계층 파이)             │
│    + 노드/엣지 클릭 사이드패널 │                          │
├──────────────────────────────┼──────────────────────────┤
│ C. Sankey 누적 흐름           │ D. Conservation Check    │
│                              │ KE_init = IE + diss + KE  │
├──────────────────────────────┴──────────────────────────┤
│ E. Time-Force Heatmap Matrix (전체 엣지의 시간 전개)      │
├─────────────────────────────────────────────────────────┤
│ TIMELINE SCRUBBER  [|||||----------]  t=0.32 ms          │
│                    ▶ play  ◀◀ reset                       │
└─────────────────────────────────────────────────────────┘
```

3페이지 정책 유지 시 → Page 3의 verdict 영역과 결합해 **"에너지로 본 verdict"** 단일 페이지로 통합. 디자인 시 결정.

### 22.13 다면 모드와 결합 (Bi-Face 기본)

smartphone 기본 구성에서는 **F1·F2 각 자세별로 별도 energy graph** 존재 → 2-way **자세 토글** 로 두 면의
에너지 전파 패턴을 직접 비교. (6-face 옵션 모드에서는 F1~F6 6-way 토글로 확장):

- F1 후면 충격 → 에너지가 PCB까지 도달 (depth 4)
- F2 전면 충격 → 에너지가 Housing에서 멈춤 (depth 2) → 안전한 자세
- 자세별 **propagation depth + edge count + dissipation ratio** 표로 한눈에 비교

### 22.14 정량 결론 자동 도출

리포트 자동 분석 결과 예:

> "임팩트 KE 100 J 중 **47%가 PCB\\Main에 흡수**됐다.
> 주 경로: Impactor → Top Plate (38%) → Frame (62%) → PCB (75%).
> Top Plate가 38%만 받아내고 나머지를 즉시 전달 — **Top Plate의 흡수 효율이 낮음**.
> 권장: Top Plate에 충격흡수재 추가 또는 hourglass 보강."

이런 **에너지 회계 기반 권고**가 핵심 차별점.

### 22.15 신규 핵심 분석 질문 (§1.2 보강)

| # | 질문 | 시각화 |
|---|---|---|
| Q6 | 임팩트 에너지가 **어떤 순서로** 부품을 거치나? | Propagation Cone / Sankey |
| Q7 | **어디서 에너지가 소산되나?** (충격흡수 효율) | Budget Sunburst |
| Q8 | **에너지가 얼마나 깊이** 침투하는가? (depth) | Force-Directed Graph |
| Q9 | 에너지 보존이 검증되는가? (해석 신뢰성) | Conservation Check |
| Q10 | 자세별 전파 패턴 차이는? | Multi-face Energy Compare |

### 22.16 워크플로 추가

```
P0a: CONTACT_AUTO_DECOMPOSITION pre-processing 통합
     → scenario.json 에 "auto_decompose_contact": true 옵션
     → KooMeshModifier로 자동 분해된 contact 사용
P0b: rcforc/matsum/glstat 통합 리더 (이미 존재) 활용
P0c: EnergyFlow 데이터 모델 도출 + 단위 테스트
```

기존 P3~P5에 **P5b 단계 추가**: Energy Flow Page (2-3주 추가).

### 22.17 위험 / 제약

- **rcforc 파일 크기**: contact 수가 수백 개로 분해되면 rcforc.csv가 수 GB 가능. 스트리밍 다운샘플링 필요 (sphere_report 패턴 재활용).
- **에너지 보존 결손**: numerical artifact로 residual 5% 이상이면 hourglass 또는 마찰 의심 → 자동 경고.
- **노드 배치 알고리즘**: 부품 수가 많으면 force-directed 안정화에 시간 소요. depth-based deterministic 레이아웃을 기본으로.
- **그래프 가독성**: 부품 ≥ 30개 시 그래프 혼잡. 자동 클러스터링(그룹 기준)으로 simplified view 제공.

### 22.18 영감 / 참고

- **D3.js force-directed graph** — 노드/엣지 라이브 시뮬레이션
- **Sankey diagram** (Plotly / D3) — 에너지 흐름 표준 표현
- **Bloomberg / NYT 시각화** — 시간 슬라이더 + 멀티뷰 연결
- **Knowledge Graph 시각화** — Obsidian / Roam Research 그래프뷰
- **CFD streamline visualization** — 입자 흐름 애니메이션 영감
- LS-DYNA의 `*INTERFACE_COMPONENT` + rcforc 표준 사용법

---

## 23. 우선순위 결정 v3 추가

`q6`: Energy Flow는 MVP에 포함? vs Phase 2로 분리?
→ 권장: **MVP에 simplified Energy Flow** (Sankey + Time-Force Heatmap만) 포함, 라이브 그래프는 P+1.

`q7`: CONTACT_AUTO_DECOMPOSITION을 모든 case에 강제 적용? vs 옵션?
→ 권장: 옵션 (`auto_decompose_contact: true|false`). 안 켜져 있으면 글로벌 에너지만 표시.

`q8`: 부품이 많을 때 (≥30개) 자동 그루핑 정책은?
→ 권장: pid_group 메타데이터로 (PKG / PCB / Frame / Housing) 클러스터링. 사용자가 정의 없으면 part_name prefix 자동 추출.

`q9`: Energy Conservation 검증 결과를 리포트에 강제 표시? (해석 신뢰성)
→ 권장: 항상 표시. residual > 5%면 빨간 경고 배너.

`q10`: 실측 비교 (high-speed force sensor) 데이터를 같이 overlay 할 수 있는 hook 필요?
→ 미래 확장 (v2에는 미포함). 단 데이터 모델에서 자리만 마련.

---

## 24. 신규 마일스톤 v3 (Energy Flow 통합)

| Phase | 산출물 | 기간 |
|---|---|---|
| P0a | CONTACT_AUTO_DECOMPOSITION 워크플로 통합 | 0.5주 |
| P0b | 샘플 **Bi-Face 50 runs (F1×25 + F2×25)** + decomposed contact 데이터셋 | 1주 |
| P1 | loader (manifest + binout 통합, bi-face) | 1주 |
| P2 | analyzer + EnergyFlow 모델 | 1주 |
| P3 | HTML Page 1 + **Bi-Face Split + Δ Map** + 임팩터 viz | 1주 |
| P4 | HTML Page 2 — **Impact Inspector** (호버 인터랙션) | 1.5주 |
| P5 | HTML Page 3 + Verdict + Sankey + Heatmap (basic energy flow) | 2주 |
| P5b | Page 4 ENERGY FLOW — Force-Directed Live Graph | 2주 |
| P6 | Linked highlighting 3중 + Energy timeline 연동 | 1주 |
| P7 | pyKooCAE 통합 + SIF + 문서 | 1주 |
| **MVP (P5까지)** | **에너지 기본 분석 포함 (Bi-Face + Impact Inspector)** | **~9주** |
| **Full (P5b 포함)** | **라이브 그래프까지** | **~11주** |

---

## 25. 핵심 차별점 요약 — 왜 이 보고서가 특별한가

1. **자세 × 위치 × 부품** 3차원 통합 분석 (smartphone: Bi-Face F1·F2 기본; 6-face 옵션)
2. **에너지 회계** — 임팩트 KE 100%가 어디로 갔는지 보존 검증
3. **지식그래프 모사** — 부품을 노드, 접촉을 엣지로 한 라이브 그래프
4. **시간 스크러버** — 에너지가 도달하는 순간을 직접 관찰
5. **자동 권고** — 데이터 기반 보강 위치 제안 (에너지 흡수 효율 분석)
6. **단일 HTML 파일** — 보안망/오프라인/이메일 전달 가능
7. **Position-centric Impact Inspector + CONTACT_AUTO_DECOMPOSITION** —
   기존 KooMeshModifier 의 단일면 접촉 자동 분해 모드를 100% 활용해 부품 간 에너지 전달을 추출하고,
   그 결과를 **호버 기반 Impact Inspector** 로 풀어 분석가의 **첫 5초에 "where to fix"** 를 알려준다.
   즉 "어디가 위험한지" 와 "그 위치가 어느 부품을 어떤 비율로 위협하는지" 가 한 화면·한 동작으로 답해진다.
