# analysis_result.json 이 잘린 시계열일 때 impact 로더가 피크를 잃지 않는지 보는 시험
"""`_extract_part_stress_strain` 규칙.

옛 unified_analyzer 는 analysis_result.json 의 시계열을 앞 10 + 뒤 10 = 20 점으로
잘라 쓰고 가운데를 `"...(omitted N entries)..."` 문자열로 대체했다.
koo_deep_report 의 `_parse_series` 가 그 표식을 지우기 때문에 로더에는 20 점짜리
정상 배열처럼 보인다. 실측(Test_Impact_A F5_DOE_013 part 21)에서 진짜 피크는
t=4.847e-05 의 2255.42 MPa 인데 20 점 배열의 최대는 201.47 MPa 였다 — 11배.

규칙은 둘이다.
  1. num_states 보다 점이 적으면 잘린 것으로 보고 전해상도 CSV 로 되읽는다.
  2. CSV 도 없으면 시계열을 내보내지 않고(0 도 20 점 그래프도 아니다) 사유를 남긴다.
변형률도 같은 규칙이다. 종전에는 '변형률 CSV 는 소수 6자리 고정이라 대체 불가'
라며 CSV 경로를 막았지만, 그 전제는 fce37bf(작성기 CSV 를 defaultfloat·유효숫자
10자리로 교체)가 없앴다.
"""
from __future__ import annotations

import math
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from koo_impact_report.loader import _extract_part_stress_strain  # noqa: E402

N_STATES = 992
TRUE_PEAK = 2255.41767732
TRUE_PEAK_T = 4.847e-05


class _Series:
    """koo_deep_report.report.models.PartTimeSeries 와 같은 모양."""

    def __init__(self, pid, quantity, unit, data, global_max):
        self.part_id = pid
        self.part_name = ""
        self.quantity = quantity
        self.unit = unit
        self.global_max = global_max
        self.global_min = 0.0
        self.time_of_max = TRUE_PEAK_T
        self.data = data


class _Result:
    def __init__(self, stress=None, strain=None, output_dir=None, num_states=N_STATES):
        self.metadata = {"num_states": num_states}
        self.stress = stress or []
        self.strain = strain or []
        self.output_dir = output_dir

    @property
    def num_states(self):
        return self.metadata.get("num_states", 0)


def _full_curve():
    """992 상태짜리 실제 곡선 — 4.847e-05 에서 2255.42 피크."""
    out = []
    for i in range(N_STATES):
        t = i * 1.008e-06
        v = TRUE_PEAK * math.exp(-((t - TRUE_PEAK_T) / 2.0e-05) ** 2)
        out.append((t, v))
    return out


def _truncated_data(curve):
    """C++ 작성기가 남기던 앞 10 + 뒤 10 점 (가운데 표식은 파서가 이미 지웠다)."""
    keep = curve[:10] + curve[-10:]
    return [{"time": t, "max": v, "min": 0.0, "avg": v / 3.0} for t, v in keep]


def _write_csv(path: Path, curve, header):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(header + "\n")
        for t, v in curve:
            f.write(f"{t:.6f},{v:.6f},0.000000,{v / 3.0:.6f},1,1\n")


