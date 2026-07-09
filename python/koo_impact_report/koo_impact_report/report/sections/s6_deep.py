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
