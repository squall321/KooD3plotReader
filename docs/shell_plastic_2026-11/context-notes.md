# 결정 기록 — 셸 파트 이력 · 핫스팟 소성 기준

## 출발 (11-07)
- 사용자 「ㄱㄱㄱ」 → 미뤄 둔 항목 세 가지에 모두 추천안을 골랐다 — 셸 이력은 분석기에서, 소성 기준은 추가 + 기본 켬, DropSet 은 없는 것만.
- 셸 파트 그림 자동 선택이 안 되던 것(리포트 그림 꾸러미 context-notes)은 증상이고, 뿌리는 분석기다 —
  `SinglePassAnalyzer::buildElementMapping`(솔리드만) · `analyzePartStatsSequential`(solid_data 가 비면 반환).
  2026-09 무결성 작업은 표시만 고쳤다(셸을 0.00 이 아니라 「계산 안 됨」으로).
- production 빌드(OpenMP)는 `analyzeWithStates` → 상태마다 `analyzePartStatsSequential`. OpenMP 없는 빌드는 `processState` →
  `analyzePartStats`. 파트 통계 루프가 세 벌 복사돼 있어, 셸은 따로 한 함수로 만들어 두 경로에서 부른다.
- 셸 배치는 `accumulateLayeredExtremes` 가 이미 규격대로 해석한다(DCOMP=2 압축 덱 건너뜀, NV2D = MAXINT·(6·IOSHL1 + IOSHL2 + NEIPS)
  + 8·IOSHL3 + 4·IOSHL4 (+12 ISTRN), 두꺼운 셸 NV3DT = 층 + {0,1,12,13}). 이 해석을 도우미로 떼어 두 곳이 같이 쓴다.
- 소성 기준의 재료는 이미 있다 — `elem_eps_max_`(ε_p 이력 최댓값, 상태 1개여도 있음) · `elem_plastic_work_`(∫σ_vm dε_p, 상태 2개 이상).
  시각은 저장하지 않으므로 ε_p 최대가 처음 난 시각을 새로 기록한다.

## mini26 DropSet 복원 (11-07, 사용자 승인)
- `/data/Tests/Test_001_Full26_1Step/output` 런 26개 중 DropSet.json 이 2개뿐(10-28 재구성본). `.work/dropset_restore/` 의 11-03
  재구성본 24개를 `cp -n` 으로 없는 곳에만 넣었다. 런 폴더에 링크 없음 확인. 26/26, 모두 `initial_conditions` 를 읽는다.
- 재구성본은 리포트 HTML 의 DATA 에서 되살린 자세(오일러각) · 파트 이름뿐이고 `_reconstructed` 표식이 있다. 정본은 KMM 재생성.

## 소비자 조사 (11-07, 조사 에이전트)
- 이력 키를 직접 읽는 것은 deep(`_parse_outputs`)뿐. sphere 는 파트별 CSV(`stress/part_<pid>_von_mises.csv` 등), impact 는 deep 을 거쳐
  `stress_history` 를 읽는다 — 셸이 이력에 들어가면 sphere · impact · federate · 캠페인 그림 · 온톨로지에 셸이 새로 나온다.
  impact 는 mtime 으로 옛 analysis_result 를 재사용하므로 재분석 전에는 셸이 안 보인다.
- 솔리드 전용 표시: deep `models.py`(peak_stress=None 주석) · `__main__.py`(peak_stress_reason · 요약 줄) · `html_report.py`
  (noStressNote · 「(솔리드만)」 — 셸 핫스팟이 있으면 무조건 붙는 조건도 있다) · `tests/test_aggregate_stress.py`.
- C++ `extractPeakElementTensors` 는 `stress_history` 의 max_element_id 를 **솔리드 ID 표**로 찾고 solid_data 를 읽는다 — 셸이 들어가면
  셸 ID 가 솔리드로 오독되고 ID 가 겹칠 수 있다. 셸 이력을 넣을 때 반드시 막을 자리.
