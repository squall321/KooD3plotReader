# 시뮬레이션 과제 종합 카탈로그

작성일: 2026-06-05
용도: 갤럭시 모델별 시뮬레이션 계획 수립 reference
출처: 사용자 환경의 study 디렉토리 + PT/PPT/제안서 자료 + deep-research (web)

본 문서는 **3개 표** + **계획서 빈칸 framework** 로 구성:
- A. 사용자 환경에서 **실제 진행/완료된 시뮬 과제** (study 디렉토리 + DOE testset)
- B. 사례 / 신규 제안 (PT 자료 + 신뢰성 PPT + 면품질 제안서)
- C. **갤럭시 모델 × AP 분배** (2020-2025, 인용 verified)
- D. 시뮬 계획서 작성용 **빈칸 framework**

---

## A. 진행/완료 시뮬 과제 — `/data/` 의 실제 study (15개 + DOE 13개)

> 환경 inventory 기반. 케이스 수가 100+ 인 것은 대규모 DOE/parametric, 5~30 은 phase-based 또는 ablation.

| # | 카테고리 | 과제 (Study 디렉토리) | 대상 부품/현상 | 케이스 수 | 시뮬 유형 / 메소드 | 환경 위치 |
|---|---|---|---|---|---|---|
| 1 | 낙하 충격 | `ball_drop_test_v1~v7` | 표준 낙하 — 회기 검증 7세대 | 7 버전 | 단일 낙하 (반복 개선) | `/data/koodyna_reports/ball_drop_test*` |
| 2 | 낙하 충격 | `dropimpact` / `drop_test_results` | 통합 drop archive | — | 단일/전각도 mix | `/data/koodyna_reports/` |
| 3 | 디스플레이 충격 | `1.DisplayImpactBallPeridynamics` (+`Fine`) | 디스플레이 ball impact | 2 mesh 레벨 | **Peridynamics** (균열 자동 발생) | `/data/koodyna_reports/` |
| 4 | 디스플레이 굴곡 | `2.Display3ptBendingPeridynamics` (+`3 pt bending test`) | 3-point bending | 2 (PD + 전통) | Peridynamics vs FEM 비교 | `/data/koodyna_reports/` |
| 5 | 디스플레이 충격 | `DisplayImpactImplicit` / `DisplayImpactShell` | implicit / shell | 2 mesh 변형 | Implicit 해석 + Shell vs Solid | `/data/koodyna_reports/` |
| 6 | **배터리 압괴/Indentation** | `battery_study` | Stacked / Wound 배터리 셀 | **161 case** (phase1~3) | 단일 충격 + 변형 | `/data/battery_study/` |
| 7 | 폴더블 힌지 | `foldable_hinge_study` | Z Flip 0/90/180° 4축 | 8 phase | 힌지 피로 / phase-a/b | `/data/foldable_hinge_study/` |
| 8 | 방열 (VC) | `vapor_chamber_study` | 베이퍼 챔버 vs 동판 | 13 phase | 열-CFD spreading | `/data/vapor_chamber_study/` |
| 9 | Warpage | `warpage_study` | 디스플레이 적층 휨 | 7 (lam_sym/asym) | 적층 휨 — Shell 적층 | `/data/warpage_study/` |
| 10 | 진동 | `floor_wave_study` | 바닥 진동 매트릭스 | **149 case** (matrigid h0.5/1.0/1.5/2.0) | 매트리지드 + 높이 매트릭스 | `/data/floor_wave_study/` |
| 11 | Shield Can 성형 | `shield_can_forming_study` | EMI shield can 성형 후 변형 | **138 case** | Stamping + 변형 / baseline + extreme/hole point | `/data/shield_can_forming_study/` |
| 12 | 테이프 | `tape_study` | 배터리/디스플레이 테이프 | 42 case + 18 phase | Bending DOE + Elastic property sweep | `/data/tape_study/` |
| 13 | 현실 반발 | `realistic_rebound_study` | mat024 sigy sweep | 24 case | baseline + sigy 변경 ablation | `/data/realistic_rebound_study/` |
| 14 | 강성 | `soft1_stiffness_study` | Soft1 재료 | 15 case (uniform → 16x fine) | mesh refinement | `/data/soft1_stiffness_study/` |
| 15 | 요소 정식화 | `tet10_elform_study` | hex8/tet10 element form | 12 (elform -2~60) | element 정식화 비교 | `/data/tet10_elform_study/` |
| 16 | 솔버 정식화 | `level_study` | tet4/tet10 dt0 | 13 | tet 정식화 | `/data/level_study/` |
| 17 | 고무 재료 | `rubber_advanced_study` | EFG/locking/inverse | 6 phase | 고무 점탄성 | `/data/rubber_advanced_study/` |
| 18 | 표준 인장 | `astm_e8_study` | ASTM E8 인장 시험 | 11 case + batch | 단축 인장 회기 검증 | `/data/astm_e8_study/` |
| 19 | FMBD (Body Dynamics) | `fmbd_study` | eigenvalue/modal/FRB | 5 phase (a/b/c) | 강체 동역학 + 주파수 응답 | `/data/fmbd_study/` |
| 20 | CMS | `cms_study` | DOE L2/L3, p0/p4 | 24 (analyze_doe) | Component Mode Synthesis | `/data/cms_study/` |
| 21 | Composite | `Composite` | Composite 적층 | — | 적층 복합재 | `/data/koodyna_reports/Composite/` |
| 22 | Solver alt | `alt_ale`/`alt_efg`/`alt_spg`/`alt_sph` | ALE/EFG/SPG/SPH 비교 | 4 솔버 | 솔버 정식화 회기 | `/data/koodyna_reports/` |
| 23 | Solver elform | `alt_tet_elform15` / `alt_tet_elform60` | tet elform 15/60 | 2 | tet 정식화 | `/data/koodyna_reports/` |
| 24 | Confined Compression | `confined_compression` | 봉인 압축 | — | 봉인 압축 시험 | `/data/koodyna_reports/` |

