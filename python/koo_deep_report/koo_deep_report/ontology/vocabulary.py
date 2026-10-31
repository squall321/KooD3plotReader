# DynaForge 전용 해석 결과 어휘(SP import 꼴, 그룹 cae)를 정의하는 정본 — docs 의 JSON 은 여기서 뽑는다
"""해석 결과 어휘 — 구조·충격해석 개념을 DynaForge 온톨로지 타입·관계로 묶는다.

꼴은 DynaForge 가 읽는 SP(StandardPlatform) import 꼴 그대로다
(`platform/backend/app/runner/ontology_def.py` 의 검증기가 결함 0 으로 통과해야 한다).
slug 는 영문 snake_case 에 `cae_` 접두, 이름·설명은 한국어.

**값의 단위는 속성의 `unit` 글자가 정한다.** DynaForge 는 단위를 바꾸지 않고 글자만 보여
주므로, 꾸러미를 만드는 쪽이 값을 이 글자의 단위로 맞춰 싣는다(`package.py`). 단위 글자가
없는 수는 무차원(변형률·비율·개수)이다.

양의 정의를 `help` 에 박는다 — 이름이 같아도 뜻이 다른 사례가 실제로 있었다
(절점 최대 변위 vs 평균 변위, 등가변형률 vs 유효소성변형률, 강체속도 대리 일).
"""
from __future__ import annotations

import hashlib
import json

#: 어휘 판. 타입·속성·관계가 바뀌면 올린다. 꾸러미 머리에 실린다.
VERSION = "0.1"
GROUP = "cae"

#: 속성 `unit` 글자 → 양의 종류. 꾸러미 작성기가 이것으로 환산 계수를 고른다.
UNIT_KINDS = {
    "MPa": "stress", "mm": "length", "s": "time", "mJ": "energy",
    "N": "force", "N·s": "impulse", "mm/s": "velocity",
}

#: 만드는 쪽이 채우지 않는 속성 — DynaForge 가 적재할 때 채운다(리포트 키를 모른다).
FILLED_AT_INGEST = {("cae_campaign", "report")}

#: 참조 속성이 곧 관계인 것 — DynaForge 자체 어휘(dev_revision.task + revision_of)처럼 둘 다 싣는다.
#: 꾸러미 작성기가 속성을 채우면 이 관계 줄을 함께 긋는다(손으로 두 번 쓰다 어긋나지 않게).
REF_RELATIONS = {
    ("cae_run", "campaign"): "run_of",
    ("cae_part", "campaign"): "part_in_campaign",
    ("cae_part_response", "run"): "response_in",
    ("cae_part_response", "part"): "response_of",
    ("cae_load_transfer", "run"): "transfer_in",
    ("cae_load_transfer", "contact"): "transfer_via",
    ("cae_load_transfer", "from_part"): "transfer_from",
    ("cae_load_transfer", "to_part"): "transfer_to",
    ("cae_load_path", "part_a"): "path_between",
    ("cae_load_path", "part_b"): "path_between",
    ("cae_hotspot", "response"): "hotspot_of",
}

_UNIT_NOTE = ("값은 이 어휘의 단위(MPa·mm·s·mJ·N·N·s·mm/s·G)로 싣는다. 캠페인의 `values_normalized` 가 거짓이면 "
              "덱 단위 원값이니 캠페인끼리 견주지 말 것.")


def _num(key, label, unit=None, help=None, **kw):
    p = {"key": key, "label": label, "data_type": "number"}
    if unit:
        p["unit"] = unit
    if help:
        p["help"] = help
    p.update(kw)
    return p


def _txt(key, label, help=None, long=False, **kw):
    p = {"key": key, "label": label, "data_type": "text_long" if long else "text"}
    if help:
        p["help"] = help
    p.update(kw)
    return p


def _enum(key, label, opts, help=None, **kw):
    p = {"key": key, "label": label, "data_type": "enum", "enum_options": list(opts)}
    if help:
        p["help"] = help
    p.update(kw)
    return p


