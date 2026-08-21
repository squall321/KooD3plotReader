# 섹션 10 — SET REPORT: 세트 응력 뷰 위에 충격 위치를 오버레이 (호버=위치별 컨투어, 클릭=영상)
"""Custom Report(세트 후처리) 연동 섹션.

핵심 UX (사용자 요청): 충격 위치 마커가 **응력 뷰 이미지 위에 겹쳐** 있다.
같은 메시·같은 카메라(뷰 메타)로 찍힌 이미지들이라 마커 좌표는 위치가
바뀌어도 고정 — 호버하면 배경 이미지만 그 위치의 피크 컨투어로 바뀐다.
클릭하면 그 위치의 영상 모달. 미디어는 <stem>_data/set_media/ 파일 참조
(base64 인라인 금지 — 용량 원칙).
"""

_PAGE10 = """
<section class="page" id="s10">
  <div class="page-head r">
    <span class="num">10</span><span class="tagline">SET &middot; OVERLAY</span>
    <span class="ttl">세트 보고서 &mdash; 응력 뷰 위 충격 위치 오버레이</span>
    <span class="sub">CUSTOM SET REPORT</span>
  </div>

  <div class="ctlbar r" id="s10-ctlbar">
    <div class="grp"><span class="lbl">세트</span>
      <select id="s10-set-select"></select>
    </div>
    <div class="grp"><span class="lbl">지표</span>
      <button class="btn active" data-s10-metric="s">&sigma;_vm</button>
      <button class="btn" data-s10-metric="e">&epsilon;_p</button>
    </div>
    <div class="grp" style="margin-left:auto">
      <span id="s10-range" style="font-size:11px;opacity:.7"></span>
    </div>
  </div>

  <div class="panel r">
    <div class="ph"><span class="pt">위치 오버레이 &mdash; 호버: 그 위치의 피크 컨투어 &middot; 클릭: 영상</span>
      <span class="pd" id="s10-info"></span></div>
    <div id="s10-stage" style="position:relative;max-width:960px;margin:0 auto">
      <img id="s10-img" style="display:block;width:100%;border-radius:4px">
      <svg id="s10-ov" style="position:absolute;inset:0;width:100%;height:100%"></svg>
    </div>
    <div class="pcap" id="s10-cap"></div>
  </div>
  <div id="s10-modal" style="display:none;position:fixed;inset:0;z-index:80;
       background:rgba(0,0,0,.85);align-items:center;justify-content:center"></div>
</section>
"""

