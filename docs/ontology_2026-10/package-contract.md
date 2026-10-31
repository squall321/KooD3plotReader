# 온톨로지 꾸러미 계약 — 초안 2 (2026-10-31)

초안 1 에 DynaForge 검토 답신(KooRemapper `docs/requests/kood3plotreader-ontology-review-2026-10-31.md`, 7e8252d)을
반영했다 — 심각도 대문자, 런 키를 `impact_cases.case_key` 와 같게(deep 은 `single`), 다대일 관계는 줄로 싣지 않음,
낙하 높이 · 충돌 속도 · 재질 칸.

후처리(KooD3plotReader)가 리포트와 함께 내는 **DynaForge 해석 어휘(`cae_*`) 인스턴스 꾸러미**의 꼴과 받는 법.
어휘 정의는 [dynaforge-cae.draft.json](dynaforge-cae.draft.json)(SP import 꼴, DynaForge 검증기 결함 0·주의 0),
정본 소스는 `python/koo_deep_report/koo_deep_report/ontology/vocabulary.py` 다.

## 1. 어디에 생기나

| 리포트 | 꾸러미 | 만드는 때 |
|---|---|---|
| 전각도 낙하 (koo_sphere_report) | `<캠페인>/report.ontology.json` (그룹이면 `report_<그룹>.ontology.json`) | post_analyze 마지막 단계(S1 다음) |
| 전위치 부분충격 (koo_impact_report) | `<캠페인>/impact_report.ontology.json` | 같음 |
| 런 하나 (koo_deep_report) | deep 산출 폴더의 `ontology.json` (result.json 옆) | deep 리포트가 스스로 |

손으로 다시 만들 때는 `koo_ontology sphere <report.json> [--test-dir DIR] [--yield-stress MPa] [--yield-map FILE]`,
`koo_ontology impact <impact_report.json>`. 어휘 JSON 은 `koo_ontology vocab`.

## 2. 꼴 (`dynaforge.onto_package` format_version 1)

```json
{
  "format": "dynaforge.onto_package", "format_version": 1,
  "vocabulary": {"group": "cae", "version": "0.1", "sha256": "<어휘 JSON 의 sha256>"},
  "producer": {"tool": "koo_deep_report.ontology", "adapter": "sphere|impact|deep",
               "version": "<모듈 VERSION>", "created_utc": "..."},
  "source": {"kind": "koo_sphere_report/report.json", "file": "report.json", "sha256": "..."},
  "scope": {"scenario_kind": "drop_all_angle|impact_all_position|single_run", "campaign_key": "campaign"},
  "units": {"system": "ton_mm_s", "normalized": true, "factors": {"stress": 1.0, "...": 1.0},
            "deck_labels": {"stress": "MPa", "disp": "mm"}, "note": ""},
  "counts": {"objects": {"cae_run": 20, "...": 0}, "relations": {"contact_side": 51, "...": 0}},
  "ref_relations": [{"type": "cae_run", "property": "campaign", "relation": "run_of"}, "..."],
  "objects":   [{"type": "cae_run", "key": "run/Run_…", "label": "P0002", "properties": {"campaign": "campaign", "...": 0}}],
  "relations": [{"relation": "path_between", "src": ["cae_load_path", "path/1-2"], "dst": ["cae_part", "part/1"], "properties": {}}]
}
```

- **값이 없으면 키가 없다.** 0·null·빈 글자로 채우지 않는다(리포트 결측 규약과 같다).
- 만드는 쪽이 어휘로 검증한다 — 없는 타입·속성·관계·열거값, 빠진 필수값, 가리킬 곳 없는 참조가 하나라도 있으면
  꾸러미를 쓰지 않고 실패한다(post_analyze 는 경고만 내고 계속).

## 3. 키와 참조

- 키는 **캠페인 안 상대 키**다: `campaign`, `run/<런 키>`, `part/<PID>`, `resp/<런 키>/<PID>`, `contact/<CID>`,
  `xfer/<런 키>/<CID>`, `path/<작은 PID>-<큰 PID>`, `hs/<런 키>/<PID>/<기준>/<요소 종류>/<순위>`, `finding/<순번>`.
