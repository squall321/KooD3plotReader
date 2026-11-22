# 결정 기록 — 빔 파트 응력 이력 · 카메라 타겟 맞춤

## 출발 (11-20)
- 사용자 「카메라 타겟 맞추기와 빔도 마저 해줘」. 둘 다 앞선 작업에서 「필요하면 다음에」 로 미뤄 둔 항목이다
  (`report_figures_2026-11/checklist.md` 3단계의 `--view-fit`, `shell_plastic_2026-11` 의 「빔 · 이산 요소는 여전히 이력이 없다」).

## 빔 — 조사에서 확정한 것
- **워드 배치(규격 `ls-dyna_database.txt`)** — 제어 워드 NEL2 28 · NUMMAT2 29 · NV1D 30, 확장(EXTRA > 0) NEIPB 67 · BEMENG 80.
  `NV1D = 6 + 5·BEAMIP + NEIPB·(3 + BEAMIP)`. 요소당 합력 6(축력 · S 전단 · T 전단 · S 모멘트 · T 모멘트 · 비틀림),
  적분점마다 5(규격 글의 나열은 τ_rs · τ_tr · σ_축 · ε_p · ε_축 — **파일의 실제 순서는 다르다, 아래 「구현에서 확정한 것」**),
  그 뒤 이력 변수. BEMENG > 0 이면 그 자리(1부터 셈)에 내부 에너지 밀도 워드.
- **실측** — R16 덱(EXTRA 64)은 빔이 없어도 `NV1D 7 · BEMENG 7`(합력 6 + 에너지 1). R13 `ElasticBeam` 은 EXTRA 0 · `NV1D 51` = 6 + 5×9.
- **데이터** — `/data` 2,476개 d3plot 폴더 중 빔이 있는 것은 2개뿐(`ElasticBeam` BEAMIP 9, `DynaAnalysis` NV1D 6). 둘 다 R13 · EXTRA 0.
  R16 배치(BEMENG 와 BEAMIP > 0 의 조합)는 실데이터가 없다. ~~로컬 솔버로 작은 덱을 만들어 잰다~~ → 라이선스 만료로 불가(아래).
- **`ControlData` 에 NEIPB · BEMENG 이 없다** — 파서가 확장 워드를 건너뛴다(`ControlDataParser.cpp` 「For now, we skip them」).

## 빔 — 설계 결정
- **빔 배열을 따로 두고 끝에서 합친다.** `part_ids_` · `part_kind_` · `HotspotElementKind` 는 건드리지 않는다. 빔 전용 파트 색인과 결과
  벡터 4개(σ_vm · σ1 · σ3 · ε_p)를 두고 `buildResult` 에서 기존 이력 뒤에 붙여 파트 번호순으로 안정 정렬한다.
  - 변형률 텐서 계열(`vm_strain` · 주변형률)에는 빔이 들어가지 않는다. `part_ids_` 에 넣으면 그 계열에 전부 NaN 인 빔 줄이 생기고,
    JSON 은 `global_unmeasured: true` 로 쓰는데 파이썬은 그 키를 읽지 않아 `global_max = 0.0` 으로 읽는다(0 위장). 또 `buildResult` 의
    주변형률 「전부 0 이면 버림」 판정이 깨진다(전부 NaN 인 줄의 `globalMax()` 는 −inf).
  - 핫스팟 · 피크 텐서 · `markUnmeasuredParts` 등 `part_ids_` 로 도는 코드를 그대로 둔다 — 솔리드 · 셸 덱 출력이 바이트 단위로 같다.
  - 솔리드 · 셸 파트와 번호가 겹치는 빔 파트는 건너뛴다(먼저 온 종류가 이긴다 — 셸과 같은 규칙).
- **적분점 값이 있는 파트만.** 빔 파트마다 「유한하고 0 아닌 적분점 워드가 한 번이라도 있는가」 를 보고, 없는 파트는 이력을 만들지
  않고 사유를 찍는다. 상태별 NaN 표식은 맞지 않는다 — 적분 빔도 상태 0 은 전부 0 이다. 파트 단위 · 실행 전체의 판정이어야 한다.
  (처음에는 할당 전에 전 상태를 미리 훑으려 했다 → 구현에서 「상태 × 파트」 표식 배열로 바꿨다, 아래.)
- **요소 값 = 적분점 극값**(셸의 층 극값과 같은 규칙). 빔 국부계 응력은 σ_rr · τ_rs · τ_tr 셋뿐이라
  σ_vm = √(σ_a² + 3(τ_rs² + τ_tr²)), 주응력은 텐서 {σ_a, 0, 0, τ_rs, 0, τ_tr} 의 고유값 — 닫힌 꼴 0 과 σ_a/2 ± √(σ_a²/4 + τ_rs² + τ_tr²).
- **핫스팟에는 넣지 않는다.** 군집은 면 이웃으로 묶는데 빔은 면이 없다. DynaForge 어휘 0.5 의 `element_type` 열거값
  (solid · thick_shell · shell)은 「응력 집중 군집」 형에만 있고 `ontology/deep.py` 는 `element_type` 을 쓰지 않는다 — 어휘 영향 없음.

## 빔 — 구현에서 확정한 것 (11-20)
- **적분점 워드 순서는 규격 글의 나열과 다르다.** 규격(`ls-dyna_database.txt` 1981–1985 줄)은 「RS 전단 · TR 전단 · 축응력 · 소성 변형률 ·
  축 변형률」 로 적었지만 파일에는 `[σ_축, τ_rs, τ_tr, ε_p, ε_축]` 로 실린다. 규격대로 읽은 첫 실행에서 `ElasticBeam` 의 σ_vm 이 기대값의
  √3 배로 나와 드러났다(축응력을 전단 자리로 읽은 값). 근거 둘.
  - 탄성 덱(E = 1.0E7)에서 첫 워드 = E × 다섯째 워드(9.99565e-05 × 1e7 = 999.565), 둘째 · 셋째 워드는 0.
  - lasso-python 2.0.3 이 `beam_layer_data[..., 0]` 을 축응력, `[..., 1:3]` 을 전단, `[..., 3]` 을 소성 변형률, `[..., 4]` 를 축 변형률로 읽는다.
  - 그 덱의 `elout` 은 합력만 찍는다 — 근거가 못 된다(계획의 「elout → 보 이론 대조」 는 하지 않았다).
- **실데이터 대조** — `ElasticBeam`(R13.1.1 음해법, `*SECTION_BEAM` ELFORM 4 · QR 4, BEAMIP 9, NEL2 20, NV1D 51, EXTRA 0, 빔 파트 4 = 요소 1117–1136).
  새 분석기와 lasso/numpy 로 따로 계산한 값이 t = 1.0 에서 10자리까지 같다 — σ_vm 최대 999.5647325(요소 1117) · 최소 94.5958199(1136) ·
  평균 689.3463558, σ3 최대 −59.16625614(1136) · 최소 −999.514809(1117) · 평균 −672.1007428, ε_p 0.
  `DynaAnalysis`(NEL2 1880, NV1D 6)는 rc 0 · 사유 한 줄 · 빔 줄 없음.
- **회귀** — 고치기 전 HEAD(401f6d3)를 작업 트리 사본(`git worktree`)에 따로 빌드해 산출 폴더를 바이트 단위로 맞대 봤다(`.work/beam_viewfit/cmp_run.py`).
  `ElasticBeam` 은 파트 4 빔 줄과 새 CSV 4개만 늘고, `DynaAnalysis` · 셸 덱(`/data/warpage_study/case_shell`)은 각인 말고 전부 같다.
- **로컬 LS-DYNA 로는 R16 덱을 풀 수 없다** — 라이선스 만료(Error 70022, 네트워크 라이선스 · MPPDYNA 제외). 우회하지 않는다.
  R16 꼴 배치(EXTRA 64 · BEMENG · NEIPB 와 BEAMIP > 0 의 조합)는 **합성 d3plot 시험으로만** 봤다. 실데이터 근거는 R13.1.1 덱 하나다.
  - BEMENG 의 주소(80)는 실제 R16 파일에서 봤다(빔 적분점 없는 덱의 `NV1D 7 · BEMENG 7`). NEIPB 의 주소(67)는 규격 글뿐이다 — NEIPB > 0 인 실제 덱이 없다.
- **BEMENG 규칙** — `e = BEMENG − 1`(요소 블록 안 0부터 셈). `e == 6` 이면 적분점 블록이 한 칸 밀린다(`ip_off = 7`).
  `6 + 5·BEAMIP ≤ e < NV1D` 면 그대로(`ip_off = 6`). 그 밖(합력 · 적분점 워드 안, 블록 밖)이면 사유를 찍고 만들지 않는다.
  에너지 워드는 NV1D 에 들어 있다 — `BEAMIP = (NV1D − 6 − [에너지 1] − 3·NEIPB) / (5 + NEIPB)` 가 정수로 떨어져야 한다.
