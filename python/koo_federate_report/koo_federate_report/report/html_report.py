# 리비전 연합 비교 결과(comparison dict)를 단일 자립 HTML 보고서로 렌더링한다.

from __future__ import annotations

import html as _html
import json

__all__ = ["generate_html"]

# 리비전 고정 팔레트 — 모든 뷰에서 같은 색 = 같은 리비전.
_PALETTE = [
    "#4dd6ff", "#ff5e84", "#4adfa1", "#f0a830", "#b46eff",
    "#5b8cff", "#ff9f4d", "#57e3d0", "#ffd166", "#8ce99a",
]

_EMDASH = "&mdash;"


def _esc(v) -> str:
    return _html.escape("" if v is None else str(v), quote=True)


def _num(v, d: int = 0) -> str:
    """숫자를 천단위 구분 문자열로. 값이 없으면 em-dash 로 정직하게 표기한다."""
    if v is None or not isinstance(v, (int, float)) or v != v:
        return _EMDASH
    return f"{v:,.{d}f}"


def _pct(v, d: int = 1) -> str:
    if v is None or not isinstance(v, (int, float)) or v != v:
        return _EMDASH
    return f"{v:+,.{d}f}%"


def _rev_labels(revs) -> list:
    out = []
    for i, r in enumerate(revs or []):
        out.append((r or {}).get("label") or f"REV{i + 1}")
    return out


# --------------------------------------------------------------------------
# CSS — 다크 Bloomberg 디자인 언어(panel / page-head / ctlbar / kpi-strip / dt)
# --------------------------------------------------------------------------
_CSS = r"""
* { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --bg:#0a0c14; --bg2:#11141f; --bg3:#1a1e2e; --bg4:#232839;
  --line:rgba(255,255,255,0.06); --line2:rgba(255,255,255,0.10);
  --fg:#e6ebff; --fg2:#aab2cf; --dim:#5c6383; --num:#c8d4ff;
  --accent:#4dd6ff; --accent2:#ff5e84; --warn:#f0a830; --good:#4adfa1;
  --crit:#ff3854; --tag:#b46eff; --cool:#3d8bff;
}
html, body { background: var(--bg); color: var(--fg);
  font-family: 'Inter', -apple-system, 'Pretendard', 'Segoe UI', system-ui, sans-serif;
  font-size: 12px; -webkit-font-smoothing: antialiased; overflow-x: hidden; }
.mono, .num { font-family: 'JetBrains Mono', 'SF Mono', Menlo, 'Courier New', monospace; font-variant-numeric: tabular-nums; }
b { color: var(--fg); font-weight: 600; }
a { color: inherit; }
.topbar { position: sticky; top: 0; z-index: 60; background: rgba(10,12,20,0.9); backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--line); display: grid; grid-template-columns: auto 1fr auto;
  align-items: center; padding: 10px 32px; gap: 24px; }
.topbar .brand { font-size: 11px; letter-spacing: 4px; color: var(--accent); font-weight: 700; }
.topbar .meta { display: flex; gap: 20px; font-size: 11px; color: var(--dim); overflow-x: auto; white-space: nowrap; }
.topbar .meta b { color: var(--fg2); font-weight: 500; }
.topbar .nav { display: flex; gap: 4px; flex-wrap: wrap; }
.topbar .nav a { text-decoration: none; color: var(--dim); padding: 4px 10px; border-radius: 4px;
  font-size: 11px; letter-spacing: 2px; font-weight: 600; transition: all 0.2s; cursor: pointer; }
.topbar .nav a:hover { color: var(--fg); background: var(--bg3); }
.page { padding: 26px 32px 40px; max-width: 1680px; margin: 0 auto; }
.page-head { display: flex; align-items: baseline; gap: 16px; margin-bottom: 16px; padding-bottom: 12px;
  border-bottom: 1px solid var(--line); flex-wrap: wrap; }
.page-head .num { font-size: 24px; font-weight: 800; color: var(--accent); letter-spacing: -1px; }
.page-head .ttl { font-size: 19px; font-weight: 700; }
.page-head .sub { color: var(--dim); font-size: 12px; flex: 1; text-align: right; letter-spacing: 1px; }
.page-head .tagline { color: var(--tag); font-size: 11px; letter-spacing: 4px; font-weight: 600; }
.grid { display: grid; gap: 14px; }
.g-12 { grid-template-columns: repeat(12, 1fr); }
.col-3{grid-column:span 3;} .col-4{grid-column:span 4;} .col-6{grid-column:span 6;}
.col-8{grid-column:span 8;} .col-12{grid-column:span 12;}
.panel { background: var(--bg2); border: 1px solid var(--line); border-radius: 8px; padding: 14px 16px; position: relative; }
.panel .ph { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 10px;
  padding-bottom: 8px; border-bottom: 1px solid var(--line); gap: 10px; }
.panel .ph .pt { font-size: 11px; font-weight: 700; letter-spacing: 2px; color: var(--accent); }
.panel .ph .pd { font-size: 10px; color: var(--dim); }
.panel .pcap { font-size: 10px; color: var(--dim); margin-top: 8px; line-height: 1.55; }
.kpi-strip { display: grid; grid-template-columns: repeat(4, 1fr); border: 1px solid var(--line);
  border-radius: 8px; overflow: hidden; background: var(--bg2); margin-bottom: 14px; }
.kpi-strip .k { padding: 10px 14px; border-right: 1px solid var(--line); }
.kpi-strip .k:last-child { border-right: none; }
.kpi-strip .k .v { font-size: 17px; font-weight: 700; color: var(--fg); font-family: 'JetBrains Mono', monospace; }
.kpi-strip .k .v .u { color: var(--dim); font-size: 11px; font-weight: 500; margin-left: 4px; font-family: 'Inter', system-ui; }
.kpi-strip .k .l { font-size: 9px; color: var(--dim); letter-spacing: 2px; text-transform: uppercase; margin-top: 4px; }
table.dt { width: 100%; border-collapse: collapse; font-size: 11px; }
table.dt th { color: var(--dim); font-weight: 600; text-align: right; padding: 6px; border-bottom: 1px solid var(--line2);
  font-size: 10px; letter-spacing: 1px; text-transform: uppercase; white-space: nowrap; }
table.dt th.tl { text-align: left; }
table.dt th.srt { cursor: pointer; }
table.dt th.srt:hover { color: var(--accent); }
table.dt td { padding: 5px 6px; border-bottom: 1px solid var(--line); text-align: right; vertical-align: middle; white-space: nowrap; }
table.dt td.tl { text-align: left; }
table.dt tr:hover td { background: rgba(255,255,255,0.02); }
table.dt td.num { color: var(--num); font-family: 'JetBrains Mono', monospace; }
table.dt td.dim { color: var(--dim); }
table.dt td.b { color: var(--fg); font-weight: 600; }
.ctlbar { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; padding: 10px 14px; background: var(--bg2);
  border: 1px solid var(--line); border-radius: 8px; margin-bottom: 14px; }
.ctlbar.fed-sticky { position: sticky; top: 46px; z-index: 40; box-shadow: 0 6px 18px rgba(0,0,0,0.45); }
.ctlbar .grp { display: flex; gap: 4px; align-items: center; flex-wrap: wrap; }
.ctlbar .lbl { font-size: 9px; letter-spacing: 2px; color: var(--dim); font-weight: 700; margin-right: 4px; }
.ctlbar .btn { background: var(--bg3); color: var(--fg2); border: 1px solid var(--line2); padding: 4px 10px;
  font-size: 11px; border-radius: 3px; cursor: pointer; font-family: 'JetBrains Mono', monospace;
  letter-spacing: 1px; transition: all 0.15s; }
.ctlbar .btn:hover { background: var(--bg4); color: var(--fg); }
.ctlbar .btn.active { background: var(--accent); color: var(--bg); border-color: var(--accent); }
select { background: var(--bg3); color: var(--fg); border: 1px solid var(--line2); padding: 3px 8px;
  font-size: 11px; border-radius: 3px; font-family: 'JetBrains Mono', monospace; }
.foot { text-align: center; padding: 24px 16px; color: var(--dim); font-size: 10px; letter-spacing: 2px;
  border-top: 1px solid var(--line); margin-top: 30px; }
.r { opacity: 0; transform: translateY(8px); transition: opacity 0.5s ease, transform 0.5s ease; }
.r.in { opacity: 1; transform: translateY(0); }

/* ---- warnings ---- */
.warn-row { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 14px; }
.warn-badge { display: inline-flex; gap: 8px; align-items: baseline; padding: 5px 12px; border-radius: 4px;
  background: rgba(240,168,48,0.10); border: 1px solid rgba(240,168,48,0.35); color: var(--warn); font-size: 11px; }
.warn-badge .wk { font-size: 9px; letter-spacing: 2px; font-weight: 700; font-family: 'JetBrains Mono', monospace; opacity: 0.85; }

/* ---- s1 revision cards ---- */
.revcards { display: grid; gap: 10px; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); margin-bottom: 14px; }
.revcard { background: var(--bg2); border: 1px solid var(--line); border-left-width: 3px; border-radius: 6px; padding: 10px 12px; }
.revcard .rl { font-size: 13px; font-weight: 700; color: var(--fg); }
.revcard .rp { font-size: 10.5px; color: var(--fg2); margin-top: 3px; font-family: 'JetBrains Mono', monospace;
  overflow: hidden; text-overflow: ellipsis; }
.revcard .rd { font-size: 10px; color: var(--dim); margin-top: 3px; font-family: 'JetBrains Mono', monospace; }
.revcard .rb { display: inline-block; margin-top: 6px; font-size: 9px; letter-spacing: 2px; font-weight: 700;
  padding: 1px 6px; border-radius: 3px; background: var(--bg4); color: var(--fg2); }
.revcard .rb.base { background: var(--accent); color: var(--bg); }
.prose { font-size: 12px; line-height: 1.85; color: var(--fg2); }
.prose b { color: var(--fg); }
.prose .up { color: var(--crit); font-weight: 600; }
.prose .dn { color: var(--good); font-weight: 600; }
.dpct.up { color: var(--crit); } .dpct.dn { color: var(--good); } .dpct.na { color: var(--dim); }

/* ---- s2 profile ---- */
.fed-prof-wrap { position: relative; background: var(--bg3); border-radius: 6px; padding: 6px; }
.fed-prof-wrap svg { width: 100%; display: block; }
.fed-tip { position: absolute; pointer-events: none; display: none; z-index: 20; min-width: 170px;
  background: rgba(10,12,20,0.96); border: 1px solid var(--line2); border-radius: 4px; padding: 7px 9px;
  font-size: 10.5px; line-height: 1.5; color: var(--fg2); box-shadow: 0 6px 20px rgba(0,0,0,0.55); }
.fed-tip.on { display: block; }
.fed-tip .tt { color: var(--accent); font-weight: 700; font-family: 'JetBrains Mono', monospace; margin-bottom: 3px; }
.fed-tip .tr { display: flex; justify-content: space-between; gap: 12px; }
.fed-tip .tr b { font-family: 'JetBrains Mono', monospace; }
.fed-legend { display: flex; gap: 12px; flex-wrap: wrap; }
.fed-legend .lg { display: inline-flex; gap: 5px; align-items: center; font-size: 10.5px; color: var(--fg2); }
.fed-legend .lg .sw { width: 12px; height: 3px; border-radius: 2px; display: inline-block; }
.fed-legend .lg.na .sw { background: var(--dim); height: 0; border-top: 2px dashed var(--dim); }

/* ---- s3 maps ---- */
.map-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(330px, 1fr)); gap: 14px; }
.map-grid .panel svg { width: 100%; display: block; background: #0e1320; border-radius: 4px; }
.map-cell { cursor: pointer; }
.map-cell:hover { stroke: #fff; stroke-width: 1.4; }
.map-cell.sel { stroke: var(--accent); stroke-width: 2; }
.map-bar { display: flex; align-items: center; gap: 8px; margin-top: 8px; font-size: 9.5px; color: var(--dim);
  font-family: 'JetBrains Mono', monospace; }
.map-bar .grad { flex: 1; height: 9px; border-radius: 2px; }
.map-bar .grad.div { background: linear-gradient(90deg, #3d8bff 0%, #232839 50%, #ff3854 100%); }
.map-bar .grad.seq { background: linear-gradient(90deg, #141827 0%, #2b4a7a 25%, #2190a0 50%, #7ec96a 75%, #fde725 100%); }

/* ---- s4 probe ---- */
.probe-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.15fr); gap: 14px; }
@media (max-width: 1100px) { .probe-grid { grid-template-columns: 1fr; } }
.probe-bars { background: var(--bg3); border-radius: 6px; padding: 8px; }
.probe-bars svg { width: 100%; display: block; }
.bbadge { display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 9px; font-weight: 700;
  letter-spacing: 1px; font-family: 'JetBrains Mono', monospace; color: #0b0b0b; }
.bbadge.bounce { background: var(--good); }
.bbadge.rebound { background: var(--warn); }
.bbadge.slide { background: var(--tag); color: #fff; }
.bbadge.embed { background: var(--crit); color: #fff; }
.bbadge.no-contact { background: #3a4152; color: #9aa5c0; }
.bbadge.unknown { background: var(--dim); color: #0b0b0b; }
.trust-no { color: var(--warn); font-weight: 600; }
.trust-yes { color: var(--good); }

/* ---- s5 / s7 ---- */
.spark { display: block; }
.mtx-wrap { background: var(--bg3); border-radius: 6px; padding: 8px; overflow-x: auto; }
.mtx-wrap svg { display: block; min-width: 100%; }
.warn-badge.error { border-color: rgba(255,94,132,.55); color: #ff5e84;
  background: rgba(255,94,132,.12); }
.warn-badge.info { opacity: .85; }
.miss-badge { display:inline-block; margin-left:6px; padding:1px 6px; border-radius:3px;
  font-size:9.5px; font-weight:700; letter-spacing:.05em; color:#ffc15e;
  background:rgba(255,193,94,.13); border:1px solid rgba(255,193,94,.45); }
.um-wrap { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:12px; }
.um-col { background:#10182a; border:1px solid #273252; border-radius:6px; padding:10px 12px; }
.um-h { font-size:11px; letter-spacing:.06em; color:#c9d2e6; margin-bottom:6px;
  display:flex; justify-content:space-between; }
.um-item { font-size:11.5px; color:#ffc15e; padding:2px 0; }
.fdrev { margin: 0 0 14px 0; }
.fdrev-h { font-size: 12px; letter-spacing: .06em; color: #c9d2e6; margin: 10px 2px 6px; }
.fdiff { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
@media (max-width: 900px) { .fdiff { grid-template-columns: 1fr; } }
.fcol { background: var(--bg2); border: 1px solid var(--line); border-radius: 6px; padding: 10px 12px; }
.fcol .fh { font-size: 10px; letter-spacing: 2px; font-weight: 700; padding-bottom: 6px; margin-bottom: 6px;
  border-bottom: 1px solid var(--line); display: flex; justify-content: space-between; }
.fcol.new .fh { color: var(--crit); } .fcol.res .fh { color: var(--good); } .fcol.kept .fh { color: var(--dim); }
.fitem { display: flex; gap: 8px; align-items: baseline; padding: 4px 0; border-bottom: 1px solid var(--line); font-size: 11px; }
.fitem:last-child { border-bottom: none; }
.fsev { font-size: 8.5px; letter-spacing: 1px; font-weight: 700; padding: 1px 5px; border-radius: 3px;
  font-family: 'JetBrains Mono', monospace; flex-shrink: 0; }
.fsev.CRITICAL { background: var(--crit); color: #fff; }
.fsev.WARNING { background: var(--warn); color: #0b0b0b; }
.fsev.INFO { background: var(--bg4); color: var(--fg2); }
.empty { color: var(--dim); font-size: 11px; font-style: italic; padding: 10px 2px; }
.bt-panel { border-left: 3px solid var(--crit); }
.bt-panel .ph .pt { color: var(--crit); }
.bt-head { font-size: 15px; font-weight: 700; color: var(--fg); line-height: 1.5; margin-bottom: 8px; }
.bt-sum { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }
.bt-chip { background: var(--bg3); border: 1px solid var(--line2); border-radius: 4px; padding: 4px 10px;
  font-size: 11px; font-family: 'JetBrains Mono', monospace; color: var(--fg2); }
.bt-chip b { color: var(--accent); }
.bt-rows { max-height: 220px; overflow-y: auto; }
@media (max-width: 1280px) {
  .col-3, .col-4, .col-6, .col-8 { grid-column: span 12; }
  .topbar { padding: 10px 16px; } .page { padding: 20px 16px; }
  .kpi-strip { grid-template-columns: repeat(2, 1fr); }
}
"""