- 받는 쪽은 적재할 때 모든 키, `object_ref` 값, 관계의 `src`/`dst` 키 앞에 `<리포트 키>/` 를 붙인다.
- `cae_campaign.report`(→ `impact_report`, 필수)와 관계 `campaign_report` 는 **만드는 쪽이 비운다** — 리포트 키를 모른다.
  받는 쪽이 채운다.
- **다대일 관계는 줄로 싣지 않는다** — 참조 속성(`cae_run.campaign`, `cae_part_response.run` 등)이 곧 그 관계다. 어느 속성이
  어느 관계인지는 머리의 `ref_relations` 에 있다(줄이 필요한 소비자는 거기서 긋는다). 줄로 싣는 것은 속성으로 정해지지 않는
  다대다 — `contact_side`(줄 `properties.role` = slave/master) · `path_between`(하중 경로의 두 끝) · `finding_about` — 뿐이다.
- 런 키(`case_key`)는 DynaForge `impact_cases.case_key` 와 같다 — 전각도 낙하는 런 폴더(`Run_…`), 없으면 방향 이름, 그것도
  없으면 `run_<순번>`(DynaForge parser 와 같은 순서), 부분충격은 위치 이름(`pos_id`), 단일 런(deep)은 `single`.
  실제 런 폴더는 `run_folder` 칸에 따로 있다.

## 4. 단위

- 수치는 **속성의 `unit` 글자 단위**다: MPa · mm · s · mJ · N · N·s · mm/s · G · deg. 글자 없는 수는 무차원.
- 덱 단위계를 알면 바꿔 싣는다(ton-mm-s 는 그대로, SI 는 Pa→MPa·m→mm·J→mJ, g-mm-ms 는 ms→s). 바꾼 배수는 `units.factors`.
- 모르면 **바꾸지 않고** `units.normalized=false`, 캠페인 `values_normalized=false` 와 `unit_note` 에 사유. 이런 캠페인은
  다른 캠페인과 수치를 견주면 안 된다. G 는 단위계를 모르면 싣지 않는다(부분충격·deep — 덱 가속도를 G 로 못 바꾼다).
- 안전율은 덱 단위끼리의 비라 단위계와 무관하다.

## 5. 어댑터별로 담기는 것

| 타입 | sphere | impact | deep |
|---|---|---|---|
| `cae_run` | 방향(롤·피치·요·분류), 충격 방향 벡터, 상태 수, S1 첫 접촉·해시 | 면·위치(x,y)·해석 품질·첫 접촉·면 자세 | 끝 시각·분석기 커밋·정상 종료 |
| `cae_part` | 전 방향 포락·안전율·판정·방향 의존도 | 포락·안전율(*MAT 항복) | 이 런 값·안전율(*MAT SIGY) |
| `cae_part_response` | σvm·σ1·σ3·εp·ε_vm·ε1·ε3·G·변위·IE/KE·시각 | σvm·σ1·σ3·εp·G·변위 | σvm·σ1·σ3·εp·ε 계열·G·변위·IE/KE |
| `cae_contact` | 덱 *CONTACT(카드 종류·양쪽 파트) | 같음 | 같음 |
| `cae_load_transfer` | 전 런(첫 맞닿음·깊이·신뢰도는 시계열 판 런만) | payload 흐름이 있는 위치 | 이 런 |
| `cae_load_path` | 파트 쌍 전 런 집계 | 같음 | 이 런 |
| `cae_hotspot` | `--hotspot-clusters` 로 분석한 캠페인만 | 없음 | 있으면 |
| `cae_finding` | 리포트 소견(파트 소견은 `finding_about`) | 리포트 소견 | 없음 |

판정(`cae_part.severity`)은 어휘 공통 규칙: 안전율 < 1 CRITICAL, < 1.5 WARNING(한계 일부 미계측이면 WARNING),
전각도 낙하만 가속도 > 200,000 G CRITICAL · > 50,000 G WARNING(그 리포트 규칙). 한계가 없으면 응력을 보지 않은 것이라
OK 가 아니라 UNKNOWN. sphere 판정은 분석기와 같은 함수(`yield_map.evaluate`)로 셈한다. 심각도 · 해석 품질 철자는
DynaForge 소견과 같은 대문자다(`cae_finding.severity` = CRITICAL · WARNING · INFO, `cae_run.solver_quality` = PASS · WARN · FAIL · UNKNOWN).

