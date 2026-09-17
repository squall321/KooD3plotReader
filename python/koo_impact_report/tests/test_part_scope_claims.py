# 부품 범위 표기 회귀 — 상위 N개만 보고 "전 부품" 이라 말하지 않는지
"""상관 네트워크와 손상지수(DI) 는 부품을 잘라 쓴다.

상관 행렬은 평균 peak_g 상위 12개만 계산하고, DI 는 상위 15개만 payload 에
싣는다. 그 자체는 화면 크기 때문에 필요한 일이지만, 계산에 들어가지도 않은
부품을 두고 "모든 부품이 독립적 응답" 이라 말하면 거짓이 된다. 잘랐다는
사실이 payload 와 화면에 남아 있어야 한다.

DI 의 max_peak_strain 은 소수 5자리 반올림이라 4.38e-06 이 0.0 으로 사라졌다 —
유효숫자로 적어야 한다.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from koo_impact_report.report.payload.doe import (  # noqa: E402
    _build_corr_network_payload,
)
from koo_impact_report.report.payload.insights import (  # noqa: E402
    _build_damage_index,
)
from koo_impact_report.report.assets.js_core import _JS_HEAD  # noqa: E402
from koo_impact_report.report.sections.s5_doe import (  # noqa: E402
    _JS_S5_DOE, _JS_TRAJ,
)

NODE = shutil.which("node")


class _Pos:
    def __init__(self, pos_id):
        self.pos_id = pos_id


class _Part:
    def __init__(self, pid):
        self.part_id = pid
        self.part_name = f"PART_{pid}"
        self.group = None


class _Res:
    def __init__(self, pid, pos, g, s=0.0, e=0.0):
        self.part_id, self.position = pid, pos
        self.peak_g, self.peak_stress, self.peak_strain = g, s, e


class _Rep:
    def __init__(self, parts, results):
        self.parts, self.results = parts, results
        self.sim_params = None


def _make_report(n_parts, n_pos=6):
    """부품마다 기울기가 다른 응답 — 상관이 1 이 되지 않도록 흔든다."""
    parts = [_Part(i + 1) for i in range(n_parts)]
    positions = [_Pos(f"P{k}") for k in range(n_pos)]
    results = []
    for i, p in enumerate(parts):
        for k, pos in enumerate(positions):
            g = 100.0 * (n_parts - i) + ((k * (i + 1)) % 5) * 7.0
            results.append(_Res(p.part_id, pos, g, s=g * 2.0, e=4.38e-06 * (i + 1)))
    return _Rep(parts, results)


# ---------------------------------------------------------------------------
# payload 계약
# ---------------------------------------------------------------------------

def test_corr_payload_reports_how_many_parts_were_left_out():
    """상위 12개만 평가했다면 후보가 몇이었는지 payload 에 남아야 한다."""
    out = _build_corr_network_payload(_make_report(25))
    assert out["max_parts"] == 12
    assert out["n_parts_total"] == 25, out.get("n_parts_total")


def test_corr_payload_scope_present_even_when_empty():
    """데이터가 없는 조기 반환에도 같은 키가 있어야 소비자가 분기하지 않는다."""
    empty = _build_corr_network_payload(_Rep([], []))
    assert "n_parts_total" in empty and empty["n_parts_total"] == 0


def test_damage_index_keeps_tiny_strain():
    """4.38e-06 을 소수 5자리로 반올림하면 0.0 이 되어 '변형 없음' 으로 읽힌다."""
    di = _build_damage_index(_make_report(3))
    strains = [r["max_peak_strain"] for r in di["per_part"]]
    assert all(v > 0.0 for v in strains), strains


def test_damage_index_reports_listed_count():
    """DI 는 상위 15개만 싣는다 — 몇 개를 실었는지 요약에 남아야 한다."""
    di = _build_damage_index(_make_report(25))
    assert len(di["per_part"]) == 15
    assert di["summary"]["n_parts_listed"] == 15, di["summary"]
    assert di["summary"]["n_parts_with_data"] == 25


# ---------------------------------------------------------------------------
# 화면 문구 (node 로 실제 JS 실행)
# ---------------------------------------------------------------------------

_HARNESS = r"""
class _N {
  constructor(tag) { this.tag = tag; this.children = []; this.style = {}; this._attr = {}; this._t = ''; this._html = ''; }
  setAttribute(k, v) { this._attr[k] = v; }
  getAttribute(k) { return this._attr[k]; }
  addEventListener() {}
  appendChild(c) { this.children.push(c); return c; }
  querySelector() { return null; }
  set textContent(v) { this._t = String(v); this.children = []; }
  get textContent() { return this._t + this.children.map(c => c.textContent).join(''); }
  set innerHTML(v) { this._html = String(v); this._t = ''; this.children = []; }
  get innerHTML() { return this._html; }
}
const _nodes = { 'doe-corr-network': new _N('div') };
const document = {
  createElement: (t) => new _N(t),
  createElementNS: (ns, t) => new _N(t),
  createTextNode: (t) => { const n = new _N('#text'); n._t = String(t); return n; },
  getElementById: (id) => _nodes[id] || null,
};