# --------------------------------------------------------------------------
# 파이썬 측 정적 섹션 빌더
# --------------------------------------------------------------------------
def _build_topbar(cmp_: dict, nav: list) -> str:
    revs = cmp_.get("revisions") or []
    kind = cmp_.get("kind") or "unknown"
    kpi = cmp_.get("kpi") or {}
    nav_html = "".join(
        f'<a href="#{_esc(sid)}">{_esc(lbl)}</a>' for sid, lbl in nav
    )
    return (
        '<div class="topbar">\n'
        '  <div class="brand">KOO &middot; FEDERATE</div>\n'
        '  <div class="meta">'
        f'<span>KIND <b>{_esc(kind.upper())}</b></span>'
        f'<span>REVISIONS <b>{len(revs)}</b></span>'
        f'<span>CELLS <b>{_esc(kpi.get("n_cells", len(cmp_.get("cells") or [])))}</b></span>'
        f'<span>COMPARABLE <b>{_esc(kpi.get("n_comparable", _EMDASH))}</b></span>'
        "</div>\n"
        f'  <div class="nav">{nav_html}</div>\n'
        "</div>\n"
    )


def _build_warnings(cmp_: dict) -> str:
    ws = cmp_.get("warnings") or []
    if not ws:
        return ""
    # 엔진 계약: {code, message, severity}. 구 샘플({kind,msg})도 함께 수용한다.
    # (code/message 를 못 읽어 경고 문구가 빈 칸으로 나가던 결함 수정)
    def _wk(w):
        return str((w or {}).get("code") or (w or {}).get("kind") or "WARN").upper()

    def _wm(w):
        return str((w or {}).get("message") or (w or {}).get("msg") or "")

    items = "".join(
        '<div class="warn-badge {sev}"><span class="wk">{k}</span><span>{m}</span></div>'.format(
            sev=_esc(str((w or {}).get("severity", "")).lower()),
            k=_esc(_wk(w)), m=_esc(_wm(w)),
        )
        for w in ws
    )
    return f'<div class="warn-row r">{items}</div>\n'


def _build_revcards(cmp_: dict) -> str:
    revs = cmp_.get("revisions") or []
    prov = cmp_.get("provenance") or []
    base = int(cmp_.get("baseline_idx") or 0)
    if not revs:
        return '<div class="empty">리비전 정보가 없다. 데이터 없음.</div>\n'
    cards = []
    for i, r in enumerate(revs):
        p = prov[i] if i < len(prov) else {}
        color = _PALETTE[i % len(_PALETTE)]
        badge = (
            '<span class="rb base">BASELINE</span>'
            if i == base
            else f'<span class="rb">REV {i + 1}</span>'
        )
        gen = (p or {}).get("generated_utc") or _EMDASH
        cards.append(
            f'<div class="revcard" style="border-left-color:{color}">'
            f'<div class="rl">{_esc((r or {}).get("label") or f"REV{i + 1}")}</div>'
            f'<div class="rp">{_esc((r or {}).get("project") or _EMDASH)}</div>'
            f'<div class="rd">{_esc(gen)}</div>'
            f"{badge}</div>"
        )
    return '<div class="revcards r">' + "".join(cards) + "</div>\n"


def _delta_cell(v, base_v):
    """baseline 대비 Δ% 를 색 클래스와 함께 반환한다."""
    if not isinstance(v, (int, float)) or not isinstance(base_v, (int, float)) or not base_v:
        return _EMDASH, "na"
    d = (v - base_v) / abs(base_v) * 100.0
    return _pct(d), ("up" if d > 0 else ("dn" if d < 0 else "na"))


def _build_kpi_table(cmp_: dict) -> str:
    kpi = cmp_.get("kpi") or {}
    labels = _rev_labels(cmp_.get("revisions"))
    base = int(cmp_.get("baseline_idx") or 0)
    gdiv = cmp_.get("g_divisor") or 0
    ul = cmp_.get("unit_labels") or {}
    if not labels:
        return ""

    rows_def = [
        ("WORST ACC", kpi.get("worst_g") or [], ("G" if gdiv else (ul.get("acc") or "")), gdiv or 1.0, 0),
        ("WORST STRESS", kpi.get("worst_s") or [], ul.get("stress") or "", 1.0, 0),
        ("DISSIPATION", kpi.get("diss_pct") or [], "%", 1.0, 1),
    ]
    head = '<th class="tl">METRIC</th>' + "".join(
        f'<th>{_esc(l)}</th><th>&Delta; vs BASE</th>' for l in labels
    )
    body = []
    for name, vals, unit, div, dec in rows_def:
        base_v = vals[base] if base < len(vals) else None
        tds = [f'<td class="tl b">{_esc(name)} <span class="dim">{_esc(unit)}</span></td>']
        for i in range(len(labels)):
            v = vals[i] if i < len(vals) else None
            shown = _num(v / div, dec) if isinstance(v, (int, float)) else _EMDASH
            dtxt, dcls = (("BASE", "na") if i == base else _delta_cell(v, base_v))
            tds.append(f'<td class="num">{shown}</td><td class="dpct {dcls}">{dtxt}</td>')
        body.append("<tr>" + "".join(tds) + "</tr>")
    return (
        '<table class="dt"><thead><tr>' + head + "</tr></thead><tbody>"
        + "".join(body) + "</tbody></table>"
    )


def _build_kpi_strip(cmp_: dict) -> str:
    kpi = cmp_.get("kpi") or {}
    cells = cmp_.get("cells") or []
    cov = cmp_.get("coverage") or {}
    n_cells = kpi.get("n_cells", len(cells))
    n_cmp = kpi.get("n_comparable")
    n_unjudged = sum(1 for c in cells if not (c or {}).get("trust_ok"))
    items = [
        (str(n_cells), "", "CELLS"),
        (_EMDASH if n_cmp is None else str(n_cmp), f"/ {n_cells}", "판정 가능"),
        (str(kpi.get("n_revisions", len(cmp_.get("revisions") or []))), "", "REVISIONS"),
        (str(n_unjudged), "", "미판정 셀"),
        (str(cov.get("intersection", _EMDASH)), "", "공통 교집합"),
    ]
    ks = "".join(
        f'<div class="k"><div class="v">{_esc(v)}<span class="u">{_esc(u)}</span></div>'
        f'<div class="l">{_esc(l)}</div></div>'
        for v, u, l in items
    )
    return f'<div class="kpi-strip r" style="grid-template-columns:repeat(5,1fr)">{ks}</div>\n'


def _summary_prose(cmp_: dict) -> str:
    revs = cmp_.get("revisions") or []
    cells = cmp_.get("cells") or []
    kpi = cmp_.get("kpi") or {}
    base = int(cmp_.get("baseline_idx") or 0)
    if not revs:
        return "비교할 리비전이 없다. 입력에 revisions 가 비어 있어 요약을 만들 수 없다."
    labels = _rev_labels(revs)
    gdiv = cmp_.get("g_divisor") or 0
    unit = "G" if gdiv else ((cmp_.get("unit_labels") or {}).get("acc") or "")
    div = gdiv or 1.0
    out = [
        f"기준 리비전은 <b>{_esc(labels[base])}</b> 이고, 총 <b>{len(revs)}</b>개 리비전을 "
        f"<b>{len(cells)}</b>개 셀에서 비교했다."
    ]

    wg = kpi.get("worst_g") or []
    pairs = [(i, v) for i, v in enumerate(wg) if isinstance(v, (int, float))]
    if len(pairs) >= 2:
        bi, bv = min(pairs, key=lambda t: t[1])
        wi, wv = max(pairs, key=lambda t: t[1])
        out.append(
            f"최저 worst 응답은 <b>{_esc(labels[bi])}</b> "
            f'(<span class="dn">{_num(bv / div)} {_esc(unit)}</span>) 로 가장 양호하고, '
            f"최악은 <b>{_esc(labels[wi])}</b> "
            f'(<span class="up">{_num(wv / div)} {_esc(unit)}</span>) 이다.'
        )
    elif len(pairs) == 1:
        out.append("worst 지표가 리비전 1개에만 있어 우열을 가릴 수 없다.")
    else:
        out.append("worst 지표가 비어 있어 리비전 우열은 판정하지 않았다.")

    frags = []
    for i in range(len(revs)):
        if i == base:
            continue
        imp = wor = 0
        for c in cells:
            d = ((c or {}).get("delta_pct") or [])
            v = d[i] if i < len(d) else None
            if not isinstance(v, (int, float)):
                continue
            if v < 0:
                imp += 1
            elif v > 0:
                wor += 1
        frags.append(
            f'<b>{_esc(labels[i])}</b> 는 개선 <span class="dn">{imp}</span>셀 &middot; '
            f'악화 <span class="up">{wor}</span>셀'
        )
    if frags:
        out.append("baseline 대비 " + ", ".join(frags) + " 이다.")

    unjudged = sum(1 for c in cells if not (c or {}).get("trust_ok"))
    if unjudged:
        out.append(
            f"<b>{unjudged}</b>개 셀은 신뢰 게이트를 통과하지 못해 Δ 를 판정하지 않았다. "
            "이 셀들은 프로파일에서 점선/회색으로 강등하고 지도에서는 빗금으로 표시한다."
        )
    else:
        out.append("모든 셀이 신뢰 게이트를 통과해 Δ 판정이 가능하다.")

    bt = cmp_.get("behavior_transitions") or {}
    if bt.get("headline"):
        out.append(
            "거동 전이가 헤드라인으로 승격됐다. 비교 기준 자체가 달라졌으므로 Δ 해석에 주의가 필요하다."
        )
    return " ".join(out)


def _build_s1(cmp_: dict) -> str:
    return (
        '<section class="page" id="s1">\n'
        '  <div class="page-head r"><span class="num">01</span>'
        '<span class="tagline">FEDERATE &middot; SUMMARY</span>'
        '<span class="ttl">리비전 연합 요약 &mdash; 무엇이 좋아지고 무엇이 나빠졌나</span>'
        '<span class="sub">BASELINE-RELATIVE OVERVIEW</span></div>\n'
        + _build_warnings(cmp_)
        + _build_revcards(cmp_)
        + _build_kpi_strip(cmp_)
        + '  <div class="grid g-12">\n'
        '    <div class="panel col-8 r"><div class="ph"><span class="pt">KPI Δ 스트립</span>'
        '<span class="pd">value + Δ% vs baseline</span></div>'
        + _build_kpi_table(cmp_)
        + '<div class="pcap">Δ 는 baseline 대비 상대 변화다. 절대 임계값은 쓰지 않고 부호와 크기만 색으로 나타낸다.</div></div>\n'
        '    <div class="panel col-4 r"><div class="ph"><span class="pt">자동 요약</span>'
        '<span class="pd">AUTO PROSE</span></div>'
        f'<div class="prose">{_summary_prose(cmp_)}</div></div>\n'
        "  </div>\n</section>\n"
    )


