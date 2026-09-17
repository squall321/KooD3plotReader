# 응력파 겉보기 속도의 거리 r 정의가 화면에 실려 나가는지 보는 시험
"""`r = hypot(px-cx, py-cy)` 는 XY 평면 거리다.

코드에 적힌 근거("임팩터 궤적의 pos_z 도 이제 변위라 t=0 이 0 이다")는
이 함수가 실제로 도달하는 경우에 대해 사실이 아니다. centroid0 은 **옛
형식(절대 좌표) motion CSV** 에서만 채워지고, traj.pos_z 는 같은 CSV 의
Avg_Disp_Z 를 읽는다 — centroid0 이 있는 바로 그 경우에 pos_z 도 절대
좌표다.

그렇다고 옛 3D 식으로 되돌리면 더 나빠진다. 실측(Test_Impact_A
Run_20260603_075531, 타점 (20,0), 임팩터 t=0 z=16.9497, 반지름 8 mm,
offset 0.01)에서 접촉면 z 는 약 8.94 이고, 임팩터 **중심** z 를 쓴 옛
식은 근거리 part 16 의 r 을 참값보다 28% 부풀렸다. 지금 XY 식은 7%
모자란다 — 옛 식보다 낫다.

그러므로 XY 정의를 유지하되, 그 정의가 화면에 보여야 한다.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from koo_impact_report.models import (  # noqa: E402
    ImpactPosition, ImpactorTrajectory, ImpactReport, PartInfo, PartMotion,
)
from koo_impact_report.report.payload.physics import (  # noqa: E402
    _build_stress_wave_velocity_payload,
)

# 실측 Run_20260603_075531 에서 그대로 가져온 값.
IMPACT_XY = (20.0, 0.0)
IMPACTOR_Z0 = 16.949668
PART16_C0 = (14.0, 13.5, 2.9)
DT = 2.0e-6   # t_peak_g - t_first_contact


def _report():
    pos = ImpactPosition(pos_id="P1", face="F1", x=IMPACT_XY[0], y=IMPACT_XY[1])
    traj = ImpactorTrajectory()
    traj.times = [0.0, 1.0e-6]
    traj.pos_z = [IMPACTOR_Z0, IMPACTOR_Z0 - 0.1]   # 옛 형식 = 절대 좌표
    traj.t_first_contact = 1.0e-6
    traj.behavior_class = "bounce"
    pm = PartMotion(part_id=16)
    pm.centroid0 = PART16_C0                        # 옛 형식에서만 채워진다
    pm.t_peak_g = traj.t_first_contact + DT
    return ImpactReport(
        parts=[PartInfo(part_id=16, part_name="PART_16")],
        positions_by_face={"F1": [pos]},
        impactor_trajectories={"P1": traj},
        part_motions={("P1", 16): pm},
    )


def test_r_is_the_xy_plane_distance():
    """v_app = r_xy / Δt — 문서화된 정의 그대로여야 한다."""
    out = _build_stress_wave_velocity_payload(_report())
    row = [r for r in out["per_part"] if r["part_id"] == 16][0]
    r_xy = math.hypot(IMPACT_XY[0] - PART16_C0[0], IMPACT_XY[1] - PART16_C0[1])
    want = (r_xy / DT) / 1000.0
    assert abs(row["median_v_app"] - want) / want < 1e-3, (row, want)


def test_payload_states_the_distance_definition():
    """정의가 payload 에 실려야 화면이 'r 이 무엇인지' 를 말할 수 있다."""
    out = _build_stress_wave_velocity_payload(_report())
    d = out["summary"].get("r_definition")
    assert d, out["summary"]
    assert "XY" in d, d


def test_old_3d_formula_would_inflate_near_part():
    """옛 3D 식(임팩터 중심 z)이 왜 더 나쁜지 수치로 못박는다."""
    r_xy = math.hypot(IMPACT_XY[0] - PART16_C0[0], IMPACT_XY[1] - PART16_C0[1])
    r_old = math.sqrt(r_xy ** 2 + (IMPACTOR_Z0 - PART16_C0[2]) ** 2)
    z_contact = IMPACTOR_Z0 - 8.0 - 0.01          # 구 반지름 8 mm, offset 0.01
    r_true = math.sqrt(r_xy ** 2 + (z_contact - PART16_C0[2]) ** 2)
    assert r_old / r_true > 1.25, (r_old, r_true)
    assert 0.90 < r_xy / r_true < 1.0, (r_xy, r_true)


def test_all():
    """진입점 — 이 파일의 시험을 모두 돌린다."""
    test_r_is_the_xy_plane_distance()
    test_payload_states_the_distance_definition()
    test_old_3d_formula_would_inflate_near_part()
