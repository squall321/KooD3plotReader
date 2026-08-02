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