- **사전 훑기 대신 「상태 × 파트」 표식 배열.** 처음 설계는 결과를 할당하기 전에 전 상태를 한 번 더 훑는 것이었다. 진입점마다 상태를 쥐는
  방식이 달라 훑는 코드가 셋 필요했다. 대신 상태별 루틴이 「이 상태 · 이 파트에 0 아닌 적분점 워드가 있었다」 를 제 칸에만 적고
  (`beam_part_seen_[state × np + slot]`, 상태 병렬에서 경합 없음), `buildResult` 가 합칠 때 한 번도 표식이 없는 파트를 빼고 사유를 찍는다.
- **주응력은 닫힌 꼴** — 성분이 σ · τ_rs · τ_tr 셋뿐이라 0 과 σ/2 ± √(σ²/4 + τ_rs² + τ_tr²). 시험은 `StressTensor::principalStresses()`
  (일반 3×3 풀이)를 독립 기준으로 쓴다.
- **비유한 값** — 적분점 5 워드 중 하나라도 NaN · inf 면 그 요소를 그 상태 통계에서 뺀다(발산 요소 하나가 파트 최대를 먹지 않게).
- **살아 있는 빔이 없는 상태**(전량 침식) — 최대 · 최소 · 평균은 NaN(JSON `null`), 요소 번호 0. 0 으로 위장하지 않는다.
- **파트 번호 충돌** — 솔리드 · 셸 파트와 번호가 같은 빔 파트는 빼고 한 줄 찍는다(한 파트에 이력 줄은 하나).
- **메타데이터** — 빔만 있는 덱은 시간 범위를 빔 이력에서 채운다. `analyzed_parts` 에 남긴 빔 파트를 더하고 번호순으로 세운다.
- **쓰기 쪽** — `D3plotWriter` 가 확장 제어 워드에 NEIPB(67) · BEMENG(80)을 싣는다(전에는 전부 0). 합성 시험에 필요해서다.
  쓰기 쪽은 삭제 표가 없다 — 침식은 읽은 뒤 `StateData::deleted_beams` 를 채워 `analyzeWithStates` 로 넣어 본다.
- **시험**(`tests/test_beam_part_history.cpp`, ctest `BeamPartHistory`) — 받는 배치 6(R13 꼴, 에너지 워드가 합력 뒤 · 적분점 블록 뒤 · 블록 끝,
  이력 변수 2 · 3), 거부 7(에너지 워드가 합력 · 적분점 안 · 블록 밖, 공식 불일치, 합력 미만, 적분점 미기록 둘), 침식, 비유한 값,
  잘린 상태 배열, 응력만 · 변형률만, 진입점 셋(`analyzeWithStates` · `analyzeParallel` · `analyzeLegacy`), 솔리드와 번호 충돌 + 정렬.
- **변이 검사** — 시험이 첫 실행에 통과해, 시험이 실제로 가려내는지 따로 봤다. 분석기 소스 사본을 한 군데씩 고장 내(워드 순서, `ip_off`,
  침식 · 비유한 건너뛰기, 표식, 충돌, 진입점 호출 둘, 에너지 셈, 배치 거부 조건들, 정렬, 경계 검사, NaN, 계수, 시간, 메타데이터, 종류 표식 등 26개)
  작업 트리 밖(`.work/beam_viewfit/mut/`)에서 빌드해 시험에 물렸다 — **26개 전부 실패로 잡히고, 고장 내지 않은 대조는 통과.**
  처음 판 시험은 둘(합친 뒤 정렬 제거, `analyzed_parts` 정렬 제거)을 놓쳤고 경계 검사는 시험이 없었다 → 충돌 덱의 솔리드 파트를 2 로 바꾸고
  잘린 상태 사례를 더했다.
  - 함정 — 변이 셋을 동시에 돌렸더니 대조가 SIGABRT 로 죽었다. 시험이 임시 폴더 이름을 고정해 써서 서로의 덱을 지운 것 — 변이마다 `TMPDIR` 을 따로 줬다.
- **C++ 시험 전체** — 렌더 켠 빌드(`.work/build_fig`)에서 25개 통과. `test_element_quality_states` · `test_part_name_lookup` ·
  `test_segment_parent_lookup` 은 그 빌드에서 링크되지 않는다(`UnifiedAnalyzer::processSetViews` · `processSectionViews` 가 렌더 쪽 소스에만 있다 —
  원래 있던 제약). 이 셋은 렌더 끈 빌드(`.work/build_tests`)에서 돌린다.

## 빔 — 파이썬 소비자 (11-20)
- **deep 표** — `stress_element_type == "beam"` 이면 피크 응력 옆에 「(빔 · 적분점 최대)」. 셸 계열의 「층 최대」 와 구분한다(빔은 층이 아니라
  단면 적분점이다). 「응력 이력 없음」 사유 · 요약 출력 · 미산출 안내는 「적분점 응력이 없는 빔(BEAMIP 0 · 합력 빔 · 트러스) · 이산 요소,
  또는 그 요소 종류를 집계하지 않던 옛 해석기 판」 으로 바꿨다 — 옛 글은 빔이면 무조건 없다고 읽혔다.
- **빔 파트는 원래 표에 있었다** — motion 이 빔 파트도 내서 deep 표에 「응력 이력 없음」 으로 나오던 줄이다. 이번에 값이 채워진다.
  `ElasticBeam` deep 실행: 파트 4 Beam 999.5647325(t = 1), 전체 피크는 파트 2 Tet 1001.07 그대로.
- **그림 꾸러미** — 빔은 면이 없다(`mesh.read_state` 는 솔리드 · 두꺼운 셸 · 셸의 바깥 면만 만든다). `PartPeak.beam = True` 로 표시하고
  상태 번호를 비운다 → 기존의 `state is not None` 거름으로 전체 그림의 기준 파트와 자동 대상에서 빠진다. 대상으로 **지정한** 빔 파트는
  스냅샷 작업을 만들지 않고 이력 차트만 만든다. 사유는 한 줄(`빔 파트 [..] 는 면이 없어 …`). 파트 요약 막대 차트에는 그대로 나온다.
  - 손대지 않으면 — 빔이 최대 응력 파트일 때 전체 그림이 `타겟 파트 의 면이 없다` 로 실패하고, 빔 파트 그림마다 실패 줄이 남는다.
  - 빔만 있는 덱은 대상이 없다(`targets = … if g else []` 그대로) — 그릴 면이 없으니 이력 차트만을 위해 흐름을 바꾸지 않았다.
- **캠페인 그림**(sphere 최악 방향) — sphere `report.json` 에는 요소 종류가 없다. 그래서 「읽은 상태에 그 파트의 면이 있는가」 로 본다.
  면이 없는 파트는 전체 그림의 기준에서 빼고, 그 파트 그림은 `그릴 면이 없다(빔 파트 등)` 사유로 건너뛴다. 이 검사가 없으면
  해석기 값 대조가 먼저 걸려 「옛 분석기 산출물일 수 있다(다시 분석 권장)」 이라는 엉뚱한 안내가 나온다.
- **손대지 않은 것**
  - `result.json`(`to_compare_dict`)에는 요소 종류 키가 없다 — 셸 때(v47)부터 그렇다. 배치 표 · DynaForge 는 빔 값을 솔리드 값과 같은 칸으로 받는다.
  - `global_unmeasured`(전 상태 미측정)는 파이썬 `_parse_series` 가 읽지 않는다 — 요소 종류와 무관한 기존 동작. 빔 줄은 이 표식을 달지 않는다
    (한 번도 값이 없던 빔 파트는 줄 자체가 없다).
  - sphere · impact 보고서는 요소 범위를 말하는 글이 없다.
- **시험** — `test_aggregate_stress.py` [4](빔 값 · 종류 · 미산출 사유, `layerTag` 를 node 로 실제 실행해 네 종류의 표식 확인),
  `test_figures.py` 3개(`_from_series` 의 빔 표시, 가짜 상태로 `pack.build` 를 돌려 그림 목록 · 알림 확인, 캠페인의 면 없는 파트).
  deep 패키지 212 통과 — `KOOD3PLOT_HOME` 으로 새 빌드를 가리켜야 한다(`build/` 의 10-30 엔진을 찾는 시험 하나가 옛 엔진이라 실패한다 — 셸 작업 때와 같다).
- **작업 중 본 것(이번 범위 밖)** — `ElasticBeam` 의 그림 꾸러미가 `part_1_peak_iso: 그림의 최대 999.303 이 해석기의 파트 최대 998.623 와 다르다` 를 낸다.
  이 덱은 솔리드가 적분점 8개를 기록한다(NV3D 56 = 7 × 8, `NINTSLD 8`). 분석기는 요소 블록의 첫 7 워드(첫 적분점)만 읽고, 그림은 lasso 로
  8개 적분점의 최대를 쓴다 — 파트 1 Hex: 첫 적분점 최대 998.6226 = 분석기 값, 8개 최대 999.3026 = 그림 값. 사면체 파트 2 는 우연히 같다.
  빔 작업과 무관한 기존 한계다(고치기 전 HEAD 빌드도 998.623). 고치지 않고 보고한다.

