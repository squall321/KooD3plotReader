# payload core — impactor/energy-flow dict + mock + device geometry (html_report.py 기계적 분할, 바이트 불변)
from __future__ import annotations

import math

from ...models import (
    EnergyFlow, ImpactReport, ImpactorSpec,
)
from .common import _safe


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
        "geometry_source": getattr(imp, "geometry_source", ""),
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
            "name": getattr(e, "name", ""),
            "conf": getattr(e, "confidence", 1.0),
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
