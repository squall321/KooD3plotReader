# 전각도 낙하 리포트(koo_sphere_report 의 report.json)를 해석 어휘 꾸러미로 바꾸는 어댑터
"""report.json 하나 → 캠페인 1 · 런 N · 파트 P(전 방향 포락) · 파트 응답 N×P · 접촉 정의 ·
하중 전달(런 × 접촉) · 하중 경로(파트 쌍 전 런 집계) · 핫스팟 · 소견.

report.json 에 없는 것은 캠페인 폴더에서 **있으면** 더 읽는다(없어도 꾸러미는 나온다).
- `output/<런>/DropSet.json` 의 part_yield → 안전율 (분석기와 같은 yield_map 모듈로 셈한다), drop_height
- 첫 런의 덱(DropSet.k) → 접촉 카드 종류·양쪽 파트 (흐름 빌더와 같은 덱 고르기 규칙), 재질, 초기 속도
- `output/s1_index.json` → 런마다 첫 접촉 시각·S1 해시

런 키는 DynaForge 리포트 반입과 같은 순서로 고른다 — 런 폴더, 없으면 방향 이름, 그것도 없으면
`run_<순번>`(parser.py `case_key`). 그래야 꾸러미의 런이 `impact_cases` 한 줄과 바로 이어진다.

값은 덱 단위 그대로 넘기고 꾸러미 작성기가 어휘 단위로 바꾼다(`package.Units`).
"""
from __future__ import annotations

import hashlib
import math
import statistics
from pathlib import Path

from . import common as C
from . import flows as F
from .package import Package, Units

_CATEGORIES = ("face", "edge", "corner", "fibonacci")

# report.json 파트 칸 → 어휘 속성. 앞 칸이 없으면 뒤 칸(옛 이름)을 본다.
_RESPONSE_KEYS = (
    (("peak_stress",), "peak_von_mises"),
    (("time_of_peak_stress",), "peak_von_mises_time"),
    (("peak_principal_stress", "peak_principal"), "peak_max_principal"),
    (("time_of_peak_principal",), "peak_max_principal_time"),
    (("min_principal_stress", "min_principal"), "min_principal"),
    # peak_strain 의 원천은 eff_plastic_strain CSV 다 — 이름만 옛것이다(json_report 주석)
    (("peak_plastic_strain", "peak_strain"), "peak_plastic_strain"),
    (("peak_vm_strain",), "peak_vm_strain"),
    (("peak_principal_strain",), "peak_max_principal_strain"),
    (("min_principal_strain",), "min_principal_strain"),
    (("peak_g",), "peak_g"),
    (("time_of_peak_g",), "peak_g_time"),
    (("peak_disp",), "peak_displacement"),
)
_ENERGY_KEYS = (("peak_ie", "peak_internal_energy"), ("peak_ie_time", "peak_internal_energy_time"),
                ("peak_ke", "peak_kinetic_energy"), ("peak_ke_time", "peak_kinetic_energy_time"),
                ("final_ie", "final_internal_energy"), ("final_ke", "final_kinetic_energy"))


def impact_dir(roll: float, pitch: float, yaw: float) -> tuple[float, float, float]:
    """기기 좌표의 낙하 방향 d = Rᵀ(0,0,−1), R = Rx(roll)·Ry(pitch)·Rz(yaw).

    리포트 JS `impactDirBody` 와 같은 식이다(1144런 덱의 *INITIAL_VELOCITY 와 내적 +1 로 검증된 것).
    """
    r, p, y = (math.radians(v or 0.0) for v in (roll, pitch, yaw))
    cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    return tuple(round(v, 9) + 0.0 for v in (cr * sp * cy - sr * sy, -sr * cy - cr * sp * sy, -cr * cp))


def response_props(pd: dict) -> dict:
    """report.json 의 런×파트 칸 → 어휘 속성(덱 단위). 없는 값은 넣지 않는다."""
    out = {}
    for srcs, dst in _RESPONSE_KEYS:
        for s in srcs:
            v = C.num(pd.get(s))
            if v is not None:
                out[dst] = v
                break
    e = pd.get("energy")
    if isinstance(e, dict):
        for s, dst in _ENERGY_KEYS:
            v = C.num(e.get(s))
            if v is not None:
                out[dst] = v
    return out


