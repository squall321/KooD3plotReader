# 파트간 에너지 흐름 그래프를 binout+contact_map 에서 조립하는 중립 빌더 (impact/sphere 공용)
"""Assemble a time-varying energy-flow graph from binout + contact_map.

impact/sphere 리포트 공용이라 ``koo_impact_report`` 모델에 의존하지 않고
순수 dict 를 반환한다 (호출측이 EnergyFlow 로 변환). 노드=파트, 엣지=접촉
인터페이스. 모든 노드·엣지가 **동일한 공유 시간축**을 쓰도록 리샘플하여
JS 측이 단일 ``t_idx`` 로 전부 인덱싱할 수 있게 한다.

engaged 필터 관련 주의:
  스펙 초안은 "peak|F|>0 인 인터페이스만 edge 생성" 이었으나, 실측(Test_Impact_A)
  결과 **미접촉 run 에서도 솔버 잔류 접촉력이 ~0.5 N 까지 발생**한다. 순수
  ``peak|F|>0`` 은 이 잡음을 전부 engage 로 오판하여(run1 에서 21개) 25개
  파트 노드만 있어야 할 그래프에 유령 노드를 대량 주입한다. 따라서 접촉
  임펄스가 **임팩터 초기 운동량의 1% 이상**일 때만 engage 로 본다(단위 무관
  비율 기준: 미접촉 run≤0.5%, 접촉 run≥100%). 임팩터 운동량을 구할 수
  없으면(임팩터 미지정/정지 출발/rbvelocity 부재) ``peak|F|>0`` 로 폴백한다.
"""
from __future__ import annotations

import math
from collections import defaultdict, deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # 실제 소비는 duck-typing (getattr) — P2 구현 세부에 결합하지 않음
    from .contact_map import ContactMap  # noqa: F401

# 접촉 판정: 임펄스가 임팩터 초기 운동량의 이 비율 이상이면 engage
_ENGAGE_IMPULSE_REL = 0.01
# first_engage 및 폴백 판정에 쓰는 peak 대비 비율
_ENGAGE_FORCE_REL = 0.01


# ---------------------------------------------------------------------------
# 수치 유틸
# ---------------------------------------------------------------------------

def _r4(x: float) -> float:
    """4자리 반올림. NaN/inf 는 0 으로."""
    try:
        xf = float(x)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(xf):
        return 0.0
    return round(xf, 4)


def _rt(t: float) -> float:
    """시간축 전용 정규화 — 4dp 로 뭉개면 미세 dt 가 붕괴하므로 9dp 유지."""
    try:
        tf = float(t)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(tf):
        return 0.0
    return round(tf, 9)


def _peak_at(series, t_full) -> tuple[float | None, float | None]:
    """원해상도 시계열의 최대값과 그 시각. 값이 없으면 (None, None).

    다운샘플된 배열에서 max() 를 하면 참피크를 놓치므로, 요약 스칼라는 반드시
    이 함수로 원본에서 뽑는다. 빈 배열을 0.0 으로 채우지 않는 것도 규칙이다
    ('측정 안 됨' 과 '0 이었음' 은 다르다).
    """
    if not series:
        return None, None
    mi = 0
    mx = series[0]
    for a in range(1, len(series)):
        if series[a] > mx:
            mx, mi = series[a], a
    tt = t_full[mi] if mi < len(t_full) else None
    return _r4(mx), (_rt(tt) if tt is not None else None)


def _downsample_indices(n: int, max_pts: int, peak_idx: int | None = None) -> list[int]:
    """[0,n) 을 max_pts 이하로 다운샘플한 인덱스 집합.

    ceil 스텝 균등 샘플 + 마지막 인덱스(n-1) + peak 인덱스 splice.
    반환은 정렬된 유니크 인덱스.
    """
    if n <= 0:
        return []
    if n <= max_pts:
        return list(range(n))
    step = max(1, math.ceil(n / max_pts))
    idx = list(range(0, n, step))
    if (n - 1) not in idx:
        idx.append(n - 1)
    if peak_idx is not None and 0 <= peak_idx < n and peak_idx not in idx:
        idx.append(peak_idx)
    return sorted(set(idx))


def _cumtrapz(f: list[float], t: list[float]) -> list[float]:
    """누적 사다리꼴 적분. 길이는 입력과 동일, out[0]=0."""
    n = len(f)
    out = [0.0] * n
    for i in range(1, n):
        out[i] = out[i - 1] + 0.5 * (f[i] + f[i - 1]) * (t[i] - t[i - 1])
    return out


