# d3plot 한 상태를 lasso 로 읽어 파트별 바깥 면 · 요소 von Mises · 바닥 후보를 만드는 모듈
"""그림 꾸러미의 데이터 쪽. d3plot 전체가 아니라 **고른 상태 하나만** 읽는다(lasso `state_filter` + `buffered_reading`).

바깥 면 규칙(C++ 소프트웨어 렌더러 · S1 과 같은 생각)
- 솔리드 8절점 꼴을 고유 절점으로 가른다. 사면체 `N1 N2 N3 N4 N4 N4 N4 N4` 는 **실제 면 4개**로 만든다 — 육면체 면으로
  세면 (N1,N2,N3,N4) 라는 있지도 않은 면이 생긴다(실제로 틀렸던 자리). 오면체 · 피라미드 · 다른 퇴화 꼴은 육면체 면에서 겹친
  절점을 지우면 맞는 면이 된다.
- 두꺼운 셸은 솔리드처럼, 셸은 그 자체가 면이다.
- 바깥 면은 **파트마다** 한 번만 나오는 면이다 — 파트끼리 절점을 나눠 써도 각 파트가 닫힌 껍질이 되어 반투명일 때 경계가 보인다.
- 삭제된 요소는 뺀다.
- 면의 감김은 바깥을 향하게 맞춘다(요소 중심에서 면 중심 쪽) — SVG 가 뒷면을 걸러 다각형 수를 반으로 줄인다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

_HEX_FACES = np.array([[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4],
                       [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]])
SOLID, SHELL, TSHELL = 0, 1, 2


@dataclass
class StateSurface:
    """한 상태의 바깥 면. 면마다 절점 4개(삼각형이면 넷째가 −1)."""
    coords: np.ndarray            # (n_nodes, 3) 그 상태의 현재 좌표
    faces: np.ndarray             # (n_faces, 4) 절점 순번, 삼각형은 [..., -1]
    face_part: np.ndarray         # (n_faces,) 파트 번호(PID)
    face_value: np.ndarray        # (n_faces,) 소유 요소의 von Mises (덱 단위), 없으면 nan
    face_elem: np.ndarray         # (n_faces,) 소유 요소의 실제 번호
    face_kind: np.ndarray         # (n_faces,) SOLID · SHELL · TSHELL
    state_index: int
    time: float
    part_titles: dict[int, str] = field(default_factory=dict)
    #: 파트마다 그 상태의 von Mises 최대 — 바깥 면만이 아니라 살아 있는 **모든 요소**에서(안쪽 요소가 최대일 수 있다)
    part_max: dict[int, float] = field(default_factory=dict)

    def parts(self) -> list[int]:
        return sorted(int(p) for p in np.unique(self.face_part))

    def part_mask(self, pids) -> np.ndarray:
        return np.isin(self.face_part, np.asarray(list(pids), dtype=self.face_part.dtype))

    def nodes_of(self, mask) -> np.ndarray:
        f = self.faces[mask]
        return np.unique(f[f >= 0])


def von_mises(stress: np.ndarray) -> np.ndarray:
    """(..., 6) xx yy zz xy yz zx → von Mises."""
    s = stress.astype(np.float64)
    sx, sy, sz, sxy, syz, szx = (s[..., i] for i in range(6))
    return np.sqrt(0.5 * ((sx - sy) ** 2 + (sy - sz) ** 2 + (sz - sx) ** 2)
                   + 3.0 * (sxy ** 2 + syz ** 2 + szx ** 2))


def _layer_max_vm(stress) -> np.ndarray | None:
    """(n_elem, n_layers, 6) 또는 (n_elem, 6) → 요소별 von Mises(층이 여럿이면 최대). 없으면 None."""
    if stress is None:
        return None
    a = np.asarray(stress)
    vm = von_mises(a)
    return vm.max(axis=1) if vm.ndim == 2 else vm


def _dedupe_faces(f: np.ndarray) -> np.ndarray:
    """(n, 4) 면에서 겹친 절점을 지운다(순서 유지). 3개면 삼각형(넷째 −1), 3개 미만이면 전부 −1."""
    a, b, c, d = f[:, 0], f[:, 1], f[:, 2], f[:, 3]
    keep = np.stack([np.ones(len(f), bool), b != a, (c != a) & (c != b),
                     (d != a) & (d != b) & (d != c)], axis=1)
    out = np.full_like(f, -1)
    cnt = keep.sum(axis=1)
    order = np.argsort(~keep, axis=1, kind="stable")      # 남길 것을 앞으로
    packed = np.take_along_axis(f, order, axis=1)
    for k in (3, 4):
        m = cnt == k
        out[m, :k] = packed[m, :k]
    return out


def solid_faces(conn: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(n, 8) 솔리드 → (면 (m, 4), 소유 요소 순번 (m,)). 퇴화 면은 버린다."""
    n = len(conn)
    if n == 0:
        return np.zeros((0, 4), np.int64), np.zeros(0, np.int64)
    tet = (conn[:, 3] == conn[:, 4]) & (conn[:, 4] == conn[:, 5]) & \
          (conn[:, 5] == conn[:, 6]) & (conn[:, 6] == conn[:, 7]) & (conn[:, 2] != conn[:, 3])
    faces, owner = [], []
    hx = np.nonzero(~tet)[0]
    if len(hx):
        f = conn[hx][:, _HEX_FACES].reshape(-1, 4)
        faces.append(_dedupe_faces(f))
        owner.append(np.repeat(hx, 6))
    tt = np.nonzero(tet)[0]
    if len(tt):
        a, b, c, d = (conn[tt, i] for i in range(4))
        m1 = np.full(len(tt), -1)
        f = np.stack([np.stack([a, c, b, m1], 1), np.stack([a, b, d, m1], 1),
                      np.stack([b, c, d, m1], 1), np.stack([c, a, d, m1], 1)], axis=1).reshape(-1, 4)
        faces.append(f)
        owner.append(np.repeat(tt, 4))
    faces = np.concatenate(faces)
    owner = np.concatenate(owner)
    ok = faces[:, 2] >= 0
    return faces[ok], owner[ok]


