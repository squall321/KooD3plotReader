# 좌표 역추정(강체 변환)의 정확성과 잔차 판정을 검증하는 시험
"""`koo_deep_report.core.coordinate_transform` 시험."""
import math
import random
import sys

from koo_deep_report.core.coordinate_transform import (
    estimate_transform, residual_verdict,
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


def _rot(ax, ay, az):
    ca, sa = math.cos(ax), math.sin(ax)
    cb, sb = math.cos(ay), math.sin(ay)
    cc, sc = math.cos(az), math.sin(az)
    Rx = [[1, 0, 0], [0, ca, -sa], [0, sa, ca]]
    Ry = [[cb, 0, sb], [0, 1, 0], [-sb, 0, cb]]
    Rz = [[cc, -sc, 0], [sc, cc, 0], [0, 0, 1]]
    def mul(A, B):
        return [[sum(A[i][k] * B[k][j] for k in range(3)) for j in range(3)]
                for i in range(3)]
    return mul(mul(Rx, Ry), Rz)


def _apply(R, t, p):
    return [sum(R[i][k] * p[k] for k in range(3)) + t[i] for i in range(3)]


print("[1] 평행이동만 — 실제 사건의 값 (Δy≈−73.7, Δz≈+4.9)")
random.seed(1)
P = [[random.uniform(-50, 50) for _ in range(3)] for _ in range(8)]
t_true = [0.0, -73.7, 4.9]
Q = [[p[i] + t_true[i] for i in range(3)] for p in P]
r = estimate_transform(P, Q)
chkb("성공", r.ok)
for i, name in enumerate("xyz"):
    chk(f"평행이동 d{name}", r.translation[i], t_true[i], 1e-9)
chk("잔차 0", r.max_residual, 0.0, 1e-9)
chkb("회전각이 0 (acos 이었다면 1e-6 잡음)",
     r.rotation_angle_deg is not None and r.rotation_angle_deg < 1e-9)
print(f"      {residual_verdict(r)}")

print("[2] 회전 + 평행이동")
R_true = _rot(math.radians(7), math.radians(-13), math.radians(21))
t_true = [10.0, -5.0, 3.0]
Q = [_apply(R_true, t_true, p) for p in P]
r = estimate_transform(P, Q)
chk("method = rigid", r.method, "rigid")
for i in range(3):
    chk(f"평행이동 [{i}]", r.translation[i], t_true[i], 1e-9)
chkb("회전행렬 일치", all(
    abs(r.rotation[i][j] - R_true[i][j]) < 1e-9 for i in range(3) for j in range(3)))
chk("잔차 0", r.max_residual, 0.0, 1e-9)

print("[3] 잡음이 있으면 잔차로 드러난다")
# 기본 허용오차는 점군 크기의 1e-3 이다. 좌표 정합은 **초기 형상** 기준이라
# 잔차가 거의 0 이어야 정상이고, 엄격한 쪽이 안전하다(조용히 틀린 정합을
# 통과시키지 않는다). 여기서는 크기 50 대비 σ=0.005 (rel ~3e-4) 를 '작은 잡음'
# 으로 본다.
Q = [[c + random.gauss(0, 0.005) for c in _apply(R_true, t_true, p)] for p in P]
r = estimate_transform(P, Q)
chkb("잔차가 0 이 아니다", r.max_residual > 1e-4)
chkb("작은 잡음은 경고하지 않는다", "의심" not in residual_verdict(r))
# 크기의 1% 잡음이면 경고가 나야 한다
Q = [[c + random.gauss(0, 0.5) for c in _apply(R_true, t_true, p)] for p in P]
r = estimate_transform(P, Q)
chkb("크기 1% 잡음은 경고한다", "의심" in residual_verdict(r))
# 한 점만 크게 어긋나면(대응 오류) 경고가 나야 한다
Q2 = [_apply(R_true, t_true, p) for p in P]
Q2[0] = [Q2[0][0] + 500.0, Q2[0][1], Q2[0][2]]
r2 = estimate_transform(P, Q2)
chkb("대응 오류는 경고로 드러난다", "의심" in residual_verdict(r2))
print(f"      {residual_verdict(r2)}")

print("[4] 회전을 결정할 수 없는 경우 — 지어내지 않는다")
# 점 2개
r = estimate_transform(P[:2], [[p[0] + 1, p[1], p[2]] for p in P[:2]])
chk("점 2개면 평행이동만", r.method, "translation_only")
chkb("사유가 적혀 있다", "회전" in r.note)
chkb("rotation 키가 비어 있다", not r.rotation)
# 한 직선 위의 점들
line = [[float(i), 0.0, 0.0] for i in range(5)]
r = estimate_transform(line, [[p[0] + 2, p[1], p[2]] for p in line])
chk("공선 점군이면 평행이동만", r.method, "translation_only")
chk("평행이동 dx", r.translation[0], 2.0, 1e-9)

print("[5] as_metadata")
r = estimate_transform(P, [[p[0] + 1, p[1] + 2, p[2] + 3] for p in P])
m = r.as_metadata()
chkb("필수 키가 있다", {"method", "n_pairs", "translation", "rmse"} <= set(m))
bad = estimate_transform([], [])
chk("실패하면 빈 dict (0 벡터를 지어내지 않는다)", bad.as_metadata(), {})

print("[6] 에러를 내지 않는가")
cases = [
    ("빈 입력", lambda: estimate_transform([], [])),
    ("길이 불일치", lambda: estimate_transform([[0, 0, 0]], [])),
    ("좌표 2개짜리 점", lambda: estimate_transform([[0, 0]], [[0, 0]])),
    ("문자열 좌표", lambda: estimate_transform([["a", 0, 0]], [[0, 0, 0]])),
    ("NaN 좌표", lambda: estimate_transform(
        [[float('nan'), 0, 0], [1, 1, 1]], [[0, 0, 0], [1, 1, 1]])),
    ("전부 NaN", lambda: estimate_transform([[float('nan')] * 3], [[0, 0, 0]])),
    ("None 입력", lambda: estimate_transform(None, None)),
    ("한 점", lambda: estimate_transform([[1, 2, 3]], [[4, 5, 6]])),
    ("같은 점 반복", lambda: estimate_transform([[1, 1, 1]] * 5, [[2, 2, 2]] * 5)),
    ("판정문: 실패한 변환", lambda: residual_verdict(estimate_transform([], []))),
    ("판정문: rel_tol 문자열", lambda: residual_verdict(
        estimate_transform(P, P), rel_tol="x")),
]
for name, fn in cases:
    try:
        fn()
        print(f"  OK  예외 없음: {name}")
    except Exception as e:          # noqa: BLE001
        fails.append(f"예외 발생: {name} → {type(e).__name__}: {e}")
        print(f"  NG  예외 발생: {name} → {type(e).__name__}: {e}")

r = estimate_transform([[float('nan'), 0, 0], [1, 1, 1], [2, 2, 2]],
                       [[0, 0, 0], [1, 1, 1], [2, 2, 2]])
chk("NaN 쌍은 버리고 나머지로 계산", r.n_pairs, 2)
r = estimate_transform([], [])
chkb("빈 입력: ok=False + 사유", (not r.ok) and bool(r.note))
r = estimate_transform([[1, 1, 1]] * 5, [[2, 2, 2]] * 5)
chkb("한 점에 몰리면 판정문이 그 사실을 말한다", "몰려" in residual_verdict(r))

print()


def test_all():
    """pytest 진입점.

    이 파일의 본문은 import 시점에 이미 실행된다(스크립트로도 돌릴 수 있게
    그렇게 썼다). pytest 는 여기서 결과만 단언한다 — 이 함수가 없으면
    `no tests ran` 으로 **조용히 지나가** CI 에서 무의미해진다.
    """
    assert not fails, "실패 %d 건:\n  - %s" % (len(fails), "\n  - ".join(fails))


if __name__ == "__main__":
    if fails:
        print(f"[FAIL] 실패 {len(fails)} 건")
        for f in fails:
            print("   -", f)
        sys.exit(1)
    print("[PASS] 실패 0 건")
