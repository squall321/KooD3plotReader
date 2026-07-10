# payload 조립 오케스트레이터 — build_payload(report) 가 DATA dict 를 만든다 (html_report.py 분할)
from __future__ import annotations

import json
import math
import os
import statistics
from typing import Any

from ...models import (
    ImpactReport, PartInfo, Severity,
)
from .common import (  # noqa: F401 — re-export (분할 과도기)
    _esc, _Encoder, _safe, _pct, _r4, _sparse_matrix, _pid_cast,
    _downsample_indices, _argmax,
)
from .tiers import tier_for
from .core import (
    _impactor_dict, _energy_flow_dict, _build_mock_energy_flow, _build_device_geometry,
)
from .doe import _build_mock_doe, _build_doe_payload
from .analytics import _build_deep_payload
from .insights import _build_insights_payload
from .physics import _build_physics_payload


def _build_payload(report: ImpactReport, tier_override=None) -> dict:
    """Distill an ImpactReport into a compact JSON payload for embedding.

    The payload is intentionally schema-driven (small keys) so a 5000-row
    matrix stays under ~500 KB.

    Args:
        tier_override: emit.py 가 출력 모드와 payload 캡을 일치시키기 위해
            전달하는 TierPolicy (예: --chunked 강제 시 tier D 캡).
    """
    has_real = bool(report.results)

    # --- tier 정책 (P4) — 위치 수가 모든 다운샘플/캡/정밀도를 결정 ----------
    _n_pos_tier = sum(len(v or []) for v in (report.positions_by_face or {}).values())
    _tier = tier_override or tier_for(_n_pos_tier)
    STRESS_TS_MAX_PTS = _tier.stress_ts_pts
    PART_MOTION_MAX_PTS = _tier.part_motion_pts
    TRAJECTORY_MAX_PTS = _tier.trajectory_pts
    _VAL_DP = _tier.precision

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
        _imp_pid_lbl = getattr(getattr(report, "impactor", None), "part_id", None)
        _imp_pid_lbl = int(_imp_pid_lbl) if _imp_pid_lbl is not None else None

        def _part_label(p):
            # C3/L12: 이름 공란 부품이 표/축에 빈칸으로 렌더되던 문제 —
            # 임팩터는 명시 라벨, 그 외는 "Part <id>" fallback.
            if p.part_name:
                return p.part_name
            if _imp_pid_lbl is not None and int(p.part_id) == _imp_pid_lbl:
                return "Impactor"
            return f"Part {int(p.part_id)}"

        parts = [
            {"id": int(p.part_id), "name": _part_label(p),
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
            """Down-sample TimeSeriesData (times+max_values) for transport.

            true-peak 보존: peak 샘플은 splice 로 항상 유지 (P4).
            """
            if not ts or not ts.times or not ts.max_values:
                return None
            if STRESS_TS_MAX_PTS <= 0:
                return None  # tier D: envelope(스칼라 s)만 — 시계열 인라인 없음
            n = min(len(ts.times), len(ts.max_values))
            idx = _downsample_indices(n, STRESS_TS_MAX_PTS,
                                      peak_idx=_argmax(ts.max_values[:n]))
            return {
                "times":      [float(ts.times[i])      for i in idx],
                "max_values": [float(ts.max_values[i]) for i in idx],
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
        # tier 정책 (P4-스케일): flow 는 위치당 ~90KB — 338위치면 30MB.
        # 에너지 페이지는 한 번에 한 위치만 보므로 tier C/D 는 dissipated
        # 상위 K개(가장 강한 접촉)만 인라인. 나머지 위치를 s9 에서 고르면
        # refreshEnergyFlowForPos 가 조용히 현 상태를 유지한다 (흐름 없음).
        _ef_items = list(report.energy_flows.items())
        _topk = getattr(_tier, "energy_flow_topk", 0)
        if _topk > 0 and len(_ef_items) > _topk:
            _ef_items.sort(key=lambda kv: -(getattr(kv[1], "energy_dissipated", 0.0) or 0.0))
            _ef_items = _ef_items[:_topk]
        for pos_id, flow in _ef_items:
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

    # C2 (QA): 유효(접촉) 런 수 — s1 각주/파이프라인 소비용
    _sq_for_kpi = getattr(report, "solver_quality", None) or {}
    _n_valid_runs = sum(
        1 for a in _sq_for_kpi.values()
        if ((a or {}).get("summary") or {}).get("impact_visible") is True
    ) if _sq_for_kpi else None

    kpi = {
        "n_valid_runs": _n_valid_runs,
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
            "pos_id": worst.get("pos_id", ""),   # s1→s9 크로스링크 (P6)
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
        # P4: trajectory 는 종전 무캡(992 states × 25+ 위치가 payload 를 지배).
        # 공유 인덱스로 t/pos/vel/ke/contact 를 일관 다운샘플. "peak" = KE 최소
        # 시점(최대 에너지 전달 순간) — 접촉 물리의 특징점이 사라지지 않게.
        _ke_full = list(traj.ke or [])
        _ke_min_idx = None
        if _ke_full:
            _am = _argmax([-v for v in _ke_full[:n]])
            _ke_min_idx = _am
        # tier C/D (pts=0): 시계열 인라인 없음 — 요약 스칼라만 (청크는 P4-3).
        if TRAJECTORY_MAX_PTS <= 0:
            _tidx = []
        else:
            _tidx = _downsample_indices(n, TRAJECTORY_MAX_PTS, peak_idx=_ke_min_idx)
        pos_list_xyz = []
        vel_list_xyz = []
        for i in _tidx:
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
        _times_full = list(traj.times or [])
        _contact_full = list(traj.contact_engaged or [])
        rebound_xy = getattr(traj, "rebound_velocity_xy", (0.0, 0.0)) or (0.0, 0.0)
        trajectories[pos_id] = {
            "face": face_code,
            "x": _safe(x), "y": _safe(y),
            "t": [round(_safe(_times_full[i]), 8) for i in _tidx if i < len(_times_full)],
            "pos": pos_list_xyz,
            "vel": vel_list_xyz,
            "ke": [round(_safe(_ke_full[i]), _VAL_DP + 1) for i in _tidx if i < len(_ke_full)],
            "contact": [bool(_contact_full[i]) for i in _tidx if i < len(_contact_full)],
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

    # tier C/D: 인라인 series 를 worst-K 위치로 제한 (위치별 최악 peak_g 순위).
    # 나머지 위치의 요약 스칼라(summary_rows)는 그대로 — 곡선만 청크로 (P4-3).
    _topk_pos: set | None = None
    if _tier.part_motion_topk > 0:
        _pos_worst: dict[str, float] = {}
        for (p_pos, _p_pid), m in raw_motions.items():
            g = _safe(getattr(m, "peak_g", 0.0)) if m is not None else 0.0
            if g > _pos_worst.get(str(p_pos), 0.0):
                _pos_worst[str(p_pos)] = g
        _topk_pos = set(sorted(_pos_worst, key=_pos_worst.get, reverse=True)
                        [:_tier.part_motion_topk])

    # P4 t_ref dedup: 같은 run(pos_id)의 모든 부품은 같은 시간축을 공유한다.
    # 위치별 공유 인덱스 = 스트라이드 ∪ {마지막} ∪ {각 부품의 peak 인덱스}
    # → t 배열을 pos 당 1회만 출고 (t_ref[pos_id]), series 는 "tref" 로 참조.
    # 구 ``n // 600`` 버그(992//600=1, 다운샘플 미작동)는 ceil 스텝으로 교체.
    _by_pos: dict[str, list] = {}
    for key, motion in raw_motions.items():
        if motion is None:
            continue
        try:
            pos_id, pid = key
            pid = int(pid)
        except Exception:  # noqa: BLE001
            continue
        if PART_MOTION_MAX_PTS <= 0:
            continue  # tier D: 곡선 인라인 없음 (요약은 summary_rows 가 담당)
        if _topk_pos is not None and str(pos_id) not in _topk_pos:
            continue
        _by_pos.setdefault(str(pos_id), []).append((pid, motion))

    part_motion_t_ref: dict[str, list] = {}
    for pos_id, entries in _by_pos.items():
        n_pos = 0
        peaks: list[int] = []
        prepped = []
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
        if not prepped:
            continue
        idx = _downsample_indices(n_pos, PART_MOTION_MAX_PTS)
        keep = set(idx) | {p for p in peaks if 0 <= p < n_pos}
        idx = sorted(keep)
        _t_src = max(prepped, key=lambda e: e[4])  # 가장 긴 times 로 t_ref 구성
        part_motion_t_ref[pos_id] = [round(_safe(_t_src[2][i]), 8) for i in idx]
        for pid, motion, times, acc_mag, n in prepped:
            a_arr = [round(_safe(acc_mag[i]), _VAL_DP) if i < n else None
                     for i in idx]
            part_motion_series.append({
                "pos_id": pos_id,
                "part_id": pid,
                "part_name": getattr(motion, "part_name", "") or pname_lookup.get(pid, f"part_{pid}"),
                "tref": pos_id,
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
        "t_ref": part_motion_t_ref,
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
        from ...solver_quality import audit_run as _audit_run
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

    # H5-3: SAFE POSITIONS 기준 통일 — s1 KPI 와 s6 안전지도가 서로 다른
    # 기준(median×0.6 vs 평균/P75 합성)으로 다른 숫자를 내던 모순 제거.
    # deep 의 safe_drop_zone 이 유효하면 그것을 단일 소스로 삼는다.
    _deep_payload = _build_deep_payload(report, fft_bins=_tier.fft_bins)
    _sz = (_deep_payload or {}).get("safe_drop_zone") or {}
    if not _sz.get("empty") and _sz.get("safe_count") is not None:
        kpi["n_safe"] = int(_sz["safe_count"])
        kpi["n_safe_basis"] = "safe_drop_zone"

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
        "deep_analytics": _deep_payload,
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


# 공개 API alias — 분할 후 정식 명칭.
build_payload = _build_payload
