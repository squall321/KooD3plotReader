# per-position 청크 번들 빌더 — tier C/D 의 드릴다운/청크 파일 데이터 (SOTA P4-3)
"""한 위치(pos_id)의 무거운 시계열을 하나의 번들 dict 로 묶는다.

용도 두 가지.
- tier C/D 청크 파일: ``report_data/pos_<id>.js`` (window.KOO_CHUNKS 주입)
- s9 per-position 드릴다운의 데이터 소스 (P6)

번들 스키마::

    {
      "pos_id": str,
      "t_ref": [...],                    # 공유 시간축 (part_motion)
      "series": [{part_id, part_name, a[], peak_g, ...}],
      "trajectory": {t[], pos[][3], vel[][3], ke[], contact[], ...스칼라},
    }
"""
from __future__ import annotations

from .common import _safe, _downsample_indices, _argmax


def build_position_bundle(report, pos_id: str,
                          motion_pts: int = 600, traj_pts: int = 400,
                          precision: int = 4) -> dict:
    """report 원본(또는 in-worker 축소본)에서 pos_id 한 위치의 번들 생성."""
    bundle: dict = {"pos_id": str(pos_id)}

    # --- part_motion: 공유 시간축 + per-part a 배열 --------------------------
    raw_motions = getattr(report, "part_motions", None) or {}
    entries = [(int(pid), m) for (p, pid), m in raw_motions.items()
               if str(p) == str(pos_id) and m is not None]
    prepped = []
    peaks: list[int] = []
    n_pos = 0
    for pid, motion in entries:
        times = list(getattr(motion, "times", []) or [])
        acc_mag = list(getattr(motion, "acc_mag", []) or [])
        if not times or not acc_mag:
            continue
        n = min(len(times), len(acc_mag))
        pk = _argmax(acc_mag[:n])
        if pk is not None:
            peaks.append(pk)
        prepped.append((pid, motion, times, acc_mag, n))
        n_pos = max(n_pos, n)
    if prepped:
        idx = sorted(set(_downsample_indices(n_pos, motion_pts))
                     | {p for p in peaks if 0 <= p < n_pos})
        _t_src = max(prepped, key=lambda e: e[4])
        bundle["t_ref"] = [round(_safe(_t_src[2][i]), 8) for i in idx]
        series = []
        for pid, motion, times, acc_mag, n in prepped:
            series.append({
                "part_id": pid,
                "part_name": getattr(motion, "part_name", "") or f"part_{pid}",
                "a": [round(_safe(acc_mag[i]), precision) if i < n else None
                      for i in idx],
                "peak_g": _safe(getattr(motion, "peak_g", 0.0)),
                "t_peak_g": _safe(getattr(motion, "t_peak_g", 0.0)),
                "peak_vel": _safe(getattr(motion, "peak_vel", 0.0)),
                "peak_disp": _safe(getattr(motion, "peak_disp", 0.0)),
            })
        bundle["series"] = series

    # --- impactor trajectory -------------------------------------------------
    traj = (getattr(report, "impactor_trajectories", None) or {}).get(pos_id)
    if traj is not None and getattr(traj, "times", None):
        n = len(traj.times)
        ke_full = list(traj.ke or [])
        ke_min = _argmax([-v for v in ke_full[:n]]) if ke_full else None
        tidx = _downsample_indices(n, traj_pts, peak_idx=ke_min)
        bundle["trajectory"] = {
            "t": [round(_safe(traj.times[i]), 8) for i in tidx],
            "pos": [[_safe(traj.pos_x[i] if i < len(traj.pos_x) else 0.0),
                     _safe(traj.pos_y[i] if i < len(traj.pos_y) else 0.0),
                     _safe(traj.pos_z[i] if i < len(traj.pos_z) else 0.0)]
                    for i in tidx],
            "vel": [[_safe(traj.vel_x[i] if i < len(traj.vel_x) else 0.0),
                     _safe(traj.vel_y[i] if i < len(traj.vel_y) else 0.0),
                     _safe(traj.vel_z[i] if i < len(traj.vel_z) else 0.0)]
                    for i in tidx],
            "ke": [round(_safe(ke_full[i]), precision + 1) for i in tidx
                   if i < len(ke_full)],
            "contact": [bool(traj.contact_engaged[i]) for i in tidx
                        if i < len(traj.contact_engaged or [])],
            "init_ke": _safe(traj.initial_ke),
            "final_ke": _safe(traj.final_ke),
            "ke_retention": _safe(traj.ke_retention),
            "behavior": getattr(traj, "behavior_class", "unknown") or "unknown",
        }
    return bundle