def _interp(xs: list[float], ys: list[float], x: float) -> float:
    """xs(오름차순) 위 ys 의 x 에서의 선형보간. 범위 밖은 양끝 값으로 클램프."""
    n = len(xs)
    if n == 0:
        return 0.0
    if n == 1 or x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    # 이분 탐색
    lo, hi = 0, n - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if xs[mid] <= x:
            lo = mid
        else:
            hi = mid
    x0, x1 = xs[lo], xs[hi]
    if x1 == x0:
        return ys[lo]
    w = (x - x0) / (x1 - x0)
    return ys[lo] + w * (ys[hi] - ys[lo])


def _resample(src_t: list[float], src_y: list[float], ref_t: list[float]) -> list[float]:
    """(src_t,src_y) 를 ref_t 축으로 선형 리샘플 후 4dp 반올림."""
    if not src_t or not src_y:
        return [0.0 for _ in ref_t]
    return [_r4(_interp(src_t, src_y, tt)) for tt in ref_t]


# ---------------------------------------------------------------------------
# contact_map 소비 (soft / duck-typed)
# ---------------------------------------------------------------------------

def _resolve_partref(pref, midx_by_pid: dict[int, int], part_names: dict[int, str],
                     pseudo: dict[str, str]) -> tuple[str, bool, int | None]:
    """PartRef → (node_id, is_real_part, matsum_index).

    실파트(matsum 에 존재)면 node_id=str(part_id) 로 실노드에 매핑, 아니면
    pseudo 노드로 등록하고 그 node_id 를 돌려준다.
    """
    kind = getattr(pref, "kind", "part")
    pid = getattr(pref, "part_id", None)
    if kind == "part" and pid is not None and int(pid) in midx_by_pid:
        pid = int(pid)
        return str(pid), True, midx_by_pid[pid]
    nid = getattr(pref, "node_id", None) or f"{kind}:{pid}"
    name = getattr(pref, "name", None) or nid
    pseudo[nid] = name
    return nid, False, None


# ---------------------------------------------------------------------------
# 메인 빌더
# ---------------------------------------------------------------------------

