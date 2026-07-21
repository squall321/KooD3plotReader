# 섹션 01 — OVERVIEW 히어로 + KPI HTML 템플릿 (기계적 분할, 바이트 불변)

_PAGE1 = """
<section class="page" id="s1">
  <div class="hero-line r">
    <div>
      <div class="page-head" style="margin-bottom:6px;border:none;padding:0">
        <span class="num">01</span><span class="tagline">METHOD &middot; OVERVIEW</span>
      </div>
      <h1>전위치 부분충격 &mdash; <span class="acc">Multi-Face Pair-wise 해석</span></h1>
      <!-- data-quality 배지 (JS 가 채움) — synthetic geometry / mock-blocked energy 등 -->
      <div id="data-quality-badges" style="margin:6px 0 8px 0;display:flex;gap:6px;flex-wrap:wrap"></div>
      <div class="lede">
        Cuboid-26 표준 자세 중 <b id="kHeroFaces">__N_FACES__</b>개 면 &times; XY 격자
        <b id="kHeroPos">__N_POSITIONS__</b> 위치 &times; <b id="kHeroParts">__N_PARTS__</b> 부품(임팩터 포함)
        = <b id="kHeroPairs">__N_PAIRS__</b> 페어. 임팩터 운동에너지가 어디로 흘러가는지
        실시간 그래프로 추적합니다.
        <span id="heroValidRuns" style="display:block;margin-top:4px"></span>
      </div>
    </div>
    <div class="right">
      <div class="pk">&#9650; WORST CELL</div>
      <div class="pkv" id="heroWorstCoord">__WORST_LINE__</div>
      <div class="pkv" id="heroWorstPart" style="color:var(--crit)">__WORST_PART_LINE__</div>
    </div>
  </div>

  <div class="grid g-12 r method-band" style="margin-bottom:12px">
    <div class="panel" style="grid-column:span 3;padding:10px 12px;margin:0">
      <div class="band-head"><span>IMPACTOR</span><span class="band-sub" id="impSubLabel">__IMP_SUB__</span></div>
      <svg id="impactor-svg" viewBox="0 0 200 110" preserveAspectRatio="xMidYMid meet" style="width:100%;height:110px"></svg>
      <table class="dt" style="margin-top:6px;font-size:10px">
        <tbody id="impactor-tbl"></tbody>
      </table>
      <div class="band-cap" id="impCap">자유낙하 KE = &frac12; m v&sup2;.</div>
    </div>

    <div class="panel" style="grid-column:span 3;padding:10px 12px;margin:0">
      <div class="band-head"><span>BI-FACE OVERVIEW</span><span class="band-sub">front · back</span></div>
      <div class="biface-grid" id="biface-mini" style="grid-template-columns:1fr 1fr;gap:6px"></div>
      <div class="band-cap">자유낙하 정면(F2)과 배면(F1) 충돌 위치 위험도. 클릭 시 INSPECTOR로 점프.</div>
    </div>

    <div class="panel" style="grid-column:span 3;padding:10px 12px;margin:0">
      <div class="band-head"><span>DOE</span><span class="band-sub" id="doeSubLabel">grid &middot; per-face</span></div>
      <table class="dt" style="font-size:10px">
        <tbody id="doe-breakdown"></tbody>
      </table>
      <div class="band-cap" id="doeCap">자세별 격자 위치 수 &middot; generation mode</div>
    </div>

    <div class="panel" style="grid-column:span 3;padding:10px 12px;margin:0">
      <div class="band-head"><span>PIPELINE</span><span class="band-sub" style="color:var(--tag)">scenario &rarr; report</span></div>
      <svg viewBox="0 0 380 92" preserveAspectRatio="xMidYMid meet" style="width:100%;height:92px">
        <defs>
          <marker id="arr2" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
            <path d="M0,0 L10,5 L0,10 Z" fill="#4dd6ff"/>
          </marker>
        </defs>
        <g font-family="Inter,system-ui" font-size="9" fill="#e6ebff">
          <g transform="translate(2,22)">
            <rect width="64" height="48" rx="4" fill="#1a1e2e" stroke="#4dd6ff" stroke-width="0.8"/>
            <text x="32" y="14" text-anchor="middle" fill="#4dd6ff" font-size="7" letter-spacing="1">SCENARIO</text>
            <text x="32" y="28" text-anchor="middle" font-weight="600" font-size="9">DOE</text>
            <text x="32" y="40" text-anchor="middle" font-size="7" fill="#5c6383">grid/lhs</text>
          </g>
          <line x1="68" y1="46" x2="80" y2="46" stroke="#4dd6ff" stroke-width="1" marker-end="url(#arr2)"/>
          <g transform="translate(82,22)">
            <rect width="64" height="48" rx="4" fill="#1a1e2e" stroke="#b46eff" stroke-width="0.8"/>
            <text x="32" y="14" text-anchor="middle" fill="#b46eff" font-size="7" letter-spacing="1">PREPARE</text>
            <text x="32" y="28" text-anchor="middle" font-weight="600" font-size="9">DECOMP</text>
            <text x="32" y="40" text-anchor="middle" font-size="7" fill="#5c6383">contacts</text>
          </g>
          <line x1="148" y1="46" x2="160" y2="46" stroke="#4dd6ff" stroke-width="1" marker-end="url(#arr2)"/>
          <g transform="translate(162,22)">
            <rect width="64" height="48" rx="4" fill="#1a1e2e" stroke="#f0a830" stroke-width="0.8"/>
            <text x="32" y="14" text-anchor="middle" fill="#f0a830" font-size="7" letter-spacing="1">SOLVE</text>
            <text x="32" y="28" text-anchor="middle" font-weight="600" font-size="9">N runs</text>
            <text x="32" y="40" text-anchor="middle" font-size="7" fill="#5c6383">LS-DYNA</text>
          </g>
          <line x1="228" y1="46" x2="240" y2="46" stroke="#4dd6ff" stroke-width="1" marker-end="url(#arr2)"/>
          <g transform="translate(242,22)">
            <rect width="64" height="48" rx="4" fill="#1a1e2e" stroke="#4adfa1" stroke-width="0.8"/>
            <text x="32" y="14" text-anchor="middle" fill="#4adfa1" font-size="7" letter-spacing="1">COLLECT</text>
            <text x="32" y="28" text-anchor="middle" font-weight="600" font-size="9">binout</text>
            <text x="32" y="40" text-anchor="middle" font-size="7" fill="#5c6383">G/&sigma;/IE/F</text>
          </g>
          <line x1="308" y1="46" x2="320" y2="46" stroke="#4dd6ff" stroke-width="1" marker-end="url(#arr2)"/>
          <g transform="translate(322,22)">
            <rect width="56" height="48" rx="4" fill="#1a1e2e" stroke="#ff3854" stroke-width="0.8"/>
            <text x="28" y="14" text-anchor="middle" fill="#ff3854" font-size="7" letter-spacing="1">REPORT</text>
            <text x="28" y="28" text-anchor="middle" font-weight="600" font-size="9">HTML</text>
            <text x="28" y="40" text-anchor="middle" font-size="7" fill="#5c6383">single-file</text>
          </g>
        </g>
      </svg>
      <div class="band-cap">5단계 무손실 파이프라인. 원본 d3plot은 디스크 상주, 결과만 단일 HTML로.</div>
    </div>
  </div>

  <div class="kpi-strip r">
    <div class="k"><div class="v" id="kPositions">__N_POSITIONS__<span class="u">pos</span></div><div class="l">TOTAL POSITIONS</div></div>
    <div class="k"><div class="v" id="kFaces">__N_FACES__</div><div class="l">FACES</div></div>
    <div class="k"><div class="v" id="kParts">__N_PARTS__</div><div class="l">PARTS</div></div>
    <div class="k"><div class="v" id="kWorstG">__WORST_G__<span class="u">G</span></div><div class="l">WORST PEAK G</div><div class="cap" style="font-size:8px;letter-spacing:0.3px;color:var(--dim);margin-top:2px" title="LSDYNA 의 element 별 nodal acceleration 의 max — mesh 거칠기/contact penalty 의 영향을 받는 raw 값. 디바이스 평균이 아님.">element-local peak</div></div>
    <div class="k"><div class="v" id="kWorstS">__WORST_S__<span class="u" id="kWorstSUnit"></span></div><div class="l">WORST STRESS</div><div class="cap" style="font-size:8px;letter-spacing:0.3px;color:var(--dim);margin-top:2px" title="element 별 stress 의 global max — mesh 거칠기 영향을 받는 raw 값. 평균 아님.">element-local peak</div></div>
    <div class="k"><div class="v" id="kCritPairs">__N_CRIT__</div><div class="l">CRITICAL PAIRS</div></div>
    <div class="k"><div class="v" id="kSafePos">__N_SAFE__</div><div class="l">SAFE POSITIONS</div><div class="cap" id="kSafeCap" style="font-size:8px;letter-spacing:0.3px;color:var(--dim);margin-top:2px"></div></div>
    <div class="k"><div class="v" id="kDiss">__DISS_PCT__<span class="u">%</span></div><div class="l">ENERGY DISSIPATED</div></div>
  </div>

  <div class="grid g-12" style="margin-top:14px">
    <div class="panel col-7 r">
      <div class="ph">
        <span class="pt">BI-FACE RISK MAPS</span>
        <span class="pd">front (F2) vs back (F1) &middot; impact-position colored by max response</span>
      </div>
      <div class="biface-grid" id="biface-split"></div>
      <div class="pcap">
        한 점 = 한 임팩트 위치. 색상 = 그 위치에서 모든 부품 중 최대 Peak G.
        ★ = 최악 셀. 클릭 시 INSPECTOR로 점프.
      </div>
    </div>

    <div class="panel col-5 r">
      <div class="ph">
        <span class="pt">PER-FACE KPI</span>
        <span class="pd">n &middot; max G &middot; worst (x,y) &middot; driver &middot; risk score &middot; &Delta;</span>
      </div>
      <table class="dt" id="face-kpi-tbl">
        <thead>
          <tr><th class="tl">FACE</th><th>n</th><th>MAX G</th><th>WORST (X,Y)</th><th class="tl">DRIVER</th><th>SCORE</th><th>vs OTHER</th></tr>
        </thead>
        <tbody></tbody>
      </table>
      <div class="pcap" id="face-kpi-cap">
        SCORE column shown only when payload.risk_score config is provided.
        &Delta; = SCORE - other face's SCORE.
      </div>
    </div>

    <div class="panel col-12 r">
      <div class="ph">
        <span class="pt">BOUNCE VECTOR MAP &middot; impactor fate per XY position</span>
        <span class="pd">arrow tail = impact &middot; arrow dir = rebound XY &middot; color = behavior class</span>
      </div>
      <div class="bvm-grid" id="bvm-grid"></div>
      <div class="bvm-legend" id="bvm-legend"></div>
      <div class="pcap">
        탄성 반사(bounce)는 녹색, 부분 반발(rebound) 노랑, 미끄러짐(slide) 주황, 박힘(embed) 빨강,
        접촉 미검출(no-contact)은 회색 — 회색 위치는 임팩터가 디바이스에 닿지 않은 런입니다.
        한눈에 어떤 영역이 임팩터를 튕겨내고 어디가 흡수하는지 보여줍니다.
      </div>
    </div>

    <div class="panel col-12 r">
      <div class="ph">
        <span class="pt">TRAJECTORY CLUSTERING MAP</span>
        <span class="pd">k-means archetypes &middot; positions colored by cluster &middot; sparkline = KE decay prototype</span>
      </div>
      <div class="bvm-grid" id="tcm-grid"></div>
      <div class="tcm-archetypes" id="tcm-archetypes"></div>
      <div class="pcap">
        클러스터링은 KE retention, max penetration, rebound speed, behavior class 기반으로 임팩터의 거동 archetypes를 학습.
        같은 클러스터 위치는 동일한 거동 패턴을 보입니다.
      </div>
    </div>

    <div class="panel col-12 r">
      <div class="ph">
        <span class="pt">TOP-K WORST PAIRS</span>
        <span class="pd">rank / face / position / part / response</span>
      </div>
      <table class="dt" id="topk-tbl">
        <thead>
          <tr><th class="tl">RANK</th><th class="tl">FACE</th><th>X<span id="topkXUnit"></span></th><th>Y<span id="topkYUnit"></span></th><th class="tl">PART</th><th>PEAK G</th><th>&sigma;<span id="topkSUnit"></span></th><th>INFLUENCE AREA</th></tr>
        </thead>
        <tbody></tbody>
      </table>
    </div>
  </div>
</section>
"""


