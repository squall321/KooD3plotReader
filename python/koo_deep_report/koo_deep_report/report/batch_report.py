"""Batch summary HTML report for multiple koo_deep_report runs."""
from __future__ import annotations
import json
from pathlib import Path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_batch_html(
    results: list[dict],       # list of result.json dicts (koo_deep_report/1.0)
    failed: list[str],         # case names that failed
    skipped: list[str],        # case names that were skipped
    output_root: Path,         # base output dir (for relative report links)
    output_path: Path,         # where to write batch_report.html
    yield_stress: float = 0.0,
) -> None:
    html = _build_html(results, failed, skipped, output_root, yield_stress)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")


def load_results_from_dir(output_root: Path) -> tuple[list[dict], list[str]]:
    """Scan output_root for result.json files. Returns (results, case_dirs_with_json)."""
    results = []
    found_dirs = []
    for p in sorted(output_root.iterdir()):
        rj = p / "result.json"
        if p.is_dir() and rj.exists():
            try:
                d = json.loads(rj.read_text(encoding="utf-8"))
                if d.get("schema", "").startswith("koo_deep_report"):
                    results.append(d)
                    found_dirs.append(p.name)
            except Exception:
                pass
    return results, found_dirs


# ---------------------------------------------------------------------------
# HTML builder
# ---------------------------------------------------------------------------

