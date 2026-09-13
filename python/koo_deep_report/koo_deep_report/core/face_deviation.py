# 면 기준자세 대비 편차각을 구하는 모듈 — 절대각으로 산포를 보면 부호가 뒤집힌다
"""면(F1~F6) 기준자세 대비 편차각.

**왜 이 모듈이 있나.**
`scenario.json` 의 roll/pitch 는 **절대각**이고 면마다 기준자세가 다르다.
절대각으로 `hypot(roll, pitch)` 를 하면 Front(기준 roll=180°)의 산포 중앙값이
180° 로 나온다. 2026-09 검증에서 실제로 이렇게 틀렸고, 면별 기준을 빼서
편차각으로 바꾸니 **상관계수 부호가 전부 뒤집혔다** (Front +0.16 → −0.77).

**무엇을 편차로 보는가.**
회전은 비가환이고 각도는 ±180° 에서 감긴다. 그래서 성분을 그냥 빼면 안 된다.
여기서는 **충격 방향 벡터 사이의 각도**를 주 지표(`dev_angle`)로 쓴다 —
"어느 방향으로 떨어지는가" 가 물리적으로 의미 있는 양이기 때문이다.
성분별 차이(`dev_roll`/`dev_pitch`/`dev_yaw`)는 보조로 함께 낸다(−180, 180] 로 감아서.

**각도 규약.**
`R = Rx(roll) · Ry(pitch) · Rz(yaw)`, 충격 방향(기기 좌표) `= Rᵀ · (0, 0, −1)`.
1144런 덱으로 검증된 규약이다.

**설계 규칙.** 예외를 던지지 않는다. 계산할 수 없으면 `None` 을 돌려준다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

#: 직육면체 26방향의 6면 기준자세 (roll, pitch, yaw) [deg].
#: koo_impact_report.loader.FACE_STANDARD 와 같은 값이다. 그 패키지가 없는
#: 환경에서도 쓸 수 있게 여기 둔다 — import 실패로 보고서를 죽이지 않는다.
FACE_STANDARD_ANGLES: dict[str, tuple[str, float, float, float]] = {
    "F1": ("Back",   0.0,   0.0, 0.0),
    "F2": ("Front",  180.0, 0.0, 0.0),
    "F3": ("Right",  0.0, -90.0, 0.0),
    "F4": ("Left",   0.0,  90.0, 0.0),
    "F5": ("Top",    90.0,  0.0, 0.0),
    "F6": ("Bottom", -90.0, 0.0, 0.0),
}


def _rot(roll_deg: float, pitch_deg: float, yaw_deg: float) -> list[list[float]]:
    """R = Rx(roll) · Ry(pitch) · Rz(yaw) (도 단위 입력)."""
    r, p, y = (math.radians(roll_deg), math.radians(pitch_deg), math.radians(yaw_deg))
    cr, sr = math.cos(r), math.sin(r)
    cp, sp = math.cos(p), math.sin(p)
    cy, sy = math.cos(y), math.sin(y)
    # Rx·Ry·Rz 를 전개한 결과
    return [
        [cp * cy,                 -cp * sy,                 sp],
        [sr * sp * cy + cr * sy,  -sr * sp * sy + cr * cy,  -sr * cp],
        [-cr * sp * cy + sr * sy,  cr * sp * sy + sr * cy,   cr * cp],
    ]


def impact_direction(roll_deg: float, pitch_deg: float, yaw_deg: float = 0.0):
    """자세에 대응하는 충격 방향 단위벡터 (기기 좌표계). 실패하면 None."""
    try:
        R = _rot(float(roll_deg), float(pitch_deg), float(yaw_deg))
    except (TypeError, ValueError):
        return None
    # Rᵀ · (0, 0, −1) = R 의 3번째 **열**에 −1 을 곱한 것
    v = (-R[0][2], -R[1][2], -R[2][2])
    n = math.sqrt(sum(c * c for c in v))
    if n <= 0:
        return None
    return (v[0] / n, v[1] / n, v[2] / n)


def angle_between(a, b) -> float | None:
    """두 벡터 사이 각도 [deg].

    🔴 `acos(a·b)` 를 쓰면 안 된다. dot 이 1 에 가까울 때 정밀도가 무너져
       같은 방향인데도 ~1e-6 도의 잡음이 나온다(실제로 8.5e-7° 를 '회귀' 로
       잘못 보고한 적이 있다). `atan2(|a×b|, a·b)` 는 전 구간에서 안정적이다.
    """
    try:
        ax, ay, az = (float(v) for v in a)
        bx, by, bz = (float(v) for v in b)
    except (TypeError, ValueError):
        return None
    cx = ay * bz - az * by
    cy = az * bx - ax * bz
    cz = ax * by - ay * bx
    cross = math.sqrt(cx * cx + cy * cy + cz * cz)
    dot = ax * bx + ay * by + az * bz
    if cross == 0.0 and dot == 0.0:
        return None                      # 영벡터가 섞였다
    return math.degrees(math.atan2(cross, dot))


def wrap180(deg: float) -> float:
    """각도를 (−180, 180] 로 감는다."""
    d = math.fmod(float(deg) + 180.0, 360.0)
    if d <= 0:
        d += 360.0
    return d - 180.0


@dataclass
class FaceDeviation:
    face: str = ""
    face_name: str = ""
    dev_angle: float | None = None   #: 충격 방향 사이 각도 [deg] — 주 지표
    dev_roll: float | None = None    #: 성분별 차이 (−180, 180]
    dev_pitch: float | None = None
    dev_yaw: float | None = None
    note: str = ""


def face_deviation(roll_deg: float, pitch_deg: float, yaw_deg: float,
                   face: str) -> FaceDeviation:
    """면 기준자세 대비 편차. 모르는 면이면 값 없이 사유를 돌려준다."""
    res = FaceDeviation(face=str(face or ""))
    ref = FACE_STANDARD_ANGLES.get(res.face.upper())
    if ref is None:
        res.note = (f"면 코드 '{res.face}' 를 모릅니다 "
                    f"({', '.join(sorted(FACE_STANDARD_ANGLES))} 중 하나여야 합니다)")
        return res
    res.face_name = ref[0]
    try:
        r, p, y = float(roll_deg), float(pitch_deg), float(yaw_deg)
    except (TypeError, ValueError):
        res.note = "자세각이 숫자가 아닙니다"
        return res
    if any(math.isnan(v) or math.isinf(v) for v in (r, p, y)):
        res.note = "자세각에 NaN/Inf 가 있습니다"
        return res

    res.dev_roll = wrap180(r - ref[1])
    res.dev_pitch = wrap180(p - ref[2])
    res.dev_yaw = wrap180(y - ref[3])

    va = impact_direction(r, p, y)
    vb = impact_direction(ref[1], ref[2], ref[3])
    if va is None or vb is None:
        res.note = "충격 방향을 계산하지 못했습니다"
        return res
    res.dev_angle = angle_between(va, vb)
    return res


#: 직육면체 26방향의 이상적인 방향 유형과 성분 크기.
#: 면 = (1,0,0), 모서리 = (1,1,0)/√2, 꼭짓점 = (1,1,1)/√3 의 순열·부호.
_IDEAL = {
    "face":   (1.0, 0.0, 0.0),
    "edge":   (1 / math.sqrt(2), 1 / math.sqrt(2), 0.0),
    "vertex": (1 / math.sqrt(3), 1 / math.sqrt(3), 1 / math.sqrt(3)),
}


def classify_direction(roll_deg: float, pitch_deg: float, yaw_deg: float = 0.0,
                       tol_deg: float = 0.5):
    """충격 방향이 26방향 중 어느 유형인지 판정한다.

    Returns:
        (유형, 이상형과의 각도차[deg]) — 유형은 "face"/"edge"/"vertex",
        어느 것과도 `tol_deg` 안에 들지 않으면 ("off_lattice", 최소 각도차).
        계산 못 하면 (None, None).

    **왜 필요한가.** 26방향 DOE 를 만든 도구에 결함이 있으면 꼭짓점이 꼭짓점이
    아닌 방향으로 생성된다(코너 roll 을 45° 로 두면 (0.707, 0.5, 0.5) 가 되어
    진짜 꼭짓점 (0.577,0.577,0.577) 에서 15.8° 벗어난다). 실제로 그런 캠페인이
    있었고, 결과만 봐서는 알 수 없었다. 여기서 기계가 잡는다.
    """
    v = impact_direction(roll_deg, pitch_deg, yaw_deg)
    if v is None:
        return (None, None)
    comps = sorted((abs(c) for c in v), reverse=True)
    best, best_a = None, None
    for kind, ideal in _IDEAL.items():
        # 성분 크기를 내림차순으로 맞춰 비교하면 축 순서·부호와 무관해진다
        a = angle_between(comps, sorted(ideal, reverse=True))
        if a is None:
            continue
        if best_a is None or a < best_a:
            best, best_a = kind, a
    if best_a is None:
        return (None, None)
    try:
        tol = float(tol_deg)
    except (TypeError, ValueError):
        tol = 0.5
    return (best if best_a <= tol else "off_lattice", best_a)


def nearest_face(roll_deg: float, pitch_deg: float, yaw_deg: float = 0.0):
    """충격 방향이 가장 가까운 면과 그 편차각. 실패하면 (None, None).

    면 코드가 폴더명에 없는 캠페인에서 쓴다. **동점이면 코드 순서로 정한다** —
    같은 입력이 늘 같은 답을 내야 한다.
    """
    v = impact_direction(roll_deg, pitch_deg, yaw_deg)
    if v is None:
        return (None, None)
    best, best_a = None, None
    for code in sorted(FACE_STANDARD_ANGLES):
        ref = FACE_STANDARD_ANGLES[code]
        vb = impact_direction(ref[1], ref[2], ref[3])
        if vb is None:
            continue
        a = angle_between(v, vb)
        if a is None:
            continue
        if best_a is None or a < best_a - 1e-12:
            best, best_a = code, a
    return (best, best_a)
