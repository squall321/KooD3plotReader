# 섹션 07 — INSIGHTS HTML 템플릿 (기계적 분할, 바이트 불변)

_PAGE7 = """
<section id="s7">
  <div class="page-head">
    <span class="num">07</span>
    <span class="t">INSIGHTS & RECOMMENDATIONS</span>
    <span class="sub">설계 검증 · 손상 정량 · 충격 후 거동 · 자동 권고</span>
    <span class="sub">SYMMETRY / DAMAGE / REBOUND / 3D TRAJ / RECOMMEND / PULSE</span>
  </div>

  <div class="panel" style="background:transparent;border:none;padding:0;">
<section class="insight-panel" id="insight-panel-symmetry" data-key="Symmetry">
  <h3 class="insight-title">대칭성 &amp; 경계 효과 분석</h3>
  <div class="insight-body" id="insight-symmetry"></div>
</section>
    <div id="insight-DamageIndex" class="insight-panel">
  <div class="insight-title">부품별 누적 손상 지표 (DI)</div>
  <div class="insight-body"></div>
</div>
<section id="insight-rebound-field" class="insight-panel rf-panel">
  <header class="insight-head">
    <h3>충격 후 반발 벡터장</h3>
    <p class="insight-sub">5×5 격자에서 impactor 반발 속도의 xy 성분을 화살표로, vz 부호를 색으로 표시</p>
  </header>
  <div class="rf-kpis"></div>
  <div class="rf-svg-wrap"></div>
  <p class="rf-caption">화살표 = 반발 방향 (xy). 파랑 = bounce (vz↑), 빨강 = embed/penetrate (vz↓), 회색 = flat. 화살표 길이 ∝ |v_xy| / max(|v_xy|).</p>
</section>
<div id="insight-panel-auto-recommend" class="insight-panel">
  <div class="insight-header">
    <h3>엔지니어링 자동 권고</h3>
    <div class="insight-subtitle">데이터 기반 규칙으로 생성된 보강/검토 권고 — 심각도 순 정렬</div>
  </div>
  <div class="insight-body"></div>
</div>

<div class="insight-panel" id="insight-panel-ContactPulse">
  <div class="insight-header">
    <h3>충격 펄스 통계 (Contact Pulse Statistics)</h3>
    <div class="insight-sub">위치별 contact 지속시간 · 밀도 · 펄스→피크 시간</div>
  </div>
  <div id="insight-ContactPulse" class="insight-body"></div>
</div>
<section id="insight-panel-trajectory3d" class="insight-panel">
  <header class="insight-head">
    <h3>3D 트래젝터리 번들</h3>
    <p class="insight-sub">25개 위치 impactor 경로를 등각투영으로 동시 표시 (각 경로 최대 30포인트)</p>
  </header>
  <div id="trajectory3d-svg" class="t3d-svg-wrap"></div>
  <p class="t3d-caption">25 위치 충돌체 경로 동시 표시. 색 = behavior.</p>
</section>
<!-- INSIGHT_PANELS_INSERT_HERE -->
    <!-- Workflow-added panel templates are inserted ABOVE this marker. -->
  </div>
</section>
"""
