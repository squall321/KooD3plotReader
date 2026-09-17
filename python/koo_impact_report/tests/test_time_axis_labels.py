# 시각 표기가 단위계를 지키는지, 접촉 타임라인 축이 실제 기록 길이를 따르는지 보는 시험
"""시간 표기 규칙.

솔버 시간 단위가 초(s)일 때만 1000배 해 ms 라벨을 붙인다. 종전 코드는
1000배 해 놓고 `_u('time')` = 's' 를 그대로 붙여, 실측 F5_DOE_014 의
t₁ = 5e-06 s 가 't₁ CONTACT 0.01 s' 로 2000배 과대 표기됐고 1e-05 s 인
F5_DOE_013 과 같은 '0.01 s' 로 뭉개졌다.

접촉 타임라인은 축을 0~1 ms 로 못 박아 두고 있었다. tFinal 2 ms 덱의
1.5 ms 접촉이 '0.8 ms' 칸에 찍힌다. 칸도 점 샘플링이라 record/20 보다 짧은
접촉은 통째로 사라진다.

t₁ 표시선은 전 위치가 같은 값 하나를 썼다 — 실측에서 미접촉 런의 노이즈
1e-06 이 전 위치 차트에 그어졌다.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from koo_impact_report.models import (  # noqa: E402
    FaceOrientation, ImpactPosition, ImpactReport, ImpactorSpec,
    ImpactorTrajectory, PairResult, PartInfo,
)
from koo_impact_report.report.html_report import generate_html  # noqa: E402
from koo_impact_report.report.payload import _build_payload  # noqa: E402


def _traj(times, tfc, behavior):
    tr = ImpactorTrajectory()
    tr.times = list(times)
    tr.pos_x = [0.0] * len(times)
    tr.pos_y = [0.0] * len(times)
    tr.pos_z = [float(-i) for i in range(len(times))]
    tr.vel_x = [0.0] * len(times)
    tr.vel_y = [0.0] * len(times)
    tr.vel_z = [-4905.0] * len(times)
    tr.ke = [1.0] * len(times)
    tr.contact_engaged = [False] * len(times)
    tr.t_first_contact = tfc
    tr.behavior_class = behavior
    return tr


def _report():
    times = [i * 1.0e-05 for i in range(20)]
    face = FaceOrientation("F5", "Top", 90.0, 0.0, 0.0)
    positions, results, trajs = [], [], {}
    spec = [("F5_DOE_001", 1e-06, "no-contact"),
            ("F5_DOE_013", 1e-05, "bounce"),
            ("F5_DOE_014", 5e-06, "bounce")]
    for i, (pid, tfc, beh) in enumerate(spec):
        pos = ImpactPosition(pos_id=pid, face="F5", x=float(i * 10), y=0.0)
        positions.append(pos)
        trajs[pid] = _traj(times, tfc, beh)
        results.append(PairResult(face="F5", position=pos, part_id=7,
                                  peak_g=1000.0 + i, peak_stress=100.0,
                                  peak_strain=1e-5, peak_disp=0.1,
                                  peak_vel=1.0,
                                  impactor_trajectory=trajs[pid]))
    return ImpactReport(
        project_name="unit",
        impactor=ImpactorSpec(type="Sphere", radius=8.0, density=7.85e-09,
                              youngs_modulus=210000.0, part_id=99),
        faces=[face],
        positions_by_face={"F5": positions},
        parts=[PartInfo(part_id=7, part_name="PKG 7")],
        results=results,
        impactor_trajectories=trajs,
        sim_params={"unit_labels": {"time": "s", "acc": "mm/s²",
                                    "stress": "MPa", "disp": "mm"}},
    )


def test_t_first_contact_is_per_position():
    """위치마다 t₁ 이 따로 나가고, 미접촉 런은 빠진다."""
    payload = _build_payload(_report())
    by_pos = payload["part_motion"]["t_first_contact_by_pos"]
    assert by_pos == {"F5_DOE_013": 1e-05, "F5_DOE_014": 5e-06}, by_pos
    # 위치가 여럿이면 전역 하나를 쓰지 않는다 (아무 값이나 전 차트에 긋지 않게).
    assert payload["part_motion"]["t_first_contact"] is None


def test_time_label_helper_exists_and_is_used():
    """1000배 + 솔버 단위 라벨 조합이 보고서에서 사라졌는지 본다."""
    html = generate_html(_report())
    assert "function _tScale()" in html
    assert "function tfmt(" in html
    # 종전 표기(1000배 하고 _u('time') 라벨)가 남아 있으면 안 된다.
    assert "(pm.t_first_contact * 1000).toFixed(2)" not in html
    assert "(tr.t_first_contact * 1000).toFixed(2)" not in html
    assert "(tv * 1000).toFixed(2)" not in html


def test_contact_timeline_axis_is_data_driven():
    """접촉 타임라인이 0~1 ms 하드코딩을 버리고 tr.t 를 쓴다.

    이 시험은 소스 문자열 회귀만 막는다. 실제 동작(구간 OR 로 짧은 펄스를
    잡는다, 2 ms 덱의 1.5 ms 접촉이 맞는 칸에 온다)은
    tests/test_contact_timeline_cells.py 가 node 로 실행해 값으로 단언한다.
    """
    html = generate_html(_report())
    assert "(i / 20).toFixed(1)" not in html
    assert "(i / 20).toFixed(2) + ' ms'" not in html
    assert "tEnd * (i / 20) * tS.k" in html
    # 칸 판정이 점 샘플링이 아니라 구간 OR 이어야 한다.
    assert "const idx = T > 0 ? Math.floor(i * (T - 1) / 20) : -1;" not in html


def test_all():
    """pytest 진입점 — 위 시험들을 한 번에 돌린다."""
    test_t_first_contact_is_per_position()
    test_time_label_helper_exists_and_is_used()
    test_contact_timeline_axis_is_data_driven()
