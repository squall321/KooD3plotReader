# sim_params(dict) 를 getattr 로 읽어 항복응력·그리드가 늘 비던 문제를 잡는 시험
"""`sim_params` 는 dict 다 — `getattr` 로는 절대 안 읽힌다.

`getattr({"yield_stress_by_part": {...}}, "yield_stress_by_part", None)` 은
언제나 None 이라, *MAT_PLASTIC_KINEMATIC 덱에서 항복 기반 손상지수(DI)가
단 한 번도 쓰이지 않고 조용히 composite 점수가 표시됐다. 그리드(nx/ny)도
마찬가지로 늘 기본값 5×5 로 떨어졌다.

DOE 위치 id 는 'F5_DOE_001' 같은 문자열이라 `int(peak_pos)` 도 터진다.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from koo_impact_report.report.payload.insights import _build_damage_index  # noqa: E402


class _Pos:
    def __init__(self, pos_id, x=0.0, y=0.0):
        self.pos_id = pos_id
        self.x = x
        self.y = y


class _Part:
    def __init__(self, pid, name):
        self.part_id = pid
        self.part_name = name


class _Res:
    def __init__(self, pid, pos, s):
        self.part_id = pid
        self.position = pos
        self.peak_g = 1.0
        self.peak_stress = s
        self.peak_strain = 1e-5


class _Rep:
    def __init__(self, parts, results, sim_params):
        self.parts = parts
        self.results = results
        self.sim_params = sim_params
        self.positions_by_face = {"F5": [r.position for r in results]}


def _report():
    parts = [_Part(7, "PKG 7")]
    results = [
        _Res(7, _Pos("F5_DOE_001", -40, -40), 180.0),   # σy=100 → excess 0.8
        _Res(7, _Pos("F5_DOE_002", 0, 0), 150.0),       # excess 0.5
        _Res(7, _Pos("F5_DOE_003", 40, 40), 50.0),      # 항복 미만
    ]
    return _Rep(parts, results, {"yield_stress_by_part": {7: 100.0}})


def test_yield_based_di_is_actually_used():
    """항복값이 있으면 di_source 가 'yield' 여야 한다 (종전엔 늘 composite)."""
    out = _build_damage_index(_report())
    assert out["summary"]["has_yield"] is True, out["summary"]
    row = out["per_part"][0]
    assert row["di_source"] == "yield", row
    assert abs(row["di"] - 1.3) < 1e-6, row["di"]      # 0.8 + 0.5
    assert row["n_positions_above_yield"] == 2


def test_string_pos_id_does_not_crash():
    """'F5_DOE_001' 같은 문자열 위치 id 가 int() 로 터지지 않는다."""
    out = _build_damage_index(_report())
    assert out["per_part"][0]["peak_pos_id"] == "F5_DOE_001"


def test_no_yield_still_falls_back_to_composite():
    """항복값이 없으면 종전대로 composite — 회귀 방지."""
    rep = _report()
    rep.sim_params = {}
    out = _build_damage_index(rep)
    assert out["summary"]["has_yield"] is False
    assert out["per_part"][0]["di_source"] == "composite"


def test_all():
    """pytest 진입점 — 위 시험들을 한 번에 돌린다."""
    test_yield_based_di_is_actually_used()
    test_string_pos_id_does_not_crash()
    test_no_yield_still_falls_back_to_composite()
