# 각도 이름이 같다고 '실측 일치' 로 짝지어 버리던 결함을 못박는 시험
"""이름이 같다 ≠ 같은 방향.

배경(2026-09 전수조사). 실제 Fibonacci DOE 는 방향 이름이 **런 순번**이다 —
P0001..P1146(6° 격자), P0001..P10313(2° 격자), P0001..P0100. 그래서 격자 크기가
다르면 같은 이름이 전혀 다른 방향을 가리킨다. 그런데 `_align_sphere` 는 세 경로
(identity / off / nearest) 모두 **이름만 보고** 짝을 지었고, 그 짝을
source='exact', measured=True, offset=0.0 으로 기록했다. 실측 격자로 재현했을 때
가장 나쁜 짝은 141° 떨어져 있었는데도 '실측률 100%' 로 보고됐다.
"""
from __future__ import annotations

import math

from koo_federate_report.models import Cell, RevisionBundle, Trust
from koo_federate_report.resample import align


def _bundle(label, angles):
    """angles: [(name, roll, pitch), ...]"""
    cells = [
        Cell(key=nm, label=nm, category="fibonacci", roll=r, pitch=p, yaw=0.0,
             metrics={"g": 100.0 + i, "s": 10.0, "e": None, "d": None},
             trust=Trust(True, "no gate"))
        for i, (nm, r, p) in enumerate(angles)
    ]
    return RevisionBundle(
        label=label, kind="sphere", path=f"/syn/{label}.json",
        meta={"project": label}, unit_labels={}, parts={1: "PartA"},
        angles=[{"name": c.key, "roll": c.roll, "pitch": c.pitch, "yaw": 0.0} for c in cells],
        cells=cells, part_cells={}, kpi={"n_cells": len(cells)},
        trust={"n_cells": len(cells), "n_gated": 0},
    )


def _fib(n):
    """런 순번 이름을 붙인 Fibonacci 격자 n점 — 실캠페인과 같은 명명 규칙."""
    out = []
    ga = math.pi * (3.0 - math.sqrt(5.0))
    for i in range(n):
        z = 1.0 - (2.0 * i + 1.0) / n
        r = math.sqrt(max(0.0, 1.0 - z * z))
        lat = math.degrees(math.asin(max(-1.0, min(1.0, z))))
        lon = math.degrees(math.atan2(r * math.sin(ga * i), r * math.cos(ga * i)))
        out.append((f"P{i + 1:04d}", round(lat, 4), round(lon, 4)))
    return out


def _pairs_far_apart(res, a, b):
    """이름으로 짝지어진 쌍 중 실제 각도가 1° 이상 떨어진 것의 수."""
    from koo_federate_report.resample import _ang_dist_deg, _unit_vec
    ia = {c.key: c for c in a.cells}
    ib = {c.key: c for c in b.cells}
    n = 0
    for node in res.nodes:
        s = node.per_rev[1]
        if s.source != "exact" or s.cell_key is None:
            continue
        ca, cb = ia.get(node.key), ib.get(s.cell_key)
        if ca is None or cb is None:
            continue
        if _ang_dist_deg(_unit_vec(ca.roll, ca.pitch), _unit_vec(cb.roll, cb.pitch)) > 1.0:
            n += 1
    return n


def test_nearest_does_not_call_a_102_degree_pair_exact():
    """이름만 같고 방향이 다른 쌍을 '실측 일치' 로 쓰면 지도가 통째로 뒤섞인다."""
    a = _bundle("RevA", _fib(40))
    b = _bundle("RevB", _fib(17))
    res = align([a, b], 0, "sphere", "nearest")
    assert _pairs_far_apart(res, a, b) == 0, "각도가 어긋난 쌍이 exact 로 남아 있다"


def test_measured_pct_is_not_inflated_to_100():
    """실측률(실측 비율)은 헤드라인 숫자다 — 이름 일치로 100% 를 만들면 안 된다."""
    a = _bundle("RevA", _fib(40))
    b = _bundle("RevB", _fib(17))
    res = align([a, b], 0, "sphere", "nearest")
    row = res.coverage["per_rev"][1]
    assert row["measured_pct"] < 100.0, res.coverage


def test_off_mode_does_not_intersect_by_name_alone():
    """off(교집합) 모드도 같은 규칙 — 이름 교집합은 방향 교집합이 아니다."""
    a = _bundle("RevA", _fib(40))
    b = _bundle("RevB", _fib(17))
    res = align([a, b], 0, "sphere", "off")
    assert _pairs_far_apart(res, a, b) == 0, "off 모드가 이름만 보고 묶었다"


def test_identical_grid_still_matches_exactly():
    """같은 격자는 그대로 실측 일치여야 한다 — 회귀 금지."""
    angles = _fib(30)
    a, b = _bundle("RevA", angles), _bundle("RevB", angles)
    res = align([a, b], 0, "sphere", "nearest")
    assert all(s.source == "exact" and s.measured for n in res.nodes for s in n.per_rev)
    assert res.coverage["per_rev"][1]["measured_pct"] == 100.0


def test_mismatch_is_reported_as_a_warning():
    """조용히 강등하지 않는다 — 무슨 일이 있었는지 말한다."""
    a = _bundle("RevA", _fib(40))
    b = _bundle("RevB", _fib(17))
    res = align([a, b], 0, "sphere", "nearest")
    codes = [w["code"] for w in res.warnings]
    assert "angle_name_collision" in codes, res.warnings


def test_all():
    """pytest 진입점."""
    test_nearest_does_not_call_a_102_degree_pair_exact()
    test_measured_pct_is_not_inflated_to_100()
    test_off_mode_does_not_intersect_by_name_alone()
    test_identical_grid_still_matches_exactly()
    test_mismatch_is_reported_as_a_warning()
