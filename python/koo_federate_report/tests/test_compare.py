# 비교 엔진 손계산 검증 — 3리비전 × 4셀의 delta/winner/trend/spread 전 수치
"""픽스처 (metric='g')

  cell   R1(base)  R2    R3     trust(R2)   behavior R1/R2/R3
  C1       100     110   120       ok       bounce / bounce / rebound
  C2       200     180   160       ok       bounce / bounce / bounce
  C3        50      90    40       ok       rebound/ rebound/ rebound
  C4        10      20    30      FAIL      no-contact / bounce / bounce

손계산
  C1: Δ=[0,10,20] Δ%=[0,10,20] winner=2 slope=10 trend=0.1
      spread range=20 mean=110 pstdev=sqrt(200/3)
  C2: Δ=[0,-20,-40] Δ%=[0,-10,-20] winner=0 slope=-20 trend=-0.1
  C3: Δ=[0,40,-10] Δ%=[0,80,-20] winner=1 slope=-5 trend=-0.1
  C4: trust_gate → 전부 None (미판정)
"""
from __future__ import annotations

import math

import pytest

from koo_federate_report import compare as compare_mod
from koo_federate_report.compare import CompareError, build_comparison
from koo_federate_report.config import Options
from koo_federate_report.matching import build_matching
from koo_federate_report.resample import align

from .helpers import make_impact_bundle

PARTS = {1: "PartA", 2: "PartB"}
COORDS = {"C1": (0.0, 0.0), "C2": (20.0, 0.0), "C3": (0.0, 20.0), "C4": (20.0, 20.0)}

G = {
    "R1": {"C1": 100.0, "C2": 200.0, "C3": 50.0, "C4": 10.0},
    "R2": {"C1": 110.0, "C2": 180.0, "C3": 90.0, "C4": 20.0},
    "R3": {"C1": 120.0, "C2": 160.0, "C3": 40.0, "C4": 30.0},
}
TRUST = {"R1": {}, "R2": {"C4": False}, "R3": {}}
BEHAVIOR = {
    "R1": {"C1": "bounce", "C2": "bounce", "C3": "rebound", "C4": "no-contact"},
    "R2": {"C1": "bounce", "C2": "bounce", "C3": "rebound", "C4": "bounce"},
    "R3": {"C1": "rebound", "C2": "bounce", "C3": "rebound", "C4": "bounce"},
}
PART_A = {
    "R1": {"C1": 90.0, "C2": 180.0, "C3": 45.0, "C4": 9.0},
    "R2": {"C1": 99.0, "C2": 162.0, "C3": 81.0, "C4": 18.0},
    "R3": {"C1": 108.0, "C2": 144.0, "C3": 36.0, "C4": 27.0},
}
PART_B = {
    "R1": {"C1": 45.0, "C2": 90.0, "C3": 22.5, "C4": 4.5},
    "R2": {"C1": 49.5, "C2": 81.0, "C3": 40.5, "C4": 9.0},
    "R3": {"C1": 54.0, "C2": 200.0, "C3": 18.0, "C4": 13.5},
}
FINDINGS = {
    "R1": [{"severity": "CRITICAL", "title": "F-old"}, {"severity": "WARNING", "title": "F-keep"}],
    "R2": [{"severity": "WARNING", "title": "F-keep"}, {"severity": "INFO", "title": "F-new"}],
    "R3": [{"severity": "WARNING", "title": "F-keep"}],
}


def _bundle(label, unit_labels=None):
    specs = [
        (key, COORDS[key][0], COORDS[key][1], "F5", G[label][key],
         TRUST[label].get(key, True), BEHAVIOR[label][key])
        for key in ("C1", "C2", "C3", "C4")
    ]
    part_values = {}
    for key in COORDS:
        part_values[(key, "PartA")] = {"g": PART_A[label][key], "s": None, "e": None, "d": None}
        part_values[(key, "PartB")] = {"g": PART_B[label][key], "s": None, "e": None, "d": None}
    return make_impact_bundle(
        label, specs, PARTS, part_values=part_values,
        unit_labels=unit_labels, findings=FINDINGS[label],
        kpi={"diss_pct": {"R1": 40.0, "R2": 45.0, "R3": 30.0}[label]},
    )