## 카메라 — 조사에서 확정한 것
- 개관 작업은 YAML `render_jobs`(deep `build_lsprepost_section_jobs` · `build_render_jobs`). 타겟 = `highlight_parts`, 나머지 = `context_parts`.
- `generateScript` 순서 — 열기 · `ac` · 타겟 강조(genselect remove → reverse → fringe → 전체 복원) · 숨김(`-M`) · 시점 문자열 + `ac` ·
  단면(`splane …` + `ac`) · 영상. 카메라는 보이는 모델 전체에 맞는다.
- LS-PrePost 4.12 배치 실측(앞선 작업) — `selectpart part N on` 은 「N 만 표시」, `-M <id>` 는 하나 숨김, `fringe` · `selectpart all on` 은
  숨김을 되돌려 `-M` 을 다시 넣어야 한다. 여러 파트만 남기는 검증된 방법은 genselect remove + reverse.

## 카메라 — 실측(11-20, LS-PrePost 4.12 배치 71 경우)
- 덱 `Test_006_Fibonacci_6deg` 의 런 하나(읽기만), 1280×720, 영상마다 프레임 3장 · 2–3초, 전부 rc 0. 도구는 `.work/beam_viewfit/lspp/`
  (`mk.py` 가 cfile 을 만들고 `run.sh` 가 운영과 같은 방식 — `Xvfb -displayfd` · 작업별 HOME · `lspp412_mesa` — 으로 돌려 첫 · 마지막 프레임을 뽑는다).
  타겟은 파트 6(20×16×1.3 mm) 등 작은 솔리드, 숨김은 바닥 파트 23(72×300×300 mm, 기울어 있다).
- **맞춤이 일어나는 곳은 `splane projectview` 다.** 단면을 넣는 순간 **보이는 파트** 의 상자에 화면을 맞춘다(정확히는 보이는 파트를
  평면이 **자른 도형** 의 상자다 — 아래 「맞춤 상자가 무엇인가(11차)」). 단면 뒤의 `ac` 는 아무것도
  바꾸지 않고(있으나 없으나 첫 프레임 md5 가 같다), `vauto` 는 이 순서들에서 아무 일도 하지 않는다.
- **화면 안 방향은 가장 최근 `ac` 가 본 상자를 따른다** — 그 상자의 긴 변이 가로로 눕는다. 그래서 타겟만 켠 채 `ac` 를 하면(P 흐름)
  타겟 단면의 긴 변이 가로가 돼, 모델 개관과 90° 돌아간 그림이 나온다(파트 6 의 Z 단면). 개관 영상과 나란히 놓고 보기 어렵다.
- 흐름 비교
  - 기본 — 강조 → 전체 복원 → 숨김 → 시점 + `ac` → 단면 + `ac`. 보이는 모델 전체.
  - P — 격리 유지 → 시점 + `ac` → 단면 → `zin` → 복원 → 숨김. 타겟에 맞지만 방향이 타겟을 따라 돈다. 버림.
  - Q — 격리 유지 → 시점(`ac` 없음) → 단면 → `zin` → 복원 → 숨김. 방향은 맨 처음 `ac`(바닥까지 포함한 전체)를 따른다.
    파트별 영상(`renderAllPartSections`)이 지금 이 방식이다 — 바닥이 큰 덱의 Y 단면은 그래서 돌아가 보인다(기존 동작, 이번에 손대지 않는다).
  - R · S — 숨김 뒤에 다시 격리. `selectpart reverse` 가 `-M` 으로 끈 파트를 **되살린다** — 바닥까지 맞춰 버린다. 실패.
  - **S2(채택)** — 기본 순서 그대로(강조 → 복원 → 숨김 → 시점 + `ac`) → **다시 격리**(genselect remove + reverse) → **다시 숨김**(`-M`) →
    단면 + `ac` → `zin m m 1-m 1-m` → 전체 복원 → 숨김 → 영상. 「모델 개관을 타겟으로 당긴 그림」 이 된다 — 방향은 기본 영상과 같고
    화면은 보이는 타겟의 상자에 맞는다(타겟의 잘린 면 — 11차).
- S2 로 확인한 것(첫 프레임 md5 가 앞선 실험의 같은 그림과 일치) — Z · Y · X 단면, 세로로 긴 타겟, 가까운 타겟 둘, 멀리 떨어진 타겟 둘
  (합친 상자 = 사실상 폰 전체), 단면이 지나지 않는 타겟(그 자리로 당겨지고 범례만 없다 — 죽지 않는다), 여백 0 · -0.3 · -4.0,
  숨김 있음 · 없음, 마지막 프레임(타겟이 화면 안에 남는다).
- **타겟이 숨김 대상이기도 할 때**(8차) — 타겟 [6, 23] · 숨김 23 은 보이는 타겟 6 에만 맞는다(타겟 6 하나일 때와 첫 프레임이 같다).
  타겟 [23] · 숨김 23 은 **빈 화면**(배경과 `Time = 0` 뿐)이다. 맞출 것이 없기 때문이다 → 보이는 타겟이 하나도 없으면 맞춤을 걸지 않는다.
- **모델에 없는 타겟 번호**(9차) — 타겟 [999] 도 같은 빈 화면이고, 타겟 [6, 999] 는 타겟 6 하나일 때와 첫 프레임이 같다.
  그래서 조건은 「**모델에 있고 숨김 대상이 아닌** 타겟이 하나라도 있다」 다(번호가 틀린 설정 하나로 영상이 통째로 비면 안 된다).
- `zin` — `zin 0 0 1 1` 은 그대로, `zin -0.3 -0.3 1.3 1.3` 은 1.6배 넓게. 양수는 타겟 안쪽으로 잘린다.
- LS-PrePost 의 그림 영역 비율은 약 1.44 다. 16:9 영상에서 가로로 긴 타겟은 여백 0 에서도 가로의 81 % 쯤까지만 찬다(-0.3 이면 51 %).
- 카메라와 절단면은 첫 상태에서 정해져 공간에 고정된다. 크게 움직이는 타겟은 타겟에 맞춘 화면 밖으로 나갈 수 있다(파트별 영상과 같은 한계).
- 단면이 없는 작업에서는 쓸모가 없다(맞춤 자체가 `splane projectview` 에서 일어난다) → 단면 작업에만 건다.

## 카메라 — 결정
- **이름** — C++ `RenderOptions::fit_highlight` · `fit_margin`, `RenderJob::view_fit_target` · `view_margin`, YAML `view_fit: target` · `view_margin`,
  파이썬 `view_fit_target` · `view_margin`, CLI `--view-fit {model,target}` · `--view-margin M`.
- **여백 규약** — 파트별 영상의 `--section-view-section-margin` 과 같은 `zin` 규약으로 둔다(음수 = 넓게, 기본 -0.3). 같은 도구에 여백 규약이
  둘이면 헷갈린다. 0.5 이상은 `zin` 사각형이 뒤집혀 받지 않는다.
- **정책은 `processRenderJobs`, 방법은 `generateScript`** — 맞춤을 걸 조건(단면이 있다 · 타겟이 있다 · 모델에 있고 숨김 대상이 아닌 타겟이 하나라도 있다)은
  작업을 푸는 쪽이 판단하고 사유를 한 줄 남긴다. cfile 쪽은 `fit_highlight` 가 켜졌고 타겟 · 단면이 있을 때만 두 덩이를 더 쓴다.
  옵션이 꺼져 있으면 cfile 은 바이트까지 같다(시험으로 묶는다).
- **`_zoom` 잘라내기는 맞춤이 걸린 작업에서 끈다** — 잘라내기 자체는 화소 기준이라(프린지 색을 찾아 자른다) 카메라와 무관하게 돌지만,
  타겟에 맞춘 영상이 이미 확대본이라 한 벌 더 만들 이유가 없다. deep 의 단면 작업은 원래 `zoom_crop: false` 다(v45).
- **소프트웨어 단면에는 걸 것이 없다** — 그쪽 카메라는 원래 타겟 상자 × `scale_factor` 에 맞는다(`SectionCamera.hpp`). deep 이 `[설정]` 으로 알린다.
- **알 수 없는 값은 말한다** — YAML `view_fit` 이 `model` · `target` 이 아니거나 `view_margin` 이 수가 아니면 · 0.5 이상이면 기본으로 두고
  `config_issues` 와 표준 오류에 한 줄 남긴다(오타가 말없이 「모델 전체」 가 되지 않게).
- **`saveToYAML` 은 넓히지 않는다** — 렌더 작업의 `parts` · `hide_part_ids` · `zoom_crop` 도 원래 쓰지 않는다(기존 구멍). 이번 범위가 아니다.
- **파트별 영상에는 걸지 않는다** — `part_section_renders` 는 이미 그 파트에 맞춘다(Q 방식). 옵션은 개관 작업(`render_jobs`)에만 닿는다.

## 카메라 — C++ 구현에서 확정한 것 (11-20)
- `generateScript` 가 쓰는 것은 두 덩이뿐이다 — 시점 `ac` 뒤의 「타겟만 남기기 + 다시 숨김」, 단면 `ac` 뒤의 「`zin` + 전체 복원 + 다시 숨김」.
  `fit_highlight` 가 켜지고 타겟 · 단면이 둘 다 있을 때만 쓴다. 숨김(`-M`)은 그래서 세 번 나간다(색 뒤 · 뒤집은 뒤 · 복원 뒤).