def exterior(faces: np.ndarray, owner: np.ndarray, owner_part: np.ndarray) -> np.ndarray:
    """파트마다 한 번만 나오는 면의 마스크."""
    if len(faces) == 0:
        return np.zeros(0, bool)
    key = np.sort(np.where(faces < 0, np.iinfo(np.int64).max, faces), axis=1)
    key = np.concatenate([owner_part[owner][:, None].astype(np.int64), key], axis=1)
    _, inv, cnt = np.unique(key, axis=0, return_inverse=True, return_counts=True)
    return cnt[inv.ravel()] == 1


def orient_outward(faces: np.ndarray, coords: np.ndarray, centers: np.ndarray) -> np.ndarray:
    """면 법선이 소유 요소 중심에서 멀어지게 감김을 뒤집는다(삼각형 · 사각형 모두)."""
    p0, p1, p2 = coords[faces[:, 0]], coords[faces[:, 1]], coords[faces[:, 2]]
    n = np.cross(p1 - p0, p2 - p0)
    tri = faces[:, 3] < 0
    fc = np.where(tri[:, None], (p0 + p1 + p2) / 3.0,
                  (p0 + p1 + p2 + coords[np.where(tri, faces[:, 0], faces[:, 3])]) / 4.0)
    flip = np.einsum("ij,ij->i", n, fc - centers) < 0
    out = faces.copy()
    q = flip & ~tri
    out[q] = out[q][:, ::-1]
    t = flip & tri
    out[t, :3] = out[t][:, 2::-1]
    return out


