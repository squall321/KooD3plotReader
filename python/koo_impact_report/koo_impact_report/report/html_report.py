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


from .payload.common import (  # noqa: F401 — re-export (분할 과도기)
    _esc, _Encoder, _safe, _pct, _r4, _sparse_matrix, _pid_cast,
)
# ---------------------------------------------------------------------------
# Payload assembly
# ---------------------------------------------------------------------------


from .payload.core import (  # noqa: F401 — re-export (분할 과도기)
    _impactor_dict,
    _energy_flow_dict,
    _build_mock_energy_flow,
    _build_device_geometry,
)


from .payload.doe import (  # noqa: F401 — re-export (분할 과도기)
    _build_mock_doe,
    _build_failure_risk_payload,
    _build_corr_network_payload,
    _build_toa_payload,
    _build_idw_predictor_payload,
    _build_pareto_severity_payload,
    _build_energy_partition_payload,
    _build_doe_payload,
)


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
    # 구조화 로드 진단 (P1b) — binout 실패/런 로드 실패/impactor 불일치 등.
    # JS 배지·Finding 승격의 원천 데이터.
    meta["load_issues"] = list(getattr(report, "load_issues", []) or [])
    # provenance 는 CLI 가 채웠을 때만 노출 — 빈 dict 키를 만들지 않아
    # loader 직접 호출 경로(골든 테스트)의 payload 바이트가 불변 (P2-5).
    _prov = getattr(report, "provenance", None)
    if _prov:
        meta["provenance"] = dict(_prov)

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

    # --- solver_quality: glstat 기반 energy-balance audit per DOE ----------
    # 각 ImpactPosition.run_dir 의 Output/glstat 를 audit_run() 으로 파싱 →
    # {pos_id: {pass_fail, summary, flags, ...}}. 한 run 당 ~10 ms (작은 파일).
    # P0/P1 의 trust signal 들을 보강하는 가장 결정적 출처.
    # P2-4: DOE 로더는 워커에서 병렬 감사해 report.solver_quality 를 채운다 —
    # 채워져 있으면 그대로 소비, 비어 있으면(face-tree 경로 등) 직렬 fallback.
    try:
        from ..solver_quality import audit_run as _audit_run
    except Exception:
        _audit_run = None
    solver_quality_per_pos: dict[str, dict] = dict(
        getattr(report, "solver_quality", None) or {}
    )
    if not solver_quality_per_pos and _audit_run is not None:
        for face_code, positions_list in (report.positions_by_face or {}).items():
            for pos in positions_list or []:
                rd = getattr(pos, "run_dir", None)
                if rd is None:
                    continue
                # Sub-runs typically have Output/glstat. dynain 단계 폴더(DynamicRelaxation/)는 제외.
                gp = rd / "Output" / "glstat" if hasattr(rd, "__truediv__") else None
                if gp is None:
                    continue
                # pos.pos_id 가 보통 "F5_DOE_001" 형식이므로 face_code 가 이미 prefix.
                # 중복 'F5_' 방지: pos_id 가 face_code 로 시작하면 그대로, 아니면 합성.
                _raw_pid = str(getattr(pos, "pos_id", "") or "")
                if _raw_pid.startswith(f"{face_code}_") or _raw_pid.startswith(face_code):
                    pos_key = _raw_pid
                else:
                    pos_key = f"{face_code}_{_raw_pid}" if _raw_pid else face_code
                try:
                    solver_quality_per_pos[pos_key] = _audit_run(gp)
                except Exception:
                    solver_quality_per_pos[pos_key] = {"available": False, "pass_fail": "UNKNOWN", "flags": ["parser-error"]}
    # 집계 — verdict 분포 + 평균 drift.
    sq_summary = {"pass": 0, "warn": 0, "fail": 0, "unknown": 0, "n": len(solver_quality_per_pos)}
    te_drifts: list[float] = []
    hg_fracs: list[float] = []
    sl_fracs: list[float] = []
    diss_pcts: list[float] = []
    impact_visible_count = 0
    for sq in solver_quality_per_pos.values():
        v = (sq or {}).get("pass_fail", "UNKNOWN")
        if v == "PASS":   sq_summary["pass"] += 1
        elif v == "WARN": sq_summary["warn"] += 1
        elif v == "FAIL": sq_summary["fail"] += 1
        else:             sq_summary["unknown"] += 1
        s = (sq or {}).get("summary", {}) or {}
        if s.get("impact_visible"):
            impact_visible_count += 1
        for arr, key in ((te_drifts, "te_drift_pct"), (hg_fracs, "hg_fraction_pct"),
                         (sl_fracs, "sl_fraction_pct"), (diss_pcts, "diss_pct")):
            v2 = s.get(key)
            # bool 은 int 의 서브클래스 — 명시적으로 제외 (isinstance(True,int)==True)
            if isinstance(v2, (int, float)) and not isinstance(v2, bool):
                arr.append(float(v2))
    def _med(arr: list[float]) -> float | None:
        if not arr:
            return None
        arr2 = sorted(arr)
        return arr2[len(arr2) // 2]
    sq_summary.update({
        "te_drift_pct_median":      _med(te_drifts),
        "hg_fraction_pct_median":   _med(hg_fracs),
        "sl_fraction_pct_median":   _med(sl_fracs),
        # diss_pct 는 impact_visible=True 인 런의 값만 (solver_quality 가
        # non-visible 런에 None 을 주므로 위 isinstance 필터가 자동 제외).
        "diss_pct_median":          _med(diss_pcts),
        "impact_visible_count":     impact_visible_count,
    })

    # 진짜 glstat 기반 diss_pct 가 있으면 KPI ENERGY DISSIPATED 도 업데이트.
    # (이전: Mock 차단 후 None → "—N/A" 표시. 이제 glstat 평균으로 실제 값.)
    sq_median_diss = sq_summary.get("diss_pct_median")
    if sq_median_diss is not None and kpi.get("diss_pct") is None:
        kpi["diss_pct"] = round(float(sq_median_diss), 1)

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
        # solver_quality: glstat 기반 (per-DOE + 집계)
        "solver_quality": {
            "per_position": solver_quality_per_pos,
            "summary": sq_summary,
        },
        # None disables the conservation-tolerance banner; set to a percent
        # (e.g. 5.0) to enable the residual check.
        "energy_conservation_tolerance": None,
    }