### A-1. DOE / 검증 testset (KooChainRun 자동화 검증)

| # | 카테고리 | 과제 | 케이스 수 | 환경 위치 |
|---|---|---|---|---|
| D1 | 부분 충격 DOE | **Test_Impact_A** (5×5 grid × 25 부품 = 625 pair) | 25 위치 | `/data/koopark/Test_Impact_A/` |
| D2 | 전각도 sweep 검증 | Test_001_Full26_1Step / 002_Full26_3Step | 26-78 | `/data/Tests/Test_001/002` |
| D3 | 6면 cyclic | Test_003_6Faces_Cyclic | 6 face | `/data/Tests/Test_003/` |
| D4 | Pitching sweep | Test_004_Pitching_Sweep | sweep | `/data/Tests/Test_004/` |
| D5 | **Fibonacci 전각도 (대규모)** | Test_005_Fibonacci_100 | **100 각도** | `/data/Tests/Test_005/` |
| D6 | Fibonacci 6° / 2° | Test_006/007 | ~600 / ~5,000 (조밀) | `/data/Tests/Test_006/007` |
| D7 | 낙하 검증 | Test_DropWeight_Validation, Test_DWI | 다수 | `/data/koopark/Test_DropWeight_Validation`, `Test_DWI` |
| D8 | 전각도 + Rigid Wall | Test_FullAngle_RW | Fibonacci 100 | `/data/koopark/Test_FullAngle_RW/` |
| D9 | IGA 전각도 | Test_IGA_FullAngle | IGA mesh | `/data/koopark/Test_IGA_FullAngle/` |
| D10 | 진동 | Test_VibP1 / VibP2 | Phase 1/2 | `/data/koopark/Test_VibP1`, `VibP2` |
| D11 | Post-process v14/v15 | Test_Postprocess_v14, v15_SeparateJob | — | KooD3plotReader 검증 |
| D12 | 시스템 검증 | Test_chdir_health, Test_semaphore, Test_010_Sequential_Quick | — | 환경 회기 |

---

## B. 신뢰성 시험 사례 + 신규 제안 (자료 기반)

### B-1. 성공 사례 (`신뢰성시험혁신전략.pptx`)

| 사례 | 부품 | 기존 시험 | 시장 Gap | CAE/시뮬 발견 | 신규 시험법 | 출처 |
|---|---|---|---|---|---|---|
| **#1 AP Ball Crack** | AP (LSI/QC) | PBA 열충격 (균일 온도) | 시장 Correlation 0% | 발열 패턴 = AP 국부 발열 (불균일 열응력 집중) | **AP On/Off 시험** + DeathMarker 앱 | 신뢰성 PPT slide 7-9 |
| **#2 FPCB 굴곡 수명** | FPCB | 빠른 굴곡, 20만회 Pass | 시장 7만회 미만 (3배 Gap) | 점탄성 Creep — 굴곡 유지 시간 영향 | **15s On / 15s Off** | 신뢰성 PPT slide 10-11 |

