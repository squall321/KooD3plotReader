"""Energy-flow analysis for partial-impact DOE cases (§22).

Models the impactor → device energy transfer as a time-varying knowledge
graph. Nodes = impactor + parts; edges = contact interfaces (one per
``CONTACT_AUTO_DECOMPOSITION``-produced pair).

The ``build_energy_flow`` function below is a stub awaiting binout
integration. All helper functions are fully implemented and operate on the
``EnergyFlow`` data model directly, so they're ready to use once flows are
populated.
"""
from __future__ import annotations
import math
from collections import defaultdict, deque
from pathlib import Path
from types import SimpleNamespace

from .models import (
    EnergyEdge, EnergyFlow, EnergyGraphFrame, EnergyNode, PartInfo,
)


# ---------------------------------------------------------------------------
# Builder — koo_deep_report.core.energy_flow_builder 로 위임 후 모델 변환
# ---------------------------------------------------------------------------

def build_energy_flow_from_binout(
    bin_data: dict,
    part_names: dict[int, str],
    impactor_pid: int | None,
    kfile: Path | None = None,
    max_pts: int = 120,
) -> EnergyFlow | None:
    """binout(dict) + keyword 접촉맵 → EnergyFlow.

    ``bin_data`` 는 loader.load_binout_energy 반환 dict(matsum/rcforc/glstat).
    contact_map 은 ``kfile`` 이 주어지면 소프트 로드 — 없거나 실패하면 None
    (빌더가 pseudo 노드로 정직 강등). 조립 불가 시 None 을 반환해 downstream
    이 빈 그래프를 "ok" 로 오인하지 않게 한다.
    """
    try:
        from koo_deep_report.core.energy_flow_builder import build_flow_graph
    except Exception:
        return None

    matsum = bin_data.get("matsum")
    if matsum is None:
        return None

    # contact_map 소프트 로드 (P2 모듈이 아직 없거나 .k 부재면 None)
    contact_map = None
    if kfile is not None:
        try:
            from koo_deep_report.core.contact_map import parse_contact_map
            contact_map = parse_contact_map(Path(kfile), part_names=part_names)
        except Exception:
            contact_map = None

    # build_flow_graph 는 binout.matsum/.rcforc/.glstat 접근 — dict 를 감싼다
    binout_obj = SimpleNamespace(
        matsum=matsum,
        rcforc=bin_data.get("rcforc") or [],
        glstat=bin_data.get("glstat"),
    )
    try:
        g = build_flow_graph(binout_obj, contact_map, part_names,
                             impactor_pid, max_pts=max_pts)
    except Exception:
        return None
    if not g or not g.get("nodes"):
        return None

    nodes = [
        EnergyNode(
            node_id=n["node_id"],
            name=n.get("name", n["node_id"]),
            is_impactor=bool(n.get("is_impactor")),
            kinetic_ts=list(n.get("kinetic_ts") or []),
            internal_ts=list(n.get("internal_ts") or []),
            times=list(n.get("times") or []),
        )
        for n in g["nodes"]
    ]
    edges = [
        EnergyEdge(
            src=e["src"], dst=e["dst"],
            contact_id=int(e.get("contact_id", -1)),
            name=e.get("name", ""),
            confidence=float(e.get("confidence", 1.0)),
            times=list(e.get("times") or []),
            force_mag_ts=list(e.get("force_mag_ts") or []),
            impulse_cum_ts=list(e.get("impulse_cum_ts") or []),
            work_cum_ts=list(e.get("work_cum_ts") or []),
            peak_force=float(e.get("peak_force", 0.0)),
            total_impulse=float(e.get("total_impulse", 0.0)),
            total_work=float(e.get("total_work", 0.0)),
        )
        for e in g["edges"]
    ]
    # 빌더의 propagation_order 는 BFS 순서 node_id 리스트(list[str]) —
    # 모델은 (node_id, weight) 튜플 리스트를 기대하므로 depth 를 weight 로 붙인다.
    _depth = {k: int(v) for k, v in (g.get("depth_map") or {}).items()}
    _prop = g.get("propagation_order", []) or []
    prop_order: list[tuple[str, float]] = []
    for item in _prop:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            prop_order.append((str(item[0]), float(item[1])))
        else:
            nid = str(item)
            prop_order.append((nid, float(_depth.get(nid, 0))))

    return EnergyFlow(
        impactor_ke_initial=float(g.get("impactor_ke_initial", 0.0)),
        impactor_ke_final=float(g.get("impactor_ke_final", 0.0)),
        energy_dissipated=float(g.get("energy_dissipated", 0.0)),
        nodes=nodes,
        edges=edges,
        propagation_order=prop_order,
        depth_map=_depth,
    )


