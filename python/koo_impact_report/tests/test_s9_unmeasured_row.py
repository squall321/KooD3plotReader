# s9 위치별 부품표와 s3 면 P95 가 미계측(null)을 0 으로 찍지 않는지 검증
"""payload 는 재지 못한 peak_g/peak_stress 를 null 로 내보낸다.

그런데 s9 의 per-part 테이블은 `r.g || 0` 로 그 null 을 0 으로 접어 '0 G ·
0% · 0.0' 행을 만든다. 같은 행의 변형률만 '—' 로 제대로 표시된다. 그 결과
미계측 부품이 그 위치에서 가장 안전한 행으로 읽힌다.

s3 의 면 KPI 도 `rows.map(r => r.g).sort((a,b) => a-b)` 로 null 을 0 처럼
정렬해 P95 표본에 섞는다.

node 로 실제 JS 를 돌려 값으로 확인한다.
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
from koo_impact_report.report.sections.s9_position import _JS_S9  # noqa: E402
from koo_impact_report.report.sections.s3_verdict import _JS_S3  # noqa: E402

NODE = shutil.which("node")

_DOM = r"""
class _N {
  constructor(tag) { this.tag = tag; this.children = []; this.style = {}; this._attr = {}; this._t = ''; this._html = ''; this.classList = { toggle() {}, add() {} }; }
  setAttribute(k, v) { this._attr[k] = v; }
  getAttribute(k) { return this._attr[k]; }
  addEventListener() {}
  appendChild(c) { this.children.push(c); return c; }
  removeChild(c) { this.children = this.children.filter(x => x !== c); return c; }
  get firstChild() { return this.children.length ? this.children[0] : null; }
  querySelector() { return null; }
  querySelectorAll() { return []; }
  set textContent(v) { this._t = String(v); this.children = []; }
  get textContent() { return this._t + this.children.map(c => c.textContent).join(''); }
  set innerHTML(v) { this._html = String(v); this._t = ''; this.children = []; }
  get innerHTML() { return this._html; }
}
const _nodes = {};
function _node(id) { if (!_nodes[id]) _nodes[id] = new _N('div'); return _nodes[id]; }
const document = {
  createElement: (t) => new _N(t),
  createElementNS: (ns, t) => new _N(t),
  createTextNode: (t) => { const n = new _N('#text'); n._t = String(t); return n; },
  getElementById: (id) => _node(id),
  querySelector: (sel) => _node(sel),
  querySelectorAll: () => [],
};
const window = {};
"""

_S9_HARNESS = _DOM + r"""
__JS__

renderS9Static('P1');
const tb = _node('#s9-part-tbl tbody');
const rows = tb.children.map(tr => ({
  cells: tr.children.map(td => td.textContent),
  barW: (tr.children[3] && tr.children[3].children[0]) ? tr.children[3].children[0].style.width : null,
  klass: tr._attr['class'] || '',
}));
console.log(JSON.stringify({ rows: rows }));
"""

_S3_HARNESS = _DOM + r"""
__JS__

