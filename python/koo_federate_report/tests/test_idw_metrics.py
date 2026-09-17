# IDW 보간이 9종 지표를 전부 채우는지 — 5종을 빠뜨려 '값 없음' 으로 막던 결함
"""보간이 지표를 가려 받지 않는다.

배경(2026-09 전수조사). `_idw_sample` 은 g/s/e/d 네 종만 보간했다.
models.METRIC_KEYS 는 9종이고 CLI `--metric` 도 9종을 받는다. sphere 어댑터는
사이드카에서 s1/s3/e1/e3/evm 을 실제로 읽어 온다. 그래서 `resample: idw` 로
`--metric s1` 을 돌리면 보간된 셀마다 그 지표가 None 이 되고, compare 가
`complete=False` → 게이트 사유 '값 없음: <리비전>' 을 붙였다. 전 셀이 보간이면
ERROR `no_comparable_cells` 까지 떴다 — 데이터에는 그 지표가 각 각도마다 다
있는데도 데이터를 탓하는 셈이다.
"""
from __future__ import annotations

import math

from koo_federate_report.compare import build_comparison
from koo_federate_report.config import Options
from koo_federate_report.matching import build_matching
from koo_federate_report.models import METRIC_KEYS, Cell, RevisionBundle, Trust
from koo_federate_report.resample import align

_ALL = {"g": 1000.0, "s": 250.0, "e": 0.002, "d": 1.5,
        "s1": 260.0, "s3": -180.0, "e1": 0.0021, "e3": -0.0015, "evm": 0.0018}


def _fib(n, pitch_shift=0.0):
    out = []
    ga = math.pi * (3.0 - math.sqrt(5.0))
    for i in range(n):
        z = 1.0 - (2.0 * i + 1.0) / n
        r = math.sqrt(max(0.0, 1.0 - z * z))
        lat = math.degrees(math.asin(max(-1.0, min(1.0, z))))
        lon = math.degrees(math.atan2(r * math.sin(ga * i), r * math.cos(ga * i)))
        out.append((f"P{i + 1:04d}", round(lat, 4), round(lon + pitch_shift, 4)))
    return out


def _bundle(label, angles):
    cells = [
        Cell(key=nm, label=nm, category="fibonacci", roll=r, pitch=p, yaw=0.0,
             metrics=dict(_ALL), trust=Trust(True, "no gate"))
        for nm, r, p in angles
    ]
    return RevisionBundle(
        label=label, kind="sphere", path=f"/syn/{label}.json",
        meta={"project": label}, unit_labels={}, parts={1: "PartA"},
        angles=[{"name": c.key, "roll": c.roll, "pitch": c.pitch, "yaw": 0.0} for c in cells],
        cells=cells, part_cells={(c.key, "PartA"): dict(_ALL) for c in cells},
        kpi={"n_cells": len(cells)}, trust={"n_cells": len(cells), "n_gated": 0},
    )


def _run(metric):
    bundles = [_bundle("RevA", _fib(40)), _bundle("RevB", _fib(37, pitch_shift=3.0))]
    options = Options()
    options.resample = "idw"
    match = build_matching(bundles, {}, options)
    aligned = align(bundles, 0, "sphere", options.resample)
    return build_comparison(bundles, 0, "sphere", match, aligned, options, metric=metric)


def test_idw_fills_every_metric_key():
    """9종 전부 보간되어야 한다 — 어댑터가 실어 온 값을 버리면 안 된다."""
    bundles = [_bundle("RevA", _fib(40)), _bundle("RevB", _fib(37, pitch_shift=3.0))]
    aligned = align(bundles, 0, "sphere", "idw")
    interpolated = [s for n in aligned.nodes for s in n.per_rev if s.source == "idw"]
    assert interpolated, "보간 샘플이 하나도 없다 — 시나리오가 성립하지 않았다"
    for mk in METRIC_KEYS:
        missing = sum(1 for s in interpolated if s.metrics.get(mk) is None)
        assert missing == 0, f"{mk}: 보간 샘플 {missing}/{len(interpolated)} 개가 값 없음"


def test_principal_metric_is_comparable_after_idw():
    """--metric s1 이 '값 없음' 으로 전부 막히면 보고서가 데이터를 탓하게 된다."""
    cmp_ = _run("s1")
    assert cmp_["kpi"]["n_comparable"] > 0, [
        c["gate_reason"] for c in cmp_["cells"][:3]]
    assert "no_comparable_cells" not in [w["code"] for w in cmp_["warnings"]]


def test_compressive_metric_keeps_sign_through_idw():
    """σ3 보간값은 음수 그대로여야 한다 (부호를 잃으면 압축이 인장이 된다)."""
    bundles = [_bundle("RevA", _fib(40)), _bundle("RevB", _fib(37, pitch_shift=3.0))]
    aligned = align(bundles, 0, "sphere", "idw")
    vals = [s.metrics.get("s3") for n in aligned.nodes for s in n.per_rev
            if s.source == "idw"]
    assert vals and all(v is not None and v < 0 for v in vals), vals[:5]


def test_base_metrics_unchanged():
    """g/s/e/d 는 예전 그대로 — 회귀 금지."""
    cmp_ = _run("s")
    assert cmp_["kpi"]["n_comparable"] > 0


def test_all():
    """pytest 진입점."""
    test_idw_fills_every_metric_key()
    test_principal_metric_is_comparable_after_idw()
    test_compressive_metric_keeps_sign_through_idw()
    test_base_metrics_unchanged()
