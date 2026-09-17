# s10 세트 오버레이 표기 회귀 — 응력 단위를 덱에서 읽는지, 자릿수가 값을 뭉개지 않는지
"""s10(SET REPORT) 오버레이의 숫자 표기 규칙.

세트 피크는 metrics.json 의 **덱 단위 그대로**다. SI 덱이면 Pa, ton-mm-s
덱이면 MPa 다. 그러니 단위 문자열은 DATA.unit_labels 에서 와야 하고,
자릿수는 fmt() 가 크기에 맞춰 정해야 한다 — toFixed(2) 는 0.1357 을 0.14 로,
4e-6 을 0.00 으로 뭉갠다.

node 로 실제 JS 를 실행해 확인한다 (node 가 없으면 건너뛴다).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from koo_impact_report.report.assets.js_core import _JS_HEAD  # noqa: E402
from koo_impact_report.report.sections.s10_set import _JS_S10  # noqa: E402

NODE = shutil.which("node")

_HARNESS = r"""
// --- 최소 DOM 스텁 (s10Draw/s10SetImage 가 쓰는 것만) ---
const _nodes = {};
function _node() {
  return { textContent: '', innerHTML: '', src: '', _attr: {},
           setAttribute(k, v) { this._attr[k] = v; } };
}
for (const id of ['s10-img', 's10-info', 's10-ov', 's10-range']) _nodes[id] = _node();
const document = { getElementById: (id) => _nodes[id] || null };

__JS__

s10Draw();
s10SetImage(__PI__);
console.log(JSON.stringify({
  info: _nodes['s10-info'].innerHTML || _nodes['s10-info'].textContent,
  range: _nodes['s10-range'].textContent,
  svg: _nodes['s10-ov'].innerHTML,
}));
"""

_META = {
    "width": 800, "height": 600,
    "origin": [0.0, 0.0, 0.0], "u": [1.0, 0.0, 0.0], "v": [0.0, 1.0, 0.0],
    "half_w": 1.0, "half_h": 1.0,
}


def _run(stress, strain, stress_label, metric="s", pi=0):
    """세트 payload 하나를 만들어 s10 JS 를 node 로 돌린다."""
    data = {
        "parts": [], "faces": [], "results": [], "device_bbox": None,
        "unit_labels": {"acc": "m/s2", "stress": stress_label, "disp": "m",
                        "vel": "m/s", "energy": "J", "time": "s",
                        "mass": "kg", "force": "N"},
        "set_report": {
            "sets": [{"name": "PCB zone", "type": "part", "id": 1, "title": ""}],
            "positions": [{"id": "P1", "mx": 0.0, "my": 0.0},
                          {"id": "P2", "mx": 0.5, "my": 0.5}],
            "stress": [stress],
            "strain": [strain],
            "media": [[{"png": "a.png", "mp4": None},
                       {"png": "b.png", "mp4": None}]],
            "meta": [_META],
            "note": "",
        },
    }
    js = _JS_HEAD.replace("__PAYLOAD__", json.dumps(data)) + _JS_S10
    src = (_HARNESS.replace("__JS__", js).replace("__PI__", str(pi))
           + "\nS10.metric = " + json.dumps(metric) + ";\n")
    # metric 을 바꾼 뒤 다시 그린다 (ε_p 경로 확인용)
    src += "s10Draw();\nconsole.log(JSON.stringify({range: _nodes['s10-range'].textContent, svg: _nodes['s10-ov'].innerHTML}));\n"
    out = subprocess.run([NODE, "-e", src], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    lines = [l for l in out.stdout.strip().splitlines() if l.startswith("{")]
    first = json.loads(lines[0])
    second = json.loads(lines[-1])
    return first, second


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 실행 검증 건너뜀")
def test_stress_unit_comes_from_deck_not_hardcoded_mpa():
    """SI 덱(Pa)에서 'MPa' 라고 적으면 6자리 틀린 값이 된다."""
    first, _ = _run([135691763.0, 1.0e8], [0.0012, 0.0009], "Pa")
    assert " Pa" in first["info"], first["info"]
    assert "MPa" not in first["info"], first["info"]
    assert "Pa" in first["range"] and "MPa" not in first["range"], first["range"]


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 실행 검증 건너뜀")
def test_stress_value_not_truncated_to_two_decimals():
    """ton-mm-s 덱의 0.1357 MPa 가 0.14 로 뭉개지면 안 된다."""
    first, _ = _run([0.135691763, 0.09], [0.0012, 0.0009], "MPa")
    assert "0.1357" in first["info"], first["info"]
    assert "MPa" in first["info"], first["info"]
    assert "0.1357" in first["range"], first["range"]


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 실행 검증 건너뜀")
def test_marker_tooltip_precision_follows_metric():
    """ε_p 마커 툴팁이 0.00123 을 '0.00' 으로 적으면 정보가 사라진다."""
    _, eps = _run([0.135691763, 0.09], [0.00123, 0.0009], "MPa", metric="e")
    assert "P1: 0.00<" not in eps["svg"], eps["svg"]
    assert "0.0012" in eps["svg"], eps["svg"]


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 실행 검증 건너뜀")
def test_missing_value_still_marked_not_zero():
    """미실행 위치는 여전히 '(미실행)' 이고 0 으로 위장하지 않는다."""
    first, _ = _run([0.5, None], [0.01, None], "MPa")
    assert "(미실행)" in first["svg"], first["svg"]


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 실행 검증 건너뜀")
def test_no_unit_label_leaves_stress_bare():
    """단위 미상 덱이면 단위를 지어내지 않는다."""
    first, _ = _run([0.5, 0.2], [0.01, 0.02], "")
    assert "MPa" not in first["info"] and "Pa" not in first["info"], first["info"]


def test_all():
    """진입점 — 이 파일의 시험을 모두 돌린다."""
    if NODE is None:
        pytest.skip("node 없음 — JS 실행 검증 건너뜀")
    test_stress_unit_comes_from_deck_not_hardcoded_mpa()
    test_stress_value_not_truncated_to_two_decimals()
    test_marker_tooltip_precision_follows_metric()
    test_missing_value_still_marked_not_zero()
    test_no_unit_label_leaves_stress_bare()