def _ref(key, label, to, inv, help=None, **kw):
    p = {"key": key, "label": label, "data_type": "object_ref", "ref_type_slug": to,
         "inverse_label": inv}
    if help:
        p["help"] = help
    p.update(kw)
    return p


def _bool(key, label, help=None):
    p = {"key": key, "label": label, "data_type": "bool"}
    if help:
        p["help"] = help
    return p


def _type(slug, label, icon, desc, props):
    return {"slug": slug, "label": label, "nav_group_slug": GROUP, "icon": icon,
            "key_policy": "required", "description": desc, "properties": props}


def _rel(slug, label, inv, desc, card, src, dst):
    return {"slug": slug, "label": label, "inverse_label": inv, "description": desc,
            "cardinality": card, "transitive": False, "acyclic": False,
            "src_type_slugs": list(src), "dst_type_slugs": list(dst)}


#: 핫스팟 기준량 — unified_analyzer 의 hotspot_clusters `criterion` 값과 같다.
HOTSPOT_CRITERIA = ("von_mises", "max_principal", "min_principal", "max_shear",
                    "x_tension", "y_tension", "z_tension")

_TYPES = [
    _type("cae_campaign", "해석 캠페인", "Layers",
          "후처리 한 번이 다룬 해석 묶음 — 전각도 낙하(구면 DOE), 전위치 부분충격 DOE, 또는 런 하나(deep). "
          "리포트(`impact_report`) 하나에 캠페인 하나. 키는 적재 때 DynaForge 가 `<리포트 키>/campaign` 으로 붙인다. "
          + _UNIT_NOTE,
          [_ref("report", "리포트", "impact_report", "해석 캠페인", required=True,
                help="이 캠페인을 낸 리포트. 적재할 때 DynaForge 가 채운다 — 만드는 쪽(후처리)은 리포트 키를 모른다."),
           _enum("scenario_kind", "해석 종류", ["drop_all_angle", "impact_all_position", "single_run"],
                 required=True,
                 help="drop_all_angle = 전각도 낙하(koo_sphere_report), impact_all_position = 전위치 부분충격"
                      "(koo_impact_report), single_run = 런 하나(koo_deep_report)."),
           _txt("test_dir", "캠페인 폴더", help="후처리가 읽은 캠페인 폴더 이름(경로가 아니라 이름)."),
           _num("n_runs", "런 수"), _num("n_runs_ok", "성공 런 수"), _num("n_runs_failed", "실패 런 수"),
           _txt("doe_strategy", "실험계획", help="runner_config 의 DOE 전략 이름(예 fibonacci, face_edge_corner)."),
           _num("angular_spacing_deg", "각도 간격", "deg", help="전각도 낙하에서 이웃 낙하 방향 사이 평균 각도."),
           _num("sphere_coverage", "구면 덮임", help="낙하 방향이 구면을 덮은 비율(0–1)."),
           _enum("unit_system", "단위계", ["si", "ton_mm_s", "ton_mm_ms", "g_mm_ms", "unknown"], required=True,
                 help="덱 *MAT 밀도로 감지한 단위계(부분충격은 --units 로 줄 수도 있다). 감지 못 하면 unknown."),
           _bool("values_normalized", "단위 정규화",
                 help="참이면 모든 수치를 이 어휘의 단위로 바꿔 실었다. 거짓이면 덱 단위 원값이다(단위계를 감지 못 했을 때)."),
           _txt("unit_note", "단위 판정 단서", long=True,
                help="단위계를 못 정한 사유, 또는 정했지만 붙은 단서. 비어 있으면 깨끗이 판정했다."),
           _num("g_factor", "1 G 환산값",
                help="1 G 를 덱 가속도 단위로 나타낸 값(ton-mm-s 이면 9806.65). G 값은 이것으로 나눈 결과다."),
           _num("impactor_part_id", "충격체 파트", help="부분충격 DOE 의 충격체 PID. 낙하에는 없다."),
           _num("impact_speed", "충격 속도", "mm/s",
                help="충격 직전 속력. 낙하는 S1 /posture 의 초기 속도 크기, 부분충격은 충격체 초기 속도 크기."),
           _enum("yield_source", "항복값 출처",
                 ["dropset_part_yield", "yield_map", "cli_yield_stress", "mat_card", "none"],
                 help="안전율에 쓴 항복 한계의 출처. none 이면 안전율을 셈하지 않았다."),
           _txt("producer", "만든 도구"), _txt("producer_version", "만든 도구 판"),
           {"key": "produced_at", "label": "만든 시각", "data_type": "datetime"}]),

    _type("cae_run", "해석 런", "PlayCircle",
          "LS-DYNA 해석 한 번 — 전각도 낙하의 한 방향, 부분충격의 한 위치. 키 `<캠페인>/run/<런 폴더>`.",
          [_ref("campaign", "캠페인", "cae_campaign", "런", required=True),
           _txt("case_key", "런 키", required=True,
                help="리포트가 런을 부르는 이름 — 전각도 낙하·deep 은 런 폴더(Run_…), 부분충격은 위치 이름(pos_id). "
                     "캠페인 안에서 유일하다."),
           _txt("angle_name", "방향 이름",
                help="DOE 표의 이름(F_TOP, E_…, C_…, P0123 등). 못 맞추면 R{roll}_P{pitch}_Y{yaw}."),
           _num("roll_deg", "롤", "deg"), _num("pitch_deg", "피치", "deg"),
           _num("yaw_deg", "요", "deg",
                help="DropSet initial_conditions.orientation_euler_deg. 모델은 그대로 두고 속도 벡터를 돌려 자세를 건다."),
           _enum("angle_category", "방향 분류", ["face", "edge", "corner", "fibonacci", "unknown"],
                 help="방향 이름의 접두로만 가른 분류(F/E/C/P) — 물리적으로 판정한 면·모서리·꼭짓점이 아니다."),
           _num("impact_dir_x", "충격 방향 x"), _num("impact_dir_y", "충격 방향 y"),
           _num("impact_dir_z", "충격 방향 z",
                help="기기 좌표계에서 본 낙하 방향 단위벡터 d = Rᵀ(0,0,−1), R = Rx(roll)·Ry(pitch)·Rz(yaw) "
                     "(리포트 지도와 같은 식)."),
           _txt("run_folder", "런 폴더", help="해석 산출물 폴더 이름(Run_…). 부분충격은 case_key 가 위치 이름이라 따로 둔다."),
           _txt("impact_face", "충격 면", help="부분충격 DOE 의 면 코드(F1…F6)."),
           _num("impact_x", "충격 위치 x", "mm", help="면 좌표계의 충격 위치(step_config LocationX)."),
           _num("impact_y", "충격 위치 y", "mm"),
           _enum("solver_quality", "해석 품질", ["pass", "warn", "fail", "unknown"],
                 help="glstat 에너지 수지 게이트(총에너지 표류·hourglass·sliding) 판정. 부분충격 리포트가 낸다."),
           _num("num_states", "상태 수"), _num("end_time", "끝 시각", "s"),
           _bool("success", "해석 성공", help="분석 결과를 읽었으면 참. 거짓이면 이 런의 응답 객체가 없다."),
           _txt("analyzer_commit", "분석기 판", help="이 런을 분석한 unified_analyzer 의 커밋."),
           _num("first_contact_time", "첫 접촉 시각", "s",
                help="S1 /posture 의 first_contact_s(틈 ÷ 초기 속도). S1 이 없으면 비운다."),
           _txt("s1_sha256", "S1 파일 해시", help="같은 런 S1 경량 추출본(s1.h5)의 sha256 — s1.json 에서 온다.")]),

    _type("cae_part", "해석 파트", "Box",
          "해석 모델의 파트(PID) — 캠페인 안에서 하나. 런마다의 값은 `cae_part_response`, 여기에는 **전 런을 걸친 "
          "최악값(포락)**과 안전율·판정을 둔다. 키 `<캠페인>/part/<PID>`. " + _UNIT_NOTE,
          [_ref("campaign", "캠페인", "cae_campaign", "파트", required=True),
           _num("part_id", "파트 번호", required=True, help="LS-DYNA PID."),
           _txt("name", "파트 이름", help="덱 *PART 제목."),
           _txt("part_group", "파트 묶음", help="이름에서 `\\` 또는 `/` 앞부분. 없으면 Other."),
           _num("yield_limit", "항복 한계", "MPa", help="최소 안전율을 정한 한계(binding)."),
           _txt("yield_criterion", "항복 기준", help="그 한계가 무엇에 대한 것인가(von_mises, max_principal)."),
           _num("worst_von_mises", "최대 등가응력(전 방향)", "MPa",
                help="모든 런의 파트 최대 von Mises 응력 σvm = √(½Σ(σi−σj)² + 3Στ²) 중 최댓값. 삭제된 요소는 뺀 "
                     "리포트 정본 값."),
           _ref("worst_von_mises_run", "최대 등가응력 런", "cae_run", "등가응력 최악 파트"),
           _num("worst_max_principal", "최대 주응력(전 방향)", "MPa", help="σ1 의 전 런 최댓값 — 인장 파괴 판단."),
           _num("worst_min_principal", "최소 주응력(전 방향)", "MPa", help="σ3 의 전 런 최솟값(가장 큰 압축)."),
           _num("worst_plastic_strain", "최대 유효소성변형률(전 방향)", help="εp 의 전 런 최댓값. 탄성분을 뺀 영구변형."),
           _num("worst_g", "최대 가속도(전 방향)", "G", help="파트 평균 가속도 크기의 최대를 1 G 로 나눈 값의 전 런 최댓값."),
           _ref("worst_g_run", "최대 가속도 런", "cae_run", "가속도 최악 파트"),
           _num("min_safety_factor", "최소 안전율",
                help="min(항복 한계 ÷ 최대 응력) — 한계 기준별로 맞는 응력을 쓴다. 한계가 없으면 비운다."),
           _bool("safety_factor_complete", "안전율 완전",
                 help="거짓이면 한계 일부의 응력을 재지 못해 안전율이 실제보다 클 수 있다(리포트는 이때 critical 로 "
                      "단정하지 않는다)."),
           _enum("severity", "판정", ["ok", "warning", "critical", "unknown"],
                 help="어휘 공통: 안전율 < 1 critical, < 1.5 warning(불완전하면 warning). 전각도 낙하만 가속도 "
                      "> 200,000 G critical, > 50,000 G warning 을 더한다(그 리포트의 규칙 — 부분충격 리포트는 "
                      "가속도 절대 기준을 두지 않는다). 응력 한계가 없고 가속도도 안 걸리면 unknown."),
           _num("von_mises_cov", "방향 의존도",
                help="런별 최대 등가응력의 변동계수(표준편차 ÷ 평균, 모집단). 0.5 이상이면 방향에 강하게 의존."),
           _num("n_runs_measured", "잰 런 수", help="이 파트의 등가응력이 있는 런 수(포락·변동계수의 분모).")]),

    _type("cae_part_response", "파트 응답", "Activity",
          "한 런에서 한 파트가 보인 최대 응답. 시계열은 담지 않는다(리포트·S1 에 있다). "
          "키 `<캠페인>/resp/<런 키>/<PID>`. " + _UNIT_NOTE,
          [_ref("run", "런", "cae_run", "파트 응답", required=True),
           _ref("part", "파트", "cae_part", "런별 응답", required=True),
           _num("peak_von_mises", "최대 등가응력", "MPa", help="von Mises 등가응력 σvm 의 시간·요소 최대(삭제 요소 제외)."),
           _num("peak_von_mises_time", "최대 등가응력 시각", "s"),
           _num("peak_max_principal", "최대 주응력", "MPa", help="최대 주응력 σ1(인장)의 최대."),
           _num("peak_max_principal_time", "최대 주응력 시각", "s"),
           _num("min_principal", "최소 주응력", "MPa", help="최소 주응력 σ3(압축)의 최소."),
           _num("peak_plastic_strain", "최대 유효소성변형률", help="유효소성변형률 εp 의 최대. 덱이 소성을 내지 않으면 없다."),
           _num("peak_vm_strain", "최대 등가변형률", help="von Mises 등가변형률 — 탄성분 포함. εp 와 다른 양이다."),
           _num("peak_max_principal_strain", "최대 주변형률"), _num("min_principal_strain", "최소 주변형률"),
           _num("peak_g", "최대 가속도", "G", help="파트 평균 가속도 크기의 최대 ÷ 1 G."),
           _num("peak_g_time", "최대 가속도 시각", "s"),
           _num("peak_displacement", "최대 변위", "mm", help="파트 안 절점 변위 크기의 최대(평균 변위가 아니다)."),
           _num("peak_internal_energy", "최대 내부에너지", "mJ", help="matsum 파트 내부(변형)에너지의 최대."),
           _num("peak_internal_energy_time", "최대 내부에너지 시각", "s"),
           _num("peak_kinetic_energy", "최대 운동에너지", "mJ"),
           _num("peak_kinetic_energy_time", "최대 운동에너지 시각", "s"),
           _num("final_internal_energy", "끝 내부에너지", "mJ", help="해석 끝 시각의 내부에너지 — 남은 변형에너지."),
           _num("final_kinetic_energy", "끝 운동에너지", "mJ"),
           _num("safety_factor", "안전율(이 런)", help="항복 한계 ÷ 이 런의 최대 응력(기준별, 작은 쪽).")]),

    _type("cae_contact", "접촉 정의", "Link2",
          "덱의 `*CONTACT` 카드 하나(rcforc 인터페이스) — 어느 파트와 어느 파트가 닿을 수 있게 정의했나. "
          "키 `<캠페인>/contact/<CID>`.",
          [_ref("campaign", "캠페인", "cae_campaign", "접촉 정의", required=True),
           _num("contact_id", "접촉 번호", required=True, help="rcforc 인터페이스 번호(_ID 카드면 CID)."),
           _txt("name", "접촉 이름"),
           _txt("contact_card", "접촉 카드",
                help="키워드 이름(예 *CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_ID, *CONTACT_TIED_…). 묶임(TIED)과 "
                     "맞닿음을 가른다."),
           _num("resolution_confidence", "파트 매핑 신뢰도",
                help="양쪽을 파트로 푼 신뢰도(1.0 = PID 직독, 세그먼트 집합은 다수결 비율, 0 = 못 풂).")]),

    _type("cae_load_transfer", "하중 전달", "ArrowRightLeft",
          "한 런에서 접촉 인터페이스 하나를 건너간 힘·충격량·일 — 파트 사이 에너지 흐름 네트워크의 엣지. 방향은 충격이 "
          "퍼진 순서(먼저 닿은 쪽 → 나중 쪽). 키 `<캠페인>/xfer/<런 키>/<CID>`. " + _UNIT_NOTE,
          [_ref("run", "런", "cae_run", "하중 전달", required=True),
           _ref("contact", "접촉", "cae_contact", "런별 하중 전달"),
           _ref("from_part", "보내는 파트", "cae_part", "내보낸 하중 전달"),
           _ref("to_part", "받는 파트", "cae_part", "받은 하중 전달"),
           _num("peak_force", "최대 접촉력", "N", help="rcforc 접촉력 크기의 최대."),
           _num("total_impulse", "충격량", "N·s", help="∫|F|dt — 접촉으로 건너간 운동량의 크기."),
           _num("total_work", "전달 일", "mJ",
                help="∫F·(v_보내는−v_받는)dt — 두 파트의 **평균 강체속도 차**로 셈한 대리값(접촉면 국부 미끄럼 일이 "
                     "아니다). 양 끝이 실제 파트일 때만."),
           _num("first_engage_time", "첫 맞닿음 시각", "s", help="접촉력이 최대의 1% 를 처음 넘은 시각."),
           _num("propagation_depth", "전파 깊이", help="첫 충격 파트에서 받는 파트까지 접촉을 몇 번 건넜나(BFS)."),
           _num("confidence", "파트 매핑 신뢰도"),
           _txt("unresolved_side", "파트로 못 푼 쪽",
                help="한쪽이 파트가 아니면(집합·전 모델·이름 없는 인터페이스) 그 그래프 노드 이름. 그쪽 파트 참조는 비운다.")]),

    _type("cae_load_path", "하중 경로", "Route",
          "두 파트 사이 하중 전달을 **모든 런에 걸쳐** 모은 것 — 어느 방향에서 이 경로로 힘이 얼마나 자주·크게 "
          "건너갔나. 파트 쌍은 순서 없음(작은 PID 가 a). 키 `<캠페인>/path/<PID a>-<PID b>`. " + _UNIT_NOTE,
          [_ref("campaign", "캠페인", "cae_campaign", "하중 경로", required=True),
           _ref("part_a", "파트 a", "cae_part", "하중 경로", required=True),
           _ref("part_b", "파트 b", "cae_part", "하중 경로", required=True),
           _num("n_runs_engaged", "맞닿은 런 수"),
           _num("engage_ratio", "맞닿은 비율", help="맞닿은 런 수 ÷ 에너지 흐름을 잰 런 수."),
           _num("n_runs_a_to_b", "a→b 런 수"), _num("n_runs_b_to_a", "b→a 런 수"),
           _num("impulse_max", "최대 충격량", "N·s"),
           _ref("impulse_max_run", "최대 충격량 런", "cae_run", "충격량 최대 경로"),
           _num("impulse_median", "충격량 중앙값", "N·s", help="맞닿은 런들의 중앙값."),
           _num("impulse_p90", "충격량 90%", "N·s", help="맞닿은 런들의 90 백분위(선형 보간)."),
           _num("peak_force_max", "최대 접촉력", "N"),
           _num("work_max", "최대 전달 일", "mJ")]),

    _type("cae_hotspot", "응력 집중 군집", "Flame",
          "한 런·한 파트에서 기준량 상위 요소가 모인 덩어리(핫스팟). "
          "키 `<캠페인>/hs/<런 키>/<PID>/<기준>/<요소 종류>/<순위>`. "
          + _UNIT_NOTE,
          [_ref("response", "파트 응답", "cae_part_response", "응력 집중 군집", required=True),
           _enum("criterion", "기준량", HOTSPOT_CRITERIA),
           _enum("element_type", "요소 종류", ["solid", "thick_shell", "shell"]),
           _num("rank", "순위"), _num("element_count", "요소 수"),
           _num("center_x", "중심 x", "mm"), _num("center_y", "중심 y", "mm"),
           _num("center_z", "중심 z", "mm", help="초기 형상(d3plot 좌표) 기준."),
           _num("radius_enclosing", "감싸는 반경", "mm"),
           _num("stress_mean", "평균 응력", "MPa"), _num("stress_max", "최대 응력", "MPa"),
           _num("peak_element_id", "최대 요소 번호"), _num("peak_time", "최대 시각", "s")]),

    _type("cae_finding", "판정 소견", "AlertTriangle",
          "후처리가 낸 판정 문장(항복 초과, 과대 가속도, 단위 불일치 등). 키 `<캠페인>/finding/<순번>`.",
          [_ref("campaign", "캠페인", "cae_campaign", "판정 소견", required=True),
           _enum("severity", "심각도", ["critical", "warning", "info"], required=True),
           _txt("title", "제목", required=True),
           _txt("detail", "내용", long=True),
           _txt("recommendation", "권고", long=True)]),
]

