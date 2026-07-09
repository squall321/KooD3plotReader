# 섹션 05 — DOE · SPATIAL ANALYSIS (위치별 응답 지도) HTML 템플릿 (기계적 분할, 바이트 불변)

_PAGE5 = """
<section class="page" id="s5" style="display:none">
  <div class="page-head r">
    <span class="num">05</span><span class="tagline">DOE &middot; SPATIAL ANALYSIS</span>
    <span class="ttl">전위치 부분충격 &mdash; 위치별 응답 지도</span>
    <span class="sub">MULTI-POSITION DOE EXPLORER</span>
  </div>

  <div id="doe-empty" class="doe-empty" style="display:none">DOE 데이터 없음 (단일 위치 리포트)</div>

  <div id="doe-content">
    <div class="kpi-strip r" id="doe-kpi-strip" style="grid-template-columns:repeat(5, 1fr);margin-bottom:14px"></div>

    <div class="ctlbar r" id="doe-ctlbar">
      <div class="grp"><span class="lbl">METRIC</span><span id="doe-metric-buttons"></span></div>
      <div class="grp"><span class="lbl">SORT</span>
        <button class="btn active" data-doe-sort="value">VALUE DESC</button>
        <button class="btn" data-doe-sort="pos">POS_ID</button>
      </div>
    </div>

    <div class="grid g-12" style="margin-bottom:14px" id="doe-grid-heat-rank">
      <div class="panel col-7 r" id="doe-panel-heatmap">
        <div class="ph">
          <span class="pt">SPATIAL HEATMAP &middot; <span id="doe-heat-metric-lbl">PEAK G</span></span>
          <span class="pd" id="doe-heat-sub">grid &middot; cell color = selected metric</span>
        </div>
        <div class="doe-grid-wrap"><svg id="doe-heatmap-svg"></svg></div>
        <div class="pcap" id="doe-heat-cap">셀 클릭 시 우측 표에서 해당 위치 강조. 라벨 = 값 + 최악 영향 부품.</div>
      </div>

      <div class="panel col-5 r" id="doe-panel-ranking">
        <div class="ph">
          <span class="pt">POSITION RANKING</span>
          <span class="pd">sorted by selected metric desc</span>
        </div>
        <div class="doe-rank">
          <table class="dt" id="doe-rank-tbl">
            <thead>
              <tr>
                <th class="tl">RANK</th>
                <th class="tl">POS_ID</th>
                <th>X<span id="doe-rank-x-unit"></span></th>
                <th>Y<span id="doe-rank-y-unit"></span></th>
                <th class="tl">BEHAVIOR</th>
                <th id="doe-rank-val-lbl">VAL</th>
                <th class="tl">DRIVER</th>
                <th>KE RET</th>
                <th>MAX PEN<span id="doe-rank-pen-unit"></span></th>
              </tr>
            </thead>
            <tbody></tbody>
          </table>
        </div>
      </div>
    </div>

    <div class="grid g-12" style="margin-bottom:14px" id="doe-grid-pp">
      <div class="panel col-12 r" id="doe-panel-pp-matrix">
        <div class="ph">
          <span class="pt">PART &times; POSITION HEATMAP</span>
          <span class="pd">rows = top 15 parts by max peak_g &middot; cols = positions by DOE index &middot; color = peak_g</span>
        </div>
        <div class="doe-pp-matrix-wrap"><svg id="doe-pp-svg"></svg></div>
        <div class="pcap">부품별로 어느 위치에서 가속도가 가장 큰지 한눈에 확인. 색상 = peak_g (위치별 정규화 아님).</div>
      </div>
    </div>

    <div class="grid g-12" style="margin-bottom:14px" id="doe-grid-traj-env">
      <div class="panel col-7 r" id="doe-panel-trajectory">
        <div class="ph">
          <span class="pt">TRAJECTORY SMALL MULTIPLES &middot; KE vs TIME</span>
          <span class="pd">25 mini-curves &middot; color = behavior class &middot; ★ = worst position</span>
        </div>
        <div class="doe-traj-mm" id="doe-traj-mm"></div>
        <div class="bvm-legend" style="margin-top:8px">
          <div class="lg"><span class="sw" style="background:#4adfa1"></span>bounce</div>
          <div class="lg"><span class="sw" style="background:#4dd6ff"></span>rebound</div>
          <div class="lg"><span class="sw" style="background:#ff3854"></span>embed</div>
          <div class="lg"><span class="sw" style="background:#ff9e64"></span>slide</div>
          <div class="lg"><span class="sw" style="background:#5c6383"></span>unknown</div>
        </div>
      </div>

      <div class="panel col-5 r" id="doe-panel-envelope">
        <div class="ph">
          <span class="pt">CROSS-POSITION ENVELOPE &middot; PER PART</span>
          <span class="pd">P5—P50—P95 whisker (peak_g) &middot; right = P95/P5</span>
        </div>
        <div class="doe-env-wrap" id="doe-env-wrap"></div>
        <div class="pcap">whisker 길이 = 위치별 부품 응답 분산. 비율 ↑ 위치 의존성 ↑.</div>
      </div>
    </div>

<div class="panel" id="doe-panel-failure-risk">
  <div class="ph">
    <span class="pt">FAILURE RISK MAP</span>
    <span class="pd">위치별 최소 안전율(SF) 히트맵 + 위험 부품 랭킹</span>
  </div>
  <div id="doe-failure-risk-body"></div>
  <div class="pcap">SF = yield / peak_stress. SF&lt;1 = 항복 초과, 1≤SF&lt;2 = 마진 부족.</div>
</div>

<div class="panel" id="doe-corr-network-panel">
  <div class="ph">
    <span class="pt">PART × PART RESPONSE CORRELATION</span>
    <span class="pd">25 위치에 걸친 peak_g 응답의 Pearson 상관 + greedy 클러스터링</span>
  </div>
  <div id="doe-corr-network" class="doe-corr-host"></div>
  <div class="pcap">25 위치에 걸친 부품 응답의 Pearson 상관. 같은 cluster = 구조적 연결 또는 같은 충격 경로. |r| ≥ 0.7 인 셀은 흰 테두리로 강조.</div>
</div>

<div class="panel col-12 r" id="doe-panel-toa">
  <div class="ph">
    <span class="pt">IMPACT WAVE PROPAGATION &middot; TIME-OF-ARRIVAL</span>
    <span class="pd">part peak_g vs impactor 첫 접촉 시점 &middot; 응답 전파 순서</span>
  </div>
  <div id="doe-toa-root" class="doe-toa-root"></div>
  <div class="pcap">
    Δt = part peak_g 시점 &minus; impactor 첫 접촉 시점. 응답 전파 순서를 시각화.
    좌측은 최악 위치의 도착 순서(상위 12개), 우측은 모든 위치 평균 기준 항상 빠른/느린 부품.
  </div>
</div>
<div class="grid g-12" style="margin-bottom:14px" id="doe-grid-idw">
  <div class="panel col-12 r" id="idw-pred-panel">
    <div class="ph">
      <span class="pt">WHAT-IF POSITION PREDICTOR &middot; IDW INTERPOLATION</span>
      <span class="pd">25 측정점 → 41×41 보간면 (역거리 가중, p=2)</span>
    </div>
    <div class="ctlbar r" style="margin-bottom:10px">
      <div class="grp"><span class="lbl">METRIC</span><span id="idw-pred-buttons"></span></div>
      <div class="grp" style="flex:1"><span class="lbl" style="opacity:.7">LEGEND</span>
        <span style="color:var(--fg2);font-size:11px">
          <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#0a0c14;border:1.5px solid #fff;vertical-align:middle;margin-right:4px"></span>측정점
          <span style="display:inline-block;width:10px;height:10px;border-radius:50%;border:2px solid #ffd84d;vertical-align:middle;margin:0 4px 0 12px"></span>예측 최대(보간 정점)
        </span>
      </div>
    </div>
    <div id="idw-pred-loo" style="margin-bottom:8px;font-size:12px;color:var(--fg2);padding:6px 10px;background:rgba(255,255,255,0.03);border-radius:4px;display:none"></div>
    <div class="doe-grid-wrap"><div id="idw-pred-stack" style="position:relative;width:100%;"><canvas id="idw-pred-canvas" width="620" height="900" style="display:block;width:100%;cursor:grab;background:#0e1320;border-radius:4px;"></canvas><svg id="idw-pred-svg" style="position:absolute;left:0;top:0;width:100%;height:100%;pointer-events:none;"></svg></div></div>
    <div id="idw-pred-info" style="margin-top:8px;font-size:12px;color:var(--fg2)"></div>
    <div class="pcap">측정 25 점 사이의 임의 위치에 떨어졌을 때 예상 응답. 점 = 실측, 면 = IDW 보간. 측정점 근처는 정확도가 높고, 측정점 사이 빈 영역은 불확실성이 커집니다 — 노란 링은 측정점 사이에 숨어 있을 가능성이 있는 "고위험 포켓"의 위치 추정입니다.</div>
  </div>
</div>

<div class="panel" id="panel-pareto-severity">
  <div class="ph">
    <span class="pt">SEVERITY × COVERAGE PARETO</span>
    <span class="pd">국소 vs 광역 충격 분류</span>
  </div>
  <div id="doe-pareto-severity" class="pareto-host"></div>
  <div class="pcap">한 위치가 '특정 부품만 심각' 인지 '여러 부품에 광범위' 인지 시각화. 우상단 = 광범위 + 심각 → 가장 위험.</div>
</div>

<div class="grid g-12" style="margin-bottom:14px" id="doe-grid-energy">
  <div class="panel col-12 r" id="doe-panel-energy">
    <div class="ph">
      <span class="pt">ENERGY PARTITION &middot; KE ABSORBED vs RETAINED</span>
      <span class="pd">per position &middot; sorted by absorption % desc</span>
    </div>
    <div class="doe-ep-summary" id="doe-ep-summary"></div>
    <div class="doe-ep-list" id="doe-ep-list"></div>
    <div class="pcap">충격 에너지가 디바이스에 흡수된 비율. 100% 흡수 = 충돌체가 정지. 행 클릭 시 상단 히트맵/랭킹에서 해당 위치 강조.</div>
  </div>
</div>

    <!-- ADV_PANELS_INSERT_HERE -->
    <!-- Workflow-added panel templates are inserted ABOVE this marker line. -->
  </div>
</section>

<div class="foot">KOOD3PLOT &middot; MULTI-FACE IMPACT &middot; v0.1.0 &middot; single-file self-contained</div>
"""