- **끄면 바이트까지 같다** — 옵션 조합 109개(타겟 0 · 1 · 3개 × 숨김 0 · 1 · 3개 × 단면 0 · 1 · 2장 × 영상 · 보폭, 시점 · 프린지 · 범위 · AVI)의
  스크립트를 고치기 전 빌드(작업 트리 `wt_head`, 401f6d3)와 지금 빌드로 뽑아 대조했다. 4,408줄이 같다(`.work/beam_viewfit/cfile_cmp/`).
- **만든 스크립트로 다시 찍었다(10차)** — 빌드한 `generateScript` 가 낸 cfile 을 측정 도구로 돌려 첫 · 마지막 프레임을 실측 그림과 대조.
  끔 = 기본 그림, 켬(-0.3) = S2 그림, 여백 0, 타겟 둘 — 넷 다 md5 가 같다. 손으로 쓴 실측 cfile 과 다른 점은 주석 줄
  (`$# Hide parts (floor etc.)`) 둘뿐이라 그림에 닿지 않는다.
- **분석기 끝에서 끝**(YAML → `processRenderJobs` → LS-PrePost, `.work/beam_viewfit/e2e_cpp/`, 작업 7개 · rc 0)

  | 작업 | 설정 | 로그 | 그림 |
  |---|---|---|---|
  | `plain_z` | 타겟 6 · 숨김 23 | — | 기본 실측과 첫 · 마지막 프레임 동일 |
  | `fit_z` | + `view_fit: target` | 타겟 파트 1개 · 여백 -0.3 | S2 실측과 동일(타겟이 가운데, 1.6배 여백) |
  | `fit_m0` | + `view_margin: 0` | 타겟 파트 1개 · 여백 0 | 여백 0 실측과 동일 |
  | `fit_mixed` | 타겟 [6, 23] · 숨김 23 | 타겟 파트 1개 | 아래 「단면 위치」 참고 |
  | `fit_hidden_target` | 타겟 [23] · 숨김 23 | 보이는 타겟이 없다 → 모델 전체 | 아래 「단면 위치」 참고 |
  | `fit_no_target` | 타겟 없음 | 타겟 파트가 없다 → 모델 전체 | 모델 전체 단면(전 파트 프린지) |
  | `crop_default` | 타겟 6 · `view_fit` 없음 | — | `plain_z` 와 동일, `_zoom` 은 이 작업에만 생긴다 |

- **단면 위치는 이번에 손대지 않았다(기존 동작)** — 절단면은 타겟 번호 **전부**(숨긴 것 · 모델에 없는 것 포함)의 합집합 상자 중심에 선다.
  그래서 타겟에 바닥(23)이 끼면 면이 z ≈ -5.85 로 내려가 폰을 지나지 않고, 영상은 빈 화면이다. `view_fit` 을 뺀 같은 작업 둘
  (`cfg_ctl.yaml`)도 첫 · 마지막 프레임이 똑같이 비어 있다 — 맞춤이 만든 것이 아니다. 보고만 한다.
- **LS-PrePost 는 작업 폴더에 `lspost.cfile` · `lspost.msg` 를 남긴다** — 운영 렌더는 작업 폴더가 d3plot 폴더라(`renderImage`) 덱 폴더에
  두 파일이 남는다(Test_006 런 폴더에 11-07 자, `/data/warpage_study/case_shell` 에 11-08 자 — 앞선 운영 방식 실행의 흔적, 그대로 뒀다).
  d3plot 을 여는 것만으로도 덱 폴더의 수정 시각이 바뀐다. 그래서 이후 시험은 덱을 심볼릭 링크로 묶은 `.work/beam_viewfit/deck006/` 로 돌린다
  (흔적이 `.work/` 아래에 떨어진다). 빔 확인 때 돌린 deep 실행(11-20 22:02)도 `ElasticBeam` 폴더에 두 파일을 남겼다 — 내가 만든 것이라
  `.work/beam_viewfit/residue_elasticbeam/` 로 옮겨 폴더를 원래 목록으로 돌려놨다.
- 시험 — `LsppViewFit`(15항: 두 덩이의 글자 · 자리 · 순서, 끈 것 = 켠 것 − 두 덩이, 여백, 타겟 여럿, 쓰이지 않는 조합),
  `test_config_inline_mapping` [H](10항: 키 읽기 · 기본값 · 못 쓰는 값 넷의 사유). `processRenderJobs` 의 판단 네 갈래(맞춤 · 단면 없음 · 타겟 없음 · 보이는 타겟 없음)는 위 실행과 단면 없는 작업 한 쌍
  (`cfg_nosec.yaml` — `view_fit` 을 넣어도 빼도 첫 · 마지막 프레임이 같다)의 로그로 봤다.
- C++ 시험 전체(`.work/beam_viewfit/run_ctests.sh`) — 렌더 켠 빌드 26개 · 끈 빌드 5개 통과. `test_surface_stress` 는 덱을 안 넘기면
  통합 검사 4건을 건너뛰고 77 로 끝난다(통과가 아니다). 작은 실덱(`deck_eb` — ElasticBeam 심볼릭 링크)을 넘겨 9건을 다 돌렸다.

## 카메라 — 맞춤 상자가 무엇인가 (11차 실측, 11-21)
- **물음** — `splane projectview` 가 화면을 맞추는 상자는 (가) 평면이 **자른 도형** 의 상자인가, (나) 평면이 지나는 **파트의 3D 상자** 인가.
  앞선 71 경우의 타겟은 축에 나란한 상자 꼴이라 둘이 같아 가릴 수 없었다. 도움말에 「무엇에 맞춘다」 고 쓸지가 여기에 달려 있다.
- **실험** — Test_006 의 바닥 파트 23(72 × 300 × 300 mm 상자 안에 약 9.5° 기운 판)을 평면 x = 70 으로 자른다. 폰(x ≤ 35.5)은 잘리지 않는다.
  계산(`lspp/floor_cut.py`, 상태 0) — 자른 도형 300.098 × 70.333 mm · 중심 z 106.965, 파트 상자는 화면 평면에서 300.178 × 299.666 mm · 중심 z -5.842.
  1280×720 · 여백 0 에서 (가)면 띠가 1037 × 243 px 로 화면 가운데(640, 360)에 오고, (나)면 721 × 169 px 이고 세로로 271 px 비켜난다.
- **결과**(`lspp/mk_floor.py` · `lspp/run11.out` — 첫 프레임에서 띠의 화소 범위, 범례 막대와 좌표축 표식은 가리고 쟀다. 덱은 심볼릭 링크 사본)

  | 경우 | 흐름 | 띠 | 첫 프레임 md5 |
  |---|---|---|---|
  | `bq_floor_plain` | 기본(격리 없음) | x 122–1157(1036 px) · y 240–479(240 px) · 중심 (639.5, 359.5) | 6ea7822ba610 |
  | `br_floor_fit_m0` | S2 · 여백 0 · 평면 기준점 = 파트 상자 중심 | 같다 | 6ea7822ba610 |
  | `bt_floor_fit_m0_pc` | S2 · 여백 0 · 평면 기준점 = 자른 도형 중심 | 같다 | 6ea7822ba610 |
  | `bs_floor_fit` | S2 · 여백 -0.3 | x 316–961(646 px = 1036 / 1.6) · y 284–435(152 px) · 중심 (638.5, 359.5) | 1adaaa67c261 |

- **맞춤 상자는 보이는 파트를 평면이 자른 도형의 상자다(가)** — 파트의 3D 상자가 아니다. 위 실측 절의 「보이는 파트의 상자」 는 이 뜻으로 읽는다.
  - 격리하지 않은 기본 그림이 격리한 그림과 같다. 단면 영상은 잘린 면만 그리고, 잘리지 않은 파트(폰)는 상자에 들지 않는다.
    그러니 기본 영상은 보이는 모델 전체의 잘린 면에, 타겟 맞춤은 타겟의 잘린 면에 화면을 맞춘다.
  - 무엇이든 잘리면 평면 기준점의 자리는 상관없다(`br` = `bt`. 앞선 `ai_q_offset` = `w_noac1` 도 같은 결과였다).
  - 타겟이 여럿이고 평면(합집합 상자 중심)이 일부만 자르면 화면은 잘린 타겟에만 맞는다 — 따로 재지 않았고 위 결과에서 나오는 귀결이다.
- **문구를 고쳤다** — CLI 도움말과 파이썬 · C++ 주석의 「타겟 상자에 맞춘다」 를 「타겟의 단면(잘린 면)에 맞춘다」 로. 분석기 진행 줄
  (`View fit: 타겟 파트 N개에 카메라를 맞춥니다`)과 `[설정]` 안내 글은 그대로 뒀다(deep 이 건지는 약속이고 뜻도 틀리지 않다).
  커밋 37c5f88 의 제목(「화면을 그 상자에 맞춘다」)은 이 실측 전의 표현이다.
