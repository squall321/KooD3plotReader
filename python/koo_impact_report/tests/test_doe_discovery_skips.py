# DOE 발견 단계에서 뺀 런이 보고서에 기록되는지 보는 시험
"""건너뛴 Run_* 는 '없었던 것' 이 아니다.

`_discover_test_impact_runs` 는 step_config.txt 가 없거나 d3plot·deep 산출물이
둘 다 없는 Run_* 를 조용히 건너뛰었다. 5×5 DOE 에서 2 개가 대기/취소 상태면
보고서는 n_positions=23 을 전체 DOE 로 제시하고 'Runs failed to load' 도 뜨지
않는다 — KPI·안전영역 집계·'n_valid_runs 9/23' 배지가 전부 23 을 분모로 쓴다.

건너뛴 디렉터리와 사유를 돌려주고, DOE 로더가 load_issues(run-skipped) 로
남기며 n_runs 를 디스크에 있던 Run_* 전체로 센다.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from koo_impact_report import loader  # noqa: E402


def _make_run(root: Path, name: str, *, cfg: bool, d3plot: bool) -> Path:
    run = root / "output" / name
    (run / "Output").mkdir(parents=True, exist_ok=True)
    if cfg:
        (run / "step_config.txt").write_text(
            "*Description,DOE001 Step1 IMPACT P_001_001\n"
            "LocationX,20\nLocationY,-40\n", encoding="utf-8")
    if d3plot:
        (run / "Output" / "d3plot").write_bytes(b"\x00" * 16)
    return run


def test_skipped_runs_are_reported(tmp_path: Path):
    """step_config 없음 / 산출물 없음 두 경우가 사유와 함께 잡힌다."""
    _make_run(tmp_path, "Run_ok", cfg=True, d3plot=True)
    _make_run(tmp_path, "Run_nocfg", cfg=False, d3plot=True)
    _make_run(tmp_path, "Run_pending", cfg=True, d3plot=False)

    skipped: list[dict] = []
    runs = loader._discover_test_impact_runs(tmp_path, skipped=skipped)
    assert [r["run_dir"].name for r in runs] == ["Run_ok"]
    got = {s["run"]: s["reason"] for s in skipped}
    assert set(got) == {"Run_nocfg", "Run_pending"}, got
    assert "step_config.txt" in got["Run_nocfg"]
    assert "d3plot" in got["Run_pending"]


def test_skipped_is_optional_and_default_is_unchanged(tmp_path: Path):
    """인자를 안 주면 종전과 똑같이 목록만 돌려준다 — 회귀 방지."""
    _make_run(tmp_path, "Run_ok", cfg=True, d3plot=True)
    _make_run(tmp_path, "Run_nocfg", cfg=False, d3plot=True)
    runs = loader._discover_test_impact_runs(tmp_path)
    assert [r["run_dir"].name for r in runs] == ["Run_ok"]


def test_all(tmp_path: Path):
    """pytest 진입점 — 위 시험들을 한 번에 돌린다."""
    test_skipped_runs_are_reported(tmp_path / "a")
    test_skipped_is_optional_and_default_is_unchanged(tmp_path / "b")
