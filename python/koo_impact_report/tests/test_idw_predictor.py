# IDW 위험면 회귀 — 측정 좌표를 반올림한 뒤 보간하면 SI 덱에서 면이 무너진다
"""_build_idw_predictor_payload 의 좌표 정밀도 규칙.

DOE 좌표는 덱 단위 그대로다. mm 덱이면 -40..40, SI 덱이면 -0.04..0.04.
소수 1자리로 반올림하면 SI 덱의 모든 낙하점이 한 점(0.0, 0.0)으로 뭉쳐
보간면이 상수가 되고 LOO 오차가 뜻을 잃는다. 반올림은 **표시용**이지
계산용이 아니다.
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
    def __init__(self, positions, bbox):
        self.sim_params = {"grid": {"bbox": list(bbox)}}
        self.positions_by_face = {"F1": positions}
        self.results = [_Res(p, g, g * 10.0) for p, g in positions_with_g(positions)]


def positions_with_g(positions):
    """낙하점마다 x 에 비례하는 peak_g — 보간면이 x 방향으로 기울어야 한다."""
    return [(p, 100.0 + 1000.0 * (p.x - positions[0].x) / (positions[-1].x - positions[0].x))
            for p in positions]


def _square(scale):
    """한 변 2*scale 인 정사각형 네 꼭짓점 (SI 면 scale=0.04 m, mm 면 40)."""
    return [
        _Pos("P1", -scale, -scale),
        _Pos("P2", -scale, scale),
        _Pos("P3", scale, -scale),
        _Pos("P4", scale, scale),
    ]


def test_si_metre_deck_keeps_distinct_sample_coordinates():
    """SI 덱(±0.04 m)에서 낙하점이 한 점으로 뭉치면 안 된다."""
    rep = _Rep(_square(0.04), [-0.05, -0.05, 0.05, 0.05])
    out = _build_idw_predictor_payload(rep)
    assert out is not None
    xs = {m["x"] for m in out["measured_points"]}
    ys = {m["y"] for m in out["measured_points"]}
    assert len(xs) == 2 and len(ys) == 2, out["measured_points"]


def test_si_metre_deck_bbox_survives_rounding():
    """bbox 를 1자리로 반올림하면 ±0.05 m 가 ±0.1 m 로 두 배가 된다."""
    rep = _Rep(_square(0.04), [-0.05, -0.05, 0.05, 0.05])
    out = _build_idw_predictor_payload(rep)
    got = out["grid_fine"]["bbox"]
    for g, want in zip(got, [-0.05, -0.05, 0.05, 0.05]):
        assert abs(g - want) <= abs(want) * 1e-3, got


def test_si_metre_deck_surface_keeps_x_gradient():
    """좌표가 뭉개지면 IDW 가 전 격자에 같은 평균값을 깔아버린다."""
    rep = _Rep(_square(0.04), [-0.05, -0.05, 0.05, 0.05])
    out = _build_idw_predictor_payload(rep)
    g = out["grid_fine"]["peak_g"]
    nx, ny = out["grid_fine"]["nx_fine"], out["grid_fine"]["ny_fine"]
    row = (ny // 2) * nx
    assert g[row + nx - 1] - g[row] > 1.0, (g[row], g[row + nx - 1])


def test_mm_deck_result_matches_metre_deck_after_scaling():
    """같은 배치를 mm 로 쓰든 m 로 쓰든 보간면(무차원 형상)은 같아야 한다."""
    out_mm = _build_idw_predictor_payload(_Rep(_square(40.0), [-50.0, -50.0, 50.0, 50.0]))
    out_si = _build_idw_predictor_payload(_Rep(_square(0.04), [-0.05, -0.05, 0.05, 0.05]))
    a = out_mm["grid_fine"]["peak_g"]
    b = out_si["grid_fine"]["peak_g"]
    assert len(a) == len(b)
    worst = max(abs(x - y) for x, y in zip(a, b))
    assert worst < 1e-3, worst


def test_loo_validation_uses_unrounded_coordinates():
    """LOO 도 같은 좌표를 써야 한다 — SI 덱에서 오차가 터지면 안 된다."""
    out = _build_idw_predictor_payload(_Rep(_square(0.04), [-0.05, -0.05, 0.05, 0.05]))
    loo = out["loo_validation"]
    assert loo is not None
    ref = _build_idw_predictor_payload(_Rep(_square(40.0), [-50.0, -50.0, 50.0, 50.0]))
    assert abs(loo["rmse_peak_g"] - ref["loo_validation"]["rmse_peak_g"]) < 1e-3


def test_all():
    """진입점 — 이 파일의 시험을 모두 돌린다."""
    test_si_metre_deck_keeps_distinct_sample_coordinates()
    test_si_metre_deck_bbox_survives_rounding()
    test_si_metre_deck_surface_keeps_x_gradient()
    test_mm_deck_result_matches_metre_deck_after_scaling()
    test_loo_validation_uses_unrounded_coordinates()
