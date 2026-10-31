# 런 하나(koo_deep_report) 분석 결과를 해석 어휘 꾸러미로 바꾸는 어댑터 — 리포트가 메모리에 든 결과에서 바로 낸다
"""analysis_result.json 이 런당 수십~수백 MB 라 다시 읽지 않는다. deep 리포트가 이미 읽어 둔
`SingleResult`(이력·모션·핫스팟)와 binout 에서 꾸러미를 짓는다.

값은 **이력(global_max·time_of_max)에서 직접** 꺼낸다. `PartSummary` 의 일부 칸(주응력·변형률·가속도)은
없을 때 0.0 으로 채워져 있어, 그것을 그대로 실으면 '잰 0' 으로 읽힌다.

런 키는 `single` 이다 — DynaForge 가 deep 리포트를 반입할 때 `impact_cases.case_key` 를 그렇게 쓴다
(parser.normalize_deep). 실제 런 폴더는 `run_folder` 에 있다.

단위계는 deep 이 판정하지 않으므로 여기서 sphere 와 같은 규칙으로 정한다 — 덱 *MAT 밀도 중앙값을
impact 검출기에 넣고, ton-mm-s 인데 해석 끝 시각이 0.5 이상이면(초 단위 낙하·충격 창은 수 ms)
시간 단위가 ms 일 수 있어 단정하지 않는다.
"""
from __future__ import annotations

import statistics
from datetime import datetime, timezone
from pathlib import Path

from . import common as C
from . import flows as F
from .package import Package, Units, write
from .sphere import _add_hotspots

_G0 = {"SI": 9.80665, "ton-mm-s": 9806.65, "g-mm-ms": 9.80665e-3}
_YIELD_SOURCE = {"mat_card": "mat_card", "manual": "yield_map"}


