# Federate Report — 컨텍스트 노트 (결정 기록)

계획: `federate-report-plan.md`. 체크리스트: `federate-report-checklist.md`.

## F1~F4 (엔진) — 2026-08-02

### 정규화 모델 (models.py)
- sphere/impact 를 `cells`(비교 축 1지점) + `part_cells`((cell_key, 파트이름) → 지표)
  두 구조로 접었다. matching/resample/compare 는 kind 를 거의 보지 않는다.
- `part_cells` 의 파트 이름은 **그 리비전 고유 이름**이다. canonical 환원은
  matching 이 만든 매핑을 compare 가 적용한다 (어댑터가 canonical 을 알 필요 없음).
- 비교 주 지표는 `g`(peak acc) 기본, CLA `--metric` 으로 s/e/d 선택. `per_rev.value` 는
  주 지표, `per_rev.values` 는 4지표 전부 — HTML 이 지표 토글을 만들 수 있게.

### trust (impact)
- `ok = (summary.impact_visible is not False) and pass_fail != 'FAIL'`.
- sphere sidecar 에는 게이트가 없으므로 항상 `ok=True / reason='no gate'`.
  없는 게이트를 있는 척하지 않는다.
- **게이트는 판정만 막고 값은 숨기지 않는다.** 셀의 `per_rev[].value` 는 그대로 두고
  `delta / delta_pct / winner / trend / spread` 만 None + `gate_reason`.
  winner 까지 막은 이유: 오염된 수치로 뽑은 "최악 리비전"도 판정이기 때문.

### 파트 집계 기준 (compare)
- 파트 worst 는 **미판정 셀을 전 리비전에서 똑같이 제외**하고 집계한다.
  리비전마다 다른 셀 집합으로 max 를 잡으면 파트 Δ 가 오염된다.
- `rank` 1 = 가장 나쁨. `rank_delta = rank_i − rank_baseline`,
  양수 = worst 순위에서 내려감(상대적 개선).
- `trend` = 리비전 순번에 대한 최소제곱 기울기를 **baseline 값으로 정규화**
  (Δ% 와 같은 기준). 원기울기는 `trend_abs` 로 별도 보존.
- `spread.cv` 는 모집단 표준편차(pstdev)/|mean| — 리비전 N개는 표본이 아니라 전수.

### resample
- 모든 리비전 격자가 동일하면 모드와 무관하게 `identity` — 불필요한 보간 금지.
- `measured=True` 는 **그 좌표에서 실제로 계산된 값**일 때만. `nearest` 는 다른 좌표의
  실측을 끌어온 것이므로 `measured=False` + `offset` 기록. 보간을 실측처럼 보이면 안 된다.
- 각도 일치 판정 허용치 `_ANGLE_EXACT_DEG = 1e-3°`. sidecar 가 각도를 소수 4자리로
  저장하므로 1e-6° 로 보면 사실상 같은 방향도 '보간'으로 강등된다. 실제 DOE 최소
  간격(수 도)보다 3~4자릿수 작아 오검출 위험 없음.
- impact 에 `resample: idw` 를 주면 nearest 로 대체하고 `resample_fallback` 경고.
- IDW 는 순수 파이썬(역거리가중, k=4, p=2). numpy 의존을 넣지 않았다 —
  격자 크기가 수백 점이라 성능 문제가 없고 의존성은 PyYAML 하나로 끝난다.

### 의존성·계약
- PyYAML + 표준 라이브러리만. koo_impact/sphere/deep 패키지 import 없음 (sidecar 스키마가 계약).
- compare 반환 dict 가 HTML 의 payload 계약. 최상위 키:
  `kind / baseline_idx / schema_version / metric / unit_labels / revisions / cells /
   parts / part_matrix / behavior_transitions / findings_diff / kpi / coverage /
   unmatched / warnings / provenance`.
- CLI 는 payload JSON 을 **HTML 렌더보다 먼저** 쓴다 — 렌더가 실패해도 비교 결과는 남는다.

### 실데이터 검증 (Test_Impact_A 3리비전)
- 25 위치 × 3 리비전, 격자 동일 → identity, 커버리지 100%.
- `trust_gate: true` 에서 **Δ 판정 가능 0/25**. 원인은 데이터 자체 —
  16개는 no-contact(impact_visible=False), 9개는 solver_quality FAIL(HG/TE/SL 게이트).
  교집합이 0 이므로 `no_comparable_cells` ERROR 경고가 헤드라인이 되는 것이 정답이다.