- 핫스팟 기준 고정 목록: deep CLI 기본값 · `_HOTSPOT_CRITERIA` · 별칭표 · `test_hotspot_wiring.py`(C++ 파서 소스와 대조), deep HTML
  `HS_CRIT_LABEL` · `HS_METRICS`, sphere 3D 뷰어(기준을 안 가려 한 색 척도), 온톨로지 어휘 `cae_hotspot.criterion` 열거값(7종) ·
  stress_max 의 MPa 환산, `campaign_cli._elout_check`(기준 무관하게 von Mises 와 대조).

## ② 핫스팟 소성 기준 (11-07)
- 응력 기준 루프(슬롯 0–6)는 그대로 두고 소성 슬롯(7 · 8)은 루프 뒤 `fillPlasticExtremes` 가 기존 `elem_eps_max_` · `elem_plastic_work_`
  에서 옮긴다. 응력 루프의 `k = 4 … kHotspotCritSlots` 축 성분 루프는 `kHotspotStressCritSlots` 로 묶었다 — 안 묶으면 슬롯 7 · 8 이
  축 성분으로 읽혀 axis_e[3] 를 넘는다.
- **선별** — 소성 기준은 소성 요소만 순위에 든다. 고르는 수는 응력 기준과 같은 「파트 유효 요소 수의 p%」, 모자라면 소성 요소 전부.
  소성 여부는 ε_p 로 본다(plastic_work 도). **바닥 1e-6** (`kHotspotPlasticEpsFloor`) — 0 초과만 보면 Test_006 바닥 파트(ε_p 최대
  3e-12)의 잡음 966개가 덩어리 2개가 됐다. yield_eps_threshold 가 더 크면 그쪽. 파트 소성역 요약(n_yield)은 종전 임계 그대로다.
- 셸 계열 ε_p 는 기존 요약과 같은 **층 평균**이라 plastic_strain 군집에 층(peak_layer)이 없다.
- 2패스: plastic_strain 은 상태별 ε_p(솔리드 word 6, 셸 층 평균)로 낸다. plastic_work 는 누적값이 상태별로 없어 하지 않는다.
- **deep CLI 기본값은 None** — 기준을 안 주면 (von_mises, plastic_strain) 중 엔진이 아는 것만. 옛 엔진에서 고르지도 않은 기본값
  때문에 멈추지 않게. 직접 준 이름은 종전대로 엄격. YAML 이 CLI 빈칸을 채우는 판정(`== "von_mises"`)도 None 기준으로 고쳤다.
- 온톨로지 어휘는 정본 DynaForge 의 바이트 사본이라 여기서 고치지 않는다 — 어휘 밖 기준은 싣지 않고 머리 warnings 에
  「DynaForge 어휘 갱신 필요」. **DynaForge 쪽에 plastic_strain · plastic_work 열거값과 단위(무차원 · 에너지/부피) 추가 요청이 남았다.**
- 검증: `case_dent_center_tetfill` 는 쓸 수 없다 — 700 사이클 오류 종료, d3plot 상태 1개(t=0, 응력 0). 메모의 「검증 덱」 은 틀렸다.
  대신 Test_006 런(992 상태, ε_p 최대 0.0069) — lasso 독립 계산(요소 ε_p 시간 최대 → 파트별 몫 · 바닥 · 컷)과 23개 파트 전부 선별 수 ·
  컷값 10자리 일치(`.work/shell_plastic/indep_eps.py`). 파트 1 · 15 · 22 에서 소성 1위 피크 요소가 응력 1위와 다르다(다른 영역을 잡는다).
  v46 배포 분석기와 같은 런 대조 — 핫스팟 밖 15개 섹션 · von_mises 항목 23개 모두 같고, 다른 것은 소성 항목 46개 추가 · 메타데이터.
- 시험: `build/`(10-30 빌드)를 찾는 파이썬 시험 `test_builtin_lists_match_built_engine` 은 옛 엔진이라 실패한다 — `KOOD3PLOT_HOME` 으로
  새 빌드를 가리키면 통과. `build/` 는 a9 와 같이 쓰므로 이쪽은 `.work/build_fig` 에 빌드한다.