_RELATIONS = [
    _rel("run_of", "캠페인", "런", "런이 어느 캠페인에 드나.", "many_to_one", ["cae_run"], ["cae_campaign"]),
    _rel("part_in_campaign", "캠페인", "파트", "파트가 어느 캠페인 모델의 것인가.", "many_to_one",
         ["cae_part"], ["cae_campaign"]),
    _rel("campaign_report", "리포트", "해석 캠페인",
         "캠페인을 낸 리포트(1급 표 — 선의 한쪽 끝이 바깥이다). 적재 때 DynaForge 가 긋는다.", "one_to_one",
         ["cae_campaign"], ["impact_report"]),
    _rel("response_in", "런", "파트 응답", "응답이 어느 런의 것인가.", "many_to_one",
         ["cae_part_response"], ["cae_run"]),
    _rel("response_of", "파트", "런별 응답", "응답이 어느 파트의 것인가.", "many_to_one",
         ["cae_part_response"], ["cae_part"]),
    _rel("contact_side", "맞닿는 파트", "접촉 정의",
         "접촉 정의의 한쪽 면이 어느 파트인가. 줄의 properties.role 이 slave/master.", "many_to_many",
         ["cae_contact"], ["cae_part"]),
    _rel("transfer_in", "런", "하중 전달", "하중 전달이 어느 런의 것인가.", "many_to_one",
         ["cae_load_transfer"], ["cae_run"]),
    _rel("transfer_via", "접촉", "하중 전달", "어느 접촉 정의를 건넜나.", "many_to_one",
         ["cae_load_transfer"], ["cae_contact"]),
    _rel("transfer_from", "보내는 파트", "내보낸 하중", "충격이 먼저 닿은 쪽.", "many_to_one",
         ["cae_load_transfer"], ["cae_part"]),
    _rel("transfer_to", "받는 파트", "받은 하중", "충격이 나중에 닿은 쪽.", "many_to_one",
         ["cae_load_transfer"], ["cae_part"]),
    _rel("path_between", "파트", "하중 경로", "하중 경로의 두 끝(줄 둘).", "many_to_many",
         ["cae_load_path"], ["cae_part"]),
    _rel("hotspot_of", "파트 응답", "응력 집중 군집", "군집이 어느 런·파트의 응답에서 나왔나.", "many_to_one",
         ["cae_hotspot"], ["cae_part_response"]),
    _rel("finding_about", "대상 파트", "판정 소견", "소견이 가리키는 파트(없을 수 있다).", "many_to_many",
         ["cae_finding"], ["cae_part"]),
]