- revB 는 파트가 개명되어 있어(`Display\Display`→`DISP_MAIN`, `PCB\PCB`→`MainPCB`)
  매칭표 없이는 미매칭 2개가 발생한다 — 매칭표를 넣으면 canonical 25개 전부 매칭.

---

## 2026-08-02 — 실데이터 결함 6건 (계속 파기 라운드)

합성 골든만으로는 안 잡히고 **실측 sidecar 를 통과시켜야 드러난** 것들이다.
공통 교훈: 골든이 그 경로에 데이터를 안 태우면 코드는 잠기지 않는다.

### 1. findings 차분 이중 계상 (18eca21)
- title 전문을 동일성 키로 써서 `접촉 미발생 런 16/25` → `14/25` 가 신규+해소로
  두 번 세졌다. 실데이터 13건 중 4건이 허수 8건으로 부풀었다.
- 안정 키는 **측정값만** 자리표시자로 치환한다(`n/N`, `|z|=x.y`, 소수). 숫자를
  전부 지우면 반대로 `F5_DOE_024` / `_019` 같은 별개 outlier 9건이 1건으로
  과잉 병합된다 — 식별자는 반드시 보존.
- 키 충돌로 건수가 줄면 `findings_key_collision` 경고. 조용한 소실 금지.

### 2. WINNER 라벨 (18eca21)
- `winner = max(values)` 는 **최악** 리비전 인덱스인데 영문 타이틀이 "WINNER MAP"
  이라 훑어보면 정반대로 읽혔다. 한글 설명("최악 리비전")만 맞았다. → WORST-REV.

### 3. 카테고리 소계가 죽어 있었다 (7afd1fd)
- 구면 보고서의 `angle.category` 는 `"fibonacci"` — **격자 생성 방식**이지 기하
  분류가 아니다. 1144각도 전부 한 종류라 엔진이 규칙대로 빈 dict 를 냈고,
  face/edge/corner 소계는 실데이터에서 영영 뜨지 않았다.
- 보고서 카테고리가 1종뿐일 때만 낙하 방향에서 파생한다. 임계값은 발명하지
  않는다 — 26개 기준 방향(면6·모서리12·꼭짓점8) 최근접 배정이라 경계는 Voronoi.
  `category_source` 로 파생 여부를 payload/화면에 명시.
- 실측: 면 247 / 모서리 414 / 꼭짓점 254, 꼭짓점이 RevB 에서 -19.1% 로 최대 개선.

### 4. 헤드라인 worst 가 참피크보다 40~46% 낮았다 (2c061c2) ★ 최대 결함
- 공통 Fibonacci 격자(915점)는 baseline 자신의 1144각도와도 어긋나 **실측률 0%**.
  IDW 는 이웃 가중평균이라 피크를 넘지 못하므로 격자 worst 는 항상 참피크 이하다.
- 결론까지 뒤집혔다: 격자 기준 RevC 는 +5.2% 악화, 참피크 기준 -1.0% (무변화).
- `true_peak_per_rev / true_peak_cell / true_peak_delta_pct / peak_damping_pct /
  measured_pct` 를 kpi 에 싣고 s1 첫 행을 "참피크(실측)" 로. 시계열의
  **다운샘플 전 참피크** 규칙을 공간축에 그대로 적용한 것.
- 불변식(재기록 불가): `격자 worst ≤ 참피크`.

### 5. sphere acc 단위가 1e6 배 과대 (2c061c2)
- `peak_g` 는 **G 로 저장**된다(loader: `abs_acc / G_FACTOR`). 구면 보고서 화면의
  "MG" 는 표시할 때 `v/1e6` 을 한 결과지 저장 단위가 아니다. 어댑터가 화면 표기를
  베껴 `unit_labels.acc = "MG"` 로 두는 바람에 1.45e6 에 MG 가 붙었다.
- **기존 계약 테스트가 MG 를 기대값으로 박아 이 버그를 잠그고 있었다.** 테스트가
  버그를 고정하는 전형적 사례 — 기대값의 근거를 주석에 남길 것.