def _build_s6(cmp_: dict, promoted: bool) -> str:
    """거동 전이 매트릭스 — 엔진 계약: per_rev[{label,n_changed,counts,entries}].

    entries 는 baseline→해당 리비전의 (from,to,count,cells) 목록이다.
    미접촉↔접촉 전이는 "같은 물리 사건이 아님"을 뜻하므로 헤드라인으로 승격된다.
    """
    bt = cmp_.get("behavior_transitions") or {}
    per_rev = bt.get("per_rev") or []
    base_idx = bt.get("baseline_idx", 0)
    n_changed = bt.get("n_changed_cells", 0)
    if not per_rev:
        return ""

    blocks = []
    for i, pr in enumerate(per_rev):
        pr = pr or {}
        if i == base_idx:
            continue
        entries = [e for e in (pr.get("entries") or []) if (e or {}).get("from") != (e or {}).get("to")]
        counts = pr.get("counts") or {}
        chips = "".join(
            f'<div class="bt-chip">{_esc(k)} <b>{_esc(v)}</b></div>' for k, v in counts.items()
        ) or '<div class="empty">거동 분포 없음.</div>'
        body_rows = "".join(
            '<tr><td class="tl"><span class="bbadge {fc}">{f}</span></td>'
            '<td class="tl">&rarr;</td>'
            '<td class="tl"><span class="bbadge {tc}">{to}</span></td>'
            '<td class="num b">{n}</td>'
            '<td class="tl dim">{cells}</td></tr>'.format(
                fc=_esc((e or {}).get("from", "unknown")),
                f=_esc((e or {}).get("from", _EMDASH)),
                tc=_esc((e or {}).get("to", "unknown")),
                to=_esc((e or {}).get("to", _EMDASH)),
                n=_esc((e or {}).get("count", 0)),
                cells=_esc(", ".join((e or {}).get("cells", [])[:8]) +
                           (" 외" if len((e or {}).get("cells", [])) > 8 else "")),
            )
            for e in entries
        ) or '<tr><td class="tl dim" colspan="5">이 리비전은 거동 전이가 없습니다.</td></tr>'
        blocks.append(
            f'<div class="panel bt-panel r"><div class="ph">'
            f'<span class="pt">{_esc(pr.get("label") or f"REV{i + 1}")} <span class="dim">vs baseline</span></span>'
            f'<span class="pd">{_esc(pr.get("n_changed", 0))} cell(s) changed</span></div>'
            f'<div class="bt-sum">{chips}</div>'
            f'<div class="bt-rows"><table class="dt"><tbody>{body_rows}</tbody></table></div></div>'
        )

    head_txt = (f"거동 분류가 바뀐 셀 {n_changed}개 — 비교 기준 자체가 달라졌을 수 있다."
                if n_changed else "거동 전이 없음 — 모든 셀이 같은 거동 분류를 유지했다.")
    num = "!!" if promoted else "06"
    return (
        f'<section class="page" id="s6">\n'
        f'  <div class="page-head r"><span class="num">{num}</span>'
        '<span class="tagline">BEHAVIOR &middot; TRANSITION</span>'
        '<span class="ttl">거동 전이 매트릭스</span>'
        '<span class="sub">CONTACT REGIME SHIFT</span></div>\n'
        f'  <div class="bt-head r">{_esc(head_txt)}</div>\n'
        + "".join(blocks) +
        '  <div class="pcap r">한쪽이 미접촉이면 두 런은 같은 물리 사건이 아니다. '
        '이 셀의 &Delta; 는 개선/악화로 읽지 말 것.</div>\n</section>\n'
    )


def _fd_list(cmp_: dict) -> list:
    """findings_diff 정규화 — 엔진은 리비전별 list, 구 샘플은 단일 dict."""
    fd = cmp_.get("findings_diff")
    if isinstance(fd, list):
        return [x or {} for x in fd]
    if isinstance(fd, dict) and fd:
        return [{"label": "vs baseline", "is_baseline": False, **fd}]
    return []


def _build_s8(cmp_: dict) -> str:
    """findings diff — 엔진은 리비전별 list 로 준다(리비전마다 diff 가 다르므로).

    baseline 은 자기 자신과의 diff 라 열에서 제외하고, 비교 리비전마다
    신규/해소/유지 3열 블록을 만든다.
    """
    fds = _fd_list(cmp_)
    cols = [("new", "신규 (+)", "new"), ("resolved", "해소 (−)", "res"), ("kept", "유지 (=)", "kept")]
    blocks = []
    for fd in fds:
        if fd.get("is_baseline"):
            continue
        html = []
        for key, title, cls in cols:
            items = fd.get(key) or []
            body = "".join(
                '<div class="fitem"><span class="fsev {sev}">{sev}</span><span>{t}</span></div>'.format(
                    sev=_esc((f or {}).get("severity", "INFO")),
                    t=_esc((f or {}).get("title", _EMDASH)),
                )
                for f in items
            ) or '<div class="empty">해당 항목 없음.</div>'
            html.append(
                f'<div class="fcol {cls}"><div class="fh"><span>{_esc(title)}</span>'
                f'<span>{len(items)}</span></div>{body}</div>'
            )
        blocks.append(
            f'<div class="fdrev"><div class="fdrev-h">{_esc(fd.get("label") or "REV")}'
            f' <span class="dim">vs baseline</span></div>'
            '<div class="fdiff r">' + "".join(html) + "</div></div>"
        )
    if not blocks:
        blocks.append('<div class="empty">비교할 findings 가 없습니다.</div>')
    return (
        '<section class="page" id="s8">\n'
        '  <div class="page-head r"><span class="num">08</span>'
        '<span class="tagline">FINDINGS &middot; DIFF</span>'
        '<span class="ttl">발견 사항 차분 &mdash; baseline 대비</span>'
        '<span class="sub">NEW / RESOLVED / KEPT</span></div>\n'
        + "".join(blocks) + "\n</section>\n"
    )


def _build_s11(cmp_: dict) -> str:
    """미매칭 파트 — 어느 리비전에서 짝을 못 찾았는지 정직하게 나열한다.

    YAML `unmatched: show` 의 실제 구현. 이게 없으면 파트 표에서 값이 빈 칸이
    '개선'으로 오독된다(부재와 0 은 다르다).
    """
    um = cmp_.get("unmatched") or []
    rows = [x for x in um if (x or {}).get("parts")]
    parts = cmp_.get("parts") or []
    partial = [p for p in parts
               if isinstance(p.get("present"), list) and not all(p["present"])]
    if not rows and not partial:
        return ""

    labels = _rev_labels(cmp_.get("revisions"))
    cols = "".join(
        '<div class="um-col"><div class="um-h"><span>{}</span><span>{}</span></div>{}</div>'.format(
            _esc((x or {}).get("label") or f"REV{i + 1}"),
            len((x or {}).get("parts") or []),
            "".join(f'<div class="um-item">{_esc(nm)}</div>'
                    for nm in ((x or {}).get("parts") or []))
            or '<div class="empty">없음.</div>',
        )
        for i, x in enumerate(rows)
    ) or '<div class="empty">리비전별 미매칭 파트가 없습니다.</div>'

    prows = "".join(
        "<tr><td class=\"tl b\">{}</td><td class=\"tl\">{}</td><td class=\"tl dim\">{}</td></tr>".format(
            _esc(p.get("canonical", _EMDASH)),
            _esc(", ".join(labels[i] for i, ok in enumerate(p.get("present") or [])
                           if not ok) or _EMDASH),
            _esc(" / ".join((n or "없음") for n in (p.get("names") or []))),
        )
        for p in partial
    )
    ptable = (
        '<div class="panel r"><div class="ph"><span class="pt">부분 존재 파트</span>'
        f'<span class="pd">{len(partial)} part(s)</span></div>'
        '<table class="dt"><thead><tr><th class="tl">CANONICAL</th>'
        '<th class="tl">없는 리비전</th><th class="tl">리비전별 원본명</th></tr></thead>'
        f"<tbody>{prows}</tbody></table>"
        '<div class="pcap">값이 비어 있는 칸은 0 이 아니라 <b>부재</b>다. '
        '이름이 바뀐 것이라면 YAML <code>parts:</code> 매칭표에 추가하면 이어진다.</div></div>'
    ) if partial else ""

    return (
        '<section class="page" id="s11">\n'
        '  <div class="page-head r"><span class="num">11</span>'
        '<span class="tagline">UNMATCHED &middot; PARTS</span>'
        '<span class="ttl">미매칭 파트 &mdash; 짝을 못 찾은 항목</span>'
        '<span class="sub">NAME MISMATCH / DESIGN CHANGE</span></div>\n'
        f'  <div class="um-wrap r">{cols}</div>\n'
        f"  {ptable}\n</section>\n"
    )


def _build_s9(cmp_: dict) -> str:
    prov = cmp_.get("provenance") or []
    cov = cmp_.get("coverage") or {}
    labels = _rev_labels(cmp_.get("revisions"))
    rows = []
    for i, p in enumerate(prov):
        p = p or {}
        rows.append(
            "<tr><td class=\"tl b\">{}</td><td class=\"tl num\">{}</td><td class=\"tl num\">{}</td>"
            "<td class=\"tl dim\">{}</td><td class=\"num\">{}</td></tr>".format(
                _esc(p.get("label") or (labels[i] if i < len(labels) else f"REV{i + 1}")),
                _esc(p.get("tool_version") or _EMDASH),
                _esc(p.get("generated_utc") or _EMDASH),
                _esc(p.get("test_dir") or _EMDASH),
                _esc(p.get("input_digest") or _EMDASH),
            )
        )
    table = (
        '<table class="dt"><thead><tr><th class="tl">리비전</th><th class="tl">TOOL VER</th>'
        '<th class="tl">GENERATED (UTC)</th><th class="tl">TEST DIR</th><th>INPUT DIGEST</th></tr></thead>'
        "<tbody>" + "".join(rows) + "</tbody></table>"
        if rows
        else '<div class="empty">provenance 정보 없음. 무엇과 무엇을 비교했는지 기록이 없다.</div>'
    )
    per_rev = cov.get("per_rev") or []
    cov_rows = "".join(
        f'<div class="bt-chip">{_esc(labels[i] if i < len(labels) else i)} <b>{_esc(v)}</b></div>'
        for i, v in enumerate(per_rev)
    ) or '<div class="empty">커버리지 정보 없음.</div>'
    return (
        '<section class="page" id="s9">\n'
        '  <div class="page-head r"><span class="num">09</span>'
        '<span class="tagline">PROVENANCE &middot; APPENDIX</span>'
        '<span class="ttl">출처 부록 &mdash; 무엇과 무엇을 비교했는가</span>'
        '<span class="sub">TRACEABILITY</span></div>\n'
        '  <div class="grid g-12">\n'
        '    <div class="panel col-8 r"><div class="ph"><span class="pt">리비전 출처</span>'
        '<span class="pd">tool version / generated / digest</span></div>' + table + "</div>\n"
        '    <div class="panel col-4 r"><div class="ph"><span class="pt">커버리지</span>'
        f'<span class="pd">intersection {_esc(cov.get("intersection", _EMDASH))} '
        f'&middot; resampled {_esc(cov.get("resampled", _EMDASH))}</span></div>'
        f'<div class="bt-sum">{cov_rows}</div>'
        f'<div class="pcap">{_esc(cov.get("note") or "리샘플 메모 없음.")}</div></div>\n'
        "  </div>\n</section>\n"
    )


#: 지표 → unit_labels 축 이름 (models.METRIC_UNIT_AXIS 와 같은 표, 렌더 전용 사본)
_METRIC_AXIS = {"g": "acc", "s": "stress", "e": "strain", "d": "disp"}