_JS_TRAJ = r"""/* ===================================================================
 * Trajectory visualisations (6 new panels)
 * =================================================================== */

const TRAJ = DATA.trajectories || {};
const TRAJ_KEYS = Object.keys(TRAJ);
const CLUSTERS = DATA.clusters || { n: 0, labels: {}, archetypes: [] };

// Behavior class palette. `slide` was previously #ff9e64 — visually
// indistinguishable from rebound's orange. Switched to the lateral-motion
// purple so all five classes are unique colors. CSS `.bbadge.slide` is in
// sync.
const BEHAVIOR_COLOR = {
  bounce: '#4adfa1',
  rebound: '#f0a830',
  slide:  '#b46eff',
  embed:  '#ff3854',
  unknown:'#5c6383'
};
const CLUSTER_PALETTE = ['#4dd6ff', '#b46eff', '#f0a830', '#4adfa1', '#ff9e64', '#ff5e84', '#aab2cf'];

function svgZoomPan(svgEl, opts) {
  // Make an existing SVG element zoom/pan/drag with wheel + mouse.
  // Adds a <g> wrapper around current children if not already present.
  // Double-click resets. ESC key resets.
  if (!svgEl || svgEl.dataset.zpInit === '1') return;
  svgEl.dataset.zpInit = '1';
  // Move all existing children into a <g class="zp-content">.
  const ns = 'http://www.w3.org/2000/svg';
  const g = document.createElementNS(ns, 'g');
  g.setAttribute('class', 'zp-content');
  // Snapshot children list (live NodeList changes during move).
  const kids = Array.from(svgEl.childNodes);
  kids.forEach(k => g.appendChild(k));
  svgEl.appendChild(g);
  const state = { tx: 0, ty: 0, scale: 1, dragging: false, lastX: 0, lastY: 0 };
  const apply = () => {
    g.setAttribute('transform', 'translate(' + state.tx + ',' + state.ty + ') scale(' + state.scale + ')');
  };
  const reset = () => { state.tx = 0; state.ty = 0; state.scale = 1; apply(); };
  svgEl.addEventListener('wheel', (ev) => {
    ev.preventDefault();
    const rect = svgEl.getBoundingClientRect();
    const mouseX = ev.clientX - rect.left;
    const mouseY = ev.clientY - rect.top;
    // Convert mouse to SVG coordinates via current viewBox.
    const vb = (svgEl.getAttribute('viewBox') || '0 0 100 100').split(/\s+/).map(Number);
    const svgX = vb[0] + (mouseX / rect.width) * vb[2];
    const svgY = vb[1] + (mouseY / rect.height) * vb[3];
    const localX = (svgX - state.tx) / state.scale;
    const localY = (svgY - state.ty) / state.scale;
    const direction = ev.deltaY < 0 ? 1 : -1;
    const factor = direction > 0 ? 1.2 : 1 / 1.2;
    state.scale = Math.max(0.25, Math.min(10, state.scale * factor));
    state.tx = svgX - localX * state.scale;
    state.ty = svgY - localY * state.scale;
    apply();
  }, { passive: false });
  svgEl.addEventListener('mousedown', (ev) => {
    state.dragging = true;
    state.lastX = ev.clientX;
    state.lastY = ev.clientY;
    svgEl.style.cursor = 'grabbing';
    ev.preventDefault();
  });
  window.addEventListener('mousemove', (ev) => {
    if (!state.dragging) return;
    const dx = ev.clientX - state.lastX;
    const dy = ev.clientY - state.lastY;
    state.lastX = ev.clientX;
    state.lastY = ev.clientY;
    const rect = svgEl.getBoundingClientRect();
    const vb = (svgEl.getAttribute('viewBox') || '0 0 100 100').split(/\s+/).map(Number);
    state.tx += dx * (vb[2] / rect.width);
    state.ty += dy * (vb[3] / rect.height);
    apply();
  });
  window.addEventListener('mouseup', () => {
    state.dragging = false;
    svgEl.style.cursor = 'grab';
  });
  svgEl.addEventListener('dblclick', reset);
  window.addEventListener('keydown', (ev) => { if (ev.key === 'Escape') reset(); });
  svgEl.style.cursor = 'grab';
  // Visual hint: a tiny help text in a corner.
  const hint = document.createElementNS(ns, 'text');
  hint.setAttribute('x', 4);
  hint.setAttribute('y', 12);
  hint.setAttribute('font-size', 8);
  hint.setAttribute('fill', '#5c6383');
  hint.textContent = 'wheel: zoom · drag: pan · dbl-click: reset';
  svgEl.appendChild(hint);
}

function canvasZoomPan(canvasEl, opts) {
  // Make a canvas zoomable/pannable. The canvas must accept a redraw callback.
  // opts.draw(ctx, transform) is invoked whenever the view changes.
  //   transform = { tx, ty, scale }
  if (!canvasEl || canvasEl.dataset.czpInit === '1') return;
  canvasEl.dataset.czpInit = '1';
  const state = { tx: 0, ty: 0, scale: 1, dragging: false, lastX: 0, lastY: 0 };
  const redraw = () => {
    if (opts && typeof opts.draw === 'function') opts.draw(canvasEl.getContext('2d'), state);
  };
  const reset = () => { state.tx = 0; state.ty = 0; state.scale = 1; redraw(); };
  canvasEl.addEventListener('wheel', (ev) => {
    ev.preventDefault();
    const rect = canvasEl.getBoundingClientRect();
    const mouseX = ev.clientX - rect.left;
    const mouseY = ev.clientY - rect.top;
    // Convert to canvas coords (account for DPR & resolution).
    const cx = mouseX * (canvasEl.width / rect.width);
    const cy = mouseY * (canvasEl.height / rect.height);
    const localX = (cx - state.tx) / state.scale;
    const localY = (cy - state.ty) / state.scale;
    const factor = ev.deltaY < 0 ? 1.2 : 1 / 1.2;
    state.scale = Math.max(0.25, Math.min(10, state.scale * factor));
    state.tx = cx - localX * state.scale;
    state.ty = cy - localY * state.scale;
    redraw();
  }, { passive: false });
  canvasEl.addEventListener('mousedown', (ev) => {
    state.dragging = true;
    state.lastX = ev.clientX;
    state.lastY = ev.clientY;
    canvasEl.style.cursor = 'grabbing';
    ev.preventDefault();
  });
  window.addEventListener('mousemove', (ev) => {
    if (!state.dragging) return;
    const rect = canvasEl.getBoundingClientRect();
    const dx = (ev.clientX - state.lastX) * (canvasEl.width / rect.width);
    const dy = (ev.clientY - state.lastY) * (canvasEl.height / rect.height);
    state.lastX = ev.clientX;
    state.lastY = ev.clientY;
    state.tx += dx;
    state.ty += dy;
    redraw();
  });
  window.addEventListener('mouseup', () => {
    state.dragging = false;
    canvasEl.style.cursor = 'grab';
  });
  canvasEl.addEventListener('dblclick', reset);
  window.addEventListener('keydown', (ev) => { if (ev.key === 'Escape') reset(); });
  canvasEl.style.cursor = 'grab';
  redraw();  // Initial frame.
  return { reset, getState: () => ({...state}) };
}

function _trajForPos(face, posId) {
  const t = TRAJ[posId];
  if (!t) return null;
  if (face && t.face !== face) return null;
  return t;
}

function _mapXYToVB(x, y, vbW, vbH, padPx) {
  return _xyToVB(x, y, vbW, vbH, padPx);
}

function _drawFaceCanvas(svgRoot, faceCode, drawFn) {
  // Common helpers: draw device bbox + part footprints, then call drawFn(vbW,vbH).
  const vbW = 600, vbH = 360;
  svgRoot.setAttribute('viewBox', '0 0 ' + vbW + ' ' + vbH);
  svgRoot.setAttribute('preserveAspectRatio', 'xMidYMid meet');
  while (svgRoot.firstChild) svgRoot.removeChild(svgRoot.firstChild);
  // background
  svgRoot.appendChild(svg('rect', { x: 0, y: 0, width: vbW, height: vbH, fill: '#0e1320', rx: 4 }));
  const bb = DEVICE_BBOX;
  if (bb) {
    const tl = _mapXYToVB(bb.xmin, bb.ymax, vbW, vbH, 22);
    const br = _mapXYToVB(bb.xmax, bb.ymin, vbW, vbH, 22);
    svgRoot.appendChild(svg('rect', {
      x: tl[0], y: tl[1], width: br[0] - tl[0], height: br[1] - tl[1],
      rx: 4, ry: 4, fill: 'none', stroke: '#3a4055', 'stroke-width': 1,
      'stroke-dasharray': '4,4'
    }));
  }
  for (const p of PARTS) {
    const bbf = _footprintBBox(p.footprint);
    if (!bbf) continue;
    const a = _mapXYToVB(bbf.xmin, bbf.ymax, vbW, vbH, 22);
    const b = _mapXYToVB(bbf.xmax, bbf.ymin, vbW, vbH, 22);
    const w = b[0] - a[0], h = b[1] - a[1];
    if (w < 1 || h < 1) continue;
    svgRoot.appendChild(svg('rect', {
      x: a[0], y: a[1], width: w, height: h, rx: 2, ry: 2,
      fill: 'rgba(170,178,207,0.04)',
      stroke: 'rgba(170,178,207,0.18)',
      'stroke-width': 0.9
    }));
  }
  drawFn(vbW, vbH);
}

/* --- Viz 1: Bounce Vector Map (page 1) ----------------------------- */
function initBounceVectorMap() {
  const grid = document.getElementById('bvm-grid');
  const legend = document.getElementById('bvm-legend');
  if (!grid) return;
  while (grid.firstChild) grid.removeChild(grid.firstChild);
  while (legend.firstChild) legend.removeChild(legend.firstChild);
  if (!TRAJ_KEYS.length) {
    grid.appendChild(el('div', { class: 'traj-na' }, 'Trajectory data unavailable — run with --enable-trajectory'));
    return;
  }
  const targets = [
    { code: 'F2', name: 'FRONT · F2' },
    { code: 'F1', name: 'BACK · F1'  }
  ];
  const totals = { bounce: 0, rebound: 0, slide: 0, embed: 0, unknown: 0 };
  for (const k in TRAJ) totals[TRAJ[k].behavior] = (totals[TRAJ[k].behavior] || 0) + 1;
  for (const t of targets) {
    if (!FACE_BY_CODE[t.code]) continue;
    const cell = el('div', { class: 'bvm-cell' });
    cell.appendChild(el('div', { class: 'bf-head' }, [
      el('div', { class: 'bf-name' }, t.name),
      el('div', { class: 'bf-sub' }, 'bounce vectors')
    ]));
    const s = svg('svg', {});
    cell.appendChild(s);
    grid.appendChild(cell);
    // find rebound mag max for this face
    const keys = TRAJ_KEYS.filter(k => TRAJ[k].face === t.code);
    let maxMag = 0;
    for (const k of keys) if (TRAJ[k].rebound_speed > maxMag) maxMag = TRAJ[k].rebound_speed;
    _drawFaceCanvas(s, t.code, function (vbW, vbH) {
      // arrowhead marker
      const defs = svg('defs', {});
      ['bounce', 'rebound', 'slide', 'embed', 'unknown'].forEach(function (b) {
        const m = svg('marker', { id: 'bvm-' + b + '-' + t.code, viewBox: '0 0 10 10', refX: 8, refY: 5, markerWidth: 5, markerHeight: 5, orient: 'auto' });
        m.appendChild(svg('path', { d: 'M0,0 L10,5 L0,10 Z', fill: BEHAVIOR_COLOR[b] }));
        defs.appendChild(m);
      });
      s.appendChild(defs);
      for (const k of keys) {
        const tr = TRAJ[k];
        const [cx, cy] = _mapXYToVB(tr.x, tr.y, vbW, vbH, 22);
        const c = BEHAVIOR_COLOR[tr.behavior] || BEHAVIOR_COLOR.unknown;
        // tail dot
        s.appendChild(svg('circle', { cx: cx, cy: cy, r: 3, fill: c, opacity: 0.9 }));
        // arrow line — length scaled
        const mag = maxMag > 0 ? Math.min(1, tr.rebound_speed / maxMag) : 0;
        const L = 8 + 40 * mag;
        const rx = tr.rebound_xy[0], ry = tr.rebound_xy[1];
        const r2 = Math.hypot(rx, ry) || 1;
        // SVG y is inverted — flip ry
        const dx = L * (rx / r2), dy = -L * (ry / r2);
        if (tr.behavior !== 'embed' && L > 4) {
          const line = svg('line', {
            x1: cx, y1: cy, x2: cx + dx, y2: cy + dy,
            stroke: c, 'stroke-width': 1.4 + mag * 1.6, opacity: 0.85,
            'marker-end': 'url(#bvm-' + tr.behavior + '-' + t.code + ')'
          });
          const ttl = svg('title', {});
          ttl.appendChild(document.createTextNode(tr.behavior.toUpperCase() + ' · ' + k + '\nrebound = ' + fmt(tr.rebound_speed, 0) + (_u('vel') ? ' ' + _u('vel') : '') + '\nKE retention = ' + (tr.ke_retention * 100).toFixed(0) + '%\nmax pen = ' + fmt(tr.max_pen, 2) + (_u('disp') ? ' ' + _u('disp') : '')));
          line.appendChild(ttl);
          s.appendChild(line);
        } else if (tr.behavior === 'embed') {
          // cross marker for embed
          s.appendChild(svg('circle', { cx: cx, cy: cy, r: 6, fill: 'none', stroke: c, 'stroke-width': 1.5 }));
        }
      }
    });
    grid.appendChild(cell);
  }
  // legend
  const order = ['bounce', 'rebound', 'slide', 'embed'];
  for (const b of order) {
    legend.appendChild(el('div', { class: 'lg' }, [
      el('span', { class: 'sw', style: { background: BEHAVIOR_COLOR[b] } }),
      el('span', null, b.toUpperCase()),
      el('b', null, String(totals[b] || 0))
    ]));
  }
  if (totals.unknown) {
    legend.appendChild(el('div', { class: 'lg' }, [
      el('span', { class: 'sw', style: { background: BEHAVIOR_COLOR.unknown } }),
      el('span', null, 'UNKNOWN'),
      el('b', null, String(totals.unknown))
    ]));
  }
  if (DATA.trajectories && Object.values(DATA.trajectories).some(t => t._mock)) {
    legend.appendChild(el('div', { class: 'lg', style: { color: 'var(--tag)', marginLeft: 'auto' } }, [
      el('span', null, '(mock — sibling pipeline not wired yet)')
    ]));
  }
}

/* --- Viz 5: Trajectory Clustering Map (page 1) --------------------- */
function initTrajectoryClustering() {
  const grid = document.getElementById('tcm-grid');
  const arch = document.getElementById('tcm-archetypes');
  if (!grid) return;
  while (grid.firstChild) grid.removeChild(grid.firstChild);
  while (arch.firstChild) arch.removeChild(arch.firstChild);
  if (!TRAJ_KEYS.length || CLUSTERS.n <= 0) {
    grid.appendChild(el('div', { class: 'traj-na' }, 'Trajectory data unavailable.'));
    return;
  }
  const targets = [
    { code: 'F2', name: 'FRONT · F2' },
    { code: 'F1', name: 'BACK · F1'  }
  ];
  for (const t of targets) {
    if (!FACE_BY_CODE[t.code]) continue;
    const cell = el('div', { class: 'bvm-cell' });
    cell.appendChild(el('div', { class: 'bf-head' }, [
      el('div', { class: 'bf-name' }, t.name),
      el('div', { class: 'bf-sub' }, CLUSTERS.n + ' clusters')
    ]));
    const s = svg('svg', {});
    cell.appendChild(s);
    grid.appendChild(cell);
    _drawFaceCanvas(s, t.code, function (vbW, vbH) {
      const faceKeys = TRAJ_KEYS.filter(k => TRAJ[k].face === t.code);
      for (const k of faceKeys) {
        const tr = TRAJ[k];
        const lab = (CLUSTERS.labels[k] != null) ? CLUSTERS.labels[k] : -1;
        const c = (lab >= 0) ? CLUSTER_PALETTE[lab % CLUSTER_PALETTE.length] : '#5c6383';
        const [cx, cy] = _mapXYToVB(tr.x, tr.y, vbW, vbH, 22);
        const dot = svg('circle', {
          cx: cx, cy: cy, r: 5, fill: c, 'fill-opacity': 0.85,
          stroke: 'rgba(10,12,20,0.9)', 'stroke-width': 0.8,
          'data-tcm-cluster': lab, 'data-tcm-key': k
        });
        const ttl = svg('title', {});
        const archName = CLUSTERS.archetypes[lab] || ('cluster ' + lab);
        ttl.appendChild(document.createTextNode(k + '\nCLUSTER: ' + archName + '\nbehavior: ' + tr.behavior + '\nKE retention: ' + (tr.ke_retention * 100).toFixed(0) + '%'));
        dot.appendChild(ttl);
        dot.style.cursor = 'pointer';
        dot.addEventListener('mouseenter', function () {
          document.querySelectorAll('[data-tcm-cluster]').forEach(function (n) {
            n.setAttribute('fill-opacity', n.getAttribute('data-tcm-cluster') === String(lab) ? '1.0' : '0.18');
          });
        });
        dot.addEventListener('mouseleave', function () {
          document.querySelectorAll('[data-tcm-cluster]').forEach(function (n) {
            n.setAttribute('fill-opacity', '0.85');
          });
        });
        s.appendChild(dot);
      }
    });
  }
  // Archetype gallery
  const memberCount = {};
  for (const k in CLUSTERS.labels) {
    const lab = CLUSTERS.labels[k];
    memberCount[lab] = (memberCount[lab] || 0) + 1;
  }
  for (let i = 0; i < CLUSTERS.n; i++) {
    const archName = CLUSTERS.archetypes[i] || ('cluster ' + i);
    const col = CLUSTER_PALETTE[i % CLUSTER_PALETTE.length];
    const card = el('div', { class: 'tcm-arch', style: { borderLeft: '3px solid ' + col } });
    card.appendChild(el('div', { class: 'ah' }, [
      el('span', { class: 'nm', style: { color: col } }, archName.toUpperCase()),
      el('span', { class: 'ct' }, 'n=' + (memberCount[i] || 0))
    ]));
    // average KE decay sparkline for cluster
    const memberKeys = Object.keys(CLUSTERS.labels).filter(k => CLUSTERS.labels[k] === i);
    const s = svg('svg', { viewBox: '0 0 200 40', preserveAspectRatio: 'none' });
    if (memberKeys.length > 0) {
      const T = TRAJ[memberKeys[0]].ke.length;
      const avgKe = new Array(T).fill(0);
      let n = 0;
      for (const k of memberKeys) {
        const ts = TRAJ[k].ke;
        if (!ts || ts.length !== T) continue;
        for (let j = 0; j < T; j++) avgKe[j] += ts[j];
        n++;
      }
      if (n > 0) {
        const mx = Math.max(...avgKe) / n || 1;
        const pts = [];
        for (let j = 0; j < T; j++) {
          const x = j / (T - 1) * 200;
          const y = 40 - (avgKe[j] / n / mx) * 36 - 2;
          pts.push(x.toFixed(1) + ',' + y.toFixed(1));
        }
        s.appendChild(svg('polyline', { points: pts.join(' '), fill: 'none', stroke: col, 'stroke-width': 1.4 }));
      }
    } else {
      // Empty archetype — explicit "no members" placeholder so the cell isn't blank.
      s.appendChild(svg('rect', { x: 0, y: 0, width: 200, height: 40, fill: 'rgba(255,255,255,0.02)' }));
      const t = svg('text', { x: 100, y: 24, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 10, 'font-family': 'JetBrains Mono, monospace' });
      t.appendChild(document.createTextNode('no positions in this archetype'));
      s.appendChild(t);
    }
    card.appendChild(s);
    arch.appendChild(card);
  }
}

/* --- Viz 2: Phase Diagram (page 3) --------------------------------- */
function initPhaseDiagram() {
  const root = document.getElementById('phase-svg');
  const legend = document.getElementById('phase-legend');
  if (!root) return;
  while (root.firstChild) root.removeChild(root.firstChild);
  while (legend.firstChild) legend.removeChild(legend.firstChild);
  if (!TRAJ_KEYS.length) {
    root.appendChild(svg('text', { x: 300, y: 180, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 12 }, [document.createTextNode('Trajectory data unavailable')]));
    return;
  }
  const W = 720, H = 380;
  root.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
  const pad = { l: 50, r: 16, t: 12, b: 30 };
  const plotW = W - pad.l - pad.r, plotH = H - pad.t - pad.b;
  // determine domain
  let keMax = 0, ieMax = 0;
  for (const k of TRAJ_KEYS) {
    const t = TRAJ[k];
    for (const v of t.ke) if (v > keMax) keMax = v;
    const ie = (t.init_ke - t.final_ke);
    if (ie > ieMax) ieMax = ie;
  }
  if (keMax <= 0) keMax = 1;
  if (ieMax <= 0) ieMax = keMax;
  const xMax = Math.max(ieMax, keMax * 1.05);
  function px(ie) { return pad.l + (ie / xMax) * plotW; }
  function py(ke) { return pad.t + (1 - ke / keMax) * plotH; }
  // grid
  for (let g = 0; g <= 4; g++) {
    const yv = keMax * g / 4;
    const yp = py(yv);
    root.appendChild(svg('line', { x1: pad.l, y1: yp, x2: pad.l + plotW, y2: yp, stroke: 'rgba(255,255,255,0.06)', 'stroke-width': 0.5 }));
    const t = svg('text', { x: pad.l - 6, y: yp + 3, 'text-anchor': 'end', fill: '#5c6383', 'font-size': 9, 'font-family': 'JetBrains Mono' });
    t.appendChild(document.createTextNode(yv.toFixed(1)));
    root.appendChild(t);
    const xv = xMax * g / 4;
    const xp = px(xv);
    root.appendChild(svg('line', { x1: xp, y1: pad.t, x2: xp, y2: pad.t + plotH, stroke: 'rgba(255,255,255,0.06)', 'stroke-width': 0.5 }));
    const t2 = svg('text', { x: xp, y: pad.t + plotH + 14, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 9, 'font-family': 'JetBrains Mono' });
    t2.appendChild(document.createTextNode(xv.toFixed(1)));
    root.appendChild(t2);
  }
  // axis labels
  const lblY = svg('text', { x: 14, y: pad.t + plotH / 2, transform: 'rotate(-90 14,' + (pad.t + plotH / 2) + ')', 'text-anchor': 'middle', fill: '#aab2cf', 'font-size': 10, 'font-family': 'JetBrains Mono' });
  lblY.appendChild(document.createTextNode('KE impactor' + _uSuffix('energy')));
  root.appendChild(lblY);
  const lblX = svg('text', { x: pad.l + plotW / 2, y: H - 6, 'text-anchor': 'middle', fill: '#aab2cf', 'font-size': 10, 'font-family': 'JetBrains Mono' });
  lblX.appendChild(document.createTextNode('IE absorbed (= KE₀ − KE)' + _uSuffix('energy')));
  root.appendChild(lblX);
  // budget line: KE + IE <= KE0 → curve from (0,KE0) to (KE0,0)
  // approximate ke0 = max init_ke
  let ke0 = 0;
  for (const k of TRAJ_KEYS) if (TRAJ[k].init_ke > ke0) ke0 = TRAJ[k].init_ke;
  root.appendChild(svg('line', { x1: px(0), y1: py(ke0), x2: px(ke0), y2: py(0), stroke: 'rgba(180,110,255,0.55)', 'stroke-width': 1.2, 'stroke-dasharray': '4,3' }));
  const lblBudget = svg('text', { x: px(ke0 * 0.5), y: py(ke0 * 0.55), fill: '#b46eff', 'font-size': 9, 'font-family': 'JetBrains Mono' });
  lblBudget.appendChild(document.createTextNode('budget: KE+IE = KE₀'));
  root.appendChild(lblBudget);
  // each trajectory as polyline
  for (const k of TRAJ_KEYS) {
    const t = TRAJ[k];
    const c = BEHAVIOR_COLOR[t.behavior] || BEHAVIOR_COLOR.unknown;
    const pts = [];
    for (let i = 0; i < t.ke.length; i++) {
      const ie = t.init_ke - t.ke[i];
      pts.push(px(Math.max(0, ie)).toFixed(1) + ',' + py(t.ke[i]).toFixed(1));
    }
    const pline = svg('polyline', {
      points: pts.join(' '), fill: 'none', stroke: c,
      'stroke-width': 1.0, opacity: 0.55, 'data-phase-key': k
    });
    root.appendChild(pline);
    // final state scatter point
    const last = t.ke.length - 1;
    const dot = svg('circle', {
      cx: px(t.init_ke - t.ke[last]), cy: py(t.ke[last]),
      r: 2.5, fill: c, opacity: 0.9
    });
    const ttl = svg('title', {});
    ttl.appendChild(document.createTextNode(k + ' · ' + t.behavior + '\nKE final = ' + fmt(t.ke[last], 2) + (_u('energy') ? ' ' + _u('energy') : '') + '\nIE = ' + fmt(t.init_ke - t.ke[last], 2)));
    dot.appendChild(ttl);
    root.appendChild(dot);
  }
  // time annotations: show small ticks at t=0.1,0.3,0.5,1.0 ms on the pinned/first trajectory
  const ref = TRAJ[TRAJ_KEYS[0]];
  if (ref) {
    [0.1e-3, 0.3e-3, 0.5e-3, 1.0e-3].forEach(function (ts) {
      let idx = 0, best = Infinity;
      for (let i = 0; i < ref.t.length; i++) {
        const d = Math.abs(ref.t[i] - ts);
        if (d < best) { best = d; idx = i; }
      }
      const ie = ref.init_ke - ref.ke[idx];
      const xp = px(Math.max(0, ie)), yp = py(ref.ke[idx]);
      root.appendChild(svg('circle', { cx: xp, cy: yp, r: 2, fill: '#fff', opacity: 0.85 }));
      const lab = svg('text', { x: xp + 4, y: yp - 4, fill: '#fff', 'font-size': 8, 'font-family': 'JetBrains Mono' });
      lab.appendChild(document.createTextNode((ts * 1000).toFixed(1) + ' ms'));
      root.appendChild(lab);
    });
  }
  // legend
  ['bounce', 'rebound', 'slide', 'embed'].forEach(function (b) {
    legend.appendChild(el('div', { class: 'lg' }, [
      el('span', { class: 'sw', style: { background: BEHAVIOR_COLOR[b] } }),
      el('span', null, b.toUpperCase())
    ]));
  });
}

/* --- Viz 3: Contact Sequence Timeline (page 3) --------------------- */
function initContactTimeline() {
  const grid = document.getElementById('cseq-grid');
  if (!grid) return;
  while (grid.firstChild) grid.removeChild(grid.firstChild);
  if (!TRAJ_KEYS.length) {
    grid.appendChild(el('div', { class: 'traj-na', style: { gridColumn: 'span 2' } }, 'Trajectory data unavailable.'));
    return;
  }
  // top-8 worst by impact peak G (use FACE_POS_MAX)
  const ranked = [];
  for (const k of TRAJ_KEYS) {
    const t = TRAJ[k];
    const posKey = t.face + '|' + k;
    const ent = FACE_POS_MAX[posKey];
    ranked.push({ key: k, traj: t, g: ent ? ent.g : 0 });
  }
  ranked.sort((a, b) => b.g - a.g);
  const top = ranked.slice(0, 8);
  // header
  grid.appendChild(el('div', { class: 'lab', style: { color: 'var(--dim)' } }, 'IMPACT'));
  const head = el('div', { class: 'cseq-row', style: { fontSize: '8px', color: 'var(--dim)', fontFamily: 'JetBrains Mono, monospace' } });
  for (let i = 0; i < 21; i++) {
    head.appendChild(el('div', { style: { textAlign: 'center' } }, (i % 5 === 0) ? (i / 20).toFixed(1) : ''));
  }
  grid.appendChild(head);
  for (const it of top) {
    const tr = it.traj;
    const c = BEHAVIOR_COLOR[tr.behavior] || BEHAVIOR_COLOR.unknown;
    const lab = el('div', { class: 'lab', title: it.key });
    lab.appendChild(el('span', { style: { color: c, fontWeight: 700 } }, '■ '));
    lab.appendChild(document.createTextNode(tr.face + ' · ' + tr.x.toFixed(0) + ',' + tr.y.toFixed(0)));
    grid.appendChild(lab);
    const row = el('div', { class: 'cseq-row' });
    const T = tr.contact ? tr.contact.length : 0;
    for (let i = 0; i < 21; i++) {
      const idx = T > 0 ? Math.floor(i * (T - 1) / 20) : -1;
      const engaged = idx >= 0 && tr.contact[idx];
      // intensity: based on KE drop rate at this index
      let intensity = 0;
      if (engaged && idx > 0) {
        const dk = (tr.ke[idx - 1] - tr.ke[idx]) / Math.max(1e-6, tr.init_ke);
        intensity = Math.min(1, Math.max(0, dk * 25));
      }
      let cellColor;
      if (!engaged) {
        cellColor = 'rgba(255,255,255,0.04)';
      } else {
        const base = c;
        // blend with intensity
        const m = base.match(/#([0-9a-f]{6})/i);
        if (m) {
          const r = parseInt(m[1].slice(0, 2), 16);
          const g = parseInt(m[1].slice(2, 4), 16);
          const b = parseInt(m[1].slice(4, 6), 16);
          const alpha = 0.35 + 0.55 * intensity;
          cellColor = 'rgba(' + r + ',' + g + ',' + b + ',' + alpha.toFixed(2) + ')';
        } else {
          cellColor = c;
        }
      }
      const cell = el('div', { class: 'cseq-cell', style: { background: cellColor } });
      cell.title = it.key + ' · t=' + (i / 20).toFixed(2) + ' ms · ' + (engaged ? 'CONTACT' : 'free flight');
      row.appendChild(cell);
    }
    grid.appendChild(row);
  }
}

/* --- Viz 4: Trajectory Bundle 3D (page 3, 3 projections) ----------- */
function initTrajectoryBundle3D() {
  const xz = document.getElementById('tb3-xz');
  const yz = document.getElementById('tb3-yz');
  const xy = document.getElementById('tb3-xy');
  if (!xz || !yz || !xy) return;
  [xz, yz, xy].forEach(function (s) { while (s.firstChild) s.removeChild(s.firstChild); });
  if (!TRAJ_KEYS.length) {
    [xz, yz, xy].forEach(function (s) {
      s.setAttribute('viewBox', '0 0 200 100');
      const t = svg('text', { x: 100, y: 50, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 10 });
      t.appendChild(document.createTextNode('No trajectory'));
      s.appendChild(t);
    });
    return;
  }
  // determine z range
  let zmin = Infinity, zmax = -Infinity;
  for (const k of TRAJ_KEYS) {
    for (const p of TRAJ[k].pos) {
      if (p[2] < zmin) zmin = p[2];
      if (p[2] > zmax) zmax = p[2];
    }
  }
  if (!isFinite(zmin)) zmin = -5;
  if (!isFinite(zmax)) zmax = 15;
  if (zmin === zmax) { zmin -= 1; zmax += 1; }
  const bb = DEVICE_BBOX;
  if (!bb) {
    [xz, yz, xy].forEach(function (s) {
      s.setAttribute('viewBox', '0 0 200 100');
      const t = svg('text', { x: 100, y: 50, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 10 });
      t.appendChild(document.createTextNode('no device layout'));
      s.appendChild(t);
    });
    return;
  }
  // XZ projection
  function drawSideXZ(root) {
    const W = 360, H = 220;
    root.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
    root.appendChild(svg('rect', { x: 0, y: 0, width: W, height: H, fill: '#0e1320', rx: 4 }));
    const pad = { l: 26, r: 8, t: 10, b: 22 };
    const plotW = W - pad.l - pad.r, plotH = H - pad.t - pad.b;
    const xMin = bb.xmin, xMax = bb.xmax;
    function px(x) { return pad.l + (x - xMin) / (xMax - xMin) * plotW; }
    function py(z) { return pad.t + (1 - (z - zmin) / (zmax - zmin)) * plotH; }
    // z=0 line + bbox
    root.appendChild(svg('line', { x1: px(xMin), y1: py(0), x2: px(xMax), y2: py(0), stroke: 'rgba(255,255,255,0.16)', 'stroke-width': 0.8, 'stroke-dasharray': '4,3' }));
    const lab = svg('text', { x: pad.l - 2, y: py(0) + 3, 'text-anchor': 'end', fill: 'rgba(255,255,255,0.5)', 'font-size': 8, 'font-family': 'JetBrains Mono' });
    lab.appendChild(document.createTextNode('z=0')); root.appendChild(lab);
    // axes labels
    ['xmin', 'xmax'].forEach(function (k, i) {
      const xv = bb[k];
      const t = svg('text', { x: i === 0 ? pad.l : pad.l + plotW, y: H - 6, 'text-anchor': i === 0 ? 'start' : 'end', fill: '#5c6383', 'font-size': 8, 'font-family': 'JetBrains Mono' });
      t.appendChild(document.createTextNode('x=' + xv.toFixed(0))); root.appendChild(t);
    });
    const zlt = svg('text', { x: 4, y: pad.t + 6, fill: '#5c6383', 'font-size': 8, 'font-family': 'JetBrains Mono' });
    zlt.appendChild(document.createTextNode('z=' + zmax.toFixed(0))); root.appendChild(zlt);
    const zlb = svg('text', { x: 4, y: pad.t + plotH, fill: '#5c6383', 'font-size': 8, 'font-family': 'JetBrains Mono' });
    zlb.appendChild(document.createTextNode('z=' + zmin.toFixed(0))); root.appendChild(zlb);
    for (const k of TRAJ_KEYS) {
      const tr = TRAJ[k];
      const c = (tr.face === 'F1') ? '#b46eff' : '#4dd6ff';
      const pts = tr.pos.map(p => px(p[0]).toFixed(1) + ',' + py(p[2]).toFixed(1)).join(' ');
      root.appendChild(svg('polyline', { points: pts, fill: 'none', stroke: c, 'stroke-width': 0.8, opacity: 0.55 }));
    }
  }
  function drawSideYZ(root) {
    const W = 360, H = 220;
    root.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
    root.appendChild(svg('rect', { x: 0, y: 0, width: W, height: H, fill: '#0e1320', rx: 4 }));
    const pad = { l: 26, r: 8, t: 10, b: 22 };
    const plotW = W - pad.l - pad.r, plotH = H - pad.t - pad.b;
    const yMin = bb.ymin, yMax = bb.ymax;
    function px(y) { return pad.l + (y - yMin) / (yMax - yMin) * plotW; }
    function py(z) { return pad.t + (1 - (z - zmin) / (zmax - zmin)) * plotH; }
    root.appendChild(svg('line', { x1: px(yMin), y1: py(0), x2: px(yMax), y2: py(0), stroke: 'rgba(255,255,255,0.16)', 'stroke-width': 0.8, 'stroke-dasharray': '4,3' }));
    const lab = svg('text', { x: pad.l - 2, y: py(0) + 3, 'text-anchor': 'end', fill: 'rgba(255,255,255,0.5)', 'font-size': 8, 'font-family': 'JetBrains Mono' });
    lab.appendChild(document.createTextNode('z=0')); root.appendChild(lab);
    ['ymin', 'ymax'].forEach(function (k, i) {
      const yv = bb[k];
      const t = svg('text', { x: i === 0 ? pad.l : pad.l + plotW, y: H - 6, 'text-anchor': i === 0 ? 'start' : 'end', fill: '#5c6383', 'font-size': 8, 'font-family': 'JetBrains Mono' });
      t.appendChild(document.createTextNode('y=' + yv.toFixed(0))); root.appendChild(t);
    });
    for (const k of TRAJ_KEYS) {
      const tr = TRAJ[k];
      const c = (tr.face === 'F1') ? '#b46eff' : '#4dd6ff';
      const pts = tr.pos.map(p => px(p[1]).toFixed(1) + ',' + py(p[2]).toFixed(1)).join(' ');
      root.appendChild(svg('polyline', { points: pts, fill: 'none', stroke: c, 'stroke-width': 0.8, opacity: 0.55 }));
    }
  }
  function drawTopXY(root) {
    const W = 360, H = 220;
    root.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
    root.appendChild(svg('rect', { x: 0, y: 0, width: W, height: H, fill: '#0e1320', rx: 4 }));
    const pad = { l: 26, r: 8, t: 10, b: 22 };
    const plotW = W - pad.l - pad.r, plotH = H - pad.t - pad.b;
    const xMin = bb.xmin, xMax = bb.xmax;
    const yMin = bb.ymin, yMax = bb.ymax;
    function px(x) { return pad.l + (x - xMin) / (xMax - xMin) * plotW; }
    function py(y) { return pad.t + (1 - (y - yMin) / (yMax - yMin)) * plotH; }
    // device bbox dashed
    root.appendChild(svg('rect', { x: px(xMin), y: py(yMax), width: plotW, height: plotH, fill: 'none', stroke: '#3a4055', 'stroke-width': 0.9, 'stroke-dasharray': '4,3' }));
    for (const k of TRAJ_KEYS) {
      const tr = TRAJ[k];
      const c = BEHAVIOR_COLOR[tr.behavior] || BEHAVIOR_COLOR.unknown;
      const pts = tr.pos.map(p => px(p[0]).toFixed(1) + ',' + py(p[1]).toFixed(1)).join(' ');
      root.appendChild(svg('polyline', { points: pts, fill: 'none', stroke: c, 'stroke-width': 0.9, opacity: 0.55 }));
      // initial dot
      const p0 = tr.pos[0];
      root.appendChild(svg('circle', { cx: px(p0[0]), cy: py(p0[1]), r: 2, fill: c, opacity: 0.9 }));
    }
  }
  drawSideXZ(xz);
  drawSideYZ(yz);
  drawTopXY(xy);
}

/* --- Viz 6: Inspector KE overlay + behavior badge (page 2 enhance) - */
function renderInspectorBehaviorBadge(rec) {
  const badge = document.getElementById('ii-behavior-badge');
  if (!badge) return;
  badge.innerHTML = '';
  if (!rec) return;
  const tr = TRAJ[rec.pos_id];
  if (!tr) return;
  const b = tr.behavior || 'unknown';
  badge.appendChild(el('span', { class: 'bbadge ' + b }, b.toUpperCase()));
}

function renderInspectorKEOverlay(rec) {
  const root = document.getElementById('ii-th-svg');
  const sub = document.getElementById('ii-th-sub');
  const kpi = document.getElementById('ii-traj-kpi');
  if (!root) return;
  while (root.firstChild) root.removeChild(root.firstChild);
  if (kpi) kpi.innerHTML = '';
  if (!rec) return;
  const tr = TRAJ[rec.pos_id];
  if (!tr) {
    if (sub) sub.textContent = '(no trajectory)';
    return;
  }
  if (sub) sub.textContent = '(behavior: ' + tr.behavior + ')';
  const W = 200, H = 70;
  const pad = { l: 4, r: 4, t: 4, b: 6 };
  const plotW = W - pad.l - pad.r, plotH = H - pad.t - pad.b;
  const T = tr.ke.length;
  if (!T) return;
  let mx = 0;
  for (const v of tr.ke) if (v > mx) mx = v;
  if (mx <= 0) mx = 1;
  // shade contact bands
  let inBand = false, bandStart = 0;
  for (let i = 0; i < T; i++) {
    const eng = tr.contact[i];
    if (eng && !inBand) { inBand = true; bandStart = i; }
    if ((!eng || i === T - 1) && inBand) {
      const end = eng && i === T - 1 ? i : i;
      const x0 = pad.l + (bandStart / (T - 1)) * plotW;
      const x1 = pad.l + (end / (T - 1)) * plotW;
      root.appendChild(svg('rect', {
        x: x0, y: pad.t, width: Math.max(1, x1 - x0), height: plotH,
        fill: 'rgba(180,110,255,0.15)'
      }));
      inBand = false;
    }
  }
  // initial KE line
  const yInit = pad.t + (1 - tr.init_ke / mx) * plotH;
  root.appendChild(svg('line', { x1: pad.l, y1: yInit, x2: pad.l + plotW, y2: yInit, stroke: 'rgba(77,214,255,0.45)', 'stroke-width': 0.6, 'stroke-dasharray': '3,2' }));
  // final KE line
  const yFin = pad.t + (1 - tr.final_ke / mx) * plotH;
  root.appendChild(svg('line', { x1: pad.l, y1: yFin, x2: pad.l + plotW, y2: yFin, stroke: 'rgba(74,223,161,0.55)', 'stroke-width': 0.6, 'stroke-dasharray': '3,2' }));
  // KE curve
  const c = BEHAVIOR_COLOR[tr.behavior] || BEHAVIOR_COLOR.unknown;
  const pts = [];
  for (let i = 0; i < T; i++) {
    const xp = pad.l + (i / (T - 1)) * plotW;
    const yp = pad.t + (1 - tr.ke[i] / mx) * plotH;
    pts.push(xp.toFixed(1) + ',' + yp.toFixed(1));
  }
  root.appendChild(svg('polyline', { points: pts.join(' '), fill: 'none', stroke: c, 'stroke-width': 1.6 }));
  // numeric KPIs
  if (kpi) {
    const rows = [
      ['REBOUND', fmt(tr.rebound_speed, 0) + (_u('vel') ? ' ' + _u('vel') : '')],
      ['MAX PEN', fmt(tr.max_pen, 2) + (_u('disp') ? ' ' + _u('disp') : '')],
      ['t₁ CONTACT', (tr.t_first_contact != null ? (tr.t_first_contact * 1000).toFixed(2) + (_u('time') ? ' ' + _u('time') : '') : '-')],
      ['KE RETAIN', (tr.ke_retention * 100).toFixed(0) + ' %']
    ];
    for (const r of rows) {
      kpi.appendChild(el('div', { class: 'iirow' }, [el('span', null, r[0]), el('b', null, r[1])]));
    }
  }
}

/* --- Page 4: Per-Part Peak G (bar + line + table) ------------------ */
const PPG_PALETTE = [
  '#4dd6ff', '#b46eff', '#f0a830', '#4adfa1', '#ff9eb9',
  '#c8d4ff', '#7a9cff', '#ffd34d', '#6fe2cd', '#ff8a5b',
  '#a0e34a', '#e066d4', '#5cb0ff', '#ffcf66'
];

"""


