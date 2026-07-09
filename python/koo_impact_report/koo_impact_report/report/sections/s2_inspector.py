# 섹션 02 — IMPACT INSPECTOR (bi-face 응답 탐색기) HTML 템플릿 (기계적 분할, 바이트 불변)

_PAGE2 = """
<section class="page" id="s2">
  <div class="page-head r">
    <span class="num">02</span><span class="tagline">IMPACT INSPECTOR</span>
    <span class="ttl">충격 위치 = 화면, 부품 응답 = 부품 라이트업</span>
    <span class="sub">HOVER-DRIVEN BI-FACE STRESS EXPLORER</span>
  </div>

  <div class="ctlbar r">
    <div class="grp"><span class="lbl">FACE</span>
      <button class="btn active" data-ii-face="F2">FRONT &middot; F2</button>
      <button class="btn" data-ii-face="F1">BACK &middot; F1</button>
    </div>
    <div class="grp"><span class="lbl">METRIC</span>
      <button class="btn active" data-ii-metric="g">PEAK G</button>
      <button class="btn" data-ii-metric="s">&sigma;</button>
      <button class="btn" data-ii-metric="e">&epsilon;</button>
      <button class="btn" data-ii-metric="d">d</button>
    </div>
    <div class="grp"><span class="lbl">NORM</span>
      <button class="btn active" data-ii-norm="abs">ABS</button>
      <button class="btn" data-ii-norm="rel">RELATIVE</button>
    </div>
    <div class="grp ii-thresh"><span class="lbl">THRESH</span>
      <input type="range" id="ii-thresh" min="0" max="100" value="0">
      <span class="vlab" id="ii-thresh-val">0%</span>
    </div>
    <label class="ii-pin" id="ii-pin-lab">
      <input type="checkbox" id="ii-pin"> PIN
    </label>
  </div>

  <div class="ii-wrap r">
    <div class="ii-main">
      <div class="ph">
        <span class="pt">IMPACT INSPECTOR &middot; <span id="ii-face-label">FRONT (F2)</span></span>
        <span class="pd">hover impact &rarr; parts light up with their response &middot; click row to pin</span>
      </div>
      <div class="ii-canvas-wrap">
        <svg id="ii-svg" viewBox="0 0 800 600" preserveAspectRatio="xMidYMid meet"></svg>
      </div>
      <div class="ii-cbar">
        <span>0</span>
        <span class="grad"></span>
        <span id="ii-cbar-max">-</span>
        <span style="color:var(--accent);margin-left:8px" id="ii-metric-name">Peak G</span>
      </div>
    </div>
    <div class="ii-side" id="ii-side-panel">
      <div class="iibox">
        <div class="iihd">HOVERED IMPACT <span id="ii-behavior-badge"></span></div>
        <div id="ii-hover-info"><div class="ii-empty">충돌 위치 위에 마우스를 올리세요.</div></div>
        <div id="ii-traj-kpi" style="margin-top:6px"></div>
      </div>
      <div class="iibox">
        <div class="iihd">TOP AFFECTED PARTS</div>
        <div id="ii-parts-list"><div class="ii-empty">-</div></div>
      </div>
      <div class="iibox">
        <div class="iihd">IMPACTOR KE @ POSITION <span id="ii-th-sub" style="color:var(--dim);font-weight:500"></span></div>
        <svg id="ii-th-svg" class="ii-th" viewBox="0 0 200 70" preserveAspectRatio="none"></svg>
        <div style="display:flex;justify-content:space-between;font-size:8.5px;color:var(--dim);font-family:'JetBrains Mono',monospace;margin-top:2px">
          <span>0</span><span>0.5</span><span>1.0 ms</span>
        </div>
      </div>
    </div>
  </div>

  <div class="grid g-12" style="margin-top:14px">
    <div class="panel col-12 r">
      <div class="ph">
        <span class="pt">INFLUENCE MATRIX &middot; TOP-10 IMPACTS</span>
        <span class="pd">rows = worst impacts on selected face &middot; cols = parts &middot; click row = inspect</span>
      </div>
      <div id="imatrix-wrap" style="overflow-x:auto"></div>
      <div class="pcap">한 줄 = (face, position) 페어. 가로축 = 모든 부품. 셀 색 = 그 페어가 그 부품에 미친 응답.</div>
    </div>
  </div>
</section>
"""


