"""Generate single-simulation HTML report."""
from __future__ import annotations
import json
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

    tabs = [("overview", "Overview")]
    if has_stress:
        tabs.append(("stress", "응력·변형률"))
    if has_motion:
        tabs.append(("motion", "운동"))
    if has_tensors:
        tabs.append(("tensor", "응력 텐서"))
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
                "peak_strain": p.peak_strain,
                "peak_max_principal": p.peak_max_principal,
                "peak_min_principal": p.peak_min_principal,
                "peak_max_principal_strain": p.peak_max_principal_strain,
                "peak_min_principal_strain": p.peak_min_principal_strain,
                "peak_disp_mag": p.peak_disp_mag,
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
        "min_principal_strain": [],
        "peak_element_tensors": [],
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
        data["peak_element_tensors"] = [{
            "element_id": t.element_id, "part_id": t.part_id,
            "reason": t.reason, "peak_value": t.peak_value, "peak_time": t.peak_time,
            "time": t.time, "sxx": t.sxx, "syy": t.syy, "szz": t.szz,
            "sxy": t.sxy, "syz": t.syz, "szx": t.szx,
        } for t in dr.peak_element_tensors]
        data["motion"] = {
            str(pid): {
                "part_id": pid,
                "part_name": md.part_name,
                "t": md.t,
                "disp_x": md.disp_x,
                "disp_y": md.disp_y,
                "disp_z": md.disp_z,
                "disp_mag": md.disp_mag,
                "vel_mag": md.vel_mag,
                "acc_mag": md.acc_mag,
                "max_disp_mag": md.max_disp_mag,
                "peak_disp_mag": md.peak_disp_mag,
                "peak_vel_mag": md.peak_vel_mag,
                "peak_acc_mag": md.peak_acc_mag,
            }
            for pid, md in dr.motion.items()
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
            "t": gl.t,
            "total_energy": gl.total_energy,
            "kinetic_energy": gl.kinetic_energy,
            "internal_energy": gl.internal_energy,
            "hourglass_energy": gl.hourglass_energy,
            "energy_ratio": gl.energy_ratio,
            "mass": gl.mass,
            "energy_ratio_min": gl.energy_ratio_min,
            "energy_ratio_max": gl.energy_ratio_max,
            "has_mass_added": gl.has_mass_added,
            "normal_termination": gl.normal_termination,
        }

    bn = result.binout_data
    if bn:
        data["binout"] = {
            "matsum": {
                "part_ids": bn.matsum.part_ids,
                "part_names": bn.matsum.part_names,
                "t": bn.matsum.t,
                "internal_energy": bn.matsum.internal_energy,
                "kinetic_energy": bn.matsum.kinetic_energy,
            } if bn.matsum else None,
            "rcforc": [
                {
                    "id": ifc.interface_id,
                    "name": ifc.name,
                    "side": ifc.side,
                    "t": ifc.t,
                    "fx": ifc.fx, "fy": ifc.fy, "fz": ifc.fz,
                    "fmag": ifc.fmag,
                    "peak_fmag": ifc.peak_fmag,
                }
                for ifc in bn.rcforc
            ],
            "sleout": [
                {
                    "id": ifc.interface_id,
                    "name": ifc.name,
                    "t": ifc.t,
                    "total_energy": ifc.total_energy,
                    "friction_energy": ifc.friction_energy,
                }
                for ifc in bn.sleout
            ],
        }

    return data


