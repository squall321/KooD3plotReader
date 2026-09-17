# 접촉 타임라인이 짧은 펄스를 실제로 잡는지 값으로 확인하는 시험
"""옛 시험은 생성된 HTML 에 어떤 문자열이 있는지만 봤다.

커밋 14e7e00 이 고쳤다고 주장한 실제 동작 — '칸이 덮는 시간 구간 안에
접촉 샘플이 하나라도 있으면 접촉' 이라 record/20 보다 짧은 40 µs 펄스를
놓치지 않는다 — 은 한 번도 실행되지 않았다. 누가 JS 를 점 샘플링으로
되돌려도 tEnd 표현식 문자열만 남아 있으면 통과한다.

여기서는 node 로 `initContactTimeline()` 을 실제로 돌려 칸 값을 단언하고,
그 칸에 들어갈 접촉 샘플이 payload 다운샘플에서 살아남는지도 본다.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from koo_impact_report.report.assets.js_core import _JS_HEAD  # noqa: E402
from koo_impact_report.report.sections.s5_doe import (  # noqa: E402
    _JS_TRAJ, _JS_S5_DOE,
)
from koo_impact_report.report.payload.common import (  # noqa: E402
    _downsample_indices,
)

NODE = shutil.which("node")

_HARNESS = r"""
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
  querySelector: () => null,
  querySelectorAll: () => [],
};
const window = {};

__JS__

initContactTimeline();
const grid = _node('cseq-grid');
// 행 구성: [IMPACT 라벨][헤더행][t 라벨][빈 행] 그다음 (라벨, 셀행) 쌍.
const rows = grid.children.filter(n => (n._attr['class'] || '') === 'cseq-row');
const cells = rows[rows.length - 1].children.map(c => (c.title || ''));
console.log(JSON.stringify({
  contact: cells.map(t => t.indexOf('CONTACT') >= 0),
  titles: cells,
}));
"""


def _run(traj, unit_labels=None):
    data = {
        "parts": [], "faces": [{"code": "F1", "name": "BOTTOM"}],
        "results": [{"part_id": 1, "part_name": "P1", "pos_id": "P1",
                     "face": "F1", "x": 0.0, "y": 0.0, "g": 100.0}],
        "device_bbox": None,
        "unit_labels": unit_labels or {"time": "s"},
        "trajectories": {"P1": traj},
        "clusters": {"n": 0, "labels": {}, "archetypes": []},
    }
    js = _JS_HEAD.replace("__PAYLOAD__", json.dumps(data)) + _JS_TRAJ + _JS_S5_DOE
    # 992 점 궤적은 `node -e` 인자 한도를 넘는다 — 스크립트를 파일로 넘긴다.
    tmp = Path(tempfile.mkdtemp(prefix="koo_cseq_"))
    try:
        script = tmp / "harness.js"
        script.write_text(_HARNESS.replace("__JS__", js), encoding="utf-8")
        out = subprocess.run([NODE, str(script)], capture_output=True, text=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    assert out.returncode == 0, out.stderr
    return json.loads([l for l in out.stdout.strip().splitlines()
                       if l.startswith("{")][-1])


def _traj(times, contact):
    return {"face": "F1", "x": 0.0, "y": 0.0, "behavior": "bounce",
            "t": times, "contact": contact,
            "ke": [1.0] * len(times), "init_ke": 1.0,
            "t_first_contact": None}


def _pulse(n=992, t_end=1.0e-3, t_lo=4.0e-4, t_hi=4.4e-4):
    """1 ms 기록 안의 40 µs 접촉 펄스."""
    times = [i * t_end / (n - 1) for i in range(n)]
    contact = [t_lo <= t < t_hi for t in times]
    return times, contact


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 실행 검증 건너뜀")
def test_short_pulse_paints_its_cell():
    """1 ms 기록의 40 µs 펄스 — 칸 폭(50 µs)보다 짧아도 잡아야 한다."""
    times, contact = _pulse()
    got = _run(_traj(times, contact))["contact"]
    assert len(got) == 21, got
    # 펄스 400–440 µs 는 칸 8 (400–450 µs) 안에 있다.
    assert got[8] is True, got
    assert sum(1 for v in got if v) == 1, got


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 실행 검증 건너뜀")
def test_contact_lands_in_the_right_cell_for_a_2ms_deck():
    """tFinal 2 ms 덱의 1.5 ms 접촉은 칸 15 다 (0~1 ms 하드코딩 회귀 방지)."""
    n = 401
    times = [i * 2.0e-3 / (n - 1) for i in range(n)]
    contact = [1.5e-3 <= t < 1.6e-3 for t in times]
    got = _run(_traj(times, contact))["contact"]
    assert got[15] is True, got
    assert got[8] is False, got


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 실행 검증 건너뜀")
def test_no_contact_row_stays_empty():
    """접촉이 없으면 어떤 칸도 CONTACT 가 되면 안 된다."""
    times, _ = _pulse()
    got = _run(_traj(times, [False] * len(times)))["contact"]
    assert not any(got), got


def _edges(contact):
    """payload 가 보존 대상으로 넘기는 접촉 on/off 전이 인덱스."""
    n = len(contact)
    return [i for i in range(n)
            if contact[i] and (i == 0 or not contact[i - 1]
                               or i + 1 >= n or not contact[i + 1])]


def test_stride_alone_loses_short_pulses():
    """기준선 — 스트라이드만으로는 20 µs 펄스가 절반 확률로 사라진다."""
    n = 992
    lost = 0
    for start in range(0, 900, 7):
        contact = [start <= i < start + 20 for i in range(n)]
        idx = _downsample_indices(n, 24)
        if not any(contact[i] for i in idx):
            lost += 1
    assert lost > 0, "이 시험의 전제(스트라이드가 펄스를 놓친다)가 깨졌다"


def test_downsample_keeps_the_short_pulse():
    """payload 다운샘플(tier D: 24점)이 펄스를 통째로 버리면 JS 가 살릴 수 없다."""
    n = 992
    for start in range(0, 900, 7):
        contact = [start <= i < start + 20 for i in range(n)]
        idx = _downsample_indices(n, 24, keep_idx=_edges(contact))
        assert any(contact[i] for i in idx), \
            f"24점 스트라이드가 20 µs 펄스를 통째로 버렸다 (start={start})"


def test_downsample_edge_preservation_is_bounded():
    """채터링 런이 다운샘플을 무력화하면 안 된다 — 호출부가 상한을 둔다."""
    from koo_impact_report.report.payload import _CONTACT_EDGE_CAP
    n = 992
    contact = [(i // 2) % 2 == 0 for i in range(n)]   # 2 샘플마다 토글
    edges = _edges(contact)
    assert len(edges) > _CONTACT_EDGE_CAP, len(edges)
    capped = edges[::-(-len(edges) // _CONTACT_EDGE_CAP)]
    assert len(capped) <= _CONTACT_EDGE_CAP, len(capped)
    idx = _downsample_indices(n, 24, keep_idx=capped)
    assert len(idx) <= 24 + _CONTACT_EDGE_CAP + 2, len(idx)


def test_all():
    """진입점 — 이 파일의 시험을 모두 돌린다."""
    test_stride_alone_loses_short_pulses()
    test_downsample_keeps_the_short_pulse()
    test_downsample_edge_preservation_is_bounded()
    if NODE is None:
        pytest.skip("node 없음 — JS 실행 검증 건너뜀")
    test_short_pulse_paints_its_cell()
    test_contact_lands_in_the_right_cell_for_a_2ms_deck()
    test_no_contact_row_stays_empty()
