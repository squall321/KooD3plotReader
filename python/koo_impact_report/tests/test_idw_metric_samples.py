# IDW 위험면 회귀 — 한 지표만 잰 위치가 다른 지표 면에 0 으로 박히지 않는지
"""가속도는 쟀지만 응력을 못 잰 낙하점이 있다.

결측 제외 조건이 `pid not in pos_g and pid not in pos_s` 라, 그런 위치는
표본에 남고 `pos_s.get(pid, 0.0)` 로 응력 0.0 이 된다. 그 0 이 31×31 응력
예측면에 '0 으로 측정된 낙하점' 으로 박혀 주변까지 끌어내린다.

지표별로 표본을 따로 가져야 한다.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from koo_impact_report.report.payload.doe import (  # noqa: E402
    _build_idw_predictor_payload,
)


class _Pos:
    def __init__(self, pos_id, x, y):
        self.pos_id, self.x, self.y = pos_id, x, y


class _Res:
    def __init__(self, pos, g, s):
        self.position, self.peak_g, self.peak_stress = pos, g, s


class _Rep:
    def __init__(self, results, positions, bbox):
        self.sim_params = {"grid": {"bbox": list(bbox)}}
        self.positions_by_face = {"F1": positions}
        self.results = results


BBOX = [-50.0, -50.0, 50.0, 50.0]


def _grid5(stress_missing_at=None):
    """5×5 격자 — 응력은 어디서나 400 MPa 로 평탄하다."""
    positions, results = [], []
    for i in range(5):
        for j in range(5):
            p = _Pos(f"P{i}{j}", -40.0 + 20.0 * i, -40.0 + 20.0 * j)
            positions.append(p)
            s = None if p.pos_id == stress_missing_at else 400.0
            results.append(_Res(p, 1000.0, s))
    return _Rep(results, positions, BBOX)


def test_unmeasured_stress_position_is_not_a_zero_sample():
    """응력을 못 잰 위치는 응력면 표본이 아니다 — 평탄면이 눌리면 안 된다."""
    full = _build_idw_predictor_payload(_grid5())
    holed = _build_idw_predictor_payload(_grid5(stress_missing_at="P22"))
    a = full["grid_fine"]["peak_stress"]
    b = holed["grid_fine"]["peak_stress"]
    worst = max(abs(x - y) for x, y in zip(a, b))
    assert worst < 1e-6, f"응력면이 0 표본에 눌렸다 (최대 차 {worst})"


def test_measured_points_report_unmeasured_metric_as_null():
    """못 잰 지표는 0.0 이 아니라 null 로 실려야 한다."""
    holed = _build_idw_predictor_payload(_grid5(stress_missing_at="P22"))
    m = [p for p in holed["measured_points"] if p["pos_id"] == "P22"][0]
    assert m["peak_stress"] is None, m
    assert m["peak_g"] == 1000.0, m


def test_peak_g_surface_unaffected_by_missing_stress():
    """가속도면은 응력 결측과 무관하다."""
    full = _build_idw_predictor_payload(_grid5())
    holed = _build_idw_predictor_payload(_grid5(stress_missing_at="P22"))
    a = full["grid_fine"]["peak_g"]
    b = holed["grid_fine"]["peak_g"]
    assert max(abs(x - y) for x, y in zip(a, b)) < 1e-9


def test_stress_surface_is_null_when_too_few_stress_samples():
    """응력 표본이 1개 이하면 면을 지어내지 않는다 — null 과 사유를 싣는다."""
    positions, results = [], []
    for i in range(5):
        p = _Pos(f"Q{i}", -40.0 + 20.0 * i, 0.0)
        positions.append(p)
        results.append(_Res(p, 1000.0, 400.0 if i == 0 else None))
    out = _build_idw_predictor_payload(_Rep(results, positions, BBOX))
    assert out["grid_fine"]["peak_stress"] is None, out["grid_fine"]["peak_stress"]
    notes = out.get("metric_notes") or {}
    assert notes.get("peak_stress"), notes
    assert out["grid_fine"]["peak_g"] is not None


def test_loo_only_uses_peak_g_samples():
    """LOO 는 peak_g 표본만 쓴다 — 응력 결측 위치가 끼면 안 된다."""
    holed = _build_idw_predictor_payload(_grid5(stress_missing_at="P22"))
    loo = holed["loo_validation"]
    assert loo is not None
    ids = {p["pos_id"] for p in loo["per_point"]}
    assert len(ids) == 25, sorted(ids)


def test_all():
    """진입점 — 이 파일의 시험을 모두 돌린다."""
    test_unmeasured_stress_position_is_not_a_zero_sample()
    test_measured_points_report_unmeasured_metric_as_null()
    test_peak_g_surface_unaffected_by_missing_stress()
    test_stress_surface_is_null_when_too_few_stress_samples()
    test_loo_only_uses_peak_g_samples()