def test_truncated_stress_is_reloaded_from_full_csv():
    """20 점으로 잘린 응력은 전해상도 CSV 로 되읽어 피크를 되찾는다."""
    curve = _full_curve()
    tmp = Path(tempfile.mkdtemp(prefix="koo_impact_ts_"))
    try:
        _write_csv(tmp / "stress" / "part_21_von_mises.csv", curve,
                   "Time,Max_von_mises,Min_von_mises,Avg_von_mises,"
                   "Max_Element_ID,Min_Element_ID")
        res = _Result(stress=[_Series(21, "von_mises", "MPa",
                                      _truncated_data(curve), TRUE_PEAK)],
                      output_dir=tmp)
        rec = _extract_part_stress_strain(res)[21]
        assert len(rec["stress_times"]) == N_STATES, \
            f"20 점짜리 잘린 배열이 그대로 나왔다: {len(rec['stress_times'])}"
        assert max(rec["stress_max_series"]) > 0.99 * TRUE_PEAK, \
            f"피크를 놓쳤다: {max(rec['stress_max_series'])}"
        assert rec["stress_ts_source"] == "csv"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_truncated_stress_without_csv_is_omitted_with_reason():
    """CSV 도 없으면 20 점 곡선을 '진짜 이력' 으로 내보내지 않는다."""
    curve = _full_curve()
    tmp = Path(tempfile.mkdtemp(prefix="koo_impact_ts_"))
    try:
        res = _Result(stress=[_Series(21, "von_mises", "MPa",
                                      _truncated_data(curve), TRUE_PEAK)],
                      output_dir=tmp)
        rec = _extract_part_stress_strain(res)[21]
        assert rec.get("stress_times") is None
        assert rec.get("stress_max_series") is None
        assert "20/992" in rec["stress_ts_issue"], rec.get("stress_ts_issue")
        # 스칼라 피크(global_max)는 잘림과 무관하게 살아 있어야 한다.
        assert abs(rec["peak_stress"] - TRUE_PEAK) < 1e-6
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_truncated_strain_is_reloaded_from_full_csv():
    """변형률도 응력과 같이 전해상도 CSV 로 되읽는다.

    종전 규칙('변형률 CSV 는 소수 6자리 고정이라 대체 불가')의 전제는
    fce37bf 가 없앴다 — 지금 작성기는 defaultfloat·유효숫자 10자리다.
    없는 손실을 근거로 시계열을 버리고 WARNING 을 만들면 안 된다.
    """
    curve = [(i * 1.008e-06, 2.5e-05) for i in range(N_STATES)]
    tmp = Path(tempfile.mkdtemp(prefix="koo_impact_ts_"))
    try:
        path = tmp / "strain" / "part_21_eff_plastic_strain.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("Time,Max_eff_plastic_strain,Min_eff_plastic_strain,"
                    "Avg_eff_plastic_strain,Max_Element_ID,Min_Element_ID\n")
            for t, v in curve:   # 새 작성기 형식 — 유효숫자 10자리
                f.write(f"{t:.10g},{v:.10g},0,{v / 3:.10g},1,1\n")
        res = _Result(strain=[_Series(21, "eff_plastic_strain", "",
                                      _truncated_data(curve), 2.532e-05)],
                      output_dir=tmp)
        rec = _extract_part_stress_strain(res)[21]
        assert len(rec["strain_times"] or []) == N_STATES, \
            f"되읽지 않았다: {rec.get('strain_ts_issue')}"
        assert max(rec["strain_max_series"]) == 2.5e-05, rec["strain_max_series"][:3]
        assert rec["strain_ts_source"] == "csv"
        assert "strain_ts_issue" not in rec, rec["strain_ts_issue"]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_truncated_strain_without_csv_is_omitted_with_the_real_reason():
    """CSV 가 없을 때만 시계열을 빼고, 사유는 '정밀도' 가 아니라 '없음' 이다."""
    curve = [(i * 1.008e-06, 2.5e-05) for i in range(N_STATES)]
    tmp = Path(tempfile.mkdtemp(prefix="koo_impact_ts_"))
    try:
        res = _Result(strain=[_Series(21, "eff_plastic_strain", "",
                                      _truncated_data(curve), 2.532e-05)],
                      output_dir=tmp)
        rec = _extract_part_stress_strain(res)[21]
        assert rec.get("strain_times") is None
        issue = rec["strain_ts_issue"]
        assert "20/992" in issue, issue
        assert "6자리" not in issue, issue
        assert "eff_plastic_strain.csv" in issue, issue
        # 스칼라 피크는 잘림과 무관하게 살아 있어야 한다.
        assert abs(rec["peak_strain"] - 2.532e-05) < 1e-12
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_full_series_passes_through():
    """잘리지 않은 시계열은 손대지 않는다 — 회귀 방지."""
    curve = _full_curve()
    data = [{"time": t, "max": v, "min": 0.0, "avg": v / 3.0} for t, v in curve]
    res = _Result(stress=[_Series(21, "von_mises", "MPa", data, TRUE_PEAK)],
                  output_dir=None)
    rec = _extract_part_stress_strain(res)[21]
    assert len(rec["stress_times"]) == N_STATES
    assert rec.get("stress_ts_issue") is None


def test_all():
    """pytest 진입점 — 위 시험들을 한 번에 돌린다."""
    test_truncated_stress_is_reloaded_from_full_csv()
    test_truncated_stress_without_csv_is_omitted_with_reason()
    test_truncated_strain_is_reloaded_from_full_csv()
    test_truncated_strain_without_csv_is_omitted_with_the_real_reason()
    test_full_series_passes_through()
