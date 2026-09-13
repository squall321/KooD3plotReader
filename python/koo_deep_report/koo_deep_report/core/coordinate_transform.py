# 결과 좌표와 원본 도면 좌표 사이의 강체 변환을 파트 중심 대응으로 역추정하는 모듈
"""좌표계 정합 — 결과 ↔ 원본 덱.

**왜 이 모듈이 있나.**
KMM 이 DropSet 을 만들 때 모델을 평행이동한다(T1_DV1 실측 Δy≈−73.7, Δz≈+4.9).
결과 좌표를 원본 도면과 그냥 비교하면 위치가 통째로 어긋난다. 지금까지는 매번
결과 파트 중심과 원본 덱 파트 중심을 손으로 대조해 역추적했다.

후처리는 변환을 *전달받지* 못한다(DropSet.json 에 기록이 없다). 그래서 여기서는
**추정**하고, 추정이 맞는지 알 수 있게 잔차를 함께 돌려준다. 잔차가 크면
"평행이동으로 설명되지 않는다" 는 뜻이고, 그때 숫자를 믿으면 안 된다.

**설계 규칙.** 예외를 던지지 않는다. numpy 가 없으면 평행이동만 추정하고
그 사실을 `method` 에 적는다 — 회전을 0 이라고 지어내지 않는다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

try:
    import numpy as _np
except ImportError:
    _np = None


@dataclass
class RigidTransform:
    """Q ≈ R·P + t 로 맞춘 결과. 실패하면 `ok=False` 이고 `note` 에 사유가 있다."""
    ok: bool = False
    method: str = ""                 #: "rigid"(회전+평행이동) | "translation_only"
    n_pairs: int = 0
    translation: list = field(default_factory=list)     #: [dx, dy, dz]
    rotation: list = field(default_factory=list)        #: 3×3 행렬 (행 우선)
    rotation_angle_deg: float | None = None             #: 회전각 (0 이면 평행이동뿐)
    rmse: float | None = None                           #: 잔차 RMS
    max_residual: float | None = None                   #: 최대 잔차
    scale_hint: float | None = None                     #: 점군 크기 (잔차 해석용)
    note: str = ""

    def as_metadata(self) -> dict:
        """`analysis_result.json > metadata.coordinate_transform` 에 넣을 형태.

        추정에 실패했으면 **키를 만들지 않도록** 빈 dict 를 돌려준다 —
        0 벡터를 넣으면 "변환 없음" 으로 읽힌다.
        """
        if not self.ok:
            return {}
        out = {
            "method": self.method,
            "n_pairs": self.n_pairs,
            "translation": [float(v) for v in self.translation],
            "rmse": self.rmse,
            "max_residual": self.max_residual,
        }
        if self.rotation:
            out["rotation"] = [[float(v) for v in row] for row in self.rotation]
            out["rotation_angle_deg"] = self.rotation_angle_deg
        return out


def _centroid(pts):
    n = len(pts)
    return [sum(p[i] for p in pts) / n for i in range(3)]


def estimate_transform(source_points, result_points,
                       allow_rotation: bool = True) -> RigidTransform:
    """대응하는 두 점군에서 강체 변환을 추정한다.

    Args:
        source_points: 원본(도면) 좌표 [[x,y,z], ...]
        result_points: 결과(해석) 좌표 — **같은 순서로 대응**해야 한다
        allow_rotation: False 면 평행이동만 추정한다

    Returns:
        RigidTransform. `rmse`/`max_residual` 이 점군 크기(`scale_hint`)에 비해
        크면 대응이 잘못됐거나 변환이 강체가 아니라는 뜻이다.
    """
    res = RigidTransform()
    def _pts(seq):
        out = []
        for p in seq:
            # 🔴 p[:3] 은 좌표가 2개여도 조용히 2개짜리를 내놓는다. 길이를 먼저 본다.
            try:
                c = list(p)
            except TypeError:
                raise ValueError("점이 시퀀스가 아닙니다")
            if len(c) < 3:
                raise ValueError(f"좌표가 {len(c)}개인 점이 있습니다 (3개 필요)")
            out.append([float(v) for v in c[:3]])
        return out

    try:
        P = _pts(source_points)
        Q = _pts(result_points)
    except (TypeError, ValueError):
        res.note = "점 좌표를 숫자 3개로 해석하지 못했습니다"
        return res
    if len(P) != len(Q):
        res.note = f"점 개수가 다릅니다 ({len(P)} vs {len(Q)})"
        return res
    # 유한하지 않은 점은 쌍으로 버린다
    keep = [i for i in range(len(P))
            if all(math.isfinite(c) for c in P[i] + Q[i])]
    P = [P[i] for i in keep]
    Q = [Q[i] for i in keep]
    res.n_pairs = len(P)
    if res.n_pairs < 1:
        res.note = "유효한 대응점이 없습니다"
        return res

    cp, cq = _centroid(P), _centroid(Q)
    spread = max((max(abs(p[i] - cp[i]) for p in P) for i in range(3)), default=0.0)
    res.scale_hint = spread

    # 회전을 추정하려면 점이 3개 이상이고 한 직선 위에 있지 않아야 한다.
    want_rot = bool(allow_rotation) and res.n_pairs >= 3 and _np is not None
    if want_rot:
        A = _np.asarray(P, dtype=float) - _np.asarray(cp, dtype=float)
        B = _np.asarray(Q, dtype=float) - _np.asarray(cq, dtype=float)
        # 점들이 퍼져 있지 않으면 회전이 결정되지 않는다 — 평행이동만 쓴다
        if float(_np.linalg.matrix_rank(A, tol=1e-9 * max(spread, 1e-12))) < 3:
            want_rot = False

    if want_rot:
        H = A.T @ B
        try:
            U, _S, Vt = _np.linalg.svd(H)
        except Exception:            # noqa: BLE001 — 수렴 실패 등
            want_rot = False
        else:
            d = 1.0 if float(_np.linalg.det(Vt.T @ U.T)) >= 0 else -1.0
            D = _np.diag([1.0, 1.0, d])          # 반사(거울상)를 막는다
            R = Vt.T @ D @ U.T
            t = _np.asarray(cq) - R @ _np.asarray(cp)
            pred = (R @ _np.asarray(P).T).T + t
            diff = pred - _np.asarray(Q)
            dist = _np.sqrt((diff * diff).sum(axis=1))
            res.ok = True
            res.method = "rigid"
            res.rotation = [[float(v) for v in row] for row in R]
            res.translation = [float(v) for v in t]
            res.rmse = float(_np.sqrt((dist * dist).mean()))
            res.max_residual = float(dist.max())
            tr = max(-1.0, min(3.0, float(_np.trace(R))))
            # 🔴 acos((tr−1)/2) 는 tr≈3 에서 정밀도가 무너진다. 회전이 없을 때
            #    ~1e-6 도가 나와 '회전이 있다' 고 오독된다. atan2 로 구한다.
            cos_t = (tr - 1.0) / 2.0
            cos_t = max(-1.0, min(1.0, cos_t))
            sin_t = math.sqrt(max(0.0, 1.0 - cos_t * cos_t))
            res.rotation_angle_deg = math.degrees(math.atan2(sin_t, cos_t))
            return res

    # ── 평행이동만 ──
    t = [cq[i] - cp[i] for i in range(3)]
    dist = [math.sqrt(sum((Q[k][i] - P[k][i] - t[i]) ** 2 for i in range(3)))
            for k in range(res.n_pairs)]
    res.ok = True
    res.method = "translation_only"
    res.translation = t
    res.rmse = math.sqrt(sum(d * d for d in dist) / len(dist))
    res.max_residual = max(dist)
    if allow_rotation and _np is None:
        res.note = "numpy 가 없어 회전은 추정하지 않았습니다 (평행이동만)"
    elif allow_rotation and res.n_pairs < 3:
        res.note = f"대응점이 {res.n_pairs}개라 회전을 결정할 수 없습니다 (평행이동만)"
    elif allow_rotation:
        res.note = "점들이 한 평면·직선에 몰려 회전을 결정할 수 없습니다 (평행이동만)"
    return res


def residual_verdict(tr: RigidTransform, rel_tol: float = 1e-3) -> str:
    """잔차가 받아들일 만한지 한 줄로 판정한다 (보고서에 그대로 실을 수 있게)."""
    if not tr.ok:
        return f"좌표 정합 실패 — {tr.note or '사유 없음'}"
    scale = tr.scale_hint or 0.0
    if scale <= 0:
        return (f"{tr.method}: 평행이동 "
                f"({', '.join(f'{v:.4g}' for v in tr.translation)}), "
                f"점군이 한 점에 몰려 잔차를 판정할 수 없습니다")
    rel = (tr.max_residual or 0.0) / scale
    try:
        tol = float(rel_tol)
    except (TypeError, ValueError):
        tol = 1e-3                  # 해석 못 하면 기본값 — 판정문이 죽지 않게
    ok = rel <= tol
    head = "좌표 정합" if ok else "⚠ 좌표 정합 의심"
    return (f"{head} [{tr.method}] 평행이동 "
            f"({', '.join(f'{v:.4g}' for v in tr.translation)})"
            f"{'' if not tr.rotation else f', 회전 {tr.rotation_angle_deg:.4g}°'}"
            f" · 대응 {tr.n_pairs}점 · 최대잔차 {tr.max_residual:.4g}"
            f" ({rel:.2e} × 크기)"
            + ("" if ok else " — 대응이 잘못됐거나 강체 변환이 아닙니다"))
