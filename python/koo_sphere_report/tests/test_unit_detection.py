# 단위계 판정이 ms 기반 덱을 조용히 ton-mm-s 로 단정하지 않는지 보는 시험
"""단위계 미검출을 '검출됨' 으로 위장하지 않는다.

배경(2026-09 전수조사). sphere 는 **덱 *MAT 밀도 하나**로 단위계를 정했다.
그런데 밀도는 초와 밀리초를 구분하지 못한다 — ton-mm-s 와 ton-mm-ms 는 둘 다
강철이 7.85e-9 이다. 그래서 impact 검출기가 돌려줄 수 있는 값은 ton-mm-s / SI /
미상 셋뿐이고, _G_FACTOR_BY_UNIT 의 'ton-mm-ms'·'g-mm-ms' 항목은 **선택될 길이
없었다**. ms 기반 덱(가속도 mm/ms²)이면 참 150,000 G 가 0.15 G 로 나온다.

미상일 때도 문제였다. MotionData.UNIT_SYSTEM 은 "ton-mm-s" 로 남고 payload 는
g_factor 9810 을 그대로 실어, 화면은 검출된 값처럼 보여 주었다. 유일한 신호는
stdout 한 줄이었다.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from koo_sphere_report import loader as L  # noqa: E402
from koo_sphere_report.models import MotionData  # noqa: E402

_DECK = """*KEYWORD
*CONTROL_TERMINATION
{endtim},0,0.0,0.0,0.0
*MAT_ELASTIC
1,{rho},2.0e5,0.3
*END
"""


@pytest.fixture(autouse=True)
def _restore_unit_system():
    """MotionData 의 단위계는 클래스 속성이라 시험 사이에 새지 않게 되돌린다."""
    saved = (MotionData.UNIT_SYSTEM, MotionData.G_FACTOR, MotionData.UNIT_NOTE)
    yield
    MotionData.UNIT_SYSTEM, MotionData.G_FACTOR, MotionData.UNIT_NOTE = saved


def _deck(tmp_path: Path, rho: str, endtim: str) -> Path:
    """test_dir/output 구조를 만들고 덱을 test_dir 에 둔다 (실제 배치와 같다)."""
    test_dir = tmp_path / "Test_X"
    out = test_dir / "output"
    out.mkdir(parents=True)
    (test_dir / "model.k").write_text(_DECK.format(rho=rho, endtim=endtim),
                                      encoding="utf-8")
    return out


def test_end_time_disagreeing_with_density_is_not_silently_ton_mm_s(tmp_path: Path):
    """밀도는 ton 계열, 종료시각은 2(=ms 스케일) — 단정하지 말고 미검출로 남긴다."""
    MotionData.UNIT_SYSTEM, MotionData.G_FACTOR = "ton-mm-s", 9810.0
    MotionData.UNIT_NOTE = ""
    L._apply_unit_system(None, _deck(tmp_path, "7.85e-9", "2.0"))
    assert MotionData.UNIT_SYSTEM == "", (
        f"'{MotionData.UNIT_SYSTEM}' 로 단정했다 — 밀도만으로는 s 와 ms 를 못 가른다")
    assert MotionData.UNIT_NOTE, "미검출 사유가 비어 있다"
    assert "2" in MotionData.UNIT_NOTE, "판단 근거(종료시각)가 사유에 없다"


def test_consistent_ton_mm_s_deck_is_still_detected(tmp_path: Path):
    """지금 잘 도는 덱(종료시각 0.003 s)은 그대로 검출되어야 한다 — 회귀 금지."""
    MotionData.UNIT_SYSTEM, MotionData.G_FACTOR = "ton-mm-s", 9810.0
    MotionData.UNIT_NOTE = ""
    L._apply_unit_system(None, _deck(tmp_path, "7.85e-9", "0.003"))
    assert MotionData.UNIT_SYSTEM == "ton-mm-s"
    assert abs(MotionData.G_FACTOR - 9806.65) < 1e-6
    assert MotionData.UNIT_NOTE == ""


def test_unknown_density_is_reported_as_undetected(tmp_path: Path):
    """g-mm-ms(ρ=7.85e-3)는 검출기가 미상을 준다 — ton-mm-s 라고 말하면 안 된다."""
    MotionData.UNIT_SYSTEM, MotionData.G_FACTOR = "ton-mm-s", 9810.0
    MotionData.UNIT_NOTE = ""
    L._apply_unit_system(None, _deck(tmp_path, "7.85e-3", "2.0"))
    assert MotionData.UNIT_SYSTEM == "", "미상을 ton-mm-s 로 보고했다"
    assert "7.85e-03" in MotionData.UNIT_NOTE or "0.00785" in MotionData.UNIT_NOTE


def test_missing_deck_is_reported_as_undetected(tmp_path: Path):
    """덱을 못 읽으면 그 사실이 값으로 남아야 한다."""
    MotionData.UNIT_SYSTEM, MotionData.G_FACTOR = "ton-mm-s", 9810.0
    MotionData.UNIT_NOTE = ""
    out = tmp_path / "Test_Y" / "output"
    out.mkdir(parents=True)
    L._apply_unit_system(None, out)
    assert MotionData.UNIT_SYSTEM == ""
    assert MotionData.UNIT_NOTE


def test_payload_carries_detection_state():
    """payload 의 unit_system 이 '검출했는가' 와 사유를 함께 실어야 한다."""
    from koo_sphere_report.models import (
        AngleCondition, PartInfo, PartResult, Report, SimulationResult)
    from koo_sphere_report.report.html_report import _build_report_data
    MotionData.UNIT_SYSTEM, MotionData.G_FACTOR = "", 9810.0
    MotionData.UNIT_NOTE = "덱 밀도를 못 읽었다"
    rep = Report(project_name="T", total_runs=1, successful_runs=1)
    pr = PartResult(part=PartInfo(part_id=1, part_name="A\\B", group="A"))
    rep.part_info = {1: pr.part}
    sr = SimulationResult(run_folder="R",
                          angle=AngleCondition(angle_name="P1", roll=0, pitch=0, yaw=0))
    sr.parts = {1: pr}
    rep.results.append(sr)
    us = _build_report_data(rep)["unit_system"]
    assert us["detected"] is False
    assert us["note"] == "덱 밀도를 못 읽었다"


def test_undetected_unit_raises_a_finding(tmp_path: Path):
    """미검출이면 findings 에 남아야 한다 — stdout 한 줄은 아무도 안 본다."""
    from koo_sphere_report.analyzer import _generate_findings
    from koo_sphere_report.models import (
        AngleCondition, PartInfo, PartResult, Report, SimulationResult)
    MotionData.UNIT_SYSTEM, MotionData.G_FACTOR = "", 9810.0
    MotionData.UNIT_NOTE = "덱 밀도를 못 읽어 단위계를 판정하지 못했다"
    rep = Report(project_name="T", total_runs=1, successful_runs=1)
    pr = PartResult(part=PartInfo(part_id=1, part_name="A\\B", group="A"))
    rep.part_info = {1: pr.part}
    sr = SimulationResult(run_folder="R",
                          angle=AngleCondition(angle_name="P1", roll=0, pitch=0, yaw=0))
    sr.parts = {1: pr}
    rep.results.append(sr)
    titles = " ".join(f.title for f in _generate_findings(rep))
    assert "단위계" in titles, "단위계 미검출이 findings 에 없다"


def test_all(tmp_path: Path):
    """pytest 진입점."""
    saved = (MotionData.UNIT_SYSTEM, MotionData.G_FACTOR, MotionData.UNIT_NOTE)
    try:
        def _d(name: str) -> Path:
            p = tmp_path / name
            p.mkdir()
            return p
        test_end_time_disagreeing_with_density_is_not_silently_ton_mm_s(_d("a"))
        test_consistent_ton_mm_s_deck_is_still_detected(_d("b"))
        test_unknown_density_is_reported_as_undetected(_d("c"))
        test_missing_deck_is_reported_as_undetected(_d("d"))
        test_payload_carries_detection_state()
        test_undetected_unit_raises_a_finding(_d("e"))
    finally:
        MotionData.UNIT_SYSTEM, MotionData.G_FACTOR, MotionData.UNIT_NOTE = saved
