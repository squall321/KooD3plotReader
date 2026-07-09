# 섹션 08 — PHYSICS HTML 템플릿 (기계적 분할, 바이트 불변)

_PAGE8 = """
<section id="s8">
  <div class="page-head">
    <span class="num">08</span>
    <span class="t">PHYSICS INSIGHTS</span>
    <span class="sub">충격파 속도 · 반발 계수 · 댐핑 · 최악 조합</span>
    <span class="sub">WAVE / RESTITUTION / DAMPING / WORST COMBOS</span>
  </div>

  <div class="panel" style="background:transparent;border:none;padding:0;">
    <div class="panel" id="physics-stress-wave-velocity">
  <div class="panel-header">
    <h3>충격파 전파 속도</h3>
    <span class="panel-sub">part별 평균 v_app = r / Δt &nbsp;·&nbsp; 이론값과 비교</span>
  </div>
  <div class="panel-body"></div>
</div>
<div class="panel" id="phys-restitution-map" data-panel-key="RestitutionMap">
  <div class="panel-header">
    <h3>위치별 반발 계수 (Coefficient of Restitution)</h3>
    <div class="panel-sub" data-role="status">반발 계수 e 데이터를 로딩 중입니다...</div>
  </div>
  <div class="rmap-kpi-row">
    <div class="rmap-kpi"><div class="rmap-kpi-label">평균 e</div><div class="rmap-kpi-value" data-role="kpi-mean">—</div></div>
    <div class="rmap-kpi"><div class="rmap-kpi-label">최대 (탄성)</div><div class="rmap-kpi-value" data-role="kpi-max">—</div></div>
    <div class="rmap-kpi"><div class="rmap-kpi-label">최소 (비탄성)</div><div class="rmap-kpi-value" data-role="kpi-min">—</div></div>
    <div class="rmap-kpi rmap-kpi-wide"><div class="rmap-kpi-label">분포</div><div class="rmap-kpi-value" data-role="kpi-buckets">—</div></div>
  </div>
  <div class="rmap-grid">
    <div class="rmap-heat">
      <div class="rmap-section-title">5×5 공간 히트맵 (빨강=비탄성, 초록=탄성)</div>
      <div data-role="heatmap" class="rmap-heat-host"></div>
    </div>
    <div class="rmap-hist">
      <div class="rmap-section-title">e 분포 (10 bins)</div>
      <div data-role="histogram" class="rmap-hist-host"></div>
    </div>
  </div>
  <div class="rmap-caption">
    e = √(KE_after / KE_before). 0 = 완전비탄성 (충돌체 정지), 1 = 완전탄성. 1 초과 시 mass scaling 효과.
  </div>
</div>
<div class="panel" id="phys-recovery-damping-panel">
  <div class="panel-header">
    <h3>부품별 댐핑 / 회복 시간</h3>
    <div class="panel-sub">최악 위치 기준 · 5% 감쇠 시간 · log-decrement ζ 추정</div>
  </div>
  <div class="panel-body" id="phys-recovery-damping-body"></div>
</div>
<section id="phys-worst-combinations" class="panel" data-panel-key="worst_combinations">
  <header class="panel-header">
    <h3 class="panel-title">최악 25 조합 (위치 × 부품)</h3>
    <div class="panel-subtitle">composite risk score 기반 Top-K — peak_g · peak_stress · peak_disp 가중 결합</div>
  </header>
  <div class="panel-body"></div>
</section>

<!-- PHYSICS_PANELS_INSERT_HERE -->
    <!-- Workflow-added panel templates are inserted ABOVE this marker. -->
  </div>
</section>
"""