def find_kfile(run_dir: Path) -> Path | None:
    """흐름 빌더(sphere loader `_find_kfile`)와 같은 규칙 — DropSet.k 먼저, 없으면 첫 *.k."""
    for base in (run_dir, run_dir / "Output"):
        p = base / "DropSet.k"
        if p.exists():
            return p
    for base in (run_dir, run_dir / "Output"):
        ks = sorted(base.glob("*.k")) if base.exists() else []
        if ks:
            return ks[0]
    return None


def load_yields(test_dir: Path | None, yield_map_path: str, yield_stress: float, stress_label: str):
    """(파트별 한계 {PID: [YieldLimit]}, 기본 한계, evaluate, 출처, 안내) — 분석기와 같은 경로.

    koo_sphere_report 를 못 불러오면 안전율을 셈하지 않는다(다른 식으로 지어내지 않는다).
    """
    try:
        from koo_sphere_report import yield_map as YM
    except ImportError:
        return {}, None, None, "none", ["koo_sphere_report.yield_map 을 불러오지 못해 안전율을 셈하지 않았습니다"]
    limits: dict[int, list] = {}
    notes: list[str] = []
    source = "none"
    if test_dir is not None:
        py, _u, ns = YM.load_from_dropset(test_dir / "output")
        notes += ns
        if py:
            limits = {pid: v.limits for pid, v in py.items()}
            source = "dropset_part_yield"
    if yield_map_path:
        py, _u, ns = YM.load_from_file(yield_map_path)
        notes += ns
        limits = {pid: v.limits for pid, v in py.items()}
        source = "yield_map"
    default_lim, default_note = YM.default_limit(yield_stress, stress_label)
    if default_note:
        notes.append(default_note)
    if source == "none" and default_lim is not None:
        source = "cli_yield_stress"
    return limits, default_lim, YM.evaluate, source, notes


def load_s1_index(test_dir: Path | None) -> dict[str, dict]:
    """output/s1_index.json → {런 폴더: 곁파일}. 없으면 빈 dict."""
    if test_dir is None:
        return {}
    import json
    p = test_dir / "output" / "s1_index.json"
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out = {}
    for j in doc.get("runs") or []:
        rel = str(j.get("s1_json") or "")
        if rel and "error" not in j:
            out[Path(rel).parts[0]] = j
    return out


def first_dropset(test_dir: Path | None) -> dict:
    """output/ 아래 첫 **읽히는** DropSet.json (yield_map 과 같은 규칙). 없으면 빈 dict."""
    import json
    out = test_dir / "output" if test_dir is not None else None
    if out is None or not out.is_dir():
        return {}
    for run_dir in sorted(out.iterdir()):
        try:
            return json.loads((run_dir / "DropSet.json").read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError):
            continue
    return {}


