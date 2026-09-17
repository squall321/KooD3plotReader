# CSV 가 없는 파트의 지표가 '계측된 0' 으로 위장되지 않는지 못박는 시험
"""미계측은 0 이 아니다.

배경(2026-09 전수조사). `peak_stress/peak_strain/peak_g/peak_disp` 는 시리즈가
없으면 0.0 을 돌려주었다. 같은 클래스의 `peak_principal`·`peak_vm_strain`·
`energy` 는 None 을 돌려주는데 이 넷만 달랐다.

실제로 일어난다. /data/Tests/*/common_analysis.yaml 은 von_mises 를 "Front*" 에,
eff_plastic_strain·part_motion 을 "PKG*" 에 건다. 그래서 Front 파트는 응력 CSV 만
있고 변형률·motion CSV 가 없다. 배포된 예제 Test_001_report.json 의 파트 1·2 가
peak_stress 461.2 / peak_strain 0.0 / peak_g 0.0 / peak_disp 0.0 인 이유다.
federate 는 그 0 을 실측으로 읽어 리비전 A 15만 G → B 0 G 를 'Δ -100% 개선' 으로
보고했고, data_status 는 'ok' 였다.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from koo_sphere_report.analyzer import _generate_findings  # noqa: E402
from koo_sphere_report.models import (  # noqa: E402
    AngleCondition, PartInfo, PartResult, Report, SimulationResult, TimeSeriesData,
)
from koo_sphere_report.report.html_report import _build_report_data  # noqa: E402
from koo_sphere_report.report.json_report import save_json  # noqa: E402


def _stress_only() -> PartResult:
    """응력 CSV 만 있는 파트 (Front 계열 — 실제 구성이다)."""
    pr = PartResult(part=PartInfo(part_id=1, part_name="Front\\Metal", group="Front"))
    ts = TimeSeriesData()
    ts.times = [0.0, 1e-4]
    ts.max_values = [0.0, 461.2]
    ts.min_values = [0.0, 0.0]
    ts.avg_values = [0.0, 200.0]
    pr.stress = ts
    return pr


def _report(pr: PartResult) -> Report:
    rep = Report(project_name="T", total_runs=1, successful_runs=1)
    rep.part_info = {1: pr.part}
    sr = SimulationResult(
        run_folder="Run_0001",
        angle=AngleCondition(angle_name="F1_Back", roll=0.0, pitch=0.0, yaw=0.0),
        num_states=2,
    )
    sr.parts = {1: pr}
    rep.results.append(sr)
    return rep


def test_absent_series_is_none_not_zero():
    """CSV 가 없으면 None — σ1·에너지와 같은 규칙이다."""
    pr = _stress_only()
    assert pr.peak_stress == 461.2
    assert pr.peak_strain is None, "변형률 CSV 가 없는데 0 이 나왔다"
    assert pr.peak_g is None, "motion CSV 가 없는데 0 G 가 나왔다"
    assert pr.peak_disp is None, "motion CSV 가 없는데 변위 0 이 나왔다"


def test_html_payload_marks_missing_as_null():
    """payload 는 미계측을 null 로 싣는다 — 화면이 '—' 로 구분할 수 있게."""
    data = _build_report_data(_report(_stress_only()))
    pd = data["results"][0]["parts"]["1"]
    assert pd["peak_stress"] == 461.2
    assert pd["peak_strain"] is None
    assert pd["peak_g"] is None
    assert pd["peak_disp"] is None


def test_json_sidecar_omits_missing_keys():
    """report.json 은 아예 키를 넣지 않는다 — federate 가 no_metric 으로 읽는다."""
    out = Path(tempfile.mkdtemp()) / "report.json"
    save_json(_report(_stress_only()), str(out))
    d = json.loads(out.read_text(encoding="utf-8"))
    pd = d["results_summary"][0]["parts"]["1"]
    assert pd["peak_stress"] == 461.2
    for k in ("peak_strain", "peak_g", "peak_disp"):
        assert k not in pd, f"{k} 키가 0 으로 실려 나갔다"


def test_findings_do_not_crash_on_missing_series():
    """findings 생성이 None 비교로 죽으면 보고서 전체가 죽는다."""
    findings = _generate_findings(_report(_stress_only()))
    assert isinstance(findings, list)


def test_terminal_report_does_not_crash():
    """터미널 요약도 None 을 만나 죽지 않는다."""
    from koo_sphere_report.report.terminal import print_report
    print_report(_report(_stress_only()))


def test_js_tells_unmeasured_strain_from_zero():
    """'소성 변형률 0 = 완전 탄성' 안내가 미계측에도 나오면 거짓말이다."""
    from koo_sphere_report.report.html_report import _JS
    assert "strainMeasured" in _JS, "변형률 계측 여부를 세는 코드가 없다"
    i = _JS.index("완전 탄성 상태를 유지합니다")
    seg = _JS[max(0, i - 900):i]
    assert "strainMeasured" in seg, "미계측일 때도 '완전 탄성' 문장이 나온다"


def test_js_strain_counter_only_counts_measured_parts():
    """계수기가 미계측까지 세면 '완전 탄성' 안내가 미계측 파트에도 나온다.

    가드(`!m.strainMeasured`) 는 그대로 두고 계수기만 무조건 증가로 바꿔도
    문자열 근접 검사는 통과한다 — 그 구멍을 그 줄을 실제로 돌려 막는다.
    """
    import re

    import pytest
    js = _js()
    if js is None:
        pytest.skip("node 가 없어 JS 동작을 확인하지 못했다")
    from koo_sphere_report.report.html_report import _JS
    m = re.search(r"^\s*(.*strainMeasured\+\+;)\s*$", _JS, re.M)
    assert m, "변형률 계수기 줄을 찾지 못했다"
    line = m.group(1)
    out = js.run_js(f"""