- **맞춤 영역은 가로 1.44·H × 세로 H 다**(H = 프레임 높이). 1280×720 에서 1037 × 720 — 위 띠 너비 1036 px 가 그 값이고, 실측 절의
  「그림 영역 비율 약 1.44」 가 이것이다. 가로로 긴 타겟은 16:9 화면에서 여백 0 이어도 가로의 81 % 까지만 찬다.

## 카메라 — deep 구현에서 확정한 것 (11-20 · 11-21)
- **작업 규칙은 한 곳** — `job_builder._fit_to_target(job, config)`. 옵션이 켜졌고 작업에 타겟(`parts` · `part_pattern`)이 있을 때만
  `view_fit: "target"` · `view_margin` 을 단다. 끄면 키를 쓰지 않아 YAML 이 종전과 글자까지 같다. 부르는 자리는 넷 —
  단면뷰 개관 · 단면뷰 파트별 루프(`build_lsprepost_section_jobs`), 예전 경로의 개관 `overview_{축}` · 파트별 `part_{pid}_{축}`(`build_render_jobs`).
  단면뷰 경로는 `_build_yaml` 이 개관 사본의 `per_part_render` 를 끄므로 실제로는 개관 작업에만 실린다. 파트별 영상(`part_section_renders`)과
  소프트웨어 단면은 건드리지 않았다.
- **CLI 기본값은 None(안 줌)** — `--view-fit {model,target}` · `--view-margin M`. 설정 파일은 CLI 가 안 준 것만 채운다. 그래서 직접 준
  `--view-fit model` 이 설정 파일의 `view_fit: target` 을 이긴다. 값은 `_apply_view_fit` 한 곳에서 풀어 두 렌더 설정에 싣는다
  (단일 · 배치 둘 다 `_apply_video_hide` 바로 뒤).
- **설정 파일 키** `view_fit` · `view_margin` — 줄 머리에서 글 전체를 훑어 읽는다(맨 위 · `section_view:` 안 · 렌더 작업 안 어디에 있어도).
  deep 의 설정 읽기가 원래 정규식 훑기라 그 방식에 맞췄다. 주석 줄은 읽지 않고 따옴표 · 대문자는 받는다. 못 쓰는 값은 표준 오류에
  `설정 파일 view_fit: … — 무시` 를 남기고 버린다.
- **실행 전 `[설정]` 안내 넷**(`_view_fit_warnings` — 기존 `_ignored_option_warnings` 를 한 글자도 안 바꾸려고 따로 뒀다)
  - 여백만 줬다(`--view-margin` 이 -0.3 이 아닌데 맞춤은 꺼져 있다)
  - 소프트웨어 백엔드다(그쪽 카메라는 타겟을 주면 원래 그 상자에 맞는다)
  - 단면뷰인데 타겟이 없다(`--section-view-target-ids` · `--section-view-target-patterns`)
  - 예전 경로인데 `--part-pattern` · `--per-part-render` 가 없다
- **분석기가 걸지 않은 영상은 건진다** — 번호가 모델에 없거나 전부 숨김 대상이거나 패턴에 맞는 파트가 없으면 분석기는 모델 전체에 맞춰 찍고
  `View fit: <까닭> — 보이는 모델 전체에 맞춥니다` 를 진행 줄로 낸다. 진행 줄은 `verbose` 와 무관하게 표준 출력으로 나간다. deep 은 출력을
  잡는 실행(verbose 아님)에서 그 줄을 모아 `[설정] --view-fit target 이 영상 N개에 걸리지 않았다(모델 전체에 맞췄다) — 까닭` 한 줄로 만든다
  (`_view_fit_declined`). rc 0 이면 경고로, rc 3 이면 실패 글 뒤에 붙고, 1차 · 2차 패스 모두 `render_warnings` 로 간다.
  `--verbose` 실행은 줄이 터미널로만 가서 건지지 못한다(rc 3 의 실패 줄도 원래 그렇다).
- **두 언어 사이의 약속** — 건지는 줄의 머리 · 꼬리 문구를 C++ 주석 한 줄과 파이썬 시험(`test_analyzer_still_prints_the_line_this_module_reads` —
  C++ 소스에 그 글자가 있는지 본다)으로 묶었다.
- **보고서** — 안내는 `render_warnings` 로 실려 갤러리 머리의 「렌더 설정 — 쓰이지 않은 옵션이 있다」 상자에 나온다. 자동화(`post_analyze.sh`)는
  deep 의 터미널 출력을 버리므로 사용자에게 닿는 길은 이것뿐이다. 보고서의 「단면뷰 렌더 설정」 패널(`_svConfigPanel`)은 넓히지 않았다 —
  소프트웨어 단면(`section_views:`)용 명령 · YAML 을 만드는 패널이라 이 옵션이 걸릴 데가 없다.
- **자동화 길** — `post_analyze.sh --deep-opts "--view-fit target --view-margin=-0.3"` 또는 `--deep-config` 설정 파일의 키. `scripts/` 는 고치지 않았다.
  대역 deep 으로 넘어오는 인수를 봤다(`.work/beam_viewfit/pa_route/`) — `--view-margin -0.5` 처럼 띄어 쓴 음수와 `--view-margin 0` 도 그대로 온다.
  post_analyze 는 LS-PrePost 를 못 찾으면 소프트웨어 백엔드로 내려가는데, 그때는 위 「소프트웨어 백엔드」 안내가 보고서에 실린다.
- **시험** — `tests/test_view_fit.py` 24개 함수 · 42 경우(작업 키 · YAML 글자 · CLI · 단일/배치 배선 · 설정 파일 · 안내 넷 · 건지기 · 약속).
  deep 패키지 254 통과(212 + 42). 변이 시험은 작업 트리를 a9 와 같이 써서 사본에서 돌렸다(`.work/beam_viewfit/mut/`) — 70개 전부 잡힘.
  처음에 살아남은 둘은 동작이 같은 변이(건지기 코드의 군더더기)여서 코드를 줄였다.

## 카메라 — deep 실렌더 (11-20 · 11-21)
- 덱은 심볼릭 링크 사본(`.work/beam_viewfit/deck006/` · `deck_eb/`)이다 — LS-PrePost 가 덱 폴더에 남기는 `lspost.*` 가 `.work/` 아래에 떨어진다.
  도구 `.work/beam_viewfit/deep_e2e/`(`run.sh` · `run_batch.sh` · `run_more.sh`, 결과 `run_*.out`). 실행마다 「남은 Xvfb 0」.
- **단면뷰 경로**(Test_006, 타겟 파트 6, 1280×720, 프레임 3장. md5 는 첫 / 마지막 프레임)

  | 경우 | 옵션 | 결과 |
  |---|---|---|
  | `plain` | 타겟 6 · Z | 3a33f80f4e80 / bebd441aec07 — 측정 도구의 기본 그림과 동일 |
  | `fit` | + `--view-fit target` | 4034cc4573fa / 631163dcb72c — S2 실측과 동일, `_zoom` 없음, 안내 없음 |
  | `xyz_plain` · `xyz_fit` | 축 x y z | 세 축 모두 측정 도구의 기본 · S2 그림과 md5 동일(X 8feb81af2486 · Y 7f8944804daf · Z 4034cc4573fa) |
  | `cfg_block` | `--config`(`section_view:` 블록 안에 키, 여백 0) | 460ad5e37345 / 8788e8692953 — 여백 0 실측과 동일 |
  | `cfg_m0` | `--config`(키 둘뿐) · 배포 꼴 설치 | 여백 0 실측과 동일 |
  | `cfg_cli_model` | 같은 설정 + `--view-fit model` | 기본 그림 + 「여백만 줬다」 안내가 로그와 보고서에 |
  | `pattern` | `--section-view-target-patterns *Motor*` | be60ae733e15 / fdfcd3718806 — 파트 18 이 여백을 두고 가운데 |
  | `declined_missing` · `declined_floor` | 타겟 999 · 타겟 23(숨긴 바닥) | 빈 화면 + 「영상 1개에 걸리지 않았다 — 보이는 타겟이 없다」 가 로그와 보고서에 |
  | `ctl_missing` · `ctl_floor` | 같은 타겟, 맞춤 없이 | 똑같이 빈 화면 — 빈 화면은 맞춤이 만든 것이 아니다(단면 위치, 기존 동작) |
  | `notarget` | 타겟 없음 + 맞춤 | 15aaab110ffb / 0dfa941a8dc4(모델 전체) + 「타겟이 있어야 쓰인다」 안내 |
  | `batch_fit` | `koo_deep_report batch` | 4034cc4573fa / 631163dcb72c — 단일 실행과 동일 |

