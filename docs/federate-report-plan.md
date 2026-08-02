# Federate Report — 리비전 연합 비교 보고서 계획서

같은 종류의 보고서 N개(서로 다른 리비전의 전각도 낙하 / 전위치 부분충격)를 입력으로
받아 **하나의 비교 보고서**를 자동 생성한다. 입력은 이미 존재하는 기계가독 sidecar
(impact `impact_payload.json`, sphere `report.json`)만 사용 — 원시 d3plot/binout 에
접근하지 않는 **독립 경량 모듈**이다.

---

## 0. 입력 YAML 스키마 (확정 제안)

```yaml
# federate.yaml — 리비전 연합 비교 설정
kind: auto                      # auto | sphere | impact  (auto = sidecar 내용으로 판별.
                                #  혼합 입력은 hard error — sphere 와 impact 는 비교 불가)
baseline: 1                     # 기준 리비전 (reports 의 1-based 순번). 모든 Δ 의 기준
output: federate_report.html

reports:                        # 순서가 곧 리비전 축 (추이 그래프의 x 순서)
  - path: /data/proj/revA/impact_payload.json
    label: "RevA (5월 양산)"     # 생략 시 provenance→디렉터리명 순 fallback
  - path: /data/proj/revB/impact_payload.json
    label: "RevB"
  - path: /data/proj/revC/impact_payload.json
    label: "RevC (+리브 보강)"

options:
  auto_match_identical: true    # 이름이 완전히 같은 파트는 매칭표 없이 자동 매칭
  name_normalize: true          # 정규화 후 비교 (대소문자/공백/'\'·'/' 통일)
  unmatched: show               # show | hide | error — 미매칭 파트 처리
                                #  show = '미매칭' 섹션에 리비전별로 정직하게 나열
  resample: idw                 # idw | nearest | off — DOE 격자(각도/위치)가 리비전마다
                                #  다를 때 공통 격자 리샘플. off = 교집합 지점만 비교
  trust_gate: true              # 한쪽이라도 no-contact/에너지게이트 FAIL 인 셀의 Δ 는
                                #  수치 대신 '미판정' 마킹 (오염 Δ 방지)
  unit_policy: error            # error | convert — 리비전 간 unit system 불일치 시.
                                #  convert 는 acc/stress 등 알려진 축만 환산

parts:                          # 파트 매칭표 — 값은 reports 순서대로 콤마 구분
  # canonical표시명: rev1이름, rev2이름, rev3이름   (~ 또는 빈칸 = 그 리비전에 없음)
  Display:  "Display\\Display, DISP_MAIN, Display\\Display"
  PCB:      "PCB\\PCB, MainPCB, PCB\\PCB"
  Battery:  "BAT\\Cell, BAT\\Cell, ~"
  # auto_match_identical: true 면 여기 없는 동일 이름 파트는 자동으로 붙는다.
  # 매칭표가 자동 매칭과 충돌하면 매칭표가 이긴다 (명시 > 암묵).
```

설계 근거.
- **sidecar 만 입력**: impact 는 payload 전체(positions/results/doe_analysis/
  solver_quality/unit_labels/provenance), sphere 는 각도별·파트별 피크+카테고리+
  findings 를 이미 담고 있음(2026-07 실사 확인). 원시 데이터 재파싱 없음 → 모듈이
  가볍고, 서로 다른 머신에서 만든 보고서도 파일만 모으면 비교 가능.
- **순번(1-based)** 이 YAML 전반의 공통 키 (baseline, parts 콤마 순서).
- `~`(YAML null) 로 "이 리비전엔 이 파트 없음"을 명시 — 파트 추가/삭제 이력도
  비교 대상이다 (신규 파트는 '추가됨' 뱃지로 표시).

---

## 1. 핵심 문제 — "N개 리비전을 어떻게 한 화면에서 비교하나"

2개면 나란히 놓으면 되지만 5개 구면 맵을 나란히 놓고 눈으로 비교하는 것은 불가능
하다(사용자 지적). SOTA 접근은 **"N장의 지도를 보여주지 말고, 질문에 답하는 1장의
합성 지도를 만들어라"** 이다. 연합 보고서가 답해야 할 질문과 그에 대응하는 뷰:

| 엔지니어의 질문 | 합성 뷰 (지도 1장/차트 1개) |
|---|---|
| 리비전 간 **크기·교차·개선폭**을 한눈에 | **UNROLLED PROFILE (주력)** — 각도/위치를 X축으로 전개, 리비전 = 겹침 선. X 정렬은 baseline 심각도 내림차순 기본(왼쪽=최악), sphere 는 카테고리 밴드 구획, impact 는 심각도순/서펜타인 토글. 절대 모드 + Δ 모드(baseline=0선) + log 토글. N 이 늘어도 무너지지 않는 유일한 원본값 뷰 |
| 어느 방향/위치에서 **어느 리비전이 최악**인가 | **WINNER MAP** — 셀 색 = 최악 리비전(리비전별 고정색), 명도 = 그 최악값. 범례가 곧 리비전 색표 |
| 리비전이 진행되며 **어디가 좋아지고 어디가 나빠졌나** | **TREND MAP** — 셀값 = 리비전 순서에 대한 회귀 기울기(정규화). 파랑=개선, 빨강=악화, 회색=변화없음. 설계 반복의 핵심 뷰 |
| 기준(baseline) 대비 **얼마나** 달라졌나 | **Δ MAP (vs baseline)** — 발산 컬러맵. N-1 장이지만 전부 같은 스케일·같은 기준이라 스캔 가능. 탭/드롭다운으로 리비전 선택 |
| 리비전 간 **가장 민감한(들쭉날쭉한) 방향**은 | **SPREAD MAP** — 셀값 = max−min (또는 CV). 여기가 재검토 1순위 방향 |
| 특정 방향의 N개 값을 정확히 | **linked probe** — 어떤 지도든 hover/클릭하면 사이드 패널에 그 방향의 리비전별 바 차트 + 수치. "지도 5장 비교"를 "한 점의 5값 비교"로 환원 |
| **파트별로** 리비전 추이는 | **PART TREND TABLE** — 행=매칭 파트, 열=리비전, 셀=worst 피크 + 인라인 스파크라인, Δ% vs baseline 정렬. "어떤 파트가 나빠졌나"의 즉답 |
| worst 순위가 **뒤바뀌었나** | **RANK BUMP CHART** — 파트 worst 순위의 리비전 간 이동(범프 차트). 교차 = 설계 변경의 부작용 신호 |
| findings 는 무엇이 **생기고 사라졌나** | **FINDINGS DIFF** — baseline 대비 신규(+)/해소(−)/유지 3분류 목록 |

원칙: **전개 프로파일이 크기 비교의 주력**, 합성 지도 4종은 공간 패턴(어디에
몰렸나) 담당 — 프로파일은 공간 인접성을 버리므로 서로의 맹점을 보완한다. 두 축은
linked probe 를 공유(프로파일 x지점 클릭 = 지도 같은 방향 하이라이트). 소지도
(small multiples)는 탐색용 썸네일로만. N=2 에서는 TREND==Δ 이므로
TREND 를 숨기고 Δ 를 전면에 (N 에 따른 뷰 자동 강등).

### sphere 특화
- 방향 격자: 리비전마다 각도 DOE 가 다를 수 있음 → 구면 IDW(repo 에 기구현)로
  공통 Fibonacci 격자에 리샘플. **실측점은 링 마커, 보간 셀은 채도 강등** —
  보간을 실측처럼 보이게 하지 않는다 (정직성 원칙).
- 카테고리(face/edge/corner/arbitrary)별 소계 비교 막대 — "코너 낙하만 나빠졌다"
  같은 구조적 회귀를 즉답.

### impact(전위치 부분충격) 특화 — sphere 보다 데이터가 풍부해 비교 축이 더 많다

impact_payload.json 은 위치별 worst 만이 아니라 (위치×파트) 쌍 응답 매트릭스,
per-position solver_quality, behavior 분류, 에너지 흐름, part_motion 시계열까지
담고 있다. v1 범위와 후속을 명시해 구체화한다.

