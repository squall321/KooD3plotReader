# tier 정책 검증 — tier 표 경계, 프로파일 선정 규칙, 집계 밴드 손계산
"""tiers.py 는 "프로파일이 무엇을 그릴지"만 줄인다.

여기서 거는 계약
  - tier 경계값 (200/800/2000) 과 top-K (전량/400/300/200)
  - 축소해도 **이야기가 있는 셀**(리비전별 최악·winner·|trend| 상위)은 살아남는다
  - cells[] 자체는 절대 줄지 않는다 (probe/지도가 전량을 쓴다)
  - 집계 밴드: value 는 전량, delta_pct 는 미판정 제외
"""
from __future__ import annotations

import pytest

from koo_federate_report import tiers
from koo_federate_report.compare import build_comparison
from koo_federate_report.config import Options
from koo_federate_report.matching import build_matching
from koo_federate_report.resample import align

from .helpers import make_impact_bundle


def _cell(key, values, winner=None, trend=None, gated=False, category=""):
    """compare.py 가 만드는 cell dict 의 최소 형태."""
    base = values[0]
    return {
        "key": key,
        "category": category,
        "per_rev": [{"value": v} for v in values],
        "delta_pct": [
            None if (gated or v is None or not base) else (v - base) / abs(base) * 100.0
            for v in values
        ],
        "winner": winner if winner is not None else max(range(len(values)), key=lambda i: values[i]),
        "trend": trend if trend is not None else (values[-1] - values[0]) / abs(base),
        "gated": gated,
    }


# --------------------------------------------------------------------------
# tier 표
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "n,name,top_k",
    [
        (1, "A", None), (200, "A", None),
        (201, "B", 400), (800, "B", 400),
        (801, "C", 300), (2000, "C", 300),
        (2001, "D", 200), (100000, "D", 200),
    ],
)
def test_tier_boundaries(n, name, top_k):
    assert tiers.tier_for(n) == (name, top_k)


def test_tier_a_no_reduction():
    cells = [_cell(f"C{i}", [100.0 - i, 90.0 - i]) for i in range(50)]
    plan = tiers.build_tier_plan(cells, 0, 2)
    assert plan["tier"]["name"] == "A"
    assert plan["tier"]["reduced"] is False
    assert plan["profile_cells"] is None and plan["profile_aggregate"] is None


def test_tier_b_reduces_only_profile():
    cells = [_cell(f"C{i:04d}", [1000.0 - i, 900.0 - i * 1.1]) for i in range(500)]
    plan = tiers.build_tier_plan(cells, 0, 2)
    assert plan["tier"]["name"] == "B"
    assert plan["tier"]["top_k"] == 400
    assert len(plan["profile_cells"]) == 400
    assert plan["profile_aggregate"]["n"] == 100
    # cells[] 는 손대지 않는다 — 축소는 표시 힌트일 뿐이다
    assert len(cells) == 500


def test_tier_c_and_d_top_k():
    c_cells = [_cell(f"C{i:04d}", [1000.0 - i, 900.0 - i]) for i in range(900)]
    assert len(tiers.build_tier_plan(c_cells, 0, 2)["profile_cells"]) == 300
    d_cells = [_cell(f"C{i:04d}", [3000.0 - i, 2700.0 - i]) for i in range(2500)]
    d_plan = tiers.build_tier_plan(d_cells, 0, 2)
    assert d_plan["tier"]["name"] == "D"
    assert len(d_plan["profile_cells"]) == 200
    assert d_plan["profile_aggregate"]["n"] == 2300


# --------------------------------------------------------------------------
# 선정 규칙 — "이야기가 있는 셀"은 반드시 살아남는다
# --------------------------------------------------------------------------
def _story_fixture(n=1200, n_rev=3):
    """baseline 심각도와 다른 축(리비전별 최악·trend)에 이야기를 심어 둔 합성 셀."""
    cells = []
    for i in range(n):
        base = 1000.0 - i * 0.5          # 심각도는 인덱스 순
        v1 = base * 0.9
        v2 = base * 0.8
        if i == 900:                      # 심각도는 낮지만 rev2 가 전체 최악
            v2 = 5000.0
        if i == 950:                      # 심각도는 낮지만 rev1 이 전체 최악
            v1 = 4000.0
        if i == 1100:                     # 심각도는 최하위지만 악화 폭이 최대
            v1, v2 = base * 3.0, base * 6.0
        cells.append(_cell(f"C{i:04d}", [base, v1, v2]))
    return cells


def test_story_cells_survive_reduction():
    cells = _story_fixture()
    plan = tiers.build_tier_plan(cells, 0, 3)
    keys = set(plan["profile_cells"])
    assert plan["tier"]["name"] == "C" and len(keys) == 300

    # 1) 각 리비전의 전체 최악 셀 (앵커) — worst KPI 가 가리키는 바로 그 셀
    for r in range(3):
        worst = max(cells, key=lambda c: c["per_rev"][r]["value"])
        assert worst["key"] in keys, f"rev{r} 의 최악 셀이 프로파일에서 사라졌다"

    # 2) |trend| 상위 10개
    top_trend = sorted(cells, key=lambda c: -abs(c["trend"]))[:10]
    assert all(c["key"] in keys for c in top_trend), "|trend| 상위 셀이 사라졌다"

    # 3) baseline 심각도 상위 100개
    top_sev = sorted(cells, key=lambda c: -c["per_rev"][0]["value"])[:100]
    assert all(c["key"] in keys for c in top_sev), "심각도 상위 셀이 사라졌다"