def _build_s10(cmp_: dict) -> str:
    """카테고리 소계 비교 — 엔진 계약: category_summary{categories[{name,n_cells,per_rev}]}.

    "코너 낙하만 나빠졌다" 같은 구조적 회귀를 한 화면에서 잡는 뷰다.
    막대는 카테고리별 worst, 막대 위 라벨은 baseline 대비 Δ% 이며,
    표에는 worst/median/mean 을 리비전별로 모두 적는다.
    카테고리가 1종 이하이면 엔진이 빈 dict 를 주므로 이 섹션은 생성되지 않는다.
    """
    cs = cmp_.get("category_summary") or {}
    cats = cs.get("categories") or []
    if not cats:
        return ""
    labels = _rev_labels(cmp_.get("revisions"))
    n_rev = len(labels)
    base = int(cs.get("baseline_idx", cmp_.get("baseline_idx") or 0))
    gdiv = cmp_.get("g_divisor") or 0
    metric = cs.get("metric") or "g"
    axis = _METRIC_AXIS.get(metric, "acc")
    unit = ("G" if (gdiv and metric == "g")
            else ((cmp_.get("unit_labels") or {}).get(axis) or ""))
    div = (gdiv or 1.0) if metric == "g" else 1.0

    def shown(v):
        return _num(v / div, 0) if isinstance(v, (int, float)) else _EMDASH

    # ---- 그룹 막대 (worst) ----
    W, H = 1240, 330
    ml, mr, mt, mb = 78, 20, 30, 62
    iw, ih = W - ml - mr, H - mt - mb
    vals = [
        (r or {}).get("worst")
        for ct in cats for r in (ct.get("per_rev") or [])
        if isinstance((r or {}).get("worst"), (int, float))
    ]
    vmax = max([v / div for v in vals], default=0.0) or 1.0
    gw = iw / max(len(cats), 1)
    bw = min(46.0, max((gw - 20.0) / max(n_rev, 1), 3.0))

    def ypx(v):
        return mt + ih - max(0.0, min(1.0, v / vmax)) * ih

    sg = []
    for t in range(5):
        tv = vmax * t / 4.0
        y = ypx(tv)
        sg.append(
            f'<line x1="{ml}" y1="{y:.1f}" x2="{W - mr}" y2="{y:.1f}" '
            f'stroke="rgba(255,255,255,0.05)"/>'
            f'<text x="{ml - 8}" y="{y + 3.5:.1f}" fill="#5c6383" font-size="10" '
            f'text-anchor="end" font-family="JetBrains Mono, monospace">{_num(tv, 0)}</text>'
        )
    sg.append(
        f'<text x="16" y="{mt + ih / 2:.1f}" fill="#aab2cf" font-size="10.5" text-anchor="middle" '
        f'transform="rotate(-90 16 {mt + ih / 2:.1f})">worst {_esc(unit)}</text>'
    )
    for j, ct in enumerate(cats):
        gx = ml + j * gw
        x0 = gx + (gw - bw * n_rev) / 2.0
        for i in range(n_rev):
            row = (ct.get("per_rev") or [{}] * n_rev)[i] if i < len(ct.get("per_rev") or []) else {}
            v = (row or {}).get("worst")
            x = x0 + i * bw
            if not isinstance(v, (int, float)):
                sg.append(
                    f'<text x="{x + bw / 2:.1f}" y="{mt + ih - 6:.1f}" fill="#5c6383" '
                    f'font-size="9" text-anchor="middle">&mdash;</text>'
                )
                continue
            y = ypx(v / div)
            sg.append(
                f'<rect x="{x + 1:.1f}" y="{y:.1f}" width="{max(bw - 2, 1):.1f}" '
                f'height="{max(mt + ih - y, 1):.1f}" fill="{_PALETTE[i % len(_PALETTE)]}" '
                f'fill-opacity="{0.95 if i == base else 0.8}" rx="2">'
                f'<title>{_esc(ct.get("name"))} · {_esc(labels[i])} · worst {shown(v)} {_esc(unit)}</title></rect>'
            )
            dpct = (row or {}).get("worst_delta_pct")
            if i != base and isinstance(dpct, (int, float)):
                col = "#ff3854" if dpct > 0 else ("#4adfa1" if dpct < 0 else "#5c6383")
                sg.append(
                    f'<text x="{x + bw / 2:.1f}" y="{y - 4:.1f}" fill="{col}" font-size="9.5" '
                    f'text-anchor="middle" font-family="JetBrains Mono, monospace">{_pct(dpct)}</text>'
                )
        sg.append(
            f'<text x="{gx + gw / 2:.1f}" y="{mt + ih + 18:.1f}" fill="#e6ebff" font-size="11" '
            f'text-anchor="middle">{_esc(ct.get("name"))}</text>'
            f'<text x="{gx + gw / 2:.1f}" y="{mt + ih + 32:.1f}" fill="#5c6383" font-size="9.5" '
            f'text-anchor="middle" font-family="JetBrains Mono, monospace">'
            f'{_esc(ct.get("n_cells", 0))} cells</text>'
        )
    sg.append(
        f'<line x1="{ml}" y1="{mt + ih}" x2="{W - mr}" y2="{mt + ih}" stroke="rgba(255,255,255,0.15)"/>'
    )
    svg = f'<svg viewBox="0 0 {W} {H}" style="width:100%;display:block">' + "".join(sg) + "</svg>"

    legend = "".join(
        f'<span class="lg"><span class="sw" style="background:{_PALETTE[i % len(_PALETTE)]}"></span>'
        f'<span>{_esc(l)}{" *" if i == base else ""}</span></span>'
        for i, l in enumerate(labels)
    )

    # ---- 표 (worst / median / mean) ----
    head = ('<th class="tl">카테고리</th><th class="tl">통계</th><th>N</th>'
            + "".join(f'<th>{_esc(l)}</th><th>&Delta; vs BASE</th>' for l in labels))
    body = []
    for ct in cats:
        per_rev = ct.get("per_rev") or []
        for si, (stat, stat_lbl) in enumerate((("worst", "WORST"), ("median", "MEDIAN"), ("mean", "MEAN"))):
            tds = []
            if si == 0:
                tds.append(f'<td class="tl b" rowspan="3">{_esc(ct.get("name"))}</td>')
            tds.append(f'<td class="tl dim">{stat_lbl}</td>')
            if si == 0:
                tds.append(f'<td class="num" rowspan="3">{_esc(ct.get("n_cells", 0))}</td>')
            for i in range(n_rev):
                row = per_rev[i] if i < len(per_rev) else {}
                v = (row or {}).get(stat)
                dpct = (row or {}).get(f"{stat}_delta_pct")
                if i == base:
                    dtxt, dcls = "BASE", "na"
                elif isinstance(dpct, (int, float)):
                    dtxt, dcls = _pct(dpct), ("up" if dpct > 0 else ("dn" if dpct < 0 else "na"))
                else:
                    dtxt, dcls = _EMDASH, "na"
                tds.append(f'<td class="num">{shown(v)}</td><td class="dpct {dcls}">{dtxt}</td>')
            body.append("<tr>" + "".join(tds) + "</tr>")
    table = ('<table class="dt"><thead><tr>' + head + "</tr></thead><tbody>"
             + "".join(body) + "</tbody></table>")

    n_excl = cs.get("n_excluded_gated") or 0
    excl_txt = (f" 미판정 셀 {n_excl}개는 모든 카테고리에서 똑같이 제외했다 — "
                "리비전마다 다른 셀 집합으로 집계하면 소계 Δ 가 오염된다."
                if n_excl else "")
    return (
        '<section class="page" id="s10">\n'
        '  <div class="page-head r"><span class="num">10</span>'
        '<span class="tagline">CATEGORY &middot; BREAKDOWN</span>'
        f'<span class="ttl">카테고리 소계 &mdash; {_esc(cs.get("metric_label") or "")} 의 구조적 회귀</span>'
        f'<span class="sub">{_esc(cs.get("n_categories", len(cats)))} CATEGORIES</span></div>\n'
        '  <div class="panel r"><div class="ph">'
        '<span class="pt">카테고리별 worst</span>'
        f'<span class="pd">막대 위 숫자 = baseline({_esc(labels[base] if base < len(labels) else "")}) 대비 &Delta;%</span></div>'
        f'{svg}'
        f'<div class="fed-legend" style="margin-top:8px">{legend}</div>'
        '<div class="pcap">"코너 낙하만 나빠졌다" 같은 구조적 회귀를 잡는 뷰다. '
        'Δ% 는 baseline 대비 상대 변화이고 절대 임계값은 쓰지 않는다.'
        f'{_esc(excl_txt)}</div></div>\n'
        '  <div class="panel r" style="margin-top:14px"><div class="ph">'
        '<span class="pt">소계 표</span><span class="pd">worst / median / mean</span></div>'
        f'{table}'
        '<div class="pcap">N 은 그 카테고리에서 Δ 판정이 가능한 셀 수이며 모든 리비전에 공통이다.</div></div>\n'
        "</section>\n"
    )


# --------------------------------------------------------------------------
# 정적 HTML 템플릿 (JS 가 채우는 컨테이너)
# --------------------------------------------------------------------------
_S2 = """
<section class="page" id="s2">
  <div class="page-head r"><span class="num">02</span>
    <span class="tagline">UNROLLED &middot; PROFILE</span>
    <span class="ttl">전개 프로파일 &mdash; 리비전 겹침 (주력 뷰)</span>
    <span class="sub">MAGNITUDE ACROSS CELLS</span></div>
  <div class="ctlbar r" id="fed-prof-ctl">
    <div class="grp"><span class="lbl">X 정렬</span>
      <button class="btn active" data-ord="severity">심각도순</button>
      <button class="btn" data-ord="key">셀 KEY</button>
      <button class="btn" data-ord="cat">카테고리 밴드</button></div>
    <div class="grp"><span class="lbl">모드</span>
      <button class="btn active" data-mode="abs">절대</button>
      <button class="btn" data-mode="delta">Δ vs BASE</button>
      <button class="btn" data-mode="log">LOG</button></div>
    <div class="grp fed-legend" id="fed-legend" style="margin-left:auto"></div>
  </div>
  <div class="panel r">
    <div class="ph"><span class="pt">전개 프로파일</span>
      <span class="pd" id="fed-prof-sub">hover = crosshair &middot; click = probe</span></div>
    <div class="fed-prof-wrap"><svg id="fed-prof"></svg><div class="fed-tip" id="fed-tip"></div></div>
    <div class="pcap">공간 인접성을 버리고 크기 비교에 집중한 뷰다. 회색 점선 구간과 X축 아래 빗금 밴드는
      신뢰 게이트 미통과(미판정)를 뜻하며, 값을 0 으로 채우지 않는다.</div>
  </div>
</section>
"""

_S3_HEAD = """
<section class="page" id="s3">
  <div class="page-head r"><span class="num">03</span>
    <span class="tagline">COMPOSITE &middot; MAPS</span>
    <span class="ttl">합성 지도 &mdash; 어디에 몰렸나</span>
    <span class="sub">WINNER / TREND / DELTA / SPREAD</span></div>
  <div class="map-grid">
"""

_S3_WINNER = """
    <div class="panel r"><div class="ph"><span class="pt">WINNER MAP</span>
        <span class="pd">색 = 최악 리비전 &middot; 명도 = 값</span></div>
      <svg id="fed-map-winner"></svg>
      <div class="fed-legend" id="fed-map-winner-lg" style="margin-top:8px"></div>
      <div class="pcap">각 셀에서 가장 나쁜 값을 낸 리비전의 고정색이다. 밝을수록 그 최악값이 크다.</div></div>
"""

_S3_TREND = """
    <div class="panel r"><div class="ph"><span class="pt">TREND MAP</span>
        <span class="pd">파랑 = 개선 &middot; 빨강 = 악화</span></div>
      <svg id="fed-map-trend"></svg>
      <div class="map-bar"><span>개선</span><span class="grad div"></span><span>악화</span></div>
      <div class="pcap">리비전 순서에 대한 정규화 기울기다. 회색은 변화 없음이다.</div></div>
"""

_S3_TREND_HIDDEN = """
    <div class="panel r"><div class="ph"><span class="pt">TREND MAP</span>
        <span class="pd">N=2 강등</span></div>
      <div class="empty">리비전이 2개면 TREND 는 Δ 와 같은 정보다. 중복을 피해 숨겼다.</div></div>
"""

_S3_DELTA = """
    <div class="panel r"><div class="ph"><span class="pt">Δ MAP (vs BASELINE)</span>
        <span class="pd"><select id="fed-dmap-sel"></select></span></div>
      <svg id="fed-map-delta"></svg>
      <div class="map-bar"><span>개선</span><span class="grad div"></span><span>악화</span></div>
      <div class="pcap">모든 리비전이 같은 스케일·같은 기준을 쓴다. 미판정 셀은 빗금이며 수치를 만들지 않는다.</div></div>
"""

_S3_SPREAD = """
    <div class="panel r"><div class="ph"><span class="pt">SPREAD MAP</span>
        <span class="pd">max &minus; min</span></div>
      <svg id="fed-map-spread"></svg>
      <div class="map-bar"><span>낮음</span><span class="grad seq"></span><span>높음</span></div>
      <div class="pcap">리비전 간 편차가 큰 셀이다. 재검토 1순위 방향을 가리킨다.</div></div>
"""

_S3_TAIL = """
  </div>
</section>
"""

_S4 = """
<section class="page" id="s4">
  <div class="page-head r"><span class="num">04</span>
    <span class="tagline">LINKED &middot; PROBE</span>
    <span class="ttl">프로브 &mdash; 한 셀의 리비전별 값</span>
    <span class="sub" id="fed-probe-key">&mdash;</span></div>
  <div class="probe-grid">
    <div class="panel r"><div class="ph"><span class="pt">리비전별 값</span>
        <span class="pd" id="fed-probe-sub">&mdash;</span></div>
      <div class="probe-bars"><svg id="fed-probe-bars"></svg></div>
      <div class="pcap">프로파일이나 지도 어디에서 클릭해도 이 패널로 모인다.</div></div>
    <div class="panel r"><div class="ph"><span class="pt">수치 / 거동 / 신뢰</span>
        <span class="pd">value &middot; Δ &middot; Δ% &middot; behavior &middot; trust</span></div>
      <div id="fed-probe-tbl"></div></div>
  </div>
</section>
"""

_S5 = """
<section class="page" id="s5">
  <div class="page-head r"><span class="num">05</span>
    <span class="tagline">PART &middot; TREND</span>
    <span class="ttl">파트별 추이 &mdash; 어떤 부품이 나빠졌나</span>
    <span class="sub">MATCHED PARTS ACROSS REVISIONS</span></div>
  <div class="panel r">
    <div class="ph"><span class="pt">파트 추이 테이블</span>
      <span class="pd">헤더 클릭 = 정렬 &middot; 이름 hover = 리비전별 원본명</span></div>
    <table class="dt" id="fed-part-tbl"><thead><tr id="fed-part-head"></tr></thead><tbody></tbody></table>
    <div class="pcap">스파크라인은 리비전 순 worst 추이다. 범프 미니차트는 worst 순위 이동이며 교차는 설계 변경의 부작용 신호다.</div>
  </div>
</section>
"""

