# 섹션 04 — PER-PART MOTION (부품별 peak G) HTML 템플릿 (기계적 분할, 바이트 불변)

_PAGE4 = """
<section class="page" id="s4">
  <div class="page-head r">
    <span class="num">04</span><span class="tagline">PER-PART MOTION</span>
    <span class="ttl">부품별 가속도 (Per-Part Peak G)</span>
    <span class="sub">RIGID-BODY MOTION &middot; PEAK G &middot; ACC-TIME HISTORY</span>
  </div>

  <div id="ppg-empty" class="r" style="display:none;color:var(--dim);padding:24px 12px;font-size:12px">
    부품별 모션 데이터 없음
  </div>

  <div id="ppg-content">
    <div class="grid g-12" style="margin-top:6px">
      <div class="panel col-7 r">
        <div class="ph">
          <span class="pt">PART PEAK G &middot; BAR CHART</span>
          <span class="pd">peak |acc| per part &middot; sorted descending &middot; impactor highlighted</span>
        </div>
        <svg id="ppg-bar-svg" preserveAspectRatio="xMidYMid meet" style="width:100%;height:340px"></svg>
        <div class="pcap" id="ppg-bar-cap">
          막대 길이 = max|a|<span id="ppg-bar-cap-unit"></span>. 임팩터 파트는 핑크색으로 강조.
        </div>
      </div>

      <div class="panel col-5 r">
        <div class="ph">
          <span class="pt">PEAK G SUMMARY TABLE</span>
          <span class="pd">part &middot; peak G &middot; t_peak &middot; peak vel/disp</span>
        </div>
        <div style="max-height:340px;overflow-y:auto">
          <table class="dt" id="ppg-summary-tbl">
            <thead>
              <tr>
                <th class="tl">PART</th>
                <th class="tl">NAME</th>
                <th>PEAK G<br><span style="font-weight:400;color:var(--dim);text-transform:none" id="ppg-th-acc"></span></th>
                <th>PEAK G<br><span style="font-weight:400;color:var(--dim);text-transform:none">g</span></th>
                <th>t<sub>peak</sub><br><span style="font-weight:400;color:var(--dim);text-transform:none" id="ppg-th-time"></span></th>
                <th>PEAK VEL<br><span style="font-weight:400;color:var(--dim);text-transform:none" id="ppg-th-vel"></span></th>
                <th>PEAK DISP<br><span style="font-weight:400;color:var(--dim);text-transform:none" id="ppg-th-disp"></span></th>
              </tr>
            </thead>
            <tbody></tbody>
          </table>
        </div>
        <div class="pcap">
          g 단위 = peak_g / 9810. 첫 번째 행이 가장 큰 가속도를 받는 부품.
        </div>
      </div>

      <div class="panel col-12 r">
        <div class="ph">
          <span class="pt">ACC MAGNITUDE TIME-SERIES &middot; ALL PARTS</span>
          <span class="pd">|a(t)| per part &middot; auto semi-log when range &gt; 2 decades &middot; dashed line = t<sub>first_contact</sub></span>
        </div>
        <svg id="ppg-line-svg" preserveAspectRatio="none" style="width:100%;height:360px"></svg>
        <div id="ppg-line-legend" style="display:flex;flex-wrap:wrap;gap:6px 12px;margin-top:6px;font-size:10px;color:var(--fg2)"></div>
        <div class="pcap" id="ppg-line-cap">
          한 선 = 한 파트의 가속도 크기 시계열. 회색 점선 세로선 = 임팩터 최초 접촉 시각.
        </div>
      </div>
    </div>
  </div>
</section>
"""


