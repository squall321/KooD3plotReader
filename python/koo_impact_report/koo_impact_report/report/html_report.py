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


def _r4(v):
    """Round numeric value to <=4 significant figures, dropping trailing zeros.

    Preserves None / non-finite / non-numeric inputs unchanged. Uses the ``%.4g``
    format which respects magnitude (works equally for 0.000123 and 1234567).
    """
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return v
    if math.isnan(f) or math.isinf(f):
        return 0.0
    if f == 0.0:
        return 0.0
    return float(f"{f:.4g}")


def _sparse_matrix(d, thresh_ratio=0.01):
    """Encode a dict-of-dict numeric matrix sparsely when >=30% of entries are
    zero (or below ``thresh_ratio * max_abs``).

    Returns either the original dense dict or
    ``{"_sparse": True, "rows": [[row_key, col_key, value], ...]}``.
    Non-numeric values are always kept (treated as significant).
    """
    if not isinstance(d, dict) or not d:
        return d
    # Gather all numeric magnitudes to compute threshold
    max_abs = 0.0
    total = 0
    for _rk, row in d.items():
        if not isinstance(row, dict):
            return d
        for _ck, v in row.items():
            total += 1
            try:
                f = abs(float(v))
                if f > max_abs:
                    max_abs = f
            except (TypeError, ValueError):
                pass
    if total == 0:
        return d
    thresh = max_abs * thresh_ratio
    # Count significant entries
    sig_rows = []
    n_drop = 0
    for rk, row in d.items():
        for ck, v in row.items():
            try:
                f = float(v)
                if abs(f) <= thresh:
                    n_drop += 1
                    continue
            except (TypeError, ValueError):
                pass
            sig_rows.append([rk, ck, v])
    if n_drop / total < 0.30:
        return d
    return {"_sparse": True, "rows": sig_rows}


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
    """Build IDW-interpolated risk surfaces (peak_g, peak_stress) on a 31x31
    fine grid covering the DOE bbox. Returns None when grid metadata or
    measurement points are unavailable.

    Pure-Python (no numpy) IDW with power p=2. Exact reproduction at
    measurement points (zero distance fallback). Payload kept compact:
    ~7 KB per metric, rounded to 4 sig-figs.
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
            "x": round(x, 1),
            "y": round(y, 1),
            "peak_g": _r4(pos_g.get(pid, 0.0)),
            "peak_stress": _r4(pos_s.get(pid, 0.0)),
        })
    if len(measured) < 2:
        return None

    # IDW interpolation, p=2 — 31x31 grid (still smooth visually, ~57% smaller)
    NX = 31
    NY = 31
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

    # Round to keep payload small (4 sig-figs)
    grid_g_r = [_r4(v) for v in grid_g]
    grid_s_r = [_r4(v) for v in grid_s]

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

    # Leave-One-Out cross-validation on peak_g (same p=2 IDW, same snap radius)
    loo_validation = None
    if len(samples) >= 3:
        per_point = []
        sq_errs = []
        err_pcts = []
        max_err_abs = -1.0
        max_err_pos_id = None
        for i_drop, m in enumerate(measured):
            sx_i, sy_i, actual_g, _ = samples[i_drop]
            wsum = 0.0
            vg = 0.0
            exact = -1
            for k, (sx, sy, sg, _ss) in enumerate(samples):
                if k == i_drop:
                    continue
                ddx = sx_i - sx
                ddy = sy_i - sy
                d2 = ddx * ddx + ddy * ddy
                if d2 <= eps2:
                    exact = k
                    break
                w = 1.0 / d2
                wsum += w
                vg += w * sg
            if exact >= 0:
                predicted = samples[exact][2]
            elif wsum > 0:
                predicted = vg / wsum
            else:
                predicted = 0.0
            err_abs = abs(predicted - actual_g)
            denom = actual_g if actual_g > 1e-12 else 1e-12
            err_pct = err_abs / denom * 100.0
            sq_errs.append(err_abs * err_abs)
            err_pcts.append(err_pct)
            per_point.append({
                "pos_id": m["pos_id"],
                "x": m["x"],
                "y": m["y"],
                "actual": _r4(actual_g),
                "predicted": _r4(predicted),
                "error_abs": _r4(err_abs),
                "error_pct": _r4(err_pct),
            })
            if err_abs > max_err_abs:
                max_err_abs = err_abs
                max_err_pos_id = m["pos_id"]
        rmse_peak_g = math.sqrt(sum(sq_errs) / len(sq_errs)) if sq_errs else 0.0
        median_err_pct = statistics.median(err_pcts) if err_pcts else 0.0
        loo_validation = {
            "rmse_peak_g": _r4(rmse_peak_g),
            "median_err_pct": _r4(median_err_pct),
            "max_error_pos_id": max_err_pos_id,
            "per_point": per_point,
        }

    return {
        "grid_fine": {
            "nx_fine": NX,
            "ny_fine": NY,
            "bbox": [round(xmin, 1), round(ymin, 1), round(xmax, 1), round(ymax, 1)],
            "peak_g": grid_g_r,
            "peak_stress": grid_s_r,
        },
        "max_sample_idx": {
            "peak_g": max_idx_g,
            "peak_stress": max_idx_s,
        },
        "measured_points": measured,
        "power": 2,
        "loo_validation": loo_validation,
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
                }, "unit_acc": ""}

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
    unit_acc = unit_labels.get("acc", "") or ""

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

def _pid_cast(pid):
    """Cast pos_id to int when possible, else keep original (e.g. DOE string IDs)."""
    try:
        return int(pid)
    except (ValueError, TypeError):
        return pid


def _fft_dominant_freq(times, signal, f_lo=10.0):
    """Return (f_dom_Hz, peak_amp, freqs, amps_normalized, fs) or None."""
    import numpy as np
    t = np.asarray(times, dtype=float)
    s = np.asarray(signal, dtype=float)
    if t.size < 8 or s.size < 8 or t.size != s.size:
        return None
    # finite values only
    mask = np.isfinite(t) & np.isfinite(s)
    if mask.sum() < 8:
        return None
    t = t[mask]
    s = s[mask]
    if np.allclose(s, 0.0):
        return None
    dts = np.diff(t)
    dts = dts[dts > 0]
    if dts.size < 4:
        return None
    dt = float(np.mean(dts))
    if not np.isfinite(dt) or dt <= 0:
        return None
    fs = 1.0 / dt
    # remove DC
    s = s - float(np.mean(s))
    if np.allclose(s, 0.0):
        return None
    # FFT
    N = s.size
    freqs = np.fft.rfftfreq(N, d=dt)
    spec = np.abs(np.fft.rfft(s))
    if spec.size == 0:
        return None
    peak = float(np.max(spec))
    if peak <= 0 or not np.isfinite(peak):
        return None
    amps_norm = spec / peak
    # dominant frequency search band
    f_hi = 0.5 * fs
    band = (freqs >= f_lo) & (freqs <= f_hi)
    if not band.any():
        return None
    idx_band = np.where(band)[0]
    sub_amps = spec[idx_band]
    if sub_amps.size == 0 or np.max(sub_amps) <= 0:
        return None
    j = int(np.argmax(sub_amps))
    f_dom = float(freqs[idx_band[j]])
    peak_amp = float(sub_amps[j])
    return f_dom, peak_amp, freqs, amps_norm, fs


def _downsample_spectrum(freqs, amps, max_bins=128):
    """Bin-average down to ≤max_bins, keep monotonic frequency axis."""
    import numpy as np
    n = freqs.size
    if n <= max_bins:
        return freqs.astype(float), amps.astype(float)
    # block-mean reduction
    factor = int(np.ceil(n / max_bins))
    new_n = n // factor
    if new_n < 2:
        return freqs.astype(float), amps.astype(float)
    f_trim = freqs[:new_n * factor].reshape(new_n, factor)
    a_trim = amps[:new_n * factor].reshape(new_n, factor)
    return f_trim.mean(axis=1), a_trim.max(axis=1)


def _build_fft_payload(report):
    """Aggregate FFT dominant frequencies per part across all positions."""
    import numpy as np
    parts_by_id = {p.part_id: p for p in getattr(report, "parts", [])}
    part_motions = getattr(report, "part_motions", {}) or {}

    # group by part_id
    by_part = {}
    for key, pm in part_motions.items():
        if not isinstance(key, tuple) or len(key) != 2:
            continue
        pos_id, part_id = key
        times = getattr(pm, "times", None)
        acc = getattr(pm, "acc_mag", None)
        if times is None or acc is None:
            continue
        res = _fft_dominant_freq(times, acc, f_lo=10.0)
        if res is None:
            continue
        f_dom, peak_amp, freqs, amps_norm, fs = res
        by_part.setdefault(part_id, []).append({
            "pos_id": _pid_cast(pos_id),
            "f_dom": f_dom,
            "peak_amp": peak_amp,
            "freqs": freqs,
            "amps_norm": amps_norm,
            "fs": fs,
        })

    per_part = {}
    all_fs = []
    n_positions_used = 0
    f_lo_used = 10.0
    f_hi_used = 0.0

    for part_id, entries in by_part.items():
        if not entries:
            continue
        f_doms = np.array([e["f_dom"] for e in entries], dtype=float)
        # pick the entry with the highest peak_amp for representative spectrum
        top = max(entries, key=lambda e: e["peak_amp"])
        ds_f, ds_a = _downsample_spectrum(top["freqs"], top["amps_norm"], max_bins=128)
        # round for payload size (4 sig-fig)
        ds_f = [_r4(float(x)) for x in ds_f.tolist()]
        ds_a = [_r4(float(x)) for x in ds_a.tolist()]
        info = parts_by_id.get(part_id)
        name = getattr(info, "part_name", None) or f"Part {part_id}"
        per_part[str(part_id)] = {
            "name": name,
            "n_samples_used": int(f_doms.size),
            "mean_f_dom_Hz": _r4(float(np.mean(f_doms))),
            "std_f_dom_Hz": _r4(float(np.std(f_doms))),
            "top_pos_id": _pid_cast(top["pos_id"]),
            "top_freq_Hz": _r4(float(top["f_dom"])),
            "top_amp": _r4(float(top["peak_amp"])),
            "spectrum": {"f": ds_f, "amp_normalized": ds_a},
        }
        all_fs.extend([e["fs"] for e in entries])
        n_positions_used += len(entries)
        f_hi_used = max(f_hi_used, 0.5 * max(e["fs"] for e in entries))

    summary = {
        "n_parts_with_data": len(per_part),
        "n_positions_used": int(n_positions_used),
        "fs_Hz": round(float(np.mean(all_fs)), 2) if all_fs else 0.0,
        "freq_band_Hz": [round(float(f_lo_used), 2), round(float(f_hi_used), 2)],
    }
    return {"per_part_dominant_freq": per_part, "summary": summary}

def _fft_dominant_freq(times, signal, f_lo=10.0):
    """Return (f_dom_Hz, peak_amp, freqs, amps_normalized, fs) or None."""
    import numpy as np
    t = np.asarray(times, dtype=float)
    s = np.asarray(signal, dtype=float)
    if t.size < 8 or s.size < 8 or t.size != s.size:
        return None
    # finite values only
    mask = np.isfinite(t) & np.isfinite(s)
    if mask.sum() < 8:
        return None
    t = t[mask]
    s = s[mask]
    if np.allclose(s, 0.0):
        return None
    dts = np.diff(t)
    dts = dts[dts > 0]
    if dts.size < 4:
        return None
    dt = float(np.mean(dts))
    if not np.isfinite(dt) or dt <= 0:
        return None
    fs = 1.0 / dt
    # remove DC
    s = s - float(np.mean(s))
    if np.allclose(s, 0.0):
        return None
    # FFT
    N = s.size
    freqs = np.fft.rfftfreq(N, d=dt)
    spec = np.abs(np.fft.rfft(s))
    if spec.size == 0:
        return None
    peak = float(np.max(spec))
    if peak <= 0 or not np.isfinite(peak):
        return None
    amps_norm = spec / peak
    # dominant frequency search band
    f_hi = 0.5 * fs
    band = (freqs >= f_lo) & (freqs <= f_hi)
    if not band.any():
        return None
    idx_band = np.where(band)[0]
    sub_amps = spec[idx_band]
    if sub_amps.size == 0 or np.max(sub_amps) <= 0:
        return None
    j = int(np.argmax(sub_amps))
    f_dom = float(freqs[idx_band[j]])
    peak_amp = float(sub_amps[j])
    return f_dom, peak_amp, freqs, amps_norm, fs


def _downsample_spectrum(freqs, amps, max_bins=128):
    """Bin-average down to ≤max_bins, keep monotonic frequency axis."""
    import numpy as np
    n = freqs.size
    if n <= max_bins:
        return freqs.astype(float), amps.astype(float)
    # block-mean reduction
    factor = int(np.ceil(n / max_bins))
    new_n = n // factor
    if new_n < 2:
        return freqs.astype(float), amps.astype(float)
    f_trim = freqs[:new_n * factor].reshape(new_n, factor)
    a_trim = amps[:new_n * factor].reshape(new_n, factor)
    return f_trim.mean(axis=1), a_trim.max(axis=1)


def _build_fft_payload(report):
    """Aggregate FFT dominant frequencies per part across all positions."""
    import numpy as np
    parts_by_id = {p.part_id: p for p in getattr(report, "parts", [])}
    part_motions = getattr(report, "part_motions", {}) or {}

    # group by part_id
    by_part = {}
    for key, pm in part_motions.items():
        if not isinstance(key, tuple) or len(key) != 2:
            continue
        pos_id, part_id = key
        times = getattr(pm, "times", None)
        acc = getattr(pm, "acc_mag", None)
        if times is None or acc is None:
            continue
        res = _fft_dominant_freq(times, acc, f_lo=10.0)
        if res is None:
            continue
        f_dom, peak_amp, freqs, amps_norm, fs = res
        by_part.setdefault(part_id, []).append({
            "pos_id": _pid_cast(pos_id),
            "f_dom": f_dom,
            "peak_amp": peak_amp,
            "freqs": freqs,
            "amps_norm": amps_norm,
            "fs": fs,
        })

    per_part = {}
    all_fs = []
    n_positions_used = 0
    f_lo_used = 10.0
    f_hi_used = 0.0

    for part_id, entries in by_part.items():
        if not entries:
            continue
        f_doms = np.array([e["f_dom"] for e in entries], dtype=float)
        # pick the entry with the highest peak_amp for representative spectrum
        top = max(entries, key=lambda e: e["peak_amp"])
        ds_f, ds_a = _downsample_spectrum(top["freqs"], top["amps_norm"], max_bins=128)
        # round for payload size (4 sig-fig)
        ds_f = [_r4(float(x)) for x in ds_f.tolist()]
        ds_a = [_r4(float(x)) for x in ds_a.tolist()]
        info = parts_by_id.get(part_id)
        name = getattr(info, "part_name", None) or f"Part {part_id}"
        per_part[str(part_id)] = {
            "name": name,
            "n_samples_used": int(f_doms.size),
            "mean_f_dom_Hz": _r4(float(np.mean(f_doms))),
            "std_f_dom_Hz": _r4(float(np.std(f_doms))),
            "top_pos_id": _pid_cast(top["pos_id"]),
            "top_freq_Hz": _r4(float(top["f_dom"])),
            "top_amp": _r4(float(top["peak_amp"])),
            "spectrum": {"f": ds_f, "amp_normalized": ds_a},
        }
        all_fs.extend([e["fs"] for e in entries])
        n_positions_used += len(entries)
        f_hi_used = max(f_hi_used, 0.5 * max(e["fs"] for e in entries))

    summary = {
        "n_parts_with_data": len(per_part),
        "n_positions_used": int(n_positions_used),
        "fs_Hz": round(float(np.mean(all_fs)), 2) if all_fs else 0.0,
        "freq_band_Hz": [round(float(f_lo_used), 2), round(float(f_hi_used), 2)],
    }
    return {"per_part_dominant_freq": per_part, "summary": summary}

def _srs_one_third_octave_centers(f_lo: float, f_hi: float):
    """Return 1/3-octave band center frequencies between f_lo and f_hi (Hz)."""
    import math
    # 1/3-octave ratio
    r = 2.0 ** (1.0 / 3.0)
    n_lo = int(math.floor(math.log(f_lo) / math.log(r)))
    n_hi = int(math.ceil(math.log(f_hi) / math.log(r)))
    centers = []
    for n in range(n_lo, n_hi + 1):
        fc = r ** n
        if f_lo <= fc <= f_hi:
            centers.append(fc)
    return centers


def _srs_sdof_max_abs_accel(t, a_in, freqs_hz, zeta: float = 0.05):
    """
    SDOF base-excitation SRS via Newmark-beta (linear acceleration, constant fixed dt).
    Equation of motion for relative response z = x - x_base:
        z'' + 2 zeta wn z' + wn^2 z = -a_in(t)
    Absolute acceleration response = z'' + a_in.
    Returns list of max(|abs_accel|) per frequency.
    """
    import numpy as np
    a_in = np.asarray(a_in, dtype=np.float64)
    t = np.asarray(t, dtype=np.float64)
    if a_in.size < 4 or t.size != a_in.size:
        return [0.0] * len(freqs_hz)

    # finite, replace nan/inf
    a_in = np.where(np.isfinite(a_in), a_in, 0.0)

    # Resample to uniform dt = median spacing (robust to non-uniform output)
    dts = np.diff(t)
    dts = dts[dts > 0]
    if dts.size == 0:
        return [0.0] * len(freqs_hz)
    dt = float(np.median(dts))
    if dt <= 0 or not np.isfinite(dt):
        return [0.0] * len(freqs_hz)

    # Uniform grid
    t_uni = np.arange(t[0], t[-1] + 0.5 * dt, dt)
    a_uni = np.interp(t_uni, t, a_in)

    # Newmark-beta linear acceleration: beta=1/6, gamma=1/2
    beta = 1.0 / 6.0
    gamma = 0.5
    n = a_uni.size

    out = []
    for fn in freqs_hz:
        wn = 2.0 * np.pi * float(fn)
        # Effective stiffness coefficient for Newmark
        # m=1; c = 2*zeta*wn; k = wn^2
        m = 1.0
        c = 2.0 * zeta * wn
        k = wn * wn
        k_hat = k + (gamma / (beta * dt)) * c + (1.0 / (beta * dt * dt)) * m
        if not np.isfinite(k_hat) or k_hat <= 0:
            out.append(0.0)
            continue

        a1 = (1.0 / (beta * dt * dt)) * m + (gamma / (beta * dt)) * c
        a2 = (1.0 / (beta * dt)) * m + (gamma / beta - 1.0) * c
        a3 = (1.0 / (2.0 * beta) - 1.0) * m + dt * (gamma / (2.0 * beta) - 1.0) * c

        z = 0.0
        zdot = 0.0
        # initial relative acceleration: m*zdd + c*zdot + k*z = -a_in => zdd = -a_in
        zdd = -a_uni[0]

        max_abs_accel = 0.0
        for i in range(1, n):
            p_eff = -a_uni[i] * m + a1 * z + a2 * zdot + a3 * zdd
            z_new = p_eff / k_hat
            zdd_new = (1.0 / (beta * dt * dt)) * (z_new - z) - (1.0 / (beta * dt)) * zdot - (1.0 / (2.0 * beta) - 1.0) * zdd
            zdot_new = zdot + dt * ((1.0 - gamma) * zdd + gamma * zdd_new)

            # absolute acceleration = relative + base
            abs_acc = abs(zdd_new + a_uni[i])
            if abs_acc > max_abs_accel:
                max_abs_accel = abs_acc

            z, zdot, zdd = z_new, zdot_new, zdd_new

        out.append(float(max_abs_accel) if np.isfinite(max_abs_accel) else 0.0)
    return out


def _build_srs_payload(report):
    """Build SRS payload: pick worst position, then top-3 parts by SRS peak."""
    import numpy as np

    # --- pick worst position ---
    # The report object doesn't have a `.doe_analysis` attribute (that is a
    # PAYLOAD key, not a model attribute), so we always derive the worst
    # position from PairResults. `r.position` is an ImpactPosition dataclass —
    # we need its `.pos_id` string to match the part_motions key tuple
    # `(pos_id_str, part_id)`. The previous code used the ImpactPosition
    # object itself, which never matched and silently dropped every part.
    pos_id = None
    results = getattr(report, "results", []) or []
    if results:
        try:
            best = max(
                (r for r in results if np.isfinite(getattr(r, "peak_g", float("nan")))),
                key=lambda r: getattr(r, "peak_g", 0.0),
                default=None,
            )
            if best is not None:
                pos_obj = getattr(best, "position", None)
                pos_id = getattr(pos_obj, "pos_id", None) if pos_obj is not None else None
        except Exception:
            pos_id = None

    part_motions = getattr(report, "part_motions", {}) or {}

    if pos_id is None or not part_motions:
        return {"available": False, "reason": "no_position_or_motions"}

    # Collect part motions belonging to this pos_id
    candidates = []
    for key, pm in part_motions.items():
        try:
            kp, kpart = key
        except Exception:
            continue
        if kp != pos_id:
            continue
        t = getattr(pm, "times", None)
        a = getattr(pm, "acc_mag", None)
        if t is None or a is None:
            continue
        t_arr = np.asarray(t, dtype=np.float64)
        a_arr = np.asarray(a, dtype=np.float64)
        if t_arr.size < 8 or a_arr.size != t_arr.size:
            continue
        if not np.any(np.isfinite(a_arr)) or np.nanmax(np.abs(a_arr)) <= 0:
            continue
        candidates.append((kpart, t_arr, a_arr))

    if not candidates:
        return {"available": False, "reason": "no_acc_data_at_position"}

    # Frequency band: 5..5000 Hz, 1/3 octave centers
    f_lo, f_hi = 5.0, 5000.0
    freqs = _srs_one_third_octave_centers(f_lo, f_hi)
    if not freqs:
        return {"available": False, "reason": "no_freq_band"}

    zeta = 0.05

    # Compute SRS for each candidate, track max(srs) for ranking
    parts_info = {p.part_id: p for p in (getattr(report, "parts", []) or [])}

    scored = []
    for (pid, t_arr, a_arr) in candidates:
        srs = _srs_sdof_max_abs_accel(t_arr, a_arr, freqs, zeta=zeta)
        if not srs:
            continue
        peak = max(srs) if srs else 0.0
        if not np.isfinite(peak) or peak <= 0:
            continue
        scored.append((peak, pid, srs, t_arr.size))

    if not scored:
        return {"available": False, "reason": "srs_all_zero"}

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:3]

    # estimate fs from first candidate
    t0 = candidates[0][1]
    diffs = np.diff(t0)
    diffs = diffs[diffs > 0]
    fs_hz = float(1.0 / np.median(diffs)) if diffs.size else 0.0

    srs_curves = []
    for peak, pid, srs, _ in top:
        pinfo = parts_info.get(pid)
        pname = getattr(pinfo, "part_name", None) if pinfo else None
        if not pname:
            pname = f"part {pid}"
        srs_curves.append({
            "pos_id": pos_id,
            "part_id": pid,
            "part_name": pname,
            "f": [_r4(float(x)) for x in freqs],
            "srs": [_r4(float(x)) for x in srs],
        })

    return {
        "available": True,
        "srs_curves": srs_curves,
        "summary": {
            "damping_ratio": zeta,
            "n_frequencies": len(freqs),
            "fs_Hz": _r4(fs_hz),
            "f_range_Hz": [f_lo, f_hi],
            "pos_id": pos_id,
        },
    }
def _safe_drop_zone_convex_hull(points):
    """Monotone-chain convex hull. Input: list of (x,y). Returns list of (x,y) in CCW order.
    Returns [] if <3 unique points."""
    pts = sorted(set((float(x), float(y)) for x, y in points))
    if len(pts) < 3:
        return []

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    hull = lower[:-1] + upper[:-1]
    return hull


def _build_safe_drop_zone(report):
    import math
    results = getattr(report, "results", []) or []
    if not results:
        return {
            "positions": [],
            "thresholds_used": {"peak_g_thresh": 0.0, "peak_stress_thresh": 0.0, "peak_disp_thresh": 0.0},
            "safe_count": 0,
            "at_risk_count": 0,
            "critical_polygon": [],
            "empty": True,
        }

    def _f(v):
        try:
            x = float(v)
            if math.isnan(x) or math.isinf(x):
                return None
            return x
        except Exception:
            return None

    gs = [_f(getattr(r, "peak_g", None)) for r in results]
    ss = [_f(getattr(r, "peak_stress", None)) for r in results]
    ds = [_f(getattr(r, "peak_disp", None)) for r in results]

    gs_clean = [v for v in gs if v is not None]
    ss_clean = [v for v in ss if v is not None]
    ds_clean = [v for v in ds if v is not None]

    if not gs_clean or not ss_clean or not ds_clean:
        return {
            "positions": [],
            "thresholds_used": {"peak_g_thresh": 0.0, "peak_stress_thresh": 0.0, "peak_disp_thresh": 0.0},
            "safe_count": 0,
            "at_risk_count": 0,
            "critical_polygon": [],
            "empty": True,
        }

    def _percentile(sorted_vals, p):
        if not sorted_vals:
            return 0.0
        if len(sorted_vals) == 1:
            return sorted_vals[0]
        k = (len(sorted_vals) - 1) * (p / 100.0)
        f = int(math.floor(k))
        c = int(math.ceil(k))
        if f == c:
            return sorted_vals[f]
        return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)

    g_thresh = sum(gs_clean) / len(gs_clean)
    s_sorted = sorted(ss_clean)
    d_sorted = sorted(ds_clean)
    s_thresh = _percentile(s_sorted, 75.0)
    d_thresh = _percentile(d_sorted, 75.0)

    # Group rows by pos_id (face+position)
    pos_map = {}
    for r in results:
        face = getattr(r, "face", None)
        pos_obj = getattr(r, "position", None)
        pid_pos = getattr(pos_obj, "pos_id", None) if pos_obj is not None else getattr(r, "pos_id", None)
        if face is None or pid_pos is None:
            continue
        key = (face, pid_pos)
        pos_map.setdefault(key, []).append(r)

    # Build position coordinate lookup from report.positions_by_face
    coord_lookup = {}
    positions_by_face = getattr(report, "positions_by_face", {}) or {}
    for face_code, plist in positions_by_face.items():
        for ip in plist or []:
            try:
                coord_lookup[(face_code, getattr(ip, "pos_id", None))] = (
                    float(getattr(ip, "x", 0.0)),
                    float(getattr(ip, "y", 0.0)),
                )
            except Exception:
                pass

    positions_out = []
    unsafe_xy = []
    safe_count = 0
    at_risk_count = 0

    for (face, pos_id), rows in sorted(pos_map.items(), key=lambda kv: (str(kv[0][0]), kv[0][1])):
        # Worst violation across parts at this position
        worst_metric = None
        worst_ratio = -1.0
        worst_value = 0.0
        worst_part_id = None
        is_safe = True

        for r in rows:
            g = _f(getattr(r, "peak_g", None))
            s = _f(getattr(r, "peak_stress", None))
            d = _f(getattr(r, "peak_disp", None))
            pid = getattr(r, "part_id", None)

            if g is not None and g > g_thresh:
                is_safe = False
                ratio = g / g_thresh if g_thresh > 0 else g
                if ratio > worst_ratio:
                    worst_ratio = ratio
                    worst_metric = "peak_g"
                    worst_value = g
                    worst_part_id = pid
            if s is not None and s > s_thresh:
                is_safe = False
                ratio = s / s_thresh if s_thresh > 0 else s
                if ratio > worst_ratio:
                    worst_ratio = ratio
                    worst_metric = "peak_stress"
                    worst_value = s
                    worst_part_id = pid
            if d is not None and d > d_thresh:
                is_safe = False
                ratio = d / d_thresh if d_thresh > 0 else d
                if ratio > worst_ratio:
                    worst_ratio = ratio
                    worst_metric = "peak_disp"
                    worst_value = d
                    worst_part_id = pid

        xy = coord_lookup.get((face, pos_id), (0.0, 0.0))
        if is_safe:
            safe_count += 1
        else:
            at_risk_count += 1
            unsafe_xy.append(xy)

        positions_out.append({
            "pos_id": pos_id,
            "face": face,
            "x": round(xy[0], 6),
            "y": round(xy[1], 6),
            "safe": bool(is_safe),
            "worst_metric": worst_metric,
            "worst_value": round(worst_value, 6) if worst_metric else 0.0,
            "worst_part_id": worst_part_id,
        })

    critical_polygon = _safe_drop_zone_convex_hull(unsafe_xy)
    critical_polygon = [[round(x, 6), round(y, 6)] for x, y in critical_polygon]

    return {
        "positions": positions_out,
        "thresholds_used": {
            "peak_g_thresh": round(g_thresh, 6),
            "peak_stress_thresh": round(s_thresh, 6),
            "peak_disp_thresh": round(d_thresh, 6),
        },
        "safe_count": safe_count,
        "at_risk_count": at_risk_count,
        "critical_polygon": critical_polygon,
        "empty": False,
    }

def _pca_modal_build(report):
    """Build PCA modal decomposition payload from peak_g matrix (positions x parts)."""
    import math
    import numpy as np

    try:
        results = getattr(report, "results", []) or []
        parts = getattr(report, "parts", []) or []
        positions_by_face = getattr(report, "positions_by_face", {}) or {}
    except Exception:
        return {"available": False, "reason": "no_report_attrs"}

    # ---- collect part_id -> name
    part_name_map = {}
    for p in parts:
        pid = getattr(p, "part_id", None)
        if pid is None:
            continue
        part_name_map[int(pid)] = str(getattr(p, "part_name", f"part_{pid}"))

    # ---- collect pos_id -> (x, y) across all faces
    pos_xy = {}
    for face_code, pos_list in positions_by_face.items():
        for pos in (pos_list or []):
            pid = getattr(pos, "pos_id", None)
            if pid is None:
                continue
            try:
                pos_xy[_pid_cast(pid)] = (float(getattr(pos, "x", 0.0)),
                                          float(getattr(pos, "y", 0.0)))
            except Exception:
                continue

    # ---- assemble peak_g cells keyed by (pos_id, part_id)
    cells = {}
    for r in results:
        pos_id = getattr(r, "pos_id", None)
        if pos_id is None:
            # fall back: some loaders carry pos_id inside .position
            pos_id = getattr(getattr(r, "position", None), "pos_id", None)
        part_id = getattr(r, "part_id", None)
        peak_g = getattr(r, "peak_g", None)
        if pos_id is None or part_id is None or peak_g is None:
            continue
        try:
            v = float(peak_g)
        except Exception:
            continue
        if not math.isfinite(v):
            continue
        cells[(_pid_cast(pos_id), int(part_id))] = v

    if not cells:
        return {"available": False, "reason": "no_peak_g_cells"}

    pos_ids = sorted({k[0] for k in cells.keys()})
    part_ids = sorted({k[1] for k in cells.keys()})

    n_pos = len(pos_ids)
    n_part = len(part_ids)

    if n_pos < 5 or n_part < 2:
        return {"available": False, "reason": f"insufficient_shape_{n_pos}x{n_part}"}

    # ---- build matrix (rows=positions, cols=parts) with NaN for missing, then mean-impute per column
    M = np.full((n_pos, n_part), np.nan, dtype=float)
    pos_index = {pid: i for i, pid in enumerate(pos_ids)}
    part_index = {pid: j for j, pid in enumerate(part_ids)}
    for (pid, part_id), v in cells.items():
        M[pos_index[pid], part_index[part_id]] = v

    # column mean-impute (only if any NaN); columns of all-NaN dropped
    keep_cols = []
    for j in range(n_part):
        col = M[:, j]
        finite = np.isfinite(col)
        if not finite.any():
            continue
        if not finite.all():
            mu = float(np.nanmean(col))
            col = np.where(finite, col, mu)
            M[:, j] = col
        keep_cols.append(j)
    if len(keep_cols) < 2:
        return {"available": False, "reason": "too_few_valid_parts"}
    if len(keep_cols) != n_part:
        M = M[:, keep_cols]
        part_ids = [part_ids[j] for j in keep_cols]
        n_part = len(part_ids)

    # ---- column-normalize by per-column max (so each part contributes equally)
    col_max = np.max(np.abs(M), axis=0)
    col_max[col_max == 0] = 1.0
    Mn = M / col_max

    # ---- center columns (PCA on covariance of column-normalized data)
    Mc = Mn - Mn.mean(axis=0, keepdims=True)

    # ---- SVD
    try:
        U, S, Vt = np.linalg.svd(Mc, full_matrices=False)
    except np.linalg.LinAlgError:
        return {"available": False, "reason": "svd_failed"}

    total_var = float(np.sum(S * S))
    if total_var <= 0:
        return {"available": False, "reason": "zero_variance"}

    k = int(min(3, S.shape[0]))
    if k == 0:
        return {"available": False, "reason": "no_components"}

    evr = (S[:k] ** 2) / total_var  # explained variance ratio
    scores = U[:, :k] * S[:k]        # (n_pos, k) — position scores along each mode

    # sign convention: make the largest |loading| positive for each mode
    modes_payload = []
    for m in range(k):
        loading_vec = Vt[m, :]  # (n_part,)
        score_vec = scores[:, m]

        # flip sign so the dominant loading is positive (deterministic orientation)
        if loading_vec.size > 0:
            idx_max = int(np.argmax(np.abs(loading_vec)))
            if loading_vec[idx_max] < 0:
                loading_vec = -loading_vec
                score_vec = -score_vec

        # top-10 part loadings by |loading|
        order = np.argsort(-np.abs(loading_vec))
        top_n = int(min(10, loading_vec.size))
        part_loadings = []
        for idx in order[:top_n]:
            pid = int(part_ids[idx])
            part_loadings.append({
                "part_id": pid,
                "part_name": part_name_map.get(pid, f"part_{pid}"),
                "loading": round(float(loading_vec[idx]), 4),
            })

        # position scores (with x,y when available)
        position_scores = []
        for i, pos_id in enumerate(pos_ids):
            xy = pos_xy.get(_pid_cast(pos_id), (None, None))
            position_scores.append({
                "pos_id": _pid_cast(pos_id),
                "x": (round(float(xy[0]), 4) if xy[0] is not None else None),
                "y": (round(float(xy[1]), 4) if xy[1] is not None else None),
                "score": round(float(score_vec[i]), 4),
            })

        modes_payload.append({
            "mode_index": m + 1,
            "explained_var_ratio": round(float(evr[m]), 4),
            "singular_value": round(float(S[m]), 4),
            "part_loadings": part_loadings,
            "position_scores": position_scores,
        })

    return {
        "available": True,
        "n_positions": int(n_pos),
        "n_parts": int(n_part),
        "total_components": int(S.shape[0]),
        "cumulative_var_ratio": round(float(np.sum(evr)), 4),
        "modes": modes_payload,
    }

def _anomaly_detection_helper(report):
    import math
    import numpy as np

    results = getattr(report, "results", []) or []
    if not results:
        return {"per_position": [], "threshold": 0.0, "n_anomalous": 0,
                "iqr_outliers": [], "z_thresh_base": 2.5, "p95_z": 0.0,
                "iqr_low": 0.0, "iqr_high": 0.0, "empty": True}

    # Collect per-(face,pos) aggregates
    by_pos = {}
    for r in results:
        face = getattr(r, "face", None)
        pos_obj = getattr(r, "position", None)
        pos_id = getattr(pos_obj, "pos_id", None) if pos_obj is not None else getattr(r, "pos_id", None)
        if face is None or pos_id is None:
            continue
        key = (face, pos_id)
        d = by_pos.setdefault(key, {"g": [], "s": [], "d": []})
        for fld, store in (("peak_g", "g"), ("peak_stress", "s"), ("peak_disp", "d")):
            v = getattr(r, fld, None)
            if v is None:
                continue
            try:
                fv = float(v)
            except Exception:
                continue
            if math.isnan(fv) or math.isinf(fv):
                continue
            d[store].append(fv)

    # Coordinates from positions_by_face
    pos_xy = {}
    pbf = getattr(report, "positions_by_face", {}) or {}
    for face_code, plist in pbf.items():
        for p in plist or []:
            pid = getattr(p, "pos_id", None)
            if pid is None:
                continue
            try:
                x = float(getattr(p, "x", 0.0))
                y = float(getattr(p, "y", 0.0))
            except Exception:
                x, y = 0.0, 0.0
            pos_xy[(face_code, pid)] = (x, y)

    # Mean per position per metric
    rows = []
    for (face, pid), agg in by_pos.items():
        def _mean(lst):
            return float(np.mean(lst)) if lst else None
        mg = _mean(agg["g"])
        ms = _mean(agg["s"])
        md = _mean(agg["d"])
        x, y = pos_xy.get((face, pid), (None, None))
        rows.append({"face": str(face), "pos_id": _pid_cast(pid),
                     "x": x, "y": y,
                     "mean_g": mg, "mean_s": ms, "mean_d": md})

    if not rows:
        return {"per_position": [], "threshold": 0.0, "n_anomalous": 0,
                "iqr_outliers": [], "z_thresh_base": 2.5, "p95_z": 0.0,
                "iqr_low": 0.0, "iqr_high": 0.0, "empty": True}

    def _zscores(key):
        vals = np.array([r[key] for r in rows if r[key] is not None], dtype=float)
        if vals.size < 2:
            return None, None
        mu = float(np.mean(vals))
        sd = float(np.std(vals, ddof=0))
        return mu, sd

    mu_g, sd_g = _zscores("mean_g")
    mu_s, sd_s = _zscores("mean_s")
    mu_d, sd_d = _zscores("mean_d")

    def _z(val, mu, sd):
        if val is None or mu is None or sd is None or sd <= 0:
            return 0.0
        return float((val - mu) / sd)

    per_position = []
    abs_z_pool = []
    for r in rows:
        zg = _z(r["mean_g"], mu_g, sd_g)
        zs = _z(r["mean_s"], mu_s, sd_s)
        zd = _z(r["mean_d"], mu_d, sd_d)
        absz = [abs(zg), abs(zs), abs(zd)]
        max_idx = int(np.argmax(absz))
        driver = ("peak_g", "peak_stress", "peak_disp")[max_idx]
        max_abs_z = float(max(absz))
        abs_z_pool.append(max_abs_z)
        per_position.append({
            "face": r["face"], "pos_id": r["pos_id"],
            "x": r["x"], "y": r["y"],
            "z_g": round(zg, 3), "z_s": round(zs, 3), "z_d": round(zd, 3),
            "max_abs_z": round(max_abs_z, 3),
            "driver": driver,
        })

    # Threshold: max(2.5, P95 of |z|)
    z_base = 2.5
    p95 = float(np.percentile(abs_z_pool, 95)) if abs_z_pool else 0.0
    threshold = float(max(z_base, p95))

    # Tukey IQR fence on peak_g means
    g_vals = np.array([r["mean_g"] for r in rows if r["mean_g"] is not None], dtype=float)
    iqr_low, iqr_high = 0.0, 0.0
    iqr_outliers = []
    if g_vals.size >= 4:
        q1 = float(np.percentile(g_vals, 25))
        q3 = float(np.percentile(g_vals, 75))
        iqr = q3 - q1
        iqr_low = q1 - 1.5 * iqr
        iqr_high = q3 + 1.5 * iqr
        for r in rows:
            if r["mean_g"] is None:
                continue
            if r["mean_g"] < iqr_low or r["mean_g"] > iqr_high:
                iqr_outliers.append({"face": r["face"], "pos_id": r["pos_id"],
                                     "mean_g": round(r["mean_g"], 3)})

    n_anomalous = 0
    for p in per_position:
        p["anomalous"] = bool(p["max_abs_z"] >= threshold)
        if p["anomalous"]:
            n_anomalous += 1

    per_position.sort(key=lambda r: r["max_abs_z"], reverse=True)

    return {
        "per_position": per_position,
        "threshold": round(threshold, 3),
        "z_thresh_base": z_base,
        "p95_z": round(p95, 3),
        "n_anomalous": int(n_anomalous),
        "iqr_outliers": iqr_outliers,
        "iqr_low": round(iqr_low, 3),
        "iqr_high": round(iqr_high, 3),
        "empty": False,
    }

def _build_per_part_drilldown(report) -> dict:
    """Index payload for the per-part drill-down panel.

    Aggregates 25-part-level summaries from PairResult rows. The heavy
    peak_g matrix is intentionally NOT duplicated here — the JS reuses
    ``DATA.doe_analysis.peak_g_matrix`` when ``reuse_doe_matrix`` is
    True. When the DOE matrix is absent, this helper still returns the
    aggregate index so the panel can render KPI + histogram tiles (the
    spatial heatmap tile shows a "no data" placeholder).
    """
    results = list(getattr(report, "results", None) or [])
    parts = list(getattr(report, "parts", None) or [])
    if not results or not parts:
        return {}

    # ------- helpers -------
    def _safe(v) -> float:
        try:
            f = float(v)
        except (TypeError, ValueError):
            return 0.0
        if f != f or f in (float("inf"), float("-inf")):  # NaN / inf
            return 0.0
        return f

    # ------- per-part aggregation across all positions -------
    # part_id -> list[(pos_id, peak_g, peak_stress, peak_disp, x, y)]
    per_part: dict = {}
    for r in results:
        pid = int(r.part_id)
        per_part.setdefault(pid, []).append(r)

    # global p75 of peak_g (data-derived threshold)
    all_g = sorted(_safe(r.peak_g) for r in results)
    if all_g:
        # Linear-interp p75
        idx = 0.75 * (len(all_g) - 1)
        lo = int(idx)
        hi = min(lo + 1, len(all_g) - 1)
        frac = idx - lo
        global_p75 = all_g[lo] * (1.0 - frac) + all_g[hi] * frac
    else:
        global_p75 = 0.0

    # yield lookup from sim_params
    sim_params = getattr(report, "sim_params", None) or {}
    yield_lut_raw = sim_params.get("yield_stress_by_part") \
        if isinstance(sim_params, dict) else None
    yield_lut: dict = {}
    if isinstance(yield_lut_raw, dict):
        for k, v in yield_lut_raw.items():
            try:
                yield_lut[int(k)] = _safe(v)
            except (TypeError, ValueError):
                continue

    # impactor material lookup (for material card when no yield)
    impactor = getattr(report, "impactor", None)
    imp_youngs = _safe(getattr(impactor, "youngs_modulus", 0.0)) if impactor else 0.0
    imp_density = _safe(getattr(impactor, "density", 0.0)) if impactor else 0.0

    # part metadata
    part_meta = {
        int(p.part_id): {
            "part_name": p.part_name or f"part_{int(p.part_id)}",
            "group": p.group or "",
        }
        for p in parts
    }

    # ------- build the part index -------
    out_parts: list = []
    for pid, rows in per_part.items():
        gs = [_safe(r.peak_g) for r in rows]
        ss = [_safe(r.peak_stress) for r in rows]
        ds = [_safe(r.peak_disp) for r in rows]
        if not gs:
            continue
        max_g = max(gs)
        mean_g = sum(gs) / len(gs)
        max_s = max(ss) if ss else 0.0
        max_d = max(ds) if ds else 0.0

        # position of max peak_g
        max_idx = gs.index(max_g)
        max_row = rows[max_idx]
        max_pos_id = max_row.position.pos_id
        max_x = _safe(getattr(max_row.position, "x", 0.0))
        max_y = _safe(getattr(max_row.position, "y", 0.0))

        # positions above global p75
        n_above = sum(1 for v in gs if v >= global_p75 and global_p75 > 0)

        meta = part_meta.get(pid, {"part_name": f"part_{pid}", "group": ""})
        yield_val = yield_lut.get(pid)
        has_yield = yield_val is not None and yield_val > 0.0

        out_parts.append({
            "part_id": pid,
            "part_name": meta["part_name"],
            "group": meta["group"],
            "max_peak_g": round(max_g, 4),
            "mean_peak_g": round(mean_g, 4),
            "max_peak_stress": round(max_s, 4),
            "max_peak_disp": round(max_d, 6),
            "max_pos_id": max_pos_id,
            "max_pos_x": round(max_x, 4),
            "max_pos_y": round(max_y, 4),
            "n_positions_above_global_p75": int(n_above),
            "has_yield": bool(has_yield),
            "yield_value": round(yield_val, 4) if has_yield else None,
        })

    out_parts.sort(key=lambda d: d["max_peak_g"], reverse=True)

    # ------- positions_lookup (xy per pos_id) -------
    positions_lookup: dict = {}
    for face_code, pos_list in (getattr(report, "positions_by_face", None) or {}).items():
        for pos in pos_list:
            positions_lookup[str(pos.pos_id)] = {
                "x": round(_safe(pos.x), 4),
                "y": round(_safe(pos.y), 4),
            }
    # Fall back to results-derived xy if positions_by_face is empty
    if not positions_lookup:
        for r in results:
            key = str(r.position.pos_id)
            if key not in positions_lookup:
                positions_lookup[key] = {
                    "x": round(_safe(getattr(r.position, "x", 0.0)), 4),
                    "y": round(_safe(getattr(r.position, "y", 0.0)), 4),
                }

    return {
        "parts": out_parts,
        "positions_lookup": positions_lookup,
        "global_p75": round(global_p75, 4),
        "reuse_doe_matrix": True,
        "impactor_material": {
            "youngs_modulus": round(imp_youngs, 4),
            "density": round(imp_density, 6),
        },
    }

def _build_symmetry_insight(report):
    """Build symmetry & boundary effect payload by comparing mirror-pair peak_g."""
    import math
    import numpy as np

    results = getattr(report, "results", []) or []
    positions_by_face = getattr(report, "positions_by_face", {}) or {}

    # peak_g per pos_id: average across parts at that position
    pg_by_pos = {}
    for r in results:
        pid = getattr(r, "pos_id", None)
        pg = getattr(r, "peak_g", None)
        if pid is None or pg is None:
            continue
        try:
            v = float(pg)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(v):
            continue
        pg_by_pos.setdefault(pid, []).append(v)
    pg_mean = {pid: float(np.mean(vs)) for pid, vs in pg_by_pos.items() if vs}

    def _asym_pct(a, b):
        m = max(abs(a), abs(b))
        if m <= 0 or not math.isfinite(m):
            return None
        return abs(a - b) / m * 100.0

    # collect (face, pos) lookup
    pos_lookup = {}   # (face, round(x,4), round(y,4)) -> pos_id
    pos_meta = {}     # pos_id -> (face, x, y)
    for face, positions in positions_by_face.items():
        for p in positions or []:
            pid = getattr(p, "pos_id", None)
            x = getattr(p, "x", None)
            y = getattr(p, "y", None)
            if pid is None or x is None or y is None:
                continue
            try:
                xf, yf = float(x), float(y)
            except (TypeError, ValueError):
                continue
            pos_lookup[(face, round(xf, 4), round(yf, 4))] = pid
            pos_meta[pid] = (face, xf, yf)

    x_pairs, y_pairs = [], []
    seen_x, seen_y = set(), set()
    for pid, (face, x, y) in pos_meta.items():
        if pid not in pg_mean:
            continue
        # X-mirror: (-x, y)
        if abs(x) > 1e-9:
            mate = pos_lookup.get((face, round(-x, 4), round(y, 4)))
            if mate is not None and mate in pg_mean:
                key = tuple(sorted((pid, mate)))
                if key not in seen_x:
                    seen_x.add(key)
                    a, b = pg_mean[pid], pg_mean[mate]
                    asym = _asym_pct(a, b)
                    if asym is not None:
                        x_pairs.append({
                            "pos_a": int(key[0]),
                            "pos_b": int(key[1]),
                            "peak_g_a": round(pg_mean[key[0]], 3),
                            "peak_g_b": round(pg_mean[key[1]], 3),
                            "asymmetry_pct": round(asym, 2),
                        })
        # Y-mirror: (x, -y)
        if abs(y) > 1e-9:
            mate = pos_lookup.get((face, round(x, 4), round(-y, 4)))
            if mate is not None and mate in pg_mean:
                key = tuple(sorted((pid, mate)))
                if key not in seen_y:
                    seen_y.add(key)
                    a, b = pg_mean[pid], pg_mean[mate]
                    asym = _asym_pct(a, b)
                    if asym is not None:
                        y_pairs.append({
                            "pos_a": int(key[0]),
                            "pos_b": int(key[1]),
                            "peak_g_a": round(pg_mean[key[0]], 3),
                            "peak_g_b": round(pg_mean[key[1]], 3),
                            "asymmetry_pct": round(asym, 2),
                        })

    x_pairs.sort(key=lambda d: d["asymmetry_pct"], reverse=True)
    y_pairs.sort(key=lambda d: d["asymmetry_pct"], reverse=True)

    # Boundary: outer ring vs inner — data-driven threshold = max(|x|,|y|) per face
    outer_vals, inner_vals = [], []
    by_face_extent = {}
    for pid, (face, x, y) in pos_meta.items():
        m = max(abs(x), abs(y))
        by_face_extent.setdefault(face, []).append(m)
    face_thr = {f: (max(v) if v else 0.0) for f, v in by_face_extent.items()}

    for pid, (face, x, y) in pos_meta.items():
        if pid not in pg_mean:
            continue
        thr = face_thr.get(face, 0.0)
        if thr <= 0:
            continue
        m = max(abs(x), abs(y))
        if m >= thr - 1e-6:
            outer_vals.append(pg_mean[pid])
        else:
            inner_vals.append(pg_mean[pid])

    outer_mean = float(np.mean(outer_vals)) if outer_vals else float("nan")
    inner_mean = float(np.mean(inner_vals)) if inner_vals else float("nan")
    if math.isfinite(outer_mean) and math.isfinite(inner_mean) and inner_mean > 0:
        boundary_amp = (outer_mean - inner_mean) / inner_mean * 100.0
    else:
        boundary_amp = float("nan")

    def _med(pairs):
        if not pairs:
            return float("nan")
        return float(np.median([p["asymmetry_pct"] for p in pairs]))

    med_x = _med(x_pairs)
    med_y = _med(y_pairs)
    design_symmetric = (
        math.isfinite(med_x) and math.isfinite(med_y)
        and med_x < 15.0 and med_y < 15.0
    )

    def _nz(v, nd=2):
        return round(v, nd) if isinstance(v, float) and math.isfinite(v) else None

    return {
        "x_mirror_pairs": x_pairs[:12],
        "y_mirror_pairs": y_pairs[:12],
        "median_x_asym_pct": _nz(med_x),
        "median_y_asym_pct": _nz(med_y),
        "boundary_summary": {
            "outer_mean_peak_g": _nz(outer_mean, 3),
            "inner_mean_peak_g": _nz(inner_mean, 3),
            "boundary_amplification_pct": _nz(boundary_amp),
            "outer_n": len(outer_vals),
            "inner_n": len(inner_vals),
        },
        "design_symmetric": bool(design_symmetric),
        "x_pair_count": len(x_pairs),
        "y_pair_count": len(y_pairs),
    }

def _build_damage_index(report):
    """Damage Accumulation Index per Part across all impact positions.

    Yield-based: DI = sum over positions of max(0, peak_stress/yield - 1).
    Composite fallback: mean of normalized peak_g/peak_stress/peak_strain in [0,1].
    """
    import numpy as np
    from collections import defaultdict

    parts = list(getattr(report, "parts", []) or [])
    results = list(getattr(report, "results", []) or [])
    sim_params = getattr(report, "sim_params", None)
    yield_map = {}
    if sim_params is not None:
        ym = getattr(sim_params, "yield_stress_by_part", None) or {}
        try:
            yield_map = {int(k): float(v) for k, v in ym.items()
                         if v is not None and np.isfinite(float(v)) and float(v) > 0.0}
        except Exception:
            yield_map = {}

    part_name = {int(p.part_id): str(getattr(p, "part_name", "") or f"part_{p.part_id}")
                 for p in parts}
    part_ids_all = [int(p.part_id) for p in parts]

    # group results by part
    by_part = defaultdict(list)  # part_id -> list of (pos_id, peak_g, peak_stress, peak_strain)
    for r in results:
        pid = getattr(r, "part_id", None)
        pos = getattr(r, "pos_id", None)
        if pid is None or pos is None:
            continue
        try:
            pid_i = int(pid)
            pos_i = int(pos)
        except Exception:
            continue
        pg = float(getattr(r, "peak_g", float("nan")) or float("nan"))
        ps = float(getattr(r, "peak_stress", float("nan")) or float("nan"))
        pe = float(getattr(r, "peak_strain", float("nan")) or float("nan"))
        by_part[pid_i].append((pos_i, pg, ps, pe))

    # Determine if yield-based DI is usable: at least one part has yield AND stress data
    has_yield = bool(yield_map) and any(
        pid in yield_map and any(np.isfinite(t[2]) for t in by_part.get(pid, []))
        for pid in part_ids_all
    )

    # Global maxima for composite fallback
    all_pg, all_ps, all_pe = [], [], []
    for lst in by_part.values():
        for _, pg, ps, pe in lst:
            if np.isfinite(pg): all_pg.append(pg)
            if np.isfinite(ps): all_ps.append(ps)
            if np.isfinite(pe): all_pe.append(pe)
    g_max_pg = float(max(all_pg)) if all_pg else 0.0
    g_max_ps = float(max(all_ps)) if all_ps else 0.0
    g_max_pe = float(max(all_pe)) if all_pe else 0.0

    per_part = []
    for pid in part_ids_all:
        lst = by_part.get(pid, [])
        if not lst:
            continue
        name = part_name.get(pid, f"part_{pid}")
        if has_yield and pid in yield_map:
            ys = yield_map[pid]
            di = 0.0
            n_above = 0
            peak_contrib = -1.0
            peak_pos = None
            for pos_i, _pg, ps, _pe in lst:
                if not np.isfinite(ps):
                    continue
                excess = ps / ys - 1.0
                if excess > 0.0:
                    di += excess
                    n_above += 1
                    if excess > peak_contrib:
                        peak_contrib = excess
                        peak_pos = pos_i
            per_part.append({
                "part_id": pid,
                "part_name": name,
                "di": round(float(di), 4),
                "di_source": "yield",
                "yield_stress": round(float(ys), 2),
                "peak_pos_id": int(peak_pos) if peak_pos is not None else None,
                "n_positions_above_yield": int(n_above),
                "n_positions": int(len(lst)),
            })
        else:
            # composite fallback
            pgs = [t[1] for t in lst if np.isfinite(t[1])]
            pss = [t[2] for t in lst if np.isfinite(t[2])]
            pes = [t[3] for t in lst if np.isfinite(t[3])]
            mx_pg = max(pgs) if pgs else 0.0
            mx_ps = max(pss) if pss else 0.0
            mx_pe = max(pes) if pes else 0.0
            c_pg = (mx_pg / g_max_pg) if g_max_pg > 0 else 0.0
            c_ps = (mx_ps / g_max_ps) if g_max_ps > 0 else 0.0
            c_pe = (mx_pe / g_max_pe) if g_max_pe > 0 else 0.0
            di = (c_pg + c_ps + c_pe) / 3.0
            # peak position: position with the highest normalized composite
            best_score = -1.0
            best_pos = None
            for pos_i, pg, ps, pe in lst:
                s = 0.0; n = 0
                if g_max_pg > 0 and np.isfinite(pg): s += pg / g_max_pg; n += 1
                if g_max_ps > 0 and np.isfinite(ps): s += ps / g_max_ps; n += 1
                if g_max_pe > 0 and np.isfinite(pe): s += pe / g_max_pe; n += 1
                if n > 0:
                    score = s / n
                    if score > best_score:
                        best_score = score
                        best_pos = pos_i
            per_part.append({
                "part_id": pid,
                "part_name": name,
                "di": round(float(di), 4),
                "di_source": "composite",
                "peak_pos_id": int(best_pos) if best_pos is not None else None,
                "max_peak_g": round(float(mx_pg), 2),
                "max_peak_stress": round(float(mx_ps), 2),
                "max_peak_strain": round(float(mx_pe), 5),
                "n_positions": int(len(lst)),
            })

    # sort desc by di, keep top 15
    per_part.sort(key=lambda d: d["di"], reverse=True)
    per_part_top = per_part[:15]

    # Top 5 (part, position) dominant combos — compute per-pair contribution
    pair_contribs = []
    for pid in part_ids_all:
        lst = by_part.get(pid, [])
        if not lst:
            continue
        name = part_name.get(pid, f"part_{pid}")
        if has_yield and pid in yield_map:
            ys = yield_map[pid]
            for pos_i, _pg, ps, _pe in lst:
                if not np.isfinite(ps):
                    continue
                excess = ps / ys - 1.0
                if excess > 0.0:
                    pair_contribs.append({
                        "part_id": pid, "part_name": name, "pos_id": pos_i,
                        "contrib": round(float(excess), 4), "source": "yield",
                    })
        else:
            for pos_i, pg, ps, pe in lst:
                s = 0.0; n = 0
                if g_max_pg > 0 and np.isfinite(pg): s += pg / g_max_pg; n += 1
                if g_max_ps > 0 and np.isfinite(ps): s += ps / g_max_ps; n += 1
                if g_max_pe > 0 and np.isfinite(pe): s += pe / g_max_pe; n += 1
                if n > 0:
                    pair_contribs.append({
                        "part_id": pid, "part_name": name, "pos_id": pos_i,
                        "contrib": round(float(s / n), 4), "source": "composite",
                    })
    pair_contribs.sort(key=lambda d: d["contrib"], reverse=True)
    top_pairs = pair_contribs[:5]

    max_di_value = float(per_part_top[0]["di"]) if per_part_top else 0.0
    max_di_part = per_part_top[0]["part_name"] if per_part_top else None
    max_di_pos = per_part_top[0].get("peak_pos_id") if per_part_top else None

    return {
        "per_part": per_part_top,
        "top_pairs": top_pairs,
        "summary": {
            "has_yield": bool(has_yield),
            "max_di_value": round(max_di_value, 4),
            "max_di_part": max_di_part,
            "max_di_position": max_di_pos,
            "n_parts_total": len(part_ids_all),
            "n_parts_with_data": len(per_part),
        },
    }

def _build_rebound_field(report):
    import numpy as np

    grid = getattr(report.sim_params, "grid", None) or {}
    bbox = grid.get("bbox") if isinstance(grid, dict) else None
    if not bbox:
        # derive from positions if missing
        xs, ys = [], []
        for face_positions in report.positions_by_face.values():
            for p in face_positions:
                xs.append(p.x); ys.append(p.y)
        if xs and ys:
            bbox = [min(xs), min(ys), max(xs), max(ys)]
        else:
            bbox = [0.0, 0.0, 1.0, 1.0]

    # Flatten positions across all faces (typically one face per report)
    positions = []
    for face, pos_list in report.positions_by_face.items():
        for p in pos_list:
            positions.append((p.pos_id, float(p.x), float(p.y), face))

    vectors = []
    speeds = []
    n_up = 0
    n_down = 0
    n_flat = 0

    for pos_id, x, y, face in positions:
        traj = report.impactor_trajectories.get(pos_id)
        if traj is None:
            vectors.append({
                "pos_id": _pid_cast(pos_id), "x": round(x, 6), "y": round(y, 6),
                "vx_rebound": 0.0, "vy_rebound": 0.0, "vz_final": 0.0,
                "speed": 0.0, "color_class": "flat", "missing": True,
            })
            continue

        # rebound_velocity_xy is typically a (vx, vy) tuple/list; guard for scalars
        rvxy = getattr(traj, "rebound_velocity_xy", None)
        if rvxy is None:
            vx_r, vy_r = 0.0, 0.0
        else:
            try:
                vx_r = float(rvxy[0]); vy_r = float(rvxy[1])
            except (TypeError, IndexError):
                vx_r, vy_r = 0.0, 0.0

        # final vz from velocity arrays
        vz_arr = getattr(traj, "vel_z", None)
        if vz_arr is not None and len(vz_arr) > 0:
            vz_final = float(np.asarray(vz_arr)[-1])
        else:
            vz_final = 0.0

        # NaN/Inf guard
        for name in ("vx_r", "vy_r", "vz_final"):
            v = locals()[name]
            if not np.isfinite(v):
                locals()[name] = 0.0
        if not np.isfinite(vx_r): vx_r = 0.0
        if not np.isfinite(vy_r): vy_r = 0.0
        if not np.isfinite(vz_final): vz_final = 0.0

        speed_xy = float(np.hypot(vx_r, vy_r))
        speeds.append(speed_xy)

        # Color class — data-driven thresholds relative to incident speed
        incident = getattr(traj, "incident_speed", None)
        try:
            incident = float(incident) if incident is not None else 0.0
        except (TypeError, ValueError):
            incident = 0.0
        # vz threshold: 5% of incident or 0.1 m/s, whichever larger
        vz_thr = max(0.05 * abs(incident), 0.1)

        if vz_final > vz_thr:
            color_class = "up"; n_up += 1
        elif vz_final < -vz_thr:
            color_class = "down"; n_down += 1
        else:
            color_class = "flat"; n_flat += 1

        vectors.append({
            "pos_id": _pid_cast(pos_id),
            "x": round(x, 6), "y": round(y, 6),
            "vx_rebound": round(vx_r, 4),
            "vy_rebound": round(vy_r, 4),
            "vz_final": round(vz_final, 4),
            "speed": round(speed_xy, 4),
            "color_class": color_class,
        })

    speeds_arr = np.asarray(speeds) if speeds else np.zeros(1)
    max_speed = float(np.max(speeds_arr)) if speeds else 0.0
    avg_speed = float(np.mean(speeds_arr)) if speeds else 0.0

    # n_sliding = vxy dominant (speed > vz threshold relative to |vz|)
    n_sliding = 0
    for v in vectors:
        if v.get("missing"):
            continue
        if v["speed"] > max(abs(v["vz_final"]), 1e-6) and v["speed"] > 0.05 * max(max_speed, 1e-6):
            n_sliding += 1

    return {
        "vectors": vectors,
        "max_speed": round(max_speed, 4),
        "avg_speed": round(avg_speed, 4),
        "n_rebound_up": n_up,
        "n_embed_down": n_down,
        "n_flat": n_flat,
        "n_sliding": n_sliding,
        "n_total": len(vectors),
        "bbox": [round(float(b), 6) for b in bbox],
        # unit_labels 의 정확한 키는 'vel' / 'disp' (loader._detect_unit_system 의 dict).
        # 'velocity' / 'length' 는 항상 fallback 'm/s' / 'm' 을 반환하던 silent 버그.
        "vel_unit": (report.sim_params.get("unit_labels") or {}).get("vel", "") if getattr(report, "sim_params", None) else "",
        "len_unit": (report.sim_params.get("unit_labels") or {}).get("disp", "") if getattr(report, "sim_params", None) else "",
    }

def _build_auto_recommend(report):
    """Generate rule-based engineering recommendations from report data."""
    import numpy as np
    from collections import defaultdict

    recs = []

    # Unit labels for interpolation into Korean recommendation strings.
    _ul = (report.sim_params or {}).get("unit_labels") or {}
    _u_acc = _ul.get("acc") or ""
    _u_len = _ul.get("disp") or ""
    _u_acc_str = f" {_u_acc}" if _u_acc else ""
    _u_len_str = f" {_u_len}" if _u_len else ""

    results = getattr(report, "results", []) or []
    parts = getattr(report, "parts", []) or []
    part_name_by_id = {p.part_id: getattr(p, "part_name", f"Part {p.part_id}") for p in parts}

    positions_by_face = getattr(report, "positions_by_face", {}) or {}
    pos_xy = {}
    for face, positions in positions_by_face.items():
        for pos in positions or []:
            pos_xy[pos.pos_id] = (getattr(pos, "x", float("nan")),
                                  getattr(pos, "y", float("nan")),
                                  face)

    # ---------- Rule 1: worst position / part peak_g ----------
    if results:
        peaks = []
        for r in results:
            g = getattr(r, "peak_g", None)
            if g is None or not np.isfinite(g):
                continue
            peaks.append((float(g), getattr(r, "pos_id", None), getattr(r, "part_id", None)))
        if peaks:
            peaks.sort(key=lambda t: -t[0])
            worst_g, worst_pos, worst_part = peaks[0]
            all_g = np.array([p[0] for p in peaks], dtype=float)
            p95 = float(np.percentile(all_g, 95)) if all_g.size else worst_g
            severity = "critical" if worst_g >= p95 else "warning"
            pname = part_name_by_id.get(worst_part, f"Part {worst_part}")
            xy = pos_xy.get(worst_pos)
            if xy is not None and np.isfinite(xy[0]) and np.isfinite(xy[1]):
                xy_str = f"(x={xy[0]:.3f}, y={xy[1]:.3f}){_u_len_str}"
            else:
                xy_str = "(좌표 미정)"
            recs.append({
                "severity": severity,
                "title": "최대 응답 위치 — 보강 우선",
                "body": f"위치 P{worst_pos} {xy_str} 에서 부품 '{pname}' 의 peak_g = {worst_g:,.1f}{_u_acc_str} 로 최대 응답이 관측되었습니다. 해당 위치/부품 보강을 최우선으로 검토하십시오.",
                "source_panel": "Peak Response Heatmap",
                "metric": round(worst_g, 1),
            })

    # ---------- Rule 2: X-axis asymmetry ----------
    # Compute asymmetry between positions with x>0 vs x<0 on dominant face.
    if results and pos_xy:
        peak_by_pos = defaultdict(list)
        for r in results:
            g = getattr(r, "peak_g", None)
            pid = getattr(r, "pos_id", None)
            if g is None or not np.isfinite(g) or pid is None:
                continue
            peak_by_pos[pid].append(float(g))
        pos_mean = {pid: float(np.mean(v)) for pid, v in peak_by_pos.items() if v}
        left = [v for pid, v in pos_mean.items()
                if pid in pos_xy and np.isfinite(pos_xy[pid][0]) and pos_xy[pid][0] < 0]
        right = [v for pid, v in pos_mean.items()
                 if pid in pos_xy and np.isfinite(pos_xy[pid][0]) and pos_xy[pid][0] > 0]
        if left and right:
            mL, mR = float(np.mean(left)), float(np.mean(right))
            denom = 0.5 * (mL + mR)
            asym = (abs(mL - mR) / denom * 100.0) if denom > 0 else 0.0
            if asym > 15.0:
                recs.append({
                    "severity": "warning" if asym < 30.0 else "critical",
                    "title": "X축 비대칭 검출",
                    "body": f"X<0 평균 peak_g = {mL:,.1f}{_u_acc_str}, X>0 평균 = {mR:,.1f}{_u_acc_str} → 비대칭 {asym:.1f}%. 디자인 균형(질량 분포·강성 분포) 재검토 권장.",
                    "source_panel": "Symmetry Diagnostic",
                    "metric": round(asym, 1),
                })

    # ---------- Rule 5: KE absorption ----------
    trajs = getattr(report, "impactor_trajectories", {}) or {}
    if trajs:
        rets = []
        for pid, tr in trajs.items():
            kr = getattr(tr, "ke_retention", None)
            if kr is None:
                continue
            try:
                arr = np.asarray(kr, dtype=float)
                if arr.size:
                    final = float(arr[-1])
                    if np.isfinite(final):
                        rets.append(final)
            except Exception:
                continue
        if rets:
            mean_ret = float(np.mean(rets))
            mean_abs_pct = (1.0 - mean_ret) * 100.0
            if mean_abs_pct < 30.0:
                sev = "warning"
            elif mean_abs_pct < 50.0:
                sev = "info"
            else:
                sev = "info"
            if mean_abs_pct < 50.0:
                recs.append({
                    "severity": sev,
                    "title": "KE 흡수율 낮음 — 충격 흡수재 추가 권장",
                    "body": f"전 위치 평균 KE 흡수율 = {mean_abs_pct:.1f}% (잔여 운동에너지 {mean_ret*100:.1f}%). 충격 흡수 폼/리브 추가 또는 두께 증가 검토.",
                    "source_panel": "Energy Partition",
                    "metric": round(mean_abs_pct, 1),
                })
            else:
                recs.append({
                    "severity": "info",
                    "title": "KE 흡수율 양호",
                    "body": f"전 위치 평균 KE 흡수율 = {mean_abs_pct:.1f}%. 현재 흡수 성능은 적정 범위.",
                    "source_panel": "Energy Partition",
                    "metric": round(mean_abs_pct, 1),
                })

    # ---------- Rule 6: damage index (yield-stress based) ----------
    sim_params = getattr(report, "sim_params", None)
    yield_by_part = {}
    if sim_params is not None:
        yield_by_part = getattr(sim_params, "yield_stress_by_part", {}) or {}
    if results and yield_by_part:
        di_by_part = defaultdict(list)
        for r in results:
            ps = getattr(r, "peak_stress", None)
            pid = getattr(r, "part_id", None)
            if ps is None or not np.isfinite(ps) or pid is None:
                continue
            ys = yield_by_part.get(pid)
            if ys is None or ys <= 0:
                continue
            di_by_part[pid].append(float(ps) / float(ys))
        di_summary = [(pid, float(np.max(v))) for pid, v in di_by_part.items() if v]
        if di_summary:
            di_summary.sort(key=lambda t: -t[1])
            top_pid, top_di = di_summary[0]
            if top_di >= 1.0:
                sev = "critical"
            elif top_di >= 0.8:
                sev = "warning"
            else:
                sev = "info"
            if top_di >= 0.6:
                pname = part_name_by_id.get(top_pid, f"Part {top_pid}")
                recs.append({
                    "severity": sev,
                    "title": "손상 지표(DI) 상위 부품",
                    "body": f"부품 '{pname}' 의 DI = peak_stress/yield = {top_di:.2f}. 재료 보강 또는 yield 향상(고강도 등급/두께 증가) 검토 권장.",
                    "source_panel": "Damage Index",
                    "metric": round(top_di, 2),
                })

    # ---------- Rule 4: statistical outliers (z>2.5 on pos-level mean peak_g) ----------
    if results:
        pos_g = defaultdict(list)
        for r in results:
            g = getattr(r, "peak_g", None)
            pid = getattr(r, "pos_id", None)
            if g is None or not np.isfinite(g) or pid is None:
                continue
            pos_g[pid].append(float(g))
        means = {pid: float(np.mean(v)) for pid, v in pos_g.items() if v}
        if len(means) >= 4:
            arr = np.array(list(means.values()), dtype=float)
            mu, sd = float(np.mean(arr)), float(np.std(arr))
            if sd > 0:
                outliers = [(pid, v, (v - mu) / sd) for pid, v in means.items()
                            if abs((v - mu) / sd) > 2.5]
                outliers.sort(key=lambda t: -abs(t[2]))
                if outliers:
                    listing = ", ".join([f"P{pid}(z={z:+.2f})" for pid, _, z in outliers[:5]])
                    recs.append({
                        "severity": "warning",
                        "title": "통계적 이상치 위치 검출",
                        "body": f"{len(outliers)}개 위치가 통계적 이상치 (|z|>2.5): {listing}. 해당 위치 메쉬/접촉 조건 재검증 권장.",
                        "source_panel": "Per-Position Stats",
                        "metric": len(outliers),
                    })

    summary = {
        "total": len(recs),
        "critical": sum(1 for r in recs if r["severity"] == "critical"),
        "warning": sum(1 for r in recs if r["severity"] == "warning"),
        "info": sum(1 for r in recs if r["severity"] == "info"),
    }

    return {"recommendations": recs, "summary": summary}

def _build_contact_pulse(report):
    """Compute contact pulse statistics per impactor position."""
    import numpy as np

    per_position = []
    durations_ms = []

    trajectories = getattr(report, "impactor_trajectories", {}) or {}
    positions_by_face = getattr(report, "positions_by_face", {}) or {}

    # Build pos_id -> (x, y, face) lookup
    pos_lookup = {}
    for face, pos_list in positions_by_face.items():
        for p in pos_list:
            pid = getattr(p, "pos_id", None)
            if pid is None:
                continue
            pos_lookup[pid] = {
                "x": float(getattr(p, "x", 0.0) or 0.0),
                "y": float(getattr(p, "y", 0.0) or 0.0),
                "face": face,
            }

    for pos_id, traj in trajectories.items():
        if traj is None:
            continue
        times = np.asarray(getattr(traj, "times", []) or [], dtype=float)
        engaged = np.asarray(getattr(traj, "contact_engaged", []) or [], dtype=bool)
        if times.size == 0 or engaged.size == 0:
            continue
        n_total = int(min(times.size, engaged.size))
        times = times[:n_total]
        engaged = engaged[:n_total]

        n_contact = int(np.count_nonzero(engaged))
        contact_density = float(n_contact / n_total) if n_total > 0 else 0.0

        if n_contact >= 1:
            idx = np.where(engaged)[0]
            t_first = float(times[idx[0]])
            t_last = float(times[idx[-1]])
            pulse_duration_ms = (t_last - t_first) * 1000.0
        else:
            pulse_duration_ms = float("nan")

        # pulse_to_peak: from t_first_contact to time of max penetration
        t_fc = getattr(traj, "t_first_contact", None)
        max_pen = getattr(traj, "max_penetration_depth", None)
        pos_z = np.asarray(getattr(traj, "pos_z", []) or [], dtype=float)
        pulse_to_peak_ms = float("nan")
        if t_fc is not None and np.isfinite(t_fc) and pos_z.size == times.size and pos_z.size > 0:
            # Find time where pos_z is at its extreme during contact (deepest penetration)
            # Penetration depth typically reaches max while engaged
            if n_contact > 0:
                idx_c = np.where(engaged)[0]
                z_contact = pos_z[idx_c]
                # Deepest = min or max depending on impact face; use extreme deviation from first-contact z
                z_ref = pos_z[idx_c[0]]
                deviations = np.abs(z_contact - z_ref)
                k = int(np.argmax(deviations))
                t_peak = float(times[idx_c[k]])
                pulse_to_peak_ms = (t_peak - float(t_fc)) * 1000.0

        coord = pos_lookup.get(pos_id, {"x": 0.0, "y": 0.0, "face": ""})
        behavior = getattr(traj, "behavior_class", "") or ""

        entry = {
            "pos_id": _pid_cast(pos_id),
            "x": coord["x"],
            "y": coord["y"],
            "face": coord["face"],
            "pulse_duration_ms": round(pulse_duration_ms, 3) if np.isfinite(pulse_duration_ms) else None,
            "n_contact_steps": n_contact,
            "contact_density": round(contact_density, 4),
            "pulse_to_peak_ms": round(pulse_to_peak_ms, 3) if np.isfinite(pulse_to_peak_ms) else None,
            "behavior_class": str(behavior),
        }
        per_position.append(entry)
        if np.isfinite(pulse_duration_ms):
            durations_ms.append((pos_id, pulse_duration_ms))

    # Summary
    summary = {
        "mean_duration_ms": None,
        "std_duration_ms": None,
        "median_duration_ms": None,
        "min_pos": None,
        "max_pos": None,
        "min_duration_ms": None,
        "max_duration_ms": None,
        "n_valid": len(durations_ms),
    }
    if durations_ms:
        vals = np.array([d for _, d in durations_ms], dtype=float)
        summary["mean_duration_ms"] = round(float(np.mean(vals)), 3)
        summary["std_duration_ms"] = round(float(np.std(vals)), 3)
        summary["median_duration_ms"] = round(float(np.median(vals)), 3)
        i_min = int(np.argmin(vals))
        i_max = int(np.argmax(vals))
        summary["min_pos"] = _pid_cast(durations_ms[i_min][0])
        summary["max_pos"] = _pid_cast(durations_ms[i_max][0])
        summary["min_duration_ms"] = round(float(vals[i_min]), 3)
        summary["max_duration_ms"] = round(float(vals[i_max]), 3)

    return {"per_position": per_position, "summary": summary}

def _build_trajectory_3d(report):
    """Section-07 "3D 트래젝터리 번들" payload.

    For each impactor trajectory in ``report.impactor_trajectories``, sample
    the (x, y, z) position track to at most 30 points and pair it with the
    position's (x, y) on the impact face and its ``behavior_class``.

    Returns
    -------
    dict with keys:
        bundles  : list[{pos_id, x, y, behavior_class, points: [[x,y,z], ...]}]
        z_range  : [zmin, zmax]
        bbox_xy  : [xmin, ymin, xmax, ymax]
    Empty dict when no trajectory data.
    """
    raw_trajs = getattr(report, "impactor_trajectories", None) or {}
    if not raw_trajs:
        return {}

    # pos_id -> (x, y, face) lookup from positions_by_face
    pos_xy = {}
    xs_pos, ys_pos = [], []
    for face, plist in (getattr(report, "positions_by_face", None) or {}).items():
        for p in plist:
            try:
                x = float(getattr(p, "x", 0.0)); y = float(getattr(p, "y", 0.0))
            except (TypeError, ValueError):
                continue
            pid = getattr(p, "pos_id", None)
            if pid is None:
                continue
            pos_xy[str(pid)] = (x, y, str(face))
            xs_pos.append(x); ys_pos.append(y)

    bundles = []
    zmin = float("inf"); zmax = float("-inf")
    MAX_PTS = 30

    for pos_id, traj in raw_trajs.items():
        if traj is None:
            continue
        px = list(getattr(traj, "pos_x", None) or [])
        py = list(getattr(traj, "pos_y", None) or [])
        pz = list(getattr(traj, "pos_z", None) or [])
        n = min(len(px), len(py), len(pz))
        if n == 0:
            continue

        # stride-sample down to <= MAX_PTS, always include first + last
        if n <= MAX_PTS:
            idxs = list(range(n))
        else:
            step = (n - 1) / (MAX_PTS - 1)
            idxs = sorted({int(round(i * step)) for i in range(MAX_PTS)})
            if idxs[-1] != n - 1:
                idxs.append(n - 1)

        pts = []
        for i in idxs:
            try:
                x = float(px[i]); y = float(py[i]); z = float(pz[i])
            except (TypeError, ValueError):
                continue
            if not (x == x and y == y and z == z):  # NaN guard
                continue
            pts.append([round(x, 4), round(y, 4), round(z, 4)])
            if z < zmin: zmin = z
            if z > zmax: zmax = z
        if not pts:
            continue

        sx, sy, _face = pos_xy.get(str(pos_id), (pts[0][0], pts[0][1], ""))
        behavior = getattr(traj, "behavior_class", "unknown") or "unknown"
        bundles.append({
            "pos_id": _pid_cast(pos_id),
            "x": round(sx, 4),
            "y": round(sy, 4),
            "behavior_class": str(behavior),
            "points": pts,
        })

    if not bundles:
        return {}

    # bbox_xy: prefer grid metadata, fall back to positions
    grid = getattr(getattr(report, "sim_params", None), "grid", None) or {}
    bbox_raw = grid.get("bbox") if isinstance(grid, dict) else None
    if bbox_raw and len(bbox_raw) == 4:
        bbox_xy = [float(bbox_raw[0]), float(bbox_raw[1]),
                   float(bbox_raw[2]), float(bbox_raw[3])]
    elif xs_pos and ys_pos:
        bbox_xy = [min(xs_pos), min(ys_pos), max(xs_pos), max(ys_pos)]
    else:
        bbox_xy = [-40.0, -40.0, 40.0, 40.0]

    if zmin == float("inf"):
        zmin, zmax = 0.0, 1.0
    if zmax <= zmin:
        zmax = zmin + 1.0

    return {
        "bundles": bundles,
        "z_range": [round(zmin, 4), round(zmax, 4)],
        "bbox_xy": [round(v, 4) for v in bbox_xy],
    }
def _build_stress_wave_velocity_payload(report) -> dict:
    """Section-08 — Apparent stress-wave velocity per (position, part).

    For each (position p, part i):
      delta_t = part_motion[(p,i)].t_peak_g - traj.t_first_contact   (clip >=0)
      r       = sqrt((px - cx)^2 + (py - cy)^2 + (impact_z - cz)^2)  (mm)
      v_app   = r / delta_t  -> m/s (mm/s -> m/s via /1000)

    Theoretical longitudinal wave speed of impactor material:
      c_theory = sqrt(E / rho)  (m/s)
      Units (LS-DYNA [ton, mm, s, MPa]): E[MPa]=N/mm^2, rho[tonne/mm^3]
      -> SI: c = sqrt((E_MPa*1e6) / (rho_tmm3*1e12)) m/s
            = sqrt(E_MPa / rho_tmm3) * 1e-3

    Empty / NaN / inf are explicitly placeheld so the panel-inventory
    Korean-string scan does not flag the panel as empty.
    """
    import math
    import numpy as np

    EMPTY = {
        "per_part": [],
        "v_theory_impactor": None,
        "summary": {},
        "_placeholder": (
            "응력파 전파 속도 데이터 없음 - part_motion / impactor_trajectory "
            "결측 또는 first_contact / t_peak_g 미검출. 입력 d3plot에서 "
            "rigid-body motion CSV와 contact engagement 파싱 결과를 확인하세요."
        ),
    }

    part_motions = getattr(report, "part_motions", None) or {}
    trajs = getattr(report, "impactor_trajectories", None) or {}
    positions_by_face = getattr(report, "positions_by_face", None) or {}
    parts_list = getattr(report, "parts", None) or []
    impactor = getattr(report, "impactor", None)

    if not part_motions or not trajs or not positions_by_face or not parts_list:
        return EMPTY

    # Lookup tables
    name_by_id = {p.part_id: (p.part_name or f"PART_{p.part_id}") for p in parts_list}
    pos_xy_by_id: dict[str, tuple[float, float]] = {}
    for face, plist in positions_by_face.items():
        for pos in (plist or []):
            pos_xy_by_id[pos.pos_id] = (float(pos.x), float(pos.y))

    # Impact-Z reference: prefer the trajectory's first pos_z (impactor tip at t=0).
    # Falls back to 0.0 if not available — keeps the formula well-defined.
    def _impact_z(pos_id: str) -> float:
        tr = trajs.get(pos_id)
        if tr is None:
            return 0.0
        pz = getattr(tr, "pos_z", None) or []
        if not pz:
            return 0.0
        try:
            return float(pz[0])
        except (TypeError, ValueError):
            return 0.0

    # Accumulate per-part samples
    samples_by_part: dict[int, list[tuple[float, float]]] = {}  # part_id -> [(v_app m/s, dt s)]
    for (pos_id, part_id), pm in part_motions.items():
        if pm is None:
            continue
        traj = trajs.get(pos_id)
        if traj is None:
            continue
        t_first = getattr(traj, "t_first_contact", None)
        t_peak = getattr(pm, "t_peak_g", None)
        if t_first is None or t_peak is None:
            continue
        try:
            t_first_f = float(t_first)
            t_peak_f = float(t_peak)
        except (TypeError, ValueError):
            continue
        if not (math.isfinite(t_first_f) and math.isfinite(t_peak_f)):
            continue
        dt = t_peak_f - t_first_f
        if dt <= 0.0:
            continue  # peak before contact -> not a propagation sample
        # Spatial distance
        if pos_id not in pos_xy_by_id:
            continue
        px, py = pos_xy_by_id[pos_id]
        dx_arr = getattr(pm, "disp_x", None) or []
        dy_arr = getattr(pm, "disp_y", None) or []
        dz_arr = getattr(pm, "disp_z", None) or []
        if not dx_arr or not dy_arr or not dz_arr:
            continue
        try:
            cx = float(dx_arr[0])
            cy = float(dy_arr[0])
            cz = float(dz_arr[0])
        except (TypeError, ValueError):
            continue
        iz = _impact_z(pos_id)
        r_mm = math.sqrt((px - cx) ** 2 + (py - cy) ** 2 + (iz - cz) ** 2)
        if not math.isfinite(r_mm) or r_mm <= 0.0:
            continue
        v_mm_s = r_mm / dt          # mm/s
        v_m_s = v_mm_s / 1000.0     # m/s
        if not math.isfinite(v_m_s) or v_m_s <= 0.0:
            continue
        samples_by_part.setdefault(int(part_id), []).append((v_m_s, dt))

    if not samples_by_part:
        return EMPTY

    # Per-part aggregates
    per_part: list[dict] = []
    all_v: list[float] = []
    for pid, sams in samples_by_part.items():
        vs = np.array([s[0] for s in sams], dtype=float)
        dts = np.array([s[1] for s in sams], dtype=float)
        if vs.size == 0:
            continue
        q25 = float(np.percentile(vs, 25))
        q75 = float(np.percentile(vs, 75))
        per_part.append({
            "part_id": int(pid),
            "part_name": name_by_id.get(pid, f"PART_{pid}"),
            "mean_v_app": _r4(float(np.mean(vs))),
            "median_v_app": _r4(float(np.median(vs))),
            "q25_v_app": _r4(q25),
            "q75_v_app": _r4(q75),
            "mean_delta_t_ms": _r4(float(np.mean(dts)) * 1000.0),
            "n_samples": int(vs.size),
        })
        all_v.extend(vs.tolist())

    per_part.sort(key=lambda d: (d["mean_v_app"] if d["mean_v_app"] is not None else -1.0), reverse=True)
    per_part = per_part[:15]

    # Theoretical impactor wave speed
    v_theory = None
    if impactor is not None:
        E = float(getattr(impactor, "youngs_modulus", 0.0) or 0.0)   # MPa
        rho = float(getattr(impactor, "density", 0.0) or 0.0)        # tonne/mm^3
        if E > 0.0 and rho > 0.0:
            # m/s: sqrt(E_MPa / rho_tmm3) * 1e-3
            try:
                v_theory = _r4(math.sqrt(E / rho) * 1e-3)
            except (ValueError, ZeroDivisionError):
                v_theory = None

    all_v_arr = np.array(all_v, dtype=float)
    summary = {
        "min_v_app": _r4(float(np.min(all_v_arr))),
        "max_v_app": _r4(float(np.max(all_v_arr))),
        "median_v_app_all": _r4(float(np.median(all_v_arr))),
        "n_total": int(all_v_arr.size),
    }

    return {
        "per_part": per_part,
        "v_theory_impactor": v_theory,
        "summary": summary,
    }


def _build_restitution_map(report):
    """Compute coefficient of restitution e = sqrt(KE_after / KE_before) per impact position.

    Pulls KE_before from traj.initial_ke (or peak pre-contact KE) and KE_after
    from traj.final_ke (or post-rebound KE) for each ImpactorTrajectory, then
    aggregates a 5x5 map keyed by pos_id with summary statistics.
    """
    import math

    def _r4(v):
        try:
            if v is None:
                return None
            fv = float(v)
            if not math.isfinite(fv):
                return None
            return float(f"{fv:.4g}")
        except (TypeError, ValueError):
            return None

    def _safe_attr(obj, name, default=None):
        try:
            val = getattr(obj, name, default)
            return val if val is not None else default
        except Exception:
            return default

    # Gather positions across all faces, keyed by pos_id
    positions_lookup = {}
    try:
        for face, plist in (report.positions_by_face or {}).items():
            for p in plist or []:
                pid = _safe_attr(p, "pos_id")
                if pid is None:
                    continue
                positions_lookup.setdefault(pid, {
                    "pos_id": pid,
                    "x": _safe_attr(p, "x", 0.0),
                    "y": _safe_attr(p, "y", 0.0),
                    "face": face,
                })
    except Exception:
        positions_lookup = {}

    trajectories = getattr(report, "impactor_trajectories", {}) or {}

    per_position = []
    e_values = []

    for pid, pmeta in positions_lookup.items():
        traj = trajectories.get(pid)
        ke_before = None
        ke_after = None
        behavior = None

        if traj is not None:
            behavior = _safe_attr(traj, "behavior_class", None)

            # Prefer explicit initial_ke / final_ke fields if available
            ke_before = _safe_attr(traj, "initial_ke")
            ke_after = _safe_attr(traj, "final_ke")

            # Fallback: derive from the KE time series
            ke_series = _safe_attr(traj, "ke", None)
            t_contact = _safe_attr(traj, "t_first_contact", None)
            times = _safe_attr(traj, "times", None)

            try:
                if ke_series is not None and len(ke_series) > 0:
                    ke_list = [float(v) for v in ke_series
                               if v is not None and math.isfinite(float(v))]
                    if ke_list:
                        if ke_before is None:
                            # Peak KE prior to first contact (or overall peak)
                            if (times is not None and t_contact is not None
                                    and len(times) == len(ke_series)):
                                pre = [float(k) for t, k in zip(times, ke_series)
                                       if (t is not None and k is not None
                                           and math.isfinite(float(t))
                                           and math.isfinite(float(k))
                                           and float(t) <= float(t_contact))]
                                ke_before = max(pre) if pre else max(ke_list)
                            else:
                                ke_before = max(ke_list)
                        if ke_after is None:
                            ke_after = ke_list[-1]
            except Exception:
                pass

        # Compute restitution if both KE values are valid and positive
        e_val = None
        e_clamped = None
        try:
            if (ke_before is not None and ke_after is not None
                    and float(ke_before) > 0.0 and float(ke_after) >= 0.0
                    and math.isfinite(float(ke_before))
                    and math.isfinite(float(ke_after))):
                ratio = float(ke_after) / float(ke_before)
                if ratio < 0.0:
                    ratio = 0.0
                e_val = math.sqrt(ratio)
                # Clamp display range to [0, 1.2]; values > 1 hint at mass scaling
                e_clamped = max(0.0, min(1.2, e_val))
        except Exception:
            e_val = None
            e_clamped = None

        if e_clamped is not None:
            e_values.append(e_clamped)

        per_position.append({
            "pos_id": pid,
            "x": _r4(pmeta.get("x")),
            "y": _r4(pmeta.get("y")),
            "face": pmeta.get("face"),
            "ke_before": _r4(ke_before),
            "ke_after": _r4(ke_after),
            "e": _r4(e_clamped),
            "e_raw": _r4(e_val),
            "behavior_class": behavior or "unknown",
        })

    # Sort per_position by pos_id for stable rendering
    per_position.sort(key=lambda r: (r["pos_id"] if r["pos_id"] is not None else 1e9))

    # Summary statistics
    summary = {
        "mean_e": None,
        "median_e": None,
        "n_e_high": 0,
        "n_e_low": 0,
        "max_e": None,
        "min_e": None,
        "max_e_pos_id": None,
        "min_e_pos_id": None,
        "n_valid": len(e_values),
        "n_total": len(per_position),
    }

    if e_values:
        try:
            import numpy as np
            arr = np.asarray(e_values, dtype=float)
            summary["mean_e"] = _r4(float(np.mean(arr)))
            summary["median_e"] = _r4(float(np.median(arr)))
            summary["n_e_high"] = int(np.sum(arr >= 0.9))
            summary["n_e_low"] = int(np.sum(arr <= 0.3))
            # Locate max/min positions
            valid_rows = [r for r in per_position if r["e"] is not None]
            if valid_rows:
                row_max = max(valid_rows, key=lambda r: r["e"])
                row_min = min(valid_rows, key=lambda r: r["e"])
                summary["max_e"] = row_max["e"]
                summary["min_e"] = row_min["e"]
                summary["max_e_pos_id"] = row_max["pos_id"]
                summary["min_e_pos_id"] = row_min["pos_id"]
        except Exception:
            # Pure-python fallback
            srt = sorted(e_values)
            summary["mean_e"] = _r4(sum(srt) / len(srt))
            mid = len(srt) // 2
            summary["median_e"] = _r4(
                srt[mid] if len(srt) % 2 else 0.5 * (srt[mid - 1] + srt[mid])
            )
            summary["n_e_high"] = sum(1 for v in e_values if v >= 0.9)
            summary["n_e_low"] = sum(1 for v in e_values if v <= 0.3)

    # Histogram: 10 bins over [0, 1.2]
    hist_bins = []
    bin_count = 10
    hi = 1.2
    edges = [i * hi / bin_count for i in range(bin_count + 1)]
    counts = [0] * bin_count
    for v in e_values:
        idx = int(v / (hi / bin_count))
        if idx >= bin_count:
            idx = bin_count - 1
        if idx < 0:
            idx = 0
        counts[idx] += 1
    for i in range(bin_count):
        hist_bins.append({
            "lo": _r4(edges[i]),
            "hi": _r4(edges[i + 1]),
            "count": int(counts[i]),
        })

    # Device geometry for aspect-ratio honouring on the heatmap
    device_geom = getattr(report.sim_params, "device_geometry", None) if hasattr(report, "sim_params") else None
    geom_payload = None
    if device_geom is not None:
        geom_payload = {
            "width": _r4(_safe_attr(device_geom, "width")),
            "height": _r4(_safe_attr(device_geom, "height")),
            "depth": _r4(_safe_attr(device_geom, "depth")),
        }

    grid_info = None
    try:
        g = getattr(report.sim_params, "grid", None)
        if g is not None:
            grid_info = {
                "nx": int(_safe_attr(g, "nx", 5) or 5),
                "ny": int(_safe_attr(g, "ny", 5) or 5),
            }
    except Exception:
        grid_info = None
    if grid_info is None:
        grid_info = {"nx": 5, "ny": 5}

    return {
        "per_position": per_position,
        "summary": summary,
        "histogram": hist_bins,
        "hist_range": [0.0, 1.2],
        "device_geometry": geom_payload,
        "grid": grid_info,
    }

def _build_recovery_damping_payload(report) -> dict:
    """Per-part post-peak recovery time and estimated damping ratio.

    For the *worst* impact position (Σ peak_g over parts), for each part:
      1. Locate t_peak_g (from PartMotion).
      2. recovery_time_ms = first time after t_peak where acc_mag drops below
         5% of peak.  Falls back to the post-peak duration if it never decays
         below 5% (under-damped tail).
      3. ω_n ≈ 2π · f_dom — f_dom uses deep_analytics.fft per_part if
         available, otherwise estimated from local zero-crossings on the
         detrended post-peak signal.
      4. ζ via log-decrement on the 5% decay:
            a_peak/a_5pct = exp(ζ · ω_n · τ)
         →  ζ = ln(a_peak/a_5pct) / (ω_n · τ)         (with τ in s)
         Clipped to [0, 1].  When ω_n·τ is non-finite or ratio<=1, ζ=NaN.

    Returns per_part (sorted by damping desc, top 15), summary, pos_id_used.
    Empty dict when nothing usable.
    """
    import math
    import numpy as np

    part_motions = getattr(report, "part_motions", {}) or {}
    parts_by_id = {p.part_id: p for p in (getattr(report, "parts", []) or [])}
    if not part_motions or not parts_by_id:
        return {}

    # --- 1. Find worst position: max Σ peak_g over parts --------------------
    pos_sum: dict = {}
    for key, pm in part_motions.items():
        if not (isinstance(key, tuple) and len(key) == 2):
            continue
        pos_id, _pid = key
        peak = float(getattr(pm, "peak_g", 0.0) or 0.0)
        if not math.isfinite(peak):
            continue
        pos_sum[pos_id] = pos_sum.get(pos_id, 0.0) + peak
    if not pos_sum:
        return {}
    pos_id_worst = max(pos_sum.items(), key=lambda kv: kv[1])[0]

    # --- 2. Optional FFT lookup (deep_analytics) ---------------------------
    # Caller stores it in payload only AFTER our builder runs, so we recompute
    # via the same primitive used by Section-06.  Cheap: O(N log N) per part.
    fft_freq_by_part: dict = {}
    for (pos, pid), pm in part_motions.items():
        if pos != pos_id_worst:
            continue
        try:
            res = _fft_dominant_freq(pm.times, pm.acc_mag, f_lo=10.0)
        except Exception:
            res = None
        if res is not None:
            fft_freq_by_part[pid] = float(res[0])  # f_dom Hz

    # --- 3. Per-part recovery / damping ------------------------------------
    out_rows = []
    n_zero_total = 0
    for (pos, pid), pm in part_motions.items():
        if pos != pos_id_worst:
            continue
        info = parts_by_id.get(pid)
        name = getattr(info, "part_name", None) or f"Part {pid}"

        t = np.asarray(getattr(pm, "times", []) or [], dtype=float)
        a = np.asarray(getattr(pm, "acc_mag", []) or [], dtype=float)
        t_pk = float(getattr(pm, "t_peak_g", 0.0) or 0.0)
        a_pk = float(getattr(pm, "peak_g", 0.0) or 0.0)
        if t.size < 8 or a.size != t.size or a_pk <= 0 or not math.isfinite(a_pk):
            out_rows.append({
                "part_id": int(pid), "part_name": name,
                "recovery_time_ms": None,
                "damping_ratio_estimated": None,
                "n_zero_crossings": 0,
                "has_data": False,
            })
            continue
        mask = np.isfinite(t) & np.isfinite(a)
        if mask.sum() < 8:
            out_rows.append({
                "part_id": int(pid), "part_name": name,
                "recovery_time_ms": None,
                "damping_ratio_estimated": None,
                "n_zero_crossings": 0,
                "has_data": False,
            })
            continue
        t = t[mask]; a = a[mask]

        # Locate peak index — fall back to argmax when t_pk == 0
        if t_pk > 0:
            i_pk = int(np.argmin(np.abs(t - t_pk)))
        else:
            i_pk = int(np.argmax(a))
        post_t = t[i_pk:]
        post_a = a[i_pk:]
        if post_t.size < 6 or float(np.max(post_a)) <= 0:
            out_rows.append({
                "part_id": int(pid), "part_name": name,
                "recovery_time_ms": None,
                "damping_ratio_estimated": None,
                "n_zero_crossings": 0,
                "has_data": False,
            })
            continue

        # 5% recovery time
        thresh = 0.05 * a_pk
        below = np.where(post_a <= thresh)[0]
        if below.size > 0:
            tau_s = float(post_t[below[0]] - post_t[0])
            decayed = True
        else:
            tau_s = float(post_t[-1] - post_t[0])
            decayed = False
        if tau_s <= 0 or not math.isfinite(tau_s):
            tau_s = float(post_t[-1] - post_t[0]) if post_t.size > 1 else 0.0

        # Zero crossings on detrended post-peak signal (for ω_n fallback)
        post_centered = post_a - float(np.mean(post_a))
        zc = int(np.sum(np.diff(np.sign(post_centered)) != 0))
        n_zero_total += zc

        # Natural frequency: prefer FFT, fallback to zero-crossings
        f_n_hz = fft_freq_by_part.get(pid)
        if f_n_hz is None or not math.isfinite(f_n_hz) or f_n_hz <= 0:
            duration_post = float(post_t[-1] - post_t[0])
            if duration_post > 0 and zc >= 2:
                # 2 zero-crossings per cycle
                f_n_hz = 0.5 * zc / duration_post
            else:
                f_n_hz = 0.0
        omega_n = 2.0 * math.pi * f_n_hz if f_n_hz > 0 else 0.0

        # Damping via log-decrement on 5% decay
        # a_peak / a_5pct = exp(ζ ω_n τ)  ⇒  ζ = ln(20) / (ω_n τ) when decayed
        # If never decayed (under-damped), use observed final ratio as bound.
        if omega_n > 0 and tau_s > 0:
            if decayed:
                ratio = max(a_pk / max(thresh, 1e-30), 1.0 + 1e-9)
            else:
                ratio = max(a_pk / max(float(post_a[-1]), 1e-30), 1.0 + 1e-9)
            zeta = math.log(ratio) / (omega_n * tau_s)
            if not math.isfinite(zeta):
                zeta = None
            else:
                zeta = max(0.0, min(1.0, zeta))
        else:
            zeta = None

        out_rows.append({
            "part_id": int(pid),
            "part_name": name,
            "recovery_time_ms": _r4(tau_s * 1000.0),
            "damping_ratio_estimated": _r4(zeta) if zeta is not None else None,
            "n_zero_crossings": zc,
            "has_data": True,
        })

    if not any(r["has_data"] for r in out_rows):
        return {}

    # Sort by damping desc, NaNs last; top 15
    def _sort_key(r):
        z = r.get("damping_ratio_estimated")
        return (-(z if z is not None else -1.0), r["part_id"])
    out_rows_sorted = sorted(out_rows, key=_sort_key)[:15]

    # --- 4. Summary --------------------------------------------------------
    recs = [r["recovery_time_ms"] for r in out_rows if r["has_data"] and r["recovery_time_ms"] is not None]
    zs = [r["damping_ratio_estimated"] for r in out_rows if r["has_data"] and r["damping_ratio_estimated"] is not None]
    median_rec = _r4(float(np.median(recs))) if recs else None
    median_dmp_pct = _r4(float(np.median(zs)) * 100.0) if zs else None

    # under-damped = lowest ζ; over-damped = highest ζ
    with_z = [r for r in out_rows if r["has_data"] and r["damping_ratio_estimated"] is not None]
    if with_z:
        top_under = min(with_z, key=lambda r: r["damping_ratio_estimated"])
        top_over = max(with_z, key=lambda r: r["damping_ratio_estimated"])
        top_under_name = top_under["part_name"]
        top_over_name = top_over["part_name"]
    else:
        top_under_name = None
        top_over_name = None

    return {
        "per_part": out_rows_sorted,
        "summary": {
            "median_recovery_ms": median_rec,
            "median_damping_pct": median_dmp_pct,
            "top_underdamped_part_name": top_under_name,
            "top_overdamped_part_name": top_over_name,
            "n_parts_with_data": int(sum(1 for r in out_rows if r["has_data"])),
        },
        "pos_id_used": str(pos_id_worst),
    }
def _build_worst_combinations(report):
    """Top-25 worst (position, part) combinations by composite risk score.

    risk = 0.4 * (peak_g / p95_g) + 0.4 * (peak_stress / p95_s)
         + 0.2 * (peak_disp / p95_d)
    where p95_* are global P95 across all PairResults.
    """
    import math
    try:
        import numpy as _np
    except Exception:
        _np = None

    def _r(v):
        try:
            f = float(v)
            if not math.isfinite(f):
                return None
            return float(f"{f:.4g}")
        except Exception:
            return None

    results = list(getattr(report, "results", []) or [])
    parts = list(getattr(report, "parts", []) or [])
    part_name_by_id = {}
    for p in parts:
        pid = getattr(p, "part_id", None)
        if pid is None:
            continue
        part_name_by_id[int(pid)] = getattr(p, "part_name", f"Part {pid}") or f"Part {pid}"

    # position lookup: (face, pos_id) -> (x, y)
    pos_by_face = getattr(report, "positions_by_face", {}) or {}
    pos_lookup = {}
    for face, positions in pos_by_face.items():
        for ip in positions or []:
            pid = getattr(ip, "pos_id", None)
            if pid is None:
                continue
            try:
                pid_key = int(pid)
            except (TypeError, ValueError):
                pid_key = str(pid)
            pos_lookup[(str(face), pid_key)] = (
                float(getattr(ip, "x", 0.0) or 0.0),
                float(getattr(ip, "y", 0.0) or 0.0),
            )

    # behavior class lookup from impactor trajectories (keyed by pos_id only)
    # traj_map 의 key 는 DOE 케이스에서 'F5_DOE_001' 같은 string. 이전 코드는
    # int(k) 실패 후 fallback 으로 pos_id=-1 을 반환해 모든 entry 가 같은 키로
    # 덮어쓰기 → behavior_by_pos = {-1: <last>} → worst_combo lookup 전부 unknown.
    # worst_combinations 가 string pos_id 사용하므로 그대로 str() 키로 통일.
    traj_map = getattr(report, "impactor_trajectories", {}) or {}
    behavior_by_pos = {}
    for k, t in traj_map.items():
        key = str(getattr(t, "pos_id", k))
        behavior_by_pos[key] = getattr(t, "behavior_class", None) or "unknown"

    # ---- collect finite arrays for P95 ----
    def _finite(vals):
        out = []
        for v in vals:
            try:
                f = float(v)
                if math.isfinite(f):
                    out.append(f)
            except Exception:
                pass
        return out

    gs = _finite(getattr(r, "peak_g", 0.0) for r in results)
    ss = _finite(getattr(r, "peak_stress", 0.0) for r in results)
    ds = _finite(getattr(r, "peak_disp", 0.0) for r in results)

    def _p95(arr):
        if not arr:
            return None
        if _np is not None:
            try:
                return float(_np.percentile(arr, 95))
            except Exception:
                pass
        arr_sorted = sorted(arr)
        k = max(0, min(len(arr_sorted) - 1, int(round(0.95 * (len(arr_sorted) - 1)))))
        return float(arr_sorted[k])

    p95_g = _p95(gs)
    p95_s = _p95(ss)
    p95_d = _p95(ds)

    # Guards: if a denominator is None/zero, drop that term's weight (renormalize)
    weights = {"g": 0.4, "s": 0.4, "d": 0.2}
    denom = {"g": p95_g, "s": p95_s, "d": p95_d}

    placeholder_msg = (
        "데이터가 충분하지 않아 위험도 점수를 계산할 수 없습니다 "
        "(PairResult 또는 P95 정규화 기준값 누락)."
    )

    if not results or all(v in (None, 0.0) for v in denom.values()):
        return {
            "ok": False,
            "reason": placeholder_msg,
            "top_25": [],
            "distribution": {
                "p50_risk": None, "p75_risk": None, "p95_risk": None,
                "max_risk": None, "n_above_risk_1": 0,
            },
            "top_3_positions_by_count": [],
            "p95_norm": {"peak_g": p95_g, "peak_stress": p95_s, "peak_disp": p95_d},
        }

    def _term(val, key):
        d = denom[key]
        if d is None or d <= 0.0:
            return None
        try:
            f = float(val)
            if not math.isfinite(f):
                return None
            return weights[key] * (f / d)
        except Exception:
            return None

    scored = []
    for r in results:
        face = str(getattr(r, "face", "") or "")
        pos_raw = getattr(r, "position", None)
        if pos_raw is None:
            continue
        # ImpactPosition dataclass 의 경우 .pos_id 속성을 우선 — 그대로 str() 하면
        # repr() 이 200+자 dump 로 누출됨 (worst_combinations top_25 에서 발생).
        _pid_attr = getattr(pos_raw, "pos_id", None)
        if _pid_attr is not None:
            pos_id = str(_pid_attr)
        else:
            try:
                pos_id = int(pos_raw)
            except (TypeError, ValueError):
                pos_id = str(pos_raw)
        try:
            part_id = int(getattr(r, "part_id", -1))
        except Exception:
            continue

        pg = getattr(r, "peak_g", float("nan"))
        ps = getattr(r, "peak_stress", float("nan"))
        pd = getattr(r, "peak_disp", float("nan"))

        terms = {
            "g": _term(pg, "g"),
            "s": _term(ps, "s"),
            "d": _term(pd, "d"),
        }
        active = {k: v for k, v in terms.items() if v is not None}
        if not active:
            continue
        active_weight = sum(weights[k] for k in active.keys())
        if active_weight <= 0:
            continue
        risk = sum(active.values()) / active_weight  # renormalize to full-weight scale

        x, y = pos_lookup.get((face, pos_id), (None, None))
        scored.append({
            "face": face,
            "pos_id": pos_id,
            "x": _r(x) if x is not None else None,
            "y": _r(y) if y is not None else None,
            "part_id": part_id,
            "part_name": part_name_by_id.get(part_id, f"Part {part_id}"),
            "peak_g": _r(pg),
            "peak_stress": _r(ps),
            "peak_disp": _r(pd),
            "risk": _r(risk),
            "behavior_class": behavior_by_pos.get(pos_id, "unknown"),
        })

    scored.sort(key=lambda d: (d["risk"] if d["risk"] is not None else -1.0), reverse=True)

    top_25 = []
    for i, row in enumerate(scored[:25], start=1):
        row2 = dict(row)
        row2["rank"] = i
        top_25.append(row2)

    risks = [d["risk"] for d in scored if d["risk"] is not None]

    def _pct(arr, q):
        if not arr:
            return None
        if _np is not None:
            try:
                return float(_np.percentile(arr, q))
            except Exception:
                pass
        a = sorted(arr)
        k = max(0, min(len(a) - 1, int(round((q / 100.0) * (len(a) - 1)))))
        return float(a[k])

    distribution = {
        "p50_risk": _r(_pct(risks, 50)),
        "p75_risk": _r(_pct(risks, 75)),
        "p95_risk": _r(_pct(risks, 95)),
        "max_risk": _r(max(risks)) if risks else None,
        "n_above_risk_1": int(sum(1 for v in risks if v >= 1.0)),
    }

    # positions repeatedly appearing in top25
    count = {}
    for row in top_25:
        key = (row["face"], row["pos_id"])
        e = count.setdefault(key, {
            "face": row["face"], "pos_id": row["pos_id"],
            "x": row["x"], "y": row["y"], "n_in_top25": 0,
        })
        e["n_in_top25"] += 1
    pos_counts = sorted(count.values(), key=lambda d: d["n_in_top25"], reverse=True)[:3]

    max_row = top_25[0] if top_25 else None
    max_summary = None
    if max_row is not None:
        max_summary = {
            "pos_id": max_row["pos_id"],
            "face": max_row["face"],
            "part_id": max_row["part_id"],
            "part_name": max_row["part_name"],
            "risk": max_row["risk"],
        }

    return {
        "ok": True,
        "top_25": top_25,
        "distribution": distribution,
        "top_3_positions_by_count": pos_counts,
        "p95_norm": {
            "peak_g": _r(p95_g),
            "peak_stress": _r(p95_s),
            "peak_disp": _r(p95_d),
        },
        "max_summary": max_summary,
        "n_total": len(scored),
        "unit_labels": dict(getattr(report, "sim_params", {}).get("unit_labels", {}) or {})
            if isinstance(getattr(report, "sim_params", None), dict)
            else dict(getattr(getattr(report, "sim_params", None), "unit_labels", {}) or {}),
    }

# === PHYSICS_PYTHON_HELPERS_INSERT_HERE ===
# Section-08 (Physics Insights) builders are inserted ABOVE this line.


def _build_physics_payload(report) -> dict:
    """Aggregate the Section-08 physics analyses. Empty dict if no data;
    individual sub-keys may be empty. JS hides panels whose sub-key is empty."""
    physics: dict = {}
    physics["StressWaveVelocity"] = _build_stress_wave_velocity_payload(report)
    physics["RestitutionMap"] = _build_restitution_map(report)
    physics["RecoveryDamping"] = _build_recovery_damping_payload(report)
    physics["worst_combinations"] = _build_worst_combinations(report)
    # === PHYSICS_PAYLOAD_EXT_INSERT_HERE ===
    return physics


# === INSIGHT_PYTHON_HELPERS_INSERT_HERE ===
# Section-07 (Insights & Recommendations) builders are inserted ABOVE this line.


def _build_insights_payload(report: ImpactReport) -> dict:
    """Aggregate the six Section-07 insight analyses into one payload.

    Empty dict when no data; individual sub-keys may be empty dicts. The
    JS layer hides panels whose sub-key is empty so this is safe for
    single-d3plot / minimal reports.
    """
    insights: dict = {}
    insights["Symmetry"] = _build_symmetry_insight(report)
    insights["DamageIndex"] = _build_damage_index(report)
    insights["ReboundField"] = _build_rebound_field(report)
    insights["auto_recommend"] = _build_auto_recommend(report)
    insights["ContactPulse"] = _build_contact_pulse(report)
    insights["Trajectory3D"] = _build_trajectory_3d(report)
    # === INSIGHT_PAYLOAD_EXT_INSERT_HERE ===
    # Workflow-added entries assign insights["<key>"] = _build_xxx(report).
    return insights


# === DEEP_PYTHON_HELPERS_INSERT_HERE ===
# Section-06 (Deep Analytics) builders are inserted ABOVE this line.
# Each helper returns a JSON-serializable dict; ``_build_deep_payload``
# below collects them into ``payload["deep_analytics"]``.


def _build_deep_payload(report: ImpactReport) -> dict:
    """Aggregate the six Section-06 advanced analyses into one payload.

    Returns an empty dict when no data is available; individual sub-keys
    may be empty dicts when their producer says so. The JS layer hides
    panels whose sub-key is empty.
    """
    deep: dict = {}
    deep["fft"] = _build_fft_payload(report)
    deep["srs"] = _build_srs_payload(report)
    deep["safe_drop_zone"] = _build_safe_drop_zone(report)
    deep["pca_modal"] = _pca_modal_build(report)
    deep["anomaly_detection"] = _anomaly_detection_helper(report)
    deep["per_part_drilldown"] = _build_per_part_drilldown(report)
    # === DEEP_PAYLOAD_EXT_INSERT_HERE ===
    # Workflow-added entries assign deep["<key>"] = _build_xxx(report).
    return deep


# === ADV_PYTHON_HELPERS_INSERT_HERE ===
# Additional Section-05 analytics builders are inserted ABOVE this line.
# Each helper returns a JSON-serializable dict; ``_build_doe_payload``
# merges them into ``advanced``.


def _build_device_geometry(report: ImpactReport) -> dict:
    """Derive device XY footprint from per-part PartMotion centroids.

    Each PartMotion holds ``disp_x[0]`` / ``disp_y[0]`` — the centroid of the
    part at t=0 in world coordinates. Collecting these across all parts (for
    a single position — they all share the same device) yields the actual
    device extent in XY, which is tighter than the DOE grid bbox.

    Falls back to ``{"source": "grid_fallback"}`` (empty bbox) when no
    PartMotion data is available; callers can then defer to the grid bbox.

    Returns::

        {
          "bbox": [xmin, ymin, xmax, ymax],
          "width": float,
          "height": float,
          "aspect": float,           # width / height, > 1 means wider than tall
          "source": "part_motions" | "grid_fallback",
        }
    """
    raw_motions = getattr(report, "part_motions", None) or {}
    if not raw_motions:
        return {"bbox": None, "width": 0.0, "height": 0.0, "aspect": 0.0,
                "source": "grid_fallback"}

    # Group motions by pos_id; pick the first pos with the most parts so we
    # get the fullest device snapshot. All positions share the same device,
    # but per-pos motion sets can be partial in edge cases.
    by_pos: dict[str, list] = {}
    for key, motion in raw_motions.items():
        if motion is None:
            continue
        try:
            pos_id, _pid = key
        except Exception:  # noqa: BLE001
            continue
        by_pos.setdefault(str(pos_id), []).append(motion)
    if not by_pos:
        return {"bbox": None, "width": 0.0, "height": 0.0, "aspect": 0.0,
                "source": "grid_fallback"}

    # Choose the pos with the most parts (fullest device snapshot).
    best_pos = max(by_pos.items(), key=lambda kv: len(kv[1]))[1]

    xs: list[float] = []
    ys: list[float] = []
    for pm in best_pos:
        dx = getattr(pm, "disp_x", None) or []
        dy = getattr(pm, "disp_y", None) or []
        cx = float(dx[0]) if dx else 0.0
        cy = float(dy[0]) if dy else 0.0
        if math.isnan(cx) or math.isnan(cy) or math.isinf(cx) or math.isinf(cy):
            continue
        xs.append(cx)
        ys.append(cy)

    if not xs or not ys:
        return {"bbox": None, "width": 0.0, "height": 0.0, "aspect": 0.0,
                "source": "grid_fallback"}

    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    width = xmax - xmin
    height = ymax - ymin
    # Single-point edge case (all centroids identical): width/height collapse
    # to zero. Report it honestly — caller decides whether to fall back.
    aspect = (width / height) if height > 0 else 0.0
    return {
        "bbox": [round(xmin, 4), round(ymin, 4), round(xmax, 4), round(ymax, 4)],
        "width": round(width, 4),
        "height": round(height, 4),
        "aspect": round(aspect, 4),
        "source": "part_motions",
    }


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
    # part_name omitted from each entry — JS resolves via parts[] using part_id
    position_top_parts: dict[str, list] = {}
    for pid, rows in position_results.items():
        # collapse multiple entries for same part_id (max peak_g)
        by_part: dict[int, tuple[float, dict]] = {}
        for r in rows:
            part_id = int(r.part_id)
            g_val = _safe(r.peak_g)
            prev = by_part.get(part_id)
            if prev is not None and prev[0] >= g_val:
                continue
            cand = {
                "part_id": part_id,
                "peak_g": _r4(r.peak_g),
                "peak_stress": _r4(r.peak_stress),
                "peak_strain": _r4(r.peak_strain),
                "peak_disp": _r4(r.peak_disp),
                "peak_vel": _r4(r.peak_vel),
            }
            by_part[part_id] = (g_val, cand)
        top = sorted(by_part.values(), key=lambda t: t[0], reverse=True)[:5]
        position_top_parts[pid] = [t[1] for t in top]

    # --- part-position matrices (peak_g + peak_stress) --------------------
    peak_g_matrix: dict[str, dict[str, float]] = {}
    peak_stress_matrix: dict[str, dict[str, float]] = {}
    for r in report.results:
        part_id = int(r.part_id)
        pid = r.position.pos_id
        g = _safe(r.peak_g)
        s = _safe(r.peak_stress)
        gm = peak_g_matrix.setdefault(str(part_id), {})
        if g > gm.get(pid, 0.0):
            gm[pid] = _r4(g)
        sm = peak_stress_matrix.setdefault(str(part_id), {})
        if s > sm.get(pid, 0.0):
            sm[pid] = _r4(s)

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

        # Downsample KE curve to ≤~120 points. Always preserve the argmax
        # and argmin indices so the peak/trough is never silently dropped.
        times = list(getattr(traj, "times", []) or [])
        ke = list(getattr(traj, "ke", []) or [])
        n = min(len(times), len(ke))
        if n > 0:
            step = max(1, n // 120)
            kept = set(range(0, n, step))
            kept.add(n - 1)
            argmax = max(range(n), key=lambda i: ke[i])
            argmin = min(range(n), key=lambda i: ke[i])
            kept.add(argmax)
            kept.add(argmin)
            kept_idx = sorted(kept)
            traj_curves[pos_id] = {
                "t":  [_r4(_safe(times[i])) for i in kept_idx],
                "ke": [_r4(_safe(ke[i]))    for i in kept_idx],
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
    # Mock energy_flow 가 is_mock=false 로 출고되면 (ke_init=100, diss=18.5%)
    # lab 외 reviewer 가 즉시 신뢰 깨짐. 진짜 데이터 없으면 빈 dict — JS 측에서
    # has_real_energy_flow=false 분기 + 'ENERGY FLOW NOT MEASURED' 배지 처리.
    # 데모 path 가 필요하면 환경변수 KOO_IMPACT_USE_MOCK=1 로 gate.
    import os as _os
    energy_flows: dict[str, dict] = {}
    if report.energy_flows:
        for pos_id, flow in report.energy_flows.items():
            energy_flows[pos_id] = _energy_flow_dict(flow)
    if not energy_flows and _os.environ.get("KOO_IMPACT_USE_MOCK") == "1":
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
    # energy_flows 가 비어있으면 (real 데이터 없음 + Mock 차단) diss_pct 는
    # 측정 불가 → None 으로 표시 (JS 측에서 '—' 또는 'N/A' 렌더). 이전 코드는
    # 0.0 으로 fallback 해서 '0%' 가 표시되어 "에너지 0% 흡수" 라는 거짓 의미.
    if energy_flows:
        diss_pct = 0.0
        for fl in energy_flows.values():
            ki = fl.get("ke_init", 0.0)
            d = fl.get("dissipated", 0.0)
            if ki > 0:
                diss_pct = max(diss_pct, 100.0 * d / ki)
    else:
        diss_pct = None  # 측정 불가

    kpi = {
        "n_positions": n_pos,
        "n_faces": len(faces),
        "n_parts": n_parts,
        "n_pairs": n_pairs,
        "worst_g": round(worst["g"], 1) if worst else 0,
        "worst_s": round(max(s_vals) if s_vals else 0.0, 1),
        "n_critical": n_crit,
        "n_safe": n_safe,
        "diss_pct": (round(diss_pct, 1) if diss_pct is not None else None),
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

    # g_divisor: depends on the acc unit declared by the loader/CLI override.
    # Computed below from unit_labels; default 9810 (mm/s²) preserved when
    # detection failed, so legacy reports keep rendering.
    _ul = (report.sim_params or {}).get("unit_labels") or {}
    _acc_for_div = (_ul.get("acc") or "").strip()
    if _acc_for_div == "m/s²":
        _g_div_pm = 9.81
    elif _acc_for_div == "mm/s²":
        _g_div_pm = 9810.0
    elif _acc_for_div == "mm/ms²":
        _g_div_pm = 9.81   # mm/ms² ≡ m/s²
    else:
        _g_div_pm = 9810.0

    part_motion_payload = {
        "summary": summary_rows,
        "series": part_motion_series,
        "impactor_part_id": impactor_part_id,
        "t_first_contact": t_first_contact,
        "g_divisor": _g_div_pm,
        "g_mm_s2": _g_div_pm,  # backward-compat alias
        "acc_unit": _acc_for_div,
    }

    # --- unit labels (data-driven) ------------------------------------------
    # Single source of truth: report.sim_params['unit_labels'] populated by the
    # loader's _detect_unit_system() (or overridden via --units). We mirror
    # whatever it produced here so the JS layer's DATA.unit_labels never falls
    # behind meta.sim_params.unit_labels.
    _sp_unit_labels = (report.sim_params or {}).get("unit_labels") or {}
    unit_labels = {
        "acc":    _sp_unit_labels.get("acc",    "") or "",
        "stress": _sp_unit_labels.get("stress", "") or "",
        "disp":   _sp_unit_labels.get("disp",   "") or "",
        "vel":    _sp_unit_labels.get("vel",    "") or "",
        "energy": _sp_unit_labels.get("energy", "") or "",
        "time":   _sp_unit_labels.get("time",   "") or "",
        "mass":   _sp_unit_labels.get("mass",   "") or "",
        "force":  _sp_unit_labels.get("force",  "") or "",
    }
    # Acceleration→g divisor matches the unit system: 9.81 m/s² = 1 g.
    _acc_unit = unit_labels.get("acc", "")
    if _acc_unit == "m/s²":
        _g_div = 9.81
    elif _acc_unit == "mm/s²":
        _g_div = 9810.0
    elif _acc_unit in ("mm/ms²", "m/s²"):  # mm/ms² ≡ m/s²
        _g_div = 9.81
    else:
        _g_div = 9810.0  # legacy default — matches pre-fix JS behaviour

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
        "deep_analytics": _build_deep_payload(report),
        "insights": _build_insights_payload(report),
        "physics": _build_physics_payload(report),
        "unit_labels": unit_labels,
        "device_geometry": _build_device_geometry(report),
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
  --device-aspect: 1;
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
.doe-grid-wrap svg { width: 100%; display: block; aspect-ratio: var(--device-aspect, 1); }
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
.doe-failrisk-grid{display:grid;gap:4px;aspect-ratio:var(--device-aspect, 1);background:var(--bg3);padding:4px;border-radius:4px;}
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
#idw-pred-canvas { max-height:560px; }
#idw-pred-stack { max-height:560px; }
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

#deep-fft-panel .panel-header { display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; }
#deep-fft-panel .deep-fft-meta { display:flex; gap:6px; flex-wrap:wrap; }
#deep-fft-panel .deep-fft-pill {
  font-size:11px; padding:2px 8px; border-radius:10px;
  background:#1a1d24; color:#cfd6e4; border:1px solid #2a2f3a;
}
#deep-fft-panel .deep-fft-body {
  display:grid; grid-template-columns:repeat(auto-fill, minmax(210px, 1fr));
  gap:10px;
}
#deep-fft-panel .deep-fft-card {
  background:#15171c; border:1px solid #23262d; border-radius:6px;
  padding:8px; display:flex; flex-direction:column; gap:4px;
}
#deep-fft-panel .deep-fft-card-head {
  display:flex; justify-content:space-between; align-items:baseline; gap:6px;
}
#deep-fft-panel .deep-fft-name {
  font-size:12px; color:#e6ecf5; font-weight:600;
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
  max-width:150px;
}
#deep-fft-panel .deep-fft-pid {
  font-size:10px; color:#8892a0; font-family:monospace;
}
#deep-fft-panel .deep-fft-svg { display:block; width:100%; height:40px; }
#deep-fft-panel .deep-fft-text {
  display:flex; justify-content:space-between; align-items:baseline;
  font-size:11px; color:#b8c0cf;
}
#deep-fft-panel .deep-fft-fdom { color:#7ad7ff; font-family:monospace; }
#deep-fft-panel .deep-fft-n { color:#8892a0; font-family:monospace; }
#deep-fft-panel .deep-empty {
  padding:24px; text-align:center; color:#8892a0; font-size:13px;
}

.deep-srs-panel .srs-body { width: 100%; }
.deep-srs-panel .srs-chart { display: block; margin: 4px 0 8px 0; background: transparent; }
.deep-srs-panel .srs-meta { color: #9aa7b8; font-size: 11px; margin: 6px 2px 2px 2px; }
.deep-srs-panel .srs-caption { color: #cfd6e0; font-size: 12px; margin: 2px 2px 0 2px; }
.deep-srs-panel .empty-note { color: #9aa7b8; font-size: 12px; padding: 24px; text-align: center; border: 1px dashed #2a3340; border-radius: 4px; }
#deep-safe-drop-zone-panel .panel-header { padding: 14px 16px 4px; }
#deep-safe-drop-zone-panel .panel-header h3 { margin: 0; font-size: 15px; color: #e6ebf0; }
#deep-safe-drop-zone-panel .panel-sub { font-size: 11px; color: #8a96a3; margin-top: 4px; }
#deep-safe-drop-zone-panel .kpi-box { transition: transform 0.15s; }
#deep-safe-drop-zone-panel .kpi-box:hover { transform: translateX(2px); }

#deep-pca-modal-panel .pca-summary{
  font-size:12.5px; color:#cbd5e1; margin-bottom:10px;
  display:flex; flex-wrap:wrap; align-items:center; gap:2px;
}
#deep-pca-modal-panel .pca-summary .sep{opacity:.55;}
#deep-pca-modal-panel .pca-mode-row{
  border:1px solid #233040; border-radius:8px;
  padding:10px 12px; margin-bottom:10px; background:rgba(20,28,38,0.45);
}
#deep-pca-modal-panel .pca-mode-head{
  display:grid; grid-template-columns: 90px 130px 1fr;
  align-items:center; gap:10px; margin-bottom:8px;
}
#deep-pca-modal-panel .pca-mode-title{font-weight:600; color:#e2e8f0; font-size:13.5px;}
#deep-pca-modal-panel .pca-mode-evr{font-size:12px; color:#94a3b8;}
#deep-pca-modal-panel .pca-mode-bar-track{
  height:8px; background:#1c2530; border-radius:4px; overflow:hidden;
}
#deep-pca-modal-panel .pca-mode-bar-fill{
  height:100%; background:linear-gradient(90deg,#3b82f6,#22d3ee);
}
#deep-pca-modal-panel .pca-mode-body{
  display:grid; grid-template-columns: 1fr 260px; gap:14px;
}
@media (max-width: 900px){
  #deep-pca-modal-panel .pca-mode-body{grid-template-columns: 1fr;}
}
#deep-pca-modal-panel .pca-sub-title{
  font-size:12px; color:#94a3b8; margin-bottom:6px; letter-spacing:.02em;
}
#deep-pca-modal-panel .pca-loading-list{display:flex; flex-direction:column; gap:3px;}
#deep-pca-modal-panel .pca-load-item{
  display:grid; grid-template-columns: 140px 1fr 52px;
  align-items:center; gap:6px; font-size:11.5px;
}
#deep-pca-modal-panel .pca-load-label{
  color:#cbd5e1; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
}
#deep-pca-modal-panel .pca-load-bar-wrap{
  position:relative; height:14px; background:#141b24; border-radius:3px;
}
#deep-pca-modal-panel .pca-load-axis{
  position:absolute; left:50%; top:0; bottom:0; width:1px; background:#3a4a5e;
}
#deep-pca-modal-panel .pca-load-bar{
  position:absolute; top:2px; bottom:2px; border-radius:2px;
}
#deep-pca-modal-panel .pca-load-bar.pos{background:#dc322f;}
#deep-pca-modal-panel .pca-load-bar.neg{background:#2166ac;}
#deep-pca-modal-panel .pca-load-val{text-align:right; font-variant-numeric:tabular-nums;}
#deep-pca-modal-panel .pca-load-val.pos{color:#fca5a5;}
#deep-pca-modal-panel .pca-load-val.neg{color:#93c5fd;}
#deep-pca-modal-panel .pca-spatial{display:flex; flex-direction:column; align-items:center;}
#deep-pca-modal-panel .pca-grid{display:block;}
#deep-pca-modal-panel .pca-legend{
  margin-top:6px; display:flex; align-items:center; gap:6px;
  font-size:10.5px; color:#94a3b8;
}
#deep-pca-modal-panel .pca-legend-bar{
  width:140px; height:8px; border-radius:2px;
  background:linear-gradient(90deg,#2166ac,#f5eee8,#dc322f);
}
#deep-pca-modal-panel .pca-caption{
  margin-top:8px; font-size:11.5px; color:#94a3b8; font-style:italic;
}
#deep-pca-modal-panel .empty-note{color:#94a3b8; font-style:italic; padding:8px 0;}
#deep-pca-modal-panel .empty-note.small{font-size:11px; padding:4px 0;}

.deep-anomaly-detection .anom-head{margin-bottom:10px;}
.deep-anomaly-detection .anom-summary{display:flex;flex-wrap:wrap;gap:14px;font-size:12px;color:#cfcfd6;}
.deep-anomaly-detection .anom-stat{padding:4px 10px;background:#23232a;border-radius:6px;border:1px solid #34343d;}
.deep-anomaly-detection .anom-facewrap{margin:8px 0;font-size:12px;color:#cfcfd6;}
.deep-anomaly-detection .anom-face-sel{margin-left:6px;background:#1d1d24;color:#eaeaf0;border:1px solid #3a3a44;padding:3px 6px;border-radius:4px;}
.deep-anomaly-detection .anom-body{display:grid;grid-template-columns:auto 1fr;gap:18px;align-items:start;}
.deep-anomaly-detection .anom-heatmap{display:block;}
.deep-anomaly-detection .anom-table{width:100%;border-collapse:collapse;font-size:12px;}
.deep-anomaly-detection .anom-table th,
.deep-anomaly-detection .anom-table td{padding:5px 8px;border-bottom:1px solid #2c2c34;text-align:center;}
.deep-anomaly-detection .anom-table th{background:#202028;color:#cfcfd6;font-weight:600;}
.deep-anomaly-detection .anom-table td.anom-zmax{color:#ff8a8a;font-weight:600;}
.deep-anomaly-detection .anom-table td.anom-driver{color:#ffd27f;}
.deep-anomaly-detection .anom-iqr-list{margin-top:12px;padding:8px 10px;background:#1e1e25;border:1px solid #2f2f38;border-radius:6px;font-size:12px;color:#dcdce4;}
.deep-anomaly-detection .anom-iqr-title{font-weight:600;color:#eaeaf0;margin-bottom:6px;}
.deep-anomaly-detection .anom-iqr-ul{margin:0;padding-left:14px;}
.deep-anomaly-detection .anom-iqr-ul li{margin:2px 0;}
.deep-anomaly-detection .anom-iqr-agree .anom-iqr-tag{color:#7fff9c;font-weight:600;}
.deep-anomaly-detection .anom-iqr-only{color:#9a9aa3;text-decoration:line-through;}
.deep-anomaly-detection .anom-iqr-only .anom-iqr-tag{color:#ffd27f;font-weight:600;text-decoration:none;}
.deep-anomaly-detection .anom-empty{color:#7a7a82;font-style:italic;}
.deep-anomaly-detection .anom-caption{margin-top:10px;font-size:11px;color:#9a9aa3;font-style:italic;}
.deep-anomaly-detection .empty{padding:18px;color:#7a7a82;text-align:center;font-style:italic;}

.ppd-caption { color: #aab2cf; font-size: 11px; margin-bottom: 8px; }
.ppd-layout {
  display: grid;
  grid-template-columns: 260px 1fr;
  gap: 12px;
  align-items: start;
}
.ppd-left {
  background: #0e1220;
  border: 1px solid #262d44;
  border-radius: 6px;
  padding: 6px;
  max-height: 720px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.ppd-left-head {
  font-size: 10px;
  color: #5c6383;
  padding: 4px 6px 6px 6px;
  border-bottom: 1px solid #262d44;
  margin-bottom: 4px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.ppd-list {
  overflow-y: auto;
  flex: 1;
  padding-right: 2px;
}
.ppd-list-row {
  display: grid;
  grid-template-columns: 1fr;
  gap: 2px;
  padding: 5px 6px;
  border-radius: 4px;
  cursor: pointer;
  border: 1px solid transparent;
  margin-bottom: 2px;
}
.ppd-list-row:hover { background: #1a1e2e; }
.ppd-list-row.active {
  background: #1a233e;
  border-color: #3b528b;
}
.ppd-list-name {
  color: #e0e4ff;
  font-size: 11px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.ppd-list-val {
  display: grid;
  grid-template-columns: 1fr 54px;
  align-items: center;
  gap: 6px;
}
.ppd-list-bar-bg {
  height: 6px;
  background: #1a1e2e;
  border-radius: 3px;
  overflow: hidden;
}
.ppd-list-bar { height: 100%; border-radius: 3px; transition: width 0.15s; }
.ppd-list-num {
  color: #aab2cf;
  font-size: 10px;
  font-variant-numeric: tabular-nums;
  text-align: right;
}
.ppd-right { display: flex; flex-direction: column; gap: 8px; }
.ppd-detail-title {
  color: #e0e4ff;
  font-size: 13px;
  padding: 4px 6px;
  background: #1a1e2e;
  border-radius: 4px;
  border-left: 3px solid #3b528b;
}
.ppd-kpi-strip {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 6px;
}
.ppd-kpi-tile {
  background: #0e1220;
  border: 1px solid #262d44;
  border-radius: 4px;
  padding: 6px 8px;
}
.ppd-kpi-label {
  font-size: 9px;
  color: #5c6383;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: 2px;
}
.ppd-kpi-val {
  font-size: 14px;
  color: #e0e4ff;
  font-variant-numeric: tabular-nums;
}
.ppd-kpi-unit { font-size: 9px; color: #5c6383; }
.ppd-grid2 {
  display: grid;
  grid-template-columns: 340px 1fr;
  gap: 8px;
}
.ppd-tile {
  background: #0e1220;
  border: 1px solid #262d44;
  border-radius: 6px;
  padding: 8px;
}
.ppd-tile-head {
  font-size: 10px;
  color: #5c6383;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: 6px;
}
.ppd-svg-square { width: 100%; height: 320px; display: block; }
.ppd-svg-wide   { width: 100%; height: 200px; display: block; }
.ppd-empty {
  color: #5c6383;
  font-size: 11px;
  text-align: center;
  padding: 16px;
}
@media (max-width: 1024px) {
  .ppd-layout { grid-template-columns: 1fr; }
  .ppd-grid2  { grid-template-columns: 1fr; }
  .ppd-kpi-strip { grid-template-columns: repeat(3, 1fr); }
}

/* DEEP_CSS_INSERT_HERE */

#insight-symmetry .sym-kpis{display:grid;grid-template-columns:repeat(4,minmax(140px,1fr));gap:10px;margin-bottom:10px}
#insight-symmetry .sym-kpi{background:#0f1623;border:1px solid #243245;border-radius:8px;padding:10px 12px}
#insight-symmetry .sym-kpi-lbl{font-size:11px;color:#8aa0bd;letter-spacing:.02em;margin-bottom:4px}
#insight-symmetry .sym-kpi-val{font-size:22px;font-weight:600;color:#e6eefc}
#insight-symmetry .sym-kpi-val-sm{font-size:15px}
#insight-symmetry .sym-kpi-suf{font-size:11px;color:#8aa0bd;font-weight:400;margin-left:3px}
#insight-symmetry .sym-kpi-meta{grid-column:span 1}
#insight-symmetry .sym-verdict{padding:8px 12px;border-radius:6px;font-size:13px;font-weight:500;margin-bottom:12px}
#insight-symmetry .sym-verdict.ok{background:#0f2a1d;border:1px solid #1f5a3d;color:#7fd4a3}
#insight-symmetry .sym-verdict.warn{background:#2a1a12;border:1px solid #6b3a1f;color:#f0a878}
#insight-symmetry .sym-tables{display:grid;grid-template-columns:1fr 1fr;gap:14px}
#insight-symmetry .sym-tblbox{background:#0c1320;border:1px solid #1f2c40;border-radius:8px;padding:10px}
#insight-symmetry .sym-tbl-title{font-size:13px;color:#cfd9ea;margin-bottom:6px;font-weight:600}
#insight-symmetry .sym-tbl-sub{font-size:11px;color:#7d8da8;font-weight:400;margin-left:6px}
#insight-symmetry .sym-tbl{width:100%;border-collapse:collapse;font-size:12px}
#insight-symmetry .sym-tbl th{text-align:right;color:#8aa0bd;font-weight:500;padding:4px 6px;border-bottom:1px solid #1f2c40}
#insight-symmetry .sym-tbl th:first-child{text-align:left}
#insight-symmetry .sym-tbl td{padding:4px 6px;border-bottom:1px solid #141d2c;color:#dde6f5}
#insight-symmetry .sym-tbl td.sym-pair{font-family:ui-monospace,Menlo,monospace;color:#a8c2ee}
#insight-symmetry .sym-tbl td.sym-num{text-align:right;font-variant-numeric:tabular-nums}
#insight-symmetry .sym-tbl td.sym-asym{font-weight:600}
#insight-symmetry .sym-tbl tr.mid td.sym-asym{color:#f0c878}
#insight-symmetry .sym-tbl tr.hi td.sym-asym{color:#f08878}
#insight-symmetry .sym-foot{margin-top:10px;font-size:11px;color:#7d8da8;line-height:1.5}
#insight-symmetry .ins-empty{color:#7d8da8;font-size:12px;padding:8px 0;text-align:center}
@media (max-width:900px){
  #insight-symmetry .sym-kpis{grid-template-columns:repeat(2,1fr)}
  #insight-symmetry .sym-tables{grid-template-columns:1fr}
}
#insight-DamageIndex .insight-title{font-weight:600;font-size:15px;margin-bottom:8px;color:#222;}
#insight-DamageIndex .di-caption{font-size:12px;color:#444;background:#fafafa;border-left:3px solid #b30000;padding:6px 10px;margin-bottom:10px;border-radius:2px;}
#insight-DamageIndex .di-wrap{display:flex;gap:18px;align-items:flex-start;flex-wrap:wrap;}
#insight-DamageIndex .di-left{flex:0 0 auto;}
#insight-DamageIndex .di-right{flex:1 1 280px;min-width:280px;}
#insight-DamageIndex .di-subtitle{font-size:13px;font-weight:600;color:#333;margin-bottom:6px;}
#insight-DamageIndex .di-svg{display:block;}
#insight-DamageIndex .di-label{font-size:11px;fill:#333;font-family:monospace;}
#insight-DamageIndex .di-value{font-size:11px;fill:#222;font-family:monospace;dominant-baseline:middle;}
#insight-DamageIndex .di-bar{cursor:default;}
#insight-DamageIndex .di-bar:hover{stroke:#000;stroke-width:1;}
#insight-DamageIndex .di-pair-list{list-style:none;padding:0;margin:0;}
#insight-DamageIndex .di-pair-list li{display:grid;grid-template-columns:24px 1fr 120px 50px;gap:6px;align-items:center;padding:4px 0;font-size:12px;border-bottom:1px solid #eee;}
#insight-DamageIndex .di-rank{font-weight:700;color:#b30000;text-align:center;}
#insight-DamageIndex .di-pair-name{font-family:monospace;color:#222;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
#insight-DamageIndex .di-pair-bar{background:#f6f6f6;border:1px solid #e5e5e5;height:12px;position:relative;border-radius:2px;overflow:hidden;}
#insight-DamageIndex .di-pair-fill{display:block;height:100%;}
#insight-DamageIndex .di-pair-val{font-family:monospace;font-size:11px;text-align:right;color:#222;}
#insight-DamageIndex .di-empty{padding:10px;color:#888;font-size:12px;font-style:italic;}
.rf-panel{padding:14px 16px;background:#161b22;border:1px solid #30363d;border-radius:8px;margin:12px 0;}
.rf-panel .insight-head h3{margin:0 0 4px 0;font-size:15px;color:#e6edf3;}
.rf-panel .insight-sub{margin:0 0 10px 0;font-size:12px;color:#8b949e;}
.rf-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:8px;margin-bottom:10px;}
.rf-kpi{background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:6px 10px;display:flex;flex-direction:column;}
.rf-kpi-lbl{font-size:11px;color:#8b949e;}
.rf-kpi-val{font-size:14px;color:#e6edf3;font-variant-numeric:tabular-nums;margin-top:2px;}
.rf-kpi-val.rf-up{color:#4493f8;}
.rf-kpi-val.rf-down{color:#f85149;}
.rf-svg-wrap{display:flex;justify-content:center;background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:8px;}
.rf-svg-wrap svg{max-width:520px;width:100%;height:auto;}
.rf-caption{margin:8px 0 0 0;font-size:11px;color:#8b949e;line-height:1.5;}
.insight-empty{padding:20px;color:#8b949e;text-align:center;font-size:12px;}
#insight-panel-auto-recommend .ar-summary {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
#insight-panel-auto-recommend .ar-chip {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
  background: #2a2f3a;
  color: #d0d5dd;
}
#insight-panel-auto-recommend .ar-chip-total    { background: #2a2f3a; color: #e6e8ec; }
#insight-panel-auto-recommend .ar-chip-critical { background: #4a1d1d; color: #ff8a8a; }
#insight-panel-auto-recommend .ar-chip-warning  { background: #4a3a14; color: #ffc266; }
#insight-panel-auto-recommend .ar-chip-info     { background: #1d3a4a; color: #80c8ff; }
#insight-panel-auto-recommend .ar-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 10px;
}
#insight-panel-auto-recommend .ar-card {
  display: flex;
  background: #1c2029;
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid #2a2f3a;
}
#insight-panel-auto-recommend .ar-stripe {
  width: 6px;
  flex-shrink: 0;
}
#insight-panel-auto-recommend .ar-critical .ar-stripe { background: #d94545; }
#insight-panel-auto-recommend .ar-warning  .ar-stripe { background: #f08a24; }
#insight-panel-auto-recommend .ar-info     .ar-stripe { background: #3a90d8; }
#insight-panel-auto-recommend .ar-main {
  padding: 10px 12px;
  flex: 1;
  min-width: 0;
}
#insight-panel-auto-recommend .ar-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
  flex-wrap: wrap;
}
#insight-panel-auto-recommend .ar-sev-tag {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 4px;
  letter-spacing: 0.5px;
}
#insight-panel-auto-recommend .ar-critical .ar-sev-tag { background: #d94545; color: #fff; }
#insight-panel-auto-recommend .ar-warning  .ar-sev-tag { background: #f08a24; color: #fff; }
#insight-panel-auto-recommend .ar-info     .ar-sev-tag { background: #3a90d8; color: #fff; }
#insight-panel-auto-recommend .ar-title {
  font-size: 13px;
  font-weight: 600;
  color: #e6e8ec;
  flex: 1;
  min-width: 0;
}
#insight-panel-auto-recommend .ar-metric {
  font-family: ui-monospace, Menlo, monospace;
  font-size: 12px;
  color: #b0b8c4;
  background: #252a35;
  padding: 2px 6px;
  border-radius: 3px;
}
#insight-panel-auto-recommend .ar-body {
  font-size: 12.5px;
  line-height: 1.5;
  color: #c0c5d0;
  margin-bottom: 8px;
}
#insight-panel-auto-recommend .ar-source {
  font-size: 11px;
  display: flex;
  align-items: center;
  gap: 6px;
}
#insight-panel-auto-recommend .ar-source-label { color: #8088a0; }
#insight-panel-auto-recommend .ar-source-tag {
  background: #2a2f3a;
  color: #9bb3d4;
  padding: 2px 8px;
  border-radius: 10px;
  border: 1px solid #354055;
}
#insight-panel-auto-recommend .insight-empty {
  color: #8088a0;
  font-style: italic;
  padding: 16px;
  text-align: center;
}

#insight-panel-ContactPulse .insight-header h3{margin:0;font-size:15px;color:#e8e8e8;}
#insight-panel-ContactPulse .insight-sub{font-size:11px;color:#888;margin-top:2px;}
#insight-panel-ContactPulse .insight-body{padding:8px 4px;}
#insight-panel-ContactPulse .ins-empty{color:#888;padding:18px;text-align:center;font-size:12px;}
#insight-panel-ContactPulse .cp-grid{display:grid;grid-template-columns:1fr 320px;gap:14px;align-items:start;}
#insight-panel-ContactPulse .cp-title{font-size:12px;color:#cfcfcf;margin-bottom:6px;font-weight:600;}
#insight-panel-ContactPulse .cp-heatmap-wrap, #insight-panel-ContactPulse .cp-hist-wrap{background:#161616;border:1px solid #2a2a2a;border-radius:4px;padding:8px;}
#insight-panel-ContactPulse .cp-hm-svg{display:block;}
#insight-panel-ContactPulse .cp-legend{margin-top:6px;}
#insight-panel-ContactPulse .cp-legend-bar{display:flex;height:8px;width:100%;border-radius:2px;overflow:hidden;}
#insight-panel-ContactPulse .cp-legend-bar span{flex:1;display:block;}
#insight-panel-ContactPulse .cp-legend-labels{display:flex;justify-content:space-between;font-size:10px;color:#999;margin-top:2px;}
#insight-panel-ContactPulse .cp-hist-svg{display:block;}
#insight-panel-ContactPulse .cp-stats{margin-top:8px;display:grid;grid-template-columns:1fr 1fr;gap:4px 12px;font-size:11px;color:#bbb;}
#insight-panel-ContactPulse .cp-stats span{color:#888;margin-right:4px;}
#insight-panel-ContactPulse .cp-stats b{color:#f0c674;font-weight:600;}
#insight-panel-ContactPulse .cp-rank-wrap{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:12px;}
#insight-panel-ContactPulse .cp-rank-col{background:#161616;border:1px solid #2a2a2a;border-radius:4px;padding:8px;}
#insight-panel-ContactPulse .cp-rank-tbl{width:100%;border-collapse:collapse;font-size:11px;color:#ccc;}
#insight-panel-ContactPulse .cp-rank-tbl th{text-align:left;border-bottom:1px solid #333;padding:3px 4px;color:#999;font-weight:500;}
#insight-panel-ContactPulse .cp-rank-tbl td{padding:3px 4px;border-bottom:1px solid #222;}
#insight-panel-ContactPulse .cp-rank-tbl tr:hover td{background:#1f1f1f;}
#insight-panel-ContactPulse .cp-caption{margin-top:10px;padding:8px 10px;background:#181818;border-left:3px solid #f0c674;font-size:11px;color:#bbb;line-height:1.5;}
#insight-panel-ContactPulse .cp-empty{color:#666;font-size:11px;padding:8px;text-align:center;}
#insight-panel-trajectory3d .insight-head{margin-bottom:8px}
#insight-panel-trajectory3d .insight-head h3{margin:0;font-size:15px;color:#e6eefc;font-weight:600}
#insight-panel-trajectory3d .insight-sub{margin:2px 0 0;font-size:11px;color:#7d8da8}
#insight-panel-trajectory3d .t3d-svg-wrap{background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:8px;display:flex;justify-content:center;min-height:360px}
#insight-panel-trajectory3d .t3d-svg-wrap svg{max-width:720px;width:100%;display:block}
#insight-panel-trajectory3d .t3d-caption{margin:8px 0 0;font-size:11px;color:#8aa0bd;text-align:center}
#insight-panel-trajectory3d .insight-empty{color:#7d8da8;font-size:12px;padding:24px 0;text-align:center;width:100%}
/* Intra-section sub-tabs (Sections 05/06/07) */
.subtab-bar { display: flex; gap: 4px; margin: 8px 0 12px; border-bottom: 1px solid var(--line); padding-bottom: 0; flex-wrap: wrap; }
.subtab-bar button {
  background: transparent; border: none; color: var(--dim); padding: 8px 14px;
  font-size: 10px; letter-spacing: 1.5px; font-weight: 600; text-transform: uppercase;
  cursor: pointer; border-bottom: 2px solid transparent; transition: all 0.15s;
  font-family: 'JetBrains Mono', monospace;
}
.subtab-bar button:hover { color: var(--fg2); }
.subtab-bar button.active { color: var(--accent); border-bottom-color: var(--accent); }
.subtab-content { display: none; }
.subtab-content.active { display: block; }
#physics-stress-wave-velocity .phys-caption{
  color:#bcd; font-size:12px; margin:4px 0 10px 0; line-height:1.5;
}
#physics-stress-wave-velocity .phys-empty{
  color:#a99; font-size:12px; padding:14px; border:1px dashed #553;
  border-radius:6px; line-height:1.55;
}
#physics-stress-wave-velocity .phys-chips{
  display:flex; flex-wrap:wrap; gap:6px; margin:0 0 10px 0;
}
#physics-stress-wave-velocity .phys-chip{
  background:#1b2330; color:#d8e2ee; font-size:11px; padding:3px 8px;
  border-radius:10px; border:1px solid #2a3548;
}
#physics-stress-wave-velocity .phys-chip b{ color:#ffd17a; margin-right:4px; }
#physics-stress-wave-velocity .phys-swv-chart{ display:block; max-width:100%; height:auto; }
#physics-stress-wave-velocity .phys-axis-tick{ fill:#aab; font-size:10px; }
#physics-stress-wave-velocity .phys-axis-label{ fill:#cde; font-size:11px; }
#physics-stress-wave-velocity .phys-row-label{ fill:#dde; font-size:11px; cursor:default; }
#physics-stress-wave-velocity .phys-row-value{ fill:#fff; font-size:10px; }
#physics-stress-wave-velocity .phys-theory-label{
  fill:#ff8a8a; font-size:11px; font-weight:600;
}
/* PHYSICS_CSS_INSERT_HERE — RestitutionMap */
#phys-restitution-map .rmap-kpi-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(120px, 1fr));
  gap: 10px;
  margin: 10px 0 14px 0;
}
#phys-restitution-map .rmap-kpi {
  background: #1a1f2b;
  border: 1px solid #2a2f3a;
  border-radius: 6px;
  padding: 8px 10px;
}
#phys-restitution-map .rmap-kpi-wide { grid-column: span 1; }
#phys-restitution-map .rmap-kpi-label {
  font-size: 11px;
  color: #8a93a3;
  margin-bottom: 3px;
  letter-spacing: 0.2px;
}
#phys-restitution-map .rmap-kpi-value {
  font-size: 15px;
  color: #e6ebf3;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
#phys-restitution-map .rmap-grid {
  display: grid;
  grid-template-columns: minmax(320px, 1.1fr) minmax(280px, 1fr);
  gap: 14px;
  margin-bottom: 10px;
}
@media (max-width: 880px) {
  #phys-restitution-map .rmap-grid { grid-template-columns: 1fr; }
  #phys-restitution-map .rmap-kpi-row { grid-template-columns: repeat(2, 1fr); }
}
#phys-restitution-map .rmap-section-title {
  font-size: 12px;
  color: #cfd5e1;
  margin-bottom: 6px;
  font-weight: 500;
}
#phys-restitution-map .rmap-heat-host,
#phys-restitution-map .rmap-hist-host {
  background: #11151d;
  border: 1px solid #2a2f3a;
  border-radius: 6px;
  padding: 6px;
}
#phys-restitution-map .rmap-caption {
  font-size: 12px;
  color: #8a93a3;
  font-style: italic;
  padding: 8px 10px;
  border-left: 3px solid #3a4150;
  background: #14181f;
  border-radius: 0 4px 4px 0;
  line-height: 1.5;
}
#phys-restitution-map .rmap-chip {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 8px;
  font-size: 9px;
  color: #fff;
  margin-left: 4px;
}
#phys-restitution-map .panel-sub {
  font-size: 12px;
  color: #8a93a3;
}

#phys-recovery-damping-panel .phys-rd-head{
  display:flex; flex-wrap:wrap; gap:8px 18px;
  padding:8px 4px 12px 4px; border-bottom:1px solid #2a3038; margin-bottom:10px;
}
#phys-recovery-damping-panel .phys-rd-kpi{ min-width:140px; }
#phys-recovery-damping-panel .phys-rd-kpi .k{
  font-size:10px; color:#8b949e; text-transform:uppercase; letter-spacing:0.04em;
}
#phys-recovery-damping-panel .phys-rd-kpi .v{ font-size:14px; color:#e6edf3; font-weight:600; margin-top:2px; }
#phys-recovery-damping-panel .phys-rd-kpi .v.vbad{ color:#ff8c00; }
#phys-recovery-damping-panel .phys-rd-kpi .v.vgood{ color:#3cc85a; }
#phys-recovery-damping-panel .phys-rd-grid{
  display:grid; grid-template-columns:1fr 1fr; gap:14px;
}
@media (max-width: 900px){
  #phys-recovery-damping-panel .phys-rd-grid{ grid-template-columns:1fr; }
}
#phys-recovery-damping-panel .phys-rd-col{ background:#0d1117; border:1px solid #2a3038; border-radius:6px; padding:6px; }
#phys-recovery-damping-panel .phys-rd-bars{ display:block; }
#phys-recovery-damping-panel .phys-rd-caption{
  margin-top:10px; font-size:11px; color:#8b949e; line-height:1.5;
}
#phys-recovery-damping-panel .phys-rd-empty{
  padding:16px; color:#8b949e; font-size:12px; line-height:1.5;
  border:1px dashed #2a3038; border-radius:6px;
}
/* WorstCombinations panel */
#phys-worst-combinations .wc-empty {
  padding: 18px;
  color: #777;
  font-size: 13px;
  background: #fafafa;
  border: 1px dashed #ccc;
  border-radius: 6px;
}
#phys-worst-combinations .wc-kpi-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}
#phys-worst-combinations .wc-kpi {
  background: #f7f8fa;
  border: 1px solid #e3e6ec;
  border-radius: 6px;
  padding: 10px 12px;
}
#phys-worst-combinations .wc-kpi-critical {
  background: #fff4f3;
  border-color: #f1bdb6;
}
#phys-worst-combinations .wc-kpi-label {
  font-size: 11px;
  color: #6a7282;
  letter-spacing: 0.02em;
  margin-bottom: 4px;
}
#phys-worst-combinations .wc-kpi-value {
  font-size: 22px;
  font-weight: 600;
  color: #1f2730;
  line-height: 1.1;
}
#phys-worst-combinations .wc-kpi-value-sm {
  font-size: 13px;
  font-weight: 500;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
#phys-worst-combinations .wc-kpi-sub {
  font-size: 11px;
  color: #8a8f99;
  margin-top: 2px;
}
#phys-worst-combinations .wc-chip-row {
  margin: 6px 0 10px 0;
  font-size: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}
#phys-worst-combinations .wc-chip-label {
  color: #6a7282;
}
#phys-worst-combinations .wc-chip {
  background: #eef2f7;
  border: 1px solid #d6dde6;
  border-radius: 999px;
  padding: 2px 9px;
  font-size: 11.5px;
  color: #2b3340;
}
#phys-worst-combinations .wc-table-wrap {
  max-height: 460px;
  overflow: auto;
  border: 1px solid #e3e6ec;
  border-radius: 6px;
}
#phys-worst-combinations .wc-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
#phys-worst-combinations .wc-th {
  position: sticky;
  top: 0;
  background: #f0f3f8;
  text-align: left;
  padding: 7px 9px;
  font-weight: 600;
  font-size: 11.5px;
  color: #2b3340;
  border-bottom: 1px solid #d6dde6;
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
}
#phys-worst-combinations .wc-th-num { text-align: right; }
#phys-worst-combinations .wc-th:hover { background: #e6ebf2; }
#phys-worst-combinations .wc-td {
  padding: 5px 9px;
  border-bottom: 1px solid #eef0f3;
  white-space: nowrap;
}
#phys-worst-combinations .wc-td-num {
  text-align: right;
  font-variant-numeric: tabular-nums;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
#phys-worst-combinations .wc-row:hover .wc-td { background: #fafbfd; }
#phys-worst-combinations .wc-risk-red {
  background: #fde7e4 !important;
  color: #a8261a;
  font-weight: 600;
}
#phys-worst-combinations .wc-risk-orange {
  background: #fff1dc !important;
  color: #9a5a05;
  font-weight: 600;
}
#phys-worst-combinations .wc-risk-gray {
  background: #f1f3f5 !important;
  color: #4a525d;
}
#phys-worst-combinations .wc-risk-na {
  color: #98a0aa;
}
#phys-worst-combinations .wc-sort-ind {
  font-size: 10px;
  color: #6a7282;
}
#phys-worst-combinations .wc-caption {
  margin-top: 10px;
  font-size: 11.5px;
  color: #6a7282;
  line-height: 1.5;
}

/* PHYSICS_CSS_INSERT_HERE */

/* INSIGHT_CSS_INSERT_HERE */
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
    <a data-target="s6" id="navS6">DEEP</a>
    <a data-target="s7" id="navS7">INSIGHTS</a>
    <a data-target="s8" id="navS8">PHYSICS</a>
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
      <!-- data-quality 배지 (JS 가 채움) — synthetic geometry / mock-blocked energy 등 -->
      <div id="data-quality-badges" style="margin:6px 0 8px 0;display:flex;gap:6px;flex-wrap:wrap"></div>
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
    <div class="k"><div class="v" id="kWorstG">__WORST_G__<span class="u">G</span></div><div class="l">WORST PEAK G</div><div class="cap" style="font-size:8px;letter-spacing:0.3px;color:var(--dim);margin-top:2px" title="LSDYNA 의 element 별 nodal acceleration 의 max — mesh 거칠기/contact penalty 의 영향을 받는 raw 값. 디바이스 평균이 아님.">element-local peak</div></div>
    <div class="k"><div class="v" id="kWorstS">__WORST_S__<span class="u" id="kWorstSUnit"></span></div><div class="l">WORST STRESS</div><div class="cap" style="font-size:8px;letter-spacing:0.3px;color:var(--dim);margin-top:2px" title="element 별 stress 의 global max — mesh 거칠기 영향을 받는 raw 값. 평균 아님.">element-local peak</div></div>
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

    <div class="ctlbar r" id="doe-ctlbar">
      <div class="grp"><span class="lbl">METRIC</span><span id="doe-metric-buttons"></span></div>
      <div class="grp"><span class="lbl">SORT</span>
        <button class="btn active" data-doe-sort="value">VALUE DESC</button>
        <button class="btn" data-doe-sort="pos">POS_ID</button>
      </div>
    </div>

    <div class="grid g-12" style="margin-bottom:14px" id="doe-grid-heat-rank">
      <div class="panel col-7 r" id="doe-panel-heatmap">
        <div class="ph">
          <span class="pt">SPATIAL HEATMAP &middot; <span id="doe-heat-metric-lbl">PEAK G</span></span>
          <span class="pd" id="doe-heat-sub">grid &middot; cell color = selected metric</span>
        </div>
        <div class="doe-grid-wrap"><svg id="doe-heatmap-svg"></svg></div>
        <div class="pcap" id="doe-heat-cap">셀 클릭 시 우측 표에서 해당 위치 강조. 라벨 = 값 + 최악 영향 부품.</div>
      </div>

      <div class="panel col-5 r" id="doe-panel-ranking">
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

    <div class="grid g-12" style="margin-bottom:14px" id="doe-grid-pp">
      <div class="panel col-12 r" id="doe-panel-pp-matrix">
        <div class="ph">
          <span class="pt">PART &times; POSITION HEATMAP</span>
          <span class="pd">rows = top 15 parts by max peak_g &middot; cols = positions by DOE index &middot; color = peak_g</span>
        </div>
        <div class="doe-pp-matrix-wrap"><svg id="doe-pp-svg"></svg></div>
        <div class="pcap">부품별로 어느 위치에서 가속도가 가장 큰지 한눈에 확인. 색상 = peak_g (위치별 정규화 아님).</div>
      </div>
    </div>

    <div class="grid g-12" style="margin-bottom:14px" id="doe-grid-traj-env">
      <div class="panel col-7 r" id="doe-panel-trajectory">
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

      <div class="panel col-5 r" id="doe-panel-envelope">
        <div class="ph">
          <span class="pt">CROSS-POSITION ENVELOPE &middot; PER PART</span>
          <span class="pd">P5—P50—P95 whisker (peak_g) &middot; right = P95/P5</span>
        </div>
        <div class="doe-env-wrap" id="doe-env-wrap"></div>
        <div class="pcap">whisker 길이 = 위치별 부품 응답 분산. 비율 ↑ 위치 의존성 ↑.</div>
      </div>
    </div>

<div class="panel" id="doe-panel-failure-risk">
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

<div class="panel col-12 r" id="doe-panel-toa">
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
<div class="grid g-12" style="margin-bottom:14px" id="doe-grid-idw">
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
    <div id="idw-pred-loo" style="margin-bottom:8px;font-size:12px;color:var(--fg2);padding:6px 10px;background:rgba(255,255,255,0.03);border-radius:4px;display:none"></div>
    <div class="doe-grid-wrap"><div id="idw-pred-stack" style="position:relative;width:100%;"><canvas id="idw-pred-canvas" width="620" height="900" style="display:block;width:100%;cursor:grab;background:#0e1320;border-radius:4px;"></canvas><svg id="idw-pred-svg" style="position:absolute;left:0;top:0;width:100%;height:100%;pointer-events:none;"></svg></div></div>
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

<div class="grid g-12" style="margin-bottom:14px" id="doe-grid-energy">
  <div class="panel col-12 r" id="doe-panel-energy">
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

_PAGE6 = """
<section id="s6">
  <div class="page-head">
    <span class="num">06</span>
    <span class="t">DEEP ANALYTICS</span>
    <span class="sub">충격 응답의 깊은 분석 · 주파수 도메인 · 모달 분해 · 드릴다운</span>
    <span class="sub">DEEP-DIVE: FFT / SRS / SAFE ZONE / PCA / ANOMALY / PER-PART</span>
  </div>

  <div class="panel" style="background:transparent;border:none;padding:0;">
    <div id="deep-fft-panel" class="panel">
  <div class="panel-header">
    <h3>주파수 도메인 — FFT 스펙트럼</h3>
    <div class="deep-fft-meta"></div>
  </div>
  <div class="panel-body">
    <div class="deep-fft-body"></div>
  </div>
</div>

<section class="panel deep-srs-panel" id="deep-srs-panel">
  <h3>충격 응답 스펙트럼 — SRS</h3>
  <div id="deep-srs-body" class="srs-body"></div>
</section>
<div class="panel" id="deep-safe-drop-zone-panel">
  <div class="panel-header">
    <h3>안전 낙하 구역 지도</h3>
    <div class="panel-sub">충격 위치별 안전/위험 분류 — 볼록껍질로 회피 구역 시각화</div>
  </div>
  <div class="panel-body" id="deep-safe-drop-zone-body"></div>
</div>

<section class="panel deep-panel" id="deep-pca-modal-panel">
  <header class="panel-head">
    <h3>PCA 모달 분해</h3>
    <p class="panel-sub">25 위치 × 25 부품 peak_g 행렬의 상위 3개 주성분 — 부품 loadings + 위치 score 맵.</p>
  </header>
  <div class="panel-body" id="deep-pca-modal-body"></div>
</section>

<section class="panel" id="deep-anomaly-panel">
  <h3>이상치 위치 자동 검출</h3>
  <div id="deep-anomaly-detection" class="deep-anomaly-detection"></div>
</section>
<div class="panel" id="ppd-host">
  <h3 style="margin:0 0 6px 0;">부품별 통합 상세 보기 — Drill-Down</h3>
  <div class="ppd-caption">한 부품에 대한 모든 위치 응답을 한 화면으로. 좌측에서 부품 선택.</div>
  <div class="ppd-layout">
    <div class="ppd-left">
      <div class="ppd-left-head">부품 (Peak G 기준 내림차순)</div>
      <div id="ppd-part-list" class="ppd-list"></div>
    </div>
    <div class="ppd-right">
      <div id="ppd-detail-title" class="ppd-detail-title">활성 부품 로딩 중…</div>
      <div id="ppd-kpi-strip" class="ppd-kpi-strip"></div>
      <div class="ppd-grid2">
        <div class="ppd-tile">
          <div class="ppd-tile-head">위치별 Peak G 히트맵 (★ = 최대)</div>
          <svg id="ppd-heatmap-svg" class="ppd-svg-square"></svg>
        </div>
        <div class="ppd-tile">
          <div class="ppd-tile-head">Peak G 분포 (10-bin 히스토그램)</div>
          <svg id="ppd-hist-svg" class="ppd-svg-wide"></svg>
        </div>
      </div>
      <div class="ppd-tile" style="margin-top:8px;">
        <div class="ppd-tile-head">항복/재료 카드</div>
        <svg id="ppd-yield-svg" class="ppd-svg-wide"></svg>
      </div>
    </div>
  </div>
</div>

<!-- DEEP_PANELS_INSERT_HERE -->
    <!-- Workflow-added panel templates are inserted ABOVE this marker. -->
  </div>
</section>
"""

_PAGE7 = """
<section id="s7">
  <div class="page-head">
    <span class="num">07</span>
    <span class="t">INSIGHTS & RECOMMENDATIONS</span>
    <span class="sub">설계 검증 · 손상 정량 · 충격 후 거동 · 자동 권고</span>
    <span class="sub">SYMMETRY / DAMAGE / REBOUND / 3D TRAJ / RECOMMEND / PULSE</span>
  </div>

  <div class="panel" style="background:transparent;border:none;padding:0;">
<section class="insight-panel" id="insight-panel-symmetry" data-key="Symmetry">
  <h3 class="insight-title">대칭성 &amp; 경계 효과 분석</h3>
  <div class="insight-body" id="insight-symmetry"></div>
</section>
    <div id="insight-DamageIndex" class="insight-panel">
  <div class="insight-title">부품별 누적 손상 지표 (DI)</div>
  <div class="insight-body"></div>
</div>
<section id="insight-rebound-field" class="insight-panel rf-panel">
  <header class="insight-head">
    <h3>충격 후 반발 벡터장</h3>
    <p class="insight-sub">5×5 격자에서 impactor 반발 속도의 xy 성분을 화살표로, vz 부호를 색으로 표시</p>
  </header>
  <div class="rf-kpis"></div>
  <div class="rf-svg-wrap"></div>
  <p class="rf-caption">화살표 = 반발 방향 (xy). 파랑 = bounce (vz↑), 빨강 = embed/penetrate (vz↓), 회색 = flat. 화살표 길이 ∝ |v_xy| / max(|v_xy|).</p>
</section>
<div id="insight-panel-auto-recommend" class="insight-panel">
  <div class="insight-header">
    <h3>엔지니어링 자동 권고</h3>
    <div class="insight-subtitle">데이터 기반 규칙으로 생성된 보강/검토 권고 — 심각도 순 정렬</div>
  </div>
  <div class="insight-body"></div>
</div>

<div class="insight-panel" id="insight-panel-ContactPulse">
  <div class="insight-header">
    <h3>충격 펄스 통계 (Contact Pulse Statistics)</h3>
    <div class="insight-sub">위치별 contact 지속시간 · 밀도 · 펄스→피크 시간</div>
  </div>
  <div id="insight-ContactPulse" class="insight-body"></div>
</div>
<section id="insight-panel-trajectory3d" class="insight-panel">
  <header class="insight-head">
    <h3>3D 트래젝터리 번들</h3>
    <p class="insight-sub">25개 위치 impactor 경로를 등각투영으로 동시 표시 (각 경로 최대 30포인트)</p>
  </header>
  <div id="trajectory3d-svg" class="t3d-svg-wrap"></div>
  <p class="t3d-caption">25 위치 충돌체 경로 동시 표시. 색 = behavior.</p>
</section>
<!-- INSIGHT_PANELS_INSERT_HERE -->
    <!-- Workflow-added panel templates are inserted ABOVE this marker. -->
  </div>
</section>
"""

_PAGE8 = """
<section id="s8">
  <div class="page-head">
    <span class="num">08</span>
    <span class="t">PHYSICS INSIGHTS</span>
    <span class="sub">충격파 속도 · 반발 계수 · 댐핑 · 최악 조합</span>
    <span class="sub">WAVE / RESTITUTION / DAMPING / WORST COMBOS</span>
  </div>

  <div class="panel" style="background:transparent;border:none;padding:0;">
    <div class="panel" id="physics-stress-wave-velocity">
  <div class="panel-header">
    <h3>충격파 전파 속도</h3>
    <span class="panel-sub">part별 평균 v_app = r / Δt &nbsp;·&nbsp; 이론값과 비교</span>
  </div>
  <div class="panel-body"></div>
</div>
<div class="panel" id="phys-restitution-map" data-panel-key="RestitutionMap">
  <div class="panel-header">
    <h3>위치별 반발 계수 (Coefficient of Restitution)</h3>
    <div class="panel-sub" data-role="status">반발 계수 e 데이터를 로딩 중입니다...</div>
  </div>
  <div class="rmap-kpi-row">
    <div class="rmap-kpi"><div class="rmap-kpi-label">평균 e</div><div class="rmap-kpi-value" data-role="kpi-mean">—</div></div>
    <div class="rmap-kpi"><div class="rmap-kpi-label">최대 (탄성)</div><div class="rmap-kpi-value" data-role="kpi-max">—</div></div>
    <div class="rmap-kpi"><div class="rmap-kpi-label">최소 (비탄성)</div><div class="rmap-kpi-value" data-role="kpi-min">—</div></div>
    <div class="rmap-kpi rmap-kpi-wide"><div class="rmap-kpi-label">분포</div><div class="rmap-kpi-value" data-role="kpi-buckets">—</div></div>
  </div>
  <div class="rmap-grid">
    <div class="rmap-heat">
      <div class="rmap-section-title">5×5 공간 히트맵 (빨강=비탄성, 초록=탄성)</div>
      <div data-role="heatmap" class="rmap-heat-host"></div>
    </div>
    <div class="rmap-hist">
      <div class="rmap-section-title">e 분포 (10 bins)</div>
      <div data-role="histogram" class="rmap-hist-host"></div>
    </div>
  </div>
  <div class="rmap-caption">
    e = √(KE_after / KE_before). 0 = 완전비탄성 (충돌체 정지), 1 = 완전탄성. 1 초과 시 mass scaling 효과.
  </div>
</div>
<div class="panel" id="phys-recovery-damping-panel">
  <div class="panel-header">
    <h3>부품별 댐핑 / 회복 시간</h3>
    <div class="panel-sub">최악 위치 기준 · 5% 감쇠 시간 · log-decrement ζ 추정</div>
  </div>
  <div class="panel-body" id="phys-recovery-damping-body"></div>
</div>
<section id="phys-worst-combinations" class="panel" data-panel-key="worst_combinations">
  <header class="panel-header">
    <h3 class="panel-title">최악 25 조합 (위치 × 부품)</h3>
    <div class="panel-subtitle">composite risk score 기반 Top-K — peak_g · peak_stress · peak_disp 가중 결합</div>
  </header>
  <div class="panel-body"></div>
</section>

<!-- PHYSICS_PANELS_INSERT_HERE -->
    <!-- Workflow-added panel templates are inserted ABOVE this marker. -->
  </div>
</section>
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
  // 매우 작은 값 (예: ton-mm-s 의 density 7.85e-9) 은 fixed-point 로 표현 못함 → exponential
  if (a > 0 && a < 1e-3) return n.toExponential(d == null ? 2 : Math.max(2, d));
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
// density 단위 (mass/length³) — unit_labels 에는 별도 키가 없으니 mass + disp 로 조합.
// ton-mm-s → 'tonne/mm³'  /  SI → 'kg/m³'.
function _uDensity() {
  const m = (UNIT_LABELS.mass || '').trim();
  const l = (UNIT_LABELS.disp || '').trim();
  return (m && l) ? m + '/' + l + '³' : '';
}
function _uDensitySuffix() { const v = _uDensity(); return v ? ' (' + v + ')' : ''; }

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
  // Acceleration→g divisor: matches the solver unit declared by the loader.
  // mm/s² → /9810, m/s² → /9.81 (= mm/ms²).
  const _gDiv = (DATA.part_motion && (DATA.part_motion.g_divisor || DATA.part_motion.g_mm_s2)) || 9810.0;
  const _worstG_in_G = (k.worst_g || 0) / _gDiv;
  document.getElementById('kPositions').innerHTML = k.n_positions + '<span class="u">pos</span>';
  document.getElementById('kFaces').textContent = k.n_faces;
  document.getElementById('kParts').textContent = k.n_parts;
  document.getElementById('kWorstG').innerHTML = fmt(_worstG_in_G, 0) + '<span class="u">G</span>';
  document.getElementById('kWorstS').innerHTML = fmt(k.worst_s, 1) + '<span class="u">' + _u('stress') + '</span>';
  document.getElementById('kCritPairs').textContent = k.n_critical;
  document.getElementById('kSafePos').textContent = k.n_safe;
  // diss_pct=null → energy_flow 진짜 데이터 없음 (Mock 출고 차단 후). '—' 표시.
  document.getElementById('kDiss').innerHTML = (k.diss_pct != null)
    ? (k.diss_pct.toFixed(1) + '<span class="u">%</span>')
    : '<span style="opacity:0.5">—</span><span class="u" style="opacity:0.5" title="energy_flow 데이터 없음">N/A</span>';
  document.getElementById('kHeroFaces').textContent = k.n_faces;
  document.getElementById('kHeroPos').textContent = k.n_positions;
  document.getElementById('kHeroParts').textContent = k.n_parts;
  document.getElementById('kHeroPairs').textContent = k.n_pairs;
  document.getElementById('heroWorstCoord').textContent = k.worst.face + ' · X ' + k.worst.x.toFixed(1) + ' / Y ' + k.worst.y.toFixed(1);
  // _gDiv 가 위에서 acc unit 기반으로 결정됨 (mm/s²→9810, m/s²→9.81)
  document.getElementById('heroWorstPart').textContent = fmt((k.worst.g || 0) / _gDiv, 0) + ' G  ON  ' + k.worst.part_name;
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
    // Unknown / empty type: draw a neutral placeholder shape and still
    // populate the data table with whatever fields the loader filled in
    // (density, E, ν, mass, v₀, KE). Many real-world decks don't expose
    // an impactor type — we don't want the panel to look broken.
    sub.textContent = imp.type ? imp.type : '(type unspecified)';
    svgRoot.appendChild(svg('rect', { x: 60, y: 25, width: 80, height: 60, rx: 6, fill: 'rgba(77,214,255,0.06)', stroke: '#4dd6ff', 'stroke-width': 1, 'stroke-dasharray': '3,3' }));
    const qm = svg('text', { x: 100, y: 62, 'text-anchor': 'middle', fill: '#4dd6ff', 'font-size': 22, 'font-family': 'JetBrains Mono', 'font-weight': '700' });
    qm.appendChild(document.createTextNode('?'));
    svgRoot.appendChild(qm);
    const tlab = svg('text', { x: 100, y: 100, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 9, 'font-family': 'JetBrains Mono' });
    tlab.appendChild(document.createTextNode('type unspecified'));
    svgRoot.appendChild(tlab);
    const rows = [
      ['TYPE',              imp.type || '(unspecified)'],
      ['ρ' + _uDensitySuffix(),   fmt(imp.density, 3)],
      ['E' + _uSuffix('stress'),  fmt(imp.youngs_modulus, 3)],
      ['ν',                 (imp.poisson_ratio != null ? imp.poisson_ratio.toFixed(3) : '?')],
      ['m' + _uSuffix('mass'),    fmt(imp.mass, 4)],
      ['v₀' + _uSuffix('vel'),    fmt(imp.velocity, 0)],
      ['KE' + _uSuffix('energy'), fmt(imp.kinetic_energy, 2)],
    ];
    for (const r of rows) {
      tbl.appendChild(el('tr', null, [el('td', { class: 'tl dim' }, r[0]), el('td', { class: 'num b' }, r[1])]));
    }
    cap.textContent = 'Geometry not declared — material + kinematics only.';
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
  const thSvg = document.getElementById('ii-th-svg');
  if (thSvg) {
    while (thSvg.firstChild) thSvg.removeChild(thSvg.firstChild);
    // Initial-state placeholder so the panel doesn't look broken before
    // the user hovers a position. Removed on first hover.
    const t = svg('text', { x: 100, y: 38, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 9, 'font-family': 'JetBrains Mono, monospace' });
    t.appendChild(document.createTextNode('hover impact → KE-time curve'));
    thSvg.appendChild(t);
  }
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
      (k.diss_pct != null
        ? { severity: 'INFO', title: 'Energy dissipation', detail: '초기 KE의 ' + k.diss_pct.toFixed(1) + '%만 소산', recommendation: '소산 효율이 낮은 페이스에 완충 패드 추가' }
        : { severity: 'INFO', title: 'Energy dissipation', detail: '측정 불가 (energy_flow 데이터 없음)', recommendation: 'binout 의 glstat 파싱 모듈 추가 권장' })
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
    const dpr = window.devicePixelRatio || 1;
    // Convert screen-space mouse to the world coords used by renderEG (the
    // pre-transform CSS-pixel coord space). Mirrors the (tx/dpr, scale) applied
    // in renderEG so hover hit-tests track the visible nodes after zoom/pan.
    const sx = (ev.clientX - rect.left) * (EG.canvas.width / rect.width) / dpr;
    const sy = (ev.clientY - rect.top) * (EG.canvas.height / rect.height) / dpr;
    const tr = EG.transform || { tx: 0, ty: 0, scale: 1 };
    const mx = (sx - tr.tx / dpr) / tr.scale;
    const my = (sy - tr.ty / dpr) / tr.scale;
    const W = EG.canvas.width / dpr;
    const H = EG.canvas.height / dpr;
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
  // Attach zoom/pan. The controller exposes the live transform via getState();
  // renderEG reads EG.transform on every frame so the animation loop and scrub
  // input stay in sync with user-driven zoom/pan.
  EG.transform = { tx: 0, ty: 0, scale: 1 };
  EG.zp = canvasZoomPan(EG.canvas, { draw: (ctx, t) => { EG.transform = t; renderEG(); } });
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
  const dpr = window.devicePixelRatio || 1;
  const W = EG.canvas.width / dpr;
  const H = EG.canvas.height / dpr;
  // Background stays in screen space (no transform) so panning doesn't tile it.
  ctx.fillStyle = '#1a1e2e';
  ctx.fillRect(0, 0, W, H);
  // Apply user zoom/pan to the graph contents. canvasZoomPan operates on canvas
  // pixel coords; renderEG draws in CSS-pixel space (dpr already baked into the
  // base transform), so divide tx/ty by dpr to keep the math consistent.
  const tr = EG.transform || { tx: 0, ty: 0, scale: 1 };
  ctx.save();
  ctx.translate(tr.tx / dpr, tr.ty / dpr);
  ctx.scale(tr.scale, tr.scale);
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
  ctx.restore();
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
    const sections = ['s1', 's2', 's3', 's4', 's5', 's6', 's7', 's8'];
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

function svgZoomPan(svgEl, opts) {
  // Make an existing SVG element zoom/pan/drag with wheel + mouse.
  // Adds a <g> wrapper around current children if not already present.
  // Double-click resets. ESC key resets.
  if (!svgEl || svgEl.dataset.zpInit === '1') return;
  svgEl.dataset.zpInit = '1';
  // Move all existing children into a <g class="zp-content">.
  const ns = 'http://www.w3.org/2000/svg';
  const g = document.createElementNS(ns, 'g');
  g.setAttribute('class', 'zp-content');
  // Snapshot children list (live NodeList changes during move).
  const kids = Array.from(svgEl.childNodes);
  kids.forEach(k => g.appendChild(k));
  svgEl.appendChild(g);
  const state = { tx: 0, ty: 0, scale: 1, dragging: false, lastX: 0, lastY: 0 };
  const apply = () => {
    g.setAttribute('transform', 'translate(' + state.tx + ',' + state.ty + ') scale(' + state.scale + ')');
  };
  const reset = () => { state.tx = 0; state.ty = 0; state.scale = 1; apply(); };
  svgEl.addEventListener('wheel', (ev) => {
    ev.preventDefault();
    const rect = svgEl.getBoundingClientRect();
    const mouseX = ev.clientX - rect.left;
    const mouseY = ev.clientY - rect.top;
    // Convert mouse to SVG coordinates via current viewBox.
    const vb = (svgEl.getAttribute('viewBox') || '0 0 100 100').split(/\s+/).map(Number);
    const svgX = vb[0] + (mouseX / rect.width) * vb[2];
    const svgY = vb[1] + (mouseY / rect.height) * vb[3];
    const localX = (svgX - state.tx) / state.scale;
    const localY = (svgY - state.ty) / state.scale;
    const direction = ev.deltaY < 0 ? 1 : -1;
    const factor = direction > 0 ? 1.2 : 1 / 1.2;
    state.scale = Math.max(0.25, Math.min(10, state.scale * factor));
    state.tx = svgX - localX * state.scale;
    state.ty = svgY - localY * state.scale;
    apply();
  }, { passive: false });
  svgEl.addEventListener('mousedown', (ev) => {
    state.dragging = true;
    state.lastX = ev.clientX;
    state.lastY = ev.clientY;
    svgEl.style.cursor = 'grabbing';
    ev.preventDefault();
  });
  window.addEventListener('mousemove', (ev) => {
    if (!state.dragging) return;
    const dx = ev.clientX - state.lastX;
    const dy = ev.clientY - state.lastY;
    state.lastX = ev.clientX;
    state.lastY = ev.clientY;
    const rect = svgEl.getBoundingClientRect();
    const vb = (svgEl.getAttribute('viewBox') || '0 0 100 100').split(/\s+/).map(Number);
    state.tx += dx * (vb[2] / rect.width);
    state.ty += dy * (vb[3] / rect.height);
    apply();
  });
  window.addEventListener('mouseup', () => {
    state.dragging = false;
    svgEl.style.cursor = 'grab';
  });
  svgEl.addEventListener('dblclick', reset);
  window.addEventListener('keydown', (ev) => { if (ev.key === 'Escape') reset(); });
  svgEl.style.cursor = 'grab';
  // Visual hint: a tiny help text in a corner.
  const hint = document.createElementNS(ns, 'text');
  hint.setAttribute('x', 4);
  hint.setAttribute('y', 12);
  hint.setAttribute('font-size', 8);
  hint.setAttribute('fill', '#5c6383');
  hint.textContent = 'wheel: zoom · drag: pan · dbl-click: reset';
  svgEl.appendChild(hint);
}

function canvasZoomPan(canvasEl, opts) {
  // Make a canvas zoomable/pannable. The canvas must accept a redraw callback.
  // opts.draw(ctx, transform) is invoked whenever the view changes.
  //   transform = { tx, ty, scale }
  if (!canvasEl || canvasEl.dataset.czpInit === '1') return;
  canvasEl.dataset.czpInit = '1';
  const state = { tx: 0, ty: 0, scale: 1, dragging: false, lastX: 0, lastY: 0 };
  const redraw = () => {
    if (opts && typeof opts.draw === 'function') opts.draw(canvasEl.getContext('2d'), state);
  };
  const reset = () => { state.tx = 0; state.ty = 0; state.scale = 1; redraw(); };
  canvasEl.addEventListener('wheel', (ev) => {
    ev.preventDefault();
    const rect = canvasEl.getBoundingClientRect();
    const mouseX = ev.clientX - rect.left;
    const mouseY = ev.clientY - rect.top;
    // Convert to canvas coords (account for DPR & resolution).
    const cx = mouseX * (canvasEl.width / rect.width);
    const cy = mouseY * (canvasEl.height / rect.height);
    const localX = (cx - state.tx) / state.scale;
    const localY = (cy - state.ty) / state.scale;
    const factor = ev.deltaY < 0 ? 1.2 : 1 / 1.2;
    state.scale = Math.max(0.25, Math.min(10, state.scale * factor));
    state.tx = cx - localX * state.scale;
    state.ty = cy - localY * state.scale;
    redraw();
  }, { passive: false });
  canvasEl.addEventListener('mousedown', (ev) => {
    state.dragging = true;
    state.lastX = ev.clientX;
    state.lastY = ev.clientY;
    canvasEl.style.cursor = 'grabbing';
    ev.preventDefault();
  });
  window.addEventListener('mousemove', (ev) => {
    if (!state.dragging) return;
    const rect = canvasEl.getBoundingClientRect();
    const dx = (ev.clientX - state.lastX) * (canvasEl.width / rect.width);
    const dy = (ev.clientY - state.lastY) * (canvasEl.height / rect.height);
    state.lastX = ev.clientX;
    state.lastY = ev.clientY;
    state.tx += dx;
    state.ty += dy;
    redraw();
  });
  window.addEventListener('mouseup', () => {
    state.dragging = false;
    canvasEl.style.cursor = 'grab';
  });
  canvasEl.addEventListener('dblclick', reset);
  window.addEventListener('keydown', (ev) => { if (ev.key === 'Escape') reset(); });
  canvasEl.style.cursor = 'grab';
  redraw();  // Initial frame.
  return { reset, getState: () => ({...state}) };
}

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
    } else {
      // Empty archetype — explicit "no members" placeholder so the cell isn't blank.
      s.appendChild(svg('rect', { x: 0, y: 0, width: 200, height: 40, fill: 'rgba(255,255,255,0.02)' }));
      const t = svg('text', { x: 100, y: 24, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 10, 'font-family': 'JetBrains Mono, monospace' });
      t.appendChild(document.createTextNode('no positions in this archetype'));
      s.appendChild(t);
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
  const _dgFR = (typeof DATA !== 'undefined' && DATA.device_geometry) || {aspect: 1};
  const _arFR = (_dgFR.aspect && isFinite(_dgFR.aspect) && _dgFR.aspect > 0) ? _dgFR.aspect : 1;
  const gridBox = el('div', {class:'doe-failrisk-grid', style:`grid-template-columns:repeat(${nx},1fr);grid-template-rows:repeat(${ny},1fr);aspect-ratio:${_arFR} / 1;`});
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
  const canvasEl = document.getElementById('idw-pred-canvas');
  const btnHost = document.getElementById('idw-pred-buttons');
  const info = document.getElementById('idw-pred-info');
  if (!svgEl || !canvasEl || !btnHost || !info) return;

  if (!adv || !adv.grid_fine || !adv.measured_points || adv.measured_points.length < 2) {
    while (svgEl.firstChild) svgEl.removeChild(svgEl.firstChild);
    svgEl.appendChild(svg('text', { x: 200, y: 200, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 11 }, [document.createTextNode('IDW 데이터 없음 (측정점 부족)')]));
    const _ctx0 = canvasEl.getContext('2d');
    _ctx0.fillStyle = '#0e1320';
    _ctx0.fillRect(0, 0, canvasEl.width, canvasEl.height);
    btnHost.innerHTML = '';
    info.innerHTML = '';
    const _looBar0 = document.getElementById('idw-pred-loo');
    if (_looBar0) { _looBar0.style.display = 'none'; _looBar0.innerHTML = ''; }
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
  const _dgI = DATA.device_geometry || {aspect: 1};
  const _arI = (_dgI.aspect && isFinite(_dgI.aspect) && _dgI.aspect > 0) ? _dgI.aspect : 1;
  const vbW = 540, vbH = Math.max(120, Math.round(vbW / _arI));
  svgEl.setAttribute('viewBox', '0 0 ' + vbW + ' ' + vbH);
  svgEl.setAttribute('preserveAspectRatio', 'xMidYMid meet');

  // Resize canvas to match SVG viewBox aspect (HiDPI handled by CSS width:100%)
  canvasEl.width = vbW;
  canvasEl.height = vbH;

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

  // Canvas-based heatmap renderer (called by canvasZoomPan on every transform).
  function drawIdwHeatmap(ctx, transform) {
    ctx.fillStyle = '#0e1320';
    ctx.fillRect(0, 0, vbW, vbH);
    ctx.save();
    const tr = transform || { tx: 0, ty: 0, scale: 1 };
    ctx.translate(tr.tx, tr.ty);
    ctx.scale(tr.scale, tr.scale);
    for (let j = 0; j < NY; j++) {
      for (let i = 0; i < NX; i++) {
        const v = arr[j * NX + i];
        const t = Math.max(0, Math.min(1, (v - vmin) / span));
        const px = padL + i * cellW;
        const py = padT + (NY - 1 - j) * cellH;
        ctx.fillStyle = gColor(t);
        ctx.fillRect(px, py, cellW + 0.6, cellH + 0.6);
      }
    }
    ctx.restore();
  }
  canvasZoomPan(canvasEl, { draw: (ctx, t) => drawIdwHeatmap(ctx, t) });
  // Always draw an initial frame (canvasZoomPan only attaches once; reuse on
  // re-render needs a manual redraw with current state).
  drawIdwHeatmap(canvasEl.getContext('2d'), { tx: 0, ty: 0, scale: 1 });

  // Axis box (SVG overlay)
  svgEl.appendChild(svg('rect', {
    x: padL, y: padT, width: plotW, height: plotH,
    fill: 'none', stroke: 'rgba(255,255,255,0.18)', 'stroke-width': 0.6
  }));

  // LOO validation info bar + per-point error lookup
  const looBar = document.getElementById('idw-pred-loo');
  const loo = adv.loo_validation || null;
  const looErrByPos = {};
  if (loo && Array.isArray(loo.per_point)) {
    loo.per_point.forEach(p => { looErrByPos[p.pos_id] = p; });
  }
  if (looBar) {
    if (loo && IDW_STATE.metric === 'peak_g') {
      looBar.style.display = '';
      looBar.innerHTML =
        '<b>보간 신뢰도 (LOO)</b>: RMSE = <b>' + fmt(loo.rmse_peak_g, 2) + '</b> ' + _u('acc') +
        ' &middot; 중간 오차 = <b>' + (Number(loo.median_err_pct)).toFixed(1) + '%</b>' +
        ' &middot; 최대 오차 위치 = <b>' + (loo.max_error_pos_id == null ? '-' : loo.max_error_pos_id) + '</b>';
    } else {
      looBar.style.display = 'none';
      looBar.innerHTML = '';
    }
  }

  // Overlay measured points (color by LOO error % when peak_g + LOO available)
  const medianErrPct = (loo && isFinite(loo.median_err_pct)) ? Number(loo.median_err_pct) : null;
  (adv.measured_points || []).forEach(m => {
    const cx = xToPx(m.x);
    const cy = yToPx(m.y);
    const g = svg('g', null);
    let dotFill = '#0a0c14';
    const ep = looErrByPos[m.pos_id];
    if (IDW_STATE.metric === 'peak_g' && ep && medianErrPct !== null && medianErrPct > 0) {
      const pct = Number(ep.error_pct);
      if (pct < medianErrPct) dotFill = '#2ecc71';            // green
      else if (pct < 2 * medianErrPct) dotFill = '#f39c12';   // orange
      else dotFill = '#e74c3c';                               // red
    }
    g.appendChild(svg('circle', { cx: cx, cy: cy, r: 4.2, fill: dotFill, stroke: '#ffffff', 'stroke-width': 1.2 }));
    const v = (IDW_STATE.metric === 'peak_stress') ? m.peak_stress : m.peak_g;
    const u = _idwMetricUnit(IDW_STATE.metric);
    let tipExtra = '';
    if (IDW_STATE.metric === 'peak_g' && ep) {
      tipExtra = '\nLOO 예측 = ' + fmt(ep.predicted, 1) +
        '\nLOO 오차 = ' + fmt(ep.error_abs, 2) + ' (' + Number(ep.error_pct).toFixed(1) + '%)';
    }
    g.appendChild(svg('title', null, [document.createTextNode(
      m.pos_id + '\nx=' + m.x.toFixed(2) + ' y=' + m.y.toFixed(2) +
      '\n측정 ' + _idwMetricLabel(IDW_STATE.metric) + ' = ' + fmt(v, 1) + (u ? ' ' + u : '') +
      tipExtra
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

  const unitAcc = (data.unit_acc) || (typeof _u === 'function' ? _u('acc') : '');

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

function _deepRenderFFT(data){
  const root = document.getElementById('deep-fft-panel');
  if (!root) return;
  const body = root.querySelector('.deep-fft-body');
  const meta = root.querySelector('.deep-fft-meta');
  if (!body) return;
  body.innerHTML = '';
  if (meta) meta.innerHTML = '';

  const payload = (data && data.fft) || {};
  const perPart = payload.per_part_dominant_freq || {};
  const summary = payload.summary || {};
  const entries = Object.entries(perPart);

  if (!entries.length){
    body.appendChild(el('div', {class:'deep-empty'}, ['데이터 없음 — 분석 가능한 가속도 신호가 없습니다.']));
    return;
  }

  // header meta
  if (meta){
    const band = summary.freq_band_Hz || [0,0];
    meta.appendChild(el('span', {class:'deep-fft-pill'},
      [`fs ≈ ${fmt(summary.fs_Hz||0,1)} Hz`]));
    meta.appendChild(el('span', {class:'deep-fft-pill'},
      [`대역: ${fmt(band[0]||0,1)} – ${fmt(band[1]||0,1)} Hz`]));
    meta.appendChild(el('span', {class:'deep-fft-pill'},
      [`파트 ${summary.n_parts_with_data||0}개 / 위치샘플 ${summary.n_positions_used||0}개`]));
  }

  // Top-12 by mean_f_dom_Hz (descending)
  entries.sort((a,b)=> (b[1].mean_f_dom_Hz||0) - (a[1].mean_f_dom_Hz||0));
  const top = entries.slice(0, 12);

  const W = 192, H = 40, PAD_L = 2, PAD_R = 2, PAD_T = 2, PAD_B = 2;

  top.forEach(([pid, info]) => {
    const spec = info.spectrum || {f:[], amp_normalized:[]};
    const fs = spec.f || [];
    const as = spec.amp_normalized || [];

    const card = el('div', {class:'deep-fft-card'});

    // header line
    const head = el('div', {class:'deep-fft-card-head'}, [
      el('span', {class:'deep-fft-name', title:info.name||('Part '+pid)},
         [info.name || ('Part '+pid)]),
      el('span', {class:'deep-fft-pid'}, ['#'+pid])
    ]);
    card.appendChild(head);

    // svg spectrum
    const s = svg('svg', {width:W, height:H, viewBox:`0 0 ${W} ${H}`, class:'deep-fft-svg'});
    // background
    s.appendChild(svg('rect', {x:0,y:0,width:W,height:H,fill:'#0f1115',stroke:'#23262d'}));

    if (fs.length >= 2 && as.length >= 2){
      const fmin = fs[0], fmax = fs[fs.length-1];
      const span = (fmax - fmin) || 1;
      const innerW = W - PAD_L - PAD_R;
      const innerH = H - PAD_T - PAD_B;
      let d = '';
      for (let i=0; i<fs.length; i++){
        const x = PAD_L + ( (fs[i]-fmin) / span ) * innerW;
        const a = Math.max(0, Math.min(1, as[i]||0));
        const y = PAD_T + (1 - a) * innerH;
        d += (i===0 ? 'M' : 'L') + x.toFixed(1) + ',' + y.toFixed(1) + ' ';
      }
      s.appendChild(svg('path', {d:d, fill:'none', stroke:'#7ad7ff', 'stroke-width':1.2}));

      // mark dominant frequency
      const fdom = info.top_freq_Hz;
      if (isFinite(fdom)){
        const xd = PAD_L + ( (fdom - fmin) / span ) * innerW;
        s.appendChild(svg('line', {x1:xd, y1:PAD_T, x2:xd, y2:H-PAD_B,
          stroke:'#ffb347', 'stroke-width':1, 'stroke-dasharray':'2,2'}));
      }
    } else {
      s.appendChild(svg('text', {x:W/2, y:H/2, fill:'#888', 'font-size':9,
        'text-anchor':'middle', 'dominant-baseline':'middle'}, ['스펙트럼 없음']));
    }
    card.appendChild(s);

    // text line
    const fdom = info.mean_f_dom_Hz, fstd = info.std_f_dom_Hz, n = info.n_samples_used;
    const txt = el('div', {class:'deep-fft-text'}, [
      el('span', {class:'deep-fft-fdom'},
         [`f_dom = ${fmt(fdom,1)} ± ${fmt(fstd,1)} Hz`]),
      el('span', {class:'deep-fft-n'}, [`n=${n}`])
    ]);
    card.appendChild(txt);

    body.appendChild(card);
  });
}

function _deepRenderSRS(data) {
  const host = document.getElementById('deep-srs-body');
  if (!host) return;
  host.innerHTML = '';

  const pay = (data && data.deep_analytics && data.deep_analytics.srs) || null;
  if (!pay || !pay.available || !pay.srs_curves || !pay.srs_curves.length) {
    host.appendChild(el('div', {class: 'empty-note'}, ['가속도 데이터 없음 — SRS 계산 불가']));
    return;
  }

  const curves = pay.srs_curves;
  const accUnit = (typeof _u === 'function') ? _u('acc') : '';

  // Layout
  const W = 720, H = 360;
  const ML = 64, MR = 160, MT = 16, MB = 44;
  const PW = W - ML - MR, PH = H - MT - MB;

  // Domain
  let fMin = Infinity, fMax = -Infinity, sMin = Infinity, sMax = -Infinity;
  curves.forEach(c => {
    c.f.forEach(v => { if (v > 0 && isFinite(v)) { if (v < fMin) fMin = v; if (v > fMax) fMax = v; } });
    c.srs.forEach(v => { if (v > 0 && isFinite(v)) { if (v < sMin) sMin = v; if (v > sMax) sMax = v; } });
  });
  if (!isFinite(fMin) || !isFinite(sMin) || sMax <= 0) {
    host.appendChild(el('div', {class: 'empty-note'}, ['SRS 값이 모두 0 — 표시할 데이터 없음']));
    return;
  }
  // pad
  const lfMin = Math.log10(fMin), lfMax = Math.log10(fMax);
  const lsMin = Math.log10(Math.max(sMin, sMax * 1e-4));
  const lsMax = Math.log10(sMax * 1.15);

  const xToPx = lf => ML + (lf - lfMin) / (lfMax - lfMin || 1) * PW;
  const yToPx = ls => MT + PH - (ls - lsMin) / (lsMax - lsMin || 1) * PH;

  const svgEl = svg('svg', {viewBox: `0 0 ${W} ${H}`, width: '100%', height: H, class: 'srs-chart'});

  // axes background
  svgEl.appendChild(svg('rect', {x: ML, y: MT, width: PW, height: PH, fill: '#0e131b', stroke: '#2a3340'}));

  // X gridlines (decades + 1/3 octave centers)
  const xTicks = [];
  for (let d = Math.floor(lfMin); d <= Math.ceil(lfMax); d++) {
    for (let m = 1; m < 10; m++) {
      const v = m * Math.pow(10, d);
      if (v < fMin * 0.99 || v > fMax * 1.01) continue;
      xTicks.push({v: v, major: (m === 1)});
    }
  }
  xTicks.forEach(t => {
    const x = xToPx(Math.log10(t.v));
    svgEl.appendChild(svg('line', {x1: x, y1: MT, x2: x, y2: MT + PH,
      stroke: t.major ? '#2f3a4a' : '#1d2530', 'stroke-width': t.major ? 1 : 0.5}));
    if (t.major) {
      svgEl.appendChild(svg('text', {x: x, y: MT + PH + 14, 'text-anchor': 'middle',
        fill: '#9aa7b8', 'font-size': 10}, [String(t.v) + ' Hz']));
    }
  });

  // Y gridlines (decades)
  const yTicks = [];
  for (let d = Math.floor(lsMin); d <= Math.ceil(lsMax); d++) {
    for (let m = 1; m < 10; m++) {
      const v = m * Math.pow(10, d);
      const lv = Math.log10(v);
      if (lv < lsMin - 1e-9 || lv > lsMax + 1e-9) continue;
      yTicks.push({v: v, lv: lv, major: (m === 1)});
    }
  }
  yTicks.forEach(t => {
    const y = yToPx(t.lv);
    svgEl.appendChild(svg('line', {x1: ML, y1: y, x2: ML + PW, y2: y,
      stroke: t.major ? '#2f3a4a' : '#1d2530', 'stroke-width': t.major ? 1 : 0.5}));
    if (t.major) {
      const lbl = (t.v >= 1000) ? (t.v / 1000).toFixed(0) + 'k' : t.v.toFixed(0);
      svgEl.appendChild(svg('text', {x: ML - 6, y: y + 3, 'text-anchor': 'end',
        fill: '#9aa7b8', 'font-size': 10}, [lbl]));
    }
  });

  // axis labels
  svgEl.appendChild(svg('text', {x: ML + PW / 2, y: H - 8, 'text-anchor': 'middle',
    fill: '#cfd6e0', 'font-size': 11}, ['주파수 (Hz)']));
  svgEl.appendChild(svg('text', {x: 14, y: MT + PH / 2,
    transform: `rotate(-90 14 ${MT + PH / 2})`,
    'text-anchor': 'middle', fill: '#cfd6e0', 'font-size': 11}, [`최대 절대 가속도 응답 (${accUnit})`]));

  // colors for up to 3 curves
  const palette = ['#f0c419', '#5dade2', '#e74c3c'];

  curves.forEach((c, idx) => {
    const color = palette[idx % palette.length];
    let d = '';
    for (let i = 0; i < c.f.length; i++) {
      const fv = c.f[i], sv = c.srs[i];
      if (!(fv > 0) || !(sv > 0) || !isFinite(fv) || !isFinite(sv)) continue;
      const x = xToPx(Math.log10(fv));
      const y = yToPx(Math.log10(sv));
      d += (d ? ' L ' : 'M ') + x.toFixed(1) + ' ' + y.toFixed(1);
    }
    if (d) {
      svgEl.appendChild(svg('path', {d: d, fill: 'none', stroke: color, 'stroke-width': 2}));
    }
    // markers
    for (let i = 0; i < c.f.length; i++) {
      const fv = c.f[i], sv = c.srs[i];
      if (!(fv > 0) || !(sv > 0)) continue;
      svgEl.appendChild(svg('circle', {cx: xToPx(Math.log10(fv)), cy: yToPx(Math.log10(sv)),
        r: 2.2, fill: color, stroke: 'none'}));
    }
  });

  // Legend
  const lgX = ML + PW + 16;
  let lgY = MT + 6;
  svgEl.appendChild(svg('text', {x: lgX, y: lgY, fill: '#cfd6e0', 'font-size': 11,
    'font-weight': 'bold'}, [`pos #${pay.summary.pos_id} TOP-3`]));
  lgY += 16;
  curves.forEach((c, idx) => {
    const color = palette[idx % palette.length];
    svgEl.appendChild(svg('rect', {x: lgX, y: lgY - 8, width: 12, height: 3, fill: color}));
    const peak = Math.max.apply(null, c.srs.filter(v => isFinite(v) && v > 0));
    const lbl = `${c.part_name} (peak ${(typeof fmt === 'function') ? fmt(peak, 0) : peak.toFixed(0)} ${accUnit})`;
    svgEl.appendChild(svg('text', {x: lgX + 18, y: lgY - 3, fill: '#cfd6e0', 'font-size': 10}, [lbl]));
    lgY += 16;
  });

  // Summary line
  const sum = pay.summary || {};
  const meta = el('div', {class: 'srs-meta'}, [
    `ζ = ${(sum.damping_ratio != null ? (sum.damping_ratio * 100).toFixed(1) : '5.0')}% · ` +
    `${sum.n_frequencies || curves[0].f.length} 주파수 · ` +
    `샘플링 ≈ ${sum.fs_Hz ? sum.fs_Hz.toFixed(0) : '—'} Hz · ` +
    `대역 ${(sum.f_range_Hz && sum.f_range_Hz[0]) || 5}–${(sum.f_range_Hz && sum.f_range_Hz[1]) || 5000} Hz`
  ]);

  const cap = el('div', {class: 'srs-caption'},
    ['SDOF 응답 (ζ=5%). 가로 = 1/3 옥타브 주파수, 세로 = 최대 절대 가속도 응답.']);

  host.appendChild(svgEl);
  host.appendChild(meta);
  host.appendChild(cap);
}
function _deepRenderSafeDropZone(data) {
  const root = document.getElementById("deep-safe-drop-zone-body");
  if (!root) return;
  root.innerHTML = "";

  const dz = (data && data.deep_analytics && data.deep_analytics.safe_drop_zone) || null;
  if (!dz || dz.empty || !dz.positions || dz.positions.length === 0) {
    root.appendChild(el("div", { class: "muted", style: "padding:16px;" }, ["데이터 없음"]));
    return;
  }

  const positions = dz.positions;
  const polygon = dz.critical_polygon || [];
  const thr = dz.thresholds_used || {};
  const accU = (typeof _u === "function") ? _u("acc") : "";
  const stressU = (typeof _u === "function") ? _u("stress") : "";
  const dispU = (typeof _u === "function") ? _u("disp") : "m";

  // Compute coordinate extent
  let xmin = Infinity, xmax = -Infinity, ymin = Infinity, ymax = -Infinity;
  positions.forEach(p => {
    if (p.x < xmin) xmin = p.x;
    if (p.x > xmax) xmax = p.x;
    if (p.y < ymin) ymin = p.y;
    if (p.y > ymax) ymax = p.y;
  });
  if (!isFinite(xmin) || !isFinite(xmax) || xmin === xmax) { xmin -= 0.5; xmax += 0.5; }
  if (!isFinite(ymin) || !isFinite(ymax) || ymin === ymax) { ymin -= 0.5; ymax += 0.5; }

  // Layout: heatmap (left) + KPIs (right)
  const wrap = el("div", { style: "display:flex; gap:18px; padding:12px; flex-wrap:wrap;" });

  // ---- SVG heatmap ----
  const _dgZ = (typeof DATA !== 'undefined' && DATA.device_geometry) || {aspect: 1};
  const _arZ = (_dgZ.aspect && isFinite(_dgZ.aspect) && _dgZ.aspect > 0) ? _dgZ.aspect : 1;
  const W = 460, H = Math.max(160, Math.round(W / _arZ)), PAD = 36;
  const innerW = W - 2 * PAD, innerH = H - 2 * PAD;
  const xRange = xmax - xmin || 1;
  const yRange = ymax - ymin || 1;
  // Distinct x/y values for cell sizing
  const xs = Array.from(new Set(positions.map(p => p.x))).sort((a, b) => a - b);
  const ys = Array.from(new Set(positions.map(p => p.y))).sort((a, b) => a - b);
  let cellW = innerW / Math.max(1, xs.length);
  let cellH = innerH / Math.max(1, ys.length);

  const sx = x => PAD + ((x - xmin) / xRange) * innerW;
  const sy = y => PAD + innerH - ((y - ymin) / yRange) * innerH;

  const svgRoot = svg("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}`, style: "background:#0c1116; border-radius:8px;" });

  // Background grid
  svgRoot.appendChild(svg("rect", { x: PAD, y: PAD, width: innerW, height: innerH, fill: "#10161d", stroke: "#1f2933", "stroke-width": 1 }));

  // Cells
  const SAFE_COLOR = "#1f8a4c";
  const RISK_COLOR = "#c83232";
  positions.forEach(p => {
    const cx = sx(p.x), cy = sy(p.y);
    const rx = cx - cellW / 2, ry = cy - cellH / 2;
    const fill = p.safe ? SAFE_COLOR : RISK_COLOR;
    svgRoot.appendChild(svg("rect", {
      x: rx, y: ry, width: cellW - 2, height: cellH - 2,
      fill: fill, "fill-opacity": p.safe ? 0.55 : 0.7,
      stroke: "#0c1116", "stroke-width": 1, rx: 3
    }));
    // Worst-metric label
    let label = "OK";
    if (!p.safe) {
      if (p.worst_metric === "peak_g") label = "g";
      else if (p.worst_metric === "peak_stress") label = "σ";
      else if (p.worst_metric === "peak_disp") label = "d";
      else label = "!";
    }
    const txt = svg("text", {
      x: cx, y: cy + 4,
      "text-anchor": "middle",
      "font-size": 13, "font-weight": 700,
      fill: "#f4f6f8"
    });
    txt.textContent = label;
    svgRoot.appendChild(txt);

    // Tooltip
    const ttParts = [
      `pos_id=${p.pos_id}`,
      `face=${p.face}`,
      `safe=${p.safe ? "예" : "아니오"}`
    ];
    if (!p.safe) {
      let metricLabel = p.worst_metric || "";
      let unit = "";
      let val = p.worst_value;
      if (p.worst_metric === "peak_g") { unit = accU; }
      else if (p.worst_metric === "peak_stress") { unit = stressU; }
      else if (p.worst_metric === "peak_disp") { unit = dispU; }
      ttParts.push(`worst=${metricLabel} (${fmt(val, 3)} ${unit})`);
      if (p.worst_part_id !== null && p.worst_part_id !== undefined) {
        ttParts.push(`part_id=${p.worst_part_id}`);
      }
    }
    const titleEl = svg("title", {});
    titleEl.textContent = ttParts.join(" | ");
    txt.appendChild(titleEl);
  });

  // Critical polygon overlay
  if (polygon && polygon.length >= 3) {
    const ptsStr = polygon.map(([x, y]) => `${sx(x).toFixed(2)},${sy(y).toFixed(2)}`).join(" ");
    svgRoot.appendChild(svg("polygon", {
      points: ptsStr,
      fill: "#ff3030", "fill-opacity": 0.22,
      stroke: "#ff5050", "stroke-width": 2,
      "stroke-dasharray": "6,4"
    }));
    // Centroid for label
    let cxSum = 0, cySum = 0;
    polygon.forEach(([x, y]) => { cxSum += sx(x); cySum += sy(y); });
    const cxC = cxSum / polygon.length;
    const cyC = cySum / polygon.length;
    const lblBg = svg("rect", { x: cxC - 38, y: cyC - 12, width: 76, height: 22, rx: 4, fill: "#1a0a0a", "fill-opacity": 0.85, stroke: "#ff5050", "stroke-width": 1 });
    svgRoot.appendChild(lblBg);
    const lbl = svg("text", { x: cxC, y: cyC + 4, "text-anchor": "middle", "font-size": 12, "font-weight": 700, fill: "#ff8080" });
    lbl.textContent = "주의 구역";
    svgRoot.appendChild(lbl);
  }

  // Axis labels
  const xLbl = svg("text", { x: W / 2, y: H - 6, "text-anchor": "middle", "font-size": 11, fill: "#8a96a3" });
  xLbl.textContent = "X 위치";
  svgRoot.appendChild(xLbl);
  const yLbl = svg("text", { x: 12, y: H / 2, "text-anchor": "middle", "font-size": 11, fill: "#8a96a3", transform: `rotate(-90 12 ${H / 2})` });
  yLbl.textContent = "Y 위치";
  svgRoot.appendChild(yLbl);

  wrap.appendChild(svgRoot);

  // ---- KPI + thresholds + legend ----
  const side = el("div", { style: "flex:1; min-width:240px; display:flex; flex-direction:column; gap:12px;" });

  const total = (dz.safe_count || 0) + (dz.at_risk_count || 0);
  const safePct = total > 0 ? (100 * dz.safe_count / total) : 0;
  const riskPct = total > 0 ? (100 * dz.at_risk_count / total) : 0;

  const kpiSafe = el("div", { class: "kpi-box", style: "background:#0f2418; border-left:4px solid #1f8a4c; padding:12px 14px; border-radius:6px;" }, [
    el("div", { style: "font-size:11px; color:#8a96a3; letter-spacing:0.5px;" }, ["안전 위치"]),
    el("div", { style: "font-size:26px; font-weight:700; color:#5fd187; margin-top:4px;" }, [`${dz.safe_count} / ${total}`]),
    el("div", { style: "font-size:11px; color:#8a96a3; margin-top:2px;" }, [`${fmt(safePct, 1)}%`]),
  ]);
  const kpiRisk = el("div", { class: "kpi-box", style: "background:#241010; border-left:4px solid #c83232; padding:12px 14px; border-radius:6px;" }, [
    el("div", { style: "font-size:11px; color:#8a96a3; letter-spacing:0.5px;" }, ["위험 위치"]),
    el("div", { style: "font-size:26px; font-weight:700; color:#ff7878; margin-top:4px;" }, [`${dz.at_risk_count} / ${total}`]),
    el("div", { style: "font-size:11px; color:#8a96a3; margin-top:2px;" }, [`${fmt(riskPct, 1)}%`]),
  ]);
  side.appendChild(kpiSafe);
  side.appendChild(kpiRisk);

  // Thresholds box
  const thrBox = el("div", { style: "background:#10161d; padding:10px 12px; border-radius:6px; border:1px solid #1f2933;" }, [
    el("div", { style: "font-size:11px; color:#8a96a3; margin-bottom:6px; letter-spacing:0.5px;" }, ["임계값 (데이터 기반)"]),
    el("div", { style: "font-size:12px; color:#d0d6dd; line-height:1.7;" }, [
      el("div", {}, [`peak_g ≤ ${fmt(thr.peak_g_thresh || 0, 3)} ${accU} (평균)`]),
      el("div", {}, [`peak_stress ≤ ${fmt(thr.peak_stress_thresh || 0, 3)} ${stressU} (P75)`]),
      el("div", {}, [`peak_disp ≤ ${fmt(thr.peak_disp_thresh || 0, 4)} ${dispU} (P75)`]),
    ]),
  ]);
  side.appendChild(thrBox);

  // Legend
  const legend = el("div", { style: "background:#10161d; padding:10px 12px; border-radius:6px; border:1px solid #1f2933;" }, [
    el("div", { style: "font-size:11px; color:#8a96a3; margin-bottom:6px; letter-spacing:0.5px;" }, ["범례"]),
    el("div", { style: "display:flex; align-items:center; gap:8px; margin-bottom:4px; font-size:12px; color:#d0d6dd;" }, [
      el("span", { style: "display:inline-block; width:14px; height:14px; background:#1f8a4c; border-radius:3px;" }, []),
      el("span", {}, ["안전 (OK)"]),
    ]),
    el("div", { style: "display:flex; align-items:center; gap:8px; margin-bottom:4px; font-size:12px; color:#d0d6dd;" }, [
      el("span", { style: "display:inline-block; width:14px; height:14px; background:#c83232; border-radius:3px;" }, []),
      el("span", {}, ["위험 (g/σ/d = 위반 지표)"]),
    ]),
    el("div", { style: "display:flex; align-items:center; gap:8px; font-size:12px; color:#d0d6dd;" }, [
      el("span", { style: "display:inline-block; width:14px; height:10px; background:rgba(255,48,48,0.22); border:1.5px dashed #ff5050;" }, []),
      el("span", {}, ["주의 구역 (위험 볼록껍질)"]),
    ]),
  ]);
  side.appendChild(legend);

  wrap.appendChild(side);
  root.appendChild(wrap);

  // Caption
  const caption = el("div", { style: "padding:10px 14px 14px; font-size:12px; color:#8a96a3; line-height:1.6;" }, [
    "전 부품 안전 = peak_g/stress/disp 모두 기준 이하. 빨간 영역 = 권장 회피 구역."
  ]);
  root.appendChild(caption);
  svgZoomPan(svgRoot);
}

function _deepRenderPCAModal(data){
  const host = document.getElementById('deep-pca-modal-body');
  if (!host) return;
  host.innerHTML = '';
  const payload = (data && data.pca_modal) || {available:false};

  if (!payload.available){
    const reason = payload.reason ? ` (${payload.reason})` : '';
    host.appendChild(el('div', {class:'empty-note'},
      [`데이터 부족 — PCA 모달 분해를 계산할 수 없습니다${reason}.`]));
    return;
  }

  const modes = payload.modes || [];
  if (!modes.length){
    host.appendChild(el('div', {class:'empty-note'}, ['주성분이 없습니다.']));
    return;
  }

  // header summary
  const cumPct = (payload.cumulative_var_ratio * 100).toFixed(1);
  host.appendChild(el('div', {class:'pca-summary'}, [
    el('span', {}, [`행렬: ${payload.n_positions} 위치 × ${payload.n_parts} 부품`]),
    el('span', {class:'sep'}, [' · ']),
    el('span', {}, [`상위 ${modes.length}개 모드 누적 분산: ${cumPct}%`]),
  ]));

  // shared range for loadings (per mode-row we still use mode-local max for bar normalization)
  // shared range for spatial scores (across all modes) for consistent color scale
  let scoreAbsMax = 0;
  modes.forEach(m => (m.position_scores || []).forEach(p => {
    const a = Math.abs(p.score || 0); if (a > scoreAbsMax) scoreAbsMax = a;
  }));
  if (scoreAbsMax <= 0) scoreAbsMax = 1;

  modes.forEach(mode => {
    const row = el('div', {class:'pca-mode-row'});

    // ----- mode header
    const evPct = (mode.explained_var_ratio * 100).toFixed(2);
    const headerWrap = el('div', {class:'pca-mode-head'}, [
      el('div', {class:'pca-mode-title'}, [`모드 ${mode.mode_index}`]),
      el('div', {class:'pca-mode-evr'}, [`설명 분산 ${evPct}%`]),
      el('div', {class:'pca-mode-bar-track'}, [
        el('div', {class:'pca-mode-bar-fill',
                   style:`width:${Math.max(0, Math.min(100, mode.explained_var_ratio*100)).toFixed(2)}%;`})
      ]),
    ]);
    row.appendChild(headerWrap);

    const body = el('div', {class:'pca-mode-body'});

    // ----- LEFT: part loadings (horizontal bars, +/- colored)
    const left = el('div', {class:'pca-loadings'}, [
      el('div', {class:'pca-sub-title'}, ['상위 부품 loadings (top-10)'])
    ]);
    const loadings = mode.part_loadings || [];
    if (!loadings.length){
      left.appendChild(el('div', {class:'empty-note small'}, ['부품 loading 없음']));
    } else {
      let lmax = 0;
      loadings.forEach(L => { const a = Math.abs(L.loading||0); if (a>lmax) lmax = a; });
      if (lmax <= 0) lmax = 1;

      const list = el('div', {class:'pca-loading-list'});
      loadings.forEach(L => {
        const v = +L.loading || 0;
        const pct = Math.abs(v) / lmax * 50; // half-width bar
        const isPos = v >= 0;
        const colorCls = isPos ? 'pos' : 'neg';
        const item = el('div', {class:'pca-load-item'}, [
          el('div', {class:'pca-load-label', title: L.part_name},
             [`${L.part_id} · ${L.part_name}`]),
          el('div', {class:'pca-load-bar-wrap'}, [
            el('div', {class:'pca-load-axis'}),
            el('div', {class:`pca-load-bar ${colorCls}`,
              style: isPos
                ? `left:50%; width:${pct.toFixed(2)}%;`
                : `right:50%; width:${pct.toFixed(2)}%;`}),
          ]),
          el('div', {class:`pca-load-val ${colorCls}`}, [fmt(v, 3)]),
        ]);
        list.appendChild(item);
      });
      left.appendChild(list);
    }
    body.appendChild(left);

    // ----- RIGHT: 5x5 spatial score map
    const right = el('div', {class:'pca-spatial'}, [
      el('div', {class:'pca-sub-title'}, ['위치 score 맵 (5×5)'])
    ]);
    const pscores = mode.position_scores || [];
    if (!pscores.length){
      right.appendChild(el('div', {class:'empty-note small'}, ['위치 score 없음']));
    } else {
      // Build a 5x5 grid by sorting positions; use (x,y) if all available, else index reshape.
      const hasXY = pscores.every(p => (p.x != null && p.y != null && isFinite(p.x) && isFinite(p.y)));
      let cells = []; // {row,col,score,pos_id}
      const N = pscores.length;
      const dim = Math.max(2, Math.round(Math.sqrt(N)));

      if (hasXY){
        // bin by unique sorted x/y
        const xs = Array.from(new Set(pscores.map(p=>+p.x))).sort((a,b)=>a-b);
        const ys = Array.from(new Set(pscores.map(p=>+p.y))).sort((a,b)=>b-a); // top→bottom
        pscores.forEach(p => {
          const cx = xs.indexOf(+p.x);
          const cy = ys.indexOf(+p.y);
          cells.push({row:cy, col:cx, score:+p.score, pos_id:p.pos_id});
        });
      } else {
        // fall back: sort by pos_id and reshape
        const sorted = pscores.slice().sort((a,b)=> (a.pos_id||0) - (b.pos_id||0));
        sorted.forEach((p, idx) => {
          cells.push({row: Math.floor(idx/dim), col: idx % dim, score:+p.score, pos_id:p.pos_id});
        });
      }

      const nRows = (cells.reduce((mx,c)=>Math.max(mx,c.row),0) + 1) || dim;
      const nCols = (cells.reduce((mx,c)=>Math.max(mx,c.col),0) + 1) || dim;

      const _dgP = (typeof DATA !== 'undefined' && DATA.device_geometry) || {aspect: 1};
      const _arP = (_dgP.aspect && isFinite(_dgP.aspect) && _dgP.aspect > 0) ? _dgP.aspect : 1;
      const W = 220, H = Math.max(80, Math.round(W / _arP)), pad = 8;
      const cw = (W - pad*2) / nCols;
      const ch = (H - pad*2) / nRows;
      const svgEl = svg('svg', {class:'pca-grid', width:W, height:H,
                                viewBox:`0 0 ${W} ${H}`});

      cells.forEach(c => {
        const t = Math.max(-1, Math.min(1, c.score / scoreAbsMax));
        const fill = _pcaDivergingColor(t);
        const x = pad + c.col * cw;
        const y = pad + c.row * ch;
        svgEl.appendChild(svg('rect', {
          x: x.toFixed(2), y: y.toFixed(2),
          width: (cw-1).toFixed(2), height: (ch-1).toFixed(2),
          fill, stroke:'#1b2530', 'stroke-width':'0.5',
          'data-pos': c.pos_id,
        }, [svg('title', {}, [`pos ${c.pos_id} · score ${fmt(c.score,3)}`])]));
        // label score
        const lbl = Math.abs(c.score) >= 0.01 ? fmt(c.score,2) : '~0';
        svgEl.appendChild(svg('text', {
          x:(x + cw/2).toFixed(2), y:(y + ch/2 + 3).toFixed(2),
          'text-anchor':'middle',
          'font-size': Math.max(8, Math.min(11, cw*0.18)).toFixed(1),
          fill: Math.abs(t) > 0.55 ? '#fff' : '#0c0f14',
        }, [lbl]));
      });
      right.appendChild(svgEl);
      svgZoomPan(svgEl);

      // legend
      const legend = el('div', {class:'pca-legend'}, [
        el('span', {class:'pca-legend-min'}, [`${fmt(-scoreAbsMax,2)}`]),
        el('div', {class:'pca-legend-bar'}),
        el('span', {class:'pca-legend-max'}, [`+${fmt(scoreAbsMax,2)}`]),
      ]);
      right.appendChild(legend);
    }
    body.appendChild(right);

    row.appendChild(body);
    host.appendChild(row);
  });

  host.appendChild(el('div', {class:'pca-caption'}, [
    '주성분 분석 — 응답 패턴의 주요 모드를 부품 loadings + 위치 score 로 분해.'
  ]));
}

function _pcaDivergingColor(t){
  // t in [-1, 1]; blue → light → red diverging
  const clamp = Math.max(-1, Math.min(1, t));
  if (clamp >= 0){
    // light → red
    const r = Math.round(245 + (220-245)*clamp);
    const g = Math.round(238 + ( 50-238)*clamp);
    const b = Math.round(232 + ( 47-232)*clamp);
    return `rgb(${r},${g},${b})`;
  } else {
    const a = -clamp;
    const r = Math.round(245 + ( 33-245)*a);
    const g = Math.round(238 + (102-238)*a);
    const b = Math.round(232 + (172-232)*a);
    return `rgb(${r},${g},${b})`;
  }
}

function _deepRenderAnomalyDetection(data){
  var root = document.getElementById('deep-anomaly-detection');
  if(!root) return;
  root.innerHTML = '';
  var payload = (data && data.deep_analytics && data.deep_analytics.anomaly_detection) || null;
  if(!payload || payload.empty || !payload.per_position || payload.per_position.length===0){
    root.appendChild(el('div',{class:'empty'},'데이터 없음'));
    return;
  }

  var rows = payload.per_position;
  var thresh = payload.threshold;

  // Group cells by face for 5x5 heatmap. Use first face that has any anomalous, else first.
  var byFace = {};
  rows.forEach(function(r){
    if(!byFace[r.face]) byFace[r.face] = [];
    byFace[r.face].push(r);
  });
  var faceCodes = Object.keys(byFace).sort();
  var preferred = null;
  for(var i=0;i<faceCodes.length;i++){
    if(byFace[faceCodes[i]].some(function(r){return r.anomalous;})){ preferred = faceCodes[i]; break; }
  }
  var defaultFace = preferred || faceCodes[0];

  // Header / summary
  var head = el('div',{class:'anom-head'},[
    el('div',{class:'anom-summary'},[
      el('span',{class:'anom-stat'},['임계값 z = ', fmt(thresh,2),
        ' (max(2.5, P95=', fmt(payload.p95_z,2), '))']),
      el('span',{class:'anom-stat'},['이상치 ', String(payload.n_anomalous), ' / ', String(rows.length), ' 위치']),
      el('span',{class:'anom-stat'},['IQR 펜스 [', fmt(payload.iqr_low,2), ', ', fmt(payload.iqr_high,2), '] (', _u('acc'), ')']),
    ])
  ]);
  root.appendChild(head);

  // Face selector
  if(faceCodes.length>1){
    var sel = el('select',{class:'anom-face-sel'});
    faceCodes.forEach(function(fc){
      var o = el('option',{value:fc},[fc===defaultFace?(fc+' ◆'):fc]);
      if(fc===defaultFace) o.selected = true;
      sel.appendChild(o);
    });
    sel.addEventListener('change', function(){ _renderAnomalyForFace(root, payload, sel.value); });
    var fwrap = el('div',{class:'anom-facewrap'},[el('span',{class:'anom-label'},['면 선택: ']), sel]);
    root.appendChild(fwrap);
  }

  _renderAnomalyForFace(root, payload, defaultFace);
}

function _renderAnomalyForFace(root, payload, faceCode){
  // Clear previous body
  var old = root.querySelector('.anom-body');
  if(old) old.remove();

  var rows = payload.per_position.filter(function(r){ return r.face === faceCode; });
  var thresh = payload.threshold;
  var maxAbsAll = 0;
  rows.forEach(function(r){ if(r.max_abs_z>maxAbsAll) maxAbsAll = r.max_abs_z; });
  var denom = Math.max(maxAbsAll, thresh, 1e-9);

  // Build 5x5 grid by ranking x then y
  var xs = Array.from(new Set(rows.map(function(r){return r.x;}))).sort(function(a,b){return a-b;});
  var ys = Array.from(new Set(rows.map(function(r){return r.y;}))).sort(function(a,b){return b-a;}); // top-down
  var nx = Math.max(xs.length,1), ny = Math.max(ys.length,1);
  var _dgA = (typeof DATA !== 'undefined' && DATA.device_geometry) || {aspect: 1};
  var _arA = (_dgA.aspect && isFinite(_dgA.aspect) && _dgA.aspect > 0) ? _dgA.aspect : 1;
  var cellW = 56;
  // Per-cell height tracks per-position physical extent: when nx==ny, ratio
  // simplifies to device aspect. (Falls back to square when ar==1.)
  var cellH = Math.max(20, Math.min(160, Math.round(cellW * (ny / nx) / _arA)));
  var pad = 28;
  var W = pad*2 + nx*cellW;
  var H = pad*2 + ny*cellH;

  var s = svg('svg',{width:W, height:H, viewBox:'0 0 '+W+' '+H, class:'anom-heatmap'});

  // Lookup map
  var grid = {};
  rows.forEach(function(r){
    var ix = xs.indexOf(r.x), iy = ys.indexOf(r.y);
    grid[ix+'_'+iy] = r;
  });

  for(var iy=0; iy<ny; iy++){
    for(var ix=0; ix<nx; ix++){
      var r = grid[ix+'_'+iy];
      var cx = pad + ix*cellW;
      var cy = pad + iy*cellH;
      var fill = '#1f1f24';
      var stroke = '#3a3a44';
      var sw = 1;
      var label = '';
      if(r){
        var t = Math.min(1, r.max_abs_z / denom);
        // gray to red ramp
        var rch = Math.round(60 + 195*t);
        var gch = Math.round(60 + (1-t)*60);
        var bch = Math.round(60 + (1-t)*60);
        fill = 'rgb('+rch+','+gch+','+bch+')';
        if(r.anomalous){ stroke = '#ff3030'; sw = 3; }
        label = String(r.pos_id);
      }
      s.appendChild(svg('rect',{
        x:cx, y:cy, width:cellW-2, height:cellH-2,
        fill: fill, stroke: stroke, 'stroke-width': sw, rx: 4
      }));
      if(r){
        s.appendChild(svg('text',{
          x: cx + (cellW-2)/2, y: cy + (cellH-2)/2 - 4,
          'text-anchor':'middle','dominant-baseline':'middle',
          'font-size': 10, fill: '#fff'
        },[label]));
        s.appendChild(svg('text',{
          x: cx + (cellW-2)/2, y: cy + (cellH-2)/2 + 10,
          'text-anchor':'middle','dominant-baseline':'middle',
          'font-size': 10, fill: '#eaeaf0', 'font-weight':600
        },['z=' + fmt(r.max_abs_z,1)]));
      }
    }
  }

  // Anomaly table for this face (top of full ranking, but limited to face)
  var anomRows = rows.filter(function(r){return r.anomalous;});
  anomRows.sort(function(a,b){return b.max_abs_z - a.max_abs_z;});

  var tbl = el('table',{class:'anom-table'});
  var thead = el('thead',{},[el('tr',{},[
    el('th',{},['순위']), el('th',{},['Pos']),
    el('th',{},['주요 원인']),
    el('th',{},['|z|max']),
    el('th',{},['z_g']), el('th',{},['z_s']), el('th',{},['z_d'])
  ])]);
  tbl.appendChild(thead);
  var tbody = el('tbody',{});
  if(anomRows.length === 0){
    tbody.appendChild(el('tr',{},[el('td',{colspan:7,class:'anom-empty'},['이 면에서 이상치 없음'])]));
  } else {
    anomRows.forEach(function(r, i){
      var driverKor = {peak_g:'가속도', peak_stress:'응력', peak_disp:'변위'}[r.driver] || r.driver;
      tbody.appendChild(el('tr',{},[
        el('td',{},[String(i+1)]),
        el('td',{},[String(r.pos_id)]),
        el('td',{class:'anom-driver'},[driverKor]),
        el('td',{class:'anom-zmax'},[fmt(r.max_abs_z,2)]),
        el('td',{},[fmt(r.z_g,2)]),
        el('td',{},[fmt(r.z_s,2)]),
        el('td',{},[fmt(r.z_d,2)]),
      ]));
    });
  }
  tbl.appendChild(tbody);

  // IQR list (cross-method)
  var zSet = {};
  payload.per_position.forEach(function(r){ if(r.anomalous) zSet[r.face+'_'+r.pos_id]=true; });
  var iqrList = el('div',{class:'anom-iqr-list'});
  iqrList.appendChild(el('div',{class:'anom-iqr-title'},['IQR 펜스 기반 이상치 (peak_g)']));
  if(!payload.iqr_outliers || payload.iqr_outliers.length===0){
    iqrList.appendChild(el('div',{class:'anom-empty'},['IQR 기준 이상치 없음']));
  } else {
    var ul = el('ul',{class:'anom-iqr-ul'});
    payload.iqr_outliers.forEach(function(o){
      var key = o.face+'_'+o.pos_id;
      var agree = !!zSet[key];
      var li = el('li',{class: agree ? 'anom-iqr-agree' : 'anom-iqr-only'},[
        el('span',{class:'anom-iqr-tag'},[agree ? '✓ 양쪽 일치' : '△ IQR만']),
        ' ', o.face, ' Pos ', String(o.pos_id),
        ' — peak_g=', fmt(o.mean_g,2), ' ', _u('acc')
      ]);
      ul.appendChild(li);
    });
    iqrList.appendChild(ul);
  }

  var body = el('div',{class:'anom-body'},[
    el('div',{class:'anom-left'},[s]),
    el('div',{class:'anom-right'},[tbl, iqrList])
  ]);
  root.appendChild(body);

  var cap = el('div',{class:'anom-caption'},[
    '위치별 응답이 평균에서 얼마나 벗어났는가. 빨간 테두리 = 통계적 이상치 (z>',
    fmt(thresh,2),' 또는 IQR fence 초과).'
  ]);
  root.appendChild(cap);
  svgZoomPan(s);
}

function _deepPpdPartName(p) {
  const nm = String(p.part_name || ('part_' + p.part_id));
  const tail = nm.split(/[\\/]/).pop();
  return tail || nm;
}

function _deepPpdRenderList(data) {
  const root = document.getElementById('ppd-part-list');
  if (!root) return;
  root.innerHTML = '';
  const parts = data.parts || [];
  if (!parts.length) {
    root.appendChild(el('div', { class: 'ppd-empty' }, '데이터 없음'));
    return;
  }
  const maxG = parts[0].max_peak_g || 1;
  parts.forEach(p => {
    const row = el('div', {
      class: 'ppd-list-row' + (DEEP_STATE.active_part === p.part_id ? ' active' : ''),
      'data-ppd-part': String(p.part_id)
    });
    const name = el('div', { class: 'ppd-list-name', title: p.part_name }, _deepPpdPartName(p));
    const valWrap = el('div', { class: 'ppd-list-val' });
    const barBg = el('div', { class: 'ppd-list-bar-bg' });
    const t = maxG > 0 ? Math.max(0.02, Math.min(1, p.max_peak_g / maxG)) : 0;
    const bar = el('div', { class: 'ppd-list-bar' });
    bar.style.width = (t * 100).toFixed(1) + '%';
    bar.style.background = gColor(t);
    barBg.appendChild(bar);
    const num = el('div', { class: 'ppd-list-num' }, fmt(p.max_peak_g, 1));
    valWrap.appendChild(barBg);
    valWrap.appendChild(num);
    row.appendChild(name);
    row.appendChild(valWrap);
    row.addEventListener('click', () => {
      DEEP_STATE.active_part = p.part_id;
      _deepPpdRenderList(data);
      _deepPpdRenderDetail(data);
    });
    root.appendChild(row);
  });
}

function _deepPpdGetMatrix() {
  // Reuse DOE matrix when available, else return null
  const doe = (DATA && DATA.doe_analysis) || null;
  if (doe && doe.peak_g_matrix && Object.keys(doe.peak_g_matrix).length > 0) {
    return doe.peak_g_matrix;
  }
  return null;
}

function _deepPpdActivePart(data) {
  const parts = data.parts || [];
  if (!parts.length) return null;
  const want = DEEP_STATE.active_part;
  for (let i = 0; i < parts.length; i++) {
    if (parts[i].part_id === want) return parts[i];
  }
  return parts[0];
}

function _deepPpdRenderKpi(data, active) {
  const root = document.getElementById('ppd-kpi-strip');
  if (!root) return;
  root.innerHTML = '';
  if (!active) {
    root.appendChild(el('div', { class: 'ppd-empty' }, '선택된 부품 없음'));
    return;
  }
  const tiles = [
    { label: '최대 Peak G',     value: fmt(active.max_peak_g, 1),     unit: _u('acc') },
    { label: '평균 Peak G',     value: fmt(active.mean_peak_g, 1),    unit: _u('acc') },
    { label: '최대 응력',        value: fmt(active.max_peak_stress, 2), unit: _u('stress') },
    { label: '최대 변위',        value: fmt(active.max_peak_disp, 3),  unit: _u('disp') },
    { label: 'P75↑ 위치 수',     value: String(active.n_positions_above_global_p75 || 0), unit: '/ ' + (Object.keys(data.positions_lookup || {}).length || 25) },
    { label: '항복 정의',        value: active.has_yield ? 'YES' : 'NO', unit: active.has_yield ? _u('stress') : '' }
  ];
  tiles.forEach(t => {
    const tile = el('div', { class: 'ppd-kpi-tile' });
    tile.appendChild(el('div', { class: 'ppd-kpi-label' }, t.label));
    const v = el('div', { class: 'ppd-kpi-val' }, t.value);
    if (t.unit) v.appendChild(el('span', { class: 'ppd-kpi-unit' }, ' ' + t.unit));
    tile.appendChild(v);
    root.appendChild(tile);
  });
}

function _deepPpdRenderHeatmap(data, active) {
  const root = document.getElementById('ppd-heatmap-svg');
  if (!root) return;
  while (root.firstChild) root.removeChild(root.firstChild);
  const _dgPP = (typeof DATA !== 'undefined' && DATA.device_geometry) || {aspect: 1};
  const _arPP = (_dgPP.aspect && isFinite(_dgPP.aspect) && _dgPP.aspect > 0) ? _dgPP.aspect : 1;
  const W = 320, H = Math.max(120, Math.round(W / _arPP));
  root.setAttribute('viewBox', '0 0 ' + W + ' ' + H);

  const mat = _deepPpdGetMatrix();
  const positions = data.positions_lookup || {};
  const posKeys = Object.keys(positions);

  if (!active || !mat || !posKeys.length) {
    root.appendChild(svg('text', { x: W/2, y: H/2, 'text-anchor': 'middle',
      fill: '#5c6383', 'font-size': 12 }, [document.createTextNode('위치별 peak_g 매트릭스 없음')]));
    return;
  }

  const row = mat[String(active.part_id)] || mat[active.part_id] || {};
  // bbox from positions
  let xmin = Infinity, xmax = -Infinity, ymin = Infinity, ymax = -Infinity;
  posKeys.forEach(k => {
    const xy = positions[k];
    if (!xy) return;
    if (xy.x < xmin) xmin = xy.x; if (xy.x > xmax) xmax = xy.x;
    if (xy.y < ymin) ymin = xy.y; if (xy.y > ymax) ymax = xy.y;
  });
  if (!isFinite(xmin) || xmin === xmax) { xmin -= 1; xmax += 1; }
  if (!isFinite(ymin) || ymin === ymax) { ymin -= 1; ymax += 1; }
  const padX = (xmax - xmin) * 0.08, padY = (ymax - ymin) * 0.08;
  xmin -= padX; xmax += padX; ymin -= padY; ymax += padY;

  // value normalization (use part's own max)
  let vmax = 0;
  posKeys.forEach(k => { const v = row[k] || 0; if (v > vmax) vmax = v; });
  if (vmax <= 0) {
    root.appendChild(svg('text', { x: W/2, y: H/2, 'text-anchor': 'middle',
      fill: '#5c6383', 'font-size': 12 }, [document.createTextNode('이 부품에 데이터 없음')]));
    return;
  }

  const margin = 24;
  const plotW = W - 2 * margin, plotH = H - 2 * margin;
  const sx = (x) => margin + (x - xmin) / (xmax - xmin) * plotW;
  const sy = (y) => margin + (1 - (y - ymin) / (ymax - ymin)) * plotH;

  // size cells based on nx/ny from grid if available
  const grid = (DATA.doe_analysis && DATA.doe_analysis.grid) || null;
  let cellW, cellH;
  if (grid && grid.nx && grid.ny) {
    cellW = plotW / grid.nx * 0.92;
    cellH = plotH / grid.ny * 0.92;
  } else {
    const n = Math.max(2, Math.ceil(Math.sqrt(posKeys.length)));
    cellW = plotW / n * 0.85;
    cellH = plotH / n * 0.85;
  }

  // background panel
  root.appendChild(svg('rect', { x: margin - 2, y: margin - 2,
    width: plotW + 4, height: plotH + 4, fill: '#0e1220', stroke: '#262d44',
    'stroke-width': 1, rx: 4 }));

  posKeys.forEach(k => {
    const xy = positions[k];
    if (!xy) return;
    const v = row[k] || 0;
    const t = v / vmax;
    const cx = sx(xy.x), cy = sy(xy.y);
    const fill = v > 0 ? gColor(t) : '#1a1e2e';
    const rect = svg('rect', { x: cx - cellW/2, y: cy - cellH/2,
      width: cellW, height: cellH, fill: fill, rx: 2,
      stroke: '#262d44', 'stroke-width': 0.5 });
    rect.appendChild(svg('title', null, [document.createTextNode(
      k + ': ' + fmt(v, 1) + ' ' + _u('acc'))]));
    root.appendChild(rect);
  });

  // star on max position
  if (active.max_pos_id && positions[active.max_pos_id]) {
    const xy = positions[active.max_pos_id];
    const cx = sx(xy.x), cy = sy(xy.y);
    // simple 5-point star path
    const r1 = Math.max(6, Math.min(cellW, cellH) * 0.35);
    const r2 = r1 * 0.45;
    let d = '';
    for (let i = 0; i < 10; i++) {
      const a = (i * Math.PI / 5) - Math.PI / 2;
      const r = (i % 2 === 0) ? r1 : r2;
      d += (i === 0 ? 'M' : 'L') + (cx + r * Math.cos(a)).toFixed(2) +
           ',' + (cy + r * Math.sin(a)).toFixed(2);
    }
    d += 'Z';
    root.appendChild(svg('path', { d: d, fill: '#fff7b0',
      stroke: '#1a1e2e', 'stroke-width': 1.2 }));
  }

  // legend min/max
  root.appendChild(svg('text', { x: margin, y: H - 4,
    fill: '#5c6383', 'font-size': 9 },
    [document.createTextNode('0 ~ ' + fmt(vmax, 1) + ' ' + _u('acc'))]));
  svgZoomPan(root);
}

function _deepPpdRenderHistogram(data, active) {
  const root = document.getElementById('ppd-hist-svg');
  if (!root) return;
  while (root.firstChild) root.removeChild(root.firstChild);
  const W = 320, H = 200;
  root.setAttribute('viewBox', '0 0 ' + W + ' ' + H);

  const mat = _deepPpdGetMatrix();
  const positions = data.positions_lookup || {};
  if (!active || !mat) {
    root.appendChild(svg('text', { x: W/2, y: H/2, 'text-anchor': 'middle',
      fill: '#5c6383', 'font-size': 12 }, [document.createTextNode('매트릭스 없음')]));
    return;
  }
  const row = mat[String(active.part_id)] || mat[active.part_id] || {};
  const vals = Object.keys(positions).map(k => Number(row[k] || 0));
  if (!vals.length) {
    root.appendChild(svg('text', { x: W/2, y: H/2, 'text-anchor': 'middle',
      fill: '#5c6383', 'font-size': 12 }, [document.createTextNode('데이터 없음')]));
    return;
  }
  const vmax = Math.max.apply(null, vals);
  if (vmax <= 0) {
    root.appendChild(svg('text', { x: W/2, y: H/2, 'text-anchor': 'middle',
      fill: '#5c6383', 'font-size': 12 }, [document.createTextNode('모든 위치에서 0')]));
    return;
  }
  const NB = 10;
  const counts = new Array(NB).fill(0);
  vals.forEach(v => {
    let b = Math.floor((v / vmax) * NB);
    if (b >= NB) b = NB - 1;
    if (b < 0) b = 0;
    counts[b] += 1;
  });
  const cmax = Math.max.apply(null, counts) || 1;

  const padL = 32, padR = 8, padT = 16, padB = 28;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  // axes
  root.appendChild(svg('line', { x1: padL, y1: padT + plotH, x2: padL + plotW,
    y2: padT + plotH, stroke: '#262d44', 'stroke-width': 1 }));
  root.appendChild(svg('line', { x1: padL, y1: padT, x2: padL,
    y2: padT + plotH, stroke: '#262d44', 'stroke-width': 1 }));

  const bw = plotW / NB;
  counts.forEach((c, i) => {
    const t = (i + 0.5) / NB;
    const h = (c / cmax) * plotH;
    const x = padL + i * bw + 1;
    const y = padT + plotH - h;
    const rect = svg('rect', { x: x, y: y, width: bw - 2, height: h,
      fill: gColor(t), rx: 1 });
    rect.appendChild(svg('title', null, [document.createTextNode(
      '[' + fmt(i * vmax / NB, 1) + ' ~ ' + fmt((i + 1) * vmax / NB, 1) +
      '] ' + _u('acc') + ': ' + c + '개')]));
    root.appendChild(rect);
  });
  // x-axis label
  root.appendChild(svg('text', { x: padL, y: H - 10, fill: '#5c6383',
    'font-size': 9, 'text-anchor': 'start' },
    [document.createTextNode('0')]));
  root.appendChild(svg('text', { x: padL + plotW, y: H - 10, fill: '#5c6383',
    'font-size': 9, 'text-anchor': 'end' },
    [document.createTextNode(fmt(vmax, 1) + ' ' + _u('acc'))]));
  root.appendChild(svg('text', { x: padL + plotW/2, y: H - 2, fill: '#aab2cf',
    'font-size': 10, 'text-anchor': 'middle' },
    [document.createTextNode('peak_g 분포 (25 위치)')]));
  // y-axis max
  root.appendChild(svg('text', { x: padL - 4, y: padT + 4, fill: '#5c6383',
    'font-size': 9, 'text-anchor': 'end' },
    [document.createTextNode(String(cmax))]));
}

function _deepPpdRenderYieldOrMat(data, active) {
  const root = document.getElementById('ppd-yield-svg');
  if (!root) return;
  while (root.firstChild) root.removeChild(root.firstChild);
  const W = 320, H = 200;
  root.setAttribute('viewBox', '0 0 ' + W + ' ' + H);

  if (!active) {
    root.appendChild(svg('text', { x: W/2, y: H/2, 'text-anchor': 'middle',
      fill: '#5c6383', 'font-size': 12 }, [document.createTextNode('선택된 부품 없음')]));
    return;
  }

  if (active.has_yield && active.yield_value && active.yield_value > 0) {
    const y = active.yield_value;
    const s = active.max_peak_stress || 0;
    const ratio = s / y;
    const vmax = Math.max(y, s) * 1.15;
    const padL = 32, padR = 16, padT = 24, padB = 40;
    const plotW = W - padL - padR, plotH = H - padT - padB;

    // background
    root.appendChild(svg('rect', { x: padL, y: padT, width: plotW, height: plotH,
      fill: '#0e1220', stroke: '#262d44', 'stroke-width': 1, rx: 2 }));

    // stress bar
    const sH = (s / vmax) * plotH;
    const fill = ratio >= 1 ? '#e85d75' : (ratio >= 0.7 ? '#f0b400' : '#5dd28a');
    const barW = plotW * 0.32;
    const sBarX = padL + plotW * 0.20;
    root.appendChild(svg('rect', { x: sBarX, y: padT + plotH - sH,
      width: barW, height: sH, fill: fill, rx: 2 }));
    root.appendChild(svg('text', { x: sBarX + barW/2, y: padT + plotH + 14,
      'text-anchor': 'middle', fill: '#aab2cf', 'font-size': 10 },
      [document.createTextNode('최대 응력')]));
    root.appendChild(svg('text', { x: sBarX + barW/2, y: padT + plotH - sH - 4,
      'text-anchor': 'middle', fill: '#e0e4ff', 'font-size': 10 },
      [document.createTextNode(fmt(s, 2))]));

    // yield bar
    const yH = (y / vmax) * plotH;
    const yBarX = padL + plotW * 0.58;
    root.appendChild(svg('rect', { x: yBarX, y: padT + plotH - yH,
      width: barW, height: yH, fill: '#3b528b', rx: 2 }));
    root.appendChild(svg('text', { x: yBarX + barW/2, y: padT + plotH + 14,
      'text-anchor': 'middle', fill: '#aab2cf', 'font-size': 10 },
      [document.createTextNode('항복')]));
    root.appendChild(svg('text', { x: yBarX + barW/2, y: padT + plotH - yH - 4,
      'text-anchor': 'middle', fill: '#e0e4ff', 'font-size': 10 },
      [document.createTextNode(fmt(y, 2))]));

    // yield line
    root.appendChild(svg('line', { x1: padL, y1: padT + plotH - yH,
      x2: padL + plotW, y2: padT + plotH - yH,
      stroke: '#e85d75', 'stroke-width': 1, 'stroke-dasharray': '4 3' }));

    root.appendChild(svg('text', { x: W/2, y: 14, 'text-anchor': 'middle',
      fill: '#e0e4ff', 'font-size': 11 },
      [document.createTextNode('응력/항복 비교 — 비율 ' + (ratio * 100).toFixed(1) + '%')]));
    root.appendChild(svg('text', { x: W/2, y: H - 6, 'text-anchor': 'middle',
      fill: '#5c6383', 'font-size': 9 },
      [document.createTextNode('단위: ' + _u('stress'))]));
  } else {
    // material card — show E and density (impactor proxy)
    const mat = data.impactor_material || { youngs_modulus: 0, density: 0 };
    root.appendChild(svg('text', { x: W/2, y: 22, 'text-anchor': 'middle',
      fill: '#e0e4ff', 'font-size': 12 },
      [document.createTextNode('항복 응력 미정의')]));
    root.appendChild(svg('text', { x: W/2, y: 42, 'text-anchor': 'middle',
      fill: '#5c6383', 'font-size': 9 },
      [document.createTextNode('대신 충격체 재료 정보 표시')]));

    const rows = [
      ['최대 응력 (관측)', fmt(active.max_peak_stress, 2) + ' ' + _u('stress')],
      ['충격체 E',         fmt(mat.youngs_modulus, 2) + ' ' + _u('stress')],
      ['충격체 밀도',      fmt(mat.density, 6)]
    ];
    rows.forEach((r, i) => {
      const y = 80 + i * 28;
      root.appendChild(svg('text', { x: 24, y: y, fill: '#aab2cf', 'font-size': 11 },
        [document.createTextNode(r[0])]));
      root.appendChild(svg('text', { x: W - 24, y: y, 'text-anchor': 'end',
        fill: '#e0e4ff', 'font-size': 11 },
        [document.createTextNode(r[1])]));
    });
  }
}

function _deepPpdRenderDetail(data) {
  const active = _deepPpdActivePart(data);
  // title
  const titleEl = document.getElementById('ppd-detail-title');
  if (titleEl) {
    if (active) {
      titleEl.textContent = '활성 부품: ' + _deepPpdPartName(active) +
        '  (id=' + active.part_id + ', 최대 위치=' + active.max_pos_id + ')';
    } else {
      titleEl.textContent = '활성 부품 없음';
    }
  }
  _deepPpdRenderKpi(data, active);
  _deepPpdRenderHeatmap(data, active);
  _deepPpdRenderHistogram(data, active);
  _deepPpdRenderYieldOrMat(data, active);
}

function _deepRenderPerPartDrillDown(deepData) {
  const data = deepData && deepData.per_part_drilldown;
  const host = document.getElementById('ppd-host');
  if (!host) return;
  if (!data || !data.parts || !data.parts.length) {
    host.style.display = 'none';
    return;
  }
  host.style.display = '';
  // initialize active part = top-1 by default
  if (DEEP_STATE.active_part == null) {
    DEEP_STATE.active_part = data.parts[0].part_id;
  }
  _deepPpdRenderList(data);
  _deepPpdRenderDetail(data);
}

function _insightRenderSymmetry(data){
  const root = document.getElementById('insight-symmetry');
  if(!root) return;
  if(!data){ root.innerHTML = '<div class="ins-empty">데이터 없음</div>'; return; }

  const xPairs = data.x_mirror_pairs || [];
  const yPairs = data.y_mirror_pairs || [];
  const bs = data.boundary_summary || {};
  const medX = (data.median_x_asym_pct==null) ? NaN : data.median_x_asym_pct;
  const medY = (data.median_y_asym_pct==null) ? NaN : data.median_y_asym_pct;

  const symX = isFinite(medX) ? Math.max(0, 100 - medX) : NaN;
  const symY = isFinite(medY) ? Math.max(0, 100 - medY) : NaN;
  const bamp = (bs.boundary_amplification_pct==null) ? NaN : bs.boundary_amplification_pct;

  const fnum = (v, nd=1) => (v==null || !isFinite(v)) ? '—' : Number(v).toFixed(nd);

  const verdictOk = !!data.design_symmetric;
  let verdictText, verdictCls;
  if(verdictOk){
    verdictText = '디자인 대칭성 양호 (X·Y 중앙값 비대칭 < 15%)';
    verdictCls = 'sym-verdict ok';
  } else {
    const reasons = [];
    if(isFinite(medX) && medX >= 15) reasons.push('X축 비대칭');
    if(isFinite(medY) && medY >= 15) reasons.push('Y축 비대칭');
    if(!reasons.length) reasons.push('데이터 불충분');
    verdictText = reasons.join(' · ');
    verdictCls = 'sym-verdict warn';
  }

  const kpi = (label, value, suffix) => `
    <div class="sym-kpi">
      <div class="sym-kpi-lbl">${label}</div>
      <div class="sym-kpi-val">${fnum(value,1)}<span class="sym-kpi-suf">${suffix||''}</span></div>
    </div>`;

  const rowHtml = (p) => {
    const cls = p.asymmetry_pct >= 15 ? 'hi' : (p.asymmetry_pct >= 8 ? 'mid' : '');
    return `<tr class="${cls}">
      <td class="sym-pair">#${p.pos_a} ↔ #${p.pos_b}</td>
      <td class="sym-num">${fnum(p.peak_g_a,2)}</td>
      <td class="sym-num">${fnum(p.peak_g_b,2)}</td>
      <td class="sym-num sym-asym">${fnum(p.asymmetry_pct,2)}%</td>
    </tr>`;
  };

  const tableHtml = (title, pairs, count) => {
    if(!pairs.length){
      return `<div class="sym-tblbox"><div class="sym-tbl-title">${title}</div>
        <div class="ins-empty">미러 쌍 없음</div></div>`;
    }
    const subtitle = count > pairs.length ? `상위 ${pairs.length} / 총 ${count}` : `${pairs.length}쌍`;
    return `<div class="sym-tblbox">
      <div class="sym-tbl-title">${title} <span class="sym-tbl-sub">${subtitle}</span></div>
      <table class="sym-tbl">
        <thead><tr>
          <th>위치 쌍</th><th>peak_g A</th><th>peak_g B</th><th>비대칭%</th>
        </tr></thead>
        <tbody>${pairs.map(rowHtml).join('')}</tbody>
      </table>
    </div>`;
  };

  const gunit = (typeof _u === 'function') ? _u('peak_g','G') : 'G';

  root.innerHTML = `
    <div class="sym-kpis">
      ${kpi('X 대칭성 점수', symX, ' /100')}
      ${kpi('Y 대칭성 점수', symY, ' /100')}
      ${kpi('경계 증폭률', bamp, '%')}
      <div class="sym-kpi sym-kpi-meta">
        <div class="sym-kpi-lbl">외곽 / 내부 평균 peak_g</div>
        <div class="sym-kpi-val sym-kpi-val-sm">
          ${fnum(bs.outer_mean_peak_g,2)} <span class="sym-kpi-suf">vs</span> ${fnum(bs.inner_mean_peak_g,2)}
          <span class="sym-kpi-suf"> ${gunit} (n=${bs.outer_n||0}/${bs.inner_n||0})</span>
        </div>
      </div>
    </div>
    <div class="${verdictCls}">${verdictText}</div>
    <div class="sym-tables">
      ${tableHtml('X-미러 쌍 ((x,y) ↔ (-x,y))', xPairs, data.x_pair_count||xPairs.length)}
      ${tableHtml('Y-미러 쌍 ((x,y) ↔ (x,-y))', yPairs, data.y_pair_count||yPairs.length)}
    </div>
    <div class="sym-foot">
      중앙값 비대칭: X = ${fnum(medX,2)}% · Y = ${fnum(medY,2)}% &nbsp;|&nbsp;
      외곽 = 위치별 max(|x|,|y|)가 면 최대치인 점, 내부 = 그 외.
    </div>
  `;
}
function _insightRenderDamageIndex(data){
  const root = document.getElementById('insight-DamageIndex');
  if(!root) return;
  const body = root.querySelector('.insight-body');
  if(!body) return;
  body.innerHTML = '';

  const d = (data && data.DamageIndex) || null;
  if(!d || !d.per_part || d.per_part.length === 0){
    body.innerHTML = '<div class="di-empty">데이터 없음 — DI를 계산할 수 있는 부품이 없습니다.</div>';
    return;
  }

  const per = d.per_part;
  const pairs = d.top_pairs || [];
  const summary = d.summary || {};
  const source = per[0].di_source;
  const sourceLabel = source === 'yield'
    ? 'yield-based (∑ max(0, σ/σ_y − 1) over positions)'
    : 'composite (normalized peak g/stress/strain → [0,1])';

  // Caption
  const cap = document.createElement('div');
  cap.className = 'di-caption';
  const mp = summary.max_di_part ? `${summary.max_di_part} @ pos ${summary.max_di_position ?? '—'}` : '—';
  cap.innerHTML = `<b>DI 산정 방식:</b> ${sourceLabel} &nbsp;·&nbsp; ` +
                  `<b>최대 DI:</b> ${(summary.max_di_value ?? 0).toFixed(3)} (${mp}) &nbsp;·&nbsp; ` +
                  `<b>대상 부품:</b> ${summary.n_parts_with_data}/${summary.n_parts_total}`;
  body.appendChild(cap);

  // Two-column layout
  const wrap = document.createElement('div');
  wrap.className = 'di-wrap';
  body.appendChild(wrap);

  // --- LEFT: horizontal bar chart (top-12) ---
  const left = document.createElement('div');
  left.className = 'di-left';
  wrap.appendChild(left);
  const h2 = document.createElement('div');
  h2.className = 'di-subtitle';
  h2.textContent = '부품별 DI (Top 12)';
  left.appendChild(h2);

  const top12 = per.slice(0, 12);
  const maxDi = Math.max.apply(null, top12.map(r => r.di)) || 1.0;
  const W = 560, rowH = 26, labelW = 150, valueW = 70;
  const chartW = W - labelW - valueW - 16;
  const H = top12.length * rowH + 12;
  const s = svg(W, H);
  s.setAttribute('class', 'di-svg');

  top12.forEach((r, i) => {
    const y = i * rowH + 6;
    const frac = (maxDi > 0) ? (r.di / maxDi) : 0;
    const barLen = Math.max(1, frac * chartW);

    // red gradient: deeper red for larger DI fraction
    const t = Math.min(1, Math.max(0, frac));
    // interpolate from #fee0d2 (light) to #99000d (deep red)
    const lerp = (a,b)=> Math.round(a + (b - a) * t);
    const r1 = lerp(254, 153), g1 = lerp(224, 0), b1 = lerp(210, 13);
    const fill = `rgb(${r1},${g1},${b1})`;

    // label
    const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    label.setAttribute('x', labelW - 6);
    label.setAttribute('y', y + rowH/2 + 4);
    label.setAttribute('text-anchor', 'end');
    label.setAttribute('class', 'di-label');
    const nm = (r.part_name || ('part_' + r.part_id));
    label.textContent = nm.length > 22 ? (nm.slice(0,21) + '…') : nm;
    label.setAttribute('title', nm);
    s.appendChild(label);

    // bar background
    const bgRect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    bgRect.setAttribute('x', labelW);
    bgRect.setAttribute('y', y + 4);
    bgRect.setAttribute('width', chartW);
    bgRect.setAttribute('height', rowH - 10);
    bgRect.setAttribute('fill', '#f6f6f6');
    bgRect.setAttribute('stroke', '#e5e5e5');
    s.appendChild(bgRect);

    // bar
    const bar = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    bar.setAttribute('x', labelW);
    bar.setAttribute('y', y + 4);
    bar.setAttribute('width', barLen);
    bar.setAttribute('height', rowH - 10);
    bar.setAttribute('fill', fill);
    bar.setAttribute('class', 'di-bar');
    // Tooltip
    let tip = `${nm}\nDI = ${r.di.toFixed(3)}\nsource: ${r.di_source}`;
    if(r.di_source === 'yield'){
      tip += `\nyield σ_y = ${r.yield_stress}\n초과 위치 수 = ${r.n_positions_above_yield}/${r.n_positions}`;
      tip += `\n최대 기여 위치: pos ${r.peak_pos_id ?? '—'}`;
    } else {
      tip += `\nmax peak_g = ${r.max_peak_g}`;
      tip += `\nmax peak_stress = ${r.max_peak_stress}`;
      tip += `\nmax peak_strain = ${r.max_peak_strain}`;
      tip += `\n최대 기여 위치: pos ${r.peak_pos_id ?? '—'}`;
    }
    const ttl = document.createElementNS('http://www.w3.org/2000/svg', 'title');
    ttl.textContent = tip;
    bar.appendChild(ttl);
    s.appendChild(bar);

    // value text
    const vt = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    vt.setAttribute('x', labelW + chartW + 6);
    vt.setAttribute('y', y + rowH/2 + 4);
    vt.setAttribute('class', 'di-value');
    vt.textContent = r.di.toFixed(3);
    s.appendChild(vt);
  });
  left.appendChild(s);

  // --- RIGHT: dominant (part, pos) Top 5 ---
  const right = document.createElement('div');
  right.className = 'di-right';
  wrap.appendChild(right);
  const h3 = document.createElement('div');
  h3.className = 'di-subtitle';
  h3.textContent = '지배적 (부품, 위치) Top 5';
  right.appendChild(h3);

  if(pairs.length === 0){
    const noPair = document.createElement('div');
    noPair.className = 'di-empty';
    noPair.textContent = '기여 위치 없음';
    right.appendChild(noPair);
  } else {
    const ol = document.createElement('ol');
    ol.className = 'di-pair-list';
    const maxContrib = Math.max.apply(null, pairs.map(p=>p.contrib)) || 1.0;
    pairs.forEach((p, idx) => {
      const li = document.createElement('li');
      const frac = (maxContrib > 0) ? p.contrib / maxContrib : 0;
      const t = Math.min(1, Math.max(0, frac));
      const lerp = (a,b)=> Math.round(a + (b - a) * t);
      const fill = `rgb(${lerp(254,153)},${lerp(224,0)},${lerp(210,13)})`;
      const nm = (p.part_name || ('part_' + p.part_id));
      li.innerHTML =
        `<span class="di-rank">${idx+1}</span>` +
        `<span class="di-pair-name" title="${nm}">${nm.length>18?nm.slice(0,17)+'…':nm}@${p.pos_id}</span>` +
        `<span class="di-pair-bar"><span class="di-pair-fill" style="width:${(frac*100).toFixed(1)}%;background:${fill}"></span></span>` +
        `<span class="di-pair-val">${p.contrib.toFixed(3)}</span>`;
      ol.appendChild(li);
    });
    right.appendChild(ol);
  }
}
function _insightRenderReboundField(data){
  const root = document.getElementById('insight-rebound-field');
  if(!root) return;
  if(!data || !data.vectors || data.vectors.length === 0){
    root.innerHTML = '<div class="insight-empty">반발 벡터 데이터 없음</div>';
    return;
  }

  const vectors = data.vectors;
  const bbox = data.bbox || [0,0,1,1];
  const maxSpeed = Math.max(data.max_speed || 0, 1e-9);
  const velU = data.vel_unit || 'm/s';

  // KPI bar
  const kpi = root.querySelector('.rf-kpis');
  if(kpi){
    kpi.innerHTML = `
      <div class="rf-kpi"><span class="rf-kpi-lbl">평균 반발 속도</span><span class="rf-kpi-val">${fmt(data.avg_speed,2)} ${velU}</span></div>
      <div class="rf-kpi"><span class="rf-kpi-lbl">최대 반발 속도</span><span class="rf-kpi-val">${fmt(data.max_speed,2)} ${velU}</span></div>
      <div class="rf-kpi"><span class="rf-kpi-lbl">바운스 (vz↑)</span><span class="rf-kpi-val rf-up">${data.n_rebound_up} / ${data.n_total}</span></div>
      <div class="rf-kpi"><span class="rf-kpi-lbl">관통/매립 (vz↓)</span><span class="rf-kpi-val rf-down">${data.n_embed_down} / ${data.n_total}</span></div>
      <div class="rf-kpi"><span class="rf-kpi-lbl">슬라이딩 (xy우세)</span><span class="rf-kpi-val">${data.n_sliding} / ${data.n_total}</span></div>
    `;
  }

  // SVG quiver — sized to device aspect (cells reflect physical layout)
  const _dgR = (typeof DATA !== 'undefined' && DATA.device_geometry) || {aspect: 1};
  const _arR = (_dgR.aspect && isFinite(_dgR.aspect) && _dgR.aspect > 0) ? _dgR.aspect : 1;
  const W = 460, H = Math.max(160, Math.round(W / _arR)), pad = 36;
  const [x0, y0, x1, y1] = bbox;
  const dx = Math.max(x1 - x0, 1e-9);
  const dy = Math.max(y1 - y0, 1e-9);
  const sx = (W - 2*pad) / dx;
  const sy = (H - 2*pad) / dy;
  const s = Math.min(sx, sy);

  // cell size (5x5 grid assumed): pick scale so max arrow ~ 0.45 * cell spacing
  // Estimate cell spacing from positions
  const uniqX = Array.from(new Set(vectors.map(v=>v.x))).sort((a,b)=>a-b);
  const uniqY = Array.from(new Set(vectors.map(v=>v.y))).sort((a,b)=>a-b);
  let cellW = (uniqX.length > 1) ? (uniqX[uniqX.length-1] - uniqX[0]) / (uniqX.length - 1) : dx/5;
  let cellH = (uniqY.length > 1) ? (uniqY[uniqY.length-1] - uniqY[0]) / (uniqY.length - 1) : dy/5;
  const cellPx = Math.min(cellW * s, cellH * s);
  const arrowMaxPx = 0.45 * cellPx;

  const xToPx = x => pad + (x - x0) * s;
  const yToPx = y => H - pad - (y - y0) * s; // flip Y

  let svgParts = [];
  // bbox frame
  svgParts.push(`<rect x="${pad}" y="${pad}" width="${W-2*pad}" height="${H-2*pad}" fill="#0d1117" stroke="#30363d" stroke-width="1"/>`);

  // Grid hints — light dotted lines at unique X/Y
  for(const xv of uniqX){
    const px = xToPx(xv);
    svgParts.push(`<line x1="${px}" y1="${pad}" x2="${px}" y2="${H-pad}" stroke="#21262d" stroke-width="0.5" stroke-dasharray="2 3"/>`);
  }
  for(const yv of uniqY){
    const py = yToPx(yv);
    svgParts.push(`<line x1="${pad}" y1="${py}" x2="${W-pad}" y2="${py}" stroke="#21262d" stroke-width="0.5" stroke-dasharray="2 3"/>`);
  }

  const colorFor = c => c === 'up' ? '#4493f8' : (c === 'down' ? '#f85149' : '#8b949e');

  // Arrows
  for(const v of vectors){
    const cx = xToPx(v.x);
    const cy = yToPx(v.y);
    const col = colorFor(v.color_class);

    // origin dot
    svgParts.push(`<circle cx="${cx}" cy="${cy}" r="2" fill="${col}" opacity="0.9"/>`);

    if(v.missing){ continue; }

    const mag = v.speed;
    if(mag < 1e-9){
      // draw an "x" to indicate no lateral motion
      svgParts.push(`<circle cx="${cx}" cy="${cy}" r="4" fill="none" stroke="${col}" stroke-width="1" opacity="0.6"/>`);
      continue;
    }

    const lenPx = (mag / maxSpeed) * arrowMaxPx;
    // vy positive = up in physical space; svg y is down, so flip
    const ux = v.vx_rebound / mag;
    const uy = -v.vy_rebound / mag;
    const ex = cx + ux * lenPx;
    const ey = cy + uy * lenPx;

    // arrow shaft
    svgParts.push(`<line x1="${cx}" y1="${cy}" x2="${ex}" y2="${ey}" stroke="${col}" stroke-width="1.6" opacity="0.95"/>`);

    // arrowhead
    const ah = Math.min(6, lenPx * 0.35);
    const ang = Math.atan2(uy, ux);
    const a1 = ang + 2.6;
    const a2 = ang - 2.6;
    const hx1 = ex + Math.cos(a1) * ah;
    const hy1 = ey + Math.sin(a1) * ah;
    const hx2 = ex + Math.cos(a2) * ah;
    const hy2 = ey + Math.sin(a2) * ah;
    svgParts.push(`<polygon points="${ex},${ey} ${hx1},${hy1} ${hx2},${hy2}" fill="${col}" opacity="0.95"/>`);

    // hover title
    svgParts.push(`<title>pos ${v.pos_id}: |v_xy|=${v.speed.toFixed(2)} ${velU}, v_z=${v.vz_final.toFixed(2)} ${velU}</title>`);
  }

  // Scale reference (bottom-left)
  const refX = pad + 6;
  const refY = H - 10;
  svgParts.push(`<line x1="${refX}" y1="${refY}" x2="${refX + arrowMaxPx}" y2="${refY}" stroke="#c9d1d9" stroke-width="1.5"/>`);
  svgParts.push(`<text x="${refX + arrowMaxPx + 6}" y="${refY + 3}" fill="#c9d1d9" font-size="10">${fmt(maxSpeed,2)} ${velU}</text>`);

  // Legend (top-right)
  const legendItems = [
    {c:'#4493f8', l:'bounce (vz↑)'},
    {c:'#f85149', l:'embed (vz↓)'},
    {c:'#8b949e', l:'flat'},
  ];
  let lx = W - pad - 110, ly = pad + 4;
  svgParts.push(`<rect x="${lx-6}" y="${ly-2}" width="116" height="${legendItems.length*14+6}" fill="#0d1117" stroke="#30363d" stroke-width="0.5" opacity="0.85"/>`);
  legendItems.forEach((it, i) => {
    const yy = ly + 10 + i*14;
    svgParts.push(`<line x1="${lx}" y1="${yy}" x2="${lx+18}" y2="${yy}" stroke="${it.c}" stroke-width="2"/>`);
    svgParts.push(`<text x="${lx+24}" y="${yy+3}" fill="#c9d1d9" font-size="10">${it.l}</text>`);
  });

  const svgWrap = root.querySelector('.rf-svg-wrap');
  if(svgWrap){
    svgWrap.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="100%" preserveAspectRatio="xMidYMid meet" style="height:auto">${svgParts.join('')}</svg>`;
    svgZoomPan(svgWrap.querySelector('svg'));
  }
}
function _insightRenderAutoRecommend(data) {
  const root = document.getElementById('insight-panel-auto-recommend');
  if (!root) return;
  const body = root.querySelector('.insight-body');
  if (!body) return;
  body.innerHTML = '';

  if (!data || !data.recommendations) {
    body.appendChild(el('div', {class: 'insight-empty'}, '권고 데이터 없음'));
    return;
  }

  // Merge with doe_analysis and deep_analytics if present
  const extra = [];
  try {
    const doe = (window.DATA && DATA.doe_analysis) ? DATA.doe_analysis : null;
    if (doe && doe.pca) {
      const pc1 = doe.pca.explained_variance_ratio
        ? (doe.pca.explained_variance_ratio[0] || 0) * 100.0
        : null;
      if (pc1 !== null && isFinite(pc1)) {
        let topLoad = '';
        if (doe.pca.top_loadings_pc1 && doe.pca.top_loadings_pc1.length) {
          topLoad = doe.pca.top_loadings_pc1[0].name || doe.pca.top_loadings_pc1[0].part_name || '';
        }
        extra.push({
          severity: pc1 > 60 ? 'warning' : 'info',
          title: 'PCA 모드 1 지배도',
          body: `PCA PC1이 전체 응답의 ${pc1.toFixed(1)}%를 설명${topLoad ? ` — '${topLoad}' 가 dominant loading` : ''}. 모드 1 형상에 대한 강성 분포 검토 권장.`,
          source_panel: 'DOE / PCA Analysis',
          metric: Number(pc1.toFixed(1))
        });
      }
    }
  } catch (e) { /* ignore */ }

  try {
    const deep = (window.DATA && DATA.deep_analytics) ? DATA.deep_analytics : null;
    if (deep && deep.anomalies && Array.isArray(deep.anomalies) && deep.anomalies.length) {
      const list = deep.anomalies.slice(0, 5)
        .map(a => `P${a.pos_id}(z=${(a.z != null ? a.z.toFixed(2) : '?')})`)
        .join(', ');
      extra.push({
        severity: 'warning',
        title: 'Deep Analytics 이상치',
        body: `${deep.anomalies.length}개 위치가 deep analytics 기준 이상치: ${list}.`,
        source_panel: 'Deep Analytics',
        metric: deep.anomalies.length
      });
    }
  } catch (e) { /* ignore */ }

  const all = (data.recommendations || []).concat(extra);
  const order = {critical: 0, warning: 1, info: 2};
  all.sort((a, b) => (order[a.severity] ?? 9) - (order[b.severity] ?? 9));

  const total = all.length;
  const crit = all.filter(r => r.severity === 'critical').length;
  const warn = all.filter(r => r.severity === 'warning').length;
  const info = all.filter(r => r.severity === 'info').length;

  const header = el('div', {class: 'ar-summary'});
  header.appendChild(el('span', {class: 'ar-chip ar-chip-total'}, `총 ${total}건`));
  header.appendChild(el('span', {class: 'ar-chip ar-chip-critical'}, `긴급 ${crit}`));
  header.appendChild(el('span', {class: 'ar-chip ar-chip-warning'}, `주의 ${warn}`));
  header.appendChild(el('span', {class: 'ar-chip ar-chip-info'}, `참고 ${info}`));
  body.appendChild(header);

  if (!all.length) {
    body.appendChild(el('div', {class: 'insight-empty'}, '생성된 권고가 없습니다. 입력 데이터 부족.'));
    return;
  }

  const grid = el('div', {class: 'ar-grid'});
  all.forEach(r => {
    const card = el('div', {class: `ar-card ar-${r.severity || 'info'}`});
    const stripe = el('div', {class: 'ar-stripe'});
    const main = el('div', {class: 'ar-main'});
    const titleRow = el('div', {class: 'ar-title-row'});
    titleRow.appendChild(el('span', {class: 'ar-sev-tag'},
      r.severity === 'critical' ? '긴급' :
      r.severity === 'warning'  ? '주의' : '참고'));
    titleRow.appendChild(el('span', {class: 'ar-title'}, r.title || '(제목 없음)'));
    if (r.metric != null) {
      titleRow.appendChild(el('span', {class: 'ar-metric'}, String(r.metric)));
    }
    main.appendChild(titleRow);
    main.appendChild(el('div', {class: 'ar-body'}, r.body || ''));
    if (r.source_panel) {
      const src = el('div', {class: 'ar-source'});
      src.appendChild(el('span', {class: 'ar-source-label'}, '출처:'));
      src.appendChild(el('span', {class: 'ar-source-tag'}, r.source_panel));
      main.appendChild(src);
    }
    card.appendChild(stripe);
    card.appendChild(main);
    grid.appendChild(card);
  });
  body.appendChild(grid);
}

function _insightRenderContactPulse(data){
  const root = document.getElementById('insight-ContactPulse');
  if(!root){ return; }
  if(!data || !data.per_position || data.per_position.length === 0){
    root.innerHTML = '<div class="ins-empty">유효한 contact pulse 데이터가 없습니다.</div>';
    return;
  }
  const pp = data.per_position.slice();
  const summary = data.summary || {};

  // Valid durations
  const valid = pp.filter(d => d.pulse_duration_ms !== null && isFinite(d.pulse_duration_ms));
  const durs = valid.map(d => d.pulse_duration_ms);
  const dMin = durs.length ? Math.min.apply(null, durs) : 0;
  const dMax = durs.length ? Math.max.apply(null, durs) : 1;
  const dRange = (dMax - dMin) || 1;

  // Color scale: short=red (sharp), long=blue (distributed)
  function colorFor(v){
    if(v === null || !isFinite(v)) return '#2a2a2a';
    const t = (v - dMin) / dRange;
    // red(short) -> yellow -> blue(long)
    const stops = [[220,60,60],[240,200,90],[70,140,220]];
    const tt = Math.max(0, Math.min(1, t));
    const seg = tt < 0.5 ? 0 : 1;
    const lt = tt < 0.5 ? tt*2 : (tt-0.5)*2;
    const a = stops[seg], b = stops[seg+1];
    const r = Math.round(a[0]+(b[0]-a[0])*lt);
    const g = Math.round(a[1]+(b[1]-a[1])*lt);
    const bl= Math.round(a[2]+(b[2]-a[2])*lt);
    return `rgb(${r},${g},${bl})`;
  }

  // --- Layout ---
  root.innerHTML = `
    <div class="cp-grid">
      <div class="cp-heatmap-wrap">
        <div class="cp-title">5×5 위치별 펄스 지속시간 (ms)</div>
        <div id="cp-heatmap"></div>
        <div class="cp-legend" id="cp-legend"></div>
      </div>
      <div class="cp-hist-wrap">
        <div class="cp-title">지속시간 분포 (10 bins)</div>
        <div id="cp-hist"></div>
        <div class="cp-stats" id="cp-stats"></div>
      </div>
    </div>
    <div class="cp-rank-wrap">
      <div class="cp-rank-col">
        <div class="cp-title">Top-5 최장 지속</div>
        <div id="cp-top5"></div>
      </div>
      <div class="cp-rank-col">
        <div class="cp-title">Bottom-5 최단 지속</div>
        <div id="cp-bot5"></div>
      </div>
    </div>
    <div class="cp-caption">Contact 지속시간 = first→last engaged 시간차. 짧을수록 강한 단발 충격, 길수록 분산된 충격.</div>
  `;

  // --- Heatmap (5x5) ---
  // Group by face if multiple, else single grid. Use x,y -> rank to 5x5.
  // Determine grid: sort unique x, unique y.
  const xs = Array.from(new Set(pp.map(p => +p.x.toFixed(6)))).sort((a,b)=>a-b);
  const ys = Array.from(new Set(pp.map(p => +p.y.toFixed(6)))).sort((a,b)=>a-b);
  const nx = Math.min(xs.length, 5);
  const ny = Math.min(ys.length, 5);

  const hmHost = document.getElementById('cp-heatmap');
  const _dgCP = (typeof DATA !== 'undefined' && DATA.device_geometry) || {aspect: 1};
  const _arCP = (_dgCP.aspect && isFinite(_dgCP.aspect) && _dgCP.aspect > 0) ? _dgCP.aspect : (56/40);
  const cellW = 56;
  // Each cell is one (nx,ny) DOE slot — its physical extent is
  // (device_w / nx) × (device_h / ny). With equal nx/ny ratios reduce to
  // device aspect itself.
  const cellH = Math.max(20, Math.min(120, Math.round(cellW * (ny / Math.max(nx,1)) / _arCP)));
  const padL = 30, padT = 10;
  const W = padL + nx*cellW + 10, H = padT + ny*cellH + 24;
  let svgEl = `<svg width="${W}" height="${H}" class="cp-hm-svg">`;
  // map x,y to cell indices
  function ix(v){ let best=0,bd=1e30; for(let i=0;i<xs.length;i++){const d=Math.abs(xs[i]-v); if(d<bd){bd=d;best=i;}} return best; }
  function iy(v){ let best=0,bd=1e30; for(let i=0;i<ys.length;i++){const d=Math.abs(ys[i]-v); if(d<bd){bd=d;best=i;}} return best; }

  // Build a map for quick lookup
  const cellMap = {};
  pp.forEach(p => {
    const i = ix(+p.x.toFixed(6));
    const j = iy(+p.y.toFixed(6));
    cellMap[`${i}_${j}`] = p;
  });

  for(let j=ny-1;j>=0;j--){
    for(let i=0;i<nx;i++){
      const x = padL + i*cellW;
      const y = padT + (ny-1-j)*cellH;
      const p = cellMap[`${i}_${j}`];
      const fill = p ? colorFor(p.pulse_duration_ms) : '#1a1a1a';
      const lbl = p ? (p.pulse_duration_ms!==null ? p.pulse_duration_ms.toFixed(1) : '—') : '';
      const pid = p ? `P${p.pos_id}` : '';
      svgEl += `<rect x="${x}" y="${y}" width="${cellW-2}" height="${cellH-2}" fill="${fill}" stroke="#444" stroke-width="0.5" rx="2">`;
      if(p){
        svgEl += `<title>P${p.pos_id} (${p.behavior_class})\n지속시간: ${p.pulse_duration_ms===null?'N/A':p.pulse_duration_ms.toFixed(2)+' ms'}\ncontact steps: ${p.n_contact_steps}\ndensity: ${(p.contact_density*100).toFixed(1)}%\npulse→peak: ${p.pulse_to_peak_ms===null?'N/A':p.pulse_to_peak_ms.toFixed(2)+' ms'}</title>`;
      }
      svgEl += `</rect>`;
      if(p){
        svgEl += `<text x="${x+cellW/2-1}" y="${y+cellH/2-3}" text-anchor="middle" fill="#fff" font-size="9" font-weight="600">${pid}</text>`;
        svgEl += `<text x="${x+cellW/2-1}" y="${y+cellH/2+9}" text-anchor="middle" fill="#fff" font-size="9">${lbl}</text>`;
      }
    }
  }
  svgEl += `<text x="${padL}" y="${H-6}" fill="#aaa" font-size="10">x →</text>`;
  svgEl += `<text x="2" y="${padT+10}" fill="#aaa" font-size="10">y↑</text>`;
  svgEl += `</svg>`;
  hmHost.innerHTML = svgEl;
  svgZoomPan(hmHost.querySelector('svg'));

  // Legend
  const legend = document.getElementById('cp-legend');
  let legHTML = '<div class="cp-legend-bar">';
  for(let k=0;k<20;k++){
    const v = dMin + (k/19)*dRange;
    legHTML += `<span style="background:${colorFor(v)}"></span>`;
  }
  legHTML += `</div><div class="cp-legend-labels"><span>${dMin.toFixed(1)} ms</span><span>${dMax.toFixed(1)} ms</span></div>`;
  legend.innerHTML = legHTML;

  // --- Histogram ---
  const hHost = document.getElementById('cp-hist');
  const nBins = 10;
  const bins = new Array(nBins).fill(0);
  const binEdges = [];
  for(let k=0;k<=nBins;k++){ binEdges.push(dMin + (k/nBins)*dRange); }
  durs.forEach(v => {
    let k = Math.floor((v - dMin) / dRange * nBins);
    if(k >= nBins) k = nBins-1;
    if(k < 0) k = 0;
    bins[k]++;
  });
  const maxCount = Math.max.apply(null, bins) || 1;
  const hW = 280, hH = 140, hpadL = 28, hpadB = 22, hpadT = 6;
  const innerW = hW - hpadL - 8;
  const innerH = hH - hpadB - hpadT;
  const bw = innerW / nBins;
  let hsv = `<svg width="${hW}" height="${hH}" class="cp-hist-svg">`;
  for(let k=0;k<nBins;k++){
    const bh = (bins[k]/maxCount)*innerH;
    const bx = hpadL + k*bw;
    const by = hpadT + (innerH - bh);
    const midVal = (binEdges[k]+binEdges[k+1])/2;
    hsv += `<rect x="${bx+1}" y="${by}" width="${bw-2}" height="${bh}" fill="${colorFor(midVal)}" stroke="#666" stroke-width="0.5"><title>${binEdges[k].toFixed(2)}–${binEdges[k+1].toFixed(2)} ms\nn=${bins[k]}</title></rect>`;
    if(bins[k]>0){
      hsv += `<text x="${bx+bw/2}" y="${by-2}" text-anchor="middle" fill="#ddd" font-size="9">${bins[k]}</text>`;
    }
  }
  // axes
  hsv += `<line x1="${hpadL}" y1="${hpadT+innerH}" x2="${hpadL+innerW}" y2="${hpadT+innerH}" stroke="#666" stroke-width="1"/>`;
  hsv += `<text x="${hpadL}" y="${hH-6}" fill="#aaa" font-size="10">${dMin.toFixed(1)}</text>`;
  hsv += `<text x="${hpadL+innerW}" y="${hH-6}" text-anchor="end" fill="#aaa" font-size="10">${dMax.toFixed(1)} ms</text>`;
  hsv += `<text x="${hpadL-4}" y="${hpadT+8}" text-anchor="end" fill="#aaa" font-size="10">${maxCount}</text>`;
  hsv += `<text x="${hpadL-4}" y="${hpadT+innerH}" text-anchor="end" fill="#aaa" font-size="10">0</text>`;
  hsv += `</svg>`;
  hHost.innerHTML = hsv;

  // Stats
  const stats = document.getElementById('cp-stats');
  const fmtMs = v => (v===null||v===undefined||!isFinite(v)) ? 'N/A' : v.toFixed(2)+' ms';
  stats.innerHTML = `
    <div><span>평균:</span><b>${fmtMs(summary.mean_duration_ms)}</b></div>
    <div><span>중앙값:</span><b>${fmtMs(summary.median_duration_ms)}</b></div>
    <div><span>표준편차:</span><b>${fmtMs(summary.std_duration_ms)}</b></div>
    <div><span>유효 위치:</span><b>${summary.n_valid ?? valid.length}</b></div>
  `;

  // Top-5 / Bottom-5
  const sorted = valid.slice().sort((a,b)=>b.pulse_duration_ms - a.pulse_duration_ms);
  const top5 = sorted.slice(0, 5);
  const bot5 = sorted.slice(-5).reverse();

  function rankHTML(list){
    if(list.length === 0) return '<div class="cp-empty">데이터 없음</div>';
    let h = '<table class="cp-rank-tbl"><thead><tr><th>#</th><th>Pos</th><th>지속(ms)</th><th>density</th><th>거동</th></tr></thead><tbody>';
    list.forEach((p, i) => {
      const bc = p.behavior_class || '—';
      h += `<tr><td>${i+1}</td><td>P${p.pos_id}</td><td>${p.pulse_duration_ms.toFixed(2)}</td><td>${(p.contact_density*100).toFixed(1)}%</td><td>${bc}</td></tr>`;
    });
    h += '</tbody></table>';
    return h;
  }
  document.getElementById('cp-top5').innerHTML = rankHTML(top5);
  document.getElementById('cp-bot5').innerHTML = rankHTML(bot5);
}

function _insightRenderTrajectory3D(data){
  const root = document.getElementById('trajectory3d-svg');
  if(!root) return;
  if(!data || !data.bundles || data.bundles.length === 0){
    root.innerHTML = '<div class="insight-empty">트래젝터리 데이터 없음</div>';
    return;
  }

  const bundles = data.bundles;
  const bbox = data.bbox_xy || [-40, -40, 40, 40];
  const zr   = data.z_range || [0, 1];
  const [x0, y0, x1, y1] = bbox;
  const [zMin, zMax] = zr;

  // Isometric projection: u = x + 0.5*y, v = z + 0.5*y
  // (tilt angle 30° — y contributes equally to horizontal and vertical)
  const proj = (x, y, z) => [x + 0.5 * y, z + 0.5 * y];

  // Compute u/v extents across floor corners + trajectory points so the
  // whole scene fits the viewBox.
  const uS = [], vS = [];
  const floorCorners = [
    [x0, y0, zMin], [x1, y0, zMin], [x1, y1, zMin], [x0, y1, zMin]
  ];
  for(const c of floorCorners){
    const [u, v] = proj(c[0], c[1], c[2]);
    uS.push(u); vS.push(v);
  }
  for(const b of bundles){
    for(const p of b.points){
      const [u, v] = proj(p[0], p[1], p[2]);
      uS.push(u); vS.push(v);
    }
  }
  const uMin = Math.min(...uS), uMax = Math.max(...uS);
  const vMin = Math.min(...vS), vMax = Math.max(...vS);

  const W = 600, H = 360, pad = 28;
  const sx = (W - 2*pad) / Math.max(uMax - uMin, 1e-9);
  const sy = (H - 2*pad) / Math.max(vMax - vMin, 1e-9);
  const s  = Math.min(sx, sy);
  // center
  const offU = pad + ((W - 2*pad) - (uMax - uMin) * s) / 2;
  const offV = pad + ((H - 2*pad) - (vMax - vMin) * s) / 2;
  const tx = (u) => offU + (u - uMin) * s;
  // SVG y grows downward; isometric v grows upward → flip
  const ty = (v) => H - offV - (v - vMin) * s;

  while(root.firstChild) root.removeChild(root.firstChild);
  const root_svg = svg('svg', {
    viewBox: '0 0 ' + W + ' ' + H,
    preserveAspectRatio: 'xMidYMid meet',
    width: '100%'
  });

  // Background
  root_svg.appendChild(svg('rect', {
    x: 0, y: 0, width: W, height: H, fill: '#0d1117', rx: 6
  }));

  // 5x5 floor wireframe at z = zMin
  const N = 5;
  const dxF = (x1 - x0) / N;
  const dyF = (y1 - y0) / N;
  const gridStroke = '#2a3447';
  // Lines parallel to x (constant y)
  for(let i = 0; i <= N; i++){
    const yv = y0 + dyF * i;
    const [uA, vA] = proj(x0, yv, zMin);
    const [uB, vB] = proj(x1, yv, zMin);
    root_svg.appendChild(svg('line', {
      x1: tx(uA), y1: ty(vA), x2: tx(uB), y2: ty(vB),
      stroke: gridStroke, 'stroke-width': 0.8, opacity: 0.8
    }));
  }
  // Lines parallel to y (constant x)
  for(let i = 0; i <= N; i++){
    const xv = x0 + dxF * i;
    const [uA, vA] = proj(xv, y0, zMin);
    const [uB, vB] = proj(xv, y1, zMin);
    root_svg.appendChild(svg('line', {
      x1: tx(uA), y1: ty(vA), x2: tx(uB), y2: ty(vB),
      stroke: gridStroke, 'stroke-width': 0.8, opacity: 0.8
    }));
  }

  // Polylines per trajectory
  for(const b of bundles){
    const color = BEHAVIOR_COLOR[b.behavior_class] || BEHAVIOR_COLOR.unknown;
    const pts = b.points.map(p => {
      const [u, v] = proj(p[0], p[1], p[2]);
      return tx(u).toFixed(2) + ',' + ty(v).toFixed(2);
    }).join(' ');
    const line = svg('polyline', {
      points: pts,
      fill: 'none',
      stroke: color,
      'stroke-width': 1.3,
      'stroke-linecap': 'round',
      'stroke-linejoin': 'round',
      opacity: 0.85
    });
    const title = svg('title', {});
    title.appendChild(document.createTextNode(
      'pos ' + b.pos_id + ' · ' + String(b.behavior_class).toUpperCase()
    ));
    line.appendChild(title);
    root_svg.appendChild(line);

    // start marker at first sampled point
    if(b.points.length){
      const [u0p, v0p] = proj(b.points[0][0], b.points[0][1], b.points[0][2]);
      root_svg.appendChild(svg('circle', {
        cx: tx(u0p), cy: ty(v0p), r: 1.8, fill: color, opacity: 0.95
      }));
    }
  }

  // Legend (top-right) — behavior classes present in bundles
  const present = {};
  for(const b of bundles) present[b.behavior_class] = (present[b.behavior_class] || 0) + 1;
  const order = ['bounce', 'rebound', 'slide', 'embed', 'unknown'];
  const items = order.filter(k => present[k]);
  let lx = W - 12, ly = 14;
  const lh = 14;
  for(let i = 0; i < items.length; i++){
    const k = items[i];
    const yy = ly + i * lh;
    root_svg.appendChild(svg('line', {
      x1: lx - 80, y1: yy, x2: lx - 60, y2: yy,
      stroke: BEHAVIOR_COLOR[k] || BEHAVIOR_COLOR.unknown,
      'stroke-width': 2
    }));
    const t = svg('text', {
      x: lx - 56, y: yy + 3,
      fill: '#c9d1d9', 'font-size': 10, 'text-anchor': 'start'
    });
    t.appendChild(document.createTextNode(k + ' (' + present[k] + ')'));
    root_svg.appendChild(t);
  }

  root.appendChild(root_svg);
  svgZoomPan(root_svg);
}
function _physRenderStressWaveVelocity(data){
  const host = document.getElementById('physics-stress-wave-velocity');
  if(!host) return;
  const d = (data && data.physics && data.physics.StressWaveVelocity) || null;
  const body = host.querySelector('.panel-body') || host;
  body.innerHTML = '';

  const placeholder = (d && d._placeholder) || '응력파 전파 속도 산출에 필요한 t_first_contact / t_peak_g / 위치-부품 거리 정보가 부족하여 현재 패널을 표시할 수 없습니다. (50자 이상 placeholder)';
  if(!d || !d.per_part || d.per_part.length === 0){
    const empty = document.createElement('div');
    empty.className = 'phys-empty';
    empty.textContent = placeholder;
    body.appendChild(empty);
    return;
  }

  // Top-12 cap (payload caps at 15; we display 12).
  const rows = d.per_part.slice(0, 12);
  const v_theory = (typeof d.v_theory_impactor === 'number' && isFinite(d.v_theory_impactor)) ? d.v_theory_impactor : null;

  // Caption
  const cap = document.createElement('div');
  cap.className = 'phys-caption';
  cap.textContent = '거리/Δt 로 산출한 외형 wave 속도. 이론값 위면 다중 모드 동시 도착, 아래면 부품간 결합 약함.';
  body.appendChild(cap);

  // Summary chips
  if(d.summary && typeof d.summary === 'object'){
    const s = d.summary;
    const chips = document.createElement('div');
    chips.className = 'phys-chips';
    const mk = (label, value, unit) => {
      const c = document.createElement('span');
      c.className = 'phys-chip';
      const v = (value == null) ? '—' : (typeof _u === 'function' ? _u(value, unit) : (value + ' ' + unit));
      c.innerHTML = '<b>' + label + '</b> ' + v;
      return c;
    };
    chips.appendChild(mk('min', s.min_v_app, 'm/s'));
    chips.appendChild(mk('median', s.median_v_app_all, 'm/s'));
    chips.appendChild(mk('max', s.max_v_app, 'm/s'));
    chips.appendChild(mk('표본수', s.n_total, '개'));
    if(v_theory != null) chips.appendChild(mk('이론 √(E/ρ)', v_theory, 'm/s'));
    body.appendChild(chips);
  }

  // Chart layout
  const W = 720, rowH = 26, padTop = 24, padBot = 36, padL = 170, padR = 70;
  const H = padTop + padBot + rowH * rows.length;
  const chartW = W - padL - padR;

  // Domain: max of bar max (q75) and v_theory, with small headroom
  let xMax = 0;
  for(const r of rows){
    const hi = (typeof r.q75_v_app === 'number') ? r.q75_v_app : (r.mean_v_app || 0);
    if(hi > xMax) xMax = hi;
  }
  if(v_theory != null && v_theory > xMax) xMax = v_theory;
  if(!(xMax > 0)) xMax = 1.0;
  xMax *= 1.10;

  const xScale = v => padL + (v / xMax) * chartW;

  const NS = 'http://www.w3.org/2000/svg';
  const root = document.createElementNS(NS, 'svg');
  root.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
  root.setAttribute('width', '100%');
  root.setAttribute('class', 'phys-swv-chart');

  // X axis ticks (4)
  for(let k=0; k<=4; k++){
    const v = (xMax / 4) * k;
    const x = xScale(v);
    const tline = document.createElementNS(NS, 'line');
    tline.setAttribute('x1', x); tline.setAttribute('x2', x);
    tline.setAttribute('y1', padTop - 4); tline.setAttribute('y2', H - padBot);
    tline.setAttribute('stroke', '#444'); tline.setAttribute('stroke-width', '0.5');
    tline.setAttribute('stroke-dasharray', '2,3');
    root.appendChild(tline);
    const tl = document.createElementNS(NS, 'text');
    tl.setAttribute('x', x); tl.setAttribute('y', H - padBot + 14);
    tl.setAttribute('text-anchor', 'middle');
    tl.setAttribute('class', 'phys-axis-tick');
    tl.textContent = (typeof fmt === 'function' ? fmt(v, 0) : v.toFixed(0));
    root.appendChild(tl);
  }
  // X axis label
  const xl = document.createElementNS(NS, 'text');
  xl.setAttribute('x', padL + chartW/2); xl.setAttribute('y', H - 6);
  xl.setAttribute('text-anchor', 'middle');
  xl.setAttribute('class', 'phys-axis-label');
  xl.textContent = '외형 wave 속도 v_app (m/s)';
  root.appendChild(xl);

  // Bars + whiskers
  rows.forEach((r, i) => {
    const y = padTop + i * rowH + rowH * 0.5;
    const mean = (typeof r.mean_v_app === 'number') ? r.mean_v_app : 0;
    const lo = (typeof r.q25_v_app === 'number') ? r.q25_v_app : mean;
    const hi = (typeof r.q75_v_app === 'number') ? r.q75_v_app : mean;
    const xMean = xScale(mean);
    const xLo = xScale(lo);
    const xHi = xScale(hi);
    const barH = rowH * 0.55;

    // Part label
    const lab = document.createElementNS(NS, 'text');
    lab.setAttribute('x', padL - 8); lab.setAttribute('y', y + 4);
    lab.setAttribute('text-anchor', 'end');
    lab.setAttribute('class', 'phys-row-label');
    const lbl = r.part_name || ('PART_' + r.part_id);
    lab.textContent = lbl.length > 22 ? (lbl.slice(0, 20) + '…') : lbl;
    const labTitle = document.createElementNS(NS, 'title');
    labTitle.textContent = (r.part_name || '') + ' (part_id ' + r.part_id + ') — n=' + (r.n_samples||0);
    lab.appendChild(labTitle);
    root.appendChild(lab);

    // Bar (mean)
    const bar = document.createElementNS(NS, 'rect');
    bar.setAttribute('x', padL);
    bar.setAttribute('y', y - barH/2);
    bar.setAttribute('width', Math.max(0, xMean - padL));
    bar.setAttribute('height', barH);
    const color = (typeof gColor === 'function') ? gColor(mean / (v_theory || xMax)) : '#4ea3ff';
    bar.setAttribute('fill', color);
    bar.setAttribute('opacity', '0.85');
    const bt = document.createElementNS(NS, 'title');
    const m_ms = (typeof r.mean_delta_t_ms === 'number') ? r.mean_delta_t_ms : null;
    bt.textContent = (r.part_name || ('PART_' + r.part_id)) +
                     '\nmean v_app: ' + (typeof fmt === 'function' ? fmt(mean,0) : mean.toFixed(0)) + ' m/s' +
                     '\nIQR: [' + (typeof fmt === 'function' ? fmt(lo,0) : lo.toFixed(0)) + ', ' +
                     (typeof fmt === 'function' ? fmt(hi,0) : hi.toFixed(0)) + '] m/s' +
                     '\nmedian: ' + (r.median_v_app != null ? r.median_v_app : '—') + ' m/s' +
                     (m_ms != null ? '\nmean Δt: ' + m_ms + ' ms' : '') +
                     '\nn=' + (r.n_samples || 0);
    bar.appendChild(bt);
    root.appendChild(bar);

    // IQR whisker (Q25..Q75)
    const wline = document.createElementNS(NS, 'line');
    wline.setAttribute('x1', xLo); wline.setAttribute('x2', xHi);
    wline.setAttribute('y1', y); wline.setAttribute('y2', y);
    wline.setAttribute('stroke', '#ddd'); wline.setAttribute('stroke-width', '1.5');
    root.appendChild(wline);
    // whisker caps
    [[xLo, '#ddd'], [xHi, '#ddd']].forEach(([xv, col]) => {
      const c = document.createElementNS(NS, 'line');
      c.setAttribute('x1', xv); c.setAttribute('x2', xv);
      c.setAttribute('y1', y - 5); c.setAttribute('y2', y + 5);
      c.setAttribute('stroke', col); c.setAttribute('stroke-width', '1.5');
      root.appendChild(c);
    });

    // Value label at bar end
    const vlab = document.createElementNS(NS, 'text');
    vlab.setAttribute('x', xMean + 4); vlab.setAttribute('y', y + 4);
    vlab.setAttribute('class', 'phys-row-value');
    vlab.textContent = (typeof fmt === 'function' ? fmt(mean,0) : mean.toFixed(0));
    root.appendChild(vlab);
  });

  // Theory vertical line
  if(v_theory != null){
    const xt = xScale(v_theory);
    const ln = document.createElementNS(NS, 'line');
    ln.setAttribute('x1', xt); ln.setAttribute('x2', xt);
    ln.setAttribute('y1', padTop - 6); ln.setAttribute('y2', H - padBot);
    ln.setAttribute('stroke', '#ff6b6b');
    ln.setAttribute('stroke-width', '1.6');
    ln.setAttribute('stroke-dasharray', '6,4');
    root.appendChild(ln);
    const lt = document.createElementNS(NS, 'text');
    lt.setAttribute('x', xt + 4); lt.setAttribute('y', padTop + 6);
    lt.setAttribute('class', 'phys-theory-label');
    lt.textContent = '이론값 √(E/ρ) = ' + (typeof fmt === 'function' ? fmt(v_theory,0) : v_theory.toFixed(0)) + ' m/s';
    root.appendChild(lt);
  }

  body.appendChild(root);

  if(typeof svgZoomPan === 'function'){
    try { svgZoomPan(root); } catch(e){}
  }
}

function _physRenderRestitutionMap(data) {
  const root = document.getElementById('phys-restitution-map');
  if (!root) return;
  const payload = (data && data.physics && data.physics.RestitutionMap) || null;

  const kpiMean = root.querySelector('[data-role="kpi-mean"]');
  const kpiMax = root.querySelector('[data-role="kpi-max"]');
  const kpiMin = root.querySelector('[data-role="kpi-min"]');
  const kpiBuckets = root.querySelector('[data-role="kpi-buckets"]');
  const heatHost = root.querySelector('[data-role="heatmap"]');
  const histHost = root.querySelector('[data-role="histogram"]');
  const statusHost = root.querySelector('[data-role="status"]');

  const PLACEHOLDER = '데이터가 비어있거나 유효한 반발 계수 e 값을 계산할 수 없습니다 (KE_before/KE_after 누락).';

  if (!payload || !payload.per_position || payload.per_position.length === 0) {
    if (statusHost) statusHost.textContent = PLACEHOLDER;
    if (heatHost) heatHost.innerHTML = '';
    if (histHost) histHost.innerHTML = '';
    return;
  }

  const rows = payload.per_position;
  const summary = payload.summary || {};
  const hist = payload.histogram || [];
  const histRange = payload.hist_range || [0, 1.2];
  const grid = payload.grid || {nx: 5, ny: 5};
  const nx = Math.max(1, grid.nx || 5);
  const ny = Math.max(1, grid.ny || 5);

  // ── KPI ──────────────────────────────────────────────────────────────
  const fmtE = v => (v == null || !isFinite(v)) ? '—' : Number(v).toFixed(3);
  if (kpiMean) kpiMean.textContent = fmtE(summary.mean_e);
  if (kpiMax) {
    kpiMax.textContent = (summary.max_e_pos_id != null)
      ? `P${summary.max_e_pos_id} (e=${fmtE(summary.max_e)})`
      : '—';
  }
  if (kpiMin) {
    kpiMin.textContent = (summary.min_e_pos_id != null)
      ? `P${summary.min_e_pos_id} (e=${fmtE(summary.min_e)})`
      : '—';
  }
  if (kpiBuckets) {
    const nHigh = summary.n_e_high || 0;
    const nLow = summary.n_e_low || 0;
    const nValid = summary.n_valid || 0;
    kpiBuckets.textContent = `탄성≥0.9: ${nHigh} · 비탄성≤0.3: ${nLow} · 유효 ${nValid}/${summary.n_total || rows.length}`;
  }

  // ── Heatmap (5×5) ────────────────────────────────────────────────────
  // Honour device aspect ratio if available
  const geom = payload.device_geometry || {};
  let aspect = 1.0;
  if (geom && isFinite(geom.width) && isFinite(geom.height) && geom.height > 0) {
    aspect = Math.max(0.4, Math.min(2.5, geom.width / geom.height));
  }
  const heatW = 360;
  const heatH = Math.round(heatW / aspect);
  const pad = {l: 36, r: 16, t: 16, b: 36};
  const innerW = heatW - pad.l - pad.r;
  const innerH = heatH - pad.t - pad.b;
  const cellW = innerW / nx;
  const cellH = innerH / ny;

  // Map pos_id → grid (i, j). pos_id is 1..25 with row-major layout.
  // Falls back to the row index when pos_id is non-numeric (e.g. "F5_DOE_001").
  function posToCell(pos_id, idx) {
    let k = idx;
    if (pos_id != null) {
      const n = Number(pos_id);
      if (isFinite(n)) k = n - 1;
    }
    if (!isFinite(k) || k < 0 || k >= nx * ny) return null;
    return {i: k % nx, j: Math.floor(k / nx)};
  }

  // Color ramp: red (low e) → yellow → green (high e)
  function eColor(e) {
    if (e == null || !isFinite(e)) return '#2a2f3a';
    const t = Math.max(0, Math.min(1, e / 1.0)); // clamp display ramp at e=1
    // Interpolate red → yellow → green in HSL
    const hue = 0 + 120 * t; // 0=red, 60=yellow, 120=green
    return `hsl(${hue.toFixed(1)}, 70%, 45%)`;
  }

  const behaviorChip = (b) => {
    if (!b) return '';
    const col = (typeof BEHAVIOR_COLOR === 'object' && BEHAVIOR_COLOR[b]) || '#888';
    return `<span class="rmap-chip" style="background:${col};">${b}</span>`;
  };

  let svgStr = `<svg viewBox="0 0 ${heatW} ${heatH}" width="100%" height="${heatH}" preserveAspectRatio="xMidYMid meet" class="rmap-heat-svg">`;
  // axes labels
  svgStr += `<text x="${heatW/2}" y="${heatH - 8}" text-anchor="middle" fill="#a8b0bd" font-size="11">X (격자)</text>`;
  svgStr += `<text x="12" y="${pad.t + innerH/2}" text-anchor="middle" fill="#a8b0bd" font-size="11" transform="rotate(-90 12 ${pad.t + innerH/2})">Y (격자)</text>`;

  rows.forEach((row, idx) => {
    const cell = posToCell(row.pos_id, idx);
    if (!cell) return;
    const x = pad.l + cell.i * cellW;
    const y = pad.t + cell.j * cellH;
    const eVal = row.e;
    const fill = eColor(eVal);
    svgStr += `<rect x="${x}" y="${y}" width="${cellW - 1.5}" height="${cellH - 1.5}" rx="3" ry="3" fill="${fill}" stroke="#0e1117" stroke-width="0.8">`;
    svgStr += `<title>P${row.pos_id} · e=${fmtE(eVal)} · KE_before=${row.ke_before ?? '—'} · KE_after=${row.ke_after ?? '—'} · ${row.behavior_class || ''}</title>`;
    svgStr += `</rect>`;
    // Value label
    const label = (eVal == null) ? '—' : Number(eVal).toFixed(2);
    svgStr += `<text x="${x + cellW/2}" y="${y + cellH/2 - 2}" text-anchor="middle" dominant-baseline="middle" fill="#0e1117" font-size="${Math.min(13, cellW*0.28).toFixed(1)}" font-weight="600">${label}</text>`;
    // Behavior chip text below value (small)
    if (row.behavior_class) {
      svgStr += `<text x="${x + cellW/2}" y="${y + cellH/2 + 12}" text-anchor="middle" fill="#0e1117" font-size="${Math.min(9, cellW*0.18).toFixed(1)}" opacity="0.75">${row.behavior_class}</text>`;
    }
    svgStr += `<text x="${x + 4}" y="${y + 10}" fill="#0e1117" font-size="8" opacity="0.7">P${row.pos_id}</text>`;
  });

  svgStr += `</svg>`;
  if (heatHost) heatHost.innerHTML = svgStr;

  // ── Histogram ────────────────────────────────────────────────────────
  if (histHost) {
    const hW = 320, hH = heatH;
    const hp = {l: 36, r: 12, t: 16, b: 36};
    const iW = hW - hp.l - hp.r;
    const iH = hH - hp.t - hp.b;
    const maxCount = hist.reduce((m, b) => Math.max(m, b.count || 0), 0) || 1;
    const barW = iW / Math.max(1, hist.length);
    let h = `<svg viewBox="0 0 ${hW} ${hH}" width="100%" height="${hH}" preserveAspectRatio="xMidYMid meet" class="rmap-hist-svg">`;
    // axes
    h += `<line x1="${hp.l}" y1="${hp.t + iH}" x2="${hp.l + iW}" y2="${hp.t + iH}" stroke="#3a4150" stroke-width="1"/>`;
    h += `<line x1="${hp.l}" y1="${hp.t}" x2="${hp.l}" y2="${hp.t + iH}" stroke="#3a4150" stroke-width="1"/>`;
    // bars
    hist.forEach((b, i) => {
      const x = hp.l + i * barW;
      const hRatio = (b.count || 0) / maxCount;
      const barH = iH * hRatio;
      const y = hp.t + iH - barH;
      const mid = ((b.lo || 0) + (b.hi || 0)) / 2;
      const fill = eColor(mid);
      h += `<rect x="${x + 1}" y="${y}" width="${barW - 2}" height="${barH}" fill="${fill}" opacity="0.85">`;
      h += `<title>e ∈ [${b.lo}, ${b.hi}) · n=${b.count}</title></rect>`;
      if (b.count > 0) {
        h += `<text x="${x + barW/2}" y="${y - 3}" text-anchor="middle" fill="#cfd5e1" font-size="9">${b.count}</text>`;
      }
    });
    // x-axis ticks (0, 0.3, 0.6, 0.9, 1.2)
    const ticks = [0, 0.3, 0.6, 0.9, 1.2];
    const xMax = histRange[1] || 1.2;
    ticks.forEach(t => {
      const tx = hp.l + (t / xMax) * iW;
      h += `<line x1="${tx}" y1="${hp.t + iH}" x2="${tx}" y2="${hp.t + iH + 4}" stroke="#a8b0bd"/>`;
      h += `<text x="${tx}" y="${hp.t + iH + 16}" text-anchor="middle" fill="#a8b0bd" font-size="10">${t.toFixed(1)}</text>`;
    });
    // y-axis label
    h += `<text x="${hp.l - 6}" y="${hp.t + 8}" text-anchor="end" fill="#a8b0bd" font-size="10">${maxCount}</text>`;
    h += `<text x="${hp.l - 6}" y="${hp.t + iH}" text-anchor="end" fill="#a8b0bd" font-size="10">0</text>`;
    // axis title
    h += `<text x="${hp.l + iW/2}" y="${hH - 6}" text-anchor="middle" fill="#cfd5e1" font-size="11">반발 계수 e</text>`;
    h += `<text x="12" y="${hp.t + iH/2}" text-anchor="middle" fill="#cfd5e1" font-size="11" transform="rotate(-90 12 ${hp.t + iH/2})">위치 수</text>`;
    // median line
    if (summary.median_e != null && isFinite(summary.median_e)) {
      const mx = hp.l + (summary.median_e / xMax) * iW;
      h += `<line x1="${mx}" y1="${hp.t}" x2="${mx}" y2="${hp.t + iH}" stroke="#f0b400" stroke-width="1.2" stroke-dasharray="3,3"/>`;
      h += `<text x="${mx + 3}" y="${hp.t + 10}" fill="#f0b400" font-size="10">median ${Number(summary.median_e).toFixed(2)}</text>`;
    }
    h += `</svg>`;
    histHost.innerHTML = h;
  }

  if (statusHost) {
    statusHost.textContent = `${summary.n_valid || 0}개 위치에서 e 값 계산 완료 (전체 ${summary.n_total || rows.length}개).`;
  }
}

function _physRenderRecoveryDamping(data) {
  const pay = (data && data.RecoveryDamping) || null;
  const host = document.getElementById('phys-recovery-damping-body');
  if (!host) return;
  host.innerHTML = '';

  if (!pay || !pay.per_part || !pay.per_part.length) {
    const msg = el('div', { class: 'phys-rd-empty' },
      '댐핑/회복 시간 데이터를 계산할 수 없습니다 — PartMotion 가속도 시계열이 ' +
      '부족하거나 모든 부품에서 post-peak 신호가 0이기 때문입니다. ' +
      'unified_analyzer의 motion CSV 출력을 확인해 주세요.');
    host.appendChild(msg);
    return;
  }

  const rows = pay.per_part.filter(r => r.has_data);
  if (!rows.length) {
    const msg = el('div', { class: 'phys-rd-empty' },
      '활성 부품 motion 데이터가 없어 댐핑 비를 추정할 수 없습니다 — ' +
      '모든 부품의 post-peak 가속도가 너무 짧거나 0 입니다.');
    host.appendChild(msg);
    return;
  }

  // --- header summary ------------------------------------------------------
  const summ = pay.summary || {};
  const head = el('div', { class: 'phys-rd-head' });
  head.appendChild(el('div', { class: 'phys-rd-kpi' }, [
    el('div', { class: 'k' }, '중앙값 회복 시간'),
    el('div', { class: 'v' },
      (summ.median_recovery_ms != null ? fmt(summ.median_recovery_ms, 2) + ' ms' : '-'))
  ]));
  head.appendChild(el('div', { class: 'phys-rd-kpi' }, [
    el('div', { class: 'k' }, '중앙값 ζ'),
    el('div', { class: 'v' },
      (summ.median_damping_pct != null ? fmt(summ.median_damping_pct, 1) + ' %' : '-'))
  ]));
  head.appendChild(el('div', { class: 'phys-rd-kpi' }, [
    el('div', { class: 'k' }, '최저 댐핑 (공진 위험)'),
    el('div', { class: 'v vbad' }, summ.top_underdamped_part_name || '-')
  ]));
  head.appendChild(el('div', { class: 'phys-rd-kpi' }, [
    el('div', { class: 'k' }, '최고 댐핑'),
    el('div', { class: 'v vgood' }, summ.top_overdamped_part_name || '-')
  ]));
  head.appendChild(el('div', { class: 'phys-rd-kpi' }, [
    el('div', { class: 'k' }, '분석 위치'),
    el('div', { class: 'v' }, 'pos #' + (pay.pos_id_used || '-'))
  ]));
  host.appendChild(head);

  // --- two-column bar charts ----------------------------------------------
  // top 12 by damping (already sorted desc); we'll keep that order on the right
  // chart and re-sort by recovery time desc for the left chart.
  const top = rows.slice(0, 12);
  const byRecovery = top.slice().sort((a, b) => (b.recovery_time_ms || 0) - (a.recovery_time_ms || 0));
  const byDamping = top.slice().sort((a, b) => (b.damping_ratio_estimated || 0) - (a.damping_ratio_estimated || 0));

  // shared color: low damping = orange, high damping = green
  // We compute ζ thresholds *from the data* so panels with very small or
  // very large ζ adapt instead of using a magic 0.05 cut-off.
  const zs = top.map(r => r.damping_ratio_estimated || 0).filter(v => v > 0);
  let zLo = 0, zHi = 1;
  if (zs.length) {
    const s = zs.slice().sort((a, b) => a - b);
    zLo = s[Math.floor(s.length * 0.25)] || 0;
    zHi = s[Math.floor(s.length * 0.75)] || 1;
    if (zHi <= zLo) zHi = zLo + 1e-6;
  }
  function _zColor(z) {
    if (z == null) return '#5a6470';
    const t = Math.max(0, Math.min(1, (z - zLo) / (zHi - zLo)));
    // orange (255,140,0) -> green (60,200,90)
    const r = Math.round(255 + (60 - 255) * t);
    const g = Math.round(140 + (200 - 140) * t);
    const b = Math.round(0 + (90 - 0) * t);
    return 'rgb(' + r + ',' + g + ',' + b + ')';
  }

  function _drawBars(parent, rowsIn, valueKey, unitLabel, headerText) {
    const W = 420, H = 28 * rowsIn.length + 48, PADL = 150, PADR = 56, PADT = 32, PADB = 8;
    const innerW = W - PADL - PADR;
    const root = svg('svg', {
      viewBox: '0 0 ' + W + ' ' + H, width: '100%',
      preserveAspectRatio: 'xMidYMid meet', class: 'phys-rd-bars'
    });
    // title
    const tnode = svg('text', {
      x: 12, y: 18, fill: '#c9d1d9', 'font-size': 12, 'font-weight': 600
    });
    tnode.appendChild(document.createTextNode(headerText));
    root.appendChild(tnode);

    const vmax = Math.max.apply(null, rowsIn.map(r => r[valueKey] || 0));
    const denom = vmax > 0 ? vmax : 1;
    const bh = 20;
    rowsIn.forEach((r, i) => {
      const y = PADT + i * 28;
      const v = r[valueKey] || 0;
      const w = Math.max(0, (v / denom) * innerW);
      const z = r.damping_ratio_estimated;
      const color = _zColor(z);
      // part name label (left)
      const nm = svg('text', {
        x: PADL - 6, y: y + bh * 0.7, fill: '#c9d1d9',
        'font-size': 10, 'text-anchor': 'end'
      });
      nm.appendChild(document.createTextNode(r.part_name.slice(0, 22)));
      root.appendChild(nm);
      // bar background
      root.appendChild(svg('rect', {
        x: PADL, y: y, width: innerW, height: bh, fill: '#1c2128',
        stroke: '#2a3038', 'stroke-width': 0.5
      }));
      // bar
      root.appendChild(svg('rect', {
        x: PADL, y: y, width: w, height: bh, fill: color, opacity: 0.92
      }));
      // value label (right)
      const vtxt = svg('text', {
        x: PADL + w + 4, y: y + bh * 0.7, fill: '#c9d1d9', 'font-size': 10
      });
      const sval = (v == null || !isFinite(v))
        ? '-'
        : (valueKey === 'damping_ratio_estimated' ? (v * 100).toFixed(2) + ' %' : fmt(v, 2) + ' ' + unitLabel);
      vtxt.appendChild(document.createTextNode(sval));
      root.appendChild(vtxt);
    });
    parent.appendChild(root);
  }

  const grid = el('div', { class: 'phys-rd-grid' });
  const colL = el('div', { class: 'phys-rd-col' });
  const colR = el('div', { class: 'phys-rd-col' });
  _drawBars(colL, byRecovery, 'recovery_time_ms', 'ms', '5% 회복 시간 (ms)');
  _drawBars(colR, byDamping, 'damping_ratio_estimated', '%', '추정 댐핑 비 ζ (%)');
  grid.appendChild(colL);
  grid.appendChild(colR);
  host.appendChild(grid);

  // caption
  const cap = el('div', { class: 'phys-rd-caption' },
    '5% 감쇠 시간 = 진동 격리 여부. ζ < 0.05 = 저댐핑 (공진 위험). ' +
    'ω_n은 deep_analytics FFT 또는 zero-crossing 추정; ' +
    'log-decrement으로 ζ를 산출했습니다.');
  host.appendChild(cap);
}
function _physRenderWorstCombinations(data) {
  const root = document.getElementById('phys-worst-combinations');
  if (!root) return;
  const body = root.querySelector('.panel-body') || root;
  body.innerHTML = '';

  const placeholderLong = '통합 위험도 점수를 계산할 충분한 데이터가 없습니다 (PairResult 또는 P95 정규화 기준값이 비어있거나 NaN).';

  if (!data || data.ok === false || !Array.isArray(data.top_25) || data.top_25.length === 0) {
    const empty = el('div', { class: 'wc-empty' }, [
      (data && data.reason) ? data.reason : placeholderLong
    ]);
    body.appendChild(empty);
    return;
  }

  const u = (data.unit_labels) || {};
  const uG = (typeof _u === 'function') ? _u('accel_g', u) : (u.accel_g || 'g');
  const uS = (typeof _u === 'function') ? _u('stress', u) : (u.stress || 'Pa');
  const uD = (typeof _u === 'function') ? _u('disp', u) : (u.disp || 'm');

  const dist = data.distribution || {};
  const ms = data.max_summary || null;
  const p95n = data.p95_norm || {};

  // ---- KPI strip ----
  const kpiStrip = el('div', { class: 'wc-kpi-strip' });
  const _num = (v, d) => (v === null || v === undefined || !isFinite(v)) ? '—' : (typeof fmt === 'function' ? fmt(v, d) : Number(v).toFixed(d));

  kpiStrip.appendChild(el('div', { class: 'wc-kpi wc-kpi-critical' }, [
    el('div', { class: 'wc-kpi-label' }, ['임계 초과 조합 (risk ≥ 1.0)']),
    el('div', { class: 'wc-kpi-value' }, [String(dist.n_above_risk_1 || 0)]),
    el('div', { class: 'wc-kpi-sub' }, ['전체 ' + (data.n_total || 0) + '개 중'])
  ]));

  kpiStrip.appendChild(el('div', { class: 'wc-kpi' }, [
    el('div', { class: 'wc-kpi-label' }, ['최대 위험도']),
    el('div', { class: 'wc-kpi-value' }, [_num(dist.max_risk, 3)]),
    el('div', { class: 'wc-kpi-sub' }, [
      ms ? ('Pos #' + ms.pos_id + ' · ' + (ms.part_name || ('Part ' + ms.part_id))) : '데이터 없음'
    ])
  ]));

  kpiStrip.appendChild(el('div', { class: 'wc-kpi' }, [
    el('div', { class: 'wc-kpi-label' }, ['P95 위험도 임계값']),
    el('div', { class: 'wc-kpi-value' }, [_num(dist.p95_risk, 3)]),
    el('div', { class: 'wc-kpi-sub' }, ['상위 5% 진입선'])
  ]));

  kpiStrip.appendChild(el('div', { class: 'wc-kpi' }, [
    el('div', { class: 'wc-kpi-label' }, ['P95 정규화 기준']),
    el('div', { class: 'wc-kpi-value wc-kpi-value-sm' }, [
      'g=' + _num(p95n.peak_g, 2) + ' · σ=' + _num(p95n.peak_stress, 3) + ' · d=' + _num(p95n.peak_disp, 4)
    ]),
    el('div', { class: 'wc-kpi-sub' }, ['전 625행 P95 (' + uG + ', ' + uS + ', ' + uD + ')'])
  ]));

  body.appendChild(kpiStrip);

  // ---- repeat-position chips ----
  const chips = data.top_3_positions_by_count || [];
  if (chips.length > 0) {
    const chipRow = el('div', { class: 'wc-chip-row' }, [
      el('span', { class: 'wc-chip-label' }, ['반복 출현 위치 (TOP25 내):'])
    ]);
    chips.forEach(c => {
      const txt = 'Pos #' + c.pos_id + ' (' + c.face + ') × ' + c.n_in_top25;
      chipRow.appendChild(el('span', { class: 'wc-chip' }, [txt]));
    });
    body.appendChild(chipRow);
  }

  // ---- sortable table ----
  const cols = [
    { key: 'rank',        label: '#',           num: true,  fmt: r => String(r.rank) },
    { key: 'face',        label: 'Face',        num: false, fmt: r => r.face || '—' },
    { key: 'pos_id',      label: 'Pos',         num: true,  fmt: r => '#' + r.pos_id },
    { key: 'xy',          label: '(x, y)',      num: false, fmt: r => (r.x === null || r.y === null) ? '—' : '(' + _num(r.x, 3) + ', ' + _num(r.y, 3) + ')',
                          sortVal: r => (r.x === null ? 0 : r.x) },
    { key: 'part_name',   label: 'Part',        num: false, fmt: r => r.part_name || ('Part ' + r.part_id) },
    { key: 'peak_g',      label: 'peak_g ('+uG+')',     num: true,  fmt: r => _num(r.peak_g, 1) },
    { key: 'peak_stress', label: 'peak_stress ('+uS+')',num: true,  fmt: r => _num(r.peak_stress, 3) },
    { key: 'peak_disp',   label: 'peak_disp ('+uD+')',  num: true,  fmt: r => _num(r.peak_disp, 4) },
    { key: 'risk',        label: 'Risk',        num: true,  fmt: r => _num(r.risk, 3), risk: true },
  ];

  const tableWrap = el('div', { class: 'wc-table-wrap' });
  const table = el('table', { class: 'wc-table' });
  const thead = el('thead');
  const headRow = el('tr');
  let sortState = { key: 'rank', dir: 'asc' };
  let rowsData = data.top_25.slice();

  cols.forEach(c => {
    const th = el('th', {
      class: 'wc-th' + (c.num ? ' wc-th-num' : ''),
      'data-key': c.key,
    }, [c.label, el('span', { class: 'wc-sort-ind' }, [''])]);
    th.addEventListener('click', () => {
      if (sortState.key === c.key) {
        sortState.dir = (sortState.dir === 'asc') ? 'desc' : 'asc';
      } else {
        sortState.key = c.key;
        sortState.dir = c.num ? 'desc' : 'asc';
      }
      renderRows();
    });
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);
  table.appendChild(thead);
  const tbody = el('tbody');
  table.appendChild(tbody);
  tableWrap.appendChild(table);
  body.appendChild(tableWrap);

  function riskClass(v) {
    if (v === null || v === undefined || !isFinite(v)) return 'wc-risk-na';
    if (v > 0.9) return 'wc-risk-red';
    if (v > 0.7) return 'wc-risk-orange';
    return 'wc-risk-gray';
  }

  function renderRows() {
    const col = cols.find(c => c.key === sortState.key) || cols[0];
    const getVal = col.sortVal || (r => r[col.key]);
    const dir = sortState.dir === 'asc' ? 1 : -1;
    rowsData.sort((a, b) => {
      const va = getVal(a), vb = getVal(b);
      if (va === null || va === undefined) return 1;
      if (vb === null || vb === undefined) return -1;
      if (typeof va === 'number' && typeof vb === 'number') return (va - vb) * dir;
      return String(va).localeCompare(String(vb)) * dir;
    });

    tbody.innerHTML = '';
    rowsData.forEach(r => {
      const tr = el('tr', { class: 'wc-row' });
      cols.forEach(c => {
        const td = el('td', { class: 'wc-td' + (c.num ? ' wc-td-num' : '') }, [c.fmt(r)]);
        if (c.risk) {
          td.classList.add(riskClass(r.risk));
        }
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });

    // update sort indicators
    headRow.querySelectorAll('.wc-th').forEach(th => {
      const ind = th.querySelector('.wc-sort-ind');
      if (!ind) return;
      if (th.getAttribute('data-key') === sortState.key) {
        ind.textContent = sortState.dir === 'asc' ? ' ▲' : ' ▼';
      } else {
        ind.textContent = '';
      }
    });
  }
  renderRows();

  // caption
  body.appendChild(el('div', { class: 'wc-caption' }, [
    '통합 위험도 점수 (peak_g 40% + stress 40% + disp 20%, P95 정규화). 단일 ranking 으로 최우선 위험 식별. 색상: 빨강 >0.9, 주황 >0.7, 회색 그 외.'
  ]));
}

// === PHYSICS_JS_FUNCTIONS_INSERT_HERE ===
// Section-08 _physRenderXxx render functions are inserted ABOVE this line.

const PHYSICS_STATE = { active_panel: null };

function initPhysics() {
  const data = (DATA && DATA.physics) || null;
  const sec = document.getElementById('s8');
  const navLink = document.getElementById('navS8');
  if (!data || !sec) {
    if (sec) sec.style.display = 'none';
    if (navLink) navLink.style.display = 'none';
    return;
  }
  const populated = Object.keys(data).some(k => {
    const v = data[k];
    return v && (typeof v !== 'object' || Object.keys(v).length > 0 || (Array.isArray(v) && v.length > 0));
  });
  if (!populated) {
    sec.style.display = 'none';
    if (navLink) navLink.style.display = 'none';
    return;
  }
  _physRenderStressWaveVelocity(DATA);
  _physRenderRestitutionMap(DATA);
  _physRenderRecoveryDamping(DATA);
  _physRenderWorstCombinations((typeof DATA !== 'undefined' && DATA.physics) ? DATA.physics.worst_combinations : null);
  // === PHYSICS_BOOT_CALLS_INSERT_HERE ===
  // Workflow-added _physRenderXxx(data) calls are inserted ABOVE this line.
}

// === INSIGHT_JS_FUNCTIONS_INSERT_HERE ===
// Section-07 _insightRenderXxx render functions are inserted ABOVE this line.

// --- Intra-section sub-tabs (Sections 05/06/07) ---------------------------
function initSubTabs(sectionId, groups) {
  // groups = [{tab_id, label, panel_ids: [string]}]
  const sec = document.getElementById(sectionId);
  if (!sec) return;
  const bar = document.createElement('div');
  bar.className = 'subtab-bar';
  groups.forEach((g, idx) => {
    const btn = document.createElement('button');
    btn.textContent = g.label;
    if (idx === 0) btn.classList.add('active');
    btn.addEventListener('click', () => {
      bar.querySelectorAll('button').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      groups.forEach(gg => {
        gg.panel_ids.forEach(pid => {
          const el = document.getElementById(pid);
          if (el) el.style.display = (gg === g) ? '' : 'none';
        });
      });
    });
    bar.appendChild(btn);
  });
  const head = sec.querySelector('.page-head');
  if (head) head.insertAdjacentElement('afterend', bar);
  groups.forEach((g, idx) => {
    g.panel_ids.forEach(pid => {
      const el = document.getElementById(pid);
      if (el) el.style.display = (idx === 0) ? '' : 'none';
    });
  });
}

const INSIGHT_STATE = { active_panel: null, hover_pos: null };

function initInsights() {
  const data = (DATA && DATA.insights) || null;
  const sec = document.getElementById('s7');
  const navLink = document.getElementById('navS7');
  if (!data || !sec) {
    if (sec) sec.style.display = 'none';
    if (navLink) navLink.style.display = 'none';
    return;
  }
  const populated = Object.keys(data).some(k => {
    const v = data[k];
    return v && (typeof v !== 'object' || Object.keys(v).length > 0 || (Array.isArray(v) && v.length > 0));
  });
  if (!populated) {
    sec.style.display = 'none';
    if (navLink) navLink.style.display = 'none';
    return;
  }
  _insightRenderSymmetry(DATA.insights && DATA.insights.Symmetry);
  _insightRenderDamageIndex(DATA.insights);
  _insightRenderReboundField(DATA.insights && DATA.insights.ReboundField);
  _insightRenderAutoRecommend(DATA.insights.auto_recommend);
  _insightRenderContactPulse(DATA.insights.ContactPulse);
  _insightRenderTrajectory3D(DATA.insights && DATA.insights.Trajectory3D);
  // === INSIGHT_BOOT_CALLS_INSERT_HERE ===
  // Workflow-added _insightRenderXxx(data) calls are inserted ABOVE this line.
}

// === DEEP_JS_FUNCTIONS_INSERT_HERE ===
// Section-06 _deepRenderXxx render functions are inserted ABOVE this line.

const DEEP_STATE = { active_part: null, srs_pos: null };

function initDeepAnalytics() {
  const data = (DATA && DATA.deep_analytics) || null;
  const sec = document.getElementById('s6');
  const navLink = document.getElementById('navS6');
  if (!data || !sec) {
    if (sec) sec.style.display = 'none';
    if (navLink) navLink.style.display = 'none';
    return;
  }
  // If every sub-key is missing/empty, hide the section.
  const populated = Object.keys(data).some(k => {
    const v = data[k];
    return v && (typeof v !== 'object' || Object.keys(v).length > 0 || (Array.isArray(v) && v.length > 0));
  });
  if (!populated) {
    sec.style.display = 'none';
    if (navLink) navLink.style.display = 'none';
    return;
  }
_deepRenderFFT(DATA.deep_analytics);
_deepRenderSRS(DATA);
  _deepRenderSafeDropZone(DATA);
_deepRenderPCAModal(DATA.deep_analytics);
_deepRenderAnomalyDetection(DATA);
_deepRenderPerPartDrillDown(data);
  // === DEEP_BOOT_CALLS_INSERT_HERE ===
  // Workflow-added _deepRenderXxx(data) calls are inserted ABOVE this line.
}

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
  {
    const _gDivExec = (DATA.part_motion && (DATA.part_motion.g_divisor || DATA.part_motion.g_mm_s2)) || 9810.0;
    host.appendChild(mkCell('MAX PEAK G', fmt((worst_g || 0) / _gDivExec, 0) + '<span class="u">G</span>'));
  }
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
  const dg = DATA.device_geometry || {aspect: 1};
  const ar = (dg.aspect && isFinite(dg.aspect) && dg.aspect > 0) ? dg.aspect : 1;
  const vbW = 540, vbH = Math.max(120, Math.round(vbW / ar));
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
  svgZoomPan(root);
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
      // mini svg — per-cell aspect ratio follows device (each cell is one DOE slot)
      const _dgT = DATA.device_geometry || {aspect: 1};
      const _arT = (_dgT.aspect && isFinite(_dgT.aspect) && _dgT.aspect > 0) ? _dgT.aspect : (90/56);
      const W = 90;
      // Cell aspect should mirror per-position physical extent: a cell spans
      // (device_width / nx) × (device_height / ny). With equal nx == ny the
      // ratio reduces to the device aspect itself.
      const H = Math.max(28, Math.min(160, Math.round(W / _arT)));
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

// === Lazy section init framework ===
// Heavy panels (Section 3-7) defer their init until their containing
// <section id="sX"> enters the viewport OR the user clicks the nav.
// This drastically reduces time-to-first-paint on the OVERVIEW landing.
const LAZY_INIT = {};
function registerLazy(id, fn) { LAZY_INIT[id] = fn; }
function fireLazy(id) {
  const fn = LAZY_INIT[id];
  if (!fn) return;
  delete LAZY_INIT[id];
  try { fn(); } catch (e) { console.error('lazy init ' + id + ' failed:', e); }
}
function setupLazyObserver() {
  if (!('IntersectionObserver' in window)) {
    Object.keys(LAZY_INIT).forEach(fireLazy);
    return;
  }
  const obs = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (e.isIntersecting && LAZY_INIT[e.target.id]) {
        fireLazy(e.target.id);
        obs.unobserve(e.target);
      }
    });
  }, { rootMargin: '300px' });
  Object.keys(LAZY_INIT).forEach(function (id) {
    const el = document.getElementById(id);
    if (el) obs.observe(el);
  });
  document.querySelectorAll('.topbar .nav a[data-target]').forEach(function (a) {
    a.addEventListener('click', function () {
      fireLazy(a.getAttribute('data-target'));
    });
  });
}

function _renderDataQualityBadges() {
  // s1 page-head 아래 데이터 신뢰성 배지 — reviewer 가 "측정값" 으로 오해 안 하도록.
  const host = document.getElementById('data-quality-badges');
  if (!host) return;
  const badges = [];
  // synthetic footprint
  const parts = DATA.parts || [];
  const syn = parts.filter(p => p._synthetic_footprint).length;
  if (syn > 0) {
    badges.push({
      cls: 'warn',
      label: 'SYNTHETIC FOOTPRINTS ' + syn + '/' + parts.length,
      title: 'part footprint XY 가 loader 의 hash 기반 placeholder 임. 실측 mesh 가 아님.',
    });
  }
  // energy_flow 측정 여부
  const ef = DATA.energy_flows || {};
  const hasReal = Object.keys(ef).length > 0 && !('__mock__' in ef);
  if (!hasReal) {
    badges.push({
      cls: 'warn',
      label: 'NO ENERGY MEASURED',
      title: 'binout 의 glstat 파싱 모듈 미구현 — KE/IE/HG/SL 시계열 측정 안 됨. ENERGY DISSIPATED KPI 도 N/A.',
    });
  }
  // mass=0 (impactor mass 추출 실패 잔재)
  const imp = (DATA.meta && DATA.meta.impactor) || {};
  if (!(imp.mass > 0)) {
    badges.push({
      cls: 'warn',
      label: 'IMPACTOR MASS UNKNOWN',
      title: 'matsum/keyword 에서 mass 추출 실패. scenario.json 의 impactor.type 명시 권장.',
    });
  }
  if (!badges.length) return;
  badges.forEach(b => {
    const el = document.createElement('span');
    el.title = b.title;
    el.textContent = b.label;
    el.style.cssText = 'display:inline-block;padding:3px 8px;border-radius:3px;font-size:10px;font-weight:600;letter-spacing:0.6px;font-family:JetBrains Mono,monospace;'
      + 'background:rgba(240,180,0,0.12);color:var(--warn);border:1px solid var(--warn);cursor:help';
    host.appendChild(el);
  });
}

function boot() {
  document.documentElement.style.setProperty('--device-aspect', (DATA.device_geometry && DATA.device_geometry.aspect) ? DATA.device_geometry.aspect : 1);
  applyUnitLabels();
  fillHeroKpi();
  _renderDataQualityBadges();
  initImpactor();
  initDoeBreakdown();
  renderAll();
  renderFindings();
  initNav();
  initReveal();
  wireControlBar();

  // Section 03 — VERDICT + ENERGY FLOW
  registerLazy('s3', function () {
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
  });

  // Section 04 — PER-PART G
  registerLazy('s4', function () {
    initPerPartPeakG();
  });

  // Section 05 — DOE SPATIAL ANALYSIS (sub-tabs must come after init)
  registerLazy('s5', function () {
    initDoeAnalysis();
    initSubTabs('s5', [
      { tab_id: 's5-spatial', label: 'SPATIAL', panel_ids: [
        'doe-kpi-strip', 'doe-ctlbar',
        'doe-grid-heat-rank', 'doe-panel-heatmap', 'doe-panel-ranking',
        'doe-grid-pp', 'doe-panel-pp-matrix',
        'doe-grid-traj-env', 'doe-panel-trajectory'
      ]},
      { tab_id: 's5-perpart', label: 'PER-PART', panel_ids: [
        'doe-panel-envelope', 'doe-panel-failure-risk'
      ]},
      { tab_id: 's5-advanced', label: 'ADVANCED', panel_ids: [
        'doe-corr-network-panel', 'panel-pareto-severity',
        'doe-grid-idw', 'idw-pred-panel',
        'doe-grid-energy', 'doe-panel-energy',
        'doe-panel-toa'
      ]}
    ]);
  });

  // Section 06 — DEEP ANALYTICS
  registerLazy('s6', function () {
    initDeepAnalytics();
    initSubTabs('s6', [
      { tab_id: 's6-freq', label: 'FREQUENCY', panel_ids: [
        'deep-fft-panel', 'deep-srs-panel'
      ]},
      { tab_id: 's6-stat', label: 'STATISTICAL', panel_ids: [
        'deep-pca-modal-panel', 'deep-anomaly-panel'
      ]},
      { tab_id: 's6-spatial', label: 'SPATIAL', panel_ids: [
        'deep-safe-drop-zone-panel', 'ppd-host'
      ]}
    ]);
  });

  // Section 07 — INSIGHTS
  registerLazy('s7', function () {
    initInsights();
    initSubTabs('s7', [
      { tab_id: 's7-design', label: 'DESIGN', panel_ids: [
        'insight-panel-symmetry', 'insight-panel-trajectory3d'
      ]},
      { tab_id: 's7-damage', label: 'DAMAGE', panel_ids: [
        'insight-DamageIndex', 'insight-panel-ContactPulse'
      ]},
      { tab_id: 's7-action', label: 'ACTION', panel_ids: [
        'insight-rebound-field', 'insight-panel-auto-recommend'
      ]}
    ]);
  });

  // Section 08 — PHYSICS
  registerLazy('s8', function () {
    initPhysics();
  });

  setupLazyObserver();
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

    # SSR g-divisor — JS 와 일관되게 acc unit 기반.
    # mm/s² → 9810,  m/s²/mm/ms² → 9.81.  raw mm/s² 를 'G' 라벨로 출력하면 안 됨.
    _acc_label = (payload.get("unit_labels") or {}).get("acc", "")
    if _acc_label == "mm/s²":
        _g_div_ssr = 9810.0
    elif _acc_label in ("m/s²", "mm/ms²"):
        _g_div_ssr = 9.81
    else:
        _g_div_ssr = 9810.0  # legacy default
    _worst_g_in_G = (worst.get("g", 0) or 0) / _g_div_ssr
    _kpi_worst_g_in_G = (kpi.get("worst_g", 0) or 0) / _g_div_ssr

    page1 = (
        _PAGE1
        .replace("__N_FACES__", str(kpi["n_faces"]))
        .replace("__N_POSITIONS__", str(kpi["n_positions"]))
        .replace("__N_PARTS__", str(kpi["n_parts"]))
        .replace("__N_PAIRS__", str(kpi["n_pairs"]))
        .replace("__WORST_LINE__", _esc(f"{worst['face']} · X {worst['x']:.1f} / Y {worst['y']:.1f}"))
        .replace("__WORST_PART_LINE__", _esc(f"{_worst_g_in_G:,.0f} G  ON  {worst['part_name']}"))
        .replace("__WORST_G__", f"{_kpi_worst_g_in_G:,.0f}")
        .replace("__WORST_S__", f"{kpi['worst_s']:.0f}")
        .replace("__N_CRIT__", str(kpi["n_critical"]))
        .replace("__N_SAFE__", str(kpi["n_safe"]))
        .replace("__DISS_PCT__", f"{kpi['diss_pct']:.1f}" if kpi.get('diss_pct') is not None else "—")
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
        "<link rel=\"icon\" href=\"data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'><rect width='64' height='64' rx='12' fill='%230e1320'/><text x='50%25' y='58%25' text-anchor='middle' font-family='monospace' font-size='30' font-weight='bold' fill='%234dd6ff'>K</text></svg>\">\n"
        "<style>\n" + _CSS + "\n</style>\n"
        "</head>\n"
        "<body>\n"
        + topbar
        + page1
        + _PAGE2
        + _PAGE3
        + _PAGE4
        + _PAGE5
        + _PAGE6
        + _PAGE7
        + _PAGE8
        + "<script>\n" + js + "\n</script>\n"
        "</body>\n</html>\n"
    )
