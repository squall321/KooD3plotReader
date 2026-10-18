# batch 하위명령이 --config 를 실제로 적용하는지 — 조용한 무시를 막는 시험
"""`koo_deep_report batch --config x.yaml <root>` 의 설정 적용.

실측 배경 (2026-10-18). `run_single` 은 맨 앞에서 `_apply_config_to_args` 를
부르는데 `run_batch` 는 부르지 않았다. 그래서 batch 에 --config 를 주면
**설정 파일 전체가 경고 한 줄 없이 무시됐다.** 항복응력·스레드·단면뷰·핫스팟이
전부 기본값으로 돌고, 로그에도 아무 말이 없어 설정대로 돈 것처럼 보였다.
__main__.py 903줄이 같은 부류의 함정을 이미 경고하고 있다.

여기서 못박는 규칙 — **설정은 single·batch 에서 같게 먹고, 안 먹는 항목은
말을 한다.**
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from koo_deep_report import __main__ as M


class _Stop(Exception):
    """설정 적용 직후 실제 배치 작업으로 넘어가기 전에 멈추기 위한 표식."""


def _batch_args(tmp_path: Path, cfg: Path) -> argparse.Namespace:
    """batch 하위명령의 기본값 네임스페이스 (argparse 기본값과 같게)."""
    return argparse.Namespace(
        command="batch", path=str(tmp_path), config=str(cfg),
        output="./single_report", yield_stress=0.0, strain_limit=0.0,
        ua_threads=0, render_threads=1, verbose=False, parts=None,
        no_render=False, skip_existing=False, threads=1,
        hotspot_clusters=False, hotspot_criterion="von_mises",
        hotspot_time_aggregate="elemmax_then_mean",
        install_dir="", part_pattern="", section_view=False,
    )


def _run_until_scan(args, monkeypatch):
    """run_batch 를 돌리되 폴더 탐색 직전에 멈춘다 (설정 적용은 그 앞에 있다)."""
    import koo_deep_report.core.sim_detector as SD

    def _boom(*a, **k):
        raise _Stop
    monkeypatch.setattr(SD, "find_all", _boom)
    with pytest.raises(_Stop):
        M.run_batch(args)


def test_batch_applies_config(tmp_path, monkeypatch):
    """**이 시험이 2026-10-18 의 조용한 무시를 잡는다.**"""
    cfg = tmp_path / "a.yaml"
    cfg.write_text(
        "design_criteria:\n"
        "  global_stress_limit: 321.0\n"
        "performance:\n"
        "  threads: 7\n",
        encoding="utf-8")
    args = _batch_args(tmp_path, cfg)
    _run_until_scan(args, monkeypatch)

    assert args.yield_stress == 321.0, "batch 가 설정 파일의 항복응력을 버렸다"
    assert args.ua_threads == 7, "batch 가 설정 파일의 스레드 수를 버렸다"


def test_batch_cli_beats_config(tmp_path, monkeypatch):
    """명령행이 설정보다 우선한다 — single 과 같은 규칙."""
    cfg = tmp_path / "a.yaml"
    cfg.write_text("design_criteria:\n  global_stress_limit: 321.0\n",
                   encoding="utf-8")
    args = _batch_args(tmp_path, cfg)
    args.yield_stress = 99.0           # 사용자가 명령행에 직접 준 값
    _run_until_scan(args, monkeypatch)
    assert args.yield_stress == 99.0


def test_batch_warns_config_path_unused(tmp_path, monkeypatch, capsys):
    """설정의 d3plot 경로는 batch 에서 안 쓰인다 — 버리되 말은 한다."""
    other = tmp_path / "elsewhere"
    other.mkdir()
    cfg = tmp_path / "a.yaml"
    cfg.write_text(f"input:\n  d3plot: {other}\n", encoding="utf-8")
    args = _batch_args(tmp_path, cfg)
    _run_until_scan(args, monkeypatch)

    out = capsys.readouterr().out
    assert "쓰지 않습니다" in out, "설정 경로를 조용히 버렸다"
    assert Path(args.path).resolve() == tmp_path.resolve()


def test_batch_no_config_is_silent(tmp_path, monkeypatch, capsys):
    """--config 없으면 아무 말도 더하지 않는다."""
    args = _batch_args(tmp_path, tmp_path / "unused.yaml")
    args.config = ""
    _run_until_scan(args, monkeypatch)
    assert "쓰지 않습니다" not in capsys.readouterr().out
