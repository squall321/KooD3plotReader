# d3plot 이 없어 신선도를 못 본 재사용이 실제로 기록에 남는지 보는 시험
"""`_reuse_staleness` 는 d3plot 이 없으면 첫 줄에서 None 을 돌려준다.

그런데 호출부는 `if _stale_reason is not None:` 안쪽에서만 'd3plot 이 없다'
분기를 갖고 있었다. 그 분기에는 도달할 수 없어, 옛 deep 산출물만 남은 런은
신선도 검증 없이 조용히 재사용되고 보고서에 아무 흔적도 남지 않았다.

'검증하지 못했다' 는 사실은 값이 아니라 사유로 남아야 한다.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent.parent / "koo_deep_report"))

from koo_impact_report import loader  # noqa: E402

_CSV = (
    "Time,Avg_Disp_X,Avg_Disp_Y,Avg_Disp_Z,Avg_Disp_Mag,"
    "Avg_Vel_X,Avg_Vel_Y,Avg_Vel_Z,Avg_Vel_Mag,"
    "Avg_Acc_X,Avg_Acc_Y,Avg_Acc_Z,Avg_Acc_Mag\n"
    "0.0,0,0,0,0,0,0,0,0,0,0,0,0\n"
    "0.001,0,0,1,1,0,0,10,10,0,0,100,100\n"
)


def _touch(p: Path, mtime_ns: int, data: bytes) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    os.utime(p, ns=(mtime_ns, mtime_ns))


def _deep_outputs(root: Path) -> Path:
    work = root / "report"
    _touch(work / "analysis_result.json", 1_000_000_001_000_000_000, b"{}")
    _touch(work / "motion" / "part_1_motion.csv",
           1_000_000_001_000_000_000, _CSV.encode())
    return work


def _stub_parse_outputs(monkeypatch):
    """_parse_outputs 는 여기서 볼 대상이 아니다 — 통과만 시킨다."""
    import koo_deep_report.core.d3plot_reader as dr
    monkeypatch.setattr(dr, "_parse_outputs", lambda *a, **k: object())


def test_missing_d3plot_reuse_is_recorded(tmp_path: Path, monkeypatch):
    """d3plot 이 없는 재사용은 load_issue 로 남아야 한다."""
    _stub_parse_outputs(monkeypatch)
    work = _deep_outputs(tmp_path)
    issues: list[dict] = []
    motions, _ = loader.load_per_part_motions(
        tmp_path / "Output" / "d3plot", work_dir=work, issues=issues)
    assert 1 in motions, motions
    kinds = [i.get("kind") for i in issues]
    assert "deep-output-unverified" in kinds, issues
    msg = [i for i in issues if i.get("kind") == "deep-output-unverified"][0]["msg"]
    assert "d3plot" in msg, msg


def test_present_and_fresh_d3plot_records_nothing(tmp_path: Path, monkeypatch):
    """d3plot 이 있고 산출물이 새로우면 아무 사유도 남기지 않는다."""
    _stub_parse_outputs(monkeypatch)
    work = _deep_outputs(tmp_path)
    _touch(tmp_path / "Output" / "d3plot", 1_000_000_000_000_000_000, b"x")
    issues: list[dict] = []
    loader.load_per_part_motions(
        tmp_path / "Output" / "d3plot", work_dir=work, issues=issues)
    assert issues == [], issues


def test_all(tmp_path: Path, monkeypatch):
    """진입점 — 이 파일의 시험을 모두 돌린다."""
    test_missing_d3plot_reuse_is_recorded(tmp_path / "a", monkeypatch)
    test_present_and_fresh_d3plot_records_nothing(tmp_path / "b", monkeypatch)
