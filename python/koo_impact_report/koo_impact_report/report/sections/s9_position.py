# 섹션 09 — POSITION DRILL-DOWN: per-position 심층 분석 (KPI/내러티브/차트/테이블, P6)

_PAGE9 = """
<section class="page" id="s9">
  <div class="page-head r">
    <span class="num">09</span><span class="tagline" data-i18n="s9Tagline">POSITION &middot; DRILL-DOWN</span>
    <span class="ttl" data-i18n="s9Title">위치별 심층 분석 &mdash; 한 낙하 지점의 모든 것</span>
    <span class="sub">PER-POSITION DEEP DIVE</span>
  </div>

  <div class="ctlbar r" id="s9-ctlbar">
    <div class="grp"><span class="lbl" data-i18n="s9SelectPos">위치 선택</span>
      <select id="s9-pos-select"></select>
      <button class="btn" id="s9-prev">&#9664;</button>
      <button class="btn" id="s9-next">&#9654;</button>
    </div>
    <div class="grp"><span class="lbl">SORT</span>
      <button class="btn active" data-s9-sort="severity" data-i18n="s9SortSeverity">심각도순</button>
      <button class="btn" data-s9-sort="pos" data-i18n="s9SortPos">위치 ID순</button>
    </div>
    <div class="grp" style="margin-left:auto">
      <svg id="s9-mini-locator" width="96" height="64"></svg>
    </div>
  </div>

  <div class="kpi-strip r" id="s9-kpi" style="grid-template-columns:repeat(6,1fr)"></div>

  <div class="panel r" id="s9-narrative-panel" style="margin-bottom:14px">
    <div class="ph"><span class="pt" data-i18n="s9NarrTitle">엔지니어링 평가</span>
      <span class="pd" id="s9-sq-badge"></span></div>
    <div id="s9-narrative"></div>
  </div>

  <div class="grid g-12" style="margin-bottom:14px">
    <div class="panel col-7 r" id="s9-panel-acc">
      <div class="ph"><span class="pt" data-i18n="s9AccTitle">가속도 오버레이 &middot; 상위 8부품</span>
        <span class="pd">|a(t)| &middot; dashed = t_first_contact</span></div>
      <svg id="s9-acc-svg" preserveAspectRatio="none" style="width:100%;height:300px"></svg>
      <div id="s9-acc-legend" style="display:flex;flex-wrap:wrap;gap:8px;font-size:10.5px;padding:6px 4px"></div>
      <div class="pcap" id="s9-acc-cap"></div>
    </div>
    <div class="panel col-5 r" id="s9-panel-traj">
      <div class="ph"><span class="pt" data-i18n="s9TrajTitle">임팩터 궤적 미니뷰</span>
        <span class="pd">KE(t) + contact &middot; z(t)</span></div>
      <svg id="s9-traj-ke" style="width:100%;height:150px"></svg>
      <svg id="s9-traj-z" style="width:100%;height:110px"></svg>
      <div id="s9-traj-kpi" style="font-size:11px;color:#9aa5c0;padding:6px 8px"></div>
      <div class="pcap">보라 밴드 = 접촉 구간. 아래 = 임팩터 z(t) — 관입·리바운드 형상.</div>
    </div>
  </div>

  <div class="panel col-12 r" id="s9-panel-parts">
    <div class="ph"><span class="pt" data-i18n="s9TblTitle">이 위치의 부품별 응답</span>
      <span class="pd">sorted by peak_g &middot; badge = role at this position</span></div>
    <table class="dt" id="s9-part-tbl">
      <thead><tr>
        <th>#</th><th class="tl">PART</th><th>PEAK G (g)</th><th></th>
        <th>% of WORST</th><th>&sigma; (MPa)</th><th>&epsilon;</th><th>TOA &Delta;t (ms)</th><th>BADGE</th>
      </tr></thead>
      <tbody></tbody>
    </table>
    <div class="pcap">badge: DRIVER=이 위치 최대 가속도 부품 &middot; &sigma;-DRIVER=최대 응력 부품 &middot;
      CRIT/WARN=전역 P95/P75 초과 &middot; IMPACTOR 행의 g 는 가해자 측 응답.</div>
  </div>
</section>
"""


