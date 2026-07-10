# 보고서 HTML 의 전체 CSS 템플릿 (html_report.py 에서 기계적 분할, 바이트 불변)

_CSS = r"""
* { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --bg: #0a0c14;
  --bg2: #11141f;
  --bg3: #1a1e2e;
  --bg4: #232839;
  --line: rgba(255,255,255,0.06);
  --line2: rgba(255,255,255,0.10);
  --fg: #e6ebff;
  --fg2: #aab2cf;
  --dim: #5c6383;
  --num: #c8d4ff;
  --accent: #4dd6ff;
  --accent2: #ff5e84;
  --warn: #f0a830;
  --good: #4adfa1;
  --crit: #ff3854;
  --tag: #b46eff;
  --device-aspect: 1;
}
html, body {
  background: var(--bg); color: var(--fg);
  font-family: 'Inter', -apple-system, 'Pretendard', 'Segoe UI', system-ui, sans-serif;
  font-size: 12px; -webkit-font-smoothing: antialiased;
  overflow-x: hidden;
}
.mono, .num { font-family: 'JetBrains Mono', 'SF Mono', Menlo, 'Courier New', monospace; font-variant-numeric: tabular-nums; }
b { color: var(--fg); font-weight: 600; }
.topbar { position: sticky; top: 0; z-index: 50; background: rgba(10,12,20,0.88); backdrop-filter: blur(12px); border-bottom: 1px solid var(--line); display: grid; grid-template-columns: auto 1fr auto; align-items: center; padding: 10px 32px; gap: 24px; }
.topbar .brand { font-size: 11px; letter-spacing: 4px; color: var(--accent); font-weight: 700; }
.topbar .meta { display: flex; gap: 20px; font-size: 11px; color: var(--dim); overflow-x: auto; white-space: nowrap; }
.topbar .meta b { color: var(--fg2); font-weight: 500; }
.topbar .nav { display: flex; gap: 4px; }
.topbar .nav a { text-decoration: none; color: var(--dim); padding: 4px 10px; border-radius: 4px; font-size: 11px; letter-spacing: 2px; font-weight: 600; transition: all 0.2s; cursor: pointer; }
.topbar .nav a:hover { color: var(--fg); background: var(--bg3); }
.topbar .nav a.active { color: var(--bg); background: var(--accent); }
.page { padding: 28px 32px 60px; max-width: 1680px; margin: 0 auto; }
.page-head { display: flex; align-items: baseline; gap: 16px; margin-bottom: 18px; padding-bottom: 14px; border-bottom: 1px solid var(--line); flex-wrap: wrap; }
.page-head .num { font-size: 24px; font-weight: 800; color: var(--accent); letter-spacing: -1px; }
.page-head .ttl { font-size: 20px; font-weight: 700; }
.page-head .sub { color: var(--dim); font-size: 12px; flex: 1; text-align: right; letter-spacing: 1px; }
.page-head .tagline { color: var(--tag); font-size: 11px; letter-spacing: 4px; font-weight: 600; }
.grid { display: grid; gap: 14px; }
.g-12 { grid-template-columns: repeat(12, 1fr); }
.panel { background: var(--bg2); border: 1px solid var(--line); border-radius: 8px; padding: 14px 16px; position: relative; overflow: hidden; }
.panel .ph { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 10px; padding-bottom: 8px; border-bottom: 1px solid var(--line); }
.panel .ph .pt { font-size: 11px; font-weight: 700; letter-spacing: 2px; color: var(--accent); }
.panel .ph .pd { font-size: 10px; color: var(--dim); }
.panel .pcap { font-size: 10px; color: var(--dim); margin-top: 8px; line-height: 1.5; }
.col-3{grid-column:span 3;} .col-4{grid-column:span 4;} .col-5{grid-column:span 5;} .col-6{grid-column:span 6;} .col-7{grid-column:span 7;} .col-8{grid-column:span 8;} .col-9{grid-column:span 9;} .col-12{grid-column:span 12;}
.kpi-strip { display: grid; grid-template-columns: repeat(8, 1fr); gap: 0; border: 1px solid var(--line); border-radius: 8px; overflow: hidden; background: var(--bg2); }
.kpi-strip .k { padding: 10px 14px; border-right: 1px solid var(--line); }
.kpi-strip .k:last-child { border-right: none; }
.kpi-strip .k .v { font-size: 17px; font-weight: 700; color: var(--fg); font-family: 'JetBrains Mono', monospace; }
.kpi-strip .k .v .u { color: var(--dim); font-size: 11px; font-weight: 500; margin-left: 4px; font-family: 'Inter', system-ui; }
.kpi-strip .k .l { font-size: 9px; color: var(--dim); letter-spacing: 2px; text-transform: uppercase; margin-top: 4px; }
table.dt { width: 100%; border-collapse: collapse; font-size: 11px; }
table.dt th { color: var(--dim); font-weight: 600; text-align: right; padding: 6px 6px; border-bottom: 1px solid var(--line2); font-size: 10px; letter-spacing: 1px; text-transform: uppercase; white-space: nowrap; }
table.dt th.tl { text-align: left; }
table.dt td { padding: 5px 6px; border-bottom: 1px solid var(--line); text-align: right; vertical-align: middle; white-space: nowrap; }
table.dt td.tl { text-align: left; }
table.dt tr:hover td { background: rgba(255,255,255,0.02); }
table.dt tr.r-crit td:first-child::before { content: '\25A0 '; color: var(--crit); }
table.dt tr.r-warn td:first-child::before { content: '\25A0 '; color: var(--warn); }
table.dt tr.r-safe td:first-child::before { content: '\25A0 '; color: var(--good); }
table.dt td.num { color: var(--num); font-family: 'JetBrains Mono', monospace; }
table.dt td.dim { color: var(--dim); }
table.dt td.b { color: var(--fg); font-weight: 600; }
.hero-line { display: grid; grid-template-columns: 1fr auto; gap: 24px; align-items: end; padding: 8px 0 18px; }
.hero-line h1 { font-size: 28px; font-weight: 800; letter-spacing: -1px; line-height: 1.1; color: var(--fg); }
.hero-line h1 .acc { color: var(--accent); }
.hero-line .lede { color: var(--fg2); font-size: 12px; margin-top: 6px; max-width: 700px; line-height: 1.6; }
.hero-line .right { text-align: right; }
.hero-line .right .pk { color: var(--crit); font-size: 11px; letter-spacing: 3px; font-weight: 700; }
.hero-line .right .pkv { font-family: 'JetBrains Mono', monospace; font-size: 14px; color: var(--fg); margin-top: 4px; }
.method-band .band-head { display:flex; justify-content:space-between; font-size:9px; letter-spacing:2px; color:var(--accent); font-weight:700; margin-bottom:6px; padding-bottom:5px; border-bottom:1px solid var(--line); }
.method-band .band-head .band-sub { color: var(--dim); font-weight: 500; letter-spacing: 1px; }
.method-band .band-cap { font-size: 9.5px; color: var(--dim); margin-top: 6px; line-height: 1.4; }
.method-band .dt td { padding: 3px 6px; font-size: 10px; }
.r { opacity: 0; transform: translateY(8px); transition: opacity 0.6s ease, transform 0.6s ease; }
.r.in { opacity: 1; transform: translateY(0); }
.foot { text-align: center; padding: 24px 16px; color: var(--dim); font-size: 10px; letter-spacing: 2px; border-top: 1px solid var(--line); margin-top: 40px; }
.cube-net { position: relative; width: 100%; aspect-ratio: 4/3; background: var(--bg3); border-radius: 6px; padding: 8px; }
.cube-net svg { width: 100%; height: 100%; display: block; }
.cube-cell text { font-family: 'JetBrains Mono', monospace; }
.cube-cell.risky rect.cell-frame { stroke: var(--crit); stroke-width: 1.5; animation: pulse-stroke 1.6s infinite; }
@keyframes pulse-stroke { 0%, 100% { stroke-opacity: 1; } 50% { stroke-opacity: 0.3; } }
.pulse-dot { animation: pulse-dot 1.5s infinite; }
@keyframes pulse-dot { 0%, 100% { r: 3; opacity: 1; } 50% { r: 6; opacity: 0.4; } }
.ctlbar { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; padding: 10px 14px; background: var(--bg2); border: 1px solid var(--line); border-radius: 8px; margin-bottom: 14px; }
.ctlbar .grp { display: flex; gap: 4px; align-items: center; }
.ctlbar .lbl { font-size: 9px; letter-spacing: 2px; color: var(--dim); font-weight: 700; margin-right: 4px; }
.ctlbar .btn { background: var(--bg3); color: var(--fg2); border: 1px solid var(--line2); padding: 4px 10px; font-size: 11px; border-radius: 3px; cursor: pointer; font-family: 'JetBrains Mono', monospace; letter-spacing: 1px; transition: all 0.15s; }
.ctlbar .btn:hover { background: var(--bg4); color: var(--fg); }
.ctlbar .btn.active { background: var(--accent); color: var(--bg); border-color: var(--accent); }
.ctlbar input[type=text] { background: var(--bg3); color: var(--fg); border: 1px solid var(--line2); padding: 4px 10px; font-size: 11px; border-radius: 3px; font-family: 'JetBrains Mono', monospace; width: 180px; }
.mini-xy-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
.mini-xy { background: var(--bg3); border: 1px solid var(--line); border-radius: 4px; padding: 4px 4px 3px; cursor: pointer; transition: border-color 0.2s; }
.mini-xy:hover { border-color: var(--accent); }
.mini-xy.dim { opacity: 0.35; }
.mini-xy .mlabel { display: flex; justify-content: space-between; font-size: 9px; font-weight: 600; color: var(--fg2); margin-bottom: 2px; line-height: 1.2; }
.mini-xy .mlabel .mid { color: var(--accent); }
.mini-xy .mlabel .mval { color: var(--num); font-family: 'JetBrains Mono', monospace; }
.mini-xy svg { width: 100%; height: 80px; display: block; }
.mini-xy .mfoot { display: flex; justify-content: space-between; font-size: 8.5px; color: var(--dim); font-family: 'JetBrains Mono', monospace; margin-top: 2px; padding-top: 2px; border-top: 1px solid var(--line); }
.imatrix { width: 100%; border-collapse: collapse; font-size: 10px; }
.imatrix th, .imatrix td { padding: 2px 4px; text-align: center; font-family: 'JetBrains Mono', monospace; }
.imatrix th.tl { text-align: left; }
.imatrix td.cell { width: 18px; height: 18px; border-radius: 2px; }
.imatrix tr:hover td { background: rgba(77, 214, 255, 0.04); }
.verdict-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.verdict-cell { padding: 12px 16px; background: var(--bg2); border-left: 3px solid var(--dim); border-radius: 4px; }
.verdict-cell.crit { border-left-color: var(--crit); }
.verdict-cell.warn { border-left-color: var(--warn); }
.verdict-cell.safe { border-left-color: var(--good); }
.verdict-cell .vl { font-size: 9px; color: var(--dim); letter-spacing: 3px; font-weight: 700; }
.verdict-cell .vn { font-size: 24px; font-weight: 700; margin-top: 2px; font-family: 'JetBrains Mono', monospace; }
.verdict-cell.crit .vn { color: var(--crit); }
.verdict-cell.warn .vn { color: var(--warn); }
.verdict-cell.safe .vn { color: var(--good); }
.verdict-cell .vd { font-size: 10px; color: var(--fg2); margin-top: 4px; line-height: 1.4; }
.ts-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; }
.ts-mini { background: var(--bg3); border: 1px solid var(--line); border-radius: 4px; padding: 6px 8px; }
.ts-mini .tlabel { display: flex; justify-content: space-between; font-size: 9px; color: var(--fg2); margin-bottom: 3px; }
.ts-mini svg { width: 100%; height: 64px; display: block; }
.eg-wrap { position: relative; background: var(--bg3); border-radius: 4px; height: 420px; overflow: hidden; }
.eg-wrap canvas { display: block; width: 100%; height: 100%; cursor: crosshair; }
.eg-side { position: absolute; right: 8px; top: 8px; width: 200px; padding: 8px 10px; background: rgba(17,20,31,0.92); border: 1px solid var(--line); border-radius: 4px; font-size: 10px; pointer-events: none; line-height: 1.5; display: none; }
.eg-side.show { display: block; }
.eg-side .ttl { color: var(--accent); font-weight: 700; font-size: 10px; letter-spacing: 1px; margin-bottom: 4px; }
.eg-side .row { display: flex; justify-content: space-between; color: var(--fg2); }
.eg-side .row b { color: var(--fg); font-family: 'JetBrains Mono', monospace; }
.scrub { display: flex; gap: 10px; align-items: center; padding: 8px 10px; background: var(--bg3); border-radius: 4px; margin-top: 8px; }
.scrub input[type=range] { flex: 1; accent-color: var(--accent); }
.scrub .btn { background: var(--bg4); color: var(--fg); border: 1px solid var(--line2); padding: 3px 10px; font-size: 11px; border-radius: 3px; cursor: pointer; font-family: 'JetBrains Mono', monospace; }
.scrub .btn:hover { background: var(--bg2); }
.scrub .tlabel { font-size: 10px; color: var(--dim); font-family: 'JetBrains Mono', monospace; min-width: 90px; text-align: right; }
.scrub .tlabel b { color: var(--accent); }
.sankey-row { display: grid; grid-template-columns: 110px 1fr 110px 60px; gap: 8px; align-items: center; padding: 3px 0; border-bottom: 1px solid var(--line); font-size: 10px; }
.sankey-row .src { color: var(--fg); font-weight: 600; text-align: right; font-family: 'JetBrains Mono', monospace; }
.sankey-row .dst { color: var(--accent); font-family: 'JetBrains Mono', monospace; }
.sankey-row .val { color: var(--num); text-align: right; font-family: 'JetBrains Mono', monospace; }
.sankey-row .bar { height: 12px; background: linear-gradient(90deg, var(--tag), var(--accent)); border-radius: 2px; }
.tfh { display: grid; gap: 1px; }
.tfh-row { display: grid; grid-template-columns: 140px repeat(21, 1fr); gap: 1px; align-items: center; font-size: 9px; height: 16px; }
.tfh-row .lab { color: var(--fg2); padding-right: 6px; text-align: right; font-family: 'JetBrains Mono', monospace; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tfh-row .cell { background: var(--bg4); border-radius: 1px; height: 14px; }
.tfh-head { display: grid; grid-template-columns: 140px repeat(21, 1fr); gap: 1px; font-size: 8px; color: var(--dim); padding-right: 6px; }
.tfh-head .h0 { text-align: right; padding-right: 6px; }
.tfh-head .ht { text-align: center; }
.cons-box { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 6px; }
.cons-cell { background: var(--bg3); padding: 8px 10px; border-radius: 4px; border-left: 2px solid var(--tag); }
.cons-cell.warn { border-left-color: var(--crit); }
.cons-cell .v { font-family: 'JetBrains Mono', monospace; font-size: 16px; font-weight: 700; color: var(--fg); }
.cons-cell .l { font-size: 9px; color: var(--dim); letter-spacing: 2px; text-transform: uppercase; margin-top: 2px; }
.cons-bar { margin-top: 8px; height: 8px; background: var(--bg4); border-radius: 4px; overflow: hidden; display: flex; }
.cons-bar .seg { height: 100%; }
.cons-banner { margin-top: 8px; padding: 6px 10px; background: rgba(255, 56, 84, 0.1); border-left: 2px solid var(--crit); font-size: 10px; color: var(--crit); border-radius: 3px; display: none; }
.cons-banner.on { display: block; }
.face-big { background: var(--bg3); border-radius: 4px; padding: 8px; }
.face-big svg { width: 100%; display: block; }
.face-big-foot { display: flex; justify-content: space-between; font-size: 10px; color: var(--dim); margin-top: 6px; padding-top: 6px; border-top: 1px solid var(--line); font-family: 'JetBrains Mono', monospace; }
.compare-grid { display: grid; gap: 4px; }
.compare-cell { background: var(--bg3); border: 1px solid var(--line); border-radius: 3px; padding: 3px; }
.compare-cell svg { width: 100%; height: 70px; display: block; }
.compare-cell .cclbl { font-size: 8.5px; color: var(--fg2); font-family: 'JetBrains Mono', monospace; text-align: center; }
@media (max-width: 1280px) {
  .col-3, .col-4, .col-5, .col-6, .col-7, .col-8, .col-9 { grid-column: span 12; }
  .mini-xy-grid { grid-template-columns: repeat(2, 1fr); }
  .ts-grid { grid-template-columns: repeat(2, 1fr); }
  .topbar { padding: 10px 16px; }
  .page { padding: 20px 16px; }
}

/* ---------- Bi-Face Split (Page 1) ---------- */
.biface-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
@media (max-width: 980px) { .biface-grid { grid-template-columns: 1fr; } }
.biface-cell { background: var(--bg3); border: 1px solid var(--line); border-radius: 6px; padding: 10px 12px 8px; cursor: pointer; transition: border-color 0.15s, box-shadow 0.15s; }
.biface-cell:hover { border-color: var(--accent); box-shadow: 0 0 0 1px rgba(77,214,255,0.25) inset; }
.biface-cell .bf-head { display: flex; justify-content: space-between; align-items: baseline; padding-bottom: 6px; border-bottom: 1px solid var(--line); margin-bottom: 6px; }
.biface-cell .bf-name { font-family: 'JetBrains Mono', monospace; font-size: 12px; color: var(--accent); letter-spacing: 1px; font-weight: 700; }
.biface-cell .bf-sub { font-size: 9px; color: var(--dim); letter-spacing: 2px; }
.biface-cell svg { width: 100%; display: block; aspect-ratio: 5/3; }
.biface-cell .bf-foot { display: flex; justify-content: space-between; font-size: 10px; color: var(--fg2); padding-top: 6px; margin-top: 4px; border-top: 1px solid var(--line); font-family: 'JetBrains Mono', monospace; }
.biface-cell .bf-foot b { color: var(--crit); }

/* ---------- Impact Inspector (Page 2) ---------- */
.ii-wrap { display: grid; grid-template-columns: 1fr 320px; gap: 14px; }
@media (max-width: 1100px) { .ii-wrap { grid-template-columns: 1fr; } }
.ii-main { background: var(--bg2); border: 1px solid var(--line); border-radius: 8px; padding: 14px 16px; }
.ii-side { background: var(--bg2); border: 1px solid var(--line); border-radius: 8px; padding: 12px 14px; display: flex; flex-direction: column; gap: 12px; max-height: 660px; overflow-y: auto; }
.ii-canvas-wrap { position: relative; background: #0e1320; border-radius: 6px; padding: 4px; }
.ii-canvas-wrap svg { width: 100%; display: block; aspect-ratio: 4/3; cursor: crosshair; }
.ii-cbar { display: flex; align-items: center; gap: 8px; margin-top: 8px; font-size: 10px; color: var(--dim); font-family: 'JetBrains Mono', monospace; }
.ii-cbar .grad { flex: 1; height: 10px; border-radius: 2px;
  background: linear-gradient(90deg, rgb(68,1,84) 0%, rgb(59,82,139) 20%, rgb(33,144,141) 40%, rgb(93,201,99) 60%, rgb(253,231,37) 80%, rgb(253,80,60) 100%); }
.ii-side .iibox { background: var(--bg3); border: 1px solid var(--line); border-radius: 4px; padding: 8px 10px; }
.ii-side .iibox .iihd { font-size: 9px; color: var(--accent); letter-spacing: 2px; font-weight: 700; margin-bottom: 4px; }
.ii-side .iirow { display: flex; justify-content: space-between; font-size: 11px; color: var(--fg2); margin-top: 2px; }
.ii-side .iirow b { color: var(--fg); font-family: 'JetBrains Mono', monospace; }
.ii-bar-row { display: grid; grid-template-columns: 90px 1fr 50px; gap: 6px; align-items: center; font-size: 10px; padding: 2px 0; cursor: pointer; border-radius: 3px; }
.ii-bar-row:hover { background: rgba(77,214,255,0.08); }
.ii-bar-row.is-max b { color: var(--crit); }
.ii-bar-row .nm { color: var(--fg2); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-family: 'JetBrains Mono', monospace; }
.ii-bar-row .bw { background: var(--bg4); border-radius: 2px; height: 8px; overflow: hidden; }
.ii-bar-row .bw .fl { display: block; height: 100%; border-radius: 2px; }
.ii-bar-row .vl { text-align: right; color: var(--num); font-family: 'JetBrains Mono', monospace; }
.ii-th { width: 100%; height: 70px; display: block; }
.ii-empty { color: var(--dim); font-size: 10px; padding: 6px 2px; font-style: italic; }
.ii-pin { display: inline-flex; align-items: center; gap: 4px; cursor: pointer; user-select: none; font-size: 10px; color: var(--fg2); letter-spacing: 1px; }
.ii-pin input { accent-color: var(--accent); }
.ii-pin.locked { color: var(--accent2); }
.ii-thresh { display: flex; align-items: center; gap: 8px; }
.ii-thresh input[type=range] { flex: 1; accent-color: var(--accent); min-width: 100px; }
.ii-thresh .vlab { font-size: 10px; color: var(--num); font-family: 'JetBrains Mono', monospace; min-width: 60px; text-align: right; }

@keyframes ii-pulse {
  0%   { r: 6;  opacity: 0.9; }
  100% { r: 14; opacity: 0;   }
}
.ii-halo { animation: ii-pulse 1.1s linear infinite; }

/* ---------- Trajectory viz family (6 new panels) ---------- */
.bvm-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
@media (max-width: 980px) { .bvm-grid { grid-template-columns: 1fr; } }
.bvm-cell { background: var(--bg3); border: 1px solid var(--line); border-radius: 6px; padding: 10px 12px 8px; }
.bvm-cell .bf-head { display: flex; justify-content: space-between; align-items: baseline; padding-bottom: 6px; border-bottom: 1px solid var(--line); margin-bottom: 6px; }
.bvm-cell .bf-name { font-family: 'JetBrains Mono', monospace; font-size: 12px; color: var(--accent); letter-spacing: 1px; font-weight: 700; }
.bvm-cell .bf-sub { font-size: 9px; color: var(--dim); letter-spacing: 2px; }
.bvm-cell svg { width: 100%; aspect-ratio: 5/3; display: block; }
.bvm-legend { display: flex; gap: 14px; flex-wrap: wrap; font-size: 10px; padding-top: 6px; margin-top: 4px; border-top: 1px solid var(--line); font-family: 'JetBrains Mono', monospace; }
.bvm-legend .lg { display: inline-flex; gap: 5px; align-items: center; color: var(--fg2); }
.bvm-legend .lg .sw { width: 10px; height: 10px; border-radius: 2px; display: inline-block; }
.bvm-legend .lg b { color: var(--fg); }

.tcm-archetypes { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-top: 10px; }
@media (max-width: 980px) { .tcm-archetypes { grid-template-columns: repeat(2, 1fr); } }
.tcm-arch { background: var(--bg3); border: 1px solid var(--line); border-radius: 4px; padding: 8px 10px; }
.tcm-arch .ah { display: flex; justify-content: space-between; align-items: baseline; }
.tcm-arch .ah .nm { font-family: 'JetBrains Mono', monospace; font-size: 10px; font-weight: 700; }
.tcm-arch .ah .ct { font-size: 9px; color: var(--dim); font-family: 'JetBrains Mono', monospace; }
.tcm-arch svg { width: 100%; height: 36px; display: block; margin-top: 4px; }

.phase-wrap { position: relative; }
.phase-wrap svg { width: 100%; height: 380px; display: block; background: var(--bg3); border-radius: 4px; }

.cseq-grid { display: grid; grid-template-columns: 110px 1fr; gap: 8px 4px; font-size: 10px; align-items: center; }
.cseq-grid .lab { color: var(--fg2); font-family: 'JetBrains Mono', monospace; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.cseq-row { display: grid; grid-template-columns: repeat(21, 1fr); gap: 1px; }
.cseq-cell { height: 14px; background: var(--bg4); border-radius: 1px; }

.tb3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
@media (max-width: 980px) { .tb3 { grid-template-columns: 1fr; } }
.tb3-cell { background: var(--bg3); border: 1px solid var(--line); border-radius: 4px; padding: 6px 8px; }
.tb3-cell .h { display: flex; justify-content: space-between; font-size: 10px; color: var(--accent); font-family: 'JetBrains Mono', monospace; letter-spacing: 1px; padding-bottom: 4px; border-bottom: 1px solid var(--line); margin-bottom: 4px; }
.tb3-cell svg { width: 100%; height: 220px; display: block; }

.bbadge { display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 9px; font-weight: 700; letter-spacing: 1px; font-family: 'JetBrains Mono', monospace; color: var(--bg); margin-left: 6px; }
.bbadge.bounce { background: var(--good); }
.bbadge.rebound { background: var(--warn); }
/* slide previously collided with rebound on orange — use the lateral-motion
   purple accent so they are visually distinct. Kept the JS palette in sync
   via DOE_BEHAVIOR_COLOR = BEHAVIOR_COLOR. */
.bbadge.slide { background: #b46eff; color: #fff; }
.bbadge.embed { background: var(--crit); color: #fff; }
.bbadge.unknown { background: var(--dim); }

.traj-na { color: var(--dim); font-size: 10px; padding: 8px 4px; text-align: center; font-style: italic; }

/* ---------- DOE Analysis (Section 05) ---------- */
.doe-row { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr); gap: 14px; }
@media (max-width: 1100px) { .doe-row { grid-template-columns: 1fr; } }
.doe-grid-wrap { background: var(--bg3); border-radius: 6px; padding: 10px 12px; }
.doe-grid-wrap svg { width: 100%; display: block; aspect-ratio: var(--device-aspect, 1); }
.doe-cell-label { font-family: 'JetBrains Mono', monospace; pointer-events: none; }
.doe-cell rect { cursor: pointer; transition: stroke-width 0.1s; }
.doe-cell.active rect { stroke: var(--accent); stroke-width: 2; }
.doe-rank { max-height: 520px; overflow-y: auto; }
.doe-rank table { width: 100%; }
.doe-pp-matrix-wrap { background: var(--bg3); border-radius: 6px; padding: 10px 12px; overflow-x: auto; }
.doe-pp-matrix-wrap svg { display: block; min-width: 100%; }
.doe-traj-mm { display: grid; gap: 4px; }
.doe-traj-cell { background: var(--bg3); border: 1px solid var(--line); border-radius: 3px; padding: 3px 4px; position: relative; }
.doe-traj-cell svg { width: 100%; height: 56px; display: block; }
.doe-traj-cell .tc-lbl { font-size: 8px; color: var(--fg2); font-family: 'JetBrains Mono', monospace; display: flex; justify-content: space-between; }
.doe-traj-cell.worst { border-color: var(--crit); box-shadow: 0 0 0 1px rgba(255,56,84,0.4) inset; }
.doe-traj-cell .star { position: absolute; right: 3px; top: 1px; font-size: 11px; color: var(--crit); }
.doe-env-wrap { background: var(--bg3); border-radius: 6px; padding: 10px 12px; }
.doe-env-row { display: grid; grid-template-columns: 130px 1fr 56px; gap: 8px; align-items: center; padding: 3px 0; border-bottom: 1px solid var(--line); font-size: 10px; }
.doe-env-row:last-child { border-bottom: none; }
.doe-env-row .nm { font-family: 'JetBrains Mono', monospace; color: var(--fg); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.doe-env-row .wis svg { width: 100%; height: 14px; display: block; }
.doe-env-row .rt { font-family: 'JetBrains Mono', monospace; color: var(--num); text-align: right; }
.doe-empty { color: var(--dim); padding: 24px 12px; font-size: 12px; text-align: center; font-style: italic; }
.doe-kpi-bb { display: inline-flex; gap: 2px; margin-top: 2px; }
.doe-kpi-bb span { display: inline-block; height: 8px; border-radius: 1px; }
.doe-failrisk-wrap{display:grid;grid-template-columns:minmax(280px, 1fr) minmax(360px, 1.2fr);gap:18px;padding:10px 4px 4px 4px;}
.doe-failrisk-left,.doe-failrisk-right{display:flex;flex-direction:column;gap:8px;min-width:0;}
.doe-failrisk-subhead{font-size:12px;color:var(--fg2);letter-spacing:.04em;text-transform:uppercase;}
.doe-failrisk-grid{display:grid;gap:4px;aspect-ratio:var(--device-aspect, 1);background:var(--bg3);padding:4px;border-radius:4px;}
.doe-failrisk-cell{display:flex;flex-direction:column;justify-content:center;align-items:center;border-radius:3px;color:#0b0b0b;font-weight:600;padding:2px;min-height:0;line-height:1.05;}
.doe-failrisk-cell.doe-failrisk-empty{background:transparent;color:var(--dim);font-weight:400;}
.doe-failrisk-cell.doe-failrisk-nodata{background:var(--bg2);color:var(--dim);font-weight:400;}
.doe-failrisk-pid{font-size:10px;opacity:.85;}
.doe-failrisk-sfval{font-size:11px;font-weight:700;}
.doe-failrisk-legend{display:flex;flex-wrap:wrap;gap:8px;font-size:11px;color:var(--fg2);margin-top:4px;}
.doe-failrisk-lg{padding:2px 6px;border-radius:3px;color:#0b0b0b;font-weight:600;}
.doe-failrisk-lg.crit{background:var(--crit);}
.doe-failrisk-lg.warn{background:var(--warn);}
.doe-failrisk-lg.good{background:var(--good);}
.doe-failrisk-list{display:flex;flex-direction:column;gap:4px;}
.doe-failrisk-item{display:grid;grid-template-columns:18px 10px 1fr auto;gap:8px;align-items:center;padding:6px 8px;background:var(--bg2);border:1px solid var(--line);border-radius:4px;}
.doe-failrisk-rank{font-size:11px;color:var(--dim);text-align:right;}
.doe-failrisk-dot{display:inline-block;width:10px;height:10px;border-radius:50%;}
.doe-failrisk-name{min-width:0;}
.doe-failrisk-pname{font-size:12px;color:var(--fg);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.doe-failrisk-pmeta{font-size:10px;color:var(--dim);}
.doe-failrisk-sf{display:flex;flex-direction:column;align-items:flex-end;gap:2px;}
.doe-failrisk-sfbig{font-size:12px;font-weight:700;letter-spacing:.02em;}
.doe-failrisk-whisker{display:block;}
.doe-failrisk-foot{font-size:11px;color:var(--dim);padding:6px 4px 0 4px;}
@media (max-width: 760px){.doe-failrisk-wrap{grid-template-columns:1fr;}}

.doe-corr-host { padding: 6px 2px 2px 2px; }
.doe-corr-wrap text { font-family: ui-sans-serif, -apple-system, "Segoe UI", sans-serif; }
@media (max-width: 1100px) {
  .doe-corr-wrap { grid-template-columns: 1fr !important; }
}
.doe-corr-clusters > div[style*="border-left"]:hover {
  background: rgba(255,255,255,0.03) !important;
  transition: background 120ms ease;
}

.doe-toa-root { display:flex; flex-direction:column; gap:10px; padding:6px 2px 2px; }
.doe-toa-empty { color: var(--dim, #5c6383); font-size: 11px; padding: 12px; text-align:center; }
.toa-tagline { display:flex; gap:14px; flex-wrap:wrap; font-size:11px; padding:0 4px; }
.toa-tag { padding:3px 8px; border-radius:3px; background:rgba(255,255,255,0.04); border:1px solid var(--line, #2a2f45); }
.toa-tag-e { color: var(--good, #4adfa1); }
.toa-tag-l { color: var(--warn, #f0a830); }
.toa-grid { display:grid; grid-template-columns: 1.4fr 1fr; gap:14px; }
@media (max-width: 980px) { .toa-grid { grid-template-columns: 1fr; } }
.toa-sec-h { display:flex; align-items:baseline; gap:8px; margin: 4px 4px 6px; }
.toa-sec-t { font-size:11px; font-weight:600; letter-spacing:.04em; color: var(--fg, #e6e8f0); text-transform:uppercase; }
.toa-sec-d { font-size:10px; color: var(--dim, #5c6383); }
.toa-sw { display:inline-block; width:9px; height:9px; border-radius:2px; vertical-align:middle; }
.toa-left, .toa-right { background: var(--bg2, #131725); border:1px solid var(--line, #2a2f45); border-radius:4px; padding:8px 10px; }
.toa-right { display:flex; flex-direction:column; gap:10px; }
.toa-strip { display:flex; flex-direction:column; gap:4px; padding:4px 2px; }
.toa-bar-row { display:grid; grid-template-columns: 140px 1fr 80px; gap:8px; align-items:center; font-size:11px; }
.toa-bar-name { color: var(--fg2, #aab2cf); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.toa-bar-track { position:relative; height:14px; background: rgba(255,255,255,0.04); border-radius:2px; overflow:hidden; }
.toa-bar-fill { height:100%; border-radius:2px; }
.toa-bar-val { font-variant-numeric: tabular-nums; color: var(--fg, #e6e8f0); text-align:right; }
.toa-axis { display:flex; justify-content:space-between; font-size:10px; color: var(--dim, #5c6383); padding: 6px 4px 2px; border-top:1px solid var(--line, #2a2f45); margin-top:4px; }
.toa-axis-mid { color: var(--fg2, #aab2cf); }
.toa-listbox { display:flex; flex-direction:column; gap:4px; }
.toa-list { display:flex; flex-direction:column; gap:3px; }
.toa-li { display:grid; grid-template-columns: 1fr auto; gap:8px; align-items:baseline; font-size:11px; padding:3px 4px; border-radius:2px; background: rgba(255,255,255,0.02); }
.toa-li-name { color: var(--fg2, #aab2cf); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.toa-li-stat { font-variant-numeric: tabular-nums; }
.toa-li-mean { color: var(--fg, #e6e8f0); font-weight:600; }
.toa-li-std { color: var(--dim, #5c6383); }
.toa-li-n { color: var(--dim, #5c6383); font-size:10px; }

#idw-pred-svg { width:100%; height:auto; max-height:560px; display:block; }
#idw-pred-canvas { max-height:560px; }
#idw-pred-stack { max-height:560px; }
#idw-pred-panel .ctlbar { padding:6px 10px; }
#idw-pred-info b { color: var(--fg); }

.pareto-host { width: 100%; min-height: 460px; }
.pareto-host svg text { font-family: inherit; }
.pareto-tip b { color: var(--accent); }
.pareto-legend span { white-space: nowrap; }

/* Energy Partition (Section 5 advanced) */
.doe-ep-summary {
  display: flex; flex-wrap: wrap; gap: 8px;
  padding: 8px 4px 14px 4px;
  border-bottom: 1px dashed var(--line);
  margin-bottom: 10px;
}
.doe-ep-list {
  display: flex; flex-direction: column; gap: 4px;
  max-height: 560px; overflow-y: auto;
  padding-right: 4px;
}
.doe-ep-row {
  display: grid;
  grid-template-columns: 90px 1fr 170px;
  align-items: center;
  gap: 10px;
  padding: 5px 8px;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.12s;
}
.doe-ep-row:hover { background: rgba(255,255,255,0.04); }
.doe-ep-lbl {
  display: inline-flex; align-items: center; gap: 6px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px; color: var(--fg);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.doe-ep-dot {
  display: inline-block; width: 8px; height: 8px; border-radius: 50%;
  flex-shrink: 0;
}
.doe-ep-bar {
  display: flex; height: 18px; width: 100%;
  background: var(--bg3); border-radius: 3px; overflow: hidden;
  border: 1px solid var(--line);
}
.doe-ep-seg {
  display: flex; align-items: center; justify-content: center;
  height: 100%; min-width: 0;
  transition: filter 0.15s;
}
.doe-ep-row:hover .doe-ep-seg { filter: brightness(1.15); }
.doe-ep-abs { background: linear-gradient(90deg, #2c8c5d, #4adfa1); }
.doe-ep-ret { background: linear-gradient(90deg, #2563a8, #4dd6ff); }
.doe-ep-seg-lbl {
  font-family: 'JetBrains Mono', monospace;
  font-size: 9px; font-weight: 700;
  color: rgba(10,12,20,0.9);
  letter-spacing: 0.3px;
}
.doe-ep-right {
  display: flex; justify-content: flex-end; align-items: baseline;
  gap: 10px; font-family: 'JetBrains Mono', monospace;
}
.doe-ep-pct {
  font-size: 12px; font-weight: 700; color: var(--good);
}
.doe-ep-ke {
  font-size: 10px; color: var(--dim);
}
@media (max-width: 900px) {
  .doe-ep-row { grid-template-columns: 70px 1fr 110px; gap: 6px; }
  .doe-ep-ke { display: none; }
}

/* ADV_CSS_INSERT_HERE */

#deep-fft-panel .panel-header { display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; }
#deep-fft-panel .deep-fft-meta { display:flex; gap:6px; flex-wrap:wrap; }
#deep-fft-panel .deep-fft-pill {
  font-size:11px; padding:2px 8px; border-radius:10px;
  background:#1a1d24; color:#cfd6e4; border:1px solid #2a2f3a;
}
#deep-fft-panel .deep-fft-body {
  display:grid; grid-template-columns:repeat(auto-fill, minmax(210px, 1fr));
  gap:10px;
}
#deep-fft-panel .deep-fft-card {
  background:#15171c; border:1px solid #23262d; border-radius:6px;
  padding:8px; display:flex; flex-direction:column; gap:4px;
}
#deep-fft-panel .deep-fft-card-head {
  display:flex; justify-content:space-between; align-items:baseline; gap:6px;
}
#deep-fft-panel .deep-fft-name {
  font-size:12px; color:#e6ecf5; font-weight:600;
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
  max-width:150px;
}
#deep-fft-panel .deep-fft-pid {
  font-size:10px; color:#8892a0; font-family:monospace;
}
#deep-fft-panel .deep-fft-svg { display:block; width:100%; height:40px; }
#deep-fft-panel .deep-fft-text {
  display:flex; justify-content:space-between; align-items:baseline;
  font-size:11px; color:#b8c0cf;
}
#deep-fft-panel .deep-fft-fdom { color:#7ad7ff; font-family:monospace; }
#deep-fft-panel .deep-fft-n { color:#8892a0; font-family:monospace; }
#deep-fft-panel .deep-empty {
  padding:24px; text-align:center; color:#8892a0; font-size:13px;
}

.deep-srs-panel .srs-body { width: 100%; }
.deep-srs-panel .srs-chart { display: block; margin: 4px 0 8px 0; background: transparent; }
.deep-srs-panel .srs-meta { color: #9aa7b8; font-size: 11px; margin: 6px 2px 2px 2px; }
.deep-srs-panel .srs-caption { color: #cfd6e0; font-size: 12px; margin: 2px 2px 0 2px; }
.deep-srs-panel .empty-note { color: #9aa7b8; font-size: 12px; padding: 24px; text-align: center; border: 1px dashed #2a3340; border-radius: 4px; }
#deep-safe-drop-zone-panel .panel-header { padding: 14px 16px 4px; }
#deep-safe-drop-zone-panel .panel-header h3 { margin: 0; font-size: 15px; color: #e6ebf0; }
#deep-safe-drop-zone-panel .panel-sub { font-size: 11px; color: #8a96a3; margin-top: 4px; }
#deep-safe-drop-zone-panel .kpi-box { transition: transform 0.15s; }
#deep-safe-drop-zone-panel .kpi-box:hover { transform: translateX(2px); }

#deep-pca-modal-panel .pca-summary{
  font-size:12.5px; color:#cbd5e1; margin-bottom:10px;
  display:flex; flex-wrap:wrap; align-items:center; gap:2px;
}
#deep-pca-modal-panel .pca-summary .sep{opacity:.55;}
#deep-pca-modal-panel .pca-mode-row{
  border:1px solid #233040; border-radius:8px;
  padding:10px 12px; margin-bottom:10px; background:rgba(20,28,38,0.45);
}
#deep-pca-modal-panel .pca-mode-head{
  display:grid; grid-template-columns: 90px 130px 1fr;
  align-items:center; gap:10px; margin-bottom:8px;
}
#deep-pca-modal-panel .pca-mode-title{font-weight:600; color:#e2e8f0; font-size:13.5px;}
#deep-pca-modal-panel .pca-mode-evr{font-size:12px; color:#94a3b8;}
#deep-pca-modal-panel .pca-mode-bar-track{
  height:8px; background:#1c2530; border-radius:4px; overflow:hidden;
}
#deep-pca-modal-panel .pca-mode-bar-fill{
  height:100%; background:linear-gradient(90deg,#3b82f6,#22d3ee);
}
#deep-pca-modal-panel .pca-mode-body{
  display:grid; grid-template-columns: 1fr 260px; gap:14px;
}
@media (max-width: 900px){
  #deep-pca-modal-panel .pca-mode-body{grid-template-columns: 1fr;}
}
#deep-pca-modal-panel .pca-sub-title{
  font-size:12px; color:#94a3b8; margin-bottom:6px; letter-spacing:.02em;
}
#deep-pca-modal-panel .pca-loading-list{display:flex; flex-direction:column; gap:3px;}
#deep-pca-modal-panel .pca-load-item{
  display:grid; grid-template-columns: 140px 1fr 52px;
  align-items:center; gap:6px; font-size:11.5px;
}
#deep-pca-modal-panel .pca-load-label{
  color:#cbd5e1; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
}
#deep-pca-modal-panel .pca-load-bar-wrap{
  position:relative; height:14px; background:#141b24; border-radius:3px;
}
#deep-pca-modal-panel .pca-load-axis{
  position:absolute; left:50%; top:0; bottom:0; width:1px; background:#3a4a5e;
}
#deep-pca-modal-panel .pca-load-bar{
  position:absolute; top:2px; bottom:2px; border-radius:2px;
}
#deep-pca-modal-panel .pca-load-bar.pos{background:#dc322f;}
#deep-pca-modal-panel .pca-load-bar.neg{background:#2166ac;}
#deep-pca-modal-panel .pca-load-val{text-align:right; font-variant-numeric:tabular-nums;}
#deep-pca-modal-panel .pca-load-val.pos{color:#fca5a5;}
#deep-pca-modal-panel .pca-load-val.neg{color:#93c5fd;}
#deep-pca-modal-panel .pca-spatial{display:flex; flex-direction:column; align-items:center;}
#deep-pca-modal-panel .pca-grid{display:block;}
#deep-pca-modal-panel .pca-legend{
  margin-top:6px; display:flex; align-items:center; gap:6px;
  font-size:10.5px; color:#94a3b8;
}
#deep-pca-modal-panel .pca-legend-bar{
  width:140px; height:8px; border-radius:2px;
  background:linear-gradient(90deg,#2166ac,#f5eee8,#dc322f);
}
#deep-pca-modal-panel .pca-caption{
  margin-top:8px; font-size:11.5px; color:#94a3b8; font-style:italic;
}
#deep-pca-modal-panel .empty-note{color:#94a3b8; font-style:italic; padding:8px 0;}
#deep-pca-modal-panel .empty-note.small{font-size:11px; padding:4px 0;}

.deep-anomaly-detection .anom-head{margin-bottom:10px;}
.deep-anomaly-detection .anom-summary{display:flex;flex-wrap:wrap;gap:14px;font-size:12px;color:#cfcfd6;}
.deep-anomaly-detection .anom-stat{padding:4px 10px;background:#23232a;border-radius:6px;border:1px solid #34343d;}
.deep-anomaly-detection .anom-facewrap{margin:8px 0;font-size:12px;color:#cfcfd6;}
.deep-anomaly-detection .anom-face-sel{margin-left:6px;background:#1d1d24;color:#eaeaf0;border:1px solid #3a3a44;padding:3px 6px;border-radius:4px;}
.deep-anomaly-detection .anom-body{display:grid;grid-template-columns:auto 1fr;gap:18px;align-items:start;}
.deep-anomaly-detection .anom-heatmap{display:block;}
.deep-anomaly-detection .anom-table{width:100%;border-collapse:collapse;font-size:12px;}
.deep-anomaly-detection .anom-table th,
.deep-anomaly-detection .anom-table td{padding:5px 8px;border-bottom:1px solid #2c2c34;text-align:center;}
.deep-anomaly-detection .anom-table th{background:#202028;color:#cfcfd6;font-weight:600;}
.deep-anomaly-detection .anom-table td.anom-zmax{color:#ff8a8a;font-weight:600;}
.deep-anomaly-detection .anom-table td.anom-driver{color:#ffd27f;}
.deep-anomaly-detection .anom-iqr-list{margin-top:12px;padding:8px 10px;background:#1e1e25;border:1px solid #2f2f38;border-radius:6px;font-size:12px;color:#dcdce4;}
.deep-anomaly-detection .anom-iqr-title{font-weight:600;color:#eaeaf0;margin-bottom:6px;}
.deep-anomaly-detection .anom-iqr-ul{margin:0;padding-left:14px;}
.deep-anomaly-detection .anom-iqr-ul li{margin:2px 0;}
.deep-anomaly-detection .anom-iqr-agree .anom-iqr-tag{color:#7fff9c;font-weight:600;}
.deep-anomaly-detection .anom-iqr-only{color:#9a9aa3;text-decoration:line-through;}
.deep-anomaly-detection .anom-iqr-only .anom-iqr-tag{color:#ffd27f;font-weight:600;text-decoration:none;}
.deep-anomaly-detection .anom-empty{color:#7a7a82;font-style:italic;}
.deep-anomaly-detection .anom-caption{margin-top:10px;font-size:11px;color:#9a9aa3;font-style:italic;}
.deep-anomaly-detection .empty{padding:18px;color:#7a7a82;text-align:center;font-style:italic;}

.ppd-caption { color: #aab2cf; font-size: 11px; margin-bottom: 8px; }
.ppd-layout {
  display: grid;
  grid-template-columns: 260px 1fr;
  gap: 12px;
  align-items: start;
}
.ppd-left {
  background: #0e1220;
  border: 1px solid #262d44;
  border-radius: 6px;
  padding: 6px;
  max-height: 720px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.ppd-left-head {
  font-size: 10px;
  color: #5c6383;
  padding: 4px 6px 6px 6px;
  border-bottom: 1px solid #262d44;
  margin-bottom: 4px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.ppd-list {
  overflow-y: auto;
  flex: 1;
  padding-right: 2px;
}
.ppd-list-row {
  display: grid;
  grid-template-columns: 1fr;
  gap: 2px;
  padding: 5px 6px;
  border-radius: 4px;
  cursor: pointer;
  border: 1px solid transparent;
  margin-bottom: 2px;
}
.ppd-list-row:hover { background: #1a1e2e; }
.ppd-list-row.active {
  background: #1a233e;
  border-color: #3b528b;
}
.ppd-list-name {
  color: #e0e4ff;
  font-size: 11px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.ppd-list-val {
  display: grid;
  grid-template-columns: 1fr 54px;
  align-items: center;
  gap: 6px;
}
.ppd-list-bar-bg {
  height: 6px;
  background: #1a1e2e;
  border-radius: 3px;
  overflow: hidden;
}
.ppd-list-bar { height: 100%; border-radius: 3px; transition: width 0.15s; }
.ppd-list-num {
  color: #aab2cf;
  font-size: 10px;
  font-variant-numeric: tabular-nums;
  text-align: right;
}
.ppd-right { display: flex; flex-direction: column; gap: 8px; }
.ppd-detail-title {
  color: #e0e4ff;
  font-size: 13px;
  padding: 4px 6px;
  background: #1a1e2e;
  border-radius: 4px;
  border-left: 3px solid #3b528b;
}
.ppd-kpi-strip {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 6px;
}
.ppd-kpi-tile {
  background: #0e1220;
  border: 1px solid #262d44;
  border-radius: 4px;
  padding: 6px 8px;
}
.ppd-kpi-label {
  font-size: 9px;
  color: #5c6383;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: 2px;
}
.ppd-kpi-val {
  font-size: 14px;
  color: #e0e4ff;
  font-variant-numeric: tabular-nums;
}
.ppd-kpi-unit { font-size: 9px; color: #5c6383; }
.ppd-grid2 {
  display: grid;
  grid-template-columns: 340px 1fr;
  gap: 8px;
}
.ppd-tile {
  background: #0e1220;
  border: 1px solid #262d44;
  border-radius: 6px;
  padding: 8px;
}
.ppd-tile-head {
  font-size: 10px;
  color: #5c6383;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: 6px;
}
.ppd-svg-square { width: 100%; height: 320px; display: block; }
.ppd-svg-wide   { width: 100%; height: 200px; display: block; }
.ppd-empty {
  color: #5c6383;
  font-size: 11px;
  text-align: center;
  padding: 16px;
}
@media (max-width: 1024px) {
  .ppd-layout { grid-template-columns: 1fr; }
  .ppd-grid2  { grid-template-columns: 1fr; }
  .ppd-kpi-strip { grid-template-columns: repeat(3, 1fr); }
}

/* DEEP_CSS_INSERT_HERE */

#insight-symmetry .sym-kpis{display:grid;grid-template-columns:repeat(4,minmax(140px,1fr));gap:10px;margin-bottom:10px}
#insight-symmetry .sym-kpi{background:#0f1623;border:1px solid #243245;border-radius:8px;padding:10px 12px}
#insight-symmetry .sym-kpi-lbl{font-size:11px;color:#8aa0bd;letter-spacing:.02em;margin-bottom:4px}
#insight-symmetry .sym-kpi-val{font-size:22px;font-weight:600;color:#e6eefc}
#insight-symmetry .sym-kpi-val-sm{font-size:15px}
#insight-symmetry .sym-kpi-suf{font-size:11px;color:#8aa0bd;font-weight:400;margin-left:3px}
#insight-symmetry .sym-kpi-meta{grid-column:span 1}
#insight-symmetry .sym-verdict{padding:8px 12px;border-radius:6px;font-size:13px;font-weight:500;margin-bottom:12px}
#insight-symmetry .sym-verdict.ok{background:#0f2a1d;border:1px solid #1f5a3d;color:#7fd4a3}
#insight-symmetry .sym-verdict.warn{background:#2a1a12;border:1px solid #6b3a1f;color:#f0a878}
#insight-symmetry .sym-tables{display:grid;grid-template-columns:1fr 1fr;gap:14px}
#insight-symmetry .sym-tblbox{background:#0c1320;border:1px solid #1f2c40;border-radius:8px;padding:10px}
#insight-symmetry .sym-tbl-title{font-size:13px;color:#cfd9ea;margin-bottom:6px;font-weight:600}
#insight-symmetry .sym-tbl-sub{font-size:11px;color:#7d8da8;font-weight:400;margin-left:6px}
#insight-symmetry .sym-tbl{width:100%;border-collapse:collapse;font-size:12px}
#insight-symmetry .sym-tbl th{text-align:right;color:#8aa0bd;font-weight:500;padding:4px 6px;border-bottom:1px solid #1f2c40}
#insight-symmetry .sym-tbl th:first-child{text-align:left}
#insight-symmetry .sym-tbl td{padding:4px 6px;border-bottom:1px solid #141d2c;color:#dde6f5}
#insight-symmetry .sym-tbl td.sym-pair{font-family:ui-monospace,Menlo,monospace;color:#a8c2ee}
#insight-symmetry .sym-tbl td.sym-num{text-align:right;font-variant-numeric:tabular-nums}
#insight-symmetry .sym-tbl td.sym-asym{font-weight:600}
#insight-symmetry .sym-tbl tr.mid td.sym-asym{color:#f0c878}
#insight-symmetry .sym-tbl tr.hi td.sym-asym{color:#f08878}
#insight-symmetry .sym-foot{margin-top:10px;font-size:11px;color:#7d8da8;line-height:1.5}
#insight-symmetry .ins-empty{color:#7d8da8;font-size:12px;padding:8px 0;text-align:center}
@media (max-width:900px){
  #insight-symmetry .sym-kpis{grid-template-columns:repeat(2,1fr)}
  #insight-symmetry .sym-tables{grid-template-columns:1fr}
}
#insight-DamageIndex .insight-title{font-weight:600;font-size:15px;margin-bottom:8px;color:#222;}
#insight-DamageIndex .di-caption{font-size:12px;color:#444;background:#fafafa;border-left:3px solid #b30000;padding:6px 10px;margin-bottom:10px;border-radius:2px;}
#insight-DamageIndex .di-wrap{display:flex;gap:18px;align-items:flex-start;flex-wrap:wrap;}
#insight-DamageIndex .di-left{flex:0 0 auto;}
#insight-DamageIndex .di-right{flex:1 1 280px;min-width:280px;}
#insight-DamageIndex .di-subtitle{font-size:13px;font-weight:600;color:#333;margin-bottom:6px;}
#insight-DamageIndex .di-svg{display:block;}
#insight-DamageIndex .di-label{font-size:11px;fill:#333;font-family:monospace;}
#insight-DamageIndex .di-value{font-size:11px;fill:#222;font-family:monospace;dominant-baseline:middle;}
#insight-DamageIndex .di-bar{cursor:default;}
#insight-DamageIndex .di-bar:hover{stroke:#000;stroke-width:1;}
#insight-DamageIndex .di-pair-list{list-style:none;padding:0;margin:0;}
#insight-DamageIndex .di-pair-list li{display:grid;grid-template-columns:24px 1fr 120px 50px;gap:6px;align-items:center;padding:4px 0;font-size:12px;border-bottom:1px solid #eee;}
#insight-DamageIndex .di-rank{font-weight:700;color:#b30000;text-align:center;}
#insight-DamageIndex .di-pair-name{font-family:monospace;color:#222;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
#insight-DamageIndex .di-pair-bar{background:#f6f6f6;border:1px solid #e5e5e5;height:12px;position:relative;border-radius:2px;overflow:hidden;}
#insight-DamageIndex .di-pair-fill{display:block;height:100%;}
#insight-DamageIndex .di-pair-val{font-family:monospace;font-size:11px;text-align:right;color:#222;}
#insight-DamageIndex .di-empty{padding:10px;color:#888;font-size:12px;font-style:italic;}
.rf-panel{padding:14px 16px;background:#161b22;border:1px solid #30363d;border-radius:8px;margin:12px 0;}
.rf-panel .insight-head h3{margin:0 0 4px 0;font-size:15px;color:#e6edf3;}
.rf-panel .insight-sub{margin:0 0 10px 0;font-size:12px;color:#8b949e;}
.rf-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:8px;margin-bottom:10px;}
.rf-kpi{background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:6px 10px;display:flex;flex-direction:column;}
.rf-kpi-lbl{font-size:11px;color:#8b949e;}
.rf-kpi-val{font-size:14px;color:#e6edf3;font-variant-numeric:tabular-nums;margin-top:2px;}
.rf-kpi-val.rf-up{color:#4493f8;}
.rf-kpi-val.rf-down{color:#f85149;}
.rf-svg-wrap{display:flex;justify-content:center;background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:8px;}
.rf-svg-wrap svg{max-width:520px;width:100%;height:auto;}
.rf-caption{margin:8px 0 0 0;font-size:11px;color:#8b949e;line-height:1.5;}
.insight-empty{padding:20px;color:#8b949e;text-align:center;font-size:12px;}
#insight-panel-auto-recommend .ar-summary {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
#insight-panel-auto-recommend .ar-chip {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
  background: #2a2f3a;
  color: #d0d5dd;
}
#insight-panel-auto-recommend .ar-chip-total    { background: #2a2f3a; color: #e6e8ec; }
#insight-panel-auto-recommend .ar-chip-critical { background: #4a1d1d; color: #ff8a8a; }
#insight-panel-auto-recommend .ar-chip-warning  { background: #4a3a14; color: #ffc266; }
#insight-panel-auto-recommend .ar-chip-info     { background: #1d3a4a; color: #80c8ff; }
#insight-panel-auto-recommend .ar-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 10px;
}
#insight-panel-auto-recommend .ar-card {
  display: flex;
  background: #1c2029;
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid #2a2f3a;
}
#insight-panel-auto-recommend .ar-stripe {
  width: 6px;
  flex-shrink: 0;
}
#insight-panel-auto-recommend .ar-critical .ar-stripe { background: #d94545; }
#insight-panel-auto-recommend .ar-warning  .ar-stripe { background: #f08a24; }
#insight-panel-auto-recommend .ar-info     .ar-stripe { background: #3a90d8; }
#insight-panel-auto-recommend .ar-main {
  padding: 10px 12px;
  flex: 1;
  min-width: 0;
}
#insight-panel-auto-recommend .ar-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
  flex-wrap: wrap;
}
#insight-panel-auto-recommend .ar-sev-tag {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 4px;
  letter-spacing: 0.5px;
}
#insight-panel-auto-recommend .ar-critical .ar-sev-tag { background: #d94545; color: #fff; }
#insight-panel-auto-recommend .ar-warning  .ar-sev-tag { background: #f08a24; color: #fff; }
#insight-panel-auto-recommend .ar-info     .ar-sev-tag { background: #3a90d8; color: #fff; }
#insight-panel-auto-recommend .ar-title {
  font-size: 13px;
  font-weight: 600;
  color: #e6e8ec;
  flex: 1;
  min-width: 0;
}
#insight-panel-auto-recommend .ar-metric {
  font-family: ui-monospace, Menlo, monospace;
  font-size: 12px;
  color: #b0b8c4;
  background: #252a35;
  padding: 2px 6px;
  border-radius: 3px;
}
#insight-panel-auto-recommend .ar-body {
  font-size: 12.5px;
  line-height: 1.5;
  color: #c0c5d0;
  margin-bottom: 8px;
}
#insight-panel-auto-recommend .ar-source {
  font-size: 11px;
  display: flex;
  align-items: center;
  gap: 6px;
}
#insight-panel-auto-recommend .ar-source-label { color: #8088a0; }
#insight-panel-auto-recommend .ar-source-tag {
  background: #2a2f3a;
  color: #9bb3d4;
  padding: 2px 8px;
  border-radius: 10px;
  border: 1px solid #354055;
}
#insight-panel-auto-recommend .insight-empty {
  color: #8088a0;
  font-style: italic;
  padding: 16px;
  text-align: center;
}

#insight-panel-ContactPulse .insight-header h3{margin:0;font-size:15px;color:#e8e8e8;}
#insight-panel-ContactPulse .insight-sub{font-size:11px;color:#888;margin-top:2px;}
#insight-panel-ContactPulse .insight-body{padding:8px 4px;}
#insight-panel-ContactPulse .ins-empty{color:#888;padding:18px;text-align:center;font-size:12px;}
#insight-panel-ContactPulse .cp-grid{display:grid;grid-template-columns:1fr 320px;gap:14px;align-items:start;}
#insight-panel-ContactPulse .cp-title{font-size:12px;color:#cfcfcf;margin-bottom:6px;font-weight:600;}
#insight-panel-ContactPulse .cp-heatmap-wrap, #insight-panel-ContactPulse .cp-hist-wrap{background:#161616;border:1px solid #2a2a2a;border-radius:4px;padding:8px;}
#insight-panel-ContactPulse .cp-hm-svg{display:block;}
#insight-panel-ContactPulse .cp-legend{margin-top:6px;}
#insight-panel-ContactPulse .cp-legend-bar{display:flex;height:8px;width:100%;border-radius:2px;overflow:hidden;}
#insight-panel-ContactPulse .cp-legend-bar span{flex:1;display:block;}
#insight-panel-ContactPulse .cp-legend-labels{display:flex;justify-content:space-between;font-size:10px;color:#999;margin-top:2px;}
#insight-panel-ContactPulse .cp-hist-svg{display:block;}
#insight-panel-ContactPulse .cp-stats{margin-top:8px;display:grid;grid-template-columns:1fr 1fr;gap:4px 12px;font-size:11px;color:#bbb;}
#insight-panel-ContactPulse .cp-stats span{color:#888;margin-right:4px;}
#insight-panel-ContactPulse .cp-stats b{color:#f0c674;font-weight:600;}
#insight-panel-ContactPulse .cp-rank-wrap{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:12px;}
#insight-panel-ContactPulse .cp-rank-col{background:#161616;border:1px solid #2a2a2a;border-radius:4px;padding:8px;}
#insight-panel-ContactPulse .cp-rank-tbl{width:100%;border-collapse:collapse;font-size:11px;color:#ccc;}
#insight-panel-ContactPulse .cp-rank-tbl th{text-align:left;border-bottom:1px solid #333;padding:3px 4px;color:#999;font-weight:500;}
#insight-panel-ContactPulse .cp-rank-tbl td{padding:3px 4px;border-bottom:1px solid #222;}
#insight-panel-ContactPulse .cp-rank-tbl tr:hover td{background:#1f1f1f;}
#insight-panel-ContactPulse .cp-caption{margin-top:10px;padding:8px 10px;background:#181818;border-left:3px solid #f0c674;font-size:11px;color:#bbb;line-height:1.5;}
#insight-panel-ContactPulse .cp-empty{color:#666;font-size:11px;padding:8px;text-align:center;}
#insight-panel-trajectory3d .insight-head{margin-bottom:8px}
#insight-panel-trajectory3d .insight-head h3{margin:0;font-size:15px;color:#e6eefc;font-weight:600}
#insight-panel-trajectory3d .insight-sub{margin:2px 0 0;font-size:11px;color:#7d8da8}
#insight-panel-trajectory3d .t3d-svg-wrap{background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:8px;display:flex;justify-content:center;min-height:360px}
#insight-panel-trajectory3d .t3d-svg-wrap svg{max-width:720px;width:100%;display:block}
#insight-panel-trajectory3d .t3d-caption{margin:8px 0 0;font-size:11px;color:#8aa0bd;text-align:center}
#insight-panel-trajectory3d .insight-empty{color:#7d8da8;font-size:12px;padding:24px 0;text-align:center;width:100%}
/* Intra-section sub-tabs (Sections 05/06/07) */
.subtab-bar { display: flex; gap: 4px; margin: 8px 0 12px; border-bottom: 1px solid var(--line); padding-bottom: 0; flex-wrap: wrap; }
.subtab-bar button {
  background: transparent; border: none; color: var(--dim); padding: 8px 14px;
  font-size: 10px; letter-spacing: 1.5px; font-weight: 600; text-transform: uppercase;
  cursor: pointer; border-bottom: 2px solid transparent; transition: all 0.15s;
  font-family: 'JetBrains Mono', monospace;
}
.subtab-bar button:hover { color: var(--fg2); }
.subtab-bar button.active { color: var(--accent); border-bottom-color: var(--accent); }
.subtab-content { display: none; }
.subtab-content.active { display: block; }
#physics-stress-wave-velocity .phys-caption{
  color:#bcd; font-size:12px; margin:4px 0 10px 0; line-height:1.5;
}
#physics-stress-wave-velocity .phys-empty{
  color:#a99; font-size:12px; padding:14px; border:1px dashed #553;
  border-radius:6px; line-height:1.55;
}
#physics-stress-wave-velocity .phys-chips{
  display:flex; flex-wrap:wrap; gap:6px; margin:0 0 10px 0;
}
#physics-stress-wave-velocity .phys-chip{
  background:#1b2330; color:#d8e2ee; font-size:11px; padding:3px 8px;
  border-radius:10px; border:1px solid #2a3548;
}
#physics-stress-wave-velocity .phys-chip b{ color:#ffd17a; margin-right:4px; }
#physics-stress-wave-velocity .phys-swv-chart{ display:block; max-width:100%; height:auto; }
#physics-stress-wave-velocity .phys-axis-tick{ fill:#aab; font-size:10px; }
#physics-stress-wave-velocity .phys-axis-label{ fill:#cde; font-size:11px; }
#physics-stress-wave-velocity .phys-row-label{ fill:#dde; font-size:11px; cursor:default; }
#physics-stress-wave-velocity .phys-row-value{ fill:#fff; font-size:10px; }
#physics-stress-wave-velocity .phys-theory-label{
  fill:#ff8a8a; font-size:11px; font-weight:600;
}
/* PHYSICS_CSS_INSERT_HERE — RestitutionMap */
#phys-restitution-map .rmap-kpi-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(120px, 1fr));
  gap: 10px;
  margin: 10px 0 14px 0;
}
#phys-restitution-map .rmap-kpi {
  background: #1a1f2b;
  border: 1px solid #2a2f3a;
  border-radius: 6px;
  padding: 8px 10px;
}
#phys-restitution-map .rmap-kpi-wide { grid-column: span 1; }
#phys-restitution-map .rmap-kpi-label {
  font-size: 11px;
  color: #8a93a3;
  margin-bottom: 3px;
  letter-spacing: 0.2px;
}
#phys-restitution-map .rmap-kpi-value {
  font-size: 15px;
  color: #e6ebf3;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
#phys-restitution-map .rmap-grid {
  display: grid;
  grid-template-columns: minmax(320px, 1.1fr) minmax(280px, 1fr);
  gap: 14px;
  margin-bottom: 10px;
}
@media (max-width: 880px) {
  #phys-restitution-map .rmap-grid { grid-template-columns: 1fr; }
  #phys-restitution-map .rmap-kpi-row { grid-template-columns: repeat(2, 1fr); }
}
#phys-restitution-map .rmap-section-title {
  font-size: 12px;
  color: #cfd5e1;
  margin-bottom: 6px;
  font-weight: 500;
}
#phys-restitution-map .rmap-heat-host,
#phys-restitution-map .rmap-hist-host {
  background: #11151d;
  border: 1px solid #2a2f3a;
  border-radius: 6px;
  padding: 6px;
}
#phys-restitution-map .rmap-caption {
  font-size: 12px;
  color: #8a93a3;
  font-style: italic;
  padding: 8px 10px;
  border-left: 3px solid #3a4150;
  background: #14181f;
  border-radius: 0 4px 4px 0;
  line-height: 1.5;
}
#phys-restitution-map .rmap-chip {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 8px;
  font-size: 9px;
  color: #fff;
  margin-left: 4px;
}
#phys-restitution-map .panel-sub {
  font-size: 12px;
  color: #8a93a3;
}

#phys-recovery-damping-panel .phys-rd-head{
  display:flex; flex-wrap:wrap; gap:8px 18px;
  padding:8px 4px 12px 4px; border-bottom:1px solid #2a3038; margin-bottom:10px;
}
#phys-recovery-damping-panel .phys-rd-kpi{ min-width:140px; }
#phys-recovery-damping-panel .phys-rd-kpi .k{
  font-size:10px; color:#8b949e; text-transform:uppercase; letter-spacing:0.04em;
}
#phys-recovery-damping-panel .phys-rd-kpi .v{ font-size:14px; color:#e6edf3; font-weight:600; margin-top:2px; }
#phys-recovery-damping-panel .phys-rd-kpi .v.vbad{ color:#ff8c00; }
#phys-recovery-damping-panel .phys-rd-kpi .v.vgood{ color:#3cc85a; }
#phys-recovery-damping-panel .phys-rd-grid{
  display:grid; grid-template-columns:1fr 1fr; gap:14px;
}
@media (max-width: 900px){
  #phys-recovery-damping-panel .phys-rd-grid{ grid-template-columns:1fr; }
}
#phys-recovery-damping-panel .phys-rd-col{ background:#0d1117; border:1px solid #2a3038; border-radius:6px; padding:6px; }
#phys-recovery-damping-panel .phys-rd-bars{ display:block; }
#phys-recovery-damping-panel .phys-rd-caption{
  margin-top:10px; font-size:11px; color:#8b949e; line-height:1.5;
}
#phys-recovery-damping-panel .phys-rd-empty{
  padding:16px; color:#8b949e; font-size:12px; line-height:1.5;
  border:1px dashed #2a3038; border-radius:6px;
}
/* WorstCombinations panel */
#phys-worst-combinations .wc-empty {
  padding: 18px;
  color: #777;
  font-size: 13px;
  background: #fafafa;
  border: 1px dashed #ccc;
  border-radius: 6px;
}
#phys-worst-combinations .wc-kpi-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}
#phys-worst-combinations .wc-kpi {
  background: #f7f8fa;
  border: 1px solid #e3e6ec;
  border-radius: 6px;
  padding: 10px 12px;
}
#phys-worst-combinations .wc-kpi-critical {
  background: #fff4f3;
  border-color: #f1bdb6;
}
#phys-worst-combinations .wc-kpi-label {
  font-size: 11px;
  color: #6a7282;
  letter-spacing: 0.02em;
  margin-bottom: 4px;
}
#phys-worst-combinations .wc-kpi-value {
  font-size: 22px;
  font-weight: 600;
  color: #1f2730;
  line-height: 1.1;
}
#phys-worst-combinations .wc-kpi-value-sm {
  font-size: 13px;
  font-weight: 500;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
#phys-worst-combinations .wc-kpi-sub {
  font-size: 11px;
  color: #8a8f99;
  margin-top: 2px;
}
#phys-worst-combinations .wc-chip-row {
  margin: 6px 0 10px 0;
  font-size: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}
#phys-worst-combinations .wc-chip-label {
  color: #6a7282;
}
#phys-worst-combinations .wc-chip {
  background: #eef2f7;
  border: 1px solid #d6dde6;
  border-radius: 999px;
  padding: 2px 9px;
  font-size: 11.5px;
  color: #2b3340;
}
#phys-worst-combinations .wc-table-wrap {
  max-height: 460px;
  overflow: auto;
  border: 1px solid #e3e6ec;
  border-radius: 6px;
}
#phys-worst-combinations .wc-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
#phys-worst-combinations .wc-th {
  position: sticky;
  top: 0;
  background: #f0f3f8;
  text-align: left;
  padding: 7px 9px;
  font-weight: 600;
  font-size: 11.5px;
  color: #2b3340;
  border-bottom: 1px solid #d6dde6;
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
}
#phys-worst-combinations .wc-th-num { text-align: right; }
#phys-worst-combinations .wc-th:hover { background: #e6ebf2; }
#phys-worst-combinations .wc-td {
  padding: 5px 9px;
  border-bottom: 1px solid #eef0f3;
  white-space: nowrap;
}
#phys-worst-combinations .wc-td-num {
  text-align: right;
  font-variant-numeric: tabular-nums;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
#phys-worst-combinations .wc-row:hover .wc-td { background: #fafbfd; }
#phys-worst-combinations .wc-risk-red {
  background: #fde7e4 !important;
  color: #a8261a;
  font-weight: 600;
}
#phys-worst-combinations .wc-risk-orange {
  background: #fff1dc !important;
  color: #9a5a05;
  font-weight: 600;
}
#phys-worst-combinations .wc-risk-gray {
  background: #f1f3f5 !important;
  color: #4a525d;
}
#phys-worst-combinations .wc-risk-na {
  color: #98a0aa;
}
#phys-worst-combinations .wc-sort-ind {
  font-size: 10px;
  color: #6a7282;
}
#phys-worst-combinations .wc-caption {
  margin-top: 10px;
  font-size: 11.5px;
  color: #6a7282;
  line-height: 1.5;
}

/* PHYSICS_CSS_INSERT_HERE */

/* INSIGHT_CSS_INSERT_HERE */

/* ---- s9 POSITION DRILL-DOWN (P6) -------------------------------------- */
.s9-badge {
  display: inline-block; padding: 1px 6px; border-radius: 3px;
  font-size: 9.5px; font-weight: 700; letter-spacing: 0.06em;
  margin-left: 4px; vertical-align: 1px;
}
.s9-badge.driver   { background: rgba(77,214,255,0.16); color: #4dd6ff; border: 1px solid rgba(77,214,255,0.45); }
.s9-badge.sdriver  { background: rgba(178,140,255,0.14); color: #b28cff; border: 1px solid rgba(178,140,255,0.45); }
.s9-badge.crit     { background: rgba(255,94,132,0.15); color: #ff5e84; border: 1px solid rgba(255,94,132,0.5); }
.s9-badge.warn     { background: rgba(255,193,94,0.13); color: #ffc15e; border: 1px solid rgba(255,193,94,0.45); }
.s9-badge.impactor { background: rgba(108,116,140,0.15); color: #8b93a8; border: 1px solid rgba(108,116,140,0.4); }
.s9-badge.firsthit { background: transparent; color: #6ee7a0; border: 1px solid rgba(110,231,160,0.55); }
.xlink-hi rect { stroke: #fff !important; stroke-width: 1.5 !important; }
tr.xlink-hi { background: rgba(77,214,255,0.08); }
.s9-skeleton {
  height: 120px; border-radius: 6px;
  background: linear-gradient(90deg, #141a2b 25%, #1b2338 50%, #141a2b 75%);
  background-size: 200% 100%; animation: s9shimmer 1.1s infinite linear;
}
@keyframes s9shimmer { from { background-position: 200% 0; } to { background-position: -200% 0; } }
#s9-narrative {
  padding: 12px 14px; font-size: 13px; line-height: 1.75; color: #c9d2e6;
}
#s9-narrative .dd-b { color: #ff5e84; font-weight: 700; }
#s9-narrative .dd-w { color: #ffc15e; font-weight: 700; }
#s9-narrative .dd-g { color: #6ee7a0; font-weight: 700; }
#s9-narrative .dd-h { color: #4dd6ff; font-weight: 700; }
#s9-pos-select {
  background: #10182a; color: #dfe6f5; border: 1px solid #273252;
  border-radius: 4px; padding: 3px 8px; font-family: inherit; font-size: 12px;
  max-width: 340px;
}
.s9-bar { display: inline-block; height: 8px; background: linear-gradient(90deg,#265a72,#4dd6ff); border-radius: 2px; vertical-align: middle; }
"""