__JS__

_doeRenderCorrNetwork({ advanced: { corr_network: __CORR__ } });
console.log(JSON.stringify({ text: _nodes['doe-corr-network'].textContent }));
"""


def _render_corr(corr):
    data = {"parts": [], "faces": [], "results": [], "device_bbox": None,
            "unit_labels": {}, "trajectories": {},
            "clusters": {"n": 0, "labels": {}, "archetypes": []}}
    js = _JS_HEAD.replace("__PAYLOAD__", json.dumps(data)) + _JS_TRAJ + _JS_S5_DOE
    src = (_HARNESS.replace("__JS__", js)
           .replace("__CORR__", json.dumps(corr)))
    out = subprocess.run([NODE, "-e", src], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    line = [l for l in out.stdout.strip().splitlines() if l.startswith("{")][-1]
    return json.loads(line)["text"]


def _corr_payload(n_eval, n_total):
    pids = list(range(1, n_eval + 1))
    return {
        "corr_matrix": {str(a): {str(b): (1.0 if a == b else 0.0) for b in pids}
                        for a in pids},
        "corr_threshold": 0.7,
        "clusters": [{"cluster_id": i, "members": [p], "member_names": [f"PART_{p}"],
                      "mean_r": 1.0, "size": 1} for i, p in enumerate(pids)],
        "parts_listed": [{"part_id": p, "part_name": f"PART_{p}", "group": None,
                          "group_idx": -1, "mean_peak_g": 100.0} for p in pids],
        "n_positions": 6,
        "max_parts": n_eval,
        "n_parts_total": n_total,
    }


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 실행 검증 건너뜀")
def test_no_cluster_message_states_evaluated_scope():
    """25개 중 12개만 봤으면서 '모든 부품' 이라 말하면 안 된다."""
    text = _render_corr(_corr_payload(12, 25))
    assert "모든 부품이 독립적 응답" not in text, text
    assert "12" in text and "25" in text, text


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 실행 검증 건너뜀")
def test_no_cluster_message_when_every_part_evaluated():
    """전부 평가했으면 범위를 덧붙이되 사실은 그대로다."""
    text = _render_corr(_corr_payload(5, 5))
    assert "강한 상관" in text, text
    assert "5" in text, text


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 실행 검증 건너뜀")
def test_old_payload_without_scope_key_still_scoped():
    """키가 없던 옛 payload(JSON 재렌더)도 '모든 부품' 이라 말하면 안 된다."""
    corr = _corr_payload(12, 25)
    del corr["n_parts_total"]
    text = _render_corr(corr)
    assert "모든 부품이 독립적 응답" not in text, text
    assert "12" in text, text


def test_all():
    """진입점 — 이 파일의 시험을 모두 돌린다."""
    test_corr_payload_reports_how_many_parts_were_left_out()
    test_corr_payload_scope_present_even_when_empty()
    test_damage_index_keeps_tiny_strain()
    test_damage_index_reports_listed_count()
    if NODE is None:
        pytest.skip("node 없음 — JS 실행 검증 건너뜀")
    test_no_cluster_message_states_evaluated_scope()
    test_no_cluster_message_when_every_part_evaluated()
    test_old_payload_without_scope_key_still_scoped()
