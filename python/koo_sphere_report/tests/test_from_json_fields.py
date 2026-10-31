# --from-json 왕복에서 사이드카 **칸**이 사라지지 않는지
"""`--from-json` 왕복의 칸 보존.

(파형 보존은 test_from_json_roundtrip.py 가 따로 지킨다 — 그쪽은 변위 곡선을
잃거나 2점 램프를 지어내던 결함의 가드다. 이 파일은 **최상위 칸**만 본다.)

2026-10-31 지적(kood3plotreader-bf). `load_report_from_json` 이 `test_dir` 을
되살리지 않아, `--from-json` 으로 다시 쓴 `report.json` 의 `test_dir` 이
`''` 가 됐다(v14: '/data/koopark/Test_Postprocess_v14' → ''). 그걸 읽는
온톨로지 꾸러미는 **덱 정보가 통째로 빈** 결과를 냈다 — 맞닿지 않은 접촉,
재질, 충돌 속도·낙하 높이, DropSet 항복값. 사라진 줄도 모른 채.

확인해 보니 같은 부류로 다섯 칸이 빠져 있었다. 그중 `part_yield_limits` 는
**화면과 소견을 갈라 놓는다** — 재생성한 HTML 이 파트별 한계를 잃고 기본값으로
떨어지면, 사이드카에 실린 소견과 다른 안전율을 말한다.

여기서 못박는 것 — **사이드카에 있는 칸은 왕복에서 살아남는다.**
"""
from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from koo_sphere_report.from_json import load_report_from_json  # noqa: E402
from koo_sphere_report.models import (  # noqa: E402
    AngleCondition, PartInfo, Report, SimulationResult,
)
from koo_sphere_report.report.json_report import save_json  # noqa: E402
from koo_sphere_report.yield_map import PartYield, YieldLimit  # noqa: E402


def _seed() -> Report:
    sr = SimulationResult(run_folder="R0", angle=AngleCondition("A", 0.0, 0.0, 0.0),
                          parts={}, end_time=0.00123, tool_commit="v9-abc")
    return Report(
        project_name="P", results=[sr], successful_runs=1,
        part_info={1: PartInfo(part_id=1, part_name="X", group="G")},
        yield_stress=350.0,
        test_dir="/data/koopark/Test_Postprocess_v14",
        tool_builds={"v9-abc": 1},
        drop_reasons={"output/<run>/DropSet.json 없음": 3},
        part_yields={1: PartYield(1, [
            YieldLimit(45.0, "von_mises", "MAT_017 SIGY"),
            YieldLimit(30.0, "max_principal", "MAT_017 FS")])},
    )


def _roundtrip(tmp_path):
    p1, p2 = tmp_path / "a.json", tmp_path / "b.json"
    save_json(_seed(), str(p1))
    rep = load_report_from_json(p1)
    save_json(rep, str(p2))
    return (json.loads(p1.read_text(encoding="utf-8")),
            json.loads(p2.read_text(encoding="utf-8")), rep)


def test_test_dir_survives(tmp_path):
    """**이것이 보고된 결함이다** — 꾸러미가 덱을 못 찾게 된다."""
    a, b, rep = _roundtrip(tmp_path)
    assert a["test_dir"] == "/data/koopark/Test_Postprocess_v14"
    assert b["test_dir"] == a["test_dir"], "왕복에서 test_dir 이 사라졌다"
    assert rep.test_dir == a["test_dir"]


def test_part_yield_limits_survive(tmp_path):
    """잃으면 재생성 HTML 이 기본값으로 떨어져 **소견과 다른 안전율**을 말한다."""
    a, b, rep = _roundtrip(tmp_path)
    assert a["part_yield_limits"]["1"][1]["source"] == "MAT_017 FS"
    assert b["part_yield_limits"] == a["part_yield_limits"]
    # 되살린 객체도 같은 한계를 갖는다 (덱 단위 그대로)
    assert [l.value for l in rep.part_yields[1].limits] == [45.0, 30.0]


def test_yield_stress_survives(tmp_path):
    """바탕이 된 항복값이 없으면 재생성본의 안전율을 재현할 수 없다."""
    a, b, rep = _roundtrip(tmp_path)
    assert a["yield_stress"] == 350.0
    assert b["yield_stress"] == 350.0
    assert rep.yield_stress == 350.0


def test_tool_builds_and_drop_reasons_survive(tmp_path):
    a, b, _ = _roundtrip(tmp_path)
    assert b["tool_builds"] == a["tool_builds"] == {"v9-abc": 1}
    assert b["drop_reasons"] == a["drop_reasons"]


def test_empty_fields_make_no_key(tmp_path):
    """빈 것은 키를 만들지 않는다 — 빈 dict 도 '있다' 로 읽힌다."""
    r = Report(project_name="P", results=[], successful_runs=0)
    p = tmp_path / "e.json"
    save_json(r, str(p))
    d = json.loads(p.read_text(encoding="utf-8"))
    assert "drop_reasons" not in d and "part_yield_limits" not in d


def test_no_report_field_is_silently_dropped(tmp_path):
    """새 칸을 Report 에 더하면 여기서 걸린다 — 왕복에서 조용히 사라지지 않게.

    (사이드카가 담지 않기로 **결정한** 칸만 아래 목록에 둔다.)
    """
    # Report 칸 이름 ≠ 사이드카 키 이름인 것
    _RENAMED = {"part_yields": "part_yield_limits",
                "simulation_params": "simulation_params"}
    _NOT_IN_SIDECAR = {
        "simulation_params",   # sim_params 로 따로 실린다
        "results",             # results_summary 로 따로
        "part_info",           # parts 로 따로
        "findings",            # findings 로 따로
        "yield_notes",         # 화면 안내문 — 재생성 시 다시 만든다
        "energy_flows",        # energy_flows 로 따로
    }
    a, _, _ = _roundtrip(tmp_path)
    missing = [f.name for f in dataclasses.fields(Report)
               if f.name not in _NOT_IN_SIDECAR
               and _RENAMED.get(f.name, f.name) not in a]
    assert not missing, f"사이드카가 안 싣는 칸: {missing}"
