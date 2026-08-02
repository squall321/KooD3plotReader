# findings 차분의 '이슈 정체' 키 회귀 — 수치 변동 이중계상 / 식별자 과잉병합 방지
"""findings diff 안정 키 테스트.

실측 결함: title 전문을 키로 쓰면 '접촉 미발생 런 16/25' → '14/25' 처럼
수치만 변한 같은 이슈가 신규+해소로 **이중 계상**된다(실데이터 4건 확인).
반대로 숫자를 전부 지우면 'F5_DOE_024 …|z|=64.1' 과 'F5_DOE_019 …|z|=61.8'
처럼 **위치가 다른 별개 이슈 9건이 1건으로 병합**된다.

두 실패 모드를 양쪽에서 못박는다.
"""
from __future__ import annotations

from koo_federate_report.compare import build_comparison
from koo_federate_report.config import Options
from koo_federate_report.matching import build_matching
from koo_federate_report.resample import align

from .helpers import make_impact_bundle

CELLS = [("P1", 0.0, 0.0, "F1", 100.0, True, "contact")]
PARTS = {1: "COVER"}


def _diff(findings_a, findings_b):
    bundles = [
        make_impact_bundle("RevA", CELLS, PARTS, findings=findings_a),
        make_impact_bundle("RevB", CELLS, PARTS, findings=findings_b),
    ]
    options = Options()
    match = build_matching(bundles, {}, options)
    aligned = align(bundles, 0, "impact", options.resample)
    cmp_ = build_comparison(bundles, 0, "impact", match, aligned, options)
    return next(x for x in cmp_["findings_diff"] if not x["is_baseline"]), cmp_


def test_numeric_only_change_is_kept_not_double_counted():
    """수치만 바뀐 같은 이슈 → 신규 0 / 해소 0 / 유지 1 (+ 변동 1)."""
    fd, _ = _diff(
        [{"severity": "WARNING", "title": "접촉 미발생 런 16/25 — DOE 배치 검토 필요"}],
        [{"severity": "WARNING", "title": "접촉 미발생 런 14/25 — DOE 배치 검토 필요"}],
    )
    assert len(fd["new"]) == 0
    assert len(fd["resolved"]) == 0
    assert len(fd["kept"]) == 1
    assert len(fd["changed"]) == 1
    assert "16/25" in fd["changed"][0]["before"]["title"]
    assert "14/25" in fd["changed"][0]["after"]["title"]


def test_distinct_identifiers_are_not_merged():
    """식별자(F5_DOE_024 vs _019)가 다르면 별개 이슈로 남는다 — 과잉 병합 금지."""
    a = [
        {"severity": "WARNING", "title": "F5_DOE_024: statistical outlier for peak_g (|z|=64.1)"},
        {"severity": "WARNING", "title": "F5_DOE_019: statistical outlier for peak_g (|z|=61.8)"},
    ]
    fd, cmp_ = _diff(a, a)
    assert len(fd["kept"]) == 2, "서로 다른 위치의 outlier 가 한 건으로 뭉쳤다"
    assert len(fd["changed"]) == 0
    assert not any(w.get("code") == "findings_key_collision" for w in cmp_["warnings"])


def test_severity_change_is_new_and_resolved():
    """심각도가 바뀌면 같은 문구라도 별개 이슈 — 승격/강등을 숨기지 않는다."""
    fd, _ = _diff(
        [{"severity": "WARNING", "title": "에너지 균형 FAIL 런 9/25"}],
        [{"severity": "CRITICAL", "title": "에너지 균형 FAIL 런 9/25"}],
    )
    assert len(fd["new"]) == 1 and fd["new"][0]["severity"] == "CRITICAL"
    assert len(fd["resolved"]) == 1 and fd["resolved"][0]["severity"] == "WARNING"


def test_key_collision_is_warned_not_silent():
    """정체 키가 충돌해 건수가 줄면 경고로 드러난다 (조용한 소실 금지)."""
    _, cmp_ = _diff(
        [{"severity": "WARNING", "title": "peak_g 12.5 초과"}],
        [
            {"severity": "WARNING", "title": "peak_g 12.5 초과"},
            {"severity": "WARNING", "title": "peak_g 33.7 초과"},
        ],
    )
    warns = [w for w in cmp_["warnings"] if w.get("code") == "findings_key_collision"]
    assert warns, "충돌로 1건이 사라졌는데 경고가 없다"
    assert "RevB" in warns[0]["message"]