_S7 = """
<section class="page" id="s7">
  <div class="page-head r"><span class="num">07</span>
    <span class="tagline">PART &times; CELL</span>
    <span class="ttl">파트×셀 Δ 매트릭스</span>
    <span class="sub">LOCAL REGRESSION DETECTOR</span></div>
  <div class="panel r">
    <div class="ph"><span class="pt">Δ% 매트릭스</span>
      <span class="pd">엔진 제공 Δ% (vs baseline) &middot; 셀 클릭 = probe</span></div>
    <div class="mtx-wrap"><svg id="fed-mtx"></svg></div>
    <div class="map-bar"><span>개선</span><span class="grad div"></span><span>악화</span></div>
    <div class="pcap">행 = 매칭 파트, 열 = 셀이다. 회색 빗금은 Δ 미판정이며 0 으로 위장하지 않는다.</div>
  </div>
</section>
"""

_S_EMPTY = """
<section class="page" id="s0empty">
  <div class="page-head r"><span class="num">00</span>
    <span class="tagline">NO &middot; DATA</span>
    <span class="ttl">비교 셀 데이터 없음</span>
    <span class="sub">GRACEFUL DEGRADATION</span></div>
  <div class="panel r"><div class="empty">cells 가 비어 있어 프로파일 · 합성 지도 · 프로브를 그릴 수 없다.
    빈 차트를 0 으로 채우지 않고 섹션 자체를 강등했다.</div></div>
</section>
"""


