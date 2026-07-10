# 섹션 06 — DEEP ANALYTICS HTML 템플릿 (기계적 분할, 바이트 불변)

_PAGE6 = """
<section id="s6">
  <div class="page-head">
    <span class="num">06</span>
    <span class="t">DEEP ANALYTICS</span>
    <span class="sub">충격 응답의 깊은 분석 · 주파수 도메인 · 모달 분해 · 드릴다운</span>
    <span class="sub">DEEP-DIVE: FFT / SRS / SAFE ZONE / PCA / ANOMALY / PER-PART</span>
  </div>

  <div class="panel" style="background:transparent;border:none;padding:0;">
    <div id="deep-fft-panel" class="panel">
  <div class="panel-header">
    <h3>주파수 도메인 — FFT 스펙트럼</h3>
    <div class="deep-fft-meta"></div>
  </div>
  <div class="panel-body">
    <div class="deep-fft-body"></div>
  </div>
</div>

<section class="panel deep-srs-panel" id="deep-srs-panel">
  <h3>충격 응답 스펙트럼 — SRS</h3>
  <div id="deep-srs-body" class="srs-body"></div>
</section>
<div class="panel" id="deep-safe-drop-zone-panel">
  <div class="panel-header">
    <h3>안전 낙하 구역 지도</h3>
    <div class="panel-sub">충격 위치별 안전/위험 분류 — 볼록껍질로 회피 구역 시각화</div>
  </div>
  <div class="panel-body" id="deep-safe-drop-zone-body"></div>
</div>

<section class="panel deep-panel" id="deep-pca-modal-panel">
  <header class="panel-head">
    <h3>PCA 모달 분해</h3>
    <p class="panel-sub">25 위치 × 25 부품 peak_g 행렬의 상위 3개 주성분 — 부품 loadings + 위치 score 맵.</p>
  </header>
  <div class="panel-body" id="deep-pca-modal-body"></div>
</section>

<section class="panel" id="deep-anomaly-panel">
  <h3>이상치 위치 자동 검출</h3>
  <div class="ppd-caption">FINDINGS 의 통계 outlier 게이트와 동일 기준 (robust z = median/MAD) — 두 화면의 수치는 상호 검증 가능.</div>
  <div id="deep-anomaly-detection" class="deep-anomaly-detection"></div>
</section>
<div class="panel" id="ppd-host">
  <h3 style="margin:0 0 6px 0;">부품별 통합 상세 보기 — Drill-Down</h3>
  <div class="ppd-caption">한 부품에 대한 모든 위치 응답을 한 화면으로. 좌측에서 부품 선택.</div>
  <div class="ppd-layout">
    <div class="ppd-left">
      <div class="ppd-left-head">부품 (Peak G 기준 내림차순)</div>
      <div id="ppd-part-list" class="ppd-list"></div>
    </div>
    <div class="ppd-right">
      <div id="ppd-detail-title" class="ppd-detail-title">활성 부품 로딩 중…</div>
      <div id="ppd-kpi-strip" class="ppd-kpi-strip"></div>
      <div class="ppd-grid2">
        <div class="ppd-tile">
          <div class="ppd-tile-head">위치별 Peak G 히트맵 (★ = 최대)</div>
          <svg id="ppd-heatmap-svg" class="ppd-svg-square"></svg>
        </div>
        <div class="ppd-tile">
          <div class="ppd-tile-head">Peak G 분포 (10-bin 히스토그램)</div>
          <svg id="ppd-hist-svg" class="ppd-svg-wide"></svg>
        </div>
      </div>
      <div class="ppd-tile" style="margin-top:8px;">
        <div class="ppd-tile-head">항복/재료 카드</div>
        <svg id="ppd-yield-svg" class="ppd-svg-wide"></svg>
      </div>
    </div>
  </div>
</div>

<!-- DEEP_PANELS_INSERT_HERE -->
    <!-- Workflow-added panel templates are inserted ABOVE this marker. -->
  </div>
</section>
"""