initFaceKpiTable();
const tb = _node('#face-kpi-tbl tbody');
console.log(JSON.stringify({
  rows: tb.children.map(tr => tr.children.map(td => td.textContent)),
}));
"""


def _payload(results):
    parts = sorted({r["part_id"] for r in results})
    return {
        "parts": [{"id": p, "name": f"PART_{p}"} for p in parts],
        "faces": [{"code": "F5", "name": "BOTTOM"}],
        "results": results,
        "positions": [{"pos_id": "P1", "x": 0.0, "y": 0.0}],
        "device_bbox": None,
        "unit_labels": {"acc": "mm/s^2", "stress": "MPa", "disp": "mm"},
        "trajectories": {},
        "part_motion": {"g_divisor": 9810.0, "series": []},
        "kpi": {"crit_threshold": 100000.0, "warn_threshold": 50000.0},
        "doe_analysis": {
            "position_metrics": {
                "P1": {"peak_g_max": 200000.0, "worst_part_id_g": 1,
                       "peak_stress_max": 400.0, "worst_part_id_s": 1},
            },
            "trajectory_summary": {},
            "advanced": {},
        },
        "solver_quality": None,
    }


def _res(pid, g, s, e):
    return {"part_id": pid, "part_name": f"PART_{pid}", "pos_id": "P1",
            "face": "F5", "x": 0.0, "y": 0.0, "g": g, "s": s, "e": e, "d": 0.0}


def _run_s9(results):
    data = _payload(results)
    js = _JS_HEAD.replace("__PAYLOAD__", json.dumps(data)) + _JS_S9
    src = _S9_HARNESS.replace("__JS__", js)
    out = subprocess.run([NODE, "-e", src], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    line = [l for l in out.stdout.strip().splitlines() if l.startswith("{")][-1]
    return json.loads(line)["rows"]


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 실행 검증 건너뜀")
def test_s9_unmeasured_part_row_is_not_printed_as_zero():
    """g=null 부품 행에 '0' 이 아니라 결측 표시가 와야 한다."""
    rows = _run_s9([
        _res(1, 200000.0, 400.0, 1.2e-3),
        _res(23, None, None, None),   # motion CSV 없는 *SECTION_BEAM
    ])
    assert len(rows) == 2, rows
    unm = [r for r in rows if "PART_23" in r["cells"][1]][0]
    g_cell, pct_cell, s_cell = unm["cells"][2], unm["cells"][4], unm["cells"][5]
    assert g_cell.strip() not in ("0", "0.0"), f"g 칸이 0 으로 찍혔다: {unm}"
    assert pct_cell.strip() != "0%", f"퍼센트 칸이 0% 로 찍혔다: {unm}"
    assert s_cell.strip() not in ("0.0", "0"), f"응력 칸이 0.0 으로 찍혔다: {unm}"
    assert unm["barW"] in (None, "0px"), f"미계측인데 막대를 그렸다: {unm}"
    assert unm["klass"] == "r-dim", unm
    assert "미계측" in unm["cells"][8], f"배지 칸이 비어 '안전' 으로 읽힌다: {unm}"


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 실행 검증 건너뜀")
def test_s9_measured_part_row_unchanged():
    """계측된 행은 종전 그대로 값과 막대를 가진다."""
    rows = _run_s9([
        _res(1, 200000.0, 400.0, 1.2e-3),
        _res(23, None, None, None),
    ])
    m = [r for r in rows if "PART_1" in r["cells"][1] and "PART_23" not in r["cells"][1]][0]
    assert m["cells"][2].strip() == "20", m
    assert m["cells"][4].strip() == "100%", m
    assert m["barW"] == "70px", m


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 실행 검증 건너뜀")
def test_s9_real_zero_still_shows_zero():
    """진짜 0 은 여전히 0 으로 나온다 — 결측과 구분한다."""
    rows = _run_s9([
        _res(1, 200000.0, 400.0, 1.2e-3),
        _res(7, 0.0, 0.0, 0.0),
    ])
    z = [r for r in rows if "PART_7" in r["cells"][1]][0]
    assert z["cells"][2].strip() == "0", z
    assert z["cells"][4].strip() == "0%", z


def _run_s3_score(gvals):
    """면 위험점수를 JS 로 실제 계산시켜 돌려받는다 (P95 가 들어간다)."""
    results = [_res(i + 1, g, 0.0, 0.0) for i, g in enumerate(gvals)]
    data = _payload(results)
    data["risk_score"] = {"weights": {"worst": 0.5, "p95": 0.4, "crit": 0.1},
                          "crit_band": 8.0, "warn_band": 5.0}
    data["kpi"]["crit_threshold"] = 1500.0
    js = _JS_HEAD.replace("__PAYLOAD__", json.dumps(data)) + _JS_S3
    src = _S3_HARNESS.replace("__JS__", js)
    out = subprocess.run([NODE, "-e", src], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    rows = json.loads([l for l in out.stdout.strip().splitlines()
                       if l.startswith("{")][-1])["rows"]
    assert len(rows) == 1, rows
    return float(rows[0][5].split("/")[0].strip())


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 실행 검증 건너뜀")
def test_s3_face_score_excludes_unmeasured():
    """null 이 0 으로 정렬돼 P95 표본에 끼면 면 점수가 내려간다."""
    measured = [float(100 * (i + 1)) for i in range(20)]
    base = _run_s3_score(measured)
    withnull = _run_s3_score(measured + [None] * 10)
    assert base == withnull, (base, withnull)


def test_all():
    """진입점 — 이 파일의 시험을 모두 돌린다."""
    if NODE is None:
        pytest.skip("node 없음 — JS 실행 검증 건너뜀")
    test_s9_unmeasured_part_row_is_not_printed_as_zero()
    test_s9_measured_part_row_unchanged()
    test_s9_real_zero_still_shows_zero()
    test_s3_face_score_excludes_unmeasured()
