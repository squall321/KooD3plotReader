# 코어 유틸/배선/lazy/boot JS 세그먼트 (html_report.py 기계적 분할, 바이트 불변)

_JS_HEAD = r"""
const DATA = __PAYLOAD__;

// --- i18n (P6): sphere L()/toggleLang 패턴 이식. 정적 라벨은 [data-i18n],
// 동적 프로즈는 인라인 이중 문자열 (reportLang 참조).
let reportLang = 'ko';
const I18N = {
  s9Tagline:      { ko: 'POSITION \u00b7 DRILL-DOWN', en: 'POSITION \u00b7 DRILL-DOWN' },
  s9Title:        { ko: '\uc704\uce58\ubcc4 \uc2ec\uce35 \ubd84\uc11d \u2014 \ud55c \ub099\ud558 \uc9c0\uc810\uc758 \ubaa8\ub4e0 \uac83', en: 'Per-Position Deep Dive' },
  s9SelectPos:    { ko: '\uc704\uce58 \uc120\ud0dd', en: 'POSITION' },
  s9SortSeverity: { ko: '\uc2ec\uac01\ub3c4\uc21c', en: 'SEVERITY' },
  s9SortPos:      { ko: '\uc704\uce58 ID\uc21c', en: 'POS ID' },
  s9NarrTitle:    { ko: '\uc5d4\uc9c0\ub2c8\uc5b4\ub9c1 \ud3c9\uac00', en: 'ENGINEERING ASSESSMENT' },
  s9AccTitle:     { ko: '\uac00\uc18d\ub3c4 \uc624\ubc84\ub808\uc774 \u00b7 \uc0c1\uc704 8\ubd80\ud488', en: 'ACC-MAG OVERLAY \u00b7 TOP-8 PARTS' },
  s9TrajTitle:    { ko: '\uc784\ud329\ud130 \uad64\uc801 \ubbf8\ub2c8\ubdf0', en: 'IMPACTOR TRAJECTORY MINI-VIEW' },
  s9TblTitle:     { ko: '\uc774 \uc704\uce58\uc758 \ubd80\ud488\ubcc4 \uc751\ub2f5', en: 'PER-PART RESPONSE @ THIS POSITION' },
  kpiWorstG:      { ko: '\ucd5c\ub300 \uac00\uc18d\ub3c4', en: 'WORST PEAK G' },
  kpiWorstStress: { ko: '\ucd5c\ub300 \uc751\ub825', en: 'WORST STRESS' },
  kpiKeAbsorbed:  { ko: '\ud761\uc218 \uc5d0\ub108\uc9c0', en: 'KE ABSORBED' },
  kpiMaxPen:      { ko: '\ucd5c\ub300 \uad00\uc785', en: 'MAX PENETRATION' },
  kpiSolverQ:     { ko: '\ud574\uc11d \ud488\uc9c8', en: 'SOLVER QUALITY' },
  kpiFirstArrival:{ ko: '\ucd5c\ucd08 \uc751\ub2f5 \ub3c4\ub2ec', en: 'FIRST ARRIVAL' },
  chunkLoading:   { ko: '\uc2dc\uacc4\uc5f4 \uccad\ud06c \ub85c\ub529 \uc911\u2026', en: 'loading time-series chunk\u2026' },
  chunkMissing:   { ko: '\uccad\ud06c \ud30c\uc77c \uc5c6\uc74c \u2014 report_data/ \ub97c HTML \uacfc \ud568\uaed8 \ub450\uc138\uc694', en: 'chunk missing \u2014 keep report_data/ next to the HTML' },
  noTraj:         { ko: '\uad64\uc801 \ub370\uc774\ud130 \uc5c6\uc74c', en: 'no trajectory data' },
};
function L(key) {
  const e = I18N[key];
  if (!e) return key;
  return e[reportLang] || e.ko || key;
}
function toggleLang() {
  reportLang = reportLang === 'ko' ? 'en' : 'ko';
  const btn = document.getElementById('lang-toggle-btn');
  if (btn) btn.textContent = reportLang === 'ko' ? 'EN' : '\ud55c';
  document.querySelectorAll('[data-i18n]').forEach(function (n) {
    n.textContent = L(n.dataset.i18n);
  });
  if (typeof S9_STATE !== 'undefined' && S9_STATE.pos) renderS9(S9_STATE.pos);
}
// \ud06c\ub85c\uc2a4\ub9c1\ud06c hover \uc0c1\ud638 \ud558\uc774\ub77c\uc774\ud2b8 (s5 \u2194 s9)
function xlinkHover(posId, on) {
  document.querySelectorAll('[data-pos="' + (window.CSS && CSS.escape ? CSS.escape(posId) : posId) + '"]')
    .forEach(function (n) { n.classList.toggle('xlink-hi', on); });
}

function fmt(n, d) {
  if (n == null || !isFinite(n)) return '-';
  const a = Math.abs(n);
  if (a >= 1e6) return (n / 1e6).toFixed(d == null ? 2 : d) + 'M';
  if (a >= 1e3) return (n / 1e3).toFixed(d == null ? 1 : d) + 'k';
  // 매우 작은 값 (예: ton-mm-s 의 density 7.85e-9) 은 fixed-point 로 표현 못함 → exponential
  if (a > 0 && a < 1e-3) return n.toExponential(d == null ? 2 : Math.max(2, d));
  if (a < 1 && a > 0) return n.toFixed((d == null ? 2 : d) + 2);
  return n.toFixed(d == null ? 2 : d);
}
function gColor(t) {
  t = Math.max(0, Math.min(1, t));
  const stops = [
    [0.00, [68,  1, 84]],
    [0.20, [59, 82,139]],
    [0.40, [33,144,141]],
    [0.60, [93,201, 99]],
    [0.80, [253,231, 37]],
    [1.00, [253, 80, 60]]
  ];
  for (let i = 0; i < stops.length - 1; i++) {
    if (t <= stops[i+1][0]) {
      const f = (t - stops[i][0]) / (stops[i+1][0] - stops[i][0]);
      const c = [0, 1, 2].map(k => Math.round(stops[i][1][k] * (1 - f) + stops[i+1][1][k] * f));
      return 'rgb(' + c[0] + ',' + c[1] + ',' + c[2] + ')';
    }
  }
  return 'rgb(253,80,60)';
}
function el(tag, attrs, children) {
  const e = document.createElement(tag);
  if (attrs) for (const k in attrs) {
    if (k === 'style' && typeof attrs[k] === 'object') Object.assign(e.style, attrs[k]);
    else if (k.startsWith('on') && typeof attrs[k] === 'function') e.addEventListener(k.slice(2), attrs[k]);
    else e.setAttribute(k, attrs[k]);
  }
  if (children) {
    if (!Array.isArray(children)) children = [children];
    for (const c of children) {
      if (c == null) continue;
      if (typeof c === 'string' || typeof c === 'number') e.appendChild(document.createTextNode(String(c)));
      else e.appendChild(c);
    }
  }
  return e;
}
function svg(tag, attrs, children) {
  const e = document.createElementNS('http://www.w3.org/2000/svg', tag);
  if (attrs) for (const k in attrs) e.setAttribute(k, attrs[k]);
  if (children) {
    if (!Array.isArray(children)) children = [children];
    for (const c of children) {
      if (c == null) continue;
      if (typeof c === 'string' || typeof c === 'number') e.appendChild(document.createTextNode(String(c)));
      else e.appendChild(c);
    }
  }
  return e;
}

const PARTS = DATA.parts;
const PART_BY_ID = Object.fromEntries(PARTS.map(p => [p.id, p]));
const FACES = DATA.faces;
const FACE_BY_CODE = Object.fromEntries(FACES.map(f => [f.code, f]));
const RESULTS = DATA.results;
// device_bbox = null in payload when no device_layout.json and no positions
// to derive a bbox from. Consumers must check DEVICE_BBOX before using.
const DEVICE_BBOX = DATA.device_bbox;

const STATE = {
  metric: 'g',
  face: 'ALL',
  scale: 'linear',
  filter: '',
  ii: {
    face: (FACE_BY_CODE.F2 ? 'F2' : (FACES[0] ? FACES[0].code : 'F2')),
    metric: 'g',
    norm: 'abs',
    thresh: 0,
    hovered_pos: null,
    pinned: false,
    selected_part: null
  }
};

function metricLabel(m) {
  return ({
    g: 'Peak G',
    s: 'sigma' + _uSuffix('stress'),
    e: 'eps',
    d: 'd' + _uSuffix('disp')
  })[m] || m;
}

function scaleNorm(v, mx) {
  if (mx <= 0) return 0;
  if (STATE.scale === 'log') return Math.log10(1 + Math.max(0, v)) / Math.log10(1 + mx);
  return v / mx;
}

const FACE_RESULTS = {};
const FACE_PART_RESULTS = {};
const FACE_POS_MAX = {};
for (const r of RESULTS) {
  (FACE_RESULTS[r.face] = FACE_RESULTS[r.face] || []).push(r);
  const fk = r.face + '|' + r.part_id;
  (FACE_PART_RESULTS[fk] = FACE_PART_RESULTS[fk] || []).push(r);
  const pk = r.face + '|' + r.pos_id;
  if (!FACE_POS_MAX[pk] || FACE_POS_MAX[pk].g < r.g) FACE_POS_MAX[pk] = r;
}

function faceBBox(faceCode) {
  const rows = FACE_RESULTS[faceCode] || [];
  if (!rows.length) return [0, 0, 0, 0];
  let xmin = Infinity, xmax = -Infinity, ymin = Infinity, ymax = -Infinity;
  for (const r of rows) {
    if (r.x < xmin) xmin = r.x; if (r.x > xmax) xmax = r.x;
    if (r.y < ymin) ymin = r.y; if (r.y > ymax) ymax = r.y;
  }
  if (xmin === xmax) { xmin -= 1; xmax += 1; }
  if (ymin === ymax) { ymin -= 1; ymax += 1; }
  const padX = (xmax - xmin) * 0.08, padY = (ymax - ymin) * 0.08;
  return [xmin - padX, xmax + padX, ymin - padY, ymax + padY];
}
function maxMetric(rows) {
  let m = 0;
  for (const r of rows) { const v = r[STATE.metric] || 0; if (v > m) m = v; }
  return m;
}

const UNIT_LABELS = DATA.unit_labels || {
  acc: '', stress: '', disp: '', vel: '', energy: '', time: '', mass: '', force: ''
};
function _u(key) { return UNIT_LABELS[key] || ''; }
// M11: acc 원시값(mm/s2 등) → G 환산 공용 헬퍼 — s1/s3/s5 표기 통일.
function gDivisor() {
  return (DATA.part_motion && (DATA.part_motion.g_divisor || DATA.part_motion.g_mm_s2)) || 9810.0;
}
function toG(v) { return (v || 0) / gDivisor(); }
function _uSuffix(key) { const v = _u(key); return v ? ' (' + v + ')' : ''; }
// density 단위 (mass/length³) — unit_labels 에는 별도 키가 없으니 mass + disp 로 조합.
// ton-mm-s → 'tonne/mm³'  /  SI → 'kg/m³'.
function _uDensity() {
  const m = (UNIT_LABELS.mass || '').trim();
  const l = (UNIT_LABELS.disp || '').trim();
  return (m && l) ? m + '/' + l + '³' : '';
}
function _uDensitySuffix() { const v = _uDensity(); return v ? ' (' + v + ')' : ''; }

function applyUnitLabels() {
  // Inject unit labels into HTML placeholders. Empty when units unspecified.
  const set = (id, text) => { const e = document.getElementById(id); if (e) e.textContent = text; };
  set('kWorstSUnit', _u('stress'));
  set('topkXUnit', _uSuffix('disp'));
  set('topkYUnit', _uSuffix('disp'));
  set('topkSUnit', _uSuffix('stress'));
  set('ppg-bar-cap-unit', _uSuffix('acc'));
  set('ppg-th-acc', _u('acc'));
  set('ppg-th-time', _u('time'));
  set('ppg-th-vel', _u('vel'));
  set('ppg-th-disp', _u('disp'));
}

"""