_JS_S10 = r"""
// ============ Section 10: SET REPORT (응력 뷰 오버레이) ============
const S10 = { set: 0, metric: 's', hover: -1, cur: -1 };

function s10Data() { return DATA.set_report || null; }

// 모델좌표 (x,y) → 이미지 분율 좌표 [0..1]. 뷰 메타(카메라 변환) 사용.
// z 항은 origin 기준으로 소거된다 (탑뷰 기저는 z 성분이 0).
function s10Map(meta, x, y) {
  const dx = x - meta.origin[0], dy = y - meta.origin[1];
  const u = dx * meta.u[0] + dy * meta.u[1];
  const v = dx * meta.v[0] + dy * meta.v[1];
  return [(u / meta.half_w + 1) / 2, (1 - v / meta.half_h) / 2];
}

function s10SetImage(pi) {
  const SR = s10Data();
  const img = document.getElementById('s10-img');
  const info = document.getElementById('s10-info');
  const m = (SR.media[S10.set] || [])[pi];
  const pos = SR.positions[pi];
  if (!m || !m.png) {
    info.textContent = pos ? pos.id + ' — 렌더 산출물 없음 (미실행)' : '';
    return;
  }
  S10.cur = pi;
  img.src = m.png;
  const sv = SR.stress[S10.set][pi], ev = SR.strain[S10.set][pi];
  const bits = ['<b>' + pos.id + '</b>'];
  if (sv !== null) bits.push('σ_vm ' + sv.toFixed(2) + ' MPa');
  if (ev !== null) bits.push('ε_p ' + ev.toFixed(5));
  if (m.mp4) bits.push('▶ 클릭 시 영상');
  info.innerHTML = bits.join(' · ');
}

function s10Draw() {
  const SR = s10Data();
  const meta = SR.meta[S10.set];
  const ov = document.getElementById('s10-ov');
  const vals = (S10.metric === 's' ? SR.stress : SR.strain)[S10.set];
  const finite = vals.filter(v => v !== null);
  const vmin = finite.length ? Math.min(...finite) : 0;
  const vmax = finite.length ? Math.max(...finite) : 1;
  // 산출이 하나도 없는 지표는 범위를 지어내지 않는다 (결측 ≠ 0~1)
  document.getElementById('s10-range').textContent =
    (S10.metric === 's' ? 'σ_vm [MPa] ' : 'ε_p ') +
    (finite.length
      ? vmin.toFixed(S10.metric === 's' ? 1 : 5) + ' ~ ' + vmax.toFixed(S10.metric === 's' ? 1 : 5)
      : '산출 없음');

  const W = meta.width, H = meta.height;
  ov.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
  ov.setAttribute('preserveAspectRatio', 'none');

  let svg = '';
  S10._pts = [];
  for (let pi = 0; pi < SR.positions.length; pi++) {
    const p = SR.positions[pi];
    // 모델 좌표(mx/my — 임팩터 궤적 기원)만 오버레이 가능. 디바이스 로컬
    // 좌표(x/y)는 뷰 메타와 좌표계가 달라 쓰면 안 된다.
    if (p.mx === null || p.mx === undefined) continue;
    const [fx, fy] = s10Map(meta, p.mx, p.my);
    const cx = fx * W, cy = fy * H;
    const off = cx < 0 || cx > W || cy < 0 || cy > H;   // 세트 뷰 밖 낙하점
    const cxc = Math.max(8, Math.min(W - 8, cx));
    const cyc = Math.max(8, Math.min(H - 8, cy));
    const has = vals[pi] !== null;
    const media = (SR.media[S10.set] || [])[pi];
    S10._pts.push({ pi, x: cxc, y: cyc, has: !!(media && media.png) });
    const col = has ? gColor(vmax > vmin ? (vals[pi] - vmin) / (vmax - vmin) : 0.5) : 'none';
    if (off) {
      // 뷰 밖: 가장자리에 작은 점선 링 — 안쪽 마커와 구분
      svg += '<circle data-pos="' + p.id + '" cx="' + cxc.toFixed(1) + '" cy="' + cyc.toFixed(1) +
             '" r="5" fill="' + (has ? col : 'rgba(120,130,160,.2)') +
             '" stroke="rgba(200,200,220,.8)" stroke-dasharray="2,2" stroke-width="1"' +
             ' style="cursor:pointer"><title>' + p.id + ' (세트 뷰 밖)' +
             (has ? ': ' + vals[pi].toFixed(2) : '') + '</title></circle>';
    } else {
      const r = has ? 9 : 5;
      svg += '<circle data-pos="' + p.id + '" cx="' + cxc.toFixed(1) + '" cy="' + cyc.toFixed(1) +
             '" r="' + r + '" fill="' + (has ? col : 'rgba(120,130,160,.25)') +
             '" stroke="' + (pi === S10.hover ? '#fff' : 'rgba(0,0,0,.55)') +
             '" stroke-width="' + (pi === S10.hover ? 2.5 : 1) + '" style="cursor:pointer">' +
             '<title>' + p.id + (has ? ': ' + vals[pi].toFixed(2) : ' (미실행)') + '</title></circle>';
    }
  }
  ov.innerHTML = svg;
}

function s10Nearest(evt) {
  const ov = document.getElementById('s10-ov');
  const SR = s10Data();
  const meta = SR.meta[S10.set];
  const rect = ov.getBoundingClientRect();
  const x = (evt.clientX - rect.left) * meta.width / rect.width;
  const y = (evt.clientY - rect.top) * meta.height / rect.height;
  let best = -1, bd = 30 * 30;
  for (const p of S10._pts) {
    const d = (p.x - x) * (p.x - x) + (p.y - y) * (p.y - y);
    if (d < bd) { bd = d; best = p.pi; }
  }
  return best;
}

function s10OpenVideo(src) {
  const m = document.getElementById('s10-modal');
  m.innerHTML = '<span style="position:absolute;top:14px;right:22px;color:#fff;' +
    'font-size:28px;cursor:pointer" onclick="s10CloseVideo()">&times;</span>' +
    '<video controls autoplay src="' + src + '" style="max-width:92vw;max-height:86vh"></video>';
  m.style.display = 'flex';
}
function s10CloseVideo() {
  const m = document.getElementById('s10-modal');
  if (m) { m.style.display = 'none'; m.innerHTML = ''; }
}

function initS10() {
  const sec = document.getElementById('s10');
  if (!sec || sec.dataset.done) return;
  const SR = s10Data();
  const nav = document.getElementById('navS10');
  // 산출물이 없으면 섹션·네비 자체를 숨긴다 (mock/미실행 대응)
  if (!SR || !SR.sets || !SR.sets.length || !SR.positions || !SR.positions.length ||
      !SR.meta || !SR.meta[0]) {
    sec.style.display = 'none';
    if (nav) nav.style.display = 'none';
    return;
  }
  sec.dataset.done = '1';

  const sel = document.getElementById('s10-set-select');
  sel.innerHTML = SR.sets.map((s, i) =>
    '<option value="' + i + '">' + s.name + ' (' + s.type + ' ' + s.id + ')</option>').join('');
  sel.addEventListener('change', () => {
    S10.set = +sel.value; S10.hover = -1; s10Draw(); s10InitImage();
  });
  document.querySelectorAll('[data-s10-metric]').forEach(b =>
    b.addEventListener('click', () => {
      document.querySelectorAll('[data-s10-metric]').forEach(x => x.classList.remove('active'));
      b.classList.add('active');
      S10.metric = b.dataset.s10Metric; s10Draw();
    }));

  const ov = document.getElementById('s10-ov');
  ov.addEventListener('mousemove', e => {
    const pi = s10Nearest(e);
    if (pi !== S10.hover) {
      S10.hover = pi; s10Draw();
      if (pi >= 0) { s10SetImage(pi); if (typeof xlinkHover === 'function') xlinkHover(SR.positions[pi].id, true); }
    }
  });
  ov.addEventListener('mouseleave', () => { S10.hover = -1; s10Draw(); });
  ov.addEventListener('click', e => {
    const pi = s10Nearest(e);
    if (pi < 0) return;
    const m = (SR.media[S10.set] || [])[pi];
    if (m && m.mp4) s10OpenVideo(m.mp4);
    else if (typeof selectPosition === 'function') selectPosition(SR.positions[pi].id, { source: 's10' });
  });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') s10CloseVideo(); });
  document.getElementById('s10-modal').addEventListener('click', e => {
    if (e.target.id === 's10-modal') s10CloseVideo();
  });

  const cap = document.getElementById('s10-cap');
  cap.textContent = (SR.note || '') +
    ' 마커 = 충격 위치 (값 색). 회색 작은 점 = custom report 미실행 위치.';

  s10Draw();
  s10InitImage();
}

function s10InitImage() {
  // 초기 이미지 = 세트 피크가 가장 큰 위치 (없으면 첫 산출물 위치)
  const SR = s10Data();
  const vals = SR.stress[S10.set];
  let best = -1, bv = -Infinity;
  for (let i = 0; i < vals.length; i++) {
    const m = (SR.media[S10.set] || [])[i];
    if (!(m && m.png)) continue;
    const v = vals[i] === null ? -Infinity : vals[i];
    if (best < 0 || v > bv) { best = i; bv = v; }
  }
  if (best >= 0) s10SetImage(best);
}
"""