_JS_S2 = r"""/* ===================================================================
 * Impact Inspector  (Page 2 hero + Page 1 bi-face mini/split)
 * =================================================================== */

/** Map XY (mm) into SVG viewBox coords using the device bbox + a pad. */
function _xyToVB(x, y, vbW, vbH, padPx) {
  const bb = DEVICE_BBOX;
  if (!bb) return [vbW / 2, vbH / 2];
  const w = bb.xmax - bb.xmin, h = bb.ymax - bb.ymin;
  if (w <= 0 || h <= 0) return [vbW / 2, vbH / 2];
  // preserve aspect ratio inside vbW x vbH (with padPx margin)
  const innerW = vbW - 2 * padPx, innerH = vbH - 2 * padPx;
  const scale = Math.min(innerW / w, innerH / h);
  const drawW = w * scale, drawH = h * scale;
  const ox = (vbW - drawW) / 2, oy = (vbH - drawH) / 2;
  const u = (x - bb.xmin) / w;
  const v = 1 - (y - bb.ymin) / h;  // flip Y so +y points up
  return [ox + u * drawW, oy + v * drawH];
}

/** Per-position max metric value for a given face. */
const POS_MAX_BY_METRIC = {};
function _ensurePosMax(metric) {
  if (POS_MAX_BY_METRIC[metric]) return POS_MAX_BY_METRIC[metric];
  const out = {};
  for (const r of RESULTS) {
    const k = r.face + '|' + r.pos_id;
    const v = r[metric] || 0;
    const cur = out[k];
    if (!cur || v > cur.v) {
      out[k] = { v: v, x: r.x, y: r.y, face: r.face, pos_id: r.pos_id, part_id: r.part_id, part_name: r.part_name };
    }
  }
  POS_MAX_BY_METRIC[metric] = out;
  return out;
}

/** (face, pos_id, part_id) → result row */
const RESULT_IDX = {};
for (const r of RESULTS) RESULT_IDX[r.face + '|' + r.pos_id + '|' + r.part_id] = r;

/** Footprint helpers — return centroid + bbox of a part's polygon. */
function _footprintBBox(fp) {
  if (!fp || !fp.length) return null;
  let xmin = Infinity, xmax = -Infinity, ymin = Infinity, ymax = -Infinity;
  let cx = 0, cy = 0;
  for (const pt of fp) {
    const x = pt[0], y = pt[1];
    if (x < xmin) xmin = x; if (x > xmax) xmax = x;
    if (y < ymin) ymin = y; if (y > ymax) ymax = y;
    cx += x; cy += y;
  }
  cx /= fp.length; cy /= fp.length;
  return { xmin: xmin, xmax: xmax, ymin: ymin, ymax: ymax, cx: cx, cy: cy };
}

/** Render the Impact Inspector into a target svg/container.
 *  opts = { containerId, faceCode, interactive: bool, mainPanel: bool, height: 'aspect' }
 */
function initImpactInspector(opts) {
  const faceCode = opts.faceCode;
  const interactive = !!opts.interactive;
  const root = document.getElementById(opts.containerId);
  if (!root) return;
  while (root.firstChild) root.removeChild(root.firstChild);

  const vbW = 800, vbH = 600;
  root.setAttribute('viewBox', '0 0 ' + vbW + ' ' + vbH);
  root.setAttribute('preserveAspectRatio', 'xMidYMid meet');

  const metric = STATE.ii.metric;

  // background
  root.appendChild(svg('rect', { x: 0, y: 0, width: vbW, height: vbH, fill: '#0e1320', rx: 6 }));

  // device outline (rounded dashed rect at true bbox). Skip when no bbox.
  const bb = DEVICE_BBOX;
  if (bb) {
    const tl = _xyToVB(bb.xmin, bb.ymax, vbW, vbH, 28);
    const br = _xyToVB(bb.xmax, bb.ymin, vbW, vbH, 28);
    root.appendChild(svg('rect', {
      x: tl[0], y: tl[1], width: br[0] - tl[0], height: br[1] - tl[1],
      rx: 6, ry: 6, fill: 'none', stroke: '#3a4055', 'stroke-width': 1.2,
      'stroke-dasharray': '5,4'
    }));
  } else {
    const t = svg('text', { x: vbW / 2, y: vbH / 2, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 14 });
    t.appendChild(document.createTextNode('no device layout'));
    root.appendChild(t);
  }

  // part outlines layer
  const partsLayer = svg('g', { id: opts.containerId + '-parts' });
  for (const p of PARTS) {
    const bbf = _footprintBBox(p.footprint);
    if (!bbf) continue;
    const a = _xyToVB(bbf.xmin, bbf.ymax, vbW, vbH, 28);
    const b = _xyToVB(bbf.xmax, bbf.ymin, vbW, vbH, 28);
    const w = b[0] - a[0], h = b[1] - a[1];
    if (w < 1 || h < 1) continue;
    const rect = svg('rect', {
      x: a[0], y: a[1], width: w, height: h, rx: 2, ry: 2,
      fill: 'rgba(170,178,207,0.06)',
      stroke: 'rgba(170,178,207,0.40)',
      'stroke-width': 1.2,
      'data-part-id': p.id
    });
    rect.dataset.partid = p.id;
    partsLayer.appendChild(rect);
    // part label (small, dim, near top of rect)
    if (w > 35 && h > 14) {
      const lab = svg('text', {
        x: a[0] + w / 2, y: a[1] + 12,
        'text-anchor': 'middle', fill: 'rgba(170,178,207,0.55)',
        'font-size': 8.5, 'font-family': 'JetBrains Mono', 'data-part-label': p.id
      });
      lab.appendChild(document.createTextNode(p.name.split('\\').pop().slice(0, 14)));
      partsLayer.appendChild(lab);
    }
  }
  root.appendChild(partsLayer);

  // impact dots layer
  const dotsLayer = svg('g', { id: opts.containerId + '-dots' });
  const posMax = _ensurePosMax(metric);
  const facePosKeys = Object.keys(posMax).filter(k => k.indexOf(faceCode + '|') === 0);
  let globalMax = 0;
  for (const k of facePosKeys) { const v = posMax[k].v; if (v > globalMax) globalMax = v; }
  const threshAbs = globalMax * (STATE.ii.thresh / 100.0);
  let worstK = null;
  for (const k of facePosKeys) if (!worstK || posMax[k].v > posMax[worstK].v) worstK = k;

  for (const k of facePosKeys) {
    const rec = posMax[k];
    const passes = rec.v >= threshAbs;
    const [cx, cy] = _xyToVB(rec.x, rec.y, vbW, vbH, 28);
    const t = globalMax > 0 ? rec.v / globalMax : 0;
    const fill = passes ? gColor(t) : 'rgba(170,178,207,0.15)';
    const r = interactive ? 6 : 5;
    const dot = svg('circle', {
      cx: cx, cy: cy, r: r, fill: fill,
      stroke: 'rgba(10,12,20,0.8)', 'stroke-width': 0.8,
      'data-pos-key': k
    });
    if (interactive) {
      dot.style.cursor = 'pointer';
      dot.addEventListener('mouseenter', function () {
        if (STATE.ii.pinned) return;
        STATE.ii.hovered_pos = k;
        _renderInspectorFill(rec, globalMax);
        _renderSidePanel(rec, globalMax);
      });
      dot.addEventListener('click', function () {
        STATE.ii.hovered_pos = k;
        STATE.ii.pinned = true;
        const pin = document.getElementById('ii-pin');
        if (pin) { pin.checked = true; document.getElementById('ii-pin-lab').classList.add('locked'); }
        _renderInspectorFill(rec, globalMax);
        _renderSidePanel(rec, globalMax);
      });
    } else {
      // non-interactive cell: clicking jumps to Page 2 with this face
      dot.style.cursor = 'pointer';
    }
    const titleNode = svg('title', {});
    titleNode.appendChild(document.createTextNode(rec.pos_id + '\nX=' + rec.x.toFixed(2) + ' Y=' + rec.y.toFixed(2) + '\nmax part: ' + rec.part_name + '\n' + _metricLabel(metric) + ' = ' + fmt(rec.v, 2)));
    dot.appendChild(titleNode);
    dotsLayer.appendChild(dot);
  }

  // worst marker (★)
  if (worstK) {
    const rec = posMax[worstK];
    const [cx, cy] = _xyToVB(rec.x, rec.y, vbW, vbH, 28);
    const star = svg('text', {
      x: cx, y: cy + 4, 'text-anchor': 'middle', fill: '#ff3854',
      'font-size': 18, 'font-weight': 700, 'pointer-events': 'none'
    });
    star.appendChild(document.createTextNode('★'));
    dotsLayer.appendChild(star);
  }
  root.appendChild(dotsLayer);

  // hover halo layer (interactive only)
  if (interactive) {
    const haloLayer = svg('g', { id: 'ii-halo-layer' });
    root.appendChild(haloLayer);
    // mouseleave on root clears hover unless pinned
    root.addEventListener('mouseleave', function () {
      if (STATE.ii.pinned) return;
      STATE.ii.hovered_pos = null;
      _renderInspectorClear();
    });
  }

  // non-interactive cell click → jump to Inspector
  if (!interactive) {
    root.style.cursor = 'pointer';
    root.addEventListener('click', function () {
      const btn = document.querySelector('.ctlbar .btn[data-ii-face="' + faceCode + '"]');
      if (btn) btn.click();
      const tgt = document.getElementById('s2');
      if (tgt) tgt.scrollIntoView({ behavior: 'smooth' });
    });
  }
}

function _metricLabel(m) {
  return ({
    g: 'Peak G',
    s: 'σ' + _uSuffix('stress'),
    e: 'ε',
    d: 'd' + _uSuffix('disp')
  })[m] || m;
}

function _renderInspectorClear() {
  const layer = document.getElementById('ii-svg-parts');
  if (!layer) return;
  for (const node of layer.querySelectorAll('rect[data-part-id]')) {
    node.setAttribute('fill', 'rgba(170,178,207,0.06)');
    node.setAttribute('stroke', 'rgba(170,178,207,0.40)');
    node.setAttribute('stroke-width', '1.2');
  }
  const halo = document.getElementById('ii-halo-layer');
  if (halo) while (halo.firstChild) halo.removeChild(halo.firstChild);
  const star = layer.parentNode.querySelector('text[data-star-overlay]');
  if (star) star.remove();
  const empty = '<div class="ii-empty">충돌 위치 위에 마우스를 올리세요.</div>';
  const hInfo = document.getElementById('ii-hover-info'); if (hInfo) hInfo.innerHTML = empty;
  const partsList = document.getElementById('ii-parts-list'); if (partsList) partsList.innerHTML = '<div class="ii-empty">-</div>';
  const thSvg = document.getElementById('ii-th-svg');
  if (thSvg) {
    while (thSvg.firstChild) thSvg.removeChild(thSvg.firstChild);
    // Initial-state placeholder so the panel doesn't look broken before
    // the user hovers a position. Removed on first hover.
    const t = svg('text', { x: 100, y: 38, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 9, 'font-family': 'JetBrains Mono, monospace' });
    t.appendChild(document.createTextNode('hover impact → KE-time curve'));
    thSvg.appendChild(t);
  }
  const sub = document.getElementById('ii-th-sub'); if (sub) sub.textContent = '';
  const badge = document.getElementById('ii-behavior-badge'); if (badge) badge.innerHTML = '';
  const kpi = document.getElementById('ii-traj-kpi'); if (kpi) kpi.innerHTML = '';
}

function _renderInspectorFill(rec, globalMax) {
  const layer = document.getElementById('ii-svg-parts');
  if (!layer) return;
  const metric = STATE.ii.metric;
  const norm = STATE.ii.norm;
  const faceCode = STATE.ii.face;
  // collect per-part response for this impact
  const partResps = [];
  let localMax = 0;
  for (const p of PARTS) {
    const r = RESULT_IDX[rec.face + '|' + rec.pos_id + '|' + p.id];
    const v = r ? (r[metric] || 0) : 0;
    if (v > localMax) localMax = v;
    partResps.push({ part: p, v: v, r: r });
  }
  const denom = norm === 'rel' ? Math.max(1e-9, localMax) : Math.max(1e-9, globalMax);
  let maxPart = null;
  for (const it of partResps) if (!maxPart || it.v > maxPart.v) maxPart = it;
  // fill each part rect
  for (const node of layer.querySelectorAll('rect[data-part-id]')) {
    const pid = parseInt(node.dataset.partid, 10);
    const entry = partResps.find(x => x.part.id === pid);
    if (!entry || entry.v <= 0) {
      node.setAttribute('fill', 'rgba(170,178,207,0.04)');
      node.setAttribute('stroke', 'rgba(170,178,207,0.18)');
      node.setAttribute('stroke-width', '1');
      continue;
    }
    const t = Math.min(1, entry.v / denom);
    const c = gColor(t);
    node.setAttribute('fill', c.replace('rgb', 'rgba').replace(')', ',0.45)'));
    node.setAttribute('stroke', c);
    node.setAttribute('stroke-width', (maxPart && entry.part.id === maxPart.part.id) ? '2.5' : '1.5');
  }
  // halo pulse over the hovered impact
  const halo = document.getElementById('ii-halo-layer');
  if (halo) {
    while (halo.firstChild) halo.removeChild(halo.firstChild);
    const [hx, hy] = _xyToVB(rec.x, rec.y, 800, 600, 28);
    const ring = svg('circle', {
      cx: hx, cy: hy, r: 6, fill: 'none', stroke: '#ff3854', 'stroke-width': 2,
      class: 'ii-halo', 'pointer-events': 'none'
    });
    halo.appendChild(ring);
    // ★ marker over max part
    if (maxPart && maxPart.v > 0) {
      const bbf = _footprintBBox(maxPart.part.footprint);
      if (bbf) {
        const [sx, sy] = _xyToVB(bbf.cx, bbf.cy, 800, 600, 28);
        const star = svg('text', {
          x: sx, y: sy + 5, 'text-anchor': 'middle', fill: '#ffffff',
          'font-size': 16, 'font-weight': 700, 'pointer-events': 'none',
          'data-star-overlay': '1'
        });
        star.appendChild(document.createTextNode('★'));
        halo.appendChild(star);
      }
    }
  }
}

function _renderSidePanel(rec, globalMax) {
  const metric = STATE.ii.metric;
  const faceCode = STATE.ii.face;
  const norm = STATE.ii.norm;
  // hovered info
  const hInfo = document.getElementById('ii-hover-info');
  if (hInfo) {
    // global rank for this face
    const posMax = _ensurePosMax(metric);
    const facePosKeys = Object.keys(posMax).filter(k => k.indexOf(faceCode + '|') === 0);
    const sortedKeys = facePosKeys.sort((a, b) => posMax[b].v - posMax[a].v);
    const rank = sortedKeys.indexOf(faceCode + '|' + rec.pos_id) + 1;
    hInfo.innerHTML = '';
    hInfo.appendChild(el('div', { class: 'iirow' }, [el('span', null, 'POS'), el('b', null, rec.pos_id)]));
    hInfo.appendChild(el('div', { class: 'iirow' }, [el('span', null, '(X, Y)'), el('b', null, rec.x.toFixed(2) + ', ' + rec.y.toFixed(2))]));
    hInfo.appendChild(el('div', { class: 'iirow' }, [el('span', null, 'RANK'), el('b', null, '#' + rank + ' / ' + facePosKeys.length)]));
    hInfo.appendChild(el('div', { class: 'iirow' }, [el('span', null, 'MAX'), el('b', { style: { color: 'var(--crit)' } }, rec.part_name + ' · ' + fmt(rec.v, 1))]));
  }
  // top affected parts (sorted desc)
  const partResps = [];
  let localMax = 0;
  for (const p of PARTS) {
    const r = RESULT_IDX[rec.face + '|' + rec.pos_id + '|' + p.id];
    const v = r ? (r[metric] || 0) : 0;
    if (v > localMax) localMax = v;
    partResps.push({ part: p, v: v });
  }
  partResps.sort((a, b) => b.v - a.v);
  const denom = norm === 'rel' ? Math.max(1e-9, localMax) : Math.max(1e-9, globalMax);
  const list = document.getElementById('ii-parts-list');
  if (list) {
    list.innerHTML = '';
    for (let i = 0; i < partResps.length; i++) {
      const it = partResps[i];
      if (it.v <= 0 && i > 0) break;
      const t = Math.min(1, it.v / denom);
      const c = gColor(t);
      const row = el('div', { class: 'ii-bar-row' + (i === 0 ? ' is-max' : '') }, [
        el('div', { class: 'nm', title: it.part.name }, it.part.name.split('\\').pop()),
        el('div', { class: 'bw' }, [el('span', { class: 'fl', style: { width: (t * 100).toFixed(1) + '%', background: c } })]),
        el('div', { class: 'vl' }, fmt(it.v, 1))
      ]);
      row.addEventListener('click', function () {
        STATE.ii.selected_part = it.part.id;
        // flash that part in main canvas
        const layer = document.getElementById('ii-svg-parts');
        if (layer) {
          const node = layer.querySelector('rect[data-part-id="' + it.part.id + '"]');
          if (node) {
            const orig = node.getAttribute('stroke-width');
            node.setAttribute('stroke-width', '4');
            setTimeout(() => node.setAttribute('stroke-width', orig || '1.5'), 600);
          }
        }
      });
      list.appendChild(row);
    }
  }
  // KE decay overlay (real impactor trajectory) + behavior badge — replaces synthetic envelope
  renderInspectorBehaviorBadge(rec);
  renderInspectorKEOverlay(rec);
}

function _renderTimeHistory(rec, partId) {
  const svgRoot = document.getElementById('ii-th-svg');
  if (!svgRoot) return;
  while (svgRoot.firstChild) svgRoot.removeChild(svgRoot.firstChild);
  const W = 200, H = 70;
  const r = RESULT_IDX[rec.face + '|' + rec.pos_id + '|' + partId];
  const p = PART_BY_ID[partId];
  document.getElementById('ii-th-sub').textContent = '(' + (p ? p.name.split('\\').pop() : '-') + ')';
  if (!r) {
    const t = svg('text', { x: W / 2, y: H / 2, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 9 });
    t.appendChild(document.createTextNode('no time-series'));
    svgRoot.appendChild(t);
    return;
  }
  // Real stress time-series from PairResult.stress_ts (d3plot extraction).
  // If unavailable, render an explicit placeholder rather than a synthetic
  // Gaussian — fake envelopes were misleading the user.
  const ts = r.stress_ts || {};
  const times = Array.isArray(ts.times) ? ts.times : [];
  const vals = Array.isArray(ts.max_values) ? ts.max_values : [];
  if (!times.length || !vals.length || times.length !== vals.length) {
    const t = svg('text', { x: W / 2, y: H / 2, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 9 });
    t.appendChild(document.createTextNode('no time-series data'));
    svgRoot.appendChild(t);
    return;
  }
  const tMin = times[0], tMax = times[times.length - 1] || tMin + 1;
  const vMax = Math.max.apply(null, vals.map(Math.abs)) || 1;
  const tx = (t) => ((t - tMin) / (tMax - tMin)) * W;
  const vy = (v) => H - 8 - (Math.abs(v) / vMax) * (H - 16);
  const pts = times.map((t, i) => [tx(t), vy(vals[i])]);
  svgRoot.appendChild(svg('polyline', {
    points: pts.map(pt => pt.join(',')).join(' '),
    fill: 'none', stroke: '#ff3854', 'stroke-width': 1.4,
  }));
}

/** Bi-Face Split (Page 1) — two compact non-interactive Inspector panels. */
function renderBiFaceSplit() {
  const big = document.getElementById('biface-split');
  const mini = document.getElementById('biface-mini');
  const targets = [
    { code: 'F2', name: 'Front', label: 'FRONT · F2' },
    { code: 'F1', name: 'Back',  label: 'BACK · F1' }
  ];

  // big version (page 1 main panel)
  if (big) {
    while (big.firstChild) big.removeChild(big.firstChild);
    for (const t of targets) {
      const f = FACE_BY_CODE[t.code];
      if (!f) continue;
      const card = el('div', { class: 'biface-cell' });
      const head = el('div', { class: 'bf-head' }, [
        el('div', { class: 'bf-name' }, t.label),
        el('div', { class: 'bf-sub' }, (f.name || '').toUpperCase())
      ]);
      card.appendChild(head);
      const id = 'bf-svg-' + t.code;
      const svgEl = svg('svg', { id: id });
      card.appendChild(svgEl);
      const foot = el('div', { class: 'bf-foot' }, [el('span', { id: 'bf-foot-' + t.code }, 'max = -')]);
      card.appendChild(foot);
      card.addEventListener('click', function () {
        const btn = document.querySelector('.ctlbar .btn[data-ii-face="' + t.code + '"]');
        if (btn) btn.click();
        const tgt = document.getElementById('s2');
        if (tgt) tgt.scrollIntoView({ behavior: 'smooth' });
      });
      big.appendChild(card);
      initImpactInspector({ containerId: id, faceCode: t.code, interactive: false });
      // populate foot label
      const posMax = _ensurePosMax(STATE.ii.metric);
      const keys = Object.keys(posMax).filter(k => k.indexOf(t.code + '|') === 0);
      let worst = null;
      for (const k of keys) if (!worst || posMax[k].v > worst.v) worst = posMax[k];
      if (worst) document.getElementById('bf-foot-' + t.code).innerHTML = 'max: <b>' + fmt(worst.v, 1) + '</b> ' + (STATE.ii.metric === 'g' ? 'G' : '') + ' &middot; ' + worst.part_name;
    }
  }

  // mini version (page 1 method-band)
  if (mini) {
    while (mini.firstChild) mini.removeChild(mini.firstChild);
    for (const t of targets) {
      const f = FACE_BY_CODE[t.code];
      if (!f) continue;
      const card = el('div', { class: 'biface-cell', style: { padding: '6px 8px' } });
      card.appendChild(el('div', { class: 'bf-head', style: { paddingBottom: '3px', marginBottom: '3px' } }, [
        el('div', { class: 'bf-name', style: { fontSize: '10px' } }, t.code),
        el('div', { class: 'bf-sub' }, f.name)
      ]));
      const id = 'bfm-svg-' + t.code;
      card.appendChild(svg('svg', { id: id }));
      card.addEventListener('click', function () {
        const btn = document.querySelector('.ctlbar .btn[data-ii-face="' + t.code + '"]');
        if (btn) btn.click();
        const tgt = document.getElementById('s2');
        if (tgt) tgt.scrollIntoView({ behavior: 'smooth' });
      });
      mini.appendChild(card);
      initImpactInspector({ containerId: id, faceCode: t.code, interactive: false });
    }
  }
}

/** Page 2 Inspector (interactive). */
function renderInspector() {
  // ensure svg id matches what _renderInspectorFill expects (-parts suffix)
  const root = document.getElementById('ii-svg');
  if (!root) return;
  initImpactInspector({ containerId: 'ii-svg', faceCode: STATE.ii.face, interactive: true });
  // rename parts layer id so the *Fill helper finds it predictably
  const oldParts = document.getElementById('ii-svg-parts');
  if (oldParts) oldParts.id = 'ii-svg-parts';  // already correct from initImpactInspector
  // update header / metric labels
  const f = FACE_BY_CODE[STATE.ii.face];
  document.getElementById('ii-face-label').textContent = (f ? (f.name + ' (' + f.code + ')') : STATE.ii.face).toUpperCase();
  const metric = STATE.ii.metric;
  document.getElementById('ii-metric-name').textContent = _metricLabel(metric);
  // cbar max
  const posMax = _ensurePosMax(metric);
  const keys = Object.keys(posMax).filter(k => k.indexOf(STATE.ii.face + '|') === 0);
  let gmx = 0; for (const k of keys) if (posMax[k].v > gmx) gmx = posMax[k].v;
  document.getElementById('ii-cbar-max').textContent = fmt(gmx, 1);
  // thresh label
  document.getElementById('ii-thresh-val').textContent = STATE.ii.thresh + '% (' + fmt(gmx * STATE.ii.thresh / 100, 1) + ')';
  // if a pinned/hovered impact exists, re-render fill
  if (STATE.ii.hovered_pos && posMax[STATE.ii.hovered_pos]) {
    _renderInspectorFill(posMax[STATE.ii.hovered_pos], gmx);
    _renderSidePanel(posMax[STATE.ii.hovered_pos], gmx);
  } else {
    _renderInspectorClear();
  }
}

"""
