# 공통 격자 정렬 테스트 — 실측/보간 마스크 불변식과 커버리지 통계
from __future__ import annotations

from koo_federate_report.resample import align

from .helpers import make_impact_bundle, make_sphere_bundle

PARTS = {1: "PartA"}
GRID = [("C1", 0.0, 0.0), ("C2", 20.0, 0.0), ("C3", 0.0, 20.0), ("C4", 20.0, 20.0)]


def _impact(label, offset=0.0, face="F5", keys=None):
    specs = [
        (k, x + offset, y + offset, face, 100.0 + i * 10, True, "bounce")
        for i, (k, x, y) in enumerate(GRID)
        if keys is None or k in keys
    ]
    return make_impact_bundle(label, specs, PARTS)


def test_impact_identical_grid_is_identity():
    res = align([_impact("A"), _impact("B")], 0, "impact", "nearest")
    assert res.coverage["mode_effective"] == "identity"
    assert all(s.source == "exact" and s.measured for n in res.nodes for s in n.per_rev)
    assert res.coverage["per_rev"][1]["coverage_pct"] == 100.0


def test_impact_nearest_within_radius():
    """격자 간격 20 → 허용 반경 8. 3mm 이동은 최근접으로 붙되 실측이 아니다."""
    res = align([_impact("A"), _impact("B", offset=3.0)], 0, "impact", "nearest")
    assert res.coverage["mode_effective"] == "nearest"
    assert res.coverage["radius_by_face"]["F5"] == 8.0
    for node in res.nodes:
        a, b = node.per_rev
        assert a.source == "exact" and a.measured is True
        assert b.source == "nearest"
        assert b.measured is False  # 보간/대체를 실측으로 표시하지 않는다
        assert b.offset > 0
    assert res.coverage["per_rev"][1]["exact"] == 0
    assert res.coverage["per_rev"][1]["nearest"] == 4
    assert res.coverage["per_rev"][1]["measured_pct"] == 0.0
    assert res.coverage["per_rev"][1]["coverage_pct"] == 100.0


def test_impact_nearest_outside_radius_is_missing():
    res = align([_impact("A"), _impact("B", offset=9.0)], 0, "impact", "nearest")
    for node in res.nodes:
        assert node.per_rev[1].source == "missing"
        assert node.per_rev[1].trust.ok is False
    assert res.coverage["per_rev"][1]["coverage_pct"] == 0.0


def test_impact_off_mode_intersection_only():
    res = align([_impact("A"), _impact("B", offset=3.0)], 0, "impact", "off")
    assert all(n.per_rev[1].source == "missing" for n in res.nodes)
    assert res.coverage["mode_effective"] == "off"


def test_impact_partial_grid():
    res = align([_impact("A"), _impact("B", keys={"C1", "C2"})], 0, "impact", "off")
    sources = [n.per_rev[1].source for n in res.nodes]
    assert sources == ["exact", "exact", "missing", "missing"]
    assert res.coverage["per_rev"][1]["coverage_pct"] == 50.0


def test_impact_idw_falls_back_to_nearest():
    res = align([_impact("A"), _impact("B")], 0, "impact", "idw")
    assert "resample_fallback" in [w["code"] for w in res.warnings]


def test_impact_face_mismatch_warns():
    res = align([_impact("A", face="F5"), _impact("B", face="F1")], 0, "impact", "nearest")
    codes = [w["code"] for w in res.warnings]
    assert "face_incomparable" in codes
    assert res.coverage["incomparable_faces"] == ["F1"]
    # baseline 에 없는 face 의 셀은 격자에 들어오지 않는다
    assert all(n.per_rev[1].source == "missing" for n in res.nodes)


# --------------------------------------------------------------------------
# sphere
# --------------------------------------------------------------------------
ANGLES_A = [
    ("A1", 0.0, 0.0, "face", 100.0),
    ("A2", 90.0, 0.0, "face", 200.0),
    ("A3", -90.0, 0.0, "face", 150.0),
    ("A4", 0.0, 90.0, "face", 300.0),
]
ANGLES_B = [
    ("B1", 10.0, 5.0, "arbitrary", 110.0),
    ("B2", 80.0, 5.0, "arbitrary", 210.0),
    ("B3", -80.0, 5.0, "arbitrary", 160.0),
    ("B4", 5.0, 85.0, "arbitrary", 310.0),
]


def test_sphere_identical_names_is_identity():
    a = make_sphere_bundle("A", ANGLES_A, PARTS)
    b = make_sphere_bundle("B", ANGLES_A, PARTS)
    res = align([a, b], 0, "sphere", "idw")
    assert res.coverage["mode_effective"] == "identity"
    assert all(s.measured for n in res.nodes for s in n.per_rev)
    assert res.warnings == []


def test_sphere_off_mode_intersection():
    a = make_sphere_bundle("A", ANGLES_A, PARTS)
    b = make_sphere_bundle("B", ANGLES_A[:2] + ANGLES_B[2:], PARTS)
    res = align([a, b], 0, "sphere", "off")
    assert [n.key for n in res.nodes] == ["A1", "A2"]
    assert "grid_mismatch" in [w["code"] for w in res.warnings]


def test_sphere_nearest_tolerance():
    a = make_sphere_bundle("A", ANGLES_A, PARTS)
    b = make_sphere_bundle("B", ANGLES_B, PARTS)
    res = align([a, b], 0, "sphere", "nearest")
    assert res.coverage["mode_effective"] == "nearest"
    assert res.coverage["tolerance_deg"] > 0
    # 10° 이상 떨어진 격자는 허용 각도를 넘어 미매칭이거나 최근접 대체
    for node in res.nodes:
        s = node.per_rev[1]
        assert s.source in ("nearest", "missing")
        assert s.measured is False


def test_sphere_idw_marks_interpolation():
    a = make_sphere_bundle("A", ANGLES_A, PARTS)
    b = make_sphere_bundle("B", ANGLES_B, PARTS)
    res = align([a, b], 0, "sphere", "idw")
    assert res.coverage["mode_effective"] == "idw"
    assert res.coverage["n_grid"] == 4  # min(len(cells))
    assert "resample_interpolated" in [w["code"] for w in res.warnings]

    lo_a = min(g for *_, g in ANGLES_A)
    hi_a = max(g for *_, g in ANGLES_A)
    for node in res.nodes:
        for s in node.per_rev:
            assert s.source in ("exact", "idw")
            if s.source == "idw":
                assert s.measured is False
                assert s.metrics["g"] is not None
        # IDW 는 볼록결합이므로 기여 샘플의 [min, max] 를 벗어나지 않는다
        va = node.per_rev[0].metrics["g"]
        assert lo_a - 1e-9 <= va <= hi_a + 1e-9


def test_sphere_idw_keeps_nearest_behavior_and_offset():
    a = make_sphere_bundle("A", ANGLES_A, PARTS)
    b = make_sphere_bundle("B", ANGLES_B, PARTS)
    res = align([a, b], 0, "sphere", "idw")
    for node in res.nodes:
        for s in node.per_rev:
            if s.source == "idw":
                assert s.offset is not None and s.offset >= 0
                assert s.cell_key is not None  # 최근접 실측 셀 참조는 남는다
