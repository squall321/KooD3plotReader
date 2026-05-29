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

from .models import (
    EnergyEdge, EnergyFlow, EnergyGraphFrame, EnergyNode, PartInfo,
)


# ---------------------------------------------------------------------------
# Builder (stub — see TODO)
# ---------------------------------------------------------------------------

def build_energy_flow(
    run_dir: Path,
    parts: list[PartInfo],
    impactor_id: str | None = None,
) -> EnergyFlow | None:
    """Construct an EnergyFlow for one run directory.

    Currently unimplemented. Returns ``None`` rather than a graph with all
    zero scalars, so downstream code (e.g. ``verify_energy_conservation``)
    cannot silently treat absent data as "ok".

    TODO: parse binout/{matsum, rcforc, glstat} via
    ``koo_deep_report.core.binout_reader.parse_binout`` and
    ``glstat_reader.parse_glstat``, then:
      1) for each part_id: build EnergyNode with kinetic_ts/internal_ts from matsum
      2) for each contact_id: build EnergyEdge with force_mag_ts + cum impulse/work
      3) compute frames per timestep
      4) populate propagation_order / depth_map via compute_propagation_depth
      5) compute impactor_ke_initial/final/dissipated from glstat
    """
    return None


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
