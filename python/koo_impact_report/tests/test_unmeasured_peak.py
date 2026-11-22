# deep 이 「값 없음」(None)으로 넘긴 피크를 impact 로더가 0 으로 바꾸지 않는지 보는 시험
"""_extract_part_stress_strain 은 global_max 를 float(… or 0.0) 로 읽어, 전 구간 미계측 시계열(None)을
「측정된 0 MPa」 로 바꿨다. 아래 단계(PairResult)는 이미 None 을 「응력 이력 없음」 으로 다룬다.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from koo_impact_report.loader import _extract_part_stress_strain  # noqa: E402


class _Series:
    def __init__(self, pid, quantity, global_max):
        self.part_id = pid
        self.part_name = ""
        self.quantity = quantity
        self.unit = "MPa"
        self.global_max = global_max
        self.global_min = global_max
        self.time_of_max = None if global_max is None else 1.0
        self.data = [{"time": 0.0, "max": global_max}, {"time": 1.0, "max": global_max}]


class _Result:
    def __init__(self, stress, strain):
        self.metadata = {"num_states": 2}
        self.stress = stress
        self.strain = strain
        self.output_dir = None

    @property
    def num_states(self):
        return 2


def test_unmeasured_peak_stays_none():
    rec = _extract_part_stress_strain(_Result([_Series(5, "von_mises", None)], [_Series(5, "eff_plastic_strain", None)]))[5]
    assert rec["peak_stress"] is None
    assert rec["peak_strain"] is None


def test_measured_peak_unchanged():
    rec = _extract_part_stress_strain(_Result([_Series(5, "von_mises", 120.0)], [_Series(5, "eff_plastic_strain", 0.0)]))[5]
    assert rec["peak_stress"] == 120.0
    assert rec["peak_strain"] == 0.0
