# 섹션 07 — INSIGHTS HTML 템플릿 (기계적 분할, 바이트 불변)

_PAGE7 = """
<section id="s7">
  <div class="page-head">
    <span class="num">07</span>
    <span class="t">INSIGHTS & RECOMMENDATIONS</span>
    <span class="sub">설계 검증 · 손상 정량 · 충격 후 거동 · 자동 권고</span>
    <span class="sub">SYMMETRY / DAMAGE / REBOUND / 3D TRAJ / RECOMMEND / PULSE</span>
  </div>

  <div class="panel" style="background:transparent;border:none;padding:0;">
<section class="insight-panel" id="insight-panel-symmetry" data-key="Symmetry">
  <h3 class="insight-title">대칭성 &amp; 경계 효과 분석</h3>
  <div class="insight-body" id="insight-symmetry"></div>
</section>
    <div id="insight-DamageIndex" class="insight-panel">
  <div class="insight-title">부품별 누적 손상 지표 (DI)</div>
  <div class="insight-body"></div>
</div>
<section id="insight-rebound-field" class="insight-panel rf-panel">
  <header class="insight-head">
    <h3>충격 후 반발 벡터장</h3>
    <p class="insight-sub">5×5 격자에서 impactor 반발 속도의 xy 성분을 화살표로, vz 부호를 색으로 표시</p>
  </header>
  <div class="rf-kpis"></div>
  <div class="rf-svg-wrap"></div>
  <p class="rf-caption">화살표 = 반발 방향 (xy). 파랑 = bounce (vz↑), 빨강 = embed/penetrate (vz↓), 회색 = flat. 화살표 길이 ∝ |v_xy| / max(|v_xy|).</p>
</section>
<div id="insight-panel-auto-recommend" class="insight-panel">
  <div class="insight-header">
    <h3>엔지니어링 자동 권고</h3>
    <div class="insight-subtitle">데이터 기반 규칙으로 생성된 보강/검토 권고 — 심각도 순 정렬</div>
  </div>
  <div class="insight-body"></div>
</div>

<div class="insight-panel" id="insight-panel-ContactPulse">
  <div class="insight-header">
    <h3>충격 펄스 통계 (Contact Pulse Statistics)</h3>
    <div class="insight-sub">위치별 contact 지속시간 · 밀도 · 펄스→피크 시간</div>
  </div>
  <div id="insight-ContactPulse" class="insight-body"></div>
</div>
<section id="insight-panel-trajectory3d" class="insight-panel">
  <header class="insight-head">
    <h3>3D 트래젝터리 번들</h3>
    <p class="insight-sub">25개 위치 impactor 경로를 등각투영으로 동시 표시 (각 경로 최대 30포인트)</p>
  </header>
  <div id="trajectory3d-svg" class="t3d-svg-wrap"></div>
  <p class="t3d-caption">25 위치 충돌체 경로 동시 표시. 색 = behavior.</p>
</section>
<!-- INSIGHT_PANELS_INSERT_HERE -->
    <!-- Workflow-added panel templates are inserted ABOVE this marker. -->
  </div>
</section>
"""