**v1 (필수)**
- XY 합성 지도 4종 (winner/trend/Δ/spread) — 2D 히트맵이라 sphere 보다 단순.
- 위치 매칭: 좌표 완전 일치 → 그대로, 불일치 → `resample` 정책 (nearest 허용
  반경 = 격자 간격의 40%, 초과 시 미매칭). **face 불일치**(revA=F5, revB=F1)는
  face 별 그룹 비교 — 같은 face 끼리만 짝짓고, 한쪽에만 있는 face 는 '비교 불가'
  섹션에 명시 (에러가 아니라 정직한 부분 비교).
- **behavior 전이 매트릭스** — impact 최우선 발견. 리비전 간 no-contact↔bounce↔
  rebound 전이를 위치별로 표시. 예: revA 미접촉 16/25 가 revB 에서 전부 접촉이
  됐다면(DOE 조준 수정) 그것이 Δ 지도보다 앞서는 **헤드라인**이고, 이 경우 Δ 는
  "비교 기준 자체가 달라짐" 경고와 함께 표시.
- **유효 비교 교집합 KPI** — trust_gate 의 확장. "Δ 판정 가능 위치 9/25"
  (양쪽 모두 유효 접촉 + PASS 인 교집합) 를 s1 KPI 로 정면 노출. 교집합이 0 이면
  지도 대신 behavior 전이 매트릭스만 출력.
- **(위치×파트) 매트릭스 Δ** — 히트맵 행=매칭 파트, 열=위치, 셀=Δ%. "위치
  (20,40)에서 Display 만 나빠졌다" 수준의 국소 회귀 검출. sphere 의 파트 추이
  테이블보다 한 단계 정밀한 impact 전용 뷰.
- **trust_gate**: 한쪽이라도 no-contact/FAIL 인 셀의 Δ 는 수치 대신 빗금
  '미판정' — FAIL 런 Δ 를 개선/악화로 오독하는 것을 구조적으로 차단.
- **energy Δ 스칼라**: 위치별 diss% Δ + ke_retention Δ (trajectory_summary 재사용)
  — 접촉 강도의 리비전 변화를 스칼라로.
- DWI 레이아웃 산출물도 동일 sidecar 스키마 → 자동 지원 (별도 코드 없음).

**후속 (v1 제외, 계획만)**
- **시계열 겹침 드릴다운** — 위치 클릭 → 매칭 파트의 acc(t) 곡선을 리비전 N개
  겹침 (part_motion 시계열이 sidecar 에 있어 가능). tier C/D 는 청크 의존이라
  "sidecar 만 입력" 원칙과 충돌 — 청크 디렉터리 동반 입력 규칙 정의 후 v2.
- **에너지 흐름 그래프 비교** — SANKEY/RESIDENCE 의 리비전 겹침. v1 은 스칼라만.
- **TOA 전파 순서 변화** — first-arrival 파트가 바뀐 위치 표시.

---

## 2. 정직성 규칙 (연합 특유의 함정)

1. **단위계 불일치**: 리비전마다 unit_labels 가 다를 수 있다(SI vs ton-mm-s).
   기본 error, `unit_policy: convert` 시 acc/stress/disp 알려진 축만 환산하고
   보고서 헤더에 "환산됨" 배지.
2. **스키마 버전**: sidecar schema_version 불일치 → 명시 에러 (조용한 오비교 금지).
3. **DOE 커버리지 차이**: revA 는 512각도, revB 는 26각도라면 Δ/TREND 는 교집합
   신뢰도가 낮다 — 커버리지 비율을 KPI 로 노출("비교 가능 방향 26/512")하고
   spread/trend 는 교집합에서만 계산.
4. **provenance 승계**: 각 리비전의 tool_version/생성시각/입력 digest 를 부록 표로 —
   "무엇과 무엇을 비교했는지"가 보고서 안에 남아야 한다.
