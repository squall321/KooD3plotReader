# 전위치 부분충격 리포트(koo_impact_report 의 report json + impact_payload.json)를 해석 어휘 꾸러미로 바꾸는 어댑터
"""report json 이 런×파트 최대값·면·위치·충격체·단위·해석 품질을, 같은 폴더의 `impact_payload.json`
이 주응력(σ1·σ3)·에너지 흐름·첫 접촉 시각을 갖는다. payload 가 없으면 그 부분만 빠진다.

sphere 와 다른 점
- 런 키는 위치 이름(pos_id, 예 F5_DOE_001) — 리포트가 그 이름으로 부른다. 런 폴더는 따로 싣는다.
- `peak_g` 가 **덱 가속도 단위**(mm/s² 등)다. 1 G(표준중력 9.80665 m/s²)를 덱 단위로 바꿔 나눈다.
  단위계를 모르면 G 로 못 바꾸니 싣지 않는다.
- 판정은 응력 안전율만 — 부분충격 분석기는 가속도 절대 기준을 두지 않는다.
- payload 의 흐름은 위치가 100개를 넘으면 소산 에너지 상위 40개만 남는다 — 하중 경로의
  `engage_ratio` 분모는 흐름이 있는 런 수다.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from . import common as C
from . import flows as F
from .package import Package, Units, paired_html
from .sphere import _sha256, find_kfile

#: 1 G 를 덱 가속도 단위로 — 표준중력 9.80665 m/s².
_G0 = {"SI": 9.80665, "ton-mm-s": 9806.65, "g-mm-ms": 9.80665e-3, "ton-mm-ms": 9.80665e-3}
_SQ = ("PASS", "WARN", "FAIL", "UNKNOWN")


def _edge(e: dict) -> dict:
    """payload 의 줄인 엣지 키 → 빌더 중립 키(flows 가 읽는 이름)."""
    return {"src": e.get("src"), "dst": e.get("dst"), "contact_id": e.get("cid", -1),
            "name": e.get("name", ""), "confidence": e.get("conf"),
            "peak_force": e.get("peak_f"), "total_impulse": e.get("total_imp"),
            "total_work": e.get("total_w")}


def load_payload(report_path: Path | None) -> dict:
    """report json 옆의 impact_payload.json 의 payload. 없거나 못 읽으면 빈 dict."""
    if report_path is None:
        return {}
    p = report_path.with_name("impact_payload.json")
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc.get("payload") or {} if isinstance(doc, dict) else {}


def build(report: dict, *, report_path: Path | None = None, payload: dict | None = None,
          contact_map=None, html_path: Path | None = None) -> dict:
    """impact report json(dict) → 꾸러미 dict. 어휘와 안 맞으면 PackageError."""
    sp = report.get("sim_params") or {}
    unit_id = str(sp.get("units") or "")
    labels = sp.get("unit_labels") or {}
    units = Units(unit_id, deck_labels={k: v for k, v in labels.items() if v},
                  note="" if unit_id else "단위계 미검출 — 값은 덱 단위 그대로, 가속도는 G 로 못 바꿔 싣지 않았다")
    g0 = _G0.get(unit_id)
    if payload is None:
        payload = load_payload(report_path)

    pkg = Package(scenario_kind="impact_all_position", units=units, adapter="impact",
                  source_kind="koo_impact_report/report.json",
                  source_file=report_path.name if report_path else "",
                  source_sha256=_sha256(report_path),
                  html_path=html_path if html_path is not None else paired_html(report_path))

    # ── 항복 한계: 리포트가 쓴 파트별 값(덱 단위, *MAT 카드) — 분석기와 같은 evaluate ──
    yields = {}
    for k, v in (sp.get("yield_stress_by_part") or {}).items():
        try:
            pid, sy = int(k), float(v)
        except (TypeError, ValueError):
            continue
        if sy > 0:
            yields[pid] = sy
    evaluate, mk_limit = None, None
    if yields:
        try:
            from koo_sphere_report import yield_map as YM
            evaluate = YM.evaluate
            def mk_limit(sy):
                return YM.YieldLimit(sy, YM.VON_MISES, "yield_stress_by_part")
        except ImportError:
            yields = {}

    # ── 파트 ──
    names: dict[int, tuple[str, str]] = {}
    for p in report.get("parts") or []:
        try:
            pid = int(p.get("part_id"))
        except (TypeError, ValueError):
            continue
        names[pid] = (p.get("part_name") or f"Part {pid}", p.get("group") or "")

    # ── 런 (위치) ──
    faces = {f.get("code"): f for f in report.get("faces") or [] if isinstance(f, dict)}
    sq = report.get("solver_quality") or {}
    traj = payload.get("trajectories") or {}
    run_keys: dict[str, str] = {}
    run_dirs: list[Path] = []
    have_rows = {str(r.get("pos_id")) for r in report.get("results") or [] if isinstance(r, dict)}
    for face_code, poss in (report.get("positions_by_face") or {}).items():
        for pos in poss or []:
            pid_s = str(pos.get("pos_id") or "")
            if not pid_s:
                continue
            rk = f"run/{pid_s}"
            run_keys[pid_s] = rk
            rd = str(pos.get("run_dir") or "")
            if rd:
                run_dirs.append(Path(rd))
            fc = faces.get(pos.get("face") or face_code) or {}
            q = (sq.get(pid_s) or {}).get("pass_fail")
            pkg.add("cae_run", rk, pid_s, {
                "campaign": "campaign", "case_key": pid_s, "run_folder": Path(rd).name or None,
                "impact_face": str(pos.get("face") or face_code) or None,
                "impact_x": C.num(pos.get("x")), "impact_y": C.num(pos.get("y")),
                "roll_deg": C.num(fc.get("roll")), "pitch_deg": C.num(fc.get("pitch")),
                "yaw_deg": C.num(fc.get("yaw")),
                "num_states": C.num(sp.get("n_states")),
                "success": pid_s in have_rows,
                "solver_quality": str(q).upper() if str(q).upper() in _SQ else None,
                "first_contact_time": C.num((traj.get(pid_s) or {}).get("t_first_contact")),
            })

    # ── 파트 응답: report 줄 + payload 줄(σ1·σ3·주변형률) ──
    extra = {}
    for r in payload.get("results") or []:
        if isinstance(r, dict):
            extra[(str(r.get("pos_id")), r.get("part_id"))] = r
    rows: dict[int, list[tuple[str, dict]]] = {}
    for r in report.get("results") or []:
        if not isinstance(r, dict):
            continue
        pos_id, pid = str(r.get("pos_id")), r.get("part_id")
        if pos_id not in run_keys or not isinstance(pid, int):
            continue
        x = extra.get((pos_id, pid)) or {}
        g = C.num(r.get("peak_g"))
        resp = {
            "peak_von_mises": C.num(r.get("peak_stress")),
            "peak_plastic_strain": C.num(r.get("peak_strain")),       # 원천이 eff_plastic_strain
            "peak_displacement": C.num(r.get("peak_disp")),
            "peak_g": g / g0 if (g is not None and g0) else None,
            "peak_max_principal": C.num(x.get("s1")), "min_principal": C.num(x.get("s3")),
            "peak_max_principal_strain": C.num(x.get("e1")), "min_principal_strain": C.num(x.get("e3")),
            "peak_vm_strain": C.num(x.get("evm")),
        }
        resp = {k: v for k, v in resp.items() if v is not None}
        if resp:
            rows.setdefault(pid, []).append((run_keys[pos_id], resp))
            names.setdefault(pid, (f"Part {pid}", ""))

    # 덱(첫 위치의 런) — 재질·접촉. 위치마다 충격 위치만 다르고 모델은 같다.
    kfile, keyword = None, None
    for rd in run_dirs[:1]:
        kfile = find_kfile(rd)
    if kfile is not None:
        try:
            from koo_deep_report.core.keyword_parser import parse_keyword_file
            keyword = parse_keyword_file(kfile)
        except Exception:  # noqa: BLE001 — 덱을 못 읽어도 꾸러미는 나간다
            keyword = None

    part_keys = {pid: f"part/{pid}" for pid in names}
    for pid in sorted(names):
        nm, grp = names[pid]
        lims = [mk_limit(yields[pid])] if pid in yields else []
        env = C.envelope(rows.get(pid, []), lims, evaluate, g_rule=False)
        pkg.add("cae_part", part_keys[pid], nm, {
            "campaign": "campaign", "part_id": pid, "name": nm, "part_group": grp or None,
            **C.material_props(keyword, pid), **env})
    for pid in sorted(rows):
        lims = [mk_limit(yields[pid])] if pid in yields else []
        for rk, resp in rows[pid]:
            pkg.add("cae_part_response", f"resp/{rk[4:]}/{pid}", f"{names[pid][0]} @ {rk[4:]}",
                    {"run": rk, "part": part_keys[pid], **resp,
                     "safety_factor": C.run_safety_factor(resp, lims, evaluate)})

    # ── 접촉 정의·하중 전달·하중 경로 ──
    flows = {pos: {"edges": [_edge(e) for e in (g.get("edges") or [])],
                   "depth_map": g.get("depth_map") or {}}
             for pos, g in (payload.get("energy_flows") or {}).items() if isinstance(g, dict)}
    if contact_map is None and flows and kfile is not None:
        from koo_deep_report.core.contact_map import parse_contact_map
        contact_map = parse_contact_map(kfile, {pid: v[0] for pid, v in names.items()})
    contact_keys = F.add_contacts(pkg, contact_map, part_keys)
    F.add_transfers(pkg, flows, run_keys, part_keys, contact_keys)

    C.add_findings(pkg, report.get("findings") or [], part_keys)

    imp = report.get("impactor") or {}
    v0 = imp.get("initial_velocity") or sp.get("impactor_v0")
    speed = None
    if isinstance(v0, list) and len(v0) == 3 and all(C.num(c) is not None for c in v0):
        speed = math.sqrt(sum(float(c) ** 2 for c in v0))
    prov = report.get("provenance") or {}
    td = report.get("test_dir") or ""
    n_pos = len(run_keys)
    n_fail = C.num(sp.get("n_failed"))
    from datetime import datetime, timezone
    pkg.add("cae_campaign", "campaign", report.get("project_name") or Path(td).name or "campaign", {
        "scenario_kind": "impact_all_position", "test_dir": Path(td).name or None,
        "n_runs": n_pos, "n_runs_failed": n_fail,
        "n_runs_ok": (n_pos - n_fail) if n_fail is not None else None,
        "doe_strategy": sp.get("doe_kind") or (report.get("doe_config") or {}).get("kind") or None,
        "unit_system": units.system, "values_normalized": units.normalized,
        "unit_note": units.note or None, "g_factor": g0,
        "impactor_part_id": C.num(imp.get("part_id")), "impact_speed": speed,
        "yield_source": "mat_card" if yields else "none",
        "producer": "koo_impact_report",
        "producer_version": prov.get("module_version") or prov.get("tool_version") or None,
        "produced_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    return pkg.finish()
