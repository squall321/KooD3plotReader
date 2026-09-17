# rcforc 접촉 판정이 노이즈 인터페이스를 '접촉' 으로 세우지 않는지 보는 시험
"""`_compute_contact_mask` 규칙.

인터페이스마다 자기 자신의 피크로만 10% 문턱을 잡으면, 통째로 0.014 N
노이즈뿐인 인터페이스도 자기 피크의 10% 는 넘는다. 미접촉 런에서
`t_first_contact` 가 잡히고 max_pen 이 자유낙하 거리로 둔갑한다.

실측(Test_Impact_A F5_DOE_001, 자유비행)의 힘 크기를 그대로 숫자로 쓴다 —
그 런에서 가장 센 인터페이스가 0.61 N, 노이즈 인터페이스가 0.0139 N 이고,
실제 접촉 런은 34~760 N 이다. 임팩터(8 mm 강구 1.68e-5 tonne, 4905 mm/s,
기록 1 ms)를 기록 시간 안에 세우는 데 드는 평균 힘은 82 N 이므로 그 1% =
0.82 N 이 물리적 바닥이다.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from koo_impact_report.loader import _compute_contact_mask  # noqa: E402

#: 실측 기반 물리 바닥 (N) — 임팩터 운동량 규모의 1%.
FLOOR = 0.82


class _RC:
    """rcforc 인터페이스 한 개 (lasso binout 과 같은 필드 이름)."""

    def __init__(self, t, fz, side=-1):
        self.t = list(t)
        self.fx = [0.0] * len(t)
        self.fy = [0.0] * len(t)
        self.fz = list(fz)
        self.side = side


def _times(n=20, dt=5e-6):
    return [i * dt for i in range(n)]


def test_noise_only_interface_is_not_contact():
    """전 구간 0.0139 N 노이즈뿐인 인터페이스는 접촉이 아니다."""
    t = _times()
    noise = _RC(t, [0.0002] * 2 + [0.0139] + [0.0002] * (len(t) - 3))
    mask = _compute_contact_mask([noise], t, force_floor=FLOOR)
    assert not any(mask), "0.0139 N 노이즈가 접촉으로 잡혔다"


def test_free_flight_run_has_no_contact_at_all():
    """미접촉 런(최대 0.61 N)은 마스크가 전부 False 여야 한다."""
    t = _times()
    strong = _RC(t, [0.0] + [0.61 * ((i % 3) / 2.0) for i in range(1, len(t))])
    noise = _RC(t, [0.0002] * 2 + [0.0139] + [0.0002] * (len(t) - 3))
    weak = _RC(t, [0.0001 * (i % 5) for i in range(len(t))])
    mask = _compute_contact_mask([strong, noise, weak], t, force_floor=FLOOR)
    assert not any(mask), f"미접촉 런에서 접촉 {sum(mask)} 스텝이 잡혔다"


def test_real_contact_still_detected():
    """진짜 접촉 펄스(34~760 N)는 그대로 잡혀야 한다 — 회귀 방지."""
    t = _times()
    fz = [0.0] * 4 + [120.0, 760.0, 340.0] + [0.0] * (len(t) - 7)
    mask = _compute_contact_mask([_RC(t, fz)], t, force_floor=FLOOR)
    assert mask[5] is True
    assert mask[4] is True
    assert not mask[0]


def test_weak_but_real_interface_above_floor_is_kept():
    """바닥(0.82 N)을 넘는 34 N 내부 접촉은 센 인터페이스가 있어도 살아야 한다."""
    t = _times()
    strong = _RC(t, [0.0] * 4 + [760.0] + [0.0] * (len(t) - 5))
    inner = _RC(t, [0.0] * 8 + [34.0] + [0.0] * (len(t) - 9))
    mask = _compute_contact_mask([inner], t, force_floor=FLOOR)
    assert mask[8] is True
    both = _compute_contact_mask([strong, inner], t, force_floor=FLOOR)
    assert both[8] is True, "센 인터페이스가 있다고 약한 실접촉이 지워지면 안 된다"


def test_no_floor_keeps_legacy_behaviour():
    """물리 바닥을 못 구한 경우(force_floor=None)는 종전 판정 그대로다."""
    t = _times()
    noise = _RC(t, [0.0002] * 2 + [0.0139] + [0.0002] * (len(t) - 3))
    assert any(_compute_contact_mask([noise], t, force_floor=None))


class _Traj:
    def __init__(self, behavior, tfc):
        self.behavior_class = behavior
        self.t_first_contact = tfc


class _PM:
    def __init__(self, pid, t_peak_g):
        self.part_id = pid
        self.part_name = f"part_{pid}"
        self.t_peak_g = t_peak_g


class _Part:
    def __init__(self, pid):
        self.part_id = pid
        self.part_name = f"part_{pid}"


class _Rep:
    def __init__(self, trajs, motions, parts):
        self.impactor_trajectories = trajs
        self.part_motions = motions
        self.parts = parts


def test_toa_excludes_no_contact_runs():
    """미접촉 런은 TOA 통계에서 빠지고, 몇 개 뺐는지 산출물에 남는다."""
    from koo_impact_report.report.payload.doe import _build_toa_payload

    trajs = {
        "DOE_001": _Traj("no-contact", 1e-06),   # 노이즈에서 나온 t₁
        "DOE_013": _Traj("bounce", 1e-05),
        "DOE_014": _Traj("bounce", 5e-06),
    }
    motions = {(p, 8): _PM(8, 3e-05) for p in trajs}
    out = _build_toa_payload(_Rep(trajs, motions, [_Part(8)]))
    assert "DOE_001" not in out["toa_per_position"]
    assert out["mean_arrival_per_part"]["8"]["n_positions"] == 2
    assert out["n_excluded_no_contact"] == 1


def test_all():
    """pytest 진입점 — 위 시험들을 한 번에 돌린다."""
    test_noise_only_interface_is_not_contact()
    test_free_flight_run_has_no_contact_at_all()
    test_real_contact_still_detected()
    test_weak_but_real_interface_above_floor_is_kept()
    test_no_floor_keeps_legacy_behaviour()
    test_toa_excludes_no_contact_runs()