def build_flow_graph(binout, contact_map, part_names: dict[int, str],
                     impactor_pid: int | None, max_pts: int = 120) -> dict | None:
    """binout + contact_map → 중립 에너지 흐름 그래프 dict.

    조립 불가(matsum 없음 등)면 None 을 반환한다.
    """
    ms = getattr(binout, "matsum", None)
    if ms is None or not getattr(ms, "t", None) or not getattr(ms, "kinetic_energy", None):
        return None

    # --- 공유 시간축: matsum.t 에서 t<0 trim 후 다운샘플 ------------------
    t_raw = ms.t
    keep = [i for i, tt in enumerate(t_raw) if tt is not None and float(tt) >= 0.0]
    if not keep:
        return None
    t_full = [float(t_raw[i]) for i in keep]
    n_full = len(t_full)

    part_ids = list(ms.part_ids)
    midx_by_pid = {int(p): j for j, p in enumerate(part_ids)}

    ke = ms.kinetic_energy
    ie = ms.internal_energy if getattr(ms, "internal_energy", None) else []

    def _matsum_series(src2d, j):
        """[n_t][n_part] 2D 에서 파트 j 열을 t_full 축으로 뽑기."""
        if not src2d:
            return None
        out = []
        for i in keep:
            try:
                out.append(float(src2d[i][j]))
            except (IndexError, TypeError, ValueError):
                out.append(0.0)
        return out

    # --- rcforc 인터페이스 dedup (같은 interface_id 는 peak|F| 큰 side 채택) ---
    rcforc = list(getattr(binout, "rcforc", []) or [])
    best_iface: dict[int, object] = {}
    for r in rcforc:
        iid = int(getattr(r, "interface_id", -1))
        cur = best_iface.get(iid)
        if cur is None or r.peak_fmag > cur.peak_fmag:
            best_iface[iid] = r

    def _trim_iface(r):
        """인터페이스를 t>=0 로 trim 한 (t, fmag, fx, fy, fz) 반환."""
        rt = r.t
        kk = [i for i, tt in enumerate(rt) if tt is not None and float(tt) >= 0.0]
        fm = r.fmag
        return (
            [float(rt[i]) for i in kk],
            [float(fm[i]) for i in kk],
            [float(r.fx[i]) for i in kk],
            [float(r.fy[i]) for i in kk],
            [float(r.fz[i]) for i in kk],
        )

    # --- 임팩터 초기 운동량 (engage 판정 기준) ----------------------------
    p0 = None
    if impactor_pid is not None and int(impactor_pid) in midx_by_pid:
        j = midx_by_pid[int(impactor_pid)]
        vx = ms.x_rbvelocity
        vy = ms.y_rbvelocity
        vz = ms.z_rbvelocity
        if vx and vy and vz:
            try:
                i0 = keep[0]
                v0 = math.sqrt(vx[i0][j] ** 2 + vy[i0][j] ** 2 + vz[i0][j] ** 2)
                ke0 = float(ke[i0][j])
                if v0 > 1e-30 and ke0 > 0:
                    p0 = 2.0 * ke0 / v0  # m*v = 2*(0.5 m v^2)/v
            except (IndexError, TypeError, ValueError):
                p0 = None

    # --- peak splice 인덱스: 전 인터페이스 합력의 t_full 상 argmax ---------
    peak_idx = None
    if best_iface:
        total_f = [0.0] * n_full
        for r in best_iface.values():
            rt, fm, *_ = _trim_iface(r)
            if not rt:
                continue
            for a, tt in enumerate(t_full):
                total_f[a] += _interp(rt, fm, tt)
        mx = -1.0
        for a, v in enumerate(total_f):
            if v > mx:
                mx, peak_idx = v, a

    idx = _downsample_indices(n_full, max_pts, peak_idx)
    ref_t = [_rt(t_full[i]) for i in idx]

    # --- 노드: matsum 파트별 ---------------------------------------------
    nodes: list[dict] = []
    node_ke0: dict[str, float] = {}
    node_ids_real: set[str] = set()
    for pid in part_ids:
        pid = int(pid)
        j = midx_by_pid[pid]
        ke_s = _matsum_series(ke, j) or [0.0] * n_full
        ie_s = _matsum_series(ie, j)
        name = part_names.get(pid) or f"Part_{pid}"
        is_imp = impactor_pid is not None and pid == int(impactor_pid)
        if is_imp and not part_names.get(pid):
            name = "Impactor"
        nid = str(pid)
        # 스칼라는 **다운샘플 이전 원해상도**에서 뽑는다. kinetic_ts/internal_ts 는
        # max_pts 로 솎은 것이라 그 위에서 max() 를 하면 참피크를 놓친다
        # (프로젝트 공통 규칙 — 시계열 요약은 항상 원해상도 선계산).
        ke_pk, ke_pt = _peak_at(ke_s, t_full)
        ie_pk, ie_pt = _peak_at(ie_s, t_full)
        nodes.append({
            "node_id": nid,
            "name": name,
            "is_impactor": is_imp,
            "times": list(ref_t),
            "kinetic_ts": [_r4(ke_s[i]) for i in idx],
            "internal_ts": ([_r4(ie_s[i]) for i in idx] if ie_s else []),
            # 파트별 에너지 요약 (원해상도). 값이 없으면 0 으로 채우지 않고 None.
            "peak_ke": ke_pk,
            "peak_ke_time": ke_pt,
            "peak_ie": ie_pk,
            "peak_ie_time": ie_pt,
            # 최종 내부에너지 = 그 파트가 끝까지 흡수하고 남은 양 (탄성 복원분 제외).
            # 피크와 다르므로 둘 다 싣는다 — 피크만 보면 되튐을 흡수로 오독한다.
            "final_ie": (_r4(ie_s[-1]) if ie_s else None),
            "final_ke": (_r4(ke_s[-1]) if ke_s else None),
        })
        node_ke0[nid] = float(ke_s[0]) if ke_s else 0.0
        node_ids_real.add(nid)

    # --- 엣지 후보 조립 (방향은 BFS 후 결정) ------------------------------
    pseudo: dict[str, str] = {}
    endpoints_map = getattr(contact_map, "endpoints", None) if contact_map is not None else None

    # 각 후보: node_a=slave, node_b=master (contact_map 기준), 유령이면 iface 노드
    raw_edges: list[dict] = []
    for iid, r in best_iface.items():
        rt, fm, fx, fy, fz = _trim_iface(r)
        if not rt:
            continue
        peak_force = max(fm) if fm else 0.0
        if peak_force <= 0:
            continue
        cimp_full = _cumtrapz(fm, rt)
        total_impulse = cimp_full[-1] if cimp_full else 0.0

        # engage 판정
        if p0 is not None:
            engaged = total_impulse > _ENGAGE_IMPULSE_REL * p0
        else:
            engaged = peak_force > 0.0
        if not engaged:
            continue

        # 엔드포인트 매핑
        ep = endpoints_map.get(iid) if endpoints_map else None
        if ep is not None:
            a_id, a_real, a_idx = _resolve_partref(getattr(ep, "slave", None),
                                                   midx_by_pid, part_names, pseudo)
            b_id, b_real, b_idx = _resolve_partref(getattr(ep, "master", None),
                                                   midx_by_pid, part_names, pseudo)
            confidence = float(getattr(ep, "confidence", 0.0) or 0.0)
            ename = getattr(ep, "name", None) or getattr(r, "name", f"Interface_{iid}")
        else:
            a_id = f"iface:{iid}_a"
            b_id = f"iface:{iid}_b"
            a_real = b_real = False
            a_idx = b_idx = None
            pseudo[a_id] = getattr(r, "name", f"Interface_{iid}")
            pseudo[b_id] = getattr(r, "name", f"Interface_{iid}")
            confidence = 0.0
            ename = getattr(r, "name", f"Interface_{iid}")

        raw_edges.append({
            "iid": iid, "a_id": a_id, "b_id": b_id,
            "a_real": a_real, "b_real": b_real, "a_idx": a_idx, "b_idx": b_idx,
            "rt": rt, "fm": fm, "fx": fx, "fy": fy, "fz": fz,
            "cimp_full": cimp_full, "peak_force": peak_force,
            "total_impulse": total_impulse, "confidence": confidence, "name": ename,
        })

    # --- BFS: 깊이/전파 순서 ---------------------------------------------
    adj: dict[str, set[str]] = defaultdict(set)
    for e in raw_edges:
        adj[e["a_id"]].add(e["b_id"])
        adj[e["b_id"]].add(e["a_id"])

    # 루트 결정: 임팩터 노드 우선, 없으면 최조기 engage 엣지의 고KE 엔드포인트
    root = None
    if impactor_pid is not None and str(int(impactor_pid)) in node_ke0:
        root = str(int(impactor_pid))
    elif raw_edges:
        def _first_engage_time(e):
            thr = _ENGAGE_FORCE_REL * e["peak_force"]
            for tt, f in zip(e["rt"], e["fm"]):
                if f > thr:
                    return tt
            return e["rt"][0]
        e0 = min(raw_edges, key=_first_engage_time)
        cands = [e0["a_id"], e0["b_id"]]
        root = max(cands, key=lambda nid: node_ke0.get(nid, -1.0))

    depth_map: dict[str, int] = {}
    prop_order: list[str] = []
    if root is not None:
        depth_map[root] = 0
        prop_order.append(root)
        q = deque([root])
        while q:
            u = q.popleft()
            for v in sorted(adj.get(u, ())):
                if v not in depth_map:
                    depth_map[v] = depth_map[u] + 1
                    prop_order.append(v)
                    q.append(v)

    _INF = 10 ** 9

    # --- 엣지 최종화: 방향 + 리샘플 + work ------------------------------
    edges: list[dict] = []
    for e in raw_edges:
        a_id, b_id = e["a_id"], e["b_id"]
        da = depth_map.get(a_id, _INF)
        db = depth_map.get(b_id, _INF)
        if da < db:
            src_id, dst_id = a_id, b_id
        elif db < da:
            src_id, dst_id = b_id, a_id
        else:
            # 동일 depth(또는 둘 다 미도달) → master(b) → slave(a)
            src_id, dst_id = b_id, a_id

        # src/dst 의 실파트 여부·matsum 인덱스
        if src_id == a_id:
            src_real, src_idx, dst_real, dst_idx = e["a_real"], e["a_idx"], e["b_real"], e["b_idx"]
        else:
            src_real, src_idx, dst_real, dst_idx = e["b_real"], e["b_idx"], e["a_real"], e["a_idx"]

        rt, fm = e["rt"], e["fm"]
        force_mag_ts = _resample(rt, fm, ref_t)
        impulse_cum_ts = _resample(rt, e["cimp_full"], ref_t)

        # first_engage_idx: ref 축에서 |F| 가 peak 의 1% 를 처음 넘는 인덱스
        thr = _ENGAGE_FORCE_REL * e["peak_force"]
        first_engage_idx = 0
        for k, f in enumerate(force_mag_ts):
            if f > thr:
                first_engage_idx = k
                break

        # work: 양끝이 실파트 + rbvelocity 존재일 때만
        work_cum_ts: list[float] = []
        total_work = 0.0
        if src_real and dst_real and src_idx is not None and dst_idx is not None \
                and ms.x_rbvelocity and ms.y_rbvelocity and ms.z_rbvelocity:
            fx_f = [_interp(rt, e["fx"], tt) for tt in t_full]
            fy_f = [_interp(rt, e["fy"], tt) for tt in t_full]
            fz_f = [_interp(rt, e["fz"], tt) for tt in t_full]
            power = []
            for a, gi in enumerate(keep):
                dvx = float(ms.x_rbvelocity[gi][src_idx]) - float(ms.x_rbvelocity[gi][dst_idx])
                dvy = float(ms.y_rbvelocity[gi][src_idx]) - float(ms.y_rbvelocity[gi][dst_idx])
                dvz = float(ms.z_rbvelocity[gi][src_idx]) - float(ms.z_rbvelocity[gi][dst_idx])
                power.append(fx_f[a] * dvx + fy_f[a] * dvy + fz_f[a] * dvz)
            work_full = _cumtrapz(power, t_full)
            total_work = work_full[-1] if work_full else 0.0
            work_cum_ts = [_r4(work_full[i]) for i in idx]

        edges.append({
            "src": src_id, "dst": dst_id, "contact_id": e["iid"], "name": e["name"],
            "times": list(ref_t),
            "force_mag_ts": force_mag_ts,
            "impulse_cum_ts": impulse_cum_ts,
            "work_cum_ts": work_cum_ts,
            "peak_force": _r4(e["peak_force"]),
            "total_impulse": _r4(e["total_impulse"]),
            "total_work": _r4(total_work),
            "confidence": _r4(e["confidence"]),
            "first_engage_idx": first_engage_idx,
        })

    # --- 유령 노드 추가 (kinetic_ts/internal_ts 빈 배열) ------------------
    existing = {n["node_id"] for n in nodes}
    for nid, pname in pseudo.items():
        if nid in existing:
            continue
        nodes.append({
            "node_id": nid, "name": pname, "is_impactor": False,
            "times": [], "kinetic_ts": [], "internal_ts": [],
        })

    # --- 스칼라 -----------------------------------------------------------
    glstat = getattr(binout, "glstat", None)

    def _last(seq):
        return float(seq[-1]) if seq else 0.0

    def _first(seq):
        return float(seq[0]) if seq else 0.0

    if glstat is not None and getattr(glstat, "kinetic_energy", None):
        impactor_ke_initial = _first(glstat.kinetic_energy)
    else:
        impactor_ke_initial = sum(float(v) for v in ke[keep[0]]) if ke else 0.0

    if impactor_pid is not None and str(int(impactor_pid)) in {n["node_id"] for n in nodes}:
        j = midx_by_pid[int(impactor_pid)]
        impactor_ke_final = float(ke[keep[-1]][j])
    else:
        impactor_ke_final = sum(float(v) for v in ke[keep[-1]]) if ke else 0.0

    if glstat is not None:
        energy_dissipated = (
            abs(_last(getattr(glstat, "sliding_interface_energy", [])))
            + abs(_last(getattr(glstat, "hourglass_energy", [])))
            + abs(_last(getattr(glstat, "system_damping_energy", [])))
            + abs(_last(getattr(glstat, "eroded_kinetic_energy", [])))
        )
    else:
        hg = ms.hourglass_energy if getattr(ms, "hourglass_energy", None) else []
        energy_dissipated = sum(abs(float(v)) for v in hg[keep[-1]]) if hg else 0.0

    return {
        "nodes": nodes,
        "edges": edges,
        "impactor_ke_initial": _r4(impactor_ke_initial),
        "impactor_ke_final": _r4(impactor_ke_final),
        "energy_dissipated": _r4(energy_dissipated),
        "depth_map": depth_map,
        "propagation_order": prop_order,
    }