### 6. 파트 빈 칸의 이유가 뭉개져 있었다 (4d6b803 → 57024b3)
- `absent`(파트 부재) / `gated`(비교 가능한 셀이 0) / `no_metric`(지표 미기록) 셋이
  전부 `—` 로 나갔다. 구면 23개 중 6개가 no_metric(Display/PCB/Bond …),
  impact 는 25위치 전량 미판정이라 48칸 전부 gated.
- 1차 수정에서 gated 를 빠뜨려 impact 파트 전부에 "지표 없음" 을 달았다(오표기).
  경고/KPI 는 `no_metric` 만 센다.

### 7. 예제 YAML 이 최악 모드를 권했다 (c16d668)
- `examples/federate_sphere.yaml` 이 `resample: idw` 를 권장했는데, 같은 데이터를
  엔진 기본값 `nearest` 로 돌리면 실측 100/100/80%, 감쇠 0%, 짝 없는 229셀은
  정직하게 미판정이다. idw 는 "커버리지 100%" 를 신뢰도처럼 보이게 만든다.
- 실측률 0% 이면 엔진이 `no_measured_cells` WARN 으로 대안까지 알린다.

### 검증 방법 메모
- Playwright 는 `file://` 이 차단돼 `python3 -m http.server` 로 띄워 확인한다.
- 경계 입력 스윕(기준값 0/음수/전부 None/5·10 리비전/셀 0개/중복 라벨)은
  크래시 없음. 음수 지표는 peak 크기값 규약 위반이라 ERROR 경고로 처리.

---

## 2026-08-02 (2차) — sphere 파트 지표 확장 + 접촉력 계측·검증

federate 와 별개로 sphere/deep/impact 본체에 들어간 것들. 다음 세션이 같은 함정을
다시 밟지 않도록 **실측으로 확인한 사실만** 적는다.

### 파이프라인 — 어느 오케스트레이터인지 먼저 확인할 것
운영은 **KooChainRun** 이다. 거기서는 unified_analyzer 가 koo_deep_report **안에서**
돌고(`__main__.py:776` run_analysis), sphere_report.sh 가 `Run_*/Output/report/` 를
`analysis_results/<Run_*>` 로 symlink 해서 읽는다. 즉 **deep 이 선행**이다.
리포 안의 `scripts/post_analyze.sh` 는 별개 오케스트레이터로 순서가 반대
(unified → sphere → deep). 헤더 주석이 옛 순서로 남아 있어 오해를 부르던 것을
0f6290a 에서 교정했다. **어느 쪽을 쓰는지 먼저 묻고 답할 것.**

### skip 판정 — 산출물이 늘면 자동으로 따라오게
양쪽 오케스트레이터 모두 "result.json / analysis_result.json 이 있으면 스킵" 이라
분석기가 새 산출물을 내도 기존 run 이 영원히 옛 산출물로 남았다.
`UA_OUTPUT_SCHEMA`(현재 2) + `.ua_schema` 마커로 바꿨다 — 마커가 없거나 값이 다른
run 만 다시 돈다. **분석기가 산출물을 늘릴 때마다 이 상수를 올릴 것**
(koo_deep_report/__main__.py, scripts/post_analyze.sh 두 곳).

### 파트 지표 — 데이터는 있었고 안 싣고 있었다
- IE/KE: binout matsum 에 201스텝 × 23파트가 있었고 energy_flow_builder 가 이미
  읽고 있었지만 최상위 energy_flows 에만 갇혀 있었다 → 파트 단위로 승격.
- σ1: unified_analyzer 가 von Mises 와 **항상 함께** 계산해 CSV 로 내는데
  (SinglePassAnalyzer.cpp:385 "always alongside von_mises") sphere loader 가
  그 파일을 안 열고 있었다. Test_006 산출물은 2026-02-11 구버전(1.0.0)이라
  CSV 자체가 없다 — 재분석해야 채워진다.
- 요약 스칼라는 **다운샘플 이전 원해상도**에서 뽑는다(프로젝트 공통 규칙).

### 접촉력 계측 — 실측으로 잡은 함정 두 개
1. **큰 쪽 side 로 재야 한다.** SSTYP=5(slave='ALL') 정의는 한쪽이 거의 0 으로만
   기록된다. Test_006 CID 172 는 slave 0.2 / master 36251.5 — slave 를 먼저
   고르면 모델 최대 접촉을 0 으로 측정한다(실제로 그렇게 나왔다).