def _run(options=None, metric="g", labels=("R1", "R2", "R3"), unit_labels=None):
    options = options or Options()
    bundles = [_bundle(lb, unit_labels=(unit_labels or {}).get(lb)) for lb in labels]
    match = build_matching(bundles, {}, options)
    aligned = align(bundles, 0, "impact", options.resample)
    return build_comparison(bundles, 0, "impact", match, aligned, options, metric=metric)


@pytest.fixture(scope="module")
def cmp_default():
    return _run()


def _cell(cmp_dict, key):
    return next(c for c in cmp_dict["cells"] if c["key"] == key)


# --------------------------------------------------------------------------
# 격자 / 계약
# --------------------------------------------------------------------------
def test_identity_grid(cmp_default):
    assert cmp_default["coverage"]["mode_effective"] == "identity"
    assert cmp_default["coverage"]["n_grid"] == 4
    for row in cmp_default["coverage"]["per_rev"]:
        assert row["exact"] == 4 and row["missing"] == 0
        assert row["measured_pct"] == 100.0


def test_contract_keys(cmp_default):
    expected = {
        "kind", "baseline_idx", "schema_version", "metric", "unit_labels", "revisions",
        "cells", "parts", "part_matrix", "behavior_transitions", "findings_diff",
        "kpi", "coverage", "unmatched", "warnings", "provenance",
    }
    assert expected <= set(cmp_default)
    c = _cell(cmp_default, "C1")
    assert {"key", "label", "x", "y", "category", "per_rev", "delta", "delta_pct",
            "winner", "trend", "spread", "gated"} <= set(c)


# --------------------------------------------------------------------------
# 셀 손계산
# --------------------------------------------------------------------------
def test_cell_values_and_trust(cmp_default):
    c1 = _cell(cmp_default, "C1")
    assert [p["value"] for p in c1["per_rev"]] == [100.0, 110.0, 120.0]
    assert [p["trust"]["ok"] for p in c1["per_rev"]] == [True, True, True]
    c4 = _cell(cmp_default, "C4")
    assert [p["trust"]["ok"] for p in c4["per_rev"]] == [True, False, True]


def test_c1_hand_numbers(cmp_default):
    c = _cell(cmp_default, "C1")
    assert c["gated"] is False
    assert c["delta"] == [0.0, 10.0, 20.0]
    assert c["delta_pct"] == pytest.approx([0.0, 10.0, 20.0])
    assert c["winner"] == 2
    assert c["trend_abs"] == pytest.approx(10.0)
    assert c["trend"] == pytest.approx(0.1)
    sp = c["spread"]
    assert sp["min"] == 100.0 and sp["max"] == 120.0 and sp["range"] == 20.0
    assert sp["stdev"] == pytest.approx(math.sqrt(200.0 / 3.0))
    assert sp["cv"] == pytest.approx(math.sqrt(200.0 / 3.0) / 110.0)


def test_c2_hand_numbers(cmp_default):
    c = _cell(cmp_default, "C2")
    assert c["delta"] == [0.0, -20.0, -40.0]
    assert c["delta_pct"] == pytest.approx([0.0, -10.0, -20.0])
    assert c["winner"] == 0
    assert c["trend_abs"] == pytest.approx(-20.0)
    assert c["trend"] == pytest.approx(-0.1)
    assert c["spread"]["range"] == 40.0
    assert c["spread"]["stdev"] == pytest.approx(math.sqrt(800.0 / 3.0))
    assert c["spread"]["cv"] == pytest.approx(math.sqrt(800.0 / 3.0) / 180.0)


def test_c3_nonmonotonic(cmp_default):
    """최악은 R2 인데 기울기는 음수 — winner 와 trend 는 다른 질문에 답한다."""
    c = _cell(cmp_default, "C3")
    assert c["delta"] == [0.0, 40.0, -10.0]
    assert c["delta_pct"] == pytest.approx([0.0, 80.0, -20.0])
    assert c["winner"] == 1
    assert c["trend_abs"] == pytest.approx(-5.0)
    assert c["trend"] == pytest.approx(-0.1)
    assert c["spread"]["range"] == 50.0
    assert c["spread"]["stdev"] == pytest.approx(math.sqrt(1400.0 / 3.0))