### B-2. 신규 제안 (`신뢰성시험혁신전략.pptx` slide 12-15)

| 신규 과제 | 부품 | 핵심 문제 | 솔루션 / 시뮬 |
|---|---|---|---|
| **디스플레이 굴곡 수명** | Display | 1.8m 낙하 (HW 파괴) / 1.5m (Glass crack) + 6면 낙하 복불복 | 강성의 역설 — Crack Arrest 설계 (점탄성 보강), Panel 응력 10% 감소 → 불량 40~60% 개선 (Weibull m=6/m=8) |

### B-3. 디스플레이 면품질 5 AI (`KooDynaAdvanced/디스플레이_면품질_확인과제_제안서.docx`)

| AI | 확인 항목 | 시뮬/시험 | 데이터 요구 |
|---|---|---|---|
| AI-1 | 두께 편차 따른 압착 품질 | 그룹 A/B/C 압착 시험 | 단품 두께 측정값, 배치 정보 |
| AI-2 | 면품질 패턴별 그룹 압착 | 패턴 분류 (중앙 솟음/가장자리 들뜸/웨이브) | 단품 스캔 데이터 |
| AI-3 | **단품 ↔ 세트 연관관계** | 다량 측정 + 이력 추적 | 최소 수백 건 + OK/NG |
| AI-4 | 공정 조건 보상 가능성 | 압력/온도/시간/쿠션재 변경 | 공정 조건 기록 |
| AI-5 | 압착 지그 위치별 편차 | 슬롯 위치 기록 | 위치별 면품질 |

### B-4. 시뮬 유형 3종 (`디지털트윈_낙하시뮬레이션_PT자료_상세.docx`)

| 유형 | 케이스 수 | 목적 | 인프라 |
|---|---|---|---|
| **단일 낙하 (Single)** | 1 | 규격 시험 조건 (Face/Edge/Corner) 상세 분석 | 128 core / 1건 |
| **전각도 낙하 (Full-Angle)** | **2,592** (θ=72×φ=36, 5° 간격) | 시장 불량 모드 사전 예측 | 346 node × 128 core = 44,288 core (8 round) |
| **누적 낙하 (Cumulative)** | N 회 (100/200) | 신뢰성 시험 사전 예측 / 사용자 패턴 (연 50회 일반 / 150회 Heavy) | step-wise dynain chain |

---

## C. 갤럭시 모델 × AP 분배 (deep-research, verified)

> 시뮬 설계자가 LSI/QC 양쪽 시뮬 필요한지 즉시 판단할 수 있도록 정리. 자세한 표/citations 는 §대화 reference 참조.

### C-1. S 시리즈 (Bar)

| 출시 | 모델 | LSI 향 (Exynos) | QC 향 (Snapdragon) | 시뮬 분리 필요? |
|---|---|---|---|---|
| 2020-03 | S20 / 20+ / 20 Ultra | 990 → EU, IN, LATAM, ROW | 865 → KR, US, CA, CN, JP | **YES (양쪽)** |
| 2020-10 | S20 FE | 990 → EU(4G), IN, ROW | 865 → KR, US, CA, CN, JP, EU(5G) | YES |
| 2021-01 | S21 / 21+ / 21 Ultra | 2100 → KR, EU, IN, LATAM, ROW | 888 → US, CA, CN, HK, TW, JP | YES |
| 2022-01 | S21 FE | 2100 → KR, IN, LATAM, JP | 888 → US, CA, CN, EU | YES |
| 2022-02 | S22 / 22+ / 22 Ultra | 2200 → EU, ROW | 8 Gen 1 → KR, US, CN, JP, IN, LATAM, AU | YES (마지막 LSI/QC Ultra) |
| **2023-02** | **S23 / 23+ / 23 Ultra** | — | **8 Gen 2 for Galaxy → Global** | **NO (단일)** |
| 2024-01 | S24 / S24+ | **2400 for Galaxy** → KR, EU, IN, ROW | 8 Gen 3 for Galaxy → US, CN, JP, LATAM | **YES (LSI 복귀)** |
| 2024-01 | S24 Ultra | — | 8 Gen 3 for Galaxy → Global | NO |
| 2025-01 | S25 / 25+ / 25 Ultra | — | **8 Elite for Galaxy → Global** | NO |