# --------------------------------------------------------------------------
# JS
# --------------------------------------------------------------------------
_JS = r"""
'use strict';
var DATA = JSON.parse(document.getElementById('fed-data').textContent);
// 계약 정규화 — 엔진(compare.py)이 내는 풍부한 구조를 렌더가 쓰는 평면 형태로.
// 엔진: spread={min,max,range,cv,stdev}, part_matrix={cells,rows[{canonical,delta_pct}]},
//       revisions[].index, cells[].gated. 구 샘플(단순형)도 그대로 통과시킨다.
(function normalizeContract() {
  (DATA.revisions || []).forEach(function (r, i) {
    if (r.idx === undefined) r.idx = (r.index !== undefined ? r.index : i);
  });
  (DATA.cells || []).forEach(function (c) {
    if (c.spread && typeof c.spread === 'object') {
      c.spread_detail = c.spread;
      c.spread = (c.spread.range !== undefined ? c.spread.range : c.spread.max - c.spread.min);
    }
    if (c.trust_ok === undefined && c.gated !== undefined) c.trust_ok = !c.gated;
  });
  var pm = DATA.part_matrix;
  if (pm && !pm.parts && (pm.rows || []).length) {
    pm.parts = pm.rows.map(function (r) { return r.canonical; });
    pm.delta_pct = pm.rows.map(function (r) { return r.delta_pct || []; });
  }
})();
var REVS  = DATA.revisions || [];
var NREV  = REVS.length;
var CELLS = DATA.cells || [];
var PARTS = DATA.parts || [];
var PAL = __PALETTE__;
var BASE = Math.min(Math.max(parseInt(DATA.baseline_idx || 0, 10) || 0, 0), Math.max(NREV - 1, 0));
var RLBL = REVS.map(function (r, i) { return (r && r.label) || ('REV' + (i + 1)); });
var GDIV = (typeof DATA.g_divisor === 'number' && DATA.g_divisor > 0) ? DATA.g_divisor : 0;
var UL   = DATA.unit_labels || {};
var VUNIT = GDIV ? 'G' : (UL.acc || '');
var RAWU  = UL.acc || '';
var NS = 'http://www.w3.org/2000/svg';
var ST = { ord: 'severity', mode: 'abs', probe: null, dmap: (BASE === 0 ? Math.min(1, NREV - 1) : 0),
           psort: 'delta', pdir: -1, mtx: (BASE === 0 ? Math.min(1, NREV - 1) : 0) };

function rc(i) { return PAL[i % PAL.length]; }
function isN(v) { return typeof v === 'number' && isFinite(v); }
function gv(v) { return isN(v) ? (GDIV ? v / GDIV : v) : null; }
function fnum(v, d) {
  if (!isN(v)) return '—';
  d = (d === undefined) ? 0 : d;
  return v.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
}
function fpct(v, d) { return isN(v) ? (v >= 0 ? '+' : '') + fnum(v, d === undefined ? 1 : d) + '%' : '—'; }
function sv(t, a) { var e = document.createElementNS(NS, t); for (var k in (a || {})) e.setAttribute(k, a[k]); return e; }
function tx(e, s) { e.appendChild(document.createTextNode(String(s))); return e; }
function clr(e) { while (e && e.firstChild) e.removeChild(e.firstChild); }
function elx(t, cls, s) { var e = document.createElement(t); if (cls) e.className = cls; if (s !== undefined) e.textContent = String(s); return e; }

/* ---- 색 ---- */
function hx(c) { c = c.replace('#', ''); return [parseInt(c.slice(0, 2), 16), parseInt(c.slice(2, 4), 16), parseInt(c.slice(4, 6), 16)]; }
function mix(a, b, t) {
  var A = hx(a), B = hx(b); t = Math.max(0, Math.min(1, t));
  return 'rgb(' + A.map(function (v, i) { return Math.round(v + (B[i] - v) * t); }).join(',') + ')';
}
var NEUTRAL = '#232839';
function diverge(t) {
  if (!isN(t)) return '#2a3048';
  var a = Math.min(1, Math.abs(t));
  return t < 0 ? mix(NEUTRAL, '#3d8bff', 0.12 + 0.88 * a) : mix(NEUTRAL, '#ff3854', 0.12 + 0.88 * a);
}
var SEQ = ['#141827', '#2b4a7a', '#2190a0', '#7ec96a', '#fde725'];
function seq(t) {
  if (!isN(t)) return '#2a3048';
  t = Math.max(0, Math.min(1, t));
  var p = t * (SEQ.length - 1), i = Math.min(SEQ.length - 2, Math.floor(p));
  return mix(SEQ[i], SEQ[i + 1], p - i);
}

/* ---- 정규화 상수 ---- */
var NORM = (function () {
  var vmax = 0, tmax = 0, smax = 0, dmax = 0;
  CELLS.forEach(function (c) {
    (c.per_rev || []).forEach(function (p) { if (p && isN(p.value)) vmax = Math.max(vmax, Math.abs(p.value)); });
    if (isN(c.trend)) tmax = Math.max(tmax, Math.abs(c.trend));
    if (isN(c.spread)) smax = Math.max(smax, c.spread);
    (c.delta_pct || []).forEach(function (d) { if (isN(d)) dmax = Math.max(dmax, Math.abs(d)); });
  });
  return { vmax: vmax || 1, tmax: tmax || 1, smax: smax || 1, dmax: dmax || 1 };
})();

/* ---- 셀 정렬 ---- */
function baseVal(c) { var p = (c.per_rev || [])[BASE]; return (p && isN(p.value)) ? p.value : -Infinity; }
function orderedCells() {
  var a = CELLS.slice();
  if (ST.ord === 'key') {
    a.sort(function (p, q) { return String(p.key).localeCompare(String(q.key)); });
  } else if (ST.ord === 'cat') {
    a.sort(function (p, q) {
      var cp = String(p.category || ''), cq = String(q.category || '');
      if (cp !== cq) return cp.localeCompare(cq);
      return baseVal(q) - baseVal(p);
    });
  } else {
    a.sort(function (p, q) { return baseVal(q) - baseVal(p); });
  }
  return a;
}

/* ================= s2 UNROLLED PROFILE ================= */
var PW = 1240, PH = 400, PM = { l: 74, r: 16, t: 18, b: 62 };
function profVal(c, r) {
  if (ST.mode === 'delta') { var d = (c.delta_pct || [])[r]; return isN(d) ? d : null; }
  var p = (c.per_rev || [])[r];
  var v = p && isN(p.value) ? gv(p.value) : null;
  if (v === null) return null;
  if (ST.mode === 'log') return v > 0 ? Math.log10(v) : null;
  return v;
}
function yLabel() {
  if (ST.mode === 'delta') return 'Δ% vs baseline';
  if (ST.mode === 'log') return 'log10(' + (VUNIT || 'value') + ')';
  return VUNIT || 'value';
}
function niceTicks(lo, hi, n) {
  if (!(isFinite(lo) && isFinite(hi)) || lo === hi) { hi = lo + 1; }
  var span = hi - lo, step = Math.pow(10, Math.floor(Math.log10(span / n)));
  var err = span / n / step;
  if (err >= 7.5) step *= 10; else if (err >= 3.5) step *= 5; else if (err >= 1.5) step *= 2;
  var out = [], v = Math.ceil(lo / step) * step;
  for (; v <= hi + step * 0.001 && out.length < 20; v += step) out.push(v);
  return out;
}
/* ---- tier 축소 (engine: tiers.py) ----
   DATA.profile_cells 가 있으면 프로파일은 그 부분집합만 그리고, 나머지는
   DATA.profile_aggregate 의 min/median/max 밴드로 배경에 깐다. cells[] 자체는
   축소되지 않으므로 지도·probe 는 전량을 그대로 쓴다. */
var PKEYS = (DATA.profile_cells && DATA.profile_cells.length) ? DATA.profile_cells : null;
var PSET = null;
if (PKEYS) { PSET = {}; PKEYS.forEach(function (k) { PSET[String(k)] = 1; }); }
var PAGG = DATA.profile_aggregate || null;
function bandY(v) {
  /* 집계 밴드 원본값 → 현재 모드의 y 좌표계 값 (profVal 과 같은 변환) */
  if (!isN(v)) return null;
  if (ST.mode === 'delta') return v;
  var g = gv(v);
  if (ST.mode === 'log') return (g > 0) ? Math.log10(g) : null;
  return g;
}
function profBand(r) {
  /* 리비전 r 의 집계 밴드 [lo, mid, hi] — 없으면 null */
  if (!PAGG) return null;
  var src = (ST.mode === 'delta') ? PAGG.delta_pct : PAGG.value;
  if (!src) return null;
  var lo = bandY((src.min || [])[r]), hi = bandY((src.max || [])[r]), mid = bandY((src.median || [])[r]);
  if (!isN(lo) || !isN(hi)) return null;
  return [Math.min(lo, hi), mid, Math.max(lo, hi)];
}
var PROF = { cells: [], x: null, y: null };
function renderProfile() {
  var s = document.getElementById('fed-prof');
  if (!s || !CELLS.length) return;
  clr(s);
  s.setAttribute('viewBox', '0 0 ' + PW + ' ' + PH);
  var cells = orderedCells();
  if (PSET) cells = cells.filter(function (c) { return PSET[String(c.key)]; });
  PROF.cells = cells;
  var n = cells.length;
  var lo = Infinity, hi = -Infinity;
  cells.forEach(function (c) {
    for (var r = 0; r < NREV; r++) { var v = profVal(c, r); if (isN(v)) { lo = Math.min(lo, v); hi = Math.max(hi, v); } }
  });
  // 밴드가 축 밖으로 잘리지 않도록 도메인에 포함한다.
  for (var rb = 0; rb < NREV; rb++) {
    var bd = profBand(rb);
    if (bd) { lo = Math.min(lo, bd[0]); hi = Math.max(hi, bd[2]); }
  }
  if (!isFinite(lo)) { lo = 0; hi = 1; }
  if (ST.mode === 'delta') { lo = Math.min(lo, 0); hi = Math.max(hi, 0); }
  if (ST.mode === 'abs') lo = Math.min(lo, 0);
  var pad = (hi - lo) * 0.08 || 1;
  lo -= pad; hi += pad;
  var iw = PW - PM.l - PM.r, ih = PH - PM.t - PM.b, step = iw / Math.max(n, 1);
  function X(i) { return PM.l + (i + 0.5) * step; }
  function Y(v) { return PM.t + ih - (v - lo) / (hi - lo) * ih; }
  PROF.x = X; PROF.y = Y; PROF.step = step; PROF.n = n;

  var defs = sv('defs');
  var pat = sv('pattern', { id: 'prof-hatch', width: 7, height: 7, patternUnits: 'userSpaceOnUse', patternTransform: 'rotate(45)' });
  pat.appendChild(sv('rect', { width: 7, height: 7, fill: '#14182a' }));
  pat.appendChild(sv('line', { x1: 0, y1: 0, x2: 0, y2: 7, stroke: '#5c6383', 'stroke-width': 2.2 }));
  defs.appendChild(pat); s.appendChild(defs);

  // 카테고리 밴드
  if (ST.ord === 'cat') {
    var start = 0;
    for (var i = 0; i <= n; i++) {
      var cur = i < n ? String(cells[i].category || '') : null;
      var prev = String(cells[start].category || '');
      if (i === n || cur !== prev) {
        var x0 = PM.l + start * step, x1 = PM.l + i * step;
        s.appendChild(sv('rect', { x: x0, y: PM.t, width: Math.max(x1 - x0, 0), height: ih,
          fill: (start / Math.max(1, n) * 10 % 2 < 1) ? 'rgba(255,255,255,0.018)' : 'rgba(77,214,255,0.03)' }));
        var lb = sv('text', { x: (x0 + x1) / 2, y: PM.t + 12, fill: '#b46eff', 'font-size': 10, 'text-anchor': 'middle' });
        s.appendChild(tx(lb, prev || 'n/a'));
        start = i;
      }
    }
  }
  // y grid
  niceTicks(lo, hi, 5).forEach(function (t) {
    var y = Y(t);
    s.appendChild(sv('line', { x1: PM.l, y1: y, x2: PW - PM.r, y2: y,
      stroke: (ST.mode === 'delta' && Math.abs(t) < 1e-9) ? '#8894b8' : 'rgba(255,255,255,0.05)',
      'stroke-width': (ST.mode === 'delta' && Math.abs(t) < 1e-9) ? 1.3 : 1 }));
    var lb2 = sv('text', { x: PM.l - 8, y: y + 3.5, fill: '#5c6383', 'font-size': 10, 'text-anchor': 'end',
      'font-family': 'JetBrains Mono, monospace' });
    s.appendChild(tx(lb2, fnum(t, (Math.abs(hi - lo) < 20) ? 2 : 0)));
  });
  var yl = sv('text', { x: 14, y: PM.t + ih / 2, fill: '#aab2cf', 'font-size': 10.5,
    transform: 'rotate(-90 14 ' + (PM.t + ih / 2) + ')', 'text-anchor': 'middle' });
  s.appendChild(tx(yl, yLabel()));
  s.appendChild(sv('line', { x1: PM.l, y1: PM.t + ih, x2: PW - PM.r, y2: PM.t + ih, stroke: 'rgba(255,255,255,0.15)' }));

  // 집계 밴드 (tier 축소로 개별 표시하지 않는 셀들의 리비전별 min~max + median)
  if (PAGG && PAGG.n) {
    for (var rg = 0; rg < NREV; rg++) {
      var bnd = profBand(rg);
      if (!bnd) continue;
      var y0 = Y(bnd[2]), y1 = Y(bnd[0]);
      s.appendChild(sv('rect', { x: PM.l, y: Math.min(y0, y1), width: iw,
        height: Math.max(Math.abs(y1 - y0), 1), fill: rc(rg), 'fill-opacity': 0.055 }));
      if (isN(bnd[1])) {
        s.appendChild(sv('line', { x1: PM.l, y1: Y(bnd[1]), x2: PW - PM.r, y2: Y(bnd[1]),
          stroke: rc(rg), 'stroke-width': 1, 'stroke-opacity': 0.4, 'stroke-dasharray': '6,5' }));
      }
    }
    var agl = sv('text', { x: PW - PM.r - 2, y: PM.t + 11, fill: '#8894b8', 'font-size': 9.5,
      'text-anchor': 'end' });
    s.appendChild(tx(agl, '반투명 밴드 = 미표시 ' + PAGG.n + '셀의 리비전별 min~max (점선 = median)'));
  }

  // 미판정 밴드
  cells.forEach(function (c, i) {
    if (c.trust_ok) return;
    s.appendChild(sv('rect', { x: PM.l + i * step, y: PM.t + ih + 2, width: step, height: 10,
      fill: 'url(#prof-hatch)', opacity: 0.85 }));
  });
  var TIER = DATA.tier || {};
  var capTxt = '빗금 = 신뢰 게이트 미통과(미판정) · 셀 ' + n + '개';
  if (PSET && CELLS.length > n) {
    capTxt = '빗금 = 신뢰 게이트 미통과(미판정) · ' + CELLS.length + '개 중 ' + n +
      '개 표시 (나머지 ' + (CELLS.length - n) + '개는 집계 밴드)' +
      (TIER.name ? ' · tier ' + TIER.name : '');
  }
  var bl = sv('text', { x: PM.l, y: PM.t + ih + 30, fill: '#5c6383', 'font-size': 9.5 });
  s.appendChild(tx(bl, capTxt));

  // x 라벨 (과밀 방지)
  var everyN = Math.max(1, Math.ceil(n / 22));
  cells.forEach(function (c, i) {
    if (i % everyN) return;
    var t2 = sv('text', { x: X(i), y: PM.t + ih + 46, fill: '#5c6383', 'font-size': 9,
      'text-anchor': 'end', 'font-family': 'JetBrains Mono, monospace',
      transform: 'rotate(-38 ' + X(i) + ' ' + (PM.t + ih + 46) + ')' });
    s.appendChild(tx(t2, String(c.label || c.key)));
  });

  // 리비전 선
  var lw = NREV >= 4 ? 1.4 : 2.0, op = NREV >= 4 ? 0.78 : 0.95;
  for (var r2 = 0; r2 < NREV; r2++) {
    for (var i2 = 0; i2 < n - 1; i2++) {
      var va = profVal(cells[i2], r2), vb = profVal(cells[i2 + 1], r2);
      if (!isN(va) || !isN(vb)) continue;
      var bad = !cells[i2].trust_ok || !cells[i2 + 1].trust_ok;
      var at = { x1: X(i2), y1: Y(va), x2: X(i2 + 1), y2: Y(vb),
        stroke: bad ? '#5c6383' : rc(r2), 'stroke-width': bad ? 1.1 : lw,
        'stroke-opacity': bad ? 0.7 : op, 'stroke-linecap': 'round' };
      if (bad) at['stroke-dasharray'] = '3,3';
      s.appendChild(sv('line', at));
    }
    if (n <= 90) {
      cells.forEach(function (c, i3) {
        var v = profVal(c, r2); if (!isN(v)) return;
        s.appendChild(sv('circle', { cx: X(i3), cy: Y(v), r: NREV >= 4 ? 1.9 : 2.5,
          fill: c.trust_ok ? rc(r2) : '#5c6383', 'fill-opacity': c.trust_ok ? 1 : 0.6 }));
      });
    }
  }
  // 선택 셀 마커
  var sel = cells.findIndex(function (c) { return c.key === ST.probe; });
  if (sel >= 0) {
    s.appendChild(sv('line', { id: 'fed-prof-sel', x1: X(sel), y1: PM.t, x2: X(sel), y2: PM.t + ih,
      stroke: '#4dd6ff', 'stroke-width': 1.2, 'stroke-dasharray': '2,3', 'stroke-opacity': 0.8 }));
  }
  var cross = sv('line', { id: 'fed-cross', x1: 0, y1: PM.t, x2: 0, y2: PM.t + ih,
    stroke: '#e6ebff', 'stroke-width': 1, 'stroke-opacity': 0 });
  s.appendChild(cross);
  var hit = sv('rect', { x: PM.l, y: PM.t, width: iw, height: ih, fill: 'transparent', style: 'cursor:crosshair' });
  s.appendChild(hit);
  hit.addEventListener('mousemove', onProfMove);
  hit.addEventListener('mouseleave', onProfLeave);
  hit.addEventListener('click', onProfClick);
  document.getElementById('fed-prof-sub').textContent =
    (PSET && CELLS.length > n ? ('셀 ' + CELLS.length + '개 중 ' + n + '개 표시')
                              : ('셀 ' + n + '개')) +
    ' · ' + NREV + '개 리비전 · ' + yLabel();
}
function profIndexFromEvent(ev) {
  var s = document.getElementById('fed-prof');
  var rect = s.getBoundingClientRect();
  var sc = rect.width / PW;
  var vx = (ev.clientX - rect.left) / sc;
  var i = Math.floor((vx - PM.l) / PROF.step);
  return Math.max(0, Math.min(PROF.n - 1, i));
}
function onProfMove(ev) {
  var i = profIndexFromEvent(ev), c = PROF.cells[i];
  if (!c) return;
  var cr = document.getElementById('fed-cross');
  if (cr) { cr.setAttribute('x1', PROF.x(i)); cr.setAttribute('x2', PROF.x(i)); cr.setAttribute('stroke-opacity', 0.35); }
  var tip = document.getElementById('fed-tip');
  clr(tip);
  var h = elx('div', 'tt', String(c.label || c.key) + (c.category ? ' · ' + c.category : ''));
  tip.appendChild(h);
  for (var r = 0; r < NREV; r++) {
    var row = elx('div', 'tr');
    var nm = elx('span', null, RLBL[r]);
    nm.style.color = rc(r);
    var v = profVal(c, r);
    var vs = isN(v) ? (ST.mode === 'delta' ? fpct(v) : fnum(v, ST.mode === 'log' ? 2 : 0)) : '—';
    var pr = (c.per_rev || [])[r] || {};
    row.appendChild(nm);
    row.appendChild(elx('b', null, vs));
    row.title = isN(pr.value) ? ('raw ' + pr.value + ' ' + RAWU) : '데이터 없음';
    tip.appendChild(row);
  }
  if (!c.trust_ok) {
    var bt0 = ((c.per_rev || [])[BASE] || {}).trust || {};
    tip.appendChild(elx('div', 'trust-no', '미판정 — ' + (bt0.reason || 'trust gate')));
  }
  var wrap = document.getElementById('fed-prof').parentNode;
  var wr = wrap.getBoundingClientRect();
  tip.classList.add('on');
  var lx = ev.clientX - wr.left + 14, ly = ev.clientY - wr.top + 10;
  if (lx + tip.offsetWidth > wr.width) lx = ev.clientX - wr.left - tip.offsetWidth - 14;
  tip.style.left = lx + 'px'; tip.style.top = ly + 'px';
}
function onProfLeave() {
  var cr = document.getElementById('fed-cross');
  if (cr) cr.setAttribute('stroke-opacity', 0);
  document.getElementById('fed-tip').classList.remove('on');
}
function onProfClick(ev) {
  var c = PROF.cells[profIndexFromEvent(ev)];
  if (c) selectCell(c.key);
}

/* ================= s3 MAPS ================= */
var MAPW = 360, MAPH = 290, MPAD = 30;
var LAYOUT = null;
function mollweide(lonDeg, latDeg, R) {
  var lat = Math.max(-89.999, Math.min(89.999, latDeg)) * Math.PI / 180;
  var lon = lonDeg * Math.PI / 180, th = lat;
  for (var i = 0; i < 14; i++) {
    var den = 2 + 2 * Math.cos(2 * th);
    if (Math.abs(den) < 1e-9) break;
    var d = (2 * th + Math.sin(2 * th) - Math.PI * Math.sin(lat)) / den;
    th -= d; if (Math.abs(d) < 1e-9) break;
  }
  return [R * 2 * Math.SQRT2 / Math.PI * lon * Math.cos(th), R * Math.SQRT2 * Math.sin(th)];
}
function buildLayout() {
  var hasXY = CELLS.length && CELLS.every(function (c) { return isN(c.x) && isN(c.y); });
  var hasRP = CELLS.length && CELLS.every(function (c) { return isN(c.roll) && isN(c.pitch); });
  if (DATA.kind === 'sphere' && hasRP) {
    var R = (MAPW - 2 * MPAD) / (4 * Math.SQRT2);
    return { type: 'moll', R: R, note: 'Mollweide 등면적 투영 (roll=경도, pitch=위도)',
      items: CELLS.map(function (c) {
        var lon = ((c.roll + 180) % 360 + 360) % 360 - 180;
        var p = mollweide(lon, c.pitch, R);
        return { c: c, shape: 'circle', cx: MAPW / 2 + p[0], cy: MAPH / 2 - p[1], rr: 7 };
      }) };
  }
  if (hasXY) {
    var xs = [], ys = [];
    CELLS.forEach(function (c) { if (xs.indexOf(c.x) < 0) xs.push(c.x); if (ys.indexOf(c.y) < 0) ys.push(c.y); });
    xs.sort(function (a, b) { return a - b; }); ys.sort(function (a, b) { return a - b; });
    var cw = (MAPW - 2 * MPAD) / xs.length, ch = (MAPH - 2 * MPAD) / ys.length;
    return { type: 'grid', xs: xs, ys: ys, note: 'X-Y 격자 (' + xs.length + '×' + ys.length + ')',
      items: CELLS.map(function (c) {
        var ix = xs.indexOf(c.x), iy = ys.indexOf(c.y);
        var x = MPAD + ix * cw, y = MPAD + (ys.length - 1 - iy) * ch;
        return { c: c, shape: 'rect', x: x + 1, y: y + 1, w: Math.max(cw - 2, 1), h: Math.max(ch - 2, 1),
          cx: x + cw / 2, cy: y + ch / 2 };
      }) };
  }
  var n = CELLS.length, cols = Math.max(1, Math.ceil(Math.sqrt(n))), rows = Math.ceil(n / cols);
  var gw = (MAPW - 2 * MPAD) / cols, gh = (MAPH - 2 * MPAD) / rows;
  return { type: 'index', note: '좌표 없음 — 인덱스 격자로 강등',
    items: CELLS.map(function (c, i) {
      var x = MPAD + (i % cols) * gw, y = MPAD + Math.floor(i / cols) * gh;
      return { c: c, shape: 'rect', x: x + 1, y: y + 1, w: Math.max(gw - 2, 1), h: Math.max(gh - 2, 1),
        cx: x + gw / 2, cy: y + gh / 2 };
    }) };
}
function mapColor(mode, c) {
  if (mode === 'winner') {
    var w = c.winner;
    if (!isN(w)) return { fill: '#2a3048', na: true };
    var best = 0;
    (c.per_rev || []).forEach(function (p) { if (p && isN(p.value)) best = Math.max(best, Math.abs(p.value)); });
    return { fill: mix('#141827', rc(w), 0.22 + 0.78 * Math.min(1, best / NORM.vmax)), na: false };
  }
  if (mode === 'trend') return isN(c.trend) ? { fill: diverge(c.trend / NORM.tmax), na: false } : { fill: '#2a3048', na: true };
  if (mode === 'spread') return isN(c.spread) ? { fill: seq(c.spread / NORM.smax), na: false } : { fill: '#2a3048', na: true };
  var d = (c.delta_pct || [])[ST.dmap];
  return isN(d) ? { fill: diverge(d / NORM.dmax), na: false } : { fill: '#20263a', na: true };
}
function mapValueText(mode, c) {
  if (mode === 'winner') return isN(c.winner) ? RLBL[c.winner] : '미판정';
  if (mode === 'trend') return isN(c.trend) ? fnum(c.trend, 3) : '미판정';
  if (mode === 'spread') return isN(c.spread) ? fnum(gv(c.spread), 0) + ' ' + VUNIT : '미판정';
  var d = (c.delta_pct || [])[ST.dmap];
  return isN(d) ? fpct(d) : '미판정';
}
function renderMap(id, mode) {
  var s = document.getElementById(id);
  if (!s || !LAYOUT) return;
  clr(s);
  s.setAttribute('viewBox', '0 0 ' + MAPW + ' ' + MAPH);
  var defs = sv('defs');
  var pid = id + '-hatch';
  var pat = sv('pattern', { id: pid, width: 6, height: 6, patternUnits: 'userSpaceOnUse', patternTransform: 'rotate(45)' });
  pat.appendChild(sv('rect', { width: 6, height: 6, fill: '#181c2c' }));
  pat.appendChild(sv('line', { x1: 0, y1: 0, x2: 0, y2: 6, stroke: '#5c6383', 'stroke-width': 2 }));
  defs.appendChild(pat); s.appendChild(defs);

  if (LAYOUT.type === 'moll') {
    var R = LAYOUT.R;
    s.appendChild(sv('ellipse', { cx: MAPW / 2, cy: MAPH / 2, rx: 2 * Math.SQRT2 * R, ry: Math.SQRT2 * R,
      fill: 'none', stroke: 'rgba(255,255,255,0.12)' }));
    s.appendChild(sv('line', { x1: MAPW / 2 - 2 * Math.SQRT2 * R, y1: MAPH / 2, x2: MAPW / 2 + 2 * Math.SQRT2 * R,
      y2: MAPH / 2, stroke: 'rgba(255,255,255,0.07)' }));
  }
  LAYOUT.items.forEach(function (it) {
    var col = mapColor(mode, it.c);
    var bad = !it.c.trust_ok;
    var at = { fill: col.fill, class: 'map-cell' + (it.c.key === ST.probe ? ' sel' : ''),
      stroke: 'rgba(0,0,0,0.35)', 'stroke-width': 0.5 };
    var node, node2 = null;
    if (it.shape === 'circle') {
      at.cx = it.cx; at.cy = it.cy; at.r = it.rr;
      node = sv('circle', at);
      if (bad || col.na) node2 = sv('circle', { cx: it.cx, cy: it.cy, r: it.rr, fill: 'url(#' + pid + ')',
        'fill-opacity': 0.65, 'pointer-events': 'none' });
    } else {
      at.x = it.x; at.y = it.y; at.width = it.w; at.height = it.h;
      node = sv('rect', at);
      if (bad || col.na) node2 = sv('rect', { x: it.x, y: it.y, width: it.w, height: it.h,
        fill: 'url(#' + pid + ')', 'fill-opacity': 0.65, 'pointer-events': 'none' });
    }
    node.setAttribute('data-key', it.c.key);
    var ti = sv('title');
    tx(ti, String(it.c.label || it.c.key) + '\n' + mapValueText(mode, it.c) + (bad ? '\n신뢰 게이트 미통과' : ''));
    node.appendChild(ti);
    node.addEventListener('click', function () { selectCell(it.c.key); });
    s.appendChild(node);
    if (node2) s.appendChild(node2);
  });
  var nt = sv('text', { x: 6, y: MAPH - 6, fill: '#5c6383', 'font-size': 9 });
  s.appendChild(tx(nt, LAYOUT.note));
}
function renderAllMaps() {
  renderMap('fed-map-winner', 'winner');
  if (document.getElementById('fed-map-trend')) renderMap('fed-map-trend', 'trend');
  renderMap('fed-map-delta', 'delta');
  renderMap('fed-map-spread', 'spread');
  var lg = document.getElementById('fed-map-winner-lg');
  if (lg) {
    clr(lg);
    RLBL.forEach(function (l, i) {
      var d = elx('span', 'lg');
      var sw = elx('span', 'sw'); sw.style.background = rc(i); sw.style.height = '10px'; sw.style.width = '10px';
      d.appendChild(sw); d.appendChild(elx('span', null, l));
      lg.appendChild(d);
    });
  }
}

/* ================= s4 PROBE ================= */
function selectCell(key) {
  if (!key) return;
  ST.probe = key;
  renderProbe();
  var s = document.getElementById('fed-prof');
  if (s) {
    var idx = PROF.cells.findIndex(function (c) { return c.key === key; });
    var old = document.getElementById('fed-prof-sel');
    if (old) old.parentNode.removeChild(old);
    if (idx >= 0 && PROF.x) {
      var ln = sv('line', { id: 'fed-prof-sel', x1: PROF.x(idx), y1: PM.t, x2: PROF.x(idx), y2: PH - PM.b,
        stroke: '#4dd6ff', 'stroke-width': 1.2, 'stroke-dasharray': '2,3', 'stroke-opacity': 0.8,
        'pointer-events': 'none' });
      s.appendChild(ln);
    }
  }
  ['fed-map-winner', 'fed-map-trend', 'fed-map-delta', 'fed-map-spread'].forEach(function (id) {
    var m = document.getElementById(id);
    if (!m) return;
    Array.prototype.forEach.call(m.querySelectorAll('.map-cell'), function (n) {
      if (n.getAttribute('data-key') === key) n.classList.add('sel'); else n.classList.remove('sel');
    });
  });
}
function cellByKey(k) { for (var i = 0; i < CELLS.length; i++) if (CELLS[i].key === k) return CELLS[i]; return null; }
function renderProbe() {
  var c = cellByKey(ST.probe);
  var kEl = document.getElementById('fed-probe-key');
  var sEl = document.getElementById('fed-probe-sub');
  var host = document.getElementById('fed-probe-tbl');
  var bars = document.getElementById('fed-probe-bars');
  if (!host || !bars) return;
  clr(host); clr(bars);
  if (!c) { kEl.textContent = '—'; host.appendChild(elx('div', 'empty', '선택된 셀이 없다.')); return; }
  kEl.textContent = String(c.label || c.key);
  sEl.textContent = (isN(c.x) && isN(c.y) ? ('x=' + c.x + ' · y=' + c.y) : '') +
    (c.category ? ' · ' + c.category : '') + (c.trust_ok ? '' : ' · 미판정');

  // 바 차트
  var BW = 520, BH = 42 + NREV * 34;
  bars.setAttribute('viewBox', '0 0 ' + BW + ' ' + BH);
  var vmax = 0;
  (c.per_rev || []).forEach(function (p) { if (p && isN(p.value)) vmax = Math.max(vmax, Math.abs(p.value)); });
  vmax = vmax || 1;
  for (var r = 0; r < NREV; r++) {
    var y = 22 + r * 34, p2 = (c.per_rev || [])[r] || {};
    var lab = sv('text', { x: 8, y: y + 13, fill: rc(r), 'font-size': 11, 'font-family': 'JetBrains Mono, monospace' });
    bars.appendChild(tx(lab, RLBL[r].slice(0, 16) + (r === BASE ? ' *' : '')));
    bars.appendChild(sv('rect', { x: 130, y: y, width: BW - 210, height: 18, fill: '#232839', rx: 2 }));
    if (isN(p2.value)) {
      var w = (BW - 210) * Math.min(1, Math.abs(p2.value) / vmax);
      bars.appendChild(sv('rect', { x: 130, y: y, width: Math.max(w, 1), height: 18, rx: 2,
        fill: rc(r), 'fill-opacity': (p2.trust && p2.trust.ok === false) ? 0.35 : 0.9 }));
      var vt = sv('text', { x: BW - 72, y: y + 13, fill: '#c8d4ff', 'font-size': 11,
        'font-family': 'JetBrains Mono, monospace' });
      bars.appendChild(tx(vt, fnum(gv(p2.value), 0)));
    } else {
      var nt2 = sv('text', { x: 138, y: y + 13, fill: '#5c6383', 'font-size': 10.5 });
      bars.appendChild(tx(nt2, '데이터 없음 —'));
    }
  }
  var ax = sv('text', { x: 130, y: BH - 6, fill: '#5c6383', 'font-size': 9.5 });
  bars.appendChild(tx(ax, '단위 ' + (VUNIT || 'raw') + ' · * = baseline · 흐린 막대 = 신뢰 게이트 미통과'));

  // 표
  var t = elx('table', 'dt');
  var th = elx('thead');
  var hr = document.createElement('tr');
  ['리비전', 'VALUE (' + (VUNIT || 'raw') + ')', 'Δ', 'Δ%', 'BEHAVIOR', 'TRUST'].forEach(function (h, i) {
    var e = document.createElement('th'); e.textContent = h; if (i === 0 || i >= 4) e.className = 'tl'; hr.appendChild(e);
  });
  th.appendChild(hr); t.appendChild(th);
  var tb = elx('tbody');
  for (var r3 = 0; r3 < NREV; r3++) {
    var pr = (c.per_rev || [])[r3] || {}, tr = document.createElement('tr');
    var c0 = elx('td', 'tl b', RLBL[r3] + (r3 === BASE ? '  (BASE)' : ''));
    c0.style.borderLeft = '3px solid ' + rc(r3);
    tr.appendChild(c0);
    var c1 = elx('td', 'num', isN(pr.value) ? fnum(gv(pr.value), 0) : '—');
    if (isN(pr.value)) c1.title = 'raw ' + pr.value + ' ' + RAWU;
    tr.appendChild(c1);
    var dv = (c.delta || [])[r3], dp = (c.delta_pct || [])[r3];
    tr.appendChild(elx('td', 'num', isN(dv) ? fnum(gv(dv), 0) : '—'));
    var dc = elx('td', 'dpct ' + (isN(dp) ? (dp > 0 ? 'up' : (dp < 0 ? 'dn' : 'na')) : 'na'), isN(dp) ? fpct(dp) : '—');
    tr.appendChild(dc);
    var bc = document.createElement('td'); bc.className = 'tl';
    var bb = elx('span', 'bbadge ' + (pr.behavior || 'unknown'), pr.behavior || '—');
    bc.appendChild(bb); tr.appendChild(bc);
    var trst = pr.trust || {};
    var tc = elx('td', 'tl ' + (trst.ok === false ? 'trust-no' : 'trust-yes'),
      (trst.ok === false ? '미판정' : 'OK') + (trst.reason ? ' · ' + trst.reason : ''));
    tr.appendChild(tc);
    tb.appendChild(tr);
  }
  t.appendChild(tb); host.appendChild(t);
  if (!c.trust_ok) {
    host.appendChild(elx('div', 'pcap', '이 셀은 신뢰 게이트를 통과하지 못했다. Δ 는 수치 대신 미판정으로 남긴다.'));
  }
}

/* ================= s5 PART TREND ================= */
function partDelta(p) { var d = p.delta_pct || []; return isN(d[d.length - 1]) ? d[d.length - 1] : null; }
function renderParts() {
  var tbl = document.getElementById('fed-part-tbl');
  if (!tbl || !PARTS.length) return;
  var head = document.getElementById('fed-part-head');
  clr(head);
  function th(label, key, cls) {
    var e = document.createElement('th');
    e.className = (cls || '') + (key ? ' srt' : '');
    e.textContent = label + (ST.psort === key ? (ST.pdir < 0 ? ' ▼' : ' ▲') : '');
    if (key) e.addEventListener('click', function () {
      if (ST.psort === key) ST.pdir = -ST.pdir; else { ST.psort = key; ST.pdir = -1; }
      renderParts();
    });
    return e;
  }
  head.appendChild(th('PART', 'name', 'tl'));
  RLBL.forEach(function (l, i) { head.appendChild(th(l + (i === BASE ? ' *' : ''), null)); });
  head.appendChild(th('추이', null));
  RLBL.forEach(function (l, i) { if (i !== BASE) head.appendChild(th('Δ% ' + l, null)); });
  head.appendChild(th('Δ% (최종)', 'delta'));
  head.appendChild(th('RANK', null));

  var rows = PARTS.slice();
  rows.sort(function (a, b) {
    if (ST.psort === 'name') return ST.pdir * String(a.canonical).localeCompare(String(b.canonical));
    var av = partDelta(a), bv = partDelta(b);
    if (av === null && bv === null) return 0;
    if (av === null) return 1;
    if (bv === null) return -1;
    return ST.pdir * (av - bv) * -1;
  });
  var dmax = 1;
  PARTS.forEach(function (p) { (p.delta_pct || []).forEach(function (d) { if (isN(d)) dmax = Math.max(dmax, Math.abs(d)); }); });
  var rmax = 1;
  PARTS.forEach(function (p) { (p.rank || []).forEach(function (r) { if (isN(r)) rmax = Math.max(rmax, r); }); });

  var tb = tbl.querySelector('tbody');
  clr(tb);
  rows.forEach(function (p) {
    var tr = document.createElement('tr');
    var nm = elx('td', 'tl b', p.canonical);
    var names = p.names || [];
    if (names.length && !names.every(function (n) { return n === names[0]; })) {
      nm.title = names.map(function (n, i) { return RLBL[i] + ': ' + (n || '없음'); }).join('\n');
      nm.appendChild(elx('span', 'dim', ' ✱'));
    }
    // 부분 존재(일부 리비전에 없음)는 반드시 시각화 — 값 없는 칸이 '개선'으로
    // 오독되면 안 된다. present[] 가 없으면 names/worst 로 추론.
    var pres = p.present || names.map(function (n) { return !!n; });
    var missIdx = [];
    for (var mi = 0; mi < NREV; mi++) if (pres[mi] === false) missIdx.push(mi);
    if (missIdx.length) {
      var mb = elx('span', 'miss-badge', missIdx.map(function (i) { return RLBL[i]; }).join(',') + ' 없음');
      mb.title = '이 파트는 해당 리비전 산출물에 없습니다 (매칭 실패 또는 설계 변경). '
               + '값이 비어 있는 것은 0 이 아니라 부재입니다.';
      nm.appendChild(mb);
    }
    tr.appendChild(nm);
    var w = p.worst || [];
    for (var i = 0; i < NREV; i++) tr.appendChild(elx('td', 'num', isN(w[i]) ? fnum(gv(w[i]), 0) : '—'));
    // 스파크라인
    var sc = document.createElement('td');
    sc.appendChild(sparkline(w));
    tr.appendChild(sc);
    // Δ% 리비전별
    for (var j = 0; j < NREV; j++) {
      if (j === BASE) continue;
      var d = (p.delta_pct || [])[j];
      var td = elx('td', 'num', isN(d) ? fpct(d) : '—');
      if (isN(d)) { td.style.background = diverge(d / dmax); td.style.color = '#f2f5ff'; }
      tr.appendChild(td);
    }
    var last = partDelta(p);
    var lt = elx('td', 'dpct ' + (isN(last) ? (last > 0 ? 'up' : 'dn') : 'na'), isN(last) ? fpct(last) : '—');
    tr.appendChild(lt);
    var rk = document.createElement('td');
    rk.appendChild(bump(p.rank || [], rmax));
    tr.appendChild(rk);
    tb.appendChild(tr);
  });
}
function sparkline(vals) {
  var W = 80, H = 20, s = sv('svg', { viewBox: '0 0 ' + W + ' ' + H, width: W, height: H, class: 'spark' });
  var f = vals.filter(isN);
  if (f.length < 2) { s.appendChild(tx(sv('text', { x: 2, y: 14, fill: '#5c6383', 'font-size': 9 }), '—')); return s; }
  var lo = Math.min.apply(null, f), hi = Math.max.apply(null, f), sp = (hi - lo) || 1;
  var pts = [];
  vals.forEach(function (v, i) {
    if (!isN(v)) return;
    pts.push((2 + i * (W - 4) / Math.max(1, vals.length - 1)) + ',' + (H - 3 - (v - lo) / sp * (H - 6)));
  });
  s.appendChild(sv('polyline', { points: pts.join(' '), fill: 'none', stroke: '#4dd6ff', 'stroke-width': 1.4 }));
  vals.forEach(function (v, i) {
    if (!isN(v)) return;
    s.appendChild(sv('circle', { cx: 2 + i * (W - 4) / Math.max(1, vals.length - 1),
      cy: H - 3 - (v - lo) / sp * (H - 6), r: 1.8, fill: rc(i) }));
  });
  return s;
}
function bump(ranks, rmax) {
  var W = 74, H = 20, s = sv('svg', { viewBox: '0 0 ' + W + ' ' + H, width: W, height: H, class: 'spark' });
  var f = ranks.filter(isN);
  if (!f.length) { s.appendChild(tx(sv('text', { x: 2, y: 14, fill: '#5c6383', 'font-size': 9 }), '—')); return s; }
  var pts = [];
  ranks.forEach(function (r, i) {
    if (!isN(r)) return;
    pts.push((3 + i * (W - 6) / Math.max(1, ranks.length - 1)) + ',' + (3 + r / Math.max(1, rmax) * (H - 6)));
  });
  s.appendChild(sv('polyline', { points: pts.join(' '), fill: 'none', stroke: '#b46eff', 'stroke-width': 1.3 }));
  ranks.forEach(function (r, i) {
    if (!isN(r)) return;
    s.appendChild(sv('circle', { cx: 3 + i * (W - 6) / Math.max(1, ranks.length - 1),
      cy: 3 + r / Math.max(1, rmax) * (H - 6), r: 2, fill: rc(i) }));
  });
  var moved = f.length > 1 && f[0] !== f[f.length - 1];
  var t = sv('title'); tx(t, moved ? ('순위 이동 ' + f[0] + ' → ' + f[f.length - 1]) : '순위 유지');
  s.appendChild(t);
  return s;
}

/* ================= s7 PART×CELL MATRIX ================= */
function renderMatrix() {
  var pm = DATA.part_matrix;
  var s = document.getElementById('fed-mtx');
  if (!s || !pm || !(pm.parts || []).length) return;
  clr(s);
  var parts = pm.parts || [], cols = pm.cells || [], dp = pm.delta_pct || [];
  var LW = 130, CH = 22, CW = Math.max(26, Math.min(60, 900 / Math.max(1, cols.length)));
  var W = LW + cols.length * CW + 10, H = 64 + parts.length * CH;
  s.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
  s.setAttribute('style', 'width:' + W + 'px;max-width:none');
  var defs = sv('defs');
  var pat = sv('pattern', { id: 'mtx-hatch', width: 6, height: 6, patternUnits: 'userSpaceOnUse', patternTransform: 'rotate(45)' });
  pat.appendChild(sv('rect', { width: 6, height: 6, fill: '#181c2c' }));
  pat.appendChild(sv('line', { x1: 0, y1: 0, x2: 0, y2: 6, stroke: '#5c6383', 'stroke-width': 2 }));
  defs.appendChild(pat); s.appendChild(defs);
  var dmax = 1;
  dp.forEach(function (row) { (row || []).forEach(function (d) { if (isN(d)) dmax = Math.max(dmax, Math.abs(d)); }); });
  cols.forEach(function (ck, j) {
    var t = sv('text', { x: LW + j * CW + CW / 2, y: 56, fill: '#5c6383', 'font-size': 9,
      'text-anchor': 'end', 'font-family': 'JetBrains Mono, monospace',
      transform: 'rotate(-55 ' + (LW + j * CW + CW / 2) + ' 56)' });
    s.appendChild(tx(t, String(ck)));
  });
  parts.forEach(function (pn, i) {
    var y = 64 + i * CH;
    var lt = sv('text', { x: LW - 8, y: y + 15, fill: '#aab2cf', 'font-size': 10.5, 'text-anchor': 'end' });
    s.appendChild(tx(lt, String(pn)));
    cols.forEach(function (ck, j) {
      var d = ((dp[i] || [])[j]);
      var x = LW + j * CW;
      var r = sv('rect', { x: x + 1, y: y + 1, width: CW - 2, height: CH - 2, rx: 2,
        fill: isN(d) ? diverge(d / dmax) : 'url(#mtx-hatch)', class: 'map-cell' });
      r.setAttribute('data-key', ck);
      var ti = sv('title');
      tx(ti, pn + ' × ' + ck + '\n' + (isN(d) ? fpct(d) : 'Δ 미판정'));
      r.appendChild(ti);
      r.addEventListener('click', function () { selectCell(ck); });
      s.appendChild(r);
      if (isN(d) && CW >= 34) {
        var vt = sv('text', { x: x + CW / 2, y: y + 15, fill: '#e8ecff', 'font-size': 8.5,
          'text-anchor': 'middle', 'font-family': 'JetBrains Mono, monospace', 'pointer-events': 'none' });
        s.appendChild(tx(vt, fnum(d, 0)));
      }
    });
  });
}

/* ================= 배선 ================= */
function buildLegend() {
  var lg = document.getElementById('fed-legend');
  if (!lg) return;
  clr(lg);
  RLBL.forEach(function (l, i) {
    var d = elx('span', 'lg');
    var sw = elx('span', 'sw'); sw.style.background = rc(i);
    d.appendChild(sw); d.appendChild(elx('span', null, l + (i === BASE ? ' *' : '')));
    lg.appendChild(d);
  });
  var na = elx('span', 'lg na');
  na.appendChild(elx('span', 'sw'));
  na.appendChild(elx('span', null, '미판정'));
  lg.appendChild(na);
  if (NREV >= 4) {
    var ctl = document.getElementById('fed-prof-ctl');
    if (ctl) ctl.classList.add('fed-sticky');
  }
}
function wireCtl() {
  Array.prototype.forEach.call(document.querySelectorAll('[data-ord]'), function (b) {
    b.addEventListener('click', function () {
      Array.prototype.forEach.call(document.querySelectorAll('[data-ord]'), function (x) { x.classList.remove('active'); });
      b.classList.add('active');
      ST.ord = b.getAttribute('data-ord');
      renderProfile(); selectCell(ST.probe);
    });
  });
  Array.prototype.forEach.call(document.querySelectorAll('[data-mode]'), function (b) {
    b.addEventListener('click', function () {
      Array.prototype.forEach.call(document.querySelectorAll('[data-mode]'), function (x) { x.classList.remove('active'); });
      b.classList.add('active');
      ST.mode = b.getAttribute('data-mode');
      renderProfile(); selectCell(ST.probe);
    });
  });
  var ds = document.getElementById('fed-dmap-sel');
  if (ds) {
    for (var i = 0; i < NREV; i++) {
      if (i === BASE) continue;
      var o = document.createElement('option');
      o.value = String(i); o.textContent = RLBL[i] + ' vs BASE';
      ds.appendChild(o);
    }
    ds.value = String(ST.dmap);
    ds.addEventListener('change', function () { ST.dmap = parseInt(ds.value, 10); renderMap('fed-map-delta', 'delta'); });
  }
}
function defaultKey() {
  var best = null, bv = -Infinity;
  CELLS.forEach(function (c) {
    if (!c.trust_ok) return;
    var v = baseVal(c);
    if (v > bv) { bv = v; best = c.key; }
  });
  return best || (CELLS[0] && CELLS[0].key) || null;
}
function reveal() {
  var els = document.querySelectorAll('.r');
  if (!('IntersectionObserver' in window)) {
    Array.prototype.forEach.call(els, function (e) { e.classList.add('in'); });
    return;
  }
  var io = new IntersectionObserver(function (ents) {
    ents.forEach(function (en) { if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target); } });
  }, { rootMargin: '0px 0px -40px 0px' });
  Array.prototype.forEach.call(els, function (e) { io.observe(e); });
}
function boot() {
  buildLegend();
  wireCtl();
  if (CELLS.length) {
    LAYOUT = buildLayout();
    renderProfile();
    renderAllMaps();
    selectCell(defaultKey());
  }
  if (PARTS.length) renderParts();
  if (DATA.part_matrix) renderMatrix();
  reveal();
}
boot();
"""