5. **절대 임계값 발명 금지**: 개선/악화 판정색은 Δ 부호와 크기 분위수만 사용.
   "몇 % 이상이 유의미한 악화"는 사용자가 `--delta-warn` 류로 줄 때만.

---

## 3. 아키텍처 — 독립 경량 모듈

```
python/koo_federate_report/
├── koo_federate_report/
│   ├── __main__.py          # CLI: python -m koo_federate_report --config federate.yaml
│   ├── config.py            # YAML 로드/검증 (스키마 §0, 친절한 에러)
│   ├── adapters/
│   │   ├── impact.py        # impact_payload.json → RevisionBundle
│   │   └── sphere.py        # sphere report.json → RevisionBundle
│   ├── models.py            # RevisionBundle(meta, parts, field_samples, kpi,
│   │                        #   trust, findings), FederatedSet
│   ├── matching.py          # 파트 매칭 (YAML 표 + auto identical + normalize)
│   ├── resample.py          # 공통 격자 리샘플 (구면 IDW / XY nearest) + 실측 마스크
│   ├── compare.py           # winner/trend/Δ/spread 필드, 파트 추이, rank shift,
│   │                        #   findings diff, trust gate
│   └── report/
│       ├── html_report.py   # 단일파일 HTML (기존 다크 Bloomberg 디자인 언어 재사용)
│       └── sections…        # s1 요약Δ / s2 합성지도 / s3 파트추이 / s4 findings diff
│                            #   / s5 provenance 부록
└── tests/
    ├── test_matching.py
    ├── test_compare.py      # 손계산 winner/trend/Δ 픽스처
    └── test_golden_federate.py  # 합성 2리비전(generate_sample seed 42 vs 7) 골든
```

- **의존성**: PyYAML + 표준 라이브러리만 (numpy 는 sphere 리샘플에 한해). deep/
  impact/sphere 패키지 import 없음 — sidecar 스키마만이 계약.
- **SIF 통합**: build_module.sh 의 4번째 wrapper (`koo_federate_report`) + PYTHONPATH
  1줄 — 기존 3개 wrapper 패턴 그대로.
- 대용량: 리비전당 payload ≤ 수 MB(이미 tier 축소본) → N=5 도 메모리 무해.
  연합 HTML 도 tier 정책 재사용(합성 지도들은 이미 집계라 가볍다).

## 4. 구현 단계 (커밋 단위)

| 단계 | 내용 | 검증 |
|---|---|---|
| F1 | config+adapters+models — 두 sidecar 를 RevisionBundle 로 정규화 | 실데이터 각 1쌍 로드 스모크 + 단위/스키마 가드 테스트 |
| F2 | matching — 매칭표/auto/normalize/미매칭 | 손계산 픽스처 pytest |
| F3 | compare — Δ/winner/trend/spread + 파트추이 + rank + findings diff + trust gate | 손계산 (3리비전 × 4셀) 전 수치 검증 |
| F4 | resample — 구면 IDW·XY nearest + 실측 마스크 | 격자 다른 합성쌍, 보간 마스크 불변식 |
| F5 | HTML 보고서 (linked probe 포함) | Playwright 콘솔 0 + 합성쌍 육안 포인트 |
| F6 | 골든(합성 2·3리비전 결정적) + build_module wrapper + 문서 | 골든 2회 결정성, SIF 빌드 테스트 |

검증 데이터: 합성 — `generate_sample --seed 42` vs `--seed 7`(같은 격자, 값만 다름)
+ `--grid` 로 격자 다른 쌍. 실데이터 — Test_Impact_A(리비전 1개뿐이므로 자기 자신
vs sidecar 수정본으로 스모크; 실제 2리비전 데이터가 생기면 V-real 추가).

## 5. 하지 않을 것

- 원시 d3plot/binout 재파싱 (sidecar 계약만).
- sphere↔impact 교차 비교 (물리적으로 다른 시험 — 명시 에러).
- 3D 구면 나란히 회전 동기화 뷰 (화려하나 N>2 에서 무력 — probe 가 대체).
- 리비전 자동 발견/스캔 (경로는 YAML 명시가 정답 — 잘못 짝지어진 비교 방지).
