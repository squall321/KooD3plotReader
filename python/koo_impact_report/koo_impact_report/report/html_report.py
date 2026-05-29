"""Single-file interactive HTML report generator for multi-face partial impact.

Generates a fully self-contained HTML (no external scripts/CSS/fonts) that
visualises a 3D-DOE (face × position × part) drop-weight impact study, plus
the Energy Flow Dynamics page (force-directed graph, sunburst, sankey,
time-force heatmap, conservation check).

Design language follows Test_006_SphereDrop_Report.html — dark Bloomberg
aesthetic, dense KPI grids, JetBrains Mono numerics, panel.ph headers,
reveal-on-scroll, cyan/pink/purple accent palette.

Public API
----------
    html_str = generate_html(report: ImpactReport) -> str

When ``report.results`` is empty the generator falls back to a built-in mock
dataset so the page is still visually testable (5 parts, 8 contact edges,
6 faces × 6 positions). The same mock payload also drives the Energy-Flow
visualisations whenever a particular case has no EnergyFlow attached.
"""
from __future__ import annotations

import dataclasses
import html
import json
import math
import os
import statistics
from enum import Enum
from typing import Any

from ..models import (
    EnergyEdge,
    EnergyFlow,
    EnergyNode,
    FaceOrientation,
    Finding,
    ImpactPosition,
    ImpactReport,
    ImpactorSpec,
    PartInfo,
    Severity,
)
try:  # forward-defensive: sibling agent X may not have committed these yet
    from ..models import ImpactorTrajectory, TrajectoryClusters  # type: ignore
except Exception:  # noqa: BLE001
    ImpactorTrajectory = None  # type: ignore
    TrajectoryClusters = None  # type: ignore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _esc(s: Any) -> str:
    """Escape a value for safe HTML interpolation."""
    return html.escape(str(s))


class _Encoder(json.JSONEncoder):
    """JSON encoder that knows about dataclasses, Enums, Paths and NaN/Inf."""

    def default(self, obj: Any) -> Any:  # type: ignore[override]
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            return dataclasses.asdict(obj)
        if isinstance(obj, Enum):
            return obj.value
        if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
            return 0.0
        if hasattr(obj, "__fspath__"):
            return str(obj)
        return super().default(obj)


def _safe(v: float, default: float = 0.0) -> float:
    if v is None:
        return default
    try:
        if math.isnan(v) or math.isinf(v):
            return default
    except (TypeError, ValueError):
        return default
    return float(v)


def _pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = max(0.0, min(1.0, q)) * (len(s) - 1)
    lo = int(math.floor(k))
    hi = int(math.ceil(k))
    if lo == hi:
        return float(s[lo])
    f = k - lo
    return float(s[lo] * (1 - f) + s[hi] * f)


# ---------------------------------------------------------------------------
# Payload assembly
# ---------------------------------------------------------------------------


def _impactor_dict(imp: ImpactorSpec) -> dict:
    return {
        "type": imp.type,
        "radius": _safe(imp.radius),
        "height": _safe(imp.height),
        "density": _safe(imp.density),
        "youngs_modulus": _safe(imp.youngs_modulus),
        "poisson_ratio": _safe(imp.poisson_ratio),
        "front_radius": _safe(imp.front_radius or 0.0),
        "outer_radius": _safe(imp.outer_radius or 0.0),
        "front_height": _safe(imp.front_height or 0.0),
        "back_height": _safe(imp.back_height or 0.0),
        "back_radius": _safe(imp.back_radius or 0.0),
        "mass": _safe(imp.mass),
        "velocity": _safe(imp.velocity),
        "kinetic_energy": _safe(imp.kinetic_energy),
    }


def _energy_flow_dict(flow: EnergyFlow) -> dict:
    nodes = [
        {
            "id": n.node_id,
            "name": n.name,
            "is_impactor": bool(n.is_impactor),
            "ke": [round(_safe(v), 5) for v in n.kinetic_ts],
            "ie": [round(_safe(v), 5) for v in n.internal_ts],
            "t": [round(_safe(v), 8) for v in n.times],
        }
        for n in flow.nodes
    ]
    edges = [
        {
            "src": e.src,
            "dst": e.dst,
            "cid": e.contact_id,
            "t": [round(_safe(v), 8) for v in e.times],
            "f": [round(_safe(v), 4) for v in e.force_mag_ts],
            "imp": [round(_safe(v), 4) for v in e.impulse_cum_ts],
            "w": [round(_safe(v), 4) for v in e.work_cum_ts],
            "peak_f": _safe(e.peak_force),
            "total_imp": _safe(e.total_impulse),
            "total_w": _safe(e.total_work),
        }
        for e in flow.edges
    ]
    return {
        "ke_init": _safe(flow.impactor_ke_initial),
        "ke_final": _safe(flow.impactor_ke_final),
        "dissipated": _safe(flow.energy_dissipated),
        "nodes": nodes,
        "edges": edges,
        "depth_map": {k: int(v) for k, v in flow.depth_map.items()},
        "propagation_order": [
            [k, _safe(v)] for k, v in flow.propagation_order
        ],
    }


def _build_mock_energy_flow() -> dict:
    """Hand-crafted energy flow for visual testing when no real flow is loaded.

    Five parts in a 4-layer device:
      impactor -> top_plate -> frame -> { pcb, ic }
                              -> sidewall
    Eight directed edges with realistic first-engage times spreading 0-1 ms.
    """
    times = [round(i * 1e-5, 6) for i in range(101)]  # 0 .. 1 ms, 10 us steps
    T = len(times)

    def gauss(t_peak: float, sigma: float, amp: float) -> list[float]:
        return [
            round(amp * math.exp(-((times[i] - t_peak) ** 2) / (2 * sigma ** 2)), 5)
            for i in range(T)
        ]

    def ramp_then_hold(t_eng: float, peak: float) -> list[float]:
        out: list[float] = []
        for i in range(T):
            t = times[i]
            if t < t_eng:
                out.append(0.0)
            else:
                rise = min(1.0, (t - t_eng) / 0.00012)
                out.append(round(peak * rise, 5))
        return out

    # Node IE/KE — each node ramps up after its first engage time.
    nodes = [
        {
            "id": "impactor", "name": "Impactor", "is_impactor": True,
            "t": times,
            "ke": [round(100.0 * max(0.0, 1.0 - times[i] / 0.0006), 4) for i in range(T)],
            "ie": [0.0] * T,
        },
        {"id": "top_plate", "name": "Top Plate", "is_impactor": False, "t": times,
         "ke": gauss(0.00020, 0.00008, 5.0), "ie": ramp_then_hold(0.00005, 38.0)},
        {"id": "frame", "name": "Frame", "is_impactor": False, "t": times,
         "ke": gauss(0.00030, 0.00010, 3.5), "ie": ramp_then_hold(0.00018, 22.0)},
        {"id": "sidewall", "name": "Sidewall", "is_impactor": False, "t": times,
         "ke": gauss(0.00040, 0.00010, 2.0), "ie": ramp_then_hold(0.00025, 11.0)},
        {"id": "pcb", "name": "PCB", "is_impactor": False, "t": times,
         "ke": gauss(0.00055, 0.00012, 0.8), "ie": ramp_then_hold(0.00040, 9.0)},
        {"id": "ic", "name": "IC", "is_impactor": False, "t": times,
         "ke": gauss(0.00060, 0.00010, 0.4), "ie": ramp_then_hold(0.00050, 4.0)},
    ]

    def edge(src: str, dst: str, cid: int, eng: float, peak_f: float, sigma: float):
        f_ts = gauss(eng + 2 * sigma, sigma, peak_f)
        imp_cum = []
        run = 0.0
        for i in range(T):
            dt = (times[i] - times[i - 1]) if i > 0 else 0.0
            run += f_ts[i] * dt
            imp_cum.append(round(run, 5))
        w_cum = [round(v * 0.6, 5) for v in imp_cum]
        return {
            "src": src, "dst": dst, "cid": cid,
            "t": times, "f": f_ts, "imp": imp_cum, "w": w_cum,
            "peak_f": peak_f, "total_imp": imp_cum[-1], "total_w": w_cum[-1],
        }

    edges = [
        edge("impactor", "top_plate", 1, 0.00005, 1.8e5, 0.00010),
        edge("top_plate", "frame",    2, 0.00018, 9.0e4, 0.00012),
        edge("top_plate", "sidewall", 3, 0.00022, 5.5e4, 0.00012),
        edge("frame",     "pcb",      4, 0.00040, 3.0e4, 0.00012),
        edge("frame",     "ic",       5, 0.00050, 1.6e4, 0.00012),
        edge("sidewall",  "frame",    6, 0.00035, 2.2e4, 0.00012),
        edge("pcb",       "ic",       7, 0.00058, 8.0e3, 0.00010),
        edge("top_plate", "pcb",      8, 0.00045, 1.2e4, 0.00012),
    ]

    return {
        "ke_init": 100.0,
        "ke_final": 6.5,
        "dissipated": 18.5,
        "nodes": nodes,
        "edges": edges,
        "depth_map": {"impactor": 0, "top_plate": 1, "frame": 2,
                      "sidewall": 2, "pcb": 3, "ic": 3},
        "propagation_order": [
            ["top_plate", 0.00005],
            ["frame", 0.00018],
            ["sidewall", 0.00022],
            ["pcb", 0.00040],
            ["top_plate.pcb", 0.00045],
            ["ic", 0.00050],
            ["pcb.ic", 0.00058],
        ],
    }


def _build_mock_doe() -> dict:
    """Mock 6-face DOE so the report is still useful with an empty ImpactReport."""
    faces = [
        {"code": "F1", "name": "Back",   "roll": 180, "pitch": 0,   "yaw": 0},
        {"code": "F2", "name": "Front",  "roll": 0,   "pitch": 0,   "yaw": 0},
        {"code": "F3", "name": "Right",  "roll": 0,   "pitch": 0,   "yaw": 90},
        {"code": "F4", "name": "Left",   "roll": 0,   "pitch": 0,   "yaw": -90},
        {"code": "F5", "name": "Top",    "roll": 0,   "pitch": 90,  "yaw": 0},
        {"code": "F6", "name": "Bottom", "roll": 0,   "pitch": -90, "yaw": 0},
    ]
    parts = [
        {"id": 1, "name": "Housing\\Top",  "group": "Housing"},
        {"id": 2, "name": "Frame\\Main",   "group": "Frame"},
        {"id": 3, "name": "PCB\\Main",     "group": "PCB"},
        {"id": 4, "name": "IC\\U1",        "group": "PCB"},
        {"id": 5, "name": "Sidewall\\L",   "group": "Housing"},
    ]
    rng_state = [1]

    def rnd() -> float:
        # tiny LCG so the layout is deterministic without numpy
        rng_state[0] = (rng_state[0] * 1103515245 + 12345) & 0x7fffffff
        return rng_state[0] / 0x7fffffff

    positions: list[dict] = []
    results: list[dict] = []
    n_per_face = {"F1": 25, "F2": 25, "F3": 15, "F4": 15, "F5": 12, "F6": 12}
    for f in faces:
        n = n_per_face[f["code"]]
        nx = int(math.ceil(math.sqrt(n)))
        for i in range(n):
            ix, iy = i % nx, i // nx
            x = -40 + 80.0 * ix / max(1, nx - 1)
            y = -30 + 60.0 * iy / max(1, nx - 1)
            pos_id = f"{f['code']}_P_{i:03d}"
            positions.append({
                "pos_id": pos_id, "face": f["code"],
                "x": round(x, 2), "y": round(y, 2),
            })
            for p in parts:
                # synthetic response — stronger near origin for face F1
                d = math.hypot(x, y)
                base = math.exp(-d * d / 1600.0)
                bias = 1.0 + (0.4 if f["code"] == "F1" else 0.0) \
                    + (0.6 if p["id"] == 3 and f["code"] == "F1" else 0.0)
                noise = 0.6 + 0.8 * rnd()
                g = round(1.2e6 * base * bias * noise, 1)
                results.append({
                    "face": f["code"], "pos_id": pos_id,
                    "x": round(x, 2), "y": round(y, 2),
                    "part_id": p["id"], "part_name": p["name"],
                    "g": g,
                    "s": round(80.0 + 1200.0 * base * bias * noise, 1),
                    "e": round(0.001 + 0.04 * base * bias * noise, 5),
                    "d": round(0.01 + 0.5 * base * bias * noise, 4),
                })
    return {"faces": faces, "parts": parts, "positions": positions, "results": results}


def _build_failure_risk_payload(report) -> dict:
    """Per-part safety factor based on yield_stress / peak_stress.

    When ``yield_stress_by_part`` is absent (e.g. all MAT_ELASTIC/MAT_RIGID
    runs), falls back to a peak_stress-based ranking payload so the panel
    stays useful. The fallback surfaces material properties (density, E,
    poisson) per part when ``sim_params['materials_by_part']`` is present,
    otherwise indicates "no material data".
    """
    sim_params = getattr(report, "sim_params", None) or {}
    yield_raw = sim_params.get("yield_stress_by_part") if isinstance(sim_params, dict) else None
    mats_raw = sim_params.get("materials_by_part") if isinstance(sim_params, dict) else None

    # Normalize yield dict keys to int part_id, drop non-positive/NaN
    yield_by_pid: dict = {}
    if isinstance(yield_raw, dict):
        for k, v in yield_raw.items():
            try:
                pid = int(k)
                fv = float(v)
            except (TypeError, ValueError):
                continue
            if fv != fv or fv <= 0.0:  # NaN or non-positive
                continue
            yield_by_pid[pid] = fv

    # Normalize material dict: pid -> {density, E, nu}
    mats_by_pid: dict = {}
    if isinstance(mats_raw, dict):
        for k, m in mats_raw.items():
            try:
                pid = int(k)
            except (TypeError, ValueError):
                continue
            if not isinstance(m, dict):
                continue
            mats_by_pid[pid] = {
                "density":        _safe(m.get("density", 0.0)),
                "youngs_modulus": _safe(m.get("youngs_modulus", 0.0)),
                "poisson_ratio":  _safe(m.get("poisson_ratio",
                                              m.get("poissons_ratio", 0.0))),
            }

    # -------------------------------------------------------------------
    # FALLBACK MODE: no yield data → rank by peak_stress, no SF math.
    # -------------------------------------------------------------------
    if not yield_by_pid:
        pname_lookup = {int(p.part_id): p.part_name
                        for p in (getattr(report, "parts", None) or [])}
        # Per-part max(peak_stress) across positions + which pos owns it
        per_part_peak: dict = {}
        for r in (report.results or []):
            try:
                pid = int(r.part_id)
            except (TypeError, ValueError):
                continue
            s = _safe(getattr(r, "peak_stress", 0.0))
            pos_id = r.position.pos_id
            prev = per_part_peak.get(pid)
            if (prev is None) or (s > prev["peak_stress"]):
                per_part_peak[pid] = {
                    "peak_stress": s,
                    "worst_pos_id": pos_id,
                    "worst_pos_xy": (_safe(r.position.x), _safe(r.position.y)),
                }

        ranked: list = []
        for pid, info in per_part_peak.items():
            m = mats_by_pid.get(pid)
            ranked.append({
                "part_id":       int(pid),
                "part_name":     pname_lookup.get(pid, f"part_{pid}"),
                "peak_stress":   round(info["peak_stress"], 4),
                "yield_stress":  None,
                "density":        m["density"]        if m else None,
                "youngs_modulus": m["youngs_modulus"] if m else None,
                "poisson_ratio":  m["poisson_ratio"]  if m else None,
                "worst_pos_id":  str(info["worst_pos_id"]),
                "worst_pos_xy":  [round(float(info["worst_pos_xy"][0]), 4),
                                  round(float(info["worst_pos_xy"][1]), 4)],
            })
        ranked.sort(key=lambda d: d["peak_stress"], reverse=True)

        return {
            "available": True,
            "mode": "peak_stress_ranking",
            "title_note": "재료 항복 데이터 부재 — peak_stress 기반 상대 순위 표시",
            "has_material_data": bool(mats_by_pid),
            "n_parts_with_yield": 0,
            "n_parts_evaluated": len(ranked),
            "parts_at_risk": ranked,
            # SF-mode fields left empty so the JS layer's `|| {}` / `|| []`
            # guards keep the legacy renderer no-op'ing the grid path.
            "sf_matrix": {},
            "min_sf_per_position": {},
            "min_sf_per_part": {},
        }

    pname_lookup = {int(p.part_id): p.part_name for p in (getattr(report, "parts", None) or [])}

    # Position xy lookup (from positions_by_face; results are fallback)
    pos_xy: dict = {}
    for _face, pos_list in (getattr(report, "positions_by_face", None) or {}).items():
        for pos in pos_list:
            pos_xy[pos.pos_id] = (_safe(pos.x), _safe(pos.y))
    if not pos_xy:
        for r in (report.results or []):
            pos_xy[r.position.pos_id] = (_safe(r.position.x), _safe(r.position.y))

    INF_TOKEN = "inf"
    HUGE = 1.0e12

    # Build sf_matrix[part_id_str][pos_id_str]
    sf_matrix: dict = {}
    # Track per-part SF distribution + worst per part
    per_part_sfs: dict = {}
    # Per position: best (= minimum) SF and which part owns it
    per_pos_min: dict = {}

    for r in (report.results or []):
        try:
            pid = int(r.part_id)
        except (TypeError, ValueError):
            continue
        if pid not in yield_by_pid:
            continue
        y = yield_by_pid[pid]
        s = _safe(getattr(r, "peak_stress", 0.0))
        pos_id = r.position.pos_id

        if s <= 0.0:
            sf_val = INF_TOKEN
            sf_num = HUGE  # for ranking only
        else:
            sf_num = y / s
            sf_val = round(sf_num, 4)

        sf_matrix.setdefault(str(pid), {})[str(pos_id)] = sf_val
        per_part_sfs.setdefault(pid, []).append((sf_num, pos_id))

        prev = per_pos_min.get(pos_id)
        if (prev is None) or (sf_num < prev["min_sf"]):
            per_pos_min[pos_id] = {
                "min_sf": sf_num,
                "worst_part_id": pid,
                "worst_part_name": pname_lookup.get(pid, f"part_{pid}"),
            }

    if not sf_matrix:
        return {"available": False, "reason": "no_overlap"}

    # min_sf_per_position payload (strings for JSON robustness)
    min_sf_per_position: dict = {}
    for pos_id, info in per_pos_min.items():
        sf = info["min_sf"]
        sf_out = INF_TOKEN if sf >= HUGE else round(sf, 4)
        min_sf_per_position[str(pos_id)] = {
            "min_sf": sf_out,
            "worst_part_id": int(info["worst_part_id"]),
            "worst_part_name": info["worst_part_name"],
        }

    # min_sf_per_part payload + parts_at_risk ranking
    risk_threshold = 2.0
    danger_threshold = 1.0
    min_sf_per_part: dict = {}
    parts_at_risk_raw: list = []
    for pid, lst in per_part_sfs.items():
        if not lst:
            continue
        sf_num, worst_pos = min(lst, key=lambda t: t[0])
        sf_out = INF_TOKEN if sf_num >= HUGE else round(sf_num, 4)
        min_sf_per_part[str(pid)] = {
            "min_sf": sf_out,
            "worst_pos_id": str(worst_pos),
        }
        if sf_num < risk_threshold:
            wx, wy = pos_xy.get(worst_pos, (0.0, 0.0))
            parts_at_risk_raw.append({
                "part_id": int(pid),
                "part_name": pname_lookup.get(pid, f"part_{pid}"),
                "min_sf": sf_out,
                "min_sf_num": sf_num,  # internal sort key, stripped below
                "worst_pos_id": str(worst_pos),
                "worst_pos_xy": [round(float(wx), 4), round(float(wy), 4)],
            })

    parts_at_risk_raw.sort(key=lambda d: d["min_sf_num"])
    parts_at_risk = []
    for d in parts_at_risk_raw:
        d.pop("min_sf_num", None)
        parts_at_risk.append(d)

    return {
        "available": True,
        "risk_threshold": risk_threshold,
        "danger_threshold": danger_threshold,
        "n_parts_with_yield": len(yield_by_pid),
        "n_parts_evaluated": len(min_sf_per_part),
        "sf_matrix": sf_matrix,
        "min_sf_per_position": min_sf_per_position,
        "min_sf_per_part": min_sf_per_part,
        "parts_at_risk": parts_at_risk,
    }

def _build_corr_network_payload(report) -> dict:
    """Pearson correlation of peak_g between parts over all DOE positions.

    Returns a payload with:
      - corr_matrix:  symmetric dict-of-dict of r-values (top-N parts only)
      - corr_threshold: float (greedy-cluster threshold, fixed at 0.7 per spec)
      - clusters:     list of cluster dicts {cluster_id, members, mean_r}
      - parts_listed: ordered metadata for matrix rows/cols
      - n_positions:  number of positions used in correlation
      - max_parts:    N used (top-N by mean peak_g)
    """
    import math

    results = getattr(report, "results", None) or []
    parts = getattr(report, "parts", None) or []
    if not results or not parts:
        return {
            "corr_matrix": {},
            "corr_threshold": 0.7,
            "clusters": [],
            "parts_listed": [],
            "n_positions": 0,
            "max_parts": 0,
        }

    # part_id -> name / group
    pname_lookup = {int(p.part_id): getattr(p, "part_name", f"part_{p.part_id}") for p in parts}
    pgroup_lookup = {int(p.part_id): getattr(p, "group", None) for p in parts}

    # Build per-part dict {pos_id: peak_g} (collapse duplicates by max)
    by_part: dict[int, dict[str, float]] = {}
    pos_id_set: set[str] = set()
    for r in results:
        try:
            pid = int(r.part_id)
        except Exception:
            continue
        pos_id = getattr(getattr(r, "position", None), "pos_id", None)
        if pos_id is None:
            continue
        try:
            g = float(getattr(r, "peak_g", 0.0) or 0.0)
        except Exception:
            g = 0.0
        if not math.isfinite(g):
            continue
        pos_id_set.add(pos_id)
        d = by_part.setdefault(pid, {})
        if g > d.get(pos_id, 0.0):
            d[pos_id] = g

    if not by_part or len(pos_id_set) < 2:
        return {
            "corr_matrix": {},
            "corr_threshold": 0.7,
            "clusters": [],
            "parts_listed": [],
            "n_positions": len(pos_id_set),
            "max_parts": 0,
        }

    pos_ids = sorted(pos_id_set)

    # Rank parts by mean peak_g, keep top-N
    MAX_PARTS = 12
    part_means: list[tuple[int, float]] = []
    for pid, pos_map in by_part.items():
        vals = [pos_map.get(pid_, 0.0) for pid_ in pos_ids]
        if not vals:
            continue
        m = sum(vals) / len(vals)
        if m > 0:
            part_means.append((pid, m))
    part_means.sort(key=lambda t: t[1], reverse=True)
    top_parts = [pid for pid, _ in part_means[:MAX_PARTS]]

    if len(top_parts) < 2:
        return {
            "corr_matrix": {},
            "corr_threshold": 0.7,
            "clusters": [],
            "parts_listed": [
                {"part_id": pid, "part_name": pname_lookup.get(pid, f"part_{pid}"),
                 "group": pgroup_lookup.get(pid), "mean_peak_g": float(m)}
                for pid, m in part_means[:MAX_PARTS]
            ],
            "n_positions": len(pos_ids),
            "max_parts": len(top_parts),
        }

    # Vectors per part (in pos_ids order)
    vecs: dict[int, list[float]] = {
        pid: [by_part[pid].get(p, 0.0) for p in pos_ids] for pid in top_parts
    }

    def _pearson(a: list[float], b: list[float]) -> float:
        n = len(a)
        if n < 2:
            return 0.0
        ma = sum(a) / n
        mb = sum(b) / n
        num = 0.0
        sa = 0.0
        sb = 0.0
        for i in range(n):
            da = a[i] - ma
            db = b[i] - mb
            num += da * db
            sa += da * da
            sb += db * db
        denom = math.sqrt(sa * sb)
        if denom <= 0.0 or not math.isfinite(denom):
            return 0.0
        r = num / denom
        if not math.isfinite(r):
            return 0.0
        return max(-1.0, min(1.0, r))

    # Symmetric matrix
    corr_matrix: dict[str, dict[str, float]] = {}
    for i, pi in enumerate(top_parts):
        row: dict[str, float] = {}
        for j, pj in enumerate(top_parts):
            if pi == pj:
                row[str(pj)] = 1.0
            elif j < i:
                # mirror earlier computed value
                row[str(pj)] = corr_matrix[str(pj)][str(pi)]
            else:
                row[str(pj)] = round(_pearson(vecs[pi], vecs[pj]), 4)
        corr_matrix[str(pi)] = row

    # Greedy clustering by r > threshold
    THRESH = 0.7
    pid_to_mean = dict(part_means)
    ordered = sorted(top_parts, key=lambda p: pid_to_mean.get(p, 0.0), reverse=True)
    assigned: set[int] = set()
    clusters: list[dict] = []
    cid = 0
    for seed in ordered:
        if seed in assigned:
            continue
        members = [seed]
        assigned.add(seed)
        for other in ordered:
            if other in assigned:
                continue
            r = corr_matrix[str(seed)][str(other)]
            if r > THRESH:
                members.append(other)
                assigned.add(other)
        # mean off-diagonal r within cluster
        if len(members) >= 2:
            rs = []
            for a in range(len(members)):
                for b in range(a + 1, len(members)):
                    rs.append(corr_matrix[str(members[a])][str(members[b])])
            mean_r = sum(rs) / len(rs) if rs else 0.0
        else:
            mean_r = 1.0
        clusters.append({
            "cluster_id": cid,
            "members": [int(m) for m in members],
            "member_names": [pname_lookup.get(int(m), f"part_{m}") for m in members],
            "mean_r": round(float(mean_r), 4),
            "size": len(members),
        })
        cid += 1

    # parts_listed in row/col order, tagged with cluster index
    pid_to_cluster: dict[int, int] = {}
    for c in clusters:
        for m in c["members"]:
            pid_to_cluster[int(m)] = int(c["cluster_id"])

    parts_listed = []
    for pid in top_parts:
        parts_listed.append({
            "part_id": int(pid),
            "part_name": pname_lookup.get(int(pid), f"part_{pid}"),
            "group": pgroup_lookup.get(int(pid)),
            "group_idx": pid_to_cluster.get(int(pid), -1),
            "mean_peak_g": round(float(pid_to_mean.get(pid, 0.0)), 4),
        })

    return {
        "corr_matrix": corr_matrix,
        "corr_threshold": THRESH,
        "clusters": clusters,
        "parts_listed": parts_listed,
        "n_positions": len(pos_ids),
        "max_parts": len(top_parts),
    }

def _build_toa_payload(report):
    """Build Time-of-Arrival payload.

    Δt_ms = (PartMotion.t_peak_g - ImpactorTrajectory.t_first_contact) * 1000
    per (position, part). Aggregated to:
      - toa_per_position[pos_id_str] = top-12 earliest parts {part_id, part_name, dt_ms}
      - mean_arrival_per_part[part_id_str] = {mean_dt_ms, std_dt_ms, n_positions}
      - earliest_part / latest_part summaries
    """
    import math

    raw_motions = getattr(report, "part_motions", None) or {}
    raw_traj = getattr(report, "impactor_trajectories", None) or {}
    parts = list(getattr(report, "parts", []) or [])
    pname_lookup = {}
    for p in parts:
        try:
            pname_lookup[int(p.part_id)] = p.part_name or f"part_{int(p.part_id)}"
        except Exception:  # noqa: BLE001
            continue

    # behavior class per position (used by JS strip-chart colorbar)
    behavior_by_pos = {}
    for pos_id, traj in raw_traj.items():
        if traj is None:
            continue
        behavior_by_pos[str(pos_id)] = getattr(traj, "behavior_class", "unknown") or "unknown"

    # t_first_contact per position
    t_contact_by_pos = {}
    for pos_id, traj in raw_traj.items():
        if traj is None:
            continue
        tfc = getattr(traj, "t_first_contact", None)
        if tfc is None:
            continue
        try:
            tfc_f = float(tfc)
        except Exception:  # noqa: BLE001
            continue
        if math.isnan(tfc_f) or math.isinf(tfc_f):
            continue
        t_contact_by_pos[str(pos_id)] = tfc_f

    # per-position list of (dt_ms, part_id, part_name)
    per_pos_rows = {}
    # per-part list of dt_ms (across all positions)
    per_part_dts = {}

    for key, motion in raw_motions.items():
        if motion is None:
            continue
        try:
            pos_id, pid = key
            pid = int(pid)
        except Exception:  # noqa: BLE001
            continue
        pos_key = str(pos_id)
        tfc = t_contact_by_pos.get(pos_key)
        if tfc is None:
            continue
        try:
            tpg = float(getattr(motion, "t_peak_g", 0.0) or 0.0)
        except Exception:  # noqa: BLE001
            continue
        if math.isnan(tpg) or math.isinf(tpg):
            continue
        if tpg <= 0.0:
            continue
        dt_ms = (tpg - tfc) * 1000.0
        if math.isnan(dt_ms) or math.isinf(dt_ms):
            continue
        # negative dt (part peaked before impactor "first contact") can occur with
        # tiny noise; clip below at 0 for ranking sanity but keep the sign
        # for the per-part stats (informative).
        pname = (getattr(motion, "part_name", "") or pname_lookup.get(pid, f"part_{pid}"))
        per_pos_rows.setdefault(pos_key, []).append({
            "part_id": pid,
            "part_name": pname,
            "dt_ms": round(dt_ms, 4),
        })
        per_part_dts.setdefault(pid, []).append(dt_ms)

    # per-position: sort asc by dt_ms, cap 12 earliest
    toa_per_position = {}
    for pos_key, rows in per_pos_rows.items():
        rows_sorted = sorted(rows, key=lambda r: r["dt_ms"])
        toa_per_position[pos_key] = rows_sorted[:12]

    # per-part: mean / std / n
    def _mean_std(vals):
        n = len(vals)
        if n == 0:
            return 0.0, 0.0
        m = sum(vals) / n
        if n < 2:
            return m, 0.0
        var = sum((v - m) ** 2 for v in vals) / (n - 1)
        return m, math.sqrt(var)

    mean_arrival_per_part = {}
    for pid, dts in per_part_dts.items():
        m, s = _mean_std(dts)
        mean_arrival_per_part[str(pid)] = {
            "mean_dt_ms": round(m, 4),
            "std_dt_ms": round(s, 4),
            "n_positions": len(dts),
        }

    # earliest / latest: require at least 2 positions to avoid one-shot noise
    candidates = [
        (pid, info) for pid, info in mean_arrival_per_part.items()
        if info["n_positions"] >= 2
    ]
    earliest_part = None
    latest_part = None
    if candidates:
        pid_e, info_e = min(candidates, key=lambda kv: kv[1]["mean_dt_ms"])
        pid_l, info_l = max(candidates, key=lambda kv: kv[1]["mean_dt_ms"])
        earliest_part = {
            "part_id": int(pid_e),
            "part_name": pname_lookup.get(int(pid_e), f"part_{pid_e}"),
            "mean_dt_ms": info_e["mean_dt_ms"],
            "std_dt_ms": info_e["std_dt_ms"],
            "n_positions": info_e["n_positions"],
        }
        latest_part = {
            "part_id": int(pid_l),
            "part_name": pname_lookup.get(int(pid_l), f"part_{pid_l}"),
            "mean_dt_ms": info_l["mean_dt_ms"],
            "std_dt_ms": info_l["std_dt_ms"],
            "n_positions": info_l["n_positions"],
        }

    return {
        "toa_per_position": toa_per_position,
        "mean_arrival_per_part": mean_arrival_per_part,
        "earliest_part": earliest_part,
        "latest_part": latest_part,
        "behavior_by_pos": behavior_by_pos,
    }

def _build_idw_predictor_payload(report):
    """Build IDW-interpolated risk surfaces (peak_g, peak_stress) on a 41x41
    fine grid covering the DOE bbox. Returns None when grid metadata or
    measurement points are unavailable.

    Pure-Python (no numpy) IDW with power p=2. Exact reproduction at
    measurement points (zero distance fallback). Payload kept compact:
    ~13 KB per metric, rounded.
    """
    sim_params = getattr(report, "sim_params", None) or {}
    grid_meta = sim_params.get("grid") if isinstance(sim_params, dict) else None
    if not grid_meta or not isinstance(grid_meta, dict):
        return None
    bbox_raw = grid_meta.get("bbox") or []
    try:
        bbox = [float(b) for b in bbox_raw]
    except Exception:
        return None
    if len(bbox) != 4:
        return None
    xmin, ymin, xmax, ymax = bbox
    if not (xmax > xmin and ymax > ymin):
        return None

    results = getattr(report, "results", None) or []
    if not results:
        return None

    # Collect xy per pos_id from positions_by_face (fall back to results)
    pos_xy = {}
    for _face, pos_list in (getattr(report, "positions_by_face", None) or {}).items():
        for pos in pos_list:
            try:
                pos_xy[pos.pos_id] = (float(pos.x), float(pos.y))
            except Exception:
                continue
    if not pos_xy:
        for r in results:
            try:
                pos_xy[r.position.pos_id] = (float(r.position.x), float(r.position.y))
            except Exception:
                continue
    if len(pos_xy) < 2:
        return None

    # Per-position max(peak_g) and max(peak_stress) across parts
    def _sv(v):
        try:
            f = float(v)
        except Exception:
            return 0.0
        if f != f or f in (float("inf"), float("-inf")):
            return 0.0
        return f

    pos_g = {}
    pos_s = {}
    for r in results:
        pid = getattr(r.position, "pos_id", None)
        if pid is None or pid not in pos_xy:
            continue
        g = _sv(getattr(r, "peak_g", 0.0))
        s = _sv(getattr(r, "peak_stress", 0.0))
        if g > pos_g.get(pid, 0.0):
            pos_g[pid] = g
        if s > pos_s.get(pid, 0.0):
            pos_s[pid] = s

    measured = []
    for pid, (x, y) in pos_xy.items():
        measured.append({
            "pos_id": pid,
            "x": round(x, 4),
            "y": round(y, 4),
            "peak_g": round(pos_g.get(pid, 0.0), 3),
            "peak_stress": round(pos_s.get(pid, 0.0), 3),
        })
    if len(measured) < 2:
        return None

    # IDW interpolation, p=2
    NX = 41
    NY = 41
    dx = (xmax - xmin) / (NX - 1)
    dy = (ymax - ymin) / (NY - 1)
    eps2 = ((dx * dx + dy * dy) * 1e-6) or 1e-12  # snap radius

    samples = [(m["x"], m["y"], m["peak_g"], m["peak_stress"]) for m in measured]

    grid_g = [0.0] * (NX * NY)
    grid_s = [0.0] * (NX * NY)

    for j in range(NY):
        gy = ymin + j * dy
        for i in range(NX):
            gx = xmin + i * dx
            idx = j * NX + i
            wsum = 0.0
            vg = 0.0
            vs = 0.0
            exact = -1
            for k, (sx, sy, sg, ss) in enumerate(samples):
                ddx = gx - sx
                ddy = gy - sy
                d2 = ddx * ddx + ddy * ddy
                if d2 <= eps2:
                    exact = k
                    break
                w = 1.0 / d2  # p=2 → 1/d^2
                wsum += w
                vg += w * sg
                vs += w * ss
            if exact >= 0:
                grid_g[idx] = samples[exact][2]
                grid_s[idx] = samples[exact][3]
            elif wsum > 0:
                grid_g[idx] = vg / wsum
                grid_s[idx] = vs / wsum

    # Round to keep payload small
    grid_g_r = [round(v, 3) for v in grid_g]
    grid_s_r = [round(v, 3) for v in grid_s]

    # Predicted max indices
    def _argmax(arr):
        if not arr:
            return 0
        best = 0
        bv = arr[0]
        for ii in range(1, len(arr)):
            if arr[ii] > bv:
                bv = arr[ii]
                best = ii
        return best

    max_idx_g = _argmax(grid_g_r)
    max_idx_s = _argmax(grid_s_r)

    return {
        "grid_fine": {
            "nx_fine": NX,
            "ny_fine": NY,
            "bbox": [round(xmin, 4), round(ymin, 4), round(xmax, 4), round(ymax, 4)],
            "peak_g": grid_g_r,
            "peak_stress": grid_s_r,
        },
        "max_sample_idx": {
            "peak_g": max_idx_g,
            "peak_stress": max_idx_s,
        },
        "measured_points": measured,
        "power": 2,
    }

def _build_pareto_severity_payload(report) -> dict:
    """Pareto severity-coverage aggregation.

    severity = max(peak_g) over all parts at the position
    coverage = (# parts with peak_g > P75_global) / total_parts_at_position
    mean_response = mean(peak_g) over all parts at the position
    """
    results = getattr(report, "results", None) or []
    if not results:
        return {"points": [], "p75_global": 0.0, "median_severity": 0.0,
                "median_coverage": 0.0, "min_mean": 0.0, "max_mean": 0.0,
                "quadrant_labels": {
                    "q1": "고집중 고심각", "q2": "광범위 고심각",
                    "q3": "광범위 저심각", "q4": "고집중 저심각",
                }, "unit_acc": "m/s²"}

    # global P75 over all (pos, part) peak_g values
    all_g = []
    for r in results:
        v = _safe(getattr(r, "peak_g", 0.0))
        if v > 0:
            all_g.append(float(v))
    all_g.sort()

    def _pct(arr, p):
        if not arr:
            return 0.0
        if len(arr) == 1:
            return float(arr[0])
        k = (len(arr) - 1) * p
        lo = int(k)
        hi = min(lo + 1, len(arr) - 1)
        frac = k - lo
        return float(arr[lo]) * (1 - frac) + float(arr[hi]) * frac

    p75_global = _pct(all_g, 0.75)

    # group results by pos_id
    by_pos: dict = {}
    pos_xy: dict = {}
    for r in results:
        pid = r.position.pos_id
        by_pos.setdefault(pid, []).append(_safe(getattr(r, "peak_g", 0.0)))
        if pid not in pos_xy:
            pos_xy[pid] = (r.face, _safe(r.position.x), _safe(r.position.y))

    # trajectory behavior_class lookup
    raw_trajs = getattr(report, "impactor_trajectories", None) or {}
    beh_lookup: dict = {}
    for pid, traj in raw_trajs.items():
        bclass = getattr(traj, "behavior_class", "unknown") or "unknown"
        beh_lookup[str(pid)] = str(bclass)

    points = []
    for pid, vals in by_pos.items():
        if not vals:
            continue
        n = len(vals)
        sev = max(vals) if vals else 0.0
        mean_g = sum(vals) / n if n > 0 else 0.0
        if p75_global > 0:
            above = sum(1 for v in vals if v > p75_global)
        else:
            above = 0
        cov = (above / n) if n > 0 else 0.0
        face, x, y = pos_xy.get(pid, ("", 0.0, 0.0))
        points.append({
            "pos_id": pid,
            "face": face,
            "x": round(float(x), 4),
            "y": round(float(y), 4),
            "severity": round(float(sev), 3),
            "coverage": round(float(cov), 4),
            "mean_response": round(float(mean_g), 3),
            "behavior_class": beh_lookup.get(str(pid), "unknown"),
            "n_parts": n,
            "n_above": int(above),
        })

    # medians for quadrant cross-hair
    sev_vals = sorted(p["severity"] for p in points)
    cov_vals = sorted(p["coverage"] for p in points)
    median_sev = _pct(sev_vals, 0.5) if sev_vals else 0.0
    median_cov = _pct(cov_vals, 0.5) if cov_vals else 0.0

    mean_vals = [p["mean_response"] for p in points]
    min_mean = min(mean_vals) if mean_vals else 0.0
    max_mean = max(mean_vals) if mean_vals else 0.0

    unit_labels = {}
    sp = getattr(report, "sim_params", None) or {}
    if isinstance(sp, dict):
        unit_labels = sp.get("unit_labels") or {}
    unit_acc = unit_labels.get("acc", "m/s²")

    return {
        "points": points,
        "p75_global": round(float(p75_global), 3),
        "median_severity": round(float(median_sev), 3),
        "median_coverage": round(float(median_cov), 4),
        "min_mean": round(float(min_mean), 3),
        "max_mean": round(float(max_mean), 3),
        "quadrant_labels": {
            "q1": "고집중 고심각",
            "q2": "광범위 고심각",
            "q3": "광범위 저심각",
            "q4": "고집중 저심각",
        },
        "unit_acc": unit_acc,
    }

def _build_energy_partition_payload(report) -> dict:
    """DOE energy partition: per-position KE absorbed vs retained.

    Derives partition from `impactor_trajectories[pos_id].initial_ke` /
    `final_ke` (already exposed on the trajectory object). Falls back to
    KE-vs-time curve peak when initial_ke is missing/zero.
    Empty/degenerate positions are skipped so the panel can render a
    "no data" placeholder cleanly.
    """
    raw_trajs = getattr(report, "impactor_trajectories", None) or {}
    # Map pos_id -> (x, y) for plotting / hover.
    pos_xy: dict = {}
    for _face, pos_list in (report.positions_by_face or {}).items():
        for pos in pos_list:
            pos_xy[pos.pos_id] = (_safe(pos.x), _safe(pos.y))

    partitions: list = []
    abs_pcts: list = []
    ke_total_initial = 0.0
    for pos_id, traj in raw_trajs.items():
        if traj is None:
            continue
        ke_init = _safe(getattr(traj, "initial_ke", 0.0))
        ke_final = _safe(getattr(traj, "final_ke", 0.0))
        # Fallback: max of KE-vs-time pre-contact if initial_ke is degenerate.
        if ke_init <= 0:
            ke_curve = list(getattr(traj, "ke", []) or [])
            contact_arr = list(getattr(traj, "contact_engaged", []) or [])
            pre_vals = []
            for i, v in enumerate(ke_curve):
                if i < len(contact_arr) and contact_arr[i]:
                    break
                pre_vals.append(_safe(v))
            if pre_vals:
                ke_init = max(pre_vals)
        if ke_init <= 0:
            continue
        ke_absorbed = max(0.0, ke_init - ke_final)
        pct = ke_absorbed / ke_init if ke_init > 0 else 0.0
        pct = max(0.0, min(1.0, pct))
        x, y = pos_xy.get(pos_id, (0.0, 0.0))
        partitions.append({
            "pos_id": pos_id,
            "x": round(x, 4),
            "y": round(y, 4),
            "ke_initial": round(ke_init, 4),
            "ke_retained": round(ke_final, 4),
            "ke_absorbed": round(ke_absorbed, 4),
            "absorption_pct": round(pct, 5),
            "behavior_class": getattr(traj, "behavior_class", "unknown") or "unknown",
        })
        abs_pcts.append(pct)
        ke_total_initial += ke_init

    if not partitions:
        return {
            "partitions": [],
            "summary": {
                "median_absorption_pct": 0.0,
                "max_absorption_pos_id": None,
                "min_absorption_pos_id": None,
                "ke_total_initial": 0.0,
            },
        }

    # Median absorption %
    s = sorted(abs_pcts)
    n = len(s)
    if n % 2 == 1:
        median = s[n // 2]
    else:
        median = 0.5 * (s[n // 2 - 1] + s[n // 2])

    max_p = max(partitions, key=lambda d: d["absorption_pct"])
    min_p = min(partitions, key=lambda d: d["absorption_pct"])

    return {
        "partitions": partitions,
        "summary": {
            "median_absorption_pct": round(median, 5),
            "max_absorption_pos_id": max_p["pos_id"],
            "max_absorption_pct": round(max_p["absorption_pct"], 5),
            "min_absorption_pos_id": min_p["pos_id"],
            "min_absorption_pct": round(min_p["absorption_pct"], 5),
            "ke_total_initial": round(ke_total_initial, 4),
        },
    }

# === ADV_PYTHON_HELPERS_INSERT_HERE ===
# Additional Section-05 analytics builders are inserted ABOVE this line.
# Each helper returns a JSON-serializable dict; ``_build_doe_payload``
# merges them into ``advanced``.


def _build_doe_payload(report: ImpactReport) -> dict | None:
    """DOE-specific aggregations for the multi-position partial-impact view.

    Returns ``None`` when the report is not a multi-position DOE (no grid
    metadata in ``sim_params`` or fewer than 2 positions). Downstream JS
    hides the DOE section entirely in that case so single-d3plot reports
    are unaffected.
    """
    sim_params = report.sim_params or {}
    grid_meta = sim_params.get("grid") if isinstance(sim_params, dict) else None
    if not grid_meta or not isinstance(grid_meta, dict):
        return None
    if not report.results:
        return None

    # --- positions: collect every unique pos_id across all faces ----------
    pos_xy: dict[str, tuple[str, float, float]] = {}
    for face_code, pos_list in (report.positions_by_face or {}).items():
        for pos in pos_list:
            pos_xy[pos.pos_id] = (face_code, _safe(pos.x), _safe(pos.y))
    # Fall back to results-derived xy when positions_by_face is empty
    if not pos_xy:
        for r in report.results:
            pos_xy[r.position.pos_id] = (r.face, _safe(r.position.x), _safe(r.position.y))

    if len(pos_xy) < 2:
        return None

    nx = int(grid_meta.get("nx") or 0)
    ny = int(grid_meta.get("ny") or 0)
    bbox_raw = grid_meta.get("bbox") or []
    try:
        bbox = [float(b) for b in bbox_raw]
        if len(bbox) != 4:
            bbox = None  # type: ignore[assignment]
    except Exception:  # noqa: BLE001
        bbox = None  # type: ignore[assignment]

    grid_payload = None
    if nx > 0 and ny > 0 and bbox:
        grid_payload = {"nx": nx, "ny": ny, "bbox": bbox}

    # --- positions list with grid row/col binning -------------------------
    positions_list: list[dict] = []
    if grid_payload:
        xmin, ymin, xmax, ymax = bbox[0], bbox[1], bbox[2], bbox[3]
        x_span = xmax - xmin if xmax > xmin else 1.0
        y_span = ymax - ymin if ymax > ymin else 1.0
        for pos_id, (_face, x, y) in pos_xy.items():
            col = int(round((x - xmin) / x_span * max(1, nx - 1))) if nx > 1 else 0
            row = int(round((y - ymin) / y_span * max(1, ny - 1))) if ny > 1 else 0
            col = max(0, min(nx - 1, col))
            row = max(0, min(ny - 1, row))
            positions_list.append({
                "pos_id": pos_id, "x": x, "y": y,
                "row": row, "col": col, "label": pos_id,
            })
    else:
        for pos_id, (_face, x, y) in pos_xy.items():
            positions_list.append({
                "pos_id": pos_id, "x": x, "y": y,
                "row": 0, "col": 0, "label": pos_id,
            })

    positions_list.sort(key=lambda d: (d["row"], d["col"], d["pos_id"]))
    for idx, p in enumerate(positions_list):
        p["doe_index"] = idx

    # --- part name lookup -------------------------------------------------
    pname_lookup = {int(p.part_id): p.part_name for p in (report.parts or [])}

    # --- metrics catalog (drop metrics whose global max is 0) ------------
    metric_specs = [
        ("peak_g",      "Peak G",       "acc"),
        ("peak_stress", "Peak Stress",  "stress"),
        ("peak_strain", "Peak Strain",  ""),
        ("peak_disp",   "Peak Disp",    "disp"),
        ("peak_vel",    "Peak Vel",     "vel"),
    ]
    metric_global_max: dict[str, float] = {k: 0.0 for k, _, _ in metric_specs}
    for r in report.results:
        for key, _, _ in metric_specs:
            v = _safe(getattr(r, key, 0.0))
            if v > metric_global_max[key]:
                metric_global_max[key] = v
    metrics_payload = [
        {"key": k, "label": lbl, "unit_key": uk}
        for k, lbl, uk in metric_specs
        if metric_global_max.get(k, 0.0) > 0
    ]

    # --- per-position aggregates ------------------------------------------
    position_metrics: dict[str, dict] = {}
    position_results: dict[str, list] = {}
    for r in report.results:
        pid = r.position.pos_id
        position_results.setdefault(pid, []).append(r)

    metric_short = {
        "peak_g": "g", "peak_stress": "s", "peak_strain": "e",
        "peak_disp": "d", "peak_vel": "v",
    }
    for pid, rows in position_results.items():
        rec: dict = {}
        for key, _, _ in metric_specs:
            best_val = 0.0
            best_pid = None
            for r in rows:
                v = _safe(getattr(r, key, 0.0))
                if v > best_val:
                    best_val = v
                    best_pid = int(r.part_id)
            rec[f"{key}_max"] = best_val
            rec[f"worst_part_id_{metric_short[key]}"] = best_pid
        position_metrics[pid] = rec

    # --- per-position top parts (sorted by peak_g, max 5) -----------------
    position_top_parts: dict[str, list] = {}
    for pid, rows in position_results.items():
        # collapse multiple entries for same part_id (max peak_g)
        by_part: dict[int, dict] = {}
        for r in rows:
            part_id = int(r.part_id)
            entry = by_part.get(part_id)
            cand = {
                "part_id": part_id,
                "part_name": pname_lookup.get(part_id, f"part_{part_id}"),
                "peak_g": _safe(r.peak_g),
                "peak_stress": _safe(r.peak_stress),
                "peak_strain": _safe(r.peak_strain),
                "peak_disp": _safe(r.peak_disp),
                "peak_vel": _safe(r.peak_vel),
            }
            if entry is None or cand["peak_g"] > entry["peak_g"]:
                by_part[part_id] = cand
        top = sorted(by_part.values(), key=lambda d: d["peak_g"], reverse=True)[:5]
        position_top_parts[pid] = top

    # --- part-position matrices (peak_g + peak_stress) --------------------
    peak_g_matrix: dict[int, dict[str, float]] = {}
    peak_stress_matrix: dict[int, dict[str, float]] = {}
    for r in report.results:
        part_id = int(r.part_id)
        pid = r.position.pos_id
        g = _safe(r.peak_g)
        s = _safe(r.peak_stress)
        gm = peak_g_matrix.setdefault(part_id, {})
        if g > gm.get(pid, 0.0):
            gm[pid] = g
        sm = peak_stress_matrix.setdefault(part_id, {})
        if s > sm.get(pid, 0.0):
            sm[pid] = s

    # --- trajectory summary + KE curves -----------------------------------
    traj_summary: dict[str, dict] = {}
    traj_curves: dict[str, dict] = {}
    behavior_counts: dict[str, int] = {}
    total_ke_absorbed: list[float] = []
    raw_trajs = getattr(report, "impactor_trajectories", None) or {}
    for pos_id, traj in raw_trajs.items():
        if traj is None:
            continue
        contact_arr = list(getattr(traj, "contact_engaged", []) or [])
        n_total = len(getattr(traj, "times", []) or [])
        n_contact = sum(1 for v in contact_arr if v)
        tfc = getattr(traj, "t_first_contact", None)
        ke_ret = _safe(getattr(traj, "ke_retention", 0.0))
        bclass = getattr(traj, "behavior_class", "unknown") or "unknown"
        traj_summary[pos_id] = {
            "ke_retention": ke_ret,
            "rebound_speed": _safe(getattr(traj, "rebound_speed", 0.0)),
            "max_penetration_depth": _safe(getattr(traj, "max_penetration_depth", 0.0)),
            "behavior_class": bclass,
            "t_first_contact": (float(tfc) if tfc is not None else None),
            "n_contact_steps": int(n_contact),
            "n_total_steps": int(n_total),
            "initial_ke": _safe(getattr(traj, "initial_ke", 0.0)),
            "final_ke": _safe(getattr(traj, "final_ke", 0.0)),
        }
        behavior_counts[bclass] = behavior_counts.get(bclass, 0) + 1
        # Only count KE absorption for trajectories with a valid initial KE.
        # A degenerate trajectory (initial_ke == 0) would otherwise contribute
        # a misleading 1.0 (100%) absorption to the headline statistic.
        if _safe(getattr(traj, "initial_ke", 0.0)) > 0:
            total_ke_absorbed.append(max(0.0, 1.0 - ke_ret))

        # Downsample KE curve to ≤~200 points. Always preserve the argmax
        # and argmin indices so the peak/trough is never silently dropped.
        times = list(getattr(traj, "times", []) or [])
        ke = list(getattr(traj, "ke", []) or [])
        n = min(len(times), len(ke))
        if n > 0:
            step = max(1, n // 200)
            kept = set(range(0, n, step))
            kept.add(n - 1)
            argmax = max(range(n), key=lambda i: ke[i])
            argmin = min(range(n), key=lambda i: ke[i])
            kept.add(argmax)
            kept.add(argmin)
            kept_idx = sorted(kept)
            traj_curves[pos_id] = {
                "t":  [round(_safe(times[i]), 8) for i in kept_idx],
                "ke": [round(_safe(ke[i]),    5) for i in kept_idx],
            }

    # --- per-part stats across positions (peak_g distribution) ------------
    per_part_g: dict[int, list[float]] = {}
    for r in report.results:
        pid = int(r.part_id)
        per_part_g.setdefault(pid, []).append(_safe(r.peak_g))
    per_part_stats: dict[int, dict] = {}
    for pid, vals in per_part_g.items():
        if not vals:
            continue
        per_part_stats[pid] = {
            "part_name": pname_lookup.get(pid, f"part_{pid}"),
            "p5":  _pct(vals, 0.05),
            "p50": _pct(vals, 0.50),
            "p95": _pct(vals, 0.95),
            "mean": sum(vals) / len(vals),
            "max": max(vals),
            "min": min(vals),
        }

    # --- worst position --------------------------------------------------
    worst_position = None
    worst_g_val = 0.0
    worst_g_pid = None
    worst_g_part = None
    for r in report.results:
        g = _safe(r.peak_g)
        if g > worst_g_val:
            worst_g_val = g
            worst_g_pid = r.position.pos_id
            worst_g_part = int(r.part_id)
    if worst_g_pid is not None:
        _face, wx, wy = pos_xy.get(worst_g_pid, ("", 0.0, 0.0))
        worst_position = {
            "pos_id": worst_g_pid,
            "x": wx, "y": wy,
            "peak_g": worst_g_val,
            "peak_g_part_id": worst_g_part,
        }

    advanced: dict = {}
    advanced["failure_risk"] = _build_failure_risk_payload(report)
    advanced["corr_network"] = _build_corr_network_payload(report)
    advanced["toa"] = _build_toa_payload(report)
    advanced["idw_predictor"] = _build_idw_predictor_payload(report)
    advanced["pareto_severity"] = _build_pareto_severity_payload(report)
    advanced["energy_partition"] = _build_energy_partition_payload(report)
    # === ADV_PAYLOAD_EXT_INSERT_HERE ===
    # Workflow-added entries below populate keys on ``advanced``.

    return {
        "grid": grid_payload,
        "positions": positions_list,
        "metrics": metrics_payload,
        "position_metrics": position_metrics,
        "position_top_parts": position_top_parts,
        "peak_g_matrix": peak_g_matrix,
        "peak_stress_matrix": peak_stress_matrix,
        # `part_position_matrix` alias removed — it was a verbatim copy of
        # peak_g_matrix and no JS consumer used it (audit confirmed).
        "trajectory_summary": traj_summary,
        "trajectory_ke_curves": traj_curves,
        "behavior_class_counts": behavior_counts,
        "per_part_stats": per_part_stats,
        "worst_position": worst_position,
        "total_ke_absorbed": total_ke_absorbed,
        "advanced": advanced,
    }


def _build_payload(report: ImpactReport) -> dict:
    """Distill an ImpactReport into a compact JSON payload for embedding.

    The payload is intentionally schema-driven (small keys) so a 5000-row
    matrix stays under ~500 KB.
    """
    has_real = bool(report.results)

    # --- meta ---------------------------------------------------------------
    meta = {
        "project": report.project_name or "Untitled Impact Study",
        "generation_mode": report.generation_mode or "DampingSpring",
        "boundary_distance": _safe(report.boundary_distance),
        "offset_distance": _safe(report.offset_distance),
        "test_dir": str(report.test_dir or ""),
        "is_mock": not has_real,
        "doe_config": report.doe_config or {},
        "sim_params": report.sim_params or {},
    }
    meta["impactor"] = _impactor_dict(report.impactor)

    # --- faces / parts / positions / results --------------------------------
    if has_real:
        faces = [
            {"code": f.code, "name": f.name,
             "roll": _safe(f.roll), "pitch": _safe(f.pitch), "yaw": _safe(f.yaw)}
            for f in report.faces
        ]
        parts = [
            {"id": int(p.part_id), "name": p.part_name,
             "group": p.group or PartInfo.extract_group(p.part_name),
             "footprint": p.footprint or None,
             "zmin": (p.z_range[0] if p.z_range else None),
             "zmax": (p.z_range[1] if p.z_range else None)}
            for p in report.parts
        ]
        positions: list[dict] = []
        for face_code, pos_list in report.positions_by_face.items():
            for pos in pos_list:
                positions.append({
                    "pos_id": pos.pos_id, "face": pos.face,
                    "x": _safe(pos.x), "y": _safe(pos.y),
                })
        def _ts_payload(ts):
            """Down-sample TimeSeriesData (times+max_values) for transport."""
            if not ts or not ts.times or not ts.max_values:
                return None
            n = len(ts.times)
            step = max(1, n // 300)  # cap ~300 pts to keep payload small
            return {
                "times":      [float(ts.times[i])      for i in range(0, n, step)],
                "max_values": [float(ts.max_values[i]) for i in range(0, n, step)],
            }
        results = [
            {
                "face": r.face, "pos_id": r.position.pos_id,
                "x": _safe(r.position.x), "y": _safe(r.position.y),
                "part_id": int(r.part_id),
                "g": _safe(r.peak_g),
                "s": _safe(r.peak_stress),
                "e": _safe(r.peak_strain),
                "d": _safe(r.peak_disp),
                "stress_ts": _ts_payload(r.stress_ts),
            }
            for r in report.results
        ]
        pname_map = {p["id"]: p["name"] for p in parts}
        for row in results:
            row["part_name"] = pname_map.get(row["part_id"], f"part_{row['part_id']}")
    else:
        mock = _build_mock_doe()
        faces = mock["faces"]
        parts = mock["parts"]
        positions = mock["positions"]
        results = mock["results"]

    # The previous bi-face hardcode (`keep_faces = {"F1", "F2"}`) silently
    # dropped every other face's data. We now honour whatever the loader
    # actually produced — single-face DOEs (e.g. F5 partial-impact on the
    # Top face) and multi-face DOEs both work.
    keep_faces = {f["code"] for f in faces}

    # --- device layout: bbox + per-part footprint from device_layout.json ---
    device_bbox = None
    device_outline = None
    layout_path = ""
    if report.test_dir:
        layout_path = os.path.join(str(report.test_dir), "device_layout.json")
    if layout_path and os.path.isfile(layout_path):
        try:
            with open(layout_path, "r", encoding="utf-8") as fh:
                layout = json.load(fh)
            bb = layout.get("bounding_box") or {}
            if bb:
                device_bbox = {
                    "xmin": _safe(bb.get("x_min", 0.0)),
                    "xmax": _safe(bb.get("x_max", 0.0)),
                    "ymin": _safe(bb.get("y_min", 0.0)),
                    "ymax": _safe(bb.get("y_max", 0.0)),
                }
            device_outline = layout.get("outline_xy") or None
            lp_by_id = {int(p["id"]): p for p in layout.get("parts", []) if "id" in p}
            for prec in parts:
                lp = lp_by_id.get(int(prec["id"]))
                if not lp:
                    continue
                if not prec.get("footprint") and lp.get("footprint"):
                    prec["footprint"] = lp["footprint"]
        except Exception:  # noqa: BLE001 - best-effort enrichment
            pass

    # fallback: derive bbox from positions if device_layout.json missing.
    # If no positions either, leave device_bbox=None so JS renders a
    # "no device layout" placeholder rather than synthesising fake extents.
    if device_bbox is None:
        xs = [p["x"] for p in positions if p["x"] is not None]
        ys = [p["y"] for p in positions if p["y"] is not None]
        if xs and ys:
            pad_x = (max(xs) - min(xs)) * 0.15 or 5.0
            pad_y = (max(ys) - min(ys)) * 0.15 or 5.0
            device_bbox = {
                "xmin": round(min(xs) - pad_x, 2), "xmax": round(max(xs) + pad_x, 2),
                "ymin": round(min(ys) - pad_y, 2), "ymax": round(max(ys) + pad_y, 2),
            }

    # fallback footprints: synthesize a small rect near device center for parts
    # without a real footprint (deterministic seed by part id). Only runs when
    # a real device_bbox exists; otherwise leave footprints empty.
    if device_bbox is not None:
        bb_w = device_bbox["xmax"] - device_bbox["xmin"]
        bb_h = device_bbox["ymax"] - device_bbox["ymin"]
        bb_cx = (device_bbox["xmax"] + device_bbox["xmin"]) / 2.0
        bb_cy = (device_bbox["ymax"] + device_bbox["ymin"]) / 2.0
        for prec in parts:
            if prec.get("footprint"):
                continue
            # deterministic offset by part id so different parts don't overlap
            pid = int(prec.get("id", 1))
            ang = (pid * 0.6180339887) * 2 * math.pi
            rad = 0.30 * min(bb_w, bb_h) * (0.4 + 0.5 * ((pid * 7) % 11) / 10.0)
            cx = bb_cx + rad * math.cos(ang)
            cy = bb_cy + rad * math.sin(ang)
            hw = max(2.0, 0.10 * bb_w * (0.5 + ((pid * 13) % 9) / 18.0))
            hh = max(2.0, 0.10 * bb_h * (0.5 + ((pid * 17) % 9) / 18.0))
            prec["footprint"] = [
                [round(cx - hw, 2), round(cy - hh, 2)],
                [round(cx + hw, 2), round(cy - hh, 2)],
                [round(cx + hw, 2), round(cy + hh, 2)],
                [round(cx - hw, 2), round(cy + hh, 2)],
            ]
            prec["_synthetic_footprint"] = True

    # --- energy flow --------------------------------------------------------
    energy_flows: dict[str, dict] = {}
    if report.energy_flows:
        for pos_id, flow in report.energy_flows.items():
            energy_flows[pos_id] = _energy_flow_dict(flow)
    if not energy_flows:
        energy_flows["__mock__"] = _build_mock_energy_flow()

    # --- aggregates ---------------------------------------------------------
    g_vals = [r["g"] for r in results if r["g"] > 0]
    s_vals = [r["s"] for r in results if r["s"] > 0]
    worst = max(results, key=lambda r: r["g"]) if results else {
        "face": "-", "x": 0, "y": 0, "part_name": "-", "g": 0
    }
    n_pos = len({(r["face"], r["pos_id"]) for r in results})
    n_parts = len(parts)
    n_pairs = len(results)
    crit_thresh = _pct(g_vals, 0.95) if g_vals else 0.0
    warn_thresh = _pct(g_vals, 0.75) if g_vals else 0.0
    influence_thresh = _pct(g_vals, 0.85) if g_vals else 0.0
    n_crit = sum(1 for v in g_vals if v >= crit_thresh)
    pos_max: dict[tuple[str, str], float] = {}
    for r in results:
        key = (r["face"], r["pos_id"])
        pos_max[key] = max(pos_max.get(key, 0.0), r["g"])
    median_g = statistics.median(pos_max.values()) if pos_max else 0.0
    n_safe = sum(1 for v in pos_max.values() if v < median_g * 0.6)
    diss_pct = 0.0
    for fl in energy_flows.values():
        ki = fl.get("ke_init", 0.0)
        d = fl.get("dissipated", 0.0)
        if ki > 0:
            diss_pct = max(diss_pct, 100.0 * d / ki)

    kpi = {
        "n_positions": n_pos,
        "n_faces": len(faces),
        "n_parts": n_parts,
        "n_pairs": n_pairs,
        "worst_g": round(worst["g"], 1) if worst else 0,
        "worst_s": round(max(s_vals) if s_vals else 0.0, 1),
        "n_critical": n_crit,
        "n_safe": n_safe,
        "diss_pct": round(diss_pct, 1),
        "worst": {
            "face": worst.get("face", "-"),
            "x": round(worst.get("x", 0.0), 2),
            "y": round(worst.get("y", 0.0), 2),
            "part_name": worst.get("part_name", "-"),
            "g": round(worst.get("g", 0.0), 1),
        },
        "crit_threshold": round(crit_thresh, 1),
        "warn_threshold": round(warn_thresh, 1),
        "influence_threshold": round(influence_thresh, 1),
    }

    # --- findings -----------------------------------------------------------
    findings = []
    for f in report.findings:
        findings.append({
            "severity": f.severity.value if isinstance(f.severity, Severity) else str(f.severity),
            "title": f.title,
            "detail": f.detail,
            "recommendation": f.recommendation,
        })

    # --- impactor trajectories + clusters (Tracker viz layer) -------------
    trajectories: dict[str, dict] = {}
    pos_xy: dict[str, tuple[str, float, float]] = {}
    for r in results:
        pos_xy[r["pos_id"]] = (r["face"], r["x"], r["y"])
    # try real trajectories first
    raw_traj = getattr(report, "impactor_trajectories", None) or {}
    for pos_id, traj in raw_traj.items():
        if traj is None:
            continue
        meta_xy = pos_xy.get(pos_id)
        if meta_xy is None:
            # try to find from positions_by_face
            for face_code, pos_list in (report.positions_by_face or {}).items():
                for pos in pos_list:
                    if pos.pos_id == pos_id:
                        meta_xy = (face_code, _safe(pos.x), _safe(pos.y))
                        break
                if meta_xy:
                    break
        if meta_xy is None:
            continue
        face_code, x, y = meta_xy
        if face_code not in keep_faces:
            continue
        n = len(getattr(traj, "times", []) or [])
        pos_list_xyz = []
        vel_list_xyz = []
        for i in range(n):
            pos_list_xyz.append([
                _safe(traj.pos_x[i] if i < len(traj.pos_x) else 0.0),
                _safe(traj.pos_y[i] if i < len(traj.pos_y) else 0.0),
                _safe(traj.pos_z[i] if i < len(traj.pos_z) else 0.0),
            ])
            vel_list_xyz.append([
                _safe(traj.vel_x[i] if i < len(traj.vel_x) else 0.0),
                _safe(traj.vel_y[i] if i < len(traj.vel_y) else 0.0),
                _safe(traj.vel_z[i] if i < len(traj.vel_z) else 0.0),
            ])
        rebound_xy = getattr(traj, "rebound_velocity_xy", (0.0, 0.0)) or (0.0, 0.0)
        trajectories[pos_id] = {
            "face": face_code,
            "x": _safe(x), "y": _safe(y),
            "t": [round(_safe(v), 8) for v in (traj.times or [])],
            "pos": pos_list_xyz,
            "vel": vel_list_xyz,
            "ke": [round(_safe(v), 5) for v in (traj.ke or [])],
            "contact": [bool(v) for v in (traj.contact_engaged or [])],
            "init_ke": _safe(traj.initial_ke),
            "final_ke": _safe(traj.final_ke),
            "ke_retention": _safe(traj.ke_retention),
            "max_pen": _safe(traj.max_penetration_depth),
            "t_first_contact": (_safe(traj.t_first_contact) if traj.t_first_contact is not None else None),
            "rebound_xy": [_safe(rebound_xy[0]), _safe(rebound_xy[1])],
            "rebound_speed": _safe(traj.rebound_speed),
            "incident_speed": _safe(traj.incident_speed),
            "behavior": getattr(traj, "behavior_class", "unknown") or "unknown",
        }

    # If no real trajectories are available, leave the dict empty and let the
    # JS render a "no trajectory data" placeholder. Synthesizing mock
    # trajectories (with magic ratio cutoffs, fallback v0/KE) would silently
    # show fabricated dynamics.

    # clusters
    clusters_payload = None
    raw_clusters = getattr(report, "trajectory_clusters", None)
    if raw_clusters is not None and getattr(raw_clusters, "n_clusters", 0) > 0:
        labels_list = list(raw_clusters.labels or [])
        # Map labels onto trajectories by results order (sibling agent contract)
        traj_keys = list(trajectories.keys())
        labels_map: dict[str, int] = {}
        for i, k in enumerate(traj_keys):
            if i < len(labels_list):
                labels_map[k] = int(labels_list[i])
        clusters_payload = {
            "n": int(raw_clusters.n_clusters),
            "labels": labels_map,
            "archetypes": list(raw_clusters.archetypes or []),
            "features_used": list(raw_clusters.features_used or []),
            "is_mock": False,
        }
    elif trajectories:
        # mock 4-cluster assignment by (behavior_class, position-region)
        archetype_for_behavior = {
            "bounce": 0, "rebound": 1, "slide": 2, "embed": 3,
        }
        labels_map = {}
        for k, t in trajectories.items():
            labels_map[k] = archetype_for_behavior.get(t["behavior"], 0)
        clusters_payload = {
            "n": 4,
            "labels": labels_map,
            "archetypes": ["fast-bounce", "decay-rebound", "slide-drift", "deep-embed"],
            "features_used": ["ke_retention", "max_pen", "rebound_speed", "behavior"],
            "is_mock": True,
        }
    else:
        clusters_payload = {
            "n": 0, "labels": {}, "archetypes": [], "features_used": [], "is_mock": True,
        }

    # --- per-part rigid-body motion (peak G summary + time series) ----------
    impactor_part_id = None
    try:
        if report.impactor and report.impactor.part_id is not None:
            impactor_part_id = int(report.impactor.part_id)
    except Exception:  # noqa: BLE001
        impactor_part_id = None

    # Aggregate peak_g per part_id (max across all PairResult entries)
    pname_lookup = {int(p["id"]): p["name"] for p in parts}
    peak_g_by_part: dict[int, float] = {}
    for r in report.results:
        try:
            pid = int(r.part_id)
        except Exception:  # noqa: BLE001
            continue
        g = _safe(getattr(r, "peak_g", 0.0))
        if g > peak_g_by_part.get(pid, 0.0):
            peak_g_by_part[pid] = g

    # Build per-(pos_id, part_id) time-series list (compact key strings)
    part_motion_series: list[dict] = []
    raw_motions = getattr(report, "part_motions", None) or {}
    for key, motion in raw_motions.items():
        if motion is None:
            continue
        try:
            pos_id, pid = key
            pid = int(pid)
        except Exception:  # noqa: BLE001
            continue
        times = list(getattr(motion, "times", []) or [])
        acc_mag = list(getattr(motion, "acc_mag", []) or [])
        if not times or not acc_mag:
            continue
        n = min(len(times), len(acc_mag))
        # downsample if very long (keep <= 600 points for SVG perf)
        step = max(1, n // 600)
        t_arr = [round(_safe(times[i]), 8) for i in range(0, n, step)]
        a_arr = [round(_safe(acc_mag[i]), 4) for i in range(0, n, step)]
        part_motion_series.append({
            "pos_id": str(pos_id),
            "part_id": pid,
            "part_name": getattr(motion, "part_name", "") or pname_lookup.get(pid, f"part_{pid}"),
            "t": t_arr,
            "a": a_arr,
            "peak_g": _safe(getattr(motion, "peak_g", 0.0)),
            "t_peak_g": _safe(getattr(motion, "t_peak_g", 0.0)),
            "peak_vel": _safe(getattr(motion, "peak_vel", 0.0)),
            "peak_disp": _safe(getattr(motion, "peak_disp", 0.0)),
        })

    # Per-part summary rows: prefer PartMotion's scalars when available,
    # otherwise fall back to the aggregated PairResult.peak_g.
    motion_by_pid: dict[int, Any] = {}
    for key, motion in raw_motions.items():
        try:
            _, pid = key
            pid = int(pid)
        except Exception:  # noqa: BLE001
            continue
        if motion is None:
            continue
        # If multiple positions for same part, keep the one with highest peak_g
        prev = motion_by_pid.get(pid)
        if prev is None or _safe(getattr(motion, "peak_g", 0.0)) > _safe(getattr(prev, "peak_g", 0.0)):
            motion_by_pid[pid] = motion

    summary_rows: list[dict] = []
    all_pids = set(peak_g_by_part.keys()) | set(motion_by_pid.keys())
    for pid in sorted(all_pids):
        m = motion_by_pid.get(pid)
        pg = _safe(getattr(m, "peak_g", 0.0)) if m is not None else 0.0
        if pg <= 0:
            pg = peak_g_by_part.get(pid, 0.0)
        summary_rows.append({
            "part_id": pid,
            "part_name": (getattr(m, "part_name", "") if m is not None else "")
                         or pname_lookup.get(pid, f"part_{pid}"),
            "peak_g": pg,
            "t_peak_g": _safe(getattr(m, "t_peak_g", 0.0)) if m is not None else 0.0,
            "peak_vel": _safe(getattr(m, "peak_vel", 0.0)) if m is not None else 0.0,
            "peak_disp": _safe(getattr(m, "peak_disp", 0.0)) if m is not None else 0.0,
            "is_impactor": (impactor_part_id is not None and pid == impactor_part_id),
        })
    summary_rows.sort(key=lambda r: r["peak_g"], reverse=True)

    # First-contact marker (use any trajectory's t_first_contact when available)
    t_first_contact = None
    for tr in trajectories.values():
        tfc = tr.get("t_first_contact")
        if tfc is not None and tfc > 0:
            t_first_contact = float(tfc)
            break

    part_motion_payload = {
        "summary": summary_rows,
        "series": part_motion_series,
        "impactor_part_id": impactor_part_id,
        "t_first_contact": t_first_contact,
        "g_mm_s2": 9810.0,
    }

    # --- unit labels (data-driven; empty when units unspecified) ------------
    # Currently the only supported LS-DYNA convention is [ton, mm, s, MPa]
    # (consistent with the d3plot loader). If sim_params doesn't declare a
    # unit system we leave the labels empty rather than fabricate them.
    _unit_system = (report.sim_params or {}).get("units", "")
    if isinstance(_unit_system, str) and _unit_system.strip().lower() in (
        "ton_mm_s_mpa", "ton-mm-s-mpa", "ton,mm,s,mpa", "dyna_mm",
    ):
        unit_labels = {
            "acc": "mm/s²", "stress": "MPa", "disp": "mm",
            "vel": "mm/s", "energy": "mJ", "time": "ms",
            "mass": "ton", "force": "N",
        }
    else:
        unit_labels = {
            "acc": "", "stress": "", "disp": "",
            "vel": "", "energy": "", "time": "",
            "mass": "", "force": "",
        }

    # --- energy-flow normalization constants (data-driven) ------------------
    _max_ie = 0.0
    for _fl in energy_flows.values():
        for _n in (_fl.get("nodes") or []):
            _ie_arr = _n.get("ie") or []
            if _ie_arr:
                _ie_last = _ie_arr[-1] if isinstance(_ie_arr[-1], (int, float)) else 0.0
                if _ie_last > _max_ie:
                    _max_ie = float(_ie_last)
    energy_flow_thresholds = {
        # ratio of peak_f below which an edge is considered "not engaged"
        "engage_ratio": 0.05,
        # ratio of peak_f below which an edge is considered "not active" at t
        "active_ratio": 0.001,
    }

    return {
        "meta": meta,
        "kpi": kpi,
        "faces": faces,
        "parts": parts,
        "positions": positions,
        "results": results,
        "energy_flows": energy_flows,
        "findings": findings,
        "device_bbox": device_bbox,
        "device_outline": device_outline,
        "trajectories": trajectories,
        "clusters": clusters_payload,
        "part_motion": part_motion_payload,
        "doe_analysis": _build_doe_payload(report),
        "unit_labels": unit_labels,
        # risk_score = None means JS hides the panel; callers can opt in by
        # populating this with {"weights": {"worst","p95","crit"}, "crit_band", "warn_band"}.
        "risk_score": None,
        "energy_flow_thresholds": energy_flow_thresholds,
        "energy_flow_max_ie": _max_ie,
        # None disables the conservation-tolerance banner; set to a percent
        # (e.g. 5.0) to enable the residual check.
        "energy_conservation_tolerance": None,
    }


# ---------------------------------------------------------------------------
# HTML template — CSS
# ---------------------------------------------------------------------------

_CSS = r"""
* { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --bg: #0a0c14;
  --bg2: #11141f;
  --bg3: #1a1e2e;
  --bg4: #232839;
  --line: rgba(255,255,255,0.06);
  --line2: rgba(255,255,255,0.10);
  --fg: #e6ebff;
  --fg2: #aab2cf;
  --dim: #5c6383;
  --num: #c8d4ff;
  --accent: #4dd6ff;
  --accent2: #ff5e84;
  --warn: #f0a830;
  --good: #4adfa1;
  --crit: #ff3854;
  --tag: #b46eff;
}
html, body {
  background: var(--bg); color: var(--fg);
  font-family: 'Inter', -apple-system, 'Pretendard', 'Segoe UI', system-ui, sans-serif;
  font-size: 12px; -webkit-font-smoothing: antialiased;
  overflow-x: hidden;
}
.mono, .num { font-family: 'JetBrains Mono', 'SF Mono', Menlo, 'Courier New', monospace; font-variant-numeric: tabular-nums; }
b { color: var(--fg); font-weight: 600; }
.topbar { position: sticky; top: 0; z-index: 50; background: rgba(10,12,20,0.88); backdrop-filter: blur(12px); border-bottom: 1px solid var(--line); display: grid; grid-template-columns: auto 1fr auto; align-items: center; padding: 10px 32px; gap: 24px; }
.topbar .brand { font-size: 11px; letter-spacing: 4px; color: var(--accent); font-weight: 700; }
.topbar .meta { display: flex; gap: 20px; font-size: 11px; color: var(--dim); overflow-x: auto; white-space: nowrap; }
.topbar .meta b { color: var(--fg2); font-weight: 500; }
.topbar .nav { display: flex; gap: 4px; }
.topbar .nav a { text-decoration: none; color: var(--dim); padding: 4px 10px; border-radius: 4px; font-size: 11px; letter-spacing: 2px; font-weight: 600; transition: all 0.2s; cursor: pointer; }
.topbar .nav a:hover { color: var(--fg); background: var(--bg3); }
.topbar .nav a.active { color: var(--bg); background: var(--accent); }
.page { padding: 28px 32px 60px; max-width: 1680px; margin: 0 auto; }
.page-head { display: flex; align-items: baseline; gap: 16px; margin-bottom: 18px; padding-bottom: 14px; border-bottom: 1px solid var(--line); flex-wrap: wrap; }
.page-head .num { font-size: 24px; font-weight: 800; color: var(--accent); letter-spacing: -1px; }
.page-head .ttl { font-size: 20px; font-weight: 700; }
.page-head .sub { color: var(--dim); font-size: 12px; flex: 1; text-align: right; letter-spacing: 1px; }
.page-head .tagline { color: var(--tag); font-size: 11px; letter-spacing: 4px; font-weight: 600; }
.grid { display: grid; gap: 14px; }
.g-12 { grid-template-columns: repeat(12, 1fr); }
.panel { background: var(--bg2); border: 1px solid var(--line); border-radius: 8px; padding: 14px 16px; position: relative; overflow: hidden; }
.panel .ph { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 10px; padding-bottom: 8px; border-bottom: 1px solid var(--line); }
.panel .ph .pt { font-size: 11px; font-weight: 700; letter-spacing: 2px; color: var(--accent); }
.panel .ph .pd { font-size: 10px; color: var(--dim); }
.panel .pcap { font-size: 10px; color: var(--dim); margin-top: 8px; line-height: 1.5; }
.col-3{grid-column:span 3;} .col-4{grid-column:span 4;} .col-5{grid-column:span 5;} .col-6{grid-column:span 6;} .col-7{grid-column:span 7;} .col-8{grid-column:span 8;} .col-9{grid-column:span 9;} .col-12{grid-column:span 12;}
.kpi-strip { display: grid; grid-template-columns: repeat(8, 1fr); gap: 0; border: 1px solid var(--line); border-radius: 8px; overflow: hidden; background: var(--bg2); }
.kpi-strip .k { padding: 10px 14px; border-right: 1px solid var(--line); }
.kpi-strip .k:last-child { border-right: none; }
.kpi-strip .k .v { font-size: 17px; font-weight: 700; color: var(--fg); font-family: 'JetBrains Mono', monospace; }
.kpi-strip .k .v .u { color: var(--dim); font-size: 11px; font-weight: 500; margin-left: 4px; font-family: 'Inter', system-ui; }
.kpi-strip .k .l { font-size: 9px; color: var(--dim); letter-spacing: 2px; text-transform: uppercase; margin-top: 4px; }
table.dt { width: 100%; border-collapse: collapse; font-size: 11px; }
table.dt th { color: var(--dim); font-weight: 600; text-align: right; padding: 6px 6px; border-bottom: 1px solid var(--line2); font-size: 10px; letter-spacing: 1px; text-transform: uppercase; white-space: nowrap; }
table.dt th.tl { text-align: left; }
table.dt td { padding: 5px 6px; border-bottom: 1px solid var(--line); text-align: right; vertical-align: middle; white-space: nowrap; }
table.dt td.tl { text-align: left; }
table.dt tr:hover td { background: rgba(255,255,255,0.02); }
table.dt tr.r-crit td:first-child::before { content: '\25A0 '; color: var(--crit); }
table.dt tr.r-warn td:first-child::before { content: '\25A0 '; color: var(--warn); }
table.dt tr.r-safe td:first-child::before { content: '\25A0 '; color: var(--good); }
table.dt td.num { color: var(--num); font-family: 'JetBrains Mono', monospace; }
table.dt td.dim { color: var(--dim); }
table.dt td.b { color: var(--fg); font-weight: 600; }
.hero-line { display: grid; grid-template-columns: 1fr auto; gap: 24px; align-items: end; padding: 8px 0 18px; }
.hero-line h1 { font-size: 28px; font-weight: 800; letter-spacing: -1px; line-height: 1.1; color: var(--fg); }
.hero-line h1 .acc { color: var(--accent); }
.hero-line .lede { color: var(--fg2); font-size: 12px; margin-top: 6px; max-width: 700px; line-height: 1.6; }
.hero-line .right { text-align: right; }
.hero-line .right .pk { color: var(--crit); font-size: 11px; letter-spacing: 3px; font-weight: 700; }
.hero-line .right .pkv { font-family: 'JetBrains Mono', monospace; font-size: 14px; color: var(--fg); margin-top: 4px; }
.method-band .band-head { display:flex; justify-content:space-between; font-size:9px; letter-spacing:2px; color:var(--accent); font-weight:700; margin-bottom:6px; padding-bottom:5px; border-bottom:1px solid var(--line); }
.method-band .band-head .band-sub { color: var(--dim); font-weight: 500; letter-spacing: 1px; }
.method-band .band-cap { font-size: 9.5px; color: var(--dim); margin-top: 6px; line-height: 1.4; }
.method-band .dt td { padding: 3px 6px; font-size: 10px; }
.r { opacity: 0; transform: translateY(8px); transition: opacity 0.6s ease, transform 0.6s ease; }
.r.in { opacity: 1; transform: translateY(0); }
.foot { text-align: center; padding: 24px 16px; color: var(--dim); font-size: 10px; letter-spacing: 2px; border-top: 1px solid var(--line); margin-top: 40px; }
.cube-net { position: relative; width: 100%; aspect-ratio: 4/3; background: var(--bg3); border-radius: 6px; padding: 8px; }
.cube-net svg { width: 100%; height: 100%; display: block; }
.cube-cell text { font-family: 'JetBrains Mono', monospace; }
.cube-cell.risky rect.cell-frame { stroke: var(--crit); stroke-width: 1.5; animation: pulse-stroke 1.6s infinite; }
@keyframes pulse-stroke { 0%, 100% { stroke-opacity: 1; } 50% { stroke-opacity: 0.3; } }
.pulse-dot { animation: pulse-dot 1.5s infinite; }
@keyframes pulse-dot { 0%, 100% { r: 3; opacity: 1; } 50% { r: 6; opacity: 0.4; } }
.ctlbar { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; padding: 10px 14px; background: var(--bg2); border: 1px solid var(--line); border-radius: 8px; margin-bottom: 14px; }
.ctlbar .grp { display: flex; gap: 4px; align-items: center; }
.ctlbar .lbl { font-size: 9px; letter-spacing: 2px; color: var(--dim); font-weight: 700; margin-right: 4px; }
.ctlbar .btn { background: var(--bg3); color: var(--fg2); border: 1px solid var(--line2); padding: 4px 10px; font-size: 11px; border-radius: 3px; cursor: pointer; font-family: 'JetBrains Mono', monospace; letter-spacing: 1px; transition: all 0.15s; }
.ctlbar .btn:hover { background: var(--bg4); color: var(--fg); }
.ctlbar .btn.active { background: var(--accent); color: var(--bg); border-color: var(--accent); }
.ctlbar input[type=text] { background: var(--bg3); color: var(--fg); border: 1px solid var(--line2); padding: 4px 10px; font-size: 11px; border-radius: 3px; font-family: 'JetBrains Mono', monospace; width: 180px; }
.mini-xy-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
.mini-xy { background: var(--bg3); border: 1px solid var(--line); border-radius: 4px; padding: 4px 4px 3px; cursor: pointer; transition: border-color 0.2s; }
.mini-xy:hover { border-color: var(--accent); }
.mini-xy.dim { opacity: 0.35; }
.mini-xy .mlabel { display: flex; justify-content: space-between; font-size: 9px; font-weight: 600; color: var(--fg2); margin-bottom: 2px; line-height: 1.2; }
.mini-xy .mlabel .mid { color: var(--accent); }
.mini-xy .mlabel .mval { color: var(--num); font-family: 'JetBrains Mono', monospace; }
.mini-xy svg { width: 100%; height: 80px; display: block; }
.mini-xy .mfoot { display: flex; justify-content: space-between; font-size: 8.5px; color: var(--dim); font-family: 'JetBrains Mono', monospace; margin-top: 2px; padding-top: 2px; border-top: 1px solid var(--line); }
.imatrix { width: 100%; border-collapse: collapse; font-size: 10px; }
.imatrix th, .imatrix td { padding: 2px 4px; text-align: center; font-family: 'JetBrains Mono', monospace; }
.imatrix th.tl { text-align: left; }
.imatrix td.cell { width: 18px; height: 18px; border-radius: 2px; }
.imatrix tr:hover td { background: rgba(77, 214, 255, 0.04); }
.verdict-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.verdict-cell { padding: 12px 16px; background: var(--bg2); border-left: 3px solid var(--dim); border-radius: 4px; }
.verdict-cell.crit { border-left-color: var(--crit); }
.verdict-cell.warn { border-left-color: var(--warn); }
.verdict-cell.safe { border-left-color: var(--good); }
.verdict-cell .vl { font-size: 9px; color: var(--dim); letter-spacing: 3px; font-weight: 700; }
.verdict-cell .vn { font-size: 24px; font-weight: 700; margin-top: 2px; font-family: 'JetBrains Mono', monospace; }
.verdict-cell.crit .vn { color: var(--crit); }
.verdict-cell.warn .vn { color: var(--warn); }
.verdict-cell.safe .vn { color: var(--good); }
.verdict-cell .vd { font-size: 10px; color: var(--fg2); margin-top: 4px; line-height: 1.4; }
.ts-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; }
.ts-mini { background: var(--bg3); border: 1px solid var(--line); border-radius: 4px; padding: 6px 8px; }
.ts-mini .tlabel { display: flex; justify-content: space-between; font-size: 9px; color: var(--fg2); margin-bottom: 3px; }
.ts-mini svg { width: 100%; height: 64px; display: block; }
.eg-wrap { position: relative; background: var(--bg3); border-radius: 4px; height: 420px; overflow: hidden; }
.eg-wrap canvas { display: block; width: 100%; height: 100%; cursor: crosshair; }
.eg-side { position: absolute; right: 8px; top: 8px; width: 200px; padding: 8px 10px; background: rgba(17,20,31,0.92); border: 1px solid var(--line); border-radius: 4px; font-size: 10px; pointer-events: none; line-height: 1.5; display: none; }
.eg-side.show { display: block; }
.eg-side .ttl { color: var(--accent); font-weight: 700; font-size: 10px; letter-spacing: 1px; margin-bottom: 4px; }
.eg-side .row { display: flex; justify-content: space-between; color: var(--fg2); }
.eg-side .row b { color: var(--fg); font-family: 'JetBrains Mono', monospace; }
.scrub { display: flex; gap: 10px; align-items: center; padding: 8px 10px; background: var(--bg3); border-radius: 4px; margin-top: 8px; }
.scrub input[type=range] { flex: 1; accent-color: var(--accent); }
.scrub .btn { background: var(--bg4); color: var(--fg); border: 1px solid var(--line2); padding: 3px 10px; font-size: 11px; border-radius: 3px; cursor: pointer; font-family: 'JetBrains Mono', monospace; }
.scrub .btn:hover { background: var(--bg2); }
.scrub .tlabel { font-size: 10px; color: var(--dim); font-family: 'JetBrains Mono', monospace; min-width: 90px; text-align: right; }
.scrub .tlabel b { color: var(--accent); }
.sankey-row { display: grid; grid-template-columns: 110px 1fr 110px 60px; gap: 8px; align-items: center; padding: 3px 0; border-bottom: 1px solid var(--line); font-size: 10px; }
.sankey-row .src { color: var(--fg); font-weight: 600; text-align: right; font-family: 'JetBrains Mono', monospace; }
.sankey-row .dst { color: var(--accent); font-family: 'JetBrains Mono', monospace; }
.sankey-row .val { color: var(--num); text-align: right; font-family: 'JetBrains Mono', monospace; }
.sankey-row .bar { height: 12px; background: linear-gradient(90deg, var(--tag), var(--accent)); border-radius: 2px; }
.tfh { display: grid; gap: 1px; }
.tfh-row { display: grid; grid-template-columns: 140px repeat(21, 1fr); gap: 1px; align-items: center; font-size: 9px; height: 16px; }
.tfh-row .lab { color: var(--fg2); padding-right: 6px; text-align: right; font-family: 'JetBrains Mono', monospace; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tfh-row .cell { background: var(--bg4); border-radius: 1px; height: 14px; }
.tfh-head { display: grid; grid-template-columns: 140px repeat(21, 1fr); gap: 1px; font-size: 8px; color: var(--dim); padding-right: 6px; }
.tfh-head .h0 { text-align: right; padding-right: 6px; }
.tfh-head .ht { text-align: center; }
.cons-box { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 6px; }
.cons-cell { background: var(--bg3); padding: 8px 10px; border-radius: 4px; border-left: 2px solid var(--tag); }
.cons-cell.warn { border-left-color: var(--crit); }
.cons-cell .v { font-family: 'JetBrains Mono', monospace; font-size: 16px; font-weight: 700; color: var(--fg); }
.cons-cell .l { font-size: 9px; color: var(--dim); letter-spacing: 2px; text-transform: uppercase; margin-top: 2px; }
.cons-bar { margin-top: 8px; height: 8px; background: var(--bg4); border-radius: 4px; overflow: hidden; display: flex; }
.cons-bar .seg { height: 100%; }
.cons-banner { margin-top: 8px; padding: 6px 10px; background: rgba(255, 56, 84, 0.1); border-left: 2px solid var(--crit); font-size: 10px; color: var(--crit); border-radius: 3px; display: none; }
.cons-banner.on { display: block; }
.face-big { background: var(--bg3); border-radius: 4px; padding: 8px; }
.face-big svg { width: 100%; display: block; }
.face-big-foot { display: flex; justify-content: space-between; font-size: 10px; color: var(--dim); margin-top: 6px; padding-top: 6px; border-top: 1px solid var(--line); font-family: 'JetBrains Mono', monospace; }
.compare-grid { display: grid; gap: 4px; }
.compare-cell { background: var(--bg3); border: 1px solid var(--line); border-radius: 3px; padding: 3px; }
.compare-cell svg { width: 100%; height: 70px; display: block; }
.compare-cell .cclbl { font-size: 8.5px; color: var(--fg2); font-family: 'JetBrains Mono', monospace; text-align: center; }
@media (max-width: 1280px) {
  .col-3, .col-4, .col-5, .col-6, .col-7, .col-8, .col-9 { grid-column: span 12; }
  .mini-xy-grid { grid-template-columns: repeat(2, 1fr); }
  .ts-grid { grid-template-columns: repeat(2, 1fr); }
  .topbar { padding: 10px 16px; }
  .page { padding: 20px 16px; }
}

/* ---------- Bi-Face Split (Page 1) ---------- */
.biface-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
@media (max-width: 980px) { .biface-grid { grid-template-columns: 1fr; } }
.biface-cell { background: var(--bg3); border: 1px solid var(--line); border-radius: 6px; padding: 10px 12px 8px; cursor: pointer; transition: border-color 0.15s, box-shadow 0.15s; }
.biface-cell:hover { border-color: var(--accent); box-shadow: 0 0 0 1px rgba(77,214,255,0.25) inset; }
.biface-cell .bf-head { display: flex; justify-content: space-between; align-items: baseline; padding-bottom: 6px; border-bottom: 1px solid var(--line); margin-bottom: 6px; }
.biface-cell .bf-name { font-family: 'JetBrains Mono', monospace; font-size: 12px; color: var(--accent); letter-spacing: 1px; font-weight: 700; }
.biface-cell .bf-sub { font-size: 9px; color: var(--dim); letter-spacing: 2px; }
.biface-cell svg { width: 100%; display: block; aspect-ratio: 5/3; }
.biface-cell .bf-foot { display: flex; justify-content: space-between; font-size: 10px; color: var(--fg2); padding-top: 6px; margin-top: 4px; border-top: 1px solid var(--line); font-family: 'JetBrains Mono', monospace; }
.biface-cell .bf-foot b { color: var(--crit); }

/* ---------- Impact Inspector (Page 2) ---------- */
.ii-wrap { display: grid; grid-template-columns: 1fr 320px; gap: 14px; }
@media (max-width: 1100px) { .ii-wrap { grid-template-columns: 1fr; } }
.ii-main { background: var(--bg2); border: 1px solid var(--line); border-radius: 8px; padding: 14px 16px; }
.ii-side { background: var(--bg2); border: 1px solid var(--line); border-radius: 8px; padding: 12px 14px; display: flex; flex-direction: column; gap: 12px; max-height: 660px; overflow-y: auto; }
.ii-canvas-wrap { position: relative; background: #0e1320; border-radius: 6px; padding: 4px; }
.ii-canvas-wrap svg { width: 100%; display: block; aspect-ratio: 4/3; cursor: crosshair; }
.ii-cbar { display: flex; align-items: center; gap: 8px; margin-top: 8px; font-size: 10px; color: var(--dim); font-family: 'JetBrains Mono', monospace; }
.ii-cbar .grad { flex: 1; height: 10px; border-radius: 2px;
  background: linear-gradient(90deg, rgb(68,1,84) 0%, rgb(59,82,139) 20%, rgb(33,144,141) 40%, rgb(93,201,99) 60%, rgb(253,231,37) 80%, rgb(253,80,60) 100%); }
.ii-side .iibox { background: var(--bg3); border: 1px solid var(--line); border-radius: 4px; padding: 8px 10px; }
.ii-side .iibox .iihd { font-size: 9px; color: var(--accent); letter-spacing: 2px; font-weight: 700; margin-bottom: 4px; }
.ii-side .iirow { display: flex; justify-content: space-between; font-size: 11px; color: var(--fg2); margin-top: 2px; }
.ii-side .iirow b { color: var(--fg); font-family: 'JetBrains Mono', monospace; }
.ii-bar-row { display: grid; grid-template-columns: 90px 1fr 50px; gap: 6px; align-items: center; font-size: 10px; padding: 2px 0; cursor: pointer; border-radius: 3px; }
.ii-bar-row:hover { background: rgba(77,214,255,0.08); }
.ii-bar-row.is-max b { color: var(--crit); }
.ii-bar-row .nm { color: var(--fg2); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-family: 'JetBrains Mono', monospace; }
.ii-bar-row .bw { background: var(--bg4); border-radius: 2px; height: 8px; overflow: hidden; }
.ii-bar-row .bw .fl { display: block; height: 100%; border-radius: 2px; }
.ii-bar-row .vl { text-align: right; color: var(--num); font-family: 'JetBrains Mono', monospace; }
.ii-th { width: 100%; height: 70px; display: block; }
.ii-empty { color: var(--dim); font-size: 10px; padding: 6px 2px; font-style: italic; }
.ii-pin { display: inline-flex; align-items: center; gap: 4px; cursor: pointer; user-select: none; font-size: 10px; color: var(--fg2); letter-spacing: 1px; }
.ii-pin input { accent-color: var(--accent); }
.ii-pin.locked { color: var(--accent2); }
.ii-thresh { display: flex; align-items: center; gap: 8px; }
.ii-thresh input[type=range] { flex: 1; accent-color: var(--accent); min-width: 100px; }
.ii-thresh .vlab { font-size: 10px; color: var(--num); font-family: 'JetBrains Mono', monospace; min-width: 60px; text-align: right; }

@keyframes ii-pulse {
  0%   { r: 6;  opacity: 0.9; }
  100% { r: 14; opacity: 0;   }
}
.ii-halo { animation: ii-pulse 1.1s linear infinite; }

/* ---------- Trajectory viz family (6 new panels) ---------- */
.bvm-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
@media (max-width: 980px) { .bvm-grid { grid-template-columns: 1fr; } }
.bvm-cell { background: var(--bg3); border: 1px solid var(--line); border-radius: 6px; padding: 10px 12px 8px; }
.bvm-cell .bf-head { display: flex; justify-content: space-between; align-items: baseline; padding-bottom: 6px; border-bottom: 1px solid var(--line); margin-bottom: 6px; }
.bvm-cell .bf-name { font-family: 'JetBrains Mono', monospace; font-size: 12px; color: var(--accent); letter-spacing: 1px; font-weight: 700; }
.bvm-cell .bf-sub { font-size: 9px; color: var(--dim); letter-spacing: 2px; }
.bvm-cell svg { width: 100%; aspect-ratio: 5/3; display: block; }
.bvm-legend { display: flex; gap: 14px; flex-wrap: wrap; font-size: 10px; padding-top: 6px; margin-top: 4px; border-top: 1px solid var(--line); font-family: 'JetBrains Mono', monospace; }
.bvm-legend .lg { display: inline-flex; gap: 5px; align-items: center; color: var(--fg2); }
.bvm-legend .lg .sw { width: 10px; height: 10px; border-radius: 2px; display: inline-block; }
.bvm-legend .lg b { color: var(--fg); }

.tcm-archetypes { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-top: 10px; }
@media (max-width: 980px) { .tcm-archetypes { grid-template-columns: repeat(2, 1fr); } }
.tcm-arch { background: var(--bg3); border: 1px solid var(--line); border-radius: 4px; padding: 8px 10px; }
.tcm-arch .ah { display: flex; justify-content: space-between; align-items: baseline; }
.tcm-arch .ah .nm { font-family: 'JetBrains Mono', monospace; font-size: 10px; font-weight: 700; }
.tcm-arch .ah .ct { font-size: 9px; color: var(--dim); font-family: 'JetBrains Mono', monospace; }
.tcm-arch svg { width: 100%; height: 36px; display: block; margin-top: 4px; }

.phase-wrap { position: relative; }
.phase-wrap svg { width: 100%; height: 380px; display: block; background: var(--bg3); border-radius: 4px; }

.cseq-grid { display: grid; grid-template-columns: 110px 1fr; gap: 8px 4px; font-size: 10px; align-items: center; }
.cseq-grid .lab { color: var(--fg2); font-family: 'JetBrains Mono', monospace; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.cseq-row { display: grid; grid-template-columns: repeat(21, 1fr); gap: 1px; }
.cseq-cell { height: 14px; background: var(--bg4); border-radius: 1px; }

.tb3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
@media (max-width: 980px) { .tb3 { grid-template-columns: 1fr; } }
.tb3-cell { background: var(--bg3); border: 1px solid var(--line); border-radius: 4px; padding: 6px 8px; }
.tb3-cell .h { display: flex; justify-content: space-between; font-size: 10px; color: var(--accent); font-family: 'JetBrains Mono', monospace; letter-spacing: 1px; padding-bottom: 4px; border-bottom: 1px solid var(--line); margin-bottom: 4px; }
.tb3-cell svg { width: 100%; height: 220px; display: block; }

.bbadge { display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 9px; font-weight: 700; letter-spacing: 1px; font-family: 'JetBrains Mono', monospace; color: var(--bg); margin-left: 6px; }
.bbadge.bounce { background: var(--good); }
.bbadge.rebound { background: var(--warn); }
/* slide previously collided with rebound on orange — use the lateral-motion
   purple accent so they are visually distinct. Kept the JS palette in sync
   via DOE_BEHAVIOR_COLOR = BEHAVIOR_COLOR. */
.bbadge.slide { background: #b46eff; color: #fff; }
.bbadge.embed { background: var(--crit); color: #fff; }
.bbadge.unknown { background: var(--dim); }

.traj-na { color: var(--dim); font-size: 10px; padding: 8px 4px; text-align: center; font-style: italic; }

/* ---------- DOE Analysis (Section 05) ---------- */
.doe-row { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr); gap: 14px; }
@media (max-width: 1100px) { .doe-row { grid-template-columns: 1fr; } }
.doe-grid-wrap { background: var(--bg3); border-radius: 6px; padding: 10px 12px; }
.doe-grid-wrap svg { width: 100%; display: block; aspect-ratio: 1/1; }
.doe-cell-label { font-family: 'JetBrains Mono', monospace; pointer-events: none; }
.doe-cell rect { cursor: pointer; transition: stroke-width 0.1s; }
.doe-cell.active rect { stroke: var(--accent); stroke-width: 2; }
.doe-rank { max-height: 520px; overflow-y: auto; }
.doe-rank table { width: 100%; }
.doe-pp-matrix-wrap { background: var(--bg3); border-radius: 6px; padding: 10px 12px; overflow-x: auto; }
.doe-pp-matrix-wrap svg { display: block; min-width: 100%; }
.doe-traj-mm { display: grid; gap: 4px; }
.doe-traj-cell { background: var(--bg3); border: 1px solid var(--line); border-radius: 3px; padding: 3px 4px; position: relative; }
.doe-traj-cell svg { width: 100%; height: 56px; display: block; }
.doe-traj-cell .tc-lbl { font-size: 8px; color: var(--fg2); font-family: 'JetBrains Mono', monospace; display: flex; justify-content: space-between; }
.doe-traj-cell.worst { border-color: var(--crit); box-shadow: 0 0 0 1px rgba(255,56,84,0.4) inset; }
.doe-traj-cell .star { position: absolute; right: 3px; top: 1px; font-size: 11px; color: var(--crit); }
.doe-env-wrap { background: var(--bg3); border-radius: 6px; padding: 10px 12px; }
.doe-env-row { display: grid; grid-template-columns: 130px 1fr 56px; gap: 8px; align-items: center; padding: 3px 0; border-bottom: 1px solid var(--line); font-size: 10px; }
.doe-env-row:last-child { border-bottom: none; }
.doe-env-row .nm { font-family: 'JetBrains Mono', monospace; color: var(--fg); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.doe-env-row .wis svg { width: 100%; height: 14px; display: block; }
.doe-env-row .rt { font-family: 'JetBrains Mono', monospace; color: var(--num); text-align: right; }
.doe-empty { color: var(--dim); padding: 24px 12px; font-size: 12px; text-align: center; font-style: italic; }
.doe-kpi-bb { display: inline-flex; gap: 2px; margin-top: 2px; }
.doe-kpi-bb span { display: inline-block; height: 8px; border-radius: 1px; }
.doe-failrisk-wrap{display:grid;grid-template-columns:minmax(280px, 1fr) minmax(360px, 1.2fr);gap:18px;padding:10px 4px 4px 4px;}
.doe-failrisk-left,.doe-failrisk-right{display:flex;flex-direction:column;gap:8px;min-width:0;}
.doe-failrisk-subhead{font-size:12px;color:var(--fg2);letter-spacing:.04em;text-transform:uppercase;}
.doe-failrisk-grid{display:grid;gap:4px;aspect-ratio:1/1;background:var(--bg3);padding:4px;border-radius:4px;}
.doe-failrisk-cell{display:flex;flex-direction:column;justify-content:center;align-items:center;border-radius:3px;color:#0b0b0b;font-weight:600;padding:2px;min-height:0;line-height:1.05;}
.doe-failrisk-cell.doe-failrisk-empty{background:transparent;color:var(--dim);font-weight:400;}
.doe-failrisk-cell.doe-failrisk-nodata{background:var(--bg2);color:var(--dim);font-weight:400;}
.doe-failrisk-pid{font-size:10px;opacity:.85;}
.doe-failrisk-sfval{font-size:11px;font-weight:700;}
.doe-failrisk-legend{display:flex;flex-wrap:wrap;gap:8px;font-size:11px;color:var(--fg2);margin-top:4px;}
.doe-failrisk-lg{padding:2px 6px;border-radius:3px;color:#0b0b0b;font-weight:600;}
.doe-failrisk-lg.crit{background:var(--crit);}
.doe-failrisk-lg.warn{background:var(--warn);}
.doe-failrisk-lg.good{background:var(--good);}
.doe-failrisk-list{display:flex;flex-direction:column;gap:4px;}
.doe-failrisk-item{display:grid;grid-template-columns:18px 10px 1fr auto;gap:8px;align-items:center;padding:6px 8px;background:var(--bg2);border:1px solid var(--line);border-radius:4px;}
.doe-failrisk-rank{font-size:11px;color:var(--dim);text-align:right;}
.doe-failrisk-dot{display:inline-block;width:10px;height:10px;border-radius:50%;}
.doe-failrisk-name{min-width:0;}
.doe-failrisk-pname{font-size:12px;color:var(--fg);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.doe-failrisk-pmeta{font-size:10px;color:var(--dim);}
.doe-failrisk-sf{display:flex;flex-direction:column;align-items:flex-end;gap:2px;}
.doe-failrisk-sfbig{font-size:12px;font-weight:700;letter-spacing:.02em;}
.doe-failrisk-whisker{display:block;}
.doe-failrisk-foot{font-size:11px;color:var(--dim);padding:6px 4px 0 4px;}
@media (max-width: 760px){.doe-failrisk-wrap{grid-template-columns:1fr;}}

.doe-corr-host { padding: 6px 2px 2px 2px; }
.doe-corr-wrap text { font-family: ui-sans-serif, -apple-system, "Segoe UI", sans-serif; }
@media (max-width: 1100px) {
  .doe-corr-wrap { grid-template-columns: 1fr !important; }
}
.doe-corr-clusters > div[style*="border-left"]:hover {
  background: rgba(255,255,255,0.03) !important;
  transition: background 120ms ease;
}

.doe-toa-root { display:flex; flex-direction:column; gap:10px; padding:6px 2px 2px; }
.doe-toa-empty { color: var(--dim, #5c6383); font-size: 11px; padding: 12px; text-align:center; }
.toa-tagline { display:flex; gap:14px; flex-wrap:wrap; font-size:11px; padding:0 4px; }
.toa-tag { padding:3px 8px; border-radius:3px; background:rgba(255,255,255,0.04); border:1px solid var(--line, #2a2f45); }
.toa-tag-e { color: var(--good, #4adfa1); }
.toa-tag-l { color: var(--warn, #f0a830); }
.toa-grid { display:grid; grid-template-columns: 1.4fr 1fr; gap:14px; }
@media (max-width: 980px) { .toa-grid { grid-template-columns: 1fr; } }
.toa-sec-h { display:flex; align-items:baseline; gap:8px; margin: 4px 4px 6px; }
.toa-sec-t { font-size:11px; font-weight:600; letter-spacing:.04em; color: var(--fg, #e6e8f0); text-transform:uppercase; }
.toa-sec-d { font-size:10px; color: var(--dim, #5c6383); }
.toa-sw { display:inline-block; width:9px; height:9px; border-radius:2px; vertical-align:middle; }
.toa-left, .toa-right { background: var(--bg2, #131725); border:1px solid var(--line, #2a2f45); border-radius:4px; padding:8px 10px; }
.toa-right { display:flex; flex-direction:column; gap:10px; }
.toa-strip { display:flex; flex-direction:column; gap:4px; padding:4px 2px; }
.toa-bar-row { display:grid; grid-template-columns: 140px 1fr 80px; gap:8px; align-items:center; font-size:11px; }
.toa-bar-name { color: var(--fg2, #aab2cf); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.toa-bar-track { position:relative; height:14px; background: rgba(255,255,255,0.04); border-radius:2px; overflow:hidden; }
.toa-bar-fill { height:100%; border-radius:2px; }
.toa-bar-val { font-variant-numeric: tabular-nums; color: var(--fg, #e6e8f0); text-align:right; }
.toa-axis { display:flex; justify-content:space-between; font-size:10px; color: var(--dim, #5c6383); padding: 6px 4px 2px; border-top:1px solid var(--line, #2a2f45); margin-top:4px; }
.toa-axis-mid { color: var(--fg2, #aab2cf); }
.toa-listbox { display:flex; flex-direction:column; gap:4px; }
.toa-list { display:flex; flex-direction:column; gap:3px; }
.toa-li { display:grid; grid-template-columns: 1fr auto; gap:8px; align-items:baseline; font-size:11px; padding:3px 4px; border-radius:2px; background: rgba(255,255,255,0.02); }
.toa-li-name { color: var(--fg2, #aab2cf); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.toa-li-stat { font-variant-numeric: tabular-nums; }
.toa-li-mean { color: var(--fg, #e6e8f0); font-weight:600; }
.toa-li-std { color: var(--dim, #5c6383); }
.toa-li-n { color: var(--dim, #5c6383); font-size:10px; }

#idw-pred-svg { width:100%; height:auto; max-height:560px; display:block; }
#idw-pred-panel .ctlbar { padding:6px 10px; }
#idw-pred-info b { color: var(--fg); }

.pareto-host { width: 100%; min-height: 460px; }
.pareto-host svg text { font-family: inherit; }
.pareto-tip b { color: var(--accent); }
.pareto-legend span { white-space: nowrap; }

/* Energy Partition (Section 5 advanced) */
.doe-ep-summary {
  display: flex; flex-wrap: wrap; gap: 8px;
  padding: 8px 4px 14px 4px;
  border-bottom: 1px dashed var(--line);
  margin-bottom: 10px;
}
.doe-ep-list {
  display: flex; flex-direction: column; gap: 4px;
  max-height: 560px; overflow-y: auto;
  padding-right: 4px;
}
.doe-ep-row {
  display: grid;
  grid-template-columns: 90px 1fr 170px;
  align-items: center;
  gap: 10px;
  padding: 5px 8px;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.12s;
}
.doe-ep-row:hover { background: rgba(255,255,255,0.04); }
.doe-ep-lbl {
  display: inline-flex; align-items: center; gap: 6px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px; color: var(--fg);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.doe-ep-dot {
  display: inline-block; width: 8px; height: 8px; border-radius: 50%;
  flex-shrink: 0;
}
.doe-ep-bar {
  display: flex; height: 18px; width: 100%;
  background: var(--bg3); border-radius: 3px; overflow: hidden;
  border: 1px solid var(--line);
}
.doe-ep-seg {
  display: flex; align-items: center; justify-content: center;
  height: 100%; min-width: 0;
  transition: filter 0.15s;
}
.doe-ep-row:hover .doe-ep-seg { filter: brightness(1.15); }
.doe-ep-abs { background: linear-gradient(90deg, #2c8c5d, #4adfa1); }
.doe-ep-ret { background: linear-gradient(90deg, #2563a8, #4dd6ff); }
.doe-ep-seg-lbl {
  font-family: 'JetBrains Mono', monospace;
  font-size: 9px; font-weight: 700;
  color: rgba(10,12,20,0.9);
  letter-spacing: 0.3px;
}
.doe-ep-right {
  display: flex; justify-content: flex-end; align-items: baseline;
  gap: 10px; font-family: 'JetBrains Mono', monospace;
}
.doe-ep-pct {
  font-size: 12px; font-weight: 700; color: var(--good);
}
.doe-ep-ke {
  font-size: 10px; color: var(--dim);
}
@media (max-width: 900px) {
  .doe-ep-row { grid-template-columns: 70px 1fr 110px; gap: 6px; }
  .doe-ep-ke { display: none; }
}

/* ADV_CSS_INSERT_HERE */
"""


def _build_topbar(meta: dict, unit_labels: dict | None = None) -> str:
    project = _esc(meta["project"])
    imp_type = _esc(meta["impactor"]["type"])
    n_faces = meta.get("_n_faces", 6)
    n_runs = meta.get("_n_runs", 0)
    gen_mode = _esc(meta["generation_mode"])
    dt_s = meta["sim_params"].get("dt", 1e-6)
    t_final = meta["sim_params"].get("t_final", 0.001)
    # Time label is data-driven: show raw seconds when units unspecified,
    # ms when the loader declared a known unit system (LS-DYNA mm-ton-s).
    t_unit = (unit_labels or {}).get("time", "")
    if t_unit == "ms":
        dt_str = f"{dt_s * 1e6:.1f} &micro;s"
        tf_str = f"{t_final * 1e3:.2f} ms"
    else:
        dt_str = f"{dt_s:g}"
        tf_str = f"{t_final:g}"
    return f"""
<div class="topbar">
  <div class="brand">KOOD3PLOT &middot; MULTI-FACE IMPACT</div>
  <div class="meta">
    <span>PROJECT <b>{project}</b></span>
    <span>IMPACTOR <b>{imp_type}</b></span>
    <span>RUNS <b>{n_runs}</b></span>
    <span>FACES <b>{n_faces}</b></span>
    <span>MODE <b>{gen_mode}</b></span>
    <span>&Delta;t <b>{dt_str}</b></span>
    <span>T <b>{tf_str}</b></span>
  </div>
  <div class="nav">
    <a data-target="s1" class="active">OVERVIEW</a>
    <a data-target="s2">INSPECTOR</a>
    <a data-target="s3">VERDICT</a>
    <a data-target="s4">PER-PART G</a>
    <a data-target="s5" id="navS5">DOE</a>
  </div>
</div>
"""


_PAGE1 = """
<section class="page" id="s1">
  <div class="hero-line r">
    <div>
      <div class="page-head" style="margin-bottom:6px;border:none;padding:0">
        <span class="num">01</span><span class="tagline">METHOD &middot; OVERVIEW</span>
      </div>
      <h1>전위치 부분충격 &mdash; <span class="acc">Multi-Face Pair-wise 해석</span></h1>
      <div class="lede">
        Cuboid-26 표준 자세 중 <b id="kHeroFaces">__N_FACES__</b>개 면 &times; XY 격자
        <b id="kHeroPos">__N_POSITIONS__</b> 위치 &times; <b id="kHeroParts">__N_PARTS__</b> 부품
        = <b id="kHeroPairs">__N_PAIRS__</b> 페어. 임팩터 운동에너지가 어디로 흘러가는지
        실시간 그래프로 추적합니다.
      </div>
    </div>
    <div class="right">
      <div class="pk">&#9650; WORST CELL</div>
      <div class="pkv" id="heroWorstCoord">__WORST_LINE__</div>
      <div class="pkv" id="heroWorstPart" style="color:var(--crit)">__WORST_PART_LINE__</div>
    </div>
  </div>

  <div class="grid g-12 r method-band" style="margin-bottom:12px">
    <div class="panel" style="grid-column:span 3;padding:10px 12px;margin:0">
      <div class="band-head"><span>IMPACTOR</span><span class="band-sub" id="impSubLabel">__IMP_SUB__</span></div>
      <svg id="impactor-svg" viewBox="0 0 200 110" preserveAspectRatio="xMidYMid meet" style="width:100%;height:110px"></svg>
      <table class="dt" style="margin-top:6px;font-size:10px">
        <tbody id="impactor-tbl"></tbody>
      </table>
      <div class="band-cap" id="impCap">자유낙하 KE = &frac12; m v&sup2;.</div>
    </div>

    <div class="panel" style="grid-column:span 3;padding:10px 12px;margin:0">
      <div class="band-head"><span>BI-FACE OVERVIEW</span><span class="band-sub">front · back</span></div>
      <div class="biface-grid" id="biface-mini" style="grid-template-columns:1fr 1fr;gap:6px"></div>
      <div class="band-cap">자유낙하 정면(F2)과 배면(F1) 충돌 위치 위험도. 클릭 시 INSPECTOR로 점프.</div>
    </div>

    <div class="panel" style="grid-column:span 3;padding:10px 12px;margin:0">
      <div class="band-head"><span>DOE</span><span class="band-sub" id="doeSubLabel">grid &middot; per-face</span></div>
      <table class="dt" style="font-size:10px">
        <tbody id="doe-breakdown"></tbody>
      </table>
      <div class="band-cap" id="doeCap">자세별 격자 위치 수 &middot; generation mode</div>
    </div>

    <div class="panel" style="grid-column:span 3;padding:10px 12px;margin:0">
      <div class="band-head"><span>PIPELINE</span><span class="band-sub" style="color:var(--tag)">scenario &rarr; report</span></div>
      <svg viewBox="0 0 380 92" preserveAspectRatio="xMidYMid meet" style="width:100%;height:92px">
        <defs>
          <marker id="arr2" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
            <path d="M0,0 L10,5 L0,10 Z" fill="#4dd6ff"/>
          </marker>
        </defs>
        <g font-family="Inter,system-ui" font-size="9" fill="#e6ebff">
          <g transform="translate(2,22)">
            <rect width="64" height="48" rx="4" fill="#1a1e2e" stroke="#4dd6ff" stroke-width="0.8"/>
            <text x="32" y="14" text-anchor="middle" fill="#4dd6ff" font-size="7" letter-spacing="1">SCENARIO</text>
            <text x="32" y="28" text-anchor="middle" font-weight="600" font-size="9">DOE</text>
            <text x="32" y="40" text-anchor="middle" font-size="7" fill="#5c6383">grid/lhs</text>
          </g>
          <line x1="68" y1="46" x2="80" y2="46" stroke="#4dd6ff" stroke-width="1" marker-end="url(#arr2)"/>
          <g transform="translate(82,22)">
            <rect width="64" height="48" rx="4" fill="#1a1e2e" stroke="#b46eff" stroke-width="0.8"/>
            <text x="32" y="14" text-anchor="middle" fill="#b46eff" font-size="7" letter-spacing="1">PREPARE</text>
            <text x="32" y="28" text-anchor="middle" font-weight="600" font-size="9">DECOMP</text>
            <text x="32" y="40" text-anchor="middle" font-size="7" fill="#5c6383">contacts</text>
          </g>
          <line x1="148" y1="46" x2="160" y2="46" stroke="#4dd6ff" stroke-width="1" marker-end="url(#arr2)"/>
          <g transform="translate(162,22)">
            <rect width="64" height="48" rx="4" fill="#1a1e2e" stroke="#f0a830" stroke-width="0.8"/>
            <text x="32" y="14" text-anchor="middle" fill="#f0a830" font-size="7" letter-spacing="1">SOLVE</text>
            <text x="32" y="28" text-anchor="middle" font-weight="600" font-size="9">N runs</text>
            <text x="32" y="40" text-anchor="middle" font-size="7" fill="#5c6383">LS-DYNA</text>
          </g>
          <line x1="228" y1="46" x2="240" y2="46" stroke="#4dd6ff" stroke-width="1" marker-end="url(#arr2)"/>
          <g transform="translate(242,22)">
            <rect width="64" height="48" rx="4" fill="#1a1e2e" stroke="#4adfa1" stroke-width="0.8"/>
            <text x="32" y="14" text-anchor="middle" fill="#4adfa1" font-size="7" letter-spacing="1">COLLECT</text>
            <text x="32" y="28" text-anchor="middle" font-weight="600" font-size="9">binout</text>
            <text x="32" y="40" text-anchor="middle" font-size="7" fill="#5c6383">G/&sigma;/IE/F</text>
          </g>
          <line x1="308" y1="46" x2="320" y2="46" stroke="#4dd6ff" stroke-width="1" marker-end="url(#arr2)"/>
          <g transform="translate(322,22)">
            <rect width="56" height="48" rx="4" fill="#1a1e2e" stroke="#ff3854" stroke-width="0.8"/>
            <text x="28" y="14" text-anchor="middle" fill="#ff3854" font-size="7" letter-spacing="1">REPORT</text>
            <text x="28" y="28" text-anchor="middle" font-weight="600" font-size="9">HTML</text>
            <text x="28" y="40" text-anchor="middle" font-size="7" fill="#5c6383">single-file</text>
          </g>
        </g>
      </svg>
      <div class="band-cap">5단계 무손실 파이프라인. 원본 d3plot은 디스크 상주, 결과만 단일 HTML로.</div>
    </div>
  </div>

  <div class="kpi-strip r">
    <div class="k"><div class="v" id="kPositions">__N_POSITIONS__<span class="u">pos</span></div><div class="l">TOTAL POSITIONS</div></div>
    <div class="k"><div class="v" id="kFaces">__N_FACES__</div><div class="l">FACES</div></div>
    <div class="k"><div class="v" id="kParts">__N_PARTS__</div><div class="l">PARTS</div></div>
    <div class="k"><div class="v" id="kWorstG">__WORST_G__<span class="u">G</span></div><div class="l">WORST PEAK G</div></div>
    <div class="k"><div class="v" id="kWorstS">__WORST_S__<span class="u" id="kWorstSUnit"></span></div><div class="l">WORST STRESS</div></div>
    <div class="k"><div class="v" id="kCritPairs">__N_CRIT__</div><div class="l">CRITICAL PAIRS</div></div>
    <div class="k"><div class="v" id="kSafePos">__N_SAFE__</div><div class="l">SAFE POSITIONS</div></div>
    <div class="k"><div class="v" id="kDiss">__DISS_PCT__<span class="u">%</span></div><div class="l">ENERGY DISSIPATED</div></div>
  </div>

  <div class="grid g-12" style="margin-top:14px">
    <div class="panel col-7 r">
      <div class="ph">
        <span class="pt">BI-FACE RISK MAPS</span>
        <span class="pd">front (F2) vs back (F1) &middot; impact-position colored by max response</span>
      </div>
      <div class="biface-grid" id="biface-split"></div>
      <div class="pcap">
        한 점 = 한 임팩트 위치. 색상 = 그 위치에서 모든 부품 중 최대 Peak G.
        ★ = 최악 셀. 클릭 시 INSPECTOR로 점프.
      </div>
    </div>

    <div class="panel col-5 r">
      <div class="ph">
        <span class="pt">PER-FACE KPI</span>
        <span class="pd">n &middot; max G &middot; worst (x,y) &middot; driver &middot; risk score &middot; &Delta;</span>
      </div>
      <table class="dt" id="face-kpi-tbl">
        <thead>
          <tr><th class="tl">FACE</th><th>n</th><th>MAX G</th><th>WORST (X,Y)</th><th class="tl">DRIVER</th><th>SCORE</th><th>vs OTHER</th></tr>
        </thead>
        <tbody></tbody>
      </table>
      <div class="pcap" id="face-kpi-cap">
        SCORE column shown only when payload.risk_score config is provided.
        &Delta; = SCORE - other face's SCORE.
      </div>
    </div>

    <div class="panel col-12 r">
      <div class="ph">
        <span class="pt">BOUNCE VECTOR MAP &middot; impactor fate per XY position</span>
        <span class="pd">arrow tail = impact &middot; arrow dir = rebound XY &middot; color = behavior class</span>
      </div>
      <div class="bvm-grid" id="bvm-grid"></div>
      <div class="bvm-legend" id="bvm-legend"></div>
      <div class="pcap">
        탄성 반사(bounce)는 녹색, 부분 반발(rebound) 노랑, 미끄러짐(slide) 주황, 박힘(embed) 빨강.
        한눈에 어떤 영역이 임팩터를 튕겨내고 어디가 흡수하는지 보여줍니다.
      </div>
    </div>

    <div class="panel col-12 r">
      <div class="ph">
        <span class="pt">TRAJECTORY CLUSTERING MAP</span>
        <span class="pd">k-means archetypes &middot; positions colored by cluster &middot; sparkline = KE decay prototype</span>
      </div>
      <div class="bvm-grid" id="tcm-grid"></div>
      <div class="tcm-archetypes" id="tcm-archetypes"></div>
      <div class="pcap">
        클러스터링은 KE retention, max penetration, rebound speed, behavior class 기반으로 임팩터의 거동 archetypes를 학습.
        같은 클러스터 위치는 동일한 거동 패턴을 보입니다.
      </div>
    </div>

    <div class="panel col-12 r">
      <div class="ph">
        <span class="pt">TOP-K WORST PAIRS</span>
        <span class="pd">rank / face / position / part / response</span>
      </div>
      <table class="dt" id="topk-tbl">
        <thead>
          <tr><th class="tl">RANK</th><th class="tl">FACE</th><th>X<span id="topkXUnit"></span></th><th>Y<span id="topkYUnit"></span></th><th class="tl">PART</th><th>PEAK G</th><th>&sigma;<span id="topkSUnit"></span></th><th>INFLUENCE AREA</th></tr>
        </thead>
        <tbody></tbody>
      </table>
    </div>
  </div>
</section>
"""

_PAGE2 = """
<section class="page" id="s2">
  <div class="page-head r">
    <span class="num">02</span><span class="tagline">IMPACT INSPECTOR</span>
    <span class="ttl">충격 위치 = 화면, 부품 응답 = 부품 라이트업</span>
    <span class="sub">HOVER-DRIVEN BI-FACE STRESS EXPLORER</span>
  </div>

  <div class="ctlbar r">
    <div class="grp"><span class="lbl">FACE</span>
      <button class="btn active" data-ii-face="F2">FRONT &middot; F2</button>
      <button class="btn" data-ii-face="F1">BACK &middot; F1</button>
    </div>
    <div class="grp"><span class="lbl">METRIC</span>
      <button class="btn active" data-ii-metric="g">PEAK G</button>
      <button class="btn" data-ii-metric="s">&sigma;</button>
      <button class="btn" data-ii-metric="e">&epsilon;</button>
      <button class="btn" data-ii-metric="d">d</button>
    </div>
    <div class="grp"><span class="lbl">NORM</span>
      <button class="btn active" data-ii-norm="abs">ABS</button>
      <button class="btn" data-ii-norm="rel">RELATIVE</button>
    </div>
    <div class="grp ii-thresh"><span class="lbl">THRESH</span>
      <input type="range" id="ii-thresh" min="0" max="100" value="0">
      <span class="vlab" id="ii-thresh-val">0%</span>
    </div>
    <label class="ii-pin" id="ii-pin-lab">
      <input type="checkbox" id="ii-pin"> PIN
    </label>
  </div>

  <div class="ii-wrap r">
    <div class="ii-main">
      <div class="ph">
        <span class="pt">IMPACT INSPECTOR &middot; <span id="ii-face-label">FRONT (F2)</span></span>
        <span class="pd">hover impact &rarr; parts light up with their response &middot; click row to pin</span>
      </div>
      <div class="ii-canvas-wrap">
        <svg id="ii-svg" viewBox="0 0 800 600" preserveAspectRatio="xMidYMid meet"></svg>
      </div>
      <div class="ii-cbar">
        <span>0</span>
        <span class="grad"></span>
        <span id="ii-cbar-max">-</span>
        <span style="color:var(--accent);margin-left:8px" id="ii-metric-name">Peak G</span>
      </div>
    </div>
    <div class="ii-side" id="ii-side-panel">
      <div class="iibox">
        <div class="iihd">HOVERED IMPACT <span id="ii-behavior-badge"></span></div>
        <div id="ii-hover-info"><div class="ii-empty">충돌 위치 위에 마우스를 올리세요.</div></div>
        <div id="ii-traj-kpi" style="margin-top:6px"></div>
      </div>
      <div class="iibox">
        <div class="iihd">TOP AFFECTED PARTS</div>
        <div id="ii-parts-list"><div class="ii-empty">-</div></div>
      </div>
      <div class="iibox">
        <div class="iihd">IMPACTOR KE @ POSITION <span id="ii-th-sub" style="color:var(--dim);font-weight:500"></span></div>
        <svg id="ii-th-svg" class="ii-th" viewBox="0 0 200 70" preserveAspectRatio="none"></svg>
        <div style="display:flex;justify-content:space-between;font-size:8.5px;color:var(--dim);font-family:'JetBrains Mono',monospace;margin-top:2px">
          <span>0</span><span>0.5</span><span>1.0 ms</span>
        </div>
      </div>
    </div>
  </div>

  <div class="grid g-12" style="margin-top:14px">
    <div class="panel col-12 r">
      <div class="ph">
        <span class="pt">INFLUENCE MATRIX &middot; TOP-10 IMPACTS</span>
        <span class="pd">rows = worst impacts on selected face &middot; cols = parts &middot; click row = inspect</span>
      </div>
      <div id="imatrix-wrap" style="overflow-x:auto"></div>
      <div class="pcap">한 줄 = (face, position) 페어. 가로축 = 모든 부품. 셀 색 = 그 페어가 그 부품에 미친 응답.</div>
    </div>
  </div>
</section>
"""

_PAGE3 = """
<section class="page" id="s3">
  <div class="page-head r">
    <span class="num">03</span><span class="tagline">VERDICT &middot; ENERGY FLOW</span>
    <span class="ttl">충격은 어디로 흘러가며, 무엇을 결정해야 하는가</span>
    <span class="sub">MULTI-CRITERIA VERDICT + ENERGY DYNAMICS</span>
  </div>

  <div class="grid g-12">
    <div class="panel col-12 r">
      <div class="ph">
        <span class="pt">STRESS-TIME ENVELOPE &middot; CRITICAL PARTS</span>
        <span class="pd">12 worst pairs &middot; P5-P95 gray band + P50 + red worst</span>
      </div>
      <div class="ts-grid" id="ts-grid"></div>
      <div class="pcap">회색 띠 = 전체 페어의 P5-P95 envelope. 흰 라인 = P50. 빨간 라인 = worst pair.</div>
    </div>

    <div class="panel col-7 r">
      <div class="ph">
        <span class="pt">MULTI-CRITERIA VERDICT MATRIX</span>
        <span class="pd">part &middot; face &middot; position &middot; class &middot; max G/&sigma;/&epsilon;/d &middot; influence area</span>
      </div>
      <div style="overflow-x:auto">
        <table class="dt" id="verdict-tbl">
          <thead>
            <tr>
              <th class="tl">PART</th><th class="tl">FACE</th><th>X</th><th>Y</th>
              <th class="tl">CLASS</th><th>MAX G</th><th>&sigma;</th><th>&epsilon;</th><th>d</th>
              <th>CoV</th><th>INFL</th><th class="tl">MODE</th>
            </tr>
          </thead>
          <tbody></tbody>
        </table>
      </div>
    </div>

    <div class="col-5" style="display:grid;gap:14px">
      <div class="verdict-row">
        <div class="verdict-cell crit"><div class="vl">CRITICAL</div><div class="vn" id="vCrit">0</div><div class="vd">G &ge; P95 threshold &middot; 즉시 대응</div></div>
        <div class="verdict-cell warn"><div class="vl">WARNING</div><div class="vn" id="vWarn">0</div><div class="vd">P75 &le; G &lt; P95 &middot; 모니터링</div></div>
        <div class="verdict-cell safe"><div class="vl">PASSED</div><div class="vn" id="vSafe">0</div><div class="vd">G &lt; P75 &middot; 안전 마진</div></div>
      </div>
      <div class="panel r" style="padding:14px">
        <div class="ph">
          <span class="pt">FINDINGS</span>
          <span class="pd">auto-derived recommendations</span>
        </div>
        <ul id="findings-list" style="list-style:none;padding:0;margin:6px 0 0 0;font-size:11px;line-height:1.55"></ul>
      </div>
    </div>
  </div>

  <div class="page-head r" style="margin-top:36px">
    <span class="num">&#9889;</span><span class="tagline" style="color:var(--accent2)">ENERGY FLOW DYNAMICS</span>
    <span class="ttl">임팩트 KE의 경로 추적</span>
    <span class="sub">FORCE GRAPH + SUNBURST + SANKEY + TIME-FORCE</span>
  </div>

  <div class="grid g-12">
    <div class="panel col-7 r">
      <div class="ph">
        <span class="pt">FORCE-DIRECTED ENERGY GRAPH</span>
        <span class="pd">node size &prop; IE &middot; edge thickness &prop; impulse</span>
      </div>
      <div class="eg-wrap">
        <canvas id="eg-canvas"></canvas>
        <div class="eg-side" id="eg-side"></div>
      </div>
      <div class="scrub">
        <button class="btn" id="eg-play">&#9654; PLAY</button>
        <button class="btn" id="eg-reset">&#11119; RESET</button>
        <input type="range" id="eg-scrub" min="0" max="100" value="0">
        <div class="tlabel">t = <b id="eg-t">0.000</b> ms</div>
      </div>
      <div class="pcap">중앙 = 임팩터. 동심원 = 전파 깊이. 외곽 펄스링 = 활성 contact. 흐르는 입자 = 순간 force.</div>
    </div>

    <div class="panel col-5 r">
      <div class="ph">
        <span class="pt">ENERGY BUDGET SUNBURST</span>
        <span class="pd">KE_init &rarr; IE / dissipated / KE_left</span>
      </div>
      <svg id="sunburst-svg" viewBox="0 0 360 340" preserveAspectRatio="xMidYMid meet" style="width:100%;height:340px"></svg>
      <div class="pcap">중심 = 임팩터 초기 KE 100%. 1차 링 = IE / 소산 / 잔존. 2차 링 = 부품별 흡수 비율.</div>
    </div>

    <div class="panel col-7 r">
      <div class="ph">
        <span class="pt">SANKEY-STYLE CUMULATIVE FLOW</span>
        <span class="pd">impactor &rarr; parts &middot; edge bar &prop; total work</span>
      </div>
      <div id="sankey-rows"></div>
      <div class="pcap">막대 길이 = 누적 work. 위에서 아래로 = first-engage 순서.</div>
    </div>

    <div class="panel col-5 r">
      <div class="ph">
        <span class="pt">TIME-FORCE HEATMAP MATRIX</span>
        <span class="pd">rows = edges &middot; cols = 21 time bins &middot; sorted by first-engage</span>
      </div>
      <div class="tfh-head">
        <div class="h0">EDGE</div>
        <div class="ht">0</div><div class="ht"></div><div class="ht"></div><div class="ht"></div><div class="ht"></div>
        <div class="ht">&frac14;</div><div class="ht"></div><div class="ht"></div><div class="ht"></div><div class="ht"></div>
        <div class="ht">&frac12;</div><div class="ht"></div><div class="ht"></div><div class="ht"></div><div class="ht"></div>
        <div class="ht">&frac34;</div><div class="ht"></div><div class="ht"></div><div class="ht"></div><div class="ht"></div>
        <div class="ht">T</div>
      </div>
      <div class="tfh" id="tfh-rows"></div>
      <div class="pcap">"몇 &micro;s 후에 어디까지 전파됐는가" &mdash; 위에서 아래로 = 시간순 전파 사슬.</div>
    </div>

    <div class="panel col-3 r">
      <div class="ph">
        <span class="pt">CONSERVATION CHECK</span>
        <span class="pd">KE&#x2080; = IE + diss + KE&#x2099;</span>
      </div>
      <div class="cons-box">
        <div class="cons-cell"><div class="v" id="consKE">0.0</div><div class="l">KE INITIAL (J)</div></div>
        <div class="cons-cell"><div class="v" id="consIE">0.0</div><div class="l">IE FINAL (J)</div></div>
        <div class="cons-cell"><div class="v" id="consDISS">0.0</div><div class="l">DISSIPATED</div></div>
        <div class="cons-cell" id="consResCell"><div class="v" id="consRES">0.0</div><div class="l">RESIDUAL %</div></div>
      </div>
      <div class="cons-bar" id="consBar"></div>
      <div class="cons-banner" id="consBanner">&#9888; Residual exceeds tolerance &mdash; energy conservation suspect</div>
    </div>

    <div class="panel col-7 r">
      <div class="ph">
        <span class="pt">PHASE DIAGRAM &middot; KE vs IE</span>
        <span class="pd">all runs overlaid &middot; color by behavior &middot; budget line = KE&#x2080;</span>
      </div>
      <div class="phase-wrap">
        <svg id="phase-svg" preserveAspectRatio="none"></svg>
      </div>
      <div class="bvm-legend" id="phase-legend"></div>
      <div class="pcap">
        가로축 = 누적 흡수 IE, 세로축 = 임팩터 KE. 대각선은 에너지 보존 budget. 곡선이 budget 위로 떨어질수록 소산이 크다는 뜻.
      </div>
    </div>

    <div class="panel col-5 r">
      <div class="ph">
        <span class="pt">CONTACT ENGAGEMENT SEQUENCE</span>
        <span class="pd">top-8 worst impacts &middot; 21 timesteps &middot; contact dominance</span>
      </div>
      <div class="cseq-grid" id="cseq-grid"></div>
      <div class="pcap">셀 색상 = 그 시점의 dominant contact part. 회색 = 비접촉. 어느 시각에 어디까지 충격이 전파되는지 한눈에 추적 가능.</div>
    </div>

    <div class="panel col-12 r">
      <div class="ph">
        <span class="pt">TRAJECTORY BUNDLE 3D &middot; impactor envelopes</span>
        <span class="pd">all runs &middot; 3 orthogonal projections &middot; XZ / YZ side + XY top</span>
      </div>
      <div class="tb3">
        <div class="tb3-cell">
          <div class="h"><span>SIDE &middot; XZ</span><span>color = face</span></div>
          <svg id="tb3-xz" preserveAspectRatio="none"></svg>
        </div>
        <div class="tb3-cell">
          <div class="h"><span>SIDE &middot; YZ</span><span>color = face</span></div>
          <svg id="tb3-yz" preserveAspectRatio="none"></svg>
        </div>
        <div class="tb3-cell">
          <div class="h"><span>TOP &middot; XY</span><span>color = behavior</span></div>
          <svg id="tb3-xy" preserveAspectRatio="none"></svg>
        </div>
      </div>
      <div class="pcap">
        각 임팩터 경로의 envelope. 검은 점선 = device bbox. 회색 가로선(z=0) = 충돌면. embed 거동(빨강)은 z &lt; 0까지 침투.
      </div>
    </div>
  </div>
</section>
"""


_PAGE4 = """
<section class="page" id="s4">
  <div class="page-head r">
    <span class="num">04</span><span class="tagline">PER-PART MOTION</span>
    <span class="ttl">부품별 가속도 (Per-Part Peak G)</span>
    <span class="sub">RIGID-BODY MOTION &middot; PEAK G &middot; ACC-TIME HISTORY</span>
  </div>

  <div id="ppg-empty" class="r" style="display:none;color:var(--dim);padding:24px 12px;font-size:12px">
    부품별 모션 데이터 없음
  </div>

  <div id="ppg-content">
    <div class="grid g-12" style="margin-top:6px">
      <div class="panel col-7 r">
        <div class="ph">
          <span class="pt">PART PEAK G &middot; BAR CHART</span>
          <span class="pd">peak |acc| per part &middot; sorted descending &middot; impactor highlighted</span>
        </div>
        <svg id="ppg-bar-svg" preserveAspectRatio="xMidYMid meet" style="width:100%;height:340px"></svg>
        <div class="pcap" id="ppg-bar-cap">
          막대 길이 = max|a|<span id="ppg-bar-cap-unit"></span>. 임팩터 파트는 핑크색으로 강조.
        </div>
      </div>

      <div class="panel col-5 r">
        <div class="ph">
          <span class="pt">PEAK G SUMMARY TABLE</span>
          <span class="pd">part &middot; peak G &middot; t_peak &middot; peak vel/disp</span>
        </div>
        <div style="max-height:340px;overflow-y:auto">
          <table class="dt" id="ppg-summary-tbl">
            <thead>
              <tr>
                <th class="tl">PART</th>
                <th class="tl">NAME</th>
                <th>PEAK G<br><span style="font-weight:400;color:var(--dim);text-transform:none" id="ppg-th-acc"></span></th>
                <th>PEAK G<br><span style="font-weight:400;color:var(--dim);text-transform:none">g</span></th>
                <th>t<sub>peak</sub><br><span style="font-weight:400;color:var(--dim);text-transform:none" id="ppg-th-time"></span></th>
                <th>PEAK VEL<br><span style="font-weight:400;color:var(--dim);text-transform:none" id="ppg-th-vel"></span></th>
                <th>PEAK DISP<br><span style="font-weight:400;color:var(--dim);text-transform:none" id="ppg-th-disp"></span></th>
              </tr>
            </thead>
            <tbody></tbody>
          </table>
        </div>
        <div class="pcap">
          g 단위 = peak_g / 9810. 첫 번째 행이 가장 큰 가속도를 받는 부품.
        </div>
      </div>

      <div class="panel col-12 r">
        <div class="ph">
          <span class="pt">ACC MAGNITUDE TIME-SERIES &middot; ALL PARTS</span>
          <span class="pd">|a(t)| per part &middot; auto semi-log when range &gt; 2 decades &middot; dashed line = t<sub>first_contact</sub></span>
        </div>
        <svg id="ppg-line-svg" preserveAspectRatio="none" style="width:100%;height:360px"></svg>
        <div id="ppg-line-legend" style="display:flex;flex-wrap:wrap;gap:6px 12px;margin-top:6px;font-size:10px;color:var(--fg2)"></div>
        <div class="pcap" id="ppg-line-cap">
          한 선 = 한 파트의 가속도 크기 시계열. 회색 점선 세로선 = 임팩터 최초 접촉 시각.
        </div>
      </div>
    </div>
  </div>
</section>
"""

_PAGE5 = """
<section class="page" id="s5" style="display:none">
  <div class="page-head r">
    <span class="num">05</span><span class="tagline">DOE &middot; SPATIAL ANALYSIS</span>
    <span class="ttl">전위치 부분충격 &mdash; 위치별 응답 지도</span>
    <span class="sub">MULTI-POSITION DOE EXPLORER</span>
  </div>

  <div id="doe-empty" class="doe-empty" style="display:none">DOE 데이터 없음 (단일 위치 리포트)</div>

  <div id="doe-content">
    <div class="kpi-strip r" id="doe-kpi-strip" style="grid-template-columns:repeat(5, 1fr);margin-bottom:14px"></div>

    <div class="ctlbar r">
      <div class="grp"><span class="lbl">METRIC</span><span id="doe-metric-buttons"></span></div>
      <div class="grp"><span class="lbl">SORT</span>
        <button class="btn active" data-doe-sort="value">VALUE DESC</button>
        <button class="btn" data-doe-sort="pos">POS_ID</button>
      </div>
    </div>

    <div class="grid g-12" style="margin-bottom:14px">
      <div class="panel col-7 r">
        <div class="ph">
          <span class="pt">SPATIAL HEATMAP &middot; <span id="doe-heat-metric-lbl">PEAK G</span></span>
          <span class="pd" id="doe-heat-sub">grid &middot; cell color = selected metric</span>
        </div>
        <div class="doe-grid-wrap"><svg id="doe-heatmap-svg"></svg></div>
        <div class="pcap" id="doe-heat-cap">셀 클릭 시 우측 표에서 해당 위치 강조. 라벨 = 값 + 최악 영향 부품.</div>
      </div>

      <div class="panel col-5 r">
        <div class="ph">
          <span class="pt">POSITION RANKING</span>
          <span class="pd">sorted by selected metric desc</span>
        </div>
        <div class="doe-rank">
          <table class="dt" id="doe-rank-tbl">
            <thead>
              <tr>
                <th class="tl">RANK</th>
                <th class="tl">POS_ID</th>
                <th>X<span id="doe-rank-x-unit"></span></th>
                <th>Y<span id="doe-rank-y-unit"></span></th>
                <th class="tl">BEHAVIOR</th>
                <th id="doe-rank-val-lbl">VAL</th>
                <th class="tl">DRIVER</th>
                <th>KE RET</th>
                <th>MAX PEN<span id="doe-rank-pen-unit"></span></th>
              </tr>
            </thead>
            <tbody></tbody>
          </table>
        </div>
      </div>
    </div>

    <div class="grid g-12" style="margin-bottom:14px">
      <div class="panel col-12 r">
        <div class="ph">
          <span class="pt">PART &times; POSITION HEATMAP</span>
          <span class="pd">rows = top 15 parts by max peak_g &middot; cols = positions by DOE index &middot; color = peak_g</span>
        </div>
        <div class="doe-pp-matrix-wrap"><svg id="doe-pp-svg"></svg></div>
        <div class="pcap">부품별로 어느 위치에서 가속도가 가장 큰지 한눈에 확인. 색상 = peak_g (위치별 정규화 아님).</div>
      </div>
    </div>

    <div class="grid g-12" style="margin-bottom:14px">
      <div class="panel col-7 r">
        <div class="ph">
          <span class="pt">TRAJECTORY SMALL MULTIPLES &middot; KE vs TIME</span>
          <span class="pd">25 mini-curves &middot; color = behavior class &middot; ★ = worst position</span>
        </div>
        <div class="doe-traj-mm" id="doe-traj-mm"></div>
        <div class="bvm-legend" style="margin-top:8px">
          <div class="lg"><span class="sw" style="background:#4adfa1"></span>bounce</div>
          <div class="lg"><span class="sw" style="background:#4dd6ff"></span>rebound</div>
          <div class="lg"><span class="sw" style="background:#ff3854"></span>embed</div>
          <div class="lg"><span class="sw" style="background:#ff9e64"></span>slide</div>
          <div class="lg"><span class="sw" style="background:#5c6383"></span>unknown</div>
        </div>
      </div>

      <div class="panel col-5 r">
        <div class="ph">
          <span class="pt">CROSS-POSITION ENVELOPE &middot; PER PART</span>
          <span class="pd">P5—P50—P95 whisker (peak_g) &middot; right = P95/P5</span>
        </div>
        <div class="doe-env-wrap" id="doe-env-wrap"></div>
        <div class="pcap">whisker 길이 = 위치별 부품 응답 분산. 비율 ↑ 위치 의존성 ↑.</div>
      </div>
    </div>

<div class="panel">
  <div class="ph">
    <span class="pt">FAILURE RISK MAP</span>
    <span class="pd">위치별 최소 안전율(SF) 히트맵 + 위험 부품 랭킹</span>
  </div>
  <div id="doe-failure-risk-body"></div>
  <div class="pcap">SF = yield / peak_stress. SF&lt;1 = 항복 초과, 1≤SF&lt;2 = 마진 부족.</div>
</div>

<div class="panel" id="doe-corr-network-panel">
  <div class="ph">
    <span class="pt">PART × PART RESPONSE CORRELATION</span>
    <span class="pd">25 위치에 걸친 peak_g 응답의 Pearson 상관 + greedy 클러스터링</span>
  </div>
  <div id="doe-corr-network" class="doe-corr-host"></div>
  <div class="pcap">25 위치에 걸친 부품 응답의 Pearson 상관. 같은 cluster = 구조적 연결 또는 같은 충격 경로. |r| ≥ 0.7 인 셀은 흰 테두리로 강조.</div>
</div>

<div class="panel col-12 r">
  <div class="ph">
    <span class="pt">IMPACT WAVE PROPAGATION &middot; TIME-OF-ARRIVAL</span>
    <span class="pd">part peak_g vs impactor 첫 접촉 시점 &middot; 응답 전파 순서</span>
  </div>
  <div id="doe-toa-root" class="doe-toa-root"></div>
  <div class="pcap">
    Δt = part peak_g 시점 &minus; impactor 첫 접촉 시점. 응답 전파 순서를 시각화.
    좌측은 최악 위치의 도착 순서(상위 12개), 우측은 모든 위치 평균 기준 항상 빠른/느린 부품.
  </div>
</div>
<div class="grid g-12" style="margin-bottom:14px">
  <div class="panel col-12 r" id="idw-pred-panel">
    <div class="ph">
      <span class="pt">WHAT-IF POSITION PREDICTOR &middot; IDW INTERPOLATION</span>
      <span class="pd">25 측정점 → 41×41 보간면 (역거리 가중, p=2)</span>
    </div>
    <div class="ctlbar r" style="margin-bottom:10px">
      <div class="grp"><span class="lbl">METRIC</span><span id="idw-pred-buttons"></span></div>
      <div class="grp" style="flex:1"><span class="lbl" style="opacity:.7">LEGEND</span>
        <span style="color:var(--fg2);font-size:11px">
          <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#0a0c14;border:1.5px solid #fff;vertical-align:middle;margin-right:4px"></span>측정점
          <span style="display:inline-block;width:10px;height:10px;border-radius:50%;border:2px solid #ffd84d;vertical-align:middle;margin:0 4px 0 12px"></span>예측 최대(보간 정점)
        </span>
      </div>
    </div>
    <div class="doe-grid-wrap"><svg id="idw-pred-svg"></svg></div>
    <div id="idw-pred-info" style="margin-top:8px;font-size:12px;color:var(--fg2)"></div>
    <div class="pcap">측정 25 점 사이의 임의 위치에 떨어졌을 때 예상 응답. 점 = 실측, 면 = IDW 보간. 측정점 근처는 정확도가 높고, 측정점 사이 빈 영역은 불확실성이 커집니다 — 노란 링은 측정점 사이에 숨어 있을 가능성이 있는 "고위험 포켓"의 위치 추정입니다.</div>
  </div>
</div>

<div class="panel" id="panel-pareto-severity">
  <div class="ph">
    <span class="pt">SEVERITY × COVERAGE PARETO</span>
    <span class="pd">국소 vs 광역 충격 분류</span>
  </div>
  <div id="doe-pareto-severity" class="pareto-host"></div>
  <div class="pcap">한 위치가 '특정 부품만 심각' 인지 '여러 부품에 광범위' 인지 시각화. 우상단 = 광범위 + 심각 → 가장 위험.</div>
</div>

<div class="grid g-12" style="margin-bottom:14px">
  <div class="panel col-12 r">
    <div class="ph">
      <span class="pt">ENERGY PARTITION &middot; KE ABSORBED vs RETAINED</span>
      <span class="pd">per position &middot; sorted by absorption % desc</span>
    </div>
    <div class="doe-ep-summary" id="doe-ep-summary"></div>
    <div class="doe-ep-list" id="doe-ep-list"></div>
    <div class="pcap">충격 에너지가 디바이스에 흡수된 비율. 100% 흡수 = 충돌체가 정지. 행 클릭 시 상단 히트맵/랭킹에서 해당 위치 강조.</div>
  </div>
</div>

    <!-- ADV_PANELS_INSERT_HERE -->
    <!-- Workflow-added panel templates are inserted ABOVE this marker line. -->
  </div>
</section>

<div class="foot">KOOD3PLOT &middot; MULTI-FACE IMPACT &middot; v0.1.0 &middot; single-file self-contained</div>
"""


# ---------------------------------------------------------------------------
# JavaScript template — large but self-contained
# ---------------------------------------------------------------------------

_JS = r"""
const DATA = __PAYLOAD__;

function fmt(n, d) {
  if (n == null || !isFinite(n)) return '-';
  const a = Math.abs(n);
  if (a >= 1e6) return (n / 1e6).toFixed(d == null ? 2 : d) + 'M';
  if (a >= 1e3) return (n / 1e3).toFixed(d == null ? 1 : d) + 'k';
  if (a < 1 && a > 0) return n.toFixed((d == null ? 2 : d) + 2);
  return n.toFixed(d == null ? 2 : d);
}
function gColor(t) {
  t = Math.max(0, Math.min(1, t));
  const stops = [
    [0.00, [68,  1, 84]],
    [0.20, [59, 82,139]],
    [0.40, [33,144,141]],
    [0.60, [93,201, 99]],
    [0.80, [253,231, 37]],
    [1.00, [253, 80, 60]]
  ];
  for (let i = 0; i < stops.length - 1; i++) {
    if (t <= stops[i+1][0]) {
      const f = (t - stops[i][0]) / (stops[i+1][0] - stops[i][0]);
      const c = [0, 1, 2].map(k => Math.round(stops[i][1][k] * (1 - f) + stops[i+1][1][k] * f));
      return 'rgb(' + c[0] + ',' + c[1] + ',' + c[2] + ')';
    }
  }
  return 'rgb(253,80,60)';
}
function el(tag, attrs, children) {
  const e = document.createElement(tag);
  if (attrs) for (const k in attrs) {
    if (k === 'style' && typeof attrs[k] === 'object') Object.assign(e.style, attrs[k]);
    else if (k.startsWith('on') && typeof attrs[k] === 'function') e.addEventListener(k.slice(2), attrs[k]);
    else e.setAttribute(k, attrs[k]);
  }
  if (children) {
    if (!Array.isArray(children)) children = [children];
    for (const c of children) {
      if (c == null) continue;
      if (typeof c === 'string' || typeof c === 'number') e.appendChild(document.createTextNode(String(c)));
      else e.appendChild(c);
    }
  }
  return e;
}
function svg(tag, attrs, children) {
  const e = document.createElementNS('http://www.w3.org/2000/svg', tag);
  if (attrs) for (const k in attrs) e.setAttribute(k, attrs[k]);
  if (children) {
    if (!Array.isArray(children)) children = [children];
    for (const c of children) {
      if (c == null) continue;
      if (typeof c === 'string' || typeof c === 'number') e.appendChild(document.createTextNode(String(c)));
      else e.appendChild(c);
    }
  }
  return e;
}

const PARTS = DATA.parts;
const PART_BY_ID = Object.fromEntries(PARTS.map(p => [p.id, p]));
const FACES = DATA.faces;
const FACE_BY_CODE = Object.fromEntries(FACES.map(f => [f.code, f]));
const RESULTS = DATA.results;
// device_bbox = null in payload when no device_layout.json and no positions
// to derive a bbox from. Consumers must check DEVICE_BBOX before using.
const DEVICE_BBOX = DATA.device_bbox;

const STATE = {
  metric: 'g',
  face: 'ALL',
  scale: 'linear',
  filter: '',
  ii: {
    face: (FACE_BY_CODE.F2 ? 'F2' : (FACES[0] ? FACES[0].code : 'F2')),
    metric: 'g',
    norm: 'abs',
    thresh: 0,
    hovered_pos: null,
    pinned: false,
    selected_part: null
  }
};

function metricLabel(m) {
  return ({
    g: 'Peak G',
    s: 'sigma' + _uSuffix('stress'),
    e: 'eps',
    d: 'd' + _uSuffix('disp')
  })[m] || m;
}

function scaleNorm(v, mx) {
  if (mx <= 0) return 0;
  if (STATE.scale === 'log') return Math.log10(1 + Math.max(0, v)) / Math.log10(1 + mx);
  return v / mx;
}

const FACE_RESULTS = {};
const FACE_PART_RESULTS = {};
const FACE_POS_MAX = {};
for (const r of RESULTS) {
  (FACE_RESULTS[r.face] = FACE_RESULTS[r.face] || []).push(r);
  const fk = r.face + '|' + r.part_id;
  (FACE_PART_RESULTS[fk] = FACE_PART_RESULTS[fk] || []).push(r);
  const pk = r.face + '|' + r.pos_id;
  if (!FACE_POS_MAX[pk] || FACE_POS_MAX[pk].g < r.g) FACE_POS_MAX[pk] = r;
}

function faceBBox(faceCode) {
  const rows = FACE_RESULTS[faceCode] || [];
  if (!rows.length) return [0, 0, 0, 0];
  let xmin = Infinity, xmax = -Infinity, ymin = Infinity, ymax = -Infinity;
  for (const r of rows) {
    if (r.x < xmin) xmin = r.x; if (r.x > xmax) xmax = r.x;
    if (r.y < ymin) ymin = r.y; if (r.y > ymax) ymax = r.y;
  }
  if (xmin === xmax) { xmin -= 1; xmax += 1; }
  if (ymin === ymax) { ymin -= 1; ymax += 1; }
  const padX = (xmax - xmin) * 0.08, padY = (ymax - ymin) * 0.08;
  return [xmin - padX, xmax + padX, ymin - padY, ymax + padY];
}
function maxMetric(rows) {
  let m = 0;
  for (const r of rows) { const v = r[STATE.metric] || 0; if (v > m) m = v; }
  return m;
}

const UNIT_LABELS = DATA.unit_labels || {
  acc: '', stress: '', disp: '', vel: '', energy: '', time: '', mass: '', force: ''
};
function _u(key) { return UNIT_LABELS[key] || ''; }
function _uSuffix(key) { const v = _u(key); return v ? ' (' + v + ')' : ''; }

function applyUnitLabels() {
  // Inject unit labels into HTML placeholders. Empty when units unspecified.
  const set = (id, text) => { const e = document.getElementById(id); if (e) e.textContent = text; };
  set('kWorstSUnit', _u('stress'));
  set('topkXUnit', _uSuffix('disp'));
  set('topkYUnit', _uSuffix('disp'));
  set('topkSUnit', _uSuffix('stress'));
  set('ppg-bar-cap-unit', _uSuffix('acc'));
  set('ppg-th-acc', _u('acc'));
  set('ppg-th-time', _u('time'));
  set('ppg-th-vel', _u('vel'));
  set('ppg-th-disp', _u('disp'));
}

function fillHeroKpi() {
  const k = DATA.kpi;
  document.getElementById('kPositions').innerHTML = k.n_positions + '<span class="u">pos</span>';
  document.getElementById('kFaces').textContent = k.n_faces;
  document.getElementById('kParts').textContent = k.n_parts;
  document.getElementById('kWorstG').innerHTML = fmt(k.worst_g, 0) + '<span class="u">G</span>';
  document.getElementById('kWorstS').innerHTML = fmt(k.worst_s, 1) + '<span class="u">' + _u('stress') + '</span>';
  document.getElementById('kCritPairs').textContent = k.n_critical;
  document.getElementById('kSafePos').textContent = k.n_safe;
  document.getElementById('kDiss').innerHTML = k.diss_pct.toFixed(1) + '<span class="u">%</span>';
  document.getElementById('kHeroFaces').textContent = k.n_faces;
  document.getElementById('kHeroPos').textContent = k.n_positions;
  document.getElementById('kHeroParts').textContent = k.n_parts;
  document.getElementById('kHeroPairs').textContent = k.n_pairs;
  document.getElementById('heroWorstCoord').textContent = k.worst.face + ' · X ' + k.worst.x.toFixed(1) + ' / Y ' + k.worst.y.toFixed(1);
  document.getElementById('heroWorstPart').textContent = fmt(k.worst.g, 0) + ' G  ON  ' + k.worst.part_name;
}

function initImpactor() {
  const imp = DATA.meta.impactor;
  const svgRoot = document.getElementById('impactor-svg');
  const tbl = document.getElementById('impactor-tbl');
  const cap = document.getElementById('impCap');
  const sub = document.getElementById('impSubLabel');
  while (svgRoot.firstChild) svgRoot.removeChild(svgRoot.firstChild);
  while (tbl.firstChild) tbl.removeChild(tbl.firstChild);
  if (imp.type === 'Sphere') {
    sub.textContent = 'Sphere';
    svgRoot.appendChild(svg('circle', { cx: 100, cy: 55, r: 32, fill: 'none', stroke: '#4dd6ff', 'stroke-width': 1.2 }));
    svgRoot.appendChild(svg('circle', { cx: 100, cy: 55, r: 8, fill: 'none', stroke: '#4dd6ff', 'stroke-width': 0.6, 'stroke-dasharray': '2,2' }));
    svgRoot.appendChild(svg('line', { x1: 100, y1: 23, x2: 100, y2: 87, stroke: '#5c6383', 'stroke-width': 0.5, 'stroke-dasharray': '1,2' }));
    const t = svg('text', { x: 100, y: 102, 'text-anchor': 'middle', fill: '#4dd6ff', 'font-size': 10, 'font-family': 'JetBrains Mono' });
    t.appendChild(document.createTextNode('R=' + imp.radius.toFixed(2)));
    svgRoot.appendChild(t);
    const rows = [
      ['TYPE', 'Sphere'],
      ['R' + _uSuffix('disp'), imp.radius.toFixed(2)],
      ['h' + _uSuffix('disp'), imp.height.toFixed(1)],
      ['v0' + _uSuffix('vel'), fmt(imp.velocity, 0)],
      ['m' + _uSuffix('mass'), fmt(imp.mass, 4)],
      ['KE' + _uSuffix('energy'), fmt(imp.kinetic_energy, 2)]
    ];
    for (const r of rows) {
      tbl.appendChild(el('tr', null, [el('td', { class: 'tl dim' }, r[0]), el('td', { class: 'num b' }, r[1])]));
    }
    cap.textContent = 'KE = 1/2 m v² (free-fall v = sqrt(2gh))';
  } else if (imp.type === 'Cylinder') {
    sub.textContent = 'Cylinder · asymmetric';
    const fr = imp.front_radius || imp.radius || 12;
    const out = imp.outer_radius || fr * 1.4;
    const br = imp.back_radius || out;
    const fh = imp.front_height || 15;
    const bh = imp.back_height || 25;
    const cx = 100, cy = 55;
    const totalH = fh + bh;
    const sx = 90 / totalH;
    const sy = 40 / Math.max(fr, out, br);
    const x0 = cx - (fh + bh) * sx / 2;
    const x1 = x0 + fh * sx;
    const x2 = x1 + bh * sx;
    const ftop = cy - fr * sy, fbot = cy + fr * sy;
    const mtop = cy - out * sy, mbot = cy + out * sy;
    const btop = cy - br * sy,  bbot = cy + br * sy;
    svgRoot.appendChild(svg('polygon', {
      points: x0 + ',' + ftop + ' ' + x1 + ',' + mtop + ' ' + x1 + ',' + mbot + ' ' + x0 + ',' + fbot,
      fill: 'rgba(77,214,255,0.12)', stroke: '#4dd6ff', 'stroke-width': 1
    }));
    svgRoot.appendChild(svg('polygon', {
      points: x1 + ',' + mtop + ' ' + x2 + ',' + btop + ' ' + x2 + ',' + bbot + ' ' + x1 + ',' + mbot,
      fill: 'rgba(180,110,255,0.12)', stroke: '#b46eff', 'stroke-width': 1
    }));
    const lab1 = svg('text', { x: x0 - 4, y: cy + 4, fill: '#5c6383', 'font-size': 8, 'text-anchor': 'end' });
    lab1.appendChild(document.createTextNode('Rf=' + fr.toFixed(1)));
    svgRoot.appendChild(lab1);
    const lab2 = svg('text', { x: x2 + 4, y: cy + 4, fill: '#5c6383', 'font-size': 8 });
    lab2.appendChild(document.createTextNode('Rb=' + br.toFixed(1)));
    svgRoot.appendChild(lab2);
    const rows = [
      ['TYPE', 'Cylinder'],
      ['Rf/Ro/Rb', fr.toFixed(1) + ' / ' + out.toFixed(1) + ' / ' + br.toFixed(1)],
      ['hf/hb' + _uSuffix('disp'), fh.toFixed(1) + ' / ' + bh.toFixed(1)],
      ['v0' + _uSuffix('vel'), fmt(imp.velocity, 0)],
      ['KE' + _uSuffix('energy'), fmt(imp.kinetic_energy, 2)]
    ];
    for (const r of rows) tbl.appendChild(el('tr', null, [el('td', { class: 'tl dim' }, r[0]), el('td', { class: 'num b' }, r[1])]));
    cap.textContent = 'Asymmetric tumbler: front + outer + back 3-stage cylinder.';
  } else {
    sub.textContent = imp.type;
    cap.textContent = 'Unknown impactor type';
  }
}

function initDoeBreakdown() {
  const tbl = document.getElementById('doe-breakdown');
  const sub = document.getElementById('doeSubLabel');
  while (tbl.firstChild) tbl.removeChild(tbl.firstChild);
  const cnt = {};
  for (const f of FACES) cnt[f.code] = 0;
  for (const p of DATA.positions) cnt[p.face] = (cnt[p.face] || 0) + 1;
  const total = Object.values(cnt).reduce((a, b) => a + b, 0);
  const doeType = (DATA.meta.doe_config && DATA.meta.doe_config.type) || 'grid';
  sub.textContent = doeType + ' · ' + total + ' pos';
  for (const f of FACES) {
    tbl.appendChild(el('tr', null, [
      el('td', { class: 'tl b' }, f.code),
      el('td', { class: 'tl dim' }, f.name),
      el('td', { class: 'num' }, String(cnt[f.code]))
    ]));
  }
  tbl.appendChild(el('tr', null, [
    el('td', { class: 'tl b', style: { color: 'var(--accent)' } }, 'TOTAL'),
    el('td', { class: 'tl dim' }, DATA.meta.generation_mode),
    el('td', { class: 'num b', style: { color: 'var(--accent)' } }, String(total))
  ]));
}

/* ===================================================================
 * Impact Inspector  (Page 2 hero + Page 1 bi-face mini/split)
 * =================================================================== */

/** Map XY (mm) into SVG viewBox coords using the device bbox + a pad. */
function _xyToVB(x, y, vbW, vbH, padPx) {
  const bb = DEVICE_BBOX;
  if (!bb) return [vbW / 2, vbH / 2];
  const w = bb.xmax - bb.xmin, h = bb.ymax - bb.ymin;
  if (w <= 0 || h <= 0) return [vbW / 2, vbH / 2];
  // preserve aspect ratio inside vbW x vbH (with padPx margin)
  const innerW = vbW - 2 * padPx, innerH = vbH - 2 * padPx;
  const scale = Math.min(innerW / w, innerH / h);
  const drawW = w * scale, drawH = h * scale;
  const ox = (vbW - drawW) / 2, oy = (vbH - drawH) / 2;
  const u = (x - bb.xmin) / w;
  const v = 1 - (y - bb.ymin) / h;  // flip Y so +y points up
  return [ox + u * drawW, oy + v * drawH];
}

/** Per-position max metric value for a given face. */
const POS_MAX_BY_METRIC = {};
function _ensurePosMax(metric) {
  if (POS_MAX_BY_METRIC[metric]) return POS_MAX_BY_METRIC[metric];
  const out = {};
  for (const r of RESULTS) {
    const k = r.face + '|' + r.pos_id;
    const v = r[metric] || 0;
    const cur = out[k];
    if (!cur || v > cur.v) {
      out[k] = { v: v, x: r.x, y: r.y, face: r.face, pos_id: r.pos_id, part_id: r.part_id, part_name: r.part_name };
    }
  }
  POS_MAX_BY_METRIC[metric] = out;
  return out;
}

/** (face, pos_id, part_id) → result row */
const RESULT_IDX = {};
for (const r of RESULTS) RESULT_IDX[r.face + '|' + r.pos_id + '|' + r.part_id] = r;

/** Footprint helpers — return centroid + bbox of a part's polygon. */
function _footprintBBox(fp) {
  if (!fp || !fp.length) return null;
  let xmin = Infinity, xmax = -Infinity, ymin = Infinity, ymax = -Infinity;
  let cx = 0, cy = 0;
  for (const pt of fp) {
    const x = pt[0], y = pt[1];
    if (x < xmin) xmin = x; if (x > xmax) xmax = x;
    if (y < ymin) ymin = y; if (y > ymax) ymax = y;
    cx += x; cy += y;
  }
  cx /= fp.length; cy /= fp.length;
  return { xmin: xmin, xmax: xmax, ymin: ymin, ymax: ymax, cx: cx, cy: cy };
}

/** Render the Impact Inspector into a target svg/container.
 *  opts = { containerId, faceCode, interactive: bool, mainPanel: bool, height: 'aspect' }
 */
function initImpactInspector(opts) {
  const faceCode = opts.faceCode;
  const interactive = !!opts.interactive;
  const root = document.getElementById(opts.containerId);
  if (!root) return;
  while (root.firstChild) root.removeChild(root.firstChild);

  const vbW = 800, vbH = 600;
  root.setAttribute('viewBox', '0 0 ' + vbW + ' ' + vbH);
  root.setAttribute('preserveAspectRatio', 'xMidYMid meet');

  const metric = STATE.ii.metric;

  // background
  root.appendChild(svg('rect', { x: 0, y: 0, width: vbW, height: vbH, fill: '#0e1320', rx: 6 }));

  // device outline (rounded dashed rect at true bbox). Skip when no bbox.
  const bb = DEVICE_BBOX;
  if (bb) {
    const tl = _xyToVB(bb.xmin, bb.ymax, vbW, vbH, 28);
    const br = _xyToVB(bb.xmax, bb.ymin, vbW, vbH, 28);
    root.appendChild(svg('rect', {
      x: tl[0], y: tl[1], width: br[0] - tl[0], height: br[1] - tl[1],
      rx: 6, ry: 6, fill: 'none', stroke: '#3a4055', 'stroke-width': 1.2,
      'stroke-dasharray': '5,4'
    }));
  } else {
    const t = svg('text', { x: vbW / 2, y: vbH / 2, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 14 });
    t.appendChild(document.createTextNode('no device layout'));
    root.appendChild(t);
  }

  // part outlines layer
  const partsLayer = svg('g', { id: opts.containerId + '-parts' });
  for (const p of PARTS) {
    const bbf = _footprintBBox(p.footprint);
    if (!bbf) continue;
    const a = _xyToVB(bbf.xmin, bbf.ymax, vbW, vbH, 28);
    const b = _xyToVB(bbf.xmax, bbf.ymin, vbW, vbH, 28);
    const w = b[0] - a[0], h = b[1] - a[1];
    if (w < 1 || h < 1) continue;
    const rect = svg('rect', {
      x: a[0], y: a[1], width: w, height: h, rx: 2, ry: 2,
      fill: 'rgba(170,178,207,0.06)',
      stroke: 'rgba(170,178,207,0.40)',
      'stroke-width': 1.2,
      'data-part-id': p.id
    });
    rect.dataset.partid = p.id;
    partsLayer.appendChild(rect);
    // part label (small, dim, near top of rect)
    if (w > 35 && h > 14) {
      const lab = svg('text', {
        x: a[0] + w / 2, y: a[1] + 12,
        'text-anchor': 'middle', fill: 'rgba(170,178,207,0.55)',
        'font-size': 8.5, 'font-family': 'JetBrains Mono', 'data-part-label': p.id
      });
      lab.appendChild(document.createTextNode(p.name.split('\\').pop().slice(0, 14)));
      partsLayer.appendChild(lab);
    }
  }
  root.appendChild(partsLayer);

  // impact dots layer
  const dotsLayer = svg('g', { id: opts.containerId + '-dots' });
  const posMax = _ensurePosMax(metric);
  const facePosKeys = Object.keys(posMax).filter(k => k.indexOf(faceCode + '|') === 0);
  let globalMax = 0;
  for (const k of facePosKeys) { const v = posMax[k].v; if (v > globalMax) globalMax = v; }
  const threshAbs = globalMax * (STATE.ii.thresh / 100.0);
  let worstK = null;
  for (const k of facePosKeys) if (!worstK || posMax[k].v > posMax[worstK].v) worstK = k;

  for (const k of facePosKeys) {
    const rec = posMax[k];
    const passes = rec.v >= threshAbs;
    const [cx, cy] = _xyToVB(rec.x, rec.y, vbW, vbH, 28);
    const t = globalMax > 0 ? rec.v / globalMax : 0;
    const fill = passes ? gColor(t) : 'rgba(170,178,207,0.15)';
    const r = interactive ? 6 : 5;
    const dot = svg('circle', {
      cx: cx, cy: cy, r: r, fill: fill,
      stroke: 'rgba(10,12,20,0.8)', 'stroke-width': 0.8,
      'data-pos-key': k
    });
    if (interactive) {
      dot.style.cursor = 'pointer';
      dot.addEventListener('mouseenter', function () {
        if (STATE.ii.pinned) return;
        STATE.ii.hovered_pos = k;
        _renderInspectorFill(rec, globalMax);
        _renderSidePanel(rec, globalMax);
      });
      dot.addEventListener('click', function () {
        STATE.ii.hovered_pos = k;
        STATE.ii.pinned = true;
        const pin = document.getElementById('ii-pin');
        if (pin) { pin.checked = true; document.getElementById('ii-pin-lab').classList.add('locked'); }
        _renderInspectorFill(rec, globalMax);
        _renderSidePanel(rec, globalMax);
      });
    } else {
      // non-interactive cell: clicking jumps to Page 2 with this face
      dot.style.cursor = 'pointer';
    }
    const titleNode = svg('title', {});
    titleNode.appendChild(document.createTextNode(rec.pos_id + '\nX=' + rec.x.toFixed(2) + ' Y=' + rec.y.toFixed(2) + '\nmax part: ' + rec.part_name + '\n' + _metricLabel(metric) + ' = ' + fmt(rec.v, 2)));
    dot.appendChild(titleNode);
    dotsLayer.appendChild(dot);
  }

  // worst marker (★)
  if (worstK) {
    const rec = posMax[worstK];
    const [cx, cy] = _xyToVB(rec.x, rec.y, vbW, vbH, 28);
    const star = svg('text', {
      x: cx, y: cy + 4, 'text-anchor': 'middle', fill: '#ff3854',
      'font-size': 18, 'font-weight': 700, 'pointer-events': 'none'
    });
    star.appendChild(document.createTextNode('★'));
    dotsLayer.appendChild(star);
  }
  root.appendChild(dotsLayer);

  // hover halo layer (interactive only)
  if (interactive) {
    const haloLayer = svg('g', { id: 'ii-halo-layer' });
    root.appendChild(haloLayer);
    // mouseleave on root clears hover unless pinned
    root.addEventListener('mouseleave', function () {
      if (STATE.ii.pinned) return;
      STATE.ii.hovered_pos = null;
      _renderInspectorClear();
    });
  }

  // non-interactive cell click → jump to Inspector
  if (!interactive) {
    root.style.cursor = 'pointer';
    root.addEventListener('click', function () {
      const btn = document.querySelector('.ctlbar .btn[data-ii-face="' + faceCode + '"]');
      if (btn) btn.click();
      const tgt = document.getElementById('s2');
      if (tgt) tgt.scrollIntoView({ behavior: 'smooth' });
    });
  }
}

function _metricLabel(m) {
  return ({
    g: 'Peak G',
    s: 'σ' + _uSuffix('stress'),
    e: 'ε',
    d: 'd' + _uSuffix('disp')
  })[m] || m;
}

function _renderInspectorClear() {
  const layer = document.getElementById('ii-svg-parts');
  if (!layer) return;
  for (const node of layer.querySelectorAll('rect[data-part-id]')) {
    node.setAttribute('fill', 'rgba(170,178,207,0.06)');
    node.setAttribute('stroke', 'rgba(170,178,207,0.40)');
    node.setAttribute('stroke-width', '1.2');
  }
  const halo = document.getElementById('ii-halo-layer');
  if (halo) while (halo.firstChild) halo.removeChild(halo.firstChild);
  const star = layer.parentNode.querySelector('text[data-star-overlay]');
  if (star) star.remove();
  const empty = '<div class="ii-empty">충돌 위치 위에 마우스를 올리세요.</div>';
  const hInfo = document.getElementById('ii-hover-info'); if (hInfo) hInfo.innerHTML = empty;
  const partsList = document.getElementById('ii-parts-list'); if (partsList) partsList.innerHTML = '<div class="ii-empty">-</div>';
  const thSvg = document.getElementById('ii-th-svg'); if (thSvg) while (thSvg.firstChild) thSvg.removeChild(thSvg.firstChild);
  const sub = document.getElementById('ii-th-sub'); if (sub) sub.textContent = '';
  const badge = document.getElementById('ii-behavior-badge'); if (badge) badge.innerHTML = '';
  const kpi = document.getElementById('ii-traj-kpi'); if (kpi) kpi.innerHTML = '';
}

function _renderInspectorFill(rec, globalMax) {
  const layer = document.getElementById('ii-svg-parts');
  if (!layer) return;
  const metric = STATE.ii.metric;
  const norm = STATE.ii.norm;
  const faceCode = STATE.ii.face;
  // collect per-part response for this impact
  const partResps = [];
  let localMax = 0;
  for (const p of PARTS) {
    const r = RESULT_IDX[rec.face + '|' + rec.pos_id + '|' + p.id];
    const v = r ? (r[metric] || 0) : 0;
    if (v > localMax) localMax = v;
    partResps.push({ part: p, v: v, r: r });
  }
  const denom = norm === 'rel' ? Math.max(1e-9, localMax) : Math.max(1e-9, globalMax);
  let maxPart = null;
  for (const it of partResps) if (!maxPart || it.v > maxPart.v) maxPart = it;
  // fill each part rect
  for (const node of layer.querySelectorAll('rect[data-part-id]')) {
    const pid = parseInt(node.dataset.partid, 10);
    const entry = partResps.find(x => x.part.id === pid);
    if (!entry || entry.v <= 0) {
      node.setAttribute('fill', 'rgba(170,178,207,0.04)');
      node.setAttribute('stroke', 'rgba(170,178,207,0.18)');
      node.setAttribute('stroke-width', '1');
      continue;
    }
    const t = Math.min(1, entry.v / denom);
    const c = gColor(t);
    node.setAttribute('fill', c.replace('rgb', 'rgba').replace(')', ',0.45)'));
    node.setAttribute('stroke', c);
    node.setAttribute('stroke-width', (maxPart && entry.part.id === maxPart.part.id) ? '2.5' : '1.5');
  }
  // halo pulse over the hovered impact
  const halo = document.getElementById('ii-halo-layer');
  if (halo) {
    while (halo.firstChild) halo.removeChild(halo.firstChild);
    const [hx, hy] = _xyToVB(rec.x, rec.y, 800, 600, 28);
    const ring = svg('circle', {
      cx: hx, cy: hy, r: 6, fill: 'none', stroke: '#ff3854', 'stroke-width': 2,
      class: 'ii-halo', 'pointer-events': 'none'
    });
    halo.appendChild(ring);
    // ★ marker over max part
    if (maxPart && maxPart.v > 0) {
      const bbf = _footprintBBox(maxPart.part.footprint);
      if (bbf) {
        const [sx, sy] = _xyToVB(bbf.cx, bbf.cy, 800, 600, 28);
        const star = svg('text', {
          x: sx, y: sy + 5, 'text-anchor': 'middle', fill: '#ffffff',
          'font-size': 16, 'font-weight': 700, 'pointer-events': 'none',
          'data-star-overlay': '1'
        });
        star.appendChild(document.createTextNode('★'));
        halo.appendChild(star);
      }
    }
  }
}

function _renderSidePanel(rec, globalMax) {
  const metric = STATE.ii.metric;
  const faceCode = STATE.ii.face;
  const norm = STATE.ii.norm;
  // hovered info
  const hInfo = document.getElementById('ii-hover-info');
  if (hInfo) {
    // global rank for this face
    const posMax = _ensurePosMax(metric);
    const facePosKeys = Object.keys(posMax).filter(k => k.indexOf(faceCode + '|') === 0);
    const sortedKeys = facePosKeys.sort((a, b) => posMax[b].v - posMax[a].v);
    const rank = sortedKeys.indexOf(faceCode + '|' + rec.pos_id) + 1;
    hInfo.innerHTML = '';
    hInfo.appendChild(el('div', { class: 'iirow' }, [el('span', null, 'POS'), el('b', null, rec.pos_id)]));
    hInfo.appendChild(el('div', { class: 'iirow' }, [el('span', null, '(X, Y)'), el('b', null, rec.x.toFixed(2) + ', ' + rec.y.toFixed(2))]));
    hInfo.appendChild(el('div', { class: 'iirow' }, [el('span', null, 'RANK'), el('b', null, '#' + rank + ' / ' + facePosKeys.length)]));
    hInfo.appendChild(el('div', { class: 'iirow' }, [el('span', null, 'MAX'), el('b', { style: { color: 'var(--crit)' } }, rec.part_name + ' · ' + fmt(rec.v, 1))]));
  }
  // top affected parts (sorted desc)
  const partResps = [];
  let localMax = 0;
  for (const p of PARTS) {
    const r = RESULT_IDX[rec.face + '|' + rec.pos_id + '|' + p.id];
    const v = r ? (r[metric] || 0) : 0;
    if (v > localMax) localMax = v;
    partResps.push({ part: p, v: v });
  }
  partResps.sort((a, b) => b.v - a.v);
  const denom = norm === 'rel' ? Math.max(1e-9, localMax) : Math.max(1e-9, globalMax);
  const list = document.getElementById('ii-parts-list');
  if (list) {
    list.innerHTML = '';
    for (let i = 0; i < partResps.length; i++) {
      const it = partResps[i];
      if (it.v <= 0 && i > 0) break;
      const t = Math.min(1, it.v / denom);
      const c = gColor(t);
      const row = el('div', { class: 'ii-bar-row' + (i === 0 ? ' is-max' : '') }, [
        el('div', { class: 'nm', title: it.part.name }, it.part.name.split('\\').pop()),
        el('div', { class: 'bw' }, [el('span', { class: 'fl', style: { width: (t * 100).toFixed(1) + '%', background: c } })]),
        el('div', { class: 'vl' }, fmt(it.v, 1))
      ]);
      row.addEventListener('click', function () {
        STATE.ii.selected_part = it.part.id;
        // flash that part in main canvas
        const layer = document.getElementById('ii-svg-parts');
        if (layer) {
          const node = layer.querySelector('rect[data-part-id="' + it.part.id + '"]');
          if (node) {
            const orig = node.getAttribute('stroke-width');
            node.setAttribute('stroke-width', '4');
            setTimeout(() => node.setAttribute('stroke-width', orig || '1.5'), 600);
          }
        }
      });
      list.appendChild(row);
    }
  }
  // KE decay overlay (real impactor trajectory) + behavior badge — replaces synthetic envelope
  renderInspectorBehaviorBadge(rec);
  renderInspectorKEOverlay(rec);
}

function _renderTimeHistory(rec, partId) {
  const svgRoot = document.getElementById('ii-th-svg');
  if (!svgRoot) return;
  while (svgRoot.firstChild) svgRoot.removeChild(svgRoot.firstChild);
  const W = 200, H = 70;
  const r = RESULT_IDX[rec.face + '|' + rec.pos_id + '|' + partId];
  const p = PART_BY_ID[partId];
  document.getElementById('ii-th-sub').textContent = '(' + (p ? p.name.split('\\').pop() : '-') + ')';
  if (!r) {
    const t = svg('text', { x: W / 2, y: H / 2, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 9 });
    t.appendChild(document.createTextNode('no time-series'));
    svgRoot.appendChild(t);
    return;
  }
  // Real stress time-series from PairResult.stress_ts (d3plot extraction).
  // If unavailable, render an explicit placeholder rather than a synthetic
  // Gaussian — fake envelopes were misleading the user.
  const ts = r.stress_ts || {};
  const times = Array.isArray(ts.times) ? ts.times : [];
  const vals = Array.isArray(ts.max_values) ? ts.max_values : [];
  if (!times.length || !vals.length || times.length !== vals.length) {
    const t = svg('text', { x: W / 2, y: H / 2, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 9 });
    t.appendChild(document.createTextNode('no time-series data'));
    svgRoot.appendChild(t);
    return;
  }
  const tMin = times[0], tMax = times[times.length - 1] || tMin + 1;
  const vMax = Math.max.apply(null, vals.map(Math.abs)) || 1;
  const tx = (t) => ((t - tMin) / (tMax - tMin)) * W;
  const vy = (v) => H - 8 - (Math.abs(v) / vMax) * (H - 16);
  const pts = times.map((t, i) => [tx(t), vy(vals[i])]);
  svgRoot.appendChild(svg('polyline', {
    points: pts.map(pt => pt.join(',')).join(' '),
    fill: 'none', stroke: '#ff3854', 'stroke-width': 1.4,
  }));
}

/** Bi-Face Split (Page 1) — two compact non-interactive Inspector panels. */
function renderBiFaceSplit() {
  const big = document.getElementById('biface-split');
  const mini = document.getElementById('biface-mini');
  const targets = [
    { code: 'F2', name: 'Front', label: 'FRONT · F2' },
    { code: 'F1', name: 'Back',  label: 'BACK · F1' }
  ];

  // big version (page 1 main panel)
  if (big) {
    while (big.firstChild) big.removeChild(big.firstChild);
    for (const t of targets) {
      const f = FACE_BY_CODE[t.code];
      if (!f) continue;
      const card = el('div', { class: 'biface-cell' });
      const head = el('div', { class: 'bf-head' }, [
        el('div', { class: 'bf-name' }, t.label),
        el('div', { class: 'bf-sub' }, (f.name || '').toUpperCase())
      ]);
      card.appendChild(head);
      const id = 'bf-svg-' + t.code;
      const svgEl = svg('svg', { id: id });
      card.appendChild(svgEl);
      const foot = el('div', { class: 'bf-foot' }, [el('span', { id: 'bf-foot-' + t.code }, 'max = -')]);
      card.appendChild(foot);
      card.addEventListener('click', function () {
        const btn = document.querySelector('.ctlbar .btn[data-ii-face="' + t.code + '"]');
        if (btn) btn.click();
        const tgt = document.getElementById('s2');
        if (tgt) tgt.scrollIntoView({ behavior: 'smooth' });
      });
      big.appendChild(card);
      initImpactInspector({ containerId: id, faceCode: t.code, interactive: false });
      // populate foot label
      const posMax = _ensurePosMax(STATE.ii.metric);
      const keys = Object.keys(posMax).filter(k => k.indexOf(t.code + '|') === 0);
      let worst = null;
      for (const k of keys) if (!worst || posMax[k].v > worst.v) worst = posMax[k];
      if (worst) document.getElementById('bf-foot-' + t.code).innerHTML = 'max: <b>' + fmt(worst.v, 1) + '</b> ' + (STATE.ii.metric === 'g' ? 'G' : '') + ' &middot; ' + worst.part_name;
    }
  }

  // mini version (page 1 method-band)
  if (mini) {
    while (mini.firstChild) mini.removeChild(mini.firstChild);
    for (const t of targets) {
      const f = FACE_BY_CODE[t.code];
      if (!f) continue;
      const card = el('div', { class: 'biface-cell', style: { padding: '6px 8px' } });
      card.appendChild(el('div', { class: 'bf-head', style: { paddingBottom: '3px', marginBottom: '3px' } }, [
        el('div', { class: 'bf-name', style: { fontSize: '10px' } }, t.code),
        el('div', { class: 'bf-sub' }, f.name)
      ]));
      const id = 'bfm-svg-' + t.code;
      card.appendChild(svg('svg', { id: id }));
      card.addEventListener('click', function () {
        const btn = document.querySelector('.ctlbar .btn[data-ii-face="' + t.code + '"]');
        if (btn) btn.click();
        const tgt = document.getElementById('s2');
        if (tgt) tgt.scrollIntoView({ behavior: 'smooth' });
      });
      mini.appendChild(card);
      initImpactInspector({ containerId: id, faceCode: t.code, interactive: false });
    }
  }
}

/** Page 2 Inspector (interactive). */
function renderInspector() {
  // ensure svg id matches what _renderInspectorFill expects (-parts suffix)
  const root = document.getElementById('ii-svg');
  if (!root) return;
  initImpactInspector({ containerId: 'ii-svg', faceCode: STATE.ii.face, interactive: true });
  // rename parts layer id so the *Fill helper finds it predictably
  const oldParts = document.getElementById('ii-svg-parts');
  if (oldParts) oldParts.id = 'ii-svg-parts';  // already correct from initImpactInspector
  // update header / metric labels
  const f = FACE_BY_CODE[STATE.ii.face];
  document.getElementById('ii-face-label').textContent = (f ? (f.name + ' (' + f.code + ')') : STATE.ii.face).toUpperCase();
  const metric = STATE.ii.metric;
  document.getElementById('ii-metric-name').textContent = _metricLabel(metric);
  // cbar max
  const posMax = _ensurePosMax(metric);
  const keys = Object.keys(posMax).filter(k => k.indexOf(STATE.ii.face + '|') === 0);
  let gmx = 0; for (const k of keys) if (posMax[k].v > gmx) gmx = posMax[k].v;
  document.getElementById('ii-cbar-max').textContent = fmt(gmx, 1);
  // thresh label
  document.getElementById('ii-thresh-val').textContent = STATE.ii.thresh + '% (' + fmt(gmx * STATE.ii.thresh / 100, 1) + ')';
  // if a pinned/hovered impact exists, re-render fill
  if (STATE.ii.hovered_pos && posMax[STATE.ii.hovered_pos]) {
    _renderInspectorFill(posMax[STATE.ii.hovered_pos], gmx);
    _renderSidePanel(posMax[STATE.ii.hovered_pos], gmx);
  } else {
    _renderInspectorClear();
  }
}

function initFaceKpiTable() {
  const tbody = document.querySelector('#face-kpi-tbl tbody');
  while (tbody.firstChild) tbody.removeChild(tbody.firstChild);
  let gmax = 0;
  for (const r of RESULTS) if (r.g > gmax) gmax = r.g;
  // Risk-score config (None in payload => panel hidden, no score column).
  const rsCfg = DATA.risk_score;
  const k = DATA.kpi || {};
  const crit_t = (k.crit_threshold != null) ? k.crit_threshold : 0;
  // compute scores for each face first so we can do the vs-other delta
  const faceStats = {};
  for (const f of FACES) {
    const rows = FACE_RESULTS[f.code] || [];
    if (!rows.length) continue;
    let worst = rows[0];
    for (const r of rows) if (r.g > worst.g) worst = r;
    const gvals = rows.map(r => r.g).sort((a, b) => a - b);
    const p95 = gvals[Math.floor(gvals.length * 0.95)] || 0;
    // Critical-count uses the payload's P95 threshold (same as the rest of
    // the report) instead of the magic 0.5 ratio.
    const crit = gvals.filter(v => v >= crit_t).length;
    let score = null;
    if (rsCfg && rsCfg.weights) {
      const w = rsCfg.weights;
      const ww = (w.worst != null ? w.worst : 0);
      const wp = (w.p95   != null ? w.p95   : 0);
      const wc = (w.crit  != null ? w.crit  : 0);
      score = (ww * worst.g / Math.max(1, gmax)
             + wp * p95     / Math.max(1, gmax)
             + wc * crit    / Math.max(1, gvals.length)) * 10;
    }
    const nPos = new Set(rows.map(r => r.pos_id)).size;
    faceStats[f.code] = { face: f, worst: worst, score: score, n: nPos };
  }
  // Hide SCORE / Δ columns when risk_score config is absent.
  const head = document.querySelector('#face-kpi-tbl thead tr');
  if (head && !rsCfg) {
    const ths = head.querySelectorAll('th');
    if (ths.length >= 7) {
      ths[5].style.display = 'none';
      ths[6].style.display = 'none';
    }
  }
  const codes = Object.keys(faceStats);
  for (const code of codes) {
    const s = faceStats[code];
    const f = s.face;
    const worst = s.worst;
    const score = s.score;
    const otherCode = codes.find(c => c !== code);
    let cls = 'r-safe';
    let scoreColor = 'var(--dim)';
    let dStr = '-';
    let dColor = 'var(--dim)';
    if (rsCfg && score != null) {
      const critBand = rsCfg.crit_band;
      const warnBand = rsCfg.warn_band;
      cls = (critBand != null && score >= critBand) ? 'r-crit'
          : (warnBand != null && score >= warnBand) ? 'r-warn' : 'r-safe';
      scoreColor = (critBand != null && score >= critBand) ? 'var(--crit)'
                 : (warnBand != null && score >= warnBand) ? 'var(--warn)' : 'var(--good)';
      const otherScore = (otherCode != null && faceStats[otherCode].score != null)
                       ? faceStats[otherCode].score : score;
      const delta = score - otherScore;
      dColor = delta > 0 ? 'var(--crit)' : delta < 0 ? 'var(--good)' : 'var(--dim)';
      dStr = (delta > 0 ? '+' : '') + delta.toFixed(2);
    }
    const cells = [
      el('td', { class: 'tl b' }, f.code + ' · ' + f.name),
      el('td', { class: 'num' }, String(s.n)),
      el('td', { class: 'num b' }, fmt(worst.g, 0)),
      el('td', { class: 'num dim' }, worst.x.toFixed(1) + ' , ' + worst.y.toFixed(1)),
      el('td', { class: 'tl b' }, worst.part_name),
      el('td', { class: 'num', style: { color: scoreColor } }, rsCfg && score != null ? (score.toFixed(1) + ' / 10') : '-'),
      el('td', { class: 'num', style: { color: dColor } }, dStr)
    ];
    if (!rsCfg) {
      cells[5].style.display = 'none';
      cells[6].style.display = 'none';
    }
    tbody.appendChild(el('tr', { class: cls }, cells));
  }
}

function initTopK() {
  const tbody = document.querySelector('#topk-tbl tbody');
  while (tbody.firstChild) tbody.removeChild(tbody.firstChild);
  const sorted = RESULTS.slice().sort((a, b) => b.g - a.g).slice(0, 12);
  // Use payload P95/P75 thresholds for row coloring (matches verdict matrix).
  const k = DATA.kpi || {};
  const g_vals = RESULTS.map(x => x.g).filter(v => v > 0);
  const crit_t = (k.crit_threshold != null) ? k.crit_threshold : _percentile(g_vals, 0.95);
  const warn_t = (k.warn_threshold != null) ? k.warn_threshold : _percentile(g_vals, 0.75);
  const infl_t = (k.influence_threshold != null) ? k.influence_threshold : _percentile(g_vals, 0.85);
  for (let i = 0; i < sorted.length; i++) {
    const r = sorted[i];
    const partRows = RESULTS.filter(x => x.part_id === r.part_id);
    // Influence area: count rows in this part above the P85 g threshold.
    const inf = partRows.filter(x => x.g >= infl_t).length;
    // Row color is value-based (P95/P75), not rank-based.
    const cls = r.g >= crit_t ? 'r-crit' : r.g >= warn_t ? 'r-warn' : 'r-safe';
    tbody.appendChild(el('tr', { class: cls }, [
      el('td', { class: 'tl b' }, '#' + (i + 1)),
      el('td', { class: 'tl b' }, r.face),
      el('td', { class: 'num' }, r.x.toFixed(2)),
      el('td', { class: 'num' }, r.y.toFixed(2)),
      el('td', { class: 'tl' }, r.part_name),
      el('td', { class: 'num b' }, fmt(r.g, 0)),
      el('td', { class: 'num' }, fmt(r.s, 1)),
      el('td', { class: 'num dim' }, inf + ' / ' + partRows.length)
    ]));
  }
}

function partMatches(p) {
  if (!STATE.filter) return true;
  return p.name.toLowerCase().indexOf(STATE.filter.toLowerCase()) >= 0;
}

function renderInfluenceMatrix() {
  const wrap = document.getElementById('imatrix-wrap');
  if (!wrap) return;
  while (wrap.firstChild) wrap.removeChild(wrap.firstChild);
  // top-10 impact positions on currently selected face, by the active metric
  const metric = STATE.ii.metric;
  const faceCode = STATE.ii.face;
  const posMax = _ensurePosMax(metric);
  const faceKeys = Object.keys(posMax).filter(k => k.indexOf(faceCode + '|') === 0);
  faceKeys.sort((a, b) => posMax[b].v - posMax[a].v);
  const topPairs = faceKeys.slice(0, 10).map(k => posMax[k]);
  let gmx = 0;
  for (const r of RESULTS) { const v = r[metric] || 0; if (v > gmx) gmx = v; }
  const tbl = el('table', { class: 'imatrix' });
  const trHead = el('tr', null, [el('th', { class: 'tl', style: { minWidth: '160px' } }, 'IMPACT (face · X, Y)')]);
  for (const p of PARTS) {
    trHead.appendChild(el('th', {
      style: { transform: 'rotate(-30deg)', transformOrigin: 'left bottom', whiteSpace: 'nowrap', paddingLeft: '10px', color: 'var(--accent)' }
    }, p.name.split('\\').pop()));
  }
  trHead.appendChild(el('th', null, 'MAX'));
  tbl.appendChild(el('thead', null, trHead));
  const tbody = el('tbody');
  for (const pair of topPairs) {
    const tr = el('tr');
    const labCell = el('td', { class: 'tl', style: { color: 'var(--fg)', fontWeight: 600, cursor: 'pointer' } }, pair.face + ' · ' + pair.x.toFixed(1) + ', ' + pair.y.toFixed(1));
    labCell.addEventListener('click', function () {
      STATE.ii.hovered_pos = pair.face + '|' + pair.pos_id;
      STATE.ii.pinned = true;
      const pin = document.getElementById('ii-pin');
      if (pin) { pin.checked = true; document.getElementById('ii-pin-lab').classList.add('locked'); }
      const key = STATE.ii.hovered_pos;
      const rec = posMax[key];
      if (rec) {
        _renderInspectorFill(rec, gmx);
        _renderSidePanel(rec, gmx);
      }
      const tgt = document.getElementById('s2');
      if (tgt) tgt.scrollIntoView({ behavior: 'smooth' });
    });
    tr.appendChild(labCell);
    for (const p of PARTS) {
      const match = RESULT_IDX[pair.face + '|' + pair.pos_id + '|' + p.id];
      const v = match ? (match[metric] || 0) : 0;
      const td = el('td', {
        class: 'cell',
        title: p.name + ': ' + fmt(v, 2),
        style: { background: v > 0 ? gColor(Math.min(1, v / Math.max(1e-9, gmx))) : '#0a0c14' }
      });
      tr.appendChild(td);
    }
    tr.appendChild(el('td', { style: { color: 'var(--num)', fontWeight: 700, paddingLeft: '8px' } }, fmt(pair.v, 1)));
    tbody.appendChild(tr);
  }
  tbl.appendChild(tbody);
  wrap.appendChild(tbl);
}

function _percentile(arr, p) {
  if (!arr || !arr.length) return 0;
  const a = arr.slice().sort((x, y) => x - y);
  const idx = Math.floor(p * (a.length - 1));
  return a[Math.max(0, Math.min(a.length - 1, idx))];
}

function renderVerdict() {
  const tbody = document.querySelector('#verdict-tbl tbody');
  while (tbody.firstChild) tbody.removeChild(tbody.firstChild);
  const byPart = {};
  for (const r of RESULTS) {
    const cur = byPart[r.part_id];
    if (!cur || r.g > cur.g) byPart[r.part_id] = r;
  }
  // Use payload-supplied percentile thresholds (P95 = crit, P75 = warn).
  // Falls back to JS-side percentile if payload field missing.
  const k = DATA.kpi || {};
  const g_vals = RESULTS.map(r => r.g).filter(v => v > 0);
  const crit_t = (k.crit_threshold != null) ? k.crit_threshold : _percentile(g_vals, 0.95);
  const warn_t = (k.warn_threshold != null) ? k.warn_threshold : _percentile(g_vals, 0.75);
  const infl_t = (k.influence_threshold != null) ? k.influence_threshold : _percentile(g_vals, 0.85);
  let nC = 0, nW = 0, nS = 0;
  const rows = Object.values(byPart).sort((a, b) => b.g - a.g);
  for (const r of rows) {
    const partRows = RESULTS.filter(x => x.part_id === r.part_id);
    const vs = partRows.map(x => x.g);
    const mean = vs.reduce((a, b) => a + b, 0) / vs.length;
    const variance = vs.reduce((a, b) => a + (b - mean) * (b - mean), 0) / vs.length;
    const cov = mean > 0 ? Math.sqrt(variance) / mean : 0;
    // influence: rows in this part exceeding the P85 threshold
    const inf = vs.filter(v => v >= infl_t).length;
    const klass = r.g >= crit_t ? 'CRITICAL' : r.g >= warn_t ? 'WARNING' : 'PASSED';
    if (klass === 'CRITICAL') nC++; else if (klass === 'WARNING') nW++; else nS++;
    const rowClass = klass === 'CRITICAL' ? 'r-crit' : klass === 'WARNING' ? 'r-warn' : 'r-safe';
    const klassColor = klass === 'CRITICAL' ? 'var(--crit)' : klass === 'WARNING' ? 'var(--warn)' : 'var(--good)';
    // MODE: just report influence count without the 0.5-ratio "전반 약화" magic
    tbody.appendChild(el('tr', { class: rowClass }, [
      el('td', { class: 'tl b' }, r.part_name),
      el('td', { class: 'tl' }, r.face),
      el('td', { class: 'num' }, r.x.toFixed(1)),
      el('td', { class: 'num' }, r.y.toFixed(1)),
      el('td', { class: 'tl', style: { color: klassColor } }, klass),
      el('td', { class: 'num b' }, fmt(r.g, 0)),
      el('td', { class: 'num' }, fmt(r.s, 1)),
      el('td', { class: 'num' }, r.e.toFixed(4)),
      el('td', { class: 'num' }, r.d.toFixed(3)),
      el('td', { class: 'num dim' }, cov.toFixed(2)),
      el('td', { class: 'num' }, inf + '/' + partRows.length),
      el('td', { class: 'tl dim' }, String(inf))
    ]));
  }
  document.getElementById('vCrit').textContent = nC;
  document.getElementById('vWarn').textContent = nW;
  document.getElementById('vSafe').textContent = nS;
}

function renderTSGrid() {
  const grid = document.getElementById('ts-grid');
  while (grid.firstChild) grid.removeChild(grid.firstChild);
  const top = RESULTS.slice().sort((a, b) => b.g - a.g).slice(0, 12);
  for (let i = 0; i < top.length; i++) {
    const r = top[i];
    const div = el('div', { class: 'ts-mini' }, [
      el('div', { class: 'tlabel' }, [
        el('span', null, r.face + ' · ' + r.part_name.split('\\').pop()),
        el('span', null, fmt(r.s, 1) + (_u('stress') ? ' ' + _u('stress') : ''))
      ])
    ]);
    const s = svg('svg', { viewBox: '0 0 200 64', preserveAspectRatio: 'none' });
    // Real stress time-series from PairResult.stress_ts. When absent, render
    // an explicit placeholder rather than a synthetic Gaussian.
    const ts = r.stress_ts || {};
    const times = Array.isArray(ts.times) ? ts.times : [];
    const vals = Array.isArray(ts.max_values) ? ts.max_values : [];
    if (!times.length || times.length !== vals.length) {
      const t = svg('text', {
        x: 100, y: 36, 'text-anchor': 'middle',
        fill: '#5c6383', 'font-size': 9,
      });
      t.appendChild(document.createTextNode('no time-series'));
      s.appendChild(t);
    } else {
      const tMin = times[0], tMax = times[times.length - 1] || tMin + 1;
      const vMax = Math.max.apply(null, vals.map(Math.abs)) || 1;
      const pts = times.map((tv, k) => [
        ((tv - tMin) / (tMax - tMin)) * 200,
        60 - (Math.abs(vals[k]) / vMax) * 50,
      ]);
      s.appendChild(svg('polyline', {
        points: pts.map(p => p.join(',')).join(' '),
        fill: 'none', stroke: '#ff3854', 'stroke-width': 1.4,
      }));
    }
    div.appendChild(s);
    grid.appendChild(div);
  }
}

function renderFindings() {
  const ul = document.getElementById('findings-list');
  while (ul.firstChild) ul.removeChild(ul.firstChild);
  let items = DATA.findings || [];
  if (!items.length) {
    const k = DATA.kpi;
    items = [
      { severity: 'CRITICAL', title: '가장 위험한 셀', detail: k.worst.face + ' (' + k.worst.x.toFixed(1) + ', ' + k.worst.y.toFixed(1) + ') — ' + k.worst.part_name + ' @ ' + fmt(k.worst.g, 0) + ' G', recommendation: '해당 영역에 완충재/보강 구조 검토' },
      { severity: 'WARNING', title: 'Critical pairs', detail: k.n_critical + '개 페어가 임계치 이상으로 응답', recommendation: '다중 페어 영향 부품 우선 보강' },
      { severity: 'INFO', title: 'Energy dissipation', detail: '초기 KE의 ' + k.diss_pct.toFixed(1) + '%만 소산', recommendation: '소산 효율이 낮은 페이스에 완충 패드 추가' }
    ];
  }
  for (const f of items.slice(0, 6)) {
    const color = f.severity === 'CRITICAL' ? 'var(--crit)' : f.severity === 'WARNING' ? 'var(--warn)' : 'var(--accent)';
    const li = el('li', {
      style: { padding: '8px 0', borderBottom: '1px solid var(--line)', display: 'grid', gridTemplateColumns: '12px 1fr', gap: '8px' }
    }, [
      el('span', { style: { color: color, fontWeight: 700 } }, '■'),
      el('div', null, [
        el('div', { style: { color: 'var(--fg)', fontWeight: 600 } }, f.title),
        el('div', { style: { color: 'var(--fg2)', marginTop: '2px' } }, f.detail),
        el('div', { style: { color: 'var(--dim)', marginTop: '3px', fontStyle: 'italic' } }, '→ ' + f.recommendation)
      ])
    ]);
    ul.appendChild(li);
  }
}

function _pickFlow() {
  const flows = DATA.energy_flows || {};
  const keys = Object.keys(flows);
  if (!keys.length) return null;
  return flows[keys[0]];
}

const EG = { canvas: null, ctx: null, playing: false, t_idx: 0, t_max: 100, flow: null, nodes_pos: null };

function _layoutFlow(flow) {
  const depth = flow.depth_map || {};
  const byDepth = {};
  for (const n of flow.nodes) {
    const d = depth[n.id] != null ? depth[n.id] : (n.is_impactor ? 0 : 99);
    (byDepth[d] = byDepth[d] || []).push(n);
  }
  const depths = Object.keys(byDepth).map(Number).sort((a, b) => a - b);
  const pos = {};
  for (const d of depths) {
    const list = byDepth[d];
    if (d === 0) {
      for (const n of list) pos[n.id] = { x: 0, y: 0 };
    } else {
      const R = 70 + d * 70;
      for (let i = 0; i < list.length; i++) {
        const ang = (2 * Math.PI * i) / list.length + d * 0.3;
        pos[list[i].id] = { x: R * Math.cos(ang), y: R * Math.sin(ang) };
      }
    }
  }
  return pos;
}

function initEnergyGraph() {
  const flow = _pickFlow();
  if (!flow) return;
  EG.flow = flow;
  EG.canvas = document.getElementById('eg-canvas');
  if (!EG.canvas) return;
  const dpr = window.devicePixelRatio || 1;
  function resize() {
    const rect = EG.canvas.getBoundingClientRect();
    EG.canvas.width = rect.width * dpr;
    EG.canvas.height = rect.height * dpr;
    EG.ctx = EG.canvas.getContext('2d');
    EG.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  resize();
  window.addEventListener('resize', () => { resize(); renderEG(); });
  EG.t_max = (flow.nodes[0] && flow.nodes[0].t ? flow.nodes[0].t.length : 101) - 1;
  EG.t_idx = 0;
  EG.nodes_pos = _layoutFlow(flow);
  const _eft = DATA.energy_flow_thresholds || { engage_ratio: 0.05, active_ratio: 0.001 };
  for (const e of flow.edges) {
    let idx = -1;
    const thr = Math.max(1, (e.peak_f || 1) * _eft.engage_ratio);
    for (let i = 0; i < e.f.length; i++) if (e.f[i] > thr) { idx = i; break; }
    e.first_engage_idx = idx < 0 ? e.t.length - 1 : idx;
  }
  const scrub = document.getElementById('eg-scrub');
  scrub.max = EG.t_max;
  scrub.value = 0;
  scrub.addEventListener('input', function () { EG.t_idx = +scrub.value; renderEG(); });
  document.getElementById('eg-play').addEventListener('click', function () {
    EG.playing = !EG.playing;
    document.getElementById('eg-play').innerHTML = EG.playing ? '❚❚ PAUSE' : '▶ PLAY';
    if (EG.playing) loopEG();
  });
  document.getElementById('eg-reset').addEventListener('click', function () {
    EG.playing = false;
    EG.t_idx = 0;
    scrub.value = 0;
    document.getElementById('eg-play').innerHTML = '▶ PLAY';
    renderEG();
  });
  EG.canvas.addEventListener('mousemove', function (ev) {
    const rect = EG.canvas.getBoundingClientRect();
    const mx = ev.clientX - rect.left, my = ev.clientY - rect.top;
    const W = EG.canvas.width / (window.devicePixelRatio || 1);
    const H = EG.canvas.height / (window.devicePixelRatio || 1);
    const cx = W / 2, cy = H / 2;
    let hit = null;
    for (const n of flow.nodes) {
      const p = EG.nodes_pos[n.id];
      const x = cx + p.x, y = cy + p.y;
      const r = 8 + Math.min(24, (n.ie[EG.t_idx] || 0) * 0.4);
      if ((mx - x) * (mx - x) + (my - y) * (my - y) <= r * r) { hit = n; break; }
    }
    const side = document.getElementById('eg-side');
    if (hit) {
      while (side.firstChild) side.removeChild(side.firstChild);
      side.appendChild(el('div', { class: 'ttl' }, hit.name));
      side.appendChild(el('div', { class: 'row' }, [el('span', null, 'IE(t)'), el('b', null, fmt(hit.ie[EG.t_idx] || 0, 3))]));
      side.appendChild(el('div', { class: 'row' }, [el('span', null, 'KE(t)'), el('b', null, fmt(hit.ke[EG.t_idx] || 0, 3))]));
      side.appendChild(el('div', { class: 'row' }, [el('span', null, 'depth'), el('b', null, String(flow.depth_map[hit.id] != null ? flow.depth_map[hit.id] : '-'))]));
      side.classList.add('show');
    } else {
      side.classList.remove('show');
    }
  });
  EG.canvas.addEventListener('mouseleave', () => document.getElementById('eg-side').classList.remove('show'));
  renderEG();
}

function loopEG() {
  if (!EG.playing) return;
  EG.t_idx = (EG.t_idx + 1) % (EG.t_max + 1);
  document.getElementById('eg-scrub').value = EG.t_idx;
  renderEG();
  requestAnimationFrame(loopEG);
}

function renderEG() {
  const ctx = EG.ctx;
  if (!ctx) return;
  const W = EG.canvas.width / (window.devicePixelRatio || 1);
  const H = EG.canvas.height / (window.devicePixelRatio || 1);
  ctx.fillStyle = '#1a1e2e';
  ctx.fillRect(0, 0, W, H);
  const cx = W / 2, cy = H / 2;
  const flow = EG.flow;
  const ti = EG.t_idx;
  const t_val = (flow.nodes[0] && flow.nodes[0].t) ? (flow.nodes[0].t[ti] || 0) : 0;
  document.getElementById('eg-t').textContent = (t_val * 1000).toFixed(3);
  ctx.strokeStyle = 'rgba(255,255,255,0.04)';
  for (let d = 1; d <= 3; d++) {
    ctx.beginPath();
    ctx.arc(cx, cy, 70 + d * 70, 0, 2 * Math.PI);
    ctx.stroke();
  }
  let maxImp = 0;
  for (const e of flow.edges) {
    const v = e.imp[ti] || 0;
    if (v > maxImp) maxImp = v;
  }
  const _eft2 = DATA.energy_flow_thresholds || { engage_ratio: 0.05, active_ratio: 0.001 };
  for (const e of flow.edges) {
    const p1 = EG.nodes_pos[e.src], p2 = EG.nodes_pos[e.dst];
    if (!p1 || !p2) continue;
    const x1 = cx + p1.x, y1 = cy + p1.y, x2 = cx + p2.x, y2 = cy + p2.y;
    const imp = e.imp[ti] || 0;
    const active = (e.f[ti] || 0) > _eft2.active_ratio * (e.peak_f || 1);
    const w = 0.4 + 4.5 * (imp / Math.max(1e-9, maxImp));
    ctx.strokeStyle = active ? 'rgba(77,214,255,0.85)' : 'rgba(180,110,255,0.35)';
    ctx.lineWidth = w;
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();
    if (active) {
      const phase = (Date.now() / 350 + e.cid * 0.7) % 1;
      const px = x1 + (x2 - x1) * phase;
      const py = y1 + (y2 - y1) * phase;
      ctx.fillStyle = '#ffffff';
      ctx.beginPath();
      ctx.arc(px, py, 2.4, 0, 2 * Math.PI);
      ctx.fill();
    }
  }
  // Derive per-node radius coefficients from the data: scale so that the
  // node with the largest IE at the final state ends near r ≈ 28.
  let _ieMaxLocal = 0, _keMaxLocal = 0;
  for (const _n of flow.nodes) {
    for (const _v of (_n.ie || [])) if (_v > _ieMaxLocal) _ieMaxLocal = _v;
    if (_n.is_impactor) for (const _v of (_n.ke || [])) if (_v > _keMaxLocal) _keMaxLocal = _v;
  }
  const _ieCoef = _ieMaxLocal > 0 ? (20 / _ieMaxLocal) : 0;
  const _keCoef = _keMaxLocal > 0 ? (8  / _keMaxLocal) : 0;
  const _ieNorm = (DATA.energy_flow_max_ie && DATA.energy_flow_max_ie > 0) ? DATA.energy_flow_max_ie : (_ieMaxLocal || 1);
  for (const n of flow.nodes) {
    const p = EG.nodes_pos[n.id];
    if (!p) continue;
    const x = cx + p.x, y = cy + p.y;
    const ie = n.ie[ti] || 0;
    const ke = n.ke[ti] || 0;
    const r = 8 + Math.min(28, ie * _ieCoef + (n.is_impactor ? ke * _keCoef : 0));
    const t01 = Math.max(0, Math.min(1, ie / _ieNorm));
    ctx.fillStyle = n.is_impactor ? '#b46eff' : gColor(t01);
    ctx.beginPath();
    ctx.arc(x, y, r, 0, 2 * Math.PI);
    ctx.fill();
    const hasActive = flow.edges.some(e => (e.src === n.id || e.dst === n.id) && (e.f[ti] || 0) > _eft2.active_ratio * (e.peak_f || 1));
    if (hasActive) {
      const pulse = 0.6 + 0.4 * Math.sin(Date.now() / 200);
      ctx.strokeStyle = 'rgba(77,214,255,' + pulse + ')';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(x, y, r + 4, 0, 2 * Math.PI);
      ctx.stroke();
    }
    ctx.fillStyle = '#e6ebff';
    ctx.font = '10px "JetBrains Mono", monospace';
    ctx.textAlign = 'center';
    ctx.fillText(n.name, x, y + r + 12);
  }
}

function initSunburst() {
  const flow = _pickFlow();
  const root = document.getElementById('sunburst-svg');
  while (root.firstChild) root.removeChild(root.firstChild);
  if (!flow) return;
  const cx = 180, cy = 170;
  const r0 = 30, r1 = 80, r2 = 130;
  const ke_init = flow.ke_init || 1;
  root.appendChild(svg('circle', { cx: cx, cy: cy, r: r0, fill: '#b46eff' }));
  const lbl1 = svg('text', { x: cx, y: cy - 2, 'text-anchor': 'middle', fill: '#fff', 'font-size': 10, 'font-weight': 700, 'font-family': 'JetBrains Mono' });
  lbl1.appendChild(document.createTextNode('KE0'));
  root.appendChild(lbl1);
  const lbl2 = svg('text', { x: cx, y: cy + 12, 'text-anchor': 'middle', fill: '#fff', 'font-size': 9, 'font-family': 'JetBrains Mono' });
  lbl2.appendChild(document.createTextNode(fmt(ke_init, 1) + ' J'));
  root.appendChild(lbl2);
  const T = (flow.nodes[0] && flow.nodes[0].t ? flow.nodes[0].t.length : 1) - 1;
  const ie_total = flow.nodes.filter(n => !n.is_impactor).reduce((a, n) => a + (n.ie[T] || 0), 0);
  const ke_left = flow.nodes.reduce((a, n) => a + (n.ke[T] || 0), 0);
  const diss = Math.max(0, ke_init - ie_total - ke_left);
  const segs1 = [
    { label: 'IE', val: ie_total, color: '#4dd6ff' },
    { label: 'diss', val: diss, color: '#f0a830' },
    { label: 'KE_n', val: Math.max(0, ke_left), color: '#4adfa1' }
  ];
  let acc = -Math.PI / 2;
  const total1 = segs1.reduce((a, s) => a + s.val, 0) || 1;
  for (const s of segs1) {
    const ang = 2 * Math.PI * s.val / total1;
    if (ang <= 0) { acc += ang; continue; }
    const x1 = cx + r0 * Math.cos(acc), y1 = cy + r0 * Math.sin(acc);
    const x2 = cx + r1 * Math.cos(acc), y2 = cy + r1 * Math.sin(acc);
    const x3 = cx + r1 * Math.cos(acc + ang), y3 = cy + r1 * Math.sin(acc + ang);
    const x4 = cx + r0 * Math.cos(acc + ang), y4 = cy + r0 * Math.sin(acc + ang);
    const large = ang > Math.PI ? 1 : 0;
    const d = 'M' + x1 + ',' + y1 + ' L' + x2 + ',' + y2 + ' A' + r1 + ',' + r1 + ' 0 ' + large + ' 1 ' + x3 + ',' + y3 + ' L' + x4 + ',' + y4 + ' A' + r0 + ',' + r0 + ' 0 ' + large + ' 0 ' + x1 + ',' + y1 + ' Z';
    const path = svg('path', { d: d, fill: s.color, opacity: 0.85, stroke: '#0a0c14', 'stroke-width': 1 });
    const title = svg('title', {});
    title.appendChild(document.createTextNode(s.label + ': ' + fmt(s.val, 2) + ' J (' + (100 * s.val / total1).toFixed(1) + '%)'));
    path.appendChild(title);
    root.appendChild(path);
    const mid = acc + ang / 2;
    const lx = cx + ((r0 + r1) / 2) * Math.cos(mid);
    const ly = cy + ((r0 + r1) / 2) * Math.sin(mid);
    const lab = svg('text', { x: lx, y: ly + 3, 'text-anchor': 'middle', fill: '#0a0c14', 'font-size': 9, 'font-weight': 700, 'font-family': 'JetBrains Mono' });
    lab.appendChild(document.createTextNode(s.label));
    root.appendChild(lab);
    acc += ang;
  }
  const parts = flow.nodes.filter(n => !n.is_impactor);
  const ie_vals = parts.map(p => ({ name: p.name, v: p.ie[T] || 0 }));
  const total2 = ie_vals.reduce((a, p) => a + p.v, 0) || 1;
  acc = -Math.PI / 2;
  for (let i = 0; i < ie_vals.length; i++) {
    const p = ie_vals[i];
    const ang = 2 * Math.PI * p.v / total2;
    if (ang <= 0) { acc += ang; continue; }
    const x1 = cx + r1 * Math.cos(acc), y1 = cy + r1 * Math.sin(acc);
    const x2 = cx + r2 * Math.cos(acc), y2 = cy + r2 * Math.sin(acc);
    const x3 = cx + r2 * Math.cos(acc + ang), y3 = cy + r2 * Math.sin(acc + ang);
    const x4 = cx + r1 * Math.cos(acc + ang), y4 = cy + r1 * Math.sin(acc + ang);
    const large = ang > Math.PI ? 1 : 0;
    const d = 'M' + x1 + ',' + y1 + ' L' + x2 + ',' + y2 + ' A' + r2 + ',' + r2 + ' 0 ' + large + ' 1 ' + x3 + ',' + y3 + ' L' + x4 + ',' + y4 + ' A' + r1 + ',' + r1 + ' 0 ' + large + ' 0 ' + x1 + ',' + y1 + ' Z';
    const t = i / Math.max(1, ie_vals.length - 1);
    const path = svg('path', { d: d, fill: gColor(t), opacity: 0.78, stroke: '#0a0c14', 'stroke-width': 0.8 });
    const title = svg('title', {});
    title.appendChild(document.createTextNode(p.name + ': ' + fmt(p.v, 2) + ' J (' + (100 * p.v / total2).toFixed(1) + '%)'));
    path.appendChild(title);
    root.appendChild(path);
    if (ang > 0.25) {
      const mid = acc + ang / 2;
      const lx = cx + ((r1 + r2) / 2) * Math.cos(mid);
      const ly = cy + ((r1 + r2) / 2) * Math.sin(mid);
      const lab = svg('text', { x: lx, y: ly + 3, 'text-anchor': 'middle', fill: '#0a0c14', 'font-size': 8.5, 'font-weight': 700, 'font-family': 'JetBrains Mono' });
      lab.appendChild(document.createTextNode(p.name.split('\\').pop()));
      root.appendChild(lab);
    }
    acc += ang;
  }
}

function initSankey() {
  const flow = _pickFlow();
  const wrap = document.getElementById('sankey-rows');
  while (wrap.firstChild) wrap.removeChild(wrap.firstChild);
  if (!flow) return;
  const sorted = flow.edges.slice().sort((a, b) => (a.first_engage_idx || 0) - (b.first_engage_idx || 0));
  let maxW = 0; for (const e of sorted) if (e.total_w > maxW) maxW = e.total_w;
  for (const e of sorted) {
    const w = maxW > 0 ? e.total_w / maxW : 0;
    const srcNode = flow.nodes.find(n => n.id === e.src);
    const dstNode = flow.nodes.find(n => n.id === e.dst);
    const srcName = srcNode ? srcNode.name : e.src;
    const dstName = dstNode ? dstNode.name : e.dst;
    const row = el('div', { class: 'sankey-row' }, [
      el('div', { class: 'src' }, srcName),
      el('div', { class: 'bar', style: { width: (4 + w * 96) + '%' } }),
      el('div', { class: 'dst' }, '→ ' + dstName),
      el('div', { class: 'val' }, fmt(e.total_w, 2))
    ]);
    wrap.appendChild(row);
  }
}

function initTimeForceHeatmap() {
  const flow = _pickFlow();
  const wrap = document.getElementById('tfh-rows');
  while (wrap.firstChild) wrap.removeChild(wrap.firstChild);
  if (!flow) return;
  const sorted = flow.edges.slice().sort((a, b) => (a.first_engage_idx || 0) - (b.first_engage_idx || 0));
  let mxF = 0;
  for (const e of flow.edges) for (const v of e.f) if (v > mxF) mxF = v;
  const NBINS = 21;
  for (const e of sorted) {
    const T = e.t.length;
    const row = el('div', { class: 'tfh-row' });
    const srcNode = flow.nodes.find(n => n.id === e.src);
    const dstNode = flow.nodes.find(n => n.id === e.dst);
    const srcName = srcNode ? srcNode.name : e.src;
    const dstName = dstNode ? dstNode.name : e.dst;
    row.appendChild(el('div', { class: 'lab', title: srcName + ' → ' + dstName },
      srcName.split('\\').pop().slice(0, 6) + '→' + dstName.split('\\').pop().slice(0, 6)));
    for (let b = 0; b < NBINS; b++) {
      const i0 = Math.floor(b * T / NBINS);
      const i1 = Math.floor((b + 1) * T / NBINS);
      let m = 0;
      for (let i = i0; i < i1; i++) { if (e.f[i] > m) m = e.f[i]; }
      const tt = (i0 / T * (e.t[T - 1] || 1) * 1000).toFixed(3);
      const cell = el('div', { class: 'cell',
        style: { background: m > 0 ? gColor(m / Math.max(1, mxF)) : 'rgba(255,255,255,0.04)' },
        title: tt + ' ms · |F|=' + fmt(m, 0)
      });
      row.appendChild(cell);
    }
    wrap.appendChild(row);
  }
}

function initConservation() {
  const flow = _pickFlow();
  if (!flow) return;
  const T = (flow.nodes[0] && flow.nodes[0].t ? flow.nodes[0].t.length : 1) - 1;
  const ke_init = flow.ke_init || 0;
  const ie_total = flow.nodes.filter(n => !n.is_impactor).reduce((a, n) => a + (n.ie[T] || 0), 0);
  const ke_left = flow.nodes.reduce((a, n) => a + (n.ke[T] || 0), 0);
  const diss = Math.max(0, ke_init - ie_total - ke_left);
  const residual_pct = ke_init > 0 ? Math.abs(ke_init - ie_total - ke_left - diss) / ke_init * 100 : 0;
  document.getElementById('consKE').textContent = fmt(ke_init, 2);
  document.getElementById('consIE').textContent = fmt(ie_total, 2);
  document.getElementById('consDISS').textContent = fmt(diss, 2);
  document.getElementById('consRES').textContent = residual_pct.toFixed(2) + ' %';
  const bar = document.getElementById('consBar');
  while (bar.firstChild) bar.removeChild(bar.firstChild);
  const total = (ie_total + diss + ke_left) || 1;
  const segs = [
    { v: ie_total, c: '#4dd6ff' },
    { v: diss, c: '#f0a830' },
    { v: ke_left, c: '#4adfa1' }
  ];
  for (const s of segs) bar.appendChild(el('div', { class: 'seg', style: { width: (100 * s.v / total) + '%', background: s.c } }));
  // Conservation-tolerance check: only run when payload provides an explicit
  // tolerance percent. None → no banner (don't silently invent a 5% rule).
  const _tol = DATA.energy_conservation_tolerance;
  const banner = document.getElementById('consBanner');
  if (_tol != null && residual_pct > _tol) {
    if (banner) {
      banner.classList.add('on');
      banner.textContent = '⚠ Residual > ' + _tol + '% — energy conservation suspect';
    }
    document.getElementById('consResCell').classList.add('warn');
  } else if (banner) {
    banner.classList.remove('on');
  }
}

function wireControlBar() {
  document.querySelectorAll('.ctlbar .btn').forEach(btn => {
    btn.addEventListener('click', function () {
      if (btn.dataset.iiFace) {
        STATE.ii.face = btn.dataset.iiFace;
        // clear hover state on face switch
        STATE.ii.hovered_pos = null;
        STATE.ii.selected_part = null;
        document.querySelectorAll('.ctlbar .btn[data-ii-face]').forEach(b => b.classList.toggle('active', b.dataset.iiFace === STATE.ii.face));
        renderInspector();
        renderInfluenceMatrix();
      } else if (btn.dataset.iiMetric) {
        STATE.ii.metric = btn.dataset.iiMetric;
        STATE.metric = STATE.ii.metric;  // keep legacy metric in sync for other panels
        document.querySelectorAll('.ctlbar .btn[data-ii-metric]').forEach(b => b.classList.toggle('active', b.dataset.iiMetric === STATE.ii.metric));
        renderAll();
      } else if (btn.dataset.iiNorm) {
        STATE.ii.norm = btn.dataset.iiNorm;
        document.querySelectorAll('.ctlbar .btn[data-ii-norm]').forEach(b => b.classList.toggle('active', b.dataset.iiNorm === STATE.ii.norm));
        renderInspector();
      }
    });
  });
  const thresh = document.getElementById('ii-thresh');
  if (thresh) thresh.addEventListener('input', function () {
    STATE.ii.thresh = parseInt(thresh.value, 10) || 0;
    renderInspector();
  });
  const pin = document.getElementById('ii-pin');
  if (pin) pin.addEventListener('change', function () {
    STATE.ii.pinned = pin.checked;
    const lab = document.getElementById('ii-pin-lab');
    if (lab) lab.classList.toggle('locked', STATE.ii.pinned);
    if (!STATE.ii.pinned) {
      STATE.ii.hovered_pos = null;
      _renderInspectorClear();
    }
  });
}

function renderAll() {
  renderBiFaceSplit();
  initFaceKpiTable();
  initTopK();
  renderInspector();
  renderInfluenceMatrix();
  renderTSGrid();
  renderVerdict();
}

function initReveal() {
  if (!('IntersectionObserver' in window)) {
    document.querySelectorAll('.r').forEach(n => n.classList.add('in'));
    return;
  }
  const io = new IntersectionObserver(function (entries) {
    for (const e of entries) {
      if (e.isIntersecting) {
        e.target.classList.add('in');
        io.unobserve(e.target);
      }
    }
  }, { rootMargin: '0px 0px -80px 0px' });
  document.querySelectorAll('.r').forEach(n => io.observe(n));
}

function initNav() {
  const navs = document.querySelectorAll('.topbar .nav a');
  navs.forEach(a => a.addEventListener('click', function () {
    const tgt = document.getElementById(a.dataset.target);
    if (tgt) tgt.scrollIntoView({ behavior: 'smooth' });
  }));
  window.addEventListener('scroll', function () {
    const sections = ['s1', 's2', 's3', 's4', 's5'];
    const y = window.scrollY + 120;
    let active = sections[0];
    for (const id of sections) {
      const sec = document.getElementById(id);
      if (sec && sec.offsetTop <= y) active = id;
    }
    navs.forEach(a => a.classList.toggle('active', a.dataset.target === active));
  });
}

/* ===================================================================
 * Trajectory visualisations (6 new panels)
 * =================================================================== */

const TRAJ = DATA.trajectories || {};
const TRAJ_KEYS = Object.keys(TRAJ);
const CLUSTERS = DATA.clusters || { n: 0, labels: {}, archetypes: [] };

// Behavior class palette. `slide` was previously #ff9e64 — visually
// indistinguishable from rebound's orange. Switched to the lateral-motion
// purple so all five classes are unique colors. CSS `.bbadge.slide` is in
// sync.
const BEHAVIOR_COLOR = {
  bounce: '#4adfa1',
  rebound: '#f0a830',
  slide:  '#b46eff',
  embed:  '#ff3854',
  unknown:'#5c6383'
};
const CLUSTER_PALETTE = ['#4dd6ff', '#b46eff', '#f0a830', '#4adfa1', '#ff9e64', '#ff5e84', '#aab2cf'];

function _trajForPos(face, posId) {
  const t = TRAJ[posId];
  if (!t) return null;
  if (face && t.face !== face) return null;
  return t;
}

function _mapXYToVB(x, y, vbW, vbH, padPx) {
  return _xyToVB(x, y, vbW, vbH, padPx);
}

function _drawFaceCanvas(svgRoot, faceCode, drawFn) {
  // Common helpers: draw device bbox + part footprints, then call drawFn(vbW,vbH).
  const vbW = 600, vbH = 360;
  svgRoot.setAttribute('viewBox', '0 0 ' + vbW + ' ' + vbH);
  svgRoot.setAttribute('preserveAspectRatio', 'xMidYMid meet');
  while (svgRoot.firstChild) svgRoot.removeChild(svgRoot.firstChild);
  // background
  svgRoot.appendChild(svg('rect', { x: 0, y: 0, width: vbW, height: vbH, fill: '#0e1320', rx: 4 }));
  const bb = DEVICE_BBOX;
  if (bb) {
    const tl = _mapXYToVB(bb.xmin, bb.ymax, vbW, vbH, 22);
    const br = _mapXYToVB(bb.xmax, bb.ymin, vbW, vbH, 22);
    svgRoot.appendChild(svg('rect', {
      x: tl[0], y: tl[1], width: br[0] - tl[0], height: br[1] - tl[1],
      rx: 4, ry: 4, fill: 'none', stroke: '#3a4055', 'stroke-width': 1,
      'stroke-dasharray': '4,4'
    }));
  }
  for (const p of PARTS) {
    const bbf = _footprintBBox(p.footprint);
    if (!bbf) continue;
    const a = _mapXYToVB(bbf.xmin, bbf.ymax, vbW, vbH, 22);
    const b = _mapXYToVB(bbf.xmax, bbf.ymin, vbW, vbH, 22);
    const w = b[0] - a[0], h = b[1] - a[1];
    if (w < 1 || h < 1) continue;
    svgRoot.appendChild(svg('rect', {
      x: a[0], y: a[1], width: w, height: h, rx: 2, ry: 2,
      fill: 'rgba(170,178,207,0.04)',
      stroke: 'rgba(170,178,207,0.18)',
      'stroke-width': 0.9
    }));
  }
  drawFn(vbW, vbH);
}

/* --- Viz 1: Bounce Vector Map (page 1) ----------------------------- */
function initBounceVectorMap() {
  const grid = document.getElementById('bvm-grid');
  const legend = document.getElementById('bvm-legend');
  if (!grid) return;
  while (grid.firstChild) grid.removeChild(grid.firstChild);
  while (legend.firstChild) legend.removeChild(legend.firstChild);
  if (!TRAJ_KEYS.length) {
    grid.appendChild(el('div', { class: 'traj-na' }, 'Trajectory data unavailable — run with --enable-trajectory'));
    return;
  }
  const targets = [
    { code: 'F2', name: 'FRONT · F2' },
    { code: 'F1', name: 'BACK · F1'  }
  ];
  const totals = { bounce: 0, rebound: 0, slide: 0, embed: 0, unknown: 0 };
  for (const k in TRAJ) totals[TRAJ[k].behavior] = (totals[TRAJ[k].behavior] || 0) + 1;
  for (const t of targets) {
    if (!FACE_BY_CODE[t.code]) continue;
    const cell = el('div', { class: 'bvm-cell' });
    cell.appendChild(el('div', { class: 'bf-head' }, [
      el('div', { class: 'bf-name' }, t.name),
      el('div', { class: 'bf-sub' }, 'bounce vectors')
    ]));
    const s = svg('svg', {});
    cell.appendChild(s);
    grid.appendChild(cell);
    // find rebound mag max for this face
    const keys = TRAJ_KEYS.filter(k => TRAJ[k].face === t.code);
    let maxMag = 0;
    for (const k of keys) if (TRAJ[k].rebound_speed > maxMag) maxMag = TRAJ[k].rebound_speed;
    _drawFaceCanvas(s, t.code, function (vbW, vbH) {
      // arrowhead marker
      const defs = svg('defs', {});
      ['bounce', 'rebound', 'slide', 'embed', 'unknown'].forEach(function (b) {
        const m = svg('marker', { id: 'bvm-' + b + '-' + t.code, viewBox: '0 0 10 10', refX: 8, refY: 5, markerWidth: 5, markerHeight: 5, orient: 'auto' });
        m.appendChild(svg('path', { d: 'M0,0 L10,5 L0,10 Z', fill: BEHAVIOR_COLOR[b] }));
        defs.appendChild(m);
      });
      s.appendChild(defs);
      for (const k of keys) {
        const tr = TRAJ[k];
        const [cx, cy] = _mapXYToVB(tr.x, tr.y, vbW, vbH, 22);
        const c = BEHAVIOR_COLOR[tr.behavior] || BEHAVIOR_COLOR.unknown;
        // tail dot
        s.appendChild(svg('circle', { cx: cx, cy: cy, r: 3, fill: c, opacity: 0.9 }));
        // arrow line — length scaled
        const mag = maxMag > 0 ? Math.min(1, tr.rebound_speed / maxMag) : 0;
        const L = 8 + 40 * mag;
        const rx = tr.rebound_xy[0], ry = tr.rebound_xy[1];
        const r2 = Math.hypot(rx, ry) || 1;
        // SVG y is inverted — flip ry
        const dx = L * (rx / r2), dy = -L * (ry / r2);
        if (tr.behavior !== 'embed' && L > 4) {
          const line = svg('line', {
            x1: cx, y1: cy, x2: cx + dx, y2: cy + dy,
            stroke: c, 'stroke-width': 1.4 + mag * 1.6, opacity: 0.85,
            'marker-end': 'url(#bvm-' + tr.behavior + '-' + t.code + ')'
          });
          const ttl = svg('title', {});
          ttl.appendChild(document.createTextNode(tr.behavior.toUpperCase() + ' · ' + k + '\nrebound = ' + fmt(tr.rebound_speed, 0) + (_u('vel') ? ' ' + _u('vel') : '') + '\nKE retention = ' + (tr.ke_retention * 100).toFixed(0) + '%\nmax pen = ' + fmt(tr.max_pen, 2) + (_u('disp') ? ' ' + _u('disp') : '')));
          line.appendChild(ttl);
          s.appendChild(line);
        } else if (tr.behavior === 'embed') {
          // cross marker for embed
          s.appendChild(svg('circle', { cx: cx, cy: cy, r: 6, fill: 'none', stroke: c, 'stroke-width': 1.5 }));
        }
      }
    });
    grid.appendChild(cell);
  }
  // legend
  const order = ['bounce', 'rebound', 'slide', 'embed'];
  for (const b of order) {
    legend.appendChild(el('div', { class: 'lg' }, [
      el('span', { class: 'sw', style: { background: BEHAVIOR_COLOR[b] } }),
      el('span', null, b.toUpperCase()),
      el('b', null, String(totals[b] || 0))
    ]));
  }
  if (totals.unknown) {
    legend.appendChild(el('div', { class: 'lg' }, [
      el('span', { class: 'sw', style: { background: BEHAVIOR_COLOR.unknown } }),
      el('span', null, 'UNKNOWN'),
      el('b', null, String(totals.unknown))
    ]));
  }
  if (DATA.trajectories && Object.values(DATA.trajectories).some(t => t._mock)) {
    legend.appendChild(el('div', { class: 'lg', style: { color: 'var(--tag)', marginLeft: 'auto' } }, [
      el('span', null, '(mock — sibling pipeline not wired yet)')
    ]));
  }
}

/* --- Viz 5: Trajectory Clustering Map (page 1) --------------------- */
function initTrajectoryClustering() {
  const grid = document.getElementById('tcm-grid');
  const arch = document.getElementById('tcm-archetypes');
  if (!grid) return;
  while (grid.firstChild) grid.removeChild(grid.firstChild);
  while (arch.firstChild) arch.removeChild(arch.firstChild);
  if (!TRAJ_KEYS.length || CLUSTERS.n <= 0) {
    grid.appendChild(el('div', { class: 'traj-na' }, 'Trajectory data unavailable.'));
    return;
  }
  const targets = [
    { code: 'F2', name: 'FRONT · F2' },
    { code: 'F1', name: 'BACK · F1'  }
  ];
  for (const t of targets) {
    if (!FACE_BY_CODE[t.code]) continue;
    const cell = el('div', { class: 'bvm-cell' });
    cell.appendChild(el('div', { class: 'bf-head' }, [
      el('div', { class: 'bf-name' }, t.name),
      el('div', { class: 'bf-sub' }, CLUSTERS.n + ' clusters')
    ]));
    const s = svg('svg', {});
    cell.appendChild(s);
    grid.appendChild(cell);
    _drawFaceCanvas(s, t.code, function (vbW, vbH) {
      const faceKeys = TRAJ_KEYS.filter(k => TRAJ[k].face === t.code);
      for (const k of faceKeys) {
        const tr = TRAJ[k];
        const lab = (CLUSTERS.labels[k] != null) ? CLUSTERS.labels[k] : -1;
        const c = (lab >= 0) ? CLUSTER_PALETTE[lab % CLUSTER_PALETTE.length] : '#5c6383';
        const [cx, cy] = _mapXYToVB(tr.x, tr.y, vbW, vbH, 22);
        const dot = svg('circle', {
          cx: cx, cy: cy, r: 5, fill: c, 'fill-opacity': 0.85,
          stroke: 'rgba(10,12,20,0.9)', 'stroke-width': 0.8,
          'data-tcm-cluster': lab, 'data-tcm-key': k
        });
        const ttl = svg('title', {});
        const archName = CLUSTERS.archetypes[lab] || ('cluster ' + lab);
        ttl.appendChild(document.createTextNode(k + '\nCLUSTER: ' + archName + '\nbehavior: ' + tr.behavior + '\nKE retention: ' + (tr.ke_retention * 100).toFixed(0) + '%'));
        dot.appendChild(ttl);
        dot.style.cursor = 'pointer';
        dot.addEventListener('mouseenter', function () {
          document.querySelectorAll('[data-tcm-cluster]').forEach(function (n) {
            n.setAttribute('fill-opacity', n.getAttribute('data-tcm-cluster') === String(lab) ? '1.0' : '0.18');
          });
        });
        dot.addEventListener('mouseleave', function () {
          document.querySelectorAll('[data-tcm-cluster]').forEach(function (n) {
            n.setAttribute('fill-opacity', '0.85');
          });
        });
        s.appendChild(dot);
      }
    });
  }
  // Archetype gallery
  const memberCount = {};
  for (const k in CLUSTERS.labels) {
    const lab = CLUSTERS.labels[k];
    memberCount[lab] = (memberCount[lab] || 0) + 1;
  }
  for (let i = 0; i < CLUSTERS.n; i++) {
    const archName = CLUSTERS.archetypes[i] || ('cluster ' + i);
    const col = CLUSTER_PALETTE[i % CLUSTER_PALETTE.length];
    const card = el('div', { class: 'tcm-arch', style: { borderLeft: '3px solid ' + col } });
    card.appendChild(el('div', { class: 'ah' }, [
      el('span', { class: 'nm', style: { color: col } }, archName.toUpperCase()),
      el('span', { class: 'ct' }, 'n=' + (memberCount[i] || 0))
    ]));
    // average KE decay sparkline for cluster
    const memberKeys = Object.keys(CLUSTERS.labels).filter(k => CLUSTERS.labels[k] === i);
    const s = svg('svg', { viewBox: '0 0 200 40', preserveAspectRatio: 'none' });
    if (memberKeys.length > 0) {
      const T = TRAJ[memberKeys[0]].ke.length;
      const avgKe = new Array(T).fill(0);
      let n = 0;
      for (const k of memberKeys) {
        const ts = TRAJ[k].ke;
        if (!ts || ts.length !== T) continue;
        for (let j = 0; j < T; j++) avgKe[j] += ts[j];
        n++;
      }
      if (n > 0) {
        const mx = Math.max(...avgKe) / n || 1;
        const pts = [];
        for (let j = 0; j < T; j++) {
          const x = j / (T - 1) * 200;
          const y = 40 - (avgKe[j] / n / mx) * 36 - 2;
          pts.push(x.toFixed(1) + ',' + y.toFixed(1));
        }
        s.appendChild(svg('polyline', { points: pts.join(' '), fill: 'none', stroke: col, 'stroke-width': 1.4 }));
      }
    }
    card.appendChild(s);
    arch.appendChild(card);
  }
}

/* --- Viz 2: Phase Diagram (page 3) --------------------------------- */
function initPhaseDiagram() {
  const root = document.getElementById('phase-svg');
  const legend = document.getElementById('phase-legend');
  if (!root) return;
  while (root.firstChild) root.removeChild(root.firstChild);
  while (legend.firstChild) legend.removeChild(legend.firstChild);
  if (!TRAJ_KEYS.length) {
    root.appendChild(svg('text', { x: 300, y: 180, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 12 }, [document.createTextNode('Trajectory data unavailable')]));
    return;
  }
  const W = 720, H = 380;
  root.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
  const pad = { l: 50, r: 16, t: 12, b: 30 };
  const plotW = W - pad.l - pad.r, plotH = H - pad.t - pad.b;
  // determine domain
  let keMax = 0, ieMax = 0;
  for (const k of TRAJ_KEYS) {
    const t = TRAJ[k];
    for (const v of t.ke) if (v > keMax) keMax = v;
    const ie = (t.init_ke - t.final_ke);
    if (ie > ieMax) ieMax = ie;
  }
  if (keMax <= 0) keMax = 1;
  if (ieMax <= 0) ieMax = keMax;
  const xMax = Math.max(ieMax, keMax * 1.05);
  function px(ie) { return pad.l + (ie / xMax) * plotW; }
  function py(ke) { return pad.t + (1 - ke / keMax) * plotH; }
  // grid
  for (let g = 0; g <= 4; g++) {
    const yv = keMax * g / 4;
    const yp = py(yv);
    root.appendChild(svg('line', { x1: pad.l, y1: yp, x2: pad.l + plotW, y2: yp, stroke: 'rgba(255,255,255,0.06)', 'stroke-width': 0.5 }));
    const t = svg('text', { x: pad.l - 6, y: yp + 3, 'text-anchor': 'end', fill: '#5c6383', 'font-size': 9, 'font-family': 'JetBrains Mono' });
    t.appendChild(document.createTextNode(yv.toFixed(1)));
    root.appendChild(t);
    const xv = xMax * g / 4;
    const xp = px(xv);
    root.appendChild(svg('line', { x1: xp, y1: pad.t, x2: xp, y2: pad.t + plotH, stroke: 'rgba(255,255,255,0.06)', 'stroke-width': 0.5 }));
    const t2 = svg('text', { x: xp, y: pad.t + plotH + 14, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 9, 'font-family': 'JetBrains Mono' });
    t2.appendChild(document.createTextNode(xv.toFixed(1)));
    root.appendChild(t2);
  }
  // axis labels
  const lblY = svg('text', { x: 14, y: pad.t + plotH / 2, transform: 'rotate(-90 14,' + (pad.t + plotH / 2) + ')', 'text-anchor': 'middle', fill: '#aab2cf', 'font-size': 10, 'font-family': 'JetBrains Mono' });
  lblY.appendChild(document.createTextNode('KE impactor' + _uSuffix('energy')));
  root.appendChild(lblY);
  const lblX = svg('text', { x: pad.l + plotW / 2, y: H - 6, 'text-anchor': 'middle', fill: '#aab2cf', 'font-size': 10, 'font-family': 'JetBrains Mono' });
  lblX.appendChild(document.createTextNode('IE absorbed (= KE₀ − KE)' + _uSuffix('energy')));
  root.appendChild(lblX);
  // budget line: KE + IE <= KE0 → curve from (0,KE0) to (KE0,0)
  // approximate ke0 = max init_ke
  let ke0 = 0;
  for (const k of TRAJ_KEYS) if (TRAJ[k].init_ke > ke0) ke0 = TRAJ[k].init_ke;
  root.appendChild(svg('line', { x1: px(0), y1: py(ke0), x2: px(ke0), y2: py(0), stroke: 'rgba(180,110,255,0.55)', 'stroke-width': 1.2, 'stroke-dasharray': '4,3' }));
  const lblBudget = svg('text', { x: px(ke0 * 0.5), y: py(ke0 * 0.55), fill: '#b46eff', 'font-size': 9, 'font-family': 'JetBrains Mono' });
  lblBudget.appendChild(document.createTextNode('budget: KE+IE = KE₀'));
  root.appendChild(lblBudget);
  // each trajectory as polyline
  for (const k of TRAJ_KEYS) {
    const t = TRAJ[k];
    const c = BEHAVIOR_COLOR[t.behavior] || BEHAVIOR_COLOR.unknown;
    const pts = [];
    for (let i = 0; i < t.ke.length; i++) {
      const ie = t.init_ke - t.ke[i];
      pts.push(px(Math.max(0, ie)).toFixed(1) + ',' + py(t.ke[i]).toFixed(1));
    }
    const pline = svg('polyline', {
      points: pts.join(' '), fill: 'none', stroke: c,
      'stroke-width': 1.0, opacity: 0.55, 'data-phase-key': k
    });
    root.appendChild(pline);
    // final state scatter point
    const last = t.ke.length - 1;
    const dot = svg('circle', {
      cx: px(t.init_ke - t.ke[last]), cy: py(t.ke[last]),
      r: 2.5, fill: c, opacity: 0.9
    });
    const ttl = svg('title', {});
    ttl.appendChild(document.createTextNode(k + ' · ' + t.behavior + '\nKE final = ' + fmt(t.ke[last], 2) + (_u('energy') ? ' ' + _u('energy') : '') + '\nIE = ' + fmt(t.init_ke - t.ke[last], 2)));
    dot.appendChild(ttl);
    root.appendChild(dot);
  }
  // time annotations: show small ticks at t=0.1,0.3,0.5,1.0 ms on the pinned/first trajectory
  const ref = TRAJ[TRAJ_KEYS[0]];
  if (ref) {
    [0.1e-3, 0.3e-3, 0.5e-3, 1.0e-3].forEach(function (ts) {
      let idx = 0, best = Infinity;
      for (let i = 0; i < ref.t.length; i++) {
        const d = Math.abs(ref.t[i] - ts);
        if (d < best) { best = d; idx = i; }
      }
      const ie = ref.init_ke - ref.ke[idx];
      const xp = px(Math.max(0, ie)), yp = py(ref.ke[idx]);
      root.appendChild(svg('circle', { cx: xp, cy: yp, r: 2, fill: '#fff', opacity: 0.85 }));
      const lab = svg('text', { x: xp + 4, y: yp - 4, fill: '#fff', 'font-size': 8, 'font-family': 'JetBrains Mono' });
      lab.appendChild(document.createTextNode((ts * 1000).toFixed(1) + ' ms'));
      root.appendChild(lab);
    });
  }
  // legend
  ['bounce', 'rebound', 'slide', 'embed'].forEach(function (b) {
    legend.appendChild(el('div', { class: 'lg' }, [
      el('span', { class: 'sw', style: { background: BEHAVIOR_COLOR[b] } }),
      el('span', null, b.toUpperCase())
    ]));
  });
}

/* --- Viz 3: Contact Sequence Timeline (page 3) --------------------- */
function initContactTimeline() {
  const grid = document.getElementById('cseq-grid');
  if (!grid) return;
  while (grid.firstChild) grid.removeChild(grid.firstChild);
  if (!TRAJ_KEYS.length) {
    grid.appendChild(el('div', { class: 'traj-na', style: { gridColumn: 'span 2' } }, 'Trajectory data unavailable.'));
    return;
  }
  // top-8 worst by impact peak G (use FACE_POS_MAX)
  const ranked = [];
  for (const k of TRAJ_KEYS) {
    const t = TRAJ[k];
    const posKey = t.face + '|' + k;
    const ent = FACE_POS_MAX[posKey];
    ranked.push({ key: k, traj: t, g: ent ? ent.g : 0 });
  }
  ranked.sort((a, b) => b.g - a.g);
  const top = ranked.slice(0, 8);
  // header
  grid.appendChild(el('div', { class: 'lab', style: { color: 'var(--dim)' } }, 'IMPACT'));
  const head = el('div', { class: 'cseq-row', style: { fontSize: '8px', color: 'var(--dim)', fontFamily: 'JetBrains Mono, monospace' } });
  for (let i = 0; i < 21; i++) {
    head.appendChild(el('div', { style: { textAlign: 'center' } }, (i % 5 === 0) ? (i / 20).toFixed(1) : ''));
  }
  grid.appendChild(head);
  for (const it of top) {
    const tr = it.traj;
    const c = BEHAVIOR_COLOR[tr.behavior] || BEHAVIOR_COLOR.unknown;
    const lab = el('div', { class: 'lab', title: it.key });
    lab.appendChild(el('span', { style: { color: c, fontWeight: 700 } }, '■ '));
    lab.appendChild(document.createTextNode(tr.face + ' · ' + tr.x.toFixed(0) + ',' + tr.y.toFixed(0)));
    grid.appendChild(lab);
    const row = el('div', { class: 'cseq-row' });
    const T = tr.contact ? tr.contact.length : 0;
    for (let i = 0; i < 21; i++) {
      const idx = T > 0 ? Math.floor(i * (T - 1) / 20) : -1;
      const engaged = idx >= 0 && tr.contact[idx];
      // intensity: based on KE drop rate at this index
      let intensity = 0;
      if (engaged && idx > 0) {
        const dk = (tr.ke[idx - 1] - tr.ke[idx]) / Math.max(1e-6, tr.init_ke);
        intensity = Math.min(1, Math.max(0, dk * 25));
      }
      let cellColor;
      if (!engaged) {
        cellColor = 'rgba(255,255,255,0.04)';
      } else {
        const base = c;
        // blend with intensity
        const m = base.match(/#([0-9a-f]{6})/i);
        if (m) {
          const r = parseInt(m[1].slice(0, 2), 16);
          const g = parseInt(m[1].slice(2, 4), 16);
          const b = parseInt(m[1].slice(4, 6), 16);
          const alpha = 0.35 + 0.55 * intensity;
          cellColor = 'rgba(' + r + ',' + g + ',' + b + ',' + alpha.toFixed(2) + ')';
        } else {
          cellColor = c;
        }
      }
      const cell = el('div', { class: 'cseq-cell', style: { background: cellColor } });
      cell.title = it.key + ' · t=' + (i / 20).toFixed(2) + ' ms · ' + (engaged ? 'CONTACT' : 'free flight');
      row.appendChild(cell);
    }
    grid.appendChild(row);
  }
}

/* --- Viz 4: Trajectory Bundle 3D (page 3, 3 projections) ----------- */
function initTrajectoryBundle3D() {
  const xz = document.getElementById('tb3-xz');
  const yz = document.getElementById('tb3-yz');
  const xy = document.getElementById('tb3-xy');
  if (!xz || !yz || !xy) return;
  [xz, yz, xy].forEach(function (s) { while (s.firstChild) s.removeChild(s.firstChild); });
  if (!TRAJ_KEYS.length) {
    [xz, yz, xy].forEach(function (s) {
      s.setAttribute('viewBox', '0 0 200 100');
      const t = svg('text', { x: 100, y: 50, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 10 });
      t.appendChild(document.createTextNode('No trajectory'));
      s.appendChild(t);
    });
    return;
  }
  // determine z range
  let zmin = Infinity, zmax = -Infinity;
  for (const k of TRAJ_KEYS) {
    for (const p of TRAJ[k].pos) {
      if (p[2] < zmin) zmin = p[2];
      if (p[2] > zmax) zmax = p[2];
    }
  }
  if (!isFinite(zmin)) zmin = -5;
  if (!isFinite(zmax)) zmax = 15;
  if (zmin === zmax) { zmin -= 1; zmax += 1; }
  const bb = DEVICE_BBOX;
  if (!bb) {
    [xz, yz, xy].forEach(function (s) {
      s.setAttribute('viewBox', '0 0 200 100');
      const t = svg('text', { x: 100, y: 50, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 10 });
      t.appendChild(document.createTextNode('no device layout'));
      s.appendChild(t);
    });
    return;
  }
  // XZ projection
  function drawSideXZ(root) {
    const W = 360, H = 220;
    root.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
    root.appendChild(svg('rect', { x: 0, y: 0, width: W, height: H, fill: '#0e1320', rx: 4 }));
    const pad = { l: 26, r: 8, t: 10, b: 22 };
    const plotW = W - pad.l - pad.r, plotH = H - pad.t - pad.b;
    const xMin = bb.xmin, xMax = bb.xmax;
    function px(x) { return pad.l + (x - xMin) / (xMax - xMin) * plotW; }
    function py(z) { return pad.t + (1 - (z - zmin) / (zmax - zmin)) * plotH; }
    // z=0 line + bbox
    root.appendChild(svg('line', { x1: px(xMin), y1: py(0), x2: px(xMax), y2: py(0), stroke: 'rgba(255,255,255,0.16)', 'stroke-width': 0.8, 'stroke-dasharray': '4,3' }));
    const lab = svg('text', { x: pad.l - 2, y: py(0) + 3, 'text-anchor': 'end', fill: 'rgba(255,255,255,0.5)', 'font-size': 8, 'font-family': 'JetBrains Mono' });
    lab.appendChild(document.createTextNode('z=0')); root.appendChild(lab);
    // axes labels
    ['xmin', 'xmax'].forEach(function (k, i) {
      const xv = bb[k];
      const t = svg('text', { x: i === 0 ? pad.l : pad.l + plotW, y: H - 6, 'text-anchor': i === 0 ? 'start' : 'end', fill: '#5c6383', 'font-size': 8, 'font-family': 'JetBrains Mono' });
      t.appendChild(document.createTextNode('x=' + xv.toFixed(0))); root.appendChild(t);
    });
    const zlt = svg('text', { x: 4, y: pad.t + 6, fill: '#5c6383', 'font-size': 8, 'font-family': 'JetBrains Mono' });
    zlt.appendChild(document.createTextNode('z=' + zmax.toFixed(0))); root.appendChild(zlt);
    const zlb = svg('text', { x: 4, y: pad.t + plotH, fill: '#5c6383', 'font-size': 8, 'font-family': 'JetBrains Mono' });
    zlb.appendChild(document.createTextNode('z=' + zmin.toFixed(0))); root.appendChild(zlb);
    for (const k of TRAJ_KEYS) {
      const tr = TRAJ[k];
      const c = (tr.face === 'F1') ? '#b46eff' : '#4dd6ff';
      const pts = tr.pos.map(p => px(p[0]).toFixed(1) + ',' + py(p[2]).toFixed(1)).join(' ');
      root.appendChild(svg('polyline', { points: pts, fill: 'none', stroke: c, 'stroke-width': 0.8, opacity: 0.55 }));
    }
  }
  function drawSideYZ(root) {
    const W = 360, H = 220;
    root.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
    root.appendChild(svg('rect', { x: 0, y: 0, width: W, height: H, fill: '#0e1320', rx: 4 }));
    const pad = { l: 26, r: 8, t: 10, b: 22 };
    const plotW = W - pad.l - pad.r, plotH = H - pad.t - pad.b;
    const yMin = bb.ymin, yMax = bb.ymax;
    function px(y) { return pad.l + (y - yMin) / (yMax - yMin) * plotW; }
    function py(z) { return pad.t + (1 - (z - zmin) / (zmax - zmin)) * plotH; }
    root.appendChild(svg('line', { x1: px(yMin), y1: py(0), x2: px(yMax), y2: py(0), stroke: 'rgba(255,255,255,0.16)', 'stroke-width': 0.8, 'stroke-dasharray': '4,3' }));
    const lab = svg('text', { x: pad.l - 2, y: py(0) + 3, 'text-anchor': 'end', fill: 'rgba(255,255,255,0.5)', 'font-size': 8, 'font-family': 'JetBrains Mono' });
    lab.appendChild(document.createTextNode('z=0')); root.appendChild(lab);
    ['ymin', 'ymax'].forEach(function (k, i) {
      const yv = bb[k];
      const t = svg('text', { x: i === 0 ? pad.l : pad.l + plotW, y: H - 6, 'text-anchor': i === 0 ? 'start' : 'end', fill: '#5c6383', 'font-size': 8, 'font-family': 'JetBrains Mono' });
      t.appendChild(document.createTextNode('y=' + yv.toFixed(0))); root.appendChild(t);
    });
    for (const k of TRAJ_KEYS) {
      const tr = TRAJ[k];
      const c = (tr.face === 'F1') ? '#b46eff' : '#4dd6ff';
      const pts = tr.pos.map(p => px(p[1]).toFixed(1) + ',' + py(p[2]).toFixed(1)).join(' ');
      root.appendChild(svg('polyline', { points: pts, fill: 'none', stroke: c, 'stroke-width': 0.8, opacity: 0.55 }));
    }
  }
  function drawTopXY(root) {
    const W = 360, H = 220;
    root.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
    root.appendChild(svg('rect', { x: 0, y: 0, width: W, height: H, fill: '#0e1320', rx: 4 }));
    const pad = { l: 26, r: 8, t: 10, b: 22 };
    const plotW = W - pad.l - pad.r, plotH = H - pad.t - pad.b;
    const xMin = bb.xmin, xMax = bb.xmax;
    const yMin = bb.ymin, yMax = bb.ymax;
    function px(x) { return pad.l + (x - xMin) / (xMax - xMin) * plotW; }
    function py(y) { return pad.t + (1 - (y - yMin) / (yMax - yMin)) * plotH; }
    // device bbox dashed
    root.appendChild(svg('rect', { x: px(xMin), y: py(yMax), width: plotW, height: plotH, fill: 'none', stroke: '#3a4055', 'stroke-width': 0.9, 'stroke-dasharray': '4,3' }));
    for (const k of TRAJ_KEYS) {
      const tr = TRAJ[k];
      const c = BEHAVIOR_COLOR[tr.behavior] || BEHAVIOR_COLOR.unknown;
      const pts = tr.pos.map(p => px(p[0]).toFixed(1) + ',' + py(p[1]).toFixed(1)).join(' ');
      root.appendChild(svg('polyline', { points: pts, fill: 'none', stroke: c, 'stroke-width': 0.9, opacity: 0.55 }));
      // initial dot
      const p0 = tr.pos[0];
      root.appendChild(svg('circle', { cx: px(p0[0]), cy: py(p0[1]), r: 2, fill: c, opacity: 0.9 }));
    }
  }
  drawSideXZ(xz);
  drawSideYZ(yz);
  drawTopXY(xy);
}

/* --- Viz 6: Inspector KE overlay + behavior badge (page 2 enhance) - */
function renderInspectorBehaviorBadge(rec) {
  const badge = document.getElementById('ii-behavior-badge');
  if (!badge) return;
  badge.innerHTML = '';
  if (!rec) return;
  const tr = TRAJ[rec.pos_id];
  if (!tr) return;
  const b = tr.behavior || 'unknown';
  badge.appendChild(el('span', { class: 'bbadge ' + b }, b.toUpperCase()));
}

function renderInspectorKEOverlay(rec) {
  const root = document.getElementById('ii-th-svg');
  const sub = document.getElementById('ii-th-sub');
  const kpi = document.getElementById('ii-traj-kpi');
  if (!root) return;
  while (root.firstChild) root.removeChild(root.firstChild);
  if (kpi) kpi.innerHTML = '';
  if (!rec) return;
  const tr = TRAJ[rec.pos_id];
  if (!tr) {
    if (sub) sub.textContent = '(no trajectory)';
    return;
  }
  if (sub) sub.textContent = '(behavior: ' + tr.behavior + ')';
  const W = 200, H = 70;
  const pad = { l: 4, r: 4, t: 4, b: 6 };
  const plotW = W - pad.l - pad.r, plotH = H - pad.t - pad.b;
  const T = tr.ke.length;
  if (!T) return;
  let mx = 0;
  for (const v of tr.ke) if (v > mx) mx = v;
  if (mx <= 0) mx = 1;
  // shade contact bands
  let inBand = false, bandStart = 0;
  for (let i = 0; i < T; i++) {
    const eng = tr.contact[i];
    if (eng && !inBand) { inBand = true; bandStart = i; }
    if ((!eng || i === T - 1) && inBand) {
      const end = eng && i === T - 1 ? i : i;
      const x0 = pad.l + (bandStart / (T - 1)) * plotW;
      const x1 = pad.l + (end / (T - 1)) * plotW;
      root.appendChild(svg('rect', {
        x: x0, y: pad.t, width: Math.max(1, x1 - x0), height: plotH,
        fill: 'rgba(180,110,255,0.15)'
      }));
      inBand = false;
    }
  }
  // initial KE line
  const yInit = pad.t + (1 - tr.init_ke / mx) * plotH;
  root.appendChild(svg('line', { x1: pad.l, y1: yInit, x2: pad.l + plotW, y2: yInit, stroke: 'rgba(77,214,255,0.45)', 'stroke-width': 0.6, 'stroke-dasharray': '3,2' }));
  // final KE line
  const yFin = pad.t + (1 - tr.final_ke / mx) * plotH;
  root.appendChild(svg('line', { x1: pad.l, y1: yFin, x2: pad.l + plotW, y2: yFin, stroke: 'rgba(74,223,161,0.55)', 'stroke-width': 0.6, 'stroke-dasharray': '3,2' }));
  // KE curve
  const c = BEHAVIOR_COLOR[tr.behavior] || BEHAVIOR_COLOR.unknown;
  const pts = [];
  for (let i = 0; i < T; i++) {
    const xp = pad.l + (i / (T - 1)) * plotW;
    const yp = pad.t + (1 - tr.ke[i] / mx) * plotH;
    pts.push(xp.toFixed(1) + ',' + yp.toFixed(1));
  }
  root.appendChild(svg('polyline', { points: pts.join(' '), fill: 'none', stroke: c, 'stroke-width': 1.6 }));
  // numeric KPIs
  if (kpi) {
    const rows = [
      ['REBOUND', fmt(tr.rebound_speed, 0) + (_u('vel') ? ' ' + _u('vel') : '')],
      ['MAX PEN', fmt(tr.max_pen, 2) + (_u('disp') ? ' ' + _u('disp') : '')],
      ['t₁ CONTACT', (tr.t_first_contact != null ? (tr.t_first_contact * 1000).toFixed(2) + (_u('time') ? ' ' + _u('time') : '') : '-')],
      ['KE RETAIN', (tr.ke_retention * 100).toFixed(0) + ' %']
    ];
    for (const r of rows) {
      kpi.appendChild(el('div', { class: 'iirow' }, [el('span', null, r[0]), el('b', null, r[1])]));
    }
  }
}

/* --- Page 4: Per-Part Peak G (bar + line + table) ------------------ */
const PPG_PALETTE = [
  '#4dd6ff', '#b46eff', '#f0a830', '#4adfa1', '#ff9eb9',
  '#c8d4ff', '#7a9cff', '#ffd34d', '#6fe2cd', '#ff8a5b',
  '#a0e34a', '#e066d4', '#5cb0ff', '#ffcf66'
];

function initPerPartPeakG() {
  const pm = DATA.part_motion || { summary: [], series: [], impactor_part_id: null, t_first_contact: null, g_mm_s2: 9810.0 };
  const summary = pm.summary || [];
  const series = pm.series || [];
  const empty = document.getElementById('ppg-empty');
  const content = document.getElementById('ppg-content');
  const hasData = summary.some(r => (r.peak_g || 0) > 0) || series.length > 0;
  if (!hasData) {
    if (empty) empty.style.display = 'block';
    if (content) content.style.display = 'none';
    return;
  }
  if (empty) empty.style.display = 'none';

  const impactorPid = pm.impactor_part_id;
  const G = pm.g_mm_s2 || 9810.0;

  // ----- Bar chart -----
  const barSvg = document.getElementById('ppg-bar-svg');
  if (barSvg) {
    while (barSvg.firstChild) barSvg.removeChild(barSvg.firstChild);
    const sorted = summary.filter(r => (r.peak_g || 0) > 0).slice();
    sorted.sort((a, b) => b.peak_g - a.peak_g);
    const n = sorted.length;
    const W = 720, rowH = 22, padTop = 14, padBot = 24, padL = 180, padR = 60;
    const H = Math.max(80, padTop + padBot + n * rowH);
    barSvg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
    barSvg.style.height = Math.max(120, Math.min(520, H)) + 'px';
    const maxG = sorted.length ? sorted[0].peak_g : 1;
    const plotW = W - padL - padR;
    // axis line
    barSvg.appendChild(svg('line', { x1: padL, y1: padTop, x2: padL, y2: H - padBot, stroke: 'rgba(255,255,255,0.18)', 'stroke-width': 0.8 }));
    barSvg.appendChild(svg('line', { x1: padL, y1: H - padBot, x2: W - padR, y2: H - padBot, stroke: 'rgba(255,255,255,0.18)', 'stroke-width': 0.8 }));
    // ticks (0, 25%, 50%, 75%, 100%)
    for (let i = 0; i <= 4; i++) {
      const xp = padL + (i / 4) * plotW;
      barSvg.appendChild(svg('line', { x1: xp, y1: H - padBot, x2: xp, y2: H - padBot + 4, stroke: 'rgba(255,255,255,0.30)', 'stroke-width': 0.6 }));
      const t = svg('text', { x: xp, y: H - padBot + 14, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 9, 'font-family': 'JetBrains Mono' });
      t.appendChild(document.createTextNode(fmt(maxG * i / 4, 0)));
      barSvg.appendChild(t);
    }
    // axis label
    const axLab = svg('text', { x: padL + plotW / 2, y: H - 4, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 9 });
    axLab.appendChild(document.createTextNode('Peak |a|' + (_u('acc') ? '  (' + _u('acc') + ')' : '')));
    barSvg.appendChild(axLab);
    // rows
    for (let i = 0; i < n; i++) {
      const row = sorted[i];
      const y = padTop + i * rowH + 4;
      const bw = (row.peak_g / maxG) * plotW;
      const isImp = row.is_impactor || (impactorPid != null && row.part_id === impactorPid);
      const color = isImp ? '#ff5e84' : '#4dd6ff';
      // label (part_id + name)
      const lab = svg('text', { x: padL - 6, y: y + 11, 'text-anchor': 'end', fill: isImp ? '#ff9eb9' : '#aab2cf', 'font-size': 10, 'font-family': 'Inter' });
      const labStr = String(row.part_id) + (row.part_name ? '  ' + row.part_name : '');
      const labShort = labStr.length > 26 ? labStr.slice(0, 24) + '…' : labStr;
      lab.appendChild(document.createTextNode(labShort));
      if (isImp) {
        const star = svg('tspan', { fill: '#ff5e84', 'font-weight': 700 });
        star.appendChild(document.createTextNode('  ◆'));
        lab.appendChild(star);
      }
      const ttl = svg('title', {});
      ttl.appendChild(document.createTextNode(labStr + (isImp ? '  (impactor)' : '')));
      lab.appendChild(ttl);
      barSvg.appendChild(lab);
      // bar
      const rect = svg('rect', { x: padL, y: y, width: Math.max(1, bw), height: rowH - 8, fill: color, opacity: 0.85, rx: 2 });
      barSvg.appendChild(rect);
      // value at end of bar
      const vt = svg('text', { x: padL + bw + 4, y: y + 11, fill: '#e6ebff', 'font-size': 9, 'font-family': 'JetBrains Mono' });
      vt.appendChild(document.createTextNode(fmt(row.peak_g, 0) + '  (' + (row.peak_g / G).toFixed(1) + ' g)'));
      barSvg.appendChild(vt);
    }
  }

  // ----- Summary table -----
  const tbody = document.querySelector('#ppg-summary-tbl tbody');
  if (tbody) {
    while (tbody.firstChild) tbody.removeChild(tbody.firstChild);
    for (const r of summary) {
      const isImp = r.is_impactor || (impactorPid != null && r.part_id === impactorPid);
      const tr = el('tr');
      if (isImp) tr.style.color = '#ff9eb9';
      tr.appendChild(el('td', { class: 'tl' }, String(r.part_id) + (isImp ? '  ◆' : '')));
      tr.appendChild(el('td', { class: 'tl' }, r.part_name || ''));
      tr.appendChild(el('td', { class: 'num' }, fmt(r.peak_g, 0)));
      tr.appendChild(el('td', { class: 'num' }, ((r.peak_g || 0) / G).toFixed(2)));
      tr.appendChild(el('td', { class: 'num' }, (r.t_peak_g != null ? (r.t_peak_g * 1000).toFixed(3) : '-')));
      tr.appendChild(el('td', { class: 'num' }, fmt(r.peak_vel, 1)));
      tr.appendChild(el('td', { class: 'num' }, fmt(r.peak_disp, 3)));
      tbody.appendChild(tr);
    }
  }

  // ----- Line chart (acc magnitude over time, one line per part) -----
  const lineSvg = document.getElementById('ppg-line-svg');
  const legend = document.getElementById('ppg-line-legend');
  if (lineSvg && legend) {
    while (lineSvg.firstChild) lineSvg.removeChild(lineSvg.firstChild);
    while (legend.firstChild) legend.removeChild(legend.firstChild);
    if (!series.length) {
      lineSvg.setAttribute('viewBox', '0 0 600 200');
      const t = svg('text', { x: 300, y: 100, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 11 });
      t.appendChild(document.createTextNode('가속도 시계열 데이터 없음'));
      lineSvg.appendChild(t);
    } else {
      const W = 900, H = 360, pad = { l: 70, r: 14, t: 14, b: 30 };
      lineSvg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
      lineSvg.setAttribute('preserveAspectRatio', 'none');
      const plotW = W - pad.l - pad.r, plotH = H - pad.t - pad.b;
      // determine ranges
      let tMin = Infinity, tMax = -Infinity, aMin = Infinity, aMax = -Infinity;
      for (const s of series) {
        for (let i = 0; i < s.t.length; i++) {
          if (s.t[i] < tMin) tMin = s.t[i];
          if (s.t[i] > tMax) tMax = s.t[i];
        }
        for (let i = 0; i < s.a.length; i++) {
          const v = s.a[i];
          if (v > 0 && v < aMin) aMin = v;
          if (v > aMax) aMax = v;
        }
      }
      if (!isFinite(tMin)) { tMin = 0; tMax = 1; }
      if (tMax === tMin) tMax = tMin + 1;
      if (!isFinite(aMax) || aMax <= 0) aMax = 1;
      if (!isFinite(aMin) || aMin <= 0) aMin = aMax * 1e-4;
      // semi-log when range > 2 decades
      const useLog = (aMax / aMin) > 1e2;
      const yLo = useLog ? aMin : 0;
      const yHi = aMax;
      function px(tv) { return pad.l + (tv - tMin) / (tMax - tMin) * plotW; }
      function py(av) {
        if (useLog) {
          const v = Math.max(av, aMin);
          const lv = Math.log10(v);
          const lLo = Math.log10(yLo);
          const lHi = Math.log10(yHi);
          return pad.t + (1 - (lv - lLo) / (lHi - lLo)) * plotH;
        }
        return pad.t + (1 - (av - yLo) / (yHi - yLo)) * plotH;
      }
      // axes
      lineSvg.appendChild(svg('rect', { x: pad.l, y: pad.t, width: plotW, height: plotH, fill: '#0e1320', stroke: 'rgba(255,255,255,0.10)', 'stroke-width': 0.6 }));
      // x ticks (6 ticks, ms)
      for (let i = 0; i <= 6; i++) {
        const tv = tMin + (i / 6) * (tMax - tMin);
        const xp = px(tv);
        lineSvg.appendChild(svg('line', { x1: xp, y1: pad.t + plotH, x2: xp, y2: pad.t + plotH + 4, stroke: 'rgba(255,255,255,0.30)', 'stroke-width': 0.6 }));
        const t = svg('text', { x: xp, y: pad.t + plotH + 16, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 9, 'font-family': 'JetBrains Mono' });
        t.appendChild(document.createTextNode((tv * 1000).toFixed(2)));
        lineSvg.appendChild(t);
      }
      const xLab = svg('text', { x: pad.l + plotW / 2, y: H - 4, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 9 });
      xLab.appendChild(document.createTextNode('t' + (_u('time') ? '  (' + _u('time') + ')' : '')));
      lineSvg.appendChild(xLab);
      // y ticks
      if (useLog) {
        const lLo = Math.ceil(Math.log10(yLo));
        const lHi = Math.floor(Math.log10(yHi));
        for (let p = lLo; p <= lHi; p++) {
          const yv = Math.pow(10, p);
          const yp = py(yv);
          lineSvg.appendChild(svg('line', { x1: pad.l, y1: yp, x2: pad.l + plotW, y2: yp, stroke: 'rgba(255,255,255,0.06)', 'stroke-width': 0.5 }));
          const t = svg('text', { x: pad.l - 6, y: yp + 3, 'text-anchor': 'end', fill: '#5c6383', 'font-size': 9, 'font-family': 'JetBrains Mono' });
          t.appendChild(document.createTextNode('1e' + p));
          lineSvg.appendChild(t);
        }
      } else {
        for (let i = 0; i <= 4; i++) {
          const yv = yLo + (i / 4) * (yHi - yLo);
          const yp = py(yv);
          lineSvg.appendChild(svg('line', { x1: pad.l, y1: yp, x2: pad.l + plotW, y2: yp, stroke: 'rgba(255,255,255,0.06)', 'stroke-width': 0.5 }));
          const t = svg('text', { x: pad.l - 6, y: yp + 3, 'text-anchor': 'end', fill: '#5c6383', 'font-size': 9, 'font-family': 'JetBrains Mono' });
          t.appendChild(document.createTextNode(fmt(yv, 0)));
          lineSvg.appendChild(t);
        }
      }
      const yLab = svg('text', { x: 8, y: pad.t + plotH / 2, fill: '#5c6383', 'font-size': 9, transform: 'rotate(-90 14 ' + (pad.t + plotH / 2) + ')' });
      yLab.appendChild(document.createTextNode('|a|' + (_u('acc') ? '  (' + _u('acc') + ')' : '') + (useLog ? '  [log]' : '')));
      lineSvg.appendChild(yLab);
      // first-contact dashed line
      if (pm.t_first_contact != null && pm.t_first_contact >= tMin && pm.t_first_contact <= tMax) {
        const xc = px(pm.t_first_contact);
        lineSvg.appendChild(svg('line', { x1: xc, y1: pad.t, x2: xc, y2: pad.t + plotH, stroke: 'rgba(180,110,255,0.7)', 'stroke-width': 1.0, 'stroke-dasharray': '4,3' }));
        const t = svg('text', { x: xc + 4, y: pad.t + 10, fill: '#b46eff', 'font-size': 9, 'font-family': 'JetBrains Mono' });
        t.appendChild(document.createTextNode('t₁ = ' + (pm.t_first_contact * 1000).toFixed(2) + (_u('time') ? ' ' + _u('time') : '')));
        lineSvg.appendChild(t);
      }
      // sort series by peak_g desc and assign colors
      const sortedSeries = series.slice().sort((a, b) => (b.peak_g || 0) - (a.peak_g || 0));
      for (let si = 0; si < sortedSeries.length; si++) {
        const s = sortedSeries[si];
        const isImp = (impactorPid != null && s.part_id === impactorPid);
        const color = isImp ? '#ff5e84' : PPG_PALETTE[si % PPG_PALETTE.length];
        const pts = [];
        const N = Math.min(s.t.length, s.a.length);
        for (let i = 0; i < N; i++) {
          const xp = px(s.t[i]);
          const yp = py(s.a[i]);
          pts.push(xp.toFixed(1) + ',' + yp.toFixed(1));
        }
        const poly = svg('polyline', { points: pts.join(' '), fill: 'none', stroke: color, 'stroke-width': isImp ? 1.8 : 1.1, opacity: isImp ? 0.95 : 0.75 });
        const ttl = svg('title', {});
        ttl.appendChild(document.createTextNode(String(s.part_id) + '  ' + (s.part_name || '') + (isImp ? '  (impactor)' : '')));
        poly.appendChild(ttl);
        lineSvg.appendChild(poly);
        // legend
        const item = el('div', { style: { display: 'flex', alignItems: 'center', gap: '4px' } });
        item.appendChild(el('span', { style: { display: 'inline-block', width: '14px', height: '3px', background: color, borderRadius: '2px' } }));
        item.appendChild(el('span', null, String(s.part_id) + '  ' + (s.part_name || '') + (isImp ? '  ◆' : '')));
        if (isImp) item.style.color = '#ff9eb9';
        legend.appendChild(item);
      }
    }
  }
}

/* ===================================================================
 * SECTION 05 — DOE Analysis (multi-position spatial view)
 * =================================================================== */

// Mirror the existing BEHAVIOR_COLOR (Section 3 / trajectory section) so
// the same physical behavior class is never shown in two different colors
// across the report. The audit confirmed Section 05 previously had a
// distinct palette where rebound was blue here but orange in the CSS
// `.bbadge.rebound` rule — visually misleading.
const DOE_BEHAVIOR_COLOR = BEHAVIOR_COLOR;

function _doeRenderFailureRisk(doe){
  const host = document.getElementById('doe-failure-risk-body');
  if(!host) return;
  host.innerHTML = '';
  const data = (doe && doe.advanced && doe.advanced.failure_risk) || null;

  if(!data || data.available === false){
    const reason = data && data.reason === 'no_overlap'
      ? '항복응력 메타데이터와 해석 결과 부품이 겹치지 않습니다.'
      : '항복응력(yield_stress_by_part) 데이터가 없어 안전율을 계산할 수 없습니다.';
    host.appendChild(el('div', {class:'doe-empty'}, reason));
    return;
  }

  const positions = (doe && doe.positions) || [];
  const grid = (doe && doe.grid) || {nx:5, ny:5};
  const nx = grid.nx || 5, ny = grid.ny || 5;
  const sfMatrix = data.sf_matrix || {};
  const minByPos = data.min_sf_per_position || {};
  const dangerT = data.danger_threshold || 1.0;
  const riskT = data.risk_threshold || 2.0;

  const INF = Number.POSITIVE_INFINITY;
  const sfNum = (v) => (v === 'inf' || v === null || v === undefined) ? INF : Number(v);
  const sfLabel = (v) => {
    const n = sfNum(v);
    if(!isFinite(n)) return '∞';
    if(n >= 100) return n.toFixed(0);
    if(n >= 10)  return n.toFixed(1);
    return n.toFixed(2);
  };
  const sfColor = (n) => {
    if(!isFinite(n)) return 'var(--good)';
    if(n < dangerT) return 'var(--crit)';
    if(n < riskT)   return 'var(--warn)';
    return 'var(--good)';
  };

  // ---- layout: grid heatmap (left) + ranking (right) ----
  const wrap = el('div', {class:'doe-failrisk-wrap'});
  host.appendChild(wrap);

  // -- LEFT: 5x5 grid --
  const left = el('div', {class:'doe-failrisk-left'});
  wrap.appendChild(left);
  left.appendChild(el('div', {class:'doe-failrisk-subhead'}, '위치별 최소 SF (5×5)'));
  const gridBox = el('div', {class:'doe-failrisk-grid', style:`grid-template-columns:repeat(${nx},1fr);grid-template-rows:repeat(${ny},1fr);`});
  left.appendChild(gridBox);

  // Build cell map by (row,col)
  const cellByRC = {};
  positions.forEach(p => { cellByRC[`${p.row}_${p.col}`] = p; });

  for(let r=ny-1; r>=0; r--){
    for(let c=0; c<nx; c++){
      const p = cellByRC[`${r}_${c}`];
      if(!p){
        gridBox.appendChild(el('div', {class:'doe-failrisk-cell doe-failrisk-empty'}, '·'));
        continue;
      }
      const info = minByPos[String(p.pos_id)];
      if(!info){
        const cell = el('div', {class:'doe-failrisk-cell doe-failrisk-nodata',
          title:`${p.pos_id}: 항복 데이터 없는 부품들만 검출`}, [
          el('div', {class:'doe-failrisk-pid'}, p.label || p.pos_id),
          el('div', {class:'doe-failrisk-sfval'}, '—'),
        ]);
        gridBox.appendChild(cell);
        continue;
      }
      const sfN = sfNum(info.min_sf);
      const col = sfColor(sfN);
      const cell = el('div', {
        class:'doe-failrisk-cell',
        style:`background:${col};`,
        title:`${p.pos_id}  min SF=${sfLabel(info.min_sf)}  worst=${info.worst_part_name} (id ${info.worst_part_id})`
      }, [
        el('div', {class:'doe-failrisk-pid'}, p.label || p.pos_id),
        el('div', {class:'doe-failrisk-sfval'}, 'SF ' + sfLabel(info.min_sf)),
      ]);
      gridBox.appendChild(cell);
    }
  }

  // legend
  const legend = el('div', {class:'doe-failrisk-legend'}, [
    el('span', {class:'doe-failrisk-lg crit'}, `SF < ${dangerT.toFixed(1)} 항복 초과`),
    el('span', {class:'doe-failrisk-lg warn'}, `${dangerT.toFixed(1)} ≤ SF < ${riskT.toFixed(1)} 마진 부족`),
    el('span', {class:'doe-failrisk-lg good'}, `SF ≥ ${riskT.toFixed(1)} 안전`),
  ]);
  left.appendChild(legend);

  // -- RIGHT: ranking --
  const right = el('div', {class:'doe-failrisk-right'});
  wrap.appendChild(right);
  const atRisk = data.parts_at_risk || [];
  right.appendChild(el('div', {class:'doe-failrisk-subhead'},
    `위험 부품 랭킹 (SF < ${riskT.toFixed(1)}, 총 ${atRisk.length}개)`));

  if(atRisk.length === 0){
    right.appendChild(el('div', {class:'doe-empty'},
      `모든 부품의 최소 SF ≥ ${riskT.toFixed(1)} — 안전 마진 충분.`));
  } else {
    const top = atRisk.slice(0, 10);
    const list = el('div', {class:'doe-failrisk-list'});
    right.appendChild(list);

    top.forEach((row, idx) => {
      const sfN = sfNum(row.min_sf);
      const dotColor = sfColor(sfN);

      // distribution across positions for whisker
      const partSFs = sfMatrix[String(row.part_id)] || {};
      const vals = Object.values(partSFs).map(sfNum).filter(v => isFinite(v));
      let whiskerSVG = null;
      if(vals.length >= 2){
        const mn = Math.min(...vals);
        const mx = Math.max(...vals);
        const span = mx - mn;
        const W = 110, H = 14, padX = 4;
        const x = (v) => padX + (span > 0 ? (v - mn) / span * (W - 2*padX) : (W - 2*padX)/2);
        whiskerSVG = svg('svg', {width:W, height:H, class:'doe-failrisk-whisker', viewBox:`0 0 ${W} ${H}`}, [
          svg('line', {x1:x(mn), y1:H/2, x2:x(mx), y2:H/2, stroke:'var(--dim)', 'stroke-width':1}),
          ...vals.map(v => svg('circle', {cx:x(v), cy:H/2, r:2, fill: sfColor(v)})),
          svg('circle', {cx:x(sfN), cy:H/2, r:3.2, fill:'var(--fg)', stroke: dotColor, 'stroke-width':1.5}),
        ]);
      }

      const xyStr = (row.worst_pos_xy && row.worst_pos_xy.length === 2)
        ? `x=${fmt(row.worst_pos_xy[0],2)}, y=${fmt(row.worst_pos_xy[1],2)}`
        : '';
      const item = el('div', {class:'doe-failrisk-item'}, [
        el('span', {class:'doe-failrisk-rank'}, String(idx + 1)),
        el('span', {class:'doe-failrisk-dot', style:`background:${dotColor};`}),
        el('div', {class:'doe-failrisk-name'}, [
          el('div', {class:'doe-failrisk-pname'}, `${row.part_name} (id ${row.part_id})`),
          el('div', {class:'doe-failrisk-pmeta'}, `worst @ ${row.worst_pos_id}  ${xyStr}`),
        ]),
        el('div', {class:'doe-failrisk-sf'}, [
          el('div', {class:'doe-failrisk-sfbig', style:`color:${dotColor};`}, 'SF ' + sfLabel(row.min_sf)),
          whiskerSVG ? whiskerSVG : el('div', {class:'doe-failrisk-pmeta'}, '단일 위치'),
        ]),
      ]);
      list.appendChild(item);
    });
  }

  // footer summary
  const footer = el('div', {class:'doe-failrisk-foot'},
    `항복 데이터 보유 부품 ${data.n_parts_with_yield}개 중 ${data.n_parts_evaluated}개 평가됨.`);
  host.appendChild(footer);
}

function _doeCorrDivergingColor(r) {
  // Diverging palette: red (-1) -> dim mid (0) -> cyan/blue (+1).
  // Returns rgba string. Uses --crit and --accent vibes for theme cohesion.
  if (r == null || !isFinite(r)) return 'rgba(170,178,207,0.08)';
  const t = Math.max(-1, Math.min(1, r));
  if (t >= 0) {
    // 0 -> #1a1e2e (near bg2), 1 -> cyan-ish (90,210,240)
    const a = t;
    const cr = Math.round(26 + (90 - 26) * a);
    const cg = Math.round(30 + (210 - 30) * a);
    const cb = Math.round(46 + (240 - 46) * a);
    return 'rgb(' + cr + ',' + cg + ',' + cb + ')';
  } else {
    const a = -t;
    // 0 -> #1a1e2e, -1 -> warm red (240,90,80)
    const cr = Math.round(26 + (240 - 26) * a);
    const cg = Math.round(30 + (90 - 30) * a);
    const cb = Math.round(46 + (80 - 46) * a);
    return 'rgb(' + cr + ',' + cg + ',' + cb + ')';
  }
}

function _doeRenderCorrNetwork(doe) {
  const host = document.getElementById('doe-corr-network');
  if (!host) return;
  host.innerHTML = '';
  const data = (doe && doe.advanced && doe.advanced.corr_network) || null;
  if (!data || !data.parts_listed || data.parts_listed.length < 2 || !data.corr_matrix) {
    host.appendChild(el('div', { class: 'no-data', style: { padding: '24px', color: 'var(--dim)', 'text-align': 'center' } },
      [document.createTextNode('상관 분석 데이터 없음 — 위치 수 < 2 또는 peak_g 데이터 부족')]));
    return;
  }

  const parts = data.parts_listed;
  const N = parts.length;
  const M = data.corr_matrix;
  const nPos = data.n_positions || 0;
  const thr = (typeof data.corr_threshold === 'number') ? data.corr_threshold : 0.7;

  // Layout: heatmap (left, flex) + cluster summary (right, fixed width)
  const wrap = el('div', { class: 'doe-corr-wrap',
    style: { display: 'grid', 'grid-template-columns': 'minmax(0, 1.3fr) minmax(260px, 1fr)',
             gap: '14px', 'align-items': 'start' } });

  // --- Heatmap (SVG) ----------------------------------------------------
  const cell = 30;
  const labelPad = 110;
  const topPad = 110;
  const vbW = labelPad + N * cell + 70; // +70 for legend
  const vbH = topPad + N * cell + 30;
  const svgRoot = svg('svg', {
    viewBox: '0 0 ' + vbW + ' ' + vbH,
    preserveAspectRatio: 'xMinYMin meet',
    style: { width: '100%', height: 'auto', background: 'var(--bg2)', 'border-radius': '6px' }
  });

  // Row labels (left, part_name) + column labels (top, rotated)
  for (let i = 0; i < N; i++) {
    const pn = parts[i].part_name || ('part_' + parts[i].part_id);
    const shortPn = pn.length > 14 ? (pn.slice(0, 12) + '…') : pn;
    // row label
    svgRoot.appendChild(svg('text', {
      x: labelPad - 6, y: topPad + i * cell + cell * 0.66,
      fill: 'var(--fg2)', 'font-size': 10, 'text-anchor': 'end',
    }, [document.createTextNode(shortPn)]));
    // col label (rotated)
    const cx = labelPad + i * cell + cell * 0.5;
    const cy = topPad - 6;
    svgRoot.appendChild(svg('text', {
      x: cx, y: cy, fill: 'var(--fg2)', 'font-size': 10, 'text-anchor': 'start',
      transform: 'rotate(-55 ' + cx + ' ' + cy + ')',
    }, [document.createTextNode(shortPn)]));
  }

  // Cells
  for (let i = 0; i < N; i++) {
    const rowKey = String(parts[i].part_id);
    const rowMap = M[rowKey] || {};
    for (let j = 0; j < N; j++) {
      const colKey = String(parts[j].part_id);
      const r = (typeof rowMap[colKey] === 'number') ? rowMap[colKey] : null;
      const fill = _doeCorrDivergingColor(r);
      const x = labelPad + j * cell;
      const y = topPad + i * cell;
      const isDiag = (i === j);
      const strong = (r != null && Math.abs(r) >= thr && !isDiag);
      const cellEl = svg('rect', {
        x: x, y: y, width: cell - 1.5, height: cell - 1.5,
        fill: fill,
        stroke: strong ? 'rgba(255,255,255,0.55)' : 'rgba(0,0,0,0.25)',
        'stroke-width': strong ? 1.2 : 0.5,
        rx: 2, ry: 2,
      });
      // Tooltip via <title>
      const piName = parts[i].part_name;
      const pjName = parts[j].part_name;
      const rTxt = (r == null) ? 'n/a' : r.toFixed(3);
      cellEl.appendChild(svg('title', {}, [document.createTextNode(
        piName + ' × ' + pjName + '\nr = ' + rTxt + '\nn_positions = ' + nPos
      )]));
      svgRoot.appendChild(cellEl);

      // Inline r text on cells with |r| >= 0.5 OR diagonal — keep grid readable
      if (r != null && (Math.abs(r) >= 0.5 || isDiag)) {
        const txt = (Math.abs(r) >= 0.995) ? r.toFixed(2) : r.toFixed(2);
        svgRoot.appendChild(svg('text', {
          x: x + (cell - 1.5) / 2, y: y + (cell - 1.5) / 2 + 3,
          fill: (Math.abs(r) > 0.55 ? '#0a0c14' : 'var(--fg)'),
          'font-size': 9, 'text-anchor': 'middle', 'pointer-events': 'none',
          style: { 'font-family': 'ui-monospace, SFMono-Regular, monospace' },
        }, [document.createTextNode(txt)]));
      }
    }
  }

  // Legend (diverging color bar) at right of matrix
  const legX = labelPad + N * cell + 16;
  const legY0 = topPad;
  const legH = N * cell;
  const legW = 12;
  const nSteps = 30;
  for (let k = 0; k < nSteps; k++) {
    const t = k / (nSteps - 1);
    const r = 1.0 - 2.0 * t; // top=+1, bottom=-1
    svgRoot.appendChild(svg('rect', {
      x: legX, y: legY0 + t * legH, width: legW, height: legH / nSteps + 0.5,
      fill: _doeCorrDivergingColor(r), stroke: 'none',
    }));
  }
  // Legend ticks: +1, 0, -1
  const legendTick = (val, frac) => {
    svgRoot.appendChild(svg('text', {
      x: legX + legW + 4, y: legY0 + frac * legH + 3,
      fill: 'var(--fg2)', 'font-size': 10,
    }, [document.createTextNode(val)]));
  };
  legendTick('+1', 0.0);
  legendTick(' 0', 0.5);
  legendTick('-1', 1.0);
  svgRoot.appendChild(svg('text', {
    x: legX + legW / 2, y: legY0 + legH + 16,
    fill: 'var(--dim)', 'font-size': 9, 'text-anchor': 'middle',
  }, [document.createTextNode('r')]));

  // Footer note: n + threshold
  svgRoot.appendChild(svg('text', {
    x: labelPad, y: vbH - 6, fill: 'var(--dim)', 'font-size': 10,
  }, [document.createTextNode('n_positions = ' + nPos + '   ·   strong if |r| ≥ ' + thr.toFixed(2))]));

  wrap.appendChild(svgRoot);

  // --- Cluster summary panel -------------------------------------------
  const summary = el('div', { class: 'doe-corr-clusters',
    style: { display: 'flex', 'flex-direction': 'column', gap: '8px' } });

  const clusters = data.clusters || [];
  const multiClusters = clusters.filter(function(c) { return (c.members || []).length >= 2; });
  const soloCount = clusters.length - multiClusters.length;

  summary.appendChild(el('div', {
    style: { color: 'var(--fg)', 'font-size': 12, 'font-weight': 600, 'margin-bottom': '2px' }
  }, [document.createTextNode('검출된 클러스터 — ' + multiClusters.length + '개 (단독 ' + soloCount + '개)')]));

  if (multiClusters.length === 0) {
    summary.appendChild(el('div', {
      style: { color: 'var(--dim)', 'font-size': 11, padding: '12px',
               background: 'var(--bg2)', 'border-radius': '6px',
               border: '1px solid var(--line)' }
    }, [document.createTextNode('|r| ≥ ' + thr.toFixed(2) + ' 인 강한 상관 부품 쌍 없음. 모든 부품이 독립적 응답.')]));
  }

  // Cluster color from gColor by cluster index spread
  multiClusters.forEach(function(c, idx) {
    const t = (multiClusters.length <= 1) ? 0.5 : (idx / (multiClusters.length - 1));
    const accent = gColor(t);
    const card = el('div', {
      style: {
        background: 'var(--bg2)',
        border: '1px solid var(--line)',
        'border-left': '3px solid ' + accent,
        'border-radius': '6px',
        padding: '8px 10px',
      }
    });
    const head = el('div', {
      style: { display: 'flex', 'justify-content': 'space-between', 'align-items': 'baseline', 'margin-bottom': '4px' }
    });
    head.appendChild(el('span', {
      style: { color: 'var(--fg)', 'font-size': 11, 'font-weight': 600 }
    }, [document.createTextNode('클러스터 ' + (c.cluster_id != null ? c.cluster_id : idx) + '  (' + c.size + ' parts)')]));
    head.appendChild(el('span', {
      style: { color: 'var(--accent)', 'font-size': 11,
               'font-family': 'ui-monospace, SFMono-Regular, monospace' }
    }, [document.createTextNode('응답 일관성 r̄ = ' + (typeof c.mean_r === 'number' ? c.mean_r.toFixed(3) : 'n/a'))]));
    card.appendChild(head);

    const names = (c.member_names || []).slice();
    const list = el('div', {
      style: { color: 'var(--fg2)', 'font-size': 10.5, 'line-height': 1.5 }
    });
    names.forEach(function(nm, k) {
      const tag = el('span', {
        style: {
          display: 'inline-block',
          padding: '1px 6px',
          margin: '2px 4px 2px 0',
          background: 'rgba(255,255,255,0.04)',
          border: '1px solid var(--line)',
          'border-radius': '3px',
          color: 'var(--fg)',
        }
      }, [document.createTextNode(nm)]);
      list.appendChild(tag);
    });
    card.appendChild(list);
    summary.appendChild(card);
  });

  if (soloCount > 0) {
    const solos = clusters.filter(function(c) { return (c.members || []).length < 2; });
    const soloNames = [];
    solos.forEach(function(c) { (c.member_names || []).forEach(function(nm) { soloNames.push(nm); }); });
    summary.appendChild(el('div', {
      style: { color: 'var(--dim)', 'font-size': 10.5, padding: '6px 10px',
               'border-top': '1px dashed var(--line)', 'margin-top': '4px' }
    }, [document.createTextNode('단독 부품: ' + (soloNames.join(', ') || '—'))]));
  }

  wrap.appendChild(summary);
  host.appendChild(wrap);
}

function _doeRenderTOA(doe) {
  const root = document.getElementById('doe-toa-root');
  if (!root) return;
  while (root.firstChild) root.removeChild(root.firstChild);
  const toa = (doe.advanced || {}).toa;
  if (!toa) {
    root.appendChild(el('div', { class: 'doe-toa-empty' }, 'TOA payload 없음.'));
    return;
  }
  const perPos = toa.toa_per_position || {};
  const meanPerPart = toa.mean_arrival_per_part || {};
  const behaviorByPos = toa.behavior_by_pos || {};

  // --- LEFT: strip chart for worst position --------------------------------
  const worstPid = doe.worst_position ? doe.worst_position.pos_id : null;
  const left = el('div', { class: 'toa-left' });

  let pickedPosId = null;
  let rows = [];
  if (worstPid && Array.isArray(perPos[worstPid]) && perPos[worstPid].length) {
    pickedPosId = worstPid;
    rows = perPos[worstPid];
  } else {
    // fallback: first non-empty pos
    for (const k of Object.keys(perPos)) {
      if (Array.isArray(perPos[k]) && perPos[k].length) {
        pickedPosId = k; rows = perPos[k]; break;
      }
    }
  }

  const leftHeader = el('div', { class: 'toa-sec-h' });
  leftHeader.appendChild(el('span', { class: 'toa-sec-t' }, '최악 위치의 응답 도착 순서'));
  if (pickedPosId) {
    const behavior = behaviorByPos[pickedPosId] || 'unknown';
    const swatchColor = (typeof BEHAVIOR_COLOR !== 'undefined' && BEHAVIOR_COLOR[behavior])
      ? BEHAVIOR_COLOR[behavior]
      : '#5c6383';
    const pidSpan = el('span', { class: 'toa-sec-d' });
    pidSpan.appendChild(document.createTextNode('pos ' + pickedPosId + ' · '));
    pidSpan.appendChild(el('span', { class: 'toa-sw', style: { background: swatchColor } }));
    pidSpan.appendChild(document.createTextNode(' ' + behavior));
    leftHeader.appendChild(pidSpan);
  }
  left.appendChild(leftHeader);

  if (!rows.length) {
    left.appendChild(el('div', { class: 'doe-toa-empty' }, '도착 시간 데이터 없음.'));
  } else {
    const dts = rows.map(r => Number(r.dt_ms));
    const dtMin = Math.min(...dts);
    const dtMax = Math.max(...dts);
    const span = Math.max(1e-6, dtMax - Math.min(0, dtMin));
    const behaviorPos = behaviorByPos[pickedPosId] || 'unknown';
    const stripColor = (typeof BEHAVIOR_COLOR !== 'undefined' && BEHAVIOR_COLOR[behaviorPos])
      ? BEHAVIOR_COLOR[behaviorPos]
      : '#5c6383';

    const strip = el('div', { class: 'toa-strip' });
    rows.forEach((r, idx) => {
      const row = el('div', { class: 'toa-bar-row' });
      row.appendChild(el('div', { class: 'toa-bar-name', title: r.part_name }, r.part_name));
      const track = el('div', { class: 'toa-bar-track' });
      const dt = Number(r.dt_ms);
      // length: clamp at 0, normalize against span
      const lenT = Math.max(0, (dt - Math.min(0, dtMin))) / span;
      const fill = el('div', {
        class: 'toa-bar-fill',
        style: {
          width: (lenT * 100).toFixed(1) + '%',
          background: stripColor,
          opacity: (0.45 + 0.55 * (1 - idx / Math.max(1, rows.length - 1))).toFixed(2),
        },
      });
      track.appendChild(fill);
      row.appendChild(track);
      row.appendChild(el('div', { class: 'toa-bar-val' }, fmt(dt, 2) + ' ms'));
      strip.appendChild(row);
    });
    left.appendChild(strip);
    const axis = el('div', { class: 'toa-axis' });
    axis.appendChild(el('span', {}, fmt(Math.min(0, dtMin), 2) + ' ms'));
    axis.appendChild(el('span', { class: 'toa-axis-mid' }, 'Δt = part peak_g − impactor 첫 접촉'));
    axis.appendChild(el('span', {}, fmt(dtMax, 2) + ' ms'));
    left.appendChild(axis);
  }

  // --- RIGHT: always-early / always-late lists -----------------------------
  const right = el('div', { class: 'toa-right' });

  function _mkList(title, dim, entries, accent) {
    const box = el('div', { class: 'toa-listbox' });
    const h = el('div', { class: 'toa-sec-h' });
    h.appendChild(el('span', { class: 'toa-sec-t', style: { color: accent } }, title));
    h.appendChild(el('span', { class: 'toa-sec-d' }, dim));
    box.appendChild(h);
    if (!entries.length) {
      box.appendChild(el('div', { class: 'doe-toa-empty' }, '데이터 부족 (n_positions ≥ 2 필요).'));
      return box;
    }
    const ul = el('div', { class: 'toa-list' });
    entries.forEach(e => {
      const li = el('div', { class: 'toa-li' });
      li.appendChild(el('div', { class: 'toa-li-name', title: e.part_name }, e.part_name));
      const meanTxt = fmt(e.mean_dt_ms, 2);
      const stdTxt = fmt(e.std_dt_ms, 2);
      const stat = el('div', { class: 'toa-li-stat' });
      stat.appendChild(el('span', { class: 'toa-li-mean' }, meanTxt + ' ms'));
      stat.appendChild(el('span', { class: 'toa-li-std' }, ' ± ' + stdTxt));
      stat.appendChild(el('span', { class: 'toa-li-n' }, ' · n=' + e.n_positions));
      li.appendChild(stat);
      ul.appendChild(li);
    });
    box.appendChild(ul);
    return box;
  }

  // Build entries from mean_arrival_per_part (require >= 2 positions)
  const entries = Object.keys(meanPerPart).map(pid => {
    const info = meanPerPart[pid] || {};
    // lookup name from doe.positions/parts: use a simple scan of any toa row
    let pname = 'part_' + pid;
    for (const k of Object.keys(perPos)) {
      const found = (perPos[k] || []).find(r => String(r.part_id) === String(pid));
      if (found) { pname = found.part_name; break; }
    }
    return {
      part_id: Number(pid),
      part_name: pname,
      mean_dt_ms: Number(info.mean_dt_ms || 0),
      std_dt_ms: Number(info.std_dt_ms || 0),
      n_positions: Number(info.n_positions || 0),
    };
  }).filter(e => e.n_positions >= 2);

  const earlyList = entries.slice().sort((a, b) => a.mean_dt_ms - b.mean_dt_ms).slice(0, 6);
  const lateList  = entries.slice().sort((a, b) => b.mean_dt_ms - a.mean_dt_ms).slice(0, 6);

  right.appendChild(_mkList('항상 빠른 부품', '평균 Δt 최소 6개', earlyList, 'var(--good, #4adfa1)'));
  right.appendChild(_mkList('항상 느린 부품', '평균 Δt 최대 6개', lateList, 'var(--warn, #f0a830)'));

  // Tagline at top: earliest / latest
  if (toa.earliest_part || toa.latest_part) {
    const tag = el('div', { class: 'toa-tagline' });
    if (toa.earliest_part) {
      tag.appendChild(el('span', { class: 'toa-tag toa-tag-e' },
        '가장 빠른 평균 Δt: ' + toa.earliest_part.part_name +
        ' (' + fmt(toa.earliest_part.mean_dt_ms, 2) + ' ms, n=' + toa.earliest_part.n_positions + ')'));
    }
    if (toa.latest_part) {
      tag.appendChild(el('span', { class: 'toa-tag toa-tag-l' },
        '가장 느린 평균 Δt: ' + toa.latest_part.part_name +
        ' (' + fmt(toa.latest_part.mean_dt_ms, 2) + ' ms, n=' + toa.latest_part.n_positions + ')'));
    }
    root.appendChild(tag);
  }

  const grid = el('div', { class: 'toa-grid' });
  grid.appendChild(left);
  grid.appendChild(right);
  root.appendChild(grid);
}

const IDW_STATE = { metric: 'peak_g' };

function _idwMetricLabel(k) {
  return k === 'peak_stress' ? 'PEAK σ' : 'PEAK G';
}
function _idwMetricUnit(k) {
  return k === 'peak_stress' ? _u('stress') : _u('acc');
}

function _doeRenderIdwPredictor(doe) {
  const host = document.getElementById('idw-pred-panel');
  if (!host) return;
  const adv = doe && doe.advanced ? doe.advanced.idw_predictor : null;
  const svgEl = document.getElementById('idw-pred-svg');
  const btnHost = document.getElementById('idw-pred-buttons');
  const info = document.getElementById('idw-pred-info');
  if (!svgEl || !btnHost || !info) return;

  if (!adv || !adv.grid_fine || !adv.measured_points || adv.measured_points.length < 2) {
    while (svgEl.firstChild) svgEl.removeChild(svgEl.firstChild);
    svgEl.appendChild(svg('text', { x: 200, y: 200, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 11 }, [document.createTextNode('IDW 데이터 없음 (측정점 부족)')]));
    btnHost.innerHTML = '';
    info.innerHTML = '';
    return;
  }

  // metric toggle buttons (built once per render call to stay in sync)
  btnHost.innerHTML = '';
  ['peak_g', 'peak_stress'].forEach(k => {
    const b = el('button', {
      class: 'btn' + (IDW_STATE.metric === k ? ' active' : ''),
      'data-idw-metric': k
    }, _idwMetricLabel(k));
    b.addEventListener('click', () => {
      IDW_STATE.metric = k;
      _doeRenderIdwPredictor(doe);
    });
    btnHost.appendChild(b);
  });

  const gf = adv.grid_fine;
  const NX = gf.nx_fine | 0, NY = gf.ny_fine | 0;
  const bb = gf.bbox;
  const arr = gf[IDW_STATE.metric] || [];
  if (NX < 2 || NY < 2 || arr.length !== NX * NY) {
    while (svgEl.firstChild) svgEl.removeChild(svgEl.firstChild);
    svgEl.appendChild(svg('text', { x: 200, y: 200, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 11 }, [document.createTextNode('IDW 그리드 형상 오류')]));
    return;
  }

  // Color scaling: use the fine-grid max (so peaks are visible). Guard zero.
  let vmin = Infinity, vmax = -Infinity;
  for (let i = 0; i < arr.length; i++) {
    const v = arr[i];
    if (!isFinite(v)) continue;
    if (v < vmin) vmin = v;
    if (v > vmax) vmax = v;
  }
  if (!isFinite(vmin) || !isFinite(vmax) || vmax <= vmin) {
    vmin = 0; vmax = vmax > 0 ? vmax : 1;
  }
  const span = vmax - vmin || 1;

  while (svgEl.firstChild) svgEl.removeChild(svgEl.firstChild);
  const vbW = 540, vbH = 540;
  svgEl.setAttribute('viewBox', '0 0 ' + vbW + ' ' + vbH);
  svgEl.setAttribute('preserveAspectRatio', 'xMidYMid meet');
  svgEl.appendChild(svg('rect', { x: 0, y: 0, width: vbW, height: vbH, fill: '#0e1320', rx: 4 }));

  const padL = 56, padR = 18, padT = 22, padB = 38;
  const plotW = vbW - padL - padR;
  const plotH = vbH - padT - padB;
  const cellW = plotW / NX;
  const cellH = plotH / NY;

  const xmin = bb[0], ymin = bb[1], xmax = bb[2], ymax = bb[3];
  const xSpan = xmax - xmin || 1;
  const ySpan = ymax - ymin || 1;
  const xToPx = x => padL + ((x - xmin) / xSpan) * plotW;
  const yToPx = y => padT + (1 - (y - ymin) / ySpan) * plotH; // flip Y

  // Render fine-grid heatmap (one rect per cell, no stroke for performance)
  for (let j = 0; j < NY; j++) {
    for (let i = 0; i < NX; i++) {
      const v = arr[j * NX + i];
      const t = Math.max(0, Math.min(1, (v - vmin) / span));
      const px = padL + i * cellW;
      // Y flip so row 0 (ymin) sits at bottom
      const py = padT + (NY - 1 - j) * cellH;
      svgEl.appendChild(svg('rect', {
        x: px, y: py,
        width: cellW + 0.6, height: cellH + 0.6,
        fill: gColor(t), 'shape-rendering': 'crispEdges'
      }));
    }
  }

  // Axis box
  svgEl.appendChild(svg('rect', {
    x: padL, y: padT, width: plotW, height: plotH,
    fill: 'none', stroke: 'rgba(255,255,255,0.18)', 'stroke-width': 0.6
  }));

  // Overlay measured points (black dot, white outline)
  (adv.measured_points || []).forEach(m => {
    const cx = xToPx(m.x);
    const cy = yToPx(m.y);
    const g = svg('g', null);
    g.appendChild(svg('circle', { cx: cx, cy: cy, r: 4.2, fill: '#0a0c14', stroke: '#ffffff', 'stroke-width': 1.2 }));
    const v = (IDW_STATE.metric === 'peak_stress') ? m.peak_stress : m.peak_g;
    const u = _idwMetricUnit(IDW_STATE.metric);
    g.appendChild(svg('title', null, [document.createTextNode(
      m.pos_id + '\nx=' + m.x.toFixed(2) + ' y=' + m.y.toFixed(2) +
      '\n측정 ' + _idwMetricLabel(IDW_STATE.metric) + ' = ' + fmt(v, 1) + (u ? ' ' + u : '')
    )]));
    svgEl.appendChild(g);
  });

  // Highlight predicted-max sample (yellow ring + tooltip)
  const maxIdx = (adv.max_sample_idx && adv.max_sample_idx[IDW_STATE.metric]) | 0;
  if (maxIdx >= 0 && maxIdx < arr.length) {
    const mi = maxIdx % NX;
    const mj = Math.floor(maxIdx / NX);
    const mx = xmin + mi * (xSpan / (NX - 1));
    const my = ymin + mj * (ySpan / (NY - 1));
    const cx = xToPx(mx);
    const cy = yToPx(my);
    const ring = svg('g', null);
    ring.appendChild(svg('circle', { cx: cx, cy: cy, r: 10, fill: 'none', stroke: '#ffd84d', 'stroke-width': 2.2 }));
    ring.appendChild(svg('circle', { cx: cx, cy: cy, r: 2.4, fill: '#ffd84d' }));
    const u = _idwMetricUnit(IDW_STATE.metric);
    const peakV = arr[maxIdx];
    ring.appendChild(svg('title', null, [document.createTextNode(
      '예측 최대 위치\nx=' + mx.toFixed(2) + ' y=' + my.toFixed(2) +
      '\n' + _idwMetricLabel(IDW_STATE.metric) + ' ≈ ' + fmt(peakV, 1) + (u ? ' ' + u : '')
    )]));
    svgEl.appendChild(ring);

    // info line under SVG
    const u2 = _idwMetricUnit(IDW_STATE.metric);
    info.innerHTML = '<span style="color:#ffd84d">●</span> 예측 최대: ' +
      '(' + mx.toFixed(2) + ', ' + my.toFixed(2) + ')' +
      '   ' + _idwMetricLabel(IDW_STATE.metric) + ' ≈ <b>' + fmt(peakV, 1) + '</b>' +
      (u2 ? ' <span class="u">' + u2 + '</span>' : '') +
      '   ·   측정점 ' + (adv.measured_points || []).length + ' 개 기반 IDW(p=' + (adv.power || 2) + ') 보간';
  } else {
    info.innerHTML = '';
  }

  // Axes labels
  svgEl.appendChild(svg('text', { x: padL, y: padT - 6, fill: '#5c6383', 'font-size': 9 },
    [document.createTextNode('X: ' + xmin.toFixed(2) + ' → ' + xmax.toFixed(2))]));
  svgEl.appendChild(svg('text', { x: padL, y: vbH - padB + 22, fill: '#5c6383', 'font-size': 9 },
    [document.createTextNode('Y: ' + ymin.toFixed(2) + ' → ' + ymax.toFixed(2))]));
  const uLab = _idwMetricUnit(IDW_STATE.metric);
  svgEl.appendChild(svg('text', { x: vbW / 2, y: vbH - 8, fill: '#aab2cf', 'font-size': 10, 'text-anchor': 'middle' },
    [document.createTextNode('IDW(p=2) ' + NX + '×' + NY + '  ·  ' + _idwMetricLabel(IDW_STATE.metric) + (uLab ? ' (' + uLab + ')' : ''))]));

  // Color legend (right edge)
  const lgX = vbW - padR - 10;
  const lgY0 = padT + 4;
  const lgH = plotH - 8;
  const N_STOPS = 24;
  for (let s = 0; s < N_STOPS; s++) {
    const t = 1 - s / (N_STOPS - 1); // top = high
    svgEl.appendChild(svg('rect', {
      x: lgX, y: lgY0 + s * (lgH / N_STOPS),
      width: 8, height: (lgH / N_STOPS) + 0.6,
      fill: gColor(t), 'shape-rendering': 'crispEdges'
    }));
  }
  svgEl.appendChild(svg('text', { x: lgX + 4, y: lgY0 - 4, fill: '#aab2cf', 'font-size': 9, 'text-anchor': 'middle' },
    [document.createTextNode(fmt(vmax, 1))]));
  svgEl.appendChild(svg('text', { x: lgX + 4, y: lgY0 + lgH + 10, fill: '#aab2cf', 'font-size': 9, 'text-anchor': 'middle' },
    [document.createTextNode(fmt(vmin, 1))]));
}

function _doeRenderParetoSeverity(doe) {
  const host = document.getElementById('doe-pareto-severity');
  if (!host) return;
  host.innerHTML = '';
  const adv = (doe && doe.advanced) || {};
  const data = adv.pareto_severity;
  if (!data || !data.points || data.points.length === 0) {
    host.appendChild(el('div', { class: 'traj-na' }, '데이터 없음 — Pareto 분석을 수행할 수 없습니다.'));
    return;
  }
  const pts = data.points.filter(p => isFinite(p.severity) && isFinite(p.coverage));
  if (pts.length === 0) {
    host.appendChild(el('div', { class: 'traj-na' }, '유효한 포인트가 없습니다.'));
    return;
  }

  const unitAcc = (data.unit_acc) || (typeof _u === 'function' ? _u('acc') : 'm/s²');

  // layout
  const W = 760, H = 460;
  const M = { l: 78, r: 24, t: 28, b: 56 };
  const innerW = W - M.l - M.r;
  const innerH = H - M.t - M.b;

  // severity log scale (guard against 0)
  const sevPos = pts.map(p => p.severity).filter(v => v > 0);
  const sevMin = sevPos.length ? Math.min.apply(null, sevPos) : 1.0;
  const sevMax = sevPos.length ? Math.max.apply(null, sevPos) : 10.0;
  const useLog = (sevMax / Math.max(sevMin, 1e-9)) > 50.0;
  const lo = useLog ? Math.log10(Math.max(sevMin, 1e-9)) : sevMin;
  const hi = useLog ? Math.log10(Math.max(sevMax, 1e-9)) : sevMax;
  const span = (hi - lo) > 0 ? (hi - lo) : 1.0;
  function sx(v) {
    const vv = useLog ? Math.log10(Math.max(v, 1e-9)) : v;
    return M.l + ((vv - lo) / span) * innerW;
  }
  function sy(c) {
    return M.t + (1.0 - Math.max(0, Math.min(1, c))) * innerH;
  }

  // marker size from mean_response
  const meanLo = data.min_mean, meanHi = data.max_mean;
  const meanSpan = (meanHi - meanLo) > 0 ? (meanHi - meanLo) : 1.0;
  function rSize(m) {
    const t = (m - meanLo) / meanSpan;
    return 4.0 + Math.max(0, Math.min(1, t)) * 10.0;
  }

  const root = svg('svg', {
    viewBox: '0 0 ' + W + ' ' + H,
    width: '100%', height: H,
    style: 'background:var(--bg2);border:1px solid var(--line);border-radius:6px;',
  });

  // grid lines (y: 0, 0.25, 0.5, 0.75, 1.0)
  [0, 0.25, 0.5, 0.75, 1.0].forEach(g => {
    const y = sy(g);
    root.appendChild(svg('line', {
      x1: M.l, x2: M.l + innerW, y1: y, y2: y,
      stroke: 'var(--line)', 'stroke-width': 0.6, 'stroke-dasharray': '2,3',
    }));
    root.appendChild(svg('text', {
      x: M.l - 8, y: y + 3, 'text-anchor': 'end',
      fill: 'var(--dim)', 'font-size': 10,
    }, [String(Math.round(g * 100)) + '%']));
  });

  // x-axis ticks
  const nTicks = 5;
  for (let i = 0; i <= nTicks; i++) {
    const t = i / nTicks;
    const v = useLog ? Math.pow(10, lo + t * span) : (lo + t * span);
    const x = M.l + t * innerW;
    root.appendChild(svg('line', {
      x1: x, x2: x, y1: M.t, y2: M.t + innerH,
      stroke: 'var(--line)', 'stroke-width': 0.5, 'stroke-dasharray': '2,3',
    }));
    root.appendChild(svg('text', {
      x: x, y: M.t + innerH + 16, 'text-anchor': 'middle',
      fill: 'var(--dim)', 'font-size': 10,
    }, [fmt(v, v >= 100 ? 0 : 2)]));
  }

  // axis labels
  root.appendChild(svg('text', {
    x: M.l + innerW / 2, y: H - 12, 'text-anchor': 'middle',
    fill: 'var(--fg2)', 'font-size': 11,
  }, ['Severity = max peak_g [' + unitAcc + ']' + (useLog ? '  (log)' : '')]));
  root.appendChild(svg('text', {
    x: 16, y: M.t + innerH / 2, 'text-anchor': 'middle',
    fill: 'var(--fg2)', 'font-size': 11,
    transform: 'rotate(-90 16 ' + (M.t + innerH / 2) + ')',
  }, ['Coverage = 부품 비율 ( > P75 )']));

  // median cross-hair (quadrant split)
  const mx = sx(data.median_severity);
  const my = sy(data.median_coverage);
  root.appendChild(svg('line', {
    x1: mx, x2: mx, y1: M.t, y2: M.t + innerH,
    stroke: 'var(--warn)', 'stroke-width': 1.2, 'stroke-dasharray': '5,4', opacity: 0.7,
  }));
  root.appendChild(svg('line', {
    x1: M.l, x2: M.l + innerW, y1: my, y2: my,
    stroke: 'var(--warn)', 'stroke-width': 1.2, 'stroke-dasharray': '5,4', opacity: 0.7,
  }));

  // quadrant labels
  const ql = data.quadrant_labels || {};
  function qLabel(txt, x, y, anchor) {
    root.appendChild(svg('text', {
      x: x, y: y, 'text-anchor': anchor,
      fill: 'var(--dim)', 'font-size': 10, 'font-style': 'italic', opacity: 0.85,
    }, [txt]));
  }
  qLabel('Q2: ' + (ql.q2 || ''), M.l + 6, M.t + 14, 'start');
  qLabel('Q1: ' + (ql.q1 || ''), M.l + innerW - 6, M.t + 14, 'end');
  qLabel('Q3: ' + (ql.q3 || ''), M.l + 6, M.t + innerH - 6, 'start');
  qLabel('Q4: ' + (ql.q4 || ''), M.l + innerW - 6, M.t + innerH - 6, 'end');

  // tooltip box (single shared)
  const tip = el('div', {
    class: 'pareto-tip',
    style: 'position:absolute;pointer-events:none;background:var(--bg3);' +
           'border:1px solid var(--line);border-radius:4px;padding:6px 8px;' +
           'font-size:11px;color:var(--fg);display:none;z-index:10;line-height:1.5;',
  });
  host.style.position = 'relative';
  host.appendChild(tip);

  const COLORS = (typeof DOE_BEHAVIOR_COLOR !== 'undefined' && DOE_BEHAVIOR_COLOR) ||
                 (typeof BEHAVIOR_COLOR !== 'undefined' ? BEHAVIOR_COLOR : {});
  function bcolor(b) {
    return COLORS[b] || 'var(--accent)';
  }

  // draw points (back→front by severity so the worst points sit on top)
  const ordered = pts.slice().sort((a, b) => a.severity - b.severity);
  ordered.forEach(p => {
    const cx = sx(Math.max(p.severity, 1e-9));
    const cy = sy(p.coverage);
    const r = rSize(p.mean_response);
    const col = bcolor(p.behavior_class);
    const c = svg('circle', {
      cx: cx, cy: cy, r: r,
      fill: col, 'fill-opacity': 0.55,
      stroke: col, 'stroke-width': 1.2,
      style: 'cursor:pointer;',
    });
    c.addEventListener('mousemove', (ev) => {
      const rect = host.getBoundingClientRect();
      tip.style.display = 'block';
      tip.style.left = (ev.clientX - rect.left + 12) + 'px';
      tip.style.top = (ev.clientY - rect.top + 12) + 'px';
      tip.innerHTML =
        '<b>' + p.pos_id + '</b> &nbsp;<span style="color:' + col + '">●</span> ' +
        p.behavior_class +
        '<br>Severity: ' + fmt(p.severity, 1) + ' ' + unitAcc +
        '<br>Coverage: ' + fmt(p.coverage * 100, 1) + ' %  (' + p.n_above + '/' + p.n_parts + ')' +
        '<br>Mean peak_g: ' + fmt(p.mean_response, 1) + ' ' + unitAcc;
    });
    c.addEventListener('mouseleave', () => { tip.style.display = 'none'; });
    root.appendChild(c);
  });

  // legend (behavior classes present + size hint)
  const presentBeh = Array.from(new Set(pts.map(p => p.behavior_class)));
  const legend = el('div', { class: 'pareto-legend',
    style: 'display:flex;flex-wrap:wrap;gap:12px;margin-top:8px;font-size:11px;color:var(--fg2);align-items:center;' });
  presentBeh.forEach(b => {
    legend.appendChild(el('span', {
      style: 'display:inline-flex;align-items:center;gap:4px;',
    }, [
      el('span', { style: 'width:10px;height:10px;border-radius:50%;background:' + bcolor(b) + ';display:inline-block;' }),
      b,
    ]));
  });
  legend.appendChild(el('span', { style: 'opacity:0.7;margin-left:auto;' },
    ['크기 = mean peak_g (' + fmt(meanLo, 1) + ' → ' + fmt(meanHi, 1) + ' ' + unitAcc + ')']));
  legend.appendChild(el('span', { style: 'opacity:0.7;' },
    ['점선 = 중앙값 분할 (P75 임계: ' + fmt(data.p75_global, 1) + ' ' + unitAcc + ')']));

  host.appendChild(root);
  host.appendChild(legend);
}

function _doeRenderEnergyPartition(doe) {
  const root = document.getElementById('doe-ep-list');
  const sumRoot = document.getElementById('doe-ep-summary');
  if (!root || !sumRoot) return;
  while (root.firstChild) root.removeChild(root.firstChild);
  while (sumRoot.firstChild) sumRoot.removeChild(sumRoot.firstChild);

  const adv = (doe.advanced || {}).energy_partition || {};
  const parts = (adv.partitions || []).slice();
  const summary = adv.summary || {};
  const ueng = _u('energy') || 'J';

  if (!parts.length) {
    root.appendChild(el('div', { class: 'doe-ep-empty', style: {
      padding: '24px', color: 'var(--dim)', 'text-align': 'center', 'font-size': '11px'
    } }, [document.createTextNode('에너지 분할 데이터 없음 (impactor trajectories 미존재)')]));
    return;
  }

  // Summary line
  const medPct = ((summary.median_absorption_pct == null ? 0 : (Number(summary.median_absorption_pct) || 0)) * 100).toFixed(1);
  const maxPid = summary.max_absorption_pos_id || '-';
  const maxPct = ((summary.max_absorption_pct == null ? 0 : (Number(summary.max_absorption_pct) || 0)) * 100).toFixed(1);
  const minPid = summary.min_absorption_pos_id || '-';
  const minPct = ((summary.min_absorption_pct == null ? 0 : (Number(summary.min_absorption_pct) || 0)) * 100).toFixed(1);
  const totKE = (summary.ke_total_initial == null ? 0 : (Number(summary.ke_total_initial) || 0));

  const mkChip = (label, val, color) => el('span', { class: 'doe-ep-chip', style: {
    display: 'inline-flex', 'align-items': 'baseline', gap: '6px',
    padding: '5px 10px', 'border-radius': '4px',
    background: 'rgba(255,255,255,0.03)', border: '1px solid var(--line)',
    'font-size': '10px', color: 'var(--dim)', 'letter-spacing': '0.5px'
  } }, [
    document.createTextNode(label),
    el('strong', { style: { color: color || 'var(--fg)', 'font-weight': 700 } },
      [document.createTextNode(val)])
  ]);

  sumRoot.appendChild(mkChip('MEDIAN 흡수율', medPct + '%', 'var(--good)'));
  sumRoot.appendChild(mkChip('최대 흡수', maxPid + ' (' + maxPct + '%)', 'var(--warn)'));
  sumRoot.appendChild(mkChip('최소 흡수', minPid + ' (' + minPct + '%)', 'var(--accent)'));
  sumRoot.appendChild(mkChip('총 초기 KE', fmt(totKE, 2) + ' ' + ueng, 'var(--fg)'));

  // Sort by absorption_pct desc.
  parts.sort((a, b) => (b.absorption_pct == null ? 0 : (Number(b.absorption_pct) || 0)) - (a.absorption_pct == null ? 0 : (Number(a.absorption_pct) || 0)));

  parts.forEach(p => {
    const pct = (p.absorption_pct == null ? 0 : (Number(p.absorption_pct) || 0));
    const pctTxt = (pct * 100).toFixed(1) + '%';
    const beh = p.behavior_class || 'unknown';
    const behColor = (typeof DOE_BEHAVIOR_COLOR !== 'undefined'
      ? (DOE_BEHAVIOR_COLOR[beh] || '#5c6383') : '#5c6383');

    const row = el('div', { class: 'doe-ep-row', 'data-pos': p.pos_id });

    // Pos id + behavior dot
    const lbl = el('div', { class: 'doe-ep-lbl' }, [
      el('span', { class: 'doe-ep-dot', style: { background: behColor } }),
      document.createTextNode(p.pos_id)
    ]);

    // Bar wrapper
    const wAbs = Math.max(0, Math.min(100, pct * 100));
    const wRet = 100 - wAbs;
    const barWrap = el('div', { class: 'doe-ep-bar' }, [
      el('div', { class: 'doe-ep-seg doe-ep-abs', style: { width: wAbs.toFixed(2) + '%' } }, [
        wAbs > 12 ? el('span', { class: 'doe-ep-seg-lbl' },
          [document.createTextNode(pctTxt)]) : null
      ].filter(Boolean)),
      el('div', { class: 'doe-ep-seg doe-ep-ret', style: { width: wRet.toFixed(2) + '%' } }, [
        wRet > 14 ? el('span', { class: 'doe-ep-seg-lbl' },
          [document.createTextNode((100 - pct * 100).toFixed(1) + '%')]) : null
      ].filter(Boolean))
    ]);

    // Right metrics
    const rightVal = el('div', { class: 'doe-ep-right' }, [
      el('span', { class: 'doe-ep-pct' }, [document.createTextNode(pctTxt)]),
      el('span', { class: 'doe-ep-ke' },
        [document.createTextNode('init ' + fmt((p.ke_initial == null ? 0 : (Number(p.ke_initial) || 0)), 2) + ' ' + ueng)])
    ]);

    // Tooltip
    row.title = [
      'POS: ' + p.pos_id,
      'Behavior: ' + beh,
      'KE initial : ' + fmt((p.ke_initial == null ? 0 : (Number(p.ke_initial) || 0)), 3) + ' ' + ueng,
      'KE absorbed: ' + fmt((p.ke_absorbed == null ? 0 : (Number(p.ke_absorbed) || 0)), 3) + ' ' + ueng +
        '  (' + (pct * 100).toFixed(2) + '%)',
      'KE retained: ' + fmt((p.ke_retained == null ? 0 : (Number(p.ke_retained) || 0)), 3) + ' ' + ueng +
        '  (' + ((1 - pct) * 100).toFixed(2) + '%)'
    ].join('\n');

    row.appendChild(lbl);
    row.appendChild(barWrap);
    row.appendChild(rightVal);

    row.addEventListener('click', () => {
      if (typeof DOE_STATE !== 'undefined') {
        DOE_STATE.active_pos = p.pos_id;
        if (typeof _doeRenderHeatmap === 'function') _doeRenderHeatmap(doe);
        if (typeof _doeRenderRanking === 'function') _doeRenderRanking(doe);
      }
    });

    root.appendChild(row);
  });
}

// === ADV_JS_FUNCTIONS_INSERT_HERE ===
// Workflow-added _doeRenderXxx render functions are inserted ABOVE this line.

const DOE_STATE = { metric: 'peak_g', sort: 'value', active_pos: null };

function _doeUnitForMetric(key) {
  return ({
    peak_g: _u('acc'),
    peak_stress: _u('stress'),
    peak_strain: '',
    peak_disp: _u('disp'),
    peak_vel: _u('vel')
  })[key] || '';
}

function _doeMetricLabel(key) {
  return ({
    peak_g: 'PEAK G',
    peak_stress: 'PEAK σ',
    peak_strain: 'PEAK ε',
    peak_disp: 'PEAK d',
    peak_vel: 'PEAK v'
  })[key] || key;
}

function _doePartName(pid) {
  const p = PART_BY_ID[pid];
  if (!p) return 'part_' + pid;
  // shorten 'Group\\Name' to last token
  const nm = String(p.name || '');
  const tail = nm.split(/[\\/]/).pop();
  return tail || nm || ('part_' + pid);
}

function initDoeAnalysis() {
  const doe = DATA.doe_analysis;
  const nav = document.getElementById('navS5');
  const sec = document.getElementById('s5');
  if (!doe || !doe.positions || !doe.positions.length) {
    if (nav) nav.style.display = 'none';
    if (sec) sec.style.display = 'none';
    return;
  }
  if (sec) sec.style.display = '';
  // default metric: first available
  if (doe.metrics && doe.metrics.length > 0) {
    DOE_STATE.metric = doe.metrics[0].key;
  }

  _doeBuildMetricButtons(doe);
  _doeBuildKpiStrip(doe);
  _doeRenderAll(doe);

  // sort buttons
  document.querySelectorAll('[data-doe-sort]').forEach(b => b.addEventListener('click', function () {
    document.querySelectorAll('[data-doe-sort]').forEach(x => x.classList.remove('active'));
    b.classList.add('active');
    DOE_STATE.sort = b.dataset.doeSort;
    _doeRenderRanking(doe);
  }));
}

function _doeBuildMetricButtons(doe) {
  const host = document.getElementById('doe-metric-buttons');
  if (!host) return;
  host.innerHTML = '';
  (doe.metrics || []).forEach((m, i) => {
    const b = el('button', {
      class: 'btn' + (m.key === DOE_STATE.metric ? ' active' : ''),
      'data-doe-metric': m.key
    }, m.label);
    b.addEventListener('click', () => {
      DOE_STATE.metric = m.key;
      host.querySelectorAll('button').forEach(x => x.classList.toggle('active', x.dataset.doeMetric === m.key));
      _doeRenderAll(doe);
    });
    host.appendChild(b);
  });
}

function _doeBuildKpiStrip(doe) {
  const host = document.getElementById('doe-kpi-strip');
  if (!host) return;
  host.innerHTML = '';
  const n_pos = (doe.positions || []).length;
  // worst peak_g across all positions
  let worst_g = 0;
  let worst_s = 0;
  Object.values(doe.position_metrics || {}).forEach(pm => {
    if ((pm.peak_g_max || 0) > worst_g) worst_g = pm.peak_g_max;
    if ((pm.peak_stress_max || 0) > worst_s) worst_s = pm.peak_stress_max;
  });
  const tka = doe.total_ke_absorbed || [];
  const mean_abs = tka.length ? tka.reduce((a, b) => a + b, 0) / tka.length : 0;
  const bcounts = doe.behavior_class_counts || {};
  const bk = Object.keys(bcounts);
  const total_b = bk.reduce((a, k) => a + bcounts[k], 0) || 1;

  const mkCell = (label, valHtml) => {
    const cell = el('div', { class: 'k' });
    cell.appendChild(el('div', { class: 'v' })).innerHTML = valHtml;
    cell.appendChild(el('div', { class: 'l' }, label));
    return cell;
  };

  host.appendChild(mkCell('TOTAL POSITIONS', String(n_pos) + '<span class="u">pos</span>'));
  host.appendChild(mkCell('MAX PEAK G', fmt(worst_g, 0) + '<span class="u">' + _u('acc') + '</span>'));
  host.appendChild(mkCell('MAX STRESS', fmt(worst_s, 1) + '<span class="u">' + _u('stress') + '</span>'));

  // behavior distribution mini bar
  const bbCell = el('div', { class: 'k' });
  const bbVal = el('div', { class: 'v', style: { fontSize: '12px' } });
  const bar = el('div', { class: 'doe-kpi-bb' });
  bk.forEach(k => {
    const w = Math.round(160 * bcounts[k] / total_b);
    bar.appendChild(el('span', { style: { width: w + 'px', background: DOE_BEHAVIOR_COLOR[k] || '#5c6383' }, title: k + ': ' + bcounts[k] }));
  });
  bbVal.appendChild(bar);
  bbCell.appendChild(bbVal);
  bbCell.appendChild(el('div', { class: 'l' }, 'BEHAVIOR DIST'));
  host.appendChild(bbCell);

  host.appendChild(mkCell('AVG KE 흡수율', (mean_abs * 100).toFixed(1) + '<span class="u">%</span>'));
}

function _doeRenderAll(doe) {
  // update top-level labels
  const lbl = _doeMetricLabel(DOE_STATE.metric);
  const heatLbl = document.getElementById('doe-heat-metric-lbl');
  if (heatLbl) heatLbl.textContent = lbl;
  const valLbl = document.getElementById('doe-rank-val-lbl');
  if (valLbl) {
    const u = _doeUnitForMetric(DOE_STATE.metric);
    valLbl.innerHTML = lbl + (u ? ('<br><span style="font-weight:400;color:var(--dim);text-transform:none">' + u + '</span>') : '');
  }
  const xUnit = document.getElementById('doe-rank-x-unit'); if (xUnit) xUnit.textContent = _uSuffix('disp');
  const yUnit = document.getElementById('doe-rank-y-unit'); if (yUnit) yUnit.textContent = _uSuffix('disp');
  const pUnit = document.getElementById('doe-rank-pen-unit'); if (pUnit) pUnit.textContent = _uSuffix('disp');

  _doeRenderHeatmap(doe);
  _doeRenderRanking(doe);
  _doeRenderPartPosMatrix(doe);
  _doeRenderTrajMM(doe);
  _doeRenderEnvelope(doe);
  _doeRenderFailureRisk(doe);
  _doeRenderCorrNetwork(doe);
  _doeRenderTOA(doe);
  _doeRenderIdwPredictor(doe);
  _doeRenderParetoSeverity(doe);
  _doeRenderEnergyPartition(doe);
  // === ADV_BOOT_CALLS_INSERT_HERE ===
  // Workflow-added _doeRenderXxx(doe) calls are inserted ABOVE this line.
}

function _doeP95(arr) {
  if (!arr || !arr.length) return 0;
  const s = arr.slice().sort((a, b) => a - b);
  const k = Math.max(0, Math.min(1, 0.95)) * (s.length - 1);
  const lo = Math.floor(k), hi = Math.ceil(k);
  if (lo === hi) return s[lo];
  return s[lo] * (1 - (k - lo)) + s[hi] * (k - lo);
}

function _doeMetricValueForPos(doe, pos_id) {
  const pm = (doe.position_metrics || {})[pos_id] || {};
  return pm[DOE_STATE.metric + '_max'] || 0;
}

function _doeMetricValuesAll(doe) {
  return (doe.positions || []).map(p => _doeMetricValueForPos(doe, p.pos_id));
}

function _doeRenderHeatmap(doe) {
  const root = document.getElementById('doe-heatmap-svg');
  if (!root) return;
  while (root.firstChild) root.removeChild(root.firstChild);
  const grid = doe.grid;
  if (!grid) {
    root.appendChild(svg('text', { x: 180, y: 180, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 11 }, [document.createTextNode('No grid metadata')]));
    return;
  }
  const vbW = 540, vbH = 540;
  root.setAttribute('viewBox', '0 0 ' + vbW + ' ' + vbH);
  root.setAttribute('preserveAspectRatio', 'xMidYMid meet');
  root.appendChild(svg('rect', { x: 0, y: 0, width: vbW, height: vbH, fill: '#0e1320', rx: 4 }));

  const padL = 60, padR = 14, padT = 24, padB = 36;
  const plotW = vbW - padL - padR, plotH = vbH - padT - padB;
  const nx = grid.nx, ny = grid.ny;
  const cellW = plotW / nx, cellH = plotH / ny;

  const vals = _doeMetricValuesAll(doe).filter(v => v > 0);
  const vmax = _doeP95(vals) || Math.max(...vals, 1);

  (doe.positions || []).forEach(pos => {
    const v = _doeMetricValueForPos(doe, pos.pos_id);
    const t = vmax > 0 ? Math.min(1, v / vmax) : 0;
    const fill = v > 0 ? gColor(t) : '#1a1e2e';
    // row 0 = lowest y → plot bottom; flip y
    const cx = padL + pos.col * cellW;
    const cy = padT + (ny - 1 - pos.row) * cellH;
    const g = svg('g', { class: 'doe-cell' + (DOE_STATE.active_pos === pos.pos_id ? ' active' : ''), 'data-pos': pos.pos_id });
    const rect = svg('rect', {
      x: cx + 1, y: cy + 1, width: cellW - 2, height: cellH - 2,
      fill: fill, stroke: 'rgba(255,255,255,0.05)', rx: 2
    });
    rect.addEventListener('click', () => {
      DOE_STATE.active_pos = pos.pos_id;
      _doeRenderHeatmap(doe);
      _doeRenderRanking(doe);
    });
    const pm = (doe.position_metrics || {})[pos.pos_id] || {};
    const short = ({ peak_g: 'g', peak_stress: 's', peak_strain: 'e', peak_disp: 'd', peak_vel: 'v' })[DOE_STATE.metric] || 'g';
    const wpid = pm['worst_part_id_' + short];
    const wnm = wpid != null ? _doePartName(wpid) : '';
    rect.appendChild(svg('title', null, [document.createTextNode(pos.pos_id + '\nx=' + pos.x.toFixed(1) + ' y=' + pos.y.toFixed(1) + '\nvalue=' + fmt(v, 1) + '\nworst part: ' + wnm)]));
    g.appendChild(rect);
    g.appendChild(svg('text', {
      x: cx + cellW / 2, y: cy + cellH / 2 - 2,
      'text-anchor': 'middle', fill: '#0a0c14', 'font-size': 10, 'font-weight': 700,
      class: 'doe-cell-label'
    }, [document.createTextNode(fmt(v, 1))]));
    if (wnm) {
      g.appendChild(svg('text', {
        x: cx + cellW / 2, y: cy + cellH / 2 + 11,
        'text-anchor': 'middle', fill: '#0a0c14', 'font-size': 8,
        class: 'doe-cell-label'
      }, [document.createTextNode(wnm.slice(0, 12))]));
    }
    root.appendChild(g);
  });

  // axis labels
  const bb = grid.bbox; // [xmin, ymin, xmax, ymax]
  root.appendChild(svg('text', { x: padL, y: padT - 8, fill: '#5c6383', 'font-size': 9 }, [document.createTextNode('X: ' + bb[0].toFixed(1) + ' → ' + bb[2].toFixed(1))]));
  root.appendChild(svg('text', { x: padL, y: vbH - padB + 22, fill: '#5c6383', 'font-size': 9 }, [document.createTextNode('Y: ' + bb[1].toFixed(1) + ' → ' + bb[3].toFixed(1))]));
  root.appendChild(svg('text', { x: vbW / 2, y: vbH - 8, fill: '#aab2cf', 'font-size': 10, 'text-anchor': 'middle' }, [document.createTextNode('Grid ' + nx + '×' + ny + '   metric: ' + _doeMetricLabel(DOE_STATE.metric))]));
}

function _doeRenderRanking(doe) {
  const tb = document.querySelector('#doe-rank-tbl tbody');
  if (!tb) return;
  tb.innerHTML = '';
  const rows = (doe.positions || []).slice();
  if (DOE_STATE.sort === 'pos') {
    rows.sort((a, b) => String(a.pos_id).localeCompare(String(b.pos_id)));
  } else {
    rows.sort((a, b) => _doeMetricValueForPos(doe, b.pos_id) - _doeMetricValueForPos(doe, a.pos_id));
  }
  const short = ({ peak_g: 'g', peak_stress: 's', peak_strain: 'e', peak_disp: 'd', peak_vel: 'v' })[DOE_STATE.metric] || 'g';
  rows.forEach((p, i) => {
    const pm = (doe.position_metrics || {})[p.pos_id] || {};
    const v = _doeMetricValueForPos(doe, p.pos_id);
    const wpid = pm['worst_part_id_' + short];
    const wnm = wpid != null ? _doePartName(wpid) : '-';
    const tsum = (doe.trajectory_summary || {})[p.pos_id] || {};
    const beh = tsum.behavior_class || 'unknown';
    const ke_ret = tsum.ke_retention;
    const pen = tsum.max_penetration_depth;
    const tr = el('tr', {});
    if (DOE_STATE.active_pos === p.pos_id) tr.style.background = 'rgba(77,214,255,0.08)';
    tr.appendChild(el('td', { class: 'tl b' }, String(i + 1)));
    tr.appendChild(el('td', { class: 'tl' }, p.pos_id));
    tr.appendChild(el('td', { class: 'num' }, p.x.toFixed(1)));
    tr.appendChild(el('td', { class: 'num' }, p.y.toFixed(1)));
    const bcell = el('td', { class: 'tl' });
    bcell.appendChild(el('span', { class: 'bbadge ' + beh }, beh));
    tr.appendChild(bcell);
    tr.appendChild(el('td', { class: 'num' }, fmt(v, 1)));
    tr.appendChild(el('td', { class: 'tl dim' }, wnm));
    tr.appendChild(el('td', { class: 'num' }, ke_ret != null ? (ke_ret * 100).toFixed(1) + '%' : '-'));
    tr.appendChild(el('td', { class: 'num' }, pen != null ? fmt(pen, 2) : '-'));
    tr.addEventListener('click', () => {
      DOE_STATE.active_pos = p.pos_id;
      _doeRenderHeatmap(doe);
      _doeRenderRanking(doe);
    });
    tr.style.cursor = 'pointer';
    tb.appendChild(tr);
  });
}

function _doeRenderPartPosMatrix(doe) {
  const root = document.getElementById('doe-pp-svg');
  if (!root) return;
  while (root.firstChild) root.removeChild(root.firstChild);

  const mat = doe.peak_g_matrix || {};
  const positions = (doe.positions || []).slice().sort((a, b) => a.doe_index - b.doe_index);
  // top 15 parts by max(peak_g)
  const partRows = Object.keys(mat).map(pid => {
    const row = mat[pid];
    let mx = 0;
    Object.keys(row).forEach(k => { if (row[k] > mx) mx = row[k]; });
    return { pid: parseInt(pid, 10), max: mx };
  });
  partRows.sort((a, b) => b.max - a.max);
  const topParts = partRows.slice(0, 15);
  if (!topParts.length || !positions.length) {
    root.setAttribute('viewBox', '0 0 600 80');
    root.appendChild(svg('text', { x: 300, y: 40, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 11 }, [document.createTextNode('No part×position data')]));
    return;
  }

  const padL = 160, padR = 8, padT = 28, padB = 8;
  const cellW = 26, cellH = 22;
  const W = padL + padR + positions.length * cellW;
  const H = padT + padB + topParts.length * cellH;
  root.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
  root.setAttribute('preserveAspectRatio', 'xMinYMid meet');
  root.setAttribute('width', W);
  root.setAttribute('height', H);

  let gmax = 0;
  topParts.forEach(p => {
    const row = mat[p.pid] || {};
    Object.keys(row).forEach(k => { if (row[k] > gmax) gmax = row[k]; });
  });
  const norm = _doeP95(topParts.flatMap(p => Object.values(mat[p.pid] || {}))) || gmax || 1;

  // column headers (pos_id)
  positions.forEach((p, ci) => {
    const cx = padL + ci * cellW + cellW / 2;
    root.appendChild(svg('text', { x: cx, y: padT - 8, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 8, transform: 'rotate(-60 ' + cx + ' ' + (padT - 8) + ')' }, [document.createTextNode(p.pos_id)]));
  });

  topParts.forEach((p, ri) => {
    const cy = padT + ri * cellH;
    root.appendChild(svg('text', { x: padL - 8, y: cy + cellH / 2 + 3, 'text-anchor': 'end', fill: '#aab2cf', 'font-size': 10 }, [document.createTextNode(_doePartName(p.pid))]));
    const row = mat[p.pid] || {};
    positions.forEach((pos, ci) => {
      const v = row[pos.pos_id] || 0;
      const t = norm > 0 ? Math.min(1, v / norm) : 0;
      const fill = v > 0 ? gColor(t) : '#1a1e2e';
      const cx = padL + ci * cellW;
      const r = svg('rect', { x: cx + 1, y: cy + 1, width: cellW - 2, height: cellH - 2, fill: fill, rx: 2 });
      r.appendChild(svg('title', null, [document.createTextNode(_doePartName(p.pid) + ' @ ' + pos.pos_id + ' = ' + fmt(v, 1) + ' ' + _u('acc'))]));
      root.appendChild(r);
    });
  });
}

function _doeRenderTrajMM(doe) {
  const host = document.getElementById('doe-traj-mm');
  if (!host) return;
  host.innerHTML = '';
  const grid = doe.grid;
  const nx = grid ? grid.nx : Math.ceil(Math.sqrt((doe.positions || []).length));
  const ny = grid ? grid.ny : nx;
  host.style.gridTemplateColumns = 'repeat(' + nx + ', 1fr)';
  const curves = doe.trajectory_ke_curves || {};
  const tsums = doe.trajectory_summary || {};
  const worst_pid = doe.worst_position ? doe.worst_position.pos_id : null;

  // Arrange cells by (row, col) – row 0 at bottom visually so iterate top-to-bottom rows = (ny-1)..0.
  // For irregular grids (partial DOE, custom layouts), multiple positions
  // could quantize to the same (row,col) — surface the collision in the
  // console rather than silently overwriting.
  const byCell = {};
  (doe.positions || []).forEach(p => {
    const k = (ny - 1 - p.row) + '_' + p.col;
    if (byCell[k]) {
      console.warn('DOE traj grid collision at cell', k, 'positions:', byCell[k].pos_id, '<->', p.pos_id);
    }
    byCell[k] = p;
  });

  for (let r = 0; r < ny; r++) {
    for (let c = 0; c < nx; c++) {
      const cellWrap = el('div', { class: 'doe-traj-cell' });
      const p = byCell[r + '_' + c];
      if (!p) { cellWrap.style.background = 'transparent'; cellWrap.style.borderColor = 'transparent'; host.appendChild(cellWrap); continue; }
      const tsum = tsums[p.pos_id] || {};
      const beh = tsum.behavior_class || 'unknown';
      const color = DOE_BEHAVIOR_COLOR[beh] || '#5c6383';
      const curve = curves[p.pos_id];
      const isWorst = p.pos_id === worst_pid;
      if (isWorst) {
        cellWrap.classList.add('worst');
        cellWrap.appendChild(el('div', { class: 'star' }, '★'));
      }
      // mini svg
      const W = 90, H = 56;
      const s = svg('svg', { viewBox: '0 0 ' + W + ' ' + H, preserveAspectRatio: 'none' });
      // Native hover tooltip on the whole cell — peak KE, behavior, retention.
      const _tk = (curve && curve.ke && curve.ke.length) ? Math.max.apply(null, curve.ke) : 0;
      const _retPct = (tsum.ke_retention != null) ? (tsum.ke_retention * 100).toFixed(0) + '%' : '?';
      const _pen = (tsum.max_penetration_depth != null) ? tsum.max_penetration_depth : '?';
      const _tt = svg('title', null);
      _tt.appendChild(document.createTextNode(
        p.pos_id + ' (' + p.x + ', ' + p.y + ')' +
        '\\n behavior: ' + beh +
        '\\n peak KE: ' + (_tk ? _tk.toExponential(2) : '–') +
        '\\n KE retention: ' + _retPct +
        '\\n max penetration: ' + _pen
      ));
      s.appendChild(_tt);
      s.appendChild(svg('rect', { x: 0, y: 0, width: W, height: H, fill: '#0e1320', rx: 2 }));
      if (curve && curve.t && curve.t.length > 1) {
        const t0 = curve.t[0], t1 = curve.t[curve.t.length - 1];
        let kmax = 0, kmin = Infinity;
        for (const k of curve.ke) { if (k > kmax) kmax = k; if (k < kmin) kmin = k; }
        if (!isFinite(kmin)) kmin = 0;
        const dT = (t1 - t0) || 1;
        const dK = (kmax - kmin) || 1;
        let d = '';
        for (let i = 0; i < curve.t.length; i++) {
          const x = ((curve.t[i] - t0) / dT) * W;
          const y = H - ((curve.ke[i] - kmin) / dK) * H;
          d += (i ? 'L' : 'M') + x.toFixed(1) + ' ' + y.toFixed(1);
        }
        s.appendChild(svg('path', { d: d, fill: 'none', stroke: color, 'stroke-width': 1.3 }));
      } else {
        s.appendChild(svg('text', { x: W / 2, y: H / 2 + 3, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 8 }, [document.createTextNode('no traj')]));
      }
      cellWrap.appendChild(s);
      const lbl = el('div', { class: 'tc-lbl' });
      lbl.appendChild(el('span', null, p.pos_id));
      lbl.appendChild(el('span', { style: { color: color } }, beh));
      cellWrap.appendChild(lbl);
      host.appendChild(cellWrap);
    }
  }
}

function _doeRenderEnvelope(doe) {
  const host = document.getElementById('doe-env-wrap');
  if (!host) return;
  host.innerHTML = '';
  const stats = doe.per_part_stats || {};
  const arr = Object.keys(stats).map(pid => {
    const s = stats[pid];
    return {
      pid: parseInt(pid, 10), name: s.part_name,
      p5: s.p5, p50: s.p50, p95: s.p95, mean: s.mean, max: s.max
    };
  });
  arr.sort((a, b) => b.p95 - a.p95);
  const top = arr.slice(0, 12);
  if (!top.length) {
    host.appendChild(el('div', { class: 'doe-empty' }, 'No per-part stats'));
    return;
  }
  const xmax = Math.max.apply(null, top.map(t => t.p95)) || 1;

  top.forEach(t => {
    const row = el('div', { class: 'doe-env-row' });
    row.appendChild(el('div', { class: 'nm' }, _doePartName(t.pid)));
    const wis = el('div', { class: 'wis' });
    const W = 240, H = 14;
    const s = svg('svg', { viewBox: '0 0 ' + W + ' ' + H, preserveAspectRatio: 'none' });
    s.appendChild(svg('rect', { x: 0, y: 0, width: W, height: H, fill: '#1a1e2e', rx: 2 }));
    const x5 = (t.p5 / xmax) * W;
    const x50 = (t.p50 / xmax) * W;
    const x95 = (t.p95 / xmax) * W;
    const xMean = (t.mean / xmax) * W;
    // whisker line
    s.appendChild(svg('line', { x1: x5, y1: H / 2, x2: x95, y2: H / 2, stroke: '#4dd6ff', 'stroke-width': 2 }));
    // p5 tick
    s.appendChild(svg('line', { x1: x5, y1: 2, x2: x5, y2: H - 2, stroke: '#aab2cf', 'stroke-width': 1 }));
    // p95 tick
    s.appendChild(svg('line', { x1: x95, y1: 2, x2: x95, y2: H - 2, stroke: '#aab2cf', 'stroke-width': 1 }));
    // p50 marker
    s.appendChild(svg('circle', { cx: x50, cy: H / 2, r: 3, fill: '#b46eff' }));
    // mean marker
    s.appendChild(svg('circle', { cx: xMean, cy: H / 2, r: 2, fill: '#ff5e84' }));
    s.appendChild(svg('title', null, [document.createTextNode('P5=' + fmt(t.p5, 1) + '  P50=' + fmt(t.p50, 1) + '  P95=' + fmt(t.p95, 1) + '  mean=' + fmt(t.mean, 1))]));
    wis.appendChild(s);
    row.appendChild(wis);
    const ratio = (t.p5 > 0) ? (t.p95 / t.p5) : (t.p95 > 0 ? Infinity : 0);
    row.appendChild(el('div', { class: 'rt' }, isFinite(ratio) ? ratio.toFixed(1) + '×' : '∞'));
    host.appendChild(row);
  });
}

function boot() {
  applyUnitLabels();
  fillHeroKpi();
  initImpactor();
  initDoeBreakdown();
  renderAll();
  renderFindings();
  initEnergyGraph();
  initSunburst();
  initSankey();
  initTimeForceHeatmap();
  initConservation();
  initBounceVectorMap();
  initTrajectoryClustering();
  initPhaseDiagram();
  initContactTimeline();
  initTrajectoryBundle3D();
  initPerPartPeakG();
  initDoeAnalysis();
  wireControlBar();
  initReveal();
  initNav();
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
else boot();
"""


# ---------------------------------------------------------------------------
# Top-level generator
# ---------------------------------------------------------------------------


def generate_html(report: ImpactReport) -> str:
    """Generate the full single-file HTML report.

    The output is fully self-contained — no external scripts, stylesheets,
    fonts, or images. JavaScript reads from one ``const DATA`` payload that
    is JSON-encoded inline.
    """
    payload = _build_payload(report)
    payload["meta"]["_n_faces"] = len(payload["faces"])
    payload["meta"]["_n_runs"] = len({(r["face"], r["pos_id"]) for r in payload["results"]})

    kpi = payload["kpi"]
    worst = kpi["worst"]

    page1 = (
        _PAGE1
        .replace("__N_FACES__", str(kpi["n_faces"]))
        .replace("__N_POSITIONS__", str(kpi["n_positions"]))
        .replace("__N_PARTS__", str(kpi["n_parts"]))
        .replace("__N_PAIRS__", str(kpi["n_pairs"]))
        .replace("__WORST_LINE__", _esc(f"{worst['face']} · X {worst['x']:.1f} / Y {worst['y']:.1f}"))
        .replace("__WORST_PART_LINE__", _esc(f"{worst['g']:.0f} G  ON  {worst['part_name']}"))
        .replace("__WORST_G__", f"{worst['g']:.0f}")
        .replace("__WORST_S__", f"{kpi['worst_s']:.0f}")
        .replace("__N_CRIT__", str(kpi["n_critical"]))
        .replace("__N_SAFE__", str(kpi["n_safe"]))
        .replace("__DISS_PCT__", f"{kpi['diss_pct']:.1f}")
        .replace("__IMP_SUB__", _esc(payload["meta"]["impactor"]["type"]))
    )

    topbar = _build_topbar(payload["meta"], payload.get("unit_labels"))
    js = _JS.replace("__PAYLOAD__", json.dumps(payload, cls=_Encoder, separators=(",", ":")))

    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"ko\">\n"
        "<head>\n"
        "<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"<title>{_esc(payload['meta']['project'])} — Multi-Face Impact Report</title>\n"
        "<style>\n" + _CSS + "\n</style>\n"
        "</head>\n"
        "<body>\n"
        + topbar
        + page1
        + _PAGE2
        + _PAGE3
        + _PAGE4
        + _PAGE5
        + "<script>\n" + js + "\n</script>\n"
        "</body>\n</html>\n"
    )