_JS_S9 = r"""// --- Section 09: POSITION DRILL-DOWN (P6) ----------------------------------
const S9_STATE = { pos: null, sort: 'severity', _loading: null, _inited: false };

function _s9gDiv() { return gDivisor(); }   // M11: 공용 헬퍼 단일 소스
function _s9doe() { return DATA.doe_analysis || null; }
function _s9posList() {
  const doe = _s9doe();
  const pm = (doe && doe.position_metrics) || {};
  const list = (DATA.positions || []).map(p => ({
    pos_id: p.pos_id, x: p.x, y: p.y,
    g: (pm[p.pos_id] || {}).peak_g_max || 0,
  }));
  if (S9_STATE.sort === 'severity') list.sort((a, b) => b.g - a.g);
  else list.sort((a, b) => String(a.pos_id).localeCompare(String(b.pos_id)));
  return list;
}
function _s9rank(posId) {
  // 순위/백분위 — position_metrics 전 pos 의 peak_g_max 로 JS 계산 (payload 추가 불요)
  const doe = _s9doe();
  const pm = (doe && doe.position_metrics) || {};
  const vals = Object.entries(pm).map(([k, v]) => [k, v.peak_g_max || 0])
    .sort((a, b) => b[1] - a[1]);
  const idx = vals.findIndex(v => v[0] === posId);
  return { rank: idx + 1, n: vals.length };
}

function selectPosition(posId, opts) {
  opts = opts || {};
  if (!posId) return;
  S9_STATE.pos = posId;
  const sel = document.getElementById('s9-pos-select');
  if (sel) sel.value = posId;
  fireLazy('s9');
  renderS9(posId);
  // s3 에너지 흐름 페이지도 이 위치로 갱신 (P5 위치 연동)
  if (typeof refreshEnergyFlowForPos === 'function') {
    try { refreshEnergyFlowForPos(posId); } catch (e) {}
  }
  // s5 활성 위치 동기화 (히트맵/랭킹 하이라이트)
  if (typeof DOE_STATE !== 'undefined' && DOE_STATE.active_pos !== posId) {
    DOE_STATE.active_pos = posId;
    const doe = _s9doe();
    if (doe && typeof _doeRenderHeatmap === 'function') {
      try { _doeRenderHeatmap(doe); _doeRenderRanking(doe); } catch (e) {}
    }
  }
  if (opts.scroll !== false) {
    const secEl = document.getElementById('s9');
    if (secEl) secEl.scrollIntoView({ behavior: 'smooth' });
  }
}

function initS9() {
  const doe = _s9doe();
  const sec = document.getElementById('s9');
  if (!sec) return;
  if (!doe || !(DATA.positions || []).length) { sec.style.display = 'none'; return; }
  if (S9_STATE._inited) return;
  S9_STATE._inited = true;

  const sel = document.getElementById('s9-pos-select');
  const gDiv = _s9gDiv();
  function rebuildOptions() {
    const cur = S9_STATE.pos;
    while (sel.firstChild) sel.removeChild(sel.firstChild);
    const crit = (DATA.kpi || {}).crit_threshold || Infinity;
    _s9posList().forEach((p, i) => {
      const beh = ((doe.trajectory_summary || {})[p.pos_id] || {}).behavior_class || '';
      const warn = p.g >= crit ? '⚠ ' : '';
      const o = el('option', { value: p.pos_id, 'data-pos': p.pos_id },
        warn + '#' + (i + 1) + '  ' + p.pos_id + ' · ' + fmt(p.g / gDiv, 0) + ' g' +
        (beh ? ' · ' + beh : ''));
      sel.appendChild(o);
    });
    if (cur) sel.value = cur;
  }
  rebuildOptions();
  sel.addEventListener('change', () => selectPosition(sel.value, { scroll: false, source: 'select' }));
  document.getElementById('s9-prev').addEventListener('click', () => {
    if (sel.selectedIndex > 0) { sel.selectedIndex -= 1; selectPosition(sel.value, { scroll: false }); }
  });
  document.getElementById('s9-next').addEventListener('click', () => {
    if (sel.selectedIndex < sel.options.length - 1) { sel.selectedIndex += 1; selectPosition(sel.value, { scroll: false }); }
  });
  document.querySelectorAll('[data-s9-sort]').forEach(b => b.addEventListener('click', () => {
    document.querySelectorAll('[data-s9-sort]').forEach(x => x.classList.remove('active'));
    b.classList.add('active');
    S9_STATE.sort = b.dataset.s9Sort;
    rebuildOptions();
  }));

  // 초기 선택: 최악 위치
  const first = _s9posList()[0];
  const initial = S9_STATE.pos ||
    ((DATA.kpi && DATA.kpi.worst && DATA.kpi.worst.pos_id) || (first && first.pos_id));
  if (initial) { S9_STATE.pos = initial; sel.value = initial; renderS9(initial); }
}

function renderS9(posId) {
  renderS9Static(posId);
  renderS9MiniLocator(posId);
  // 차트 데이터: 인라인 우선, 없으면 청크 (tier C/D)
  const inlineSeries = (DATA.part_motion.series || []).filter(s => s.pos_id === posId);
  const traj = (DATA.trajectories || {})[posId];
  const trajRich = traj && traj.t && traj.t.length >= 60;
  if (inlineSeries.length && trajRich) { renderS9Charts(posId, null); return; }
  if (DATA.chunks) {
    showS9ChartMsg(L('chunkLoading'));
    if (S9_STATE._loading === posId) return;
    S9_STATE._loading = posId;
    loadChunk(chunkIdForPos(posId), b => {
      S9_STATE._loading = null;
      if (S9_STATE.pos !== posId) return;   // 그 사이 다른 위치 선택됨
      if (b) renderS9Charts(posId, b);
      else showS9ChartMsg(L('chunkMissing'));
    });
  } else {
    renderS9Charts(posId, null);   // 저해상 인라인이라도 그린다
  }
}

function _s9SvgMsg(svgEl, msg) {
  while (svgEl.firstChild) svgEl.removeChild(svgEl.firstChild);
  svgEl.setAttribute('viewBox', '0 0 600 120');
  const t = svg('text', { x: 300, y: 60, 'text-anchor': 'middle', fill: '#5c6383', 'font-size': 11 });
  t.appendChild(document.createTextNode(msg));
  svgEl.appendChild(t);
}
function showS9ChartMsg(msg) {
  _s9SvgMsg(document.getElementById('s9-acc-svg'), msg);
  _s9SvgMsg(document.getElementById('s9-traj-ke'), msg);
  const z = document.getElementById('s9-traj-z');
  while (z.firstChild) z.removeChild(z.firstChild);
}

// ---- 정적부: KPI 6카드 + 내러티브 + per-part 테이블 -----------------------
function renderS9Static(posId) {
  const doe = _s9doe();
  const gDiv = _s9gDiv();
  const pm = (doe.position_metrics || {})[posId] || {};
  const ts = (doe.trajectory_summary || {})[posId] || {};
  const traj = (DATA.trajectories || {})[posId] || {};
  const sq = ((DATA.solver_quality || {}).per_position || {})[posId] || null;
  const toa = (((doe.advanced || {}).toa || {}).toa_per_position || {})[posId] || [];
  const { rank, n } = _s9rank(posId);
  const ko = reportLang === 'ko';

  function pname(pid) { return (PART_BY_ID[pid] || {}).name || ('part_' + pid); }

  // KPI 카드
  const kpiHost = document.getElementById('s9-kpi');
  while (kpiHost.firstChild) kpiHost.removeChild(kpiHost.firstChild);
  function card(label, value, unit, sub, color) {
    const k = el('div', { class: 'k' });
    k.appendChild(el('div', { class: 'l' }, label));
    const v = el('div', { class: 'v' }, value);
    if (color) v.style.color = color;
    k.appendChild(v);
    if (unit) k.appendChild(el('div', { class: 'u' }, unit));
    if (sub) k.appendChild(el('div', { class: 'l', style: { marginTop: '2px' } }, sub));
    kpiHost.appendChild(k);
  }
  const pct = n ? Math.round(100 * rank / n) : null;
  card(L('kpiWorstG'), pm.peak_g_max != null ? fmt(pm.peak_g_max / gDiv, 0) : '—', 'g · element-local',
       pm.worst_part_id_g != null ? pname(pm.worst_part_id_g) + (pct != null ? ' · #' + rank + '/' + n : '') : null,
       rank <= Math.max(1, Math.round(n * 0.1)) ? 'var(--crit, #ff5e84)' : null);
  card(L('kpiWorstStress'), pm.peak_stress_max != null ? fmt(pm.peak_stress_max, 1) : '—', _u('stress') || 'MPa',
       pm.worst_part_id_s != null ? pname(pm.worst_part_id_s) : null);
  card(L('kpiKeAbsorbed'),
       ts.ke_retention != null ? ((1 - ts.ke_retention) * 100).toFixed(1) + '%' : '—', null,
       ts.behavior_class || null);
  const cor = (traj.incident_speed > 0 && traj.rebound_speed != null)
    ? (traj.rebound_speed / traj.incident_speed) : null;
  card(L('kpiMaxPen'), ts.max_penetration_depth != null ? fmt(ts.max_penetration_depth, 2) : '—',
       _u('disp') || 'mm', cor != null ? 'COR ≈ ' + cor.toFixed(2) : null);
  const sqv = sq ? (sq.pass_fail || 'UNKNOWN') : 'N/A';
  card(L('kpiSolverQ'), sqv, null,
       sq && (sq.flags || []).length ? (sq.flags.length + ' flag(s)') : null,
       sqv === 'FAIL' ? 'var(--crit, #ff5e84)' : (sqv === 'PASS' ? '#6ee7a0' : null));
  card(L('kpiFirstArrival'),
       toa.length ? toa[0].part_name : '—', null,
       toa.length ? ('+' + toa[0].dt_ms.toFixed(3) + ' ms') : null);

  // solver 배지 (내러티브 패널 헤더)
  const sqBadge = document.getElementById('s9-sq-badge');
  sqBadge.textContent = sq ? ('SOLVER ' + sqv + ((sq.flags || []).length ? ' · ' + sq.flags.join(', ') : '')) : '';
  sqBadge.style.color = sqv === 'FAIL' ? '#ff5e84' : '#6a7282';

  // 내러티브
  document.getElementById('s9-narrative').innerHTML =
    buildPositionNarrative(posId, { pm, ts, traj, sq, toa, rank, n, gDiv, ko });

  // per-part 테이블
  const rows = (DATA.results || []).filter(r => r.pos_id === posId)
    .slice().sort((a, b) => (b.g || 0) - (a.g || 0));
  const toaByPart = {};
  toa.forEach(t2 => { toaByPart[t2.part_id] = t2.dt_ms; });
  const firstHit = toa.length ? toa[0].part_id : null;
  const impPid = (DATA.part_motion || {}).impactor_part_id;
  const crit = (DATA.kpi || {}).crit_threshold;
  const warn = (DATA.kpi || {}).warn_threshold;
  const worstG = pm.peak_g_max || (rows[0] && rows[0].g) || 1;
  const tb = document.querySelector('#s9-part-tbl tbody');
  while (tb.firstChild) tb.removeChild(tb.firstChild);
  rows.forEach((r, i) => {
    const tr = el('tr', { 'data-part': r.part_id });
    tr.appendChild(el('td', { class: 'tl b' }, String(i + 1)));
    tr.appendChild(el('td', { class: 'tl' }, r.part_name || pname(r.part_id)));
    tr.appendChild(el('td', { class: 'num' }, fmt((r.g || 0) / gDiv, 0)));
    const barTd = el('td', {});
    barTd.appendChild(el('span', {
      class: 's9-bar',
      style: { width: Math.max(2, 70 * (r.g || 0) / worstG) + 'px' },
    }));
    tr.appendChild(barTd);
    tr.appendChild(el('td', { class: 'num' }, (100 * (r.g || 0) / worstG).toFixed(0) + '%'));
    const sTd = el('td', { class: 'num' }, fmt(r.s || 0, 1));
    const _sLim = (DATA.kpi || {}).stress_limit;
    if (_sLim != null && (r.s || 0) > _sLim) {
      sTd.style.color = 'var(--crit, #ff5e84)';
      sTd.title = '설계 응력 한계 ' + _sLim + ' 초과';
    }
    tr.appendChild(sTd);
    const eTd = el('td', { class: 'num' }, r.e ? r.e.toExponential(1) : '—');
    if (!r.e) eTd.style.opacity = 0.4;
    tr.appendChild(eTd);
    tr.appendChild(el('td', { class: 'num' },
      toaByPart[r.part_id] != null ? toaByPart[r.part_id].toFixed(3) : '—'));
    const bTd = el('td', { class: 'tl' });
    const isImp = impPid != null && r.part_id === impPid;
    if (r.part_id === pm.worst_part_id_g) bTd.appendChild(el('span', { class: 's9-badge driver' }, 'DRIVER'));
    if (r.part_id === pm.worst_part_id_s && pm.worst_part_id_s !== pm.worst_part_id_g)
      bTd.appendChild(el('span', { class: 's9-badge sdriver' }, 'σ-DRIVER'));
    if (isImp) bTd.appendChild(el('span', { class: 's9-badge impactor' }, 'IMPACTOR'));
    else if (crit && r.g >= crit) bTd.appendChild(el('span', { class: 's9-badge crit' }, 'CRIT'));
    else if (warn && r.g >= warn) bTd.appendChild(el('span', { class: 's9-badge warn' }, 'WARN'));
    if (firstHit != null && r.part_id === firstHit) bTd.appendChild(el('span', { class: 's9-badge firsthit' }, 'FIRST-HIT'));
    tr.appendChild(bTd);
    tb.appendChild(tr);
  });
}

// ---- 내러티브 (설계 §2: 슬롯 S0-S5, 2-4문장 clamp, 값없음 통생략) ----------
function buildPositionNarrative(posId, m) {
  const ko = m.ko;
  const B = s => '<span class="dd-b">' + s + '</span>';
  const W = s => '<span class="dd-w">' + s + '</span>';
  const G = s => '<span class="dd-g">' + s + '</span>';
  const H = s => '<span class="dd-h">' + s + '</span>';
  function pname(pid) { return (PART_BY_ID[pid] || {}).name || ('part_' + pid); }
  const S = [];

  // S0 신뢰 게이트
  const sqv = m.sq ? m.sq.pass_fail : null;
  const impactVisible = m.sq && m.sq.summary ? m.sq.summary.impact_visible : null;
  if (sqv === 'FAIL') {
    const fl = (m.sq.flags || []).join(', ');
    S.push(ko
      ? 'solver 품질 감사가 ' + B('FAIL') + ' (' + fl + ') 이므로 아래 수치는 순위 비교 용도로만 사용하고, 절대값 판정은 재해석 후에 하시기를 권장합니다.'
      : 'The solver-quality audit is ' + B('FAIL') + ' (' + fl + ') — use the numbers below for ranking only and re-run before absolute judgements.');
  } else if (impactVisible === false) {
    S.push(ko
      ? 'glstat 감사 창에는 유의미한 충격 이벤트가 기록되지 않았습니다(' + W('no-impact-in-glstat-window') + ') — 이 위치의 실효 접촉은 미미합니다.'
      : 'The glstat audit window records no significant impact event (' + W('no-impact-in-glstat-window') + ') — effective contact here is negligible.');
  }

  // S1 오프닝+순위 (필수)
  const pos = (DATA.positions || []).find(p => p.pos_id === posId) || { x: 0, y: 0 };
  if (m.n) {
    const topFrac = m.rank / m.n;
    const rankTxt = '#' + m.rank + '/' + m.n;
    const emph = m.rank <= 3 ? B : (topFrac <= 0.25 ? W : (topFrac <= 0.5 ? H : G));
    S.push(ko
      ? '위치 ' + H(posId) + ' (x ' + pos.x.toFixed(1) + ', y ' + pos.y.toFixed(1) + ')는 전체 ' + m.n + '개 위치 중 최대 응답 ' + emph(rankTxt + ' (상위 ' + Math.round(100 * topFrac) + '%)') + ' 입니다.'
      : 'Position ' + H(posId) + ' (x ' + pos.x.toFixed(1) + ', y ' + pos.y.toFixed(1) + ') ranks ' + emph(rankTxt + ' (top ' + Math.round(100 * topFrac) + '%)') + ' in peak response.');
  }

  // S2 응답 드라이버
  if (m.pm.peak_g_max > 0 && m.pm.worst_part_id_g != null) {
    const gTxt = fmt(m.pm.peak_g_max / m.gDiv, 0) + ' g';
    let s2 = ko
      ? H(pname(m.pm.worst_part_id_g)) + ' 에서 element-local peak ' + B(gTxt) + ' 가 관측되었습니다'
      : H(pname(m.pm.worst_part_id_g)) + ' sees an element-local peak of ' + B(gTxt);
    if (m.pm.worst_part_id_s != null && m.pm.worst_part_id_s !== m.pm.worst_part_id_g && m.pm.peak_stress_max > 0) {
      s2 += ko
        ? '. 응력 드라이버는 별도 부품(' + H(pname(m.pm.worst_part_id_s)) + ', σ=' + fmt(m.pm.peak_stress_max, 1) + ' ' + (_u('stress') || 'MPa') + ')으로 가속도·응력 취약점이 분리되어 있습니다.'
        : ', while the stress driver is a different part (' + H(pname(m.pm.worst_part_id_s)) + ', σ = ' + fmt(m.pm.peak_stress_max, 1) + ' ' + (_u('stress') || 'MPa') + ') — the two vulnerabilities are decoupled.';
    } else { s2 += '.'; }
    S.push(s2);
  }

  // S3 임팩터 운명 (ke_retention 정상 범위일 때만)
  const kr = m.ts.ke_retention;
  if (m.ts.behavior_class === 'no-contact') {
    // MED-7 (QA): 미접촉 런에 '관입/반발속도비' 를 쓰면 자유낙하 아티팩트가
    // 물리량처럼 보임 — 접촉 없음 사실만 서술.
    S.push(ko
      ? '임팩터는 이 위치에서 디바이스와 접촉하지 않고 통과했습니다 — 관입·반발 지표는 해당 없음.'
      : 'The impactor passed this position without contacting the device — penetration/rebound metrics are not applicable.');
  } else if (kr != null && kr >= 0 && kr <= 1.0001 && m.ts.behavior_class) {
    const abs = ((1 - kr) * 100);
    let s3;
    if (m.ts.behavior_class === 'bounce' && abs < 1) {
      s3 = ko
        ? '임팩터는 운동에너지를 사실상 전량 보존한 채(' + G('KE retention ' + (kr * 100).toFixed(1) + '%') + ') bounce 하여 에너지 전달이 사실상 없습니다.'
        : 'The impactor bounces with essentially full kinetic energy retained (' + G((kr * 100).toFixed(1) + '%') + ') — practically no energy transfer.';
    } else {
      const corTxt = (m.traj.incident_speed > 0 && m.traj.rebound_speed != null)
        ? (ko ? ', 반발속도비≈' : ', COR ≈ ') + (m.traj.rebound_speed / m.traj.incident_speed).toFixed(2) : '';
      s3 = ko
        ? '임팩터는 ' + H(m.ts.behavior_class) + ' 거동으로 초기 운동에너지의 ' + W(abs.toFixed(1) + '%') + ' 를 디바이스에 전달했습니다(관입 ' + fmt(m.ts.max_penetration_depth || 0, 2) + ' ' + (_u('disp') || 'mm') + corTxt + ').'
        : 'The impactor shows ' + H(m.ts.behavior_class) + ' behavior, transferring ' + W(abs.toFixed(1) + '%') + ' of its kinetic energy (penetration ' + fmt(m.ts.max_penetration_depth || 0, 2) + ' ' + (_u('disp') || 'mm') + corTxt + ').';
    }
    S.push(s3);
  }

  // S4 전파 순서
  if (m.toa.length >= 2) {
    S.push(ko
      ? '첫 접촉 후 +' + m.toa[0].dt_ms.toFixed(3) + ' ms 에 ' + H(m.toa[0].part_name) + ' → +' + m.toa[1].dt_ms.toFixed(3) + ' ms 에 ' + H(m.toa[1].part_name) + ' 순으로 응답이 도달했습니다.'
      : 'After first contact the response arrives at ' + H(m.toa[0].part_name) + ' (+' + m.toa[0].dt_ms.toFixed(3) + ' ms) then ' + H(m.toa[1].part_name) + ' (+' + m.toa[1].dt_ms.toFixed(3) + ' ms).');
  }

  // clamp: S0(있으면) + 이후 우선순위순 — 총 4문장
  const cap = S.slice(0, 4);
  if (!cap.length) {
    return ko ? '위치 ' + posId + ': 표시할 데이터가 충분하지 않습니다.'
              : 'Position ' + posId + ': not enough data to assess.';
  }
  return cap.join(' ');
}

// ---- mini-locator: XY 격자에서 현재 위치 하이라이트 ------------------------
function renderS9MiniLocator(posId) {
  const host = document.getElementById('s9-mini-locator');
  while (host.firstChild) host.removeChild(host.firstChild);
  const doe = _s9doe();
  const grid = (doe && doe.grid) || null;
  const poss = DATA.positions || [];
  if (!poss.length) return;
  let xmin = Infinity, xmax = -Infinity, ymin = Infinity, ymax = -Infinity;
  poss.forEach(p => {
    if (p.x < xmin) xmin = p.x; if (p.x > xmax) xmax = p.x;
    if (p.y < ymin) ymin = p.y; if (p.y > ymax) ymax = p.y;
  });
  if (grid && grid.bbox) { xmin = grid.bbox[0]; ymin = grid.bbox[1]; xmax = grid.bbox[2]; ymax = grid.bbox[3]; }
  const W = 96, Hh = 64, pad = 5;
  host.setAttribute('viewBox', '0 0 ' + W + ' ' + Hh);
  const sx = v => pad + (xmax > xmin ? (v - xmin) / (xmax - xmin) : 0.5) * (W - 2 * pad);
  const sy = v => Hh - pad - (ymax > ymin ? (v - ymin) / (ymax - ymin) : 0.5) * (Hh - 2 * pad);
  poss.forEach(p => {
    const active = p.pos_id === posId;
    const c = svg('circle', {
      cx: sx(p.x).toFixed(1), cy: sy(p.y).toFixed(1), r: active ? 3.4 : 1.6,
      fill: active ? '#4dd6ff' : '#3a4569', 'data-pos': p.pos_id,
      style: 'cursor:pointer',
    });
    c.addEventListener('click', () => selectPosition(p.pos_id, { scroll: false, source: 'locator' }));
    c.addEventListener('mouseenter', () => xlinkHover(p.pos_id, true));
    c.addEventListener('mouseleave', () => xlinkHover(p.pos_id, false));
    host.appendChild(c);
  });
}

// ---- 차트: acc 오버레이 + 궤적 미니뷰 --------------------------------------
function renderS9Charts(posId, bundle) {
  const gDiv = _s9gDiv();
  // 시리즈 소스: 청크 번들 > 인라인
  let series, tArr;
  if (bundle && bundle.series && bundle.series.length) {
    series = bundle.series;
    tArr = bundle.t_ref || [];
  } else {
    const tRef = (DATA.part_motion || {}).t_ref || {};
    series = (DATA.part_motion.series || []).filter(s => s.pos_id === posId);
    tArr = series.length ? (series[0].t || tRef[series[0].tref] || []) : [];
  }
  const impPid = (DATA.part_motion || {}).impactor_part_id;
  const accSvg = document.getElementById('s9-acc-svg');
  const legend = document.getElementById('s9-acc-legend');
  while (accSvg.firstChild) accSvg.removeChild(accSvg.firstChild);
  while (legend.firstChild) legend.removeChild(legend.firstChild);

  if (!series.length || !tArr.length) {
    _s9SvgMsg(accSvg, reportLang === 'ko' ? '가속도 시계열 없음' : 'no acc time series');
  } else {
    const top = series.slice().sort((a, b) => (b.peak_g || 0) - (a.peak_g || 0)).slice(0, 8);
    const W = 900, Hh = 300, pad = { l: 64, r: 12, t: 10, b: 26 };
    accSvg.setAttribute('viewBox', '0 0 ' + W + ' ' + Hh);
    const plotW = W - pad.l - pad.r, plotH = Hh - pad.t - pad.b;
    let tMin = Infinity, tMax = -Infinity, aMax = 0;
    top.forEach(s => {
      const T = s.t || tArr;
      for (let i = 0; i < T.length; i++) { if (T[i] < tMin) tMin = T[i]; if (T[i] > tMax) tMax = T[i]; }
      (s.a || []).forEach(v => { if (v != null && v > aMax) aMax = v; });
    });
    if (!isFinite(tMin)) { tMin = 0; tMax = 1; }
    if (aMax <= 0) aMax = 1;
    const px = tv => pad.l + (tv - tMin) / (tMax - tMin || 1) * plotW;
    const py = av => pad.t + (1 - av / aMax) * plotH;
    // t_first_contact 점선
    const tfc = (DATA.part_motion || {}).t_first_contact;
    if (tfc != null && tfc >= tMin && tfc <= tMax) {
      accSvg.appendChild(svg('line', { x1: px(tfc), x2: px(tfc), y1: pad.t, y2: pad.t + plotH,
        stroke: '#b28cff', 'stroke-dasharray': '4,3', 'stroke-width': 1 }));
    }
    const PAL = ['#4dd6ff', '#ffc15e', '#6ee7a0', '#ff9eb9', '#b28cff', '#7ce0e0', '#e0c97c', '#9ab8ff'];
    top.forEach((s, si) => {
      const T = s.t || tArr;
      const isImp = impPid != null && s.part_id === impPid;
      const color = isImp ? '#ff5e84' : PAL[si % PAL.length];
      const pts = [];
      const N = Math.min(T.length, (s.a || []).length);
      for (let i = 0; i < N; i++) {
        if (s.a[i] == null) continue;
        pts.push(px(T[i]).toFixed(1) + ',' + py(s.a[i]).toFixed(1));
      }
      accSvg.appendChild(svg('polyline', { points: pts.join(' '), fill: 'none', stroke: color,
        'stroke-width': isImp ? 1.8 : 1.2, opacity: 0.85 }));
      const item = el('span', { style: { color: color, cursor: 'default' } },
        (s.part_name || String(s.part_id)) + ' · ' + fmt((s.peak_g || 0) / gDiv, 0) + 'g');
      legend.appendChild(item);
    });
    // y 라벨
    accSvg.appendChild(svg('text', { x: 6, y: pad.t + 10, fill: '#5c6383', 'font-size': 10 },
      '|a| ' + (_u('acc') || '')));
    document.getElementById('s9-acc-cap').textContent =
      (reportLang === 'ko' ? '상위 8부품 (peak g 기준). 점선 = 최초 접촉.' :
       'Top-8 parts by peak g. Dashed line = first contact.');
  }

  // 궤적 미니뷰
  const traj = (bundle && bundle.trajectory) || (DATA.trajectories || {})[posId] || null;
  const keSvg = document.getElementById('s9-traj-ke');
  const zSvg = document.getElementById('s9-traj-z');
  while (keSvg.firstChild) keSvg.removeChild(keSvg.firstChild);
  while (zSvg.firstChild) zSvg.removeChild(zSvg.firstChild);
  const tk = document.getElementById('s9-traj-kpi');
  tk.textContent = '';
  if (!traj || !traj.t || !traj.t.length) {
    _s9SvgMsg(keSvg, L('noTraj'));
    return;
  }
  const W2 = 420, H2 = 150, H3 = 110, pad2 = { l: 46, r: 8, t: 8, b: 18 };
  keSvg.setAttribute('viewBox', '0 0 ' + W2 + ' ' + H2);
  zSvg.setAttribute('viewBox', '0 0 ' + W2 + ' ' + H3);
  const T = traj.t;
  const tMin2 = T[0], tMax2 = T[T.length - 1] || 1;
  const px2 = tv => pad2.l + (tv - tMin2) / (tMax2 - tMin2 || 1) * (W2 - pad2.l - pad2.r);
  // 접촉 밴드
  const contact = traj.contact || [];
  let bandStart = null;
  for (let i = 0; i <= contact.length; i++) {
    const on = i < contact.length && contact[i];
    if (on && bandStart == null) bandStart = i;
    if (!on && bandStart != null) {
      [keSvg, zSvg].forEach((sv2, k) => {
        sv2.appendChild(svg('rect', {
          x: px2(T[bandStart]).toFixed(1), y: pad2.t,
          width: Math.max(1, px2(T[Math.min(i, T.length - 1)]) - px2(T[bandStart])).toFixed(1),
          height: (k === 0 ? H2 : H3) - pad2.t - pad2.b,
          fill: 'rgba(178,140,255,0.10)',
        }));
      });
      bandStart = null;
    }
  }
  // KE(t)
  const ke = traj.ke || [];
  let keMax = 0; ke.forEach(v => { if (v > keMax) keMax = v; });
  if (keMax > 0) {
    const pyK = v => pad2.t + (1 - v / keMax) * (H2 - pad2.t - pad2.b);
    const pts = [];
    for (let i = 0; i < Math.min(T.length, ke.length); i++)
      pts.push(px2(T[i]).toFixed(1) + ',' + pyK(ke[i]).toFixed(1));
    keSvg.appendChild(svg('polyline', { points: pts.join(' '), fill: 'none',
      stroke: '#4dd6ff', 'stroke-width': 1.5 }));
    keSvg.appendChild(svg('text', { x: 4, y: pad2.t + 9, fill: '#5c6383', 'font-size': 9 },
      'KE ' + (_u('energy') || '')));
  }
  // z(t)
  const posArr = traj.pos || [];
  if (posArr.length) {
    let zMin = Infinity, zMax = -Infinity;
    posArr.forEach(p3 => { const z = p3[2]; if (z < zMin) zMin = z; if (z > zMax) zMax = z; });
    if (zMax === zMin) { zMax = zMin + 1; }
    const pyZ = v => pad2.t + (1 - (v - zMin) / (zMax - zMin)) * (H3 - pad2.t - pad2.b);
    const pts = [];
    for (let i = 0; i < Math.min(T.length, posArr.length); i++)
      pts.push(px2(T[i]).toFixed(1) + ',' + pyZ(posArr[i][2]).toFixed(1));
    zSvg.appendChild(svg('polyline', { points: pts.join(' '), fill: 'none',
      stroke: '#6ee7a0', 'stroke-width': 1.3 }));
    zSvg.appendChild(svg('text', { x: 4, y: pad2.t + 9, fill: '#5c6383', 'font-size': 9 }, 'z'));
  }
  // 스칼라 요약 (인라인 trajectories 는 tier D 에서도 스칼라 보유)
  const inline = (DATA.trajectories || {})[posId] || {};
  const bits = [];
  if (inline.ke_retention != null) bits.push('KE retain ' + (inline.ke_retention * 100).toFixed(1) + '%');
  if (inline.max_pen != null) bits.push('max pen ' + fmt(inline.max_pen, 2));
  if (inline.rebound_speed != null && inline.incident_speed > 0)
    bits.push('COR≈' + (inline.rebound_speed / inline.incident_speed).toFixed(2));
  if (inline.behavior) bits.push(inline.behavior);
  tk.textContent = bits.join('  ·  ');
}

"""
