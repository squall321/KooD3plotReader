# 통계 이상치 게이트가 미계측 위치를 '이상하게 낮다' 로 만들지 않는지 보는 시험
"""`_statistical_outlier_findings` 는 위치별 worst 를 집계할 때
`max(d, float(r.peak_g or 0.0))` 로 None 을 0.0 으로 접었다.

한 위치의 모든 파트가 미계측이면 그 위치의 worst 가 0.0 으로 들어가
median/MAD 표본을 오염시키고, |z| 가 임계를 넘으면
'statistical outlier for peak_g, peak_g=0.000e+00' 이라는 WARNING 이
만들어진다. 그 문구는 '응답이 이상하게 낮다' 로 읽히지만 실제로는
재지 못한 것이다.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from koo_impact_report.analyzer import _statistical_outlier_findings  # noqa: E402
from koo_impact_report.models import (  # noqa: E402
    ImpactPosition, ImpactReport, PairResult,
)


def _report(rows):
    """rows = [(pos_id, peak_g, peak_stress)] — 위치당 파트 1개."""
    results = []
    for pos_id, g, s in rows:
        pos = ImpactPosition(pos_id=pos_id, face="F1", x=0.0, y=0.0)
        results.append(PairResult(face="F1", position=pos, part_id=1,
                                  peak_g=g, peak_stress=s))
    return ImpactReport(results=results)


def _tight(n=23, base=1000.0):
    """MAD 가 작은 촘촘한 모집단 — 0 하나가 끼면 곧바로 |z|>3.5 가 된다."""
    return [(f"P{i:02d}", base + (i % 3) * 1.0, 100.0 + (i % 3) * 0.1)
            for i in range(n)]


def test_unmeasured_position_is_not_reported_as_outlier():
    """motion 추출이 실패한 위치가 '이상치' WARNING 으로 나오면 안 된다."""
    rows = _tight() + [("PX", None, None), ("PY", None, None)]
    findings = _statistical_outlier_findings(_report(rows))
    titles = [f.title for f in findings]
    assert not any("PX" in t or "PY" in t for t in titles), titles
    assert not any("0.000e+00" in f.detail for f in findings), \
        [f.detail for f in findings]


def test_unmeasured_position_does_not_shift_median():
    """미계측 위치가 표본에 섞이면 진짜 이상치의 z 가 부풀려진다."""
    rows = _tight() + [("PHOT", 1400.0, 100.0)]
    clean = _statistical_outlier_findings(_report(rows))
    polluted = _statistical_outlier_findings(
        _report(rows + [("PX", None, None), ("PY", None, None)]))

    def _z(fs, pid):
        for f in fs:
            if f.title.startswith(pid + ":") and "peak_g" in f.title:
                return f.title
        return None

    assert _z(clean, "PHOT") == _z(polluted, "PHOT"), (
        _z(clean, "PHOT"), _z(polluted, "PHOT"))


def test_real_outlier_still_found():
    """진짜 낮은/높은 위치는 그대로 잡는다 — 게이트를 무디게 만들지 않는다."""
    rows = _tight() + [("PHOT", 1400.0, 100.0)]
    findings = _statistical_outlier_findings(_report(rows))
    assert any(f.title.startswith("PHOT:") for f in findings), \
        [f.title for f in findings]


def test_metric_with_too_few_measured_positions_is_skipped():
    """응력을 단 3곳만 쟀으면 그 지표로는 z 를 계산하지 않는다."""
    rows = [(f"P{i:02d}", 1000.0 + (i % 3), 100.0 if i < 3 else None)
            for i in range(20)]
    rows.append(("PHOT", 1000.0, 9999.0))
    findings = _statistical_outlier_findings(_report(rows))
    assert not any("peak_stress" in f.title for f in findings), \
        [f.title for f in findings]


def test_all():
    """진입점 — 이 파일의 시험을 모두 돌린다."""
    test_unmeasured_position_is_not_reported_as_outlier()
    test_unmeasured_position_does_not_shift_median()
    test_real_outlier_still_found()
    test_metric_with_too_few_measured_positions_is_skipped()
