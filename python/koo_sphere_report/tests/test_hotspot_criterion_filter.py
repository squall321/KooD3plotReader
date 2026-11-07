# 핫스팟 3D 뷰어가 기준을 하나씩만 그리는지 · 's' 척도 이름표가 기준을 따르는지 node 로 검증하는 시험
"""핫스팟 3D 인벨롭의 기준 거르기 (2026-11-07).

분석기 기본 기준이 von_mises + plastic_strain 이 되면서 한 런의 hotspot 목록에 두 기준이
섞여 온다. 뷰어는 기준을 보지 않고 군집을 한 색 척도에 모았기 때문에, 응력(수백 MPa)과
ε_p(0.001)가 섞이면 소성 군집은 전부 가장 옅은 색이 되고 이름표는 '응력 최대' 였다.

여기서 못박는 규칙.
- 고른 기준의 군집만 모은다.
- 's' 척도(stress_max)의 이름표는 기준을 따른다 — 소성 기준이면 응력이라 부르지 않는다.
- 기준 목록은 데이터에 나온 순서, 중복 없음.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import jsutil as js

_JS = (Path(__file__).resolve().parents[1]
       / "koo_sphere_report" / "report" / "html_report.py").read_text(encoding="utf-8")

pytestmark = pytest.mark.skipif(js.node_bin() is None, reason="node 없음")

_DATA = """
const DATA = { results: [
  { folder: 'F1', angle: { name: 'F1' }, hotspot: [
      { p: 5, cr: 'von_mises', cl: [ { k: 1, s: 320.0 }, { k: 2, s: 280.0 } ] },
      { p: 5, cr: 'plastic_strain', cl: [ { k: 1, s: 0.004 } ] } ] },
  { folder: 'F2', angle: { name: 'F2' }, hotspot: [
      { p: 7, cr: 'plastic_strain', cl: [ { k: 1, s: 0.002 } ] },
      { p: 7, cr: 'von_mises', cl: [ { k: 1, s: 150.0 } ] } ] },
] };
const HS3D = { crit: null, off: {}, offPart: {} };
"""

_FUNCS = ["hs3dRuns", "hs3dEnabled", "hs3dPartOn", "hs3dClusters", "hs3dCriteria", "hs3dMeasureLabel"]


def _measures() -> str:
    i = _JS.index("const HS3D_MEASURES = [")
    return _JS[i:_JS.index("];", i) + 2] + "\n"


def _run(body: str) -> list[str]:
    return js.run_js(_DATA + _measures() + js.extract_functions(_JS, _FUNCS) + "\n" + body)


def test_criteria_listed_in_data_order():
    assert _run("console.log(hs3dCriteria().join(','));") == ["von_mises,plastic_strain"]


def test_only_selected_criterion_is_gathered():
    out = _run("HS3D.crit = 'von_mises'; console.log(hs3dClusters().map(o => o.c.s).join(','));\n"
               "HS3D.crit = 'plastic_strain'; console.log(hs3dClusters().map(o => o.c.s).join(','));")
    assert out == ["320,280,150", "0.004,0.002"]


def test_stress_measure_label_follows_criterion():
    out = _run("for (const c of ['von_mises', 'plastic_strain', 'plastic_work']) "
               "{ HS3D.crit = c; console.log(hs3dMeasureLabel('s')); }\n"
               "console.log(hs3dMeasureLabel('wd'));")
    assert out[0] == "응력 최대"
    assert out[1].startswith("ε_p") and "응력" not in out[1]
    assert out[2].startswith("w_p")
    assert out[3] == "소성일 밀도 (mJ/mm³)"          # 다른 척도는 그대로
