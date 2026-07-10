# payload INSIGHTS — 대칭/손상지수/리바운드/자동권고/접촉펄스/3D 궤적 (html_report.py 기계적 분할, 바이트 불변)
from __future__ import annotations

from ...models import (
    ImpactReport,
)
from .common import _pid_cast


def _pos_id(r):
    """PairResult 의 pos_id — 직접 속성이 없으면 .position.pos_id (H4 fix).

    getattr(r, "pos_id") 는 항상 None 이었음 (models.PairResult 에 해당 속성
    부재) — Symmetry/DamageIndex/auto_recommend 3개 패널이 조용히 죽어 있던
    원인. analytics.py 의 fallback 패턴과 동일.
    """
    pid = getattr(r, "pos_id", None)
    if pid is None:
        pid = getattr(getattr(r, "position", None), "pos_id", None)
    return pid


def _build_symmetry_insight(report):
    """Build symmetry & boundary effect payload by comparing mirror-pair peak_g."""
    import math
    import numpy as np

    results = getattr(report, "results", []) or []
    positions_by_face = getattr(report, "positions_by_face", {}) or {}

    # peak_g per pos_id: average across parts at that position
    pg_by_pos = {}
    for r in results:
        pid = _pos_id(r)
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
                            "pos_a": _pid_cast(key[0]),
                            "pos_b": _pid_cast(key[1]),
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
                            "pos_a": _pid_cast(key[0]),
                            "pos_b": _pid_cast(key[1]),
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
        pos = _pos_id(r)
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
            peaks.append((float(g), _pos_id(r), getattr(r, "part_id", None)))
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
            pid = _pos_id(r)
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
            pid = _pos_id(r)
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
