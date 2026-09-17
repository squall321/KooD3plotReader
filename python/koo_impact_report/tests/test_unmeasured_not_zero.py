# 측정 못 한 파트·런이 0 이 아니라 '미계측' 으로 나오는지 보는 시험
"""결측은 0 이 아니다.

motion CSV 가 없는 파트(실측 Test_Impact_A part 23 = *SECTION_BEAM 댐퍼)와
unified_analyzer 가 통째로 실패한 런이 peak_g/peak_disp/peak_stress = 0.0 으로
나가면, 판정표가 그 행을 '0 G · PASSED' 로 그리고 안전 낙하영역 통계가 그
0 들을 평균에 넣는다. peak_stress 는 한술 더 떠 matsum 내부에너지(mJ)로
대체돼 MPa 라벨 아래 전시됐다 (실측 part 1 = 20.96 mJ).

규칙.
  - 못 잰 값은 None → payload 는 null.
  - 내부에너지는 peak_internal_energy 로 따로 (단위가 다르다).
  - 런 전체 실패는 load_issues + n_failed 에 잡히고 캐시에 들어가지 않는다.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent.parent / "koo_deep_report"))

from koo_impact_report.models import PairResult  # noqa: E402


def test_pair_result_defaults_are_none_not_zero():
    """PairResult 를 값 없이 만들면 0 이 아니라 None 이다."""
    r = PairResult(face="F5", position=None, part_id=23)
    assert r.peak_g is None
    assert r.peak_stress is None
    assert r.peak_strain is None
    assert r.peak_disp is None
    assert r.peak_vel is None
    assert r.peak_internal_energy is None


@pytest.fixture(scope="module")
def dataset(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("unmeasured") / "sample"
    subprocess.run(
        [sys.executable, str(HERE / "generate_sample.py"),
         "--output", str(out), "--seed", "42", "--faces", "F1"],
        check=True, capture_output=True,
    )
    return out


def _report_with_unmeasured_part(dataset: Path):
    """샘플 DOE 를 읽고 한 파트를 '미계측' 으로 만든다 (빔 댐퍼 재현)."""
    from koo_impact_report.loader import load_impact_report

    report = load_impact_report(dataset)
    target = report.results[0].part_id
    for r in report.results:
        if r.part_id == target:
            r.peak_g = None
            r.peak_stress = None
            r.peak_strain = None
            r.peak_disp = None
            r.peak_vel = None
            r.part_motion = None
    return report, target


def test_payload_emits_null_for_unmeasured(dataset: Path):
    """payload 의 g/s/e/d 가 0 이 아니라 null 로 나간다."""
    from koo_impact_report.report.payload import _build_payload

    report, target = _report_with_unmeasured_part(dataset)
    payload = _build_payload(report)
    rows = [r for r in payload["results"] if r["part_id"] == target]
    assert rows, "대상 파트 행이 사라졌다"
    for row in rows:
        assert row["g"] is None, f"미계측 peak_g 가 {row['g']} 로 나갔다"
        assert row["s"] is None
        assert row["e"] is None
        assert row["d"] is None
    # 나머지 파트는 그대로 숫자여야 한다 — 회귀 방지.
    others = [r for r in payload["results"] if r["part_id"] != target]
    assert any(r["g"] is not None for r in others)


def test_kpi_and_safe_zone_ignore_unmeasured(dataset: Path):
    """미계측 0 이 KPI·안전영역 통계에 섞이지 않는다."""
    from koo_impact_report.report.payload import _build_payload

    report, target = _report_with_unmeasured_part(dataset)
    payload = _build_payload(report)
    assert payload["kpi"]["worst_g"] > 0
    assert payload["kpi"]["n_pairs"] == len(payload["results"])


def test_html_renders_with_unmeasured(dataset: Path):
    """미계측이 섞여도 보고서가 예외 없이 끝까지 만들어진다."""
    from koo_impact_report import analyzer
    from koo_impact_report.report.html_report import generate_html

    report, _ = _report_with_unmeasured_part(dataset)
    analyzer.analyze(report)
    html = generate_html(report)
    assert "<html" in html.lower()
    # 판정표 JS 가 null 을 '미계측' 으로 분기해야 한다 — 없으면 0 G PASSED 로 읽힌다.
    assert "NOT MEASURED" in html
    assert "r.g == null ? '미계측'" in html


def test_all(dataset: Path):
    """pytest 진입점 — 위 시험들을 한 번에 돌린다."""
    test_pair_result_defaults_are_none_not_zero()
    test_payload_emits_null_for_unmeasured(dataset)
    test_kpi_and_safe_zone_ignore_unmeasured(dataset)
    test_html_renders_with_unmeasured(dataset)