def test_selection_is_deterministic():
    cells = _story_fixture()
    a = tiers.build_tier_plan(cells, 0, 3)["profile_cells"]
    b = tiers.build_tier_plan(cells, 0, 3)["profile_cells"]
    assert a == b


def test_selection_counts_cover_every_reason():
    cells = _story_fixture()
    counts = tiers.build_tier_plan(cells, 0, 3)["tier"]["selection"]
    assert counts["anchor"] >= 1
    assert counts["severity"] >= 1
    assert sum(counts.values()) == 300


# --------------------------------------------------------------------------
# 집계 밴드 손계산
# --------------------------------------------------------------------------
#  key  r0   r1     Δ%(r1)
#   A   100   90    -10
#   B    50  120   +140
#   C    40   30    -25
#   D    30   35   +16.666…
#   E    20   10    -50
#   F    10   12    +20
#  top_k=3 → 앵커 A(r0 최악)·B(r1 최악) + 심각도 C  ⇒ 나머지 D·E·F 가 밴드
_BAND_SPECS = [("A", 100.0, 90.0), ("B", 50.0, 120.0), ("C", 40.0, 30.0),
               ("D", 30.0, 35.0), ("E", 20.0, 10.0), ("F", 10.0, 12.0)]


def _band_cells():
    return [_cell(k, [a, b]) for k, a, b in _BAND_SPECS]


def test_selection_hand_calc():
    sel = tiers.select_profile_cells(_band_cells(), 0, 2, 3)
    assert sorted(sel["keys"]) == ["A", "B", "C"]
    assert sel["reasons"]["A"] == "anchor"   # r0 최악
    assert sel["reasons"]["B"] == "anchor"   # r1 최악
    assert sel["reasons"]["C"] == "severity"


def test_aggregate_band_hand_calc():
    cells = _band_cells()
    rest = [c for c in cells if c["key"] in ("D", "E", "F")]
    agg = tiers._aggregate(rest, 2)
    assert agg["n"] == 3 and agg["n_gated"] == 0
    assert agg["value"]["min"] == [10.0, 10.0]
    assert agg["value"]["median"] == [20.0, 12.0]
    assert agg["value"]["max"] == [30.0, 35.0]
    assert agg["delta_pct"]["min"] == pytest.approx([0.0, -50.0])
    assert agg["delta_pct"]["median"] == pytest.approx([0.0, 100.0 * 5.0 / 30.0])
    assert agg["delta_pct"]["max"] == pytest.approx([0.0, 20.0])


def test_aggregate_excludes_gated_delta_but_keeps_value():
    """미판정 셀의 Δ 는 밴드에서 빼되, 측정값 자체는 숨기지 않는다."""
    rest = [_cell("D", [30.0, 35.0]), _cell("E", [20.0, 10.0], gated=True)]
    agg = tiers._aggregate(rest, 2)
    assert agg["n_gated"] == 1
    assert agg["value"]["min"] == [20.0, 10.0]      # 값은 전량
    assert agg["delta_pct"]["min"] == pytest.approx([0.0, 100.0 * 5.0 / 30.0])
    assert agg["delta_pct"]["max"] == pytest.approx([0.0, 100.0 * 5.0 / 30.0])


def test_empty_cells():
    plan = tiers.build_tier_plan([], 0, 2)
    assert plan["tier"]["name"] == "A" and plan["profile_cells"] is None


# --------------------------------------------------------------------------
# compare.py 계약 통합
# --------------------------------------------------------------------------
def test_compare_emits_tier_contract():
    parts = {1: "PartA"}
    specs = [(f"C{i:03d}", float(i), 0.0, "F5", 100.0 + i, True, "bounce") for i in range(300)]
    bundles = [
        make_impact_bundle("R1", specs, parts),
        make_impact_bundle(
            "R2",
            [(k, x, y, f, g * 0.9, ok, b) for k, x, y, f, g, ok, b in specs],
            parts,
        ),
    ]
    options = Options()
    match = build_matching(bundles, {}, options)
    aligned = align(bundles, 0, "impact", options.resample)
    cmp_ = build_comparison(bundles, 0, "impact", match, aligned, options)
    # 셀 300개 → tier B 이지만 top_k 400 이하이므로 축소되지 않아야 한다
    assert cmp_["tier"]["name"] == "B"
    assert cmp_["tier"]["reduced"] is False
    assert cmp_["profile_cells"] is None and cmp_["profile_aggregate"] is None
    assert len(cmp_["cells"]) == 300
