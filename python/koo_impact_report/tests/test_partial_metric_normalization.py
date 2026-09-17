# 일부 지표만 잰 부품의 점수를 잰 항목만으로 매기는지 보는 시험
"""세 곳이 서로 다른 규칙을 썼다.

- `compute_severity_score._n()` 은 None 을 0.0 으로 정규화하고 가중치를
  재정규화하지 않는다 — 주석은 '기여에서 뺀다' 고 적었지만 실제로는
  '0 으로 측정' 과 완전히 같다.
- `_build_damage_index` 의 composite DI 는 `(c_pg + c_ps + c_pe) / 3.0` 로
  잰 지표 수와 무관하게 3 으로 나눈다. 같은 함수의 per-pair contrib 는
  이미 잰 개수 n 으로 나눈다 — 한 함수 안에서도 규칙이 다르다.
- `_build_worst_combinations` 만 active_weight 로 재정규화한다.

기준은 physics 쪽(잰 항목의 가중치로 재정규화)으로 맞춘다.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from koo_impact_report.analyzer import compute_severity_score  # noqa: E402
from koo_impact_report.models import (  # noqa: E402
    ImpactPosition, ImpactReport, PairResult, PartInfo,
)
from koo_impact_report.report.payload.insights import (  # noqa: E402
    _build_damage_index,
)

W = {"g": 0.4, "s": 0.4, "e": 0.2}
MAX = {"peak_g": 1000.0, "peak_stress": 500.0, "peak_strain": 0.01}


def _pr(g=None, s=None, e=None):
    pos = ImpactPosition(pos_id="P1", face="F1", x=0.0, y=0.0)
    return PairResult(face="F1", position=pos, part_id=1,
                      peak_g=g, peak_stress=s, peak_strain=e)


def test_severity_uses_only_measured_terms():
    """응력·변형률을 못 잰 부품이 peak_g 최대여도 0.4 배로 눌리면 안 된다."""
    only_g = compute_severity_score(_pr(g=1000.0), W, MAX)
    all_max = compute_severity_score(_pr(g=1000.0, s=500.0, e=0.01), W, MAX)
    assert only_g == all_max, (only_g, all_max)


def test_severity_none_when_nothing_measured():
    """한 항목도 못 쟀으면 점수를 지어내지 않는다."""
    assert compute_severity_score(_pr(), W, MAX) is None


def test_severity_partial_pair_is_renormalized():
    """g/s 만 쟀으면 두 항목의 가중치로만 재정규화한다."""
    got = compute_severity_score(_pr(g=1000.0, s=250.0), W, MAX)
    want = (0.4 * 1.0 + 0.4 * 0.5) / (0.4 + 0.4)
    assert abs(got - want) < 1e-12, (got, want)


def _di_report(rows):
    """rows = [(part_id, peak_g, peak_stress, peak_strain)] — 위치 1개."""
    pos = ImpactPosition(pos_id="P1", face="F1", x=0.0, y=0.0)
    results = [PairResult(face="F1", position=pos, part_id=pid,
                          peak_g=g, peak_stress=s, peak_strain=e)
               for pid, g, s, e in rows]
    parts = [PartInfo(part_id=pid, part_name=f"PART_{pid}") for pid, *_ in rows]
    return ImpactReport(parts=parts, positions_by_face={"F1": [pos]},
                        results=results)


def test_di_composite_divides_by_measured_metric_count():
    """가속도만 잰 부품의 DI 가 1/3 로 눌리면 상위 목록에서 사라진다."""
    rep = _di_report([(1, 1000.0, None, None), (2, 1000.0, 500.0, 0.01)])
    di = {r["part_id"]: r["di"] for r in _build_damage_index(rep)["per_part"]}
    assert di[1] == di[2], di


def test_di_skips_parts_with_no_metric_at_all():
    """한 지표도 못 잰 부품은 DI 0.0 으로 싣지 않는다 — 0 은 측정이 아니다."""
    rep = _di_report([(1, 1000.0, 500.0, 0.01), (9, None, None, None)])
    out = _build_damage_index(rep)
    ids = {r["part_id"] for r in out["per_part"]}
    assert 9 not in ids, out["per_part"]
    assert out["summary"]["n_parts_total"] == 2
    assert out["summary"]["n_parts_with_data"] == 1, out["summary"]


def test_all():
    """진입점 — 이 파일의 시험을 모두 돌린다."""
    test_severity_uses_only_measured_terms()
    test_severity_none_when_nothing_measured()
    test_severity_partial_pair_is_renormalized()
    test_di_composite_divides_by_measured_metric_count()
    test_di_skips_parts_with_no_metric_at_all()
