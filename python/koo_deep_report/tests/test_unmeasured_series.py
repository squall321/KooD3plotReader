# 전 구간 미계측 시계열(global_unmeasured)을 측정된 0 으로 읽지 않는지 보는 시험
"""analysis_result.json 의 시계열이 전 상태에서 미계측이면(셸에만 변형률 텐서가 있는 덱의 솔리드 파트 등)
C++ 는 global_max · global_min · time_of_max 를 쓰지 않고 "global_unmeasured": true 를 쓴다.
예전 _parse_series 는 빠진 키를 0.0 으로 채워 「측정된 0」 으로 보고했다.
"""
from pathlib import Path

from koo_deep_report.__main__ import _aggregate
from koo_deep_report.core.d3plot_reader import _parse_series
from koo_deep_report.report.models import D3plotResult, SimInfo

UNMEASURED = {
    "part_id": 2, "quantity": "von_mises_strain", "unit": "", "num_points": 2,
    "global_unmeasured": True, "global_unmeasured_reason": "전 상태에서 이 물리량이 계측되지 않았습니다",
    "data": [{"time": 0.0, "max": None, "min": None, "avg": None}, {"time": 1.0, "max": None, "min": None, "avg": None}],
}
MEASURED = {
    "part_id": 1, "quantity": "von_mises", "unit": "MPa", "num_points": 2,
    "global_max": 300.0, "global_min": 0.0, "time_of_max": 1.0,
    "data": [{"time": 0.0, "max": 0.0, "min": 0.0, "avg": 0.0, "max_element_id": 1},
             {"time": 1.0, "max": 300.0, "min": 0.0, "avg": 150.0, "max_element_id": 7}],
}


def test_parse_unmeasured_is_none_not_zero():
    s = _parse_series(UNMEASURED)
    assert s.global_max is None and s.global_min is None and s.time_of_max is None


def test_parse_measured_unchanged():
    s = _parse_series(MEASURED)
    assert (s.global_max, s.global_min, s.time_of_max) == (300.0, 0.0, 1.0)


def test_aggregate_treats_unmeasured_as_absent():
    stress2 = dict(UNMEASURED, quantity="von_mises", unit="MPa")
    dr = D3plotResult(
        metadata={"num_states": 2, "end_time": 1.0, "analyzed_parts": [1, 2]},
        stress=[_parse_series(MEASURED), _parse_series(stress2)],
        strain=[], acceleration=[], motion={},
        vm_strain=[_parse_series(dict(UNMEASURED, part_id=1))],
        output_dir=Path("/tmp"),
    )
    si = SimInfo(path=Path("/tmp/case"), d3plot=Path("/tmp/case/d3plot"), tier=1)
    res = _aggregate(si, dr, None, 0.0, "case")
    assert res.parts[1].peak_stress == 300.0
    assert res.parts[1].peak_vm_strain is None, "미계측 변형률 텐서 시계열은 0 이 아니라 값 없음"
    assert res.parts[2].peak_stress is None and res.parts[2].peak_stress_reason
    assert res.peak_stress_global == 300.0
