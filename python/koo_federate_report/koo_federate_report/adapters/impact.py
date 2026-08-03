# impact_payload.json (koo_impact_report sidecar) → RevisionBundle 변환
"""impact sidecar 어댑터.

소스 키 (실측 확인, schema_version 1)
  payload.positions[{pos_id, face, x, y}]
  payload.results[{pos_id, part_id, part_name, g, s, e, d}]
  payload.doe_analysis.position_metrics[pos_id]{peak_g_max, peak_stress_max, ...}
  payload.doe_analysis.trajectory_summary[pos_id]{ke_retention, behavior_class, ...}
  payload.solver_quality.per_position[pos_id]{pass_fail, summary.impact_visible, ...}
  payload.kpi / payload.unit_labels / payload.meta.provenance / payload.findings
  payload.parts[{id, name}]

trust 규칙 (계획서 §impact trust_gate)
  ok = (summary.impact_visible is not False) and pass_fail != 'FAIL'
  → 미접촉(no-contact) 이거나 solver 게이트 FAIL 인 위치는 Δ 계산에서 제외된다.
"""
from __future__ import annotations

from ..models import RevisionBundle, Cell, Trust, METRIC_KEYS, METRIC_COMPRESSIVE


def _num(v):
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _trust_for(sq_pos) -> Trust:
    if not isinstance(sq_pos, dict):
        return Trust(True, "no gate")
    summary = sq_pos.get("summary") or {}
    visible = summary.get("impact_visible")
    pass_fail = sq_pos.get("pass_fail")
    reasons = []
    if visible is False:
        reasons.append("impact_visible=False (접촉 미발생)")
    if pass_fail == "FAIL":
        flags = sq_pos.get("flags") or []
        reasons.append("solver_quality=FAIL" + (f" [{', '.join(map(str, flags))}]" if flags else ""))
    if reasons:
        return Trust(False, "; ".join(reasons))
    return Trust(True, f"pass_fail={pass_fail or 'n/a'}, impact_visible={visible}")


def _fallback_metrics(results_by_pos, pos_id):
    """position_metrics 가 없을 때 results 에서 위치별 최대치를 직접 집계."""
    out = {}
    for rec in results_by_pos.get(pos_id, []):
        for key in METRIC_KEYS:
            v = _num(rec.get(key))
            if v is None:
                continue
            cur = out.get(key)
            if cur is None:
                out[key] = v
                continue
            # 압축측(s3/e3)은 음수라 "최악" 이 최솟값이다.
            worse = (v < cur) if key in METRIC_COMPRESSIVE else (v > cur)
            if worse:
                out[key] = v
    return out


