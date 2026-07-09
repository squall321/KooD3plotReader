# 섹션 03 — VERDICT · ENERGY FLOW HTML 템플릿 (기계적 분할, 바이트 불변)

_PAGE3 = """
<section class="page" id="s3">
  <div class="page-head r">
    <span class="num">03</span><span class="tagline">VERDICT &middot; ENERGY FLOW</span>
    <span class="ttl">충격은 어디로 흘러가며, 무엇을 결정해야 하는가</span>
    <span class="sub">MULTI-CRITERIA VERDICT + ENERGY DYNAMICS</span>
  </div>

  <div class="grid g-12">
    <div class="panel col-12 r">
      <div class="ph">
        <span class="pt">STRESS-TIME ENVELOPE &middot; CRITICAL PARTS</span>
        <span class="pd">12 worst pairs &middot; P5-P95 gray band + P50 + red worst</span>
      </div>
      <div class="ts-grid" id="ts-grid"></div>
      <div class="pcap">회색 띠 = 전체 페어의 P5-P95 envelope. 흰 라인 = P50. 빨간 라인 = worst pair.</div>
    </div>

    <div class="panel col-7 r">
      <div class="ph">
        <span class="pt">MULTI-CRITERIA VERDICT MATRIX</span>
        <span class="pd">part &middot; face &middot; position &middot; class &middot; max G/&sigma;/&epsilon;/d &middot; influence area</span>
      </div>
      <div style="overflow-x:auto">
        <table class="dt" id="verdict-tbl">
          <thead>
            <tr>
              <th class="tl">PART</th><th class="tl">FACE</th><th>X</th><th>Y</th>
              <th class="tl">CLASS</th><th>MAX G</th><th>&sigma;</th><th>&epsilon;</th><th>d</th>
              <th>CoV</th><th>INFL</th><th class="tl">MODE</th>
            </tr>
          </thead>
          <tbody></tbody>
        </table>
      </div>
    </div>

    <div class="col-5" style="display:grid;gap:14px">
      <div class="verdict-row">
        <div class="verdict-cell crit"><div class="vl">CRITICAL</div><div class="vn" id="vCrit">0</div><div class="vd">G &ge; P95 threshold &middot; 즉시 대응</div></div>
        <div class="verdict-cell warn"><div class="vl">WARNING</div><div class="vn" id="vWarn">0</div><div class="vd">P75 &le; G &lt; P95 &middot; 모니터링</div></div>
        <div class="verdict-cell safe"><div class="vl">PASSED</div><div class="vn" id="vSafe">0</div><div class="vd">G &lt; P75 &middot; 안전 마진</div></div>
      </div>
      <div class="panel r" style="padding:14px">
        <div class="ph">
          <span class="pt">FINDINGS</span>
          <span class="pd">auto-derived recommendations</span>
        </div>
        <ul id="findings-list" style="list-style:none;padding:0;margin:6px 0 0 0;font-size:11px;line-height:1.55"></ul>
      </div>
    </div>
  </div>

  <div class="page-head r" style="margin-top:36px">
    <span class="num">&#9889;</span><span class="tagline" style="color:var(--accent2)">ENERGY FLOW DYNAMICS</span>
    <span class="ttl">임팩트 KE의 경로 추적</span>
    <span class="sub">FORCE GRAPH + SUNBURST + SANKEY + TIME-FORCE</span>
  </div>

  <div class="grid g-12">
    <div class="panel col-7 r">
      <div class="ph">
        <span class="pt">FORCE-DIRECTED ENERGY GRAPH</span>
        <span class="pd">node size &prop; IE &middot; edge thickness &prop; impulse</span>
      </div>
      <div class="eg-wrap">
        <canvas id="eg-canvas"></canvas>
        <div class="eg-side" id="eg-side"></div>
      </div>
      <div class="scrub">
        <button class="btn" id="eg-play">&#9654; PLAY</button>
        <button class="btn" id="eg-reset">&#11119; RESET</button>
        <input type="range" id="eg-scrub" min="0" max="100" value="0">
        <div class="tlabel">t = <b id="eg-t">0.000</b> ms</div>
      </div>
      <div class="pcap">중앙 = 임팩터. 동심원 = 전파 깊이. 외곽 펄스링 = 활성 contact. 흐르는 입자 = 순간 force.</div>
    </div>

    <div class="panel col-5 r">
      <div class="ph">
        <span class="pt">ENERGY BUDGET SUNBURST</span>
        <span class="pd">KE_init &rarr; IE / dissipated / KE_left</span>
      </div>
      <svg id="sunburst-svg" viewBox="0 0 360 340" preserveAspectRatio="xMidYMid meet" style="width:100%;height:340px"></svg>
      <div class="pcap">중심 = 임팩터 초기 KE 100%. 1차 링 = IE / 소산 / 잔존. 2차 링 = 부품별 흡수 비율.</div>
    </div>

    <div class="panel col-7 r">
      <div class="ph">
        <span class="pt">SANKEY-STYLE CUMULATIVE FLOW</span>
        <span class="pd">impactor &rarr; parts &middot; edge bar &prop; total work</span>
      </div>
      <div id="sankey-rows"></div>
      <div class="pcap">막대 길이 = 누적 work. 위에서 아래로 = first-engage 순서.</div>
    </div>

    <div class="panel col-5 r">
      <div class="ph">
        <span class="pt">TIME-FORCE HEATMAP MATRIX</span>
        <span class="pd">rows = edges &middot; cols = 21 time bins &middot; sorted by first-engage</span>
      </div>
      <div class="tfh-head">
        <div class="h0">EDGE</div>
        <div class="ht">0</div><div class="ht"></div><div class="ht"></div><div class="ht"></div><div class="ht"></div>
        <div class="ht">&frac14;</div><div class="ht"></div><div class="ht"></div><div class="ht"></div><div class="ht"></div>
        <div class="ht">&frac12;</div><div class="ht"></div><div class="ht"></div><div class="ht"></div><div class="ht"></div>
        <div class="ht">&frac34;</div><div class="ht"></div><div class="ht"></div><div class="ht"></div><div class="ht"></div>
        <div class="ht">T</div>
      </div>
      <div class="tfh" id="tfh-rows"></div>
      <div class="pcap">"몇 &micro;s 후에 어디까지 전파됐는가" &mdash; 위에서 아래로 = 시간순 전파 사슬.</div>
    </div>

    <div class="panel col-3 r">
      <div class="ph">
        <span class="pt">CONSERVATION CHECK</span>
        <span class="pd">KE&#x2080; = IE + diss + KE&#x2099;</span>
      </div>
      <div class="cons-box">
        <div class="cons-cell"><div class="v" id="consKE">0.0</div><div class="l">KE INITIAL (J)</div></div>
        <div class="cons-cell"><div class="v" id="consIE">0.0</div><div class="l">IE FINAL (J)</div></div>
        <div class="cons-cell"><div class="v" id="consDISS">0.0</div><div class="l">DISSIPATED</div></div>
        <div class="cons-cell" id="consResCell"><div class="v" id="consRES">0.0</div><div class="l">RESIDUAL %</div></div>
      </div>
      <div class="cons-bar" id="consBar"></div>
      <div class="cons-banner" id="consBanner">&#9888; Residual exceeds tolerance &mdash; energy conservation suspect</div>
    </div>

    <div class="panel col-7 r">
      <div class="ph">
        <span class="pt">PHASE DIAGRAM &middot; KE vs IE</span>
        <span class="pd">all runs overlaid &middot; color by behavior &middot; budget line = KE&#x2080;</span>
      </div>
      <div class="phase-wrap">
        <svg id="phase-svg" preserveAspectRatio="none"></svg>
      </div>
      <div class="bvm-legend" id="phase-legend"></div>
      <div class="pcap">
        가로축 = 누적 흡수 IE, 세로축 = 임팩터 KE. 대각선은 에너지 보존 budget. 곡선이 budget 위로 떨어질수록 소산이 크다는 뜻.
      </div>
    </div>

    <div class="panel col-5 r">
      <div class="ph">
        <span class="pt">CONTACT ENGAGEMENT SEQUENCE</span>
        <span class="pd">top-8 worst impacts &middot; 21 timesteps &middot; contact dominance</span>
      </div>
      <div class="cseq-grid" id="cseq-grid"></div>
      <div class="pcap">셀 색상 = 그 시점의 dominant contact part. 회색 = 비접촉. 어느 시각에 어디까지 충격이 전파되는지 한눈에 추적 가능.</div>
    </div>

    <div class="panel col-12 r">
      <div class="ph">
        <span class="pt">TRAJECTORY BUNDLE 3D &middot; impactor envelopes</span>
        <span class="pd">all runs &middot; 3 orthogonal projections &middot; XZ / YZ side + XY top</span>
      </div>
      <div class="tb3">
        <div class="tb3-cell">
          <div class="h"><span>SIDE &middot; XZ</span><span>color = face</span></div>
          <svg id="tb3-xz" preserveAspectRatio="none"></svg>
        </div>
        <div class="tb3-cell">
          <div class="h"><span>SIDE &middot; YZ</span><span>color = face</span></div>
          <svg id="tb3-yz" preserveAspectRatio="none"></svg>
        </div>
        <div class="tb3-cell">
          <div class="h"><span>TOP &middot; XY</span><span>color = behavior</span></div>
          <svg id="tb3-xy" preserveAspectRatio="none"></svg>
        </div>
      </div>
      <div class="pcap">
        각 임팩터 경로의 envelope. 검은 점선 = device bbox. 회색 가로선(z=0) = 충돌면. embed 거동(빨강)은 z &lt; 0까지 침투.
      </div>
    </div>
  </div>
</section>
"""


