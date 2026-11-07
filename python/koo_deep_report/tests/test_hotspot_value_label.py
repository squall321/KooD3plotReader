# 핫스팟 색 척도 'stress' 의 이름표가 기준을 따르는지(소성 기준이면 응력이라 부르지 않는지) node 로 검증하는 시험
"""deep 리포트 핫스팟 탭의 첫 색 척도는 군집의 stress_max 다. 소성 기준(plastic_strain · plastic_work,
2026-11-07)에서는 그 값이 ε_p · w_p 인데 이름표가 '응력 피크 [MPa]' 로 남으면 색 막대 · 툴팁 · 선택지가
모두 틀린 단위를 말한다. 실제 함수 원문을 뽑아 node 로 돌린다. node 가 없으면 건너뛴다.
"""
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from koo_deep_report.report import html_report

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node 없음")


def _src() -> str:
    js = html_report._JS
    metrics = re.search(r"const HS_METRICS = \[[\s\S]*?\n\];", js).group(0)
    label = re.search(r"function hsValueLabel\(crit\) \{[\s\S]*?\n\}", js).group(0)
    mdef = re.search(r"function hsMetricDef\(code\) \{[\s\S]*?\n\}", js).group(0)
    return "const U_S = 'MPa';\nlet _hsState = {crit: null};\n" + metrics + "\n" + label + "\n" + mdef + "\n"


def _labels(crits: list[str], code: str) -> list[str]:
    body = (f"console.log(JSON.stringify({json.dumps(crits)}.map(c => "
            f"{{ _hsState.crit = c; return hsMetricDef('{code}')[1]; }})));\n")
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "lab.js"
        f.write_text(_src() + body, encoding="utf-8")
        r = subprocess.run([NODE, str(f)], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_stress_metric_label_follows_criterion():
    vm, s1, ep, wp = _labels(["von_mises", "max_principal", "plastic_strain", "plastic_work"], "stress")
    assert vm == s1 == "응력 피크 [MPa]"
    assert ep == "ε_p 피크 [-]"
    assert wp.startswith("w_p 피크 [MPa")


def test_other_metrics_keep_their_labels():
    assert _labels(["plastic_strain"], "energy_density") == ["소성일 밀도 [mJ/mm³]"]