def detect_units(keyword, end_time) -> tuple[str, str]:
    """(단위계 id, 단서). 못 정하면 ('', 사유)."""
    dens = sorted(m.density for m in (getattr(keyword, "materials", None) or {}).values()
                  if (m.density or 0) > 0)
    if not dens:
        return "", "덱 *MAT 밀도를 읽지 못해 단위계를 판정하지 못했다"
    try:
        from koo_impact_report.loader import _detect_unit_system
    except Exception:  # noqa: BLE001
        return "", "단위계 검출기(koo_impact_report)를 불러오지 못했다"
    rho = dens[len(dens) // 2]
    uid = str((_detect_unit_system(rho) or {}).get("id") or "")
    if uid not in _G0:
        return "", f"덱 밀도 {rho:g} 로는 단위계를 판정할 수 없다"
    if uid == "ton-mm-s" and end_time is not None and end_time >= 0.5:
        return "", (f"덱 밀도({rho:g})는 ton-mm-s 를 가리키지만 해석 끝 시각이 {end_time:g} 라 시간 단위가 "
                    f"ms 일 수 있다 — 단정하지 않는다")
    return uid, ""


def run_folder_of(sim_path: Path) -> str:
    """<Run_…>/Output 이면 Run_… , 아니면 폴더 이름."""
    return sim_path.parent.name if sim_path.name == "Output" else sim_path.name


def build(result, *, flow=None, keyword=None) -> dict:
    """SingleResult → 꾸러미 dict. `flow`=(흐름 그래프, contact_map), `keyword`=KeywordData 를 주면
    다시 짓지 않는다(시험·재사용)."""
    si = result.sim_info
    d3 = result.d3plot_result
    meta = (d3.metadata if d3 else {}) or {}
    end_time = C.num(meta.get("end_time"))

    if keyword is None:
        try:
            from koo_deep_report.core.keyword_parser import find_and_parse_keyword
            keyword = find_and_parse_keyword(si.keyword or si.d3plot)
        except Exception:  # noqa: BLE001
            keyword = None
    uid, note = detect_units(keyword, end_time)
    units = Units(uid, note=note)
    g0 = _G0.get(uid)

    if flow is None:
        try:
            from koo_deep_report.core.energy_flow_csv import build_flow
            flow = build_flow(result.binout_data, si.keyword, d3plot_path=si.d3plot)
        except Exception:  # noqa: BLE001
            flow = None
    graph, contact_map = flow if flow else ({}, None)

    pkg = Package(scenario_kind="single_run", units=units, adapter="deep",
                  source_kind="koo_deep_report/SingleResult", source_file=str(si.d3plot or ""))

    folder = run_folder_of(Path(si.path))
    case = "single"
    rk = f"run/{case}"
    pkg.add("cae_run", rk, result.label or folder, {
        "campaign": "campaign", "case_key": case, "run_folder": folder or None,
        "num_states": C.num(meta.get("num_states")), "end_time": end_time,
        "success": si.normal_termination if isinstance(si.normal_termination, bool) else None,
        "analyzer_commit": meta.get("tool_commit") or None,
    })

    energy = {}
    for n in graph.get("nodes") or []:
        nid = str(n.get("node_id") or "")
        if nid.isdigit():
            energy[int(nid)] = n

    part_keys = {pid: f"part/{pid}" for pid in result.parts}
    sources = set()
    for pid in sorted(result.parts):
        ps = result.parts[pid]
        get = (lambda f: f(pid) if d3 else None)
        st, sr = get(d3.get_stress if d3 else None), get(d3.get_strain if d3 else None)
        s1, s3 = get(d3.get_max_principal if d3 else None), get(d3.get_min_principal if d3 else None)
        e1, e3 = get(d3.get_max_principal_strain if d3 else None), get(d3.get_min_principal_strain if d3 else None)
        evm = get(d3.get_vm_strain if d3 else None)
        mo = d3.get_motion(pid) if d3 else None
        en = energy.get(pid) or {}
        # MotionData.peak_acc_mag 는 열이 없어도 0.0 을 준다 — 열을 직접 본다
        acc = max(mo.acc_mag) if (mo is not None and mo.acc_mag) else None
        resp = {
            "peak_von_mises": st.global_max if st else None,
            "peak_von_mises_time": st.time_of_max if st else None,
            "peak_max_principal": s1.global_max if s1 else None,
            "peak_max_principal_time": s1.time_of_max if s1 else None,
            "min_principal": s3.global_min if s3 else None,
            "peak_plastic_strain": sr.global_max if sr else None,
            "peak_vm_strain": evm.global_max if evm else None,
            "peak_max_principal_strain": e1.global_max if e1 else None,
            "min_principal_strain": e3.global_min if e3 else None,
            "peak_displacement": ps.peak_disp_mag,
            "peak_g": acc / g0 if (acc is not None and g0) else None,
            "peak_internal_energy": C.num(en.get("peak_ie")),
            "peak_internal_energy_time": C.num(en.get("peak_ie_time")),
            "peak_kinetic_energy": C.num(en.get("peak_ke")),
            "peak_kinetic_energy_time": C.num(en.get("peak_ke_time")),
            "final_internal_energy": C.num(en.get("final_ie")),
            "final_kinetic_energy": C.num(en.get("final_ke")),
        }
        resp = {k: C.num(v) for k, v in resp.items() if C.num(v) is not None}
        lims, evaluate = [], None
        if (ps.stress_limit or 0) > 0:
            try:
                from koo_sphere_report import yield_map as YM
                lims, evaluate = [YM.YieldLimit(ps.stress_limit, YM.VON_MISES, ps.stress_source)], YM.evaluate
                sources.add(_YIELD_SOURCE.get(ps.stress_source, "yield_map"))
            except ImportError:
                pass
        rows = [(rk, resp)] if resp else []
        env = C.envelope(rows, lims, evaluate, g_rule=False)
        pkg.add("cae_part", part_keys[pid], ps.part_name or f"Part {pid}", {
            "campaign": "campaign", "part_id": pid, "name": ps.part_name or None,
            **C.material_props(keyword, pid), **env})
        if resp:
            pkg.add("cae_part_response", f"resp/{case}/{pid}", f"{ps.part_name or pid} @ {folder}",
                    {"run": rk, "part": part_keys[pid], **resp,
                     "safety_factor": C.run_safety_factor(resp, lims, evaluate)})

    names = {pid: (p.part_name or f"Part {pid}", "") for pid, p in result.parts.items()}
    for item in (d3.hotspot_clusters if d3 else None) or []:
        _add_hotspots(pkg, item, case, rk, part_keys, names)

    contact_keys = F.add_contacts(pkg, contact_map, part_keys)
    F.add_transfers(pkg, {case: graph} if graph else {}, {case: rk}, part_keys, contact_keys)
    speed, _, _ = C.drop_condition(keyword, None, None, g0)

    pkg.add("cae_campaign", "campaign", result.label or folder, {
        "scenario_kind": "single_run", "n_runs": 1,
        "n_runs_ok": 0 if si.normal_termination is False else 1,
        "n_runs_failed": 1 if si.normal_termination is False else 0,
        "unit_system": units.system, "values_normalized": units.normalized,
        "unit_note": units.note or None, "g_factor": g0, "impact_speed": speed,
        "yield_source": sorted(sources)[0] if len(sources) == 1 else ("mat_card" if sources else "none"),
        "producer": "koo_deep_report",
        "produced_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    return pkg.finish()


def write_for_result(result, output_dir: Path) -> Path:
    """deep 리포트 산출 폴더에 ontology.json 을 쓴다."""
    return write(build(result), Path(output_dir) / "ontology.json")
