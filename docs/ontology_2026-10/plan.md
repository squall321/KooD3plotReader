# 해석 결과 온톨로지화 — 설계안 v0 (2026-10-31)

**요청(사용자)** 전각도 낙하 시뮬레이션 결과를 온톨로지화해 그 꼴 그대로 DynaForge 에 넣는다. 구조·충격해석 개념을
DynaForge 온톨로지 모듈 안에서 **DynaForge 전용 용어**로 만든다. deep · sphere · impact 후처리가 리포트와 함께
온톨로지 모듈과 연동되는 결과를 같이 낸다.

## 1. 목표
- 세 후처리(deep · sphere · impact)가 리포트 옆에 **온톨로지 꾸러미**(`ontology.json`)를 함께 낸다.
- 꾸러미는 DynaForge 전용 해석 어휘(`cae_*`)로 쓴 인스턴스(객체 · 관계)다. 어휘 정본은 DynaForge(10-31 결정), 이쪽은 바이트 사본
  `python/koo_deep_report/koo_deep_report/ontology/dynaforge-cae.json`.
- DynaForge 가 리포트를 받을 때 꾸러미도 받아 `onto_objects` · `onto_relations` 에 올리고, 파트 · 런 · 하중 경로
  네트워크로 질의한다(예 「이 파트로 충격량이 가장 많이 들어오는 경로와 방향」, 「안전율 1.5 미만인 파트의 최악 방향」).
- 1차 대상은 전각도 낙하(sphere). 같은 어휘로 deep(런 하나) · impact(전위치)를 잇는다.

## 2. 현황 — 조사로 확인한 것
**DynaForge 온톨로지 모듈** (KooRemapper `platform/`)
- 정의는 SP(StandardPlatform) import 꼴 — `groups / types(properties) / relation_types(cardinality)`, slug 영문 snake_case,
  이름 · 설명 한국어, 단위는 속성마다 표시용 글자 하나(변환 없음).
- 인스턴스는 DB 행 — `onto_objects(type_slug, key, label, properties)`, `onto_relations(관계, 양 끝 type·key, properties)`.
  관계는 다섯 값(관계 · 양 끝)이 유일하다. 지우지 않고 「삭제됨」 표시.
- 자체 어휘는 `dev_revision`(개발 개정) 하나뿐이고 **해석 개념 용어는 없다.** 자체 정의 파일은 런타임에 적재되지 않고,
  시험이 「타입은 dev_revision 하나」 · 「쓰기 경로 목록」 을 고정한다. 바깥에서 인스턴스를 밀어 넣는 API 가 없다.
- 해석 수치는 지금 리포트 표(`impact_reports` · `impact_cases.parts_metrics`)에만 있다.
- SP 관례: 도메인 묶음은 따로 파일, 타입 · 속성은 `<그룹코드>_` 접두. 허브에 CAE 확장 초안(`sim_test_item` · `sim_analysis`)이 있다.

**후처리(이 저장소)**
- 런마다 파트별 최대 등가응력 · 주응력 · 소성/등가 변형률 · G · 변위 · IE/KE 와 시각, 핫스팟 군집, 에너지 흐름 그래프
  (노드 = 파트, 엣지 = 접촉, 충격량 · 일)가 있다.
- 각도 사이 집계(최악값 · 변동계수 · 안전율)는 대부분 **HTML 의 JS 안**에만 있다. JS 의 안전율은 파트별 항복값과 단위를 무시한다.
- 에너지 흐름에 **단위가 없고**, 접촉 종류(TIED 등)는 버려지며, 각도를 가로지르는 하중 경로 집계가 없다.
- report.json 에 스키마 판 · 생성 시각 · 도구 커밋이 없다.

## 3. 어휘 — 초안 v0 (지금은 사본 `ontology/dynaforge-cae.json`, 정본 DynaForge)
그룹 `cae` 「해석 결과」, 타입 9 · 속성 118 · 관계 13. **DynaForge 검증기 결함 0 · 주의 0, `dynaforge-core.json` 과 합쳐도 0.**