### C-2. Z Flip 시리즈

| 출시 | 모델 | SoC | 시뮬 분리 |
|---|---|---|---|
| 2020-02 | Z Flip | SD 855+ | Global 단일 |
| 2020-08 | Z Flip 5G | SD 865+ | Global 단일 |
| 2021-08 | Z Flip3 | SD 888 | Global 단일 |
| 2022-08 | Z Flip4 | SD 8+ Gen 1 | Global 단일 |
| 2023-08 | Z Flip5 | SD 8 Gen 2 for Galaxy | Global 단일 |
| 2024-07 | Z Flip6 | SD 8 Gen 3 for Galaxy | Global 단일 |
| **2025-07** | **Z Flip7** | **Exynos 2500** (Flip 최초 LSI) | Global 단일 (LSI) |

### C-3. Z Fold 시리즈

| 출시 | 모델 | SoC | 시뮬 분리 |
|---|---|---|---|
| 2020-09 | Z Fold2 | SD 865+ | Global 단일 |
| 2021-08 | Z Fold3 | SD 888 | Global 단일 |
| 2022-08 | Z Fold4 | SD 8+ Gen 1 | Global 단일 |
| 2023-08 | Z Fold5 | SD 8 Gen 2 for Galaxy | Global 단일 |
| 2024-07 | Z Fold6 | SD 8 Gen 3 for Galaxy | Global 단일 |
| 2025-07 | **Z Fold7** | SD 8 Elite for Galaxy (Flip7 와 대조) | Global 단일 (QC) |

---

## D. 시뮬 계획서 작성용 빈칸 framework

> 위 A/B/C 를 보고 사용자가 다음 표 채워서 PT 슬라이드/계획서 만들면 됨.

```
| # | 모델 | 출시 연도 | AP 향 | 부품/도메인 | 과제명 | 시뮬 유형 | 케이스 수 | 인프라 | 진행 기간 | 담당 | 결과/이슈 |
|---|------|---------|------|----------|------|--------|---------|------|---------|------|---------|
| 1 | S20 Ultra | 2020 | LSI 990 (EU 향)   | AP    | [채움] | 단일/전각도/누적/On-Off 등 | [채움] | 128c × N | YYYY-MM | [채움] | [채움] |
| 2 | S20 Ultra | 2020 | QC 865 (US 향)    | AP    | [채움] | ...                       | ...    | ...      | ...     | ...    | ...    |
| 3 | S21 Ultra | 2021 | LSI 2100         | FPCB  | [채움] | 굴곡 15s On/Off          | ...    | ...      | ...     | ...    | ...    |
| 4 | ...       | ...  | ...              | ...   | ...    | ...                       | ...    | ...      | ...     | ...    | ...    |
```

### D-1. 시뮬 유형 enum (선택지)

- **단일 낙하** (Face/Edge/Corner)
- **전각도 낙하** (2,592 / Fibonacci 100 / Fibonacci 6° / Fibonacci 2°)
- **누적 낙하** (100회 / 200회 / Heavy user 150회)
- **AP On/Off** (열-기계 연성)
- **FPCB 굴곡 15s On/Off** (Creep 반영)
- **디스플레이 굴곡 수명** (Crack Arrest 검증)
- **부분 충격 DOE** (5×5 grid 등)
- **힌지 피로** (0/90/180° 4축)
- **배터리 압괴** (stacked / wound)
- **면품질 압착** (5 AI)
- **방열 (VC)** (베이퍼 챔버 vs 동판)
- **Warpage** (적층 휨)
- **진동** (eigenvalue / modal / FRB / floor wave)
- **Shield can 성형** (stamping + 변형)
- **테이프 굴곡** (점탄성)
- **고무 재료** (EFG / locking / inverse)
- **표준 인장** (ASTM E8)

### D-2. 부품/도메인 enum

- AP (LSI/QC), PBA, FPCB, Display Panel, Display 적층, Glass / Cover Glass, Battery (cell / pack), Hinge, Shield Can, Tape (battery / display), Cushion, Rubber 재료, EMI/EMC, VC (베이퍼 챔버) / 방열, 카메라 모듈, Sub-PBA

### D-3. 인프라 옵션