- `.work/build_tests` 는 SECTION_RENDER=OFF 라 `test_section_center_mode` 가 링크되지 않는다(시험 CMake 가 조건 없이 링크 — 원래 있던 결함).
  그 시험은 `.work/build_fig` 에서 돌린다.

## ① 셸 파트 이력 (11-07)
- 배치 해석을 `LayeredLayout`(initialize 에서 종류마다 한 번)으로 뗐다. 핫스팟 층별 극값도 이것을 쓴다 — 세 덱에서 핫스팟 출력이
  v46 과 바이트 단위로 같아 리팩터링이 결과를 바꾸지 않았다.
- 셸 계열 파트는 **배치가 규격과 맞을 때만** part_ids_ 에 든다. 안 맞으면(DCOMP=2 압축, 응력 미기록, NV2D 공식 불일치) 종전처럼
  이력에 없고 `[parts]` 한 줄로 사유를 남긴다 — 전 상태 NaN 줄이 sphere CSV 를 어지럽히지 않게.
- 요소 값은 적분점 층 극값: σ_vm · σ1 · ε_p 는 층 최대, σ3 는 층 최소. 변형률 텐서(ISTRN)는 안쪽 · 바깥쪽 면 중 극값.
  그림 엔진과 같은 규칙이고, 핫스팟 소성 기준(ε_p 층 **평균**)과는 다르다 — 그쪽은 소성역 요약과 같은 값을 쓰기 위한 것.
- 평균(avg)은 요소 값(층 극값)의 산술 평균 — 솔리드와 같은 규칙. 삭제 요소는 뺀다.
- `element_type` 은 셸 계열 이력에만 쓴다(솔리드만 있는 덱의 JSON 은 바이트 단위로 같다 — Test_006 확인).
- 셸 변형률 텐서만 있는 덱이면 주변형률 이력을 만들고, 텐서가 없는 솔리드 파트는 미계측(NaN)으로 남는다(airbag 덱).
- **`extractPeakElementTensors` 는 셸 이력을 건너뛴다** — 셸 max_element_id 를 솔리드 ID 표로 찾아 엉뚱한 텐서를 읽던 자리.
- 솔리드가 없는 덱(case_shell)은 상태마다 `solid_data` 가 비어 통째로 돌아가던 것을 셋 다 빌 때만 돌아가게 고쳤다.
- 검증
  - v46 대 새 분석기(세 덱): 기존 솔리드 항목 전부 같음, 그 밖 섹션 같음, 셸 파트 1 · 58 · 31 개가 새로 생김.
  - lasso 독립 계산(상태마다 파트 최대 · σ3 최소 · ε_p · 최대 요소 ID): case_shell 4/4, airbag 232/232.
  - 두꺼운 셸 덱(case_01)은 **lasso 가 못 읽는다** — 요소당 에너지 워드(TSHENG)를 빼고 계산해 보폭이 하나 어긋난다(70≠69, 상태 24/22).
    두꺼운 셸이 든 덱 셋 모두 같은 경고. 대신 분석기 안 두 경로(파트 이력의 전역 최대 = 핫스팟 요소 극값의 파트 최대)를 대조 —
    33/33(두꺼운 셸 11 · 셸 20 · 솔리드 2).
  - deep 끝까지(airbag): 그림 대상이 셸 5개, 그림 엔진(lasso) 값 = 해석기 값 5/5. 그림도 정상(층 최대 · 주변 반투명).
- **하류 행동 변화(보고할 것)** — 셸이 이력에 들어가면 그대로 읽는 곳에 셸이 새로 나온다: sphere(파트별 CSV → 최악 파트 순위 ·
  report.json · 캠페인 그림), impact(순위 · 위치별 최대, 단 mtime 으로 옛 결과를 재사용하면 재분석 전까지는 안 보임),
  federate(옛 판과 견주면 셸이 '새로 생김'), custom(셸이 든 세트의 지표 값), 온톨로지(셸 파트 응답), batch 전체 피크.
- 남은 것: 빔 · 이산 요소는 여전히 이력이 없다. 셸 이력 실덱 회귀 시험(덱이 있어야 도는 (나) 시험)은 만들지 않았다.