_JS_WIRING = r"""function wireControlBar() {
  document.querySelectorAll('.ctlbar .btn').forEach(btn => {
    btn.addEventListener('click', function () {
      if (btn.dataset.iiFace) {
        STATE.ii.face = btn.dataset.iiFace;
        // clear hover state on face switch
        STATE.ii.hovered_pos = null;
        STATE.ii.selected_part = null;
        document.querySelectorAll('.ctlbar .btn[data-ii-face]').forEach(b => b.classList.toggle('active', b.dataset.iiFace === STATE.ii.face));
        renderInspector();
        renderInfluenceMatrix();
      } else if (btn.dataset.iiMetric) {
        STATE.ii.metric = btn.dataset.iiMetric;
        STATE.metric = STATE.ii.metric;  // keep legacy metric in sync for other panels
        document.querySelectorAll('.ctlbar .btn[data-ii-metric]').forEach(b => b.classList.toggle('active', b.dataset.iiMetric === STATE.ii.metric));
        renderAll();
      } else if (btn.dataset.iiNorm) {
        STATE.ii.norm = btn.dataset.iiNorm;
        document.querySelectorAll('.ctlbar .btn[data-ii-norm]').forEach(b => b.classList.toggle('active', b.dataset.iiNorm === STATE.ii.norm));
        renderInspector();
      }
    });
  });
  const thresh = document.getElementById('ii-thresh');
  if (thresh) thresh.addEventListener('input', function () {
    STATE.ii.thresh = parseInt(thresh.value, 10) || 0;
    renderInspector();
  });
  const pin = document.getElementById('ii-pin');
  if (pin) pin.addEventListener('change', function () {
    STATE.ii.pinned = pin.checked;
    const lab = document.getElementById('ii-pin-lab');
    if (lab) lab.classList.toggle('locked', STATE.ii.pinned);
    if (!STATE.ii.pinned) {
      STATE.ii.hovered_pos = null;
      _renderInspectorClear();
    }
  });
}

function renderAll() {
  renderBiFaceSplit();
  initFaceKpiTable();
  initTopK();
  renderInspector();
  renderInfluenceMatrix();
  renderTSGrid();
  renderVerdict();
}

function initReveal() {
  if (!('IntersectionObserver' in window)) {
    document.querySelectorAll('.r').forEach(n => n.classList.add('in'));
    return;
  }
  const io = new IntersectionObserver(function (entries) {
    for (const e of entries) {
      if (e.isIntersecting) {
        e.target.classList.add('in');
        io.unobserve(e.target);
      }
    }
  }, { rootMargin: '0px 0px -80px 0px' });
  document.querySelectorAll('.r').forEach(n => io.observe(n));
}

function initNav() {
  const navs = document.querySelectorAll('.topbar .nav a');
  navs.forEach(a => a.addEventListener('click', function () {
    const tgt = document.getElementById(a.dataset.target);
    if (tgt) tgt.scrollIntoView({ behavior: 'smooth' });
  }));
  window.addEventListener('scroll', function () {
    const sections = ['s1', 's2', 's3', 's4', 's5', 's6', 's7', 's8', 's9'];
    const y = window.scrollY + 120;
    let active = sections[0];
    for (const id of sections) {
      const sec = document.getElementById(id);
      if (sec && sec.offsetTop <= y) active = id;
    }
    navs.forEach(a => a.classList.toggle('active', a.dataset.target === active));
  });
}

"""