_JS_S6 = r"""function _deepRenderFFT(data){
  const root = document.getElementById('deep-fft-panel');
  if (!root) return;
  const body = root.querySelector('.deep-fft-body');
  const meta = root.querySelector('.deep-fft-meta');
  if (!body) return;
  body.innerHTML = '';
  if (meta) meta.innerHTML = '';

  const payload = (data && data.fft) || {};
  const perPart = payload.per_part_dominant_freq || {};
  const summary = payload.summary || {};
  const entries = Object.entries(perPart);

  if (!entries.length){
    body.appendChild(el('div', {class:'deep-empty'}, ['데이터 없음 — 분석 가능한 가속도 신호가 없습니다.']));
    return;
  }

  // header meta
  if (meta){
    const band = summary.freq_band_Hz || [0,0];
    meta.appendChild(el('span', {class:'deep-fft-pill'},
      [`fs ≈ ${fmt(summary.fs_Hz||0,1)} Hz`]));
    meta.appendChild(el('span', {class:'deep-fft-pill'},
      [`대역: ${fmt(band[0]||0,1)} – ${fmt(band[1]||0,1)} Hz`]));
    meta.appendChild(el('span', {class:'deep-fft-pill'},
      [`파트 ${summary.n_parts_with_data||0}개 / 위치샘플 ${summary.n_positions_used||0}개`]));
  }

  // Top-12 by mean_f_dom_Hz (descending)
  entries.sort((a,b)=> (b[1].mean_f_dom_Hz||0) - (a[1].mean_f_dom_Hz||0));
  const top = entries.slice(0, 12);

  const W = 192, H = 40, PAD_L = 2, PAD_R = 2, PAD_T = 2, PAD_B = 2;

  top.forEach(([pid, info]) => {
    const spec = info.spectrum || {f:[], amp_normalized:[]};
    const fs = spec.f || [];
    const as = spec.amp_normalized || [];

    const card = el('div', {class:'deep-fft-card'});

    // header line
    const head = el('div', {class:'deep-fft-card-head'}, [
      el('span', {class:'deep-fft-name', title:info.name||('Part '+pid)},
         [info.name || ('Part '+pid)]),
      el('span', {class:'deep-fft-pid'}, ['#'+pid])
    ]);
    card.appendChild(head);

    // svg spectrum
    const s = svg('svg', {width:W, height:H, viewBox:`0 0 ${W} ${H}`, class:'deep-fft-svg'});
    // background
    s.appendChild(svg('rect', {x:0,y:0,width:W,height:H,fill:'#0f1115',stroke:'#23262d'}));

    if (fs.length >= 2 && as.length >= 2){
      const fmin = fs[0], fmax = fs[fs.length-1];
      const span = (fmax - fmin) || 1;
      const innerW = W - PAD_L - PAD_R;
      const innerH = H - PAD_T - PAD_B;
      let d = '';
      for (let i=0; i<fs.length; i++){
        const x = PAD_L + ( (fs[i]-fmin) / span ) * innerW;
        const a = Math.max(0, Math.min(1, as[i]||0));
        const y = PAD_T + (1 - a) * innerH;
        d += (i===0 ? 'M' : 'L') + x.toFixed(1) + ',' + y.toFixed(1) + ' ';
      }
      s.appendChild(svg('path', {d:d, fill:'none', stroke:'#7ad7ff', 'stroke-width':1.2}));

      // mark dominant frequency
      const fdom = info.top_freq_Hz;
      if (isFinite(fdom)){
        const xd = PAD_L + ( (fdom - fmin) / span ) * innerW;
        s.appendChild(svg('line', {x1:xd, y1:PAD_T, x2:xd, y2:H-PAD_B,
          stroke:'#ffb347', 'stroke-width':1, 'stroke-dasharray':'2,2'}));
      }
    } else {
      s.appendChild(svg('text', {x:W/2, y:H/2, fill:'#888', 'font-size':9,
        'text-anchor':'middle', 'dominant-baseline':'middle'}, ['스펙트럼 없음']));
    }
    card.appendChild(s);

    // text line
    const fdom = info.mean_f_dom_Hz, fstd = info.std_f_dom_Hz, n = info.n_samples_used;
    const txt = el('div', {class:'deep-fft-text'}, [
      el('span', {class:'deep-fft-fdom'},
         [`f_dom = ${fmt(fdom,1)} ± ${fmt(fstd,1)} Hz`]),
      el('span', {class:'deep-fft-n'}, [`n=${n}`])
    ]);
    card.appendChild(txt);

    body.appendChild(card);
  });
}

function _deepRenderSRS(data) {
  const host = document.getElementById('deep-srs-body');
  if (!host) return;
  host.innerHTML = '';

  const pay = (data && data.deep_analytics && data.deep_analytics.srs) || null;
  if (!pay || !pay.available || !pay.srs_curves || !pay.srs_curves.length) {
    host.appendChild(el('div', {class: 'empty-note'}, ['가속도 데이터 없음 — SRS 계산 불가']));
    return;
  }

  const curves = pay.srs_curves;
  const accUnit = (typeof _u === 'function') ? _u('acc') : '';

  // Layout
  const W = 720, H = 360;
  const ML = 64, MR = 160, MT = 16, MB = 44;
  const PW = W - ML - MR, PH = H - MT - MB;

  // Domain
  let fMin = Infinity, fMax = -Infinity, sMin = Infinity, sMax = -Infinity;
  curves.forEach(c => {
    c.f.forEach(v => { if (v > 0 && isFinite(v)) { if (v < fMin) fMin = v; if (v > fMax) fMax = v; } });
    c.srs.forEach(v => { if (v > 0 && isFinite(v)) { if (v < sMin) sMin = v; if (v > sMax) sMax = v; } });
  });
  if (!isFinite(fMin) || !isFinite(sMin) || sMax <= 0) {
    host.appendChild(el('div', {class: 'empty-note'}, ['SRS 값이 모두 0 — 표시할 데이터 없음']));
    return;
  }
  // pad
  const lfMin = Math.log10(fMin), lfMax = Math.log10(fMax);
  const lsMin = Math.log10(Math.max(sMin, sMax * 1e-4));
  const lsMax = Math.log10(sMax * 1.15);

  const xToPx = lf => ML + (lf - lfMin) / (lfMax - lfMin || 1) * PW;
  const yToPx = ls => MT + PH - (ls - lsMin) / (lsMax - lsMin || 1) * PH;

  const svgEl = svg('svg', {viewBox: `0 0 ${W} ${H}`, width: '100%', height: H, class: 'srs-chart'});

  // axes background
  svgEl.appendChild(svg('rect', {x: ML, y: MT, width: PW, height: PH, fill: '#0e131b', stroke: '#2a3340'}));

  // X gridlines (decades + 1/3 octave centers)
  const xTicks = [];
  for (let d = Math.floor(lfMin); d <= Math.ceil(lfMax); d++) {
    for (let m = 1; m < 10; m++) {
      const v = m * Math.pow(10, d);
      if (v < fMin * 0.99 || v > fMax * 1.01) continue;
      xTicks.push({v: v, major: (m === 1)});
    }
  }
  xTicks.forEach(t => {
    const x = xToPx(Math.log10(t.v));
    svgEl.appendChild(svg('line', {x1: x, y1: MT, x2: x, y2: MT + PH,
      stroke: t.major ? '#2f3a4a' : '#1d2530', 'stroke-width': t.major ? 1 : 0.5}));
    if (t.major) {
      svgEl.appendChild(svg('text', {x: x, y: MT + PH + 14, 'text-anchor': 'middle',
        fill: '#9aa7b8', 'font-size': 10}, [String(t.v) + ' Hz']));
    }
  });

  // Y gridlines (decades)
  const yTicks = [];
  for (let d = Math.floor(lsMin); d <= Math.ceil(lsMax); d++) {
    for (let m = 1; m < 10; m++) {
      const v = m * Math.pow(10, d);
      const lv = Math.log10(v);
      if (lv < lsMin - 1e-9 || lv > lsMax + 1e-9) continue;
      yTicks.push({v: v, lv: lv, major: (m === 1)});
    }
  }
  yTicks.forEach(t => {
    const y = yToPx(t.lv);
    svgEl.appendChild(svg('line', {x1: ML, y1: y, x2: ML + PW, y2: y,
      stroke: t.major ? '#2f3a4a' : '#1d2530', 'stroke-width': t.major ? 1 : 0.5}));
    if (t.major) {
      const lbl = (t.v >= 1000) ? (t.v / 1000).toFixed(0) + 'k' : t.v.toFixed(0);
      svgEl.appendChild(svg('text', {x: ML - 6, y: y + 3, 'text-anchor': 'end',
        fill: '#9aa7b8', 'font-size': 10}, [lbl]));
    }
  });

  // axis labels
  svgEl.appendChild(svg('text', {x: ML + PW / 2, y: H - 8, 'text-anchor': 'middle',
    fill: '#cfd6e0', 'font-size': 11}, ['주파수 (Hz)']));
  svgEl.appendChild(svg('text', {x: 14, y: MT + PH / 2,
    transform: `rotate(-90 14 ${MT + PH / 2})`,
    'text-anchor': 'middle', fill: '#cfd6e0', 'font-size': 11}, [`최대 절대 가속도 응답 (${accUnit})`]));

  // colors for up to 3 curves
  const palette = ['#f0c419', '#5dade2', '#e74c3c'];

  curves.forEach((c, idx) => {
    const color = palette[idx % palette.length];
    let d = '';
    for (let i = 0; i < c.f.length; i++) {
      const fv = c.f[i], sv = c.srs[i];
      if (!(fv > 0) || !(sv > 0) || !isFinite(fv) || !isFinite(sv)) continue;
      const x = xToPx(Math.log10(fv));
      const y = yToPx(Math.log10(sv));
      d += (d ? ' L ' : 'M ') + x.toFixed(1) + ' ' + y.toFixed(1);
    }
    if (d) {
      svgEl.appendChild(svg('path', {d: d, fill: 'none', stroke: color, 'stroke-width': 2}));
    }
    // markers
    for (let i = 0; i < c.f.length; i++) {
      const fv = c.f[i], sv = c.srs[i];
      if (!(fv > 0) || !(sv > 0)) continue;
      svgEl.appendChild(svg('circle', {cx: xToPx(Math.log10(fv)), cy: yToPx(Math.log10(sv)),
        r: 2.2, fill: color, stroke: 'none'}));
    }
  });

  // Legend
  const lgX = ML + PW + 16;
  let lgY = MT + 6;
  svgEl.appendChild(svg('text', {x: lgX, y: lgY, fill: '#cfd6e0', 'font-size': 11,
    'font-weight': 'bold'}, [`pos #${pay.summary.pos_id} TOP-3`]));
  lgY += 16;
  curves.forEach((c, idx) => {
    const color = palette[idx % palette.length];
    svgEl.appendChild(svg('rect', {x: lgX, y: lgY - 8, width: 12, height: 3, fill: color}));
    const peak = Math.max.apply(null, c.srs.filter(v => isFinite(v) && v > 0));
    const lbl = `${c.part_name} (peak ${(typeof fmt === 'function') ? fmt(peak, 0) : peak.toFixed(0)} ${accUnit})`;
    svgEl.appendChild(svg('text', {x: lgX + 18, y: lgY - 3, fill: '#cfd6e0', 'font-size': 10}, [lbl]));
    lgY += 16;
  });

  // Summary line
  const sum = pay.summary || {};
  const meta = el('div', {class: 'srs-meta'}, [
    `ζ = ${(sum.damping_ratio != null ? (sum.damping_ratio * 100).toFixed(1) : '5.0')}% · ` +
    `${sum.n_frequencies || curves[0].f.length} 주파수 · ` +
    `샘플링 ≈ ${sum.fs_Hz ? sum.fs_Hz.toFixed(0) : '—'} Hz · ` +
    `대역 ${(sum.f_range_Hz && sum.f_range_Hz[0]) || 5}–${(sum.f_range_Hz && sum.f_range_Hz[1]) || 5000} Hz`
  ]);

  const cap = el('div', {class: 'srs-caption'},
    ['SDOF 응답 (ζ=5%). 가로 = 1/3 옥타브 주파수, 세로 = 최대 절대 가속도 응답.']);

  host.appendChild(svgEl);
  host.appendChild(meta);
  host.appendChild(cap);
}
function _deepRenderSafeDropZone(data) {
  const root = document.getElementById("deep-safe-drop-zone-body");
  if (!root) return;
  root.innerHTML = "";

  const dz = (data && data.deep_analytics && data.deep_analytics.safe_drop_zone) || null;
  if (!dz || dz.empty || !dz.positions || dz.positions.length === 0) {
    root.appendChild(el("div", { class: "muted", style: "padding:16px;" }, ["데이터 없음"]));
    return;
  }

  const positions = dz.positions;
  const polygon = dz.critical_polygon || [];
  const thr = dz.thresholds_used || {};
  const accU = (typeof _u === "function") ? _u("acc") : "";
  const stressU = (typeof _u === "function") ? _u("stress") : "";
  const dispU = (typeof _u === "function") ? _u("disp") : "m";

  // Compute coordinate extent
  let xmin = Infinity, xmax = -Infinity, ymin = Infinity, ymax = -Infinity;
  positions.forEach(p => {
    if (p.x < xmin) xmin = p.x;
    if (p.x > xmax) xmax = p.x;
    if (p.y < ymin) ymin = p.y;
    if (p.y > ymax) ymax = p.y;
  });
  if (!isFinite(xmin) || !isFinite(xmax) || xmin === xmax) { xmin -= 0.5; xmax += 0.5; }
  if (!isFinite(ymin) || !isFinite(ymax) || ymin === ymax) { ymin -= 0.5; ymax += 0.5; }

  // Layout: heatmap (left) + KPIs (right)
  const wrap = el("div", { style: "display:flex; gap:18px; padding:12px; flex-wrap:wrap;" });

  // ---- SVG heatmap ----
  const _dgZ = (typeof DATA !== 'undefined' && DATA.device_geometry) || {aspect: 1};
  const _arZ = (_dgZ.aspect && isFinite(_dgZ.aspect) && _dgZ.aspect > 0) ? _dgZ.aspect : 1;
  const W = 460, H = Math.max(160, Math.round(W / _arZ)), PAD = 36;
  const innerW = W - 2 * PAD, innerH = H - 2 * PAD;
  const xRange = xmax - xmin || 1;
  const yRange = ymax - ymin || 1;
  // Distinct x/y values for cell sizing
  const xs = Array.from(new Set(positions.map(p => p.x))).sort((a, b) => a - b);
  const ys = Array.from(new Set(positions.map(p => p.y))).sort((a, b) => a - b);
  let cellW = innerW / Math.max(1, xs.length);
  let cellH = innerH / Math.max(1, ys.length);

  const sx = x => PAD + ((x - xmin) / xRange) * innerW;
  const sy = y => PAD + innerH - ((y - ymin) / yRange) * innerH;

  const svgRoot = svg("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}`, style: "background:#0c1116; border-radius:8px;" });

  // Background grid
  svgRoot.appendChild(svg("rect", { x: PAD, y: PAD, width: innerW, height: innerH, fill: "#10161d", stroke: "#1f2933", "stroke-width": 1 }));

  // Cells
  const SAFE_COLOR = "#1f8a4c";
  const RISK_COLOR = "#c83232";
  positions.forEach(p => {
    const cx = sx(p.x), cy = sy(p.y);
    const rx = cx - cellW / 2, ry = cy - cellH / 2;
    const fill = p.safe ? SAFE_COLOR : RISK_COLOR;
    svgRoot.appendChild(svg("rect", {
      x: rx, y: ry, width: cellW - 2, height: cellH - 2,
      fill: fill, "fill-opacity": p.safe ? 0.55 : 0.7,
      stroke: "#0c1116", "stroke-width": 1, rx: 3
    }));
    // Worst-metric label
    let label = "OK";
    if (!p.safe) {
      if (p.worst_metric === "peak_g") label = "g";
      else if (p.worst_metric === "peak_stress") label = "σ";
      else if (p.worst_metric === "peak_disp") label = "d";
      else label = "!";
    }
    const txt = svg("text", {
      x: cx, y: cy + 4,
      "text-anchor": "middle",
      "font-size": 13, "font-weight": 700,
      fill: "#f4f6f8"
    });
    txt.textContent = label;
    svgRoot.appendChild(txt);

    // Tooltip
    const ttParts = [
      `pos_id=${p.pos_id}`,
      `face=${p.face}`,
      `safe=${p.safe ? "예" : "아니오"}`
    ];
    if (!p.safe) {
      let metricLabel = p.worst_metric || "";
      let unit = "";
      let val = p.worst_value;
      if (p.worst_metric === "peak_g") { unit = accU; }
      else if (p.worst_metric === "peak_stress") { unit = stressU; }
      else if (p.worst_metric === "peak_disp") { unit = dispU; }
      ttParts.push(`worst=${metricLabel} (${fmt(val, 3)} ${unit})`);
      if (p.worst_part_id !== null && p.worst_part_id !== undefined) {
        ttParts.push(`part_id=${p.worst_part_id}`);
      }
    }
    const titleEl = svg("title", {});
    titleEl.textContent = ttParts.join(" | ");
    txt.appendChild(titleEl);
  });

  // Critical polygon overlay
  if (polygon && polygon.length >= 3) {
    const ptsStr = polygon.map(([x, y]) => `${sx(x).toFixed(2)},${sy(y).toFixed(2)}`).join(" ");
    svgRoot.appendChild(svg("polygon", {
      points: ptsStr,
      fill: "#ff3030", "fill-opacity": 0.22,
      stroke: "#ff5050", "stroke-width": 2,
      "stroke-dasharray": "6,4"
    }));
    // Centroid for label
    let cxSum = 0, cySum = 0;
    polygon.forEach(([x, y]) => { cxSum += sx(x); cySum += sy(y); });
    const cxC = cxSum / polygon.length;
    const cyC = cySum / polygon.length;
    const lblBg = svg("rect", { x: cxC - 38, y: cyC - 12, width: 76, height: 22, rx: 4, fill: "#1a0a0a", "fill-opacity": 0.85, stroke: "#ff5050", "stroke-width": 1 });
    svgRoot.appendChild(lblBg);
    const lbl = svg("text", { x: cxC, y: cyC + 4, "text-anchor": "middle", "font-size": 12, "font-weight": 700, fill: "#ff8080" });
    lbl.textContent = "주의 구역";
    svgRoot.appendChild(lbl);
  }

  // Axis labels
  const xLbl = svg("text", { x: W / 2, y: H - 6, "text-anchor": "middle", "font-size": 11, fill: "#8a96a3" });
  xLbl.textContent = "X 위치";
  svgRoot.appendChild(xLbl);
  const yLbl = svg("text", { x: 12, y: H / 2, "text-anchor": "middle", "font-size": 11, fill: "#8a96a3", transform: `rotate(-90 12 ${H / 2})` });
  yLbl.textContent = "Y 위치";
  svgRoot.appendChild(yLbl);

  wrap.appendChild(svgRoot);

  // ---- KPI + thresholds + legend ----
  const side = el("div", { style: "flex:1; min-width:240px; display:flex; flex-direction:column; gap:12px;" });

  const total = (dz.safe_count || 0) + (dz.at_risk_count || 0);
  const safePct = total > 0 ? (100 * dz.safe_count / total) : 0;
  const riskPct = total > 0 ? (100 * dz.at_risk_count / total) : 0;

  const kpiSafe = el("div", { class: "kpi-box", style: "background:#0f2418; border-left:4px solid #1f8a4c; padding:12px 14px; border-radius:6px;" }, [
    el("div", { style: "font-size:11px; color:#8a96a3; letter-spacing:0.5px;" }, ["안전 위치"]),
    el("div", { style: "font-size:26px; font-weight:700; color:#5fd187; margin-top:4px;" }, [`${dz.safe_count} / ${total}`]),
    el("div", { style: "font-size:11px; color:#8a96a3; margin-top:2px;" }, [`${fmt(safePct, 1)}%`]),
  ]);
  const kpiRisk = el("div", { class: "kpi-box", style: "background:#241010; border-left:4px solid #c83232; padding:12px 14px; border-radius:6px;" }, [
    el("div", { style: "font-size:11px; color:#8a96a3; letter-spacing:0.5px;" }, ["위험 위치"]),
    el("div", { style: "font-size:26px; font-weight:700; color:#ff7878; margin-top:4px;" }, [`${dz.at_risk_count} / ${total}`]),
    el("div", { style: "font-size:11px; color:#8a96a3; margin-top:2px;" }, [`${fmt(riskPct, 1)}%`]),
  ]);
  side.appendChild(kpiSafe);
  side.appendChild(kpiRisk);

  // Thresholds box
  const thrBox = el("div", { style: "background:#10161d; padding:10px 12px; border-radius:6px; border:1px solid #1f2933;" }, [
    el("div", { style: "font-size:11px; color:#8a96a3; margin-bottom:6px; letter-spacing:0.5px;" }, ["임계값 (데이터 기반)"]),
    el("div", { style: "font-size:12px; color:#d0d6dd; line-height:1.7;" }, [
      el("div", {}, [`peak_g ≤ ${fmt(thr.peak_g_thresh || 0, 3)} ${accU} (평균)`]),
      el("div", {}, [`peak_stress ≤ ${fmt(thr.peak_stress_thresh || 0, 3)} ${stressU} (P75)`]),
      el("div", {}, [`peak_disp ≤ ${fmt(thr.peak_disp_thresh || 0, 4)} ${dispU} (P75)`]),
    ]),
  ]);
  side.appendChild(thrBox);

  // Legend
  const legend = el("div", { style: "background:#10161d; padding:10px 12px; border-radius:6px; border:1px solid #1f2933;" }, [
    el("div", { style: "font-size:11px; color:#8a96a3; margin-bottom:6px; letter-spacing:0.5px;" }, ["범례"]),
    el("div", { style: "display:flex; align-items:center; gap:8px; margin-bottom:4px; font-size:12px; color:#d0d6dd;" }, [
      el("span", { style: "display:inline-block; width:14px; height:14px; background:#1f8a4c; border-radius:3px;" }, []),
      el("span", {}, ["안전 (OK)"]),
    ]),
    el("div", { style: "display:flex; align-items:center; gap:8px; margin-bottom:4px; font-size:12px; color:#d0d6dd;" }, [
      el("span", { style: "display:inline-block; width:14px; height:14px; background:#c83232; border-radius:3px;" }, []),
      el("span", {}, ["위험 (g/σ/d = 위반 지표)"]),
    ]),
    el("div", { style: "display:flex; align-items:center; gap:8px; font-size:12px; color:#d0d6dd;" }, [
      el("span", { style: "display:inline-block; width:14px; height:10px; background:rgba(255,48,48,0.22); border:1.5px dashed #ff5050;" }, []),
      el("span", {}, ["주의 구역 (위험 볼록껍질)"]),
    ]),
  ]);
  side.appendChild(legend);

  wrap.appendChild(side);
  root.appendChild(wrap);

  // Caption
  const caption = el("div", { style: "padding:10px 14px 14px; font-size:12px; color:#8a96a3; line-height:1.6;" }, [
    "전 부품 안전 = peak_g/stress/disp 모두 기준 이하. 빨간 영역 = 권장 회피 구역."
  ]);
  root.appendChild(caption);
  svgZoomPan(svgRoot);
}

function _deepRenderPCAModal(data){
  const host = document.getElementById('deep-pca-modal-body');
  if (!host) return;
  host.innerHTML = '';
  const payload = (data && data.pca_modal) || {available:false};

  if (!payload.available){
    const reason = payload.reason ? ` (${payload.reason})` : '';
    host.appendChild(el('div', {class:'empty-note'},
      [`데이터 부족 — PCA 모달 분해를 계산할 수 없습니다${reason}.`]));
    return;
  }

  const modes = payload.modes || [];
  if (!modes.length){
    host.appendChild(el('div', {class:'empty-note'}, ['주성분이 없습니다.']));
    return;
  }

  // header summary
  const cumPct = (payload.cumulative_var_ratio * 100).toFixed(1);
  host.appendChild(el('div', {class:'pca-summary'}, [
    el('span', {}, [`행렬: ${payload.n_positions} 위치 × ${payload.n_parts} 부품`]),
    el('span', {class:'sep'}, [' · ']),
    el('span', {}, [`상위 ${modes.length}개 모드 누적 분산: ${cumPct}%`]),
  ]));

  // shared range for loadings (per mode-row we still use mode-local max for bar normalization)
  // shared range for spatial scores (across all modes) for consistent color scale
  let scoreAbsMax = 0;
  modes.forEach(m => (m.position_scores || []).forEach(p => {
    const a = Math.abs(p.score || 0); if (a > scoreAbsMax) scoreAbsMax = a;
  }));
  if (scoreAbsMax <= 0) scoreAbsMax = 1;

  modes.forEach(mode => {
    const row = el('div', {class:'pca-mode-row'});

    // ----- mode header
    const evPct = (mode.explained_var_ratio * 100).toFixed(2);
    const headerWrap = el('div', {class:'pca-mode-head'}, [
      el('div', {class:'pca-mode-title'}, [`모드 ${mode.mode_index}`]),
      el('div', {class:'pca-mode-evr'}, [`설명 분산 ${evPct}%`]),
      el('div', {class:'pca-mode-bar-track'}, [
        el('div', {class:'pca-mode-bar-fill',
                   style:`width:${Math.max(0, Math.min(100, mode.explained_var_ratio*100)).toFixed(2)}%;`})
      ]),
    ]);
    row.appendChild(headerWrap);

    const body = el('div', {class:'pca-mode-body'});

    // ----- LEFT: part loadings (horizontal bars, +/- colored)
    const left = el('div', {class:'pca-loadings'}, [
      el('div', {class:'pca-sub-title'}, ['상위 부품 loadings (top-10)'])
    ]);
    const loadings = mode.part_loadings || [];
    if (!loadings.length){
      left.appendChild(el('div', {class:'empty-note small'}, ['부품 loading 없음']));
    } else {
      let lmax = 0;
      loadings.forEach(L => { const a = Math.abs(L.loading||0); if (a>lmax) lmax = a; });
      if (lmax <= 0) lmax = 1;

      const list = el('div', {class:'pca-loading-list'});
      loadings.forEach(L => {
        const v = +L.loading || 0;
        const pct = Math.abs(v) / lmax * 50; // half-width bar
        const isPos = v >= 0;
        const colorCls = isPos ? 'pos' : 'neg';
        const item = el('div', {class:'pca-load-item'}, [
          el('div', {class:'pca-load-label', title: L.part_name},
             [`${L.part_id} · ${L.part_name}`]),
          el('div', {class:'pca-load-bar-wrap'}, [
            el('div', {class:'pca-load-axis'}),
            el('div', {class:`pca-load-bar ${colorCls}`,
              style: isPos
                ? `left:50%; width:${pct.toFixed(2)}%;`
                : `right:50%; width:${pct.toFixed(2)}%;`}),
          ]),
          el('div', {class:`pca-load-val ${colorCls}`}, [fmt(v, 3)]),
        ]);
        list.appendChild(item);
      });
      left.appendChild(list);
    }
    body.appendChild(left);

    // ----- RIGHT: 5x5 spatial score map
    const right = el('div', {class:'pca-spatial'}, [
      el('div', {class:'pca-sub-title'}, ['위치 score 맵 (5×5)'])
    ]);
    const pscores = mode.position_scores || [];
    if (!pscores.length){
      right.appendChild(el('div', {class:'empty-note small'}, ['위치 score 없음']));
    } else {
      // Build a 5x5 grid by sorting positions; use (x,y) if all available, else index reshape.
      const hasXY = pscores.every(p => (p.x != null && p.y != null && isFinite(p.x) && isFinite(p.y)));
      let cells = []; // {row,col,score,pos_id}
      const N = pscores.length;
      const dim = Math.max(2, Math.round(Math.sqrt(N)));

      if (hasXY){
        // bin by unique sorted x/y
        const xs = Array.from(new Set(pscores.map(p=>+p.x))).sort((a,b)=>a-b);
        const ys = Array.from(new Set(pscores.map(p=>+p.y))).sort((a,b)=>b-a); // top→bottom
        pscores.forEach(p => {
          const cx = xs.indexOf(+p.x);
          const cy = ys.indexOf(+p.y);
          cells.push({row:cy, col:cx, score:+p.score, pos_id:p.pos_id});
        });
      } else {
        // fall back: sort by pos_id and reshape
        const sorted = pscores.slice().sort((a,b)=> (a.pos_id||0) - (b.pos_id||0));
        sorted.forEach((p, idx) => {
          cells.push({row: Math.floor(idx/dim), col: idx % dim, score:+p.score, pos_id:p.pos_id});
        });
      }

      const nRows = (cells.reduce((mx,c)=>Math.max(mx,c.row),0) + 1) || dim;
      const nCols = (cells.reduce((mx,c)=>Math.max(mx,c.col),0) + 1) || dim;

      const _dgP = (typeof DATA !== 'undefined' && DATA.device_geometry) || {aspect: 1};
      const _arP = (_dgP.aspect && isFinite(_dgP.aspect) && _dgP.aspect > 0) ? _dgP.aspect : 1;
      const W = 220, H = Math.max(80, Math.round(W / _arP)), pad = 8;
      const cw = (W - pad*2) / nCols;
      const ch = (H - pad*2) / nRows;
      const svgEl = svg('svg', {class:'pca-grid', width:W, height:H,
                                viewBox:`0 0 ${W} ${H}`});

      cells.forEach(c => {
        const t = Math.max(-1, Math.min(1, c.score / scoreAbsMax));
        const fill = _pcaDivergingColor(t);
        const x = pad + c.col * cw;
        const y = pad + c.row * ch;
        svgEl.appendChild(svg('rect', {
          x: x.toFixed(2), y: y.toFixed(2),
          width: (cw-1).toFixed(2), height: (ch-1).toFixed(2),
          fill, stroke:'#1b2530', 'stroke-width':'0.5',
          'data-pos': c.pos_id,
        }, [svg('title', {}, [`pos ${c.pos_id} · score ${fmt(c.score,3)}`])]));
        // label score
        const lbl = Math.abs(c.score) >= 0.01 ? fmt(c.score,2) : '~0';
        svgEl.appendChild(svg('text', {
          x:(x + cw/2).toFixed(2), y:(y + ch/2 + 3).toFixed(2),
          'text-anchor':'middle',
          'font-size': Math.max(8, Math.min(11, cw*0.18)).toFixed(1),
          fill: Math.abs(t) > 0.55 ? '#fff' : '#0c0f14',
        }, [lbl]));
      });
      right.appendChild(svgEl);
      svgZoomPan(svgEl);

      // legend
      const legend = el('div', {class:'pca-legend'}, [
        el('span', {class:'pca-legend-min'}, [`${fmt(-scoreAbsMax,2)}`]),
        el('div', {class:'pca-legend-bar'}),
        el('span', {class:'pca-legend-max'}, [`+${fmt(scoreAbsMax,2)}`]),
      ]);
      right.appendChild(legend);
    }
    body.appendChild(right);

    row.appendChild(body);
    host.appendChild(row);
  });

  host.appendChild(el('div', {class:'pca-caption'}, [
    '주성분 분석 — 응답 패턴의 주요 모드를 부품 loadings + 위치 score 로 분해.'
  ]));
}

function _pcaDivergingColor(t){
  // t in [-1, 1]; blue → light → red diverging
  const clamp = Math.max(-1, Math.min(1, t));
  if (clamp >= 0){
    // light → red
    const r = Math.round(245 + (220-245)*clamp);
    const g = Math.round(238 + ( 50-238)*clamp);
    const b = Math.round(232 + ( 47-232)*clamp);
    return `rgb(${r},${g},${b})`;
  } else {
    const a = -clamp;
    const r = Math.round(245 + ( 33-245)*a);
    const g = Math.round(238 + (102-238)*a);
    const b = Math.round(232 + (172-232)*a);
    return `rgb(${r},${g},${b})`;
  }
}

function _deepRenderAnomalyDetection(data){
  var root = document.getElementById('deep-anomaly-detection');
  if(!root) return;
  root.innerHTML = '';
  var payload = (data && data.deep_analytics && data.deep_analytics.anomaly_detection) || null;
  if(!payload || payload.empty || !payload.per_position || payload.per_position.length===0){
    root.appendChild(el('div',{class:'empty'},'데이터 없음'));
    return;
  }

  var rows = payload.per_position;
  var thresh = payload.threshold;

  // Group cells by face for 5x5 heatmap. Use first face that has any anomalous, else first.
  var byFace = {};
  rows.forEach(function(r){
    if(!byFace[r.face]) byFace[r.face] = [];
    byFace[r.face].push(r);
  });
  var faceCodes = Object.keys(byFace).sort();
  var preferred = null;
  for(var i=0;i<faceCodes.length;i++){
    if(byFace[faceCodes[i]].some(function(r){return r.anomalous;})){ preferred = faceCodes[i]; break; }
  }
  var defaultFace = preferred || faceCodes[0];

  // Header / summary
  var head = el('div',{class:'anom-head'},[
    el('div',{class:'anom-summary'},[
      el('span',{class:'anom-stat'},['임계값 z = ', fmt(thresh,2),
        ' (max(2.5, P95=', fmt(payload.p95_z,2), '))']),
      el('span',{class:'anom-stat'},['이상치 ', String(payload.n_anomalous), ' / ', String(rows.length), ' 위치']),
      el('span',{class:'anom-stat'},['IQR 펜스 [', fmt(payload.iqr_low,2), ', ', fmt(payload.iqr_high,2), '] (', _u('acc'), ')']),
    ])
  ]);
  root.appendChild(head);

  // Face selector
  if(faceCodes.length>1){
    var sel = el('select',{class:'anom-face-sel'});
    faceCodes.forEach(function(fc){
      var o = el('option',{value:fc},[fc===defaultFace?(fc+' ◆'):fc]);
      if(fc===defaultFace) o.selected = true;
      sel.appendChild(o);
    });
    sel.addEventListener('change', function(){ _renderAnomalyForFace(root, payload, sel.value); });
    var fwrap = el('div',{class:'anom-facewrap'},[el('span',{class:'anom-label'},['면 선택: ']), sel]);
    root.appendChild(fwrap);
  }

  _renderAnomalyForFace(root, payload, defaultFace);
}

function _renderAnomalyForFace(root, payload, faceCode){
  // Clear previous body
  var old = root.querySelector('.anom-body');
  if(old) old.remove();

  var rows = payload.per_position.filter(function(r){ return r.face === faceCode; });
  var thresh = payload.threshold;
  var maxAbsAll = 0;
  rows.forEach(function(r){ if(r.max_abs_z>maxAbsAll) maxAbsAll = r.max_abs_z; });
  var denom = Math.max(maxAbsAll, thresh, 1e-9);

  // Build 5x5 grid by ranking x then y
  var xs = Array.from(new Set(rows.map(function(r){return r.x;}))).sort(function(a,b){return a-b;});
  var ys = Array.from(new Set(rows.map(function(r){return r.y;}))).sort(function(a,b){return b-a;}); // top-down
  var nx = Math.max(xs.length,1), ny = Math.max(ys.length,1);
  var _dgA = (typeof DATA !== 'undefined' && DATA.device_geometry) || {aspect: 1};
  var _arA = (_dgA.aspect && isFinite(_dgA.aspect) && _dgA.aspect > 0) ? _dgA.aspect : 1;
  var cellW = 56;
  // Per-cell height tracks per-position physical extent: when nx==ny, ratio
  // simplifies to device aspect. (Falls back to square when ar==1.)
  var cellH = Math.max(20, Math.min(160, Math.round(cellW * (ny / nx) / _arA)));
  var pad = 28;
  var W = pad*2 + nx*cellW;
  var H = pad*2 + ny*cellH;

  var s = svg('svg',{width:W, height:H, viewBox:'0 0 '+W+' '+H, class:'anom-heatmap'});

  // Lookup map
  var grid = {};
  rows.forEach(function(r){
    var ix = xs.indexOf(r.x), iy = ys.indexOf(r.y);
    grid[ix+'_'+iy] = r;
  });

  for(var iy=0; iy<ny; iy++){
    for(var ix=0; ix<nx; ix++){
      var r = grid[ix+'_'+iy];
      var cx = pad + ix*cellW;
      var cy = pad + iy*cellH;
      var fill = '#1f1f24';
      var stroke = '#3a3a44';
      var sw = 1;
      var label = '';
      if(r){
        var t = Math.min(1, r.max_abs_z / denom);
        // gray to red ramp
        var rch = Math.round(60 + 195*t);
        var gch = Math.round(60 + (1-t)*60);
        var bch = Math.round(60 + (1-t)*60);
        fill = 'rgb('+rch+','+gch+','+bch+')';
        if(r.anomalous){ stroke = '#ff3030'; sw = 3; }
        label = String(r.pos_id);
      }
      s.appendChild(svg('rect',{
        x:cx, y:cy, width:cellW-2, height:cellH-2,
        fill: fill, stroke: stroke, 'stroke-width': sw, rx: 4
      }));
      if(r){
        s.appendChild(svg('text',{
          x: cx + (cellW-2)/2, y: cy + (cellH-2)/2 - 4,
          'text-anchor':'middle','dominant-baseline':'middle',
          'font-size': 10, fill: '#fff'
        },[label]));
        s.appendChild(svg('text',{
          x: cx + (cellW-2)/2, y: cy + (cellH-2)/2 + 10,
          'text-anchor':'middle','dominant-baseline':'middle',
          'font-size': 10, fill: '#eaeaf0', 'font-weight':600
        },['z=' + fmt(r.max_abs_z,1)]));
      }
    }
  }

  // Anomaly table for this face (top of full ranking, but limited to face)
  var anomRows = rows.filter(function(r){return r.anomalous;});
  anomRows.sort(function(a,b){return b.max_abs_z - a.max_abs_z;});

  var tbl = el('table',{class:'anom-table'});
  var thead = el('thead',{},[el('tr',{},[
    el('th',{},['순위']), el('th',{},['Pos']),
    el('th',{},['주요 원인']),
    el('th',{},['|z|max']),
    el('th',{},['z_g']), el('th',{},['z_s']), el('th',{},['z_d'])
  ])]);
  tbl.appendChild(thead);
  var tbody = el('tbody',{});
  if(anomRows.length === 0){
    tbody.appendChild(el('tr',{},[el('td',{colspan:7,class:'anom-empty'},['이 면에서 이상치 없음'])]));
  } else {
    anomRows.forEach(function(r, i){
      var driverKor = {peak_g:'가속도', peak_stress:'응력', peak_disp:'변위'}[r.driver] || r.driver;
      tbody.appendChild(el('tr',{},[
        el('td',{},[String(i+1)]),
        el('td',{},[String(r.pos_id)]),
        el('td',{class:'anom-driver'},[driverKor]),
        el('td',{class:'anom-zmax'},[fmt(r.max_abs_z,2)]),
        el('td',{},[fmt(r.z_g,2)]),
        el('td',{},[fmt(r.z_s,2)]),
        el('td',{},[fmt(r.z_d,2)]),
      ]));
    });
  }
  tbl.appendChild(tbody);

  // IQR list (cross-method)
  var zSet = {};
  payload.per_position.forEach(function(r){ if(r.anomalous) zSet[r.face+'_'+r.pos_id]=true; });
  var iqrList = el('div',{class:'anom-iqr-list'});
  iqrList.appendChild(el('div',{class:'anom-iqr-title'},['IQR 펜스 기반 이상치 (peak_g)']));
  if(!payload.iqr_outliers || payload.iqr_outliers.length===0){
    iqrList.appendChild(el('div',{class:'anom-empty'},['IQR 기준 이상치 없음']));
  } else {
    var ul = el('ul',{class:'anom-iqr-ul'});
    payload.iqr_outliers.forEach(function(o){
      var key = o.face+'_'+o.pos_id;
      var agree = !!zSet[key];
      var li = el('li',{class: agree ? 'anom-iqr-agree' : 'anom-iqr-only'},[
        el('span',{class:'anom-iqr-tag'},[agree ? '✓ 양쪽 일치' : '△ IQR만']),
        ' ', o.face, ' Pos ', String(o.pos_id),
        ' — peak_g=', fmt(o.mean_g,2), ' ', _u('acc')
      ]);
      ul.appendChild(li);
    });
    iqrList.appendChild(ul);
  }

  var body = el('div',{class:'anom-body'},[
    el('div',{class:'anom-left'},[s]),
    el('div',{class:'anom-right'},[tbl, iqrList])
  ]);
  root.appendChild(body);

  var cap = el('div',{class:'anom-caption'},[
    '위치별 응답이 평균에서 얼마나 벗어났는가. 빨간 테두리 = 통계적 이상치 (z>',
    fmt(thresh,2),' 또는 IQR fence 초과).'
  ]);
  root.appendChild(cap);
  svgZoomPan(s);
}

function _deepPpdPartName(p) {
  const nm = String(p.part_name || ('part_' + p.part_id));
  const tail = nm.split(/[\\/]/).pop();
  return tail || nm;
}

function _deepPpdRenderList(data) {
  const root = document.getElementById('ppd-part-list');
  if (!root) return;
  root.innerHTML = '';
  const parts = data.parts || [];
  if (!parts.length) {
    root.appendChild(el('div', { class: 'ppd-empty' }, '데이터 없음'));
    return;
  }
  const maxG = parts[0].max_peak_g || 1;
  parts.forEach(p => {
    const row = el('div', {
      class: 'ppd-list-row' + (DEEP_STATE.active_part === p.part_id ? ' active' : ''),
      'data-ppd-part': String(p.part_id)
    });
    const name = el('div', { class: 'ppd-list-name', title: p.part_name }, _deepPpdPartName(p));
    const valWrap = el('div', { class: 'ppd-list-val' });
    const barBg = el('div', { class: 'ppd-list-bar-bg' });
    const t = maxG > 0 ? Math.max(0.02, Math.min(1, p.max_peak_g / maxG)) : 0;
    const bar = el('div', { class: 'ppd-list-bar' });
    bar.style.width = (t * 100).toFixed(1) + '%';
    bar.style.background = gColor(t);
    barBg.appendChild(bar);
    const num = el('div', { class: 'ppd-list-num' }, fmt(p.max_peak_g, 1));
    valWrap.appendChild(barBg);
    valWrap.appendChild(num);
    row.appendChild(name);
    row.appendChild(valWrap);
    row.addEventListener('click', () => {
      DEEP_STATE.active_part = p.part_id;
      _deepPpdRenderList(data);
      _deepPpdRenderDetail(data);
    });
    root.appendChild(row);
  });
}

function _deepPpdGetMatrix() {
  // Reuse DOE matrix when available, else return null
  const doe = (DATA && DATA.doe_analysis) || null;
  if (doe && doe.peak_g_matrix && Object.keys(doe.peak_g_matrix).length > 0) {
    return doe.peak_g_matrix;
  }
  return null;
}

function _deepPpdActivePart(data) {
  const parts = data.parts || [];
  if (!parts.length) return null;
  const want = DEEP_STATE.active_part;
  for (let i = 0; i < parts.length; i++) {
    if (parts[i].part_id === want) return parts[i];
  }
  return parts[0];
}

function _deepPpdRenderKpi(data, active) {
  const root = document.getElementById('ppd-kpi-strip');
  if (!root) return;
  root.innerHTML = '';
  if (!active) {
    root.appendChild(el('div', { class: 'ppd-empty' }, '선택된 부품 없음'));
    return;
  }
  const tiles = [
    { label: '최대 Peak G',     value: fmt(active.max_peak_g, 1),     unit: _u('acc') },
    { label: '평균 Peak G',     value: fmt(active.mean_peak_g, 1),    unit: _u('acc') },
    { label: '최대 응력',        value: fmt(active.max_peak_stress, 2), unit: _u('stress') },
    { label: '최대 변위',        value: fmt(active.max_peak_disp, 3),  unit: _u('disp') },
    { label: 'P75↑ 위치 수',     value: String(active.n_positions_above_global_p75 || 0), unit: '/ ' + (Object.keys(data.positions_lookup || {}).length || 25) },
    { label: '항복 정의',        value: active.has_yield ? 'YES' : 'NO', unit: active.has_yield ? _u('stress') : '' }
  ];
  tiles.forEach(t => {
    const tile = el('div', { class: 'ppd-kpi-tile' });
    tile.appendChild(el('div', { class: 'ppd-kpi-label' }, t.label));
    const v = el('div', { class: 'ppd-kpi-val' }, t.value);
    if (t.unit) v.appendChild(el('span', { class: 'ppd-kpi-unit' }, ' ' + t.unit));
    tile.appendChild(v);
    root.appendChild(tile);
  });
}

function _deepPpdRenderHeatmap(data, active) {
  const root = document.getElementById('ppd-heatmap-svg');
  if (!root) return;
  while (root.firstChild) root.removeChild(root.firstChild);
  const _dgPP = (typeof DATA !== 'undefined' && DATA.device_geometry) || {aspect: 1};
  const _arPP = (_dgPP.aspect && isFinite(_dgPP.aspect) && _dgPP.aspect > 0) ? _dgPP.aspect : 1;
  const W = 320, H = Math.max(120, Math.round(W / _arPP));
  root.setAttribute('viewBox', '0 0 ' + W + ' ' + H);

  const mat = _deepPpdGetMatrix();
  const positions = data.positions_lookup || {};
  const posKeys = Object.keys(positions);

  if (!active || !mat || !posKeys.length) {
    root.appendChild(svg('text', { x: W/2, y: H/2, 'text-anchor': 'middle',
      fill: '#5c6383', 'font-size': 12 }, [document.createTextNode('위치별 peak_g 매트릭스 없음')]));
    return;
  }

  const row = mat[String(active.part_id)] || mat[active.part_id] || {};
  // bbox from positions
  let xmin = Infinity, xmax = -Infinity, ymin = Infinity, ymax = -Infinity;
  posKeys.forEach(k => {
    const xy = positions[k];
    if (!xy) return;
    if (xy.x < xmin) xmin = xy.x; if (xy.x > xmax) xmax = xy.x;
    if (xy.y < ymin) ymin = xy.y; if (xy.y > ymax) ymax = xy.y;
  });
  if (!isFinite(xmin) || xmin === xmax) { xmin -= 1; xmax += 1; }
  if (!isFinite(ymin) || ymin === ymax) { ymin -= 1; ymax += 1; }
  const padX = (xmax - xmin) * 0.08, padY = (ymax - ymin) * 0.08;
  xmin -= padX; xmax += padX; ymin -= padY; ymax += padY;

  // value normalization (use part's own max)
  let vmax = 0;
  posKeys.forEach(k => { const v = row[k] || 0; if (v > vmax) vmax = v; });
  if (vmax <= 0) {
    root.appendChild(svg('text', { x: W/2, y: H/2, 'text-anchor': 'middle',
      fill: '#5c6383', 'font-size': 12 }, [document.createTextNode('이 부품에 데이터 없음')]));
    return;
  }

  const margin = 24;
  const plotW = W - 2 * margin, plotH = H - 2 * margin;
  const sx = (x) => margin + (x - xmin) / (xmax - xmin) * plotW;
  const sy = (y) => margin + (1 - (y - ymin) / (ymax - ymin)) * plotH;

  // size cells based on nx/ny from grid if available
  const grid = (DATA.doe_analysis && DATA.doe_analysis.grid) || null;
  let cellW, cellH;
  if (grid && grid.nx && grid.ny) {
    cellW = plotW / grid.nx * 0.92;
    cellH = plotH / grid.ny * 0.92;
  } else {
    const n = Math.max(2, Math.ceil(Math.sqrt(posKeys.length)));
    cellW = plotW / n * 0.85;
    cellH = plotH / n * 0.85;
  }

  // background panel
  root.appendChild(svg('rect', { x: margin - 2, y: margin - 2,
    width: plotW + 4, height: plotH + 4, fill: '#0e1220', stroke: '#262d44',
    'stroke-width': 1, rx: 4 }));

  posKeys.forEach(k => {
    const xy = positions[k];
    if (!xy) return;
    const v = row[k] || 0;
    const t = v / vmax;
    const cx = sx(xy.x), cy = sy(xy.y);
    const fill = v > 0 ? gColor(t) : '#1a1e2e';
    const rect = svg('rect', { x: cx - cellW/2, y: cy - cellH/2,
      width: cellW, height: cellH, fill: fill, rx: 2,
      stroke: '#262d44', 'stroke-width': 0.5 });
    rect.appendChild(svg('title', null, [document.createTextNode(
      k + ': ' + fmt(v, 1) + ' ' + _u('acc'))]));
    root.appendChild(rect);
  });

  // star on max position
  if (active.max_pos_id && positions[active.max_pos_id]) {
    const xy = positions[active.max_pos_id];
    const cx = sx(xy.x), cy = sy(xy.y);
    // simple 5-point star path
    const r1 = Math.max(6, Math.min(cellW, cellH) * 0.35);
    const r2 = r1 * 0.45;
    let d = '';
    for (let i = 0; i < 10; i++) {
      const a = (i * Math.PI / 5) - Math.PI / 2;
      const r = (i % 2 === 0) ? r1 : r2;
      d += (i === 0 ? 'M' : 'L') + (cx + r * Math.cos(a)).toFixed(2) +
           ',' + (cy + r * Math.sin(a)).toFixed(2);
    }
    d += 'Z';
    root.appendChild(svg('path', { d: d, fill: '#fff7b0',
      stroke: '#1a1e2e', 'stroke-width': 1.2 }));
  }

  // legend min/max
  root.appendChild(svg('text', { x: margin, y: H - 4,
    fill: '#5c6383', 'font-size': 9 },
    [document.createTextNode('0 ~ ' + fmt(vmax, 1) + ' ' + _u('acc'))]));
  svgZoomPan(root);
}

function _deepPpdRenderHistogram(data, active) {
  const root = document.getElementById('ppd-hist-svg');
  if (!root) return;
  while (root.firstChild) root.removeChild(root.firstChild);
  const W = 320, H = 200;
  root.setAttribute('viewBox', '0 0 ' + W + ' ' + H);

  const mat = _deepPpdGetMatrix();
  const positions = data.positions_lookup || {};
  if (!active || !mat) {
    root.appendChild(svg('text', { x: W/2, y: H/2, 'text-anchor': 'middle',
      fill: '#5c6383', 'font-size': 12 }, [document.createTextNode('매트릭스 없음')]));
    return;
  }
  const row = mat[String(active.part_id)] || mat[active.part_id] || {};
  const vals = Object.keys(positions).map(k => Number(row[k] || 0));
  if (!vals.length) {
    root.appendChild(svg('text', { x: W/2, y: H/2, 'text-anchor': 'middle',
      fill: '#5c6383', 'font-size': 12 }, [document.createTextNode('데이터 없음')]));
    return;
  }
  const vmax = Math.max.apply(null, vals);
  if (vmax <= 0) {
    root.appendChild(svg('text', { x: W/2, y: H/2, 'text-anchor': 'middle',
      fill: '#5c6383', 'font-size': 12 }, [document.createTextNode('모든 위치에서 0')]));
    return;
  }
  const NB = 10;
  const counts = new Array(NB).fill(0);
  vals.forEach(v => {
    let b = Math.floor((v / vmax) * NB);
    if (b >= NB) b = NB - 1;
    if (b < 0) b = 0;
    counts[b] += 1;
  });
  const cmax = Math.max.apply(null, counts) || 1;

  const padL = 32, padR = 8, padT = 16, padB = 28;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  // axes
  root.appendChild(svg('line', { x1: padL, y1: padT + plotH, x2: padL + plotW,
    y2: padT + plotH, stroke: '#262d44', 'stroke-width': 1 }));
  root.appendChild(svg('line', { x1: padL, y1: padT, x2: padL,
    y2: padT + plotH, stroke: '#262d44', 'stroke-width': 1 }));

  const bw = plotW / NB;
  counts.forEach((c, i) => {
    const t = (i + 0.5) / NB;
    const h = (c / cmax) * plotH;
    const x = padL + i * bw + 1;
    const y = padT + plotH - h;
    const rect = svg('rect', { x: x, y: y, width: bw - 2, height: h,
      fill: gColor(t), rx: 1 });
    rect.appendChild(svg('title', null, [document.createTextNode(
      '[' + fmt(i * vmax / NB, 1) + ' ~ ' + fmt((i + 1) * vmax / NB, 1) +
      '] ' + _u('acc') + ': ' + c + '개')]));
    root.appendChild(rect);
  });
  // x-axis label
  root.appendChild(svg('text', { x: padL, y: H - 10, fill: '#5c6383',
    'font-size': 9, 'text-anchor': 'start' },
    [document.createTextNode('0')]));
  root.appendChild(svg('text', { x: padL + plotW, y: H - 10, fill: '#5c6383',
    'font-size': 9, 'text-anchor': 'end' },
    [document.createTextNode(fmt(vmax, 1) + ' ' + _u('acc'))]));
  root.appendChild(svg('text', { x: padL + plotW/2, y: H - 2, fill: '#aab2cf',
    'font-size': 10, 'text-anchor': 'middle' },
    [document.createTextNode('peak_g 분포 (25 위치)')]));
  // y-axis max
  root.appendChild(svg('text', { x: padL - 4, y: padT + 4, fill: '#5c6383',
    'font-size': 9, 'text-anchor': 'end' },
    [document.createTextNode(String(cmax))]));
}

function _deepPpdRenderYieldOrMat(data, active) {
  const root = document.getElementById('ppd-yield-svg');
  if (!root) return;
  while (root.firstChild) root.removeChild(root.firstChild);
  const W = 320, H = 200;
  root.setAttribute('viewBox', '0 0 ' + W + ' ' + H);

  if (!active) {
    root.appendChild(svg('text', { x: W/2, y: H/2, 'text-anchor': 'middle',
      fill: '#5c6383', 'font-size': 12 }, [document.createTextNode('선택된 부품 없음')]));
    return;
  }

  if (active.has_yield && active.yield_value && active.yield_value > 0) {
    const y = active.yield_value;
    const s = active.max_peak_stress || 0;
    const ratio = s / y;
    const vmax = Math.max(y, s) * 1.15;
    const padL = 32, padR = 16, padT = 24, padB = 40;
    const plotW = W - padL - padR, plotH = H - padT - padB;

    // background
    root.appendChild(svg('rect', { x: padL, y: padT, width: plotW, height: plotH,
      fill: '#0e1220', stroke: '#262d44', 'stroke-width': 1, rx: 2 }));

    // stress bar
    const sH = (s / vmax) * plotH;
    const fill = ratio >= 1 ? '#e85d75' : (ratio >= 0.7 ? '#f0b400' : '#5dd28a');
    const barW = plotW * 0.32;
    const sBarX = padL + plotW * 0.20;
    root.appendChild(svg('rect', { x: sBarX, y: padT + plotH - sH,
      width: barW, height: sH, fill: fill, rx: 2 }));
    root.appendChild(svg('text', { x: sBarX + barW/2, y: padT + plotH + 14,
      'text-anchor': 'middle', fill: '#aab2cf', 'font-size': 10 },
      [document.createTextNode('최대 응력')]));
    root.appendChild(svg('text', { x: sBarX + barW/2, y: padT + plotH - sH - 4,
      'text-anchor': 'middle', fill: '#e0e4ff', 'font-size': 10 },
      [document.createTextNode(fmt(s, 2))]));

    // yield bar
    const yH = (y / vmax) * plotH;
    const yBarX = padL + plotW * 0.58;
    root.appendChild(svg('rect', { x: yBarX, y: padT + plotH - yH,
      width: barW, height: yH, fill: '#3b528b', rx: 2 }));
    root.appendChild(svg('text', { x: yBarX + barW/2, y: padT + plotH + 14,
      'text-anchor': 'middle', fill: '#aab2cf', 'font-size': 10 },
      [document.createTextNode('항복')]));
    root.appendChild(svg('text', { x: yBarX + barW/2, y: padT + plotH - yH - 4,
      'text-anchor': 'middle', fill: '#e0e4ff', 'font-size': 10 },
      [document.createTextNode(fmt(y, 2))]));

    // yield line
    root.appendChild(svg('line', { x1: padL, y1: padT + plotH - yH,
      x2: padL + plotW, y2: padT + plotH - yH,
      stroke: '#e85d75', 'stroke-width': 1, 'stroke-dasharray': '4 3' }));

    root.appendChild(svg('text', { x: W/2, y: 14, 'text-anchor': 'middle',
      fill: '#e0e4ff', 'font-size': 11 },
      [document.createTextNode('응력/항복 비교 — 비율 ' + (ratio * 100).toFixed(1) + '%')]));
    root.appendChild(svg('text', { x: W/2, y: H - 6, 'text-anchor': 'middle',
      fill: '#5c6383', 'font-size': 9 },
      [document.createTextNode('단위: ' + _u('stress'))]));
  } else {
    // material card — show E and density (impactor proxy)
    const mat = data.impactor_material || { youngs_modulus: 0, density: 0 };
    root.appendChild(svg('text', { x: W/2, y: 22, 'text-anchor': 'middle',
      fill: '#e0e4ff', 'font-size': 12 },
      [document.createTextNode('항복 응력 미정의')]));
    root.appendChild(svg('text', { x: W/2, y: 42, 'text-anchor': 'middle',
      fill: '#5c6383', 'font-size': 9 },
      [document.createTextNode('대신 충격체 재료 정보 표시')]));

    const rows = [
      ['최대 응력 (관측)', fmt(active.max_peak_stress, 2) + ' ' + _u('stress')],
      ['충격체 E',         fmt(mat.youngs_modulus, 2) + ' ' + _u('stress')],
      ['충격체 밀도',      fmt(mat.density, 6)]
    ];
    rows.forEach((r, i) => {
      const y = 80 + i * 28;
      root.appendChild(svg('text', { x: 24, y: y, fill: '#aab2cf', 'font-size': 11 },
        [document.createTextNode(r[0])]));
      root.appendChild(svg('text', { x: W - 24, y: y, 'text-anchor': 'end',
        fill: '#e0e4ff', 'font-size': 11 },
        [document.createTextNode(r[1])]));
    });
  }
}

function _deepPpdRenderDetail(data) {
  const active = _deepPpdActivePart(data);
  // title
  const titleEl = document.getElementById('ppd-detail-title');
  if (titleEl) {
    if (active) {
      titleEl.textContent = '활성 부품: ' + _deepPpdPartName(active) +
        '  (id=' + active.part_id + ', 최대 위치=' + active.max_pos_id + ')';
    } else {
      titleEl.textContent = '활성 부품 없음';
    }
  }
  _deepPpdRenderKpi(data, active);
  _deepPpdRenderHeatmap(data, active);
  _deepPpdRenderHistogram(data, active);
  _deepPpdRenderYieldOrMat(data, active);
}

function _deepRenderPerPartDrillDown(deepData) {
  const data = deepData && deepData.per_part_drilldown;
  const host = document.getElementById('ppd-host');
  if (!host) return;
  if (!data || !data.parts || !data.parts.length) {
    host.style.display = 'none';
    return;
  }
  host.style.display = '';
  // initialize active part = top-1 by default
  if (DEEP_STATE.active_part == null) {
    DEEP_STATE.active_part = data.parts[0].part_id;
  }
  _deepPpdRenderList(data);
  _deepPpdRenderDetail(data);
}

"""