_JS_S3 = r"""function initFaceKpiTable() {
  const tbody = document.querySelector('#face-kpi-tbl tbody');
  while (tbody.firstChild) tbody.removeChild(tbody.firstChild);
  let gmax = 0;
  for (const r of RESULTS) if (r.g > gmax) gmax = r.g;
  // Risk-score config (None in payload => panel hidden, no score column).
  const rsCfg = DATA.risk_score;
  const k = DATA.kpi || {};
  const crit_t = (k.crit_threshold != null) ? k.crit_threshold : 0;
  // compute scores for each face first so we can do the vs-other delta
  const faceStats = {};
  for (const f of FACES) {
    const rows = FACE_RESULTS[f.code] || [];
    if (!rows.length) continue;
    let worst = rows[0];
    for (const r of rows) if (r.g > worst.g) worst = r;
    const gvals = rows.map(r => r.g).sort((a, b) => a - b);
    const p95 = gvals[Math.floor(gvals.length * 0.95)] || 0;
    // Critical-count uses the payload's P95 threshold (same as the rest of
    // the report) instead of the magic 0.5 ratio.
    const crit = gvals.filter(v => v >= crit_t).length;
    let score = null;
    if (rsCfg && rsCfg.weights) {
      const w = rsCfg.weights;
      const ww = (w.worst != null ? w.worst : 0);
      const wp = (w.p95   != null ? w.p95   : 0);
      const wc = (w.crit  != null ? w.crit  : 0);
      score = (ww * worst.g / Math.max(1, gmax)
             + wp * p95     / Math.max(1, gmax)
             + wc * crit    / Math.max(1, gvals.length)) * 10;
    }
    const nPos = new Set(rows.map(r => r.pos_id)).size;
    faceStats[f.code] = { face: f, worst: worst, score: score, n: nPos };
  }
  // Hide SCORE / Δ columns when risk_score config is absent.
  const head = document.querySelector('#face-kpi-tbl thead tr');
  if (head && !rsCfg) {
    const ths = head.querySelectorAll('th');
    if (ths.length >= 7) {
      ths[5].style.display = 'none';
      ths[6].style.display = 'none';
    }
  }
  const codes = Object.keys(faceStats);
  for (const code of codes) {
    const s = faceStats[code];
    const f = s.face;
    const worst = s.worst;
    const score = s.score;
    const otherCode = codes.find(c => c !== code);
    let cls = 'r-safe';
    let scoreColor = 'var(--dim)';
    let dStr = '-';
    let dColor = 'var(--dim)';
    if (rsCfg && score != null) {
      const critBand = rsCfg.crit_band;
      const warnBand = rsCfg.warn_band;
      cls = (critBand != null && score >= critBand) ? 'r-crit'
          : (warnBand != null && score >= warnBand) ? 'r-warn' : 'r-safe';
      scoreColor = (critBand != null && score >= critBand) ? 'var(--crit)'
                 : (warnBand != null && score >= warnBand) ? 'var(--warn)' : 'var(--good)';
      const otherScore = (otherCode != null && faceStats[otherCode].score != null)
                       ? faceStats[otherCode].score : score;
      const delta = score - otherScore;
      dColor = delta > 0 ? 'var(--crit)' : delta < 0 ? 'var(--good)' : 'var(--dim)';
      dStr = (delta > 0 ? '+' : '') + delta.toFixed(2);
    }
    const cells = [
      el('td', { class: 'tl b' }, f.code + ' · ' + f.name),
      el('td', { class: 'num' }, String(s.n)),
      el('td', { class: 'num b' }, fmt(worst.g, 0)),
      el('td', { class: 'num dim' }, worst.x.toFixed(1) + ' , ' + worst.y.toFixed(1)),
      el('td', { class: 'tl b' }, worst.part_name),
      el('td', { class: 'num', style: { color: scoreColor } }, rsCfg && score != null ? (score.toFixed(1) + ' / 10') : '-'),
      el('td', { class: 'num', style: { color: dColor } }, dStr)
    ];
    if (!rsCfg) {
      cells[5].style.display = 'none';
      cells[6].style.display = 'none';
    }
    tbody.appendChild(el('tr', { class: cls }, cells));
  }
}

function initTopK() {
  const tbody = document.querySelector('#topk-tbl tbody');
  while (tbody.firstChild) tbody.removeChild(tbody.firstChild);
  const sorted = RESULTS.slice().sort((a, b) => b.g - a.g).slice(0, 12);
  // Use payload P95/P75 thresholds for row coloring (matches verdict matrix).
  const k = DATA.kpi || {};
  const g_vals = RESULTS.map(x => x.g).filter(v => v > 0);
  const crit_t = (k.crit_threshold != null) ? k.crit_threshold : _percentile(g_vals, 0.95);
  const warn_t = (k.warn_threshold != null) ? k.warn_threshold : _percentile(g_vals, 0.75);
  const infl_t = (k.influence_threshold != null) ? k.influence_threshold : _percentile(g_vals, 0.85);
  for (let i = 0; i < sorted.length; i++) {
    const r = sorted[i];
    const partRows = RESULTS.filter(x => x.part_id === r.part_id);
    // Influence area: count rows in this part above the P85 g threshold.
    const inf = partRows.filter(x => x.g >= infl_t).length;
    // Row color is value-based (P95/P75), not rank-based.
    const cls = r.g >= crit_t ? 'r-crit' : r.g >= warn_t ? 'r-warn' : 'r-safe';
    tbody.appendChild(el('tr', { class: cls }, [
      el('td', { class: 'tl b' }, '#' + (i + 1)),
      el('td', { class: 'tl b' }, r.face),
      el('td', { class: 'num' }, r.x.toFixed(2)),
      el('td', { class: 'num' }, r.y.toFixed(2)),
      el('td', { class: 'tl' }, r.part_name),
      el('td', { class: 'num b' }, fmt(r.g, 0)),
      el('td', { class: 'num' }, fmt(r.s, 1)),
      el('td', { class: 'num dim' }, inf + ' / ' + partRows.length)
    ]));
  }
}

function partMatches(p) {
  if (!STATE.filter) return true;
  return p.name.toLowerCase().indexOf(STATE.filter.toLowerCase()) >= 0;
}

function renderInfluenceMatrix() {
  const wrap = document.getElementById('imatrix-wrap');
  if (!wrap) return;
  while (wrap.firstChild) wrap.removeChild(wrap.firstChild);
  // top-10 impact positions on currently selected face, by the active metric
  const metric = STATE.ii.metric;
  const faceCode = STATE.ii.face;
  const posMax = _ensurePosMax(metric);
  const faceKeys = Object.keys(posMax).filter(k => k.indexOf(faceCode + '|') === 0);
  faceKeys.sort((a, b) => posMax[b].v - posMax[a].v);
  const topPairs = faceKeys.slice(0, 10).map(k => posMax[k]);
  let gmx = 0;
  for (const r of RESULTS) { const v = r[metric] || 0; if (v > gmx) gmx = v; }
  const tbl = el('table', { class: 'imatrix' });
  const trHead = el('tr', null, [el('th', { class: 'tl', style: { minWidth: '160px' } }, 'IMPACT (face · X, Y)')]);
  for (const p of PARTS) {
    trHead.appendChild(el('th', {
      style: { transform: 'rotate(-30deg)', transformOrigin: 'left bottom', whiteSpace: 'nowrap', paddingLeft: '10px', color: 'var(--accent)' }
    }, p.name.split('\\').pop()));
  }
  trHead.appendChild(el('th', null, 'MAX'));
  tbl.appendChild(el('thead', null, trHead));
  const tbody = el('tbody');
  for (const pair of topPairs) {
    const tr = el('tr');
    const labCell = el('td', { class: 'tl', style: { color: 'var(--fg)', fontWeight: 600, cursor: 'pointer' } }, pair.face + ' · ' + pair.x.toFixed(1) + ', ' + pair.y.toFixed(1));
    labCell.addEventListener('click', function () {
      STATE.ii.hovered_pos = pair.face + '|' + pair.pos_id;
      STATE.ii.pinned = true;
      const pin = document.getElementById('ii-pin');
      if (pin) { pin.checked = true; document.getElementById('ii-pin-lab').classList.add('locked'); }
      const key = STATE.ii.hovered_pos;
      const rec = posMax[key];
      if (rec) {
        _renderInspectorFill(rec, gmx);
        _renderSidePanel(rec, gmx);
      }
      const tgt = document.getElementById('s2');
      if (tgt) tgt.scrollIntoView({ behavior: 'smooth' });
    });
    tr.appendChild(labCell);
    for (const p of PARTS) {
      const match = RESULT_IDX[pair.face + '|' + pair.pos_id + '|' + p.id];
      const v = match ? (match[metric] || 0) : 0;
      const td = el('td', {
        class: 'cell',
        title: p.name + ': ' + fmt(v, 2),
        style: { background: v > 0 ? gColor(Math.min(1, v / Math.max(1e-9, gmx))) : '#0a0c14' }
      });
      tr.appendChild(td);
    }
    tr.appendChild(el('td', { style: { color: 'var(--num)', fontWeight: 700, paddingLeft: '8px' } }, fmt(pair.v, 1)));
    tbody.appendChild(tr);
  }
  tbl.appendChild(tbody);
  wrap.appendChild(tbl);
}

function _percentile(arr, p) {
  if (!arr || !arr.length) return 0;
  const a = arr.slice().sort((x, y) => x - y);
  const idx = Math.floor(p * (a.length - 1));
  return a[Math.max(0, Math.min(a.length - 1, idx))];
}

function renderVerdict() {
  const tbody = document.querySelector('#verdict-tbl tbody');
  while (tbody.firstChild) tbody.removeChild(tbody.firstChild);
  const byPart = {};
  for (const r of RESULTS) {
    const cur = byPart[r.part_id];
    if (!cur || r.g > cur.g) byPart[r.part_id] = r;
  }
  // Use payload-supplied percentile thresholds (P95 = crit, P75 = warn).
  // Falls back to JS-side percentile if payload field missing.
  const k = DATA.kpi || {};
  const g_vals = RESULTS.map(r => r.g).filter(v => v > 0);
  const crit_t = (k.crit_threshold != null) ? k.crit_threshold : _percentile(g_vals, 0.95);
  const warn_t = (k.warn_threshold != null) ? k.warn_threshold : _percentile(g_vals, 0.75);
  const infl_t = (k.influence_threshold != null) ? k.influence_threshold : _percentile(g_vals, 0.85);
  let nC = 0, nW = 0, nS = 0;
  const rows = Object.values(byPart).sort((a, b) => b.g - a.g);
  for (const r of rows) {
    const partRows = RESULTS.filter(x => x.part_id === r.part_id);
    const vs = partRows.map(x => x.g);
    const mean = vs.reduce((a, b) => a + b, 0) / vs.length;
    const variance = vs.reduce((a, b) => a + (b - mean) * (b - mean), 0) / vs.length;
    const cov = mean > 0 ? Math.sqrt(variance) / mean : 0;
    // influence: rows in this part exceeding the P85 threshold
    const inf = vs.filter(v => v >= infl_t).length;
    const klass = r.g >= crit_t ? 'CRITICAL' : r.g >= warn_t ? 'WARNING' : 'PASSED';
    if (klass === 'CRITICAL') nC++; else if (klass === 'WARNING') nW++; else nS++;
    const rowClass = klass === 'CRITICAL' ? 'r-crit' : klass === 'WARNING' ? 'r-warn' : 'r-safe';
    const klassColor = klass === 'CRITICAL' ? 'var(--crit)' : klass === 'WARNING' ? 'var(--warn)' : 'var(--good)';
    // MODE: just report influence count without the 0.5-ratio "전반 약화" magic
    tbody.appendChild(el('tr', { class: rowClass }, [
      el('td', { class: 'tl b' }, r.part_name),
      el('td', { class: 'tl' }, r.face),
      el('td', { class: 'num' }, r.x.toFixed(1)),
      el('td', { class: 'num' }, r.y.toFixed(1)),
      el('td', { class: 'tl', style: { color: klassColor } }, klass),
      el('td', { class: 'num b' }, fmt(r.g, 0)),
      el('td', { class: 'num' }, fmt(r.s, 1)),
      el('td', { class: 'num' }, r.e.toFixed(4)),
      el('td', { class: 'num' }, r.d.toFixed(3)),
      el('td', { class: 'num dim' }, cov.toFixed(2)),
      el('td', { class: 'num' }, inf + '/' + partRows.length),
      el('td', { class: 'tl dim' }, String(inf))
    ]));
  }
  document.getElementById('vCrit').textContent = nC;
  document.getElementById('vWarn').textContent = nW;
  document.getElementById('vSafe').textContent = nS;
}

function renderTSGrid() {
  const grid = document.getElementById('ts-grid');
  while (grid.firstChild) grid.removeChild(grid.firstChild);
  const top = RESULTS.slice().sort((a, b) => b.g - a.g).slice(0, 12);
  for (let i = 0; i < top.length; i++) {
    const r = top[i];
    const div = el('div', { class: 'ts-mini' }, [
      el('div', { class: 'tlabel' }, [
        el('span', null, r.face + ' · ' + r.part_name.split('\\').pop()),
        el('span', null, fmt(r.s, 1) + (_u('stress') ? ' ' + _u('stress') : ''))
      ])
    ]);
    const s = svg('svg', { viewBox: '0 0 200 64', preserveAspectRatio: 'none' });
    // Real stress time-series from PairResult.stress_ts. When absent, render
    // an explicit placeholder rather than a synthetic Gaussian.
    const ts = r.stress_ts || {};
    const times = Array.isArray(ts.times) ? ts.times : [];
    const vals = Array.isArray(ts.max_values) ? ts.max_values : [];
    if (!times.length || times.length !== vals.length) {
      const t = svg('text', {
        x: 100, y: 36, 'text-anchor': 'middle',
        fill: '#5c6383', 'font-size': 9,
      });
      t.appendChild(document.createTextNode('no time-series'));
      s.appendChild(t);
    } else {
      const tMin = times[0], tMax = times[times.length - 1] || tMin + 1;
      const vMax = Math.max.apply(null, vals.map(Math.abs)) || 1;
      const pts = times.map((tv, k) => [
        ((tv - tMin) / (tMax - tMin)) * 200,
        60 - (Math.abs(vals[k]) / vMax) * 50,
      ]);
      s.appendChild(svg('polyline', {
        points: pts.map(p => p.join(',')).join(' '),
        fill: 'none', stroke: '#ff3854', 'stroke-width': 1.4,
      }));
    }
    div.appendChild(s);
    grid.appendChild(div);
  }
}

function renderFindings() {
  const ul = document.getElementById('findings-list');
  while (ul.firstChild) ul.removeChild(ul.firstChild);
  let items = DATA.findings || [];
  if (!items.length) {
    const k = DATA.kpi;
    items = [
      { severity: 'CRITICAL', title: '가장 위험한 셀', detail: k.worst.face + ' (' + k.worst.x.toFixed(1) + ', ' + k.worst.y.toFixed(1) + ') — ' + k.worst.part_name + ' @ ' + fmt(k.worst.g, 0) + ' G', recommendation: '해당 영역에 완충재/보강 구조 검토' },
      { severity: 'WARNING', title: 'Critical pairs', detail: k.n_critical + '개 페어가 임계치 이상으로 응답', recommendation: '다중 페어 영향 부품 우선 보강' },
      (k.diss_pct != null
        ? { severity: 'INFO', title: 'Energy dissipation', detail: '초기 KE의 ' + k.diss_pct.toFixed(1) + '%만 소산', recommendation: '소산 효율이 낮은 페이스에 완충 패드 추가' }
        : { severity: 'INFO', title: 'Energy dissipation', detail: '측정 불가 (energy_flow 데이터 없음)', recommendation: 'binout 의 glstat 파싱 모듈 추가 권장' })
    ];
  }
  for (const f of items.slice(0, 6)) {
    const color = f.severity === 'CRITICAL' ? 'var(--crit)' : f.severity === 'WARNING' ? 'var(--warn)' : 'var(--accent)';
    const li = el('li', {
      style: { padding: '8px 0', borderBottom: '1px solid var(--line)', display: 'grid', gridTemplateColumns: '12px 1fr', gap: '8px' }
    }, [
      el('span', { style: { color: color, fontWeight: 700 } }, '■'),
      el('div', null, [
        el('div', { style: { color: 'var(--fg)', fontWeight: 600 } }, f.title),
        el('div', { style: { color: 'var(--fg2)', marginTop: '2px' } }, f.detail),
        el('div', { style: { color: 'var(--dim)', marginTop: '3px', fontStyle: 'italic' } }, '→ ' + f.recommendation)
      ])
    ]);
    ul.appendChild(li);
  }
}

function _pickFlow() {
  const flows = DATA.energy_flows || {};
  const keys = Object.keys(flows);
  if (!keys.length) return null;
  return flows[keys[0]];
}

const EG = { canvas: null, ctx: null, playing: false, t_idx: 0, t_max: 100, flow: null, nodes_pos: null };

function _layoutFlow(flow) {
  const depth = flow.depth_map || {};
  const byDepth = {};
  for (const n of flow.nodes) {
    const d = depth[n.id] != null ? depth[n.id] : (n.is_impactor ? 0 : 99);
    (byDepth[d] = byDepth[d] || []).push(n);
  }
  const depths = Object.keys(byDepth).map(Number).sort((a, b) => a - b);
  const pos = {};
  for (const d of depths) {
    const list = byDepth[d];
    if (d === 0) {
      for (const n of list) pos[n.id] = { x: 0, y: 0 };
    } else {
      const R = 70 + d * 70;
      for (let i = 0; i < list.length; i++) {
        const ang = (2 * Math.PI * i) / list.length + d * 0.3;
        pos[list[i].id] = { x: R * Math.cos(ang), y: R * Math.sin(ang) };
      }
    }
  }
  return pos;
}

function initEnergyGraph() {
  const flow = _pickFlow();
  if (!flow) return;
  EG.flow = flow;
  EG.canvas = document.getElementById('eg-canvas');
  if (!EG.canvas) return;
  const dpr = window.devicePixelRatio || 1;
  function resize() {
    const rect = EG.canvas.getBoundingClientRect();
    EG.canvas.width = rect.width * dpr;
    EG.canvas.height = rect.height * dpr;
    EG.ctx = EG.canvas.getContext('2d');
    EG.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  resize();
  window.addEventListener('resize', () => { resize(); renderEG(); });
  EG.t_max = (flow.nodes[0] && flow.nodes[0].t ? flow.nodes[0].t.length : 101) - 1;
  EG.t_idx = 0;
  EG.nodes_pos = _layoutFlow(flow);
  const _eft = DATA.energy_flow_thresholds || { engage_ratio: 0.05, active_ratio: 0.001 };
  for (const e of flow.edges) {
    let idx = -1;
    const thr = Math.max(1, (e.peak_f || 1) * _eft.engage_ratio);
    for (let i = 0; i < e.f.length; i++) if (e.f[i] > thr) { idx = i; break; }
    e.first_engage_idx = idx < 0 ? e.t.length - 1 : idx;
  }
  const scrub = document.getElementById('eg-scrub');
  scrub.max = EG.t_max;
  scrub.value = 0;
  scrub.addEventListener('input', function () { EG.t_idx = +scrub.value; renderEG(); });
  document.getElementById('eg-play').addEventListener('click', function () {
    EG.playing = !EG.playing;
    document.getElementById('eg-play').innerHTML = EG.playing ? '❚❚ PAUSE' : '▶ PLAY';
    if (EG.playing) loopEG();
  });
  document.getElementById('eg-reset').addEventListener('click', function () {
    EG.playing = false;
    EG.t_idx = 0;
    scrub.value = 0;
    document.getElementById('eg-play').innerHTML = '▶ PLAY';
    renderEG();
  });
  EG.canvas.addEventListener('mousemove', function (ev) {
    const rect = EG.canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    // Convert screen-space mouse to the world coords used by renderEG (the
    // pre-transform CSS-pixel coord space). Mirrors the (tx/dpr, scale) applied
    // in renderEG so hover hit-tests track the visible nodes after zoom/pan.
    const sx = (ev.clientX - rect.left) * (EG.canvas.width / rect.width) / dpr;
    const sy = (ev.clientY - rect.top) * (EG.canvas.height / rect.height) / dpr;
    const tr = EG.transform || { tx: 0, ty: 0, scale: 1 };
    const mx = (sx - tr.tx / dpr) / tr.scale;
    const my = (sy - tr.ty / dpr) / tr.scale;
    const W = EG.canvas.width / dpr;
    const H = EG.canvas.height / dpr;
    const cx = W / 2, cy = H / 2;
    let hit = null;
    for (const n of flow.nodes) {
      const p = EG.nodes_pos[n.id];
      const x = cx + p.x, y = cy + p.y;
      const r = 8 + Math.min(24, (n.ie[EG.t_idx] || 0) * 0.4);
      if ((mx - x) * (mx - x) + (my - y) * (my - y) <= r * r) { hit = n; break; }
    }
    const side = document.getElementById('eg-side');
    if (hit) {
      while (side.firstChild) side.removeChild(side.firstChild);
      side.appendChild(el('div', { class: 'ttl' }, hit.name));
      side.appendChild(el('div', { class: 'row' }, [el('span', null, 'IE(t)'), el('b', null, fmt(hit.ie[EG.t_idx] || 0, 3))]));
      side.appendChild(el('div', { class: 'row' }, [el('span', null, 'KE(t)'), el('b', null, fmt(hit.ke[EG.t_idx] || 0, 3))]));
      side.appendChild(el('div', { class: 'row' }, [el('span', null, 'depth'), el('b', null, String(flow.depth_map[hit.id] != null ? flow.depth_map[hit.id] : '-'))]));
      side.classList.add('show');
    } else {
      side.classList.remove('show');
    }
  });
  EG.canvas.addEventListener('mouseleave', () => document.getElementById('eg-side').classList.remove('show'));
  // Attach zoom/pan. The controller exposes the live transform via getState();
  // renderEG reads EG.transform on every frame so the animation loop and scrub
  // input stay in sync with user-driven zoom/pan.
  EG.transform = { tx: 0, ty: 0, scale: 1 };
  EG.zp = canvasZoomPan(EG.canvas, { draw: (ctx, t) => { EG.transform = t; renderEG(); } });
  renderEG();
}

function loopEG() {
  if (!EG.playing) return;
  EG.t_idx = (EG.t_idx + 1) % (EG.t_max + 1);
  document.getElementById('eg-scrub').value = EG.t_idx;
  renderEG();
  requestAnimationFrame(loopEG);
}

function renderEG() {
  const ctx = EG.ctx;
  if (!ctx) return;
  const dpr = window.devicePixelRatio || 1;
  const W = EG.canvas.width / dpr;
  const H = EG.canvas.height / dpr;
  // Background stays in screen space (no transform) so panning doesn't tile it.
  ctx.fillStyle = '#1a1e2e';
  ctx.fillRect(0, 0, W, H);
  // Apply user zoom/pan to the graph contents. canvasZoomPan operates on canvas
  // pixel coords; renderEG draws in CSS-pixel space (dpr already baked into the
  // base transform), so divide tx/ty by dpr to keep the math consistent.
  const tr = EG.transform || { tx: 0, ty: 0, scale: 1 };
  ctx.save();
  ctx.translate(tr.tx / dpr, tr.ty / dpr);
  ctx.scale(tr.scale, tr.scale);
  const cx = W / 2, cy = H / 2;
  const flow = EG.flow;
  const ti = EG.t_idx;
  const t_val = (flow.nodes[0] && flow.nodes[0].t) ? (flow.nodes[0].t[ti] || 0) : 0;
  document.getElementById('eg-t').textContent = (t_val * 1000).toFixed(3);
  ctx.strokeStyle = 'rgba(255,255,255,0.04)';
  for (let d = 1; d <= 3; d++) {
    ctx.beginPath();
    ctx.arc(cx, cy, 70 + d * 70, 0, 2 * Math.PI);
    ctx.stroke();
  }
  let maxImp = 0;
  for (const e of flow.edges) {
    const v = e.imp[ti] || 0;
    if (v > maxImp) maxImp = v;
  }
  const _eft2 = DATA.energy_flow_thresholds || { engage_ratio: 0.05, active_ratio: 0.001 };
  for (const e of flow.edges) {
    const p1 = EG.nodes_pos[e.src], p2 = EG.nodes_pos[e.dst];
    if (!p1 || !p2) continue;
    const x1 = cx + p1.x, y1 = cy + p1.y, x2 = cx + p2.x, y2 = cy + p2.y;
    const imp = e.imp[ti] || 0;
    const active = (e.f[ti] || 0) > _eft2.active_ratio * (e.peak_f || 1);
    const w = 0.4 + 4.5 * (imp / Math.max(1e-9, maxImp));
    ctx.strokeStyle = active ? 'rgba(77,214,255,0.85)' : 'rgba(180,110,255,0.35)';
    ctx.lineWidth = w;
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();
    if (active) {
      const phase = (Date.now() / 350 + e.cid * 0.7) % 1;
      const px = x1 + (x2 - x1) * phase;
      const py = y1 + (y2 - y1) * phase;
      ctx.fillStyle = '#ffffff';
      ctx.beginPath();
      ctx.arc(px, py, 2.4, 0, 2 * Math.PI);
      ctx.fill();
    }
  }
  // Derive per-node radius coefficients from the data: scale so that the
  // node with the largest IE at the final state ends near r ≈ 28.
  let _ieMaxLocal = 0, _keMaxLocal = 0;
  for (const _n of flow.nodes) {
    for (const _v of (_n.ie || [])) if (_v > _ieMaxLocal) _ieMaxLocal = _v;
    if (_n.is_impactor) for (const _v of (_n.ke || [])) if (_v > _keMaxLocal) _keMaxLocal = _v;
  }
  const _ieCoef = _ieMaxLocal > 0 ? (20 / _ieMaxLocal) : 0;
  const _keCoef = _keMaxLocal > 0 ? (8  / _keMaxLocal) : 0;
  const _ieNorm = (DATA.energy_flow_max_ie && DATA.energy_flow_max_ie > 0) ? DATA.energy_flow_max_ie : (_ieMaxLocal || 1);
  for (const n of flow.nodes) {
    const p = EG.nodes_pos[n.id];
    if (!p) continue;
    const x = cx + p.x, y = cy + p.y;
    const ie = n.ie[ti] || 0;
    const ke = n.ke[ti] || 0;
    const r = 8 + Math.min(28, ie * _ieCoef + (n.is_impactor ? ke * _keCoef : 0));
    const t01 = Math.max(0, Math.min(1, ie / _ieNorm));
    ctx.fillStyle = n.is_impactor ? '#b46eff' : gColor(t01);
    ctx.beginPath();
    ctx.arc(x, y, r, 0, 2 * Math.PI);
    ctx.fill();
    const hasActive = flow.edges.some(e => (e.src === n.id || e.dst === n.id) && (e.f[ti] || 0) > _eft2.active_ratio * (e.peak_f || 1));
    if (hasActive) {
      const pulse = 0.6 + 0.4 * Math.sin(Date.now() / 200);
      ctx.strokeStyle = 'rgba(77,214,255,' + pulse + ')';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(x, y, r + 4, 0, 2 * Math.PI);
      ctx.stroke();
    }
    ctx.fillStyle = '#e6ebff';
    ctx.font = '10px "JetBrains Mono", monospace';
    ctx.textAlign = 'center';
    ctx.fillText(n.name, x, y + r + 12);
  }
  ctx.restore();
}

function initSunburst() {
  const flow = _pickFlow();
  const root = document.getElementById('sunburst-svg');
  while (root.firstChild) root.removeChild(root.firstChild);
  if (!flow) return;
  const cx = 180, cy = 170;
  const r0 = 30, r1 = 80, r2 = 130;
  const ke_init = flow.ke_init || 1;
  root.appendChild(svg('circle', { cx: cx, cy: cy, r: r0, fill: '#b46eff' }));
  const lbl1 = svg('text', { x: cx, y: cy - 2, 'text-anchor': 'middle', fill: '#fff', 'font-size': 10, 'font-weight': 700, 'font-family': 'JetBrains Mono' });
  lbl1.appendChild(document.createTextNode('KE0'));
  root.appendChild(lbl1);
  const lbl2 = svg('text', { x: cx, y: cy + 12, 'text-anchor': 'middle', fill: '#fff', 'font-size': 9, 'font-family': 'JetBrains Mono' });
  lbl2.appendChild(document.createTextNode(fmt(ke_init, 1) + ' J'));
  root.appendChild(lbl2);
  const T = (flow.nodes[0] && flow.nodes[0].t ? flow.nodes[0].t.length : 1) - 1;
  const ie_total = flow.nodes.filter(n => !n.is_impactor).reduce((a, n) => a + (n.ie[T] || 0), 0);
  const ke_left = flow.nodes.reduce((a, n) => a + (n.ke[T] || 0), 0);
  const diss = Math.max(0, ke_init - ie_total - ke_left);
  const segs1 = [
    { label: 'IE', val: ie_total, color: '#4dd6ff' },
    { label: 'diss', val: diss, color: '#f0a830' },
    { label: 'KE_n', val: Math.max(0, ke_left), color: '#4adfa1' }
  ];
  let acc = -Math.PI / 2;
  const total1 = segs1.reduce((a, s) => a + s.val, 0) || 1;
  for (const s of segs1) {
    const ang = 2 * Math.PI * s.val / total1;
    if (ang <= 0) { acc += ang; continue; }
    const x1 = cx + r0 * Math.cos(acc), y1 = cy + r0 * Math.sin(acc);
    const x2 = cx + r1 * Math.cos(acc), y2 = cy + r1 * Math.sin(acc);
    const x3 = cx + r1 * Math.cos(acc + ang), y3 = cy + r1 * Math.sin(acc + ang);
    const x4 = cx + r0 * Math.cos(acc + ang), y4 = cy + r0 * Math.sin(acc + ang);
    const large = ang > Math.PI ? 1 : 0;
    const d = 'M' + x1 + ',' + y1 + ' L' + x2 + ',' + y2 + ' A' + r1 + ',' + r1 + ' 0 ' + large + ' 1 ' + x3 + ',' + y3 + ' L' + x4 + ',' + y4 + ' A' + r0 + ',' + r0 + ' 0 ' + large + ' 0 ' + x1 + ',' + y1 + ' Z';
    const path = svg('path', { d: d, fill: s.color, opacity: 0.85, stroke: '#0a0c14', 'stroke-width': 1 });
    const title = svg('title', {});
    title.appendChild(document.createTextNode(s.label + ': ' + fmt(s.val, 2) + ' J (' + (100 * s.val / total1).toFixed(1) + '%)'));
    path.appendChild(title);
    root.appendChild(path);
    const mid = acc + ang / 2;
    const lx = cx + ((r0 + r1) / 2) * Math.cos(mid);
    const ly = cy + ((r0 + r1) / 2) * Math.sin(mid);
    const lab = svg('text', { x: lx, y: ly + 3, 'text-anchor': 'middle', fill: '#0a0c14', 'font-size': 9, 'font-weight': 700, 'font-family': 'JetBrains Mono' });
    lab.appendChild(document.createTextNode(s.label));
    root.appendChild(lab);
    acc += ang;
  }
  const parts = flow.nodes.filter(n => !n.is_impactor);
  const ie_vals = parts.map(p => ({ name: p.name, v: p.ie[T] || 0 }));
  const total2 = ie_vals.reduce((a, p) => a + p.v, 0) || 1;
  acc = -Math.PI / 2;
  for (let i = 0; i < ie_vals.length; i++) {
    const p = ie_vals[i];
    const ang = 2 * Math.PI * p.v / total2;
    if (ang <= 0) { acc += ang; continue; }
    const x1 = cx + r1 * Math.cos(acc), y1 = cy + r1 * Math.sin(acc);
    const x2 = cx + r2 * Math.cos(acc), y2 = cy + r2 * Math.sin(acc);
    const x3 = cx + r2 * Math.cos(acc + ang), y3 = cy + r2 * Math.sin(acc + ang);
    const x4 = cx + r1 * Math.cos(acc + ang), y4 = cy + r1 * Math.sin(acc + ang);
    const large = ang > Math.PI ? 1 : 0;
    const d = 'M' + x1 + ',' + y1 + ' L' + x2 + ',' + y2 + ' A' + r2 + ',' + r2 + ' 0 ' + large + ' 1 ' + x3 + ',' + y3 + ' L' + x4 + ',' + y4 + ' A' + r1 + ',' + r1 + ' 0 ' + large + ' 0 ' + x1 + ',' + y1 + ' Z';
    const t = i / Math.max(1, ie_vals.length - 1);
    const path = svg('path', { d: d, fill: gColor(t), opacity: 0.78, stroke: '#0a0c14', 'stroke-width': 0.8 });
    const title = svg('title', {});
    title.appendChild(document.createTextNode(p.name + ': ' + fmt(p.v, 2) + ' J (' + (100 * p.v / total2).toFixed(1) + '%)'));
    path.appendChild(title);
    root.appendChild(path);
    if (ang > 0.25) {
      const mid = acc + ang / 2;
      const lx = cx + ((r1 + r2) / 2) * Math.cos(mid);
      const ly = cy + ((r1 + r2) / 2) * Math.sin(mid);
      const lab = svg('text', { x: lx, y: ly + 3, 'text-anchor': 'middle', fill: '#0a0c14', 'font-size': 8.5, 'font-weight': 700, 'font-family': 'JetBrains Mono' });
      lab.appendChild(document.createTextNode(p.name.split('\\').pop()));
      root.appendChild(lab);
    }
    acc += ang;
  }
}

function initSankey() {
  const flow = _pickFlow();
  const wrap = document.getElementById('sankey-rows');
  while (wrap.firstChild) wrap.removeChild(wrap.firstChild);
  if (!flow) return;
  const sorted = flow.edges.slice().sort((a, b) => (a.first_engage_idx || 0) - (b.first_engage_idx || 0));
  let maxW = 0; for (const e of sorted) if (e.total_w > maxW) maxW = e.total_w;
  for (const e of sorted) {
    const w = maxW > 0 ? e.total_w / maxW : 0;
    const srcNode = flow.nodes.find(n => n.id === e.src);
    const dstNode = flow.nodes.find(n => n.id === e.dst);
    const srcName = srcNode ? srcNode.name : e.src;
    const dstName = dstNode ? dstNode.name : e.dst;
    const row = el('div', { class: 'sankey-row' }, [
      el('div', { class: 'src' }, srcName),
      el('div', { class: 'bar', style: { width: (4 + w * 96) + '%' } }),
      el('div', { class: 'dst' }, '→ ' + dstName),
      el('div', { class: 'val' }, fmt(e.total_w, 2))
    ]);
    wrap.appendChild(row);
  }
}

function initTimeForceHeatmap() {
  const flow = _pickFlow();
  const wrap = document.getElementById('tfh-rows');
  while (wrap.firstChild) wrap.removeChild(wrap.firstChild);
  if (!flow) return;
  const sorted = flow.edges.slice().sort((a, b) => (a.first_engage_idx || 0) - (b.first_engage_idx || 0));
  let mxF = 0;
  for (const e of flow.edges) for (const v of e.f) if (v > mxF) mxF = v;
  const NBINS = 21;
  for (const e of sorted) {
    const T = e.t.length;
    const row = el('div', { class: 'tfh-row' });
    const srcNode = flow.nodes.find(n => n.id === e.src);
    const dstNode = flow.nodes.find(n => n.id === e.dst);
    const srcName = srcNode ? srcNode.name : e.src;
    const dstName = dstNode ? dstNode.name : e.dst;
    row.appendChild(el('div', { class: 'lab', title: srcName + ' → ' + dstName },
      srcName.split('\\').pop().slice(0, 6) + '→' + dstName.split('\\').pop().slice(0, 6)));
    for (let b = 0; b < NBINS; b++) {
      const i0 = Math.floor(b * T / NBINS);
      const i1 = Math.floor((b + 1) * T / NBINS);
      let m = 0;
      for (let i = i0; i < i1; i++) { if (e.f[i] > m) m = e.f[i]; }
      const tt = (i0 / T * (e.t[T - 1] || 1) * 1000).toFixed(3);
      const cell = el('div', { class: 'cell',
        style: { background: m > 0 ? gColor(m / Math.max(1, mxF)) : 'rgba(255,255,255,0.04)' },
        title: tt + ' ms · |F|=' + fmt(m, 0)
      });
      row.appendChild(cell);
    }
    wrap.appendChild(row);
  }
}

function initConservation() {
  const flow = _pickFlow();
  if (!flow) return;
  const T = (flow.nodes[0] && flow.nodes[0].t ? flow.nodes[0].t.length : 1) - 1;
  const ke_init = flow.ke_init || 0;
  const ie_total = flow.nodes.filter(n => !n.is_impactor).reduce((a, n) => a + (n.ie[T] || 0), 0);
  const ke_left = flow.nodes.reduce((a, n) => a + (n.ke[T] || 0), 0);
  const diss = Math.max(0, ke_init - ie_total - ke_left);
  const residual_pct = ke_init > 0 ? Math.abs(ke_init - ie_total - ke_left - diss) / ke_init * 100 : 0;
  document.getElementById('consKE').textContent = fmt(ke_init, 2);
  document.getElementById('consIE').textContent = fmt(ie_total, 2);
  document.getElementById('consDISS').textContent = fmt(diss, 2);
  document.getElementById('consRES').textContent = residual_pct.toFixed(2) + ' %';
  const bar = document.getElementById('consBar');
  while (bar.firstChild) bar.removeChild(bar.firstChild);
  const total = (ie_total + diss + ke_left) || 1;
  const segs = [
    { v: ie_total, c: '#4dd6ff' },
    { v: diss, c: '#f0a830' },
    { v: ke_left, c: '#4adfa1' }
  ];
  for (const s of segs) bar.appendChild(el('div', { class: 'seg', style: { width: (100 * s.v / total) + '%', background: s.c } }));
  // Conservation-tolerance check: only run when payload provides an explicit
  // tolerance percent. None → no banner (don't silently invent a 5% rule).
  const _tol = DATA.energy_conservation_tolerance;
  const banner = document.getElementById('consBanner');
  if (_tol != null && residual_pct > _tol) {
    if (banner) {
      banner.classList.add('on');
      banner.textContent = '⚠ Residual > ' + _tol + '% — energy conservation suspect';
    }
    document.getElementById('consResCell').classList.add('warn');
  } else if (banner) {
    banner.classList.remove('on');
  }
}

"""
