# payload·사이드카 반올림이 작은 값을 0 으로 붕괴시키지 않는지 못박는 시험
"""자릿수 규칙 — 고정 소수점이 아니라 **유효숫자를 지킨다**.

배경(2026-09 전수조사). `_build_report_data` 는 런 수로 소수 자릿수를 정했다
(`s_prec = 1 if n_results > 500 else 2`, `e_prec = 4 if ... else 6`). 값의 크기가
아니라 캠페인 크기로 자릿수를 정하니, 1144런 캠페인(Test_006 — 실제로 존재한다)
에서 유효소성변형률 4.2e-5 가 0.0 이 되었다. 화면 안내문은 변형률 0 을
"완전 탄성" 으로 읽어 준다. report.json 사이드카도 같은 방식이라 두 리비전의
0.0863 / 0.0891 이 모두 0.09 로 나가 federate Δ 가 0.0% 가 되었다.

규칙. 반올림하더라도 **유효숫자 4자리는 남긴다**. 큰 값의 자릿수는 늘리지 않아
payload 크기는 그대로다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from koo_sphere_report.models import (  # noqa: E402
    AngleCondition, MotionData, PartInfo, PartResult, Report, SimulationResult,
    TimeSeriesData,
)
from koo_sphere_report.report.html_report import _build_report_data  # noqa: E402
from koo_sphere_report.report.json_report import save_json  # noqa: E402


def _ts(vals):
    ts = TimeSeriesData()
    ts.times = [i * 1e-4 for i in range(len(vals))]
    ts.max_values = list(vals)
    ts.min_values = [-v for v in vals]
    ts.avg_values = [v / 2.0 for v in vals]
    return ts


def _report(pr: PartResult, n_results: int) -> Report:
    rep = Report(project_name="T", total_runs=n_results, successful_runs=n_results)
    rep.part_info = {7: pr.part}
    for i in range(n_results):
        sr = SimulationResult(
            run_folder=f"Run_{i:04d}",
            angle=AngleCondition(angle_name=f"P{i:04d}", roll=0.0, pitch=0.0, yaw=0.0),
            num_states=3,
        )
        sr.parts = {7: pr}
        rep.results.append(sr)
    return rep


def _part(stress=None, strain=None):
    pr = PartResult(part=PartInfo(part_id=7, part_name="PKG\\A", group="PKG"))
    if stress is not None:
        pr.stress = _ts(stress)
    if strain is not None:
        pr.strain = _ts(strain)
    return pr


def test_small_plastic_strain_is_not_zero_at_1144_runs():
    """1144런 tier 에서 유효소성변형률 4.2e-5 가 0.0 이 되면 '완전 탄성' 으로 오독된다."""
    pr = _part(strain=[0.0, 4.2e-5])
    data = _build_report_data(_report(pr, 1144))
    pd = data["results"][0]["parts"]["7"]
    assert pd["peak_strain"] != 0.0, "소성변형률이 0 으로 붕괴했다"
    assert abs(pd["peak_strain"] - 4.2e-5) < 4.2e-9
    assert max(pd["strain_ts"]["max"]) != 0.0, "변형률 시계열도 0 으로 붕괴했다"


def test_gpa_scale_stress_keeps_distinct_values():
    """0.0863 과 0.0891 이 같은 수로 뭉치면 순위·Δ 가 통째로 사라진다."""
    a = _build_report_data(_report(_part(stress=[0.0, 0.0863]), 1144))
    b = _build_report_data(_report(_part(stress=[0.0, 0.0891]), 1144))
    va = a["results"][0]["parts"]["7"]["peak_stress"]
    vb = b["results"][0]["parts"]["7"]["peak_stress"]
    assert va != vb, f"{va} == {vb} — 서로 다른 응력이 한 값으로 뭉쳤다"
    assert abs(va - 0.0863) < 1e-6 and abs(vb - 0.0891) < 1e-6


def test_large_values_keep_current_precision():
    """큰 값의 자릿수는 늘리지 않는다 — payload 가 부풀면 안 된다."""
    pr = _part(stress=[0.0, 470.123456])
    pr.motion = MotionData()
    pr.motion.times = [0.0, 1e-4]
    pr.motion.avg_acc_mag = [0.0, 139029.0 * MotionData.G_FACTOR]
    pr.motion.avg_disp_mag = [0.0, 12.345678]
    pr.motion.max_disp_mag = [0.0, 12.345678]
    pr.motion.avg_vel_mag = [0.0, 5300.4321]
    data = _build_report_data(_report(pr, 1144))
    pd = data["results"][0]["parts"]["7"]
    assert pd["peak_stress"] == 470.1          # 소수 1자리 tier 그대로
    assert pd["peak_g"] == 139029.0            # 큰 값은 절대 깎이지 않는다
    assert pd["peak_disp"] == 12.35            # 유효숫자 4자리가 바닥이다


def test_sidecar_keeps_small_compressive_and_disp():
    """report.json — σ3 -0.0042 가 -0.0 이 되면 federate 가 그 값을 실측으로 읽는다."""
    pr = _part(stress=[0.0, 0.0863])
    pr.principal_min = _ts([0.0, 0.0])
    pr.principal_min.min_values = [0.0, -0.0042]
    pr.principal_min.true_min = -0.0042
    pr.motion = MotionData()
    pr.motion.times = [0.0, 1e-4]
    pr.motion.avg_acc_mag = [0.0, 10.0]
    pr.motion.avg_disp_mag = [0.0, 0.0004]
    pr.motion.max_disp_mag = [0.0, 0.0004]
    pr.motion.avg_vel_mag = [0.0, 1.0]

    out = Path(__import__("tempfile").mkdtemp()) / "report.json"
    save_json(_report(pr, 1144), str(out))
    d = json.loads(out.read_text(encoding="utf-8"))
    pd = d["results_summary"][0]["parts"]["7"]
    assert pd["min_principal_stress"] == -0.0042, pd["min_principal_stress"]
    assert pd["peak_stress"] == 0.0863, pd["peak_stress"]
    assert pd["peak_disp"] == 0.0004, pd["peak_disp"]


def test_js_tolerance_does_not_drop_measured_zero():
    """공차 DOE 가 0 을 '값 없음' 으로 버리면 정각도(_NOM) 가 통째로 사라진다."""
    from koo_sphere_report.report.html_report import _JS
    assert "if (v == null || !isFinite(v) || v === 0) continue;" not in _JS, (
        "반올림으로 0 이 된 값을 미계측으로 버리고 있다")


def test_js_formats_small_values_with_significant_digits():
    """화면 표기도 0.0863 MPa 를 '0.1 MPa' 로 만들면 안 된다."""
    from koo_sphere_report.report.html_report import _JS
    assert "toPrecision" in _JS, "작은 값용 유효숫자 표기가 없다"


def test_all():
    """pytest 진입점."""
    test_small_plastic_strain_is_not_zero_at_1144_runs()
    test_gpa_scale_stress_keeps_distinct_values()
    test_large_values_keep_current_precision()
    test_sidecar_keeps_small_compressive_and_disp()
    test_js_tolerance_does_not_drop_measured_zero()
    test_js_formats_small_values_with_significant_digits()
