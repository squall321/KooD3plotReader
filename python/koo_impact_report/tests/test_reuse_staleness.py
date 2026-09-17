# 옛 deep 산출물 재사용과 캐시 지문이 코드·입력 변화를 잡는지 보는 시험
"""재사용 판단은 '파일이 있는가' 가 아니라 '그게 지금 입력에서 나온 것인가' 다.

종전 `_reuse` 는 analysis_result.json 과 motion/*.csv 의 존재만 봤다. 같은
자리에서 다시 푼 런(rerun.sh)이면 d3plot·binout 이 산출물보다 새롭고, 한
위치에 옛 peak_g/응력/motion 과 새 에너지흐름·solver_quality 가 섞인다.

`_run_fingerprint` 도 입력 파일 stat 만 봤다. unified_analyzer 를 새로 빌드하거나
로더를 고쳐도 지문이 같아 '캐시 N/N 적중' 으로 옛 산출물이 그대로 재사용됐다
(_CACHE_SCHEMA 를 손으로 올리기 전까지). 키워드 덱(파트 이름·재료·항복값·
초기속도의 출처)도 지문에 없었다.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from koo_impact_report import loader  # noqa: E402


def _touch(p: Path, mtime_ns: int, data: bytes = b"x") -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    os.utime(p, ns=(mtime_ns, mtime_ns))


def _layout(root: Path, d3_ns: int, out_ns: int):
    d3 = root / "Output" / "d3plot"
    work = root / "report"
    _touch(d3, d3_ns)
    _touch(work / "analysis_result.json", out_ns, b"{}")
    _touch(work / "motion" / "part_1_motion.csv", out_ns, b"Time\n0.0\n")
    return d3, work


def test_fresh_output_is_reusable(tmp_path: Path):
    """산출물이 d3plot 보다 새로우면 재사용한다 — 회귀 방지."""
    d3, work = _layout(tmp_path, d3_ns=1_000_000_000_000_000_000,
                       out_ns=1_000_000_001_000_000_000)
    assert loader._reuse_staleness(d3, work) is None


def test_resolved_run_invalidates_output(tmp_path: Path):
    """d3plot 이 더 새로우면 사유를 돌려준다 (그러면 다시 돌린다)."""
    d3, work = _layout(tmp_path, d3_ns=1_000_000_002_000_000_000,
                       out_ns=1_000_000_001_000_000_000)
    reason = loader._reuse_staleness(d3, work)
    assert reason is not None and "d3plot" in reason, reason


def test_stale_motion_csv_is_caught(tmp_path: Path):
    """JSON 만 새로 쓰고 motion CSV 가 옛것인 경우도 잡는다."""
    d3, work = _layout(tmp_path, d3_ns=1_000_000_002_000_000_000,
                       out_ns=1_000_000_003_000_000_000)
    old = 1_000_000_001_000_000_000
    csv_p = work / "motion" / "part_1_motion.csv"
    os.utime(csv_p, ns=(old, old))
    reason = loader._reuse_staleness(d3, work)
    assert reason is not None and "motion CSV" in reason, reason


def test_missing_d3plot_cannot_be_judged(tmp_path: Path):
    """d3plot 이 지워졌으면 비교 불가 — None (호출부가 따로 기록한다)."""
    _, work = _layout(tmp_path, d3_ns=1_000_000_002_000_000_000,
                      out_ns=1_000_000_001_000_000_000)
    assert loader._reuse_staleness(tmp_path / "Output" / "gone", work) is None


def test_fingerprint_includes_producer_and_keyword(tmp_path: Path):
    """지문이 생산자(코드·바이너리)와 키워드 덱을 포함한다."""
    d3, work = _layout(tmp_path, d3_ns=1_000_000_001_000_000_000,
                       out_ns=1_000_000_002_000_000_000)
    kfile = d3.parent / "DropWeightImpactTestSet.k"
    _touch(kfile, 1_000_000_000_000_000_000, b"*PART\n")
    run = {"d3plot": d3, "deep_dir": work, "config": {"LocationX": "20"}}

    fp0 = loader._run_fingerprint(run, 0, 0)

    # 키워드 덱이 바뀌면 지문이 바뀌어야 한다 (파트 이름·항복값의 출처).
    _touch(kfile, 1_000_000_009_000_000_000, b"*PART\n*MAT_ELASTIC\n")
    assert loader._run_fingerprint(run, 0, 0) != fp0

    # 생산자 정체가 지문에 실제로 들어간다.
    ident = loader._producer_identity()
    assert "impact=" in ident and "loader=" in ident and "ua=" in ident, ident
    fp1 = loader._run_fingerprint(run, 0, 0)
    _orig = loader._producer_identity
    try:
        loader._producer_identity = lambda: ident + "|rebuilt"
        fp_rebuilt = loader._run_fingerprint(run, 0, 0)
    finally:
        loader._producer_identity = _orig
    assert fp_rebuilt != fp1, \
        "바이너리/코드가 바뀌어도 지문이 같다 — 옛 캐시가 조용히 적중한다"


def test_all(tmp_path: Path):
    """pytest 진입점 — 위 시험들을 한 번에 돌린다."""
    test_fresh_output_is_reusable(tmp_path / "a")
    test_resolved_run_invalidates_output(tmp_path / "b")
    test_stale_motion_csv_is_caught(tmp_path / "c")
    test_missing_d3plot_cannot_be_judged(tmp_path / "d")
    test_fingerprint_includes_producer_and_keyword(tmp_path / "e")
