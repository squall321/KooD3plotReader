# 다운샘플 전 참극값(σ3 최소·ε3 최소·최대 속도)이 살아남는지 못박는 시험
"""로더가 배열을 줄이기 전에 **양 끝**을 다 기록하는지 확인한다.

배경. `_load_stress_strain_csv` 는 오래도록 최댓값만 `true_peak` 로 따로 챙기고
최솟값은 챙기지 않았다. σ3(최소 주응력)·ε3(최소 주변형률)은 압축측이라 **최솟값이
곧 피크**인데, `min_principal` 이 다운샘플된 `min_values` 에서 min() 을 뽑아
992 상태 덱의 -412 MPa 압축 스파이크가 -30 MPa 로 보고되었다.

속도도 같다. `peak_vel` 은 다운샘플된 `avg_vel_mag` 에서 max(abs()) 를 뽑는다.
실캠페인(Test_006, 992상태→42행)에서 최대 25% 낮게 나왔다.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from koo_sphere_report.loader import (  # noqa: E402
    _load_motion_csv, _load_stress_strain_csv,
)
from koo_sphere_report.models import PartInfo, PartResult  # noqa: E402


def _write_principal_csv(path: Path, mins: list[float]) -> None:
    """σ3 CSV 를 쓴다 (unified_analyzer exportResults 와 같은 머리말)."""
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Time", "Max_min_principal_stress", "Min_min_principal_stress",
                    "Avg_min_principal_stress", "Max_Element_ID", "Min_Element_ID"])
        for i, v in enumerate(mins):
            w.writerow([f"{i * 1e-6:.6f}", 0.0, v, v / 2.0, 34000 + i, 12000 + i])


def _write_motion_csv(path: Path, vels: list[float]) -> None:
    cols = ["Time", "Avg_Disp_X", "Avg_Disp_Y", "Avg_Disp_Z", "Avg_Disp_Mag",
            "Avg_Vel_X", "Avg_Vel_Y", "Avg_Vel_Z", "Avg_Vel_Mag",
            "Avg_Acc_X", "Avg_Acc_Y", "Avg_Acc_Z", "Avg_Acc_Mag",
            "Max_Disp_Mag", "Max_Disp_Node_ID"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for i, v in enumerate(vels):
            w.writerow([f"{i * 1e-6:.6f}", 0, 0, 0, 1.0,
                        0, 0, v, v,
                        0, 0, 0, 100.0,
                        1.0, 5])


def test_min_principal_keeps_compressive_spike(tmp_path: Path):
    """992 상태 중 한 점에만 있는 -412 MPa 압축 스파이크가 살아야 한다.

    시나리오(전수조사 확정): 상태 437 에만 -412, 나머지는 -30. 어떤 tier
    (40/120/400점)로 줄여도 992//400=2 라 홀수 인덱스 437 은 stride 에 안 걸린다.
    """
    mins = [-30.0] * 992
    mins[437] = -412.0
    csv_path = tmp_path / "part_7_min_principal_stress.csv"
    _write_principal_csv(csv_path, mins)

    for target in (40, 120, 400):
        ts = _load_stress_strain_csv(csv_path, target)
        pr = PartResult(part=PartInfo(part_id=7, part_name="A\\B", group="A"))
        pr.principal_min = ts
        assert pr.min_principal == -412.0, (
            f"target={target}: σ3 최소가 {pr.min_principal} — 압축 스파이크를 잃었다")
        assert ts.true_min_time == 437 * 1e-6, "참최소 시각이 어긋난다"


def test_min_principal_strain_keeps_spike(tmp_path: Path):
    """ε3 도 같은 규칙 — 압축측은 최솟값이 피크다."""
    mins = [-1e-4] * 500
    mins[251] = -3.7e-3
    csv_path = tmp_path / "part_7_min_principal_strain.csv"
    _write_principal_csv(csv_path, mins)
    pr = PartResult(part=PartInfo(part_id=7, part_name="A\\B", group="A"))
    pr.principal_strain_min = _load_stress_strain_csv(csv_path, 40)
    assert pr.min_principal_strain == -3.7e-3


def test_true_peak_vel_survives_downsample(tmp_path: Path):
    """최대 속도도 다운샘플 전 값이 남아야 한다."""
    vels = [100.0] * 992
    vels[437] = 5300.0
    csv_path = tmp_path / "part_7_motion.csv"
    _write_motion_csv(csv_path, vels)
    md = _load_motion_csv(csv_path, 40)
    assert md.true_peak_vel == 5300.0, f"참최대속도가 {md.true_peak_vel}"
    assert md.peak_vel == 5300.0


def test_no_downsample_still_reports_true_extremes(tmp_path: Path):
    """줄이지 않은 경우에도 값은 같아야 한다 (회귀 방지)."""
    mins = [-1.0, -5.0, -2.0]
    csv_path = tmp_path / "part_1_min_principal_stress.csv"
    _write_principal_csv(csv_path, mins)
    ts = _load_stress_strain_csv(csv_path, None)
    assert ts.true_min == -5.0
    assert ts.min_values == mins


def test_all(tmp_path: Path):
    """pytest 진입점 — 개별 시험이 이미 수집되지만 관례상 함께 둔다."""
    def _d(name: str) -> Path:
        p = tmp_path / name
        p.mkdir()
        return p
    test_min_principal_keeps_compressive_spike(_d("a"))
    test_min_principal_strain_keeps_spike(_d("b"))
    test_true_peak_vel_survives_downsample(_d("c"))
    test_no_downsample_still_reports_true_extremes(_d("d"))