def _build_html(
    results: list[dict],
    failed: list[str],
    skipped: list[str],
    output_root: Path,
    yield_stress: float,
) -> str:
    n_ok = len(results)
    n_fail = len(failed)
    n_skip = len(skipped)
    n_total = n_ok + n_fail + n_skip

    data_js = json.dumps(results, ensure_ascii=False)
    failed_js = json.dumps(failed, ensure_ascii=False)
    skipped_js = json.dumps(skipped, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Batch Analysis Report</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
:root {{
  --bg: #111317; --bg2: #1a1d23; --bg3: #22262e;
  --fg: #e8eaf0; --fg2: #9ba3b5; --border: #2e3340;
  --accent: #4f8ef7; --accent2: #7ecfff;
  --ok: #4caf6f; --warn: #f5a623; --err: #e05555;
  --font: 'Segoe UI', system-ui, sans-serif;
}}
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ background: var(--bg); color: var(--fg); font-family: var(--font); font-size: 14px; }}
a {{ color: var(--accent2); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}

header {{ background: var(--bg2); border-bottom: 1px solid var(--border); padding: 16px 24px; display: flex; align-items: center; gap: 12px; }}
header h1 {{ font-size: 1.2rem; font-weight: 700; color: var(--fg); }}
header .sub {{ font-size: 0.85rem; color: var(--fg2); }}

.container {{ max-width: 1400px; margin: 0 auto; padding: 20px 24px; }}

/* KPI cards */
.kpi-row {{ display: flex; gap: 12px; margin-bottom: 20px; flex-wrap: wrap; }}
.kpi-card {{ background: var(--bg2); border: 1px solid var(--border); border-radius: 8px; padding: 14px 20px; min-width: 140px; flex: 1; }}
.kpi-label {{ font-size: 0.75rem; color: var(--fg2); margin-bottom: 4px; }}
.kpi-value {{ font-size: 1.5rem; font-weight: 700; }}
.kpi-ok   {{ color: var(--ok); }}
.kpi-warn {{ color: var(--warn); }}
.kpi-err  {{ color: var(--err); }}
.kpi-unit {{ font-size: 0.75rem; color: var(--fg2); margin-top: 2px; }}

/* Toolbar */
.toolbar {{ display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; align-items: center; }}
.toolbar input {{ background: var(--bg3); border: 1px solid var(--border); border-radius: 6px; padding: 6px 10px; color: var(--fg); font-size: 13px; width: 220px; }}
.toolbar select {{ background: var(--bg3); border: 1px solid var(--border); border-radius: 6px; padding: 6px 10px; color: var(--fg); font-size: 13px; }}
.toolbar label {{ font-size: 13px; color: var(--fg2); }}

/* Table */
.table-wrap {{ overflow-x: auto; background: var(--bg2); border: 1px solid var(--border); border-radius: 8px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
thead th {{ background: var(--bg3); padding: 10px 12px; text-align: left; color: var(--fg2); font-weight: 600; white-space: nowrap; cursor: pointer; user-select: none; border-bottom: 1px solid var(--border); }}
thead th:hover {{ color: var(--fg); }}
thead th.sort-asc::after {{ content: ' ▲'; font-size: 10px; }}
thead th.sort-desc::after {{ content: ' ▼'; font-size: 10px; }}
tbody tr {{ border-bottom: 1px solid var(--border); transition: background 0.1s; }}
tbody tr:hover {{ background: var(--bg3); }}
tbody td {{ padding: 8px 12px; white-space: nowrap; }}
tbody tr.row-fail {{ opacity: 0.6; }}
tbody tr.row-skip {{ opacity: 0.5; font-style: italic; }}

.badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }}
.badge-ok   {{ background: #1e3b2a; color: var(--ok); }}
.badge-fail {{ background: #3b1e1e; color: var(--err); }}
.badge-skip {{ background: #2e2e1e; color: var(--warn); }}
.badge-t0 {{ background: #3b1e1e; color: var(--err); }}
.badge-t1 {{ background: #1e2b3b; color: var(--accent2); }}
.badge-t2 {{ background: #1e2b3b; color: var(--accent2); }}
.badge-t3 {{ background: #1e2b3b; color: var(--accent); }}
.badge-t4 {{ background: #1e2b3b; color: var(--accent); }}

/* Charts */
.charts-row {{ display: flex; gap: 16px; margin-top: 20px; flex-wrap: wrap; }}
.chart-card {{ background: var(--bg2); border: 1px solid var(--border); border-radius: 8px; padding: 12px; flex: 1; min-width: 320px; }}
.chart-title {{ font-size: 0.85rem; font-weight: 600; color: var(--fg2); margin-bottom: 8px; }}

/* Failed/Skipped */
.fail-section {{ margin-top: 16px; }}
.fail-section summary {{ cursor: pointer; color: var(--err); font-weight: 600; padding: 8px 0; }}
.fail-list {{ padding: 8px 16px; font-size: 12px; color: var(--fg2); line-height: 1.8; }}

.empty-msg {{ padding: 40px; text-align: center; color: var(--fg2); }}

/* Tab navigation */
.tab-nav {{ display: flex; gap: 0; margin-top: 24px; border-bottom: 2px solid var(--border); }}
.tab-btn {{ background: none; border: none; padding: 10px 20px; font-size: 14px; color: var(--fg2); cursor: pointer; border-bottom: 2px solid transparent; margin-bottom: -2px; transition: all 0.15s; }}
.tab-btn:hover {{ color: var(--fg); }}
.tab-btn.active {{ color: var(--accent2); border-bottom-color: var(--accent2); font-weight: 600; }}
.tab-panel {{ display: none; padding-top: 16px; }}
.tab-panel.active {{ display: block; }}

/* Part filter */
.part-filter {{ display: flex; gap: 8px; align-items: center; margin-bottom: 12px; flex-wrap: wrap; }}
.part-filter input {{ background: var(--bg3); border: 1px solid var(--border); border-radius: 6px; padding: 6px 12px; color: var(--fg); font-size: 13px; width: 320px; }}
.part-filter .hint {{ font-size: 11px; color: var(--fg2); }}
.part-filter .clear-btn {{ background: var(--bg3); border: 1px solid var(--border); border-radius: 6px; padding: 5px 10px; color: var(--fg2); cursor: pointer; font-size: 12px; }}
.part-filter .clear-btn:hover {{ color: var(--fg); border-color: var(--accent); }}

/* Part comparison table */
.part-table thead th {{ position: sticky; top: 0; z-index: 1; }}
.part-table .val-stress {{ color: var(--accent2); }}
.part-table .val-strain {{ color: #7ecfa0; }}
.part-table .val-disp   {{ color: #d4a0f7; }}
.part-table .val-warn   {{ color: var(--warn); font-weight: 600; }}
.part-table .val-danger  {{ color: var(--err); font-weight: 600; }}
</style>
</head>
<body>
<header>
  <div>
    <h1>Batch Analysis Report</h1>
    <div class="sub">koo_deep_report — {output_root}</div>
  </div>
</header>
<div class="container">
  <div class="kpi-row" id="kpi-row"></div>

  <!-- Tab navigation -->
  <div class="tab-nav">
    <button class="tab-btn active" data-tab="tab-overview">케이스 요약</button>
    <button class="tab-btn" data-tab="tab-parts">파트별 비교</button>
  </div>

  <div id="tab-overview" class="tab-panel active">
    <div class="toolbar">
      <input id="search-box" type="text" placeholder="케이스 이름 검색...">
      <label>Tier:
        <select id="tier-filter">
          <option value="">전체</option>
          <option value="0">T0</option>
          <option value="1">T1</option>
          <option value="2">T2</option>
          <option value="3">T3</option>
          <option value="4">T4</option>
        </select>
      </label>
      <label>상태:
        <select id="status-filter">
          <option value="">전체</option>
          <option value="ok">성공</option>
          <option value="fail">실패</option>
          <option value="skip">스킵</option>
        </select>
      </label>
    </div>

    <div class="table-wrap">
      <table id="cases-table">
        <thead>
          <tr>
            <th data-col="idx">#</th>
            <th data-col="label">케이스</th>
            <th data-col="status">상태</th>
            <th data-col="tier">Tier</th>
            <th data-col="num_parts">Parts</th>
            <th data-col="t_end">T end</th>
            <th data-col="peak_stress">피크 응력 (MPa)</th>
            <th data-col="peak_strain">피크 변형률</th>
            <th data-col="peak_disp">피크 변위 (mm)</th>
            <th data-col="er_min">E-ratio min</th>
            {'<th data-col="sf">Safety Factor</th>' if yield_stress > 0 else ''}
            <th>리포트</th>
          </tr>
        </thead>
        <tbody id="table-body"></tbody>
      </table>
    </div>

    <div class="charts-row">
      <div class="chart-card">
        <div class="chart-title">케이스별 피크 Von Mises 응력 (MPa)</div>
        <div id="chart-stress" style="height:300px"></div>
      </div>
      <div class="chart-card">
        <div class="chart-title">케이스별 에너지 비율 (min)</div>
        <div id="chart-energy" style="height:300px"></div>
      </div>
    </div>
  </div>

  <div id="tab-parts" class="tab-panel">
    <div class="part-filter">
      <input id="part-filter-input" type="text" placeholder="파트 이름 필터 (콤마 구분, 예: PKG, CELL, BOARD)">
      <button class="clear-btn" onclick="clearPartFilter()">초기화</button>
      <span class="hint">콤마로 키워드 구분 — 대소문자 무관, 부분 매칭</span>
    </div>
    <div class="part-filter">
      <label style="font-size:13px;color:var(--fg2);">정렬 기준:
        <select id="part-sort-field" style="background:var(--bg3);border:1px solid var(--border);border-radius:6px;padding:5px 8px;color:var(--fg);font-size:13px;">
          <option value="peak_stress">피크 응력</option>
          <option value="peak_strain">피크 변형률</option>
          <option value="peak_disp_mag">피크 변위</option>
          <option value="stress_ratio">응력 비율</option>
          <option value="strain_ratio">변형률 비율</option>
        </select>
      </label>
      <label style="font-size:13px;color:var(--fg2);">표시:
        <select id="part-metric-select" style="background:var(--bg3);border:1px solid var(--border);border-radius:6px;padding:5px 8px;color:var(--fg);font-size:13px;">
          <option value="peak_stress">피크 응력 (MPa)</option>
          <option value="peak_strain">피크 변형률</option>
          <option value="peak_disp_mag">피크 변위 (mm)</option>
        </select>
      </label>
    </div>

    <div class="table-wrap" style="max-height:600px;overflow-y:auto;">
      <table class="part-table" id="part-compare-table">
        <thead id="part-thead"></thead>
        <tbody id="part-tbody"></tbody>
      </table>
    </div>

    <div class="charts-row" style="margin-top:16px">
      <div class="chart-card" style="min-width:100%">
        <div class="chart-title">파트별 크로스-케이스 비교</div>
        <div id="chart-part-compare" style="height:400px"></div>
      </div>
    </div>
  </div>

  <div class="fail-section">
    <details id="fail-details" style="display:none">
      <summary id="fail-summary"></summary>
      <div class="fail-list" id="fail-list"></div>
    </details>
    <details id="skip-details" style="display:none">
      <summary id="skip-summary" style="color:var(--warn)"></summary>
      <div class="fail-list" id="skip-list"></div>
    </details>
  </div>
</div>

<script>
const RESULTS  = {data_js};
const FAILED   = {failed_js};
const SKIPPED  = {skipped_js};
const YIELD_STRESS = {yield_stress};

const PLOT_LAYOUT = {{
  paper_bgcolor: 'rgba(0,0,0,0)',
  plot_bgcolor:  'rgba(0,0,0,0)',
  font: {{ color: '#9ba3b5', size: 12 }},
  margin: {{ l: 60, r: 20, t: 20, b: 100 }},
  xaxis: {{ gridcolor: '#2e3340', tickangle: -40 }},
  yaxis: {{ gridcolor: '#2e3340' }},
}};
const PLOT_CONFIG = {{ displayModeBar: false, responsive: true }};

// Build row data
const ROWS = [];
let idx = 1;
for (const r of RESULTS) {{
  const s = r.summary || {{}};
  const m = r.metadata || {{}};
  ROWS.push({{
    idx: idx++,
    label: r.label || m.project_name || '—',
    status: 'ok',
    tier: r.tier ?? -1,
    num_parts: m.num_parts ?? 0,
    t_end: m.t_end ?? 0,
    peak_stress: s.peak_stress_global ?? 0,
    peak_strain: s.peak_strain_global ?? 0,
    peak_disp: s.peak_disp_global ?? 0,
    er_min: s.energy_ratio_min ?? null,
    sf: (() => {{
      if (YIELD_STRESS <= 0 || !(s.peak_stress_global > 0)) return null;
      return YIELD_STRESS / s.peak_stress_global;
    }})(),
    report_link: r.label || m.project_name || null,
    _raw: r,
  }});
}}
for (const f of FAILED) {{
  ROWS.push({{ idx: idx++, label: f, status: 'fail', tier: -1, num_parts: 0, t_end: 0,
    peak_stress: 0, peak_strain: 0, peak_disp: 0, er_min: null, sf: null, report_link: null }});
}}
for (const sk of SKIPPED) {{
  ROWS.push({{ idx: idx++, label: sk, status: 'skip', tier: -1, num_parts: 0, t_end: 0,
    peak_stress: 0, peak_strain: 0, peak_disp: 0, er_min: null, sf: null, report_link: null }});
}}

// KPI
function renderKPIs() {{
  const okRows = ROWS.filter(r => r.status === 'ok');
  const stresses = okRows.map(r => r.peak_stress).filter(v => v > 0);
  const avgStr = stresses.length ? stresses.reduce((a,b)=>a+b,0)/stresses.length : 0;
  const maxStr = stresses.length ? Math.max(...stresses) : 0;
  const erVals = okRows.map(r => r.er_min).filter(v => v !== null);
  const erMin  = erVals.length ? Math.min(...erVals) : null;

  const n_ok   = RESULTS.length;
  const n_fail = FAILED.length;
  const n_skip = SKIPPED.length;
  const n_tot  = n_ok + n_fail + n_skip;

  const fmt = (v, d=2) => v == null ? '—' : Number(v).toFixed(d);

  document.getElementById('kpi-row').innerHTML = `
    <div class="kpi-card">
      <div class="kpi-label">전체 케이스</div>
      <div class="kpi-value">${{n_tot}}</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">성공</div>
      <div class="kpi-value kpi-ok">${{n_ok}}</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">실패</div>
      <div class="kpi-value ${{n_fail>0?'kpi-err':''}}">${{n_fail}}</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">스킵</div>
      <div class="kpi-value ${{n_skip>0?'kpi-warn':''}}">${{n_skip}}</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">최대 응력</div>
      <div class="kpi-value">${{fmt(maxStr)}}</div>
      <div class="kpi-unit">MPa</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">평균 응력</div>
      <div class="kpi-value">${{fmt(avgStr)}}</div>
      <div class="kpi-unit">MPa</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">에너지 비율 (최소)</div>
      <div class="kpi-value ${{erMin!==null&&erMin>1.1?'kpi-err':erMin!==null&&erMin>1.05?'kpi-warn':''}}">${{fmt(erMin,4)}}</div>
    </div>
  `;
}}

// Table
let sortCol = 'idx', sortDir = 1;
let filteredRows = [...ROWS];

function applyFilter() {{
  const q = document.getElementById('search-box').value.toLowerCase();
  const tier = document.getElementById('tier-filter').value;
  const status = document.getElementById('status-filter').value;
  filteredRows = ROWS.filter(r => {{
    if (q && !r.label.toLowerCase().includes(q)) return false;
    if (tier !== '' && String(r.tier) !== tier) return false;
    if (status && r.status !== status) return false;
    return true;
  }});
  renderTable();
}}

function sortRows() {{
  filteredRows.sort((a, b) => {{
    let av = a[sortCol], bv = b[sortCol];
    if (av === null) av = -Infinity;
    if (bv === null) bv = -Infinity;
    return (av < bv ? -1 : av > bv ? 1 : 0) * sortDir;
  }});
}}

function fmt(v, d=2) {{ return v == null || v === 0 ? '—' : Number(v).toFixed(d); }}
function fmtE(v) {{ return v == null ? '—' : Number(v).toFixed(4); }}

function tierBadge(t) {{
  if (t < 0) return '';
  return `<span class="badge badge-t${{t}}">T${{t}}</span>`;
}}

function statusBadge(s) {{
  if (s === 'ok')   return '<span class="badge badge-ok">정상</span>';
  if (s === 'fail') return '<span class="badge badge-fail">실패</span>';
  if (s === 'skip') return '<span class="badge badge-skip">스킵</span>';
  return '';
}}

function erClass(v) {{
  if (v === null) return '';
  if (v > 1.1)  return 'style="color:var(--err)"';
  if (v > 1.05) return 'style="color:var(--warn)"';
  return '';
}}

function sfClass(v) {{
  if (v === null) return '';
  if (v >= 1.0)  return 'style="color:var(--ok)"';
  if (v >= 0.85) return 'style="color:var(--warn)"';
  return 'style="color:var(--err)"';
}}

function reportLink(r) {{
  if (r.report_link) {{
    return `<a href="./${{encodeURIComponent(r.label || r.report_link)}}/report.html" target="_blank">열기</a>`;
  }}
  return '—';
}}

function renderTable() {{
  sortRows();
  const showSF = YIELD_STRESS > 0;
  const tbody = document.getElementById('table-body');
  if (!filteredRows.length) {{
    tbody.innerHTML = `<tr><td colspan="20" class="empty-msg">케이스 없음</td></tr>`;
    return;
  }}
  tbody.innerHTML = filteredRows.map(r => `
    <tr class="${{r.status==='fail'?'row-fail':r.status==='skip'?'row-skip':''}}">
      <td>${{r.idx}}</td>
      <td>${{r.label}}</td>
      <td>${{statusBadge(r.status)}}</td>
      <td>${{tierBadge(r.tier)}}</td>
      <td>${{r.num_parts || '—'}}</td>
      <td>${{r.t_end ? Number(r.t_end).toFixed(1) : '—'}}</td>
      <td>${{fmt(r.peak_stress)}}</td>
      <td>${{fmt(r.peak_strain, 4)}}</td>
      <td>${{fmt(r.peak_disp)}}</td>
      <td ${{erClass(r.er_min)}}>${{fmtE(r.er_min)}}</td>
      ${{showSF ? `<td ${{sfClass(r.sf)}}>${{r.sf!==null?Number(r.sf).toFixed(2):'—'}}</td>` : ''}}
      <td>${{reportLink(r)}}</td>
    </tr>`).join('');
}}

// Charts
function renderCharts() {{
  const okRows = ROWS.filter(r => r.status === 'ok' && r.peak_stress > 0);
  if (!okRows.length) return;

  // Stress chart
  const stressColor = okRows.map(r => {{
    if (YIELD_STRESS > 0) {{
      if (r.peak_stress > YIELD_STRESS) return '#e05555';
      if (r.peak_stress > YIELD_STRESS * 0.85) return '#f5a623';
      return '#4caf6f';
    }}
    return '#4f8ef7';
  }});
  Plotly.newPlot('chart-stress', [{{
    type: 'bar', x: okRows.map(r => r.label), y: okRows.map(r => r.peak_stress),
    marker: {{ color: stressColor }}, hovertemplate: '%{{x}}<br>%{{y:.2f}} MPa<extra></extra>',
  }}], PLOT_LAYOUT, PLOT_CONFIG);

  // Energy ratio chart
  const erRows = ROWS.filter(r => r.status === 'ok' && r.er_min !== null);
  if (erRows.length) {{
    const erColor = erRows.map(r => r.er_min > 1.1 ? '#e05555' : r.er_min > 1.05 ? '#f5a623' : '#4f8ef7');
    Plotly.newPlot('chart-energy', [
      {{ type: 'bar', x: erRows.map(r => r.label), y: erRows.map(r => r.er_min),
         marker: {{ color: erColor }}, hovertemplate: '%{{x}}<br>%{{y:.4f}}<extra></extra>' }},
      {{ type: 'scatter', mode: 'lines', x: [erRows[0].label, erRows[erRows.length-1].label],
         y: [1.05, 1.05], line: {{ color: '#f5a623', dash: 'dot' }}, name: '+5%', showlegend: true }},
    ], PLOT_LAYOUT, PLOT_CONFIG);
  }}
}}

// Fail/Skip sections
function renderFailSections() {{
  if (FAILED.length) {{
    const d = document.getElementById('fail-details');
    d.style.display = '';
    document.getElementById('fail-summary').textContent = `실패 케이스 ${{FAILED.length}}개`;
    document.getElementById('fail-list').innerHTML = FAILED.map(f => `<div>${{f}}</div>`).join('');
  }}
  if (SKIPPED.length) {{
    const d = document.getElementById('skip-details');
    d.style.display = '';
    document.getElementById('skip-summary').textContent = `스킵된 케이스 ${{SKIPPED.length}}개`;
    document.getElementById('skip-list').innerHTML = SKIPPED.map(s => `<div>${{s}}</div>`).join('');
  }}
}}

// Table sorting
document.querySelectorAll('thead th[data-col]').forEach(th => {{
  th.addEventListener('click', () => {{
    const col = th.dataset.col;
    if (sortCol === col) sortDir *= -1;
    else {{ sortCol = col; sortDir = 1; }}
    document.querySelectorAll('thead th').forEach(t => t.classList.remove('sort-asc','sort-desc'));
    th.classList.add(sortDir === 1 ? 'sort-asc' : 'sort-desc');
    renderTable();
  }});
}});

document.getElementById('search-box').addEventListener('input', applyFilter);
document.getElementById('tier-filter').addEventListener('change', applyFilter);
document.getElementById('status-filter').addEventListener('change', applyFilter);

// ============================================================
// Tab switching
// ============================================================
document.querySelectorAll('.tab-btn').forEach(btn => {{
  btn.addEventListener('click', () => {{
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(btn.dataset.tab).classList.add('active');
    if (btn.dataset.tab === 'tab-parts') renderPartComparison();
  }});
}});

// ============================================================
// Part comparison
// ============================================================
// Build ALL_PARTS: {{ part_name -> {{ pid, cases: {{ case_label -> part_data }} }} }}
const ALL_PARTS = {{}};
for (const r of RESULTS) {{
  const caseLabel = r.label || (r.metadata || {{}}).project_name || '?';
  const parts = r.parts || {{}};
  for (const [pid, pdata] of Object.entries(parts)) {{
    const pname = pdata.name || `Part ${{pid}}`;
    const key = pname;
    if (!ALL_PARTS[key]) ALL_PARTS[key] = {{ pid: parseInt(pid), cases: {{}} }};
    ALL_PARTS[key].cases[caseLabel] = pdata;
  }}
}}
const CASE_LABELS = RESULTS.map(r => r.label || (r.metadata || {{}}).project_name || '?');

let _partFilterKeywords = [];

function partMatchesFilter(partName) {{
  if (_partFilterKeywords.length === 0) return true;
  const lower = partName.toLowerCase();
  return _partFilterKeywords.some(kw => lower.includes(kw));
}}

function getFilteredParts() {{
  const sortField = document.getElementById('part-sort-field').value;
  let entries = Object.entries(ALL_PARTS).filter(([name]) => partMatchesFilter(name));

  // Sort by max value across all cases
  entries.sort((a, b) => {{
    const aMax = Math.max(...Object.values(a[1].cases).map(c => c[sortField] || 0));
    const bMax = Math.max(...Object.values(b[1].cases).map(c => c[sortField] || 0));
    return bMax - aMax;
  }});
  return entries;
}}

function valClass(pdata, field) {{
  if (!pdata) return '';
  if (field === 'peak_stress') {{
    if (pdata.stress_warning === 'OVER') return 'val-danger';
    if (pdata.stress_ratio && pdata.stress_ratio > 0.85) return 'val-warn';
    return 'val-stress';
  }}
  if (field === 'peak_strain') {{
    if (pdata.strain_warning === 'OVER') return 'val-danger';
    if (pdata.strain_ratio && pdata.strain_ratio > 0.85) return 'val-warn';
    return 'val-strain';
  }}
  return 'val-disp';
}}

function fmtVal(v, field) {{
  if (v == null || v === 0) return '—';
  if (field === 'peak_strain') return Number(v).toFixed(4);
  return Number(v).toFixed(2);
}}

function renderPartComparison() {{
  const metric = document.getElementById('part-metric-select').value;
  const parts = getFilteredParts();

  // Table header: Part Name | Case1 | Case2 | ... | Max
  const thead = document.getElementById('part-thead');
  thead.innerHTML = `<tr>
    <th style="min-width:160px">파트</th>
    ${{CASE_LABELS.map(c => `<th style="min-width:90px">${{c}}</th>`).join('')}}
    <th style="min-width:80px">최대</th>
  </tr>`;

  const tbody = document.getElementById('part-tbody');
  if (!parts.length) {{
    tbody.innerHTML = '<tr><td colspan="100" class="empty-msg">매칭되는 파트 없음</td></tr>';
    renderPartChart([], metric);
    return;
  }}

  tbody.innerHTML = parts.map(([name, info]) => {{
    const vals = CASE_LABELS.map(cl => {{
      const pd = info.cases[cl];
      const v = pd ? pd[metric] : null;
      return `<td class="${{valClass(pd, metric)}}">${{fmtVal(v, metric)}}</td>`;
    }});
    const maxVal = Math.max(...Object.values(info.cases).map(c => c[metric] || 0));
    return `<tr>
      <td style="font-weight:600">${{name}}</td>
      ${{vals.join('')}}
      <td style="font-weight:700">${{fmtVal(maxVal, metric)}}</td>
    </tr>`;
  }}).join('');

  renderPartChart(parts, metric);
}}

function renderPartChart(parts, metric) {{
  const labels = {{ peak_stress: '피크 응력 (MPa)', peak_strain: '피크 변형률', peak_disp_mag: '피크 변위 (mm)' }};
  const colors = ['#4f8ef7','#7ecfff','#f5a623','#4caf6f','#e05555','#d4a0f7','#ff9cf5','#8fde7e','#ffcc00','#ff6b6b',
                  '#6bdfff','#c78fff','#ff9e6b','#6bff9e','#ff6bdf','#9eff6b','#6b9eff','#dfff6b','#ff6b9e','#6bffdf'];

  if (!parts.length) {{
    Plotly.purge('chart-part-compare');
    return;
  }}

  // Show top 15 parts max for readability
  const topParts = parts.slice(0, 15);
  const traces = topParts.map(([name, info], i) => ({{
    type: 'bar',
    name: name,
    x: CASE_LABELS,
    y: CASE_LABELS.map(cl => {{
      const pd = info.cases[cl];
      return pd ? (pd[metric] || 0) : 0;
    }}),
    marker: {{ color: colors[i % colors.length] }},
    hovertemplate: `${{name}}<br>%{{x}}: %{{y:.3f}}<extra></extra>`,
  }})));

  Plotly.newPlot('chart-part-compare', traces, {{
    ...PLOT_LAYOUT,
    barmode: 'group',
    margin: {{ l: 60, r: 20, t: 30, b: 100 }},
    yaxis: {{ ...PLOT_LAYOUT.yaxis, title: labels[metric] || metric }},
    legend: {{ font: {{ color: '#9ba3b5', size: 11 }}, bgcolor: 'rgba(0,0,0,0)' }},
  }}, PLOT_CONFIG);
}}

function clearPartFilter() {{
  document.getElementById('part-filter-input').value = '';
  _partFilterKeywords = [];
  renderPartComparison();
}}

// Part filter input (debounced)
let _partFilterTimer = null;
document.getElementById('part-filter-input').addEventListener('input', (e) => {{
  clearTimeout(_partFilterTimer);
  _partFilterTimer = setTimeout(() => {{
    const raw = e.target.value.trim();
    _partFilterKeywords = raw ? raw.split(',').map(k => k.trim().toLowerCase()).filter(k => k) : [];
    renderPartComparison();
  }}, 300);
}});
document.getElementById('part-sort-field').addEventListener('change', renderPartComparison);
document.getElementById('part-metric-select').addEventListener('change', renderPartComparison);

// Init
applyFilter();
renderKPIs();
renderCharts();
renderFailSections();
</script>
</body>
</html>
"""
