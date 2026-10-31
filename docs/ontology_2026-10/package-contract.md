# 온톨로지 꾸러미 계약 — 초안 1 (2026-10-31)

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
  "counts": {"objects": {"cae_run": 20, "...": 0}, "relations": {"run_of": 20, "...": 0}},
  "objects":   [{"type": "cae_run", "key": "run/Run_…", "label": "P0002", "properties": {"campaign": "campaign", "...": 0}}],
  "relations": [{"relation": "run_of", "src": ["cae_run", "run/Run_…"], "dst": ["cae_campaign", "campaign"], "properties": {}}]
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
- 참조 속성과 관계를 **둘 다** 싣는다(DynaForge 자체 어휘의 `dev_revision.task` + `revision_of` 와 같은 방식).
  어느 속성이 어느 관계인지는 `vocabulary.REF_RELATIONS`.
- 런 키: 전각도 낙하·deep 은 런 폴더(`Run_…`), 부분충격은 위치 이름(`pos_id`, 예 `F5_DOE_001`). 런 폴더는 `run_folder` 칸에 따로 있다.

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

판정(`cae_part.severity`)은 어휘 공통 규칙: 안전율 < 1 critical, < 1.5 warning(한계 일부 미계측이면 warning),
전각도 낙하만 가속도 > 200,000 G critical · > 50,000 G warning(그 리포트 규칙). 한계가 없으면 응력을 보지 않은 것이라
ok 가 아니라 unknown. sphere 판정은 분석기와 같은 함수(`yield_map.evaluate`)로 셈한다.

## 6. 받는 쪽(DynaForge)에 제안하는 일

1. **어휘 채택** — `platform/core/ontology/` 에 그룹 파일로(SP 관례: 도메인 묶음은 따로 파일). 자체 정의를 런타임에
   `onto_types` 로 적재하고, 「타입은 dev_revision 하나」 고정 시험을 푼다.
2. **적재** — 리포트를 받을 때 같은 폴더의 꾸러미를 읽어: `format`·`format_version` 확인 → `vocabulary.sha256` 이 자기
   어휘와 다르면 적재하지 않고 불일치를 보인다 → 키 접두 → upsert → `report`·`campaign_report` 채움. 같은 리포트를 다시
   적재하면 그 리포트 접두의 옛 행 중 새 꾸러미에 없는 것은 삭제 표시(지우지 않는다).
3. **질의** — 하중 경로 상위(충격량·맞닿은 비율), 파트 최악 방향(`worst_*_run`), 안전율 미달·판정 목록, 방향별 응답.

## 7. 실측 (2026-10-31)

| 캠페인 | 객체 | 관계 | 크기 | gzip |
|---|---|---|---|---|
| Test_Postprocess_v14 전각도 20런 | 1,014 | 2,817 | 0.90 MB | 74 KB |
| Test_Impact_A 부분충격 25위치 | 945 | 2,204 | 0.57 MB | 41 KB |
| Test_HotspotKeys_v118 deep 1런(핫스팟 58) | 176 | 308 | 0.12 MB | 13 KB |

1,000런 전각도는 약 45 MB(gzip 약 4 MB)로 어림한다.

대조: v14 파트 판정 23/23 이 리포트 분석기 소견과 같고, 런 최대 응력 22파트가 S1 게이트와 리포트 반올림 안에서 같다.
impact 는 payload 엣지 207 = 하중 전달 207, 리포트 행 625 = 응답 625, 해석 품질 25/25 일치. deep 은 σvm 23/23 이
analysis_result 의 global_max 와, G 가 최대 가속도 ÷ 9806.65 와 같다.

## 8. 알려진 빈칸

- sphere 런의 끝 시각·분석기 커밋 — report.json 에 없다(koo_sphere_report 가 싣기로 함). 런당 93 MB 원본은 다시 읽지 않는다.
- sphere 첫 맞닿음 시각 — 흐름 캐시가 9-17 빌더 수정 전 것이면 빠진다(캐시 판 4 로 올림, 2eeb7c0 — 다시 돌리면 채워진다).
- 부분충격 — 위치가 100개를 넘으면 payload 흐름이 상위 40개뿐이다(`engage_ratio` 분모는 흐름이 있는 런 수).
  충격체 접촉이 단일면(전 모델) 카드면 파트로 못 풀어 하중 경로에 충격체가 나오지 않는다(`unresolved_side` 에 남는다).
- 안전율 — 파트별 항복값이 든 실캠페인이 아직 없어 합성 시험으로만 확인했다.
