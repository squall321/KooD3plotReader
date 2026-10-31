# 화면(JS) 안전율이 분석기와 같은 값을 쓰는지 — 두 판정이 갈리지 않게
"""화면과 소견의 일치.

2026-10-31 지적(kood3plotreader-bf). analyzer 는 파트별 한계를 덱 단위로
비교하도록 고쳤는데 **화면 JS 는 그대로** `DATA.yield_stress`(사람이 넣은 MPa)를
덱 단위 응력으로 나누고 라벨에 "MPa" 를 박아 쓰고 있었다. 같은 보고서 안에서
소견과 화면이 **다른 안전율**을 말하게 된다 — SI 덱이면 1e6 배 차이다.

여기서 못박는 것 — **환산은 파이썬에서 한 번만** 하고(`yield_map.default_limit`),
화면은 그 결과(`DATA.yield_deck`·`DATA.part_yield_limits`)를 받아 쓴다.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import jsutil as js  # noqa: E402

_JS = (Path(__file__).resolve().parents[1]
       / "koo_sphere_report" / "report" / "html_report.py").read_text(encoding="utf-8")

pytestmark = pytest.mark.skipif(js.node_bin() is None, reason="node 없음")

_FNS = ["isNum", "stressUnit", "yieldLimits", "safetyFactor"]


def _eval(data_js: str, expr: str) -> str:
    src = (f"const DATA = {data_js};\n"
           + js.extract_functions(_JS, _FNS)
           + f"\nconsole.log(JSON.stringify({expr}));\n")
    return js.run_js(src)[0]


_MAT017 = """{
  "yield_deck": null, "stress_unit": "MPa",
  "part_yield_limits": {"1": [
    {"value": 45, "criterion": "von_mises", "source": "MAT_017 SIGY"},
    {"value": 30, "criterion": "max_principal", "source": "MAT_017 FS"}]}}"""


def test_js_picks_the_binding_limit_like_the_analyzer():
    """σvm 만 보면 1.125, FS 까지 보면 0.600 — 분석기와 같은 답이어야 한다."""
    out = _eval(_MAT017,
                "safetyFactor(1, {von_mises: 40, max_principal: 50})")
    import json
    r = json.loads(out)
    assert r["sf"] == pytest.approx(0.600)
    assert r["binding"]["source"] == "MAT_017 FS"
    assert r["complete"] is True


def test_js_flags_incomplete_when_a_measure_is_missing():
    """**놓치는 방향이 위험한 쪽**이라 조용히 빼면 안 된다."""
    import json
    r = json.loads(_eval(_MAT017,
                         "safetyFactor(1, {von_mises: 40, max_principal: null})"))
    assert r["sf"] == pytest.approx(1.125)   # 실제(0.600)보다 크다
    assert r["complete"] is False


def test_js_uses_deck_units_not_raw_mpa():
    """SI 덱: yield_deck 이 3.5e8 Pa 로 와야 한다 — 350 을 쓰면 1e6 배 틀린다."""
    import json
    data = ('{"yield_deck": 3.5e8, "stress_unit": "Pa", "part_yield_limits": {}}')
    r = json.loads(_eval(data, "safetyFactor(7, {von_mises: 2.7e8})"))
    assert 1.0 < r["sf"] < 1.5
    assert _eval(data, "stressUnit()") == '"Pa"'


def test_js_has_no_limits_when_unit_is_unknown():
    """단위를 모르면 화면도 안전율을 내지 않는다 — 분석기와 같은 규칙."""
    data = '{"yield_deck": null, "stress_unit": "", "part_yield_limits": {}}'
    assert _eval(data, "yieldLimits(3).length") == "0"
    import json
    assert json.loads(_eval(data, "safetyFactor(3, {von_mises: 100})"))["sf"] is None


def test_no_raw_yield_stress_left_in_js():
    """`DATA.yield_stress` 를 다시 쓰면 같은 결함이 되살아난다."""
    body = _JS[_JS.index("_JS = r\"\"\"") if "_JS = r\"\"\"" in _JS else 0:]
    uses = [ln.strip() for ln in body.split("\n")
            if "DATA.yield_stress" in ln and not ln.strip().startswith("//")]
    assert not uses, f"JS 가 아직 MPa 원값을 쓴다: {uses[:3]}"