- **예전 경로**(`--section-view` 없이. 작은 실덱 `deck_eb` = ElasticBeam — 파트 1 Hex · 2 Tet · 3 Shell · 4 Beam, 프레임 2장)
  - `--part-pattern *Tet*` — 개관 세 축이 타겟에 맞고 `_zoom` 이 사라진다(맞춤 없이는 3개). 패턴으로 준 것과 `parts: [2]` 는 프레임이 같다.
  - `--per-part-render` — 2차 패스 YAML 의 작업 12개(`part_{1..4}_{x,y,z}`)에 키가 다 실리고, 타겟 없는 개관 3개는 종전과 프레임이 같다.
  - 화소로 잰 것(`deep_e2e/blobs.py`, 프레임 1594×1192) — 솔리드(Hex · Tet) · 셸 타겟이 X · Y · Z 에서 화면 가운데로 오고 1.6배 여백이 생긴다.
    길이 5 의 막대는 1074 px(가로의 67 %), 0.5 × 0.5 단면은 742 × 742 px(세로의 62 %), 맞춤 없이는 막대가 프레임 양끝에서 잘려 있었다.
  - **돌리지 않은 것** — Test_006 의 예전 경로(`legacy_plain` · `legacy_fit`, 2560×1440 · 992 상태라 무겁다). 예전 경로의 실렌더 근거는 `deck_eb` 뿐이다.
- **예전 경로에서 본 것(이번에 고치지 않는다)**
  - 예전 경로의 기본 해상도 2560×1440 은 나오지 않는다 — Xvfb 화면이 1600×1200 고정이라(`LSPrePostRenderer.cpp`) 영상은 1594×1192 다.
    이 프레임은 비율이 1.337 로 맞춤 영역(1.44·H)보다 좁아, 가로로 긴 모델은 기본 영상에서 양끝이 3.8 % 쯤 잘린다.
    타겟 맞춤의 기본 여백 -0.3 은 괜찮고(가로의 67 %), 여백 0 을 주면 가로로 긴 타겟이 같은 만큼 잘린다.
  - **평면이 아무것도 자르지 않으면** LS-PrePost 는 보이는 파트와 평면 기준점을 묶은 상자로 물러난다. 근거는 둘 — 평면과 같은 면에 누운 셸 타겟
    (`part_3_z` — 화면 중심이 셸 상자 중심, 셸은 그려지지 않는다), 빔 타겟의 X 단면(`part_4_x` — 화면 중심이 기준점과 빔의 중점
    (y 3.376, z 0.437), 계산 (3.375, 0.4375)). 두 경우 다 기준점이 모델 중심이라 「기준점」 인지 「모델 중심」 인지는 가리지 못했다.
  - **단면은 빔을 그리지 않는다**(`part_4_x` 에서 빔 자리 ±50 px 에 화소 0). 평면과 같은 면에 누운 셸도 그려지지 않는다.
  - **빔만 있는 파트가 타겟이면** — `GeometryAnalyzer::calculatePartBounds` 는 솔리드 · 셸 · 두꺼운 셸 절점만 모으고, 없으면 모델 전체 상자로
    물러난다. 그래서 절단면이 모델 중심에 서고, 분석기는 빔 파트를 「보이는 타겟」 으로 세어 맞춤을 건다(화면은 위 물러남 규칙대로 간다).
    어차피 단면에 빔은 안 나온다. `--per-part-render` 는 빔 파트에도 단면 영상을 만든다(기존 동작). 분석기가 빔만 있는 타겟의 맞춤을
    거절하게 하거나 상자 계산을 빔까지 넓히는 길은 버렸다 — 앞의 것은 새 문구가 생기고, 뒤의 것은 기존 단면 위치를 바꾼다. 보고만 한다.
  - 파트 1 · 파트 2 의 맞춤 X 프레임이 바이트까지 같다(ccbbf443e661) — 단면 크기 · 색 띠가 같고 화면에 다른 것이 없으며 범례가 모델 전체 기준이라 그렇다.
- **`--config` 가 렌더를 끄는 기존 규칙** — 설정 파일에 `render_jobs:` 가 없고 `section_view:` 블록이 켜져 있지도 않으면 deep 은 렌더를 끈다
  (CLI 로 `--section-view` 를 줘도 `(렌더OFF | 단면뷰ON)`). 그러면 생성 YAML 에 `lsprepost_path` 가 빠지고 분석기가 스스로 찾는데, 배포 꼴
  (`bin/unified_analyzer` 옆 `lsprepost/`)에서는 찾고 개발용 심볼릭 링크 꼴에서는 못 찾아 rc 3 이다. 내 키가 없는 설정(`ua_threads: 4` 뿐)으로도
  똑같이 난다 — 2026-03 · 05 의 규칙이고 이번 기능과 무관하다. 고치지 않고 보고한다.

## 마감 (11-21)
- **전체 시험** — 문구 · 주석을 고친 뒤 다시 돌린 결과다.
  - C++(`.work/beam_viewfit/run_ctests.sh`) — 렌더 켠 빌드 26개 통과(건너뜀 0) · 끈 빌드 5개 통과.
  - 파이썬 여섯 패키지 820 통과 — deep 254 · sphere 187 · impact 148 · federate 211 · custom 13 · scatter 7(`KOOD3PLOT_HOME` 은 새 빌드).
  - `tests/scripts/test_post_analyze.sh` 통과(실패 0 건).
  - 실렌더 다시 — 단면뷰 세 축(맞춤 전 · 후)과 예전 경로 `*Tet*`(맞춤 전 · 후)의 첫 · 마지막 프레임이 위에 적은 md5 와 전부 같다
    (`deep_e2e/run_final.out`). 남은 Xvfb 0.
- **솔리드가 적분점을 여러 개 기록한 덱이 얼마나 되나** — 빔 작업 중에 본 「분석기는 솔리드의 첫 적분점만 읽는다」 가 닿는 범위다.
  머리말만 읽어 셌다(`.work/beam_viewfit/scan_solid_ip.py` · `.out`, 깊이 7 까지, 심볼릭 링크는 따라가지 않음).
  `/data/Tests` · `/data/koopark` · `/data/warpage_study` · `/data/battery_study` · `/data/cms_study` · `/data/backup` 의 d3plot 폴더 1,992개 중
  솔리드가 있는 것이 1,695개, 그 가운데 `NV3D - NEIPH > 13` 인 것이 44개다 — `/data/battery_study` 43개(NV3D 208 = 8 × (7 + 19))와
  `ElasticBeam`(NV3D 56 = 8 × 7). 나머지 네 곳에는 없다. 값을 읽어 「분석기 값 = 첫 적분점」 을 확인한 것은 `ElasticBeam` 하나고,
  배터리 덱 43개는 머리말 산수로만 본 것이다. 고치지 않고 보고한다.
- **옛 문서** — `report_figures_2026-11/checklist.md` 3단계의 보류 칸, 같은 폴더 `plan.md` 2-3 의 `vauto` 설명,
  `shell_plastic_2026-11/context-notes.md` 의 「빔은 이력이 없다」 에 이 폴더를 가리키는 말을 달았다.
- **치운 것** — 고치기 전 빌드용 작업 트리 `.work/beam_viewfit/wt_head`(401f6d3). 대조 결과는 `cfile_cmp/` 에 남아 있다.
- **하지 못한 것 · 하지 않은 것**
  - 로컬 LS-DYNA 라이선스가 만료돼 R16 빔 덱을 풀지 못했다(우회하지 않았다). 빔 워드 순서의 실데이터 근거는 R13.1.1 덱 하나다.
  - 예전 경로의 Test_006 실렌더는 돌리지 않았다(근거는 `deck_eb` 뿐).
  - 기존 동작이라 손대지 않은 것 — 단면 위치(타겟 번호 전부의 합집합 상자 중심), 빔만 있는 타겟의 상자, `--config` 가 렌더를 끄는 규칙,
    Xvfb 1600×1200 고정, 솔리드 첫 적분점. 위 각 절에 적었다.
- **작업 중 본 것(이번 범위 밖 — 고치지 않았다)**
  - `--config` 도움말은 「CLI 인수보다 우선」 이라 하는데 코드는 반대다 — CLI 가 준 값은 두고, 기본값 그대로인 것만 설정 파일이 채운다(`_apply_config_to_args`).
  - rc 3 일 때 보고서에 실리는 까닭은 `FAILED` · `failed` 가 든 줄뿐이다. LS-PrePost 를 못 찾은 경우의 실제 사유 줄
    (`WARNING: LSPrePost not found at: …`)은 실리지 않는다.
  - 타겟이 있는 개관 영상은 프린지 범위(`range userdef`)를 쓰지 않는다 — `generateScript` 의 타겟 없는 가지에만 있다. 범례는 LS-PrePost 기본이다.
  - deep 은 분석기 설정 사본을 `/tmp/last_ua_config_<pid>.yaml` 로 남긴다(디버그용).
  - `test_surface_stress` 는 `add_test` 로 등록돼 있지 않고(실행 파일만 만든다) CSV 를 `/tmp` 에 쓴다.
- push · 배포 요청은 사용자 승인 뒤에 한다 — 로컬 커밋 401f6d3 · c06e5e7 · 378a611 · 37c5f88 · 5dbdfa9 와 이 마감 커밋.