_JS_TABS = r"""// --- Intra-section sub-tabs (Sections 05/06/07) ---------------------------
function initSubTabs(sectionId, groups) {
  // groups = [{tab_id, label, panel_ids: [string]}]
  const sec = document.getElementById(sectionId);
  if (!sec) return;
  const bar = document.createElement('div');
  bar.className = 'subtab-bar';
  groups.forEach((g, idx) => {
    const btn = document.createElement('button');
    btn.textContent = g.label;
    if (idx === 0) btn.classList.add('active');
    btn.addEventListener('click', () => {
      bar.querySelectorAll('button').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      groups.forEach(gg => {
        gg.panel_ids.forEach(pid => {
          const el = document.getElementById(pid);
          if (el) el.style.display = (gg === g) ? '' : 'none';
        });
      });
    });
    bar.appendChild(btn);
  });
  const head = sec.querySelector('.page-head');
  if (head) head.insertAdjacentElement('afterend', bar);
  groups.forEach((g, idx) => {
    g.panel_ids.forEach(pid => {
      const el = document.getElementById(pid);
      if (el) el.style.display = (idx === 0) ? '' : 'none';
    });
  });
}

const INSIGHT_STATE = { active_panel: null, hover_pos: null };

function initInsights() {
  const data = (DATA && DATA.insights) || null;
  const sec = document.getElementById('s7');
  const navLink = document.getElementById('navS7');
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
  _insightRenderSymmetry(DATA.insights && DATA.insights.Symmetry);
  _insightRenderDamageIndex(DATA.insights);
  _insightRenderReboundField(DATA.insights && DATA.insights.ReboundField);
  _insightRenderAutoRecommend(DATA.insights.auto_recommend);
  _insightRenderContactPulse(DATA.insights.ContactPulse);
  _insightRenderTrajectory3D(DATA.insights && DATA.insights.Trajectory3D);
  // === INSIGHT_BOOT_CALLS_INSERT_HERE ===
  // Workflow-added _insightRenderXxx(data) calls are inserted ABOVE this line.
}

// === DEEP_JS_FUNCTIONS_INSERT_HERE ===
// Section-06 _deepRenderXxx render functions are inserted ABOVE this line.

const DEEP_STATE = { active_part: null, srs_pos: null };

function initDeepAnalytics() {
  const data = (DATA && DATA.deep_analytics) || null;
  const sec = document.getElementById('s6');
  const navLink = document.getElementById('navS6');
  if (!data || !sec) {
    if (sec) sec.style.display = 'none';
    if (navLink) navLink.style.display = 'none';
    return;
  }
  // If every sub-key is missing/empty, hide the section.
  const populated = Object.keys(data).some(k => {
    const v = data[k];
    return v && (typeof v !== 'object' || Object.keys(v).length > 0 || (Array.isArray(v) && v.length > 0));
  });
  if (!populated) {
    sec.style.display = 'none';
    if (navLink) navLink.style.display = 'none';
    return;
  }
_deepRenderFFT(DATA.deep_analytics);
_deepRenderSRS(DATA);
  _deepRenderSafeDropZone(DATA);
_deepRenderPCAModal(DATA.deep_analytics);
_deepRenderAnomalyDetection(DATA);
_deepRenderPerPartDrillDown(data);
  // === DEEP_BOOT_CALLS_INSERT_HERE ===
  // Workflow-added _deepRenderXxx(data) calls are inserted ABOVE this line.
}

const DOE_STATE = { metric: 'peak_g', sort: 'value', active_pos: null };

"""


