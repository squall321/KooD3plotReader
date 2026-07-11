# KooChainRun DWI 레이아웃(output/results/dwi_*/Run_*) discover 확장 단위 테스트
"""``_discover_test_impact_runs`` 의 DWI 레이아웃 스캔 검증.

실데이터 없이 tmp_path 로 최소 픽스처(빈 d3plot + DropWeightImpactTestSet.json)를
구성해, 위치/DOE 파싱과 discovery-order fallback, 무회귀를 확인한다.
"""
from __future__ import annotations

import json

import pytest

try:
    from koo_impact_report import loader
except ImportError as exc:  # pragma: no cover
    pytest.skip(f"koo_impact_report.loader not importable: {exc}",
                allow_module_level=True)


def _make_dwi_run(test_dir, folder: str, stage: str, description: str) -> None:
    """output/results/<folder>/Run_.../ 에 빈 d3plot + testset json 생성."""
    run = test_dir / "output" / "results" / folder / "Run_20260710_000000_abc"
    (run / "Output").mkdir(parents=True)
    (run / "Output" / "d3plot").write_bytes(b"")  # 존재만 하면 discover 통과
    (run / "DropWeightImpactTestSet.json").write_text(
        json.dumps({"stage": stage, "description": description}),
        encoding="utf-8",
    )


def test_discover_dwi_layout(tmp_path):
    """dwi_0001/0002 → 위치·DOE 를 json description/stage 에서 파싱."""
    _make_dwi_run(tmp_path, "dwi_0001", "Case0001",
                  "DWI Case1/2 x=-30.00 y=-60.00")
    _make_dwi_run(tmp_path, "dwi_0002", "Case0002",
                  "DWI Case2/2 x=30.00 y=-60.00")

    runs = loader._discover_test_impact_runs(tmp_path)

    assert len(runs) == 2
    by_pos = {r["pos_name"]: r for r in runs}
    assert set(by_pos) == {"DOE_001", "DOE_002"}

    r1 = by_pos["DOE_001"]
    assert r1["doe_index"] == 1
    assert r1["location_x"] == pytest.approx(-30.0)
    assert r1["location_y"] == pytest.approx(-60.0)
    assert r1["deep_dir"] is None          # deep_report 산출물 없음 → 워커 직접 처리
    assert r1["config"] is None            # step_config.txt 없음
    assert r1["d3plot"].exists()

    r2 = by_pos["DOE_002"]
    assert r2["doe_index"] == 2
    assert r2["location_x"] == pytest.approx(30.0)
    assert r2["location_y"] == pytest.approx(-60.0)

    # DOE 인덱스 순 정렬
    assert [r["pos_name"] for r in runs] == ["DOE_001", "DOE_002"]


def test_discover_dwi_fallback_on_unparseable_json(tmp_path):
    """stage/description 파싱 실패 → 폴더번호 doe_index, 위치는 0.0."""
    # description 에 x=/y= 없음, stage 도 Case 형식 아님 → 폴더번호 fallback.
    _make_dwi_run(tmp_path, "dwi_0007", "bogus", "no coords here")

    runs = loader._discover_test_impact_runs(tmp_path)

    assert len(runs) == 1
    r = runs[0]
    assert r["doe_index"] == 7          # dwi_0007 폴더번호 fallback
    assert r["pos_name"] == "DOE_007"
    assert r["location_x"] == 0.0
    assert r["location_y"] == 0.0


def test_discover_empty_output_returns_empty(tmp_path):
    """output/ 부재 시 빈 리스트 — 무회귀 안전장치."""
    assert loader._discover_test_impact_runs(tmp_path) == []
