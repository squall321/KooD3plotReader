# report.json 이 런 end_time·tool_commit, 소견 part_id 를 싣는지 — 없으면 키를 안 만든다
"""온톨로지 변환기가 읽을 칸 (DynaForge 요청, 2026-10-31).

이 셋이 없으면 소비자가 런당 **93 MB** 짜리 analysis_result.json 을 열어야 한다.

규칙은 이 저장소의 평소 것과 같다 — **없으면 키를 만들지 않는다.**
- `end_time`·`tool_commit`: 옛 산출물에는 기록이 없다. 0 이나 빈 글자를 넣으면
  '0초에 끝났다'·'빌드 미상이 아니라 빈 빌드' 로 읽힌다.
- `part_id`: 캠페인 전체를 두고 하는 소견(단위 미검출, 맵 자릿수, 요약)에는
  파트가 없다. 0 으로 채우면 읽는 쪽이 **'파트 0'** 으로 읽는다.
"""
from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from koo_sphere_report.models import (  # noqa: E402
    AngleCondition, Finding, PartInfo, Report, Severity, SimulationResult,
)
from koo_sphere_report.report.json_report import save_json  # noqa: E402


def _save(report, tmp_path) -> dict:
    p = tmp_path / "r.json"
    save_json(report, str(p))
    return json.loads(p.read_text(encoding="utf-8"))


def _report(**kw):
    return Report(part_info={1: PartInfo(part_id=1, part_name="X", group="G")}, **kw)


def test_run_carries_end_time_and_tool_commit(tmp_path):
    sr = SimulationResult(run_folder="R", angle=AngleCondition("A", 0, 0, 0),
                          parts={}, end_time=0.001234, tool_commit="v2.4-abc")
    d = _save(_report(results=[sr], successful_runs=1), tmp_path)
    r = d["results_summary"][0]
    assert r["end_time"] == pytest.approx(0.001234)
    assert r["tool_commit"] == "v2.4-abc"


def test_missing_run_fields_make_no_key(tmp_path):
    """옛 산출물 — 0 이나 빈 글자로 채우지 않는다."""
    sr = SimulationResult(run_folder="R", angle=AngleCondition("A", 0, 0, 0),
                          parts={}, end_time=None, tool_commit="")
    r = _save(_report(results=[sr], successful_runs=1), tmp_path)["results_summary"][0]
    assert "end_time" not in r and "tool_commit" not in r


def test_part_finding_carries_part_id(tmp_path):
    f = Finding(Severity.CRITICAL, "Part 1 (X): stress exceeds yield", "d", "r",
                part_id=1)
    d = _save(_report(findings=[f]), tmp_path)
    assert d["findings"][0]["part_id"] == 1


def test_campaign_wide_finding_has_no_part_id(tmp_path):
    """**0 으로 채우면 '파트 0' 으로 읽힌다.** 키를 빼는 것이 맞다."""
    f = Finding(Severity.WARNING, "단위계 미검출", "d", "r")
    d = _save(_report(findings=[f]), tmp_path)
    assert "part_id" not in d["findings"][0]


def test_finding_default_is_none_not_zero():
    assert dataclasses.fields(Finding)[-1].name == "part_id"
    assert Finding(Severity.INFO, "t", "d", "r").part_id is None


def test_every_part_scoped_finding_gets_an_id():
    """**이 시험이 2026-10-31 의 누락을 잡는다.**

    처음엔 `recommendation=…,` 로 끝나는 줄만 찾아 붙이는 식으로 고쳤는데,
    여러 줄로 이어진 호출 셋 중 둘을 놓쳤다. 실데이터에서 part_id 가 0건으로
    나와서야 드러났다. 그래서 자리 수가 아니라 **파트 루프 안의 모든 Finding**
    이 id 를 갖는지 구조로 본다.
    """
    import re
    src = Path(__import__("koo_sphere_report.analyzer", fromlist=["x"]).__file__
               ).read_text(encoding="utf-8")
    lines = src.split("\n")
    lo = next(i for i, l in enumerate(lines)
              if l.startswith("    for pid, pi in report.part_info.items():"))
    hi = next(i for i, l in enumerate(lines) if l.startswith("    # ── 항복 판정의 바탕"))
    missing = []
    for i in range(lo, hi):
        if "findings.append(Finding(" not in lines[i]:
            continue
        j, body = i + 1, []
        while j < len(lines) and lines[j].strip() != "))":
            body.append(lines[j]); j += 1
        if not any("part_id=" in b for b in body):
            missing.append(lines[i + 1].strip()[:60])
    assert not missing, f"파트 소견인데 part_id 가 없다: {missing}"
