# 시계열을 두 번 줄여도 피크(값·시각·요소 ID)가 살아남는지 못박는 시험
"""보고서 시계열의 극값 보존 규칙.

배경(2026-09 전수조사). sphere 시계열은 **두 번** 솎였다.
① 로더가 report_pts×4 목표로 `all_max[::step]`,
② html/json 이 그 결과를 다시 `range(0, len, len//ts_pts)` 로.
둘 다 '매 N번째 행' 이라 한두 샘플짜리 충격 피크가 통째로 사라졌다.
스칼라 peak_* 만 참값을 지켰고, 화면의 KPI(Peak G·펄스 폭·CAI·핫스팟 요소)는
전부 솎인 배열에서 다시 계산되었다. 실캠페인 Test_006(1144런×992상태)에서
g 시리즈는 참피크의 12% 까지, 응력은 27% 까지 내려갔다.

여기서 못박는 규칙. **줄이더라도 구간마다 최대·최소는 남긴다** — 전역 피크가
들어 있는 구간은 그 위치를 그대로 내보내므로 값·시각·요소 ID 가 함께 보존된다.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from koo_sphere_report.loader import (  # noqa: E402
    _load_motion_csv, _load_stress_strain_csv,
)
from koo_sphere_report.models import (  # noqa: E402
    AngleCondition, MotionData, PartInfo, PartResult, Report, SimulationResult,
)
from koo_sphere_report.report.html_report import _build_report_data  # noqa: E402
from koo_sphere_report.report.json_report import save_json  # noqa: E402

N_STATES = 992
PEAK_IDX = 811          # 홀수 — 어떤 stride 에도 걸리지 않는다
PEAK_STRESS = 227.6
BG_STRESS = 61.5
PEAK_ELEM = 34016


def _write_stress_csv(path: Path) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Time", "Max_von_mises", "Min_von_mises", "Avg_von_mises",
                    "Max_Element_ID", "Min_Element_ID"])
        for i in range(N_STATES):
            v = PEAK_STRESS if i == PEAK_IDX else BG_STRESS
            eid = PEAK_ELEM if i == PEAK_IDX else 34022
            w.writerow([f"{i * 1e-6:.6f}", v, 0.0, v / 3.0, eid, 0])


def _write_motion_csv(path: Path, peak_acc: float) -> None:
    cols = ["Time", "Avg_Disp_X", "Avg_Disp_Y", "Avg_Disp_Z", "Avg_Disp_Mag",
            "Avg_Vel_X", "Avg_Vel_Y", "Avg_Vel_Z", "Avg_Vel_Mag",
            "Avg_Acc_X", "Avg_Acc_Y", "Avg_Acc_Z", "Avg_Acc_Mag",
            "Max_Disp_Mag", "Max_Disp_Node_ID"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for i in range(N_STATES):
            a = peak_acc if i == PEAK_IDX else 1.0e4
            w.writerow([f"{i * 1e-6:.6f}", 0, 0, 0, float(i),
                        0, 0, 0, 1.0,
                        0, 0, a, a,
                        float(i), 5])


def _report(pr: PartResult, n_results: int) -> Report:
    """n_results 개 런짜리 보고서 — tier(정밀도·점수)를 고르는 유일한 입력이다."""
    rep = Report(project_name="T", total_runs=n_results, successful_runs=n_results)
    rep.part_info = {7: pr.part}
    for i in range(n_results):
        sr = SimulationResult(
            run_folder=f"Run_{i:04d}",
            angle=AngleCondition(angle_name=f"P{i:04d}", roll=0.0, pitch=0.0, yaw=0.0),
            num_states=N_STATES,
        )
        sr.parts = {7: pr}
        rep.results.append(sr)
    return rep


def test_loader_stage_keeps_stress_peak(tmp_path: Path):
    """① 로더 단계 — 목표 40점으로 줄여도 참피크 행이 남아야 한다."""
    csv_path = tmp_path / "part_7_von_mises.csv"
    _write_stress_csv(csv_path)
    ts = _load_stress_strain_csv(csv_path, 40)
    assert max(ts.max_values) == PEAK_STRESS, (
        f"로더가 피크를 버렸다: {max(ts.max_values)}")
    i = ts.max_values.index(PEAK_STRESS)
    assert ts.times[i] == PEAK_IDX * 1e-6, "피크 시각이 어긋난다"
    assert ts.max_element_ids[i] == PEAK_ELEM, "피크 요소 ID 가 어긋난다"
    assert len(ts.times) <= 40, f"점수 예산(40)을 넘었다: {len(ts.times)}"


def test_two_stage_keeps_stress_peak_and_element(tmp_path: Path):
    """①+② 두 단계를 거쳐도 HTML payload 에 참피크와 그 요소 ID 가 남아야 한다.

    실측: Run_20260207_215839_edb467 part 14 — 참 227.6 MPa 가 61.5 MPa 로,
    핫스팟 요소는 34016 이 아니라 34022 로 보고되었다.
    """
    csv_path = tmp_path / "part_7_von_mises.csv"
    _write_stress_csv(csv_path)
    pr = PartResult(part=PartInfo(part_id=7, part_name="PKG\\A", group="PKG"))
    pr.stress = _load_stress_strain_csv(csv_path, 40)      # 1144런 tier: 10×4

    data = _build_report_data(_report(pr, 1144))
    sts = data["results"][0]["parts"]["7"]["stress_ts"]
    assert max(sts["max"]) == PEAK_STRESS, (
        f"HTML 시계열의 피크가 {max(sts['max'])} — 참피크 {PEAK_STRESS} 를 잃었다")

    # ≤200런 tier 에서는 요소 ID 가 실린다 — 핫스팟 표가 이 배열의 argmax 를 쓴다.
    pr2 = PartResult(part=PartInfo(part_id=7, part_name="PKG\\A", group="PKG"))
    pr2.stress = _load_stress_strain_csv(csv_path, 120)    # 200런 tier: 30×4
    d2 = _build_report_data(_report(pr2, 200))
    s2 = d2["results"][0]["parts"]["7"]["stress_ts"]
    j = s2["max"].index(max(s2["max"]))
    assert max(s2["max"]) == PEAK_STRESS
    assert s2["elem"][j] == PEAK_ELEM, (
        f"핫스팟 요소가 {s2['elem'][j]} — 참피크 요소 {PEAK_ELEM} 가 아니다")


def test_two_stage_keeps_peak_g(tmp_path: Path):
    """가속도 — 실측 최악은 139,029 G 가 16,928 G(12%)로 찍혔다."""
    peak_g = 139029.0
    csv_path = tmp_path / "part_7_motion.csv"
    _write_motion_csv(csv_path, peak_g * MotionData.G_FACTOR)
    pr = PartResult(part=PartInfo(part_id=7, part_name="PKG\\A", group="PKG"))
    pr.motion = _load_motion_csv(csv_path, 40)

    data = _build_report_data(_report(pr, 1144))
    pd = data["results"][0]["parts"]["7"]
    assert max(pd["g_ts"]["g"]) >= peak_g * 0.999, (
        f"g 시계열 피크가 {max(pd['g_ts']['g'])} — 참피크 {peak_g} 를 잃었다")
    # 변위 시계열도 같은 인덱스 집합을 쓰므로 마지막(최대) 점이 남아야 한다
    assert max(pd["disp_ts"]["mag"]) == float(N_STATES - 1)


def test_json_sidecar_keeps_peak(tmp_path: Path):
    """report.json(federate 사이드카)의 시계열도 같은 규칙을 따른다."""
    csv_path = tmp_path / "part_7_von_mises.csv"
    _write_stress_csv(csv_path)
    pr = PartResult(part=PartInfo(part_id=7, part_name="PKG\\A", group="PKG"))
    pr.stress = _load_stress_strain_csv(csv_path, 40)
    out = tmp_path / "report.json"
    save_json(_report(pr, 1144), str(out))
    import json
    d = json.loads(out.read_text(encoding="utf-8"))
    mx = d["results_summary"][0]["parts"]["7"]["stress_ts"]["max"]
    assert max(mx) >= PEAK_STRESS * 0.999, f"사이드카 시계열 피크가 {max(mx)}"


def test_point_budget_respected(tmp_path: Path):
    """예산 초과 금지 — 1144런 payload 가 부풀면 100MB 를 넘긴다."""
    csv_path = tmp_path / "part_7_von_mises.csv"
    _write_stress_csv(csv_path)
    pr = PartResult(part=PartInfo(part_id=7, part_name="PKG\\A", group="PKG"))
    pr.stress = _load_stress_strain_csv(csv_path, 40)
    data = _build_report_data(_report(pr, 1144))
    sts = data["results"][0]["parts"]["7"]["stress_ts"]
    assert len(sts["t"]) <= 10, f"ts_pts=10 예산을 넘었다: {len(sts['t'])}"
    assert len(sts["t"]) == len(sts["max"]) == len(sts["avg"]), "배열 정렬이 깨졌다"


def test_all(tmp_path: Path):
    """pytest 진입점."""
    def _d(name: str) -> Path:
        p = tmp_path / name
        p.mkdir()
        return p
    test_loader_stage_keeps_stress_peak(_d("a"))
    test_two_stage_keeps_stress_peak_and_element(_d("b"))
    test_two_stage_keeps_peak_g(_d("c"))
    test_json_sidecar_keeps_peak(_d("d"))
    test_point_budget_respected(_d("e"))
