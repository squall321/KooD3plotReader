# 평행 투영 카메라 — 시점 고르기 · 화면에 투영된 크기로 맞추기 · 점 투영(PNG 와 SVG 가 같은 값을 쓴다)
"""VTK 평행 투영과 같은 약속을 쓴다: 시선 방향 d(카메라 → 초점), 위쪽 u, 오른쪽 r = d × u, `scale` = 화면 높이의 절반(월드 단위).
그래서 `to_vtk` 로 pyvista 에 넘긴 그림과 `project` 로 그린 SVG 가 같은 자리에 같은 크기로 나온다.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

#: 이름 있는 시점 — (시선 방향, 위쪽). iso 는 VTK 의 iso 와 같다(+X+Y+Z 쪽에서 원점을 본다).
_NAMED = {
    "iso": ((-1.0, -1.0, -1.0), (0.0, 0.0, 1.0)),
    "iso_back": ((1.0, 1.0, -1.0), (0.0, 0.0, 1.0)),
    "top": ((0.0, 0.0, -1.0), (0.0, 1.0, 0.0)),
    "bottom": ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0)),
    "front": ((0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
    "back": ((0.0, -1.0, 0.0), (0.0, 0.0, 1.0)),
    "right": ((-1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
    "left": ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
}


def _unit(v) -> np.ndarray:
    v = np.asarray(v, dtype=np.float64)
    n = np.linalg.norm(v)
    if n < 1e-15:
        raise ValueError("방향 벡터가 0 이다")
    return v / n


def _orthogonal_up(direction: np.ndarray, up) -> np.ndarray:
    u = np.asarray(up, dtype=np.float64)
    u = u - direction * u.dot(direction)
    if np.linalg.norm(u) < 1e-6:                       # 시선과 위쪽이 나란하면 다른 축을 위로
        for alt in ((0.0, 1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)):
            a = np.asarray(alt) - direction * np.dot(alt, direction)
            if np.linalg.norm(a) > 1e-6:
                u = a
                break
    return _unit(u)


@dataclass
class Camera:
    direction: np.ndarray        # 단위 시선 방향(카메라 → 초점)
    up: np.ndarray               # 단위, 시선과 수직
    focal: np.ndarray            # 초점(월드)
    scale: float                 # 화면 높이의 절반(월드 단위)
    width: int
    height: int

    @property
    def right(self) -> np.ndarray:
        return np.cross(self.direction, self.up)

    @property
    def px_per_unit(self) -> float:
        return (self.height / 2.0) / self.scale

    def project(self, pts: np.ndarray) -> np.ndarray:
        """(n, 3) → (n, 3) 화면 x · y(픽셀, 위가 0) · 깊이(클수록 멀다)."""
        rel = np.asarray(pts, dtype=np.float64) - self.focal
        k = self.px_per_unit
        x = self.width / 2.0 + (rel @ self.right) * k
        y = self.height / 2.0 - (rel @ self.up) * k
        z = rel @ self.direction
        return np.stack([x, y, z], axis=1)

    def to_vtk(self, distance: float) -> dict:
        """pyvista 카메라 값. distance 는 초점에서 카메라까지(평행 투영이라 그림에는 영향 없음, 자름면만)."""
        return {"focal_point": tuple(self.focal), "position": tuple(self.focal - self.direction * distance),
                "view_up": tuple(self.up), "parallel_scale": float(self.scale)}


def view_basis(view: str | tuple | np.ndarray, up=(0.0, 0.0, 1.0)) -> tuple[np.ndarray, np.ndarray]:
    """시점 이름 또는 시선 방향 벡터 → (시선 방향, 위쪽)."""
    if isinstance(view, str):
        if view not in _NAMED:
            raise ValueError(f"모르는 시점 {view!r} — {', '.join(_NAMED)} 또는 방향 벡터")
        d, u = _NAMED[view]
    else:
        d, u = view, up
    d = _unit(d)
    return d, _orthogonal_up(d, u)


def peak_view(normal: np.ndarray, iso_weight: float = 0.6) -> np.ndarray:
    """최대점이 보이는 시선 — 최대 요소 바깥 면 법선을 마주 보되, iso 쪽으로 기울여 입체감을 남긴다."""
    n = _unit(normal)
    d_iso = _unit(_NAMED["iso"][0])
    d = -n + iso_weight * d_iso
    if np.linalg.norm(d) < 1e-6:
        d = -n
    d = _unit(d)
    if d.dot(n) > -0.2:                                # 그래도 면을 마주 보게(뒤에서 보지 않게)
        d = _unit(-n)
    return d


def fit(points: np.ndarray, direction: np.ndarray, up: np.ndarray, width: int, height: int,
        margin: float = 1.08, right_frac: float = 0.0, top_frac: float = 0.0) -> Camera:
    """점들이 화면에 꽉 차게(평행 투영). 오른쪽 `right_frac`(범례) · 위 `top_frac`(제목) 는 비워 둔다."""
    pts = np.asarray(points, dtype=np.float64)
    if len(pts) == 0:
        raise ValueError("맞출 점이 없다")
    r = np.cross(direction, up)
    c = pts.mean(axis=0)
    x = (pts - c) @ r
    y = (pts - c) @ up
    wx = max(x.max() - x.min(), 1e-9)
    wy = max(y.max() - y.min(), 1e-9)
    avail_w = width * (1.0 - right_frac)
    avail_h = height * (1.0 - top_frac)
    # scale = 화면 높이의 절반(월드): 세로 · 가로 중 빠듯한 쪽에 맞춘다
    scale = max(wy * margin * height / (2.0 * avail_h), wx * margin * height / (2.0 * avail_w))
    bbox_c = c + r * (x.max() + x.min()) / 2.0 + up * (y.max() + y.min()) / 2.0
    k = (height / 2.0) / scale
    # 상자 가운데가 남은 자리의 가운데에 오게 초점을 옮긴다
    dx_px = width * (1.0 - right_frac) / 2.0 - width / 2.0
    dy_px = height * top_frac / 2.0                     # 화면 y 는 아래로 — 남은 자리 가운데는 아래로 치우친다
    focal = bbox_c - r * (dx_px / k) + up * (dy_px / k)
    return Camera(direction=direction, up=up, focal=focal, scale=float(scale), width=width, height=height)
