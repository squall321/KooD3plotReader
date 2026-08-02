# 카테고리 소계 손계산 — face/edge/corner 소계와 baseline 대비 Δ%
"""픽스처 (metric='g', 2리비전, baseline=R1)

  cell  category  R1     R2    비고
  C1    F5        100    110
  C2    F5        200    180
  C3    F1         50     60
  C4    F1         10     20   R2 신뢰 게이트 FAIL → 미판정 (소계에서 제외)
  C5    F2         60     30

손계산
  F5: R1 worst 200 median 150 mean 150 / R2 worst 180 median 145 mean 145
      Δ% = worst -10, median -10/3, mean -10/3
  F1: C4 제외 → C3 만. R1 50 / R2 60 → Δ% +20 (worst=median=mean)
  F2: C5 만. R1 60 / R2 30 → Δ% -50
  정렬은 baseline worst 내림차순 → F5(200), F2(60), F1(50)
"""
from __future__ import annotations

import pytest

from koo_federate_report.compare import UNCATEGORIZED, build_comparison
from koo_federate_report.config import Options
from koo_federate_report.matching import build_matching
from koo_federate_report.resample import align

from .helpers import make_impact_bundle

PARTS = {1: "PartA"}
#           key    x     y     category
COORDS = [("C1", 0.0, 0.0, "F5"), ("C2", 20.0, 0.0, "F5"), ("C3", 0.0, 20.0, "F1"),
          ("C4", 20.0, 20.0, "F1"), ("C5", 40.0, 0.0, "F2")]
G = {
    "R1": {"C1": 100.0, "C2": 200.0, "C3": 50.0, "C4": 10.0, "C5": 60.0},
    "R2": {"C1": 110.0, "C2": 180.0, "C3": 60.0, "C4": 20.0, "C5": 30.0},
}
TRUST = {"R1": {}, "R2": {"C4": False}}


def _bundle(label, categories=None):
    specs = [
        (key, x, y, (categories or {}).get(key, cat), G[label][key],
         TRUST[label].get(key, True), "bounce")
        for key, x, y, cat in COORDS
    ]
    return make_impact_bundle(label, specs, PARTS)


def _run(categories=None, options=None):
    options = options or Options()
    bundles = [_bundle(lb, categories) for lb in ("R1", "R2")]
    match = build_matching(bundles, {}, options)
    aligned = align(bundles, 0, "impact", options.resample)
    return build_comparison(bundles, 0, "impact", match, aligned, options, metric="g")


@pytest.fixture(scope="module")
def cs():
    return _run()["category_summary"]


def _cat(cs_, name):
    return next(c for c in cs_["categories"] if c["name"] == name)


def test_header(cs):
    assert cs["metric"] == "g"
    assert cs["n_categories"] == 3
    assert cs["baseline_idx"] == 0
    assert cs["n_excluded_gated"] == 1  # C4


def test_sorted_by_baseline_worst(cs):
    assert [c["name"] for c in cs["categories"]] == ["F5", "F2", "F1"]


def test_f5_hand_calc(cs):
    f5 = _cat(cs, "F5")
    assert f5["n_cells"] == 2 and f5["cells"] == ["C1", "C2"]
    r1, r2 = f5["per_rev"]
    assert (r1["n"], r1["worst"], r1["median"], r1["mean"]) == (2, 200.0, 150.0, 150.0)
    assert (r2["n"], r2["worst"], r2["median"], r2["mean"]) == (2, 180.0, 145.0, 145.0)
    assert r1["worst_delta_pct"] == 0.0
    assert r2["worst_delta_pct"] == pytest.approx(-10.0)
    assert r2["median_delta_pct"] == pytest.approx(-10.0 / 3.0)
    assert r2["mean_delta_pct"] == pytest.approx(-10.0 / 3.0)


def test_gated_cell_excluded_from_subtotal(cs):
    """C4 는 R2 가 미판정이라 F1 소계에서 양쪽 리비전 모두 빠진다."""
    f1 = _cat(cs, "F1")
    assert f1["n_cells"] == 1 and f1["cells"] == ["C3"]
    r1, r2 = f1["per_rev"]
    assert r1["worst"] == 50.0 and r2["worst"] == 60.0
    assert r2["worst_delta_pct"] == pytest.approx(20.0)


def test_single_cell_category(cs):
    f2 = _cat(cs, "F2")
    r1, r2 = f2["per_rev"]
    assert (r1["worst"], r1["median"], r1["mean"]) == (60.0, 60.0, 60.0)
    assert r2["worst_delta_pct"] == pytest.approx(-50.0)


def test_single_category_yields_empty_dict():
    """카테고리가 1종뿐이면 비교할 것이 없으므로 빈 dict (보고서가 섹션 생략)."""
    same = {k: "F5" for k, _, _, _ in COORDS}
    assert _run(categories=same)["category_summary"] == {}


def test_blank_category_is_labelled_not_dropped():
    """빈 카테고리는 버리지 않고 '(미지정)' 한 칸으로 모은다."""
    mixed = {"C1": "", "C2": "", "C3": "F1", "C4": "F1", "C5": "F1"}
    cs_ = _run(categories=mixed)["category_summary"]
    names = [c["name"] for c in cs_["categories"]]
    assert UNCATEGORIZED in names and "F1" in names
    assert _cat(cs_, UNCATEGORIZED)["n_cells"] == 2


def test_trust_gate_off_includes_all_cells():
    cs_ = _run(options=Options(trust_gate=False))["category_summary"]
    f1 = _cat(cs_, "F1")
    assert f1["n_cells"] == 2 and cs_["n_excluded_gated"] == 0
    r1, r2 = f1["per_rev"]
    assert (r1["worst"], r1["mean"]) == (50.0, 30.0)     # (50+10)/2
    assert (r2["worst"], r2["mean"]) == (60.0, 40.0)     # (60+20)/2
    assert r2["mean_delta_pct"] == pytest.approx(100.0 / 3.0)