def build_energy_flow(
    run_dir: Path,
    parts: list[PartInfo],
    impactor_id: str | None = None,
) -> EnergyFlow | None:
    """레거시 시그니처 유지 — run_dir 에서 직접 조립.

    loader 는 이미 파싱한 bin_data 를 재사용하려고
    ``build_energy_flow_from_binout`` 을 직접 부른다. 이 진입점은 독립
    호출자(테스트/외부) 대비 — run_dir 에서 binout 을 새로 파싱한다.
    """
    from .loader import load_binout_energy
    bin_data = load_binout_energy(run_dir)
    if bin_data.get("error"):
        return None
    part_names = {int(p.part_id): p.part_name for p in parts}
    imp_pid = None
    if impactor_id is not None:
        try:
            imp_pid = int(impactor_id)
        except (TypeError, ValueError):
            imp_pid = None
    return build_energy_flow_from_binout(bin_data, part_names, imp_pid)


# ---------------------------------------------------------------------------
# Helpers (fully implemented)
# ---------------------------------------------------------------------------

def compute_first_engage_time(
    edge: EnergyEdge,
    threshold: float | None = None,
    threshold_ratio: float = 0.01,
) -> float | None:
    """First t at which |F|(t) exceeds a data-driven threshold (§22.11.D).

    ``threshold`` (absolute, in the dataset's force unit) takes precedence
    when supplied. Otherwise the threshold is derived from the edge itself
    as ``threshold_ratio × peak |F|`` (default 1 %), keeping the check
    unit-agnostic. Returns ``None`` if the edge never engages.
    """
    if not edge.force_mag_ts:
        return None
    if threshold is None:
        peak = max(abs(f) for f in edge.force_mag_ts)
        if peak <= 0:
            return None
        threshold = threshold_ratio * peak
    for t, f in zip(edge.times, edge.force_mag_ts):
        if abs(f) > threshold:
            return float(t)
    return None


def compute_propagation_depth(impactor_id: str, edges: list[EnergyEdge]) -> dict[str, int]:
    """BFS distance (in graph hops) from impactor to each node (§22.11.C).

    Edges are treated as undirected for connectivity purposes — energy can
    propagate either way along a contact.
    """
    adj: dict[str, set[str]] = defaultdict(set)
    for e in edges:
        adj[e.src].add(e.dst)
        adj[e.dst].add(e.src)

    depth: dict[str, int] = {impactor_id: 0}
    queue: deque[str] = deque([impactor_id])
    while queue:
        node = queue.popleft()
        for nb in adj.get(node, set()):
            if nb not in depth:
                depth[nb] = depth[node] + 1
                queue.append(nb)
    return depth