| 타입 | 이름 | 무엇 | 키(캠페인 안) |
|---|---|---|---|
| `cae_campaign` | 해석 캠페인 | 후처리 한 번이 다룬 해석 묶음(전각도 낙하 · 전위치 충격 · 런 하나), 단위계 · 항복값 출처 | `campaign` |
| `cae_run` | 해석 런 | 해석 한 번 — 낙하 방향(roll/pitch/yaw · 충격 방향 벡터 · 분류) 또는 충격 위치, 첫 접촉 시각, S1 해시 | `run/<런 키>` |
| `cae_part` | 해석 파트 | PID 하나 + **전 방향 포락**(최악 등가응력 · 주응력 · 소성변형률 · G 와 그 런, 최소 안전율, 판정, 방향 의존도) | `part/<PID>` |
| `cae_part_response` | 파트 응답 | 런 × 파트 최대 응답(응력 · 변형률 · G · 변위 · 에너지와 시각, 이 런 안전율) | `resp/<런>/<PID>` |
| `cae_contact` | 접촉 정의 | 덱 `*CONTACT…_ID` 하나(카드 이름으로 묶임/맞닿음 구분) | `contact/<CID>` |
| `cae_load_transfer` | 하중 전달 | 런 × 접촉 — 보내는 · 받는 파트, 최대 접촉력, 충격량, 전달 일, 첫 맞닿음, 전파 깊이 | `xfer/<런>/<CID>` |
| `cae_load_path` | 하중 경로 | 파트 쌍의 **전 런 집계** — 맞닿은 비율, 방향 수, 충격량 최대 · 중앙 · 90%, 최대 런 | `path/<a>-<b>` |
| `cae_hotspot` | 응력 집중 군집 | 런 × 파트 × 기준량 덩어리 — 중심 · 반경 · 응력 · 최대 요소 | `hs/<런>/<PID>/<기준>/<순위>` |
| `cae_finding` | 판정 소견 | 후처리 판정 문장(심각도 · 제목 · 내용 · 권고) | `finding/<순번>` |

관계: `run_of` · `part_in_campaign` · `campaign_report`(→ `impact_report`) · `response_in` · `response_of` · `contact_side`
(줄 properties.role = slave/master) · `transfer_in` · `transfer_via` · `transfer_from` · `transfer_to` · `path_between` ·
`hotspot_of` · `finding_about`.

설계 판단
- **파트는 캠페인 범위**다. 같은 모델의 각도 1,000개가 같은 파트를 가리키고, 전 방향 포락은 파트에 둔다.
- **런마다의 파트 사이 전달은 객체로 세운다**(`cae_load_transfer`). 관계는 (관계 · 양 끝)이 유일해서 같은 두 파트 사이 런별 값을
  관계 줄에 담을 수 없다.
- **양의 정의를 `help` 에 박는다** — 예 `peak_g` = 파트 평균 가속도 크기 최대 ÷ 1 G, `peak_displacement` = 절점 변위 크기 최대(평균 아님),
  `total_work` = 평균 강체속도 차로 셈한 대리값, `peak_vm_strain` ≠ 유효소성변형률. 받는 쪽이 이름만 보고 다른 양으로 읽는 일을 막는다.
- **시계열은 담지 않는다.** 리포트 · S1 이 정본이고, 런은 S1 해시로 잇는다.
- 기존 이름과 겹치지 않는다(`cae_` 접두). 허브의 `sim_*` 와는 나중에 맞춤 표로 잇는다.

## 4. 꾸러미 꼴 — `dynaforge.onto_package` v1
```json
{
  "format": "dynaforge.onto_package", "format_version": 1,
  "vocabulary": {"group": "cae", "sha256": "<어휘 파일 해시>"},
  "producer": {"tool": "koo_sphere_report", "version": "<커밋>", "created_utc": "…"},
  "units": {"system": "ton_mm_s", "normalized": true},
  "objects":   [{"type": "cae_run", "key": "run/Run_20260602_093237_801e2b", "label": "F_TOP",
                 "properties": {"campaign": "campaign", "roll_deg": 0, "pitch_deg": 90, "…": "…"}}],
  "relations": [{"relation": "run_of", "src": ["cae_run", "run/Run_…"], "dst": ["cae_campaign", "campaign"], "properties": {}}]
}
```
- 키는 **캠페인 안 상대 키**다. DynaForge 가 적재할 때 `<리포트 키>/` 를 앞에 붙인다(drop-twin 계획의 run_id = report_id + case_key 와 같은 원칙).
  `object_ref` 값도 상대 키로 쓰고 같은 규칙으로 바뀐다.
- 만드는 쪽은 어휘로 검증하고 쓴다 — 없는 타입 · 속성 · 열거값, 빠진 필수값이면 꾸러미를 쓰지 않고 실패.
- 값이 없으면 키를 뺀다(0 이나 null 로 채우지 않는다 — 리포트 결측 규약과 같다).