2. **한쪽만 기록된 접촉은 뉴턴 3법칙 위반이 아니다.** 섞으면 max_rel 이 0.9999992
   가 되어 정상 모델도 늘 실패로 보인다. 빼고 나니 max 1.56e-07 / median 5.4e-08.

**충격량↔운동량 검증은 일부러 넣지 않았다.** rcforc 가 master/slave 를 같은 부호로
기록해 내부 접촉쌍이 상쇄되지 않고 ∫|F|dt 는 방향을 버린다. 실측에서 내부 TIED
25개 합이 Δp 의 280배라 늘 '불일치' 로 나왔다. 늘 실패처럼 보이는 지표는 사람을
검증에서 멀어지게 한다 — 다시 넣고 싶으면 부호 규약부터 확정할 것.

### contact_map 은 덱에 따라 결과가 갈린다
Test_006 구면 덱(TIED_SURFACE_TO_SURFACE 25 + AUTO_S2S 1 + SINGLE_SURFACE 1)에서는
27개 중 25개가 (part,part) 신뢰도 1.00 으로 해결된다. 세그먼트셋(SSTYP=0)도
절점→요소→파트 투표로 잘 풀린다. **"contact_map 이 깨진다" 는 다른 덱 얘기이므로
덱마다 실제로 돌려보고 판단할 것.**

### 규모
1144각도 보고서는 흐름 시계열까지 담으면 100MB 를 넘는다. 상위 60각도만 담는
tier 를 걸되 무엇이 빠졌는지 화면에 적는다. 각도 비교용 스칼라 프로파일
(contact_profile)은 전 각도를 담으므로 비교 자체는 영향 없다.

---

## 2026-08-03 — 변형률 계열: ISTRN 판정과 STRFLG 실측

응력은 von Mises·σ1·σ3 인데 변형률은 eff_plastic 하나뿐이던 원인을 끝까지 팠다.

### ① ISTRN 경계 오류 (src/data/ControlData.cpp)
규격 원문:
  "IDTDT ! 10000 = 1: ... **IDTDT>100**, then this is the value of ISTRN"
  "The value of ISTRN must be computed **if IDTDT<100**"
코드는 `IDTDT >= 100` 이라 `IDTDT==100` 이 읽기 분기를 타 `(100/10000)%10 = 0`
→ ISTRN=0. 그런데 IDTDT==100 은 100 자리 = 1, 곧 "소성 변형률 텐서 기록" 이라
변형률이 **있는** 케이스다. `> 100` 으로 교정.

### ② 고쳤더니 값이 전부 0 이었다 → 가드
Test_006 은 `*DATABASE_EXTENT_BINARY` 의 **STRFLG=10**(소성 변형률 텐서만)이라
일반 변형률 슬롯(NEIPH 여분 6성분)이 비어 있었다. lasso 확인:
`element_solid_strain` shape 정상 / max = 0.
그대로 두면 "변형률 0" 을 참값으로 내보내므로, 전 파트·전 상태가 0 이면
주변형률 결과를 버리고 사유를 출력하는 가드를 넣었다(미기록 ≠ 0).

### ③ STRFLG=1 로 실제 솔버 실행해 관통 확인
`LSDynaBasic_aocc420_ompi4.0.5_mpp_d.sif`, ncpu=4, 정상 종료.
  element_solid_strain max 0 → 0.0364 / IDTDT=0 → ISTRN=1 /
  주변형률 CSV 23파트 / sphere ε1·ε3 23/23 / 콘솔 에러 0
  PID21 ε1 0.01348 · ε3 -0.03692 · σ1 831.7MPa (응력·변형률 순위 일치)

**덱 축소 시 함정** — `*DATABASE_BINARY_D3PLOT` 의 NPLTC(4번째)가 DT 를
덮어쓴다(DT = ENDTIM/NPLTC). DT 만 줄이면 출력이 1e-7 마다 나가 6.9GB 가 된다.
ENDTIM 을 줄일 때 NPLTC 도 같이 줄일 것.

### 남은 것
von Mises 변형률은 계산 코드가 `NodalAverager.cpp` 에 있으나 단면뷰 렌더
전용이라 파트별 시계열 CSV 로는 안 나온다. 넣으려면 SinglePassAnalyzer 에
추가해야 한다.
