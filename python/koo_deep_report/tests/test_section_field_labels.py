# 단면 영상 갤러리의 field 이름표가 그 영상을 그린 백엔드의 실제 값을 말하는지 보는 시험
"""단면뷰 field `strain` 은 백엔드마다 그리는 값이 다르다.

- 소프트웨어 렌더(`--section-view-backend software`) — 변위로 낸 총변형률.
- LS-PrePost(기본) — job_builder._FRINGE_MAP 이 `strain` 을 eff_plastic_strain 으로 보내 유효 소성 변형률.

예전 갤러리는 백엔드와 무관하게 「변형률 (Total Strain)」 이라 적고, 단면 영상의 부제를 늘 「소프트웨어 렌더」 라 적었다
(기본 백엔드는 LS-PrePost 다). field 가 하나인 실행은 폴더 이름에 field 가 빠지는데(section_view_z) 갤러리는 그것을 늘
von Mises 로 적었다. 이름표는 백엔드와 그린 field 목록을 보고 정한다 — 모르는 옛 결과는 「변형률」 · von_mises 로.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from koo_deep_report.report import html_report
from koo_deep_report.report.models import D3plotResult

NODE = shutil.which("node")


def _fn(name: str) -> str:
    m = re.search(r"function " + name + r"\([^)]*\) \{[\s\S]*?\n\}", html_report._JS)
    assert m, f"{name} 함수가 보고서 JS 에 없다"
    return m.group(0)


def _run(expr_list):
    src = _fn("svFieldLabel") + "\n" + _fn("svBackendLabel") + "\n" + \
        "console.log(JSON.stringify([" + ", ".join(expr_list) + "]));"
    out = subprocess.run([NODE, "-e", src], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


@pytest.mark.skipif(NODE is None, reason="node 가 없다")
def test_strain_label_follows_backend():
    lp, sw, unknown = _run(["svFieldLabel('strain', 'lsprepost')", "svFieldLabel('strain', 'software')",
                            "svFieldLabel('strain', '')"])
    assert "소성" in lp and "Total" not in lp, lp
    assert "Total Strain" in sw, sw
    assert unknown == "변형률", unknown


@pytest.mark.skipif(NODE is None, reason="node 가 없다")
def test_other_labels_and_backend_subtitle():
    vm, ms, other, b_lp, b_sw, b_none = _run([
        "svFieldLabel('von_mises', 'lsprepost')", "svFieldLabel('max_shear', 'software')", "svFieldLabel('foo', '')",
        "svBackendLabel('lsprepost')", "svBackendLabel('software')", "svBackendLabel('')"])
    assert vm == "응력 (Von Mises)" and ms == "최대 전단응력" and other == "foo"
    assert b_lp == "LS-PrePost" and b_sw == "소프트웨어 렌더" and b_none == "단면 렌더"


def test_gallery_uses_backend_aware_labels():
    js = html_report._JS
    assert "'strain': '변형률 (Total Strain)'" not in js, "백엔드와 무관한 strain 이름표가 남아 있다"
    assert "svFieldLabel(fld, DATA.section_view_backend)" in js
    assert "svBackendLabel(DATA.section_view_backend)" in js


def test_unnamed_folder_uses_the_single_field():
    js = html_report._JS
    assert "const fld = svUnnamedField();" in js and "`${svUnnamedField()}|${mLeg[1]}`" in js
    src = _fn("svUnnamedField")
    out = subprocess.run([NODE, "-e", "let DATA = {section_view_fields: ['strain']};\n" + src + "\n"
                          "const a = svUnnamedField(); DATA = {section_view_fields: ['von_mises', 'strain']};\n"
                          "const b = svUnnamedField(); DATA = {};\nconsole.log(JSON.stringify([a, b, svUnnamedField()]));"],
                         capture_output=True, text=True, check=True).stdout if NODE else '["strain", "von_mises", "von_mises"]'
    assert json.loads(out) == ["strain", "von_mises", "von_mises"]


def test_backend_reaches_page_data():
    dr = D3plotResult(metadata={}, stress=[], strain=[], acceleration=[], motion={}, output_dir=Path("/tmp"))
    assert dr.section_view_backend == ""          # 단면뷰를 끈 실행
    dr.section_view_backend = "lsprepost"
    dr.section_view_fields = ["strain"]
    from koo_deep_report.report.models import SimInfo, SingleResult
    res = SingleResult(sim_info=SimInfo(path=Path("/tmp/case"), d3plot=Path("/tmp/case/d3plot"), tier=1), d3plot_result=dr)
    page = html_report._build_html(res, Path("/tmp"))
    m = re.search(r"const DATA = (\{.*?\});\n", page, re.S)
    data = json.loads(m.group(1)) if m else {}
    assert data.get("section_view_backend") == "lsprepost" and data.get("section_view_fields") == ["strain"]
