# payload DOE — 위치별 응답 지도/failure risk/corr/TOA/IDW/pareto/energy partition (html_report.py 기계적 분할, 바이트 불변)
from __future__ import annotations

import statistics

from ...models import (
    ImpactReport,
)
from .common import _r4, _safe


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
