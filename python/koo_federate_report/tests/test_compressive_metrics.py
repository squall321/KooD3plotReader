# 압축측 지표(σ3/ε3)의 '최악' 이 최솟값인지 — 집계·순위·Δ·경고 전 경로 확인
"""압축측 지표는 음수라 최악이 최솟값이다.

배경(2026-09 전수조사). METRIC_COMPRESSIVE 를 존중하는 곳은 셀 winner 단 한
군데였다. 나머지는 전부 max() 였다 — sphere 어댑터의 각도별 집계, 파트 worst,
순위 정렬, 참피크, worst_per_rev, 카테고리 worst, tiers 앵커. 그래서 PCB 가
-350 MPa 로 압축받는 각도에서 셀 값이 FOAM 의 -0.4 MPa 가 되고, 파트 순위 1위
(가장 나쁨)가 FOAM 이 되었다. Δ% 도 `(new-base)/|base|` 라 -350 → -500(43% 더
심한 압축)이 "-42.9% 개선" 으로 표시됐다. 여기에 더해 compare 의 음수 경고가
정상적인 σ3/ε3 값을 ERROR 로 올렸다.
"""
from __future__ import annotations

from koo_federate_report.adapters.sphere import to_bundle as sphere_bundle
from koo_federate_report.compare import build_comparison
from koo_federate_report.config import Options
from koo_federate_report.matching import build_matching
from koo_federate_report.resample import align

_ANGLES = [("P0001", 0.0, 0.0, "face"), ("P0002", 30.0, 60.0, "face"),
           ("P0003", -30.0, -60.0, "corner")]


def _sidecar(pcb_s3, foam_s3):
    """PCB 는 크게 압축받고 FOAM 은 거의 안 받는다 (실제 부품 구성이다)."""
    return {
        "project_name": "SYN",
        "total_runs": len(_ANGLES),
        "parts": {"1": {"part_name": "PCB\\PCB", "group": "PCB"},
                  "2": {"part_name": "FOAM\\FOAM", "group": "FOAM"}},
        "results_summary": [
            {
                "run_folder": f"run_{i}",
                "angle": {"name": nm, "roll": r, "pitch": p, "yaw": 0.0, "category": c},
                "parts": {
                    "1": {"peak_stress": 300.0, "min_principal_stress": pcb_s3 + i},
                    "2": {"peak_stress": 10.0, "min_principal_stress": foam_s3},
                },
            }
            for i, (nm, r, p, c) in enumerate(_ANGLES)
        ],
    }


def _cmp(metric="s3"):
    bundles = [sphere_bundle(_sidecar(-350.0, -0.4), label="RevA"),
               sphere_bundle(_sidecar(-500.0, -0.3), label="RevB")]
    options = Options()
    match = build_matching(bundles, {}, options)
    aligned = align(bundles, 0, "sphere", options.resample)
    return bundles, build_comparison(bundles, 0, "sphere", match, aligned, options,
                                     metric=metric)


def test_adapter_cell_takes_the_most_compressive_part():
    """각도 셀의 σ3 는 가장 크게 압축받은 파트의 값이어야 한다."""
    b = sphere_bundle(_sidecar(-350.0, -0.4), label="RevA")
    vals = [c.metrics["s3"] for c in b.cells]
    assert min(vals) <= -350.0, f"셀 σ3 가 {vals} — 가장 약한 압축(FOAM)을 골랐다"
    assert max(vals) < -300.0, f"셀 σ3 가 {vals} — FOAM(-0.4)이 섞여 있다"


def test_part_worst_and_rank_follow_compression():
    """파트 worst 와 순위(1=가장 나쁨)가 압축 크기를 따라야 한다."""
    _, cmp_ = _cmp()
    by_name = {p["canonical"]: p for p in cmp_["parts"]}
    pcb, foam = by_name["PCB\\PCB"], by_name["FOAM\\FOAM"]
    assert pcb["worst"][0] <= -350.0, f"PCB worst {pcb['worst'][0]}"
    assert pcb["rank"][0] == 1, f"가장 나쁜 파트가 {pcb['rank'][0]}위 — FOAM 이 1위가 됐다"
    assert foam["rank"][0] == 2


def test_true_peak_and_worst_per_rev_are_most_compressive():
    """참피크·격자 worst 도 최솟값이어야 한다."""
    _, cmp_ = _cmp()
    kpi = cmp_["kpi"]
    assert kpi["true_peak_per_rev"][0] <= -350.0, kpi["true_peak_per_rev"]
    assert kpi["true_peak_per_rev"][1] <= -500.0, kpi["true_peak_per_rev"]
    assert kpi["worst_per_rev"][0] <= -350.0, kpi["worst_per_rev"]


def test_delta_pct_calls_more_compression_worse():
    """-350 → -500 은 43% 악화다. 개선(음수)으로 표시되면 결론이 뒤집힌다."""
    _, cmp_ = _cmp()
    dp = cmp_["kpi"]["true_peak_delta_pct"][1]
    assert dp is not None and dp > 0, f"Δ% 가 {dp} — 더 심한 압축을 개선으로 읽었다"
    cell = cmp_["cells"][0]
    assert cell["delta_pct"][1] > 0, f"셀 Δ% 가 {cell['delta_pct']}"


def test_category_worst_is_most_compressive():
    """카테고리 소계의 worst 도 같은 규칙."""
    _, cmp_ = _cmp()
    cs = cmp_.get("category_summary") or {}
    for ct in (cs.get("categories") or []):
        w = ct["per_rev"][0]["worst"]
        if w is not None:
            assert w <= -300.0, f"{ct['name']} worst {w} — 가장 약한 압축을 골랐다"


def test_negative_sigma3_is_not_an_error():
    """정상적인 σ3 음수값에 'negative_metric' ERROR 를 올리면 안 된다."""
    _, cmp_ = _cmp()
    codes = [w["code"] for w in cmp_["warnings"]]
    assert "negative_metric" not in codes, cmp_["warnings"]


def test_positive_metric_behaviour_unchanged():
    """인장·가속도 계열은 예전 그대로(최대가 최악)."""
    _, cmp_ = _cmp(metric="s")
    kpi = cmp_["kpi"]
    assert kpi["true_peak_per_rev"][0] == 300.0
    by_name = {p["canonical"]: p for p in cmp_["parts"]}
    assert by_name["PCB\\PCB"]["rank"][0] == 1


def test_all():
    """pytest 진입점."""
    test_adapter_cell_takes_the_most_compressive_part()
    test_part_worst_and_rank_follow_compression()
    test_true_peak_and_worst_per_rev_are_most_compressive()
    test_delta_pct_calls_more_compression_worse()
    test_category_worst_is_most_compressive()
    test_negative_sigma3_is_not_an_error()
    test_positive_metric_behaviour_unchanged()
