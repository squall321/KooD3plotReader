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
        results = [
            {
                "face": r.face, "pos_id": r.position.pos_id,
                "x": _safe(r.position.x), "y": _safe(r.position.y),
                "part_id": int(r.part_id),
                "g": _safe(r.peak_g),
                "s": _safe(r.peak_stress),
                "e": _safe(r.peak_strain),
                "d": _safe(r.peak_disp),
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

    return {
        "meta": meta,
        "kpi": kpi,
        "faces": faces,
        "parts": parts,
        "positions": positions,
        "results": results,
        "energy_flows": energy_flows,
        "findings": findings,
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
"""


def _build_topbar(meta: dict) -> str:
    project = _esc(meta["project"])
    imp_type = _esc(meta["impactor"]["type"])
    n_faces = meta.get("_n_faces", 6)
    n_runs = meta.get("_n_runs", 0)
    gen_mode = _esc(meta["generation_mode"])
    dt_s = meta["sim_params"].get("dt", 1e-6)
    t_final = meta["sim_params"].get("t_final", 0.001)
    return f"""
<div class="topbar">
  <div class="brand">KOOD3PLOT &middot; MULTI-FACE IMPACT</div>
  <div class="meta">
    <span>PROJECT <b>{project}</b></span>
    <span>IMPACTOR <b>{imp_type}</b></span>
    <span>RUNS <b>{n_runs}</b></span>
    <span>FACES <b>{n_faces}</b></span>
    <span>MODE <b>{gen_mode}</b></span>
    <span>&Delta;t <b>{dt_s * 1e6:.1f} &micro;s</b></span>
    <span>T <b>{t_final * 1e3:.2f} ms</b></span>
  </div>
  <div class="nav">
    <a data-target="s1" class="active">OVERVIEW</a>
    <a data-target="s2">TRANSFER</a>
    <a data-target="s3">VERDICT</a>
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
      <div class="band-head"><span>CUBE NET</span><span class="band-sub">6-face cross unfold</span></div>
      <div class="cube-net" id="cube-net-mini"></div>
      <div class="band-cap">각 면에 worst-G 미니 히트맵. 빨간 외곽 펄스 = 가장 위험한 자세.</div>
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
    <div class="k"><div class="v" id="kWorstS">__WORST_S__<span class="u">MPa</span></div><div class="l">WORST STRESS</div></div>
    <div class="k"><div class="v" id="kCritPairs">__N_CRIT__</div><div class="l">CRITICAL PAIRS</div></div>
    <div class="k"><div class="v" id="kSafePos">__N_SAFE__</div><div class="l">SAFE POSITIONS</div></div>
    <div class="k"><div class="v" id="kDiss">__DISS_PCT__<span class="u">%</span></div><div class="l">ENERGY DISSIPATED</div></div>
  </div>

  <div class="grid g-12" style="margin-top:14px">
    <div class="panel col-7 r">
      <div class="ph">
        <span class="pt">GLOBAL RISK MAP &middot; CUBE NET</span>
        <span class="pd">per-face XY heatmaps &middot; click cell to jump</span>
      </div>
      <div class="cube-net" style="aspect-ratio: 3/2" id="cube-net-big"></div>
      <div class="pcap">
        한 셀 = 한 임팩트 위치. 색상 = 그 위치에서 발생한 부품 중 최대 Peak G.
        상위 1% 셀은 펄스링. 클릭 시 그 자세로 점프.
      </div>
    </div>

    <div class="panel col-5 r">
      <div class="ph">
        <span class="pt">PER-FACE KPI</span>
        <span class="pd">n &middot; max G &middot; worst (x,y) &middot; driver &middot; risk score</span>
      </div>
      <table class="dt" id="face-kpi-tbl">
        <thead>
          <tr><th class="tl">FACE</th><th>n</th><th>MAX G</th><th>WORST (X,Y)</th><th class="tl">DRIVER</th><th>SCORE</th></tr>
        </thead>
        <tbody></tbody>
      </table>
      <div class="pcap">
        Risk Score = 0.5&middot;(maxG/Gmax) + 0.3&middot;(P95/Gmax) + 0.2&middot;(crit_count/n) &middot; 10.
      </div>
    </div>

    <div class="panel col-12 r">
      <div class="ph">
        <span class="pt">TOP-K WORST PAIRS</span>
        <span class="pd">rank / face / position / part / response</span>
      </div>
      <table class="dt" id="topk-tbl">
        <thead>
          <tr><th class="tl">RANK</th><th class="tl">FACE</th><th>X (mm)</th><th>Y (mm)</th><th class="tl">PART</th><th>PEAK G</th><th>&sigma; (MPa)</th><th>INFLUENCE AREA</th></tr>
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
    <span class="num">02</span><span class="tagline">TRANSFER MAPS</span>
    <span class="ttl">어디를 때리면 어느 부품이 깨지는가</span>
    <span class="sub">PER-PART XY VULNERABILITY &middot; MULTI-FACE</span>
  </div>

  <div class="ctlbar r">
    <div class="grp"><span class="lbl">METRIC</span>
      <button class="btn active" data-metric="g">PEAK G</button>
      <button class="btn" data-metric="s">&sigma;</button>
      <button class="btn" data-metric="e">&epsilon;</button>
      <button class="btn" data-metric="d">d</button>
    </div>
    <div class="grp"><span class="lbl">FACE</span>
      <button class="btn active" data-face="ALL">ALL</button>
      <button class="btn" data-face="F1">F1</button>
      <button class="btn" data-face="F2">F2</button>
      <button class="btn" data-face="F3">F3</button>
      <button class="btn" data-face="F4">F4</button>
      <button class="btn" data-face="F5">F5</button>
      <button class="btn" data-face="F6">F6</button>
    </div>
    <div class="grp"><span class="lbl">SCALE</span>
      <button class="btn active" data-scale="linear">LINEAR</button>
      <button class="btn" data-scale="log">LOG</button>
      <button class="btn" data-scale="pct">PCT</button>
    </div>
    <div class="grp"><span class="lbl">SEARCH</span>
      <input type="text" id="part-filter" placeholder="part name filter">
    </div>
  </div>

  <div class="grid g-12" id="mode-single" style="display:none">
    <div class="panel col-7 r">
      <div class="ph">
        <span class="pt">FACE GLOBAL MAP</span>
        <span class="pd" id="single-face-sub">F? &middot; worst-G per position</span>
      </div>
      <div class="face-big">
        <svg id="single-face-svg" viewBox="0 0 600 400" preserveAspectRatio="xMidYMid meet" style="height:340px"></svg>
      </div>
      <div class="face-big-foot">
        <span>&starf; weighted centroid</span>
        <span>&times; worst cell</span>
        <span id="single-face-stat">max = -</span>
      </div>
    </div>
    <div class="panel col-5 r">
      <div class="ph">
        <span class="pt">PER-PART MINI-MAPS</span>
        <span class="pd">part footprint highlighted &middot; centroid + worst markers</span>
      </div>
      <div class="mini-xy-grid" id="single-part-grid"></div>
      <div class="pcap">각 타일: 디바이스 외곽 점선 + 자기 footprint 강조 + 그리드 셀 색상 = 응답. ★ centroid, &times; worst.</div>
    </div>
  </div>

  <div class="grid g-12" id="mode-compare">
    <div class="panel col-12 r">
      <div class="ph">
        <span class="pt">M PARTS &times; 6 FACES &mdash; 2D COMPARE GRID</span>
        <span class="pd">row = part, column = face &middot; which face hurts which part</span>
      </div>
      <div id="compare-grid-wrap" style="overflow-x:auto"></div>
      <div class="pcap">
        각 셀의 색 = 그 (부품, 자세) 조합에서의 worst 응답값. 색이 진할수록 해당 자세가 그 부품에 치명적.
      </div>
    </div>
  </div>

  <div class="grid g-12" style="margin-top:14px">
    <div class="panel col-12 r">
      <div class="ph">
        <span class="pt">INFLUENCE MATRIX</span>
        <span class="pd">top-20 worst pairs &times; M parts &middot; row hover = column highlight</span>
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
        <div class="verdict-cell warn"><div class="vl">WARNING</div><div class="vn" id="vWarn">0</div><div class="vd">G &ge; P75 &middot; 모니터링</div></div>
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
      <div class="cons-banner" id="consBanner">&#9888; Residual &gt; 5% &mdash; energy conservation suspect</div>
    </div>
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
    for (const c of children) if (c) e.appendChild(c);
  }
  return e;
}

const PARTS = DATA.parts;
const PART_BY_ID = Object.fromEntries(PARTS.map(p => [p.id, p]));
const FACES = DATA.faces;
const FACE_BY_CODE = Object.fromEntries(FACES.map(f => [f.code, f]));
const RESULTS = DATA.results;

const STATE = {
  metric: 'g',
  face: 'ALL',
  scale: 'linear',
  filter: ''
};

function metricLabel(m) {
  return { g: 'Peak G', s: 'sigma (MPa)', e: 'eps', d: 'd (mm)' }[m] || m;
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

function fillHeroKpi() {
  const k = DATA.kpi;
  document.getElementById('kPositions').innerHTML = k.n_positions + '<span class="u">pos</span>';
  document.getElementById('kFaces').textContent = k.n_faces;
  document.getElementById('kParts').textContent = k.n_parts;
  document.getElementById('kWorstG').innerHTML = fmt(k.worst_g, 0) + '<span class="u">G</span>';
  document.getElementById('kWorstS').innerHTML = fmt(k.worst_s, 1) + '<span class="u">MPa</span>';
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
      ['R (mm)', imp.radius.toFixed(2)],
      ['h (mm)', imp.height.toFixed(1)],
      ['v0 (mm/s)', fmt(imp.velocity, 0)],
      ['m (kg)', fmt(imp.mass, 4)],
      ['KE (mJ)', fmt(imp.kinetic_energy * 1e-3, 2)]
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
      ['hf/hb (mm)', fh.toFixed(1) + ' / ' + bh.toFixed(1)],
      ['v0 (mm/s)', fmt(imp.velocity, 0)],
      ['KE (mJ)', fmt(imp.kinetic_energy * 1e-3, 2)]
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

function _cellHeatmapSVG(faceCode, w, h, opts) {
  const g = svg('g', {});
  const rows = FACE_RESULTS[faceCode] || [];
  g.appendChild(svg('rect', { x: 0, y: 0, width: w, height: h, fill: '#0f1320' }));
  if (!rows.length) {
    const t = svg('text', { x: w / 2, y: h / 2 + 3, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 8 });
    t.appendChild(document.createTextNode('no data'));
    g.appendChild(t);
    return g;
  }
  const bb = faceBBox(faceCode);
  const xmin = bb[0], xmax = bb[1], ymin = bb[2], ymax = bb[3];
  const mx = maxMetric(rows);
  const seen = {};
  for (const r of rows) {
    const k = r.face + '|' + r.pos_id;
    if (seen[k]) continue;
    seen[k] = 1;
    const wr = FACE_POS_MAX[k];
    if (!wr) continue;
    const u = (wr.x - xmin) / (xmax - xmin);
    const v = 1 - (wr.y - ymin) / (ymax - ymin);
    const cx = u * w, cy = v * h;
    const sz = Math.max(2, Math.min(w, h) / 8);
    g.appendChild(svg('rect', {
      x: cx - sz / 2, y: cy - sz / 2, width: sz, height: sz,
      fill: gColor(scaleNorm(wr[STATE.metric] || 0, mx)),
      opacity: 0.9
    }));
  }
  if (opts && opts.label) {
    const t = svg('text', { x: 4, y: 10, fill: '#4dd6ff', 'font-size': 9, 'font-family': 'JetBrains Mono', 'font-weight': 700 });
    t.appendChild(document.createTextNode(opts.label));
    g.appendChild(t);
  }
  return g;
}

function initCubeNet(containerId, big) {
  const root = document.getElementById(containerId);
  while (root.firstChild) root.removeChild(root.firstChild);
  const W = 400, H = 300;
  const cw = W / 4.2, ch = H / 3.2;
  const sx = (W - 4 * cw) / 2;
  const sy = (H - 3 * ch) / 2;
  const cellPos = {
    F5: [sx + cw, sy],
    F4: [sx, sy + ch],
    F1: [sx + cw, sy + ch],
    F3: [sx + 2 * cw, sy + ch],
    F2: [sx + 3 * cw, sy + ch],
    F6: [sx + cw, sy + 2 * ch]
  };
  const root_svg = svg('svg', { viewBox: '0 0 ' + W + ' ' + H, preserveAspectRatio: 'xMidYMid meet' });
  let riskyFace = null, riskyMax = -1;
  for (const f of FACES) {
    const rows = FACE_RESULTS[f.code] || [];
    const m = maxMetric(rows);
    if (m > riskyMax) { riskyMax = m; riskyFace = f.code; }
  }
  for (const f of FACES) {
    const pos = cellPos[f.code] || [0, 0];
    const g = svg('g', { transform: 'translate(' + pos[0] + ',' + pos[1] + ')', class: 'cube-cell' + (f.code === riskyFace ? ' risky' : '') });
    g.appendChild(svg('rect', {
      x: 0, y: 0, width: cw - 2, height: ch - 2, rx: 3,
      class: 'cell-frame', fill: 'none',
      stroke: f.code === riskyFace ? '#ff3854' : '#5c6383', 'stroke-width': 1
    }));
    g.appendChild(_cellHeatmapSVG(f.code, cw - 2, ch - 2, { label: big ? (f.code + ' · ' + f.name) : f.code }));
    if (big) {
      const rows = FACE_RESULTS[f.code] || [];
      const mxx = maxMetric(rows);
      const t = svg('text', { x: cw - 4, y: ch - 6, fill: '#aab2cf', 'font-size': 8, 'text-anchor': 'end', 'font-family': 'JetBrains Mono' });
      t.appendChild(document.createTextNode(fmt(mxx, 0)));
      g.appendChild(t);
    }
    g.style.cursor = 'pointer';
    g.addEventListener('click', function () {
      const btn = document.querySelector('.ctlbar .btn[data-face="' + f.code + '"]');
      if (btn) btn.click();
      const tgt = document.getElementById('s2');
      if (tgt) tgt.scrollIntoView({ behavior: 'smooth' });
    });
    root_svg.appendChild(g);
  }
  root.appendChild(root_svg);
}

function initFaceKpiTable() {
  const tbody = document.querySelector('#face-kpi-tbl tbody');
  while (tbody.firstChild) tbody.removeChild(tbody.firstChild);
  let gmax = 0;
  for (const r of RESULTS) if (r.g > gmax) gmax = r.g;
  for (const f of FACES) {
    const rows = FACE_RESULTS[f.code] || [];
    if (!rows.length) continue;
    let worst = rows[0];
    for (const r of rows) if (r.g > worst.g) worst = r;
    const gvals = rows.map(r => r.g).sort((a, b) => a - b);
    const p95 = gvals[Math.floor(gvals.length * 0.95)] || 0;
    const crit = gvals.filter(v => v >= gmax * 0.5).length;
    const score = (0.5 * worst.g / Math.max(1, gmax) + 0.3 * p95 / Math.max(1, gmax) + 0.2 * crit / Math.max(1, gvals.length)) * 10;
    const cls = score >= 7 ? 'r-crit' : score >= 4 ? 'r-warn' : 'r-safe';
    const scoreColor = score >= 7 ? 'var(--crit)' : score >= 4 ? 'var(--warn)' : 'var(--good)';
    tbody.appendChild(el('tr', { class: cls }, [
      el('td', { class: 'tl b' }, f.code + ' · ' + f.name),
      el('td', { class: 'num' }, String(Math.max(1, rows.length / Math.max(1, PARTS.length) | 0))),
      el('td', { class: 'num b' }, fmt(worst.g, 0)),
      el('td', { class: 'num dim' }, worst.x.toFixed(1) + ' , ' + worst.y.toFixed(1)),
      el('td', { class: 'tl b' }, worst.part_name),
      el('td', { class: 'num', style: { color: scoreColor } }, score.toFixed(1) + ' / 10')
    ]));
  }
}

function initTopK() {
  const tbody = document.querySelector('#topk-tbl tbody');
  while (tbody.firstChild) tbody.removeChild(tbody.firstChild);
  const sorted = RESULTS.slice().sort((a, b) => b.g - a.g).slice(0, 12);
  const gmax = sorted[0] ? sorted[0].g : 1;
  for (let i = 0; i < sorted.length; i++) {
    const r = sorted[i];
    const partRows = RESULTS.filter(x => x.part_id === r.part_id);
    const thr = gmax * 0.4;
    const inf = partRows.filter(x => x.g >= thr).length;
    const cls = i < 3 ? 'r-crit' : i < 8 ? 'r-warn' : 'r-safe';
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

function _miniFaceHeatmapSVG(faceCode, partId, width, height) {
  const fk = faceCode + '|' + partId;
  const rows = FACE_PART_RESULTS[fk] || [];
  const root = svg('svg', { viewBox: '0 0 ' + width + ' ' + height, preserveAspectRatio: 'xMidYMid meet' });
  if (!rows.length) {
    root.appendChild(svg('rect', { x: 0, y: 0, width: width, height: height, fill: '#0f1320' }));
    return root;
  }
  const bb = faceBBox(faceCode);
  const xmin = bb[0], xmax = bb[1], ymin = bb[2], ymax = bb[3];
  root.appendChild(svg('rect', {
    x: width * 0.06, y: height * 0.08,
    width: width * 0.88, height: height * 0.84,
    fill: 'none', stroke: '#3a4055', 'stroke-width': 0.6,
    'stroke-dasharray': '2,2', rx: 4
  }));
  let mx = 0;
  for (const r of rows) { const v = r[STATE.metric] || 0; if (v > mx) mx = v; }
  let sumW = 0, sumWX = 0, sumWY = 0;
  let worst = rows[0];
  for (const r of rows) {
    const v = r[STATE.metric] || 0;
    if (v > (worst[STATE.metric] || 0)) worst = r;
    const u = (r.x - xmin) / (xmax - xmin);
    const vv = 1 - (r.y - ymin) / (ymax - ymin);
    const cx = u * width, cy = vv * height;
    const sz = Math.max(2, Math.min(width, height) / 8);
    root.appendChild(svg('rect', {
      x: cx - sz / 2, y: cy - sz / 2, width: sz, height: sz,
      fill: gColor(scaleNorm(v, mx)), opacity: 0.92
    }));
    sumW += v; sumWX += v * r.x; sumWY += v * r.y;
  }
  if (sumW > 0) {
    const cx = sumWX / sumW, cy = sumWY / sumW;
    const u = (cx - xmin) / (xmax - xmin);
    const vv = 1 - (cy - ymin) / (ymax - ymin);
    const px = u * width, py = vv * height;
    const t = svg('text', { x: px, y: py + 4, 'text-anchor': 'middle', fill: '#ffffff', 'font-size': 10, 'font-weight': 700 });
    t.appendChild(document.createTextNode('★'));
    root.appendChild(t);
  }
  const wu = (worst.x - xmin) / (xmax - xmin);
  const wv = 1 - (worst.y - ymin) / (ymax - ymin);
  const tx = svg('text', { x: wu * width, y: wv * height + 4, 'text-anchor': 'middle', fill: '#ff3854', 'font-size': 11, 'font-weight': 700 });
  tx.appendChild(document.createTextNode('×'));
  root.appendChild(tx);
  return root;
}

function _computeCoV(rows) {
  if (!rows.length) return 0;
  const vs = rows.map(r => r[STATE.metric] || 0);
  const mean = vs.reduce((a, b) => a + b, 0) / vs.length;
  if (mean === 0) return 0;
  const variance = vs.reduce((a, b) => a + (b - mean) * (b - mean), 0) / vs.length;
  return Math.sqrt(variance) / mean;
}

function renderSingleFace() {
  const face = STATE.face;
  document.getElementById('mode-single').style.display = '';
  document.getElementById('mode-compare').style.display = 'none';
  const fObj = FACE_BY_CODE[face];
  document.getElementById('single-face-sub').textContent = face + ' · ' + (fObj ? fObj.name : '') + ' · ' + metricLabel(STATE.metric);
  const root = document.getElementById('single-face-svg');
  while (root.firstChild) root.removeChild(root.firstChild);
  const rows = FACE_RESULTS[face] || [];
  const bb = faceBBox(face);
  const xmin = bb[0], xmax = bb[1], ymin = bb[2], ymax = bb[3];
  const vbW = 600, vbH = 400;
  root.appendChild(svg('rect', { x: 0, y: 0, width: vbW, height: vbH, fill: '#0f1320', rx: 6 }));
  root.appendChild(svg('rect', {
    x: vbW * 0.05, y: vbH * 0.05, width: vbW * 0.9, height: vbH * 0.9,
    fill: 'none', stroke: '#3a4055', 'stroke-width': 0.8,
    'stroke-dasharray': '4,3', rx: 6
  }));
  let mx = 0;
  for (const r of rows) { const v = r[STATE.metric] || 0; if (v > mx) mx = v; }
  const seen = {};
  let worst = rows[0];
  for (const r of rows) {
    const k = r.face + '|' + r.pos_id;
    if (seen[k]) continue;
    seen[k] = 1;
    const wr = FACE_POS_MAX[k] || r;
    if (wr.g > (worst ? worst.g : 0)) worst = wr;
    const u = (wr.x - xmin) / (xmax - xmin);
    const v2 = 1 - (wr.y - ymin) / (ymax - ymin);
    const cx = u * vbW, cy = v2 * vbH;
    const sz = Math.min(vbW, vbH) / 24;
    const rect = svg('rect', {
      x: cx - sz / 2, y: cy - sz / 2, width: sz, height: sz,
      fill: gColor(scaleNorm(wr[STATE.metric] || 0, mx)), rx: 1
    });
    const title = svg('title', {});
    title.appendChild(document.createTextNode(wr.pos_id + '\nX=' + wr.x.toFixed(2) + ' Y=' + wr.y.toFixed(2) + '\nworst part = ' + wr.part_name + '\n' + metricLabel(STATE.metric) + ' = ' + fmt(wr[STATE.metric] || 0, 2)));
    rect.appendChild(title);
    if ((wr[STATE.metric] || 0) >= mx * 0.95) {
      root.appendChild(svg('circle', { cx: cx, cy: cy, r: 4, fill: 'none', stroke: '#ff3854', 'stroke-width': 1, class: 'pulse-dot' }));
    }
    root.appendChild(rect);
  }
  if (worst) {
    const u = (worst.x - xmin) / (xmax - xmin);
    const v2 = 1 - (worst.y - ymin) / (ymax - ymin);
    const t = svg('text', { x: u * vbW, y: v2 * vbH + 5, 'text-anchor': 'middle', fill: '#ff3854', 'font-size': 18, 'font-weight': 700 });
    t.appendChild(document.createTextNode('×'));
    root.appendChild(t);
  }
  document.getElementById('single-face-stat').textContent = 'max ' + metricLabel(STATE.metric) + ' = ' + fmt(mx, 2);
  const grid = document.getElementById('single-part-grid');
  while (grid.firstChild) grid.removeChild(grid.firstChild);
  const nPosFace = Object.keys(FACE_POS_MAX).filter(k => k.indexOf(face + '|') === 0).length;
  for (const p of PARTS) {
    const fk = face + '|' + p.id;
    const prows = FACE_PART_RESULTS[fk] || [];
    let pmx = 0;
    for (const r of prows) { const v = r[STATE.metric] || 0; if (v > pmx) pmx = v; }
    const cov = _computeCoV(prows);
    const dimmed = !partMatches(p);
    const tile = el('div', { class: 'mini-xy' + (dimmed ? ' dim' : '') }, [
      el('div', { class: 'mlabel' }, [
        el('span', { class: 'mid' }, p.name.split('\\').pop()),
        el('span', { class: 'mval' }, fmt(pmx, 1))
      ])
    ]);
    tile.appendChild(_miniFaceHeatmapSVG(face, p.id, 200, 80));
    tile.appendChild(el('div', { class: 'mfoot' }, [
      el('span', null, 'CoV ' + cov.toFixed(2)),
      el('span', null, prows.length + '/' + nPosFace)
    ]));
    tile.addEventListener('click', () => {
      const tgt = document.getElementById('s3');
      if (tgt) tgt.scrollIntoView({ behavior: 'smooth' });
    });
    grid.appendChild(tile);
  }
}

function renderCompare() {
  document.getElementById('mode-single').style.display = 'none';
  document.getElementById('mode-compare').style.display = '';
  const wrap = document.getElementById('compare-grid-wrap');
  while (wrap.firstChild) wrap.removeChild(wrap.firstChild);
  const grid = el('div', {
    class: 'compare-grid',
    style: { gridTemplateColumns: 'minmax(120px,1fr) repeat(' + FACES.length + ', minmax(80px, 1fr))' }
  });
  grid.appendChild(el('div', { class: 'cclbl', style: { color: 'var(--dim)', fontWeight: 700 } }, 'PART \\ FACE'));
  for (const f of FACES) grid.appendChild(el('div', { class: 'cclbl', style: { color: 'var(--accent)', fontWeight: 700 } }, f.code));
  for (const p of PARTS) {
    if (!partMatches(p)) continue;
    grid.appendChild(el('div', { class: 'cclbl', style: { textAlign: 'left', color: 'var(--fg2)', padding: '4px 8px' } }, p.name.split('\\').pop()));
    for (const f of FACES) {
      const cell = el('div', { class: 'compare-cell' });
      cell.appendChild(_miniFaceHeatmapSVG(f.code, p.id, 100, 60));
      const fk = f.code + '|' + p.id;
      const rs = FACE_PART_RESULTS[fk] || [];
      let mx = 0; for (const r of rs) { const v = r[STATE.metric] || 0; if (v > mx) mx = v; }
      cell.appendChild(el('div', { class: 'cclbl' }, fmt(mx, 1)));
      grid.appendChild(cell);
    }
  }
  wrap.appendChild(grid);
}

function renderTransfer() {
  if (STATE.face === 'ALL') renderCompare();
  else renderSingleFace();
  renderInfluenceMatrix();
}

function renderInfluenceMatrix() {
  const wrap = document.getElementById('imatrix-wrap');
  while (wrap.firstChild) wrap.removeChild(wrap.firstChild);
  const sorted = RESULTS.slice().sort((a, b) => b[STATE.metric] - a[STATE.metric]);
  const seen = {};
  const topPairs = [];
  for (const r of sorted) {
    const k = r.face + '|' + r.pos_id;
    if (seen[k]) continue;
    seen[k] = 1;
    topPairs.push({ face: r.face, pos_id: r.pos_id, x: r.x, y: r.y });
    if (topPairs.length >= 20) break;
  }
  let gmx = 0; for (const r of RESULTS) { const v = r[STATE.metric] || 0; if (v > gmx) gmx = v; }
  const tbl = el('table', { class: 'imatrix' });
  const trHead = el('tr', null, [el('th', { class: 'tl', style: { minWidth: '130px' } }, 'PAIR (face · pos)')]);
  for (const p of PARTS) {
    trHead.appendChild(el('th', {
      style: { transform: 'rotate(-30deg)', transformOrigin: 'left bottom', whiteSpace: 'nowrap', paddingLeft: '10px', color: 'var(--accent)' }
    }, p.name.split('\\').pop()));
  }
  trHead.appendChild(el('th', null, 'TOTAL'));
  tbl.appendChild(el('thead', null, trHead));
  const tbody = el('tbody');
  // index by (face, pos_id, part_id)
  const idx = {};
  for (const r of RESULTS) idx[r.face + '|' + r.pos_id + '|' + r.part_id] = r;
  for (const pair of topPairs) {
    const tr = el('tr');
    tr.appendChild(el('td', { class: 'tl', style: { color: 'var(--fg)', fontWeight: 600 } }, pair.face + ' · ' + pair.x.toFixed(1) + ',' + pair.y.toFixed(1)));
    let rowSum = 0;
    for (const p of PARTS) {
      const match = idx[pair.face + '|' + pair.pos_id + '|' + p.id];
      const v = match ? (match[STATE.metric] || 0) : 0;
      rowSum += v;
      const td = el('td', {
        class: 'cell',
        title: p.name + ': ' + fmt(v, 2),
        style: { background: v > 0 ? gColor(scaleNorm(v, gmx)) : '#0a0c14' }
      });
      tr.appendChild(td);
    }
    tr.appendChild(el('td', { style: { color: 'var(--num)', fontWeight: 700, paddingLeft: '8px' } }, fmt(rowSum, 1)));
    tbody.appendChild(tr);
  }
  tbl.appendChild(tbody);
  wrap.appendChild(tbl);
}

function renderVerdict() {
  const tbody = document.querySelector('#verdict-tbl tbody');
  while (tbody.firstChild) tbody.removeChild(tbody.firstChild);
  const byPart = {};
  for (const r of RESULTS) {
    const cur = byPart[r.part_id];
    if (!cur || r.g > cur.g) byPart[r.part_id] = r;
  }
  let gmx = 0; for (const r of RESULTS) if (r.g > gmx) gmx = r.g;
  const crit_t = gmx * 0.6;
  const warn_t = gmx * 0.3;
  let nC = 0, nW = 0, nS = 0;
  const rows = Object.values(byPart).sort((a, b) => b.g - a.g);
  for (const r of rows) {
    const partRows = RESULTS.filter(x => x.part_id === r.part_id);
    const vs = partRows.map(x => x.g);
    const mean = vs.reduce((a, b) => a + b, 0) / vs.length;
    const variance = vs.reduce((a, b) => a + (b - mean) * (b - mean), 0) / vs.length;
    const cov = mean > 0 ? Math.sqrt(variance) / mean : 0;
    const inf = vs.filter(v => v >= gmx * 0.4).length;
    const klass = r.g >= crit_t ? 'CRITICAL' : r.g >= warn_t ? 'WARNING' : 'PASSED';
    if (klass === 'CRITICAL') nC++; else if (klass === 'WARNING') nW++; else nS++;
    const rowClass = klass === 'CRITICAL' ? 'r-crit' : klass === 'WARNING' ? 'r-warn' : 'r-safe';
    const klassColor = klass === 'CRITICAL' ? 'var(--crit)' : klass === 'WARNING' ? 'var(--warn)' : 'var(--good)';
    const mode = inf > partRows.length * 0.5 ? '전반 약화' : inf > 3 ? '국소 다중' : '단일 위치';
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
      el('td', { class: 'tl dim' }, mode)
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
        el('span', null, fmt(r.s, 1) + ' MPa')
      ])
    ]);
    const s = svg('svg', { viewBox: '0 0 200 64', preserveAspectRatio: 'none' });
    const peakT = 0.20 + 0.15 * Math.sin(i * 1.7);
    const ptsHi = [], ptsLo = [], pts50 = [], ptsW = [];
    for (let k = 0; k <= 40; k++) {
      const t = k / 40;
      const env = Math.exp(-((t - peakT) * (t - peakT)) / 0.012);
      const env_w = Math.exp(-((t - peakT) * (t - peakT)) / 0.006);
      pts50.push([t * 200, 60 - env * 50]);
      ptsHi.push([t * 200, 60 - Math.min(1, env * 1.2) * 55]);
      ptsLo.push([t * 200, 60 - Math.max(0, env * 0.4) * 45]);
      ptsW.push([t * 200, 60 - env_w * 60]);
    }
    const bandPath = 'M' + ptsHi.map(p => p.join(',')).join(' L ') + ' L ' + ptsLo.slice().reverse().map(p => p.join(',')).join(' L ') + ' Z';
    s.appendChild(svg('path', { d: bandPath, fill: 'rgba(170,178,207,0.18)', stroke: 'none' }));
    s.appendChild(svg('polyline', { points: pts50.map(p => p.join(',')).join(' '), fill: 'none', stroke: '#aab2cf', 'stroke-width': 0.8 }));
    s.appendChild(svg('polyline', { points: ptsW.map(p => p.join(',')).join(' '), fill: 'none', stroke: '#ff3854', 'stroke-width': 1.4 }));
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
  for (const e of flow.edges) {
    let idx = -1;
    const thr = Math.max(1, (e.peak_f || 1) * 0.05);
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
  for (const e of flow.edges) {
    const p1 = EG.nodes_pos[e.src], p2 = EG.nodes_pos[e.dst];
    if (!p1 || !p2) continue;
    const x1 = cx + p1.x, y1 = cy + p1.y, x2 = cx + p2.x, y2 = cy + p2.y;
    const imp = e.imp[ti] || 0;
    const active = (e.f[ti] || 0) > 0.001 * (e.peak_f || 1);
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
  for (const n of flow.nodes) {
    const p = EG.nodes_pos[n.id];
    if (!p) continue;
    const x = cx + p.x, y = cy + p.y;
    const ie = n.ie[ti] || 0;
    const ke = n.ke[ti] || 0;
    const r = 8 + Math.min(28, ie * 0.4 + (n.is_impactor ? ke * 0.15 : 0));
    const t01 = Math.max(0, Math.min(1, ie / 40));
    ctx.fillStyle = n.is_impactor ? '#b46eff' : gColor(t01);
    ctx.beginPath();
    ctx.arc(x, y, r, 0, 2 * Math.PI);
    ctx.fill();
    const hasActive = flow.edges.some(e => (e.src === n.id || e.dst === n.id) && (e.f[ti] || 0) > 0.001 * (e.peak_f || 1));
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
  if (residual_pct > 5) {
    document.getElementById('consBanner').classList.add('on');
    document.getElementById('consResCell').classList.add('warn');
  }
}

function wireControlBar() {
  document.querySelectorAll('.ctlbar .btn').forEach(btn => {
    btn.addEventListener('click', function () {
      if (btn.dataset.metric) {
        STATE.metric = btn.dataset.metric;
        document.querySelectorAll('.ctlbar .btn[data-metric]').forEach(b => b.classList.toggle('active', b.dataset.metric === STATE.metric));
        renderAll();
      } else if (btn.dataset.face) {
        STATE.face = btn.dataset.face;
        document.querySelectorAll('.ctlbar .btn[data-face]').forEach(b => b.classList.toggle('active', b.dataset.face === STATE.face));
        renderTransfer();
      } else if (btn.dataset.scale) {
        STATE.scale = btn.dataset.scale;
        document.querySelectorAll('.ctlbar .btn[data-scale]').forEach(b => b.classList.toggle('active', b.dataset.scale === STATE.scale));
        renderAll();
      }
    });
  });
  document.getElementById('part-filter').addEventListener('input', function (ev) {
    STATE.filter = ev.target.value;
    renderTransfer();
  });
}

function renderAll() {
  initCubeNet('cube-net-mini', false);
  initCubeNet('cube-net-big', true);
  initFaceKpiTable();
  initTopK();
  renderTransfer();
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
    const sections = ['s1', 's2', 's3'];
    const y = window.scrollY + 120;
    let active = sections[0];
    for (const id of sections) {
      const sec = document.getElementById(id);
      if (sec && sec.offsetTop <= y) active = id;
    }
    navs.forEach(a => a.classList.toggle('active', a.dataset.target === active));
  });
}

function boot() {
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

    topbar = _build_topbar(payload["meta"])
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
        + "<script>\n" + js + "\n</script>\n"
        "</body>\n</html>\n"
    )