_JS_LAZY = r"""function registerLazy(id, fn) { LAZY_INIT[id] = fn; }
function fireLazy(id) {
  const fn = LAZY_INIT[id];
  if (!fn) return;
  delete LAZY_INIT[id];
  try { fn(); } catch (e) { console.error('lazy init ' + id + ' failed:', e); }
}
function setupLazyObserver() {
  if (!('IntersectionObserver' in window)) {
    Object.keys(LAZY_INIT).forEach(fireLazy);
    return;
  }
  const obs = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (e.isIntersecting && LAZY_INIT[e.target.id]) {
        fireLazy(e.target.id);
        obs.unobserve(e.target);
      }
    });
  }, { rootMargin: '300px' });
  Object.keys(LAZY_INIT).forEach(function (id) {
    const el = document.getElementById(id);
    if (el) obs.observe(el);
  });
  document.querySelectorAll('.topbar .nav a[data-target]').forEach(function (a) {
    a.addEventListener('click', function () {
      fireLazy(a.getAttribute('data-target'));
    });
  });
}

// --- 청크 로더 (tier C/D, P4-3) --------------------------------------------
// file:// 에서 fetch/XHR 가 막히므로 <script src> JSONP 방식만 사용한다.
// 청크 파일은 window.KOO_CHUNKS[id] 에 per-position 번들을 넣는다.
window.KOO_CHUNKS = window.KOO_CHUNKS || {};
const _CHUNK_WAITERS = {};
function loadChunk(id, cb) {
  if (window.KOO_CHUNKS[id]) { if (cb) cb(window.KOO_CHUNKS[id]); return; }
  const man = DATA.chunks;
  if (!man || !man.ids || man.ids.indexOf(id) < 0) { if (cb) cb(null); return; }
  if (_CHUNK_WAITERS[id]) { if (cb) _CHUNK_WAITERS[id].push(cb); return; }
  _CHUNK_WAITERS[id] = cb ? [cb] : [];
  const s = document.createElement('script');
  s.src = man.dir + '/' + id + '.js';
  s.onload = function () {
    const data = window.KOO_CHUNKS[id] || null;
    (_CHUNK_WAITERS[id] || []).forEach(function (f) { try { f(data); } catch (e) { console.error(e); } });
    delete _CHUNK_WAITERS[id];
  };
  s.onerror = function () {
    console.error('chunk load failed: ' + id);
    (_CHUNK_WAITERS[id] || []).forEach(function (f) { try { f(null); } catch (e) {} });
    delete _CHUNK_WAITERS[id];
  };
  document.head.appendChild(s);
}
// pos_id → 청크 id (Python emit._chunk_fname 과 동일 규칙)
function chunkIdForPos(posId) {
  return 'pos_' + String(posId).replace(/[^A-Za-z0-9_-]/g, '_');
}

"""