def read_state(d3plot: str | Path, state_index: int) -> StateSurface:
    """d3plot 의 상태 하나 → 파트별 바깥 면. lasso 가 필요하다."""
    from lasso.dyna import ArrayType as A, D3plot

    want = [A.node_displacement, A.element_solid_stress, A.element_shell_stress, A.element_tshell_stress,
            A.element_solid_is_alive, A.element_shell_is_alive, A.element_tshell_is_alive, A.global_timesteps]
    d = D3plot(str(d3plot), state_filter={int(state_index)}, buffered_reading=True, state_array_filter=want)
    arr = d.arrays
    if A.node_displacement not in arr or len(arr[A.node_displacement]) == 0:
        raise ValueError(f"상태 {state_index} 를 읽지 못했다 — d3plot 에 그 상태가 없다")
    coords = np.asarray(arr[A.node_displacement][0], dtype=np.float64)   # lasso: 현재 좌표
    t = float(np.asarray(arr.get(A.global_timesteps, [np.nan]))[0])
    pids = np.asarray(arr.get(A.part_ids, arr.get(A.part_titles_ids)))
    titles = {}
    if A.part_titles in arr and A.part_titles_ids in arr:
        for pid, tt in zip(arr[A.part_titles_ids], arr[A.part_titles]):
            s = tt.decode("utf-8", "replace") if isinstance(tt, bytes) else str(tt)
            titles[int(pid)] = s.strip()

    all_f, all_part, all_val, all_elem, all_kind = [], [], [], [], []
    part_max: dict[int, float] = {}

    def note_max(part_of, vm_of):
        """파트별 요소 최대를 part_max 에 더한다."""
        if vm_of is None:
            return
        ok = np.isfinite(vm_of)
        p, v = part_of[ok], vm_of[ok]
        if not len(p):
            return
        order = np.argsort(p, kind="stable")
        u, start = np.unique(p[order], return_index=True)
        for pid, m in zip(u.tolist(), np.maximum.reduceat(v[order], start).tolist()):
            part_max[int(pid)] = max(m, part_max.get(int(pid), -np.inf))

    def add_volume(conn_key, part_key, id_key, stress_key, alive_key, kind):
        if conn_key not in arr:
            return
        conn = np.asarray(arr[conn_key], dtype=np.int64)
        part = pids[np.asarray(arr[part_key], dtype=np.int64)]
        ids = np.asarray(arr.get(id_key, np.arange(1, len(conn) + 1)))
        vm = _layer_max_vm(arr[stress_key][0] if stress_key in arr else None)
        alive = np.asarray(arr[alive_key][0]) != 0 if alive_key in arr else np.ones(len(conn), bool)
        live = np.nonzero(alive)[0]
        note_max(part[live], vm[live] if vm is not None else None)
        f, own = solid_faces(conn[live])
        own = live[own]
        ext = exterior(f, own, part)
        f, own = f[ext], own[ext]
        centers = coords[conn[own]].mean(axis=1)
        f = orient_outward(f, coords, centers)
        all_f.append(f); all_part.append(part[own]); all_elem.append(ids[own]); all_kind.append(np.full(len(f), kind))
        all_val.append(vm[own] if vm is not None else np.full(len(f), np.nan))

    add_volume(A.element_solid_node_indexes, A.element_solid_part_indexes, A.element_solid_ids,
               A.element_solid_stress, A.element_solid_is_alive, SOLID)
    add_volume(A.element_tshell_node_indexes, A.element_tshell_part_indexes, A.element_tshell_ids,
               A.element_tshell_stress, A.element_tshell_is_alive, TSHELL)
    if A.element_shell_node_indexes in arr:
        conn = np.asarray(arr[A.element_shell_node_indexes], dtype=np.int64)
        part = pids[np.asarray(arr[A.element_shell_part_indexes], dtype=np.int64)]
        ids = np.asarray(arr.get(A.element_shell_ids, np.arange(1, len(conn) + 1)))
        vm = _layer_max_vm(arr[A.element_shell_stress][0] if A.element_shell_stress in arr else None)
        alive = (np.asarray(arr[A.element_shell_is_alive][0]) != 0 if A.element_shell_is_alive in arr
                 else np.ones(len(conn), bool))
        live = np.nonzero(alive)[0]
        note_max(part[live], vm[live] if vm is not None else None)
        f = _dedupe_faces(conn[live])
        ok = f[:, 2] >= 0
        live, f = live[ok], f[ok]
        all_f.append(f); all_part.append(part[live]); all_elem.append(ids[live])
        all_kind.append(np.full(len(f), SHELL))
        all_val.append(vm[live] if vm is not None else np.full(len(f), np.nan))

    if not all_f:
        raise ValueError("그릴 면이 없다 — 솔리드 · 셸 요소가 없는 d3plot")
    return StateSurface(coords=coords, faces=np.concatenate(all_f), face_part=np.concatenate(all_part).astype(np.int64),
                        face_value=np.concatenate(all_val).astype(np.float64),
                        face_elem=np.concatenate(all_elem).astype(np.int64),
                        face_kind=np.concatenate(all_kind).astype(np.int8),
                        state_index=int(state_index), time=t, part_titles=titles, part_max=part_max)


