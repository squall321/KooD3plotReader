# motion CSV 의 Avg_Disp_* 를 파트 중심 좌표로 읽던 소비자들을 잡는 시험
"""motion CSV 의 Avg_Disp_*/Max_Disp_Mag 는 **변위** 다, 좌표가 아니다.

MotionAnalyzer 가 초기 좌표를 빼도록 바뀐 뒤(a9895c5) t=0 행은 전부 0 이다.
옛 산출물은 그 자리에 절대 좌표가 들어 있었다 — 실측
Test_Impact_A/Run_20260603_071717_fab346 의 part 24 t=0 행은
(20.016, -39.992, 16.950), part 15 는 (35.0, 15.0, 2.4) 이고 Max_Disp_Mag 는
각각 55.84 / 67.55 였다(중심에서 가장 먼 절점까지의 거리).

impact 소비자들은 아직 옛 뜻으로 읽는다.
  - s8 응력파 속도: r = |(충격점) - (파트 중심)| 이 전 파트에서 원점까지 거리로
    같아져 v_app = r/Δt 가 파트 형상과 무관해진다. 중심 타격(0,0)이면 r=0 이라
    전 표본이 버려지고 패널이 빈다.
  - 임팩터 반경: 첫 0 아닌 Max_Disp_Mag(= 그냥 그때의 변위)를 경계 반경으로 썼다.
  - 장치 XY 범위: 전 파트 중심이 (0,0) 이라 폭·높이 0 인 상자가 된다.

없는 값을 지어내지 않는다 — 중심 좌표가 없으면 사유를 남기고 비운다.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from koo_impact_report.models import (  # noqa: E402
    FaceOrientation, ImpactPosition, ImpactReport, ImpactorSpec,
    ImpactorTrajectory, PairResult, PartInfo, PartMotion,
)
from koo_impact_report.report.payload.core import _build_device_geometry  # noqa: E402
from koo_impact_report.report.payload.physics import (  # noqa: E402
    _build_stress_wave_velocity_payload,
)

#: 실측 part 15 / part 24 의 t=0 중심 (옛 CSV 가 담고 있던 값).
CENTROID_A = (35.0, 15.0, 2.4)
CENTROID_B = (-30.0, 10.0, 0.5)


def _pm(part_id, centroid, t_peak_g, *, with_centroid0):
    """현재 작성기 기준 motion — disp_* 는 변위라 t=0 이 0 이다."""
    m = PartMotion(part_id=part_id, part_name=f"PKG {part_id}")
    m.times = [0.0, 1e-05, 2e-05, 3e-05]
    m.disp_x = [0.0, 0.01, 0.02, 0.03]
    m.disp_y = [0.0, 0.01, 0.02, 0.03]
    m.disp_z = [0.0, -0.01, -0.02, -0.03]
    m.disp_mag = [0.0, 0.017, 0.034, 0.051]
    m.acc_mag = [0.0, 1.0, 2.0, 1.5]
    m.t_peak_g = t_peak_g
    if with_centroid0:
        m.centroid0 = tuple(centroid)
    return m


def _report(with_centroid0: bool):
    pos = ImpactPosition(pos_id="F5_DOE_001", face="F5", x=20.0, y=-15.0)
    traj = ImpactorTrajectory()
    traj.times = [0.0, 1e-05, 2e-05]
    traj.pos_x = [0.0, 0.0, 0.0]
    traj.pos_y = [0.0, 0.0, 0.0]
    traj.pos_z = [0.0, -0.05, -0.1]
    traj.vel_z = [-4905.0] * 3
    traj.vel_x = [0.0] * 3
    traj.vel_y = [0.0] * 3
    traj.ke = [1.0] * 3
    traj.contact_engaged = [False, True, True]
    traj.t_first_contact = 1e-05
    traj.behavior_class = "bounce"
    motions = {
        ("F5_DOE_001", 15): _pm(15, CENTROID_A, 1.6e-05, with_centroid0=with_centroid0),
        ("F5_DOE_001", 24): _pm(24, CENTROID_B, 2.4e-05, with_centroid0=with_centroid0),
    }
    return ImpactReport(
        project_name="unit",
        impactor=ImpactorSpec(type="Sphere", radius=8.0, density=7.85e-09,
                              youngs_modulus=210000.0, part_id=99),
        faces=[FaceOrientation("F5", "Top", 90.0, 0.0, 0.0)],
        positions_by_face={"F5": [pos]},
        parts=[PartInfo(part_id=15, part_name="PKG 15"),
               PartInfo(part_id=24, part_name="PKG 24")],
        results=[PairResult(face="F5", position=pos, part_id=15, peak_g=1000.0),
                 PairResult(face="F5", position=pos, part_id=24, peak_g=900.0)],
        impactor_trajectories={"F5_DOE_001": traj},
        part_motions=motions,
        sim_params={"unit_labels": {"time": "s"}},
    )


def test_wave_speed_needs_real_centroids():
    """중심 좌표가 없으면 겉보기 속도를 지어내지 않는다."""
    out = _build_stress_wave_velocity_payload(_report(with_centroid0=False))
    assert out["per_part"] == [], out["per_part"]
    assert "_placeholder" in out
    assert "중심" in out["_placeholder"], out["_placeholder"]


def test_wave_speed_uses_centroid_when_available():
    """중심 좌표가 실리면 파트마다 다른 r 로 제대로 계산한다."""
    import math

    out = _build_stress_wave_velocity_payload(_report(with_centroid0=True))
    by_pid = {d["part_id"]: d for d in out["per_part"]}
    assert set(by_pid) == {15, 24}, out["per_part"]
    # r 은 XY 평면 거리다 — 임팩터 z 는 이제 변위라 중심과 같은 좌표계가
    # 아니므로 섞지 않는다. Δt 는 t_peak_g - t_first_contact.
    r15 = math.hypot(20.0 - CENTROID_A[0], -15.0 - CENTROID_A[1])
    assert abs(by_pid[15]["median_v_app"] - (r15 / 6e-06) / 1000.0) < 1.0
    assert by_pid[15]["median_v_app"] != by_pid[24]["median_v_app"], \
        "파트가 달라도 같은 속도가 나오면 r 이 형상과 무관하다는 뜻이다"


def test_device_bbox_is_not_a_zero_box():
    """전 파트 변위가 0 인 t=0 으로 장치 범위를 만들지 않는다."""
    geo = _build_device_geometry(_report(with_centroid0=False))
    assert geo["source"] == "grid_fallback", geo
    assert geo["bbox"] is None


def test_impactor_radius_is_not_taken_from_max_disp(tmp_path: Path):
    """Max_Disp_Mag 는 변위다 — 경계 반경으로 쓰지 않는다."""
    from koo_impact_report import loader

    work = tmp_path / "report"
    (work / "motion").mkdir(parents=True)
    (work / "motion" / "part_24_motion.csv").write_text(
        "Time,Avg_Disp_X,Avg_Disp_Y,Avg_Disp_Z,Avg_Disp_Mag,"
        "Avg_Vel_X,Avg_Vel_Y,Avg_Vel_Z,Avg_Vel_Mag,"
        "Avg_Acc_X,Avg_Acc_Y,Avg_Acc_Z,Avg_Acc_Mag,"
        "Max_Disp_Mag,Max_Disp_Node_ID\n"
        "0.000000,0,0,0,0,0,0,0,0,0,0,0,0,0.000000,1\n"
        "0.000100,0,0,-0.5,0.5,0,0,0,0,0,0,0,0,0.511000,1\n",
        encoding="utf-8")
    assert loader._bbox_from_d3plot_part(tmp_path / "d3plot", 24, work) is None


def test_all(tmp_path: Path):
    """pytest 진입점 — 위 시험들을 한 번에 돌린다."""
    test_wave_speed_needs_real_centroids()
    test_wave_speed_uses_centroid_when_available()
    test_device_bbox_is_not_a_zero_box()
    test_impactor_radius_is_not_taken_from_max_disp(tmp_path)
