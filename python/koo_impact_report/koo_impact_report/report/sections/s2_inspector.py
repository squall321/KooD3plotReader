# 섹션 02 — IMPACT INSPECTOR (bi-face 응답 탐색기) HTML 템플릿 (기계적 분할, 바이트 불변)

_PAGE2 = """
<section class="page" id="s2">
  <div class="page-head r">
    <span class="num">02</span><span class="tagline">IMPACT INSPECTOR</span>
    <span class="ttl">충격 위치 = 화면, 부품 응답 = 부품 라이트업</span>
    <span class="sub">HOVER-DRIVEN BI-FACE STRESS EXPLORER</span>
  </div>

  <div class="ctlbar r">
    <div class="grp"><span class="lbl">FACE</span>
      <button class="btn active" data-ii-face="F2">FRONT &middot; F2</button>
      <button class="btn" data-ii-face="F1">BACK &middot; F1</button>
    </div>
    <div class="grp"><span class="lbl">METRIC</span>
      <button class="btn active" data-ii-metric="g">PEAK G</button>
      <button class="btn" data-ii-metric="s">&sigma;</button>
      <button class="btn" data-ii-metric="e">&epsilon;</button>
      <button class="btn" data-ii-metric="d">d</button>
    </div>
    <div class="grp"><span class="lbl">NORM</span>
      <button class="btn active" data-ii-norm="abs">ABS</button>
      <button class="btn" data-ii-norm="rel">RELATIVE</button>
    </div>
    <div class="grp ii-thresh"><span class="lbl">THRESH</span>
      <input type="range" id="ii-thresh" min="0" max="100" value="0">
      <span class="vlab" id="ii-thresh-val">0%</span>
    </div>
    <label class="ii-pin" id="ii-pin-lab">
      <input type="checkbox" id="ii-pin"> PIN
    </label>
  </div>

  <div class="ii-wrap r">
    <div class="ii-main">
      <div class="ph">
        <span class="pt">IMPACT INSPECTOR &middot; <span id="ii-face-label">FRONT (F2)</span></span>
        <span class="pd">hover impact &rarr; parts light up with their response &middot; click row to pin</span>
      </div>
      <div class="ii-canvas-wrap">
        <svg id="ii-svg" viewBox="0 0 800 600" preserveAspectRatio="xMidYMid meet"></svg>
      </div>
      <div class="ii-cbar">
        <span>0</span>
        <span class="grad"></span>
        <span id="ii-cbar-max">-</span>
        <span style="color:var(--accent);margin-left:8px" id="ii-metric-name">Peak G</span>
      </div>
    </div>
    <div class="ii-side" id="ii-side-panel">
      <div class="iibox">
        <div class="iihd">HOVERED IMPACT <span id="ii-behavior-badge"></span></div>
        <div id="ii-hover-info"><div class="ii-empty">충돌 위치 위에 마우스를 올리세요.</div></div>
        <div id="ii-traj-kpi" style="margin-top:6px"></div>
      </div>
      <div class="iibox">
        <div class="iihd">TOP AFFECTED PARTS</div>
        <div id="ii-parts-list"><div class="ii-empty">-</div></div>
      </div>
      <div class="iibox">
        <div class="iihd">IMPACTOR KE @ POSITION <span id="ii-th-sub" style="color:var(--dim);font-weight:500"></span></div>
        <svg id="ii-th-svg" class="ii-th" viewBox="0 0 200 70" preserveAspectRatio="none"></svg>
        <div style="display:flex;justify-content:space-between;font-size:8.5px;color:var(--dim);font-family:'JetBrains Mono',monospace;margin-top:2px">
          <span>0</span><span>0.5</span><span>1.0 ms</span>
        </div>
      </div>
    </div>
  </div>

  <div class="grid g-12" style="margin-top:14px">
    <div class="panel col-12 r">
      <div class="ph">
        <span class="pt">INFLUENCE MATRIX &middot; TOP-10 IMPACTS</span>
        <span class="pd">rows = worst impacts on selected face &middot; cols = parts &middot; click row = inspect</span>
      </div>
      <div id="imatrix-wrap" style="overflow-x:auto"></div>
      <div class="pcap">한 줄 = (face, position) 페어. 가로축 = 모든 부품. 셀 색 = 그 페어가 그 부품에 미친 응답.</div>
    </div>
  </div>
</section>
"""
