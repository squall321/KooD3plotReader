# 섹션 04 — PER-PART MOTION (부품별 peak G) HTML 템플릿 (기계적 분할, 바이트 불변)

_PAGE4 = """
<section class="page" id="s4">
  <div class="page-head r">
    <span class="num">04</span><span class="tagline">PER-PART MOTION</span>
    <span class="ttl">부품별 가속도 (Per-Part Peak G)</span>
    <span class="sub">RIGID-BODY MOTION &middot; PEAK G &middot; ACC-TIME HISTORY</span>
  </div>

  <div id="ppg-empty" class="r" style="display:none;color:var(--dim);padding:24px 12px;font-size:12px">
    부품별 모션 데이터 없음
  </div>

  <div id="ppg-content">
    <div class="grid g-12" style="margin-top:6px">
      <div class="panel col-7 r">
        <div class="ph">
          <span class="pt">PART PEAK G &middot; BAR CHART</span>
          <span class="pd">peak |acc| per part &middot; sorted descending &middot; impactor highlighted</span>
        </div>
        <svg id="ppg-bar-svg" preserveAspectRatio="xMidYMid meet" style="width:100%;height:340px"></svg>
        <div class="pcap" id="ppg-bar-cap">
          막대 길이 = max|a|<span id="ppg-bar-cap-unit"></span>. 임팩터 파트는 핑크색으로 강조.
        </div>
      </div>

      <div class="panel col-5 r">
        <div class="ph">
          <span class="pt">PEAK G SUMMARY TABLE</span>
          <span class="pd">part &middot; peak G &middot; t_peak &middot; peak vel/disp</span>
        </div>
        <div style="max-height:340px;overflow-y:auto">
          <table class="dt" id="ppg-summary-tbl">
            <thead>
              <tr>
                <th class="tl">PART</th>
                <th class="tl">NAME</th>
                <th>PEAK G<br><span style="font-weight:400;color:var(--dim);text-transform:none" id="ppg-th-acc"></span></th>
                <th>PEAK G<br><span style="font-weight:400;color:var(--dim);text-transform:none">g</span></th>
                <th>t<sub>peak</sub><br><span style="font-weight:400;color:var(--dim);text-transform:none" id="ppg-th-time"></span></th>
                <th>PEAK VEL<br><span style="font-weight:400;color:var(--dim);text-transform:none" id="ppg-th-vel"></span></th>
                <th>PEAK DISP<br><span style="font-weight:400;color:var(--dim);text-transform:none" id="ppg-th-disp"></span></th>
              </tr>
            </thead>
            <tbody></tbody>
          </table>
        </div>
        <div class="pcap">
          g 단위 = peak_g / 9810. 첫 번째 행이 가장 큰 가속도를 받는 부품.
        </div>
      </div>

      <div class="panel col-12 r">
        <div class="ph">
          <span class="pt">ACC MAGNITUDE TIME-SERIES &middot; ALL PARTS</span>
          <span class="pd">|a(t)| per part &middot; auto semi-log when range &gt; 2 decades &middot; dashed line = t<sub>first_contact</sub></span>
        </div>
        <svg id="ppg-line-svg" preserveAspectRatio="none" style="width:100%;height:360px"></svg>
        <div id="ppg-line-legend" style="display:flex;flex-wrap:wrap;gap:6px 12px;margin-top:6px;font-size:10px;color:var(--fg2)"></div>
        <div class="pcap" id="ppg-line-cap">
          한 선 = 한 파트의 가속도 크기 시계열. 회색 점선 세로선 = 임팩터 최초 접촉 시각.
        </div>
      </div>
    </div>
  </div>
</section>
"""
