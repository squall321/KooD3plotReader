# 스냅샷 장면 — 타겟 · 주변 · 숨김 파트, 색 범위, 최대점, 카메라를 한 번 정해 PNG 와 SVG 가 함께 쓴다
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import camera as C
from . import colors as K
from .mesh import SHELL, StateSurface


@dataclass
class Scene:
    surf: StateSurface
    target_mask: np.ndarray            # 응력 색으로 그릴 면
    context_mask: np.ndarray           # 반투명 회색으로 그릴 면
    cam: C.Camera
    clim: tuple[float, float]
    peak_face: int                     # 타겟 면 중 최대 값 면의 순번(전체 면 기준), 없으면 −1
    peak_value: float                  # 그 면의 값 — 바깥 면 최대(최대점 표시 자리)
    peak_point: np.ndarray
    view: str
    context_opacity: float = 0.15
    targets: list[int] = field(default_factory=list)
    hidden: list[int] = field(default_factory=list)
    #: 타겟 파트 모든 요소의 최대(안쪽 포함). 제목 · manifest 값은 이것이다. peak_value 보다 크면 최대 요소가 안에 있다
    value_max: float = float("nan")

    @property
    def peak_inside(self) -> bool:
        """최대 요소가 바깥 면에 없다(그림에 보이는 최대점이 실제 최대보다 작다)."""
        return bool(np.isfinite(self.value_max) and np.isfinite(self.peak_value)
                    and self.value_max > self.peak_value * (1 + 1e-9) + 1e-12)


def face_normals(coords: np.ndarray, faces: np.ndarray) -> np.ndarray:
    p0, p1, p2 = coords[faces[:, 0]], coords[faces[:, 1]], coords[faces[:, 2]]
    return np.cross(p1 - p0, p2 - p0)


def face_centers(coords: np.ndarray, faces: np.ndarray) -> np.ndarray:
    tri = faces[:, 3] < 0
    s = coords[faces[:, 0]] + coords[faces[:, 1]] + coords[faces[:, 2]]
    quad4 = coords[np.where(tri, faces[:, 0], faces[:, 3])]
    return np.where(tri[:, None], s / 3.0, (s + quad4) / 4.0)


def build(surf: StateSurface, targets: list[int] | None, hidden: list[int] | None = None, *,
          view: str = "iso", width: int = 1600, height: int = 1100, clim: str | float = "p99.5",
          context_opacity: float = 0.15, right_frac: float = 0.15, top_frac: float = 0.09,
          margin: float = 1.06) -> Scene:
    """targets 가 비면 보이는 파트 전부가 타겟(전체 뷰). view — 'iso' 등 이름, 또는 'peak'(최대점이 보이는 시점)."""
    hidden = sorted(set(hidden or []))
    visible = ~surf.part_mask(hidden) if hidden else np.ones(len(surf.faces), bool)
    targets = sorted(set(targets or [])) or sorted(set(int(p) for p in np.unique(surf.face_part[visible])))
    tmask = surf.part_mask(targets) & visible
    if not tmask.any():
        raise ValueError(f"타겟 파트 {targets} 의 면이 없다(숨긴 파트 {hidden})")
    cmask = visible & ~tmask

    vals = surf.face_value
    tv = np.where(tmask & np.isfinite(vals), vals, -np.inf)
    if np.isfinite(tv).any() and tv.max() > -np.inf:
        peak = int(np.argmax(tv))
        peak_val = float(vals[peak])
    else:
        peak, peak_val = -1, float("nan")
    lo_hi = K.color_range(vals[tmask], clim) if np.isfinite(vals[tmask]).any() else (0.0, 1.0)
    centers = face_centers(surf.coords, surf.faces)
    peak_pt = centers[peak] if peak >= 0 else centers[tmask].mean(axis=0)

    if view == "peak" and peak >= 0:
        n = face_normals(surf.coords, surf.faces[peak:peak + 1])[0]
        if surf.face_kind[peak] == SHELL:              # 셸은 앞뒤가 없다 — iso 와 같은 쪽 면을 본다
            d_iso, _ = C.view_basis("iso")
            n = n if n.dot(d_iso) < 0 else -n
        d, u = C.view_basis(C.peak_view(n))
    else:
        d, u = C.view_basis("iso" if view == "peak" else view)
    pm = [surf.part_max[int(p)] for p in np.unique(surf.face_part[tmask]) if int(p) in surf.part_max]
    vmax = max(pm) if pm else peak_val
    pts = surf.coords[surf.nodes_of(tmask)]
    cam = C.fit(pts, d, u, width, height, margin=margin, right_frac=right_frac, top_frac=top_frac)
    return Scene(surf=surf, target_mask=tmask, context_mask=cmask, cam=cam, clim=lo_hi, peak_face=peak,
                 peak_value=peak_val, peak_point=peak_pt, view=view, context_opacity=context_opacity,
                 targets=targets, hidden=hidden, value_max=float(vmax))
