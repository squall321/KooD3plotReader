# 파트에 없는 시계열(변형률 · 주응력 · 주변형률 · 속도 · 가속도)을 측정된 0 으로 보고하지 않는지 보는 시험
"""_aggregate 는 응력 이력이 없는 파트의 피크 응력을 None + 사유로 두지만, 같은 파트의 변형률 · 주응력 · 주변형률과
motion 이 없는 파트의 속도 · 가속도는 0.0 으로 채웠다. 운동만 있는 파트(DynaAnalysis 덱 파트 2 — 응력 · 변형률 이력 없음)는
보고서 상세 카드에 「피크 변형률 0 · σ₁ 0 · σ₃ 0」 이 찍히고 result.json 에 "peak_strain": 0 이 실려, 소비처가
「소성 변형률 0 으로 측정됐다」 로 읽었다. 없는 값은 None(result.json 은 null)이다.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from koo_deep_report.__main__ import _aggregate, _print_summary
from koo_deep_report.core.d3plot_reader import _parse_series
from koo_deep_report.report import html_report
from koo_deep_report.report.models import D3plotResult, MotionData, SimInfo

NODE = shutil.which("node")


def _series(pid, quantity, lo, hi):
    return _parse_series({
        "part_id": pid, "quantity": quantity, "unit": "MPa", "num_points": 2,
        "global_max": hi, "global_min": lo, "time_of_max": 1.0,
        "data": [{"time": 0.0, "max": 0.0, "min": 0.0, "avg": 0.0, "max_element_id": 1},
                 {"time": 1.0, "max": hi, "min": lo, "avg": hi / 2, "max_element_id": 7}],
    })


def _result(strain=True):
    """파트 1 — 다 있다. 파트 2 — 운동만(속도 · 가속도 열 없음). 파트 3 — 응력만(motion 없음)."""
    dr = D3plotResult(
        metadata={"num_states": 2, "end_time": 1.0, "analyzed_parts": [1, 2, 3]},
        stress=[_series(1, "von_mises", 0.0, 300.0), _series(3, "von_mises", 0.0, 200.0)],
        strain=[_series(1, "eff_plastic_strain", 0.0, 0.01)] if strain else [],
        acceleration=[],
        motion={
            1: MotionData(1, t=[0.0, 1.0], max_disp_mag=[0.0, 1.5], vel_mag=[0.0, 2.0], acc_mag=[0.0, 9.0]),
            2: MotionData(2, part_name="MOTIONONLY", t=[0.0, 1.0], max_disp_mag=[0.0, 0.5]),
        },
        max_principal=[_series(1, "max_principal", 0.0, 250.0)],
        min_principal=[_series(1, "min_principal", -120.0, 0.0)],
        output_dir=Path("/tmp"),
    )
    si = SimInfo(path=Path("/tmp/case"), d3plot=Path("/tmp/case/d3plot"), tier=1)
    return _aggregate(si, dr, None, 0.0, "case")


ABSENT = ("peak_strain", "peak_max_principal", "peak_min_principal",
          "peak_max_principal_strain", "peak_min_principal_strain", "peak_vel_mag", "peak_acc_mag")


def test_absent_series_are_none_not_zero():
    res = _result()
    p1, p2, p3 = res.parts[1], res.parts[2], res.parts[3]
    assert (p1.peak_strain, p1.peak_max_principal, p1.peak_min_principal) == (0.01, 250.0, -120.0)
    assert (p1.peak_vel_mag, p1.peak_acc_mag) == (2.0, 9.0)
    for f in ABSENT:
        assert getattr(p2, f) is None, f"운동만 있는 파트의 {f} 는 0 이 아니라 값 없음"
    assert p2.peak_disp_mag == 0.5
    for f in ("peak_strain", "peak_max_principal", "peak_min_principal", "peak_vel_mag", "peak_acc_mag"):
        assert getattr(p3, f) is None, f"응력만 있는 파트의 {f} 는 0 이 아니라 값 없음"
    assert p3.strain_ratio is None and p3.strain_warning == "none"
    assert res.peak_strain_global == 0.01


def test_no_strain_series_anywhere_global_is_none():
    res = _result(strain=False)
    assert all(p.peak_strain is None for p in res.parts.values())
    assert res.peak_strain_global is None, "변형률 이력이 하나도 없으면 전체 최대도 값 없음"


def test_result_json_writes_null(capsys):
    res = _result()
    d = json.loads(json.dumps(res.to_compare_dict()))
    assert d["parts"]["2"]["peak_strain"] is None and d["parts"]["2"]["peak_acc_mag"] is None
    assert d["parts"]["1"]["peak_strain"] == 0.01 and d["parts"]["1"]["peak_acc_mag"] == 9.0
    _print_summary(_result(strain=False))       # None 을 서식에 넣다 터지지 않는다
    assert "피크 변형률  : 미산출" in capsys.readouterr().out


def _page_js(res) -> str:
    page = html_report._build_html(res, Path("/tmp"))
    return next(s for s in re.findall(r"<script>([\s\S]*?)</script>", page) if "function renderStress" in s)


STUB = """
const noop = new Proxy(function(){}, {get: (t, p) => p === Symbol.toPrimitive ? () => '' : (p === 'length' ? 0 : noop), apply: () => noop});
const rec = {};
const el = id => id === 'dd-part-sel' ? {value: SEL} : (rec[id] = rec[id] || new Proxy({}, {get: (o, k) => k in o ? o[k] : noop, set: (o, k, v) => { o[k] = v; return true; }}));
globalThis.document = new Proxy({}, {get: (t, p) => p === 'getElementById' ? el : noop});
globalThis.window = noop; globalThis.localStorage = noop; globalThis.addEventListener = noop;
globalThis.IntersectionObserver = function(){ return noop; }; globalThis.ResizeObserver = function(){ return noop; };
globalThis.MutationObserver = function(){ return noop; };
globalThis.Plotly = noop; globalThis.requestAnimationFrame = noop; globalThis.setTimeout = noop;
"""


def _run_node(res, sel, tail):
    src = f"const SEL = '{sel}';\n" + STUB + _page_js(res) + "\n" + tail
    out = subprocess.run([NODE, "-e", src], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr[-2000:]
    return json.loads(out.stdout.strip().splitlines()[-1])


def _section(html, title, nxt):
    return html[html.index(title):html.index(nxt)]


@pytest.mark.skipif(NODE is None, reason="node 가 없다")
def test_principal_rankings_skip_absent_parts():
    html = _run_node(_result(), "1", "console.log(JSON.stringify(renderStress()));")
    s1 = _section(html, "Max Principal Stress (σ₁) 순위", "Min Principal Stress (σ₃)")
    s3 = _section(html, "Min Principal Stress (σ₃)", "소성 변형률 순위")
    for sec in (s1, s3):
        assert "Part 1" in sec, sec
        assert "MOTIONONLY" not in sec and "Part 3" not in sec, "주응력이 없는 파트가 순위에 끼었다"
    assert "NaN" not in html


@pytest.mark.skipif(NODE is None, reason="node 가 없다")
def test_deep_dive_cards_show_dash_for_absent():
    kpi = _run_node(_result(), "2", "try { updateDeepDive(); } catch (e) {}\n"
                                    "console.log(JSON.stringify(rec['dd-kpis'] ? rec['dd-kpis'].innerHTML : ''));")
    vals = dict(re.findall(r'kpi-label">([^<]+)</div><div class="kpi-value[^"]*">([^<]*)</div>', kpi))
    for label in ("피크 변형률", "Max Principal (σ₁)", "Min Principal (σ₃)", "피크 가속도"):
        assert vals.get(label) == "—", f"{label} 카드: {vals.get(label)!r} — 없는 값은 0 이 아니다"
