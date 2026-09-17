"""Generate single-simulation HTML report."""
from __future__ import annotations
import json
import math
from datetime import datetime
from pathlib import Path

from .models import SingleResult, PartSummary


def generate_html(result: SingleResult, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    html = _build_html(result, output_path.parent)
    output_path.write_text(html, encoding="utf-8")


# ---------------------------------------------------------------------------
# Top-level builder
# ---------------------------------------------------------------------------

def _build_html(result: SingleResult, report_dir: Path) -> str:
    dr = result.d3plot_result
    gl = result.glstat_data
    bn = result.binout_data
    si = result.sim_info

    # Determine which tabs to show
    has_stress = dr is not None and (dr.stress or dr.strain)
    has_motion = dr is not None and bool(dr.motion)
    has_energy = gl is not None and bool(gl.t)
    has_contact = bn is not None and (bool(bn.rcforc) or bool(bn.sleout) or bn.matsum is not None)
    has_renders = dr is not None and bool(dr.render_files)
    has_quality = dr is not None and bool(dr.element_quality)
    has_tensors = dr is not None and bool(dr.peak_element_tensors)
    # 덩어리가 하나도 없어도 항목이 있으면 탭을 연다 — "선별됐지만 흩어졌다" 도 정보다.
    has_hotspot = dr is not None and bool(dr.hotspot_clusters)

    tabs = [("overview", "Overview")]
    if has_stress:
        tabs.append(("stress", "응력·변형률"))
    if has_motion:
        tabs.append(("motion", "운동"))
    if has_tensors:
        tabs.append(("tensor", "응력 텐서"))
    if has_hotspot:
        tabs.append(("hotspot", "핫스팟 군집"))
    if has_stress or has_motion:
        tabs.append(("deep_dive", "부품 Deep Dive"))
    if has_energy:
        tabs.append(("energy", "에너지"))
    if has_contact:
        tabs.append(("contact", "접촉·에너지"))
    if has_quality:
        tabs.append(("quality", "요소 품질"))
    if has_renders:
        tabs.append(("renders", "렌더 갤러리"))
    tabs.append(("sysinfo", "시스템 정보"))

    # Pre-build strings that would require backslashes inside f-strings
    tab_buttons = "".join(
        f'<button class="tab-btn" data-tab="{tid}" onclick="switchTab(\'{tid}\')">{name}</button>'
        for tid, name in tabs
    )
    tab_panels = "".join(
        f'<div class="tab-panel" id="panel-{tid}"></div>'
        for tid, _ in tabs
    )
    term_class = "ok" if si.normal_termination else ("error" if si.normal_termination is False else "unknown")
    term_text = ("✓ Normal termination" if si.normal_termination
                 else ("✗ Error termination" if si.normal_termination is False
                       else "? Unknown termination"))
    d3plot_str = str(si.d3plot) if si.d3plot else "d3plot 없음"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Serialize data for JS
    js_data = _build_js_data(result)
    js_data_str = json.dumps(js_data, ensure_ascii=False, default=str)
    js_tabs_str = json.dumps([t[0] for t in tabs])

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Single Analyzer — {si.path.name}</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
{_CSS}
</style>
</head>
<body>
<div class="header">
  <div class="header-title">
    <span class="badge tier-badge">Tier {si.tier}</span>
    <h1>{si.path.name}</h1>
    <span class="sub">{d3plot_str}</span>
  </div>
  <div class="header-meta">
    <span class="termination {term_class}">{term_text}</span>
    <span class="meta-item">{si.tier_label}</span>
    <span class="meta-item">생성: {now_str}</span>
  </div>
</div>

<div class="tab-bar">
{tab_buttons}
</div>

<div class="filter-bar">
  <label for="part-filter">파트 필터:</label>
  <input type="text" id="part-filter" placeholder="키워드를 콤마로 구분 (예: PKG, PCB, Motor)" />
  <button id="filter-clear" onclick="clearFilter()">초기화</button>
  <span id="filter-count"></span>
</div>

<div class="content">
{tab_panels}
</div>

<script>
const DATA = {js_data_str};
const TABS = {js_tabs_str};

{_JS}

// Init
switchTab(TABS[0]);
</script>

<!-- Fullscreen render modal -->
<div id="render-modal">
  <button class="modal-close" onclick="closeModal()">&#x2715;</button>
  <div id="modal-content"></div>
  <div class="modal-label"></div>
</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# JS data serialization
# ---------------------------------------------------------------------------

def _build_js_data(result: SingleResult) -> dict:
    dr = result.d3plot_result
    gl = result.glstat_data
    si = result.sim_info

    data: dict = {
        # rcforc 계측·검증. 없으면 빈 dict → 접촉 탭이 그 블록만 건너뛴다.
        "contact_metrics": (getattr(result, "contact_metrics", None) or {}),
        "sim": {
            "name": si.path.name,
            "path": str(si.path),
            "d3plot": str(si.d3plot) if si.d3plot else None,
            "tier": si.tier,
            "tier_label": si.tier_label,
            "normal_termination": si.normal_termination,
            "termination_source": si.termination_source,
            "files": {
                "glstat": str(si.glstat) if si.glstat else None,
                "binout": str(si.binout) if si.binout else None,
                "rcforc": str(si.rcforc) if si.rcforc else None,
                "matsum": str(si.matsum) if si.matsum else None,
            },
        },
        "label": result.label,
        "yield_stress": result.yield_stress,
        "summary": {
            "peak_stress": result.peak_stress_global,
            "peak_stress_part_id": result.peak_stress_part_id,
            "peak_strain": result.peak_strain_global,
            "peak_disp": result.peak_disp_global,
            "energy_ratio_min": result.energy_ratio_min,
        },
        "parts": {
            str(pid): {
                "name": p.part_name,
                "peak_stress": p.peak_stress,
                "time_of_peak_stress": p.time_of_peak_stress,
                "peak_element_id": p.peak_element_id,
                "peak_element_reason": p.peak_element_reason,
                "peak_strain": p.peak_strain,
                "peak_max_principal": p.peak_max_principal,
                "peak_min_principal": p.peak_min_principal,
                "peak_max_principal_strain": p.peak_max_principal_strain,
                "peak_min_principal_strain": p.peak_min_principal_strain,
                "peak_vm_strain": p.peak_vm_strain,
                "peak_disp_mag": p.peak_disp_mag,
                "peak_avg_disp_mag": p.peak_avg_disp_mag,
                "peak_disp_node": p.peak_disp_node,
                "peak_disp_reason": p.peak_disp_reason,
                "peak_vel_mag": p.peak_vel_mag,
                "peak_acc_mag": p.peak_acc_mag,
                "safety_factor": p.safety_factor,
            }
            for pid, p in result.parts.items()
        },
        "stress": [],
        "strain": [],
        "max_principal": [],
        "min_principal": [],
        "max_principal_strain": [],
        "vm_strain": [],
        "min_principal_strain": [],
        "peak_element_tensors": [],
        "hotspot": [],
        "motion": {},
        "glstat": None,
        "binout": None,
        "renders": [],
        "element_quality": [],
        "metadata": {},
    }

    if dr:
        data["metadata"] = dr.metadata
        data["stress"] = [_series_to_dict(s) for s in dr.stress]
        data["strain"] = [_series_to_dict(s) for s in dr.strain]
        data["max_principal"] = [_series_to_dict(s) for s in dr.max_principal]
        data["min_principal"] = [_series_to_dict(s) for s in dr.min_principal]
        data["max_principal_strain"] = [_series_to_dict(s) for s in dr.max_principal_strain]
        data["min_principal_strain"] = [_series_to_dict(s) for s in dr.min_principal_strain]
        data["peak_element_tensors"] = []
        for t in dr.peak_element_tensors:
            g = _downsample_group(t.time, {"sxx": t.sxx, "syy": t.syy, "szz": t.szz,
                                           "sxy": t.sxy, "syz": t.syz, "szx": t.szx})
            data["peak_element_tensors"].append({
                "element_id": t.element_id, "part_id": t.part_id,
                "reason": t.reason, "peak_value": t.peak_value, "peak_time": t.peak_time,
                "time": g["t"], "sxx": g["sxx"], "syy": g["syy"], "szz": g["szz"],
                "sxy": g["sxy"], "syz": g["syz"], "szx": g["szx"],
            })
        data["hotspot"] = dr.hotspot_clusters
        data["motion"] = {}
        for pid, md in dr.motion.items():
            g = _downsample_group(md.t, {
                "disp_x": md.disp_x, "disp_y": md.disp_y, "disp_z": md.disp_z,
                "disp_mag": md.disp_mag, "vel_mag": md.vel_mag, "acc_mag": md.acc_mag,
                "max_disp_mag": md.max_disp_mag,
            })
            data["motion"][str(pid)] = {
                "part_id": pid,
                "part_name": md.part_name,
                **g,
                "peak_disp_mag": md.peak_disp_mag,
                "peak_avg_disp_mag": md.peak_avg_disp_mag,
                "peak_disp_node": md.peak_disp_node,
                "peak_disp_reason": md.peak_disp_reason,
                "peak_vel_mag": md.peak_vel_mag,
                "peak_acc_mag": md.peak_acc_mag,
            }
        renders_dir = result.d3plot_result.output_dir / "renders"
        data["renders"] = [
            str(p.relative_to(renders_dir)) for p in dr.render_files
        ]
        data["element_quality"] = [
            {
                "part_id": eq.part_id,
                "part_name": eq.part_name,
                "element_type": eq.element_type,
                "num_elements": eq.num_elements,
                "peak_aspect_ratio": eq.peak_aspect_ratio,
                "aspect_measured": eq.aspect_measured,
                "jacobian_measured": eq.jacobian_measured,
                "volume_measured": eq.volume_measured,
                "warpage_measured": eq.warpage_measured,
                "skewness_measured": eq.skewness_measured,
                "jacobian_unavailable_count": eq.jacobian_unavailable_count,
                "min_jacobian": eq.min_jacobian,
                "peak_warpage": eq.peak_warpage,
                "peak_skewness": eq.peak_skewness,
                "min_volume_change": eq.min_volume_change,
                "max_volume_change": eq.max_volume_change,
                "max_negative_jacobian_count": eq.max_negative_jacobian_count,
                "data": eq.data,
            }
            for eq in dr.element_quality
        ]

    if gl:
        data["glstat"] = {
            **_downsample_group(gl.t, {
                "total_energy": gl.total_energy, "kinetic_energy": gl.kinetic_energy,
                "internal_energy": gl.internal_energy, "hourglass_energy": gl.hourglass_energy,
                "energy_ratio": gl.energy_ratio, "mass": gl.mass,
            }),
            "energy_ratio_min": gl.energy_ratio_min,
            "energy_ratio_max": gl.energy_ratio_max,
            "has_mass_added": gl.has_mass_added,
            "normal_termination": gl.normal_termination,
        }

    bn = result.binout_data
    if bn:
        matsum = None
        if bn.matsum:
            ms = bn.matsum
            g = _downsample_rows(ms.t, {"internal_energy": ms.internal_energy,
                                        "kinetic_energy": ms.kinetic_energy})
            matsum = {
                "part_ids": ms.part_ids,
                "part_names": ms.part_names,
                "t": g["t"],
                "internal_energy": g["internal_energy"],
                "kinetic_energy": g["kinetic_energy"],
            }
        rcforc = []
        for ifc in bn.rcforc:
            g = _downsample_group(ifc.t, {"fx": ifc.fx, "fy": ifc.fy, "fz": ifc.fz, "fmag": ifc.fmag})
            rcforc.append({"id": ifc.interface_id, "name": ifc.name, "side": ifc.side,
                           **g, "peak_fmag": ifc.peak_fmag})
        sleout = []
        for ifc in bn.sleout:
            g = _downsample_group(ifc.t, {"total_energy": ifc.total_energy,
                                          "friction_energy": ifc.friction_energy})
            sleout.append({"id": ifc.interface_id, "name": ifc.name, **g})
        data["binout"] = {"matsum": matsum, "rcforc": rcforc, "sleout": sleout}

    return data


def _finite(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _extreme_indices(n: int, arrays: list, n_max: int) -> list[int]:
    """구간마다 각 배열의 최대·최소 위치를 남기는 인덱스 (처음·끝 포함, 오름차순).

    균등 간격으로 뽑으면 한두 샘플짜리 충격 피크가 사라진다 — JSON 이 전 상태를
    담게 된 뒤 실덱 응력 시리즈 23개 중 21개가 그래프에서 피크를 잃었다(2026-09).
    배열이 많으면 구간 수를 줄이되 50 구간(최대 4×n_max 점) 아래로는 내리지 않는다.
    """
    k = max(1, len(arrays))
    buckets = max((n_max - 2) // (2 * k), min(50, (4 * n_max) // (2 * k)), 1)
    buckets = min(buckets, n)
    keep = {0, n - 1}
    for vals in arrays:
        for b in range(buckets):
            lo, hi = b * n // buckets, (b + 1) * n // buckets
            imax = imin = None
            for i in range(lo, hi):
                v = vals[i]
                if not _finite(v):
                    continue
                if imax is None or v > vals[imax]:
                    imax = i
                if imin is None or v < vals[imin]:
                    imin = i
            if imax is not None:
                keep.add(imax)
                keep.add(imin)
    return sorted(keep)


def _downsample_group(t: list, arrays: dict, n_max: int = 500) -> dict:
    """시간축 t 와 그 위에 그려지는 배열들을 **같은 인덱스로** 줄인다.

    반환: {"t": ..., <이름>: ...}. 각 배열의 전역 최대·최소는 항상 남는다.
    길이가 t 와 다른 배열은 t 의 인덱스로 뽑을 수 없으므로 섞지 않고 따로 줄인다.
    """
    t = list(t or [])
    n = len(t)
    aligned = {k: v for k, v in arrays.items() if v is not None and len(v) == n}
    out: dict = {}
    if n <= n_max:
        out["t"] = t
        out.update({k: list(v) for k, v in aligned.items()})
    else:
        idx = _extreme_indices(n, list(aligned.values()), n_max)
        out["t"] = [t[i] for i in idx]
        out.update({k: [v[i] for i in idx] for k, v in aligned.items()})
    for k, v in arrays.items():
        if k in aligned:
            continue
        v = list(v or [])
        if len(v) <= n_max:
            out[k] = v
        else:
            out[k] = [v[i] for i in _extreme_indices(len(v), [v], n_max)]
    return out


def _downsample_rows(t: list, tables: dict, n_max: int = 500) -> dict:
    """[n_times][n_cols] 표들을 시간축과 같은 인덱스로 줄인다 (matsum 에너지 등).

    열(파트)마다 극값을 보존하도록 열 단위로 풀어 _downsample_group 에 넘기고 다시 행으로 묶는다.
    행 수가 t 와 다르거나 행 길이가 들쭉날쭉한 표는 시각과 짝지을 수 없어 빈 목록으로 두고,
    같은 이름의 "<이름>_note" 에 사유를 남긴다.
    """
    t = list(t or [])
    n = len(t)
    cols: dict = {}
    widths: dict = {}
    notes: dict = {}
    for name, rows in tables.items():
        rows = list(rows or [])
        if not rows:
            widths[name] = 0
            continue
        w = len(rows[0]) if isinstance(rows[0], (list, tuple)) else -1
        if len(rows) != n or w < 0 or any(not isinstance(r, (list, tuple)) or len(r) != w for r in rows):
            notes[name] = f"행 {len(rows)}개가 시각 {n}개와 맞지 않거나 행 길이가 달라 표시하지 않음"
            widths[name] = None
            continue
        widths[name] = w
        for c in range(w):
            cols[(name, c)] = [r[c] for r in rows]
    g = _downsample_group(t, cols, n_max=n_max)
    out = {"t": g["t"]}
    for name, w in widths.items():
        if w is None:
            out[name] = []
            out[f"{name}_note"] = notes[name]
        elif w == 0:
            out[name] = []
        else:
            out[name] = [[g[(name, c)][j] for c in range(w)] for j in range(len(g["t"]))]
    return out


def _series_to_dict(s) -> dict:
    g = _downsample_group(s.t, {"max_vals": s.max_vals, "avg_vals": s.avg_vals})
    return {
        "part_id": s.part_id,
        "part_name": s.part_name,
        "quantity": s.quantity,
        "unit": s.unit,
        "global_max": s.global_max,
        "global_min": s.global_min,
        "time_of_max": s.time_of_max,
        "t": g["t"],
        "max_vals": g["max_vals"],
        "avg_vals": g["avg_vals"],
    }


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

_CSS = """
:root {
  --bg: #1a1a2e; --bg2: #16213e; --bg3: #0f3460;
  --fg: #e0e0e0; --fg2: #a0a0b0;
  --accent: #e94560; --accent2: #4ecca3; --accent3: #f5a623;
  --border: #2a2a4a; --card: #1e2a45;
  --ok: #4ecca3; --err: #e94560; --warn: #f5a623;
  --radius: 8px; --font: 'Segoe UI', system-ui, sans-serif;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: var(--bg); color: var(--fg); font-family: var(--font); font-size: 14px; }
a { color: var(--accent2); }

.header { background: var(--bg2); border-bottom: 1px solid var(--border); padding: 16px 24px;
          display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.header-title h1 { font-size: 1.3rem; margin: 4px 0; }
.header-title .sub { color: var(--fg2); font-size: 0.8rem; font-family: monospace; }
.header-meta { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.meta-item { color: var(--fg2); font-size: 0.82rem; }

.badge { padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
.tier-badge { background: var(--bg3); color: var(--accent2); }
.termination { font-size: 0.85rem; font-weight: 600; }
.termination.ok { color: var(--ok); }
.termination.error { color: var(--err); }
.termination.unknown { color: var(--warn); }

.tab-bar { background: var(--bg2); border-bottom: 1px solid var(--border);
           display: flex; gap: 2px; padding: 0 12px; overflow-x: auto; }
.tab-btn { background: none; border: none; color: var(--fg2); cursor: pointer;
           padding: 10px 16px; font-size: 0.85rem; border-bottom: 2px solid transparent;
           white-space: nowrap; transition: all .2s; }
.tab-btn:hover { color: var(--fg); }
.tab-btn.active { color: var(--accent2); border-bottom-color: var(--accent2); }
.filter-bar { background: var(--bg2); padding: 8px 16px; display: flex; align-items: center;
              gap: 10px; border-bottom: 1px solid var(--border); }
.filter-bar label { color: var(--fg2); font-size: 0.85rem; white-space: nowrap; }
.filter-bar input { flex: 1; max-width: 500px; padding: 6px 10px; border-radius: 4px;
                    border: 1px solid var(--border); background: var(--bg); color: var(--fg);
                    font-size: 0.85rem; }
.filter-bar input::placeholder { color: var(--fg2); opacity: 0.6; }
.filter-bar button { padding: 5px 12px; border-radius: 4px; border: 1px solid var(--border);
                     background: var(--bg); color: var(--fg2); cursor: pointer; font-size: 0.8rem; }
.filter-bar button:hover { background: var(--bg2); color: var(--fg); }
#filter-count { color: var(--fg2); font-size: 0.8rem; }

.content { padding: 20px 24px; }
.tab-panel { display: none; }
.tab-panel.active { display: block; }

/* Cards */
.kpi-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; margin-bottom: 20px; }
.kpi-card { background: var(--card); border: 1px solid var(--border); border-radius: var(--radius);
            padding: 14px 16px; }
.kpi-label { font-size: 0.75rem; color: var(--fg2); text-transform: uppercase; letter-spacing: .5px; }
.kpi-value { font-size: 1.4rem; font-weight: 700; margin: 4px 0; }
.kpi-unit { font-size: 0.75rem; color: var(--fg2); }
.kpi-warn { color: var(--warn); }
.kpi-err { color: var(--err); }
.kpi-ok { color: var(--ok); }

/* Section heading */
.sec-title { font-size: 1rem; font-weight: 600; margin: 20px 0 10px;
             border-left: 3px solid var(--accent2); padding-left: 10px; }

/* Tables */
.data-table { width: 100%; border-collapse: collapse; font-size: 0.83rem; }
.data-table th { background: var(--bg3); color: var(--fg2); padding: 7px 10px; text-align: left; font-weight: 500; }
.data-table td { padding: 6px 10px; border-bottom: 1px solid var(--border); }
.data-table tr:hover td { background: rgba(78,204,163,.06); }
.data-table .num { text-align: right; font-family: monospace; }
.warn-row td { color: var(--warn); }
.err-row td { color: var(--err); }

/* Charts */
.chart-box { background: var(--card); border: 1px solid var(--border); border-radius: var(--radius);
             padding: 14px; margin-bottom: 16px; }
.chart-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
@media (max-width: 900px) { .chart-row { grid-template-columns: 1fr; } }
.chart-title { font-size: 0.85rem; color: var(--fg2); margin-bottom: 8px; }
.plotly-chart { width: 100%; }

/* Quality indicators */
.crit { background: rgba(235,87,87,.18); color: var(--err); font-weight: 600; }
.warn { background: rgba(242,201,76,.15); color: var(--warn); font-weight: 600; }
.na { color: var(--fg2); opacity: .55; }   /* 미산출 — 경고도 정상도 아니다 */

/* Part selector */
.part-selector { display: flex; gap: 8px; align-items: center; margin-bottom: 16px; flex-wrap: wrap; }
.part-selector label { font-size: 0.85rem; color: var(--fg2); }
.part-selector select { background: var(--bg3); color: var(--fg); border: 1px solid var(--border);
                         border-radius: 4px; padding: 5px 10px; font-size: 0.85rem; cursor: pointer; }

/* File list */
.file-list { display: flex; flex-direction: column; gap: 4px; }
.file-item { display: flex; align-items: center; gap: 8px; padding: 5px 0;
             border-bottom: 1px solid var(--border); font-size: 0.82rem; }
.file-status { font-weight: 600; width: 16px; text-align: center; }
.file-status.present { color: var(--ok); }
.file-status.absent { color: var(--fg2); }
.file-path { font-family: monospace; color: var(--fg2); font-size: 0.78rem; }

/* Render gallery */
.render-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.render-card { background: var(--card); border: 1px solid var(--border); border-radius: var(--radius);
               padding: 10px; cursor: zoom-in; transition: border-color .2s; }
.render-card:hover { border-color: var(--accent2); }
.render-card video, .render-card img { width: 100%; border-radius: 4px; display: block; }
.render-card .render-name { font-size: 0.78rem; color: var(--fg2); margin-top: 6px;
                             text-align: center; font-family: monospace; }
.render-axis-label { font-size: 0.95rem; font-weight: 700; color: var(--accent2);
                     text-align: center; margin-bottom: 4px; letter-spacing: 1px; }
/* Folder accordion */
.render-folder { border: 1px solid var(--border); border-radius: var(--radius); margin-bottom: 8px; overflow: hidden; }
.render-folder-header { display: flex; align-items: center; gap: 10px; padding: 10px 14px;
                         background: var(--bg2); cursor: pointer; user-select: none;
                         transition: background .15s; }
.render-folder-header:hover { background: var(--bg3); }
.render-folder-arrow { font-size: 0.75rem; color: var(--fg2); transition: transform .2s; }
.render-folder.open .render-folder-arrow { transform: rotate(90deg); }
.render-folder-title { font-size: 0.9rem; font-weight: 600; color: var(--fg); flex: 1; }
.render-folder-count { font-size: 0.75rem; color: var(--fg2); }
.render-folder-body { display: none; padding: 12px; background: var(--bg1); }
.render-folder.open .render-folder-body { display: block; }
/* Fullscreen modal */
#render-modal { display: none; position: fixed; inset: 0; background: rgba(0,0,0,.92);
                z-index: 9999; align-items: center; justify-content: center; flex-direction: column; }
#render-modal.open { display: flex; }
#render-modal video, #render-modal img { max-width: 95vw; max-height: 88vh; border-radius: 6px; }
#render-modal .modal-label { color: #aaa; font-size: 0.85rem; margin-top: 10px; font-family: monospace; }
#render-modal .modal-close { position: absolute; top: 16px; right: 20px; background: none; border: none;
                              color: #fff; font-size: 2rem; cursor: pointer; line-height: 1; }

/* Bar chart inline */
.bar-row { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.bar-label { width: 120px; font-size: 0.8rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--fg2); text-align: right; }
.bar-track { flex: 1; background: var(--bg3); border-radius: 3px; height: 14px; overflow: hidden; }
.bar-fill { height: 100%; background: var(--accent2); border-radius: 3px; transition: width .3s; }
.bar-val { width: 90px; font-size: 0.78rem; font-family: monospace; color: var(--fg); }

/* Warn box */
.warn-box { background: rgba(245,166,35,.1); border: 1px solid var(--warn); border-radius: var(--radius);
            padding: 10px 14px; margin-bottom: 12px; color: var(--warn); font-size: 0.85rem; }
.err-box { background: rgba(233,69,96,.1); border: 1px solid var(--err); border-radius: var(--radius);
           padding: 10px 14px; margin-bottom: 12px; color: var(--err); font-size: 0.85rem; }

/* Safety factor */
.sf-ok { color: var(--ok); }
.sf-warn { color: var(--warn); }
.sf-fail { color: var(--err); }

/* Section view config panel */
.sv-config { background: var(--card); border: 1px solid var(--accent2); border-radius: var(--radius);
             padding: 16px; margin-bottom: 20px; }
.sv-config-title { font-size: 0.95rem; font-weight: 600; color: var(--accent2); margin-bottom: 12px; }
.sv-config-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }
.sv-field { display: flex; flex-direction: column; gap: 4px; }
.sv-field label { font-size: 0.78rem; color: var(--fg2); text-transform: uppercase; letter-spacing: .5px; }
.sv-field select, .sv-field input[type="text"], .sv-field input[type="number"] {
  background: var(--bg); color: var(--fg); border: 1px solid var(--border);
  border-radius: 4px; padding: 6px 8px; font-size: 0.85rem; }
.sv-field .sv-checkboxes { display: flex; gap: 12px; align-items: center; }
.sv-field .sv-checkboxes label { text-transform: none; font-size: 0.85rem; cursor: pointer; display: flex; align-items: center; gap: 4px; }
.sv-actions { display: flex; gap: 10px; margin-top: 14px; }
.sv-actions button { padding: 7px 16px; border-radius: 4px; border: 1px solid var(--border);
                     cursor: pointer; font-size: 0.83rem; font-weight: 500; }
.sv-btn-primary { background: var(--accent2); color: #1a1b26; border-color: var(--accent2) !important; }
.sv-btn-primary:hover { opacity: .85; }
.sv-btn-secondary { background: var(--bg); color: var(--fg2); }
.sv-btn-secondary:hover { background: var(--bg2); color: var(--fg); }
.sv-output { background: var(--bg); border: 1px solid var(--border); border-radius: 4px;
             padding: 10px; margin-top: 10px; font-family: monospace; font-size: 0.8rem;
             color: var(--fg2); white-space: pre-wrap; display: none; max-height: 200px; overflow-y: auto; }

@media (max-width: 600px) {
  .kpi-grid { grid-template-columns: repeat(2, 1fr); }
  .content { padding: 12px; }
}
/* 핫스팟 군집 탭 */
.hs-note { color: var(--fg2); font-size: 0.85rem; margin: 0 0 12px; line-height: 1.55; }
.hs-dim { color: var(--fg2); font-size: 0.78rem; }
.hs-row { cursor: pointer; }
.hs-row.hs-sel td { background: rgba(78,204,163,.14); }
.hs-meta { display: flex; flex-wrap: wrap; gap: 6px 18px; font-size: 0.8rem; color: var(--fg2); margin: 0 0 10px; }
"""


# ---------------------------------------------------------------------------
# JavaScript
# ---------------------------------------------------------------------------

_JS = r"""
// ── Plotly default layout ──────────────────────────────────────────────
const PLOT_LAYOUT = {
  paper_bgcolor: 'transparent',
  plot_bgcolor: 'rgba(15,52,96,0.4)',
  font: {color: '#e0e0e0', size: 12},
  margin: {l: 55, r: 20, t: 30, b: 45},
  xaxis: {gridcolor: '#2a2a4a', linecolor: '#2a2a4a', zerolinecolor: '#2a2a4a'},
  yaxis: {gridcolor: '#2a2a4a', linecolor: '#2a2a4a', zerolinecolor: '#2a2a4a'},
  legend: {bgcolor: 'rgba(0,0,0,0)', bordercolor: '#2a2a4a'},
};
const PLOT_CONFIG = {responsive: true, displayModeBar: false};
const COLORS = ['#4ecca3','#e94560','#f5a623','#7b68ee','#00bcd4','#ff9800','#9c27b0','#4caf50'];

function fmt(v, dec=2) {
  if (v === null || v === undefined) return '—';
  if (Math.abs(v) >= 1e6) return v.toExponential(2);
  return Number(v).toFixed(dec);
}
function fmtPct(v, dec=1) { return v === null ? '—' : fmt(v*100, dec) + '%'; }

// ── Part filter ───────────────────────────────────────────────────────
let _filterKeywords = [];

function partMatchesFilter(pid, partObj) {
  if (_filterKeywords.length === 0) return true;
  const haystack = ('Part ' + pid + ' ' + (partObj?.name || '')).toLowerCase();
  return _filterKeywords.every(kw => haystack.includes(kw));
}

function filteredParts() {
  return Object.entries(DATA.parts).filter(([pid, p]) => partMatchesFilter(pid, p));
}

function applyFilter() {
  const input = document.getElementById('part-filter');
  const raw = input.value.trim();
  _filterKeywords = raw ? raw.split(',').map(s => s.trim().toLowerCase()).filter(s => s) : [];

  // Re-render all already-rendered tabs
  _rendered = {};
  TABS.forEach(tid => {
    const el = document.getElementById('panel-' + tid);
    if (el) el.innerHTML = '';
  });
  const activeBtn = document.querySelector('.tab-btn.active');
  const activeTid = activeBtn ? activeBtn.dataset.tab : TABS[0];
  switchTab(activeTid);

  // Update count
  const total = Object.keys(DATA.parts).length;
  const shown = filteredParts().length;
  const countEl = document.getElementById('filter-count');
  if (countEl) {
    countEl.textContent = _filterKeywords.length > 0 ? `${shown} / ${total} 파트` : '';
  }
}

function clearFilter() {
  const input = document.getElementById('part-filter');
  input.value = '';
  applyFilter();
}

// Debounce filter input
(function() {
  let timer;
  document.addEventListener('DOMContentLoaded', () => {
    const input = document.getElementById('part-filter');
    if (input) input.addEventListener('input', () => {
      clearTimeout(timer);
      timer = setTimeout(applyFilter, 300);
    });
  });
  // Also fire if DOM already loaded
  if (document.readyState !== 'loading') {
    const input = document.getElementById('part-filter');
    if (input) input.addEventListener('input', () => {
      clearTimeout(timer);
      timer = setTimeout(applyFilter, 300);
    });
  }
})();

// ── Tab switching ──────────────────────────────────────────────────────
let _rendered = {};
function switchTab(tid) {
  document.querySelectorAll('.tab-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.tab === tid);
  });
  document.querySelectorAll('.tab-panel').forEach(p => {
    p.classList.toggle('active', p.id === 'panel-' + tid);
  });
  if (!_rendered[tid]) {
    _rendered[tid] = true;
    renderTab(tid);
  }
}

function renderTab(tid) {
  const el = document.getElementById('panel-' + tid);
  if (!el) return;
  switch(tid) {
    case 'overview':   el.innerHTML = renderOverview(); break;
    case 'stress':     el.innerHTML = renderStress(); initStressCharts(); break;
    case 'tensor':     el.innerHTML = renderTensor(); initTensorCharts(); break;
    case 'hotspot':    el.innerHTML = renderHotspot(); initHotspot(); break;
    case 'motion':     el.innerHTML = renderMotion(); initMotionCharts(); break;
    case 'deep_dive':  el.innerHTML = renderDeepDive(); initDeepDive(); break;
    case 'energy':     el.innerHTML = renderEnergy(); initEnergyCharts(); break;
    case 'contact':    el.innerHTML = renderContact(); initContactCharts(); break;
    case 'quality':    el.innerHTML = renderQuality(); initQualityCharts(); break;
    case 'renders':    el.innerHTML = renderGallery(); initGallery(); break;
    case 'sysinfo':    el.innerHTML = renderSysInfo(); break;
  }
}

// ── Helper: format part label as "Part {id} ({name})" ────────────────
function partLabel(pid, p) {
  return p && p.name ? 'Part ' + pid + ' (' + p.name + ')' : 'Part ' + pid;
}

// ── Overview ──────────────────────────────────────────────────────────
function renderOverview() {
  const s = DATA.summary;
  const yld = DATA.yield_stress;
  const sf = (yld > 0 && s.peak_stress > 0) ? (yld / s.peak_stress) : null;
  const er = s.energy_ratio_min;
  // 에너지 생성(>1.1)만 오류. 소산(<1.0)은 물리적으로 정상 (고무·소성·감쇠 해석).
  const erClass = er === null ? '' : er > 1.1 ? 'kpi-err' : er > 1.05 ? 'kpi-warn' : 'kpi-ok';

  // 🔴 응력 시간이력 집계(stress_history)는 솔리드 전용이다. 셸·두꺼운 셸이 있는 덱에서
  //    '피크 응력' 을 모델 전체 최대로 읽으면 틀린다 → 있으면 명시한다.
  const solidOnly = (DATA.hotspot || []).some(p => (p.element_type || 'solid') !== 'solid');
  let kpis = `
  <div class="kpi-card">
    <div class="kpi-label">피크 Von Mises 응력${solidOnly ? ' (솔리드만)' : ''}</div>
    <div class="kpi-value">${fmt(s.peak_stress)}</div>
    <div class="kpi-unit">MPa${s.peak_stress_part_id ? ' — Part ' + s.peak_stress_part_id + (DATA.parts[s.peak_stress_part_id]?.name ? ' (' + DATA.parts[s.peak_stress_part_id].name + ')' : '') : ''}</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">피크 소성 변형률</div>
    <div class="kpi-value">${fmt(s.peak_strain, 4)}</div>
    <div class="kpi-unit">—</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">피크 변위</div>
    <div class="kpi-value">${fmt(s.peak_disp)}</div>
    <div class="kpi-unit">${s.peak_disp === null || s.peak_disp === undefined ? '미계측 — motion CSV 에 Max_Disp_Mag 없음' : 'mm (절점 최대)'}</div>
  </div>`;
  if (sf !== null) {
    const sfClass = sf >= 1.0 ? 'kpi-ok' : sf >= 0.85 ? 'kpi-warn' : 'kpi-err';
    kpis += `<div class="kpi-card">
    <div class="kpi-label">Safety Factor</div>
    <div class="kpi-value ${sfClass}">${fmt(sf, 3)}</div>
    <div class="kpi-unit">σ_yield=${fmt(yld)} MPa</div>
    </div>`;
  }
  if (er !== null) {
    kpis += `<div class="kpi-card">
    <div class="kpi-label">에너지 비율 (최소)</div>
    <div class="kpi-value ${erClass}">${fmt(er, 4)}</div>
    <div class="kpi-unit">internal/total (이상: 1.0)</div>
    </div>`;
  }
  kpis += `<div class="kpi-card">
    <div class="kpi-label">분석 States</div>
    <div class="kpi-value">${DATA.metadata.num_states || '—'}</div>
    <div class="kpi-unit">t_end=${fmt(DATA.metadata.end_time, 4)}</div>
  </div>`;

  // Top 5 stress parts
  const parts = filteredParts()
    .sort((a,b) => b[1].peak_stress - a[1].peak_stress)
    .slice(0, 5);
  const maxStress = parts[0]?.[1].peak_stress || 1;
  const topBars = parts.map(([pid, p], i) => {
    const pct = (p.peak_stress / maxStress * 100).toFixed(1);
    return `<div class="bar-row">
      <div class="bar-label" title="${p.name}">${partLabel(pid, p)}</div>
      <div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div>
      <div class="bar-val">${fmt(p.peak_stress)} MPa</div>
    </div>`;
  }).join('');

  // 핫스팟 군집 요약 — 첫 기준량의 1위 덩어리 상위 3개
  let hsCard = '';
  const hsAll = (DATA.hotspot || []);
  if (hsAll.length) {
    const crit0 = hsAll[0].criterion;
    const isMin0 = hsAll[0].direction === 'min';
    const top = hsAll.filter(p => p.criterion === crit0 && p.clusters && p.clusters.length && !p.uniform && hsMatchesFilter(p))
      .sort((a, b) => isMin0 ? a.clusters[0].stress_max - b.clusters[0].stress_max
                              : b.clusters[0].stress_max - a.clusters[0].stress_max).slice(0, 3);
    const nC = hsAll.filter(p => p.criterion === crit0 && !p.uniform).reduce((n, p) => n + (p.clusters ? p.clusters.length : 0), 0);
    const nFlat = hsAll.filter(p => p.criterion === crit0 && p.uniform).length;
    const items = top.map(p => {
      const c = p.clusters[0];
      return `<div class="bar-row"><div class="bar-label">${partLabel(p.part_id, {name: hsPartName(p)})}</div>
        <div style="flex:1;color:var(--fg2);font-size:0.82rem">${hsZoneLabel(p, hsRelPos(p, c))} · 요소 ${c.element_count} · 평균 ${fmt(c.stress_mean)}</div>
        <div class="bar-val">${fmt(c.stress_max)}</div></div>`;
    }).join('');
    hsCard = `<div class="sec-title">핫스팟 군집 (${HS_CRIT_LABEL[crit0] || crit0}) — 덩어리 ${nC}개
      <a href="#" onclick="switchTab('hotspot');return false" style="font-size:0.8rem;margin-left:8px;color:var(--accent2)">상세 →</a></div>
      <div class="chart-box">${items || `<div style="color:var(--fg2);padding:8px">${nFlat && !nC
        ? '응력이 파트 전체에 균일 — 핫스팟 없음'
        : '덩어리 없음 — 핫스팟이 흩어져 있다'}</div>`}</div>`;
  }

  return `
<div class="kpi-grid">${kpis}</div>
<div class="sec-title">응력 상위 부품${solidOnly ? ' (솔리드만)' : ''}</div>
<div class="chart-box">${topBars || '<div style="color:var(--fg2);padding:8px">응력 데이터 없음</div>'}
${solidOnly ? '<div class="hs-dim" style="margin-top:6px">이 모델에는 셸·두꺼운 셸이 있다. 위 집계는 솔리드 요소만 본다 — 셸 계열 응력은 핫스팟 군집 탭에 있다.</div>' : ''}</div>
${hsCard}`;
}

// ── Stress & Strain ──────────────────────────────────────────────────
function renderStress() {
  const parts = filteredParts().sort((a,b) => b[1].peak_stress - a[1].peak_stress);
  const maxS = parts[0]?.[1].peak_stress || 1;

  const stressBars = parts.map(([pid, p]) => {
    const pct = (p.peak_stress / maxS * 100).toFixed(1);
    const sf = p.safety_factor;
    const sfHtml = sf !== null && sf !== undefined
      ? `<span class="${sf>=1?'sf-ok':sf>=0.85?'sf-warn':'sf-fail'}"> SF=${fmt(sf,3)}</span>` : '';
    return `<div class="bar-row">
      <div class="bar-label" title="${p.name}">${partLabel(pid, p)}</div>
      <div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div>
      <div class="bar-val">${fmt(p.peak_stress)} MPa${sfHtml}</div>
    </div>`;
  }).join('');

  const maxE = Math.max(...parts.map(([,p]) => p.peak_strain), 0) || 1;
  const strainBars = parts.filter(([,p]) => p.peak_strain > 0)
    .sort((a,b) => b[1].peak_strain - a[1].peak_strain)
    .map(([pid, p]) => {
      const pct = (p.peak_strain / maxE * 100).toFixed(1);
      return `<div class="bar-row">
        <div class="bar-label" title="${p.name}">${partLabel(pid, p)}</div>
        <div class="bar-track"><div class="bar-fill" style="background:var(--accent3);width:${pct}%"></div></div>
        <div class="bar-val">${fmt(p.peak_strain, 4)}</div>
      </div>`;
    }).join('');

  // Max principal stress ranking
  const maxPrincipalParts = filteredParts().filter(([,p]) => p.peak_max_principal !== 0)
    .sort((a,b) => b[1].peak_max_principal - a[1].peak_max_principal);
  const maxP1 = maxPrincipalParts[0]?.[1].peak_max_principal || 1;
  const maxPrincipalBars = maxPrincipalParts.map(([pid, p]) => {
    const pct = (p.peak_max_principal / maxP1 * 100).toFixed(1);
    return `<div class="bar-row">
      <div class="bar-label" title="${p.name}">${partLabel(pid, p)}</div>
      <div class="bar-track"><div class="bar-fill" style="background:#e67e22;width:${pct}%"></div></div>
      <div class="bar-val">${fmt(p.peak_max_principal)} MPa</div>
    </div>`;
  }).join('');

  // Min principal stress ranking (most compressive = most negative)
  const minPrincipalParts = filteredParts().filter(([,p]) => p.peak_min_principal !== 0)
    .sort((a,b) => a[1].peak_min_principal - b[1].peak_min_principal);
  const minP3 = Math.abs(minPrincipalParts[0]?.[1].peak_min_principal) || 1;
  const minPrincipalBars = minPrincipalParts.map(([pid, p]) => {
    const pct = (Math.abs(p.peak_min_principal) / minP3 * 100).toFixed(1);
    return `<div class="bar-row">
      <div class="bar-label" title="${p.name}">${partLabel(pid, p)}</div>
      <div class="bar-track"><div class="bar-fill" style="background:#8e44ad;width:${pct}%"></div></div>
      <div class="bar-val">${fmt(p.peak_min_principal)} MPa</div>
    </div>`;
  }).join('');

  // Max principal strain ranking (conditional — only when strain tensor data exists)
  const maxPrincipalStrainParts = filteredParts().filter(([,p]) => p.peak_max_principal_strain !== 0)
    .sort((a,b) => b[1].peak_max_principal_strain - a[1].peak_max_principal_strain);
  const maxPE1 = maxPrincipalStrainParts[0]?.[1].peak_max_principal_strain || 1;
  const maxPrincipalStrainBars = maxPrincipalStrainParts.map(([pid, p]) => {
    const pct = (p.peak_max_principal_strain / maxPE1 * 100).toFixed(1);
    return `<div class="bar-row">
      <div class="bar-label" title="${p.name}">${partLabel(pid, p)}</div>
      <div class="bar-track"><div class="bar-fill" style="background:#27ae60;width:${pct}%"></div></div>
      <div class="bar-val">${fmt(p.peak_max_principal_strain, 4)}</div>
    </div>`;
  }).join('');

  const minPrincipalStrainParts = filteredParts().filter(([,p]) => p.peak_min_principal_strain !== 0)
    .sort((a,b) => a[1].peak_min_principal_strain - b[1].peak_min_principal_strain);
  const minPE3 = Math.abs(minPrincipalStrainParts[0]?.[1].peak_min_principal_strain) || 1;
  const minPrincipalStrainBars = minPrincipalStrainParts.map(([pid, p]) => {
    const pct = (Math.abs(p.peak_min_principal_strain) / minPE3 * 100).toFixed(1);
    return `<div class="bar-row">
      <div class="bar-label" title="${p.name}">${partLabel(pid, p)}</div>
      <div class="bar-track"><div class="bar-fill" style="background:#2c3e50;width:${pct}%"></div></div>
      <div class="bar-val">${fmt(p.peak_min_principal_strain, 4)}</div>
    </div>`;
  }).join('');

  const hasPrincipalStrain = maxPrincipalStrainParts.length > 0 || minPrincipalStrainParts.length > 0;

  const opts = filteredParts()
    .sort((a,b) => b[1].peak_stress - a[1].peak_stress)
    .map(([pid, p]) => `<option value="${pid}">${partLabel(pid, p)}</option>`).join('');

  return `
<div class="sec-title">Von Mises 응력 순위</div>
<div class="chart-box">${stressBars||'<div style="color:var(--fg2)">데이터 없음</div>'}</div>
<div class="sec-title">Max Principal Stress (σ₁) 순위</div>
<div class="chart-box">${maxPrincipalBars||'<div style="color:var(--fg2)">데이터 없음</div>'}</div>
<div class="sec-title">Min Principal Stress (σ₃) 순위 — 압축 최대</div>
<div class="chart-box">${minPrincipalBars||'<div style="color:var(--fg2)">데이터 없음</div>'}</div>
<div class="sec-title">소성 변형률 순위</div>
<div class="chart-box">${strainBars||'<div style="color:var(--fg2)">데이터 없음</div>'}</div>
${hasPrincipalStrain ? `
<div class="sec-title">Max Principal Strain (ε₁) 순위</div>
<div class="chart-box">${maxPrincipalStrainBars}</div>
<div class="sec-title">Min Principal Strain (ε₃) 순위 — 압축 최대</div>
<div class="chart-box">${minPrincipalStrainBars}</div>` : ''}
<div class="sec-title">전체 부품 응력 이력 오버레이</div>
<div class="chart-box"><div id="stress-overlay-chart" class="plotly-chart" style="height:320px"></div></div>
<div class="sec-title">부품별 상세 시계열</div>
<div class="part-selector">
  <label>부품 선택:</label>
  <select id="stress-part-sel" onchange="updateStressChart()">${opts}</select>
</div>
<div class="chart-box"><div id="stress-chart" class="plotly-chart" style="height:300px"></div></div>
<div class="chart-box"><div id="strain-chart" class="plotly-chart" style="height:280px"></div></div>`;
}

function initStressCharts() {
  // Overlay: all parts max stress on one chart
  if (DATA.stress.length > 0) {
    const traces = DATA.stress.map((s, i) => ({
      x: s.t, y: s.max_vals, name: s.part_name ? `Part ${s.part_id} (${s.part_name})` : `Part ${s.part_id}`,
      mode: 'lines', line: {color: COLORS[i % COLORS.length]},
    }));
    Plotly.newPlot('stress-overlay-chart', traces,
      {...PLOT_LAYOUT, title:{text:'Von Mises Max — 전체 부품 (MPa)',font:{size:13}}}, PLOT_CONFIG);
  }
  updateStressChart();
}

function updateStressChart() {
  const pid = document.getElementById('stress-part-sel')?.value;
  if (!pid) return;
  const st = DATA.stress.find(s => String(s.part_id) === pid);
  const sr = DATA.strain.find(s => String(s.part_id) === pid);

  if (st) {
    Plotly.newPlot('stress-chart', [{
      x: st.t, y: st.max_vals, name: 'Max', type: 'scatter', mode: 'lines',
      line: {color: COLORS[0]}
    }, {
      x: st.t, y: st.avg_vals, name: 'Avg', type: 'scatter', mode: 'lines',
      line: {color: COLORS[0], dash: 'dot'}
    }], {...PLOT_LAYOUT, title: {text: `Von Mises — Part ${st.part_id}${st.part_name ? ' (' + st.part_name + ')' : ''}`, font:{size:13}}}, PLOT_CONFIG);
  }
  if (sr) {
    Plotly.newPlot('strain-chart', [{
      x: sr.t, y: sr.max_vals, name: 'Max', type: 'scatter', mode: 'lines',
      line: {color: COLORS[2]}
    }, {
      x: sr.t, y: sr.avg_vals, name: 'Avg', type: 'scatter', mode: 'lines',
      line: {color: COLORS[2], dash: 'dot'}
    }], {...PLOT_LAYOUT, title: {text: `소성 변형률 — Part ${sr.part_id}${sr.part_name ? ' (' + sr.part_name + ')' : ''}`, font:{size:13}}}, PLOT_CONFIG);
  }
}

// ── Stress Tensor (peak element histories) ───────────────────────────
function renderTensor() {
  const tensors = DATA.peak_element_tensors || [];
  if (tensors.length === 0) return '<div style="color:var(--fg2)">텐서 데이터 없음</div>';

  const reasonLabel = {
    'peak_von_mises': 'Peak Von Mises',
    'peak_max_principal': 'Peak σ₁',
    'peak_min_principal': 'Peak σ₃ (압축)',
  };

  const opts = tensors.map((t, i) => {
    const pInfo = DATA.parts[String(t.part_id)];
    const pName = pInfo?.name ? ` (${pInfo.name})` : '';
    return `<option value="${i}">Part ${t.part_id}${pName} — Elem ${t.element_id} [${reasonLabel[t.reason] || t.reason}]</option>`;
  }).join('');

  return `
<div class="sec-title">피크 요소 응력 텐서 시계열 (Stress Ellipsoid용)</div>
<p style="color:var(--fg2);font-size:0.85rem;margin:0 0 12px">
  파트별 최대 응력 요소의 6성분 (σxx, σyy, σzz, σxy, σyz, σzx) 시간 히스토리.
  주응력 (σ₁, σ₂, σ₃)은 텐서에서 실시간 계산.
</p>
<div class="part-selector">
  <label>요소 선택:</label>
  <select id="tensor-sel" onchange="updateTensorChart()">${opts}</select>
</div>
<div class="chart-box"><div id="tensor-components-chart" class="plotly-chart" style="height:340px"></div></div>
<div class="chart-box"><div id="tensor-principals-chart" class="plotly-chart" style="height:300px"></div></div>
<div class="sec-title">Stress Ellipsoid & Mohr's Circles</div>
<div style="display:flex;align-items:center;gap:12px;margin:8px 0 4px">
  <label style="font-size:0.85rem;color:var(--fg2)">시간:</label>
  <input type="range" id="tensor-time-slider" min="0" max="0" value="0" style="flex:1"
         oninput="updateEllipsoidAndMohr()">
  <button onclick="jumpToPeakTime()" style="padding:3px 10px;font-size:0.8rem;cursor:pointer;
    border:1px solid var(--border);border-radius:4px;background:var(--accent);color:#fff;white-space:nowrap">Peak 이동</button>
  <span id="tensor-time-label" style="font-size:0.85rem;min-width:100px;color:var(--fg2)">t = 0</span>
</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
  <div class="chart-box"><div id="stress-ellipsoid-chart" style="height:420px"></div></div>
  <div class="chart-box"><div id="mohr-circle-chart" style="height:420px"></div></div>
</div>
<div class="chart-box"><div id="tensor-table-container"></div></div>`;
}

function eigenvalues3x3(sxx,syy,szz,sxy,syz,szx) {
  // Principal stresses from symmetric 3x3 tensor (Lode angle method)
  const I1 = sxx + syy + szz;
  const mean = I1 / 3;
  const dxx = sxx - mean, dyy = syy - mean, dzz = szz - mean;
  const J2 = 0.5*(dxx*dxx + dyy*dyy + dzz*dzz + 2*(sxy*sxy + syz*syz + szx*szx));
  if (J2 < 1e-20) return [mean, mean, mean];
  const J3 = dxx*(dyy*dzz - syz*syz) - sxy*(sxy*dzz - syz*szx) + szx*(sxy*syz - dyy*szx);
  const r = Math.sqrt(J2/3);
  let cos3t = J3 / (2*r*r*r);
  cos3t = Math.max(-1, Math.min(1, cos3t));
  const theta = Math.acos(cos3t) / 3;
  const s1 = mean + 2*r*Math.cos(theta);
  const s2 = mean + 2*r*Math.cos(theta - 2*Math.PI/3);
  const s3 = mean + 2*r*Math.cos(theta + 2*Math.PI/3);
  return [s1, s2, s3].sort((a,b) => b - a);
}

// Cached principal stress arrays for slider
let _tensorCache = {principals: null, vm: null, tIdx: -1};

function initTensorCharts() { updateTensorChart(); }

function updateTensorChart() {
  const idx = parseInt(document.getElementById('tensor-sel')?.value || '0');
  const t = DATA.peak_element_tensors[idx];
  if (!t) return;

  // Component traces
  const comps = [
    {arr: t.sxx, name: 'σxx', color: '#e74c3c'},
    {arr: t.syy, name: 'σyy', color: '#3498db'},
    {arr: t.szz, name: 'σzz', color: '#2ecc71'},
    {arr: t.sxy, name: 'σxy', color: '#e67e22', dash: 'dot'},
    {arr: t.syz, name: 'σyz', color: '#9b59b6', dash: 'dot'},
    {arr: t.szx, name: 'σzx', color: '#1abc9c', dash: 'dot'},
  ];
  const traces1 = comps.map(c => ({
    x: t.time, y: c.arr, name: c.name, mode: 'lines',
    line: {color: c.color, dash: c.dash || 'solid'},
  }));
  const pInfo = DATA.parts[String(t.part_id)];
  const pLabel = pInfo?.name ? `Part ${t.part_id} (${pInfo.name})` : `Part ${t.part_id}`;
  Plotly.newPlot('tensor-components-chart', traces1,
    {...PLOT_LAYOUT, title:{text:`응력 텐서 6성분 — ${pLabel}, Elem ${t.element_id} (MPa)`,font:{size:13}}}, PLOT_CONFIG);

  // Compute principals at each time step
  const s1=[], s2=[], s3=[], vmArr=[];
  for (let i=0; i<t.time.length; i++) {
    const [p1,p2,p3] = eigenvalues3x3(t.sxx[i],t.syy[i],t.szz[i],t.sxy[i],t.syz[i],t.szx[i]);
    s1.push(p1); s2.push(p2); s3.push(p3);
    const d1=p1-p2, d2=p2-p3, d3=p3-p1;
    vmArr.push(Math.sqrt(0.5*(d1*d1+d2*d2+d3*d3)));
  }
  // Compute fixed axis range: 1.3x the max |principal| across all time steps
  let globalMaxP = 0;
  for (let i=0; i<s1.length; i++) {
    globalMaxP = Math.max(globalMaxP, Math.abs(s1[i]), Math.abs(s2[i]), Math.abs(s3[i]));
  }
  const axisRange = Math.max(globalMaxP * 1.3, 1e-6);  // fixed range for all time steps

  // Find peak VM time index
  let peakVmIdx = 0;
  for (let i=1; i<vmArr.length; i++) { if (vmArr[i] > vmArr[peakVmIdx]) peakVmIdx = i; }

  _tensorCache = {s1, s2, s3, vm: vmArr, tIdx: idx, axisRange, peakVmIdx};

  Plotly.newPlot('tensor-principals-chart', [
    {x:t.time, y:s1, name:'σ₁ (max)', line:{color:'#e74c3c'}},
    {x:t.time, y:s2, name:'σ₂ (mid)', line:{color:'#f39c12'}},
    {x:t.time, y:s3, name:'σ₃ (min)', line:{color:'#3498db'}},
    {x:t.time, y:vmArr, name:'Von Mises', line:{color:'#2c3e50',dash:'dot'}},
  ], {...PLOT_LAYOUT, title:{text:`주응력 & Von Mises — Elem ${t.element_id} (MPa)`,font:{size:13}}}, PLOT_CONFIG);

  // Setup time slider
  const slider = document.getElementById('tensor-time-slider');
  if (slider) {
    slider.max = t.time.length - 1;
    // Set to peak time
    const peakIdx = t.time.indexOf(t.peak_time) >= 0 ? t.time.indexOf(t.peak_time) :
      vmArr.reduce((best,v,i) => v > vmArr[best] ? i : best, 0);
    slider.value = peakIdx;
  }
  updateEllipsoidAndMohr();
}

function makeEllipsoidSurface(a, b, c, N) {
  // Parametric ellipsoid: x=a*sin(th)*cos(ph), y=b*sin(th)*sin(ph), z=c*cos(th)
  // Handle negative principal stresses: use absolute values for shape, color by sign
  const aa = Math.abs(a) || 0.01, bb = Math.abs(b) || 0.01, cc = Math.abs(c) || 0.01;
  const xs=[], ys=[], zs=[], cs=[];
  for (let i=0; i<=N; i++) {
    const th = Math.PI * i / N;
    const xr=[], yr=[], zr=[], cr=[];
    for (let j=0; j<=N; j++) {
      const ph = 2*Math.PI * j / N;
      const x = aa * Math.sin(th) * Math.cos(ph);
      const y = bb * Math.sin(th) * Math.sin(ph);
      const z = cc * Math.cos(th);
      xr.push(x); yr.push(y); zr.push(z);
      // Color by distance from origin (stress intensity)
      cr.push(Math.sqrt(x*x+y*y+z*z));
    }
    xs.push(xr); ys.push(yr); zs.push(zr); cs.push(cr);
  }
  return {xs, ys, zs, cs};
}

function makeMohrCircles(p1, p2, p3) {
  // 3 Mohr's circles: (σ₁,σ₂), (σ₂,σ₃), (σ₁,σ₃)
  const circles = [];
  const pairs = [[p1,p2,'#e74c3c','σ₁-σ₂'],[p2,p3,'#3498db','σ₂-σ₃'],[p1,p3,'#2ecc71','σ₁-σ₃']];
  for (const [sa,sb,col,name] of pairs) {
    const center = (sa + sb) / 2;
    const radius = Math.abs(sa - sb) / 2;
    const cx=[], cy=[];
    const N = 100;
    for (let i=0; i<=N; i++) {
      const angle = 2*Math.PI*i/N;
      cx.push(center + radius*Math.cos(angle));
      cy.push(radius*Math.sin(angle));
    }
    circles.push({x:cx, y:cy, color:col, name, center, radius});
  }
  return circles;
}

function jumpToPeakTime() {
  const tc = _tensorCache;
  if (tc.peakVmIdx === undefined) return;
  const slider = document.getElementById('tensor-time-slider');
  if (slider) { slider.value = tc.peakVmIdx; }
  updateEllipsoidAndMohr();
}

function updateEllipsoidAndMohr() {
  const idx = parseInt(document.getElementById('tensor-sel')?.value || '0');
  const t = DATA.peak_element_tensors[idx];
  if (!t) return;
  const si = parseInt(document.getElementById('tensor-time-slider')?.value || '0');
  const tc = _tensorCache;
  if (!tc.s1 || tc.tIdx !== idx) return;

  const p1=tc.s1[si], p2=tc.s2[si], p3=tc.s3[si], vmVal=tc.vm[si];
  const timeVal = t.time[si];
  document.getElementById('tensor-time-label').textContent =
    `t = ${fmt(timeVal,6)}  |  σ₁=${fmt(p1)} σ₂=${fmt(p2)} σ₃=${fmt(p3)} VM=${fmt(vmVal)}`;

  // ── Stress Ellipsoid (3D) ──
  const ell = makeEllipsoidSurface(p1, p2, p3, 24);
  const ellTrace = {
    type: 'surface', x: ell.xs, y: ell.ys, z: ell.zs,
    surfacecolor: ell.cs, colorscale: 'YlOrRd', showscale: false,
    opacity: 0.85,
    contours: {x:{show:true,color:'rgba(0,0,0,0.15)',width:1},
               y:{show:true,color:'rgba(0,0,0,0.15)',width:1},
               z:{show:true,color:'rgba(0,0,0,0.15)',width:1}},
  };
  // Axis lines — use fixed range (1.3x global max) for consistent scale across time
  const maxR = tc.axisRange;
  const axTraces = [
    {type:'scatter3d',x:[-maxR,maxR],y:[0,0],z:[0,0],mode:'lines',line:{color:'#e74c3c',width:3},name:'σ₁ axis',showlegend:true},
    {type:'scatter3d',x:[0,0],y:[-maxR,maxR],z:[0,0],mode:'lines',line:{color:'#f39c12',width:3},name:'σ₂ axis',showlegend:true},
    {type:'scatter3d',x:[0,0],y:[0,0],z:[-maxR,maxR],mode:'lines',line:{color:'#3498db',width:3},name:'σ₃ axis',showlegend:true},
  ];
  // Sign markers at ellipsoid tips
  const tipMarkers = {
    type:'scatter3d', mode:'markers+text',
    x:[Math.abs(p1)*Math.sign(p1)||0.01, 0, 0],
    y:[0, Math.abs(p2)*Math.sign(p2)||0.01, 0],
    z:[0, 0, Math.abs(p3)*Math.sign(p3)||0.01],
    text:[`σ₁=${fmt(p1)}`,`σ₂=${fmt(p2)}`,`σ₃=${fmt(p3)}`],
    textposition:'top center', textfont:{size:10},
    marker:{size:4,color:['#e74c3c','#f39c12','#3498db']},
    showlegend:false,
  };
  const layout3d = {
    ...PLOT_LAYOUT, margin:{l:0,r:0,t:40,b:0},
    title:{text:`Stress Ellipsoid (t=${fmt(timeVal,5)})`,font:{size:12}},
    scene:{
      xaxis:{title:'σ₁ (MPa)',range:[-maxR,maxR]},
      yaxis:{title:'σ₂ (MPa)',range:[-maxR,maxR]},
      zaxis:{title:'σ₃ (MPa)',range:[-maxR,maxR]},
      aspectmode:'cube',
      camera:{eye:{x:1.5,y:1.5,z:1.0}},
    },
  };
  Plotly.newPlot('stress-ellipsoid-chart', [ellTrace,...axTraces,tipMarkers], layout3d, PLOT_CONFIG);

  // ── Mohr's Circles (2D) ──
  const circles = makeMohrCircles(p1, p2, p3);
  const mohrTraces = circles.map(c => ({
    x:c.x, y:c.y, mode:'lines', name:c.name,
    line:{color:c.color, width:2},
  }));
  // Principal stress markers on σ axis
  mohrTraces.push({
    x:[p1,p2,p3], y:[0,0,0], mode:'markers+text',
    text:[`σ₁=${fmt(p1)}`,`σ₂=${fmt(p2)}`,`σ₃=${fmt(p3)}`],
    textposition:['top right','top center','top left'],
    textfont:{size:10}, marker:{size:8,color:['#e74c3c','#f39c12','#3498db']},
    showlegend:false,
  });
  const mohrMax = circles[2]?.center + circles[2]?.radius || 100;
  const mohrMin = circles[2]?.center - circles[2]?.radius || -100;
  const tauMax = circles[2]?.radius || 50;
  Plotly.newPlot('mohr-circle-chart', mohrTraces, {
    ...PLOT_LAYOUT, margin:{l:50,r:20,t:40,b:50},
    title:{text:`Mohr's Circles (t=${fmt(timeVal,5)})`,font:{size:12}},
    xaxis:{title:'σ (MPa)',range:[mohrMin*1.15,mohrMax*1.15],zeroline:true,zerolinewidth:1},
    yaxis:{title:'τ (MPa)',range:[-tauMax*1.3,tauMax*1.3],zeroline:true,zerolinewidth:1,scaleanchor:'x'},
    showlegend:true, legend:{x:0,y:1,font:{size:10}},
  }, PLOT_CONFIG);

  // Table
  const hydro = (p1+p2+p3)/3;
  const triax = vmVal > 1e-10 ? hydro/vmVal : 0;
  const maxShear = (p1-p3)/2;
  document.getElementById('tensor-table-container').innerHTML = `
    <div class="sec-title">텐서 상세 (t = ${fmt(timeVal,6)})</div>
    <table class="data-table">
      <tr><th>성분</th><th>값 (MPa)</th></tr>
      <tr><td>σxx</td><td class="num">${fmt(t.sxx[si])}</td></tr>
      <tr><td>σyy</td><td class="num">${fmt(t.syy[si])}</td></tr>
      <tr><td>σzz</td><td class="num">${fmt(t.szz[si])}</td></tr>
      <tr><td>σxy</td><td class="num">${fmt(t.sxy[si])}</td></tr>
      <tr><td>σyz</td><td class="num">${fmt(t.syz[si])}</td></tr>
      <tr><td>σzx</td><td class="num">${fmt(t.szx[si])}</td></tr>
      <tr><td colspan="2" style="border-top:2px solid var(--border)"></td></tr>
      <tr><td>σ₁ (max principal)</td><td class="num" style="color:#e74c3c">${fmt(p1)}</td></tr>
      <tr><td>σ₂ (mid principal)</td><td class="num" style="color:#f39c12">${fmt(p2)}</td></tr>
      <tr><td>σ₃ (min principal)</td><td class="num" style="color:#3498db">${fmt(p3)}</td></tr>
      <tr><td>Von Mises</td><td class="num">${fmt(vmVal)}</td></tr>
      <tr><td>Hydrostatic (σm)</td><td class="num">${fmt(hydro)}</td></tr>
      <tr><td>Max Shear (τmax)</td><td class="num">${fmt(maxShear)}</td></tr>
      <tr><td>Triaxiality (σm/σvm)</td><td class="num">${fmt(triax,4)}</td></tr>
      <tr><td>Lode Angle Parameter</td><td class="num">${fmt(lodeAngle(p1,p2,p3),4)}</td></tr>
    </table>`;
}

function lodeAngle(s1,s2,s3) {
  // Normalized Lode angle parameter: ξ = (2σ₂-σ₁-σ₃)/(σ₁-σ₃)
  const denom = s1-s3;
  if (Math.abs(denom) < 1e-10) return 0;
  return (2*s2-s1-s3)/denom;
}

// ── Motion ────────────────────────────────────────────────────────────
function renderMotion() {
  const mEntries = Object.entries(DATA.motion)
    .filter(([pid]) => partMatchesFilter(pid, DATA.parts[pid]))
    .sort((a,b) => (b[1].peak_disp_mag ?? -Infinity) - (a[1].peak_disp_mag ?? -Infinity));
  // 미계측 파트는 막대로 그리지 않는다 — 0 막대는 '안 움직였다' 로 읽힌다.
  const measured = mEntries.filter(([,m]) => m.peak_disp_mag !== null && m.peak_disp_mag !== undefined);
  const unmeasured = mEntries.length - measured.length;
  const maxD = measured[0]?.[1].peak_disp_mag || 1;

  const dispBars = measured.map(([pid, m]) => {
    const pct = (m.peak_disp_mag / maxD * 100).toFixed(1);
    const node = m.peak_disp_node ? ' <span class="hs-dim">node #'+m.peak_disp_node+'</span>' : '';
    return `<div class="bar-row">
      <div class="bar-label" title="${m.part_name}">${m.part_name ? 'Part '+pid+' ('+m.part_name+')' : 'Part '+pid}</div>
      <div class="bar-track"><div class="bar-fill" style="background:var(--accent2);width:${pct}%"></div></div>
      <div class="bar-val">${fmt(m.peak_disp_mag)} mm${node}</div>
    </div>`;
  }).join('')
  + (unmeasured ? `<div class="hs-dim" style="margin-top:6px">${unmeasured}개 파트는 절점 최대 변위 미계측 (motion CSV 에 Max_Disp_Mag 열 없음)</div>` : '');

  const opts = mEntries.map(([pid, m]) =>
    `<option value="${pid}">${m.part_name ? 'Part '+pid+' ('+m.part_name+')' : 'Part '+pid}</option>`).join('');

  return `
<div class="sec-title">최대 변위 순위</div>
<div class="chart-box">${dispBars||'<div style="color:var(--fg2)">데이터 없음</div>'}</div>
<div class="sec-title">시계열</div>
<div class="part-selector">
  <label>부품 선택:</label>
  <select id="motion-part-sel" onchange="updateMotionChart()">${opts}</select>
</div>
<div class="chart-box"><div id="motion-disp-chart" class="plotly-chart" style="height:280px"></div></div>
<div class="chart-box"><div id="motion-disp-xyz-chart" class="plotly-chart" style="height:260px"></div></div>
<div class="chart-box"><div id="motion-vel-chart" class="plotly-chart" style="height:250px"></div></div>
<div class="chart-box"><div id="motion-acc-chart" class="plotly-chart" style="height:240px"></div></div>`;
}

function initMotionCharts() { updateMotionChart(); }

function updateMotionChart() {
  const pid = document.getElementById('motion-part-sel')?.value;
  if (!pid || !DATA.motion[pid]) return;
  const m = DATA.motion[pid];
  Plotly.newPlot('motion-disp-chart', [{
    x: m.t, y: m.disp_mag, name: 'Avg |U|', type: 'scatter', mode: 'lines',
    line: {color: COLORS[1]}
  }, {
    x: m.t, y: m.max_disp_mag, name: 'Max |U|', type: 'scatter', mode: 'lines',
    line: {color: COLORS[1], dash: 'dot'}
  }], {...PLOT_LAYOUT, title: {text: `변위 크기 (mm) — Part ${m.part_id}${m.part_name ? ' (' + m.part_name + ')' : ''}`, font:{size:13}}}, PLOT_CONFIG);

  // X/Y/Z directional displacement
  if (m.disp_x?.some(v => v !== 0) || m.disp_y?.some(v => v !== 0) || m.disp_z?.some(v => v !== 0)) {
    Plotly.newPlot('motion-disp-xyz-chart', [
      {x: m.t, y: m.disp_x, name: 'Ux', mode: 'lines', line: {color: '#e05555'}},
      {x: m.t, y: m.disp_y, name: 'Uy', mode: 'lines', line: {color: '#4caf6f'}},
      {x: m.t, y: m.disp_z, name: 'Uz', mode: 'lines', line: {color: '#4f8ef7'}},
    ], {...PLOT_LAYOUT, title: {text: `변위 성분 X/Y/Z (mm) — Part ${m.part_id}${m.part_name ? ' (' + m.part_name + ')' : ''}`, font:{size:13}}}, PLOT_CONFIG);
  }

  if (m.vel_mag && m.vel_mag.some(v => v > 0)) {
    Plotly.newPlot('motion-vel-chart', [{
      x: m.t, y: m.vel_mag, name: 'Avg |V|', type: 'scatter', mode: 'lines',
      line: {color: COLORS[3]}
    }], {...PLOT_LAYOUT, title: {text: `속도 크기 — Part ${m.part_id}${m.part_name ? ' (' + m.part_name + ')' : ''}`, font:{size:13}}}, PLOT_CONFIG);
  }

  if (m.acc_mag && m.acc_mag.some(v => v > 0)) {
    Plotly.newPlot('motion-acc-chart', [{
      x: m.t, y: m.acc_mag, name: 'Avg |A|', type: 'scatter', mode: 'lines',
      line: {color: COLORS[4]}
    }], {...PLOT_LAYOUT, title: {text: `가속도 크기 — Part ${m.part_id}${m.part_name ? ' (' + m.part_name + ')' : ''}`, font:{size:13}}}, PLOT_CONFIG);
  }
}

// ── Deep Dive ─────────────────────────────────────────────────────────
function renderDeepDive() {
  const opts = filteredParts()
    .sort((a,b) => b[1].peak_stress - a[1].peak_stress)
    .map(([pid, p]) => `<option value="${pid}">${partLabel(pid, p)}</option>`).join('');
  return `
<div class="part-selector">
  <label>부품 선택:</label>
  <select id="dd-part-sel" onchange="updateDeepDive()">${opts}</select>
</div>
<div id="dd-kpis" class="kpi-grid"></div>
<div id="dd-renders"></div>
<div class="chart-box"><div id="dd-stress-chart" style="height:260px"></div></div>
<div class="chart-box"><div id="dd-strain-chart" style="height:240px"></div></div>
<div class="chart-box"><div id="dd-disp-chart" style="height:240px"></div></div>
<div class="chart-box"><div id="dd-disp-xyz-chart" style="height:230px"></div></div>
<div class="chart-box"><div id="dd-vel-chart" style="height:220px"></div></div>
<div class="chart-box"><div id="dd-acc-chart" style="height:220px"></div></div>`;
}

function initDeepDive() { updateDeepDive(); }

function updateDeepDive() {
  const pid = document.getElementById('dd-part-sel')?.value;
  if (!pid) return;
  const p = DATA.parts[pid];
  const st = DATA.stress.find(s => String(s.part_id) === pid);
  const sr = DATA.strain.find(s => String(s.part_id) === pid);
  const mo = DATA.motion[pid];

  // KPI cards
  const sf = p?.safety_factor;
  const sfClass = sf === null || sf === undefined ? '' : sf >= 1.0 ? 'kpi-ok' : sf >= 0.85 ? 'kpi-warn' : 'kpi-err';
  let kpiHtml = `
  <div class="kpi-card"><div class="kpi-label">피크 응력</div><div class="kpi-value">${fmt(p?.peak_stress)}</div><div class="kpi-unit">MPa (t=${fmt(p?.time_of_peak_stress,4)})</div></div>
  <div class="kpi-card"><div class="kpi-label">피크 변형률</div><div class="kpi-value">${fmt(p?.peak_strain,4)}</div><div class="kpi-unit">—</div></div>
  <div class="kpi-card"><div class="kpi-label">Max Principal (σ₁)</div><div class="kpi-value">${fmt(p?.peak_max_principal)}</div><div class="kpi-unit">MPa</div></div>
  <div class="kpi-card"><div class="kpi-label">Min Principal (σ₃)</div><div class="kpi-value">${fmt(p?.peak_min_principal)}</div><div class="kpi-unit">MPa</div></div>
  ${p?.peak_max_principal_strain ? `<div class="kpi-card"><div class="kpi-label">Max Principal Strain (ε₁)</div><div class="kpi-value">${fmt(p?.peak_max_principal_strain,4)}</div><div class="kpi-unit">—</div></div>` : ''}
  ${p?.peak_min_principal_strain ? `<div class="kpi-card"><div class="kpi-label">Min Principal Strain (ε₃)</div><div class="kpi-value">${fmt(p?.peak_min_principal_strain,4)}</div><div class="kpi-unit">—</div></div>` : ''}
  <div class="kpi-card"><div class="kpi-label">피크 변위</div><div class="kpi-value">${fmt(p?.peak_disp_mag)}</div><div class="kpi-unit">${p?.peak_disp_mag === null || p?.peak_disp_mag === undefined ? (p?.peak_disp_reason || '미계측') : 'mm (절점 최대' + (p?.peak_disp_node ? ' #' + p.peak_disp_node : '') + ')'}</div></div>
  <div class="kpi-card"><div class="kpi-label">피크 가속도</div><div class="kpi-value">${fmt(p?.peak_acc_mag)}</div><div class="kpi-unit">—</div></div>`;
  if (sf !== null && sf !== undefined) {
    kpiHtml += `<div class="kpi-card"><div class="kpi-label">Safety Factor</div><div class="kpi-value ${sfClass}">${fmt(sf,3)}</div><div class="kpi-unit">σ_yield=${fmt(DATA.yield_stress)} MPa</div></div>`;
  }
  if (p?.peak_element_id) {
    kpiHtml += `<div class="kpi-card"><div class="kpi-label">피크 Element</div><div class="kpi-value" style="font-size:1rem">#${p.peak_element_id}</div><div class="kpi-unit">max stress 위치</div></div>`;
  } else if (p?.peak_element_reason) {
    // 미기록을 빈칸으로 두면 '없다' 가 아니라 '안 봤다' 로 읽힌다 — 사유를 띄운다.
    kpiHtml += `<div class="kpi-card"><div class="kpi-label">피크 Element</div><div class="kpi-value" style="font-size:1rem">—</div><div class="kpi-unit">${p.peak_element_reason}</div></div>`;
  }
  document.getElementById('dd-kpis').innerHTML = kpiHtml;

  // Per-part renders
  const partFolder = 'part_' + pid;
  const partVideos = (DATA.renders || []).filter(r => r.startsWith(partFolder + '/'));
  const ddRendersEl = document.getElementById('dd-renders');
  if (partVideos.length > 0) {
    const axisOrder = ['x', 'y', 'z'];
    const sorted = partVideos.sort((a,b) => {
      const ai = axisOrder.findIndex(x => a.includes('_' + x + '.'));
      const bi = axisOrder.findIndex(x => b.includes('_' + x + '.'));
      return (ai < 0 ? 99 : ai) - (bi < 0 ? 99 : bi);
    });
    const labels = {x: 'X-Section (YZ plane)', y: 'Y-Section (XZ plane)', z: 'Z-Section (XY plane)'};
    ddRendersEl.innerHTML = `
      <div class="sec-title">단면 렌더링</div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:10px;margin-bottom:16px">
        ${sorted.map(r => {
          const ax = axisOrder.find(x => r.includes('_' + x + '.')) || '';
          const label = labels[ax] || ax.toUpperCase();
          return `<div class="render-card" style="cursor:pointer" onclick="openModal('renders/${r}','${label}')">
            <video muted loop playsinline onmouseenter="this.play()" onmouseleave="this.pause();this.currentTime=0">
              <source src="renders/${r}" type="video/mp4"></video>
            <div style="text-align:center;font-size:0.8rem;color:var(--fg2);padding:4px 0">${label}</div>
          </div>`;
        }).join('')}
      </div>`;
  } else {
    ddRendersEl.innerHTML = '';
  }

  // Charts
  if (st) Plotly.newPlot('dd-stress-chart',
    [{x:st.t, y:st.max_vals, name:'Max', line:{color:COLORS[0]}},
     {x:st.t, y:st.avg_vals, name:'Avg', line:{color:COLORS[0],dash:'dot'}}],
    {...PLOT_LAYOUT, title:{text:'Von Mises Stress (MPa)',font:{size:12}}}, PLOT_CONFIG);
  if (sr) Plotly.newPlot('dd-strain-chart',
    [{x:sr.t, y:sr.max_vals, name:'Max', line:{color:COLORS[2]}},
     {x:sr.t, y:sr.avg_vals, name:'Avg', line:{color:COLORS[2],dash:'dot'}}],
    {...PLOT_LAYOUT, title:{text:'Eff. Plastic Strain',font:{size:12}}}, PLOT_CONFIG);
  if (mo) {
    Plotly.newPlot('dd-disp-chart',
      [{x:mo.t, y:mo.disp_mag, name:'Avg |U|', line:{color:COLORS[1]}},
       {x:mo.t, y:mo.max_disp_mag, name:'Max |U|', line:{color:COLORS[1],dash:'dot'}}],
      {...PLOT_LAYOUT, title:{text:'변위 크기 (mm)',font:{size:12}}}, PLOT_CONFIG);
    if (mo.disp_x?.some(v => v !== 0) || mo.disp_y?.some(v => v !== 0) || mo.disp_z?.some(v => v !== 0)) {
      Plotly.newPlot('dd-disp-xyz-chart', [
        {x:mo.t, y:mo.disp_x, name:'Ux', mode:'lines', line:{color:'#e05555'}},
        {x:mo.t, y:mo.disp_y, name:'Uy', mode:'lines', line:{color:'#4caf6f'}},
        {x:mo.t, y:mo.disp_z, name:'Uz', mode:'lines', line:{color:'#4f8ef7'}},
      ], {...PLOT_LAYOUT, title:{text:'변위 성분 X/Y/Z (mm)',font:{size:12}}}, PLOT_CONFIG);
    }
    if (mo.vel_mag?.some(v => v > 0)) {
      Plotly.newPlot('dd-vel-chart',
        [{x:mo.t, y:mo.vel_mag, name:'Avg |V|', line:{color:COLORS[3]}}],
        {...PLOT_LAYOUT, title:{text:'속도 크기',font:{size:12}}}, PLOT_CONFIG);
    }
    if (mo.acc_mag?.some(v => v > 0)) {
      Plotly.newPlot('dd-acc-chart',
        [{x:mo.t, y:mo.acc_mag, name:'Avg |A|', line:{color:COLORS[4]}}],
        {...PLOT_LAYOUT, title:{text:'가속도 크기',font:{size:12}}}, PLOT_CONFIG);
    }
  }
}

// ── Energy ────────────────────────────────────────────────────────────
function renderEnergy() {
  const g = DATA.glstat;
  if (!g) return '<div class="err-box">glstat 데이터 없음</div>';

  const erMin = g.energy_ratio_min;
  const erMax = g.energy_ratio_max;
  // 에너지 비율 = total energy / initial energy
  // 소산(<1.0): 고무·소성·감쇠 해석에서 정상. 생성(>1.0): 수치 불안정 가능.
  const warn = (erMax !== null && erMax > 1.1)
    ? `<div class="err-box">에너지 비율 이상: max=${fmt(erMax,4)} — 에너지가 생성됨 (수치 불안정 가능)</div>` :
    (erMax !== null && erMax > 1.05)
    ? `<div class="warn-box">에너지 비율 주의: max=${fmt(erMax,4)} — 에너지 소폭 증가</div>` : '';
  const massWarn = g.has_mass_added
    ? '<div class="warn-box">질량 추가 감지 — 시간 스텝 조절에 의한 인위적 질량 증가 확인 필요</div>' : '';

  return `${warn}${massWarn}
<div class="sec-title">에너지 이력</div>
<div class="chart-box"><div id="energy-main-chart" style="height:320px"></div></div>
<div class="sec-title">에너지 비율 (total / initial)</div>
<div class="chart-box"><div id="energy-ratio-chart" style="height:240px"></div></div>`;
}

function initEnergyCharts() {
  const g = DATA.glstat;
  if (!g || !g.t.length) return;
  Plotly.newPlot('energy-main-chart', [
    {x:g.t, y:g.total_energy,    name:'Total',    line:{color:COLORS[0]}},
    {x:g.t, y:g.kinetic_energy,  name:'Kinetic',  line:{color:COLORS[1]}},
    {x:g.t, y:g.internal_energy, name:'Internal', line:{color:COLORS[2]}},
    {x:g.t, y:g.hourglass_energy,name:'Hourglass',line:{color:COLORS[3], dash:'dot'}},
  ], {...PLOT_LAYOUT, title:{text:'에너지 이력',font:{size:13}}}, PLOT_CONFIG);

  const refLine  = {x:g.t, y:g.t.map(()=>1.0),  name:'ideal', line:{color:'#444',dash:'dash'}, showlegend:false};
  const warnHigh = {x:g.t, y:g.t.map(()=>1.05), name:'+5%',  line:{color:'#f5a623',dash:'dot'}, showlegend:true};
  Plotly.newPlot('energy-ratio-chart', [
    {x:g.t, y:g.energy_ratio, name:'에너지 비율', line:{color:COLORS[4]}},
    refLine, warnHigh,
  ], {...PLOT_LAYOUT, title:{text:'에너지 비율 (total / initial)',font:{size:13}}}, PLOT_CONFIG);
}

// ── Contact & Energy (binout) ─────────────────────────────────────────
function renderContact() {
  const bn = DATA.binout;
  if (!bn) return '<div class="err-box">binout 데이터 없음</div>';

  let html = '';

  // 계측 신뢰 — 값 자체보다 먼저 "믿어도 되는가" 를 보여준다.
  // 계측 안 됐으면 사유를 적고 아래 표는 그대로 진행한다(에러 아님).
  const cmv = DATA.contact_metrics || {};
  if (cmv.reason && !cmv.available) {
    html += `<div class="sec-title">접촉력 계측</div>
      <div class="chart-box"><p style="color:#888">${cmv.reason}</p></div>`;
  } else if (cmv.available) {
    const n3 = (cmv.checks || {}).newton3 || {};
    const tm = (cmv.checks || {}).timing || {};
    const se = (cmv.checks || {}).sliding_energy || {};
    const ex = v => (v == null ? '&mdash;'
                   : (Math.abs(v) < 1e-4 ? v.toExponential(1) : (+v).toFixed(4)));
    html += `<div class="sec-title">접촉력 계측 신뢰</div>
<div class="chart-box">
  <table class="data-table"><thead><tr><th>검증</th><th>값</th><th>의미</th></tr></thead><tbody>
   <tr><td>뉴턴 3법칙 최악</td><td class="num">${ex(n3.max_rel)}</td>
       <td>master/slave 충격량 상대차 (검증 ${n3.n_checked || 0}건, 한쪽만 ${n3.n_one_sided || 0}건)</td></tr>
   <tr><td>접촉 동시성</td><td class="num">${ex(tm.peak_spread)}</td>
       <td>인터페이스 피크 시각 분포 폭 (접촉 ${tm.n_engaged || 0}건, 최초 ${ex(tm.first_engage)})</td></tr>
   <tr><td>sliding 에너지</td><td class="num">${ex(se.rel)}</td>
       <td>glstat ${ex(se.glstat_sliding)} vs sleout 합 ${ex(se.sleout_sum)}</td></tr>
  </tbody></table>
  <p style="color:#888;font-size:12px;margin-top:6px">
    절대 합격 기준은 두지 않는다 — 값만 보고한다. 판단은 사람이 한다.
    ${cmv.note ? '<br>' + cmv.note : ''}</p>
</div>`;
  }

  // rcforc: interface peak force table + selector
  if (bn.rcforc && bn.rcforc.length) {
    const slaves = bn.rcforc.filter(r => r.side === 0);
    // 계측표는 contact_metrics 를 우선 쓴다. bn.rcforc 의 slave 측만 보면
    // SSTYP=5(반대편이 'ALL') 정의에서 값이 0 으로 나온다 — 실측 CID 172 는
    // slave 0.2 / master 36251.5 였다. 계측 모듈은 큰 쪽으로 잰다.
    const cm = DATA.contact_metrics || {};
    let rows;
    if (cm.available && (cm.interfaces || []).length) {
      const fx = v => (v == null ? '&mdash;' : fmt(v));
      // 시각은 1e-5 수준이라 fmt(2자리)로는 전부 0.00 이 된다 — 지수로 쓴다.
      const ft = v => (v == null ? '&mdash;'
                     : (Math.abs(v) >= 0.01 ? (+v).toFixed(4) : (+v).toExponential(2)));
      rows = cm.interfaces.slice().sort((a,b) => (b.peak_force||0)-(a.peak_force||0))
        .map(i => {
          const pair = i.resolved
            ? `${i.src_name} &rarr; ${i.dst_name}`
            : `<span title="파트로 분해되지 않는 접촉 — 인터페이스 단위 합력이다">${i.src_name || i.src} &rarr; ${i.dst_name || i.dst} &#9888;</span>`;
          const win = (i.engage_t0 == null) ? '&mdash;'
            : `${ft(i.engage_t0)} ~ ${ft(i.engage_t1)}`;
          return `<tr><td>${i.cid}</td><td>${i.name || ''}</td><td>${pair}</td>`
               + `<td class="num">${fx(i.peak_force)}</td><td class="num">${ft(i.peak_time)}</td>`
               + `<td class="num">${fx(i.impulse)}</td><td class="num">${win}</td></tr>`;
        }).join('');
    } else {
      rows = slaves.map(r =>
        `<tr><td>${r.id}</td><td>${r.name}</td><td>&mdash;</td><td class="num">${fmt(r.peak_fmag)}</td>`
        + `<td>&mdash;</td><td>&mdash;</td><td>&mdash;</td></tr>`
      ).join('');
    }
    const opts = slaves.map(r =>
      `<option value="${r.id}">${r.name} (id=${r.id})</option>`).join('');
    html += `
<div class="sec-title">접촉 인터페이스 피크 합력</div>
<div class="chart-box">
  <table class="data-table"><thead><tr><th>CID</th><th>이름</th><th>파트쌍</th>
    <th>피크 합력</th><th>피크 시각</th><th>충격량</th><th>접촉 구간</th></tr></thead>
  <tbody>${rows}</tbody></table>
</div>
<div class="sec-title">접촉력 시계열</div>
<div class="part-selector">
  <label>인터페이스:</label>
  <select id="rcforc-sel" onchange="updateRcforcChart()">${opts}</select>
</div>
<div class="chart-box"><div id="rcforc-chart" class="plotly-chart" style="height:300px"></div></div>`;
  }

  // matsum: per-part internal energy
  if (bn.matsum) {
    const ms = bn.matsum;
    const opts = ms.part_ids.map((pid, i) =>
      `<option value="${i}" ${partMatchesFilter(pid, {name: ms.part_names[i]}) ? '' : 'hidden'}>Part ${pid}${ms.part_names[i] ? ' (' + ms.part_names[i] + ')' : ''}</option>`)
      .filter((_, i) => partMatchesFilter(ms.part_ids[i], {name: ms.part_names[i]}))
      .join('');
    html += `
<div class="sec-title">재료별 내부 에너지 (matsum)</div>
<div class="part-selector">
  <label>재료:</label>
  <select id="matsum-sel" onchange="updateMatsumChart()">${opts}</select>
</div>
<div class="chart-box"><div id="matsum-chart" class="plotly-chart" style="height:280px"></div></div>`;
  }

  // sleout: sliding energy
  if (bn.sleout && bn.sleout.length) {
    const opts = bn.sleout.map(s =>
      `<option value="${s.id}">${s.name} (id=${s.id})</option>`).join('');
    html += `
<div class="sec-title">슬라이딩 에너지 (sleout)</div>
<div class="part-selector">
  <label>인터페이스:</label>
  <select id="sleout-sel" onchange="updateSleoutChart()">${opts}</select>
</div>
<div class="chart-box"><div id="sleout-chart" class="plotly-chart" style="height:260px"></div></div>`;
  }

  return html || '<div class="warn-box">binout 데이터 없음</div>';
}

function initContactCharts() {
  updateRcforcChart();
  updateMatsumChart();
  updateSleoutChart();
}

function updateRcforcChart() {
  const bn = DATA.binout;
  if (!bn || !bn.rcforc) return;
  const sel = document.getElementById('rcforc-sel');
  if (!sel) return;
  const id = parseInt(sel.value);
  const ifc = bn.rcforc.find(r => r.id === id && r.side === 0);
  if (!ifc) return;
  Plotly.newPlot('rcforc-chart', [
    {x: ifc.t, y: ifc.fx, name: 'Fx', line: {color: COLORS[0]}},
    {x: ifc.t, y: ifc.fy, name: 'Fy', line: {color: COLORS[1]}},
    {x: ifc.t, y: ifc.fz, name: 'Fz', line: {color: COLORS[2]}},
    {x: ifc.t, y: ifc.fmag, name: '|F|', line: {color: COLORS[3], width: 2}},
  ], {...PLOT_LAYOUT, title: {text: `접촉력 — ${ifc.name}`, font:{size:13}}}, PLOT_CONFIG);
}

function updateMatsumChart() {
  const bn = DATA.binout;
  if (!bn || !bn.matsum) return;
  const sel = document.getElementById('matsum-sel');
  if (!sel) return;
  const idx = parseInt(sel.value);
  const ms = bn.matsum;
  const ie = ms.internal_energy.map(row => row[idx]);
  const ke = ms.kinetic_energy.map(row => row[idx]);
  // 시각과 짝지을 수 없어 비운 표는 빈 그래프 대신 사유를 보인다
  const notes = [ms.internal_energy_note, ms.kinetic_energy_note].filter(Boolean);
  Plotly.newPlot('matsum-chart', [
    {x: ms.t, y: ie, name: '내부 에너지', line: {color: COLORS[2]}},
    {x: ms.t, y: ke, name: '운동 에너지', line: {color: COLORS[1]}},
  ], {...PLOT_LAYOUT, title: {text: `에너지 — Part ${ms.part_ids[idx]}${ms.part_names[idx] ? ' (' + ms.part_names[idx] + ')' : ''}`, font:{size:13}},
      annotations: notes.length ? [{text: notes.join('<br>'), xref: 'paper', yref: 'paper', x: 0.5, y: 0.5, showarrow: false}] : []}, PLOT_CONFIG);
}

function updateSleoutChart() {
  const bn = DATA.binout;
  if (!bn || !bn.sleout) return;
  const sel = document.getElementById('sleout-sel');
  if (!sel) return;
  const id = parseInt(sel.value);
  const ifc = bn.sleout.find(s => s.id === id);
  if (!ifc) return;
  Plotly.newPlot('sleout-chart', [
    {x: ifc.t, y: ifc.total_energy, name: '총 슬라이딩 에너지', line: {color: COLORS[4]}},
    {x: ifc.t, y: ifc.friction_energy, name: '마찰 에너지', line: {color: COLORS[5], dash: 'dot'}},
  ], {...PLOT_LAYOUT, title: {text: `슬라이딩 에너지 — ${ifc.name}`, font:{size:13}}}, PLOT_CONFIG);
}

// ── Render Gallery ────────────────────────────────────────────────────
function _mediaCard(relPath, label) {
  const ext = relPath.split('.').pop().toLowerCase();
  const src = 'renders/' + relPath;
  const inner = (ext === 'mp4' || ext === 'webm')
    ? `<video controls loop muted playsinline><source src="${src}" type="video/${ext}"></video>`
    : `<img src="${src}" alt="${label}" loading="lazy">`;
  return `<div class="render-card" onclick="openModal('${src}','${label}')">
    <div class="render-axis-label">${label}</div>
    ${inner}
    <div class="render-name">${relPath}</div>
  </div>`;
}

function _axisLabel(relPath) {
  // Try filename-based axis first (e.g. overview_z.mp4, part_4_x.mp4)
  const mFile = relPath.match(/_([xyz])(?:_final)?\.\w+$/i);
  if (mFile) {
    const ax = mFile[1].toUpperCase();
    return relPath.includes('final') ? ax + '축 (최종)' : ax + '축';
  }
  // Fall back to folder-based axis (e.g. section_view_z/section_view.mp4)
  const mFolder = relPath.match(/^(?:.*\/)?[^/]*_([xyz])\/[^/]+$/i);
  if (mFolder) return mFolder[1].toUpperCase() + '축';
  return relPath.replace(/\.\w+$/, '');
}

function _folderHtml(folderId, title, subtitle, renders, openByDefault) {
  const axisOrder = ['x','y','z'];
  renders.sort((a,b) => {
    const ax = (a.match(/_([xyz])(?:_final)?\./i)||[])[1]||'';
    const bx = (b.match(/_([xyz])(?:_final)?\./i)||[])[1]||'';
    return axisOrder.indexOf(ax.toLowerCase()) - axisOrder.indexOf(bx.toLowerCase());
  });
  const cards = renders.map(r => _mediaCard(r, _axisLabel(r))).join('');
  const openCls = openByDefault ? ' open' : '';
  return `<div class="render-folder${openCls}" id="folder-${folderId}">
    <div class="render-folder-header" onclick="toggleFolder('${folderId}')">
      <span class="render-folder-arrow">▶</span>
      <span class="render-folder-title">${title}</span>
      <span class="render-folder-count">${subtitle} · ${renders.length}개</span>
    </div>
    <div class="render-folder-body">
      <div class="render-grid">${cards}</div>
    </div>
  </div>`;
}

function _svConfigPanel() {
  const partIds = DATA.parts ? Object.keys(DATA.parts).sort((a,b) => +a - +b) : [];
  const partOpts = partIds.map(pid => {
    const p = DATA.parts[pid];
    const nm = p && p.name ? ` (${p.name})` : '';
    return `<option value="${pid}">Part ${pid}${nm}</option>`;
  }).join('');

  return `
<div class="sv-config">
  <div class="sv-config-title">단면뷰 렌더 설정</div>
  <div class="sv-config-grid">
    <div class="sv-field">
      <label>뷰 모드</label>
      <select id="sv-mode">
        <option value="section" selected>section (2D 단면)</option>
        <option value="section_3d">section_3d (3D 반절단)</option>
      </select>
    </div>
    <div class="sv-field">
      <label>축</label>
      <div class="sv-checkboxes">
        <label><input type="checkbox" id="sv-ax-x" checked> X</label>
        <label><input type="checkbox" id="sv-ax-y" checked> Y</label>
        <label><input type="checkbox" id="sv-ax-z" checked> Z</label>
      </div>
    </div>
    <div class="sv-field">
      <label>스칼라 필드</label>
      <select id="sv-field" multiple size="3" style="min-height:70px">
        <option value="von_mises" selected>Von Mises 응력</option>
        <option value="strain" selected>변형률 (Total Strain)</option>
        <option value="eps">소성 변형률 (EPS)</option>
        <option value="displacement">변위</option>
        <option value="pressure">정수압</option>
        <option value="max_shear">최대 전단응력</option>
      </select>
    </div>
    <div class="sv-field">
      <label>타겟 파트</label>
      <select id="sv-target-parts" multiple size="4" style="min-height:80px">
        ${partOpts}
      </select>
      <span style="font-size:0.72rem;color:var(--fg2)">미선택 = 전체</span>
    </div>
    <div class="sv-field">
      <label>Fade 거리</label>
      <input type="number" id="sv-fade" value="0.0" step="0.1" min="0" style="width:100px">
      <span style="font-size:0.72rem;color:var(--fg2)">0 = 단색, >0 = 거리별 반투명</span>
    </div>
    <div class="sv-field">
      <label>파트별 단면</label>
      <div class="sv-checkboxes">
        <label><input type="checkbox" id="sv-per-part"> 활성화</label>
      </div>
    </div>
  </div>
  <div class="sv-actions">
    <button class="sv-btn-primary" onclick="svGenCli()">CLI 명령 생성</button>
    <button class="sv-btn-secondary" onclick="svGenYaml()">YAML 생성</button>
    <button class="sv-btn-secondary" onclick="svCopyOutput()">복사</button>
  </div>
  <pre class="sv-output" id="sv-output"></pre>
</div>`;
}

function svGenCli() {
  const mode = document.getElementById('sv-mode').value;
  const axes = ['x','y','z'].filter(a => document.getElementById('sv-ax-'+a).checked);
  const fields = [...document.getElementById('sv-field').selectedOptions].map(o => o.value);
  const targets = [...document.getElementById('sv-target-parts').selectedOptions].map(o => o.value);
  const fade = parseFloat(document.getElementById('sv-fade').value) || 0;
  const perPart = document.getElementById('sv-per-part').checked;

  let cmd = 'python3 -m koo_deep_report <d3plot_path> --section-view';
  cmd += ` --section-view-mode ${mode}`;
  if (axes.length < 3) cmd += ` --section-view-axes ${axes.join(' ')}`;
  if (fields.length) cmd += ` --section-view-fields ${fields.join(' ')}`;
  if (targets.length) cmd += ` --section-view-target-ids ${targets.join(' ')}`;
  if (fade > 0) cmd += ` --section-view-fade ${fade}`;
  if (perPart) cmd += ' --section-view-per-part';

  const out = document.getElementById('sv-output');
  out.textContent = cmd;
  out.style.display = 'block';
}

function svGenYaml() {
  const mode = document.getElementById('sv-mode').value;
  const axes = ['x','y','z'].filter(a => document.getElementById('sv-ax-'+a).checked);
  const fields = [...document.getElementById('sv-field').selectedOptions].map(o => o.value);
  const targets = [...document.getElementById('sv-target-parts').selectedOptions].map(o => o.value);
  const fade = parseFloat(document.getElementById('sv-fade').value) || 0;
  const perPart = document.getElementById('sv-per-part').checked;

  let yaml = 'section_views:\n';
  for (const fld of fields) {
    for (const ax of axes) {
      yaml += `  - name: "section_view_${fld}_${ax}"\n`;
      yaml += `    view_mode: ${mode}\n`;
      yaml += `    plane:\n      axis: ${ax}\n`;
      yaml += '    auto_center: true\n    auto_slab: true\n';
      if (targets.length) yaml += `    target_parts:\n      ids: [${targets.join(', ')}]\n`;
      yaml += `    field: ${fld}\n`;
      yaml += '    colormap: fringe\n    global_range: true\n';
      if (fade > 0) yaml += `    target_fade_distance: ${fade}\n`;
      yaml += '    supersampling: 2\n';
      yaml += '    output:\n      width: 1280\n      height: 720\n';
      yaml += '      png_frames: true\n      mp4: true\n      fps: 24\n';
      yaml += `      output_dir: "renders/section_view_${fld}_${ax}"\n\n`;
    }
  }
  if (perPart && targets.length) {
    for (const fld of fields) {
      for (const pid of targets) {
        for (const ax of axes) {
          yaml += `  - name: "section_view_${fld}_part_${pid}_${ax}"\n`;
          yaml += `    view_mode: ${mode}\n`;
          yaml += `    plane:\n      axis: ${ax}\n`;
          yaml += '    auto_center: true\n    auto_slab: true\n';
          yaml += `    target_parts:\n      ids: [${pid}]\n`;
          yaml += `    field: ${fld}\n`;
          yaml += '    colormap: fringe\n    global_range: true\n';
          yaml += '    supersampling: 2\n';
          yaml += '    output:\n      width: 1280\n      height: 720\n';
          yaml += '      png_frames: true\n      mp4: true\n      fps: 24\n';
          yaml += `      output_dir: "renders/section_view_${fld}_part_${pid}_${ax}"\n\n`;
        }
      }
    }
  }

  const out = document.getElementById('sv-output');
  out.textContent = yaml;
  out.style.display = 'block';
}

function svCopyOutput() {
  const out = document.getElementById('sv-output');
  if (out.textContent) {
    navigator.clipboard.writeText(out.textContent).then(() => {
      const btn = event.target;
      btn.textContent = '복사됨!';
      setTimeout(() => { btn.textContent = '복사'; }, 1500);
    });
  }
}

function renderGallery() {
  let galleryHtml = _svConfigPanel();

  if (!DATA.renders || !DATA.renders.length) {
    return galleryHtml + '<div class="warn-box">렌더 파일 없음</div>';
  }

  const overviewRenders = DATA.renders.filter(r => !r.includes('/'));
  const partRenders     = DATA.renders.filter(r => r.includes('/'));

  // Group by first path component
  const groups = {};
  for (const r of partRenders) {
    const folder = r.split('/')[0];
    if (!groups[folder]) groups[folder] = [];
    groups[folder].push(r);
  }

  // Name map from DATA.parts
  const nameMap = {};
  if (DATA.parts) filteredParts().forEach(([pid, p]) => {
    nameMap['part_' + pid] = p.name && p.name !== 'Part_' + pid ? p.name : null;
  });

  let html = '';

  if (overviewRenders.length) {
    html += _folderHtml('overview', '전체 모델 단면', 'Overview', overviewRenders, true);
  }

  // Collect section_view overview folders, grouped by field
  // Patterns: section_view_x (legacy), section_view_von_mises_x, section_view_strain_z, etc.
  const FIELD_LABELS = {
    'von_mises': '응력 (Von Mises)',
    'strain': '변형률 (Total Strain)',
    'eps': '소성 변형률 (EPS)',
    'displacement': '변위',
    'pressure': '정수압',
    'max_shear': '최대 전단응력',
  };

  const svOverviewByField = {};  // field -> [renders]
  const svOverviewFolders = [];
  for (const folder of Object.keys(groups)) {
    // Legacy: section_view_x (no field name → von_mises)
    const mLeg = folder.match(/^section_view_([xyz])$/i);
    if (mLeg) {
      const fld = 'von_mises';
      if (!svOverviewByField[fld]) svOverviewByField[fld] = [];
      svOverviewByField[fld].push(...groups[folder]);
      svOverviewFolders.push(folder);
      continue;
    }
    // New: section_view_{field}_{axis}
    const mNew = folder.match(/^section_view_([a-z_]+)_([xyz])$/i);
    if (mNew && !folder.match(/^section_view_part_/)) {
      const fld = mNew[1];
      if (!svOverviewByField[fld]) svOverviewByField[fld] = [];
      svOverviewByField[fld].push(...groups[folder]);
      svOverviewFolders.push(folder);
    }
  }
  const fieldOrder = ['von_mises', 'strain', 'eps', 'displacement', 'pressure', 'max_shear'];
  const sortedFields = Object.keys(svOverviewByField).sort((a, b) =>
    (fieldOrder.indexOf(a) === -1 ? 99 : fieldOrder.indexOf(a)) -
    (fieldOrder.indexOf(b) === -1 ? 99 : fieldOrder.indexOf(b))
  );
  for (const fld of sortedFields) {
    const label = FIELD_LABELS[fld] || fld;
    const isFirst = fld === sortedFields[0];
    html += _folderHtml(`sv_${fld}`, `단면뷰 — ${label}`, '소프트웨어 렌더', svOverviewByField[fld], isFirst);
  }

  // Collect section_view_part folders, grouped by field then part
  // Patterns: section_view_part_N_axis (legacy), section_view_{field}_part_N_axis (new)
  const svPartByFieldPart = {};  // "field|pid" -> [renders]
  for (const folder of Object.keys(groups)) {
    const mLeg = folder.match(/^section_view_part_(\d+)_([xyz])$/i);
    if (mLeg) {
      const key = `von_mises|${mLeg[1]}`;
      if (!svPartByFieldPart[key]) svPartByFieldPart[key] = [];
      svPartByFieldPart[key].push(...groups[folder]);
      svOverviewFolders.push(folder);
      continue;
    }
    const mNew = folder.match(/^section_view_([a-z_]+)_part_(\d+)_([xyz])$/i);
    if (mNew) {
      const key = `${mNew[1]}|${mNew[2]}`;
      if (!svPartByFieldPart[key]) svPartByFieldPart[key] = [];
      svPartByFieldPart[key].push(...groups[folder]);
      svOverviewFolders.push(folder);
    }
  }
  // Group by field, then by part
  const svPartFields = [...new Set(Object.keys(svPartByFieldPart).map(k => k.split('|')[0]))];
  svPartFields.sort((a, b) =>
    (fieldOrder.indexOf(a) === -1 ? 99 : fieldOrder.indexOf(a)) -
    (fieldOrder.indexOf(b) === -1 ? 99 : fieldOrder.indexOf(b))
  );
  for (const fld of svPartFields) {
    const label = FIELD_LABELS[fld] || fld;
    const partKeys = Object.keys(svPartByFieldPart)
      .filter(k => k.startsWith(fld + '|'))
      .map(k => parseInt(k.split('|')[1]))
      .sort((a, b) => a - b);
    for (const pid of partKeys) {
      const pname = nameMap['part_' + pid] ? ' — ' + nameMap['part_' + pid] : '';
      html += _folderHtml(`sv_${fld}_part_${pid}`, `Part ${pid}${pname}`, `${label} 단면뷰`, svPartByFieldPart[`${fld}|${pid}`], false);
    }
  }

  // Remaining folders (LSPrePost part renders, unknown)
  const handled = new Set([
    ...svOverviewFolders,
    ...Object.keys(groups).filter(f => /^section_view_part_/.test(f) || /^section_view_[a-z_]+_part_/.test(f)),
  ]);
  const folderKeys = Object.keys(groups).filter(f => !handled.has(f)).sort();
  for (const folder of folderKeys) {
    const partM = folder.match(/^part_(\d+)$/);
    let title, subtitle;
    if (partM) {
      const pid = partM[1];
      const pname = nameMap['part_' + pid] ? ' — ' + nameMap['part_' + pid] : '';
      title = `Part ${pid}${pname}`;
      subtitle = 'X · Y · Z 단면';
    } else {
      title = folder;
      subtitle = '단면';
    }
    html += _folderHtml(folder, title, subtitle, groups[folder], false);
  }

  return galleryHtml + html;
}

function toggleFolder(id) {
  document.getElementById('folder-' + id).classList.toggle('open');
}

function initGallery() {
  const modal = document.getElementById('render-modal');
  if (modal) modal.addEventListener('click', e => { if (e.target === modal) closeModal(); });
}

// Fullscreen modal
function openModal(src, label) {
  const modal = document.getElementById('render-modal');
  const ext = src.split('.').pop().toLowerCase();
  const isVid = ext === 'mp4' || ext === 'webm';
  modal.querySelector('#modal-content').innerHTML = isVid
    ? `<video controls autoplay loop muted><source src="${src}" type="video/${ext}"></video>`
    : `<img src="${src}" alt="${label}">`;
  modal.querySelector('.modal-label').textContent = label;
  modal.classList.add('open');
}
function closeModal() {
  const modal = document.getElementById('render-modal');
  modal.classList.remove('open');
  modal.querySelector('#modal-content').innerHTML = '';
}

// ── Element Quality ────────────────────────────────────────────────────
function renderQuality() {
  const eq = DATA.element_quality || [];
  if (!eq.length) return '<div class="card"><p>요소 품질 데이터가 없습니다. <code>--element-quality</code> 옵션으로 실행하세요.</p></div>';

  let html = '<div class="card"><h2>요소 품질 요약</h2>';
  html += '<table class="data-table"><thead><tr>';
  html += '<th>Part ID</th><th>이름</th><th>타입</th><th>요소 수</th>';
  html += '<th>Peak AR</th><th>Min Jac</th><th>Peak Warp(°)</th><th>Peak Skew</th>';
  html += '<th>Vol Min</th><th>Vol Max</th><th>음수 Jac</th>';
  html += '</tr></thead><tbody>';

  for (const q of eq) {
    // 미산출은 0/1.0 대신 "—" 로 둔다. 값이 없다는 사실 자체가 정보다.
    const arM = q.aspect_measured !== false;
    const jacM = q.jacobian_measured !== false;
    const volM = q.volume_measured !== false;
    const arCls = !arM ? 'na' : (q.peak_aspect_ratio > 10 ? 'crit' : (q.peak_aspect_ratio > 5 ? 'warn' : ''));
    const jacCls = !jacM ? 'na' : (q.min_jacobian < 0 ? 'crit' : (q.min_jacobian < 0.3 ? 'warn' : ''));
    const negCls = q.max_negative_jacobian_count > 0 ? 'crit' : '';
    const naTip = '축퇴 요소(tet/wedge 를 hex8 로 저장)라 hex 기준 지표가 정의되지 않음';

    html += `<tr>
      <td>${q.part_id}</td><td>${q.part_name}</td><td>${q.element_type}</td><td>${q.num_elements}</td>
      <td class="${arCls}"${arM ? '' : ` title="${naTip}"`}>${arM ? q.peak_aspect_ratio.toFixed(2) : '—'}</td>
      <td class="${jacCls}"${jacM ? '' : ` title="${naTip}"`}>${jacM ? q.min_jacobian.toFixed(3) : '—'}</td>
      <td class="${q.warpage_measured === false ? 'na' : ''}">${q.warpage_measured === false ? '—' : q.peak_warpage.toFixed(1)}</td>
      <td class="${q.skewness_measured === false ? 'na' : ''}">${q.skewness_measured === false ? '—' : q.peak_skewness.toFixed(3)}</td>
      <td>${volM ? q.min_volume_change.toFixed(3) : '—'}</td>
      <td>${volM ? q.max_volume_change.toFixed(3) : '—'}</td>
      <td class="${negCls}">${q.max_negative_jacobian_count}</td>
    </tr>`;
  }
  html += '</tbody></table></div>';

  // Charts per part (time history)
  for (let i = 0; i < eq.length; i++) {
    const q = eq[i];
    if (!q.data || q.data.length < 2) continue;
    html += `<div class="card"><h3>Part ${q.part_id}: ${q.part_name} (${q.element_type})</h3>`;
    html += `<div class="chart-row"><div id="eq-ar-${i}" class="chart-box"></div><div id="eq-vol-${i}" class="chart-box"></div></div>`;
    if (q.element_type === 'shell') {
      html += `<div class="chart-row"><div id="eq-warp-${i}" class="chart-box"></div><div id="eq-skew-${i}" class="chart-box"></div></div>`;
    }
    html += '</div>';
  }
  return html;
}

function initQualityCharts() {
  const eq = DATA.element_quality || [];
  const layout = {margin:{t:30,b:40,l:50,r:20}, height:250, paper_bgcolor:'#1a1b26', plot_bgcolor:'#1a1b26',
    font:{color:'#d5daf0',size:10}, xaxis:{title:'Time',color:'#7982a9',gridcolor:'#24283b'},
    yaxis:{color:'#7982a9',gridcolor:'#24283b'}};

  for (let i = 0; i < eq.length; i++) {
    const q = eq[i];
    if (!q.data || q.data.length < 2) continue;
    const t = q.data.map(d=>d.time);

    // Aspect ratio chart
    Plotly.newPlot('eq-ar-'+i, [
      {x:t, y:q.data.map(d=>d.ar_max), name:'Max', line:{color:'#f7768e'}},
      {x:t, y:q.data.map(d=>d.ar_avg), name:'Avg', line:{color:'#7aa2f7'}},
    ], {...layout, yaxis:{...layout.yaxis, title:'Aspect Ratio'}, title:{text:'Aspect Ratio',font:{size:12}}});

    // Volume change chart
    Plotly.newPlot('eq-vol-'+i, [
      {x:t, y:q.data.map(d=>d.vol_min), name:'Min (compressed)', line:{color:'#f7768e'}},
      {x:t, y:q.data.map(d=>d.vol_max), name:'Max (expanded)', line:{color:'#9ece6a'}},
    ], {...layout, yaxis:{...layout.yaxis, title:'Volume/Area Ratio'}, title:{text:'Volume/Area Change',font:{size:12}},
      shapes:[{type:'line',x0:t[0],x1:t[t.length-1],y0:1,y1:1,line:{color:'#7982a9',dash:'dot',width:1}}]});

    if (q.element_type === 'shell') {
      // Warpage chart
      const wEl = document.getElementById('eq-warp-'+i);
      if (wEl) {
        Plotly.newPlot('eq-warp-'+i, [
          {x:t, y:q.data.map(d=>d.warp_max), name:'Max', line:{color:'#e0af68'}},
        ], {...layout, yaxis:{...layout.yaxis, title:'Warpage (°)'}, title:{text:'Warpage Angle',font:{size:12}}});
      }
      // Skewness chart
      const sEl = document.getElementById('eq-skew-'+i);
      if (sEl) {
        Plotly.newPlot('eq-skew-'+i, [
          {x:t, y:q.data.map(d=>d.skew_max), name:'Max', line:{color:'#bb9af7'}},
        ], {...layout, yaxis:{...layout.yaxis, title:'Skewness'}, title:{text:'Skewness',font:{size:12}}});
      }
    }
  }
}

// ── System Info ────────────────────────────────────────────────────────
// 시스템·파일 정보. '빌드' 줄은 어느 판으로 돌린 결과인지 알려준다 —
// kood3plot_version 은 계속 1.0.0 이라 구분이 안 된다. 옛 산출물에는 tool_commit
// 키가 없으므로 그때는 줄 자체를 내지 않는다 (없는 값을 지어내지 않는다).
function renderSysInfo() {
  const s = DATA.sim;
  const files = [
    {name: 'd3plot',  path: s.d3plot,       present: !!s.d3plot},
    {name: 'glstat',  path: s.files.glstat, present: !!s.files.glstat},
    {name: 'binout',  path: s.files.binout, present: !!s.files.binout},
    {name: 'rcforc',  path: s.files.rcforc, present: !!s.files.rcforc},
    {name: 'matsum',  path: s.files.matsum, present: !!s.files.matsum},
  ];
  const fileList = files.map(f => `
    <div class="file-item">
      <span class="file-status ${f.present?'present':'absent'}">${f.present?'✓':'○'}</span>
      <span style="width:70px;font-size:.82rem">${f.name}</span>
      <span class="file-path">${f.path||'—'}</span>
    </div>`).join('');

  const meta = DATA.metadata;
  return `
<div class="sec-title">시뮬레이션 정보</div>
<div class="chart-box">
  <div class="file-list">
    <div class="file-item"><span style="width:140px;color:var(--fg2)">경로</span><span class="file-path">${s.path}</span></div>
    <div class="file-item"><span style="width:140px;color:var(--fg2)">분석 Tier</span><span>${s.tier_label}</span></div>
    <div class="file-item"><span style="width:140px;color:var(--fg2)">종료 상태</span><span>${s.normal_termination===true?'정상':s.normal_termination===false?'오류':'불명'} (${s.termination_source})</span></div>
    <div class="file-item"><span style="width:140px;color:var(--fg2)">States 수</span><span>${meta.num_states||'—'}</span></div>
    <div class="file-item"><span style="width:140px;color:var(--fg2)">시간 범위</span><span>${fmt(meta.start_time,4)} ~ ${fmt(meta.end_time,4)}</span></div>
    <div class="file-item"><span style="width:140px;color:var(--fg2)">분석 부품 수</span><span>${(meta.analyzed_parts||[]).length}</span></div>
    <div class="file-item"><span style="width:140px;color:var(--fg2)">unified_analyzer</span><span>${meta.kood3plot_version||'—'}</span></div>
    ${meta.tool_commit ? `<div class="file-item"><span style="width:140px;color:var(--fg2)">빌드</span><span>${meta.tool_commit}${meta.tool_built?` · ${meta.tool_built}`:''}</span></div>` : ''}
  </div>
</div>
<div class="sec-title">파일 목록</div>
<div class="chart-box"><div class="file-list">${fileList}</div></div>`;
}

// ── Plotly auto-resize when charts scroll into view ──
(function() {
  if (!window.IntersectionObserver) return;
  const resized = new WeakSet();
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting && !resized.has(entry.target)) {
        resized.add(entry.target);
        try { Plotly.Plots.resize(entry.target); } catch(e) {}
      }
    });
  }, { threshold: 0.1 });
  const _origSwitchTab = switchTab;
  switchTab = function(tid) {
    _origSwitchTab(tid);
    requestAnimationFrame(() => {
      document.querySelectorAll('.plotly-chart, [class*="js-plotly-plot"], [id$="-chart"]').forEach(el => {
        observer.observe(el);
      });
    });
  };
})();

// ── Hotspot clusters (analysis_result.json hotspot_clusters) ─────────
// 항목 = 파트 × 기준량 × 요소종류. 필드 뜻: docs/hotspot-cluster-usage.md
const HS_CRIT_LABEL = {
  von_mises: 'Von Mises',
  max_principal: 'σ₁ 최대주응력 (인장 집중)',
  min_principal: 'σ₃ 최소주응력 (압축 집중)',
};
const HS_TYPE_LABEL = {solid: '솔리드', thick_shell: '두꺼운 셸', shell: '셸'};
const HS_STRAIN_LABEL = {equivalent: '등가변형률', max_principal: 'ε₁', min_principal: 'ε₃'};
const HS_WEIGHT_LABEL = {volume: '부피', area_x_thickness: '면적×두께', area: '면적'};
let _hsState = {crit: null, type: 'all', key: null, metric: 'stress'};

function hsEntries() { return DATA.hotspot || []; }
function hsKey(p) { return p.criterion + '|' + (p.element_type || 'solid') + '|' + p.part_id; }
function hsPartName(p) {
  const pi = DATA.parts[String(p.part_id)];
  return (pi && pi.name) || p.part_name || '';
}
function hsMatchesFilter(p) { return partMatchesFilter(String(p.part_id), {name: hsPartName(p)}); }
function hsLayerLabel(p, L) {
  if (L === undefined || L === null || L < 0) return '—';
  if (p.layer_scheme === 'mid_inner_outer') return ['중립면', '안쪽 면', '바깥쪽 면'][L] || ('IP ' + (L + 1));
  return 'IP ' + (L + 1);
}
// 파트 경계상자 기준 백분율. 두께가 0 인 축은 null.
function hsRelPos(p, c) {
  if (!p.bbox_min || !p.bbox_max) return null;
  return [0, 1, 2].map(i => {
    const e = p.bbox_max[i] - p.bbox_min[i];
    return e > 1e-12 ? (c.center[i] - p.bbox_min[i]) / e * 100 : null;
  });
}
// 파트의 '평면' — 경계상자에서 가장 넓은 두 축 (x<y<z 순서 유지). 판재면 그 판의 면.
function hsPlaneAxes(p) {
  if (!p || !p.bbox_min || !p.bbox_max) return [0, 1];
  const e = [0, 1, 2].map(i => p.bbox_max[i] - p.bbox_min[i]);
  const drop = e.indexOf(Math.min(...e));
  return [0, 1, 2].filter(i => i !== drop);
}
// 파트 평면 기준 9구역 이름 — 첫 축 좌→우, 둘째 축 하→상.
// 🔴 얇은 방향의 % 로 이름을 붙이면 두께 0.4 mm 판의 '상단' 같은 오독이 난다 → 평면 두 축만 쓴다.
function hsZoneLabel(p, rel) {
  if (!rel) return '—';
  const [a, b] = hsPlaneAxes(p);
  if (rel[a] === null || rel[b] === null) return '—';
  const bx = rel[a] < 33.3 ? 0 : rel[a] > 66.7 ? 2 : 1;
  const by = rel[b] < 33.3 ? 0 : rel[b] > 66.7 ? 2 : 1;
  const T = [['좌하단', '중앙 하단', '우하단'], ['좌측 중앙', '정중앙', '우측 중앙'], ['좌상단', '중앙 상단', '우상단']];
  const ax = 'xyz';
  return T[by][bx] + (a === 0 && b === 1 ? '' : ` (${ax[a]}·${ax[b]} 평면)`);
}
function hsXYLabel(rel) { return hsZoneLabel(null, rel); }
function hsRelText(rel) {
  if (!rel) return '—';
  return ['x', 'y', 'z'].map((a, i) => rel[i] === null ? a + ' —' : a + ' ' + rel[i].toFixed(0) + '%').join(' · ');
}

function renderHotspot() {
  const all = hsEntries();
  if (!all.length) return '<div class="chart-box"><p>핫스팟 군집 결과가 없습니다. <code>--hotspot-clusters</code> 로 실행하세요.</p></div>';
  const crits = [...new Set(all.map(p => p.criterion))];
  const types = [...new Set(all.map(p => p.element_type || 'solid'))];
  if (!_hsState.crit || !crits.includes(_hsState.crit)) _hsState.crit = crits[0];
  if (_hsState.type !== 'all' && !types.includes(_hsState.type)) _hsState.type = 'all';
  const critOpts = crits.map(c =>
    `<option value="${c}" ${c === _hsState.crit ? 'selected' : ''}>${HS_CRIT_LABEL[c] || c}</option>`).join('');
  const typeOpts = ['all', ...types].map(t =>
    `<option value="${t}" ${t === _hsState.type ? 'selected' : ''}>${t === 'all' ? '전체' : (HS_TYPE_LABEL[t] || t)}</option>`).join('');
  return `
<div class="sec-title">핫스팟 군집 — 파트 내 상위 ${fmt(all[0].top_percent, 1)}% 요소를 공간 군집화</div>
<p class="hs-note">최대 요소 하나로는 알 수 없는 것 — 응력이 <b>한 곳에 뭉쳤나 흩어졌나</b>, 파트의 <b>어디에</b>,
<b>얼마나 넓게</b>, 그 범위의 <b>평균 수준</b>은 얼마인가 — 를 덩어리 단위로 보여준다.
중심·경계상자는 <b>초기 형상</b> 기준. 파트 내 위치 이름은 파트의 평면(경계상자에서 가장 넓은 두 축) 기준 — 첫 축 왼쪽→오른쪽, 둘째 축 아래→위. XY 평면이면 +x 오른쪽, +y 위.</p>
<div class="part-selector">
  <label>기준량:</label><select id="hs-crit" onchange="hsSet('crit', this.value)">${critOpts}</select>
  <label>요소:</label><select id="hs-type" onchange="hsSet('type', this.value)">${typeOpts}</select>
</div>
<div class="chart-box"><div class="chart-title">파트별 1위 덩어리 — 행을 누르면 아래에 상세</div><div id="hs-summary"></div></div>
<div id="hs-detail"></div>`;
}

function initHotspot() { hsUpdate(); }
function hsSet(k, v) {
  _hsState[k] = v;
  if (k !== 'key') _hsState.key = null;
  hsUpdate();
}
function hsSelected() {
  return hsEntries().filter(p => p.criterion === _hsState.crit &&
    (_hsState.type === 'all' || (p.element_type || 'solid') === _hsState.type) && hsMatchesFilter(p));
}

function hsUpdate() {
  const rows = hsSelected();
  const isMin = rows.length > 0 && rows[0].direction === 'min';
  // 평탄 분포(uniform)는 덩어리가 우연히 생겨도 위치에 의미가 없다 → 순위표에서 뺀다
  const isFlat = p => p.uniform === true;
  const withC = rows.filter(p => p.clusters && p.clusters.length && !isFlat(p));
  withC.sort((a, b) => isMin ? a.clusters[0].stress_max - b.clusters[0].stress_max
                             : b.clusters[0].stress_max - a.clusters[0].stress_max);
  // 덩어리가 없는 파트를 둘로 나눈다 — 상위 값이 컷값과 같으면 평탄 분포(핫스팟 자체가 없음),
  // 아니면 뜨거운 요소가 실제로 흩어져 있다.
  const flat = rows.filter(isFlat);
  const scattered = rows.filter(p => !isFlat(p) && !(p.clusters && p.clusters.length) && p.element_count_selected > 0);
  if ((!_hsState.key || !withC.some(p => hsKey(p) === _hsState.key)) && withC.length) _hsState.key = hsKey(withC[0]);
  if (!withC.length) _hsState.key = null;

  const extLabel = isMin ? '1위 최솟값' : '1위 최댓값';
  let html = `<table class="data-table hs-table"><thead><tr>
    <th>파트</th><th>요소</th><th class="num">덩어리</th><th class="num">${extLabel}</th><th class="num">1위 평균</th>
    <th>1위 위치 (파트 내)</th><th class="num">선별 / 전체</th><th>가중</th></tr></thead><tbody>`;
  for (const p of withC) {
    const c = p.clusters[0];
    const rel = hsRelPos(p, c);
    const sel = hsKey(p) === _hsState.key ? ' hs-sel' : '';
    html += `<tr class="hs-row${sel}" onclick="hsSet('key','${hsKey(p)}')">
      <td>${partLabel(p.part_id, {name: hsPartName(p)})}</td>
      <td>${HS_TYPE_LABEL[p.element_type] || p.element_type || '솔리드'}</td>
      <td class="num">${p.clusters.length}</td>
      <td class="num">${fmt(c.stress_max)}</td>
      <td class="num">${fmt(c.stress_mean)}</td>
      <td>${hsZoneLabel(p, rel)} <span class="hs-dim">(${hsRelText(rel)})</span></td>
      <td class="num">${p.element_count_selected} / ${p.element_count_total}</td>
      <td>${HS_WEIGHT_LABEL[p.weight_measure] || p.weight_measure || '부피'}</td></tr>`;
  }
  html += '</tbody></table>';
  if (!withC.length) html = '<p class="hs-dim">이 조건에 덩어리가 있는 파트가 없습니다.</p>';
  if (flat.length) {
    html += `<p class="hs-dim" style="margin-top:8px">상위 값이 파트 전체에 <b>균일</b>해 핫스팟이 없는 파트 — 상위 선별이 같은 값들 중 임의로 뽑혀 흩어져 보일 뿐이다: ` +
      flat.map(p => `${partLabel(p.part_id, {name: hsPartName(p)})} (값 ${fmt(p.value_extreme, 4)})`).join(', ') + '</p>';
  }
  if (scattered.length) {
    html += `<p class="hs-dim" style="margin-top:8px">선별은 됐지만 최소 크기 이상 뭉친 덩어리가 없는 파트 — 핫스팟이 흩어져 있다: ` +
      scattered.map(p => `${partLabel(p.part_id, {name: hsPartName(p)})} (선별 ${p.element_count_selected})`).join(', ') + '</p>';
  }
  document.getElementById('hs-summary').innerHTML = html;
  hsRenderDetail(rows.find(p => hsKey(p) === _hsState.key));
}

function hsRenderDetail(p) {
  const el = document.getElementById('hs-detail');
  if (!p) { el.innerHTML = ''; return; }
  const isMin = p.direction === 'min';
  const isShell = (p.element_type || 'solid') === 'shell';
  const layered = (p.element_type || 'solid') !== 'solid';
  const strainOn = p.strain_available && p.clusters.some(c => c.strain_available);
  const sLab = HS_STRAIN_LABEL[p.strain_measure] || '변형률';
  let rows = '';
  for (const c of p.clusters) {
    const rel = hsRelPos(p, c);
    rows += `<tr>
      <td class="num">${c.rank}</td><td class="num">${c.element_count}</td>
      <td class="num">${c.center.map(v => fmt(v, 2)).join(', ')}</td>
      <td>${hsZoneLabel(p, rel)}<br><span class="hs-dim">${hsRelText(rel)}</span></td>
      <td class="num">${fmt(c.radius_enclosing, 3)}</td><td class="num">${fmt(c.radius_rms, 3)}</td>
      <td class="num">${isShell ? fmt(c.area, 3) : fmt(c.volume, 3)}</td>
      <td class="num">${fmt(c.stress_mean)}</td><td class="num">${fmt(c.stress_max)}</td>
      ${strainOn ? `<td class="num">${c.strain_available ? fmt(c.strain_mean, 5) : '—'}</td><td class="num">${c.strain_available ? fmt(c.strain_max, 5) : '—'}</td>` : ''}
      <td class="num">${c.peak_element_id}</td><td class="num">${fmt(c.peak_time, 5)}</td>
      ${layered ? `<td>${hsLayerLabel(p, c.peak_layer)}</td>` : ''}</tr>`;
  }
  el.innerHTML = `
<div class="chart-box">
  <div class="chart-title">${partLabel(p.part_id, {name: hsPartName(p)})} — ${HS_TYPE_LABEL[p.element_type] || '솔리드'} ·
    ${HS_CRIT_LABEL[p.criterion] || p.criterion}</div>
  <div class="hs-meta">
    <span>선별 ${p.element_count_selected} / 전체 ${p.element_count_total} · 덩어리 소속 ${p.element_count_clustered}</span>
    <span>컷값 ${fmt(p.threshold_value)} (${isMin ? '이하' : '이상'} 선별)${p.cut_ties_unselected > 0 ? ` · 컷값 동률 미선별 ${p.cut_ties_unselected}개` : ''}</span>
    <span>대표 요소 크기 ${fmt(p.element_size_ref, 3)} · 거리 임계 ${fmt(p.distance_threshold, 3)}</span>
    <span>가중 ${HS_WEIGHT_LABEL[p.weight_measure] || p.weight_measure || '부피'}</span>
  </div>
  <div style="overflow-x:auto"><table class="data-table"><thead><tr>
    <th class="num">순위</th><th class="num">요소</th><th class="num">중심 (x, y, z)</th><th>파트 내 위치</th>
    <th class="num">포함 반경</th><th class="num">RMS 반경</th><th class="num">${isShell ? '면적' : '부피'}</th>
    <th class="num">평균</th><th class="num">${isMin ? '최솟값' : '최댓값'}</th>
    ${strainOn ? `<th class="num">${sLab} 평균</th><th class="num">${sLab} ${isMin ? '최솟값' : '최댓값'}</th>` : ''}
    <th class="num">피크 요소</th><th class="num">피크 시각</th>${layered ? '<th>피크 층</th>' : ''}
  </tr></thead><tbody>${rows}</tbody></table></div>
  <p class="hs-dim" style="margin:8px 0 0">평균은 ${HS_WEIGHT_LABEL[p.weight_measure] || '부피'} 가중(산술평균 아님).
    포함 반경 = 중심에서 구성 요소의 가장 먼 절점까지, RMS 반경이 포함 반경보다 훨씬 작으면 한 점에 몰린 것.
    ${isMin ? '압축 기준이라 값이 작을수록(더 음수일수록) 위험하다.' : ''}</p>
</div>
<div class="chart-box"><div class="chart-title">파트 경계상자 안의 덩어리 — 원(구) 반지름 = 포함 반경, 색 = ${isMin ? '최솟값' : '최댓값'}
  <span class="part-selector" style="display:inline-flex;margin:0 0 0 12px">
    <label>보기:</label>
    <select id="hs-view" onchange="hsDraw(_hsCurrent)">
      <option value="plane">파트 평면 (${'xyz'[hsPlaneAxes(p)[0]]}·${'xyz'[hsPlaneAxes(p)[1]]})</option>
      <option value="xy">XY</option><option value="xz">XZ</option><option value="yz">YZ</option><option value="3d">3D</option>
    </select>
    <label style="margin-left:12px">색:</label>
    <select id="hs-metric" onchange="_hsState.metric=this.value;hsDraw(_hsCurrent)">
      ${HS_METRICS.filter(m => hsMetricAvailable(p, m[0]))
        .map(m => `<option value="${m[0]}"${_hsState.metric === m[0] ? ' selected' : ''}>${m[1]}</option>`).join('')}
    </select></span></div>
  <div id="hs-view-chart" style="height:560px"></div></div>`;
  _hsCurrent = p;
  hsDraw(p);
}
let _hsCurrent = null;

// 뜨거운 쪽이 진하게: max 방향은 옅은 노랑→진한 빨강, min(압축) 방향은 진한 파랑→옅은 파랑
// 색(리스크) 척도 — [코드, 라벨, 군집 필드, 가용성 플래그]
// 응력 피크만 보면 '짧게 튄 응력' 과 '실제 손상' 이 구분되지 않는다.
// 소성일 w_p=∫σ_vm dε_p 는 탄성 스파이크가 Δε_p=0 이라 기여하지 않는다.
const HS_METRICS = [
  ['stress', '응력 피크 [MPa]',            'stress_max',   null],
  ['strain', '변형률 피크 [-]',             'strain_max',   'strain_available'],
  ['energy', '소성일 ∫σ dε_p [mJ]',         'energy_total', 'energy_available'],
  ['energy_density', '소성일 밀도 [mJ/mm³]', 'energy_max',   'energy_available'],
];
function hsMetricDef(code) { return HS_METRICS.find(m => m[0] === code) || HS_METRICS[0]; }
// 그 척도가 이 파트의 군집에 실제로 있는가. 없으면 선택지에서 감춘다 —
// 남겨 두면 고르는 순간 전부 같은 색이 되어 '값이 균일' 로 오독된다.
function hsMetricAvailable(p, code) {
  const d = hsMetricDef(code);
  return (p.clusters || []).some(c =>
    (d[3] === null || c[d[3]] === true) && typeof c[d[2]] === 'number');
}
function hsMetricValue(c, code) { const v = c[hsMetricDef(code)[2]]; return typeof v === 'number' ? v : 0; }
// 에너지는 늘 '클수록 위험' 이다 — 압축 기준(σ3)이어도 방향이 뒤집히지 않는다.
function hsMetricIsMin(p, code) { return code === 'stress' || code === 'strain' ? p.direction === 'min' : false; }
// 척도 통계. uniform 이면 색으로 구분할 게 없다 — 이때 최대색(빨강)을 칠하면
// '전부 0(탄성)' 인 파트가 가장 위험해 보인다. 중립색 + 주석으로 사실대로 말한다.
function hsMetricStats(p, code) {
  const vals = p.clusters.map(c => hsMetricValue(c, code));
  const vmin = Math.min(...vals), vmax = Math.max(...vals);
  return {vals, vmin, vmax, uniform: !(vmax > vmin)};
}
const HS_FLAT_COLOR = 'rgb(128,140,160)';
// 소성일은 1e-5 mJ 수준까지 내려간다. 공용 fmt(소수 2자리)로 찍으면 전부 '0.00'
// 이 되어 '값이 없다' 와 구분되지 않는다.
function hsMetricFmt(v) {
  if (typeof v !== 'number' || !isFinite(v)) return '—';
  if (v === 0) return '0';
  return Math.abs(v) >= 0.01 ? fmt(v, 3) : v.toExponential(3);
}
function hsFlatAnnotation(p, code, st) {
  const lab = hsMetricDef(code)[1];
  const zero = !(st.vmin > 0 || st.vmin < 0);
  const why = zero && (code === 'energy' || code === 'energy_density')
    ? ' — 이 파트는 소성 변형이 없습니다 (탄성 거동)' : '';
  return {xref: 'paper', yref: 'paper', x: 0, y: 1.03, xanchor: 'left', yanchor: 'bottom',
          showarrow: false, font: {color: '#c8c8d8', size: 11},
          text: `${lab} 이 덩어리마다 같습니다 (${hsMetricFmt(st.vmin)})${why}. 색 구분 없음.`};
}
// 색 척도가 응력이 아니면 그 값도 툴팁에 적는다 — 컬러바는 소성일인데
// 툴팁은 응력만 보여 주면 색과 숫자가 어긋난 채로 읽힌다.
function hsMetricHover(c, code) {
  if (code === 'stress') return '';
  return `<br>${hsMetricDef(code)[1]} ${hsMetricFmt(hsMetricValue(c, code))}`;
}

const HS_SCALE_MAX = [[0, '#fff3c4'], [0.5, '#fc8d3c'], [1, '#b10026']];
const HS_SCALE_MIN = [[0, '#08306b'], [0.5, '#4292c6'], [1, '#deebf7']];
function hsColorAt(scale, t) {
  t = Math.max(0, Math.min(1, t));
  let i = 0; while (i < scale.length - 2 && t > scale[i + 1][0]) i++;
  const [t0, c0] = scale[i], [t1, c1] = scale[i + 1];
  const f = (t - t0) / ((t1 - t0) || 1);
  const h = c => [1, 3, 5].map(k => parseInt(c.substr(k, 2), 16));
  const a = h(c0), b = h(c1);
  return 'rgb(' + a.map((v, k) => Math.round(v + (b[k] - v) * f)).join(',') + ')';
}

function hsDraw(p) {
  if (!p) return;
  const sel = document.getElementById('hs-view');
  const mode = sel ? sel.value : 'plane';
  if (mode === '3d') { hsDraw3D(p); return; }
  const ax = mode === 'xy' ? [0, 1] : mode === 'xz' ? [0, 2] : mode === 'yz' ? [1, 2] : hsPlaneAxes(p);
  hsDraw2D(p, ax[0], ax[1]);
}

// 평면 투영 — 구의 투영은 같은 반지름의 원이다. 등축 비율로 실제 크기 관계를 지킨다.
function hsDraw2D(p, a, b) {
  const el = document.getElementById('hs-view-chart');
  if (!el || !window.Plotly) return;
  // 선택한 척도가 이 파트에 없으면 응력으로 되돌린다 (빈/균일 색 방지)
  let mcode = _hsState.metric;
  if (!hsMetricAvailable(p, mcode)) mcode = 'stress';
  const mdef = hsMetricDef(mcode);
  const isMin = hsMetricIsMin(p, mcode);
  const scale = isMin ? HS_SCALE_MIN : HS_SCALE_MAX;
  const st = hsMetricStats(p, mcode);
  const vals = st.vals, vmin = st.vmin, vmax = st.vmax;
  const tOf = v => st.uniform ? 0.5 : (isMin ? (vmax - v) / (vmax - vmin) : (v - vmin) / (vmax - vmin));
  const shapes = [];
  if (p.bbox_min && p.bbox_max) {
    shapes.push({type: 'rect', xref: 'x', yref: 'y', x0: p.bbox_min[a], x1: p.bbox_max[a], y0: p.bbox_min[b], y1: p.bbox_max[b],
                 line: {color: '#a0a0b0', width: 1.5, dash: 'dot'}, fillcolor: 'rgba(160,160,176,0.06)', layer: 'below'});
  }
  // 순위가 낮은(덜 뜨거운) 것부터 그려 1위가 위에 오게
  [...p.clusters].reverse().forEach(c => {
    const r = Math.max(c.radius_enclosing, 1e-9);
    const cv = hsMetricValue(c, mcode);
    const col = st.uniform ? HS_FLAT_COLOR : hsColorAt(scale, isMin ? 1 - tOf(cv) : tOf(cv));
    shapes.push({type: 'circle', xref: 'x', yref: 'y', x0: c.center[a] - r, x1: c.center[a] + r, y0: c.center[b] - r, y1: c.center[b] + r,
                 line: {color: col, width: 2}, fillcolor: col, opacity: 0.6});
  });
  const axn = 'xyz';
  const traces = [{
    type: 'scatter', mode: 'markers+text', x: p.clusters.map(c => c.center[a]), y: p.clusters.map(c => c.center[b]),
    text: p.clusters.map(c => '#' + c.rank), textposition: 'middle center', textfont: {color: '#ffffff', size: 12},
    marker: {size: 2, color: vals, colorscale: scale, cmin: vmin, cmax: vmax === vmin ? vmin + 1 : vmax, showscale: !st.uniform,
             colorbar: {title: {text: mdef[1], side: 'right'}, len: 0.8}},
    hovertext: p.clusters.map(c => `#${c.rank} · 요소 ${c.element_count}<br>${isMin ? '최솟값' : '최댓값'} ${fmt(c.stress_max)} · 평균 ${fmt(c.stress_mean)}` +
                                  hsMetricHover(c, mcode) +
                                  `<br>중심 (${c.center.map(v => fmt(v, 2)).join(', ')})<br>포함 반경 ${fmt(c.radius_enclosing, 3)}`),
    hoverinfo: 'text', showlegend: false,
  }];
  Plotly.newPlot(el, traces, {
    ...PLOT_LAYOUT, margin: {l: 60, r: 20, t: st.uniform ? 28 : 10, b: 50}, shapes,
    annotations: st.uniform ? [hsFlatAnnotation(p, mcode, st)] : [],
    xaxis: {...PLOT_LAYOUT.xaxis, title: axn[a], zeroline: false},
    yaxis: {...PLOT_LAYOUT.yaxis, title: axn[b], zeroline: false, scaleanchor: 'x', scaleratio: 1},
  }, PLOT_CONFIG);
}

// 단위 구 표본점 (위도·경도 격자) — mesh3d alphahull=0 이 볼록 껍질로 면을 만든다
function hsSpherePts(cx, cy, cz, r) {
  const x = [], y = [], z = [];
  const NU = 10, NV = 16;
  for (let i = 0; i <= NU; i++) {
    const th = Math.PI * i / NU;
    for (let j = 0; j < NV; j++) {
      const ph = 2 * Math.PI * j / NV;
      x.push(cx + r * Math.sin(th) * Math.cos(ph));
      y.push(cy + r * Math.sin(th) * Math.sin(ph));
      z.push(cz + r * Math.cos(th));
    }
  }
  return {x, y, z};
}

function hsDraw3D(p) {
  const el = document.getElementById('hs-view-chart');
  if (!el || !window.Plotly) return;
  const traces = [];
  if (p.bbox_min && p.bbox_max) {
    const a = p.bbox_min, b = p.bbox_max;
    const C = [[a[0],a[1],a[2]],[b[0],a[1],a[2]],[b[0],b[1],a[2]],[a[0],b[1],a[2]],
               [a[0],a[1],b[2]],[b[0],a[1],b[2]],[b[0],b[1],b[2]],[a[0],b[1],b[2]]];
    const E = [[0,1],[1,2],[2,3],[3,0],[4,5],[5,6],[6,7],[7,4],[0,4],[1,5],[2,6],[3,7]];
    const lx = [], ly = [], lz = [];
    for (const [i, j] of E) { lx.push(C[i][0], C[j][0], null); ly.push(C[i][1], C[j][1], null); lz.push(C[i][2], C[j][2], null); }
    traces.push({type: 'scatter3d', mode: 'lines', x: lx, y: ly, z: lz, name: '파트 경계상자',
                 line: {color: '#a0a0b0', width: 2}, hoverinfo: 'skip'});
  }
  let mcode = _hsState.metric;
  if (!hsMetricAvailable(p, mcode)) mcode = 'stress';
  const mdef = hsMetricDef(mcode);
  const st = hsMetricStats(p, mcode);
  const vmin = st.vmin, vmax = st.vmax;
  const isMin = hsMetricIsMin(p, mcode);
  p.clusters.forEach((c, k) => {
    const s = hsSpherePts(c.center[0], c.center[1], c.center[2], Math.max(c.radius_enclosing, 1e-9));
    const mesh = {type: 'mesh3d', x: s.x, y: s.y, z: s.z, alphahull: 0, opacity: 0.55,
      name: '#' + c.rank,
      hovertemplate: `#${c.rank} · 요소 ${c.element_count}<br>${isMin ? '최솟값' : '최댓값'} ${fmt(c.stress_max)} · 평균 ${fmt(c.stress_mean)}` +
                     hsMetricHover(c, mcode) +
                     `<br>포함 반경 ${fmt(c.radius_enclosing, 3)}<extra></extra>`};
    if (st.uniform) {
      mesh.color = HS_FLAT_COLOR; mesh.showscale = false;
    } else {
      mesh.intensity = s.x.map(() => hsMetricValue(c, mcode));
      mesh.cmin = vmin; mesh.cmax = vmax;
      mesh.colorscale = isMin ? HS_SCALE_MIN : HS_SCALE_MAX;
      mesh.showscale = k === 0;
      mesh.colorbar = {title: {text: mdef[1], side: 'right'}, len: 0.7};
    }
    traces.push(mesh);
  });
  traces.push({type: 'scatter3d', mode: 'text', x: p.clusters.map(c => c.center[0]),
               y: p.clusters.map(c => c.center[1]), z: p.clusters.map(c => c.center[2]),
               text: p.clusters.map(c => '#' + c.rank), textfont: {color: '#ffffff', size: 12},
               hoverinfo: 'skip', showlegend: false});
  const ax = t => ({title: t, gridcolor: '#2a2a4a', zerolinecolor: '#2a2a4a', color: '#e0e0e0', backgroundcolor: 'rgba(15,52,96,0.25)', showbackground: true});
  Plotly.newPlot(el, traces, {
    paper_bgcolor: 'transparent', font: {color: '#e0e0e0', size: 11},
    margin: {l: 0, r: 0, t: st.uniform ? 28 : 10, b: 0}, showlegend: false,
    annotations: st.uniform ? [hsFlatAnnotation(p, mcode, st)] : [],
    scene: {aspectmode: 'data', xaxis: ax('x'), yaxis: ax('y'), zaxis: ax('z'),
            camera: {projection: {type: 'orthographic'}}},
  }, PLOT_CONFIG).then(() => {
    // 그리는 사이에 2D 로 바뀌었으면 scene 이 없다 — 카메라 조정은 건너뛴다
    if (!el.layout || !el.layout.scene) return;
    // aspectmode 'data' 는 가장 긴 축을 1 이상으로 늘린다 — 카메라를 그 비율만큼 물려야 잘리지 않는다
    const ar = el.layout.scene.aspectratio || {x: 1, y: 1, z: 1};
    const m = Math.max(ar.x, ar.y, ar.z);
    Plotly.relayout(el, {'scene.camera': {projection: {type: 'orthographic'},
                                          eye: {x: 1.25 * m, y: -1.25 * m, z: 1.25 * m}, up: {x: 0, y: 0, z: 1}}});
  });
}
"""