_JS_S8 = r"""function _physRenderStressWaveVelocity(data){
  const host = document.getElementById('physics-stress-wave-velocity');
  if(!host) return;
  const d = (data && data.physics && data.physics.StressWaveVelocity) || null;
  const body = host.querySelector('.panel-body') || host;
  body.innerHTML = '';

  const placeholder = (d && d._placeholder) || '응력파 전파 속도 산출에 필요한 t_first_contact / t_peak_g / 위치-부품 거리 정보가 부족하여 현재 패널을 표시할 수 없습니다. (50자 이상 placeholder)';
  if(!d || !d.per_part || d.per_part.length === 0){
    const empty = document.createElement('div');
    empty.className = 'phys-empty';
    empty.textContent = placeholder;
    body.appendChild(empty);
    return;
  }

  // Top-12 cap (payload caps at 15; we display 12).
  const rows = d.per_part.slice(0, 12);
  const v_theory = (typeof d.v_theory_impactor === 'number' && isFinite(d.v_theory_impactor)) ? d.v_theory_impactor : null;

  // Caption
  const cap = document.createElement('div');
  cap.className = 'phys-caption';
  cap.textContent = '거리/Δt 로 산출한 외형 wave 속도. 이론값 위면 다중 모드 동시 도착, 아래면 부품간 결합 약함.';
  body.appendChild(cap);

  // Summary chips
  if(d.summary && typeof d.summary === 'object'){
    const s = d.summary;
    const chips = document.createElement('div');
    chips.className = 'phys-chips';
    const mk = (label, value, unit) => {
      const c = document.createElement('span');
      c.className = 'phys-chip';
      const v = (value == null) ? '—' : (typeof _u === 'function' ? _u(value, unit) : (value + ' ' + unit));
      c.innerHTML = '<b>' + label + '</b> ' + v;
      return c;
    };
    chips.appendChild(mk('min', s.min_v_app, 'm/s'));
    chips.appendChild(mk('median', s.median_v_app_all, 'm/s'));
    chips.appendChild(mk('max', s.max_v_app, 'm/s'));
    chips.appendChild(mk('표본수', s.n_total, '개'));
    if(v_theory != null) chips.appendChild(mk('이론 √(E/ρ)', v_theory, 'm/s'));
    body.appendChild(chips);
  }

  // Chart layout
  const W = 720, rowH = 26, padTop = 24, padBot = 36, padL = 170, padR = 70;
  const H = padTop + padBot + rowH * rows.length;
  const chartW = W - padL - padR;

  // Domain: max of bar max (q75) and v_theory, with small headroom
  let xMax = 0;
  for(const r of rows){
    const hi = (typeof r.q75_v_app === 'number') ? r.q75_v_app : (r.mean_v_app || 0);
    if(hi > xMax) xMax = hi;
  }
  if(v_theory != null && v_theory > xMax) xMax = v_theory;
  if(!(xMax > 0)) xMax = 1.0;
  xMax *= 1.10;

  const xScale = v => padL + (v / xMax) * chartW;

  const NS = 'http://www.w3.org/2000/svg';
  const root = document.createElementNS(NS, 'svg');
  root.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
  root.setAttribute('width', '100%');
  root.setAttribute('class', 'phys-swv-chart');

  // X axis ticks (4)
  for(let k=0; k<=4; k++){
    const v = (xMax / 4) * k;
    const x = xScale(v);
    const tline = document.createElementNS(NS, 'line');
    tline.setAttribute('x1', x); tline.setAttribute('x2', x);
    tline.setAttribute('y1', padTop - 4); tline.setAttribute('y2', H - padBot);
    tline.setAttribute('stroke', '#444'); tline.setAttribute('stroke-width', '0.5');
    tline.setAttribute('stroke-dasharray', '2,3');
    root.appendChild(tline);
    const tl = document.createElementNS(NS, 'text');
    tl.setAttribute('x', x); tl.setAttribute('y', H - padBot + 14);
    tl.setAttribute('text-anchor', 'middle');
    tl.setAttribute('class', 'phys-axis-tick');
    tl.textContent = (typeof fmt === 'function' ? fmt(v, 0) : v.toFixed(0));
    root.appendChild(tl);
  }
  // X axis label
  const xl = document.createElementNS(NS, 'text');
  xl.setAttribute('x', padL + chartW/2); xl.setAttribute('y', H - 6);
  xl.setAttribute('text-anchor', 'middle');
  xl.setAttribute('class', 'phys-axis-label');
  xl.textContent = '외형 wave 속도 v_app (m/s)';
  root.appendChild(xl);

  // Bars + whiskers
  rows.forEach((r, i) => {
    const y = padTop + i * rowH + rowH * 0.5;
    const mean = (typeof r.mean_v_app === 'number') ? r.mean_v_app : 0;
    const lo = (typeof r.q25_v_app === 'number') ? r.q25_v_app : mean;
    const hi = (typeof r.q75_v_app === 'number') ? r.q75_v_app : mean;
    const xMean = xScale(mean);
    const xLo = xScale(lo);
    const xHi = xScale(hi);
    const barH = rowH * 0.55;

    // Part label
    const lab = document.createElementNS(NS, 'text');
    lab.setAttribute('x', padL - 8); lab.setAttribute('y', y + 4);
    lab.setAttribute('text-anchor', 'end');
    lab.setAttribute('class', 'phys-row-label');
    const lbl = r.part_name || ('PART_' + r.part_id);
    lab.textContent = lbl.length > 22 ? (lbl.slice(0, 20) + '…') : lbl;
    const labTitle = document.createElementNS(NS, 'title');
    labTitle.textContent = (r.part_name || '') + ' (part_id ' + r.part_id + ') — n=' + (r.n_samples||0);
    lab.appendChild(labTitle);
    root.appendChild(lab);

    // Bar (mean)
    const bar = document.createElementNS(NS, 'rect');
    bar.setAttribute('x', padL);
    bar.setAttribute('y', y - barH/2);
    bar.setAttribute('width', Math.max(0, xMean - padL));
    bar.setAttribute('height', barH);
    const color = (typeof gColor === 'function') ? gColor(mean / (v_theory || xMax)) : '#4ea3ff';
    bar.setAttribute('fill', color);
    bar.setAttribute('opacity', '0.85');
    const bt = document.createElementNS(NS, 'title');
    const m_ms = (typeof r.mean_delta_t_ms === 'number') ? r.mean_delta_t_ms : null;
    bt.textContent = (r.part_name || ('PART_' + r.part_id)) +
                     '\nmean v_app: ' + (typeof fmt === 'function' ? fmt(mean,0) : mean.toFixed(0)) + ' m/s' +
                     '\nIQR: [' + (typeof fmt === 'function' ? fmt(lo,0) : lo.toFixed(0)) + ', ' +
                     (typeof fmt === 'function' ? fmt(hi,0) : hi.toFixed(0)) + '] m/s' +
                     '\nmedian: ' + (r.median_v_app != null ? r.median_v_app : '—') + ' m/s' +
                     (m_ms != null ? '\nmean Δt: ' + m_ms + ' ms' : '') +
                     '\nn=' + (r.n_samples || 0);
    bar.appendChild(bt);
    root.appendChild(bar);

    // IQR whisker (Q25..Q75)
    const wline = document.createElementNS(NS, 'line');
    wline.setAttribute('x1', xLo); wline.setAttribute('x2', xHi);
    wline.setAttribute('y1', y); wline.setAttribute('y2', y);
    wline.setAttribute('stroke', '#ddd'); wline.setAttribute('stroke-width', '1.5');
    root.appendChild(wline);
    // whisker caps
    [[xLo, '#ddd'], [xHi, '#ddd']].forEach(([xv, col]) => {
      const c = document.createElementNS(NS, 'line');
      c.setAttribute('x1', xv); c.setAttribute('x2', xv);
      c.setAttribute('y1', y - 5); c.setAttribute('y2', y + 5);
      c.setAttribute('stroke', col); c.setAttribute('stroke-width', '1.5');
      root.appendChild(c);
    });

    // Value label at bar end
    const vlab = document.createElementNS(NS, 'text');
    vlab.setAttribute('x', xMean + 4); vlab.setAttribute('y', y + 4);
    vlab.setAttribute('class', 'phys-row-value');
    vlab.textContent = (typeof fmt === 'function' ? fmt(mean,0) : mean.toFixed(0));
    root.appendChild(vlab);
  });

  // Theory vertical line
  if(v_theory != null){
    const xt = xScale(v_theory);
    const ln = document.createElementNS(NS, 'line');
    ln.setAttribute('x1', xt); ln.setAttribute('x2', xt);
    ln.setAttribute('y1', padTop - 6); ln.setAttribute('y2', H - padBot);
    ln.setAttribute('stroke', '#ff6b6b');
    ln.setAttribute('stroke-width', '1.6');
    ln.setAttribute('stroke-dasharray', '6,4');
    root.appendChild(ln);
    const lt = document.createElementNS(NS, 'text');
    lt.setAttribute('x', xt + 4); lt.setAttribute('y', padTop + 6);
    lt.setAttribute('class', 'phys-theory-label');
    lt.textContent = '이론값 √(E/ρ) = ' + (typeof fmt === 'function' ? fmt(v_theory,0) : v_theory.toFixed(0)) + ' m/s';
    root.appendChild(lt);
  }

  body.appendChild(root);

  if(typeof svgZoomPan === 'function'){
    try { svgZoomPan(root); } catch(e){}
  }
}

function _physRenderRestitutionMap(data) {
  const root = document.getElementById('phys-restitution-map');
  if (!root) return;
  const payload = (data && data.physics && data.physics.RestitutionMap) || null;

  const kpiMean = root.querySelector('[data-role="kpi-mean"]');
  const kpiMax = root.querySelector('[data-role="kpi-max"]');
  const kpiMin = root.querySelector('[data-role="kpi-min"]');
  const kpiBuckets = root.querySelector('[data-role="kpi-buckets"]');
  const heatHost = root.querySelector('[data-role="heatmap"]');
  const histHost = root.querySelector('[data-role="histogram"]');
  const statusHost = root.querySelector('[data-role="status"]');

  const PLACEHOLDER = '데이터가 비어있거나 유효한 반발 계수 e 값을 계산할 수 없습니다 (KE_before/KE_after 누락).';

  if (!payload || !payload.per_position || payload.per_position.length === 0) {
    if (statusHost) statusHost.textContent = PLACEHOLDER;
    if (heatHost) heatHost.innerHTML = '';
    if (histHost) histHost.innerHTML = '';
    return;
  }

  const rows = payload.per_position;
  const summary = payload.summary || {};
  const hist = payload.histogram || [];
  const histRange = payload.hist_range || [0, 1.2];
  const grid = payload.grid || {nx: 5, ny: 5};
  const nx = Math.max(1, grid.nx || 5);
  const ny = Math.max(1, grid.ny || 5);

  // ── KPI ──────────────────────────────────────────────────────────────
  const fmtE = v => (v == null || !isFinite(v)) ? '—' : Number(v).toFixed(3);
  if (kpiMean) kpiMean.textContent = fmtE(summary.mean_e);
  if (kpiMax) {
    kpiMax.textContent = (summary.max_e_pos_id != null)
      ? `P${summary.max_e_pos_id} (e=${fmtE(summary.max_e)})`
      : '—';
  }
  if (kpiMin) {
    kpiMin.textContent = (summary.min_e_pos_id != null)
      ? `P${summary.min_e_pos_id} (e=${fmtE(summary.min_e)})`
      : '—';
  }
  if (kpiBuckets) {
    const nHigh = summary.n_e_high || 0;
    const nLow = summary.n_e_low || 0;
    const nValid = summary.n_valid || 0;
    kpiBuckets.textContent = `탄성≥0.9: ${nHigh} · 비탄성≤0.3: ${nLow} · 유효 ${nValid}/${summary.n_total || rows.length}`;
  }

  // ── Heatmap (5×5) ────────────────────────────────────────────────────
  // Honour device aspect ratio if available
  const geom = payload.device_geometry || {};
  let aspect = 1.0;
  if (geom && isFinite(geom.width) && isFinite(geom.height) && geom.height > 0) {
    aspect = Math.max(0.4, Math.min(2.5, geom.width / geom.height));
  }
  const heatW = 360;
  const heatH = Math.round(heatW / aspect);
  const pad = {l: 36, r: 16, t: 16, b: 36};
  const innerW = heatW - pad.l - pad.r;
  const innerH = heatH - pad.t - pad.b;
  const cellW = innerW / nx;
  const cellH = innerH / ny;

  // Map pos_id → grid (i, j). pos_id is 1..25 with row-major layout.
  // Falls back to the row index when pos_id is non-numeric (e.g. "F5_DOE_001").
  function posToCell(pos_id, idx) {
    let k = idx;
    if (pos_id != null) {
      const n = Number(pos_id);
      if (isFinite(n)) k = n - 1;
    }
    if (!isFinite(k) || k < 0 || k >= nx * ny) return null;
    return {i: k % nx, j: Math.floor(k / nx)};
  }

  // Color ramp: red (low e) → yellow → green (high e)
  function eColor(e) {
    if (e == null || !isFinite(e)) return '#2a2f3a';
    const t = Math.max(0, Math.min(1, e / 1.0)); // clamp display ramp at e=1
    // Interpolate red → yellow → green in HSL
    const hue = 0 + 120 * t; // 0=red, 60=yellow, 120=green
    return `hsl(${hue.toFixed(1)}, 70%, 45%)`;
  }

  const behaviorChip = (b) => {
    if (!b) return '';
    const col = (typeof BEHAVIOR_COLOR === 'object' && BEHAVIOR_COLOR[b]) || '#888';
    return `<span class="rmap-chip" style="background:${col};">${b}</span>`;
  };

  let svgStr = `<svg viewBox="0 0 ${heatW} ${heatH}" width="100%" height="${heatH}" preserveAspectRatio="xMidYMid meet" class="rmap-heat-svg">`;
  // axes labels
  svgStr += `<text x="${heatW/2}" y="${heatH - 8}" text-anchor="middle" fill="#a8b0bd" font-size="11">X (격자)</text>`;
  svgStr += `<text x="12" y="${pad.t + innerH/2}" text-anchor="middle" fill="#a8b0bd" font-size="11" transform="rotate(-90 12 ${pad.t + innerH/2})">Y (격자)</text>`;

  rows.forEach((row, idx) => {
    const cell = posToCell(row.pos_id, idx);
    if (!cell) return;
    const x = pad.l + cell.i * cellW;
    const y = pad.t + cell.j * cellH;
    const eVal = row.e;
    const fill = eColor(eVal);
    svgStr += `<rect x="${x}" y="${y}" width="${cellW - 1.5}" height="${cellH - 1.5}" rx="3" ry="3" fill="${fill}" stroke="#0e1117" stroke-width="0.8">`;
    svgStr += `<title>P${row.pos_id} · e=${fmtE(eVal)} · KE_before=${row.ke_before ?? '—'} · KE_after=${row.ke_after ?? '—'} · ${row.behavior_class || ''}</title>`;
    svgStr += `</rect>`;
    // Value label
    const label = (eVal == null) ? '—' : Number(eVal).toFixed(2);
    svgStr += `<text x="${x + cellW/2}" y="${y + cellH/2 - 2}" text-anchor="middle" dominant-baseline="middle" fill="#0e1117" font-size="${Math.min(13, cellW*0.28).toFixed(1)}" font-weight="600">${label}</text>`;
    // Behavior chip text below value (small)
    if (row.behavior_class) {
      svgStr += `<text x="${x + cellW/2}" y="${y + cellH/2 + 12}" text-anchor="middle" fill="#0e1117" font-size="${Math.min(9, cellW*0.18).toFixed(1)}" opacity="0.75">${row.behavior_class}</text>`;
    }
    svgStr += `<text x="${x + 4}" y="${y + 10}" fill="#0e1117" font-size="8" opacity="0.7">P${row.pos_id}</text>`;
  });

  svgStr += `</svg>`;
  if (heatHost) heatHost.innerHTML = svgStr;

  // ── Histogram ────────────────────────────────────────────────────────
  if (histHost) {
    const hW = 320, hH = heatH;
    const hp = {l: 36, r: 12, t: 16, b: 36};
    const iW = hW - hp.l - hp.r;
    const iH = hH - hp.t - hp.b;
    const maxCount = hist.reduce((m, b) => Math.max(m, b.count || 0), 0) || 1;
    const barW = iW / Math.max(1, hist.length);
    let h = `<svg viewBox="0 0 ${hW} ${hH}" width="100%" height="${hH}" preserveAspectRatio="xMidYMid meet" class="rmap-hist-svg">`;
    // axes
    h += `<line x1="${hp.l}" y1="${hp.t + iH}" x2="${hp.l + iW}" y2="${hp.t + iH}" stroke="#3a4150" stroke-width="1"/>`;
    h += `<line x1="${hp.l}" y1="${hp.t}" x2="${hp.l}" y2="${hp.t + iH}" stroke="#3a4150" stroke-width="1"/>`;
    // bars
    hist.forEach((b, i) => {
      const x = hp.l + i * barW;
      const hRatio = (b.count || 0) / maxCount;
      const barH = iH * hRatio;
      const y = hp.t + iH - barH;
      const mid = ((b.lo || 0) + (b.hi || 0)) / 2;
      const fill = eColor(mid);
      h += `<rect x="${x + 1}" y="${y}" width="${barW - 2}" height="${barH}" fill="${fill}" opacity="0.85">`;
      h += `<title>e ∈ [${b.lo}, ${b.hi}) · n=${b.count}</title></rect>`;
      if (b.count > 0) {
        h += `<text x="${x + barW/2}" y="${y - 3}" text-anchor="middle" fill="#cfd5e1" font-size="9">${b.count}</text>`;
      }
    });
    // x-axis ticks (0, 0.3, 0.6, 0.9, 1.2)
    const ticks = [0, 0.3, 0.6, 0.9, 1.2];
    const xMax = histRange[1] || 1.2;
    ticks.forEach(t => {
      const tx = hp.l + (t / xMax) * iW;
      h += `<line x1="${tx}" y1="${hp.t + iH}" x2="${tx}" y2="${hp.t + iH + 4}" stroke="#a8b0bd"/>`;
      h += `<text x="${tx}" y="${hp.t + iH + 16}" text-anchor="middle" fill="#a8b0bd" font-size="10">${t.toFixed(1)}</text>`;
    });
    // y-axis label
    h += `<text x="${hp.l - 6}" y="${hp.t + 8}" text-anchor="end" fill="#a8b0bd" font-size="10">${maxCount}</text>`;
    h += `<text x="${hp.l - 6}" y="${hp.t + iH}" text-anchor="end" fill="#a8b0bd" font-size="10">0</text>`;
    // axis title
    h += `<text x="${hp.l + iW/2}" y="${hH - 6}" text-anchor="middle" fill="#cfd5e1" font-size="11">반발 계수 e</text>`;
    h += `<text x="12" y="${hp.t + iH/2}" text-anchor="middle" fill="#cfd5e1" font-size="11" transform="rotate(-90 12 ${hp.t + iH/2})">위치 수</text>`;
    // median line
    if (summary.median_e != null && isFinite(summary.median_e)) {
      const mx = hp.l + (summary.median_e / xMax) * iW;
      h += `<line x1="${mx}" y1="${hp.t}" x2="${mx}" y2="${hp.t + iH}" stroke="#f0b400" stroke-width="1.2" stroke-dasharray="3,3"/>`;
      h += `<text x="${mx + 3}" y="${hp.t + 10}" fill="#f0b400" font-size="10">median ${Number(summary.median_e).toFixed(2)}</text>`;
    }
    h += `</svg>`;
    histHost.innerHTML = h;
  }

  if (statusHost) {
    statusHost.textContent = `${summary.n_valid || 0}개 위치에서 e 값 계산 완료 (전체 ${summary.n_total || rows.length}개).`;
  }
}

function _physRenderRecoveryDamping(data) {
  const pay = (data && data.RecoveryDamping) || null;
  const host = document.getElementById('phys-recovery-damping-body');
  if (!host) return;
  host.innerHTML = '';

  if (!pay || !pay.per_part || !pay.per_part.length) {
    const msg = el('div', { class: 'phys-rd-empty' },
      '댐핑/회복 시간 데이터를 계산할 수 없습니다 — PartMotion 가속도 시계열이 ' +
      '부족하거나 모든 부품에서 post-peak 신호가 0이기 때문입니다. ' +
      'unified_analyzer의 motion CSV 출력을 확인해 주세요.');
    host.appendChild(msg);
    return;
  }

  const rows = pay.per_part.filter(r => r.has_data);
  if (!rows.length) {
    const msg = el('div', { class: 'phys-rd-empty' },
      '활성 부품 motion 데이터가 없어 댐핑 비를 추정할 수 없습니다 — ' +
      '모든 부품의 post-peak 가속도가 너무 짧거나 0 입니다.');
    host.appendChild(msg);
    return;
  }

  // --- header summary ------------------------------------------------------
  const summ = pay.summary || {};
  const head = el('div', { class: 'phys-rd-head' });
  head.appendChild(el('div', { class: 'phys-rd-kpi' }, [
    el('div', { class: 'k' }, '중앙값 회복 시간'),
    el('div', { class: 'v' },
      (summ.median_recovery_ms != null ? fmt(summ.median_recovery_ms, 2) + ' ms' : '-'))
  ]));
  head.appendChild(el('div', { class: 'phys-rd-kpi' }, [
    el('div', { class: 'k' }, '중앙값 ζ'),
    el('div', { class: 'v' },
      (summ.median_damping_pct != null ? fmt(summ.median_damping_pct, 1) + ' %' : '-'))
  ]));
  head.appendChild(el('div', { class: 'phys-rd-kpi' }, [
    el('div', { class: 'k' }, '최저 댐핑 (공진 위험)'),
    el('div', { class: 'v vbad' }, summ.top_underdamped_part_name || '-')
  ]));
  head.appendChild(el('div', { class: 'phys-rd-kpi' }, [
    el('div', { class: 'k' }, '최고 댐핑'),
    el('div', { class: 'v vgood' }, summ.top_overdamped_part_name || '-')
  ]));
  head.appendChild(el('div', { class: 'phys-rd-kpi' }, [
    el('div', { class: 'k' }, '분석 위치'),
    el('div', { class: 'v' }, 'pos #' + (pay.pos_id_used || '-'))
  ]));
  host.appendChild(head);

  // --- two-column bar charts ----------------------------------------------
  // top 12 by damping (already sorted desc); we'll keep that order on the right
  // chart and re-sort by recovery time desc for the left chart.
  const top = rows.slice(0, 12);
  const byRecovery = top.slice().sort((a, b) => (b.recovery_time_ms || 0) - (a.recovery_time_ms || 0));
  const byDamping = top.slice().sort((a, b) => (b.damping_ratio_estimated || 0) - (a.damping_ratio_estimated || 0));

  // shared color: low damping = orange, high damping = green
  // We compute ζ thresholds *from the data* so panels with very small or
  // very large ζ adapt instead of using a magic 0.05 cut-off.
  const zs = top.map(r => r.damping_ratio_estimated || 0).filter(v => v > 0);
  let zLo = 0, zHi = 1;
  if (zs.length) {
    const s = zs.slice().sort((a, b) => a - b);
    zLo = s[Math.floor(s.length * 0.25)] || 0;
    zHi = s[Math.floor(s.length * 0.75)] || 1;
    if (zHi <= zLo) zHi = zLo + 1e-6;
  }
  function _zColor(z) {
    if (z == null) return '#5a6470';
    const t = Math.max(0, Math.min(1, (z - zLo) / (zHi - zLo)));
    // orange (255,140,0) -> green (60,200,90)
    const r = Math.round(255 + (60 - 255) * t);
    const g = Math.round(140 + (200 - 140) * t);
    const b = Math.round(0 + (90 - 0) * t);
    return 'rgb(' + r + ',' + g + ',' + b + ')';
  }

  function _drawBars(parent, rowsIn, valueKey, unitLabel, headerText) {
    const W = 420, H = 28 * rowsIn.length + 48, PADL = 150, PADR = 56, PADT = 32, PADB = 8;
    const innerW = W - PADL - PADR;
    const root = svg('svg', {
      viewBox: '0 0 ' + W + ' ' + H, width: '100%',
      preserveAspectRatio: 'xMidYMid meet', class: 'phys-rd-bars'
    });
    // title
    const tnode = svg('text', {
      x: 12, y: 18, fill: '#c9d1d9', 'font-size': 12, 'font-weight': 600
    });
    tnode.appendChild(document.createTextNode(headerText));
    root.appendChild(tnode);

    const vmax = Math.max.apply(null, rowsIn.map(r => r[valueKey] || 0));
    const denom = vmax > 0 ? vmax : 1;
    const bh = 20;
    rowsIn.forEach((r, i) => {
      const y = PADT + i * 28;
      const v = r[valueKey] || 0;
      const w = Math.max(0, (v / denom) * innerW);
      const z = r.damping_ratio_estimated;
      const color = _zColor(z);
      // part name label (left)
      const nm = svg('text', {
        x: PADL - 6, y: y + bh * 0.7, fill: '#c9d1d9',
        'font-size': 10, 'text-anchor': 'end'
      });
      nm.appendChild(document.createTextNode(r.part_name.slice(0, 22)));
      root.appendChild(nm);
      // bar background
      root.appendChild(svg('rect', {
        x: PADL, y: y, width: innerW, height: bh, fill: '#1c2128',
        stroke: '#2a3038', 'stroke-width': 0.5
      }));
      // bar
      root.appendChild(svg('rect', {
        x: PADL, y: y, width: w, height: bh, fill: color, opacity: 0.92
      }));
      // value label (right)
      const vtxt = svg('text', {
        x: PADL + w + 4, y: y + bh * 0.7, fill: '#c9d1d9', 'font-size': 10
      });
      const sval = (v == null || !isFinite(v))
        ? '-'
        : (valueKey === 'damping_ratio_estimated' ? (v * 100).toFixed(2) + ' %' : fmt(v, 2) + ' ' + unitLabel);
      vtxt.appendChild(document.createTextNode(sval));
      root.appendChild(vtxt);
    });
    parent.appendChild(root);
  }

  const grid = el('div', { class: 'phys-rd-grid' });
  const colL = el('div', { class: 'phys-rd-col' });
  const colR = el('div', { class: 'phys-rd-col' });
  _drawBars(colL, byRecovery, 'recovery_time_ms', 'ms', '5% 회복 시간 (ms)');
  _drawBars(colR, byDamping, 'damping_ratio_estimated', '%', '추정 댐핑 비 ζ (%)');
  grid.appendChild(colL);
  grid.appendChild(colR);
  host.appendChild(grid);

  // caption
  const cap = el('div', { class: 'phys-rd-caption' },
    '5% 감쇠 시간 = 진동 격리 여부. ζ < 0.05 = 저댐핑 (공진 위험). ' +
    'ω_n은 deep_analytics FFT 또는 zero-crossing 추정; ' +
    'log-decrement으로 ζ를 산출했습니다.');
  host.appendChild(cap);
}
function _physRenderWorstCombinations(data) {
  const root = document.getElementById('phys-worst-combinations');
  if (!root) return;
  const body = root.querySelector('.panel-body') || root;
  body.innerHTML = '';

  const placeholderLong = '통합 위험도 점수를 계산할 충분한 데이터가 없습니다 (PairResult 또는 P95 정규화 기준값이 비어있거나 NaN).';

  if (!data || data.ok === false || !Array.isArray(data.top_25) || data.top_25.length === 0) {
    const empty = el('div', { class: 'wc-empty' }, [
      (data && data.reason) ? data.reason : placeholderLong
    ]);
    body.appendChild(empty);
    return;
  }

  const u = (data.unit_labels) || {};
  const uG = (typeof _u === 'function') ? _u('accel_g', u) : (u.accel_g || 'g');
  const uS = (typeof _u === 'function') ? _u('stress', u) : (u.stress || 'Pa');
  const uD = (typeof _u === 'function') ? _u('disp', u) : (u.disp || 'm');

  const dist = data.distribution || {};
  const ms = data.max_summary || null;
  const p95n = data.p95_norm || {};

  // ---- KPI strip ----
  const kpiStrip = el('div', { class: 'wc-kpi-strip' });
  const _num = (v, d) => (v === null || v === undefined || !isFinite(v)) ? '—' : (typeof fmt === 'function' ? fmt(v, d) : Number(v).toFixed(d));

  kpiStrip.appendChild(el('div', { class: 'wc-kpi wc-kpi-critical' }, [
    el('div', { class: 'wc-kpi-label' }, ['임계 초과 조합 (risk ≥ 1.0)']),
    el('div', { class: 'wc-kpi-value' }, [String(dist.n_above_risk_1 || 0)]),
    el('div', { class: 'wc-kpi-sub' }, ['전체 ' + (data.n_total || 0) + '개 중'])
  ]));

  kpiStrip.appendChild(el('div', { class: 'wc-kpi' }, [
    el('div', { class: 'wc-kpi-label' }, ['최대 위험도']),
    el('div', { class: 'wc-kpi-value' }, [_num(dist.max_risk, 3)]),
    el('div', { class: 'wc-kpi-sub' }, [
      ms ? ('Pos #' + ms.pos_id + ' · ' + (ms.part_name || ('Part ' + ms.part_id))) : '데이터 없음'
    ])
  ]));

  kpiStrip.appendChild(el('div', { class: 'wc-kpi' }, [
    el('div', { class: 'wc-kpi-label' }, ['P95 위험도 임계값']),
    el('div', { class: 'wc-kpi-value' }, [_num(dist.p95_risk, 3)]),
    el('div', { class: 'wc-kpi-sub' }, ['상위 5% 진입선'])
  ]));

  kpiStrip.appendChild(el('div', { class: 'wc-kpi' }, [
    el('div', { class: 'wc-kpi-label' }, ['P95 정규화 기준']),
    el('div', { class: 'wc-kpi-value wc-kpi-value-sm' }, [
      'g=' + _num(p95n.peak_g, 2) + ' · σ=' + _num(p95n.peak_stress, 3) + ' · d=' + _num(p95n.peak_disp, 4)
    ]),
    el('div', { class: 'wc-kpi-sub' }, ['전 625행 P95 (' + uG + ', ' + uS + ', ' + uD + ')'])
  ]));

  body.appendChild(kpiStrip);

  // ---- repeat-position chips ----
  const chips = data.top_3_positions_by_count || [];
  if (chips.length > 0) {
    const chipRow = el('div', { class: 'wc-chip-row' }, [
      el('span', { class: 'wc-chip-label' }, ['반복 출현 위치 (TOP25 내):'])
    ]);
    chips.forEach(c => {
      const txt = 'Pos #' + c.pos_id + ' (' + c.face + ') × ' + c.n_in_top25;
      chipRow.appendChild(el('span', { class: 'wc-chip' }, [txt]));
    });
    body.appendChild(chipRow);
  }

  // ---- sortable table ----
  const cols = [
    { key: 'rank',        label: '#',           num: true,  fmt: r => String(r.rank) },
    { key: 'face',        label: 'Face',        num: false, fmt: r => r.face || '—' },
    { key: 'pos_id',      label: 'Pos',         num: true,  fmt: r => '#' + r.pos_id },
    { key: 'xy',          label: '(x, y)',      num: false, fmt: r => (r.x === null || r.y === null) ? '—' : '(' + _num(r.x, 3) + ', ' + _num(r.y, 3) + ')',
                          sortVal: r => (r.x === null ? 0 : r.x) },
    { key: 'part_name',   label: 'Part',        num: false, fmt: r => r.part_name || ('Part ' + r.part_id) },
    { key: 'peak_g',      label: 'peak_g ('+uG+')',     num: true,  fmt: r => _num(r.peak_g, 1) },
    { key: 'peak_stress', label: 'peak_stress ('+uS+')',num: true,  fmt: r => _num(r.peak_stress, 3) },
    { key: 'peak_disp',   label: 'peak_disp ('+uD+')',  num: true,  fmt: r => _num(r.peak_disp, 4) },
    { key: 'risk',        label: 'Risk',        num: true,  fmt: r => _num(r.risk, 3), risk: true },
  ];

  const tableWrap = el('div', { class: 'wc-table-wrap' });
  const table = el('table', { class: 'wc-table' });
  const thead = el('thead');
  const headRow = el('tr');
  let sortState = { key: 'rank', dir: 'asc' };
  let rowsData = data.top_25.slice();

  cols.forEach(c => {
    const th = el('th', {
      class: 'wc-th' + (c.num ? ' wc-th-num' : ''),
      'data-key': c.key,
    }, [c.label, el('span', { class: 'wc-sort-ind' }, [''])]);
    th.addEventListener('click', () => {
      if (sortState.key === c.key) {
        sortState.dir = (sortState.dir === 'asc') ? 'desc' : 'asc';
      } else {
        sortState.key = c.key;
        sortState.dir = c.num ? 'desc' : 'asc';
      }
      renderRows();
    });
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);
  table.appendChild(thead);
  const tbody = el('tbody');
  table.appendChild(tbody);
  tableWrap.appendChild(table);
  body.appendChild(tableWrap);

  function riskClass(v) {
    if (v === null || v === undefined || !isFinite(v)) return 'wc-risk-na';
    if (v > 0.9) return 'wc-risk-red';
    if (v > 0.7) return 'wc-risk-orange';
    return 'wc-risk-gray';
  }

  function renderRows() {
    const col = cols.find(c => c.key === sortState.key) || cols[0];
    const getVal = col.sortVal || (r => r[col.key]);
    const dir = sortState.dir === 'asc' ? 1 : -1;
    rowsData.sort((a, b) => {
      const va = getVal(a), vb = getVal(b);
      if (va === null || va === undefined) return 1;
      if (vb === null || vb === undefined) return -1;
      if (typeof va === 'number' && typeof vb === 'number') return (va - vb) * dir;
      return String(va).localeCompare(String(vb)) * dir;
    });

    tbody.innerHTML = '';
    rowsData.forEach(r => {
      const tr = el('tr', { class: 'wc-row' });
      cols.forEach(c => {
        const td = el('td', { class: 'wc-td' + (c.num ? ' wc-td-num' : '') }, [c.fmt(r)]);
        if (c.risk) {
          td.classList.add(riskClass(r.risk));
        }
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });

    // update sort indicators
    headRow.querySelectorAll('.wc-th').forEach(th => {
      const ind = th.querySelector('.wc-sort-ind');
      if (!ind) return;
      if (th.getAttribute('data-key') === sortState.key) {
        ind.textContent = sortState.dir === 'asc' ? ' ▲' : ' ▼';
      } else {
        ind.textContent = '';
      }
    });
  }
  renderRows();

  // caption
  body.appendChild(el('div', { class: 'wc-caption' }, [
    '통합 위험도 점수 (peak_g 40% + stress 40% + disp 20%, P95 정규화). 단일 ranking 으로 최우선 위험 식별. 색상: 빨강 >0.9, 주황 >0.7, 회색 그 외.'
  ]));
}

// === PHYSICS_JS_FUNCTIONS_INSERT_HERE ===
// Section-08 _physRenderXxx render functions are inserted ABOVE this line.

const PHYSICS_STATE = { active_panel: null };

function initPhysics() {
  const data = (DATA && DATA.physics) || null;
  const sec = document.getElementById('s8');
  const navLink = document.getElementById('navS8');
  if (!data || !sec) {
    if (sec) sec.style.display = 'none';
    if (navLink) navLink.style.display = 'none';
    return;
  }
  const populated = Object.keys(data).some(k => {
    const v = data[k];
    return v && (typeof v !== 'object' || Object.keys(v).length > 0 || (Array.isArray(v) && v.length > 0));
  });
  if (!populated) {
    sec.style.display = 'none';
    if (navLink) navLink.style.display = 'none';
    return;
  }
  _physRenderStressWaveVelocity(DATA);
  _physRenderRestitutionMap(DATA);
  _physRenderRecoveryDamping(DATA);
  _physRenderWorstCombinations((typeof DATA !== 'undefined' && DATA.physics) ? DATA.physics.worst_combinations : null);
  // === PHYSICS_BOOT_CALLS_INSERT_HERE ===
  // Workflow-added _physRenderXxx(data) calls are inserted ABOVE this line.
}

// === INSIGHT_JS_FUNCTIONS_INSERT_HERE ===
// Section-07 _insightRenderXxx render functions are inserted ABOVE this line.

"""
