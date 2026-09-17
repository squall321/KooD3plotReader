# 짧은 접촉 펄스가 다운샘플에 걸려 't=0 부터 접촉' 으로 둔갑하지 않는지 검증하는 시험
"""`koo_deep_report.core.energy_flow_builder` 의 engage 시각·자릿수 시험.

force_mag_ts 는 솎아낸 ref 축에서 점 샘플링된다. 샘플 사이에만 존재하는
짧은 펄스는 그 배열에서 통째로 사라지고, first_engage 를 그 배열 위에서
찾으면 아무것도 임계를 넘지 못해 인덱스가 0 으로 남는다 — CSV 에는
t_engage=0.0, 즉 '해석 시작부터 접촉' 이라고 적힌다.
또 total_impulse·peak_force 를 소수 4자리로 반올림하면 작은 접촉이
'충격량 0' 인 채로 engaged 로 남는다.
"""
import sys
from pathlib import Path

from koo_deep_report.core.binout_reader import (
    BinoutData, MatSumData, RcforcInterface,
)
from koo_deep_report.core.energy_flow_builder import build_flow_graph

fails = []


def chk(name, got, want, tol=0.0):
    ok = (got == want) if tol == 0 else (
        got is not None and want is not None and abs(got - want) <= tol)
    if not ok:
        fails.append(f"{name}: got={got!r} want={want!r}")
    print(f"  {'OK ' if ok else 'NG '} {name}")


def chkb(name, cond):
    if not cond:
        fails.append(name)
    print(f"  {'OK ' if cond else 'NG '} {name}")


class _PartRef:
    def __init__(self, kind, part_id, node_id, name):
        self.kind, self.part_id, self.node_id, self.name = kind, part_id, node_id, name


class _Endpoint:
    def __init__(self, cid, name, slave, master, confidence):
        self.cid, self.name = cid, name
        self.slave, self.master, self.confidence = slave, master, confidence


class _ContactMap:
    def __init__(self, endpoints):
        self.endpoints = endpoints


# 2000 샘플 · 5 us 간격 (t_end = 9.995 ms)
N = 2000
DT = 5.0e-6
T = [i * DT for i in range(N)]

# 접촉 10: 주 접촉 — 넓은 펄스 (다운샘플에도 살아남는다)
F10 = [0.0] * N
for i in range(200, 600):
    F10[i] = 1000.0

# 접촉 20: 부 접촉 — 인덱스 1001~1003 에만 50 N (폭 15 us)
F20 = [0.0] * N
for i in (1001, 1002, 1003):
    F20[i] = 50.0
PULSE_T0 = T[1001]          # 0.005005 s

matsum = MatSumData(
    part_ids=[1, 2, 3],
    t=T,
    kinetic_energy=[[100.0, 0.0, 0.0] for _ in range(N)],
    internal_energy=[[0.0, 0.0, 0.0] for _ in range(N)],
    hourglass_energy=[[0.0, 0.0, 0.0] for _ in range(N)],
    x_rbvelocity=[[10.0, 0.0, 0.0] for _ in range(N)],
    y_rbvelocity=[[0.0, 0.0, 0.0] for _ in range(N)],
    z_rbvelocity=[[0.0, 0.0, 0.0] for _ in range(N)],
)
rcforc = []
for cid, fs in ((10, F10), (20, F20)):
    for side in (0, 1):
        rcforc.append(RcforcInterface(
            interface_id=cid, name=f"C{cid}", side=side, t=T,
            fx=list(fs), fy=[0.0] * N, fz=[0.0] * N))

cmap = _ContactMap({
    10: _Endpoint(10, "C10", slave=_PartRef("part", 1, "1", "P1"),
                  master=_PartRef("part", 2, "2", "P2"), confidence=0.9),
    20: _Endpoint(20, "C20", slave=_PartRef("part", 2, "2", "P2"),
                  master=_PartRef("part", 3, "3", "P3"), confidence=0.8),
})

g = build_flow_graph(BinoutData(matsum=matsum, rcforc=rcforc, glstat=None),
                     cmap, {1: "P1", 2: "P2", 3: "P3"},
                     impactor_pid=None, max_pts=200)
edges = {e["contact_id"]: e for e in (g or {}).get("edges", [])}

# ---------------------------------------------------------------------------
print("[1] 짧은 펄스의 engage 시각을 원해상도에서 찾는다")

chkb("두 엣지가 모두 나온다", set(edges) == {10, 20})
e20 = edges.get(20, {})
chkb("부 접촉의 engage 시각이 기록된다", e20.get("first_engage_t") is not None)
chk("engage 시각 = 0.005005 s (t0 아님)", e20.get("first_engage_t"), PULSE_T0, tol=1e-9)
chkb("engage 를 t=0 으로 두지 않는다", (e20.get("first_engage_t") or 0.0) > 0.0)
chkb("first_engage_idx 도 그 시각 근처", (e20.get("first_engage_idx") or 0) > 0)

# 주 접촉은 예전과 같아야 한다 (회귀).
e10 = edges.get(10, {})
chk("주 접촉 engage 시각 = 0.001 s", e10.get("first_engage_t"), T[200], tol=1e-9)

print()

# ---------------------------------------------------------------------------
print("[2] 솎은 force_mag_ts 에서도 펄스가 사라지지 않는다")

fm20 = e20.get("force_mag_ts") or []
chkb("force_mag_ts 가 전부 0 이 아니다", max(fm20, default=0.0) > 0.0)
chk("구간 최대가 50 N 로 남는다", max(fm20, default=0.0), 50.0, tol=1e-6)

print()

# ---------------------------------------------------------------------------
print("[3] 작은 충격량이 반올림으로 0 이 되지 않는다")

# 사다리꼴 적분: 50 N 펄스(인덱스 1001~1003) → 3*DT*50 = 7.5e-4 N*s
# 옛 코드는 round(7.5e-4, 4) = 0.0007 로 6.7% 를 잃었다.
chkb("total_impulse 가 0 이 아니다", (e20.get("total_impulse") or 0.0) > 0.0)
chk("total_impulse = 7.5e-4 N*s", e20.get("total_impulse"), 7.5e-4, tol=1e-9)
chk("peak_force = 50 N", e20.get("peak_force"), 50.0, tol=1e-6)

print()


def test_all():
    """pytest 진입점."""
    assert not fails, "실패 %d 건:\n  - %s" % (len(fails), "\n  - ".join(fails))


if __name__ == "__main__":
    if fails:
        print(f"[FAIL] 실패 {len(fails)} 건")
        for f in fails:
            print("   -", f)
        sys.exit(1)
    print("[PASS] 실패 0 건")