# --------------------------------------------------------------------------
# 진입점
# --------------------------------------------------------------------------
def generate_html(comparison: dict) -> str:
    """비교 결과 dict 를 단일 자립 HTML 문자열로 변환한다."""
    cmp_ = comparison if isinstance(comparison, dict) else {}
    cells = cmp_.get("cells") or []
    parts = cmp_.get("parts") or []
    pmx = cmp_.get("part_matrix") or None
    bt = cmp_.get("behavior_transitions") or {}
    n_rev = len(cmp_.get("revisions") or [])
    promoted = bool(bt.get("headline"))

    has_bt = bool(bt.get("per_rev"))
    has_mtx = bool(pmx and ((pmx.get("parts") or []) or (pmx.get("rows") or [])))
    has_fd = any(any(x.get(k) for k in ("new", "resolved", "kept"))
                 for x in _fd_list(cmp_) if not x.get("is_baseline"))

    nav = [("s1", "SUMMARY")]
    if has_bt and promoted:
        nav.append(("s6", "BEHAVIOR"))
    if cells:
        nav += [("s2", "PROFILE"), ("s3", "MAPS"), ("s4", "PROBE")]
    if parts:
        nav.append(("s5", "PARTS"))
    if has_bt and not promoted:
        nav.append(("s6", "BEHAVIOR"))
    if has_mtx:
        nav.append(("s7", "MATRIX"))
    if has_fd:
        nav.append(("s8", "FINDINGS"))
    has_cat = bool((cmp_.get("category_summary") or {}).get("categories"))
    if has_cat:
        nav.append(("s10", "CATEGORY"))
    _um = [x for x in (cmp_.get("unmatched") or []) if (x or {}).get("parts")]
    _partial = [p for p in (parts or [])
                if isinstance(p.get("present"), list) and not all(p["present"])]
    has_um = bool(_um or _partial)
    if has_um:
        nav.append(("s11", "UNMATCHED"))
    nav.append(("s9", "PROVENANCE"))

    body = [_build_topbar(cmp_, nav), _build_s1(cmp_)]
    if has_bt and promoted:
        body.append(_build_s6(cmp_, True))
    if cells:
        body.append(_S2)
        maps = [_S3_HEAD, _S3_WINNER]
        maps.append(_S3_TREND if n_rev >= 3 else _S3_TREND_HIDDEN)
        maps += [_S3_DELTA, _S3_SPREAD, _S3_TAIL]
        body.append("".join(maps))
        body.append(_S4)
    else:
        body.append(_S_EMPTY)
    if parts:
        body.append(_S5)
    if has_bt and not promoted:
        body.append(_build_s6(cmp_, False))
    if has_mtx:
        body.append(_S7)
    if has_fd:
        body.append(_build_s8(cmp_))
    if has_cat:
        body.append(_build_s10(cmp_))
    if has_um:
        body.append(_build_s11(cmp_))
    body.append(_build_s9(cmp_))
    body.append(
        '<div class="foot">KOO FEDERATE REPORT &middot; 리비전 연합 비교 &middot; '
        "sidecar 계약만으로 생성 &middot; 미판정은 0 으로 채우지 않는다</div>\n"
    )

    data_json = json.dumps(cmp_, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    js = _JS.replace("__PALETTE__", json.dumps(_PALETTE))
    title = "리비전 연합 비교 — KOO FEDERATE"

    return (
        "<!DOCTYPE html>\n<html lang=\"ko\">\n<head>\n"
        "<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"<title>{_esc(title)}</title>\n"
        "<link rel=\"icon\" href=\"data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>"
        "<rect width='64' height='64' rx='12' fill='%230e1320'/><text x='50%25' y='58%25' text-anchor='middle' "
        "font-family='monospace' font-size='28' font-weight='bold' fill='%234dd6ff'>F</text></svg>\">\n"
        "<style>\n" + _CSS + "\n</style>\n</head>\n<body>\n"
        + "".join(body)
        + '<script type="application/json" id="fed-data">' + data_json + "</script>\n"
        "<script>\n" + js + "\n</script>\n</body>\n</html>\n"
    )