def test_c4_trust_gated(cmp_default):
    c = _cell(cmp_default, "C4")
    assert c["gated"] is True
    assert c["delta"] == [None, None, None]
    assert c["delta_pct"] == [None, None, None]
    assert c["winner"] is None
    assert c["trend"] is None and c["trend_abs"] is None
    assert c["spread"] is None
    assert "R2" in c["gate_reason"]
    # 원본 값 자체는 숨기지 않는다 (정직성 — 게이트는 판정만 막는다)
    assert [p["value"] for p in c["per_rev"]] == [10.0, 20.0, 30.0]


def test_trust_gate_off_reveals_c4():
    cmp_dict = _run(Options(trust_gate=False))
    c = _cell(cmp_dict, "C4")
    assert c["gated"] is False
    assert c["delta"] == [0.0, 10.0, 20.0]
    assert c["winner"] == 2
    assert c["trend_abs"] == pytest.approx(10.0)
    assert c["trend"] == pytest.approx(1.0)
    assert c["spread"]["cv"] == pytest.approx(math.sqrt(200.0 / 3.0) / 20.0)
    assert cmp_dict["kpi"]["n_comparable"] == 4


# --------------------------------------------------------------------------
# KPI / 교집합
# --------------------------------------------------------------------------
def test_kpi(cmp_default):
    k = cmp_default["kpi"]
    assert k["n_cells"] == 4
    assert k["n_comparable"] == 3
    assert k["n_gated"] == 1
    assert k["comparable_pct"] == 75.0
    assert k["worst_per_rev"] == [200.0, 180.0, 160.0]
    assert k["n_parts_canonical"] == 2 and k["n_parts_matched"] == 2
    assert k["energy"]["diss_pct"] == [40.0, 45.0, 30.0]
    assert k["energy"]["diss_pct_delta"] == pytest.approx([0.0, 5.0, -10.0])


def test_no_comparable_cells_warning():
    """전 셀 미판정이면 지도가 아니라 경고가 헤드라인."""
    options = Options()
    bundles = [_bundle(lb) for lb in ("R1", "R2", "R3")]
    for b in bundles[1].cells:
        b.trust.ok = False
    match = build_matching(bundles, {}, options)
    aligned = align(bundles, 0, "impact", options.resample)
    cmp_dict = build_comparison(bundles, 0, "impact", match, aligned, options)
    assert cmp_dict["kpi"]["n_comparable"] == 0
    assert "no_comparable_cells" in [w["code"] for w in cmp_dict["warnings"]]
    assert all(p["worst"] == [None, None, None] for p in cmp_dict["parts"])


# --------------------------------------------------------------------------
# 파트 추이 / rank bump
# --------------------------------------------------------------------------
def test_part_trend_excludes_gated_cell(cmp_default):
    a = next(p for p in cmp_default["parts"] if p["canonical"] == "PartA")
    # C4 는 미판정이라 전 리비전에서 동일하게 제외 → C1..C3 의 최대값
    assert a["worst"] == [180.0, 162.0, 144.0]
    assert a["n_cells_used"] == [3, 3, 3]
    assert a["delta"] == pytest.approx([0.0, -18.0, -36.0])
    assert a["delta_pct"] == pytest.approx([0.0, -10.0, -20.0])
    assert a["trend"] == pytest.approx(-0.1)
    assert a["present"] == [True, True, True]


def test_rank_bump(cmp_default):
    a = next(p for p in cmp_default["parts"] if p["canonical"] == "PartA")
    b = next(p for p in cmp_default["parts"] if p["canonical"] == "PartB")
    assert b["worst"] == [90.0, 81.0, 200.0]
    assert a["rank"] == [1, 1, 2]
    assert b["rank"] == [2, 2, 1]
    assert a["rank_delta"] == [0, 0, 1]  # worst 순위에서 내려감 = 상대적으로 나아짐
    assert b["rank_delta"] == [0, 0, -1]  # 순위가 올라감 = 나빠짐


