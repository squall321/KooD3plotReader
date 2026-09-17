# --from-json 재생성이 저장된 값을 읽는지, 없는 파형을 지어내지 않는지 보는 시험
"""report.json → Report 왕복.

배경(2026-09 전수조사). `from_json` 은 저장된 시계열을 **한 번도 읽지 않고**
피크 스칼라만으로 2점 파형을 지어냈다.
  stress_ts = {t:[0, peak_time], max:[0, peak], avg:[0, peak]}   ← avg = max 는 날조
  g_ts      = {t:[0, peak_g_time], g:[0, peak_g]}
변형률은 제 시각 대신 `time_of_peak_stress` 를 썼고, σ1/σ3/주변형률/에너지 키는
읽지 않아 그 칸이 통째로 사라졌다. 그 위에서 Impact Pulse 는 2점으로 펄스 폭과
충격량을 계산하고, Energy Absorption 은 avg=peak 때문에 15배 큰 값을 냈다.
화면 어디에도 "이 곡선은 합성" 이라는 표시가 없었다.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from koo_sphere_report.from_json import load_report_from_json  # noqa: E402
from koo_sphere_report.models import (  # noqa: E402
    AngleCondition, MotionData, PartEnergy, PartInfo, PartResult, Report,
    SimulationResult, TimeSeriesData,
)
from koo_sphere_report.report.json_report import save_json  # noqa: E402

N = 60
STRESS = [300.0 * (i / 20.0 if i <= 20 else max(0.0, (40 - i) / 20.0)) for i in range(N)]
STRAIN = [0.0] * N
STRAIN[37] = 0.0042          # 응력 피크(=20)와 **다른** 시각에 온다


def _built_report() -> Report:
    pr = PartResult(part=PartInfo(part_id=7, part_name="PKG\\A", group="PKG"))
    t = [i * 1e-5 for i in range(N)]

    st = TimeSeriesData()
    st.times, st.max_values = list(t), list(STRESS)
    st.min_values = [0.0] * N
    st.avg_values = [v / 3.0 for v in STRESS]
    pr.stress = st

    sn = TimeSeriesData()
    sn.times, sn.max_values = list(t), list(STRAIN)
    sn.avg_values = [v / 2.0 for v in STRAIN]
    pr.strain = sn

    p1 = TimeSeriesData()
    p1.times, p1.max_values = list(t), [v * 1.08 for v in STRESS]
    pr.principal = p1

    p3 = TimeSeriesData()
    p3.times, p3.max_values = list(t), [0.0] * N
    p3.min_values = [-v * 0.9 for v in STRESS]
    p3.true_min = -min(-v * 0.9 for v in STRESS) * -1.0
    pr.principal_min = p3

    pr.energy = PartEnergy(peak_ie=12.5, peak_ie_time=2e-4, peak_ke=31.0,
                           peak_ke_time=1e-5, final_ie=9.75, final_ke=0.5)

    mo = MotionData()
    mo.times = list(t)
    mo.avg_acc_mag = [v * 100.0 for v in STRESS]
    mo.avg_disp_mag = [float(i) * 0.1 for i in range(N)]
    mo.max_disp_mag = [float(i) * 0.11 for i in range(N)]
    mo.avg_vel_mag = [float(i) for i in range(N)]
    pr.motion = mo

    rep = Report(project_name="RT", total_runs=1, successful_runs=1)
    rep.part_info = {7: pr.part}
    sr = SimulationResult(
        run_folder="Run_0001",
        angle=AngleCondition(angle_name="P0001", roll=1.0, pitch=2.0, yaw=3.0),
        num_states=N,
    )
    sr.parts = {7: pr}
    rep.results.append(sr)
    return rep


def _roundtrip() -> PartResult:
    out = Path(tempfile.mkdtemp()) / "report.json"
    save_json(_built_report(), str(out))
    back = load_report_from_json(out)
    return back.results[0].parts[7]


def test_stress_series_is_read_not_invented():
    """저장된 시계열을 읽어야 한다 — 2점 램프는 있지도 않은 파형이다."""
    pr = _roundtrip()
    assert pr.stress is not None
    assert len(pr.stress.times) > 2, (
        f"응력 시계열이 {len(pr.stress.times)}점 — 피크만으로 지어낸 파형이다")
    assert abs(pr.stress.peak - 300.0) < 1.0


def test_avg_is_not_set_equal_to_peak():
    """avg = max 로 채우면 에너지 흡수 적분이 15배 커진다.

    사이드카는 stress_ts 에 t/max 만 실는다 — avg 는 **없는 것이 맞다**.
    화면은 `pd.stress_ts.avg &&` 로 가려져 에너지 흡수 칸을 감춘다.
    금지되는 것은 avg 를 peak 으로 채워 있는 척하는 일이다.
    """
    pr = _roundtrip()
    avg = pr.stress.avg_values
    assert (not avg) or max(avg) < pr.stress.peak * 0.9, (
        f"avg 최대 {max(avg)} 가 피크 {pr.stress.peak} 와 같다 — 날조된 값이다")


def test_strain_uses_its_own_peak_time():
    """변형률 피크 시각에 응력 피크 시각을 쓰면 다른 사건을 같은 순간으로 만든다."""
    pr = _roundtrip()
    assert pr.strain is not None
    assert abs(pr.strain.peak_time - 37e-5) < 1e-7, (
        f"변형률 피크 시각 {pr.strain.peak_time} — 응력 피크(20e-5)를 가져다 썼다")


def test_principal_and_energy_survive():
    """σ1/σ3·에너지 칸이 재생성에서 사라지면 안 된다."""
    pr = _roundtrip()
    assert pr.peak_principal is not None and pr.peak_principal > 300.0
    assert pr.min_principal is not None and pr.min_principal < 0.0
    assert pr.energy is not None and pr.energy.final_ie == 9.75


def test_motion_series_is_read():
    """g_ts/disp_ts 를 읽어야 Impact Pulse 가 2점으로 폭을 재지 않는다."""
    pr = _roundtrip()
    assert pr.motion is not None
    assert len(pr.motion.avg_acc_mag) > 2
    assert len(pr.motion.avg_disp_mag) > 2


def test_absent_series_stays_absent():
    """키가 없으면 빈 채로 둔다 — 없는 곡선을 만들지 않는다."""
    d = {
        "results_summary": [{
            "run_folder": "R", "num_states": 0,
            "angle": {"name": "P0001", "roll": 0.0, "pitch": 0.0, "yaw": 0.0},
            "parts": {"7": {"peak_stress": 100.0, "time_of_peak_stress": 1e-4}},
        }],
        "parts": {"7": {"part_name": "PKG\\A", "group": "PKG"}},
    }
    out = Path(tempfile.mkdtemp()) / "r.json"
    out.write_text(json.dumps(d), encoding="utf-8")
    pr = load_report_from_json(out).results[0].parts[7]
    assert pr.motion is None, "motion 이 없는데 지어냈다"
    assert pr.strain is None, "변형률이 없는데 지어냈다"
    assert pr.peak_stress == 100.0
    assert pr.stress.times == [], "시계열이 없는데 점을 만들어냈다"


def test_all():
    """pytest 진입점."""
    test_stress_series_is_read_not_invented()
    test_avg_is_not_set_equal_to_peak()
    test_strain_uses_its_own_peak_time()
    test_principal_and_energy_survive()
    test_motion_series_is_read()
    test_absent_series_stays_absent()
