# 섹션 08 — PHYSICS HTML 템플릿 (기계적 분할, 바이트 불변)

_PAGE8 = """
<section id="s8">
  <div class="page-head">
    <span class="num">08</span>
    <span class="t">PHYSICS INSIGHTS</span>
    <span class="sub">충격파 속도 · 반발 계수 · 댐핑 · 최악 조합</span>
    <span class="sub">WAVE / RESTITUTION / DAMPING / WORST COMBOS</span>
  </div>

  <div class="panel" style="background:transparent;border:none;padding:0;">
    <div class="panel" id="physics-stress-wave-velocity">
  <div class="panel-header">
    <h3>충격파 전파 속도</h3>
    <span class="panel-sub">part별 평균 v_app = r / Δt &nbsp;·&nbsp; 이론값과 비교</span>
  </div>
  <div class="panel-body"></div>
</div>
<div class="panel" id="phys-restitution-map" data-panel-key="RestitutionMap">
  <div class="panel-header">
    <h3>위치별 반발 계수 (Coefficient of Restitution)</h3>
    <div class="panel-sub" data-role="status">반발 계수 e 데이터를 로딩 중입니다...</div>
  </div>
  <div class="rmap-kpi-row">
    <div class="rmap-kpi"><div class="rmap-kpi-label">평균 e</div><div class="rmap-kpi-value" data-role="kpi-mean">—</div></div>
    <div class="rmap-kpi"><div class="rmap-kpi-label">최대 (탄성)</div><div class="rmap-kpi-value" data-role="kpi-max">—</div></div>
    <div class="rmap-kpi"><div class="rmap-kpi-label">최소 (비탄성)</div><div class="rmap-kpi-value" data-role="kpi-min">—</div></div>
    <div class="rmap-kpi rmap-kpi-wide"><div class="rmap-kpi-label">분포</div><div class="rmap-kpi-value" data-role="kpi-buckets">—</div></div>
  </div>
  <div class="rmap-grid">
    <div class="rmap-heat">
      <div class="rmap-section-title">5×5 공간 히트맵 (빨강=비탄성, 초록=탄성)</div>
      <div data-role="heatmap" class="rmap-heat-host"></div>
    </div>
    <div class="rmap-hist">
      <div class="rmap-section-title">e 분포 (10 bins)</div>
      <div data-role="histogram" class="rmap-hist-host"></div>
    </div>
  </div>
  <div class="rmap-caption">
    e = √(KE_after / KE_before). 0 = 완전비탄성 (충돌체 정지), 1 = 완전탄성. 1 초과 시 mass scaling 효과.
  </div>
</div>
<div class="panel" id="phys-recovery-damping-panel">
  <div class="panel-header">
    <h3>부품별 댐핑 / 회복 시간</h3>
    <div class="panel-sub">최악 위치 기준 · 5% 감쇠 시간 · log-decrement ζ 추정</div>
  </div>
  <div class="panel-body" id="phys-recovery-damping-body"></div>
</div>
<section id="phys-worst-combinations" class="panel" data-panel-key="worst_combinations">
  <header class="panel-header">
    <h3 class="panel-title">최악 25 조합 (위치 × 부품)</h3>
    <div class="panel-subtitle">composite risk score 기반 Top-K — peak_g · peak_stress · peak_disp 가중 결합</div>
  </header>
  <div class="panel-body"></div>
</section>

<!-- PHYSICS_PANELS_INSERT_HERE -->
    <!-- Workflow-added panel templates are inserted ABOVE this marker. -->
  </div>
</section>
"""