_JS_S5_DOE = r"""/* ===================================================================
 * SECTION 05 — DOE Analysis (multi-position spatial view)
 * =================================================================== */

// Mirror the existing BEHAVIOR_COLOR (Section 3 / trajectory section) so
// the same physical behavior class is never shown in two different colors
// across the report. The audit confirmed Section 05 previously had a
// distinct palette where rebound was blue here but orange in the CSS
// `.bbadge.rebound` rule — visually misleading.
const DOE_BEHAVIOR_COLOR = BEHAVIOR_COLOR;

function _doeRenderFailureRisk(doe){
  const host = document.getElementById('doe-failure-risk-body');
  if(!host) return;
  host.innerHTML = '';
  const data = (doe && doe.advanced && doe.advanced.failure_risk) || null;

  if(!data || data.available === false){
    const reason = data && data.reason === 'no_overlap'
      ? '항복응력 메타데이터와 해석 결과 부품이 겹치지 않습니다.'
      : '항복응력(yield_stress_by_part) 데이터가 없어 안전율을 계산할 수 없습니다.';
    host.appendChild(el('div', {class:'doe-empty'}, reason));
    return;
  }

  const positions = (doe && doe.positions) || [];
  const grid = (doe && doe.grid) || {nx:5, ny:5};
  const nx = grid.nx || 5, ny = grid.ny || 5;
  const sfMatrix = data.sf_matrix || {};
  const minByPos = data.min_sf_per_position || {};
  const dangerT = data.danger_threshold || 1.0;
  const riskT = data.risk_threshold || 2.0;

  const INF = Number.POSITIVE_INFINITY;
  const sfNum = (v) => (v === 'inf' || v === null || v === undefined) ? INF : Number(v);
  const sfLabel = (v) => {
    const n = sfNum(v);
    if(!isFinite(n)) return '∞';
    if(n >= 100) return n.toFixed(0);
    if(n >= 10)  return n.toFixed(1);
    return n.toFixed(2);
  };
  const sfColor = (n) => {
    if(!isFinite(n)) return 'var(--good)';
    if(n < dangerT) return 'var(--crit)';
    if(n < riskT)   return 'var(--warn)';
    return 'var(--good)';
  };

  // ---- layout: grid heatmap (left) + ranking (right) ----
  const wrap = el('div', {class:'doe-failrisk-wrap'});
  host.appendChild(wrap);

  // -- LEFT: 5x5 grid --
  const left = el('div', {class:'doe-failrisk-left'});
  wrap.appendChild(left);
  left.appendChild(el('div', {class:'doe-failrisk-subhead'}, '위치별 최소 SF (5×5)'));
  const _dgFR = (typeof DATA !== 'undefined' && DATA.device_geometry) || {aspect: 1};
  const _arFR = (_dgFR.aspect && isFinite(_dgFR.aspect) && _dgFR.aspect > 0) ? _dgFR.aspect : 1;
  const gridBox = el('div', {class:'doe-failrisk-grid', style:`grid-template-columns:repeat(${nx},1fr);grid-template-rows:repeat(${ny},1fr);aspect-ratio:${_arFR} / 1;`});
  left.appendChild(gridBox);

  // Build cell map by (row,col)
  const cellByRC = {};
  positions.forEach(p => { cellByRC[`${p.row}_${p.col}`] = p; });

  for(let r=ny-1; r>=0; r--){
    for(let c=0; c<nx; c++){
      const p = cellByRC[`${r}_${c}`];
      if(!p){
        gridBox.appendChild(el('div', {class:'doe-failrisk-cell doe-failrisk-empty'}, '·'));
        continue;
      }
      const info = minByPos[String(p.pos_id)];
      if(!info){
        const cell = el('div', {class:'doe-failrisk-cell doe-failrisk-nodata',
          title:`${p.pos_id}: 항복 데이터 없는 부품들만 검출`}, [
          el('div', {class:'doe-failrisk-pid'}, p.label || p.pos_id),
          el('div', {class:'doe-failrisk-sfval'}, '—'),
        ]);
        gridBox.appendChild(cell);
        continue;
      }
      const sfN = sfNum(info.min_sf);
      const col = sfColor(sfN);
      const cell = el('div', {
        class:'doe-failrisk-cell',
        style:`background:${col};`,
        title:`${p.pos_id}  min SF=${sfLabel(info.min_sf)}  worst=${info.worst_part_name} (id ${info.worst_part_id})`
      }, [
        el('div', {class:'doe-failrisk-pid'}, p.label || p.pos_id),
        el('div', {class:'doe-failrisk-sfval'}, 'SF ' + sfLabel(info.min_sf)),
      ]);
      gridBox.appendChild(cell);
    }
  }

  // legend
  const legend = el('div', {class:'doe-failrisk-legend'}, [
    el('span', {class:'doe-failrisk-lg crit'}, `SF < ${dangerT.toFixed(1)} 항복 초과`),
    el('span', {class:'doe-failrisk-lg warn'}, `${dangerT.toFixed(1)} ≤ SF < ${riskT.toFixed(1)} 마진 부족`),
    el('span', {class:'doe-failrisk-lg good'}, `SF ≥ ${riskT.toFixed(1)} 안전`),
  ]);
  left.appendChild(legend);

  // -- RIGHT: ranking --
  const right = el('div', {class:'doe-failrisk-right'});
  wrap.appendChild(right);
  const atRisk = data.parts_at_risk || [];
  right.appendChild(el('div', {class:'doe-failrisk-subhead'},
    `위험 부품 랭킹 (SF < ${riskT.toFixed(1)}, 총 ${atRisk.length}개)`));

  if(atRisk.length === 0){
    right.appendChild(el('div', {class:'doe-empty'},
      `모든 부품의 최소 SF ≥ ${riskT.toFixed(1)} — 안전 마진 충분.`));
  } else {
    const top = atRisk.slice(0, 10);
    const list = el('div', {class:'doe-failrisk-list'});
    right.appendChild(list);

    top.forEach((row, idx) => {
      const sfN = sfNum(row.min_sf);
      const dotColor = sfColor(sfN);

      // distribution across positions for whisker
      const partSFs = sfMatrix[String(row.part_id)] || {};
      const vals = Object.values(partSFs).map(sfNum).filter(v => isFinite(v));
      let whiskerSVG = null;
      if(vals.length >= 2){
        const mn = Math.min(...vals);
        const mx = Math.max(...vals);
        const span = mx - mn;
        const W = 110, H = 14, padX = 4;
        const x = (v) => padX + (span > 0 ? (v - mn) / span * (W - 2*padX) : (W - 2*padX)/2);
        whiskerSVG = svg('svg', {width:W, height:H, class:'doe-failrisk-whisker', viewBox:`0 0 ${W} ${H}`}, [
          svg('line', {x1:x(mn), y1:H/2, x2:x(mx), y2:H/2, stroke:'var(--dim)', 'stroke-width':1}),
          ...vals.map(v => svg('circle', {cx:x(v), cy:H/2, r:2, fill: sfColor(v)})),
          svg('circle', {cx:x(sfN), cy:H/2, r:3.2, fill:'var(--fg)', stroke: dotColor, 'stroke-width':1.5}),
        ]);
      }

      const xyStr = (row.worst_pos_xy && row.worst_pos_xy.length === 2)
        ? `x=${fmt(row.worst_pos_xy[0],2)}, y=${fmt(row.worst_pos_xy[1],2)}`
        : '';
      const item = el('div', {class:'doe-failrisk-item'}, [
        el('span', {class:'doe-failrisk-rank'}, String(idx + 1)),
        el('span', {class:'doe-failrisk-dot', style:`background:${dotColor};`}),
        el('div', {class:'doe-failrisk-name'}, [
          el('div', {class:'doe-failrisk-pname'}, `${row.part_name} (id ${row.part_id})`),
          el('div', {class:'doe-failrisk-pmeta'}, `worst @ ${row.worst_pos_id}  ${xyStr}`),
        ]),
        el('div', {class:'doe-failrisk-sf'}, [
          el('div', {class:'doe-failrisk-sfbig', style:`color:${dotColor};`}, 'SF ' + sfLabel(row.min_sf)),
          whiskerSVG ? whiskerSVG : el('div', {class:'doe-failrisk-pmeta'}, '단일 위치'),
        ]),
      ]);
      list.appendChild(item);
    });
  }

  // footer summary
  const footer = el('div', {class:'doe-failrisk-foot'},
    `항복 데이터 보유 부품 ${data.n_parts_with_yield}개 중 ${data.n_parts_evaluated}개 평가됨.`);
  host.appendChild(footer);
}

function _doeCorrDivergingColor(r) {
  // Diverging palette: red (-1) -> dim mid (0) -> cyan/blue (+1).
  // Returns rgba string. Uses --crit and --accent vibes for theme cohesion.
  if (r == null || !isFinite(r)) return 'rgba(170,178,207,0.08)';
  const t = Math.max(-1, Math.min(1, r));
  if (t >= 0) {
    // 0 -> #1a1e2e (near bg2), 1 -> cyan-ish (90,210,240)
    const a = t;
    const cr = Math.round(26 + (90 - 26) * a);
    const cg = Math.round(30 + (210 - 30) * a);
    const cb = Math.round(46 + (240 - 46) * a);
    return 'rgb(' + cr + ',' + cg + ',' + cb + ')';
  } else {
    const a = -t;
    // 0 -> #1a1e2e, -1 -> warm red (240,90,80)
    const cr = Math.round(26 + (240 - 26) * a);
    const cg = Math.round(30 + (90 - 30) * a);
    const cb = Math.round(46 + (80 - 46) * a);
    return 'rgb(' + cr + ',' + cg + ',' + cb + ')';
  }
}

function _doeRenderCorrNetwork(doe) {
  const host = document.getElementById('doe-corr-network');
  if (!host) return;
  host.innerHTML = '';
  const data = (doe && doe.advanced && doe.advanced.corr_network) || null;
  if (!data || !data.parts_listed || data.parts_listed.length < 2 || !data.corr_matrix) {
    host.appendChild(el('div', { class: 'no-data', style: { padding: '24px', color: 'var(--dim)', 'text-align': 'center' } },
      [document.createTextNode('상관 분석 데이터 없음 — 위치 수 < 2 또는 peak_g 데이터 부족')]));
    return;
  }

  const parts = data.parts_listed;
  const N = parts.length;
  const M = data.corr_matrix;
  const nPos = data.n_positions || 0;
  const thr = (typeof data.corr_threshold === 'number') ? data.corr_threshold : 0.7;

  // Layout: heatmap (left, flex) + cluster summary (right, fixed width)
  const wrap = el('div', { class: 'doe-corr-wrap',
    style: { display: 'grid', 'grid-template-columns': 'minmax(0, 1.3fr) minmax(260px, 1fr)',
             gap: '14px', 'align-items': 'start' } });

  // --- Heatmap (SVG) ----------------------------------------------------
  const cell = 30;
  const labelPad = 110;
  const topPad = 110;
  const vbW = labelPad + N * cell + 70; // +70 for legend
  const vbH = topPad + N * cell + 30;
  const svgRoot = svg('svg', {
    viewBox: '0 0 ' + vbW + ' ' + vbH,
    preserveAspectRatio: 'xMinYMin meet',
    style: { width: '100%', height: 'auto', background: 'var(--bg2)', 'border-radius': '6px' }
  });

  // Row labels (left, part_name) + column labels (top, rotated)
  for (let i = 0; i < N; i++) {
    const pn = parts[i].part_name || ('part_' + parts[i].part_id);
    const shortPn = pn.length > 14 ? (pn.slice(0, 12) + '…') : pn;
    // row label
    svgRoot.appendChild(svg('text', {
      x: labelPad - 6, y: topPad + i * cell + cell * 0.66,
      fill: 'var(--fg2)', 'font-size': 10, 'text-anchor': 'end',
    }, [document.createTextNode(shortPn)]));
    // col label (rotated)
    const cx = labelPad + i * cell + cell * 0.5;
    const cy = topPad - 6;
    svgRoot.appendChild(svg('text', {
      x: cx, y: cy, fill: 'var(--fg2)', 'font-size': 10, 'text-anchor': 'start',
      transform: 'rotate(-55 ' + cx + ' ' + cy + ')',
    }, [document.createTextNode(shortPn)]));
  }

  // Cells
  for (let i = 0; i < N; i++) {
    const rowKey = String(parts[i].part_id);
    const rowMap = M[rowKey] || {};
    for (let j = 0; j < N; j++) {
      const colKey = String(parts[j].part_id);
      const r = (typeof rowMap[colKey] === 'number') ? rowMap[colKey] : null;
      const fill = _doeCorrDivergingColor(r);
      const x = labelPad + j * cell;
      const y = topPad + i * cell;
      const isDiag = (i === j);
      const strong = (r != null && Math.abs(r) >= thr && !isDiag);
      const cellEl = svg('rect', {
        x: x, y: y, width: cell - 1.5, height: cell - 1.5,
        fill: fill,
        stroke: strong ? 'rgba(255,255,255,0.55)' : 'rgba(0,0,0,0.25)',
        'stroke-width': strong ? 1.2 : 0.5,
        rx: 2, ry: 2,
      });
      // Tooltip via <title>
      const piName = parts[i].part_name;
      const pjName = parts[j].part_name;
      const rTxt = (r == null) ? 'n/a' : r.toFixed(3);
      cellEl.appendChild(svg('title', {}, [document.createTextNode(
        piName + ' × ' + pjName + '\nr = ' + rTxt + '\nn_positions = ' + nPos
      )]));
      svgRoot.appendChild(cellEl);

      // Inline r text on cells with |r| >= 0.5 OR diagonal — keep grid readable
      if (r != null && (Math.abs(r) >= 0.5 || isDiag)) {
        const txt = (Math.abs(r) >= 0.995) ? r.toFixed(2) : r.toFixed(2);
        svgRoot.appendChild(svg('text', {
          x: x + (cell - 1.5) / 2, y: y + (cell - 1.5) / 2 + 3,
          fill: (Math.abs(r) > 0.55 ? '#0a0c14' : 'var(--fg)'),
          'font-size': 9, 'text-anchor': 'middle', 'pointer-events': 'none',
          style: { 'font-family': 'ui-monospace, SFMono-Regular, monospace' },
        }, [document.createTextNode(txt)]));
      }
    }
  }

  // Legend (diverging color bar) at right of matrix
  const legX = labelPad + N * cell + 16;
  const legY0 = topPad;
  const legH = N * cell;
  const legW = 12;
  const nSteps = 30;
  for (let k = 0; k < nSteps; k++) {
    const t = k / (nSteps - 1);
    const r = 1.0 - 2.0 * t; // top=+1, bottom=-1
    svgRoot.appendChild(svg('rect', {
      x: legX, y: legY0 + t * legH, width: legW, height: legH / nSteps + 0.5,
      fill: _doeCorrDivergingColor(r), stroke: 'none',
    }));
  }
  // Legend ticks: +1, 0, -1
  const legendTick = (val, frac) => {
    svgRoot.appendChild(svg('text', {
      x: legX + legW + 4, y: legY0 + frac * legH + 3,
      fill: 'var(--fg2)', 'font-size': 10,
    }, [document.createTextNode(val)]));
  };
  legendTick('+1', 0.0);
  legendTick(' 0', 0.5);
  legendTick('-1', 1.0);
  svgRoot.appendChild(svg('text', {
    x: legX + legW / 2, y: legY0 + legH + 16,
    fill: 'var(--dim)', 'font-size': 9, 'text-anchor': 'middle',
  }, [document.createTextNode('r')]));

  // Footer note: n + threshold
  svgRoot.appendChild(svg('text', {
    x: labelPad, y: vbH - 6, fill: 'var(--dim)', 'font-size': 10,
  }, [document.createTextNode('n_positions = ' + nPos + '   ·   strong if |r| ≥ ' + thr.toFixed(2))]));

  wrap.appendChild(svgRoot);

  // --- Cluster summary panel -------------------------------------------
  const summary = el('div', { class: 'doe-corr-clusters',
    style: { display: 'flex', 'flex-direction': 'column', gap: '8px' } });

  const clusters = data.clusters || [];
  const multiClusters = clusters.filter(function(c) { return (c.members || []).length >= 2; });
  const soloCount = clusters.length - multiClusters.length;

  summary.appendChild(el('div', {
    style: { color: 'var(--fg)', 'font-size': 12, 'font-weight': 600, 'margin-bottom': '2px' }
  }, [document.createTextNode('검출된 클러스터 — ' + multiClusters.length + '개 (단독 ' + soloCount + '개)')]));

  if (multiClusters.length === 0) {
    summary.appendChild(el('div', {
      style: { color: 'var(--dim)', 'font-size': 11, padding: '12px',
               background: 'var(--bg2)', 'border-radius': '6px',
               border: '1px solid var(--line)' }
    }, [document.createTextNode('|r| ≥ ' + thr.toFixed(2) + ' 인 강한 상관 부품 쌍 없음. 모든 부품이 독립적 응답.')]));
  }

  // Cluster color from gColor by cluster index spread
  multiClusters.forEach(function(c, idx) {
    const t = (multiClusters.length <= 1) ? 0.5 : (idx / (multiClusters.length - 1));
    const accent = gColor(t);
    const card = el('div', {
      style: {
        background: 'var(--bg2)',
        border: '1px solid var(--line)',
        'border-left': '3px solid ' + accent,
        'border-radius': '6px',
        padding: '8px 10px',
      }
    });
    const head = el('div', {
      style: { display: 'flex', 'justify-content': 'space-between', 'align-items': 'baseline', 'margin-bottom': '4px' }
    });
    head.appendChild(el('span', {
      style: { color: 'var(--fg)', 'font-size': 11, 'font-weight': 600 }
    }, [document.createTextNode('클러스터 ' + (c.cluster_id != null ? c.cluster_id : idx) + '  (' + c.size + ' parts)')]));
    head.appendChild(el('span', {
      style: { color: 'var(--accent)', 'font-size': 11,
               'font-family': 'ui-monospace, SFMono-Regular, monospace' }
    }, [document.createTextNode('응답 일관성 r̄ = ' + (typeof c.mean_r === 'number' ? c.mean_r.toFixed(3) : 'n/a'))]));
    card.appendChild(head);

    const names = (c.member_names || []).slice();
    const list = el('div', {
      style: { color: 'var(--fg2)', 'font-size': 10.5, 'line-height': 1.5 }
    });
    names.forEach(function(nm, k) {
      const tag = el('span', {
        style: {
          display: 'inline-block',
          padding: '1px 6px',
          margin: '2px 4px 2px 0',
          background: 'rgba(255,255,255,0.04)',
          border: '1px solid var(--line)',
          'border-radius': '3px',
          color: 'var(--fg)',
        }
      }, [document.createTextNode(nm)]);
      list.appendChild(tag);
    });
    card.appendChild(list);
    summary.appendChild(card);
  });

  if (soloCount > 0) {
    const solos = clusters.filter(function(c) { return (c.members || []).length < 2; });
    const soloNames = [];
    solos.forEach(function(c) { (c.member_names || []).forEach(function(nm) { soloNames.push(nm); }); });
    summary.appendChild(el('div', {
      style: { color: 'var(--dim)', 'font-size': 10.5, padding: '6px 10px',
               'border-top': '1px dashed var(--line)', 'margin-top': '4px' }
    }, [document.createTextNode('단독 부품: ' + (soloNames.join(', ') || '—'))]));
  }

  wrap.appendChild(summary);
  host.appendChild(wrap);
}

function _doeRenderTOA(doe) {
  const root = document.getElementById('doe-toa-root');
  if (!root) return;
  while (root.firstChild) root.removeChild(root.firstChild);
  const toa = (doe.advanced || {}).toa;
  if (!toa) {
    root.appendChild(el('div', { class: 'doe-toa-empty' }, 'TOA payload 없음.'));
    return;
  }
  const perPos = toa.toa_per_position || {};
  const meanPerPart = toa.mean_arrival_per_part || {};
  const behaviorByPos = toa.behavior_by_pos || {};

  // --- LEFT: strip chart for worst position --------------------------------
  const worstPid = doe.worst_position ? doe.worst_position.pos_id : null;
  const left = el('div', { class: 'toa-left' });

  let pickedPosId = null;
  let rows = [];
  if (worstPid && Array.isArray(perPos[worstPid]) && perPos[worstPid].length) {
    pickedPosId = worstPid;
    rows = perPos[worstPid];
  } else {
    // fallback: first non-empty pos
    for (const k of Object.keys(perPos)) {
      if (Array.isArray(perPos[k]) && perPos[k].length) {
        pickedPosId = k; rows = perPos[k]; break;
      }
    }
  }

  const leftHeader = el('div', { class: 'toa-sec-h' });
  leftHeader.appendChild(el('span', { class: 'toa-sec-t' }, '최악 위치의 응답 도착 순서'));
  if (pickedPosId) {
    const behavior = behaviorByPos[pickedPosId] || 'unknown';
    const swatchColor = (typeof BEHAVIOR_COLOR !== 'undefined' && BEHAVIOR_COLOR[behavior])
      ? BEHAVIOR_COLOR[behavior]
      : '#5c6383';
    const pidSpan = el('span', { class: 'toa-sec-d' });
    pidSpan.appendChild(document.createTextNode('pos ' + pickedPosId + ' · '));
    pidSpan.appendChild(el('span', { class: 'toa-sw', style: { background: swatchColor } }));
    pidSpan.appendChild(document.createTextNode(' ' + behavior));
    leftHeader.appendChild(pidSpan);
  }
  left.appendChild(leftHeader);

  if (!rows.length) {
    left.appendChild(el('div', { class: 'doe-toa-empty' }, '도착 시간 데이터 없음.'));
  } else {
    const dts = rows.map(r => Number(r.dt_ms));
    const dtMin = Math.min(...dts);
    const dtMax = Math.max(...dts);
    const span = Math.max(1e-6, dtMax - Math.min(0, dtMin));
    const behaviorPos = behaviorByPos[pickedPosId] || 'unknown';
    const stripColor = (typeof BEHAVIOR_COLOR !== 'undefined' && BEHAVIOR_COLOR[behaviorPos])
      ? BEHAVIOR_COLOR[behaviorPos]
      : '#5c6383';

    const strip = el('div', { class: 'toa-strip' });
    rows.forEach((r, idx) => {
      const row = el('div', { class: 'toa-bar-row' });
      row.appendChild(el('div', { class: 'toa-bar-name', title: r.part_name }, r.part_name));
      const track = el('div', { class: 'toa-bar-track' });
      const dt = Number(r.dt_ms);
      // length: clamp at 0, normalize against span
      const lenT = Math.max(0, (dt - Math.min(0, dtMin))) / span;
      const fill = el('div', {
        class: 'toa-bar-fill',
        style: {
          width: (lenT * 100).toFixed(1) + '%',
          background: stripColor,
          opacity: (0.45 + 0.55 * (1 - idx / Math.max(1, rows.length - 1))).toFixed(2),
        },
      });
      track.appendChild(fill);
      row.appendChild(track);
      row.appendChild(el('div', { class: 'toa-bar-val' }, fmt(dt, 2) + ' ms'));
      strip.appendChild(row);
    });
    left.appendChild(strip);
    const axis = el('div', { class: 'toa-axis' });
    axis.appendChild(el('span', {}, fmt(Math.min(0, dtMin), 2) + ' ms'));
    axis.appendChild(el('span', { class: 'toa-axis-mid' }, 'Δt = part peak_g − impactor 첫 접촉'));
    axis.appendChild(el('span', {}, fmt(dtMax, 2) + ' ms'));
    left.appendChild(axis);
  }

  // --- RIGHT: always-early / always-late lists -----------------------------
  const right = el('div', { class: 'toa-right' });

  function _mkList(title, dim, entries, accent) {
    const box = el('div', { class: 'toa-listbox' });
    const h = el('div', { class: 'toa-sec-h' });
    h.appendChild(el('span', { class: 'toa-sec-t', style: { color: accent } }, title));
    h.appendChild(el('span', { class: 'toa-sec-d' }, dim));
    box.appendChild(h);
    if (!entries.length) {
      box.appendChild(el('div', { class: 'doe-toa-empty' }, '데이터 부족 (n_positions ≥ 2 필요).'));
      return box;
    }
    const ul = el('div', { class: 'toa-list' });
    entries.forEach(e => {
      const li = el('div', { class: 'toa-li' });
      li.appendChild(el('div', { class: 'toa-li-name', title: e.part_name }, e.part_name));
      const meanTxt = fmt(e.mean_dt_ms, 2);
      const stdTxt = fmt(e.std_dt_ms, 2);
      const stat = el('div', { class: 'toa-li-stat' });
      stat.appendChild(el('span', { class: 'toa-li-mean' }, meanTxt + ' ms'));
      stat.appendChild(el('span', { class: 'toa-li-std' }, ' ± ' + stdTxt));
      stat.appendChild(el('span', { class: 'toa-li-n' }, ' · n=' + e.n_positions));
      li.appendChild(stat);
      ul.appendChild(li);
    });
    box.appendChild(ul);
    return box;
  }

  // Build entries from mean_arrival_per_part (require >= 2 positions)
  const entries = Object.keys(meanPerPart).map(pid => {
    const info = meanPerPart[pid] || {};
    // lookup name from doe.positions/parts: use a simple scan of any toa row
    let pname = 'part_' + pid;
    for (const k of Object.keys(perPos)) {
      const found = (perPos[k] || []).find(r => String(r.part_id) === String(pid));
      if (found) { pname = found.part_name; break; }
    }
    return {
      part_id: Number(pid),
      part_name: pname,
      mean_dt_ms: Number(info.mean_dt_ms || 0),
      std_dt_ms: Number(info.std_dt_ms || 0),
      n_positions: Number(info.n_positions || 0),
    };
  }).filter(e => e.n_positions >= 2);

  const earlyList = entries.slice().sort((a, b) => a.mean_dt_ms - b.mean_dt_ms).slice(0, 6);
  const lateList  = entries.slice().sort((a, b) => b.mean_dt_ms - a.mean_dt_ms).slice(0, 6);

  right.appendChild(_mkList('항상 빠른 부품', '평균 Δt 최소 6개', earlyList, 'var(--good, #4adfa1)'));
  right.appendChild(_mkList('항상 느린 부품', '평균 Δt 최대 6개', lateList, 'var(--warn, #f0a830)'));

  // Tagline at top: earliest / latest
  if (toa.earliest_part || toa.latest_part) {
    const tag = el('div', { class: 'toa-tagline' });
    if (toa.earliest_part) {
      tag.appendChild(el('span', { class: 'toa-tag toa-tag-e' },
        '가장 빠른 평균 Δt: ' + toa.earliest_part.part_name +
        ' (' + fmt(toa.earliest_part.mean_dt_ms, 2) + ' ms, n=' + toa.earliest_part.n_positions + ')'));
    }
    if (toa.latest_part) {
      tag.appendChild(el('span', { class: 'toa-tag toa-tag-l' },
        '가장 느린 평균 Δt: ' + toa.latest_part.part_name +
        ' (' + fmt(toa.latest_part.mean_dt_ms, 2) + ' ms, n=' + toa.latest_part.n_positions + ')'));
    }
    root.appendChild(tag);
  }

  const grid = el('div', { class: 'toa-grid' });
  grid.appendChild(left);
  grid.appendChild(right);
  root.appendChild(grid);
}

const IDW_STATE = { metric: 'peak_g' };

function _idwMetricLabel(k) {
  return k === 'peak_stress' ? 'PEAK σ' : 'PEAK G';
}
function _idwMetricUnit(k) {
  return k === 'peak_stress' ? _u('stress') : _u('acc');
}

function _doeRenderIdwPredictor(doe) {
  const host = document.getElementById('idw-pred-panel');
  if (!host) return;
  const adv = doe && doe.advanced ? doe.advanced.idw_predictor : null;
  const svgEl = document.getElementById('idw-pred-svg');
  const canvasEl = document.getElementById('idw-pred-canvas');
  const btnHost = document.getElementById('idw-pred-buttons');
  const info = document.getElementById('idw-pred-info');
  if (!svgEl || !canvasEl || !btnHost || !info) return;

  if (!adv || !adv.grid_fine || !adv.measured_points || adv.measured_points.length < 2) {
    while (svgEl.firstChild) svgEl.removeChild(svgEl.firstChild);
    svgEl.appendChild(svg('text', { x: 200, y: 200, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 11 }, [document.createTextNode('IDW 데이터 없음 (측정점 부족)')]));
    const _ctx0 = canvasEl.getContext('2d');
    _ctx0.fillStyle = '#0e1320';
    _ctx0.fillRect(0, 0, canvasEl.width, canvasEl.height);
    btnHost.innerHTML = '';
    info.innerHTML = '';
    const _looBar0 = document.getElementById('idw-pred-loo');
    if (_looBar0) { _looBar0.style.display = 'none'; _looBar0.innerHTML = ''; }
    return;
  }

  // metric toggle buttons (built once per render call to stay in sync)
  btnHost.innerHTML = '';
  ['peak_g', 'peak_stress'].forEach(k => {
    const b = el('button', {
      class: 'btn' + (IDW_STATE.metric === k ? ' active' : ''),
      'data-idw-metric': k
    }, _idwMetricLabel(k));
    b.addEventListener('click', () => {
      IDW_STATE.metric = k;
      _doeRenderIdwPredictor(doe);
    });
    btnHost.appendChild(b);
  });

  const gf = adv.grid_fine;
  const NX = gf.nx_fine | 0, NY = gf.ny_fine | 0;
  const bb = gf.bbox;
  const arr = gf[IDW_STATE.metric] || [];
  if (NX < 2 || NY < 2 || arr.length !== NX * NY) {
    while (svgEl.firstChild) svgEl.removeChild(svgEl.firstChild);
    svgEl.appendChild(svg('text', { x: 200, y: 200, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 11 }, [document.createTextNode('IDW 그리드 형상 오류')]));
    return;
  }

  // Color scaling: use the fine-grid max (so peaks are visible). Guard zero.
  let vmin = Infinity, vmax = -Infinity;
  for (let i = 0; i < arr.length; i++) {
    const v = arr[i];
    if (!isFinite(v)) continue;
    if (v < vmin) vmin = v;
    if (v > vmax) vmax = v;
  }
  if (!isFinite(vmin) || !isFinite(vmax) || vmax <= vmin) {
    vmin = 0; vmax = vmax > 0 ? vmax : 1;
  }
  const span = vmax - vmin || 1;

  while (svgEl.firstChild) svgEl.removeChild(svgEl.firstChild);
  const _dgI = DATA.device_geometry || {aspect: 1};
  const _arI = (_dgI.aspect && isFinite(_dgI.aspect) && _dgI.aspect > 0) ? _dgI.aspect : 1;
  const vbW = 540, vbH = Math.max(120, Math.round(vbW / _arI));
  svgEl.setAttribute('viewBox', '0 0 ' + vbW + ' ' + vbH);
  svgEl.setAttribute('preserveAspectRatio', 'xMidYMid meet');

  // Resize canvas to match SVG viewBox aspect (HiDPI handled by CSS width:100%)
  canvasEl.width = vbW;
  canvasEl.height = vbH;

  const padL = 56, padR = 18, padT = 22, padB = 38;
  const plotW = vbW - padL - padR;
  const plotH = vbH - padT - padB;
  const cellW = plotW / NX;
  const cellH = plotH / NY;

  const xmin = bb[0], ymin = bb[1], xmax = bb[2], ymax = bb[3];
  const xSpan = xmax - xmin || 1;
  const ySpan = ymax - ymin || 1;
  const xToPx = x => padL + ((x - xmin) / xSpan) * plotW;
  const yToPx = y => padT + (1 - (y - ymin) / ySpan) * plotH; // flip Y

  // Canvas-based heatmap renderer (called by canvasZoomPan on every transform).
  function drawIdwHeatmap(ctx, transform) {
    ctx.fillStyle = '#0e1320';
    ctx.fillRect(0, 0, vbW, vbH);
    ctx.save();
    const tr = transform || { tx: 0, ty: 0, scale: 1 };
    ctx.translate(tr.tx, tr.ty);
    ctx.scale(tr.scale, tr.scale);
    for (let j = 0; j < NY; j++) {
      for (let i = 0; i < NX; i++) {
        const v = arr[j * NX + i];
        const t = Math.max(0, Math.min(1, (v - vmin) / span));
        const px = padL + i * cellW;
        const py = padT + (NY - 1 - j) * cellH;
        ctx.fillStyle = gColor(t);
        ctx.fillRect(px, py, cellW + 0.6, cellH + 0.6);
      }
    }
    ctx.restore();
  }
  canvasZoomPan(canvasEl, { draw: (ctx, t) => drawIdwHeatmap(ctx, t) });
  // Always draw an initial frame (canvasZoomPan only attaches once; reuse on
  // re-render needs a manual redraw with current state).
  drawIdwHeatmap(canvasEl.getContext('2d'), { tx: 0, ty: 0, scale: 1 });

  // Axis box (SVG overlay)
  svgEl.appendChild(svg('rect', {
    x: padL, y: padT, width: plotW, height: plotH,
    fill: 'none', stroke: 'rgba(255,255,255,0.18)', 'stroke-width': 0.6
  }));

  // LOO validation info bar + per-point error lookup
  const looBar = document.getElementById('idw-pred-loo');
  const loo = adv.loo_validation || null;
  const looErrByPos = {};
  if (loo && Array.isArray(loo.per_point)) {
    loo.per_point.forEach(p => { looErrByPos[p.pos_id] = p; });
  }
  if (looBar) {
    if (loo && IDW_STATE.metric === 'peak_g') {
      looBar.style.display = '';
      looBar.innerHTML =
        '<b>보간 신뢰도 (LOO)</b>: RMSE = <b>' + fmt(loo.rmse_peak_g, 2) + '</b> ' + _u('acc') +
        ' &middot; 중간 오차 = <b>' + (Number(loo.median_err_pct)).toFixed(1) + '%</b>' +
        ' &middot; 최대 오차 위치 = <b>' + (loo.max_error_pos_id == null ? '-' : loo.max_error_pos_id) + '</b>';
    } else {
      looBar.style.display = 'none';
      looBar.innerHTML = '';
    }
  }

  // Overlay measured points (color by LOO error % when peak_g + LOO available)
  const medianErrPct = (loo && isFinite(loo.median_err_pct)) ? Number(loo.median_err_pct) : null;
  (adv.measured_points || []).forEach(m => {
    const cx = xToPx(m.x);
    const cy = yToPx(m.y);
    const g = svg('g', null);
    let dotFill = '#0a0c14';
    const ep = looErrByPos[m.pos_id];
    if (IDW_STATE.metric === 'peak_g' && ep && medianErrPct !== null && medianErrPct > 0) {
      const pct = Number(ep.error_pct);
      if (pct < medianErrPct) dotFill = '#2ecc71';            // green
      else if (pct < 2 * medianErrPct) dotFill = '#f39c12';   // orange
      else dotFill = '#e74c3c';                               // red
    }
    g.appendChild(svg('circle', { cx: cx, cy: cy, r: 4.2, fill: dotFill, stroke: '#ffffff', 'stroke-width': 1.2 }));
    const v = (IDW_STATE.metric === 'peak_stress') ? m.peak_stress : m.peak_g;
    const u = _idwMetricUnit(IDW_STATE.metric);
    let tipExtra = '';
    if (IDW_STATE.metric === 'peak_g' && ep) {
      tipExtra = '\nLOO 예측 = ' + fmt(ep.predicted, 1) +
        '\nLOO 오차 = ' + fmt(ep.error_abs, 2) + ' (' + Number(ep.error_pct).toFixed(1) + '%)';
    }
    g.appendChild(svg('title', null, [document.createTextNode(
      m.pos_id + '\nx=' + m.x.toFixed(2) + ' y=' + m.y.toFixed(2) +
      '\n측정 ' + _idwMetricLabel(IDW_STATE.metric) + ' = ' + fmt(v, 1) + (u ? ' ' + u : '') +
      tipExtra
    )]));
    svgEl.appendChild(g);
  });

  // Highlight predicted-max sample (yellow ring + tooltip)
  const maxIdx = (adv.max_sample_idx && adv.max_sample_idx[IDW_STATE.metric]) | 0;
  if (maxIdx >= 0 && maxIdx < arr.length) {
    const mi = maxIdx % NX;
    const mj = Math.floor(maxIdx / NX);
    const mx = xmin + mi * (xSpan / (NX - 1));
    const my = ymin + mj * (ySpan / (NY - 1));
    const cx = xToPx(mx);
    const cy = yToPx(my);
    const ring = svg('g', null);
    ring.appendChild(svg('circle', { cx: cx, cy: cy, r: 10, fill: 'none', stroke: '#ffd84d', 'stroke-width': 2.2 }));
    ring.appendChild(svg('circle', { cx: cx, cy: cy, r: 2.4, fill: '#ffd84d' }));
    const u = _idwMetricUnit(IDW_STATE.metric);
    const peakV = arr[maxIdx];
    ring.appendChild(svg('title', null, [document.createTextNode(
      '예측 최대 위치\nx=' + mx.toFixed(2) + ' y=' + my.toFixed(2) +
      '\n' + _idwMetricLabel(IDW_STATE.metric) + ' ≈ ' + fmt(peakV, 1) + (u ? ' ' + u : '')
    )]));
    svgEl.appendChild(ring);

    // info line under SVG
    const u2 = _idwMetricUnit(IDW_STATE.metric);
    info.innerHTML = '<span style="color:#ffd84d">●</span> 예측 최대: ' +
      '(' + mx.toFixed(2) + ', ' + my.toFixed(2) + ')' +
      '   ' + _idwMetricLabel(IDW_STATE.metric) + ' ≈ <b>' + fmt(peakV, 1) + '</b>' +
      (u2 ? ' <span class="u">' + u2 + '</span>' : '') +
      '   ·   측정점 ' + (adv.measured_points || []).length + ' 개 기반 IDW(p=' + (adv.power || 2) + ') 보간';
  } else {
    info.innerHTML = '';
  }

  // Axes labels
  svgEl.appendChild(svg('text', { x: padL, y: padT - 6, fill: '#5c6383', 'font-size': 9 },
    [document.createTextNode('X: ' + xmin.toFixed(2) + ' → ' + xmax.toFixed(2))]));
  svgEl.appendChild(svg('text', { x: padL, y: vbH - padB + 22, fill: '#5c6383', 'font-size': 9 },
    [document.createTextNode('Y: ' + ymin.toFixed(2) + ' → ' + ymax.toFixed(2))]));
  const uLab = _idwMetricUnit(IDW_STATE.metric);
  svgEl.appendChild(svg('text', { x: vbW / 2, y: vbH - 8, fill: '#aab2cf', 'font-size': 10, 'text-anchor': 'middle' },
    [document.createTextNode('IDW(p=2) ' + NX + '×' + NY + '  ·  ' + _idwMetricLabel(IDW_STATE.metric) + (uLab ? ' (' + uLab + ')' : ''))]));

  // Color legend (right edge)
  const lgX = vbW - padR - 10;
  const lgY0 = padT + 4;
  const lgH = plotH - 8;
  const N_STOPS = 24;
  for (let s = 0; s < N_STOPS; s++) {
    const t = 1 - s / (N_STOPS - 1); // top = high
    svgEl.appendChild(svg('rect', {
      x: lgX, y: lgY0 + s * (lgH / N_STOPS),
      width: 8, height: (lgH / N_STOPS) + 0.6,
      fill: gColor(t), 'shape-rendering': 'crispEdges'
    }));
  }
  svgEl.appendChild(svg('text', { x: lgX + 4, y: lgY0 - 4, fill: '#aab2cf', 'font-size': 9, 'text-anchor': 'middle' },
    [document.createTextNode(fmt(vmax, 1))]));
  svgEl.appendChild(svg('text', { x: lgX + 4, y: lgY0 + lgH + 10, fill: '#aab2cf', 'font-size': 9, 'text-anchor': 'middle' },
    [document.createTextNode(fmt(vmin, 1))]));
}

function _doeRenderParetoSeverity(doe) {
  const host = document.getElementById('doe-pareto-severity');
  if (!host) return;
  host.innerHTML = '';
  const adv = (doe && doe.advanced) || {};
  const data = adv.pareto_severity;
  if (!data || !data.points || data.points.length === 0) {
    host.appendChild(el('div', { class: 'traj-na' }, '데이터 없음 — Pareto 분석을 수행할 수 없습니다.'));
    return;
  }
  const pts = data.points.filter(p => isFinite(p.severity) && isFinite(p.coverage));
  if (pts.length === 0) {
    host.appendChild(el('div', { class: 'traj-na' }, '유효한 포인트가 없습니다.'));
    return;
  }

  const unitAcc = (data.unit_acc) || (typeof _u === 'function' ? _u('acc') : '');

  // layout
  const W = 760, H = 460;
  const M = { l: 78, r: 24, t: 28, b: 56 };
  const innerW = W - M.l - M.r;
  const innerH = H - M.t - M.b;

  // severity log scale (guard against 0)
  const sevPos = pts.map(p => p.severity).filter(v => v > 0);
  const sevMin = sevPos.length ? Math.min.apply(null, sevPos) : 1.0;
  const sevMax = sevPos.length ? Math.max.apply(null, sevPos) : 10.0;
  const useLog = (sevMax / Math.max(sevMin, 1e-9)) > 50.0;
  const lo = useLog ? Math.log10(Math.max(sevMin, 1e-9)) : sevMin;
  const hi = useLog ? Math.log10(Math.max(sevMax, 1e-9)) : sevMax;
  const span = (hi - lo) > 0 ? (hi - lo) : 1.0;
  function sx(v) {
    const vv = useLog ? Math.log10(Math.max(v, 1e-9)) : v;
    return M.l + ((vv - lo) / span) * innerW;
  }
  function sy(c) {
    return M.t + (1.0 - Math.max(0, Math.min(1, c))) * innerH;
  }

  // marker size from mean_response
  const meanLo = data.min_mean, meanHi = data.max_mean;
  const meanSpan = (meanHi - meanLo) > 0 ? (meanHi - meanLo) : 1.0;
  function rSize(m) {
    const t = (m - meanLo) / meanSpan;
    return 4.0 + Math.max(0, Math.min(1, t)) * 10.0;
  }

  const root = svg('svg', {
    viewBox: '0 0 ' + W + ' ' + H,
    width: '100%', height: H,
    style: 'background:var(--bg2);border:1px solid var(--line);border-radius:6px;',
  });

  // grid lines (y: 0, 0.25, 0.5, 0.75, 1.0)
  [0, 0.25, 0.5, 0.75, 1.0].forEach(g => {
    const y = sy(g);
    root.appendChild(svg('line', {
      x1: M.l, x2: M.l + innerW, y1: y, y2: y,
      stroke: 'var(--line)', 'stroke-width': 0.6, 'stroke-dasharray': '2,3',
    }));
    root.appendChild(svg('text', {
      x: M.l - 8, y: y + 3, 'text-anchor': 'end',
      fill: 'var(--dim)', 'font-size': 10,
    }, [String(Math.round(g * 100)) + '%']));
  });

  // x-axis ticks
  const nTicks = 5;
  for (let i = 0; i <= nTicks; i++) {
    const t = i / nTicks;
    const v = useLog ? Math.pow(10, lo + t * span) : (lo + t * span);
    const x = M.l + t * innerW;
    root.appendChild(svg('line', {
      x1: x, x2: x, y1: M.t, y2: M.t + innerH,
      stroke: 'var(--line)', 'stroke-width': 0.5, 'stroke-dasharray': '2,3',
    }));
    root.appendChild(svg('text', {
      x: x, y: M.t + innerH + 16, 'text-anchor': 'middle',
      fill: 'var(--dim)', 'font-size': 10,
    }, [fmt(v, v >= 100 ? 0 : 2)]));
  }

  // axis labels
  root.appendChild(svg('text', {
    x: M.l + innerW / 2, y: H - 12, 'text-anchor': 'middle',
    fill: 'var(--fg2)', 'font-size': 11,
  }, ['Severity = max peak_g [' + unitAcc + ']' + (useLog ? '  (log)' : '')]));
  root.appendChild(svg('text', {
    x: 16, y: M.t + innerH / 2, 'text-anchor': 'middle',
    fill: 'var(--fg2)', 'font-size': 11,
    transform: 'rotate(-90 16 ' + (M.t + innerH / 2) + ')',
  }, ['Coverage = 부품 비율 ( > P75 )']));

  // median cross-hair (quadrant split)
  const mx = sx(data.median_severity);
  const my = sy(data.median_coverage);
  root.appendChild(svg('line', {
    x1: mx, x2: mx, y1: M.t, y2: M.t + innerH,
    stroke: 'var(--warn)', 'stroke-width': 1.2, 'stroke-dasharray': '5,4', opacity: 0.7,
  }));
  root.appendChild(svg('line', {
    x1: M.l, x2: M.l + innerW, y1: my, y2: my,
    stroke: 'var(--warn)', 'stroke-width': 1.2, 'stroke-dasharray': '5,4', opacity: 0.7,
  }));

  // quadrant labels
  const ql = data.quadrant_labels || {};
  function qLabel(txt, x, y, anchor) {
    root.appendChild(svg('text', {
      x: x, y: y, 'text-anchor': anchor,
      fill: 'var(--dim)', 'font-size': 10, 'font-style': 'italic', opacity: 0.85,
    }, [txt]));
  }
  qLabel('Q2: ' + (ql.q2 || ''), M.l + 6, M.t + 14, 'start');
  qLabel('Q1: ' + (ql.q1 || ''), M.l + innerW - 6, M.t + 14, 'end');
  qLabel('Q3: ' + (ql.q3 || ''), M.l + 6, M.t + innerH - 6, 'start');
  qLabel('Q4: ' + (ql.q4 || ''), M.l + innerW - 6, M.t + innerH - 6, 'end');

  // tooltip box (single shared)
  const tip = el('div', {
    class: 'pareto-tip',
    style: 'position:absolute;pointer-events:none;background:var(--bg3);' +
           'border:1px solid var(--line);border-radius:4px;padding:6px 8px;' +
           'font-size:11px;color:var(--fg);display:none;z-index:10;line-height:1.5;',
  });
  host.style.position = 'relative';
  host.appendChild(tip);

  const COLORS = (typeof DOE_BEHAVIOR_COLOR !== 'undefined' && DOE_BEHAVIOR_COLOR) ||
                 (typeof BEHAVIOR_COLOR !== 'undefined' ? BEHAVIOR_COLOR : {});
  function bcolor(b) {
    return COLORS[b] || 'var(--accent)';
  }

  // draw points (back→front by severity so the worst points sit on top)
  const ordered = pts.slice().sort((a, b) => a.severity - b.severity);
  ordered.forEach(p => {
    const cx = sx(Math.max(p.severity, 1e-9));
    const cy = sy(p.coverage);
    const r = rSize(p.mean_response);
    const col = bcolor(p.behavior_class);
    const c = svg('circle', {
      cx: cx, cy: cy, r: r,
      fill: col, 'fill-opacity': 0.55,
      stroke: col, 'stroke-width': 1.2,
      style: 'cursor:pointer;',
    });
    c.addEventListener('mousemove', (ev) => {
      const rect = host.getBoundingClientRect();
      tip.style.display = 'block';
      tip.style.left = (ev.clientX - rect.left + 12) + 'px';
      tip.style.top = (ev.clientY - rect.top + 12) + 'px';
      tip.innerHTML =
        '<b>' + p.pos_id + '</b> &nbsp;<span style="color:' + col + '">●</span> ' +
        p.behavior_class +
        '<br>Severity: ' + fmt(p.severity, 1) + ' ' + unitAcc +
        '<br>Coverage: ' + fmt(p.coverage * 100, 1) + ' %  (' + p.n_above + '/' + p.n_parts + ')' +
        '<br>Mean peak_g: ' + fmt(p.mean_response, 1) + ' ' + unitAcc;
    });
    c.addEventListener('mouseleave', () => { tip.style.display = 'none'; });
    root.appendChild(c);
  });

  // legend (behavior classes present + size hint)
  const presentBeh = Array.from(new Set(pts.map(p => p.behavior_class)));
  const legend = el('div', { class: 'pareto-legend',
    style: 'display:flex;flex-wrap:wrap;gap:12px;margin-top:8px;font-size:11px;color:var(--fg2);align-items:center;' });
  presentBeh.forEach(b => {
    legend.appendChild(el('span', {
      style: 'display:inline-flex;align-items:center;gap:4px;',
    }, [
      el('span', { style: 'width:10px;height:10px;border-radius:50%;background:' + bcolor(b) + ';display:inline-block;' }),
      b,
    ]));
  });
  legend.appendChild(el('span', { style: 'opacity:0.7;margin-left:auto;' },
    ['크기 = mean peak_g (' + fmt(meanLo, 1) + ' → ' + fmt(meanHi, 1) + ' ' + unitAcc + ')']));
  legend.appendChild(el('span', { style: 'opacity:0.7;' },
    ['점선 = 중앙값 분할 (P75 임계: ' + fmt(data.p75_global, 1) + ' ' + unitAcc + ')']));

  host.appendChild(root);
  host.appendChild(legend);
}

function _doeRenderEnergyPartition(doe) {
  const root = document.getElementById('doe-ep-list');
  const sumRoot = document.getElementById('doe-ep-summary');
  if (!root || !sumRoot) return;
  while (root.firstChild) root.removeChild(root.firstChild);
  while (sumRoot.firstChild) sumRoot.removeChild(sumRoot.firstChild);

  const adv = (doe.advanced || {}).energy_partition || {};
  const parts = (adv.partitions || []).slice();
  const summary = adv.summary || {};
  const ueng = _u('energy') || 'J';

  if (!parts.length) {
    root.appendChild(el('div', { class: 'doe-ep-empty', style: {
      padding: '24px', color: 'var(--dim)', 'text-align': 'center', 'font-size': '11px'
    } }, [document.createTextNode('에너지 분할 데이터 없음 (impactor trajectories 미존재)')]));
    return;
  }

  // Summary line
  const medPct = ((summary.median_absorption_pct == null ? 0 : (Number(summary.median_absorption_pct) || 0)) * 100).toFixed(1);
  const maxPid = summary.max_absorption_pos_id || '-';
  const maxPct = ((summary.max_absorption_pct == null ? 0 : (Number(summary.max_absorption_pct) || 0)) * 100).toFixed(1);
  const minPid = summary.min_absorption_pos_id || '-';
  const minPct = ((summary.min_absorption_pct == null ? 0 : (Number(summary.min_absorption_pct) || 0)) * 100).toFixed(1);
  const totKE = (summary.ke_total_initial == null ? 0 : (Number(summary.ke_total_initial) || 0));

  const mkChip = (label, val, color) => el('span', { class: 'doe-ep-chip', style: {
    display: 'inline-flex', 'align-items': 'baseline', gap: '6px',
    padding: '5px 10px', 'border-radius': '4px',
    background: 'rgba(255,255,255,0.03)', border: '1px solid var(--line)',
    'font-size': '10px', color: 'var(--dim)', 'letter-spacing': '0.5px'
  } }, [
    document.createTextNode(label),
    el('strong', { style: { color: color || 'var(--fg)', 'font-weight': 700 } },
      [document.createTextNode(val)])
  ]);

  sumRoot.appendChild(mkChip('MEDIAN 흡수율', medPct + '%', 'var(--good)'));
  sumRoot.appendChild(mkChip('최대 흡수', maxPid + ' (' + maxPct + '%)', 'var(--warn)'));
  sumRoot.appendChild(mkChip('최소 흡수', minPid + ' (' + minPct + '%)', 'var(--accent)'));
  sumRoot.appendChild(mkChip('총 초기 KE', fmt(totKE, 2) + ' ' + ueng, 'var(--fg)'));

  // Sort by absorption_pct desc.
  parts.sort((a, b) => (b.absorption_pct == null ? 0 : (Number(b.absorption_pct) || 0)) - (a.absorption_pct == null ? 0 : (Number(a.absorption_pct) || 0)));

  parts.forEach(p => {
    const pct = (p.absorption_pct == null ? 0 : (Number(p.absorption_pct) || 0));
    const pctTxt = (pct * 100).toFixed(1) + '%';
    const beh = p.behavior_class || 'unknown';
    const behColor = (typeof DOE_BEHAVIOR_COLOR !== 'undefined'
      ? (DOE_BEHAVIOR_COLOR[beh] || '#5c6383') : '#5c6383');

    const row = el('div', { class: 'doe-ep-row', 'data-pos': p.pos_id });

    // Pos id + behavior dot
    const lbl = el('div', { class: 'doe-ep-lbl' }, [
      el('span', { class: 'doe-ep-dot', style: { background: behColor } }),
      document.createTextNode(p.pos_id)
    ]);

    // Bar wrapper
    const wAbs = Math.max(0, Math.min(100, pct * 100));
    const wRet = 100 - wAbs;
    const barWrap = el('div', { class: 'doe-ep-bar' }, [
      el('div', { class: 'doe-ep-seg doe-ep-abs', style: { width: wAbs.toFixed(2) + '%' } }, [
        wAbs > 12 ? el('span', { class: 'doe-ep-seg-lbl' },
          [document.createTextNode(pctTxt)]) : null
      ].filter(Boolean)),
      el('div', { class: 'doe-ep-seg doe-ep-ret', style: { width: wRet.toFixed(2) + '%' } }, [
        wRet > 14 ? el('span', { class: 'doe-ep-seg-lbl' },
          [document.createTextNode((100 - pct * 100).toFixed(1) + '%')]) : null
      ].filter(Boolean))
    ]);

    // Right metrics
    const rightVal = el('div', { class: 'doe-ep-right' }, [
      el('span', { class: 'doe-ep-pct' }, [document.createTextNode(pctTxt)]),
      el('span', { class: 'doe-ep-ke' },
        [document.createTextNode('init ' + fmt((p.ke_initial == null ? 0 : (Number(p.ke_initial) || 0)), 2) + ' ' + ueng)])
    ]);

    // Tooltip
    row.title = [
      'POS: ' + p.pos_id,
      'Behavior: ' + beh,
      'KE initial : ' + fmt((p.ke_initial == null ? 0 : (Number(p.ke_initial) || 0)), 3) + ' ' + ueng,
      'KE absorbed: ' + fmt((p.ke_absorbed == null ? 0 : (Number(p.ke_absorbed) || 0)), 3) + ' ' + ueng +
        '  (' + (pct * 100).toFixed(2) + '%)',
      'KE retained: ' + fmt((p.ke_retained == null ? 0 : (Number(p.ke_retained) || 0)), 3) + ' ' + ueng +
        '  (' + ((1 - pct) * 100).toFixed(2) + '%)'
    ].join('\n');

    row.appendChild(lbl);
    row.appendChild(barWrap);
    row.appendChild(rightVal);

    row.addEventListener('click', () => {
      if (typeof DOE_STATE !== 'undefined') {
        DOE_STATE.active_pos = p.pos_id;
        if (typeof _doeRenderHeatmap === 'function') _doeRenderHeatmap(doe);
        if (typeof _doeRenderRanking === 'function') _doeRenderRanking(doe);
      }
    });

    root.appendChild(row);
  });
}

// === ADV_JS_FUNCTIONS_INSERT_HERE ===
// Workflow-added _doeRenderXxx render functions are inserted ABOVE this line.

"""


