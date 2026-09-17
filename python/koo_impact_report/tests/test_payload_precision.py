# payload 반올림이 작은 단위계 값을 0 으로 뭉개지 않는지 보는 시험
"""고정 소수 자릿수 반올림은 단위계를 가정한다.

- `round(density, 6)` 은 ton/mm³ 밀도 7.85e-09 를 0.0 으로 만든다. 실측
  Test_Impact_A 의 meta.impactor.density 는 7.85e-09 인데 부품 드릴다운
  재료카드에는 0.000000 이 찍혔다.
- `round(worst_s, 1)` 은 GPa 단위 덱(최악 0.0863 GPa)을 0.1 로 올려 +16%
  과대 표시하고, --stress-limit 0.09 와 비교하면 넘지도 않은 한계를
  넘은 것으로 칠한다.

둘 다 유효숫자 기반(_r4)으로 바꾼다 — 자릿수는 화면에서 정한다.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from koo_impact_report.report.payload.common import _r4  # noqa: E402


class _Pos:
    def __init__(self, pos_id, x=0.0, y=0.0):
        self.pos_id, self.x, self.y = pos_id, x, y


class _Part:
    def __init__(self, pid, name="P"):
        self.part_id, self.part_name, self.group = pid, name, ""


class _Res:
    def __init__(self, pid, pos, g, s):
        self.part_id, self.position = pid, pos
        self.peak_g, self.peak_stress, self.peak_disp = g, s, 0.1
        self.peak_strain = 1e-5
        self.peak_vel = 1.0
        self.face = "F5"


class _Imp:
    #: ton-mm-s 강철 — 밀도 7.85e-09, E 210000 MPa.
    youngs_modulus = 210000.0
    density = 7.85e-09
    part_id = 99


class _Rep:
    def __init__(self):
        self.parts = [_Part(7)]
        self.results = [_Res(7, _Pos("F5_DOE_001"), 1000.0, 0.0863)]
        self.impactor = _Imp()
        self.sim_params = {}
        self.positions_by_face = {"F5": [self.results[0].position]}
        self.part_motions = {}
        self.impactor_trajectories = {}


def test_impactor_density_survives_rounding():
    """ton/mm³ 밀도 7.85e-09 가 0 이 되지 않는다."""
    from koo_impact_report.report.payload.analytics import _build_per_part_drilldown

    out = _build_per_part_drilldown(_Rep())
    d = out["impactor_material"]["density"]
    assert d is not None and d > 0, f"밀도가 {d} 로 뭉개졌다"
    assert abs(d - 7.85e-09) / 7.85e-09 < 1e-3
    # kg/mm³ 덱(7.85e-06)도 같은 이유로 살아야 한다.
    assert _r4(7.85e-06) > 0


def test_worst_stress_keeps_full_precision():
    """GPa 단위 최악 응력 0.0863 이 0.1 로 반올림되지 않는다."""
    from koo_impact_report.models import (
        FaceOrientation, ImpactPosition, ImpactReport, ImpactorSpec,
        PairResult, PartInfo,
    )
    from koo_impact_report.report.payload import _build_payload

    pos = ImpactPosition(pos_id="F5_DOE_001", face="F5", x=0.0, y=0.0)
    rep = ImpactReport(
        project_name="unit",
        impactor=ImpactorSpec(type="Sphere", radius=8.0, density=7.85e-09,
                              youngs_modulus=210000.0, part_id=99),
        faces=[FaceOrientation("F5", "Top", 90.0, 0.0, 0.0)],
        positions_by_face={"F5": [pos]},
        parts=[PartInfo(part_id=7, part_name="PKG 7")],
        results=[PairResult(face="F5", position=pos, part_id=7,
                            peak_g=1000.0, peak_stress=0.0863,
                            peak_strain=1e-5, peak_disp=0.1, peak_vel=1.0)],
        # kg-mm-ms 계열 덱: 응력 라벨이 GPa 인 경우를 그대로 쓴다.
        sim_params={"unit_labels": {"stress": "GPa", "acc": "mm/ms²"}},
    )
    payload = _build_payload(rep)
    ws = payload["kpi"]["worst_s"]
    assert abs(ws - 0.0863) < 1e-9, f"worst_s 가 {ws} 로 뭉개졌다"
    # --stress-limit 0.09 와 비교했을 때 넘지 않아야 한다.
    assert ws <= 0.09


def test_all():
    """pytest 진입점 — 위 시험들을 한 번에 돌린다."""
    test_impactor_density_survives_rounding()
    test_worst_stress_keeps_full_precision()