## push · 배포 요청 (11-21)
- 사용자 승인(「ㄱㄱ」 — 「push 와 pykoocae-53 배포 요청을 진행할까요?」 의 답)으로 `dff1a22..d2f0d6b` 를 push 했다(origin/main = d2f0d6b).
  굽는 프로세스가 없는 것을 본 뒤다. 이어 pykoocae-53 에 v52 배포 요청을 보냈다. 완료 알림까지 push · `apptainer/` · `scripts/` 수정은 멈추고,
  이 절과 checklist 6절은 커밋하지 않고 둔다.
- **판정 꾸러미 `/data/koopark/Post_v52/`** — 배포판은 `--no-home` 으로 봐야 해서 홈 밖에 둔다(앞선 `Post_vNN` 과 같은 자리).
  - `check_v52.sh <SIF|local> <태그>` — ① 분석기 여섯 덱(Test_006 · ElasticBeam · DynaAnalysis · case_shell · 두꺼운 셸 · airbag, 핫스팟 세 기준)
    ② ElasticBeam deep(렌더 없이) ③ Test_006 Z 단면뷰 다섯 가지(plain · fit · fit_m0 · pattern · declined, 보폭 400 = 3프레임)
    ④ 남은 Xvfb · 링크 덱에 떨어진 것 · 원본 덱 폴더 여섯 곳의 수정 시각. `local` 은 같은 일을 로컬 빌드(`.work/beam_viewfit/inst_dep`)로 돈다.
  - `cmp_v52.py <옛 태그> <새 태그>` — 분석기 산출을 각인 · 빔 줄만 떼고 바이트로 맞대고(허용: ElasticBeam 파트 4 의 빔 줄 넷 + 새 CSV 넷),
    빔 값을 lasso 기준값과(1e-9), deep 의 파트 4 피크와 표식, 카메라 프레임 md5 와 안내 줄을 본다. 끝 줄 「어긋난 것 N」, 어긋나면 rc 1.
  - 렌더는 꾸러미 안 심볼릭 링크 덱 `deck006/` · `deck_eb/` 로만 돈다. 기준 프레임은 `ref/`(로컬 빌드 d2f0d6b 가 찍은 10장).
- **v51 기준선**(`check_v51.log`) — VERSION 226eca7. 분석기 여섯 덱 rc 0 · 빔 사유 줄 0. ElasticBeam 파트 4 피크 None(「응력 이력 없음」).
  `plain` rc 0 · 3프레임, 나머지 네 칸은 rc 2(`unrecognized arguments: --view-fit …` — 옛 판이라 당연하다). 남은 Xvfb 0 · 원본 덱 폴더 그대로.
  - **배포판 v51 의 `plain` 프레임이 로컬 빌드와 md5 까지 같다**(3a33f80f4e80 / bebd441aec07). SIF 의 렌더 스택이 달라 md5 가 어긋날까 봐
    화소 비교(`framecmp.py`)를 넣었는데, 실제로는 md5 를 그대로 맞대도 된다.
- **로컬 예행**(`check_local.log` · `cmp_v51_local.log`) — 「어긋난 것 0」.
  - 분석기 산출은 여섯 덱 모두 ElasticBeam 파트 4 의 빔 줄 · 새 CSV 넷 · 각인 말고 바이트까지 같다(공통 파일 Test_006 170 · ElasticBeam 26 ·
    DynaAnalysis 28 · case_shell 6 · 두꺼운 셸 283 · airbag 487). 핫스팟 세 기준을 켠 Test_006 · 두꺼운 셸 · airbag 은 이번에 처음 옛 · 새 판을 맞댄 덱이다.
  - 빔 값은 lasso 기준과 같고, DynaAnalysis 사유 줄 1 · deep 파트 4 피크 999.5647325 · 「빔 · 적분점 최대」 1.
  - 카메라 다섯 칸 rc 0 · 1280×720 · 3프레임, 프레임이 기준과 md5 동일. `declined` 는 `[설정]` 안내가 로그와 보고서에 실렸다. `_zoom` 0 · 남은 Xvfb 0.

## v52 배포 · 확인 (11-21)
- **배포** — pykoocae-53 이 11:25:37 – 11:37:17 UTC 에 구웠다(`/data/koopark/Post_v52/post_release.log`, `RELEASE_RC=0`). 스왑 39/39 GB 가 찬 머신이라
  `post_release_capped.sh` 로 묶어 돌렸다 — `systemd-run --scope` 의 `MemoryMax=28G` · `MemorySwapMax=0`, `taskset -c 0-7` · `nice -n 10`,
  가용 메모리가 8.5 GB 아래로 내려가면 멈추는 감시. 굽는 동안 최저 가용 34,448,872 kB. Drive 올림 셋과 메일 발송까지 로그에 있다.
  - 헤드리스 SIF 1,156,812,800 B · sha256 `75b03b9d43d634a59830e8a7e45f87cfc7ac8b35bcfc9141c0bf47ff9fa4760f` — VERSION `d2f0d6b` ·
    Built `2026-11-21T11:27:18Z` · Viewer false · LSPrePost bundled.
  - GUI SIF 370,671,616 B · sha256 `992a0a646b80b8bee0d55bb805d9c824bf4aa150167e5ef9068955a0ff5ab0b6` — VERSION `d2f0d6b` ·
    Built `2026-11-21T11:31:47Z` · Viewer true · LSPrePost not included.
  - tar `/data/SmartTwinPostprocessor/SmartTwinPostprocessor_20261121_v52.tar.gz` 575,429,803 B ·
    sha256 `7bbdd2c241182521faf19ed6bd4294d8ef3308099f23634a73e8c3c278412f25`.
  - **네 지점이 같다** — 빌드 원본 `apptainer/` · `/data/SmartTwinPostprocessor/` · 헤드 `/opt/apptainers/` ·
    `KooSlurmInstallAutomationRefactory/apptainer/compute-node-images/` 의 SIF 여덟 개와 tar 의 sha256 을 직접 셌다(12:07 UTC).
    각인은 NFS · 헤드 사본 넷을 `--no-home` 으로 읽었다.
  - 옛 판(v51) 사본 — `/data/SmartTwinPostprocessor/SmartTwinPostprocessor_backup_20261121_113203.sif`,
    `/opt/apptainers/SmartTwinPostprocessor{,GUI}_backup_20261121_114036.sif`.
  - **노드 로컬 사본은 옛 판 그대로다** — `sinfo`(12:00 UTC)에서 node001 · node002 · viz-node001 이 `down*`, viz-node002 가 `unknown*`.
    기록에 남은 마지막 노드 판은 v47 이다(`report_figures_2026-11/context-notes.md`). VM 이 뜨면 따로 바꿔야 한다.
- **배포 세션 판정**(태그 `v52` — `check_v52.log` · `cmp_v51_v52.log`) — VERSION d2f0d6b, 분석기 여섯 덱 rc 0(DynaAnalysis 사유 줄 1),
  카메라 다섯 칸 rc 0 · 1280×720 · 3프레임 · 기준 프레임과 동일, `cmp_v52.py v51 v52` 「어긋난 것 0」. 알려진 나쁜 입력 `cmp_v52.py v51 v51` 은
  rc 1 이다(`knownbad_v51_as_new.log` — `!!` 15줄 뒤, v51 에는 `declined/` 가 없어 `FileNotFoundError` 로 끝난다. 종료 코드가 0 이 아니라
  판정은 서므로 꾸러미는 그대로 뒀다).
- **직접 다시 잰 것**(태그 `v52b` — 헤드 사본 `/opt/apptainers/SmartTwinPostprocessor.sif` · `--no-home`, `check_v52b.log` · `cmp_v51_v52b.log`) — 「어긋난 것 0」.
  - 분석기 여섯 덱 rc 0, DynaAnalysis 사유 줄 1. 산출은 ElasticBeam 파트 4 의 빔 줄 넷 · 새 CSV 넷 · 각인 말고 v51 과 바이트까지 같다
    (공통 파일 Test_006 170 · ElasticBeam 26 · DynaAnalysis 28 · case_shell 6 · 두꺼운 셸 283 · airbag 487).
  - deep — 파트 1 `Hex` 998.6226228 · 2 `Tet` 1001.069475 · 3 `Shell` 999.3968813 · 4 `Beam` 999.5647325(t = 1), 「빔 · 적분점 최대」 1곳,
    「빔 파트 [4] 는 면이 없어 스냅샷을 만들지 않는다」 줄.
  - 카메라 — plain 52초 · fit 23 · fit_m0 21 · pattern 19 · declined 18, 다섯 칸 rc 0 · `1280,720,3`, 프레임 md5 가 `cmp_v52.py` 의 `LOCAL` 표와 같다.
    `declined` 는 `[설정]` 안내가 로그와 보고서에 실렸다. `_zoom` 0 · 남은 Xvfb 0 · 원본 덱 폴더 여섯 곳의 수정 시각 그대로.
    링크 덱 `deck006` 에는 `lspost.cfile` · `lspost.msg` 가 떨어진다(그걸 받으라고 둔 링크 덱이다).
