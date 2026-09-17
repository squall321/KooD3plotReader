# sphere report.json (koo_sphere_report sidecar) → RevisionBundle 변환
"""sphere sidecar 어댑터.

소스 키 (실측 확인)
  results_summary[{run_folder, angle{name,roll,pitch,yaw,category},
                   parts{pid → {peak_stress, peak_strain, peak_g, peak_disp}}}]
  parts{pid → {part_name, group}}
  findings[{severity,title,detail,recommendation}]
  simulation_params / project_name / test_dir

sphere sidecar 에는 solver_quality 게이트가 없다. 따라서 trust 는 항상
ok=True / reason='no gate' — 없는 게이트를 있는 척하지 않는다.
"""
from __future__ import annotations

from ..models import RevisionBundle, Cell, Trust, severity

#: sphere 파트 지표 → 공통 지표 키
_METRIC_SRC = {
    "g": "peak_g", "s": "peak_stress", "e": "peak_strain", "d": "peak_disp",
    # 아래 5종은 sphere report.json 에 있을 때만 채워진다 (없으면 None).
    "s1": "peak_principal_stress", "s3": "min_principal_stress",
    "e1": "peak_principal_strain", "e3": "min_principal_strain",
    "evm": "peak_vm_strain",
}



def _num(v):
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return None


def to_bundle(raw: dict, path: str = "", label: str = "") -> RevisionBundle:
    runs = raw.get("results_summary")
    if not isinstance(runs, list):
        raise ValueError(f"sphere sidecar 에 results_summary 목록이 없습니다 — {path}")

    parts = {}
    for pid, info in (raw.get("parts") or {}).items():
        try:
            key = int(pid)
        except (TypeError, ValueError):
            continue
        name = (info or {}).get("part_name") if isinstance(info, dict) else None
        parts[key] = str(name) if name else f"PART_{key}"

    cells = []
    part_cells = {}
    angles = []
    for run in runs:
        if not isinstance(run, dict):
            continue
        ang = run.get("angle") or {}
        name = ang.get("name") or run.get("run_folder")
        if not name:
            continue
        key = str(name)
        roll, pitch, yaw = _num(ang.get("roll")), _num(ang.get("pitch")), _num(ang.get("yaw"))
        angles.append(
            {"name": key, "roll": roll, "pitch": pitch, "yaw": yaw,
             "category": ang.get("category") or "", "run_folder": run.get("run_folder")}
        )

        agg = {k: None for k in _METRIC_SRC}
        for pid, pdata in (run.get("parts") or {}).items():
            if not isinstance(pdata, dict):
                continue
            try:
                pid_i = int(pid)
            except (TypeError, ValueError):
                continue
            pname = parts.get(pid_i, f"PART_{pid_i}")
            metrics = {mk: _num(pdata.get(src)) for mk, src in _METRIC_SRC.items()}
            part_cells[(key, pname)] = metrics
            # 각도 셀 값 = 그 각도에서 **가장 나쁜** 파트의 값. 압축측(σ3/ε3)은
            # 음수라 max() 를 쓰면 가장 약한 압축이 최악으로 뒤집힌다
            # (실측: PCB -350 MPa 대신 FOAM -0.4 MPa 가 셀 값이 됐다).
            for mk, v in metrics.items():
                if v is None:
                    continue
                if agg[mk] is None or severity(v, mk) > severity(agg[mk], mk):
                    agg[mk] = v

        parts_txt = []
        for axis, val in (("r", roll), ("p", pitch), ("y", yaw)):
            if val is not None:
                parts_txt.append(f"{axis}{val:g}")
        cells.append(
            Cell(
                key=key,
                label=f"{key} ({', '.join(parts_txt)})" if parts_txt else key,
                category=ang.get("category") or "",
                roll=roll,
                pitch=pitch,
                yaw=yaw,
                metrics=agg,
                trust=Trust(True, "no gate"),
                behavior=None,
                energy={},
                extra={"run_folder": run.get("run_folder"), "num_states": run.get("num_states")},
            )
        )

    worst_g = max((c.metrics.get("g") or 0.0) for c in cells) if cells else None
    worst_s = max((c.metrics.get("s") or 0.0) for c in cells) if cells else None

    return RevisionBundle(
        label=label or "",
        kind="sphere",
        path=path,
        schema_version=raw.get("schema_version"),
        meta={
            "project": raw.get("project_name"),
            "test_dir": raw.get("test_dir"),
            "doe_strategy": raw.get("doe_strategy"),
            "simulation_params": dict(raw.get("simulation_params") or {}),
            "angular_spacing_deg": raw.get("angular_spacing_deg"),
            "sphere_coverage": raw.get("sphere_coverage"),
            "n_angles": len(cells),
        },
        # 사이드카가 적은 단위만 쓴다. 예전에는 없으면 MPa/mm 를 채워 넣었는데,
        # sphere 사이드카는 단위를 한 줄도 싣지 않았으므로 **모든** sphere 리비전이
        # 같은 라벨을 갖게 돼 단위 가드가 영영 뜰 수 없었다(SI 덱 Pa 와 MPa 덱을
        # 나란히 놓아도 응력 Δ% -99.9999% 가 '개선' 으로). 모르면 비워 둔다.
        unit_labels=dict(raw.get("unit_labels") or {}),
        parts=parts,
        positions=[],
        angles=angles,
        cells=cells,
        part_cells=part_cells,
        kpi={
            "n_cells": len(cells),
            "n_parts": len(parts),
            "total_runs": raw.get("total_runs"),
            "successful_runs": raw.get("successful_runs"),
            "failed_runs": raw.get("failed_runs"),
            "sphere_coverage": raw.get("sphere_coverage"),
            "worst_g": worst_g,
            "worst_s": worst_s,
        },
        trust={
            "n_cells": len(cells),
            "n_gated": 0,
            "n_ok": len(cells),
            "basis": "no gate (sphere sidecar 에 solver_quality 없음)",
        },
        findings=[dict(f) for f in (raw.get("findings") or []) if isinstance(f, dict)],
        provenance=dict(raw.get("provenance") or {}),
    )