## 5. 매핑 — 전각도 낙하(sphere) 기준
| 어휘 | 원천 |
|---|---|
| `cae_campaign` | report: project/test_dir · runs 수 · doe_strategy · angular_spacing · sphere_coverage · unit_system · g_factor, DropSet 낙하 높이, 항복값 출처 |
| `cae_run` | SimulationResult: run_folder · angle(name · roll/pitch/yaw · category) · num_states · end_time · success · tool_commit; 충격 방향 = Rᵀ(0,0,−1); S1 s1.json(first_contact_s · sha256) |
| `cae_part` | parts{pid: name, group}; 포락은 런별 응답에서 Python 으로 새로 셈(최댓값 · 그 런 · 변동계수), 안전율 = yield_map(min 한계 ÷ 최대 응력, 기준별 응력), 판정 규칙은 analyzer 와 같게 |
| `cae_part_response` | PartResult: stress/principal/strain/vm_strain/motion/energy 의 true_peak · 시각, 단위 정규화 |
| `cae_contact` | contact_map(덱 `*CONTACT…_ID`) — **카드 이름을 보존하도록 contact_map 을 고친다** |
| `cae_load_transfer` | energy_flows edges(전 런 — slim 도 src·dst·cid·peak_force·total_impulse·total_work 가 있다), 상위 60 런은 first_engage · depth 까지 |
| `cae_load_path` | 위 전달을 파트 쌍으로 모아 새로 셈(맞닿은 런 수 · 방향 수 · 충격량 통계) |
| `cae_hotspot` | analysis_result.json hotspot_clusters(켠 덱만) |
| `cae_finding` | Report.findings — 파트 소견은 파트 번호를 달도록 analyzer 를 고친다(koo_sphere_report 담당과 맞춤) |

크기 어림 — 1,000 방향 × 23 파트면 응답 2.3만, 전달 2–6만, 관계는 객체의 약 2배 → JSON 수십 MB(gzip 약 1/5).

## 6. 할 일
**KooD3plotReader (이 세션)**
1. 공용 모듈 `koo_deep_report/ontology/` — 어휘 사본 · 꾸러미 작성기 · 어휘 검증 · 단위 정규화(SI · ton-mm-s 는 정확한 환산, 못 감지하면 원값 + `values_normalized=false`).
2. sphere 매핑 + 각도 사이 집계(Python). JS 와 정의를 맞추고, JS 안전율 결함(파트 항복값 · 단위 무시)은 따로 보고.
3. contact_map 이 접촉 카드 이름을 보존. 에너지 흐름 값에 단위를 붙인다.
4. impact · deep 매핑.
5. 시험 — 합성 데이터 단위 시험 + 실캠페인(Test_005 · Test_Postprocess_v14)으로 꾸러미 생성 · 어휘 검증 · 크기 · 리포트 수치와 일치.
6. sphere 연결은 koo_sphere_report 담당 세션(kood3plotreader-a9)과 맞춘다(그 세션이 해당 파일을 고치는 중).

**DynaForge (KooRemapper — 담당 · 위치는 결정 사항)**
1. 어휘 채택 — `platform/core/ontology/` 에 새 그룹 파일(SP 관례) 또는 `dynaforge-core.json` 에 합침. 시험의 「타입은 dev_revision 하나」 고정 풀기.
2. 자체 정의를 런타임에 `onto_types` 로 적재(source = dynaforge) — 지금은 적재되지 않는다.
3. 리포트를 받을 때 `ontology.json` 을 받아 upsert(키 접두 · 같은 리포트 재적재 때 옛 행 삭제 표시). 쓰기 경로 목록 시험 갱신.
4. 질의 — MCP 도구 · 화면(하중 경로 상위, 파트 최악 방향, 안전율 미달 목록).

## 7. 결정 — 사용자 확정 (10-31)
1. **단위** — 감지된 단위계면 어휘 단위(MPa · mm · s · mJ · N · N·s · mm/s · G)로 바꿔 싣고, 못 감지하면 원값 + 표시. ✅ 구현
2. **세밀도** — 런별 응답 · 전달까지 전부 + 캠페인 집계. 시계열은 담지 않는다. ✅ 구현
3. **기본 산출** — 세 리포트가 늘 함께 낸다(기존 산출 불변, 꾸러미 실패는 경고만). ✅ 구현
4. **DynaForge 쪽 작업** — DynaForge 세션이 채택 · 적재 · 질의를 맡는다. 어휘 정본은 DynaForge `platform/core/ontology/dynaforge-cae.json`, 이쪽은 바이트 사본. 적재는 (가) 캠페인 수준만 행으로.
5. **내보내기** — push 하고 상류 표준 경로로 SIF 재빌드 · 배포를 청한다.

## 8. 진행 (10-31)
- 어휘 v0.1(9타입 126속성 13관계) · 꾸러미 작성기 · sphere/impact/deep 어댑터 · post_analyze 마지막 단계 · koo_ontology 래퍼.
- 실데이터 대조 통과 — [package-contract.md](package-contract.md) §7. 계약은 그 문서가 정본.
- 남음: SIF 재빌드 · 배포(상류 표준 경로), DynaForge 채택 · 적재, sphere report.json 의 런 끝 시각 · 커밋 · 소견 파트 번호(a9).
