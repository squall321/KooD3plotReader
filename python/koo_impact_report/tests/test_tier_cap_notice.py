# tier 캡으로 버린 위치를 화면이 알려주는지 보는 시험
"""tier C(101~300 위치)는 에너지 흐름과 가속도 곡선을 상위 40 위치만 싣는다.

캡 자체는 전송 예산이라 정당하다. 문제는 **조용하다** 는 것이었다.
41위 위치를 s9 에서 고르면 에너지 패널이 직전 위치 그래프를 그대로 붙들고
있었고(`if (!flows[posId]) return;`), s9 가속도 차트는 '가속도 시계열 없음'
이라 적었다 — 계산은 됐는데 전송에서 빠진 것을 데이터 부재로 읽게 만든다.

캡 값을 payload meta 에 싣고 두 곳 문구에 반영한다.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from koo_impact_report.models import (  # noqa: E402
    FaceOrientation, ImpactPosition, ImpactReport, ImpactorSpec,
    PairResult, PartInfo,
)
from koo_impact_report.report.html_report import generate_html  # noqa: E402
from koo_impact_report.report.payload import _build_payload  # noqa: E402
from koo_impact_report.report.payload.tiers import tier_for  # noqa: E402


def _report(n_positions: int) -> ImpactReport:
    face = FaceOrientation("F5", "Top", 90.0, 0.0, 0.0)
    positions, results = [], []
    for i in range(n_positions):
        pos = ImpactPosition(pos_id=f"F5_DOE_{i + 1:03d}", face="F5",
                             x=float(i), y=0.0)
        positions.append(pos)
        results.append(PairResult(face="F5", position=pos, part_id=7,
                                  peak_g=1000.0 + i, peak_stress=100.0,
                                  peak_strain=1e-5, peak_disp=0.1, peak_vel=1.0))
    return ImpactReport(
        project_name="unit",
        impactor=ImpactorSpec(type="Sphere", radius=8.0, part_id=99),
        faces=[face],
        positions_by_face={"F5": positions},
        parts=[PartInfo(part_id=7, part_name="PKG 7")],
        results=results,
        sim_params={"unit_labels": {"time": "s"}},
    )


def test_tier_cap_is_in_payload_meta():
    """150 위치(tier C)면 meta.tier 에 상위 40 캡이 실린다."""
    payload = _build_payload(_report(150))
    tier = payload["meta"]["tier"]
    assert tier["name"] == "C", tier
    assert tier["energy_flow_topk"] == tier_for(150).energy_flow_topk == 40
    assert tier["part_motion_topk"] == 40


def test_tier_a_reports_no_cap():
    """50 위치 이하(tier A)는 캡이 0 — 문구가 뜨지 않아야 한다."""
    tier = _build_payload(_report(10))["meta"]["tier"]
    assert tier["name"] == "A"
    assert tier["energy_flow_topk"] == 0
    assert tier["part_motion_topk"] == 0


def test_capped_position_is_announced_not_silent():
    """잘린 위치를 고르면 조용히 이전 상태를 유지하지 않는다."""
    html = generate_html(_report(150))
    # 종전의 무고지 조기 반환이 남아 있으면 안 된다.
    assert "if (!flows[posId]) return;" not in html
    assert "energy_flow_topk" in html
    assert "part_motion_topk" in html


def test_all():
    """pytest 진입점 — 위 시험들을 한 번에 돌린다."""
    test_tier_cap_is_in_payload_meta()
    test_tier_a_reports_no_cap()
    test_capped_position_is_announced_not_silent()