_JS_S5_MAIN = r"""function _doeUnitForMetric(key) {
  return ({
    peak_g: _u('acc'),
    peak_stress: _u('stress'),
    peak_strain: '',
    peak_disp: _u('disp'),
    peak_vel: _u('vel')
  })[key] || '';
}

function _doeMetricLabel(key) {
  return ({
    peak_g: 'PEAK G',
    peak_stress: 'PEAK σ',
    peak_strain: 'PEAK ε',
    peak_disp: 'PEAK d',
    peak_vel: 'PEAK v'
  })[key] || key;
}

function _doePartName(pid) {
  const p = PART_BY_ID[pid];
  if (!p) return 'part_' + pid;
  // shorten 'Group\\Name' to last token
  const nm = String(p.name || '');
  const tail = nm.split(/[\\/]/).pop();
  return tail || nm || ('part_' + pid);
}

function initDoeAnalysis() {
  const doe = DATA.doe_analysis;
  const nav = document.getElementById('navS5');
  const sec = document.getElementById('s5');
  if (!doe || !doe.positions || !doe.positions.length) {
    if (nav) nav.style.display = 'none';
    if (sec) sec.style.display = 'none';
    return;
  }
  if (sec) sec.style.display = '';
  // default metric: first available
  if (doe.metrics && doe.metrics.length > 0) {
    DOE_STATE.metric = doe.metrics[0].key;
  }

  _doeBuildMetricButtons(doe);
  _doeBuildKpiStrip(doe);
  _doeRenderAll(doe);

  // sort buttons
  document.querySelectorAll('[data-doe-sort]').forEach(b => b.addEventListener('click', function () {
    document.querySelectorAll('[data-doe-sort]').forEach(x => x.classList.remove('active'));
    b.classList.add('active');
    DOE_STATE.sort = b.dataset.doeSort;
    _doeRenderRanking(doe);
  }));
}

function _doeBuildMetricButtons(doe) {
  const host = document.getElementById('doe-metric-buttons');
  if (!host) return;
  host.innerHTML = '';
  (doe.metrics || []).forEach((m, i) => {
    const b = el('button', {
      class: 'btn' + (m.key === DOE_STATE.metric ? ' active' : ''),
      'data-doe-metric': m.key
    }, m.label);
    b.addEventListener('click', () => {
      DOE_STATE.metric = m.key;
      host.querySelectorAll('button').forEach(x => x.classList.toggle('active', x.dataset.doeMetric === m.key));
      _doeRenderAll(doe);
    });
    host.appendChild(b);
  });
}

function _doeBuildKpiStrip(doe) {
  const host = document.getElementById('doe-kpi-strip');
  if (!host) return;
  host.innerHTML = '';
  const n_pos = (doe.positions || []).length;
  // worst peak_g across all positions
  let worst_g = 0;
  let worst_s = 0;
  Object.values(doe.position_metrics || {}).forEach(pm => {
    if ((pm.peak_g_max || 0) > worst_g) worst_g = pm.peak_g_max;
    if ((pm.peak_stress_max || 0) > worst_s) worst_s = pm.peak_stress_max;
  });
  const tka = doe.total_ke_absorbed || [];
  const mean_abs = tka.length ? tka.reduce((a, b) => a + b, 0) / tka.length : 0;
  const bcounts = doe.behavior_class_counts || {};
  const bk = Object.keys(bcounts);
  const total_b = bk.reduce((a, k) => a + bcounts[k], 0) || 1;

  const mkCell = (label, valHtml) => {
    const cell = el('div', { class: 'k' });
    cell.appendChild(el('div', { class: 'v' })).innerHTML = valHtml;
    cell.appendChild(el('div', { class: 'l' }, label));
    return cell;
  };

  host.appendChild(mkCell('TOTAL POSITIONS', String(n_pos) + '<span class="u">pos</span>'));
  {
    const _gDivExec = (DATA.part_motion && (DATA.part_motion.g_divisor || DATA.part_motion.g_mm_s2)) || 9810.0;
    host.appendChild(mkCell('MAX PEAK G', fmt((worst_g || 0) / _gDivExec, 0) + '<span class="u">G</span>'));
  }
  host.appendChild(mkCell('MAX STRESS', fmt(worst_s, 1) + '<span class="u">' + _u('stress') + '</span>'));

  // behavior distribution mini bar
  const bbCell = el('div', { class: 'k' });
  const bbVal = el('div', { class: 'v', style: { fontSize: '12px' } });
  const bar = el('div', { class: 'doe-kpi-bb' });
  bk.forEach(k => {
    const w = Math.round(160 * bcounts[k] / total_b);
    bar.appendChild(el('span', { style: { width: w + 'px', background: DOE_BEHAVIOR_COLOR[k] || '#5c6383' }, title: k + ': ' + bcounts[k] }));
  });
  bbVal.appendChild(bar);
  bbCell.appendChild(bbVal);
  bbCell.appendChild(el('div', { class: 'l' }, 'BEHAVIOR DIST'));
  host.appendChild(bbCell);

  host.appendChild(mkCell('AVG KE 흡수율', (mean_abs * 100).toFixed(1) + '<span class="u">%</span>'));
}

function _doeRenderAll(doe) {
  // update top-level labels
  const lbl = _doeMetricLabel(DOE_STATE.metric);
  const heatLbl = document.getElementById('doe-heat-metric-lbl');
  if (heatLbl) heatLbl.textContent = lbl;
  const valLbl = document.getElementById('doe-rank-val-lbl');
  if (valLbl) {
    const u = _doeUnitForMetric(DOE_STATE.metric);
    valLbl.innerHTML = lbl + (u ? ('<br><span style="font-weight:400;color:var(--dim);text-transform:none">' + u + '</span>') : '');
  }
  const xUnit = document.getElementById('doe-rank-x-unit'); if (xUnit) xUnit.textContent = _uSuffix('disp');
  const yUnit = document.getElementById('doe-rank-y-unit'); if (yUnit) yUnit.textContent = _uSuffix('disp');
  const pUnit = document.getElementById('doe-rank-pen-unit'); if (pUnit) pUnit.textContent = _uSuffix('disp');

  _doeRenderHeatmap(doe);
  _doeRenderRanking(doe);
  _doeRenderPartPosMatrix(doe);
  _doeRenderTrajMM(doe);
  _doeRenderEnvelope(doe);
  _doeRenderFailureRisk(doe);
  _doeRenderCorrNetwork(doe);
  _doeRenderTOA(doe);
  _doeRenderIdwPredictor(doe);
  _doeRenderParetoSeverity(doe);
  _doeRenderEnergyPartition(doe);
  // === ADV_BOOT_CALLS_INSERT_HERE ===
  // Workflow-added _doeRenderXxx(doe) calls are inserted ABOVE this line.
}

function _doeP95(arr) {
  if (!arr || !arr.length) return 0;
  const s = arr.slice().sort((a, b) => a - b);
  const k = Math.max(0, Math.min(1, 0.95)) * (s.length - 1);
  const lo = Math.floor(k), hi = Math.ceil(k);
  if (lo === hi) return s[lo];
  return s[lo] * (1 - (k - lo)) + s[hi] * (k - lo);
}

function _doeMetricValueForPos(doe, pos_id) {
  const pm = (doe.position_metrics || {})[pos_id] || {};
  return pm[DOE_STATE.metric + '_max'] || 0;
}

function _doeMetricValuesAll(doe) {
  return (doe.positions || []).map(p => _doeMetricValueForPos(doe, p.pos_id));
}

function _doeRenderHeatmap(doe) {
  const root = document.getElementById('doe-heatmap-svg');
  if (!root) return;
  while (root.firstChild) root.removeChild(root.firstChild);
  const grid = doe.grid;
  if (!grid) {
    root.appendChild(svg('text', { x: 180, y: 180, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 11 }, [document.createTextNode('No grid metadata')]));
    return;
  }
  const dg = DATA.device_geometry || {aspect: 1};
  const ar = (dg.aspect && isFinite(dg.aspect) && dg.aspect > 0) ? dg.aspect : 1;
  const vbW = 540, vbH = Math.max(120, Math.round(vbW / ar));
  root.setAttribute('viewBox', '0 0 ' + vbW + ' ' + vbH);
  root.setAttribute('preserveAspectRatio', 'xMidYMid meet');
  root.appendChild(svg('rect', { x: 0, y: 0, width: vbW, height: vbH, fill: '#0e1320', rx: 4 }));

  const padL = 60, padR = 14, padT = 24, padB = 36;
  const plotW = vbW - padL - padR, plotH = vbH - padT - padB;
  const nx = grid.nx, ny = grid.ny;
  const cellW = plotW / nx, cellH = plotH / ny;

  const vals = _doeMetricValuesAll(doe).filter(v => v > 0);
  const vmax = _doeP95(vals) || Math.max(...vals, 1);

  (doe.positions || []).forEach(pos => {
    const v = _doeMetricValueForPos(doe, pos.pos_id);
    const t = vmax > 0 ? Math.min(1, v / vmax) : 0;
    const fill = v > 0 ? gColor(t) : '#1a1e2e';
    // row 0 = lowest y → plot bottom; flip y
    const cx = padL + pos.col * cellW;
    const cy = padT + (ny - 1 - pos.row) * cellH;
    const g = svg('g', { class: 'doe-cell' + (DOE_STATE.active_pos === pos.pos_id ? ' active' : ''), 'data-pos': pos.pos_id });
    const rect = svg('rect', {
      x: cx + 1, y: cy + 1, width: cellW - 2, height: cellH - 2,
      fill: fill, stroke: 'rgba(255,255,255,0.05)', rx: 2
    });
    rect.addEventListener('click', () => {
      DOE_STATE.active_pos = pos.pos_id;
      _doeRenderHeatmap(doe);
      _doeRenderRanking(doe);
    });
    const pm = (doe.position_metrics || {})[pos.pos_id] || {};
    const short = ({ peak_g: 'g', peak_stress: 's', peak_strain: 'e', peak_disp: 'd', peak_vel: 'v' })[DOE_STATE.metric] || 'g';
    const wpid = pm['worst_part_id_' + short];
    const wnm = wpid != null ? _doePartName(wpid) : '';
    rect.appendChild(svg('title', null, [document.createTextNode(pos.pos_id + '\nx=' + pos.x.toFixed(1) + ' y=' + pos.y.toFixed(1) + '\nvalue=' + fmt(v, 1) + '\nworst part: ' + wnm)]));
    g.appendChild(rect);
    g.appendChild(svg('text', {
      x: cx + cellW / 2, y: cy + cellH / 2 - 2,
      'text-anchor': 'middle', fill: '#0a0c14', 'font-size': 10, 'font-weight': 700,
      class: 'doe-cell-label'
    }, [document.createTextNode(fmt(v, 1))]));
    if (wnm) {
      g.appendChild(svg('text', {
        x: cx + cellW / 2, y: cy + cellH / 2 + 11,
        'text-anchor': 'middle', fill: '#0a0c14', 'font-size': 8,
        class: 'doe-cell-label'
      }, [document.createTextNode(wnm.slice(0, 12))]));
    }
    root.appendChild(g);
  });

  // axis labels
  const bb = grid.bbox; // [xmin, ymin, xmax, ymax]
  root.appendChild(svg('text', { x: padL, y: padT - 8, fill: '#5c6383', 'font-size': 9 }, [document.createTextNode('X: ' + bb[0].toFixed(1) + ' → ' + bb[2].toFixed(1))]));
  root.appendChild(svg('text', { x: padL, y: vbH - padB + 22, fill: '#5c6383', 'font-size': 9 }, [document.createTextNode('Y: ' + bb[1].toFixed(1) + ' → ' + bb[3].toFixed(1))]));
  root.appendChild(svg('text', { x: vbW / 2, y: vbH - 8, fill: '#aab2cf', 'font-size': 10, 'text-anchor': 'middle' }, [document.createTextNode('Grid ' + nx + '×' + ny + '   metric: ' + _doeMetricLabel(DOE_STATE.metric))]));
  svgZoomPan(root);
}

function _doeRenderRanking(doe) {
  const tb = document.querySelector('#doe-rank-tbl tbody');
  if (!tb) return;
  tb.innerHTML = '';
  const rows = (doe.positions || []).slice();
  if (DOE_STATE.sort === 'pos') {
    rows.sort((a, b) => String(a.pos_id).localeCompare(String(b.pos_id)));
  } else {
    rows.sort((a, b) => _doeMetricValueForPos(doe, b.pos_id) - _doeMetricValueForPos(doe, a.pos_id));
  }
  const short = ({ peak_g: 'g', peak_stress: 's', peak_strain: 'e', peak_disp: 'd', peak_vel: 'v' })[DOE_STATE.metric] || 'g';
  rows.forEach((p, i) => {
    const pm = (doe.position_metrics || {})[p.pos_id] || {};
    const v = _doeMetricValueForPos(doe, p.pos_id);
    const wpid = pm['worst_part_id_' + short];
    const wnm = wpid != null ? _doePartName(wpid) : '-';
    const tsum = (doe.trajectory_summary || {})[p.pos_id] || {};
    const beh = tsum.behavior_class || 'unknown';
    const ke_ret = tsum.ke_retention;
    const pen = tsum.max_penetration_depth;
    const tr = el('tr', {});
    if (DOE_STATE.active_pos === p.pos_id) tr.style.background = 'rgba(77,214,255,0.08)';
    tr.appendChild(el('td', { class: 'tl b' }, String(i + 1)));
    tr.appendChild(el('td', { class: 'tl' }, p.pos_id));
    tr.appendChild(el('td', { class: 'num' }, p.x.toFixed(1)));
    tr.appendChild(el('td', { class: 'num' }, p.y.toFixed(1)));
    const bcell = el('td', { class: 'tl' });
    bcell.appendChild(el('span', { class: 'bbadge ' + beh }, beh));
    tr.appendChild(bcell);
    tr.appendChild(el('td', { class: 'num' }, fmt(v, 1)));
    tr.appendChild(el('td', { class: 'tl dim' }, wnm));
    tr.appendChild(el('td', { class: 'num' }, ke_ret != null ? (ke_ret * 100).toFixed(1) + '%' : '-'));
    tr.appendChild(el('td', { class: 'num' }, pen != null ? fmt(pen, 2) : '-'));
    tr.addEventListener('click', () => {
      DOE_STATE.active_pos = p.pos_id;
      _doeRenderHeatmap(doe);
      _doeRenderRanking(doe);
    });
    tr.style.cursor = 'pointer';
    tb.appendChild(tr);
  });
}

function _doeRenderPartPosMatrix(doe) {
  const root = document.getElementById('doe-pp-svg');
  if (!root) return;
  while (root.firstChild) root.removeChild(root.firstChild);

  const mat = doe.peak_g_matrix || {};
  const positions = (doe.positions || []).slice().sort((a, b) => a.doe_index - b.doe_index);
  // top 15 parts by max(peak_g)
  const partRows = Object.keys(mat).map(pid => {
    const row = mat[pid];
    let mx = 0;
    Object.keys(row).forEach(k => { if (row[k] > mx) mx = row[k]; });
    return { pid: parseInt(pid, 10), max: mx };
  });
  partRows.sort((a, b) => b.max - a.max);
  const topParts = partRows.slice(0, 15);
  if (!topParts.length || !positions.length) {
    root.setAttribute('viewBox', '0 0 600 80');
    root.appendChild(svg('text', { x: 300, y: 40, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 11 }, [document.createTextNode('No part×position data')]));
    return;
  }

  const padL = 160, padR = 8, padT = 28, padB = 8;
  const cellW = 26, cellH = 22;
  const W = padL + padR + positions.length * cellW;
  const H = padT + padB + topParts.length * cellH;
  root.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
  root.setAttribute('preserveAspectRatio', 'xMinYMid meet');
  root.setAttribute('width', W);
  root.setAttribute('height', H);

  let gmax = 0;
  topParts.forEach(p => {
    const row = mat[p.pid] || {};
    Object.keys(row).forEach(k => { if (row[k] > gmax) gmax = row[k]; });
  });
  const norm = _doeP95(topParts.flatMap(p => Object.values(mat[p.pid] || {}))) || gmax || 1;

  // column headers (pos_id)
  positions.forEach((p, ci) => {
    const cx = padL + ci * cellW + cellW / 2;
    root.appendChild(svg('text', { x: cx, y: padT - 8, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 8, transform: 'rotate(-60 ' + cx + ' ' + (padT - 8) + ')' }, [document.createTextNode(p.pos_id)]));
  });

  topParts.forEach((p, ri) => {
    const cy = padT + ri * cellH;
    root.appendChild(svg('text', { x: padL - 8, y: cy + cellH / 2 + 3, 'text-anchor': 'end', fill: '#aab2cf', 'font-size': 10 }, [document.createTextNode(_doePartName(p.pid))]));
    const row = mat[p.pid] || {};
    positions.forEach((pos, ci) => {
      const v = row[pos.pos_id] || 0;
      const t = norm > 0 ? Math.min(1, v / norm) : 0;
      const fill = v > 0 ? gColor(t) : '#1a1e2e';
      const cx = padL + ci * cellW;
      const r = svg('rect', { x: cx + 1, y: cy + 1, width: cellW - 2, height: cellH - 2, fill: fill, rx: 2 });
      r.appendChild(svg('title', null, [document.createTextNode(_doePartName(p.pid) + ' @ ' + pos.pos_id + ' = ' + fmt(v, 1) + ' ' + _u('acc'))]));
      root.appendChild(r);
    });
  });
}

function _doeRenderTrajMM(doe) {
  const host = document.getElementById('doe-traj-mm');
  if (!host) return;
  host.innerHTML = '';
  const grid = doe.grid;
  const nx = grid ? grid.nx : Math.ceil(Math.sqrt((doe.positions || []).length));
  const ny = grid ? grid.ny : nx;
  host.style.gridTemplateColumns = 'repeat(' + nx + ', 1fr)';
  const curves = doe.trajectory_ke_curves || {};
  const tsums = doe.trajectory_summary || {};
  const worst_pid = doe.worst_position ? doe.worst_position.pos_id : null;

  // Arrange cells by (row, col) – row 0 at bottom visually so iterate top-to-bottom rows = (ny-1)..0.
  // For irregular grids (partial DOE, custom layouts), multiple positions
  // could quantize to the same (row,col) — surface the collision in the
  // console rather than silently overwriting.
  const byCell = {};
  (doe.positions || []).forEach(p => {
    const k = (ny - 1 - p.row) + '_' + p.col;
    if (byCell[k]) {
      console.warn('DOE traj grid collision at cell', k, 'positions:', byCell[k].pos_id, '<->', p.pos_id);
    }
    byCell[k] = p;
  });

  for (let r = 0; r < ny; r++) {
    for (let c = 0; c < nx; c++) {
      const cellWrap = el('div', { class: 'doe-traj-cell' });
      const p = byCell[r + '_' + c];
      if (!p) { cellWrap.style.background = 'transparent'; cellWrap.style.borderColor = 'transparent'; host.appendChild(cellWrap); continue; }
      const tsum = tsums[p.pos_id] || {};
      const beh = tsum.behavior_class || 'unknown';
      const color = DOE_BEHAVIOR_COLOR[beh] || '#5c6383';
      const curve = curves[p.pos_id];
      const isWorst = p.pos_id === worst_pid;
      if (isWorst) {
        cellWrap.classList.add('worst');
        cellWrap.appendChild(el('div', { class: 'star' }, '★'));
      }
      // mini svg — per-cell aspect ratio follows device (each cell is one DOE slot)
      const _dgT = DATA.device_geometry || {aspect: 1};
      const _arT = (_dgT.aspect && isFinite(_dgT.aspect) && _dgT.aspect > 0) ? _dgT.aspect : (90/56);
      const W = 90;
      // Cell aspect should mirror per-position physical extent: a cell spans
      // (device_width / nx) × (device_height / ny). With equal nx == ny the
      // ratio reduces to the device aspect itself.
      const H = Math.max(28, Math.min(160, Math.round(W / _arT)));
      const s = svg('svg', { viewBox: '0 0 ' + W + ' ' + H, preserveAspectRatio: 'none' });
      // Native hover tooltip on the whole cell — peak KE, behavior, retention.
      const _tk = (curve && curve.ke && curve.ke.length) ? Math.max.apply(null, curve.ke) : 0;
      const _retPct = (tsum.ke_retention != null) ? (tsum.ke_retention * 100).toFixed(0) + '%' : '?';
      const _pen = (tsum.max_penetration_depth != null) ? tsum.max_penetration_depth : '?';
      const _tt = svg('title', null);
      _tt.appendChild(document.createTextNode(
        p.pos_id + ' (' + p.x + ', ' + p.y + ')' +
        '\\n behavior: ' + beh +
        '\\n peak KE: ' + (_tk ? _tk.toExponential(2) : '–') +
        '\\n KE retention: ' + _retPct +
        '\\n max penetration: ' + _pen
      ));
      s.appendChild(_tt);
      s.appendChild(svg('rect', { x: 0, y: 0, width: W, height: H, fill: '#0e1320', rx: 2 }));
      if (curve && curve.t && curve.t.length > 1) {
        const t0 = curve.t[0], t1 = curve.t[curve.t.length - 1];
        let kmax = 0, kmin = Infinity;
        for (const k of curve.ke) { if (k > kmax) kmax = k; if (k < kmin) kmin = k; }
        if (!isFinite(kmin)) kmin = 0;
        const dT = (t1 - t0) || 1;
        const dK = (kmax - kmin) || 1;
        let d = '';
        for (let i = 0; i < curve.t.length; i++) {
          const x = ((curve.t[i] - t0) / dT) * W;
          const y = H - ((curve.ke[i] - kmin) / dK) * H;
          d += (i ? 'L' : 'M') + x.toFixed(1) + ' ' + y.toFixed(1);
        }
        s.appendChild(svg('path', { d: d, fill: 'none', stroke: color, 'stroke-width': 1.3 }));
      } else {
        s.appendChild(svg('text', { x: W / 2, y: H / 2 + 3, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 8 }, [document.createTextNode('no traj')]));
      }
      cellWrap.appendChild(s);
      const lbl = el('div', { class: 'tc-lbl' });
      lbl.appendChild(el('span', null, p.pos_id));
      lbl.appendChild(el('span', { style: { color: color } }, beh));
      cellWrap.appendChild(lbl);
      host.appendChild(cellWrap);
    }
  }
}

function _doeRenderEnvelope(doe) {
  const host = document.getElementById('doe-env-wrap');
  if (!host) return;
  host.innerHTML = '';
  const stats = doe.per_part_stats || {};
  const arr = Object.keys(stats).map(pid => {
    const s = stats[pid];
    return {
      pid: parseInt(pid, 10), name: s.part_name,
      p5: s.p5, p50: s.p50, p95: s.p95, mean: s.mean, max: s.max
    };
  });
  arr.sort((a, b) => b.p95 - a.p95);
  const top = arr.slice(0, 12);
  if (!top.length) {
    host.appendChild(el('div', { class: 'doe-empty' }, 'No per-part stats'));
    return;
  }
  const xmax = Math.max.apply(null, top.map(t => t.p95)) || 1;

  top.forEach(t => {
    const row = el('div', { class: 'doe-env-row' });
    row.appendChild(el('div', { class: 'nm' }, _doePartName(t.pid)));
    const wis = el('div', { class: 'wis' });
    const W = 240, H = 14;
    const s = svg('svg', { viewBox: '0 0 ' + W + ' ' + H, preserveAspectRatio: 'none' });
    s.appendChild(svg('rect', { x: 0, y: 0, width: W, height: H, fill: '#1a1e2e', rx: 2 }));
    const x5 = (t.p5 / xmax) * W;
    const x50 = (t.p50 / xmax) * W;
    const x95 = (t.p95 / xmax) * W;
    const xMean = (t.mean / xmax) * W;
    // whisker line
    s.appendChild(svg('line', { x1: x5, y1: H / 2, x2: x95, y2: H / 2, stroke: '#4dd6ff', 'stroke-width': 2 }));
    // p5 tick
    s.appendChild(svg('line', { x1: x5, y1: 2, x2: x5, y2: H - 2, stroke: '#aab2cf', 'stroke-width': 1 }));
    // p95 tick
    s.appendChild(svg('line', { x1: x95, y1: 2, x2: x95, y2: H - 2, stroke: '#aab2cf', 'stroke-width': 1 }));
    // p50 marker
    s.appendChild(svg('circle', { cx: x50, cy: H / 2, r: 3, fill: '#b46eff' }));
    // mean marker
    s.appendChild(svg('circle', { cx: xMean, cy: H / 2, r: 2, fill: '#ff5e84' }));
    s.appendChild(svg('title', null, [document.createTextNode('P5=' + fmt(t.p5, 1) + '  P50=' + fmt(t.p50, 1) + '  P95=' + fmt(t.p95, 1) + '  mean=' + fmt(t.mean, 1))]));
    wis.appendChild(s);
    row.appendChild(wis);
    const ratio = (t.p5 > 0) ? (t.p95 / t.p5) : (t.p95 > 0 ? Infinity : 0);
    row.appendChild(el('div', { class: 'rt' }, isFinite(ratio) ? ratio.toFixed(1) + '×' : '∞'));
    host.appendChild(row);
  });
}

// === Lazy section init framework ===
// Heavy panels (Section 3-7) defer their init until their containing
// <section id="sX"> enters the viewport OR the user clicks the nav.
// This drastically reduces time-to-first-paint on the OVERVIEW landing.
const LAZY_INIT = {};
"""
