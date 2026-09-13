# 면 기준 편차각 계산의 정확성·경계 동작을 검증하는 시험
"""`koo_deep_report.core.face_deviation` 시험.

[2] 가 핵심이다 — 절대각으로 산포를 보면 Front 가 180° 로 나오는 실제 오류를
재현하고, 편차각이 그것을 고치는지 확인한다.
"""
import math
import sys

from koo_deep_report.core.face_deviation import (
    FACE_STANDARD_ANGLES, impact_direction, angle_between, wrap180,
    face_deviation, nearest_face,
)

fails = []


def chk(name, got, want, tol=0.0):
    ok = (got == want) if tol == 0 else (
        got is not None and abs(got - want) <= tol)
    if not ok:
        fails.append(f"{name}: got={got!r} want={want!r}")
    print(f"  {'OK ' if ok else 'NG '} {name}")


def chkb(name, cond):
    if not cond:
        fails.append(name)
    print(f"  {'OK ' if cond else 'NG '} {name}")


print("[1] 충격 방향 — 기준자세에서 알려진 축")
# F1 Back (0,0,0): Rᵀ·(0,0,-1) = (0,0,-1)
v = impact_direction(0, 0, 0)
chk("F1 방향 = (0,0,-1)", max(abs(v[i] - (0, 0, -1)[i]) for i in range(3)), 0.0, 1e-15)
# F2 Front (180,0,0): roll 180 → z 가 뒤집힌다
v = impact_direction(180, 0, 0)
chk("F2 방향 = (0,0,+1)", max(abs(v[i] - (0, 0, 1)[i]) for i in range(3)), 0.0, 1e-15)
# 6면의 방향이 서로 다른 축이어야 한다
dirs = {c: impact_direction(a[1], a[2], a[3]) for c, a in FACE_STANDARD_ANGLES.items()}
pairs = [(c1, c2) for c1 in dirs for c2 in dirs if c1 < c2]
mins = min(angle_between(dirs[a], dirs[b]) for a, b in pairs)
chk("서로 다른 면은 최소 90° 떨어져 있다", round(mins, 9), 90.0, 1e-9)
chkb("모든 면 방향이 단위벡터", all(
    abs(math.sqrt(sum(c * c for c in v)) - 1) < 1e-15 for v in dirs.values()))

print("[2] 실제 오류 재현 — 절대각 vs 편차각")
# Front(F2) 기준 180°, 거기서 3° 벗어난 자세
r, p = 177.0, 0.0
abs_metric = math.hypot(r, p)
d = face_deviation(r, p, 0.0, "F2")
print(f"      절대각 hypot(roll,pitch) = {abs_metric:.1f}°  ← 이것이 오류의 원인")
print(f"      편차각 dev_angle         = {d.dev_angle:.1f}°")
chkb("절대각은 177° 로 나온다 (산포가 아니라 기준자세를 재고 있다)",
     abs(abs_metric - 177.0) < 1e-9)
chk("편차각은 3°", d.dev_angle, 3.0, 1e-9)
chk("dev_roll 은 -3° (180 에서 감긴다)", d.dev_roll, -3.0, 1e-9)

print("[3] 기준자세 자신의 편차는 0")
for code, ref in FACE_STANDARD_ANGLES.items():
    d = face_deviation(ref[1], ref[2], ref[3], code)
    # 🔴 acos 을 썼다면 여기서 ~1e-6 도의 잡음이 나온다. atan2 는 정확히 0.
    ok = d.dev_angle is not None and d.dev_angle == 0.0
    if not ok:
        fails.append(f"{code} 기준자세 편차 {d.dev_angle}")
    print(f"  {'OK ' if ok else 'NG '} {code} ({d.face_name}) 편차 = {d.dev_angle}")

print("[4] 코너 각도 — 이 규약(R=Rx·Ry·Rz, v=Rᵀ·(0,0,−1))에서의 꼭짓점")
# 꼭짓점 방향은 (±1,±1,±1)/√3.
# v = (−sin p, sin r·cos p, −cos r·cos p) 이므로 세 성분이 같으려면
#   sin p = 1/√3  →  |pitch| = asin(1/√3) = 35.264390°
#   sin r·cos p = 1/√3, cos p = √(2/3)  →  roll = 45°
# 🔴 즉 이 규약에서 35.264° 인 것은 **pitch** 이고 roll 은 45° 다.
#    (다른 회전 순서 규약에서는 반대로 적히기도 한다 — 뒤바꾸면 9.74° 틀린다.)
corner = math.degrees(math.asin(1 / math.sqrt(3)))
chk("asin(1/√3) = 35.264390°", corner, 35.264389682754654, 1e-12)
v = impact_direction(45.0, -corner, 0.0)
comps = sorted(abs(c) for c in v)
chkb("roll=45, pitch=-35.264 → 세 성분 크기가 같다 (1/√3)",
     abs(comps[0] - comps[2]) < 1e-12 and abs(comps[0] - 1 / math.sqrt(3)) < 1e-12)

