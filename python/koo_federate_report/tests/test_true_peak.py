# 참피크 회귀 — 공통 격자(IDW) worst 가 실측 피크를 대체하지 않도록 못박는다
"""리샘플 후 worst 는 헤드라인이 될 수 없다.

실측 결함: 구면 3리비전(1144각도)을 915점 공통 Fibonacci 격자로 맞추면
격자 셀의 실측 비율이 **0%** 가 되고, 그 격자에서 뽑은 worst 는 IDW 이웃
가중평균이라 실제 피크보다 40~46% 낮았다. 보고서 헤드라인이 '한 번도 계산된
적 없는, 게다가 절반 가까이 낮은' 값이었다는 뜻이다.

여기서는 ① 격자 worst ≤ 참피크 (IDW 구조상 항상), ② 참피크는 실측 원본에서
나온다, ③ 감쇠와 실측률이 payload 에 드러난다 를 고정한다.
"""
from __future__ import annotations

from koo_federate_report.compare import build_comparison
from koo_federate_report.config import Options
from koo_federate_report.matching import build_matching
from koo_federate_report.resample import align

from .helpers import make_sphere_bundle

PARTS = {1: "CASE"}


def _spike_angles(n: int, spike_at: int, base: float, spike: float) -> list:
    """한 각도만 뾰족한 피크 — 보간이 깎는 것을 눈에 보이게 만든다."""
    out = []
    for i in range(n):
        roll = -80.0 + 160.0 * i / max(1, n - 1)
        pitch = (i * 137.5) % 360.0 - 180.0
        out.append((f"A{i:03d}", roll, pitch, "fibonacci",
                    spike if i == spike_at else base))
    return out


def _run(bundles):
    options = Options()
    match = build_matching(bundles, {}, options)
    aligned = align(bundles, 0, "sphere", options.resample)
    return build_comparison(bundles, 0, "sphere", match, aligned, options)


def test_grid_worst_never_exceeds_true_peak():
    """격자 worst 는 참피크를 넘을 수 없다 — 넘으면 없는 값을 만들어낸 것."""
    b = [
        make_sphere_bundle("RevA", _spike_angles(40, 7, 100.0, 900.0), PARTS),
        make_sphere_bundle("RevB", _spike_angles(37, 5, 90.0, 700.0), PARTS),
    ]
    kpi = _run(b)["kpi"]
    for gw, tp in zip(kpi["worst_per_rev"], kpi["true_peak_per_rev"]):
        assert tp is not None
        assert gw <= tp + 1e-9, f"격자 worst {gw} > 참피크 {tp}"


def test_true_peak_comes_from_raw_and_damping_is_reported():
    """참피크는 원본 최대값과 정확히 일치하고, 감쇠/실측률이 드러난다."""
    a = _spike_angles(40, 7, 100.0, 900.0)
    b = [
        make_sphere_bundle("RevA", a, PARTS),
        make_sphere_bundle("RevB", _spike_angles(37, 5, 90.0, 700.0), PARTS),
    ]
    cmp_ = _run(b)
    kpi = cmp_["kpi"]
    assert kpi["true_peak_per_rev"][0] == max(x[4] for x in a)
    assert kpi["true_peak_cell"][0].startswith("A007")
    # 격자가 달라 보간이 일어난 경우 감쇠는 음수(=깎임)로 보고된다
    damp = kpi["peak_damping_pct"]
    assert damp[0] is not None and damp[0] <= 0.0
    assert kpi["measured_pct"][0] is not None


def test_true_peak_delta_is_relative_to_baseline():
    """참피크 Δ% 는 baseline 대비이고 baseline 자신은 0."""
    b = [
        make_sphere_bundle("RevA", _spike_angles(40, 7, 100.0, 1000.0), PARTS),
        make_sphere_bundle("RevB", _spike_angles(40, 7, 100.0, 800.0), PARTS),
    ]
    kpi = _run(b)["kpi"]
    assert kpi["true_peak_delta_pct"][0] == 0.0
    assert abs(kpi["true_peak_delta_pct"][1] - (-20.0)) < 1e-9


def test_zero_measured_grid_is_warned():
    """실측률 0% (전부 보간) 이면 경고한다 — 커버리지 100%% 가 신뢰도가 아니다."""
    b = [
        make_sphere_bundle("RevA", _spike_angles(40, 7, 100.0, 900.0), PARTS),
        make_sphere_bundle("RevB", _spike_angles(37, 5, 90.0, 700.0), PARTS),
    ]
    options = Options()
    options.resample = "idw"
    match = build_matching(b, {}, options)
    aligned = align(b, 0, "sphere", options.resample)
    cmp_ = build_comparison(b, 0, "sphere", match, aligned, options)
    meas = [m for m in cmp_["kpi"]["measured_pct"] if m is not None]
    if meas and max(meas) <= 0.0:
        assert any(w.get("code") == "no_measured_cells" for w in cmp_["warnings"]), (
            "전부 보간인데 경고가 없다")


def test_nearest_keeps_measured_values():
    """nearest 는 실측값만 쓴다 — 격자 worst 가 참피크와 같아야 한다."""
    a = _spike_angles(40, 7, 100.0, 900.0)
    b = [
        make_sphere_bundle("RevA", a, PARTS),
        make_sphere_bundle("RevB", a, PARTS),   # 같은 격자 → 전부 exact
    ]
    options = Options()
    options.resample = "nearest"
    match = build_matching(b, {}, options)
    aligned = align(b, 0, "sphere", options.resample)
    kpi = build_comparison(b, 0, "sphere", match, aligned, options)["kpi"]
    assert kpi["worst_per_rev"][0] == kpi["true_peak_per_rev"][0]
    assert kpi["peak_damping_pct"][0] == 0.0
    assert kpi["measured_pct"][0] == 100.0
