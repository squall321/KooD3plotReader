# payload PHYSICS — 응력파 속도/반발계수 맵/회복·감쇠/최악 조합 (html_report.py 기계적 분할, 바이트 불변)
from __future__ import annotations

from .analytics import _fft_dominant_freq
from .common import _r4


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
    # M10: Δt→0 발산 샘플 + 미접촉 런(노이즈 피크)이 mean 을 지배해
    # 190,400 m/s 같은 물리 불가능 수치가 전시되던 문제 — sanity 게이트.
    V_APP_CEIL_M_S = 12000.0   # 고체 종파 상한(다이아몬드급) — 이 위는 Δt 해상도 부족
    n_dropped_ceil = 0
    n_dropped_nocontact = 0
    samples_by_part: dict[int, list[tuple[float, float]]] = {}  # part_id -> [(v_app m/s, dt s)]
    for (pos_id, part_id), pm in part_motions.items():
        if pm is None:
            continue
        traj = trajs.get(pos_id)
        if traj is None:
            continue
        if getattr(traj, "behavior_class", "") == "no-contact":
            n_dropped_nocontact += 1
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
        if v_m_s > V_APP_CEIL_M_S:
            n_dropped_ceil += 1
            continue  # Δt 해상도 부족 — 물리 불가능 겉보기 속도
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

    # M10: 대표값/정렬은 median — 발산 잔존 샘플의 mean 왜곡 회피
    per_part.sort(key=lambda d: (d["median_v_app"] if d["median_v_app"] is not None else -1.0), reverse=True)
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

    summary["n_dropped_v_ceiling"] = n_dropped_ceil
    summary["n_dropped_no_contact"] = n_dropped_nocontact
    summary["v_app_ceiling_m_s"] = V_APP_CEIL_M_S
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

        # M8 후속: 미접촉 런의 e=1.0 은 반발이 아니라 '접촉 없음' — 통계 제외
        # (지도에는 behavior_class 로 회색 렌더 유지).
        if e_clamped is not None and (behavior or "") != "no-contact":
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
            valid_rows = [r for r in per_position
                          if r["e"] is not None
                          and r.get("behavior_class") != "no-contact"]
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
