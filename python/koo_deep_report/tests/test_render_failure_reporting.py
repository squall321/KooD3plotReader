# 렌더 실패가 unified_analyzer 종료 코드에서 보고서까지 올라오는지 검증하는 시험
"""DynaForge 결함 보고 K-4 (2026-10-28).

unified_analyzer 는 분석은 됐지만 렌더·단면 영상이 실패하면 rc 3 을 낸다.
예전에는 rc 0 이었고 2차 패스의 RuntimeError 도 버려, 빠진 영상이 갤러리
공백으로 조용히 지나갔다. 이제 render_warnings 로 보고서에 남는다.
"""
import stat
from pathlib import Path

import pytest

from koo_deep_report.core import d3plot_reader as R
from koo_deep_report.render.job_builder import RenderConfig, SectionViewRenderConfig
from koo_deep_report.report.models import D3plotResult, PartTimeSeries


def _fake_ua(tmp_path: Path, rc: int, stdout: str = "", stderr: str = "") -> Path:
    exe = tmp_path / "unified_analyzer"
    exe.write_text(
        "#!/bin/sh\n"
        f"cat <<'EOF'\n{stdout}\nEOF\n"
        f"cat >&2 <<'EOF'\n{stderr}\nEOF\n"
        f"exit {rc}\n"
    )
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    return exe


# ── _run_ua 종료 코드 해석 ──────────────────────────────────

def test_run_ua_rc0_returns_none(tmp_path):
    assert R._run_ua(_fake_ua(tmp_path, 0), "version: 2.0\n", verbose=False) is None


def test_run_ua_rc3_returns_failed_lines(tmp_path):
    ua = _fake_ua(
        tmp_path, 3,
        stdout="    [1/1] section_view_z [z center]\n"
               "    FAILED: section_view_z [z center] - LSPrePost exited with code 134",
        stderr="[RENDER] Some render jobs failed.",
    )
    w = R._run_ua(ua, "version: 2.0\n", verbose=False)
    assert w is not None and "rc=3" in w
    assert "FAILED: section_view_z" in w and "code 134" in w


def test_run_ua_other_rc_raises(tmp_path):
    with pytest.raises(RuntimeError, match="rc=1"):
        R._run_ua(_fake_ua(tmp_path, 1, stderr="Analysis failed"), "version: 2.0\n", verbose=False)


# ── run_analysis 가 두 패스의 실패를 모두 남기는가 ────────────

def _result_with_part(output_dir: Path) -> D3plotResult:
    ts = PartTimeSeries(part_id=7, part_name="P7", quantity="von_mises", unit="",
                        global_max=1.0, global_min=0.0, time_of_max=0.0, data=[])
    return D3plotResult(metadata={}, stress=[ts], strain=[], acceleration=[], motion={},
                        output_dir=output_dir)


def test_run_analysis_records_both_pass_failures(tmp_path, monkeypatch):
    calls = []

    def fake_run_ua(ua, yaml_content, verbose):
        calls.append(yaml_content)
        if len(calls) == 1:
            return "unified_analyzer 렌더 일부 실패 (rc=3):\nFAILED: overview"
        raise RuntimeError("unified_analyzer failed (rc=134)")

    monkeypatch.setattr(R, "find_unified_analyzer", lambda install_dir=None: tmp_path / "ua")
    monkeypatch.setattr(R, "_run_ua", fake_run_ua)
    monkeypatch.setattr(R, "_parse_outputs", lambda out, **kw: _result_with_part(out))
    monkeypatch.setattr(R, "_resolve_lsprepost", lambda rc, install_dir=None: "/opt/lsprepost")

    sv = SectionViewRenderConfig(enabled=True, backend="lsprepost", per_part_render=True,
                                 axes=["z"])
    res = R.run_analysis(tmp_path / "d3plot", tmp_path / "out",
                         render_config=RenderConfig(enabled=True), section_view_config=sv)

    assert len(calls) == 2, "파트별 2차 패스가 돌아야 한다"
    assert len(res.render_warnings) == 2
    assert "FAILED: overview" in res.render_warnings[0]
    assert "파트별 렌더 패스 실패" in res.render_warnings[1] and "rc=134" in res.render_warnings[1]