def environment_parts(surf: StateSurface, factor: float = 1.5, min_axes: int = 2) -> list[int]:
    """바닥 · 벽 같은 환경 파트 — 다른 파트를 다 합친 상자보다 `min_axes` 축 이상에서 `factor` 배 넘게 큰 파트.

    make_stl 의 기기/환경 가르기와 같은 규칙이다. 파트가 하나뿐이면 없다.
    """
    boxes = {}
    for p in surf.parts():
        xyz = surf.coords[surf.nodes_of(surf.face_part == p)]
        boxes[p] = (xyz.min(axis=0), xyz.max(axis=0))
    return _env_from_boxes(boxes, factor, min_axes)


def environment_parts_d3plot(d3plot: str | Path, factor: float = 1.5, min_axes: int = 2) -> list[int]:
    """d3plot 의 초기 형상만으로 환경 파트(바닥) — 영상 숨김(`--hide-floor`)용. 상태 값은 읽지 않는다(lasso)."""
    from lasso.dyna import ArrayType as A, D3plot

    d = D3plot(str(d3plot), state_filter={0}, buffered_reading=True, state_array_filter=[A.global_timesteps])
    arr = d.arrays
    xyz = np.asarray(arr[A.node_coordinates], dtype=np.float64)
    pids = np.asarray(arr.get(A.part_ids, arr.get(A.part_titles_ids)))
    boxes: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    for conn_key, part_key in ((A.element_solid_node_indexes, A.element_solid_part_indexes),
                               (A.element_tshell_node_indexes, A.element_tshell_part_indexes),
                               (A.element_shell_node_indexes, A.element_shell_part_indexes)):
        if conn_key not in arr:
            continue
        conn = np.asarray(arr[conn_key], dtype=np.int64)
        part = pids[np.asarray(arr[part_key], dtype=np.int64)]
        order = np.argsort(part, kind="stable")
        ps, starts = np.unique(part[order], return_index=True)
        ends = list(starts[1:]) + [len(order)]
        for p, a, b in zip(ps.tolist(), starts.tolist(), ends):
            nodes = np.unique(conn[order[a:b]])
            lo, hi = xyz[nodes].min(axis=0), xyz[nodes].max(axis=0)
            if p in boxes:
                lo, hi = np.minimum(lo, boxes[p][0]), np.maximum(hi, boxes[p][1])
            boxes[int(p)] = (lo, hi)
    return _env_from_boxes(boxes, factor, min_axes)


def _env_from_boxes(boxes: dict, factor: float, min_axes: int) -> list[int]:
    """{파트: (최소, 최대)} → 환경 파트. 파트가 하나뿐이면 없다."""
    pids = sorted(boxes)
    if len(pids) < 2:
        return []
    out = []
    for p in pids:
        others = [boxes[q] for q in pids if q != p]
        lo = np.min([b[0] for b in others], axis=0)
        hi = np.max([b[1] for b in others], axis=0)
        ext_o = np.maximum(hi - lo, 1e-12)
        ext_p = boxes[p][1] - boxes[p][0]
        if int(np.sum(ext_p > factor * ext_o)) >= min_axes:
            out.append(p)
    return out
