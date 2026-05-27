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

    # --- restrict to bi-face (F1/F2) for the redesigned report --------------
    keep_faces = {"F1", "F2"}
    faces = [f for f in faces if f["code"] in keep_faces]
    positions = [p for p in positions if p["face"] in keep_faces]
    results = [r for r in results if r["face"] in keep_faces]

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

    # fallback: derive bbox from positions if device_layout.json missing
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
        else:
            device_bbox = {"xmin": -50.0, "xmax": 50.0, "ymin": -40.0, "ymax": 40.0}

    # fallback footprints: synthesize a small rect near device center for parts
    # without a real footprint (deterministic seed by part id).
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

    # If no real trajectories, synthesise a deterministic mock so the
    # visualisations have something to render.
    if not trajectories:
        unique_pos = {}
        for r in results:
            unique_pos[r["pos_id"]] = (r["face"], r["x"], r["y"], r["g"])
        g_vals_t = [v[3] for v in unique_pos.values() if v[3] > 0]
        gmax_t = max(g_vals_t) if g_vals_t else 1.0
        v0 = _safe(report.impactor.velocity) or 1400.0
        ke0_mJ = _safe(report.impactor.kinetic_energy) * 1e-3
        if ke0_mJ <= 0:
            ke0_mJ = 100.0
        for pos_id, (face_code, x, y, gv) in unique_pos.items():
            # deterministic-but-position-varying behaviour
            seed = (abs(hash(pos_id)) & 0xFFFFFFFF) / 0xFFFFFFFF
            ratio = (gv / gmax_t) if gmax_t > 0 else 0.5
            # high-g => embed; low-g => bounce
            if ratio > 0.75:
                behavior = "embed"
                ke_ret = 0.05 + 0.10 * seed
                pen = 1.5 + 4.0 * seed
            elif ratio > 0.45:
                behavior = "rebound"
                ke_ret = 0.30 + 0.25 * seed
                pen = 0.8 + 1.5 * seed
            elif seed > 0.55:
                behavior = "slide"
                ke_ret = 0.55 + 0.20 * seed
                pen = 0.2 + 0.5 * seed
            else:
                behavior = "bounce"
                ke_ret = 0.75 + 0.20 * seed
                pen = 0.05 + 0.4 * seed
            T_pts = 21
            t_arr = [round(i * 1.0e-3 / (T_pts - 1), 6) for i in range(T_pts)]
            # KE decay shape
            ke_arr = []
            for i in range(T_pts):
                t_norm = i / (T_pts - 1)
                if behavior == "bounce":
                    k = 1.0 if t_norm < 0.20 else 0.30 + (ke_ret - 0.30) * min(1.0, (t_norm - 0.20) / 0.4)
                    if t_norm >= 0.55:
                        k = ke_ret
                elif behavior == "embed":
                    k = max(ke_ret, 1.0 * math.exp(-t_norm * 4.5))
                elif behavior == "slide":
                    k = max(ke_ret, 1.0 - (1.0 - ke_ret) * min(1.0, t_norm / 0.5))
                else:  # rebound
                    k = max(ke_ret, 1.0 - (1.0 - ke_ret) * (t_norm / 0.5) ** 0.8)
                ke_arr.append(round(ke0_mJ * k, 5))
            # contact: from 15% to 70% of duration
            contact_arr = [(0.15 <= (i / (T_pts - 1)) <= 0.70) for i in range(T_pts)]
            # rebound direction: roughly random-ish based on (x,y) but with sliding bias
            ang = (x * 0.07 + y * 0.13 + seed * 6.28) % (2 * math.pi)
            rebound_mag = v0 * (0.05 if behavior == "embed" else
                                 0.35 if behavior == "rebound" else
                                 0.60 if behavior == "slide" else 0.80) * (0.6 + 0.4 * seed)
            rx = rebound_mag * math.cos(ang)
            ry = rebound_mag * math.sin(ang) * (0.4 if behavior != "slide" else 1.0)
            # build positions: descending Z to z_min, then maybe rising
            pos_xyz = []
            vel_xyz = []
            z_top = 10.0
            for i in range(T_pts):
                tn = i / (T_pts - 1)
                # vertical motion
                if behavior == "embed":
                    z = z_top * max(0.0, 1.0 - tn * 2.0) - pen * min(1.0, tn * 2.0)
                else:
                    # bounce-ish parabola
                    z = z_top - tn * (z_top + pen) * 2.0
                    if tn > 0.5:
                        z = -pen + (z_top * 0.6) * (tn - 0.5) * 2.0 * (1.0 - (1.0 - ke_ret))
                # lateral drift
                xp = x + rx * (tn ** 1.2) * 1e-4
                yp = y + ry * (tn ** 1.2) * 1e-4
                pos_xyz.append([round(xp, 3), round(yp, 3), round(z, 3)])
                # velocities
                if i == 0:
                    vx, vy, vz = 0.0, 0.0, -v0
                else:
                    dt = t_arr[i] - t_arr[i - 1] or 1e-9
                    vx = (pos_xyz[i][0] - pos_xyz[i - 1][0]) / dt
                    vy = (pos_xyz[i][1] - pos_xyz[i - 1][1]) / dt
                    vz = (pos_xyz[i][2] - pos_xyz[i - 1][2]) / dt
                vel_xyz.append([round(vx, 2), round(vy, 2), round(vz, 2)])
            trajectories[pos_id] = {
                "face": face_code,
                "x": _safe(x), "y": _safe(y),
                "t": t_arr,
                "pos": pos_xyz,
                "vel": vel_xyz,
                "ke": ke_arr,
                "contact": contact_arr,
                "init_ke": round(ke0_mJ, 4),
                "final_ke": round(ke0_mJ * ke_ret, 4),
                "ke_retention": round(ke_ret, 4),
                "max_pen": round(pen, 3),
                "t_first_contact": round(0.15e-3, 6),
                "rebound_xy": [round(rx, 2), round(ry, 2)],
                "rebound_speed": round(rebound_mag, 2),
                "incident_speed": round(v0, 2),
                "behavior": behavior,
                "_mock": True,
            }

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
.bbadge.slide { background: #ff9e64; }
.bbadge.embed { background: var(--crit); color: #fff; }
.bbadge.unknown { background: var(--dim); }

.traj-na { color: var(--dim); font-size: 10px; padding: 8px 4px; text-align: center; font-style: italic; }
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
    <a data-target="s2">INSPECTOR</a>
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
    <div class="k"><div class="v" id="kWorstS">__WORST_S__<span class="u">MPa</span></div><div class="l">WORST STRESS</div></div>
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
      <div class="pcap">
        Risk Score = 0.5&middot;(maxG/Gmax) + 0.3&middot;(P95/Gmax) + 0.2&middot;(crit_count/n) &middot; 10.
        &Delta; = Risk Score - other face's score.
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
const DEVICE_BBOX = DATA.device_bbox || { xmin: -50, xmax: 50, ymin: -40, ymax: 40 };

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

/* ===================================================================
 * Impact Inspector  (Page 2 hero + Page 1 bi-face mini/split)
 * =================================================================== */

/** Map XY (mm) into SVG viewBox coords using the device bbox + a pad. */
function _xyToVB(x, y, vbW, vbH, padPx) {
  const bb = DEVICE_BBOX;
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

  // device outline (rounded dashed rect at true bbox)
  const bb = DEVICE_BBOX;
  const tl = _xyToVB(bb.xmin, bb.ymax, vbW, vbH, 28);
  const br = _xyToVB(bb.xmax, bb.ymin, vbW, vbH, 28);
  root.appendChild(svg('rect', {
    x: tl[0], y: tl[1], width: br[0] - tl[0], height: br[1] - tl[1],
    rx: 6, ry: 6, fill: 'none', stroke: '#3a4055', 'stroke-width': 1.2,
    'stroke-dasharray': '5,4'
  }));

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
  return { g: 'Peak G', s: 'σ (MPa)', e: 'ε', d: 'd (mm)' }[m] || m;
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
  // synthetic envelope (we don't currently store per-pair time series)
  // peak occurs ~30% of timeline; envelope width scales with G magnitude
  const peakT = 0.25 + 0.10 * Math.sin((partId * 1.3) + (rec.x * 0.03));
  const ptsW = [], ptsHi = [], ptsLo = [], pts50 = [];
  for (let k = 0; k <= 40; k++) {
    const t = k / 40;
    const env = Math.exp(-((t - peakT) * (t - peakT)) / 0.012);
    const env_w = Math.exp(-((t - peakT) * (t - peakT)) / 0.006);
    pts50.push([t * W, H - 8 - env * (H - 16)]);
    ptsHi.push([t * W, H - 8 - Math.min(1, env * 1.2) * (H - 16)]);
    ptsLo.push([t * W, H - 8 - Math.max(0, env * 0.4) * (H - 18)]);
    ptsW.push([t * W, H - 8 - env_w * (H - 12)]);
  }
  const bandPath = 'M' + ptsHi.map(pt => pt.join(',')).join(' L ') + ' L ' + ptsLo.slice().reverse().map(pt => pt.join(',')).join(' L ') + ' Z';
  svgRoot.appendChild(svg('path', { d: bandPath, fill: 'rgba(170,178,207,0.18)', stroke: 'none' }));
  svgRoot.appendChild(svg('polyline', { points: pts50.map(pt => pt.join(',')).join(' '), fill: 'none', stroke: '#aab2cf', 'stroke-width': 0.8 }));
  svgRoot.appendChild(svg('polyline', { points: ptsW.map(pt => pt.join(',')).join(' '), fill: 'none', stroke: '#ff3854', 'stroke-width': 1.4 }));
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
  // compute scores for each face first so we can do the vs-other delta
  const faceStats = {};
  for (const f of FACES) {
    const rows = FACE_RESULTS[f.code] || [];
    if (!rows.length) continue;
    let worst = rows[0];
    for (const r of rows) if (r.g > worst.g) worst = r;
    const gvals = rows.map(r => r.g).sort((a, b) => a - b);
    const p95 = gvals[Math.floor(gvals.length * 0.95)] || 0;
    const crit = gvals.filter(v => v >= gmax * 0.5).length;
    const score = (0.5 * worst.g / Math.max(1, gmax) + 0.3 * p95 / Math.max(1, gmax) + 0.2 * crit / Math.max(1, gvals.length)) * 10;
    const nPos = new Set(rows.map(r => r.pos_id)).size;
    faceStats[f.code] = { face: f, worst: worst, score: score, n: nPos };
  }
  const codes = Object.keys(faceStats);
  for (const code of codes) {
    const s = faceStats[code];
    const f = s.face;
    const worst = s.worst;
    const score = s.score;
    const otherCode = codes.find(c => c !== code);
    const delta = (otherCode != null) ? (score - faceStats[otherCode].score) : 0;
    const cls = score >= 7 ? 'r-crit' : score >= 4 ? 'r-warn' : 'r-safe';
    const scoreColor = score >= 7 ? 'var(--crit)' : score >= 4 ? 'var(--warn)' : 'var(--good)';
    const dColor = delta > 0 ? 'var(--crit)' : delta < 0 ? 'var(--good)' : 'var(--dim)';
    const dStr = (delta > 0 ? '+' : '') + delta.toFixed(2);
    tbody.appendChild(el('tr', { class: cls }, [
      el('td', { class: 'tl b' }, f.code + ' · ' + f.name),
      el('td', { class: 'num' }, String(s.n)),
      el('td', { class: 'num b' }, fmt(worst.g, 0)),
      el('td', { class: 'num dim' }, worst.x.toFixed(1) + ' , ' + worst.y.toFixed(1)),
      el('td', { class: 'tl b' }, worst.part_name),
      el('td', { class: 'num', style: { color: scoreColor } }, score.toFixed(1) + ' / 10'),
      el('td', { class: 'num', style: { color: dColor } }, dStr)
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

/* ===================================================================
 * Trajectory visualisations (6 new panels)
 * =================================================================== */

const TRAJ = DATA.trajectories || {};
const TRAJ_KEYS = Object.keys(TRAJ);
const CLUSTERS = DATA.clusters || { n: 0, labels: {}, archetypes: [] };

const BEHAVIOR_COLOR = {
  bounce: '#4adfa1',
  rebound: '#f0a830',
  slide:  '#ff9e64',
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
  const tl = _mapXYToVB(bb.xmin, bb.ymax, vbW, vbH, 22);
  const br = _mapXYToVB(bb.xmax, bb.ymin, vbW, vbH, 22);
  svgRoot.appendChild(svg('rect', {
    x: tl[0], y: tl[1], width: br[0] - tl[0], height: br[1] - tl[1],
    rx: 4, ry: 4, fill: 'none', stroke: '#3a4055', 'stroke-width': 1,
    'stroke-dasharray': '4,4'
  }));
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
          ttl.appendChild(document.createTextNode(tr.behavior.toUpperCase() + ' · ' + k + '\nrebound = ' + fmt(tr.rebound_speed, 0) + ' mm/s\nKE retention = ' + (tr.ke_retention * 100).toFixed(0) + '%\nmax pen = ' + fmt(tr.max_pen, 2) + ' mm'));
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
  lblY.appendChild(document.createTextNode('KE impactor (mJ)'));
  root.appendChild(lblY);
  const lblX = svg('text', { x: pad.l + plotW / 2, y: H - 6, 'text-anchor': 'middle', fill: '#aab2cf', 'font-size': 10, 'font-family': 'JetBrains Mono' });
  lblX.appendChild(document.createTextNode('IE absorbed (= KE₀ − KE) (mJ)'));
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
    ttl.appendChild(document.createTextNode(k + ' · ' + t.behavior + '\nKE final = ' + fmt(t.ke[last], 2) + ' mJ\nIE = ' + fmt(t.init_ke - t.ke[last], 2)));
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
      ['REBOUND', fmt(tr.rebound_speed, 0) + ' mm/s'],
      ['MAX PEN', fmt(tr.max_pen, 2) + ' mm'],
      ['t₁ CONTACT', (tr.t_first_contact != null ? (tr.t_first_contact * 1000).toFixed(2) + ' ms' : '-')],
      ['KE RETAIN', (tr.ke_retention * 100).toFixed(0) + ' %']
    ];
    for (const r of rows) {
      kpi.appendChild(el('div', { class: 'iirow' }, [el('span', null, r[0]), el('b', null, r[1])]));
    }
  }
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
  initBounceVectorMap();
  initTrajectoryClustering();
  initPhaseDiagram();
  initContactTimeline();
  initTrajectoryBundle3D();
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