_JS_S7 = r"""function _insightRenderSymmetry(data){
  const root = document.getElementById('insight-symmetry');
  if(!root) return;
  if(!data){ root.innerHTML = '<div class="ins-empty">데이터 없음</div>'; return; }

  const xPairs = data.x_mirror_pairs || [];
  const yPairs = data.y_mirror_pairs || [];
  const bs = data.boundary_summary || {};
  const medX = (data.median_x_asym_pct==null) ? NaN : data.median_x_asym_pct;
  const medY = (data.median_y_asym_pct==null) ? NaN : data.median_y_asym_pct;

  const symX = isFinite(medX) ? Math.max(0, 100 - medX) : NaN;
  const symY = isFinite(medY) ? Math.max(0, 100 - medY) : NaN;
  const bamp = (bs.boundary_amplification_pct==null) ? NaN : bs.boundary_amplification_pct;

  const fnum = (v, nd=1) => (v==null || !isFinite(v)) ? '—' : Number(v).toFixed(nd);

  const verdictOk = !!data.design_symmetric;
  let verdictText, verdictCls;
  if(verdictOk){
    verdictText = '디자인 대칭성 양호 (X·Y 중앙값 비대칭 < 15%)';
    verdictCls = 'sym-verdict ok';
  } else {
    const reasons = [];
    if(isFinite(medX) && medX >= 15) reasons.push('X축 비대칭');
    if(isFinite(medY) && medY >= 15) reasons.push('Y축 비대칭');
    if(!reasons.length) reasons.push('데이터 불충분');
    verdictText = reasons.join(' · ');
    verdictCls = 'sym-verdict warn';
  }

  const kpi = (label, value, suffix) => `
    <div class="sym-kpi">
      <div class="sym-kpi-lbl">${label}</div>
      <div class="sym-kpi-val">${fnum(value,1)}<span class="sym-kpi-suf">${suffix||''}</span></div>
    </div>`;

  const rowHtml = (p) => {
    const cls = p.asymmetry_pct >= 15 ? 'hi' : (p.asymmetry_pct >= 8 ? 'mid' : '');
    return `<tr class="${cls}">
      <td class="sym-pair">#${p.pos_a} ↔ #${p.pos_b}</td>
      <td class="sym-num">${fnum(p.peak_g_a,2)}</td>
      <td class="sym-num">${fnum(p.peak_g_b,2)}</td>
      <td class="sym-num sym-asym">${fnum(p.asymmetry_pct,2)}%</td>
    </tr>`;
  };

  const tableHtml = (title, pairs, count) => {
    if(!pairs.length){
      return `<div class="sym-tblbox"><div class="sym-tbl-title">${title}</div>
        <div class="ins-empty">미러 쌍 없음</div></div>`;
    }
    const subtitle = count > pairs.length ? `상위 ${pairs.length} / 총 ${count}` : `${pairs.length}쌍`;
    return `<div class="sym-tblbox">
      <div class="sym-tbl-title">${title} <span class="sym-tbl-sub">${subtitle}</span></div>
      <table class="sym-tbl">
        <thead><tr>
          <th>위치 쌍</th><th>peak_g A</th><th>peak_g B</th><th>비대칭%</th>
        </tr></thead>
        <tbody>${pairs.map(rowHtml).join('')}</tbody>
      </table>
    </div>`;
  };

  const gunit = (typeof _u === 'function') ? _u('peak_g','G') : 'G';

  root.innerHTML = `
    <div class="sym-kpis">
      ${kpi('X 대칭성 점수', symX, ' /100')}
      ${kpi('Y 대칭성 점수', symY, ' /100')}
      ${kpi('경계 증폭률', bamp, '%')}
      <div class="sym-kpi sym-kpi-meta">
        <div class="sym-kpi-lbl">외곽 / 내부 평균 peak_g</div>
        <div class="sym-kpi-val sym-kpi-val-sm">
          ${fnum(bs.outer_mean_peak_g,2)} <span class="sym-kpi-suf">vs</span> ${fnum(bs.inner_mean_peak_g,2)}
          <span class="sym-kpi-suf"> ${gunit} (n=${bs.outer_n||0}/${bs.inner_n||0})</span>
        </div>
      </div>
    </div>
    <div class="${verdictCls}">${verdictText}</div>
    <div class="sym-tables">
      ${tableHtml('X-미러 쌍 ((x,y) ↔ (-x,y))', xPairs, data.x_pair_count||xPairs.length)}
      ${tableHtml('Y-미러 쌍 ((x,y) ↔ (x,-y))', yPairs, data.y_pair_count||yPairs.length)}
    </div>
    <div class="sym-foot">
      중앙값 비대칭: X = ${fnum(medX,2)}% · Y = ${fnum(medY,2)}% &nbsp;|&nbsp;
      외곽 = 위치별 max(|x|,|y|)가 면 최대치인 점, 내부 = 그 외.
    </div>
  `;
}
function _insightRenderDamageIndex(data){
  const root = document.getElementById('insight-DamageIndex');
  if(!root) return;
  const body = root.querySelector('.insight-body');
  if(!body) return;
  body.innerHTML = '';

  const d = (data && data.DamageIndex) || null;
  if(!d || !d.per_part || d.per_part.length === 0){
    body.innerHTML = '<div class="di-empty">데이터 없음 — DI를 계산할 수 있는 부품이 없습니다.</div>';
    return;
  }

  const per = d.per_part;
  const pairs = d.top_pairs || [];
  const summary = d.summary || {};
  const source = per[0].di_source;
  const sourceLabel = source === 'yield'
    ? 'yield-based (∑ max(0, σ/σ_y − 1) over positions)'
    : 'composite (normalized peak g/stress/strain → [0,1])';

  // Caption
  const cap = document.createElement('div');
  cap.className = 'di-caption';
  const mp = summary.max_di_part ? `${summary.max_di_part} @ pos ${summary.max_di_position ?? '—'}` : '—';
  cap.innerHTML = `<b>DI 산정 방식:</b> ${sourceLabel} &nbsp;·&nbsp; ` +
                  `<b>최대 DI:</b> ${(summary.max_di_value ?? 0).toFixed(3)} (${mp}) &nbsp;·&nbsp; ` +
                  `<b>대상 부품:</b> ${summary.n_parts_with_data}/${summary.n_parts_total}`;
  body.appendChild(cap);

  // Two-column layout
  const wrap = document.createElement('div');
  wrap.className = 'di-wrap';
  body.appendChild(wrap);

  // --- LEFT: horizontal bar chart (top-12) ---
  const left = document.createElement('div');
  left.className = 'di-left';
  wrap.appendChild(left);
  const h2 = document.createElement('div');
  h2.className = 'di-subtitle';
  h2.textContent = '부품별 DI (Top 12)';
  left.appendChild(h2);

  const top12 = per.slice(0, 12);
  const maxDi = Math.max.apply(null, top12.map(r => r.di)) || 1.0;
  const W = 560, rowH = 26, labelW = 150, valueW = 70;
  const chartW = W - labelW - valueW - 16;
  const H = top12.length * rowH + 12;
  const s = svg(W, H);
  s.setAttribute('class', 'di-svg');

  top12.forEach((r, i) => {
    const y = i * rowH + 6;
    const frac = (maxDi > 0) ? (r.di / maxDi) : 0;
    const barLen = Math.max(1, frac * chartW);

    // red gradient: deeper red for larger DI fraction
    const t = Math.min(1, Math.max(0, frac));
    // interpolate from #fee0d2 (light) to #99000d (deep red)
    const lerp = (a,b)=> Math.round(a + (b - a) * t);
    const r1 = lerp(254, 153), g1 = lerp(224, 0), b1 = lerp(210, 13);
    const fill = `rgb(${r1},${g1},${b1})`;

    // label
    const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    label.setAttribute('x', labelW - 6);
    label.setAttribute('y', y + rowH/2 + 4);
    label.setAttribute('text-anchor', 'end');
    label.setAttribute('class', 'di-label');
    const nm = (r.part_name || ('part_' + r.part_id));
    label.textContent = nm.length > 22 ? (nm.slice(0,21) + '…') : nm;
    label.setAttribute('title', nm);
    s.appendChild(label);

    // bar background
    const bgRect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    bgRect.setAttribute('x', labelW);
    bgRect.setAttribute('y', y + 4);
    bgRect.setAttribute('width', chartW);
    bgRect.setAttribute('height', rowH - 10);
    bgRect.setAttribute('fill', '#f6f6f6');
    bgRect.setAttribute('stroke', '#e5e5e5');
    s.appendChild(bgRect);

    // bar
    const bar = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    bar.setAttribute('x', labelW);
    bar.setAttribute('y', y + 4);
    bar.setAttribute('width', barLen);
    bar.setAttribute('height', rowH - 10);
    bar.setAttribute('fill', fill);
    bar.setAttribute('class', 'di-bar');
    // Tooltip
    let tip = `${nm}\nDI = ${r.di.toFixed(3)}\nsource: ${r.di_source}`;
    if(r.di_source === 'yield'){
      tip += `\nyield σ_y = ${r.yield_stress}\n초과 위치 수 = ${r.n_positions_above_yield}/${r.n_positions}`;
      tip += `\n최대 기여 위치: pos ${r.peak_pos_id ?? '—'}`;
    } else {
      tip += `\nmax peak_g = ${r.max_peak_g}`;
      tip += `\nmax peak_stress = ${r.max_peak_stress}`;
      tip += `\nmax peak_strain = ${r.max_peak_strain}`;
      tip += `\n최대 기여 위치: pos ${r.peak_pos_id ?? '—'}`;
    }
    const ttl = document.createElementNS('http://www.w3.org/2000/svg', 'title');
    ttl.textContent = tip;
    bar.appendChild(ttl);
    s.appendChild(bar);

    // value text
    const vt = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    vt.setAttribute('x', labelW + chartW + 6);
    vt.setAttribute('y', y + rowH/2 + 4);
    vt.setAttribute('class', 'di-value');
    vt.textContent = r.di.toFixed(3);
    s.appendChild(vt);
  });
  left.appendChild(s);

  // --- RIGHT: dominant (part, pos) Top 5 ---
  const right = document.createElement('div');
  right.className = 'di-right';
  wrap.appendChild(right);
  const h3 = document.createElement('div');
  h3.className = 'di-subtitle';
  h3.textContent = '지배적 (부품, 위치) Top 5';
  right.appendChild(h3);

  if(pairs.length === 0){
    const noPair = document.createElement('div');
    noPair.className = 'di-empty';
    noPair.textContent = '기여 위치 없음';
    right.appendChild(noPair);
  } else {
    const ol = document.createElement('ol');
    ol.className = 'di-pair-list';
    const maxContrib = Math.max.apply(null, pairs.map(p=>p.contrib)) || 1.0;
    pairs.forEach((p, idx) => {
      const li = document.createElement('li');
      const frac = (maxContrib > 0) ? p.contrib / maxContrib : 0;
      const t = Math.min(1, Math.max(0, frac));
      const lerp = (a,b)=> Math.round(a + (b - a) * t);
      const fill = `rgb(${lerp(254,153)},${lerp(224,0)},${lerp(210,13)})`;
      const nm = (p.part_name || ('part_' + p.part_id));
      li.innerHTML =
        `<span class="di-rank">${idx+1}</span>` +
        `<span class="di-pair-name" title="${nm}">${nm.length>18?nm.slice(0,17)+'…':nm}@${p.pos_id}</span>` +
        `<span class="di-pair-bar"><span class="di-pair-fill" style="width:${(frac*100).toFixed(1)}%;background:${fill}"></span></span>` +
        `<span class="di-pair-val">${p.contrib.toFixed(3)}</span>`;
      ol.appendChild(li);
    });
    right.appendChild(ol);
  }
}
function _insightRenderReboundField(data){
  const root = document.getElementById('insight-rebound-field');
  if(!root) return;
  if(!data || !data.vectors || data.vectors.length === 0){
    root.innerHTML = '<div class="insight-empty">반발 벡터 데이터 없음</div>';
    return;
  }

  const vectors = data.vectors;
  const bbox = data.bbox || [0,0,1,1];
  const maxSpeed = Math.max(data.max_speed || 0, 1e-9);
  const velU = data.vel_unit || 'm/s';

  // KPI bar
  const kpi = root.querySelector('.rf-kpis');
  if(kpi){
    kpi.innerHTML = `
      <div class="rf-kpi"><span class="rf-kpi-lbl">평균 반발 속도</span><span class="rf-kpi-val">${fmt(data.avg_speed,2)} ${velU}</span></div>
      <div class="rf-kpi"><span class="rf-kpi-lbl">최대 반발 속도</span><span class="rf-kpi-val">${fmt(data.max_speed,2)} ${velU}</span></div>
      <div class="rf-kpi"><span class="rf-kpi-lbl">바운스 (vz↑)</span><span class="rf-kpi-val rf-up">${data.n_rebound_up} / ${data.n_total}</span></div>
      <div class="rf-kpi"><span class="rf-kpi-lbl">관통/매립 (vz↓)</span><span class="rf-kpi-val rf-down">${data.n_embed_down} / ${data.n_total}</span></div>
      <div class="rf-kpi"><span class="rf-kpi-lbl">슬라이딩 (xy우세)</span><span class="rf-kpi-val">${data.n_sliding} / ${data.n_total}</span></div>
    `;
  }

  // SVG quiver — sized to device aspect (cells reflect physical layout)
  const _dgR = (typeof DATA !== 'undefined' && DATA.device_geometry) || {aspect: 1};
  const _arR = (_dgR.aspect && isFinite(_dgR.aspect) && _dgR.aspect > 0) ? _dgR.aspect : 1;
  const W = 460, H = Math.max(160, Math.round(W / _arR)), pad = 36;
  const [x0, y0, x1, y1] = bbox;
  const dx = Math.max(x1 - x0, 1e-9);
  const dy = Math.max(y1 - y0, 1e-9);
  const sx = (W - 2*pad) / dx;
  const sy = (H - 2*pad) / dy;
  const s = Math.min(sx, sy);

  // cell size (5x5 grid assumed): pick scale so max arrow ~ 0.45 * cell spacing
  // Estimate cell spacing from positions
  const uniqX = Array.from(new Set(vectors.map(v=>v.x))).sort((a,b)=>a-b);
  const uniqY = Array.from(new Set(vectors.map(v=>v.y))).sort((a,b)=>a-b);
  let cellW = (uniqX.length > 1) ? (uniqX[uniqX.length-1] - uniqX[0]) / (uniqX.length - 1) : dx/5;
  let cellH = (uniqY.length > 1) ? (uniqY[uniqY.length-1] - uniqY[0]) / (uniqY.length - 1) : dy/5;
  const cellPx = Math.min(cellW * s, cellH * s);
  const arrowMaxPx = 0.45 * cellPx;

  const xToPx = x => pad + (x - x0) * s;
  const yToPx = y => H - pad - (y - y0) * s; // flip Y

  let svgParts = [];
  // bbox frame
  svgParts.push(`<rect x="${pad}" y="${pad}" width="${W-2*pad}" height="${H-2*pad}" fill="#0d1117" stroke="#30363d" stroke-width="1"/>`);

  // Grid hints — light dotted lines at unique X/Y
  for(const xv of uniqX){
    const px = xToPx(xv);
    svgParts.push(`<line x1="${px}" y1="${pad}" x2="${px}" y2="${H-pad}" stroke="#21262d" stroke-width="0.5" stroke-dasharray="2 3"/>`);
  }
  for(const yv of uniqY){
    const py = yToPx(yv);
    svgParts.push(`<line x1="${pad}" y1="${py}" x2="${W-pad}" y2="${py}" stroke="#21262d" stroke-width="0.5" stroke-dasharray="2 3"/>`);
  }

  const colorFor = c => c === 'up' ? '#4493f8' : (c === 'down' ? '#f85149' : '#8b949e');

  // Arrows
  for(const v of vectors){
    const cx = xToPx(v.x);
    const cy = yToPx(v.y);
    const col = colorFor(v.color_class);

    // origin dot
    svgParts.push(`<circle cx="${cx}" cy="${cy}" r="2" fill="${col}" opacity="0.9"/>`);

    if(v.missing){ continue; }

    const mag = v.speed;
    if(mag < 1e-9){
      // draw an "x" to indicate no lateral motion
      svgParts.push(`<circle cx="${cx}" cy="${cy}" r="4" fill="none" stroke="${col}" stroke-width="1" opacity="0.6"/>`);
      continue;
    }

    const lenPx = (mag / maxSpeed) * arrowMaxPx;
    // vy positive = up in physical space; svg y is down, so flip
    const ux = v.vx_rebound / mag;
    const uy = -v.vy_rebound / mag;
    const ex = cx + ux * lenPx;
    const ey = cy + uy * lenPx;

    // arrow shaft
    svgParts.push(`<line x1="${cx}" y1="${cy}" x2="${ex}" y2="${ey}" stroke="${col}" stroke-width="1.6" opacity="0.95"/>`);

    // arrowhead
    const ah = Math.min(6, lenPx * 0.35);
    const ang = Math.atan2(uy, ux);
    const a1 = ang + 2.6;
    const a2 = ang - 2.6;
    const hx1 = ex + Math.cos(a1) * ah;
    const hy1 = ey + Math.sin(a1) * ah;
    const hx2 = ex + Math.cos(a2) * ah;
    const hy2 = ey + Math.sin(a2) * ah;
    svgParts.push(`<polygon points="${ex},${ey} ${hx1},${hy1} ${hx2},${hy2}" fill="${col}" opacity="0.95"/>`);

    // hover title
    svgParts.push(`<title>pos ${v.pos_id}: |v_xy|=${v.speed.toFixed(2)} ${velU}, v_z=${v.vz_final.toFixed(2)} ${velU}</title>`);
  }

  // Scale reference (bottom-left)
  const refX = pad + 6;
  const refY = H - 10;
  svgParts.push(`<line x1="${refX}" y1="${refY}" x2="${refX + arrowMaxPx}" y2="${refY}" stroke="#c9d1d9" stroke-width="1.5"/>`);
  svgParts.push(`<text x="${refX + arrowMaxPx + 6}" y="${refY + 3}" fill="#c9d1d9" font-size="10">${fmt(maxSpeed,2)} ${velU}</text>`);

  // Legend (top-right)
  const legendItems = [
    {c:'#4493f8', l:'bounce (vz↑)'},
    {c:'#f85149', l:'embed (vz↓)'},
    {c:'#8b949e', l:'flat'},
  ];
  let lx = W - pad - 110, ly = pad + 4;
  svgParts.push(`<rect x="${lx-6}" y="${ly-2}" width="116" height="${legendItems.length*14+6}" fill="#0d1117" stroke="#30363d" stroke-width="0.5" opacity="0.85"/>`);
  legendItems.forEach((it, i) => {
    const yy = ly + 10 + i*14;
    svgParts.push(`<line x1="${lx}" y1="${yy}" x2="${lx+18}" y2="${yy}" stroke="${it.c}" stroke-width="2"/>`);
    svgParts.push(`<text x="${lx+24}" y="${yy+3}" fill="#c9d1d9" font-size="10">${it.l}</text>`);
  });

  const svgWrap = root.querySelector('.rf-svg-wrap');
  if(svgWrap){
    svgWrap.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="100%" preserveAspectRatio="xMidYMid meet" style="height:auto">${svgParts.join('')}</svg>`;
    svgZoomPan(svgWrap.querySelector('svg'));
  }
}
function _insightRenderAutoRecommend(data) {
  const root = document.getElementById('insight-panel-auto-recommend');
  if (!root) return;
  const body = root.querySelector('.insight-body');
  if (!body) return;
  body.innerHTML = '';

  if (!data || !data.recommendations) {
    body.appendChild(el('div', {class: 'insight-empty'}, '권고 데이터 없음'));
    return;
  }

  // Merge with doe_analysis and deep_analytics if present
  const extra = [];
  try {
    const doe = (window.DATA && DATA.doe_analysis) ? DATA.doe_analysis : null;
    if (doe && doe.pca) {
      const pc1 = doe.pca.explained_variance_ratio
        ? (doe.pca.explained_variance_ratio[0] || 0) * 100.0
        : null;
      if (pc1 !== null && isFinite(pc1)) {
        let topLoad = '';
        if (doe.pca.top_loadings_pc1 && doe.pca.top_loadings_pc1.length) {
          topLoad = doe.pca.top_loadings_pc1[0].name || doe.pca.top_loadings_pc1[0].part_name || '';
        }
        extra.push({
          severity: pc1 > 60 ? 'warning' : 'info',
          title: 'PCA 모드 1 지배도',
          body: `PCA PC1이 전체 응답의 ${pc1.toFixed(1)}%를 설명${topLoad ? ` — '${topLoad}' 가 dominant loading` : ''}. 모드 1 형상에 대한 강성 분포 검토 권장.`,
          source_panel: 'DOE / PCA Analysis',
          metric: Number(pc1.toFixed(1))
        });
      }
    }
  } catch (e) { /* ignore */ }

  try {
    const deep = (window.DATA && DATA.deep_analytics) ? DATA.deep_analytics : null;
    if (deep && deep.anomalies && Array.isArray(deep.anomalies) && deep.anomalies.length) {
      const list = deep.anomalies.slice(0, 5)
        .map(a => `P${a.pos_id}(z=${(a.z != null ? a.z.toFixed(2) : '?')})`)
        .join(', ');
      extra.push({
        severity: 'warning',
        title: 'Deep Analytics 이상치',
        body: `${deep.anomalies.length}개 위치가 deep analytics 기준 이상치: ${list}.`,
        source_panel: 'Deep Analytics',
        metric: deep.anomalies.length
      });
    }
  } catch (e) { /* ignore */ }

  const all = (data.recommendations || []).concat(extra);
  const order = {critical: 0, warning: 1, info: 2};
  all.sort((a, b) => (order[a.severity] ?? 9) - (order[b.severity] ?? 9));

  const total = all.length;
  const crit = all.filter(r => r.severity === 'critical').length;
  const warn = all.filter(r => r.severity === 'warning').length;
  const info = all.filter(r => r.severity === 'info').length;

  const header = el('div', {class: 'ar-summary'});
  header.appendChild(el('span', {class: 'ar-chip ar-chip-total'}, `총 ${total}건`));
  header.appendChild(el('span', {class: 'ar-chip ar-chip-critical'}, `긴급 ${crit}`));
  header.appendChild(el('span', {class: 'ar-chip ar-chip-warning'}, `주의 ${warn}`));
  header.appendChild(el('span', {class: 'ar-chip ar-chip-info'}, `참고 ${info}`));
  body.appendChild(header);

  if (!all.length) {
    body.appendChild(el('div', {class: 'insight-empty'}, '생성된 권고가 없습니다. 입력 데이터 부족.'));
    return;
  }

  const grid = el('div', {class: 'ar-grid'});
  all.forEach(r => {
    const card = el('div', {class: `ar-card ar-${r.severity || 'info'}`});
    const stripe = el('div', {class: 'ar-stripe'});
    const main = el('div', {class: 'ar-main'});
    const titleRow = el('div', {class: 'ar-title-row'});
    titleRow.appendChild(el('span', {class: 'ar-sev-tag'},
      r.severity === 'critical' ? '긴급' :
      r.severity === 'warning'  ? '주의' : '참고'));
    titleRow.appendChild(el('span', {class: 'ar-title'}, r.title || '(제목 없음)'));
    if (r.metric != null) {
      titleRow.appendChild(el('span', {class: 'ar-metric'}, String(r.metric)));
    }
    main.appendChild(titleRow);
    main.appendChild(el('div', {class: 'ar-body'}, r.body || ''));
    if (r.source_panel) {
      const src = el('div', {class: 'ar-source'});
      src.appendChild(el('span', {class: 'ar-source-label'}, '출처:'));
      src.appendChild(el('span', {class: 'ar-source-tag'}, r.source_panel));
      main.appendChild(src);
    }
    card.appendChild(stripe);
    card.appendChild(main);
    grid.appendChild(card);
  });
  body.appendChild(grid);
}

function _insightRenderContactPulse(data){
  const root = document.getElementById('insight-ContactPulse');
  if(!root){ return; }
  if(!data || !data.per_position || data.per_position.length === 0){
    root.innerHTML = '<div class="ins-empty">유효한 contact pulse 데이터가 없습니다.</div>';
    return;
  }
  const pp = data.per_position.slice();
  const summary = data.summary || {};

  // Valid durations
  const valid = pp.filter(d => d.pulse_duration_ms !== null && isFinite(d.pulse_duration_ms));
  const durs = valid.map(d => d.pulse_duration_ms);
  const dMin = durs.length ? Math.min.apply(null, durs) : 0;
  const dMax = durs.length ? Math.max.apply(null, durs) : 1;
  const dRange = (dMax - dMin) || 1;

  // Color scale: short=red (sharp), long=blue (distributed)
  function colorFor(v){
    if(v === null || !isFinite(v)) return '#2a2a2a';
    const t = (v - dMin) / dRange;
    // red(short) -> yellow -> blue(long)
    const stops = [[220,60,60],[240,200,90],[70,140,220]];
    const tt = Math.max(0, Math.min(1, t));
    const seg = tt < 0.5 ? 0 : 1;
    const lt = tt < 0.5 ? tt*2 : (tt-0.5)*2;
    const a = stops[seg], b = stops[seg+1];
    const r = Math.round(a[0]+(b[0]-a[0])*lt);
    const g = Math.round(a[1]+(b[1]-a[1])*lt);
    const bl= Math.round(a[2]+(b[2]-a[2])*lt);
    return `rgb(${r},${g},${bl})`;
  }

  // --- Layout ---
  root.innerHTML = `
    <div class="cp-grid">
      <div class="cp-heatmap-wrap">
        <div class="cp-title">5×5 위치별 펄스 지속시간 (ms)</div>
        <div id="cp-heatmap"></div>
        <div class="cp-legend" id="cp-legend"></div>
      </div>
      <div class="cp-hist-wrap">
        <div class="cp-title">지속시간 분포 (10 bins)</div>
        <div id="cp-hist"></div>
        <div class="cp-stats" id="cp-stats"></div>
      </div>
    </div>
    <div class="cp-rank-wrap">
      <div class="cp-rank-col">
        <div class="cp-title">Top-5 최장 지속</div>
        <div id="cp-top5"></div>
      </div>
      <div class="cp-rank-col">
        <div class="cp-title">Bottom-5 최단 지속</div>
        <div id="cp-bot5"></div>
      </div>
    </div>
    <div class="cp-caption">Contact 지속시간 = first→last engaged 시간차. 짧을수록 강한 단발 충격, 길수록 분산된 충격.</div>
  `;

  // --- Heatmap (5x5) ---
  // Group by face if multiple, else single grid. Use x,y -> rank to 5x5.
  // Determine grid: sort unique x, unique y.
  const xs = Array.from(new Set(pp.map(p => +p.x.toFixed(6)))).sort((a,b)=>a-b);
  const ys = Array.from(new Set(pp.map(p => +p.y.toFixed(6)))).sort((a,b)=>a-b);
  const nx = Math.min(xs.length, 5);
  const ny = Math.min(ys.length, 5);

  const hmHost = document.getElementById('cp-heatmap');
  const _dgCP = (typeof DATA !== 'undefined' && DATA.device_geometry) || {aspect: 1};
  const _arCP = (_dgCP.aspect && isFinite(_dgCP.aspect) && _dgCP.aspect > 0) ? _dgCP.aspect : (56/40);
  const cellW = 56;
  // Each cell is one (nx,ny) DOE slot — its physical extent is
  // (device_w / nx) × (device_h / ny). With equal nx/ny ratios reduce to
  // device aspect itself.
  const cellH = Math.max(20, Math.min(120, Math.round(cellW * (ny / Math.max(nx,1)) / _arCP)));
  const padL = 30, padT = 10;
  const W = padL + nx*cellW + 10, H = padT + ny*cellH + 24;
  let svgEl = `<svg width="${W}" height="${H}" class="cp-hm-svg">`;
  // map x,y to cell indices
  function ix(v){ let best=0,bd=1e30; for(let i=0;i<xs.length;i++){const d=Math.abs(xs[i]-v); if(d<bd){bd=d;best=i;}} return best; }
  function iy(v){ let best=0,bd=1e30; for(let i=0;i<ys.length;i++){const d=Math.abs(ys[i]-v); if(d<bd){bd=d;best=i;}} return best; }

  // Build a map for quick lookup
  const cellMap = {};
  pp.forEach(p => {
    const i = ix(+p.x.toFixed(6));
    const j = iy(+p.y.toFixed(6));
    cellMap[`${i}_${j}`] = p;
  });

  for(let j=ny-1;j>=0;j--){
    for(let i=0;i<nx;i++){
      const x = padL + i*cellW;
      const y = padT + (ny-1-j)*cellH;
      const p = cellMap[`${i}_${j}`];
      const fill = p ? colorFor(p.pulse_duration_ms) : '#1a1a1a';
      const lbl = p ? (p.pulse_duration_ms!==null ? p.pulse_duration_ms.toFixed(1) : '—') : '';
      const pid = p ? `P${p.pos_id}` : '';
      svgEl += `<rect x="${x}" y="${y}" width="${cellW-2}" height="${cellH-2}" fill="${fill}" stroke="#444" stroke-width="0.5" rx="2">`;
      if(p){
        svgEl += `<title>P${p.pos_id} (${p.behavior_class})\n지속시간: ${p.pulse_duration_ms===null?'N/A':p.pulse_duration_ms.toFixed(2)+' ms'}\ncontact steps: ${p.n_contact_steps}\ndensity: ${(p.contact_density*100).toFixed(1)}%\npulse→peak: ${p.pulse_to_peak_ms===null?'N/A':p.pulse_to_peak_ms.toFixed(2)+' ms'}</title>`;
      }
      svgEl += `</rect>`;
      if(p){
        svgEl += `<text x="${x+cellW/2-1}" y="${y+cellH/2-3}" text-anchor="middle" fill="#fff" font-size="9" font-weight="600">${pid}</text>`;
        svgEl += `<text x="${x+cellW/2-1}" y="${y+cellH/2+9}" text-anchor="middle" fill="#fff" font-size="9">${lbl}</text>`;
      }
    }
  }
  svgEl += `<text x="${padL}" y="${H-6}" fill="#aaa" font-size="10">x →</text>`;
  svgEl += `<text x="2" y="${padT+10}" fill="#aaa" font-size="10">y↑</text>`;
  svgEl += `</svg>`;
  hmHost.innerHTML = svgEl;
  svgZoomPan(hmHost.querySelector('svg'));

  // Legend
  const legend = document.getElementById('cp-legend');
  let legHTML = '<div class="cp-legend-bar">';
  for(let k=0;k<20;k++){
    const v = dMin + (k/19)*dRange;
    legHTML += `<span style="background:${colorFor(v)}"></span>`;
  }
  legHTML += `</div><div class="cp-legend-labels"><span>${dMin.toFixed(1)} ms</span><span>${dMax.toFixed(1)} ms</span></div>`;
  legend.innerHTML = legHTML;

  // --- Histogram ---
  const hHost = document.getElementById('cp-hist');
  const nBins = 10;
  const bins = new Array(nBins).fill(0);
  const binEdges = [];
  for(let k=0;k<=nBins;k++){ binEdges.push(dMin + (k/nBins)*dRange); }
  durs.forEach(v => {
    let k = Math.floor((v - dMin) / dRange * nBins);
    if(k >= nBins) k = nBins-1;
    if(k < 0) k = 0;
    bins[k]++;
  });
  const maxCount = Math.max.apply(null, bins) || 1;
  const hW = 280, hH = 140, hpadL = 28, hpadB = 22, hpadT = 6;
  const innerW = hW - hpadL - 8;
  const innerH = hH - hpadB - hpadT;
  const bw = innerW / nBins;
  let hsv = `<svg width="${hW}" height="${hH}" class="cp-hist-svg">`;
  for(let k=0;k<nBins;k++){
    const bh = (bins[k]/maxCount)*innerH;
    const bx = hpadL + k*bw;
    const by = hpadT + (innerH - bh);
    const midVal = (binEdges[k]+binEdges[k+1])/2;
    hsv += `<rect x="${bx+1}" y="${by}" width="${bw-2}" height="${bh}" fill="${colorFor(midVal)}" stroke="#666" stroke-width="0.5"><title>${binEdges[k].toFixed(2)}–${binEdges[k+1].toFixed(2)} ms\nn=${bins[k]}</title></rect>`;
    if(bins[k]>0){
      hsv += `<text x="${bx+bw/2}" y="${by-2}" text-anchor="middle" fill="#ddd" font-size="9">${bins[k]}</text>`;
    }
  }
  // axes
  hsv += `<line x1="${hpadL}" y1="${hpadT+innerH}" x2="${hpadL+innerW}" y2="${hpadT+innerH}" stroke="#666" stroke-width="1"/>`;
  hsv += `<text x="${hpadL}" y="${hH-6}" fill="#aaa" font-size="10">${dMin.toFixed(1)}</text>`;
  hsv += `<text x="${hpadL+innerW}" y="${hH-6}" text-anchor="end" fill="#aaa" font-size="10">${dMax.toFixed(1)} ms</text>`;
  hsv += `<text x="${hpadL-4}" y="${hpadT+8}" text-anchor="end" fill="#aaa" font-size="10">${maxCount}</text>`;
  hsv += `<text x="${hpadL-4}" y="${hpadT+innerH}" text-anchor="end" fill="#aaa" font-size="10">0</text>`;
  hsv += `</svg>`;
  hHost.innerHTML = hsv;

  // Stats
  const stats = document.getElementById('cp-stats');
  const fmtMs = v => (v===null||v===undefined||!isFinite(v)) ? 'N/A' : v.toFixed(2)+' ms';
  stats.innerHTML = `
    <div><span>평균:</span><b>${fmtMs(summary.mean_duration_ms)}</b></div>
    <div><span>중앙값:</span><b>${fmtMs(summary.median_duration_ms)}</b></div>
    <div><span>표준편차:</span><b>${fmtMs(summary.std_duration_ms)}</b></div>
    <div><span>유효 위치:</span><b>${summary.n_valid ?? valid.length}</b></div>
  `;

  // Top-5 / Bottom-5
  const sorted = valid.slice().sort((a,b)=>b.pulse_duration_ms - a.pulse_duration_ms);
  const top5 = sorted.slice(0, 5);
  const bot5 = sorted.slice(-5).reverse();

  function rankHTML(list){
    if(list.length === 0) return '<div class="cp-empty">데이터 없음</div>';
    let h = '<table class="cp-rank-tbl"><thead><tr><th>#</th><th>Pos</th><th>지속(ms)</th><th>density</th><th>거동</th></tr></thead><tbody>';
    list.forEach((p, i) => {
      const bc = p.behavior_class || '—';
      h += `<tr><td>${i+1}</td><td>P${p.pos_id}</td><td>${p.pulse_duration_ms.toFixed(2)}</td><td>${(p.contact_density*100).toFixed(1)}%</td><td>${bc}</td></tr>`;
    });
    h += '</tbody></table>';
    return h;
  }
  document.getElementById('cp-top5').innerHTML = rankHTML(top5);
  document.getElementById('cp-bot5').innerHTML = rankHTML(bot5);
}

function _insightRenderTrajectory3D(data){
  const root = document.getElementById('trajectory3d-svg');
  if(!root) return;
  if(!data || !data.bundles || data.bundles.length === 0){
    root.innerHTML = '<div class="insight-empty">트래젝터리 데이터 없음</div>';
    return;
  }

  const bundles = data.bundles;
  const bbox = data.bbox_xy || [-40, -40, 40, 40];
  const zr   = data.z_range || [0, 1];
  const [x0, y0, x1, y1] = bbox;
  const [zMin, zMax] = zr;

  // Isometric projection: u = x + 0.5*y, v = z + 0.5*y
  // (tilt angle 30° — y contributes equally to horizontal and vertical)
  const proj = (x, y, z) => [x + 0.5 * y, z + 0.5 * y];

  // Compute u/v extents across floor corners + trajectory points so the
  // whole scene fits the viewBox.
  const uS = [], vS = [];
  const floorCorners = [
    [x0, y0, zMin], [x1, y0, zMin], [x1, y1, zMin], [x0, y1, zMin]
  ];
  for(const c of floorCorners){
    const [u, v] = proj(c[0], c[1], c[2]);
    uS.push(u); vS.push(v);
  }
  for(const b of bundles){
    for(const p of b.points){
      const [u, v] = proj(p[0], p[1], p[2]);
      uS.push(u); vS.push(v);
    }
  }
  const uMin = Math.min(...uS), uMax = Math.max(...uS);
  const vMin = Math.min(...vS), vMax = Math.max(...vS);

  const W = 600, H = 360, pad = 28;
  const sx = (W - 2*pad) / Math.max(uMax - uMin, 1e-9);
  const sy = (H - 2*pad) / Math.max(vMax - vMin, 1e-9);
  const s  = Math.min(sx, sy);
  // center
  const offU = pad + ((W - 2*pad) - (uMax - uMin) * s) / 2;
  const offV = pad + ((H - 2*pad) - (vMax - vMin) * s) / 2;
  const tx = (u) => offU + (u - uMin) * s;
  // SVG y grows downward; isometric v grows upward → flip
  const ty = (v) => H - offV - (v - vMin) * s;

  while(root.firstChild) root.removeChild(root.firstChild);
  const root_svg = svg('svg', {
    viewBox: '0 0 ' + W + ' ' + H,
    preserveAspectRatio: 'xMidYMid meet',
    width: '100%'
  });

  // Background
  root_svg.appendChild(svg('rect', {
    x: 0, y: 0, width: W, height: H, fill: '#0d1117', rx: 6
  }));

  // 5x5 floor wireframe at z = zMin
  const N = 5;
  const dxF = (x1 - x0) / N;
  const dyF = (y1 - y0) / N;
  const gridStroke = '#2a3447';
  // Lines parallel to x (constant y)
  for(let i = 0; i <= N; i++){
    const yv = y0 + dyF * i;
    const [uA, vA] = proj(x0, yv, zMin);
    const [uB, vB] = proj(x1, yv, zMin);
    root_svg.appendChild(svg('line', {
      x1: tx(uA), y1: ty(vA), x2: tx(uB), y2: ty(vB),
      stroke: gridStroke, 'stroke-width': 0.8, opacity: 0.8
    }));
  }
  // Lines parallel to y (constant x)
  for(let i = 0; i <= N; i++){
    const xv = x0 + dxF * i;
    const [uA, vA] = proj(xv, y0, zMin);
    const [uB, vB] = proj(xv, y1, zMin);
    root_svg.appendChild(svg('line', {
      x1: tx(uA), y1: ty(vA), x2: tx(uB), y2: ty(vB),
      stroke: gridStroke, 'stroke-width': 0.8, opacity: 0.8
    }));
  }

  // Polylines per trajectory
  for(const b of bundles){
    const color = BEHAVIOR_COLOR[b.behavior_class] || BEHAVIOR_COLOR.unknown;
    const pts = b.points.map(p => {
      const [u, v] = proj(p[0], p[1], p[2]);
      return tx(u).toFixed(2) + ',' + ty(v).toFixed(2);
    }).join(' ');
    const line = svg('polyline', {
      points: pts,
      fill: 'none',
      stroke: color,
      'stroke-width': 1.3,
      'stroke-linecap': 'round',
      'stroke-linejoin': 'round',
      opacity: 0.85
    });
    const title = svg('title', {});
    title.appendChild(document.createTextNode(
      'pos ' + b.pos_id + ' · ' + String(b.behavior_class).toUpperCase()
    ));
    line.appendChild(title);
    root_svg.appendChild(line);

    // start marker at first sampled point
    if(b.points.length){
      const [u0p, v0p] = proj(b.points[0][0], b.points[0][1], b.points[0][2]);
      root_svg.appendChild(svg('circle', {
        cx: tx(u0p), cy: ty(v0p), r: 1.8, fill: color, opacity: 0.95
      }));
    }
  }

  // Legend (top-right) — behavior classes present in bundles
  const present = {};
  for(const b of bundles) present[b.behavior_class] = (present[b.behavior_class] || 0) + 1;
  const order = ['bounce', 'rebound', 'slide', 'embed', 'unknown'];
  const items = order.filter(k => present[k]);
  let lx = W - 12, ly = 14;
  const lh = 14;
  for(let i = 0; i < items.length; i++){
    const k = items[i];
    const yy = ly + i * lh;
    root_svg.appendChild(svg('line', {
      x1: lx - 80, y1: yy, x2: lx - 60, y2: yy,
      stroke: BEHAVIOR_COLOR[k] || BEHAVIOR_COLOR.unknown,
      'stroke-width': 2
    }));
    const t = svg('text', {
      x: lx - 56, y: yy + 3,
      fill: '#c9d1d9', 'font-size': 10, 'text-anchor': 'start'
    });
    t.appendChild(document.createTextNode(k + ' (' + present[k] + ')'));
    root_svg.appendChild(t);
  }

  root.appendChild(root_svg);
  svgZoomPan(root_svg);
}
"""