let strainMeasured = 0;
let pd = {{}};
{line}
console.log(String(strainMeasured));
pd = {{peak_strain: 0.0}};
{line}
console.log(String(strainMeasured));
""")
    assert out[0] == "0", "변형률을 안 잰 파트를 '계측됨' 으로 셌다"
    assert out[1] == "1", "반올림으로 0 이 된 변형률을 미계측으로 버렸다"


def _js():
    """tests/ 를 경로에 넣고 jsutil 을 돌려준다 (node 없으면 None)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import jsutil
    return jsutil if jsutil.node_bin() else None


def test_js_tooltip_shows_dash_for_unmeasured_velocity():
    """미계측 속도를 '0.0 mm/s' 로 찍으면 계측된 0 으로 읽힌다.

    같은 툴팁의 나머지 네 줄은 '—' 로 정직하게 비어 있어 대비가 더 오해를 부른다.
    --from-json 재생성본은 속도를 복원하지 않으므로 항상 이 경로를 탄다.
    """
    import re

    import pytest
    js = _js()
    if js is None:
        pytest.skip("node 가 없어 JS 동작을 확인하지 못했다")
    from koo_sphere_report.report.html_report import _JS
    m = re.search(r"Vel: <b>(.*?)</b>", _JS)
    assert m, "툴팁의 Vel 줄을 찾지 못했다"
    cell = m.group(1)          # 템플릿 조각 그대로 — 그대로 평가한다
    out = js.run_js(js.extract_functions(_JS, ["fxv"]) + f"""
let pd = {{}};
console.log(`{cell}`);
pd = {{peak_vel: 1234.5}};
console.log(`{cell}`);
""")
    assert out[0] == "—", f"미계측 속도가 '{out[0]}' 로 찍힌다 — 계측된 0 이 아니다"
    assert out[1] == "1234.5 mm/s", out[1]


def test_js_kpi_card_shows_dash_when_velocity_never_measured():
    """속도를 한 번도 못 잰 파트의 KPI 카드가 '0.0' 을 최악값으로 내세우면 안 된다."""
    import re

    import pytest
    js = _js()
    if js is None:
        pytest.skip("node 가 없어 JS 동작을 확인하지 못했다")
    from koo_sphere_report.report.html_report import _JS
    base = ("function L(k){return k;}\nlet reportLang='ko';\n"
            + js.extract_functions(_JS, ["fxv", "buildKPISection"]))
    def _m(vel):
        return ("{sf:2,ys:300,worstStress:{val:100,angle:'a'},worstG:{val:1e6,angle:'a'},"
                "worstStrain:{val:0.1,angle:'a'},worstDisp:{val:1,angle:'a'},"
                f"worstVel:{{val:{vel},angle:'',ri:-1}},"
                "globalRank:1,totalParts:1,cov:0.1,meanStress:100,stdStress:1}")
    out = js.run_js(base + f"""
console.log(buildKPISection({_m('null')}).includes('—'));
console.log(buildKPISection({_m('12.34')}).includes('12.3'));
""")
    assert out[0] == "true", "한 번도 못 잰 속도가 '0.0' 으로 찍힌다"
    assert out[1] == "true", "잰 속도는 그대로 찍혀야 한다"

    # 개요 안내문의 '최대 속도' 도 같은 규칙을 따라야 한다.
    m = re.search(r"reportMax'\)\}: \$\{globalMaxVel[^}]*\}", _JS)
    assert m, "개요 안내문의 최대 속도 줄을 찾지 못했다"
    cell = m.group(0).split("}: ", 1)[1]
    out = js.run_js(js.extract_functions(_JS, ["fxv"]) + f"""
let globalMaxVel = null;
console.log(`{cell}`);
globalMaxVel = 987.6;
console.log(`{cell}`);
""")
    assert out[0] == "—", f"한 번도 못 잰 최대 속도가 '{out[0]}' 로 찍힌다"
    assert out[1] == "987.6 mm/s", out[1]


def test_all():
    """pytest 진입점."""
    test_absent_series_is_none_not_zero()
    test_html_payload_marks_missing_as_null()
    test_json_sidecar_omits_missing_keys()
    test_findings_do_not_crash_on_missing_series()
    test_terminal_report_does_not_crash()
    test_js_tells_unmeasured_strain_from_zero()
    test_js_strain_counter_only_counts_measured_parts()
    test_js_tooltip_shows_dash_for_unmeasured_velocity()
    test_js_kpi_card_shows_dash_when_velocity_never_measured()