def _sha256(path: Path | None) -> str:
    if path is None:
        return ""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build(report: dict, *, report_path: Path | None = None, test_dir: Path | None = None,
          yield_map_path: str = "", yield_stress: float = 0.0, contact_map=None) -> dict:
    """sphere report.json(dict) → 꾸러미 dict. 어휘와 안 맞으면 PackageError.

    `test_dir` 를 안 주면 report.json 의 test_dir 가 있을 때 그것을 쓴다.
    `contact_map` 을 주면 덱을 읽지 않는다(시험용).
    """
    if test_dir is None and report.get("test_dir"):
        cand = Path(report["test_dir"])
        test_dir = cand if cand.is_dir() else None

    us = report.get("unit_system")
    labels = report.get("unit_labels") or {}
    if isinstance(us, dict):
        units = Units(us.get("id"), deck_labels=labels,
                      note=us.get("note") or ("" if us.get("id") else "단위계 미검출"))
        g_factor = C.num(us.get("g_factor"))
    else:
        units = Units(None, note="report.json 에 단위계 기록이 없다(옛 산출물) — 값은 덱 단위 그대로다")
        g_factor = None

    pkg = Package(scenario_kind="drop_all_angle", units=units, adapter="sphere",
                  source_kind="koo_sphere_report/report.json",
                  source_file=report_path.name if report_path else "",
                  source_sha256=_sha256(report_path))

    limits, default_lim, evaluate, yield_source, yield_notes = load_yields(
        test_dir, yield_map_path, yield_stress, labels.get("stress", ""))
    s1 = load_s1_index(test_dir)

    # ── 파트 이름 ──
    names: dict[int, tuple[str, str]] = {}
    for pid_s, pi in (report.get("parts") or {}).items():
        try:
            pid = int(pid_s)
        except (TypeError, ValueError):
            continue
        nm = (pi or {}).get("part_name") or (pi or {}).get("name") or f"Part {pid}"
        names[pid] = (nm, (pi or {}).get("group") or "")

    # ── 런·응답 (덱 단위 값을 먼저 모은다 — 파트 포락이 그것으로 셈된다) ──
    results = [r for r in (report.get("results_summary") or report.get("results") or [])
               if isinstance(r, dict)]
    run_keys: dict[str, str] = {}      # 런 폴더 → 런 객체 키 (흐름이 폴더로 매달린다)
    case_of: list[str] = []            # results 순서대로의 런 키(case_key)
    rows: dict[int, list[tuple[str, dict]]] = {}
    speeds = []
    for r in results:
        ang = r.get("angle") or {}
        folder = str(r.get("run_folder") or "")
        case = folder or str(ang.get("name") or "") or f"run_{len(case_of)}"
        case_of.append(case)
        rk = f"run/{case}"
        if folder:
            run_keys[folder] = rk
        roll, pitch, yaw = (C.num(ang.get(k)) for k in ("roll", "pitch", "yaw"))
        dx = dy = dz = None
        if roll is not None and pitch is not None:
            dx, dy, dz = impact_dir(roll, pitch, yaw or 0.0)
        cat = str(ang.get("category") or "")
        s1j = s1.get(folder) or {}
        post = s1j.get("posture") or {}
        v0 = post.get("initial_velocity")
        if isinstance(v0, list) and len(v0) == 3 and all(C.num(c) is not None for c in v0):
            speeds.append(math.sqrt(sum(float(c) ** 2 for c in v0)))
        pkg.add("cae_run", rk, ang.get("name") or case, {
            "campaign": "campaign", "case_key": case, "run_folder": folder or None,
            "angle_name": ang.get("name") or None,
            "roll_deg": roll, "pitch_deg": pitch, "yaw_deg": yaw,
            "angle_category": cat if cat in _CATEGORIES else "unknown",
            "impact_dir_x": dx, "impact_dir_y": dy, "impact_dir_z": dz,
            "num_states": C.num(r.get("num_states")), "success": True,
            "first_contact_time": C.num(post.get("first_contact_s")),
            "s1_sha256": s1j.get("sha256") or None,
        })
        for pid_s, pd in (r.get("parts") or {}).items():
            try:
                pid = int(pid_s)
            except (TypeError, ValueError):
                continue
            resp = response_props(pd or {})
            if resp:
                rows.setdefault(pid, []).append((rk, resp))
                names.setdefault(pid, (f"Part {pid}", ""))

    # ── 덱 (첫 런) — 재질·초기 속도·접촉 ──
    kfile, keyword = None, None
    first = next((r for r in results if r.get("run_folder")), None)
    if test_dir is not None and first is not None:
        kfile = find_kfile(test_dir / "output" / str(first["run_folder"]))
    if kfile is not None:
        try:
            from koo_deep_report.core.keyword_parser import parse_keyword_file
            keyword = parse_keyword_file(kfile)
        except Exception:  # noqa: BLE001 — 덱을 못 읽어도 꾸러미는 나간다(재질·속도만 빈다)
            keyword = None

    # ── 파트 (전 방향 포락·판정) ──
    part_keys = {pid: f"part/{pid}" for pid in names}
    for pid in sorted(names):
        nm, grp = names[pid]
        lims = limits.get(pid) or ([default_lim] if default_lim is not None else [])
        env = C.envelope(rows.get(pid, []), lims, evaluate)
        pkg.add("cae_part", part_keys[pid], nm, {
            "campaign": "campaign", "part_id": pid, "name": nm, "part_group": grp or None,
            **C.material_props(keyword, pid), **env})

    # ── 파트 응답 ──
    for pid in sorted(rows):
        lims = limits.get(pid) or ([default_lim] if default_lim is not None else [])
        for rk, resp in rows[pid]:
            sf = C.run_safety_factor(resp, lims, evaluate)
            pkg.add("cae_part_response", f"resp/{rk[4:]}/{pid}", f"{names[pid][0]} @ {rk[4:]}",
                    {"run": rk, "part": part_keys[pid], **resp, "safety_factor": sf})

    # ── 핫스팟 ──
    for r, case in zip(results, case_of):
        for item in r.get("hotspot_clusters") or []:
            _add_hotspots(pkg, item, case, f"run/{case}", part_keys, names)

    # ── 접촉 정의·하중 전달·하중 경로 ──
    flows = report.get("energy_flows") or {}
    if contact_map is None and flows and kfile is not None:
        from koo_deep_report.core.contact_map import parse_contact_map
        contact_map = parse_contact_map(kfile, {pid: v[0] for pid, v in names.items()})
    contact_keys = F.add_contacts(pkg, contact_map, part_keys)
    F.add_transfers(pkg, flows, run_keys, part_keys, contact_keys)

    # ── 소견 ──
    C.add_findings(pkg, report.get("findings") or [], part_keys)

    # ── 캠페인 ──
    from datetime import datetime, timezone
    td = report.get("test_dir") or ""
    ds_height = C.num(((first_dropset(test_dir).get("initial_conditions") or {}).get("drop_height")))
    speed, height, drop_note = C.drop_condition(
        keyword, statistics.median(speeds) if speeds else None, ds_height,
        g_factor if units.system != "unknown" else None)
    pkg.add("cae_campaign", "campaign", report.get("project_name") or Path(td).name or "campaign", {
        "scenario_kind": "drop_all_angle",
        "test_dir": Path(td).name or None,
        "n_runs": C.num(report.get("total_runs")), "n_runs_ok": C.num(report.get("successful_runs")),
        "n_runs_failed": C.num(report.get("failed_runs")),
        "doe_strategy": report.get("doe_strategy") or None,
        "angular_spacing_deg": C.num(report.get("angular_spacing_deg")),
        "sphere_coverage": C.num(report.get("sphere_coverage")),
        "unit_system": units.system, "values_normalized": units.normalized,
        "unit_note": "; ".join(x for x in [units.note, *yield_notes, drop_note] if x) or None,
        "g_factor": g_factor,
        "impact_speed": speed, "drop_height": height,
        "yield_source": yield_source,
        "producer": "koo_sphere_report",
        "produced_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    return pkg.finish()


def _add_hotspots(pkg, item: dict, folder: str, run_key: str, part_keys: dict[int, str],
                  names: dict[int, tuple[str, str]]) -> None:
    """hotspot_clusters 한 항목(파트 × 기준 × 요소 종류) → 군집마다 cae_hotspot."""
    if not isinstance(item, dict):
        return
    try:
        pid = int(item.get("part_id"))
    except (TypeError, ValueError):
        return
    if pid not in part_keys:
        return
    crit = str(item.get("criterion") or "")
    et = str(item.get("element_type") or "solid")
    resp_key = f"resp/{folder}/{pid}"
    if not pkg.has("cae_part_response", resp_key):
        # 응답 값이 하나도 없는 파트에도 군집은 있을 수 있다 — 군집이 매달릴 응답을 세운다
        pkg.add("cae_part_response", resp_key, f"{names[pid][0]} @ {folder}",
                {"run": run_key, "part": part_keys[pid]})
    for c in item.get("clusters") or []:
        if not isinstance(c, dict) or C.num(c.get("rank")) is None:
            continue
        rank = int(c["rank"])
        ctr = c.get("center") if isinstance(c.get("center"), list) else [None, None, None]
        pkg.add("cae_hotspot", f"hs/{folder}/{pid}/{crit}/{et}/{rank}",
                f"{names[pid][0]} {crit} #{rank} @ {folder}", {
                    "response": resp_key, "criterion": crit or None, "element_type": et,
                    "rank": rank, "element_count": C.num(c.get("element_count")),
                    "center_x": C.num(ctr[0]) if len(ctr) > 0 else None,
                    "center_y": C.num(ctr[1]) if len(ctr) > 1 else None,
                    "center_z": C.num(ctr[2]) if len(ctr) > 2 else None,
                    "radius_enclosing": C.num(c.get("radius_enclosing")),
                    "stress_mean": C.num(c.get("stress_mean")), "stress_max": C.num(c.get("stress_max")),
                    "peak_element_id": C.num(c.get("peak_element_id")),
                    "peak_time": C.num(c.get("peak_time")),
                })