def compute_node_positions(
    depth_map: dict[str, int],
    max_depth: int | None = None,
    radius_step: float = 1.0,
    angle_offset: float = 0.0,
) -> dict[str, tuple[float, float]]:
    """Lay nodes out in concentric rings by depth (§22.11.F).

    Impactor (depth 0) sits at origin; depth ``d`` nodes spread evenly
    around a circle of radius ``radius_step * d``. ``radius_step`` is in
    layout units (caller's responsibility) — the default of 1.0 keeps the
    layout dimensionless so the caller scales for the target viewport.
    """
    by_depth: dict[int, list[str]] = defaultdict(list)
    for n, d in depth_map.items():
        by_depth[d].append(n)

    positions: dict[str, tuple[float, float]] = {}
    if 0 in by_depth:
        # depth 0 → origin (use first; further depth-0 nodes share origin)
        for n in by_depth[0]:
            positions[n] = (0.0, 0.0)

    upper = max_depth if max_depth is not None else (max(by_depth) if by_depth else 0)
    for d in range(1, upper + 1):
        ring = sorted(by_depth.get(d, []))
        if not ring:
            continue
        r = radius_step * d
        for i, n in enumerate(ring):
            angle = 2.0 * math.pi * i / len(ring) + angle_offset
            positions[n] = (r * math.cos(angle), r * math.sin(angle))
    return positions


def verify_energy_conservation(
    flow: EnergyFlow,
    tolerance_pct: float | None = None,
) -> dict | None:
    """KE_init = KE_final + IE_final + dissipated (§22.11.E).

    Returns ``None`` when there is no initial KE to compare against —
    callers should NOT interpret zero-initial-KE as a passing check. When
    ``tolerance_pct`` is supplied, the ``ok`` field reflects ``|residual %|
    < tolerance_pct``; otherwise ``ok`` is omitted (no implicit threshold).
    """
    ke_init = float(flow.impactor_ke_initial)
    if ke_init <= 0:
        return None
    ke_final_total = 0.0
    ie_final_total = 0.0
    for n in flow.nodes:
        if n.kinetic_ts:
            ke_final_total += float(n.kinetic_ts[-1])
        if n.internal_ts:
            ie_final_total += float(n.internal_ts[-1])
    dissipated = float(flow.energy_dissipated)
    residual = ke_init - ke_final_total - ie_final_total - dissipated
    pct = abs(residual) / ke_init * 100.0
    out = {
        "ke_init": ke_init,
        "ke_final_total": ke_final_total,
        "ie_final_total": ie_final_total,
        "dissipated": dissipated,
        "residual": residual,
        "residual_pct": pct,
    }
    if tolerance_pct is not None:
        out["ok"] = pct < float(tolerance_pct)
    return out


def compute_energy_path(
    flow: EnergyFlow,
    source: str,
    sink: str,
) -> list[str]:
    """Dominant energy path from ``source`` to ``sink``.

    Uses a simple max-weight greedy BFS over total_impulse to choose the
    highest-energy path. Returns ``[source, …, sink]`` or ``[]`` if no path.
    """
    # weighted adjacency: prefer edges with larger total_impulse
    adj: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for e in flow.edges:
        adj[e.src].append((e.dst, float(e.total_impulse)))
        adj[e.dst].append((e.src, float(e.total_impulse)))

    if source not in adj and source != sink:
        return []

    # Dijkstra-style on "cost" = -impulse (so higher impulse = shorter cost)
    import heapq
    best_cost: dict[str, float] = {source: 0.0}
    prev: dict[str, str] = {}
    heap: list[tuple[float, str]] = [(0.0, source)]
    while heap:
        cost, node = heapq.heappop(heap)
        if node == sink:
            break
        if cost > best_cost.get(node, float("inf")):
            continue
        for nb, imp in adj.get(node, []):
            edge_cost = 1.0 / (imp + 1e-12)
            new_cost = cost + edge_cost
            if new_cost < best_cost.get(nb, float("inf")):
                best_cost[nb] = new_cost
                prev[nb] = node
                heapq.heappush(heap, (new_cost, nb))

    if sink not in best_cost:
        return []

    # Reconstruct path
    path: list[str] = [sink]
    while path[-1] != source:
        p = prev.get(path[-1])
        if p is None:
            return []
        path.append(p)
    path.reverse()
    return path