- 단일: 128 core / 1건 (~4시간)
- 병렬: 346 node × 128 core = 44,288 core (~8 round 로 2,592 case 완료)
- License: 44,288 core (86배 확대)

---

## 출처 / 인용

### 환경 자료 (직접 inventory)

- `/data/*_study/` (15 디렉토리 — battery 161, shield_can 138, floor_wave 149, tape 42, realistic_rebound 24, cms 24, soft1 15, vapor_chamber 13, level 13, tet10_elform 12, astm_e8 11, foldable_hinge 8, warpage 7, rubber 6, fmbd 5)
- `/data/koodyna_reports/` (ball_drop_v1~7, peridynamics, alt_ale/efg/spg/sph 등)
- `/data/koopark/Test_*` + `/data/Tests/Test_*` (DOE/검증 testset)

### PT/PPT/docx 자료

- `Downloads/디지털트윈_낙하시뮬레이션_PT자료_상세.docx` — 시뮬 유형 3종 + 인프라
- `Downloads/신뢰성시험혁신전략.pptx` — 성공 사례 #1 AP Ball Crack, #2 FPCB, 신규 디스플레이 굴곡
- `STCStrategy/전각도_낙하_시뮬레이션_자동화_소프트웨어_소개_v2.docx` — 5개 SW 시스템
- `KooDynaAdvanced/디스플레이_면품질_확인과제_제안서.docx` — 5 AI

### 갤럭시 모델 × AP (deep-research, verified)

- [Samsung Galaxy S20 — Wikipedia](https://en.wikipedia.org/wiki/Samsung_Galaxy_S20)
- [Samsung Galaxy S21 — Wikipedia](https://en.wikipedia.org/wiki/Samsung_Galaxy_S21)
- [Samsung Galaxy S22 — Wikipedia](https://en.wikipedia.org/wiki/Samsung_Galaxy_S22)
- [Samsung Galaxy S23 — Wikipedia](https://en.wikipedia.org/wiki/Samsung_Galaxy_S23) — S23 SD 단독
- [Samsung Galaxy S24 — Wikipedia](https://en.wikipedia.org/wiki/Samsung_Galaxy_S24) — S24/24+ Exynos 2400 복귀, Ultra QC 단독
- [Samsung Galaxy S25 — Wikipedia](https://en.wikipedia.org/wiki/Samsung_Galaxy_S25) — SD 8 Elite Global 단독
- [Samsung Galaxy Z Flip7 — Wikipedia](https://en.wikipedia.org/wiki/Samsung_Galaxy_Z_Flip7) — Exynos 2500 단독 (Flip 최초 LSI)
- [Exynos 990 vs SD865 PhoneArena](https://www.phonearena.com/news/Galaxy-S20-Ultra-Exynos-vs-Snapdragon-battery-life_id123572) — 배터리 -25~27%
- [Qualcomm — SD 8 Gen 2/3/Elite for Galaxy](https://www.qualcomm.com/news/releases/2023/02/qualcomm-and-samsung-extend-snapdragon-platform-collaboration)
- [AnandTech — Exynos 990 Deep Dive](https://www.anandtech.com/show/15446/the-exynos-990-anandtech-deep-dive)
- [SamMobile — Exynos 2500 3nm SF3 yield](https://www.sammobile.com/news/exynos-2500-galaxy-s25-3nm-yield-issues/)
- [XDA — S21 FE variants](https://www.xda-developers.com/samsung-galaxy-s21-fe-snapdragon-888-vs-exynos-2100/)
- [GSMArena — Samsung phones](https://www.gsmarena.com/samsung-phones-9.php)

---

## 활용 방법

1. **A 표** 에서 — 이미 진행한/완료된 study 가 어떤 카테고리인지 확인 → 재사용 가능 자산 파악
2. **B 표** 에서 — 어떤 사례/신규 제안이 있는지 → 시뮬 유형/이슈 선택
3. **C 표** 에서 — 모델별 LSI/QC 양쪽 시뮬 필요한지 즉시 판단
4. **D 빈칸** 에 — 회사 내부 자료 (Confluence/SharePoint/CAE팀 트래킹) 보고 채움 → 시뮬 계획서/PT 슬라이드 직행

본 문서는 사용자 환경의 진행 과제 + 공개 모델 정보 reference. **실제 과제 history (모델별 진행 트래킹)** 는 회사 내부 자료를 D 표에 매핑해야 완성.