# ---------------------------------------------------------------------------
# HTML template — CSS
# ---------------------------------------------------------------------------

from .assets.css import _CSS


from .assets.topbar import _build_topbar  # noqa: F401 — re-export (분할 과도기)


from .sections.s1_overview import _PAGE1  # noqa: F401
from .sections.s2_inspector import _PAGE2  # noqa: F401
from .sections.s3_verdict import _PAGE3  # noqa: F401
from .sections.s4_part_g import _PAGE4  # noqa: F401
from .sections.s5_doe import _PAGE5  # noqa: F401
from .sections.s6_deep import _PAGE6  # noqa: F401
from .sections.s7_insights import _PAGE7  # noqa: F401
from .sections.s8_physics import _PAGE8  # noqa: F401










# ---------------------------------------------------------------------------
# JavaScript template — large but self-contained
# ---------------------------------------------------------------------------

from .assets.js_core import (  # noqa: F401
    _JS_HEAD, _JS_WIRING, _JS_TABS, _JS_LAZY, _JS_TAIL,
)
from .sections.s1_overview import _JS_S1  # noqa: F401
from .sections.s2_inspector import _JS_S2  # noqa: F401
from .sections.s3_verdict import _JS_S3  # noqa: F401
from .sections.s4_part_g import _JS_S4  # noqa: F401
from .sections.s5_doe import _JS_TRAJ, _JS_S5_DOE, _JS_S5_MAIN  # noqa: F401
from .sections.s6_deep import _JS_S6  # noqa: F401
from .sections.s7_insights import _JS_S7  # noqa: F401
from .sections.s8_physics import _JS_S8  # noqa: F401

# 원본 파일 순서 보존 조립 — 1단계 불변식: join == 분할 전 _JS 바이트 동일.
_JS = "".join((
    _JS_HEAD, _JS_S1, _JS_S2, _JS_S3, _JS_WIRING, _JS_TRAJ, _JS_S4,
    _JS_S5_DOE, _JS_S6, _JS_S7, _JS_S8, _JS_TABS, _JS_S5_MAIN,
    _JS_LAZY, _JS_TAIL,
))


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