_JS_S4 = r"""function initPerPartPeakG() {
  const pm = DATA.part_motion || { summary: [], series: [], impactor_part_id: null, t_first_contact: null, g_mm_s2: 9810.0 };
  const summary = pm.summary || [];
  const series = pm.series || [];
  const empty = document.getElementById('ppg-empty');
  const content = document.getElementById('ppg-content');
  const hasData = summary.some(r => (r.peak_g || 0) > 0) || series.length > 0;
  if (!hasData) {
    if (empty) empty.style.display = 'block';
    if (content) content.style.display = 'none';
    return;
  }
  if (empty) empty.style.display = 'none';

  const impactorPid = pm.impactor_part_id;
  const G = pm.g_mm_s2 || 9810.0;

  // ----- Bar chart -----
  const barSvg = document.getElementById('ppg-bar-svg');
  if (barSvg) {
    while (barSvg.firstChild) barSvg.removeChild(barSvg.firstChild);
    const sorted = summary.filter(r => (r.peak_g || 0) > 0).slice();
    sorted.sort((a, b) => b.peak_g - a.peak_g);
    const n = sorted.length;
    const W = 720, rowH = 22, padTop = 14, padBot = 24, padL = 180, padR = 60;
    const H = Math.max(80, padTop + padBot + n * rowH);
    barSvg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
    barSvg.style.height = Math.max(120, Math.min(520, H)) + 'px';
    const maxG = sorted.length ? sorted[0].peak_g : 1;
    const plotW = W - padL - padR;
    // axis line
    barSvg.appendChild(svg('line', { x1: padL, y1: padTop, x2: padL, y2: H - padBot, stroke: 'rgba(255,255,255,0.18)', 'stroke-width': 0.8 }));
    barSvg.appendChild(svg('line', { x1: padL, y1: H - padBot, x2: W - padR, y2: H - padBot, stroke: 'rgba(255,255,255,0.18)', 'stroke-width': 0.8 }));
    // ticks (0, 25%, 50%, 75%, 100%)
    for (let i = 0; i <= 4; i++) {
      const xp = padL + (i / 4) * plotW;
      barSvg.appendChild(svg('line', { x1: xp, y1: H - padBot, x2: xp, y2: H - padBot + 4, stroke: 'rgba(255,255,255,0.30)', 'stroke-width': 0.6 }));
      const t = svg('text', { x: xp, y: H - padBot + 14, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 9, 'font-family': 'JetBrains Mono' });
      t.appendChild(document.createTextNode(fmt(maxG * i / 4, 0)));
      barSvg.appendChild(t);
    }
    // axis label
    const axLab = svg('text', { x: padL + plotW / 2, y: H - 4, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 9 });
    axLab.appendChild(document.createTextNode('Peak |a|' + (_u('acc') ? '  (' + _u('acc') + ')' : '')));
    barSvg.appendChild(axLab);
    // rows
    for (let i = 0; i < n; i++) {
      const row = sorted[i];
      const y = padTop + i * rowH + 4;
      const bw = (row.peak_g / maxG) * plotW;
      const isImp = row.is_impactor || (impactorPid != null && row.part_id === impactorPid);
      const color = isImp ? '#ff5e84' : '#4dd6ff';
      // label (part_id + name)
      const lab = svg('text', { x: padL - 6, y: y + 11, 'text-anchor': 'end', fill: isImp ? '#ff9eb9' : '#aab2cf', 'font-size': 10, 'font-family': 'Inter' });
      const labStr = String(row.part_id) + (row.part_name ? '  ' + row.part_name : '');
      const labShort = labStr.length > 26 ? labStr.slice(0, 24) + '…' : labStr;
      lab.appendChild(document.createTextNode(labShort));
      if (isImp) {
        const star = svg('tspan', { fill: '#ff5e84', 'font-weight': 700 });
        star.appendChild(document.createTextNode('  ◆'));
        lab.appendChild(star);
      }
      const ttl = svg('title', {});
      ttl.appendChild(document.createTextNode(labStr + (isImp ? '  (impactor)' : '')));
      lab.appendChild(ttl);
      barSvg.appendChild(lab);
      // bar
      const rect = svg('rect', { x: padL, y: y, width: Math.max(1, bw), height: rowH - 8, fill: color, opacity: 0.85, rx: 2 });
      barSvg.appendChild(rect);
      // value at end of bar
      const vt = svg('text', { x: padL + bw + 4, y: y + 11, fill: '#e6ebff', 'font-size': 9, 'font-family': 'JetBrains Mono' });
      vt.appendChild(document.createTextNode(fmt(row.peak_g, 0) + '  (' + (row.peak_g / G).toFixed(1) + ' g)'));
      barSvg.appendChild(vt);
    }
  }

  // ----- Summary table -----
  const tbody = document.querySelector('#ppg-summary-tbl tbody');
  if (tbody) {
    while (tbody.firstChild) tbody.removeChild(tbody.firstChild);
    for (const r of summary) {
      const isImp = r.is_impactor || (impactorPid != null && r.part_id === impactorPid);
      const tr = el('tr');
      if (isImp) tr.style.color = '#ff9eb9';
      tr.appendChild(el('td', { class: 'tl' }, String(r.part_id) + (isImp ? '  ◆' : '')));
      tr.appendChild(el('td', { class: 'tl' }, r.part_name || ''));
      tr.appendChild(el('td', { class: 'num' }, fmt(r.peak_g, 0)));
      tr.appendChild(el('td', { class: 'num' }, ((r.peak_g || 0) / G).toFixed(2)));
      tr.appendChild(el('td', { class: 'num' }, (r.t_peak_g != null ? (r.t_peak_g * 1000).toFixed(3) : '-')));
      tr.appendChild(el('td', { class: 'num' }, fmt(r.peak_vel, 1)));
      tr.appendChild(el('td', { class: 'num' }, fmt(r.peak_disp, 3)));
      tbody.appendChild(tr);
    }
  }

  // ----- Line chart (acc magnitude over time, one line per part) -----
  const lineSvg = document.getElementById('ppg-line-svg');
  const legend = document.getElementById('ppg-line-legend');
  if (lineSvg && legend) {
    while (lineSvg.firstChild) lineSvg.removeChild(lineSvg.firstChild);
    while (legend.firstChild) legend.removeChild(legend.firstChild);
    if (!series.length) {
      lineSvg.setAttribute('viewBox', '0 0 600 200');
      const t = svg('text', { x: 300, y: 100, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 11 });
      t.appendChild(document.createTextNode('가속도 시계열 데이터 없음'));
      lineSvg.appendChild(t);
    } else {
      const W = 900, H = 360, pad = { l: 70, r: 14, t: 14, b: 30 };
      lineSvg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
      lineSvg.setAttribute('preserveAspectRatio', 'none');
      const plotW = W - pad.l - pad.r, plotH = H - pad.t - pad.b;
      // determine ranges
      let tMin = Infinity, tMax = -Infinity, aMin = Infinity, aMax = -Infinity;
      for (const s of series) {
        for (let i = 0; i < s.t.length; i++) {
          if (s.t[i] < tMin) tMin = s.t[i];
          if (s.t[i] > tMax) tMax = s.t[i];
        }
        for (let i = 0; i < s.a.length; i++) {
          const v = s.a[i];
          if (v > 0 && v < aMin) aMin = v;
          if (v > aMax) aMax = v;
        }
      }
      if (!isFinite(tMin)) { tMin = 0; tMax = 1; }
      if (tMax === tMin) tMax = tMin + 1;
      if (!isFinite(aMax) || aMax <= 0) aMax = 1;
      if (!isFinite(aMin) || aMin <= 0) aMin = aMax * 1e-4;
      // semi-log when range > 2 decades
      const useLog = (aMax / aMin) > 1e2;
      const yLo = useLog ? aMin : 0;
      const yHi = aMax;
      function px(tv) { return pad.l + (tv - tMin) / (tMax - tMin) * plotW; }
      function py(av) {
        if (useLog) {
          const v = Math.max(av, aMin);
          const lv = Math.log10(v);
          const lLo = Math.log10(yLo);
          const lHi = Math.log10(yHi);
          return pad.t + (1 - (lv - lLo) / (lHi - lLo)) * plotH;
        }
        return pad.t + (1 - (av - yLo) / (yHi - yLo)) * plotH;
      }
      // axes
      lineSvg.appendChild(svg('rect', { x: pad.l, y: pad.t, width: plotW, height: plotH, fill: '#0e1320', stroke: 'rgba(255,255,255,0.10)', 'stroke-width': 0.6 }));
      // x ticks (6 ticks, ms)
      for (let i = 0; i <= 6; i++) {
        const tv = tMin + (i / 6) * (tMax - tMin);
        const xp = px(tv);
        lineSvg.appendChild(svg('line', { x1: xp, y1: pad.t + plotH, x2: xp, y2: pad.t + plotH + 4, stroke: 'rgba(255,255,255,0.30)', 'stroke-width': 0.6 }));
        const t = svg('text', { x: xp, y: pad.t + plotH + 16, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 9, 'font-family': 'JetBrains Mono' });
        t.appendChild(document.createTextNode((tv * 1000).toFixed(2)));
        lineSvg.appendChild(t);
      }
      const xLab = svg('text', { x: pad.l + plotW / 2, y: H - 4, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 9 });
      xLab.appendChild(document.createTextNode('t' + (_u('time') ? '  (' + _u('time') + ')' : '')));
      lineSvg.appendChild(xLab);
      // y ticks
      if (useLog) {
        const lLo = Math.ceil(Math.log10(yLo));
        const lHi = Math.floor(Math.log10(yHi));
        for (let p = lLo; p <= lHi; p++) {
          const yv = Math.pow(10, p);
          const yp = py(yv);
          lineSvg.appendChild(svg('line', { x1: pad.l, y1: yp, x2: pad.l + plotW, y2: yp, stroke: 'rgba(255,255,255,0.06)', 'stroke-width': 0.5 }));
          const t = svg('text', { x: pad.l - 6, y: yp + 3, 'text-anchor': 'end', fill: '#5c6383', 'font-size': 9, 'font-family': 'JetBrains Mono' });
          t.appendChild(document.createTextNode('1e' + p));
          lineSvg.appendChild(t);
        }
      } else {
        for (let i = 0; i <= 4; i++) {
          const yv = yLo + (i / 4) * (yHi - yLo);
          const yp = py(yv);
          lineSvg.appendChild(svg('line', { x1: pad.l, y1: yp, x2: pad.l + plotW, y2: yp, stroke: 'rgba(255,255,255,0.06)', 'stroke-width': 0.5 }));
          const t = svg('text', { x: pad.l - 6, y: yp + 3, 'text-anchor': 'end', fill: '#5c6383', 'font-size': 9, 'font-family': 'JetBrains Mono' });
          t.appendChild(document.createTextNode(fmt(yv, 0)));
          lineSvg.appendChild(t);
        }
      }
      const yLab = svg('text', { x: 8, y: pad.t + plotH / 2, fill: '#5c6383', 'font-size': 9, transform: 'rotate(-90 14 ' + (pad.t + plotH / 2) + ')' });
      yLab.appendChild(document.createTextNode('|a|' + (_u('acc') ? '  (' + _u('acc') + ')' : '') + (useLog ? '  [log]' : '')));
      lineSvg.appendChild(yLab);
      // first-contact dashed line
      if (pm.t_first_contact != null && pm.t_first_contact >= tMin && pm.t_first_contact <= tMax) {
        const xc = px(pm.t_first_contact);
        lineSvg.appendChild(svg('line', { x1: xc, y1: pad.t, x2: xc, y2: pad.t + plotH, stroke: 'rgba(180,110,255,0.7)', 'stroke-width': 1.0, 'stroke-dasharray': '4,3' }));
        const t = svg('text', { x: xc + 4, y: pad.t + 10, fill: '#b46eff', 'font-size': 9, 'font-family': 'JetBrains Mono' });
        t.appendChild(document.createTextNode('t₁ = ' + (pm.t_first_contact * 1000).toFixed(2) + (_u('time') ? ' ' + _u('time') : '')));
        lineSvg.appendChild(t);
      }
      // sort series by peak_g desc and assign colors
      const sortedSeries = series.slice().sort((a, b) => (b.peak_g || 0) - (a.peak_g || 0));
      for (let si = 0; si < sortedSeries.length; si++) {
        const s = sortedSeries[si];
        const isImp = (impactorPid != null && s.part_id === impactorPid);
        const color = isImp ? '#ff5e84' : PPG_PALETTE[si % PPG_PALETTE.length];
        const pts = [];
        const N = Math.min(s.t.length, s.a.length);
        for (let i = 0; i < N; i++) {
          const xp = px(s.t[i]);
          const yp = py(s.a[i]);
          pts.push(xp.toFixed(1) + ',' + yp.toFixed(1));
        }
        const poly = svg('polyline', { points: pts.join(' '), fill: 'none', stroke: color, 'stroke-width': isImp ? 1.8 : 1.1, opacity: isImp ? 0.95 : 0.75 });
        const ttl = svg('title', {});
        ttl.appendChild(document.createTextNode(String(s.part_id) + '  ' + (s.part_name || '') + (isImp ? '  (impactor)' : '')));
        poly.appendChild(ttl);
        lineSvg.appendChild(poly);
        // legend
        const item = el('div', { style: { display: 'flex', alignItems: 'center', gap: '4px' } });
        item.appendChild(el('span', { style: { display: 'inline-block', width: '14px', height: '3px', background: color, borderRadius: '2px' } }));
        item.appendChild(el('span', null, String(s.part_id) + '  ' + (s.part_name || '') + (isImp ? '  ◆' : '')));
        if (isImp) item.style.color = '#ff9eb9';
        legend.appendChild(item);
      }
    }
  }
}

"""