print("[4b] 26방향 격자 판정 — 옛 도구의 코너 결함을 잡는가")
from koo_deep_report.core.face_deviation import classify_direction
chk("면 판정", classify_direction(0, 0, 0)[0], "face")
chk("모서리 판정", classify_direction(45, 0, 0)[0], "edge")
chk("꼭짓점 판정", classify_direction(45, -corner, 0)[0], "vertex")
# 코너 roll 을 45° 로 둔 옛 결함: (0.707, 0.5, 0.5) — 꼭짓점에서 9.7356° 벗어난다
kind, off = classify_direction(45, 45, 0)
chkb("옛 코너 결함을 격자 벗어남으로 잡는다", kind == "off_lattice")
chk("벗어난 각도 = 45 − asin(1/√3) 에 해당", off, 9.735610317245343, 1e-9)
print(f"      옛 코너(roll=45,pitch=45): {kind}, 이상형에서 {off:.4f}°")
# 허용오차를 키우면 꼭짓점으로 통과한다 (판정이 tol 을 실제로 쓰는지)
chk("tol 을 10° 로 키우면 vertex", classify_direction(45, 45, 0, tol_deg=10)[0], "vertex")

print("[5] angle_between — acos 정밀도 함정")
a = (0.0, 0.0, -1.0)
chk("같은 벡터는 정확히 0°", angle_between(a, a), 0.0)
chk("반대 벡터는 180°", angle_between(a, (0, 0, 1)), 180.0, 1e-13)
chk("직교는 90°", angle_between((1, 0, 0), (0, 1, 0)), 90.0, 1e-13)
# 아주 작은 각도도 잡아야 한다 (acos 은 여기서 0 으로 뭉갠다)
eps = 1e-7
b = (math.sin(math.radians(eps)), 0.0, -math.cos(math.radians(eps)))
got = angle_between(a, b)
chk("1e-7° 도 잡아낸다", got, eps, eps * 1e-6)

print("[6] wrap180")
chk("190 → -170", wrap180(190), -170.0, 1e-12)
chk("180 → 180", wrap180(180), 180.0, 1e-12)
chk("-180 → 180", wrap180(-180), 180.0, 1e-12)
chk("-190 → 170", wrap180(-190), 170.0, 1e-12)
chk("360 → 0", wrap180(360), 0.0, 1e-12)

print("[7] nearest_face")
chk("F1 기준자세 → F1", nearest_face(0, 0, 0)[0], "F1")
chk("F5 기준자세 → F5", nearest_face(90, 0, 0)[0], "F5")
code, ang = nearest_face(3, 0, 0)
chkb("F1 에서 3° 벗어나도 F1", code == "F1" and abs(ang - 3.0) < 1e-9)

print("[8] 에러를 내지 않는가")
cases = [
    ("모르는 면", lambda: face_deviation(0, 0, 0, "F9")),
    ("빈 면 코드", lambda: face_deviation(0, 0, 0, "")),
    ("None 면", lambda: face_deviation(0, 0, 0, None)),
    ("문자열 각도", lambda: face_deviation("a", 0, 0, "F1")),
    ("NaN 각도", lambda: face_deviation(float('nan'), 0, 0, "F1")),
    ("Inf 각도", lambda: face_deviation(float('inf'), 0, 0, "F1")),
    ("소문자 면", lambda: face_deviation(0, 0, 0, "f1")),
    ("방향: 문자열", lambda: impact_direction("a", 0, 0)),
    ("각도: 영벡터", lambda: angle_between((0, 0, 0), (0, 0, 0))),
    ("각도: 길이 부족", lambda: angle_between((1, 0), (0, 1, 0))),
    ("각도: 문자열", lambda: angle_between(("a", 0, 0), (0, 1, 0))),
    ("nearest: 문자열", lambda: nearest_face("a", 0, 0)),
    ("classify: 문자열", lambda: classify_direction("a", 0, 0)),
    ("classify: NaN", lambda: classify_direction(float('nan'), 0, 0)),
    ("classify: tol 문자열", lambda: classify_direction(0, 0, 0, tol_deg="x")),
]
for name, fn in cases:
    try:
        fn()
        print(f"  OK  예외 없음: {name}")
    except Exception as e:          # noqa: BLE001
        fails.append(f"예외 발생: {name} → {type(e).__name__}: {e}")
        print(f"  NG  예외 발생: {name} → {type(e).__name__}: {e}")

d = face_deviation(0, 0, 0, "F9")
chkb("모르는 면: 값 None + 사유", d.dev_angle is None and bool(d.note))
d = face_deviation(0, 0, 0, "f1")
chkb("소문자 면 코드도 인식", d.dev_angle == 0.0)

print()
if fails:
    print(f"[FAIL] 실패 {len(fails)} 건")
    for f in fails:
        print("   -", f)
    sys.exit(1)
print("[PASS] 실패 0 건")