VOCABULARY = {
    "_note": (f"DynaForge 해석 결과 어휘 초안 v{VERSION} (KooD3plotReader 작성) — SP import 꼴. 전각도 낙하·전위치 부분충격·"
              "단일 런 후처리 결과를 온톨로지 인스턴스로 싣기 위한 타입·관계. 용어는 구조·충격해석 개념을 DynaForge 전용 "
              "slug(cae_ 접두)로 묶었다. 정본 위치·채택은 DynaForge 결정. 이 파일은 "
              "python/koo_deep_report/koo_deep_report/ontology/vocabulary.py 에서 뽑는다."),
    "groups": [{"slug": GROUP, "label": "해석 결과", "sort_order": 20}],
    "types": _TYPES,
    "relation_types": _RELATIONS,
}


def dumps() -> str:
    """어휘 JSON 문자열 — docs 에 두는 파일과 바이트까지 같다."""
    return json.dumps(VOCABULARY, ensure_ascii=False, indent=2) + "\n"


def sha256() -> str:
    """꾸러미 머리에 싣는 어휘 지문. 받는 쪽이 자기 사본과 같은 어휘인지 본다."""
    return hashlib.sha256(dumps().encode("utf-8")).hexdigest()


def types_by_slug() -> dict[str, dict]:
    return {t["slug"]: t for t in _TYPES}


def relations_by_slug() -> dict[str, dict]:
    return {r["slug"]: r for r in _RELATIONS}
