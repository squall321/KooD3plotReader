# FFT/SRS 패널이 빈 이유를 사실대로 말하는지 보는 시험
"""시각 축이 깨진 런은 주파수 분석을 내지 않는다. 그건 옳다.

문제는 화면이다. payload 는 `fft.time_issue` 에 사유를 실어 보내지만
sections/assets 어디에서도 읽지 않고, s6 패널은 '분석 가능한 가속도
신호가 없습니다' 라고 쓴다 — 가속도는 992 점씩 있다. SRS 도 같은 이유로
빠졌는데 'no_acc_data_at_position' 이라는 내부 문자열을 그대로 보여준다.

사용자는 모델에 가속도 출력이 없다고 결론 내리고 덱을 고치러 간다.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from koo_impact_report.models import (  # noqa: E402
    ImpactPosition, ImpactReport, PairResult, PartInfo, PartMotion,
)
from koo_impact_report.report.payload.analytics import (  # noqa: E402
    _build_fft_payload, _build_srs_payload,
)
from koo_impact_report.report.assets.js_core import _JS_HEAD  # noqa: E402
from koo_impact_report.report.sections.s6_deep import _JS_S6  # noqa: E402

NODE = shutil.which("node")

TIME_ISSUE = ("motion CSV 시각이 단조증가하지 않는다 — 4/991 구간이 중복"
              "(Time 이 소수 6자리 고정이라 1 µs 미만 간격은 뭉개진다). "
              "주파수 분석(FFT/SRS)은 표본율을 알 수 없어 내보내지 않는다")


def _report_with_time_issue():
    """가속도는 있으나 시각 축이 깨진 런 하나."""
    pos = ImpactPosition(pos_id="P1", face="F1", x=0.0, y=0.0)
    pm = PartMotion(part_id=3)
    pm.times = [i * 1e-6 for i in range(64)]
    pm.acc_mag = [float(i % 7) + 1.0 for i in range(64)]
    pm.time_issue = TIME_ISSUE
    return ImpactReport(
        parts=[PartInfo(part_id=3, part_name="PART_3")],
        positions_by_face={"F1": [pos]},
        results=[PairResult(face="F1", position=pos, part_id=3, peak_g=1000.0)],
        part_motions={("P1", 3): pm},
    )


def test_fft_payload_carries_the_reason():
    """회귀 방지 — 사유는 이미 실린다."""
    out = _build_fft_payload(_report_with_time_issue())
    assert out.get("time_issue"), out
    assert not out["per_part_dominant_freq"], out


def test_srs_reason_is_the_real_cause_not_no_acc_data():
    """가속도는 있다 — '위치에 가속도 없음' 은 거짓이다."""
    srs = _build_srs_payload(_report_with_time_issue())
    assert srs["available"] is False
    assert srs["reason"] != "no_acc_data_at_position", srs
    assert "시각" in srs["reason"], srs


_HARNESS = r"""
class _N {
  constructor(tag) { this.tag = tag; this.children = []; this.style = {}; this._attr = {}; this._t = ''; this._html = ''; }
  setAttribute(k, v) { this._attr[k] = v; }
  getAttribute(k) { return this._attr[k]; }
  addEventListener() {}
  appendChild(c) { this.children.push(c); return c; }
  removeChild(c) { this.children = this.children.filter(x => x !== c); return c; }
  get firstChild() { return this.children.length ? this.children[0] : null; }
  querySelector(sel) { if (!this._q) this._q = {}; if (!this._q[sel]) this._q[sel] = new _N('div'); return this._q[sel]; }
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

__JS__

_deepRenderFFT(__DEEP__);
_deepRenderSRS({ deep_analytics: __DEEP__ });
const fftHost = _node('deep-fft-panel').querySelector('.deep-fft-body');
console.log(JSON.stringify({
  fft: fftHost.textContent,
  srs: _node('deep-srs-body').textContent,
}));
"""


def _render(deep):
    data = {"parts": [], "faces": [], "results": [], "device_bbox": None,
            "unit_labels": {}, "trajectories": {}}
    js = _JS_HEAD.replace("__PAYLOAD__", json.dumps(data)) + _JS_S6
    src = _HARNESS.replace("__JS__", js).replace("__DEEP__", json.dumps(deep))
    out = subprocess.run([NODE, "-e", src], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return json.loads([l for l in out.stdout.strip().splitlines()
                       if l.startswith("{")][-1])


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 실행 검증 건너뜀")
def test_s6_fft_panel_shows_the_reason():
    """'가속도 신호가 없습니다' 는 거짓 — 실린 사유를 보여야 한다."""
    txt = _render({"fft": {"per_part_dominant_freq": {}, "summary": {},
                           "time_issue": TIME_ISSUE},
                   "srs": {"available": False, "reason": TIME_ISSUE}})
    assert "가속도 신호가 없습니다" not in txt["fft"], txt["fft"]
    assert "시각" in txt["fft"], txt["fft"]


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 실행 검증 건너뜀")
def test_s6_srs_panel_shows_the_reason():
    """SRS 도 사유를 보여야 한다."""
    txt = _render({"fft": {"per_part_dominant_freq": {}, "summary": {},
                           "time_issue": TIME_ISSUE},
                   "srs": {"available": False, "reason": TIME_ISSUE}})
    assert "시각" in txt["srs"], txt["srs"]


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 실행 검증 건너뜀")
def test_s6_panels_without_reason_keep_the_old_message():
    """사유가 없으면 종전 문구 그대로 — 없는 사유를 지어내지 않는다."""
    txt = _render({"fft": {"per_part_dominant_freq": {}, "summary": {}},
                   "srs": {"available": False}})
    assert "가속도" in txt["fft"], txt["fft"]
    assert "가속도" in txt["srs"], txt["srs"]


def test_all():
    """진입점 — 이 파일의 시험을 모두 돌린다."""
    test_fft_payload_carries_the_reason()
    test_srs_reason_is_the_real_cause_not_no_acc_data()
    if NODE is None:
        pytest.skip("node 없음 — JS 실행 검증 건너뜀")
    test_s6_fft_panel_shows_the_reason()
    test_s6_srs_panel_shows_the_reason()
    test_s6_panels_without_reason_keep_the_old_message()