def to_bundle(raw: dict, path: str = "", label: str = "") -> RevisionBundle:
    payload = raw.get("payload")
    if not isinstance(payload, dict):
        raise ValueError(f"impact sidecar 에 payload 객체가 없습니다 — {path}")

    positions = payload.get("positions") or []
    results = payload.get("results") or []
    doe = payload.get("doe_analysis") or {}
    pos_metrics = doe.get("position_metrics") or {}
    traj = doe.get("trajectory_summary") or {}
    sq_per_pos = (payload.get("solver_quality") or {}).get("per_position") or {}
    meta = payload.get("meta") or {}

    # 임팩터(가해자)는 '부품' 이 아니다 — 본 impact 보고서가 이미 집계에서
    # 제외하는 규칙을 연합에서도 지킨다. 안 그러면 부품 추이/rank 표에
    # 임팩터가 섞여 순위 경쟁을 한다(실측: 24,272 G 로 15위).
    _imp_pid = (payload.get("part_motion") or {}).get("impactor_part_id")
    _imp_name = None
    if _imp_pid is not None:
        for _p in payload.get("parts") or []:
            if _p.get("id") == _imp_pid:
                _imp_name = _p.get("name")
                break

    # (cell_key, part_name) → metrics, 그리고 position_metrics fallback 용 인덱스
    part_cells = {}
    results_by_pos = {}
    excluded_impactor = 0
    for rec in results:
        pos_id = rec.get("pos_id")
        name = rec.get("part_name")
        if pos_id is None or not name:
            continue
        if (_imp_pid is not None and rec.get("part_id") == _imp_pid) or \
           (_imp_name and name == _imp_name):
            excluded_impactor += 1
            continue
        results_by_pos.setdefault(pos_id, []).append(rec)
        metrics = {k: _num(rec.get(k)) for k in ("g", "s", "e", "d")}
        prev = part_cells.get((pos_id, name))
        if prev is None:
            part_cells[(pos_id, name)] = metrics
        else:  # 같은 이름의 파트가 여러 pid 로 나뉜 경우 최대치 채택
            for k, v in metrics.items():
                if v is not None and (prev.get(k) is None or v > prev[k]):
                    prev[k] = v

    cells = []
    n_gated = 0
    for pos in positions:
        pos_id = pos.get("pos_id")
        if pos_id is None:
            continue
        pm = pos_metrics.get(pos_id) or {}
        metrics = {
            "g": _num(pm.get("peak_g_max")),
            "s": _num(pm.get("peak_stress_max")),
            "e": _num(pm.get("peak_strain_max")),
            "d": _num(pm.get("peak_disp_max")),
        }
        # 주응력/주변형률은 position_metrics 에 없다 — results 행에서 집계한다.
        # 상류에 없으면 그대로 None 이라 그 지표 비교는 미판정이 된다.
        for _k, _v in _fallback_metrics(results_by_pos, pos_id).items():
            if _k not in metrics or metrics.get(_k) is None:
                metrics[_k] = _v
        if all(v is None for v in metrics.values()):
            metrics = _fallback_metrics(results_by_pos, pos_id)

        tr = _trust_for(sq_per_pos.get(pos_id))
        if not tr.ok:
            n_gated += 1

        tj = traj.get(pos_id) or {}
        sq_summary = (sq_per_pos.get(pos_id) or {}).get("summary") or {}
        face = pos.get("face") or ""
        x, y = _num(pos.get("x")), _num(pos.get("y"))
        label_txt = f"{pos_id}"
        if x is not None and y is not None:
            label_txt = f"{pos_id} ({x:g}, {y:g})"

        cells.append(
            Cell(
                key=str(pos_id),
                label=label_txt,
                category=face,
                x=x,
                y=y,
                metrics=metrics,
                trust=tr,
                behavior=tj.get("behavior_class"),
                energy={
                    "ke_retention": _num(tj.get("ke_retention")),
                    "max_penetration_depth": _num(tj.get("max_penetration_depth")),
                    "diss_pct": _num(sq_summary.get("diss_pct")),
                },
                extra={
                    "worst_part_id_g": pm.get("worst_part_id_g"),
                    "worst_part_id_s": pm.get("worst_part_id_s"),
                    "pass_fail": (sq_per_pos.get(pos_id) or {}).get("pass_fail"),
                },
            )
        )

    parts = {}
    for p in payload.get("parts") or []:
        pid = p.get("id")
        name = p.get("name")
        if pid is None or not name:
            continue
        if _imp_pid is not None and pid == _imp_pid:
            continue                      # 임팩터는 부품 목록에서 제외
        parts[int(pid)] = str(name)

    unit_labels = payload.get("unit_labels") or (meta.get("sim_params") or {}).get("unit_labels") or {}

    return RevisionBundle(
        label=label or "",
        kind="impact",
        path=path,
        schema_version=raw.get("schema_version"),
        meta={
            "project": meta.get("project"),
            "test_dir": meta.get("test_dir"),
            "units": (meta.get("sim_params") or {}).get("units"),
            "grid": (meta.get("sim_params") or {}).get("grid"),
            "faces": payload.get("faces") or [],
            "generation_mode": meta.get("generation_mode"),
            "n_positions": len(positions),
        },
        unit_labels=dict(unit_labels),
        parts=parts,
        positions=[dict(p) for p in positions],
        angles=[],
        cells=cells,
        part_cells=part_cells,
        kpi=dict(payload.get("kpi") or {}),
        trust={
            "n_cells": len(cells),
            "n_gated": n_gated,
            "n_ok": len(cells) - n_gated,
            "basis": "impact_visible + solver_quality.pass_fail",
            "behavior_counts": dict(doe.get("behavior_class_counts") or {}),
        },
        findings=[dict(f) for f in (payload.get("findings") or []) if isinstance(f, dict)],
        provenance=dict(meta.get("provenance") or {}),
    )
