# 결정 기록 — 빔 파트 응력 이력 · 카메라 타겟 맞춤

## 출발 (11-20)
- 사용자 「카메라 타겟 맞추기와 빔도 마저 해줘」. 둘 다 앞선 작업에서 「필요하면 다음에」 로 미뤄 둔 항목이다
  (`report_figures_2026-11/checklist.md` 3단계의 `--view-fit`, `shell_plastic_2026-11` 의 「빔 · 이산 요소는 여전히 이력이 없다」).

## 빔 — 조사에서 확정한 것
- **워드 배치(규격 `ls-dyna_database.txt`)** — 제어 워드 NEL2 28 · NUMMAT2 29 · NV1D 30, 확장(EXTRA > 0) NEIPB 67 · BEMENG 80.
  `NV1D = 6 + 5·BEAMIP + NEIPB·(3 + BEAMIP)`. 요소당 합력 6(축력 · S 전단 · T 전단 · S 모멘트 · T 모멘트 · 비틀림),
  적분점마다 5(τ_rs · τ_tr · σ_축 · ε_p · ε_축), 그 뒤 이력 변수. BEMENG > 0 이면 그 자리(1부터 셈)에 내부 에너지 밀도 워드.
- **실측** — R16 덱(EXTRA 64)은 빔이 없어도 `NV1D 7 · BEMENG 7`(합력 6 + 에너지 1). R13 `ElasticBeam` 은 EXTRA 0 · `NV1D 51` = 6 + 5×9.
- **데이터** — `/data` 2,476개 d3plot 폴더 중 빔이 있는 것은 2개뿐(`ElasticBeam` BEAMIP 9, `DynaAnalysis` NV1D 6). 둘 다 R13 · EXTRA 0.
  R16 배치(BEMENG 와 BEAMIP > 0 의 조합)는 실데이터가 없어 로컬 솔버로 작은 덱을 만들어 잰다.
- **`ControlData` 에 NEIPB · BEMENG 이 없다** — 파서가 확장 워드를 건너뛴다(`ControlDataParser.cpp` 「For now, we skip them」).

## 빔 — 설계 결정
- **빔 배열을 따로 두고 끝에서 합친다.** `part_ids_` · `part_kind_` · `HotspotElementKind` 는 건드리지 않는다. 빔 전용 파트 색인과 결과
  벡터 4개(σ_vm · σ1 · σ3 · ε_p)를 두고 `buildResult` 에서 기존 이력 뒤에 붙여 파트 번호순으로 안정 정렬한다.
  - 변형률 텐서 계열(`vm_strain` · 주변형률)에는 빔이 들어가지 않는다. `part_ids_` 에 넣으면 그 계열에 전부 NaN 인 빔 줄이 생기고,
    JSON 은 `global_unmeasured: true` 로 쓰는데 파이썬은 그 키를 읽지 않아 `global_max = 0.0` 으로 읽는다(0 위장). 또 `buildResult` 의
    주변형률 「전부 0 이면 버림」 판정이 깨진다(전부 NaN 인 줄의 `globalMax()` 는 −inf).
  - 핫스팟 · 피크 텐서 · `markUnmeasuredParts` 등 `part_ids_` 로 도는 코드를 그대로 둔다 — 솔리드 · 셸 덱 출력이 바이트 단위로 같다.
  - 솔리드 · 셸 파트와 번호가 겹치는 빔 파트는 건너뛴다(먼저 온 종류가 이긴다 — 셸과 같은 규칙).
- **적분점 값이 있는 파트만.** 세 진입점 모두 결과를 할당하기 전에 전 상태가 메모리에 있다. 할당 전에 빔 파트마다 「유한하고 0 아닌
  적분점 워드가 한 번이라도 있는가」 를 훑어, 없는 파트는 이력을 만들지 않고 사유를 찍는다. 상태별 NaN 표식은 맞지 않는다 —
  적분 빔도 상태 0 은 전부 0 이다. 파트 단위 · 실행 전체의 판정이어야 한다.
- **요소 값 = 적분점 극값**(셸의 층 극값과 같은 규칙). 빔 국부계 응력은 σ_rr · τ_rs · τ_tr 셋뿐이라
  σ_vm = √(σ_a² + 3(τ_rs² + τ_tr²)), 주응력은 텐서 {σ_a, 0, 0, τ_rs, 0, τ_tr} 의 고유값.
- **핫스팟에는 넣지 않는다.** 군집은 면 이웃으로 묶는데 빔은 면이 없다. DynaForge 어휘 0.5 의 `element_type` 열거값
  (solid · thick_shell · shell)은 「응력 집중 군집」 형에만 있고 `ontology/deep.py` 는 `element_type` 을 쓰지 않는다 — 어휘 영향 없음.

## 카메라 — 조사에서 확정한 것
- 개관 작업은 YAML `render_jobs`(deep `build_lsprepost_section_jobs` · `build_render_jobs`). 타겟 = `highlight_parts`, 나머지 = `context_parts`.
- `generateScript` 순서 — 열기 · `ac` · 타겟 강조(genselect remove → reverse → fringe → 전체 복원) · 숨김(`-M`) · 시점 문자열 + `ac` ·
  단면(`splane …` + `ac`) · 영상. 카메라는 보이는 모델 전체에 맞는다.
- LS-PrePost 4.12 배치 실측(앞선 작업) — `selectpart part N on` 은 「N 만 표시」, `-M <id>` 는 하나 숨김, `fringe` · `selectpart all on` 은
  숨김을 되돌려 `-M` 을 다시 넣어야 한다. 여러 파트만 남기는 검증된 방법은 genselect remove + reverse.
