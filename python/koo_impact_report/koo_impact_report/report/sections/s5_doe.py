# 섹션 05 — DOE · SPATIAL ANALYSIS (위치별 응답 지도) HTML 템플릿 (기계적 분할, 바이트 불변)

_PAGE5 = """
<section class="page" id="s5" style="display:none">
  <div class="page-head r">
    <span class="num">05</span><span class="tagline">DOE &middot; SPATIAL ANALYSIS</span>
    <span class="ttl">전위치 부분충격 &mdash; 위치별 응답 지도</span>
    <span class="sub">MULTI-POSITION DOE EXPLORER</span>
  </div>

  <div id="doe-empty" class="doe-empty" style="display:none">DOE 데이터 없음 (단일 위치 리포트)</div>

  <div id="doe-content">
    <div class="kpi-strip r" id="doe-kpi-strip" style="grid-template-columns:repeat(5, 1fr);margin-bottom:14px"></div>

    <div class="ctlbar r" id="doe-ctlbar">
      <div class="grp"><span class="lbl">METRIC</span><span id="doe-metric-buttons"></span></div>
      <div class="grp"><span class="lbl">SORT</span>
        <button class="btn active" data-doe-sort="value">VALUE DESC</button>
        <button class="btn" data-doe-sort="pos">POS_ID</button>
      </div>
    </div>

    <div class="grid g-12" style="margin-bottom:14px" id="doe-grid-heat-rank">
      <div class="panel col-7 r" id="doe-panel-heatmap">
        <div class="ph">
          <span class="pt">SPATIAL HEATMAP &middot; <span id="doe-heat-metric-lbl">PEAK G</span></span>
          <span class="pd" id="doe-heat-sub">grid &middot; cell color = selected metric</span>
        </div>
        <div class="doe-grid-wrap"><svg id="doe-heatmap-svg"></svg></div>
        <div class="pcap" id="doe-heat-cap">셀 클릭 시 우측 표에서 해당 위치 강조. 라벨 = 값 + 최악 영향 부품.</div>
      </div>

      <div class="panel col-5 r" id="doe-panel-ranking">
        <div class="ph">
          <span class="pt">POSITION RANKING</span>
          <span class="pd">sorted by selected metric desc</span>
        </div>
        <div class="doe-rank">
          <table class="dt" id="doe-rank-tbl">
            <thead>
              <tr>
                <th class="tl">RANK</th>
                <th class="tl">POS_ID</th>
                <th>X<span id="doe-rank-x-unit"></span></th>
                <th>Y<span id="doe-rank-y-unit"></span></th>
                <th class="tl">BEHAVIOR</th>
                <th id="doe-rank-val-lbl">VAL</th>
                <th class="tl">DRIVER</th>
                <th>KE RET</th>
                <th>MAX PEN<span id="doe-rank-pen-unit"></span></th>
              </tr>
            </thead>
            <tbody></tbody>
          </table>
        </div>
      </div>
    </div>

    <div class="grid g-12" style="margin-bottom:14px" id="doe-grid-pp">
      <div class="panel col-12 r" id="doe-panel-pp-matrix">
        <div class="ph">
          <span class="pt">PART &times; POSITION HEATMAP</span>
          <span class="pd">rows = top 15 parts by max peak_g &middot; cols = positions by DOE index &middot; color = peak_g</span>
        </div>
        <div class="doe-pp-matrix-wrap"><svg id="doe-pp-svg"></svg></div>
        <div class="pcap">부품별로 어느 위치에서 가속도가 가장 큰지 한눈에 확인. 색상 = peak_g (위치별 정규화 아님).</div>
      </div>
    </div>

    <div class="grid g-12" style="margin-bottom:14px" id="doe-grid-traj-env">
      <div class="panel col-7 r" id="doe-panel-trajectory">
        <div class="ph">
          <span class="pt">TRAJECTORY SMALL MULTIPLES &middot; KE vs TIME</span>
          <span class="pd">25 mini-curves &middot; color = behavior class &middot; ★ = worst position</span>
        </div>
        <div class="doe-traj-mm" id="doe-traj-mm"></div>
        <div class="bvm-legend" style="margin-top:8px">
          <div class="lg"><span class="sw" style="background:#4adfa1"></span>bounce</div>
          <div class="lg"><span class="sw" style="background:#4dd6ff"></span>rebound</div>
          <div class="lg"><span class="sw" style="background:#ff3854"></span>embed</div>
          <div class="lg"><span class="sw" style="background:#ff9e64"></span>slide</div>
          <div class="lg"><span class="sw" style="background:#5c6383"></span>unknown</div>
        </div>
      </div>

      <div class="panel col-5 r" id="doe-panel-envelope">
        <div class="ph">
          <span class="pt">CROSS-POSITION ENVELOPE &middot; PER PART</span>
          <span class="pd">P5—P50—P95 whisker (peak_g) &middot; right = P95/P5</span>
        </div>
        <div class="doe-env-wrap" id="doe-env-wrap"></div>
        <div class="pcap">whisker 길이 = 위치별 부품 응답 분산. 비율 ↑ 위치 의존성 ↑.</div>
      </div>
    </div>

<div class="panel" id="doe-panel-failure-risk">
  <div class="ph">
    <span class="pt">FAILURE RISK MAP</span>
    <span class="pd">위치별 최소 안전율(SF) 히트맵 + 위험 부품 랭킹</span>
  </div>
  <div id="doe-failure-risk-body"></div>
  <div class="pcap">SF = yield / peak_stress. SF&lt;1 = 항복 초과, 1≤SF&lt;2 = 마진 부족.</div>
</div>

<div class="panel" id="doe-corr-network-panel">
  <div class="ph">
    <span class="pt">PART × PART RESPONSE CORRELATION</span>
    <span class="pd">25 위치에 걸친 peak_g 응답의 Pearson 상관 + greedy 클러스터링</span>
  </div>
  <div id="doe-corr-network" class="doe-corr-host"></div>
  <div class="pcap">25 위치에 걸친 부품 응답의 Pearson 상관. 같은 cluster = 구조적 연결 또는 같은 충격 경로. |r| ≥ 0.7 인 셀은 흰 테두리로 강조.</div>
</div>

<div class="panel col-12 r" id="doe-panel-toa">
  <div class="ph">
    <span class="pt">IMPACT WAVE PROPAGATION &middot; TIME-OF-ARRIVAL</span>
    <span class="pd">part peak_g vs impactor 첫 접촉 시점 &middot; 응답 전파 순서</span>
  </div>
  <div id="doe-toa-root" class="doe-toa-root"></div>
  <div class="pcap">
    Δt = part peak_g 시점 &minus; impactor 첫 접촉 시점. 응답 전파 순서를 시각화.
    좌측은 최악 위치의 도착 순서(상위 12개), 우측은 모든 위치 평균 기준 항상 빠른/느린 부품.
  </div>
</div>
<div class="grid g-12" style="margin-bottom:14px" id="doe-grid-idw">
  <div class="panel col-12 r" id="idw-pred-panel">
    <div class="ph">
      <span class="pt">WHAT-IF POSITION PREDICTOR &middot; IDW INTERPOLATION</span>
      <span class="pd">25 측정점 → 41×41 보간면 (역거리 가중, p=2)</span>
    </div>
    <div class="ctlbar r" style="margin-bottom:10px">
      <div class="grp"><span class="lbl">METRIC</span><span id="idw-pred-buttons"></span></div>
      <div class="grp" style="flex:1"><span class="lbl" style="opacity:.7">LEGEND</span>
        <span style="color:var(--fg2);font-size:11px">
          <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#0a0c14;border:1.5px solid #fff;vertical-align:middle;margin-right:4px"></span>측정점
          <span style="display:inline-block;width:10px;height:10px;border-radius:50%;border:2px solid #ffd84d;vertical-align:middle;margin:0 4px 0 12px"></span>예측 최대(보간 정점)
        </span>
      </div>
    </div>
    <div id="idw-pred-loo" style="margin-bottom:8px;font-size:12px;color:var(--fg2);padding:6px 10px;background:rgba(255,255,255,0.03);border-radius:4px;display:none"></div>
    <div class="doe-grid-wrap"><div id="idw-pred-stack" style="position:relative;width:100%;"><canvas id="idw-pred-canvas" width="620" height="900" style="display:block;width:100%;cursor:grab;background:#0e1320;border-radius:4px;"></canvas><svg id="idw-pred-svg" style="position:absolute;left:0;top:0;width:100%;height:100%;pointer-events:none;"></svg></div></div>
    <div id="idw-pred-info" style="margin-top:8px;font-size:12px;color:var(--fg2)"></div>
    <div class="pcap">측정 25 점 사이의 임의 위치에 떨어졌을 때 예상 응답. 점 = 실측, 면 = IDW 보간. 측정점 근처는 정확도가 높고, 측정점 사이 빈 영역은 불확실성이 커집니다 — 노란 링은 측정점 사이에 숨어 있을 가능성이 있는 "고위험 포켓"의 위치 추정입니다.</div>
  </div>
</div>

<div class="panel" id="panel-pareto-severity">
  <div class="ph">
    <span class="pt">SEVERITY × COVERAGE PARETO</span>
    <span class="pd">국소 vs 광역 충격 분류</span>
  </div>
  <div id="doe-pareto-severity" class="pareto-host"></div>
  <div class="pcap">한 위치가 '특정 부품만 심각' 인지 '여러 부품에 광범위' 인지 시각화. 우상단 = 광범위 + 심각 → 가장 위험.</div>
</div>

<div class="grid g-12" style="margin-bottom:14px" id="doe-grid-energy">
  <div class="panel col-12 r" id="doe-panel-energy">
    <div class="ph">
      <span class="pt">ENERGY PARTITION &middot; KE ABSORBED vs RETAINED</span>
      <span class="pd">per position &middot; sorted by absorption % desc</span>
    </div>
    <div class="doe-ep-summary" id="doe-ep-summary"></div>
    <div class="doe-ep-list" id="doe-ep-list"></div>
    <div class="pcap">충격 에너지가 디바이스에 흡수된 비율. 100% 흡수 = 충돌체가 정지. 행 클릭 시 상단 히트맵/랭킹에서 해당 위치 강조.</div>
  </div>
</div>

    <!-- ADV_PANELS_INSERT_HERE -->
    <!-- Workflow-added panel templates are inserted ABOVE this marker line. -->
  </div>
</section>

<div class="foot">KOOD3PLOT &middot; MULTI-FACE IMPACT &middot; v0.1.0 &middot; single-file self-contained</div>
"""
