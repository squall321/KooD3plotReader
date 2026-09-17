# 보고서가 지표별 단위·자릿수를 지키는지 — 모든 값을 G 제수로 나누던 결함
"""지표가 g 가 아닐 때의 단위와 자릿수.

배경(2026-09 전수조사). compare 는 baseline 의 unit_labels.acc 만 보고
`g_divisor` 를 정했다 — 어떤 지표로 비교하든 값이었다. HTML 은 그것을 지표와
무관하게 모든 값에 적용했다(`gv(v) = v / GDIV`, 라벨은 'G'). 그래서
`--metric s` 로 돌리면 470 MPa 가 fnum(470/9810, 0) = "0", 단위는 "G" 로 찍혔다.
Δ 50 MPa 도 "0". 살아남는 것은 Δ% 뿐이었다. sphere 사이드카(GDIV 없음)로
`--metric e` 를 돌리면 변형률 0.0021 이 0 자리 반올림으로 "0" 이 되었다.

여기서 못박는 것은 둘이다.
  ① G 환산은 지표가 가속도일 때만 적용한다.
  ② 자릿수는 값의 크기로 정한다 — 1 미만인 값을 0 자리로 찍지 않는다.
"""
from __future__ import annotations

from koo_federate_report.compare import build_comparison
from koo_federate_report.config import Options
from koo_federate_report.matching import build_matching
from koo_federate_report.report.html_report import generate_html
from koo_federate_report.resample import align

from .helpers import make_impact_bundle

PARTS = {1: "PartA"}
_SPECS = [("C1", 0.0, 0.0, "F5", 4700.0, True, "bounce")]


def _cmp(metric, s_values=(470.0, 520.0), acc_unit="mm/s²"):
    bundles = []
    for lb, s in zip(("R1", "R2"), s_values):
        b = make_impact_bundle(lb, _SPECS, PARTS,
                               unit_labels={"acc": acc_unit, "stress": "MPa",
                                            "strain": "", "disp": "mm"})
        for c in b.cells:
            c.metrics["s"] = s
            c.metrics["e"] = s / 247619.0        # 0.0019 / 0.0021
        bundles.append(b)
    options = Options()
    match = build_matching(bundles, {}, options)
    aligned = align(bundles, 0, "impact", options.resample)
    return build_comparison(bundles, 0, "impact", match, aligned, options, metric=metric)


def test_g_divisor_is_only_for_acceleration():
    """지표가 응력이면 payload 의 G 제수가 적용되면 안 된다."""
    cmp_ = _cmp("s")
    gd = cmp_.get("g_divisor")
    assert not gd, f"metric='s' 인데 g_divisor 가 {gd} 다 — 모든 값이 9810 으로 나뉜다"
    assert _cmp("g").get("g_divisor") == 9810.0, "가속도 비교에서는 G 환산이 필요하다"


def test_kpi_table_shows_stress_not_zero_g():
    """KPI 표가 470 MPa 를 'G 0' 으로 찍으면 안 된다."""
    html = generate_html(_cmp("s"))
    i = html.index("참피크") if "참피크" in html else html.index("WORST")
    seg = html[i - 200:i + 1200]
    assert "470" in seg, f"KPI 표에 470 이 없다:\n{seg[:600]}"
    assert ">G<" not in seg, "응력 비교인데 단위가 G 로 찍혔다"


def test_summary_prose_does_not_say_zero_g():
    """요약 문장도 같은 규칙 — '0 G' 는 거짓말이다."""
    html = generate_html(_cmp("s"))
    i = html.index("최저 worst 응답은")
    seg = html[i:i + 400]
    assert "470" in seg and "520" in seg, seg
    assert " G<" not in seg, f"요약이 응력을 G 로 말한다:\n{seg}"


def test_small_values_keep_digits():
    """변형률 0.0019 는 0 자리로 찍으면 통째로 사라진다."""
    html = generate_html(_cmp("e"))
    assert "0.0019" in html or "0.00190" in html, "변형률이 표에서 0 으로 붕괴했다"


def test_js_applies_g_divisor_only_for_g_metric():
    """화면 스크립트도 지표를 봐야 한다 (표만 고치면 probe·지도는 그대로 틀린다)."""
    from koo_federate_report.report.html_report import _JS
    assert "var VUNIT = GDIV ? 'G' : (UL.acc || '');" not in _JS, (
        "단위 라벨이 지표와 무관하게 acc 를 쓴다")
    assert "METRIC" in _JS and "g_divisor" in _JS
    i = _JS.index("var GDIV")
    assert "METRIC" in _JS[i - 200:i + 200], "GDIV 가 지표와 무관하게 정해진다"


def test_js_formats_values_by_magnitude():
    """0 자리 고정 표기를 걷어냈는지 — fnum(gv(x), 0) 이 남아 있으면 안 된다."""
    from koo_federate_report.report.html_report import _JS
    assert "fnum(gv(" not in _JS, "값 표기가 아직 0 자리 고정이다"


def test_acceleration_report_unchanged():
    """기본(가속도) 보고서는 그대로 G 로 보여야 한다 — 회귀 금지."""
    html = generate_html(_cmp("g"))
    assert "G" in html


def test_all():
    """pytest 진입점."""
    test_g_divisor_is_only_for_acceleration()
    test_kpi_table_shows_stress_not_zero_g()
    test_summary_prose_does_not_say_zero_g()
    test_small_values_keep_digits()
    test_js_applies_g_divisor_only_for_g_metric()
    test_js_formats_values_by_magnitude()
    test_acceleration_report_unchanged()