캠페인의 낙하 조건 — `impact_speed` 는 덱 `*INITIAL_VELOCITY` 의 크기(없으면 S1 초기 속도), `drop_height` 는 DropSet.json 의
값을 √(2gh) 가 그 속도와 3% 안에서 맞을 때만 싣는다(높이의 단위를 물리로 확인). 파트 재질은 덱 `*PART` → `*MAT` 에서
`material_id` · `material_type` · `material_name`(`_TITLE` 제목).

## 6. 받는 쪽(DynaForge) — 검토 답신의 의견 (정하는 것은 사용자)

- **담당** — DynaForge 가 채택 · 적재 · 질의를 맡는 것이 맞다는 의견이다(용어 · 검증기 · 표 · 화면 · MCP · 반입 자리가 거기 있다).
- **어휘 정본** — DynaForge `platform/core/ontology/dynaforge-cae.json`(그룹 파일)으로 옮기자는 의견이다. 그러면 이쪽은 그 바이트
  사본을 싣고 꾸러미의 `vocabulary.sha256` 으로 맞춰 본다(받는 쪽은 다르면 적재하지 않고 불일치를 보인다). 옮기기 전까지
  정본은 이 저장소의 `vocabulary.py` 다.
- **적재 범위** — (가) 캠페인 수준만 행으로(campaign · part · contact · load_path · finding · hotspot. 런 · 파트 응답은 이미 있는
  `impact_cases` 를 끝점으로, 하중 전달은 꾸러미 파일 + 도구) 를 권한다. (나) 전부 행, (다) 파일로만과의 비교는 답신 §4.
- **어느 범위든** 리포트를 지우거나 다시 반입하면 그 리포트 접두의 행 · 선을 함께 정리해야 한다(지금 트리거는 끝점이
  `impact_report` 인 선만 본다).
- 전각도 그룹 리포트(`report_<그룹>.json`)가 DynaForge 리포트로 따로 생기는지는 반입 쪽에서 확인할 일이다.

## 7. 실측 (2026-10-31)

| 캠페인 | 객체 | 관계 | 크기 | gzip |
|---|---|---|---|---|
| Test_Postprocess_v14 전각도 20런 | 1,014 | 114 | 0.51 MB | 61 KB |
| Test_Impact_A 부분충격 25위치 | 945 | 94 | 0.31 MB | 33 KB |
| Test_HotspotKeys_v118 deep 1런(핫스팟 58) | 176 | 93 | 0.08 MB | 12 KB |

다대일 줄을 빼기 전(초안 1)에는 v14 가 관계 2,817 · 0.90 MB(gzip 74 KB)였다. 1,000런 전각도는 객체 약 5만 · 약 25 MB
(gzip 약 3 MB)로 어림한다. 남은 다대다 줄은 접촉 · 파트 쌍 · 소견 수를 따라가서 런 수와 거의 무관하다(수백 줄).

대조: v14 파트 판정 23/23 이 리포트 분석기 소견과 같고, 런 최대 응력 22파트가 S1 게이트와 리포트 반올림 안에서 같다.
impact 는 payload 엣지 207 = 하중 전달 207, 리포트 행 625 = 응답 625, 해석 품질 25/25 일치. deep 은 σvm 23/23 이
analysis_result 의 global_max 와, G 가 최대 가속도 ÷ 9806.65 와 같다.

## 8. 알려진 빈칸

- sphere 런의 끝 시각·분석기 커밋 — report.json 에 없다(koo_sphere_report 가 싣기로 함). 런당 93 MB 원본은 다시 읽지 않는다.
- sphere 첫 맞닿음 시각 — 흐름 캐시가 9-17 빌더 수정 전 것이면 빠진다(캐시 판 4 로 올림, 2eeb7c0 — 다시 돌리면 채워진다).
- 부분충격 — 위치가 100개를 넘으면 payload 흐름이 상위 40개뿐이다(`engage_ratio` 분모는 흐름이 있는 런 수).
  충격체 접촉이 단일면(전 모델) 카드면 파트로 못 풀어 하중 경로에 충격체가 나오지 않는다(`unresolved_side` 에 남는다).
- 안전율 — 파트별 항복값이 든 실캠페인이 아직 없어 합성 시험으로만 확인했다.
