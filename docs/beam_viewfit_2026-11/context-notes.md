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
  - lasso 2.2.6 이 `beam_layer_data[..., 0]` 을 축응력, `[..., 1:3]` 을 전단, `[..., 3]` 을 소성 변형률, `[..., 4]` 를 축 변형률로 읽는다.
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

## 카메라 — 조사에서 확정한 것
- 개관 작업은 YAML `render_jobs`(deep `build_lsprepost_section_jobs` · `build_render_jobs`). 타겟 = `highlight_parts`, 나머지 = `context_parts`.
- `generateScript` 순서 — 열기 · `ac` · 타겟 강조(genselect remove → reverse → fringe → 전체 복원) · 숨김(`-M`) · 시점 문자열 + `ac` ·
  단면(`splane …` + `ac`) · 영상. 카메라는 보이는 모델 전체에 맞는다.
- LS-PrePost 4.12 배치 실측(앞선 작업) — `selectpart part N on` 은 「N 만 표시」, `-M <id>` 는 하나 숨김, `fringe` · `selectpart all on` 은
  숨김을 되돌려 `-M` 을 다시 넣어야 한다. 여러 파트만 남기는 검증된 방법은 genselect remove + reverse.