- **배포 뒤 더 본 것**
  - **σ1 독립 대조** — 「빔 — 구현에서 확정한 것」 절에서 lasso 와 맞댄 것은 σ_vm · σ3 뿐이었다. ElasticBeam t = 1 의 σ1 을 lasso · numpy 로 따로 내면
    최대 999.5647325(요소 1117) · 최소 94.5958199(1136) · 평균 689.3463558 로 분석기 값과 같다. σ_vm 과 숫자까지 같은 것은 이 덱의 전단 워드가
    전부 0 이라서다 — 그러면 σ_vm = |σ_축|, σ1 = max(σ_축, 0) 이고, 요소 20개의 평균까지 같으니 요소마다 인장 쪽 적분점이 더 크다는 뜻이다.
    그래서 이 대조는 주응력 식의 전단 항을 보지 못한다.
    - 꾸러미 `cmp_v52.py` 의 기준표에 σ1 줄을 넣고(11:59 UTC) 세 판을 다시 맞댔다 — `cmp_v51_v52_s1.log` · `cmp_v51_v52b_s1.log` ·
      `cmp_v51_local_s1.log` 모두 「어긋난 것 0」. σ1 줄이 없던 때의 로그(`cmp_v51_v52.log` · `cmp_v51_v52b.log` · `cmp_v51_local.log` ·
      `knownbad_v51_as_new.log`)는 그대로 둔다.
    - 새 줄이 잡는지 기준값을 바꿔 봤다 — 값(999.5657325) · 요소 번호 맞바꿈 · 평균(689.3473558)은 rc 1 로 잡히고, 1e-7 변이(999.5647326)는
      **잡히지 않는다**. 꾸러미의 값 비교는 상대 1e-9, 곧 아홉 자리쯤까지다. 「lasso 와 10자리 일치」 는 값을 직접 맞댄 결과지 꾸러미가 보장하는 것이 아니다.
  - **빔 워드 순서의 값 근거는 축응력 · 축변형률 자리뿐이다** — ElasticBeam 의 lasso 배열을 다시 세면 `element_beam_axial_stress` 와
    `element_beam_axial_strain` 은 0 이 아닌 값이 180개씩인데, `element_beam_shear_stress`(2 × 20 × 9 × 2)와 `element_beam_plastic_strain` 에는
    **0 이 아닌 값이 하나도 없다**. 실덱이 값으로 받쳐 주는 것은 첫째 워드 = 축응력, 다섯째 워드 = 축변형률(σ = E·ε, E = 1.0E7)이고,
    둘째 – 넷째 워드(τ_rs · τ_tr · ε_p)의 자리는 lasso-python 2.0.3 의 배치를 따른 것이다. 합성 시험(`BeamPartHistory`)은 전단 · 소성 워드를 채워 식을 보지만,
    읽는 쪽과 같은 배치로 쓴 자료라 자리의 근거는 못 된다. 전단이나 소성이 생기는 빔(Hughes-Liu 소성 빔 따위)의 σ_vm · ε_p 는 실덱 값으로 확인한 적이 없다 —
    앞 절들의 「실데이터 근거는 R13.1.1 덱 하나」 를 이만큼 좁혀 읽어야 한다.
  - **DynaForge 꾸러미가 받는 것** — ElasticBeam 의 `report.ontology.json` 을 v51 · v52b 로 맞대면 어휘 0.5 와 객체 수(캠페인 1 · 런 1 · 파트 4 ·
    파트 응답 4)는 그대로고 달라지는 것은 셋이다(4,635 → 4,959 B).
    ① `cae_part part/4` 에 `worst_von_mises` 999.5647325 · `worst_von_mises_run` · `worst_max_principal` 999.5647325 · `worst_min_principal` −999.514809 ·
    `worst_plastic_strain` 0 이 생기고 `n_runs_measured` 가 0 → 1. ② `cae_part_response resp/single/4` 에 `peak_von_mises` · `peak_von_mises_time` 1 ·
    `peak_max_principal` · `peak_max_principal_time` 1 · `min_principal` · `peak_plastic_strain` 0. ③ 각인(`cae_run.analyzer_commit` 226eca7 → d2f0d6b ·
    `cae_campaign.produced_at`). 빔에는 변형률 계열 값이 없고, 꾸러미에도 deep `result.json` 에도 요소 종류 키가 없다. `severity` 는 UNKNOWN 그대로다
    (탄성 재료라 항복 한계가 없다). 항복 한계가 있는 빔 파트에는 `min_safety_factor` · `yield_limit` · `yield_criterion` · `severity` 가 붙는다 —
    코드 경로로만 봤고 돌려 본 덱은 없다.
  - **DynaForge 검사기 통과** — 그쪽 저장소의 `KooRemapper/platform/backend/app/reports/onto_package.py` `check()` 에 v51 · v52 · v52b 꾸러미를
    그대로 넣으면 셋 다 통과한다(행 5 · 선 1 · 경고 없음 — `.work/beam_viewfit/sphere_csv/check_dynaforge.py` · `.out`). 검사기는 읽기만 했다.
  - **sphere 로 가는 길이 있다** — sphere 는 `stress_history` 키를 읽지 않지만(참조 0건), 적재기 `loader.py` `load_simulation_result()` 가
    `metadata.analyzed_parts` 의 파트마다 `stress/part_{pid}_von_mises.csv`(726행) · `…_max_principal_stress.csv`(732) ·
    `…_min_principal_stress.csv`(735) · `strain/part_{pid}_eff_plastic_strain.csv`(748)를 있으면 읽는다. v52 는 빔 파트에 이 넷을 새로 쓰고
    (열은 솔리드 것과 같다 — 요소 종류 열이 없다), 빔 파트 번호는 운동 작업 덕에 v51 때도 `analyzed_parts` 에 있었다. 적재기를 두 판 산출에 직접 돌리면
    (`.work/beam_viewfit/sphere_csv/probe_loader.py` · `.out`) 파트 4 의 `peak_stress` · `peak_principal` · `min_principal` · `peak_strain` 이
    v51 에서는 전부 None, v52b 에서는 999.5647325 · 999.5647325 · −999.514809 · 0.0 이다. 파트 1 – 3 은 두 판이 같다.
    - sphere 는 그 파트가 빔인 줄 모른다. `models.py:268`(`peak_stress`) → `report/json_report.py:162` · `report/html_report.py:232` 로 솔리드와 같은 길을 타고,
      `analyzer.py` 의 항복 판정도 파트 종류를 가리지 않는다(`pr.peak_stress` · `pr.peak_principal` 을 파트의 한계와 견준다 — 코드로만 봤다).
      `stress_ts.elem` 은 `Max_Element_ID` 를 보여 줄 뿐 메시에서 찾지 않는다.
    - **이번 판의 「회귀 불요」 는 그대로 선다** — 적분 빔이 없는 다섯 덱은 CSV 까지 v51 과 바이트로 같고, 훑은 `/data` 2,476 폴더 중 적분 빔 덱은
      ElasticBeam 하나며 sphere 캠페인이 아니다. 적분 빔이 든 덱으로 캠페인을 돌리면 v52 부터 빔 파트 값이 sphere 표 · 항복 판정 · 온톨로지 꾸러미에
      실린다 — 아무도 돌려 본 적 없는 자리다.
    - a9 의 원장(`docs/sphere_automation_2026-10/release-verdicts.md`) v52 항목은 이 길을 「통로 자체가 없다」 로 적고 있었다. 11:57 UTC 쯤 알렸고
      a9 가 af0b301 로 고쳤다(통로 4 를 「분석기 산출 폴더 전체 — 파트별 CSV 포함」 으로 넓힘). 원장은 그쪽 파일이라 손대지 않았다.
    - a9 가 미리 짚어 둔 것 — 핫스팟 군집이 빔을 품게 되면 sphere 가 `hotspot_clusters[].element_type` 의 `"beam"` 을 `meta["et"]`
      (`report/html_report.py:481`)로 그대로 싣는다. 빔을 핫스팟에 넣는 일을 하게 되면 먼저 a9 에 알린다.
- **알림** — kooremapper-4a(DynaForge)에 v52 판 알림을 보냈다(11:57 UTC 쯤 — 판 지문 · 바뀐 것 둘 · 확인한 것 · 남는 한계). 회신은 청하지 않았고,
  그쪽이 다른 일을 하는 중이라 수신함에 들어간 것까지만 안다. a9 에 보낸 것은 위와 같다.
- **저장소** — a9 가 d2f0d6b 위에 12c2cb4 · c033f66 · af0b301(원장)을 올려 origin/main = af0b301 이다. 이 절과 checklist 6절을 담은 커밋은
  그 위 로컬에 있고, push 는 사용자 승인 뒤에 한다.
- **치운 것** — 11-08 부터 떠 있던 내 배경 셸 하나(`xargs … grep` 이 표준 입력을 기다리며 멈춰 있었다)를 끝냈다.
- **남는 것** — 노드 로컬 SIF(v47 → 최신, VM 이 뜨면) · 전단이나 소성이 있는 빔 덱으로 값 확인(라이선스가 살아나면) ·
  적분 빔 캠페인이 생기면 sphere 쪽 표식과 판정 · 솔리드 첫 적분점(44 덱). 앞의 둘은 지금 손댈 수 없고, 뒤의 둘은 요청받지 않았다.
