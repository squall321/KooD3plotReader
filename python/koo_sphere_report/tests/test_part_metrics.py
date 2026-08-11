# sphere 파트 지표 회귀 — 주응력/에너지가 '미계측' 을 0 으로 위장하지 않는지
"""파트별 σ1 · IE/KE 의 정직성 규칙.

실측 배경: sphere 의 파트 지표는 오래도록 peak_stress(von Mises)/strain/g/disp
4종뿐이었다. σ1 은 unified_analyzer 가 von Mises 와 항상 함께 CSV 로 내지만
로더가 그 파일을 열지 않았고, IE/KE 는 binout matsum 에 있는데 흐름 탭
전용으로만 갇혀 있었다.

여기서 못박는 규칙은 하나다 — **없는 값은 None 이지 0 이 아니다.**
σ1 이 없다고 von Mises 로 대체하거나 0 으로 채우면 화면에서 구분이 불가능해진다.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from koo_sphere_report.models import (  # noqa: E402
    PartEnergy, PartInfo, PartResult, TimeSeriesData,
)


def _ts(vals, times=None):
    ts = TimeSeriesData()
    ts.times = times or [i * 1e-4 for i in range(len(vals))]
    ts.max_values = list(vals)
    return ts


def _part():
    return PartResult(part=PartInfo(part_id=1, part_name="A\\B", group="A"))


def test_principal_absent_is_none_not_zero():
    """σ1 CSV 가 없으면 None — 0.0 이면 '주응력 0' 으로 오독된다."""
    pr = _part()
    pr.stress = _ts([10.0, 500.0, 20.0])
    assert pr.peak_stress == 500.0
    assert pr.peak_principal is None, "미계측 σ1 이 숫자로 나왔다"


def test_principal_is_independent_of_von_mises():
    """σ1 은 von Mises 와 다른 물리량 — 값이 서로 대체되면 안 된다.

    이축인장 상태에서는 σ1 > von Mises 도 정상이므로, σ1 을 von Mises 로
    clamp 하는 로직이 들어가면 이 테스트가 깨진다.
    """
    pr = _part()
    pr.stress = _ts([0.0, 100.0])
    pr.principal = _ts([0.0, 108.0])       # 실측에서 실제로 관측된 비율(1.08)
    assert pr.peak_stress == 100.0
    assert pr.peak_principal == 108.0


def test_energy_absent_is_none():
    """matsum 이 없으면 energy 자체가 None (0 으로 채우지 않는다)."""
    pr = _part()
    assert pr.energy is None


def test_energy_fields_default_none():
    """PartEnergy 필드 기본값도 0 이 아니라 None 이어야 한다."""
    e = PartEnergy()
    for f in ("peak_ie", "peak_ie_time", "peak_ke", "peak_ke_time",
              "final_ie", "final_ke"):
        assert getattr(e, f) is None, f"{f} 기본값이 None 이 아니다"


def test_true_peak_survives_downsampling():
    """TimeSeriesData 는 다운샘플 후에도 참피크를 유지한다 (기존 계약)."""
    ts = _ts([1.0, 999.0, 2.0])
    ts.true_peak = 999.0
    ts.max_values = [1.0, 2.0]             # 피크가 솎인 상황을 모사
    assert ts.peak == 999.0


# --------------------------------------------------------------------------
# 파트쌍 접촉력 프로파일 (Contact Profile 탭 데이터)
# --------------------------------------------------------------------------
from koo_sphere_report.report.html_report import (  # noqa: E402
    _contact_profile, _flow_detail_folders, _FLOW_DETAIL_LIMIT,
)


def _flow(edges):
    return {"nodes": [{"node_id": "1", "times": [0.0, 1.0],
                       "kinetic_ts": [1.0, 0.0], "internal_ts": [0.0, 1.0]}],
            "edges": edges}


def _edge(src, dst, cid, pf, ti=1.0, tw=2.0, name=""):
    return {"src": src, "dst": dst, "contact_id": cid, "name": name,
            "peak_force": pf, "total_impulse": ti, "total_work": tw}


def test_contact_profile_missing_angle_is_none_not_zero():
    """어떤 각도에 그 접촉이 없으면 None — 0 이면 '힘 0' 으로 오독된다."""
    results = [{"folder": "A"}, {"folder": "B"}, {"folder": "C"}]
    flows = {
        "A": _flow([_edge("1", "2", 10, 100.0)]),
        "C": _flow([_edge("1", "2", 10, 300.0)]),   # B 에는 접촉 없음
    }
    cp = _contact_profile(flows, results)
    assert len(cp["pairs"]) == 1
    assert cp["pf"][0] == [100.0, None, 300.0]


def test_contact_profile_marks_unresolved_pairs():
    """파트로 분해 안 된 접촉은 resolved=False — 파트쌍인 척하지 않는다."""
    results = [{"folder": "A"}]
    flows = {"A": _flow([
        _edge("1", "2", 10, 100.0),
        _edge("23", "iface:172", 172, 900.0),
    ])}
    cp = _contact_profile(flows, results)
    by = {p["key"]: p for p in cp["pairs"]}
    assert by["1>2"]["resolved"] is True
    assert by["23>iface:172"]["resolved"] is False
    # 정렬: 해결된 쌍이 먼저 (힘이 더 작아도)
    assert cp["pairs"][0]["key"] == "1>2"


def test_contact_profile_empty_when_no_flows():
    assert _contact_profile({}, [{"folder": "A"}])["pairs"] == []
    assert _contact_profile({"A": _flow([])}, [])["pairs"] == []


def test_flow_detail_tier_keeps_worst_and_reports_truncation():
    """각도가 많으면 시계열은 상위만 담되 **무엇이 빠졌는지 알린다**."""
    n = _FLOW_DETAIL_LIMIT + 10
    flows = {f"R{i:03d}": _flow([_edge("1", "2", 10, float(i))]) for i in range(n)}
    keep, note = _flow_detail_folders(flows)
    assert len(keep) == _FLOW_DETAIL_LIMIT
    assert f"R{n-1:03d}" in keep, "접촉력 최대 각도가 빠졌다"
    assert f"R000" not in keep
    assert note and str(n) in note, "절삭 사실이 사용자에게 안 알려진다"


def test_flow_detail_no_truncation_when_small():
    flows = {f"R{i}": _flow([_edge("1", "2", 10, 1.0)]) for i in range(3)}
    keep, note = _flow_detail_folders(flows)
    assert len(keep) == 3 and note == ""


def test_from_json_reads_part_name_key(tmp_path):
    """--from-json 재생성에서 파트명이 소실되면 안 된다.

    json_report 는 "part_name" 으로 쓰는데 from_json 이 "name" 만 읽어
    전 파트가 "Part <id>" 로 뭉개졌다(실측 확인).
    """
    import json
    from koo_sphere_report.from_json import load_report_from_json

    doc = {
        "project_name": "P", "doe_strategy": "fibonacci",
        "simulation_params": {}, "findings": [],
        "parts": {"1": {"part_name": "Front\\Metal", "group": "Front"},
                  "2": {"name": "Legacy\\Old"}},          # 구 샘플 호환
        "results_summary": [],
    }
    p = tmp_path / "r.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    rep = load_report_from_json(str(p))
    assert rep.part_info[1].part_name == "Front\\Metal"
    assert rep.part_info[1].group == "Front"
    assert rep.part_info[2].part_name == "Legacy\\Old"


# --------------------------------------------------------------------------
# 단위계 자동검출 — 조용히 1000배 틀리던 것
# --------------------------------------------------------------------------
from koo_sphere_report.loader import _deck_density, _apply_unit_system  # noqa: E402
from koo_sphere_report.models import MotionData  # noqa: E402


def _deck(tmp_path, densities):
    d = tmp_path / "t"; (d / "output").mkdir(parents=True)
    lines = []
    for i, ro in enumerate(densities, 1):
        lines += [f"*MAT_ELASTIC_TITLE", f"Elastic{i}",
                  f"{i:10d}{ro:>10} 1.660e+05 3.300e-01"]
    (d / "m.k").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return d / "output"


def test_deck_density_read_from_mat_cards(tmp_path):
    """밀도는 덱의 *MAT 에서 읽는다 (runner_config 값은 템플릿이라 못 믿는다)."""
    out = _deck(tmp_path, ["2.330e-09", "2.800e-09", "7.850e-09"])
    assert _deck_density(out) == pytest.approx(2.8e-09)


def test_deck_density_missing_returns_none(tmp_path):
    """덱이 없으면 None — 예외를 올리지 않는다."""
    out = tmp_path / "empty" / "output"; out.mkdir(parents=True)
    assert _deck_density(out) is None


def test_unit_detection_keeps_default_when_deck_missing(tmp_path):
    """판정 불가면 기본값 유지 — 틀린 단위로 자신 있게 환산하지 않는다."""
    before_id, before_gf = MotionData.UNIT_SYSTEM, MotionData.G_FACTOR
    try:
        out = tmp_path / "e" / "output"; out.mkdir(parents=True)
        _apply_unit_system(object(), out)
        assert MotionData.UNIT_SYSTEM == before_id
        assert MotionData.G_FACTOR == before_gf
    finally:
        MotionData.set_unit_system(before_id, before_gf)


def test_ton_mm_s_deck_is_not_flipped_to_si(tmp_path):
    """ton-mm-s 덱(ρ~1e-9)을 SI 로 뒤집으면 peak-G 가 1000배 커진다.

    실측 회귀: runner_config 의 density=7850(SI 풍) 으로 판정하면 실제로
    그렇게 뒤집혔다. 판정 근거를 덱으로 바꾼 이유다.
    """
    before_id, before_gf = MotionData.UNIT_SYSTEM, MotionData.G_FACTOR
    try:
        out = _deck(tmp_path, ["2.330e-09"])
        _apply_unit_system(object(), out)
        assert MotionData.UNIT_SYSTEM == "ton-mm-s"
        assert MotionData.G_FACTOR == pytest.approx(9806.65)
    finally:
        MotionData.set_unit_system(before_id, before_gf)


def test_sigma3_uses_minimum_not_peak():
    """σ3 는 압축측 — max 가 아니라 **최소값**이 최악이다."""
    pr = _part()
    ts = _ts([0.0, -100.0, -500.0, -50.0])
    ts.min_values = [0.0, -100.0, -500.0, -50.0]
    pr.principal_min = ts
    assert pr.min_principal == -500.0


def test_sigma3_absent_is_none():
    """σ3 CSV 가 없으면 None — σ1 이나 von Mises 로 대체하지 않는다."""
    pr = _part()
    pr.stress = _ts([10.0, 500.0])
    pr.principal = _ts([0.0, 300.0])
    assert pr.min_principal is None


def test_principal_strain_absent_is_none():
    """변형률 텐서가 없는 덱에서는 ε1/ε3 가 None — 유효소성변형률로 대체 금지."""
    pr = _part()
    pr.strain = _ts([0.0, 0.004])          # eff_plastic 은 있다
    assert pr.peak_principal_strain is None
    assert pr.min_principal_strain is None


def test_principal_strain_min_uses_minimum():
    """ε3 도 압축측 — 최소값이 최악이다."""
    pr = _part()
    ts = _ts([0.0, -1e-4, -5e-4])
    ts.min_values = [0.0, -1e-4, -5e-4]
    pr.principal_strain_min = ts
    pr.principal_strain = _ts([0.0, 3e-4])
    assert pr.min_principal_strain == -5e-4
    assert pr.peak_principal_strain == 3e-4


def test_vm_strain_is_separate_from_eff_plastic():
    """ε_vm 과 유효소성변형률은 다른 양 — 서로 대체하면 안 된다.

    ε_vm 은 탄성분을 포함한 등가 변형률이라 실측에서 eff_plastic 보다 크다
    (Test_006 STRFLG=1: PID21 ε_vm 0.0324 vs eff_pl 0.0138).
    """
    pr = _part()
    pr.strain = _ts([0.0, 0.0138])       # eff_plastic
    pr.vm_strain = _ts([0.0, 0.0324])    # von Mises 등가
    assert pr.peak_strain == 0.0138
    assert pr.peak_vm_strain == 0.0324


def test_vm_strain_absent_is_none():
    pr = _part()
    pr.strain = _ts([0.0, 0.01])
    assert pr.peak_vm_strain is None


# --------------------------------------------------------------------------
# 지도/히트맵 물리량 — 압축 계열은 크기로 정렬해야 색이 안 뒤집힌다
# --------------------------------------------------------------------------
def test_view_quantities_present_in_js():
    """σ1/σ3/ε1/ε3/ε_vm 이 지도·히트맵 선택지에 있어야 한다."""
    from koo_sphere_report.report.html_report import _JS
    for q in ("peak_principal_stress", "min_principal_stress",
              "peak_vm_strain", "peak_principal_strain", "min_principal_strain"):
        assert q in _JS, f"{q} 가 뷰 선택지에 없다"


def test_compression_quantities_use_magnitude():
    """σ3/ε3 는 음수라 그대로 색 스케일에 넣으면 뒤집힌다 — 절대값 처리 확인."""
    from koo_sphere_report.report.html_report import _JS
    assert "_MAG_QTYS" in _JS
    assert "min_principal_stress: 1" in _JS and "min_principal_strain: 1" in _JS


def test_mollweide_fallback_has_center_coords():
    """폴백 크기에도 cx/cy/rx/ry 가 있어야 한다 — 없으면 SVG 좌표가 NaN 이 된다."""
    from koo_sphere_report.report.html_report import _JS
    i = _JS.index("function getMollweideSize()")
    body = _JS[i:i + 1200]
    fb = body[body.index("clientWidth < 100"):]
    for k in ("cx:", "cy:", "rx:", "ry:"):
        assert k in fb[:400], f"폴백에 {k} 없음"


# --------------------------------------------------------------------------
# Tolerance DOE 탭 — 26방향 × 공차 산포
# --------------------------------------------------------------------------
def test_tolerance_doe_parses_direction_naming():
    """{방향}_{설명}_DOE{n}[_NOM] 규칙을 파싱하는 코드가 실려 있어야 한다."""
    from koo_sphere_report.report.html_report import _JS
    assert "function tolParse" in _JS
    assert "renderToleranceDoe" in _JS
    # 방향 접두 정규식과 _NOM 판정
    assert "([FEC]" in _JS and "_NOM$" in _JS


def test_tolerance_doe_sensitivity_needs_nominal():
    """정각도가 없으면 민감도는 None — 0 으로 채우면 '공차에 둔감' 으로 오독된다."""
    from koo_sphere_report.report.html_report import _JS
    i = _JS.index("e.sens =")
    seg = _JS[i:i + 200]
    assert "e.nominal" in seg and "null" in seg


def test_tolerance_doe_hides_when_naming_mismatch():
    """규칙에 안 맞는 데이터셋이면 안내문만 — 에러가 아니라 누락이다."""
    from koo_sphere_report.report.html_report import _JS
    assert "공차 DOE 로 해석할 수 없습니다" in _JS