_JS_S1 = r"""function fillHeroKpi() {
  const k = DATA.kpi;
  // s1 -> s9 크로스링크 (P6): worst KPI/히어로 클릭 -> 해당 위치 드릴다운
  const _worstPos = (k.worst && k.worst.pos_id) ||
    ((DATA.doe_analysis && DATA.doe_analysis.worst_position) ? DATA.doe_analysis.worst_position.pos_id : null);
  // C1: 유효 접촉 런 수를 hover 배지가 아닌 본문으로 승격
  (function () {
    const sqSum = (DATA.solver_quality && DATA.solver_quality.summary) || null;
    const host = document.getElementById('heroValidRuns');
    if (!host || !sqSum || !sqSum.n) return;
    const vis = sqSum.impact_visible_count;
    if (vis != null && vis < sqSum.n) {
      host.innerHTML = '유효 접촉 런 <b style="color:var(--crit)">' + vis + '/' + sqSum.n +
        '</b> — 나머지 ' + (sqSum.n - vis) + '런은 glstat 창에서 접촉 미검출 (FINDINGS 참조).';
    } else if (sqSum.fail > 0) {
      host.innerHTML = '에너지 균형 FAIL <b style="color:var(--crit)">' + sqSum.fail + '/' + sqSum.n + '</b> 런 — 수치는 잠정치 (FINDINGS 참조).';
    }
  })();
  // H5-4: 설계 한계 제공 시 — WORST G 기준 출처 + WORST STRESS 한계 초과 표시
  (function () {
    const k2 = DATA.kpi || {};
    if (k2.crit_basis === 'user') {
      const tile = document.getElementById('kWorstG');
      const capHost = tile && tile.parentElement ? tile.parentElement.querySelector('.cap') : null;
      if (capHost) capHost.textContent = capHost.textContent.replace('element-local peak',
        'element-local peak · 기준: 설계 한계 ' + fmt(k2.crit_threshold / gDivisor(), 0) + ' G');
    }
    if (k2.stress_limit != null) {
      const sv = document.getElementById('kWorstS');
      const sCap = sv && sv.parentElement ? sv.parentElement.querySelector('.cap') : null;
      if (sCap) sCap.textContent = sCap.textContent + ' · 한계 ' + fmt(k2.stress_limit, 0) + ' ' + (_u('stress') || 'MPa');
      if (sv && (k2.worst_s || 0) > k2.stress_limit) sv.style.color = 'var(--crit)';
    }
  })();
  // C2 (QA): ENERGY DISSIPATED 가 FAIL 런들의 median 이면 각주
  (function () {
    const sqSum = (DATA.solver_quality && DATA.solver_quality.summary) || null;
    if (!sqSum) return;
    const vis = sqSum.impact_visible_count || 0;
    if (vis > 0 && sqSum.fail >= vis) {
      const tile = document.getElementById('kDiss');
      const host = tile && tile.parentElement ? tile.parentElement : null;
      if (host && !host.querySelector('.cap')) {
        const cap = document.createElement('div');
        cap.className = 'cap';
        cap.style.cssText = 'font-size:8px;letter-spacing:0.3px;color:var(--dim);margin-top:2px';
        cap.textContent = '⚠ 에너지 균형 FAIL 런 기반 — 잠정치';
        host.appendChild(cap);
      }
    }
  })();
  // C2: worst KPI 가 FAIL 런 유래면 타일 캡션에 각주
  (function () {
    const perPos = (DATA.solver_quality && DATA.solver_quality.per_position) || {};
    const wp = _worstPos && perPos[_worstPos];
    if (wp && wp.pass_fail === 'FAIL') {
      const tile = document.getElementById('kWorstG');
      const capHost = tile && tile.parentElement ? tile.parentElement.querySelector('.cap') : null;
      if (capHost) capHost.textContent = capHost.textContent + ' · ⚠ 에너지 균형 FAIL 런에서 관측';
    }
  })();
  if (_worstPos) {
    ['kWorstG', 'heroWorstPart', 'heroWorstCoord'].forEach(function (eid) {
      const n = document.getElementById(eid);
      if (!n) return;
      n.style.cursor = 'pointer';
      n.addEventListener('click', function () {
        if (typeof selectPosition === 'function') selectPosition(_worstPos, { source: 's1' });
      });
    });
  }
  // Acceleration→g divisor: matches the solver unit declared by the loader.
  // mm/s² → /9810, m/s² → /9.81 (= mm/ms²).
  const _gDiv = gDivisor();   // M11: 공용 헬퍼 단일 소스
  const _worstG_in_G = (k.worst_g || 0) / _gDiv;
  document.getElementById('kPositions').innerHTML = k.n_positions + '<span class="u">pos</span>';
  document.getElementById('kFaces').textContent = k.n_faces;
  document.getElementById('kParts').textContent = k.n_parts;
  document.getElementById('kWorstG').innerHTML = fmt(_worstG_in_G, 0) + '<span class="u">G</span>';
  document.getElementById('kWorstS').innerHTML = fmt(k.worst_s, 1) + '<span class="u">' + _u('stress') + '</span>';
  document.getElementById('kCritPairs').textContent = k.n_critical;
  document.getElementById('kSafePos').textContent = k.n_safe;
  // HIGH-1 (QA): 접촉 미검출 위치는 안전 판정에서 제외됐음을 명시
  (function () {
    const dz = (DATA.deep_analytics || {}).safe_drop_zone || {};
    const capEl = document.getElementById('kSafeCap');
    if (!capEl) return;
    if (k.n_safe_basis === 'safe_drop_zone') {
      capEl.textContent = (dz.no_contact_count > 0)
        ? ('접촉 런만 판정 — 미접촉 ' + dz.no_contact_count + '개 제외')
        : '기준: 안전 낙하 구역 지도와 동일';
    }
  })();
  // diss_pct=null → energy_flow 진짜 데이터 없음 (Mock 출고 차단 후). '—' 표시.
  document.getElementById('kDiss').innerHTML = (k.diss_pct != null)
    ? (k.diss_pct.toFixed(1) + '<span class="u">%</span>')
    : '<span style="opacity:0.5">—</span><span class="u" style="opacity:0.5" title="energy_flow 데이터 없음">N/A</span>';
  document.getElementById('kHeroFaces').textContent = k.n_faces;
  document.getElementById('kHeroPos').textContent = k.n_positions;
  document.getElementById('kHeroParts').textContent = k.n_parts;
  document.getElementById('kHeroPairs').textContent = k.n_pairs;
  document.getElementById('heroWorstCoord').textContent = k.worst.face + ' · X ' + k.worst.x.toFixed(1) + ' / Y ' + k.worst.y.toFixed(1);
  // _gDiv 가 위에서 acc unit 기반으로 결정됨 (mm/s²→9810, m/s²→9.81)
  document.getElementById('heroWorstPart').textContent = fmt((k.worst.g || 0) / _gDiv, 0) + ' G  ON  ' + k.worst.part_name;
}

function initImpactor() {
  const imp = DATA.meta.impactor;
  const svgRoot = document.getElementById('impactor-svg');
  const tbl = document.getElementById('impactor-tbl');
  const cap = document.getElementById('impCap');
  const sub = document.getElementById('impSubLabel');
  while (svgRoot.firstChild) svgRoot.removeChild(svgRoot.firstChild);
  while (tbl.firstChild) tbl.removeChild(tbl.firstChild);
  if (imp.type === 'Sphere') {
    sub.textContent = 'Sphere';
    svgRoot.appendChild(svg('circle', { cx: 100, cy: 55, r: 32, fill: 'none', stroke: '#4dd6ff', 'stroke-width': 1.2 }));
    svgRoot.appendChild(svg('circle', { cx: 100, cy: 55, r: 8, fill: 'none', stroke: '#4dd6ff', 'stroke-width': 0.6, 'stroke-dasharray': '2,2' }));
    svgRoot.appendChild(svg('line', { x1: 100, y1: 23, x2: 100, y2: 87, stroke: '#5c6383', 'stroke-width': 0.5, 'stroke-dasharray': '1,2' }));
    const t = svg('text', { x: 100, y: 102, 'text-anchor': 'middle', fill: '#4dd6ff', 'font-size': 10, 'font-family': 'JetBrains Mono' });
    t.appendChild(document.createTextNode('R=' + imp.radius.toFixed(2)));
    svgRoot.appendChild(t);
    const rows = [
      ['TYPE', 'Sphere'],
      ['R' + _uSuffix('disp'), imp.radius.toFixed(2)],
      ['h' + _uSuffix('disp'), imp.height.toFixed(1)],
      ['v0' + _uSuffix('vel'), fmt(imp.velocity, 0)],
      ['m' + _uSuffix('mass'), fmt(imp.mass, 4)],
      ['KE' + _uSuffix('energy'), fmt(imp.kinetic_energy, 2)]
    ];
    for (const r of rows) {
      tbl.appendChild(el('tr', null, [el('td', { class: 'tl dim' }, r[0]), el('td', { class: 'num b' }, r[1])]));
    }
    cap.textContent = 'KE = 1/2 m v² (free-fall v = sqrt(2gh))';
  } else if (imp.type === 'Cylinder') {
    sub.textContent = 'Cylinder · asymmetric';
    const fr = imp.front_radius || imp.radius || 12;
    const out = imp.outer_radius || fr * 1.4;
    const br = imp.back_radius || out;
    const fh = imp.front_height || 15;
    const bh = imp.back_height || 25;
    const cx = 100, cy = 55;
    const totalH = fh + bh;
    const sx = 90 / totalH;
    const sy = 40 / Math.max(fr, out, br);
    const x0 = cx - (fh + bh) * sx / 2;
    const x1 = x0 + fh * sx;
    const x2 = x1 + bh * sx;
    const ftop = cy - fr * sy, fbot = cy + fr * sy;
    const mtop = cy - out * sy, mbot = cy + out * sy;
    const btop = cy - br * sy,  bbot = cy + br * sy;
    svgRoot.appendChild(svg('polygon', {
      points: x0 + ',' + ftop + ' ' + x1 + ',' + mtop + ' ' + x1 + ',' + mbot + ' ' + x0 + ',' + fbot,
      fill: 'rgba(77,214,255,0.12)', stroke: '#4dd6ff', 'stroke-width': 1
    }));
    svgRoot.appendChild(svg('polygon', {
      points: x1 + ',' + mtop + ' ' + x2 + ',' + btop + ' ' + x2 + ',' + bbot + ' ' + x1 + ',' + mbot,
      fill: 'rgba(180,110,255,0.12)', stroke: '#b46eff', 'stroke-width': 1
    }));
    const lab1 = svg('text', { x: x0 - 4, y: cy + 4, fill: '#5c6383', 'font-size': 8, 'text-anchor': 'end' });
    lab1.appendChild(document.createTextNode('Rf=' + fr.toFixed(1)));
    svgRoot.appendChild(lab1);
    const lab2 = svg('text', { x: x2 + 4, y: cy + 4, fill: '#5c6383', 'font-size': 8 });
    lab2.appendChild(document.createTextNode('Rb=' + br.toFixed(1)));
    svgRoot.appendChild(lab2);
    const rows = [
      ['TYPE', 'Cylinder'],
      ['Rf/Ro/Rb', fr.toFixed(1) + ' / ' + out.toFixed(1) + ' / ' + br.toFixed(1)],
      ['hf/hb' + _uSuffix('disp'), fh.toFixed(1) + ' / ' + bh.toFixed(1)],
      ['v0' + _uSuffix('vel'), fmt(imp.velocity, 0)],
      ['KE' + _uSuffix('energy'), fmt(imp.kinetic_energy, 2)]
    ];
    for (const r of rows) tbl.appendChild(el('tr', null, [el('td', { class: 'tl dim' }, r[0]), el('td', { class: 'num b' }, r[1])]));
    cap.textContent = 'Asymmetric tumbler: front + outer + back 3-stage cylinder.';
  } else {
    // Unknown / empty type: draw a neutral placeholder shape and still
    // populate the data table with whatever fields the loader filled in
    // (density, E, ν, mass, v₀, KE). Many real-world decks don't expose
    // an impactor type — we don't want the panel to look broken.
    sub.textContent = imp.type ? imp.type : '(type unspecified)';
    svgRoot.appendChild(svg('rect', { x: 60, y: 25, width: 80, height: 60, rx: 6, fill: 'rgba(77,214,255,0.06)', stroke: '#4dd6ff', 'stroke-width': 1, 'stroke-dasharray': '3,3' }));
    const qm = svg('text', { x: 100, y: 62, 'text-anchor': 'middle', fill: '#4dd6ff', 'font-size': 22, 'font-family': 'JetBrains Mono', 'font-weight': '700' });
    qm.appendChild(document.createTextNode('?'));
    svgRoot.appendChild(qm);
    const tlab = svg('text', { x: 100, y: 100, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 9, 'font-family': 'JetBrains Mono' });
    tlab.appendChild(document.createTextNode('type unspecified'));
    svgRoot.appendChild(tlab);
    const rows = [
      ['TYPE',              imp.type || '(unspecified)'],
      ['ρ' + _uDensitySuffix(),   fmt(imp.density, 3)],
      ['E' + _uSuffix('stress'),  fmt(imp.youngs_modulus, 3)],
      ['ν',                 (imp.poisson_ratio != null ? imp.poisson_ratio.toFixed(3) : '?')],
      ['m' + _uSuffix('mass'),    fmt(imp.mass, 4)],
      ['v₀' + _uSuffix('vel'),    fmt(imp.velocity, 0)],
      ['KE' + _uSuffix('energy'), fmt(imp.kinetic_energy, 2)],
    ];
    for (const r of rows) {
      tbl.appendChild(el('tr', null, [el('td', { class: 'tl dim' }, r[0]), el('td', { class: 'num b' }, r[1])]));
    }
    cap.textContent = 'Geometry not declared — material + kinematics only.';
  }
}

function initDoeBreakdown() {
  const tbl = document.getElementById('doe-breakdown');
  const sub = document.getElementById('doeSubLabel');
  while (tbl.firstChild) tbl.removeChild(tbl.firstChild);
  const cnt = {};
  for (const f of FACES) cnt[f.code] = 0;
  for (const p of DATA.positions) cnt[p.face] = (cnt[p.face] || 0) + 1;
  const total = Object.values(cnt).reduce((a, b) => a + b, 0);
  const doeType = (DATA.meta.doe_config && DATA.meta.doe_config.type) || 'grid';
  sub.textContent = doeType + ' · ' + total + ' pos';
  for (const f of FACES) {
    tbl.appendChild(el('tr', null, [
      el('td', { class: 'tl b' }, f.code),
      el('td', { class: 'tl dim' }, f.name),
      el('td', { class: 'num' }, String(cnt[f.code]))
    ]));
  }
  tbl.appendChild(el('tr', null, [
    el('td', { class: 'tl b', style: { color: 'var(--accent)' } }, 'TOTAL'),
    el('td', { class: 'tl dim' }, DATA.meta.generation_mode),
    el('td', { class: 'num b', style: { color: 'var(--accent)' } }, String(total))
  ]));
}

"""
