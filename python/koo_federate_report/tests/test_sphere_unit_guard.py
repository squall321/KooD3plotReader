# sphere 사이드카에 단위를 지어내 단위 가드가 못 뜨던 결함을 못박는 시험
"""없는 단위를 채워 넣지 않는다.

배경(2026-09 전수조사). sphere 어댑터는 사이드카에 unit_labels 가 없으면
`_SPHERE_DEFAULT_UNITS`(acc=G, stress=MPa, disp=mm)를 채웠다. sphere 사이드카는
**단위를 한 줄도 싣지 않았으므로** 모든 sphere 리비전이 같은 라벨을 갖게 되고,
compare._unit_factors 는 `lb == li` 로 건너뛰어 계수 1.0 에 경고도 없었다.
unit_policy: error 에서도 그랬다. SI 덱(Pa·m)과 ton-mm-s 덱(MPa·mm)을 나란히
놓아도 응력 Δ% -99.9999% 가 '개선' 으로 나왔다.
"""
from __future__ import annotations

from koo_federate_report.adapters.sphere import to_bundle as sphere_bundle
from koo_federate_report.compare import build_comparison
from koo_federate_report.config import Options
from koo_federate_report.matching import build_matching
from koo_federate_report.resample import align


def _sidecar(stress, unit_labels=None):
    d = {
        "project_name": "SYN",
        "total_runs": 1,
        "parts": {"1": {"part_name": "PCB\\PCB", "group": "PCB"}},
        "results_summary": [{
            "run_folder": "run_1",
            "angle": {"name": "P0001", "roll": 0.0, "pitch": 0.0, "yaw": 0.0,
                      "category": "face"},
            "parts": {"1": {"peak_stress": stress, "peak_g": 1000.0}},
        }],
    }
    if unit_labels is not None:
        d["unit_labels"] = unit_labels
    return d


def test_adapter_does_not_invent_units():
    """라벨이 없으면 비워 둔다 — MPa/mm 를 지어내면 가드가 영영 못 뜬다."""
    b = sphere_bundle(_sidecar(310.0), label="RevA")
    assert not (b.unit_labels or {}).get("stress"), (
        f"단위를 지어냈다: {b.unit_labels}")


def test_adapter_uses_labels_when_present():
    """사이드카가 라벨을 실으면 그대로 쓴다."""
    b = sphere_bundle(_sidecar(3.1e8, {"acc": "G", "stress": "Pa", "disp": "m"}),
                      label="RevA")
    assert b.unit_labels["stress"] == "Pa"


def _cmp(a, b, metric="s", policy="warn"):
    bundles = [sphere_bundle(a, label="RevA"), sphere_bundle(b, label="RevB")]
    options = Options()
    options.unit_policy = policy
    match = build_matching(bundles, {}, options)
    aligned = align(bundles, 0, "sphere", options.resample)
    return build_comparison(bundles, 0, "sphere", match, aligned, options, metric=metric)


def test_mismatched_units_are_caught_now():
    """Pa 리비전과 MPa 리비전을 나란히 놓으면 가드가 떠야 한다."""
    cmp_ = _cmp(_sidecar(3.1e8, {"acc": "G", "stress": "Pa", "disp": "m"}),
                _sidecar(310.0, {"acc": "G", "stress": "MPa", "disp": "mm"}))
    codes = [w["code"] for w in cmp_["warnings"]]
    assert any(c in ("unit_mismatch", "unit_unknown", "unit_converted") for c in codes), (
        cmp_["warnings"])


def test_unlabeled_units_are_reported_not_silently_assumed():
    """라벨이 없다는 사실 자체가 경고로 나와야 한다 — 침묵이 가장 나쁘다."""
    cmp_ = _cmp(_sidecar(310.0), _sidecar(320.0))
    codes = [w["code"] for w in cmp_["warnings"]]
    assert "unit_unlabeled" in codes, cmp_["warnings"]


def test_strain_metric_is_not_nagged():
    """변형률은 무차원이라 라벨이 비어 있는 것이 정상 — 경고를 내면 소음이다."""
    a = _sidecar(310.0, {"acc": "G", "stress": "MPa", "strain": "", "disp": "mm"})
    cmp_ = _cmp(a, a, metric="e")
    assert "unit_unlabeled" not in [w["code"] for w in cmp_["warnings"]]


def test_all():
    """pytest 진입점."""
    test_adapter_does_not_invent_units()
    test_adapter_uses_labels_when_present()
    test_mismatched_units_are_caught_now()
    test_unlabeled_units_are_reported_not_silently_assumed()
    test_strain_metric_is_not_nagged()