def _series_to_dict(s) -> dict:
    return {
        "part_id": s.part_id,
        "part_name": s.part_name,
        "quantity": s.quantity,
        "unit": s.unit,
        "global_max": s.global_max,
        "global_min": s.global_min,
        "time_of_max": s.time_of_max,
        "t": s.t,
        "max_vals": s.max_vals,
        "avg_vals": s.avg_vals,
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

@media (max-width: 600px) {
  .kpi-grid { grid-template-columns: repeat(2, 1fr); }
  .content { padding: 12px; }
}
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

  let kpis = `
  <div class="kpi-card">
    <div class="kpi-label">피크 Von Mises 응력</div>
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
    <div class="kpi-unit">mm</div>
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

  return `
<div class="kpi-grid">${kpis}</div>
<div class="sec-title">응력 상위 부품</div>
<div class="chart-box">${topBars || '<div style="color:var(--fg2);padding:8px">응력 데이터 없음</div>'}</div>`;
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
    .sort((a,b) => b[1].peak_disp_mag - a[1].peak_disp_mag);
  const maxD = mEntries[0]?.[1].peak_disp_mag || 1;

  const dispBars = mEntries.map(([pid, m]) => {
    const pct = (m.peak_disp_mag / maxD * 100).toFixed(1);
    return `<div class="bar-row">
      <div class="bar-label" title="${m.part_name}">${m.part_name ? 'Part '+pid+' ('+m.part_name+')' : 'Part '+pid}</div>
      <div class="bar-track"><div class="bar-fill" style="background:var(--accent2);width:${pct}%"></div></div>
      <div class="bar-val">${fmt(m.peak_disp_mag)} mm</div>
    </div>`;
  }).join('');

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
  <div class="kpi-card"><div class="kpi-label">피크 변위</div><div class="kpi-value">${fmt(p?.peak_disp_mag)}</div><div class="kpi-unit">mm</div></div>
  <div class="kpi-card"><div class="kpi-label">피크 가속도</div><div class="kpi-value">${fmt(p?.peak_acc_mag)}</div><div class="kpi-unit">—</div></div>`;
  if (sf !== null && sf !== undefined) {
    kpiHtml += `<div class="kpi-card"><div class="kpi-label">Safety Factor</div><div class="kpi-value ${sfClass}">${fmt(sf,3)}</div><div class="kpi-unit">σ_yield=${fmt(DATA.yield_stress)} MPa</div></div>`;
  }
  if (p?.peak_element_id) {
    kpiHtml += `<div class="kpi-card"><div class="kpi-label">피크 Element</div><div class="kpi-value" style="font-size:1rem">#${p.peak_element_id}</div><div class="kpi-unit">max stress 위치</div></div>`;
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

  // rcforc: interface peak force table + selector
  if (bn.rcforc && bn.rcforc.length) {
    const slaves = bn.rcforc.filter(r => r.side === 0);
    const rows = slaves.map(r =>
      `<tr><td>${r.id}</td><td>${r.name}</td><td class="num">${fmt(r.peak_fmag)}</td></tr>`
    ).join('');
    const opts = slaves.map(r =>
      `<option value="${r.id}">${r.name} (id=${r.id})</option>`).join('');
    html += `
<div class="sec-title">접촉 인터페이스 피크 합력</div>
<div class="chart-box">
  <table class="data-table"><thead><tr><th>ID</th><th>이름</th><th>피크 합력</th></tr></thead>
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
  Plotly.newPlot('matsum-chart', [
    {x: ms.t, y: ie, name: '내부 에너지', line: {color: COLORS[2]}},
    {x: ms.t, y: ke, name: '운동 에너지', line: {color: COLORS[1]}},
  ], {...PLOT_LAYOUT, title: {text: `에너지 — Part ${ms.part_ids[idx]}${ms.part_names[idx] ? ' (' + ms.part_names[idx] + ')' : ''}`, font:{size:13}}}, PLOT_CONFIG);
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

function renderGallery() {
  if (!DATA.renders || !DATA.renders.length) {
    return '<div class="warn-box">렌더 파일 없음</div>';
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

  return html;
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
    const arCls = q.peak_aspect_ratio > 10 ? 'crit' : (q.peak_aspect_ratio > 5 ? 'warn' : '');
    const jacCls = q.min_jacobian < 0 ? 'crit' : (q.min_jacobian < 0.3 ? 'warn' : '');
    const negCls = q.max_negative_jacobian_count > 0 ? 'crit' : '';

    html += `<tr>
      <td>${q.part_id}</td><td>${q.part_name}</td><td>${q.element_type}</td><td>${q.num_elements}</td>
      <td class="${arCls}">${q.peak_aspect_ratio.toFixed(2)}</td>
      <td class="${jacCls}">${q.min_jacobian.toFixed(3)}</td>
      <td>${q.peak_warpage.toFixed(1)}</td>
      <td>${q.peak_skewness.toFixed(3)}</td>
      <td>${q.min_volume_change.toFixed(3)}</td>
      <td>${q.max_volume_change.toFixed(3)}</td>
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
  </div>
</div>
<div class="sec-title">파일 목록</div>
<div class="chart-box"><div class="file-list">${fileList}</div></div>`;
}
"""