_JS_TAIL = r"""function _renderDataQualityBadges() {
  // s1 page-head 아래 데이터 신뢰성 배지 — reviewer 가 "측정값" 으로 오해 안 하도록.
  const host = document.getElementById('data-quality-badges');
  if (!host) return;
  const badges = [];
  // synthetic footprint
  const parts = DATA.parts || [];
  const syn = parts.filter(p => p._synthetic_footprint).length;
  if (syn > 0) {
    badges.push({
      cls: 'warn',
      label: 'SYNTHETIC FOOTPRINTS ' + syn + '/' + parts.length,
      title: 'part footprint XY 가 loader 의 hash 기반 placeholder 임. 실측 mesh 가 아님.',
    });
  }
  // 에너지 측정 배지 — 3상태 (정직화):
  //   1) NO ENERGY MEASURED     : binout energy_flow 도 없고, glstat 에서도
  //      impact 가 보이는 런이 0 → 어디에서도 에너지 미측정.
  //   2) IMPACT NOT IN GLSTAT WINDOW (k/N): 일부 런의 glstat 윈도우에서 KE 가
  //      평탄 — 그 런들은 dissipation 통계에서 제외됨.
  //   3) 없음: 진짜로 측정됨.
  // (이전: solver_quality 가 '존재만' 해도 배지를 숨겨 energy_flows={} 전량
  //  빈 값이 무음 통과 — 2026-06 산출물 실증. 존재가 아니라 impact_visible
  //  기준으로 판정한다.)
  // H5-2: 설계 한계 미제공 배지 — P95/P75 는 자기분포 기준임을 명시.
  // H5-4: --g-limit/--stress-limit/yield 중 하나라도 제공되면 미표시.
  const _yieldMap = ((DATA.meta || {}).sim_params || {}).yield_stress_by_part || {};
  const _hasUserLimit = ((DATA.kpi || {}).crit_basis === 'user') ||
                        ((DATA.kpi || {}).stress_limit != null);
  if (!DATA.risk_score && !_hasUserLimit && Object.keys(_yieldMap).length === 0) {
    badges.push({
      cls: 'warn',
      label: 'NO DESIGN LIMITS PROVIDED',
      title: '판정 기준(CRIT/WARN)은 자기분포 P95/P75 — 설계 한계(항복응력, G 스펙) 미제공. --yield-stress 또는 *MAT 카드로 절대 기준 제공 가능.',
    });
  }
  const ef = DATA.energy_flows || {};
  const hasFlowReal = Object.keys(ef).length > 0 && !('__mock__' in ef);
  const sqSum0 = (DATA.solver_quality && DATA.solver_quality.summary) || null;
  const sqN0 = sqSum0 ? (sqSum0.n || 0) : 0;
  const sqVisible = sqSum0 ? (sqSum0.impact_visible_count || 0) : 0;
  if (!hasFlowReal && sqVisible === 0) {
    badges.push({
      cls: 'warn',
      label: 'NO ENERGY MEASURED',
      title: 'binout energy_flow 없음 + glstat 윈도우에 impact 가 보이는 런 0. '
           + 'ENERGY DISSIPATED KPI 는 N/A (조작성 0.0 표시 금지).',
    });
  } else if (sqN0 > 0 && sqVisible < sqN0) {
    const kNv = sqN0 - sqVisible;
    badges.push({
      cls: 'warn',
      label: 'IMPACT NOT IN GLSTAT WINDOW (' + kNv + '/' + sqN0 + ')',
      title: '해당 런들의 glstat 기록 구간에서 KE 가 평탄 — 충돌이 그 윈도우에 '
           + '없음. dissipation 통계·KPI 에서 제외됨.',
    });
  }
  // mass=0 (impactor mass 추출 실패 잔재)
  const imp = (DATA.meta && DATA.meta.impactor) || {};
  if (!(imp.mass > 0)) {
    badges.push({
      cls: 'warn',
      label: 'IMPACTOR MASS UNKNOWN',
      title: 'matsum/keyword 에서 mass 추출 실패. scenario.json 의 impactor.type 명시 권장.',
    });
  } else if (imp.geometry_source === 'motion-bbox') {
    // mass>0 이지만 geometry 가 d3plot bounding-box 에서 추정됨 (step_config
    // 부재). bbox 는 진짜 radius 를 과대평가 → ρ·V mass 가 부풀 수 있음.
    badges.push({
      cls: 'warn',
      label: 'IMPACTOR GEOMETRY ESTIMATED',
      title: 'impactor radius 가 d3plot bounding-box 에서 추정됨 (step_config.txt 부재). '
           + '실제 mesh radius 보다 클 수 있어 mass/KE 가 과대평가될 위험. '
           + 'step_config.txt 또는 scenario.json 의 impactor geometry 명시 권장.',
    });
  }
  // solver_quality: glstat 기반 energy-balance verdict
  const sq = (DATA.solver_quality && DATA.solver_quality.summary) || null;
  if (sq && sq.n > 0) {
    const total = sq.n;
    const pass = sq.pass || 0, warn = sq.warn || 0, fail = sq.fail || 0;
    const td = sq.te_drift_pct_median, hg = sq.hg_fraction_pct_median, sf = sq.sl_fraction_pct_median;
    const tooltip = 'glstat 기반 energy-balance audit (LSDYNA 안정성 게이트)\\n'
                  + '  PASS=' + pass + ' / WARN=' + warn + ' / FAIL=' + fail + ' / total=' + total + '\\n'
                  + '  TE drift median = ' + (td != null ? td.toFixed(2) + '%' : '?')
                  + ' (산업 기준 < 2% PASS, < 5% WARN)\\n'
                  + '  Hourglass / IE median = ' + (hg != null ? hg.toFixed(1) + '%' : '?')
                  + ' (< 10% PASS, < 20% WARN)\\n'
                  + '  Sliding / KE0 median = ' + (sf != null ? sf.toFixed(1) + '%' : '?')
                  + ' (< 5% PASS, < 10% WARN)';
    let label, cls;
    if (fail > 0) {
      label = 'ENERGY BALANCE: FAIL (' + fail + '/' + total + ')';
      cls = 'crit';
    } else if (warn > 0) {
      label = 'ENERGY BALANCE: WARN (' + warn + '/' + total + ')';
      cls = 'warn';
    } else if (pass === total && total > 0) {
      label = 'ENERGY BALANCE: PASS (' + total + '/' + total + ')';
      cls = 'good';
    } else {
      label = 'ENERGY BALANCE: UNKNOWN';
      cls = 'warn';
    }
    badges.push({ cls, label, title: tooltip });
  }
  if (!badges.length) return;
  const _palette = {
    warn: { bg: 'rgba(240,180,0,0.12)', fg: 'var(--warn)', border: 'var(--warn)' },
    crit: { bg: 'rgba(232,93,117,0.14)', fg: 'var(--crit)', border: 'var(--crit)' },
    good: { bg: 'rgba(93,210,138,0.12)', fg: 'var(--good)', border: 'var(--good)' },
  };
  badges.forEach(b => {
    const p = _palette[b.cls] || _palette.warn;
    const el = document.createElement('span');
    el.title = b.title;
    el.textContent = b.label;
    el.style.cssText = 'display:inline-block;padding:3px 8px;border-radius:3px;font-size:10px;font-weight:600;letter-spacing:0.6px;font-family:JetBrains Mono,monospace;'
      + 'background:' + p.bg + ';color:' + p.fg + ';border:1px solid ' + p.border + ';cursor:help;white-space:pre';
    host.appendChild(el);
  });
}

function boot() {
  document.documentElement.style.setProperty('--device-aspect', (DATA.device_geometry && DATA.device_geometry.aspect) ? DATA.device_geometry.aspect : 1);
  applyUnitLabels();
  fillHeroKpi();
  _renderDataQualityBadges();
  initImpactor();
  initDoeBreakdown();
  renderAll();
  renderFindings();
  initNav();
  initReveal();
  wireControlBar();

  // Section 03 — VERDICT + ENERGY FLOW
  registerLazy('s3', function () {
    initEnergyFlowPage();
    initEnergyGraph();
    initEnergyResidence();
    initSunburst();
    initSankey();
    initTimeForceHeatmap();
    initConservation();
    initBounceVectorMap();
    initTrajectoryClustering();
    initPhaseDiagram();
    initContactTimeline();
    initTrajectoryBundle3D();
    // rcforc 계측 신뢰 — 없으면 패널이 스스로 숨는다(에러 아님)
    if (typeof renderContactTrust === 'function') {
      renderContactTrust(typeof _EF_POS !== 'undefined' ? _EF_POS : null);
    }
  });

  // Section 04 — PER-PART G
  registerLazy('s4', function () {
    initPerPartPeakG();
  });

  // Section 05 — DOE SPATIAL ANALYSIS (sub-tabs must come after init)
  registerLazy('s5', function () {
    initDoeAnalysis();
    initSubTabs('s5', [
      { tab_id: 's5-spatial', label: 'SPATIAL', panel_ids: [
        'doe-kpi-strip', 'doe-ctlbar',
        'doe-grid-heat-rank', 'doe-panel-heatmap', 'doe-panel-ranking',
        'doe-grid-pp', 'doe-panel-pp-matrix',
        'doe-grid-traj-env', 'doe-panel-trajectory'
      ]},
      { tab_id: 's5-perpart', label: 'PER-PART', panel_ids: [
        'doe-panel-envelope', 'doe-panel-failure-risk'
      ]},
      { tab_id: 's5-advanced', label: 'ADVANCED', panel_ids: [
        'doe-corr-network-panel', 'panel-pareto-severity',
        'doe-grid-idw', 'idw-pred-panel',
        'doe-grid-energy', 'doe-panel-energy',
        'doe-panel-toa'
      ]}
    ]);
  });

  // Section 06 — DEEP ANALYTICS
  registerLazy('s6', function () {
    initDeepAnalytics();
    initSubTabs('s6', [
      { tab_id: 's6-freq', label: 'FREQUENCY', panel_ids: [
        'deep-fft-panel', 'deep-srs-panel'
      ]},
      { tab_id: 's6-stat', label: 'STATISTICAL', panel_ids: [
        'deep-pca-modal-panel', 'deep-anomaly-panel'
      ]},
      { tab_id: 's6-spatial', label: 'SPATIAL', panel_ids: [
        'deep-safe-drop-zone-panel', 'ppd-host'
      ]}
    ]);
  });

  // Section 07 — INSIGHTS
  registerLazy('s7', function () {
    initInsights();
    initSubTabs('s7', [
      { tab_id: 's7-design', label: 'DESIGN', panel_ids: [
        'insight-panel-symmetry', 'insight-panel-trajectory3d'
      ]},
      { tab_id: 's7-damage', label: 'DAMAGE', panel_ids: [
        'insight-DamageIndex', 'insight-panel-ContactPulse'
      ]},
      { tab_id: 's7-action', label: 'ACTION', panel_ids: [
        'insight-rebound-field', 'insight-panel-auto-recommend'
      ]}
    ]);
  });

  // Section 08 — PHYSICS
  registerLazy('s8', function () {
    initPhysics();
  });

  // Section 09 — POSITION DRILL-DOWN (P6)
  registerLazy('s9', function () {
    if (typeof initS9 === 'function') initS9();
  });

  setupLazyObserver();
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
else boot();
"""