def test_part_matrix(cmp_default):
    pm = cmp_default["part_matrix"]
    assert pm["cells"] == ["C1", "C2", "C3", "C4"]
    assert pm["gated"] == [False, False, False, True]
    row = next(r for r in pm["rows"] if r["canonical"] == "PartA")
    assert row["per_rev"][0] == [90.0, 180.0, 45.0, 9.0]
    assert row["delta_pct"][1] == pytest.approx([10.0, -10.0, 80.0, None])
    assert row["delta_pct"][2] == pytest.approx([20.0, -20.0, -20.0, None])


# --------------------------------------------------------------------------
# behavior 전이
# --------------------------------------------------------------------------
def test_behavior_transitions(cmp_default):
    bt = cmp_default["behavior_transitions"]
    assert bt["headline"] is True
    assert bt["n_changed_cells"] == 2  # C1(R3), C4(R2·R3)
    assert bt["per_rev"][0]["n_changed"] == 0
    assert bt["per_rev"][1]["n_changed"] == 1
    assert bt["per_rev"][2]["n_changed"] == 2
    r2_changed = [e for e in bt["per_rev"][1]["entries"] if e["changed"]]
    assert r2_changed == [{"from": "no-contact", "to": "bounce", "count": 1,
                          "cells": ["C4"], "changed": True}]
    r3_changed = sorted(
        (e for e in bt["per_rev"][2]["entries"] if e["changed"]), key=lambda e: e["cells"]
    )
    assert [(e["from"], e["to"], e["cells"]) for e in r3_changed] == [
        ("bounce", "rebound", ["C1"]),
        ("no-contact", "bounce", ["C4"]),
    ]
    assert "behavior_transition" in [w["code"] for w in cmp_default["warnings"]]


# --------------------------------------------------------------------------
# findings diff
# --------------------------------------------------------------------------
def test_findings_diff(cmp_default):
    fd = cmp_default["findings_diff"]
    assert fd[0]["is_baseline"] is True
    assert [f["title"] for f in fd[1]["new"]] == ["F-new"]
    assert [f["title"] for f in fd[1]["resolved"]] == ["F-old"]
    assert [f["title"] for f in fd[1]["kept"]] == ["F-keep"]
    assert fd[2]["new"] == []
    assert [f["title"] for f in fd[2]["resolved"]] == ["F-old"]


# --------------------------------------------------------------------------
# 가드
# --------------------------------------------------------------------------
def test_schema_version_guard():
    options = Options()
    bundles = [_bundle(lb) for lb in ("R1", "R2")]
    bundles[1].schema_version = 2
    match = build_matching(bundles, {}, options)
    aligned = align(bundles, 0, "impact", options.resample)
    with pytest.raises(CompareError, match="schema_version"):
        build_comparison(bundles, 0, "impact", match, aligned, options)


def test_unit_mismatch_error():
    with pytest.raises(CompareError, match="단위계"):
        _run(unit_labels={"R2": {"acc": "m/s²", "stress": "MPa", "disp": "mm"}})


def test_unit_convert():
    cmp_dict = _run(
        Options(unit_policy="convert"),
        unit_labels={"R2": {"acc": "m/s²", "stress": "MPa", "disp": "mm"}},
    )
    c = _cell(cmp_dict, "C1")
    # R2 의 110 m/s² → baseline mm/s² 기준 110000
    assert c["per_rev"][1]["value"] == pytest.approx(110000.0)
    assert cmp_dict["revisions"][1]["unit_factor"]["g"] == pytest.approx(1000.0)
    assert "unit_converted" in [w["code"] for w in cmp_dict["warnings"]]


def test_unknown_metric():
    options = Options()
    bundles = [_bundle(lb) for lb in ("R1", "R2")]
    match = build_matching(bundles, {}, options)
    aligned = align(bundles, 0, "impact", options.resample)
    with pytest.raises(CompareError, match="metric"):
        build_comparison(bundles, 0, "impact", match, aligned, options, metric="q")


def test_slope_helper():
    assert compare_mod._slope([100.0, 110.0, 120.0]) == pytest.approx(10.0)
    assert compare_mod._slope([5.0]) is None
    assert compare_mod._slope([3.0, 3.0, 3.0]) == pytest.approx(0.0)
