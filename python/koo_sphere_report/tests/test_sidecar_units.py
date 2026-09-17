# report.json 사이드카가 단위 라벨을 싣는지 — federate 가 단위 불일치를 보게
"""사이드카는 자기 값의 단위를 말해야 한다.

배경(2026-09 전수조사). sphere report.json 은 **단위를 한 줄도 적지 않았다**.
로더가 SI·ton-mm-s 를 검출해도 그 결과는 G 환산 계수에만 쓰였고, peak_stress·
peak_disp 는 덱 단위 그대로(SI 덱이면 Pa·m) 나갔다. federate 는 라벨이 없으면
MPa/mm 를 채워 넣었기 때문에, SI 덱과 ton-mm-s 덱을 나란히 놓아도 두 리비전의
라벨이 같아 보여 단위 가드가 영영 뜨지 않았다(응력 Δ% -99.9999% 가 '개선' 으로).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from koo_sphere_report.models import (  # noqa: E402
    AngleCondition, MotionData, PartInfo, PartResult, Report, SimulationResult,
    TimeSeriesData,
)
from koo_sphere_report.report.json_report import save_json  # noqa: E402


@pytest.fixture(autouse=True)
def _restore():
    saved = (MotionData.UNIT_SYSTEM, MotionData.G_FACTOR,
             MotionData.UNIT_NOTE, dict(MotionData.UNIT_LABELS))
    yield
    (MotionData.UNIT_SYSTEM, MotionData.G_FACTOR,
     MotionData.UNIT_NOTE, MotionData.UNIT_LABELS) = saved


def _report() -> Report:
    pr = PartResult(part=PartInfo(part_id=1, part_name="PKG\\A", group="PKG"))
    ts = TimeSeriesData()
    ts.times, ts.max_values = [0.0, 1e-4], [0.0, 300.0]
    ts.min_values, ts.avg_values = [0.0, 0.0], [0.0, 100.0]
    pr.stress = ts
    rep = Report(project_name="T", total_runs=1, successful_runs=1)
    rep.part_info = {1: pr.part}
    sr = SimulationResult(run_folder="R",
                          angle=AngleCondition(angle_name="P1", roll=0, pitch=0, yaw=0))
    sr.parts = {1: pr}
    rep.results.append(sr)
    return rep


def _saved() -> dict:
    out = Path(tempfile.mkdtemp()) / "report.json"
    save_json(_report(), str(out))
    return json.loads(out.read_text(encoding="utf-8"))


def test_sidecar_carries_detected_unit_labels():
    """검출된 단위계의 라벨이 사이드카에 실려야 한다."""
    MotionData.set_unit_system("ton-mm-s", 9806.65,
                               labels={"acc": "G", "stress": "MPa", "disp": "mm"})
    d = _saved()
    ul = d.get("unit_labels")
    assert ul, "unit_labels 가 없다 — federate 가 단위를 지어내게 된다"
    assert ul["stress"] == "MPa" and ul["disp"] == "mm"
    assert ul["acc"] == "G", "peak_g 는 G 로 저장되므로 acc 라벨은 G 여야 한다"
    assert d["unit_system"]["id"] == "ton-mm-s"


def test_si_deck_labels_are_pa_and_m():
    """SI 덱은 Pa·m 로 적어야 한다 — MPa/mm 로 적으면 1e6 배 오독이다."""
    MotionData.set_unit_system("SI", 9.80665,
                               labels={"acc": "G", "stress": "Pa", "disp": "m"})
    ul = _saved()["unit_labels"]
    assert ul["stress"] == "Pa" and ul["disp"] == "m"


def test_undetected_unit_writes_no_labels():
    """미검출이면 라벨을 지어내지 않는다 — 대신 사유를 적는다."""
    MotionData.set_unit_system("", note="덱 밀도를 못 읽었다")
    d = _saved()
    assert "unit_labels" not in d, "단위를 모르는데 라벨을 만들었다"
    assert d["unit_system"]["detected"] is False
    assert d["unit_system"]["note"]


def test_all():
    """pytest 진입점."""
    saved = (MotionData.UNIT_SYSTEM, MotionData.G_FACTOR,
             MotionData.UNIT_NOTE, dict(MotionData.UNIT_LABELS))
    try:
        test_sidecar_carries_detected_unit_labels()
        test_si_deck_labels_are_pa_and_m()
        test_undetected_unit_writes_no_labels()
    finally:
        (MotionData.UNIT_SYSTEM, MotionData.G_FACTOR,
         MotionData.UNIT_NOTE, MotionData.UNIT_LABELS) = saved
