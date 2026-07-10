# payload DEEP analytics — FFT/SRS/safe-drop/PCA/anomaly/per-part drilldown (html_report.py 기계적 분할, 바이트 불변)
from __future__ import annotations

from ...models import (
    ImpactReport,
)
from .common import _pid_cast, _r4


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


def _build_fft_payload(report, max_bins: int = 128):
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
        ds_f, ds_a = _downsample_spectrum(top["freqs"], top["amps_norm"], max_bins=max_bins)
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
    # C3 fix: 임팩터 행 제외 — 미접촉 위치의 위반 사유가 "임팩터 자신의
    # 자유낙하 이동거리(peak_disp)" 가 되어 전면 at-risk 라는 무의미한
    # 지도가 되던 문제.
    _imp_pid = getattr(getattr(report, "impactor", None), "part_id", None)
    if _imp_pid is not None:
        _imp_pid = int(_imp_pid)
        results = [r for r in results
                   if int(getattr(r, "part_id", -1)) != _imp_pid]
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
    no_contact_count = 0

    # HIGH-1 (QA): 미접촉 런은 '응답이 작아서 안전' 이 아니라 '데이터 없음' —
    # safe 로 승격하면 같은 화면의 CRITICAL finding 과 정면 모순.
    _trajs = getattr(report, "impactor_trajectories", {}) or {}

    for (face, pos_id), rows in sorted(pos_map.items(), key=lambda kv: (str(kv[0][0]), kv[0][1])):
        _beh = getattr(_trajs.get(pos_id), "behavior_class", "") if _trajs.get(pos_id) else ""
        if _beh == "no-contact":
            no_contact_count += 1
            xy = coord_lookup.get((face, pos_id), (0.0, 0.0))
            positions_out.append({
                "pos_id": pos_id,
                "face": face,
                "x": round(xy[0], 6),
                "y": round(xy[1], 6),
                "safe": None,                    # 판정 불가 — JS 는 회색 렌더
                "status": "no-contact",
                "worst_metric": None,
                "worst_value": 0.0,
                "worst_part_id": None,
            })
            continue
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
            "status": "safe" if is_safe else "at-risk",
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
        "no_contact_count": no_contact_count,
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
        # M9: median/MAD robust z — analyzer 의 outlier 게이트와 동일 기준.
        # 종전 mean/std 는 outlier 자신이 σ 를 부풀려 z 를 희석 (같은 데이터에서
        # findings "outlier 9건" vs 이 패널 "1건" 모순의 원인).
        vals = np.array([r[key] for r in rows if r[key] is not None], dtype=float)
        if vals.size < 2:
            return None, None
        med = float(np.median(vals))
        mad = float(np.median(np.abs(vals - med)))
        sd = mad / 0.6745 if mad > 0 else 0.0
        return med, sd

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

    # Threshold (M9): analyzer 의 outlier 게이트와 동일한 고정 |z|>3.5.
    # 종전 max(2.5, P95(|z|)) 는 구조적으로 상위 ~5% 만 표시하는 자기제한 —
    # findings "9건" vs 이 패널 "1건" 모순의 두 번째 원인이었다.
    z_base = 3.5
    p95 = float(np.percentile(abs_z_pool, 95)) if abs_z_pool else 0.0
    threshold = z_base

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


def _build_deep_payload(report: ImpactReport, fft_bins: int = 128) -> dict:
    """Aggregate the six Section-06 advanced analyses into one payload.

    Returns an empty dict when no data is available; individual sub-keys
    may be empty dicts when their producer says so. The JS layer hides
    panels whose sub-key is empty.
    """
    deep: dict = {}
    deep["fft"] = _build_fft_payload(report, max_bins=fft_bins)
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
