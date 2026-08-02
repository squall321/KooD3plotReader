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
