# report/models.py 의 파생값(피크 요소 ID·피크 변위)이 원자료와 어긋나지 않는지 검증하는 시험
"""`koo_deep_report.report.models` 시험.

여기서 보는 것은 "파생값이 원자료를 배신하지 않는가" 하나다.
- 시계열이 잘려 피크 시점이 사라졌으면 그 시점의 요소 ID 는 **없는 것**이다.
  가장 가까운 남은 점의 ID 를 대신 내놓으면 다른 시각의 요소를 피크라고
  부르게 된다.
- '피크 변위' 는 절점 최대(Max_Disp_Mag)여야 한다. 파트 평균 변위 벡터의
  크기는 굽힘·회전에서 상쇄되어 실제 최대보다 한참 작다.
"""
import json
import sys
from pathlib import Path

from koo_deep_report.core.d3plot_reader import _parse_series
from koo_deep_report.report.models import MotionData, PartTimeSeries

fails = []


def chk(name, got, want, tol=0.0):
    ok = (got == want) if tol == 0 else (
        got is not None and want is not None and abs(got - want) <= tol)
    if not ok:
        fails.append(f"{name}: got={got!r} want={want!r}")
    print(f"  {'OK ' if ok else 'NG '} {name}")


def chkb(name, cond):
    if not cond:
        fails.append(name)
    print(f"  {'OK ' if cond else 'NG '} {name}")


# ---------------------------------------------------------------------------
print("[1] 잘린 시계열의 peak_element_id — 다른 시각의 요소를 내놓지 않는다")

# 커밋된 표본 analysis_result.json 재현: 992 상태 중 앞 10·뒤 10 만 남았다.
# time_of_max=7.977e-05 는 잘려나간 가운데 구간에 있다.
trunc = PartTimeSeries(
    part_id=1, part_name="HOUSING", quantity="von_mises", unit="MPa",
    global_max=3748.51419693, global_min=0.0, time_of_max=7.977e-05,
    data=[{"time": 9.09e-06, "max": 0.43062902, "min": 0.0, "avg": 0.01,
           "max_element_id": 4218},
          {"time": 1.0e-05, "max": 0.5, "min": 0.0, "avg": 0.01,
           "max_element_id": 4219}],
    num_points=992,
)
chkb("잘린 계열은 truncated=True", trunc.truncated is True)
chk("생략된 점 수 = 992-2", trunc.omitted_points, 990)
chk("피크 시점이 없으면 peak_element_id=None", trunc.peak_element_id, None)
chkb("사유가 남는다", "잘림" in (trunc.peak_element_reason or ""))

full = PartTimeSeries(
    part_id=1, part_name="HOUSING", quantity="von_mises", unit="MPa",
    global_max=3748.51419693, global_min=0.0, time_of_max=7.977e-05,
    data=[{"time": 9.09e-06, "max": 0.43062902, "min": 0.0, "avg": 0.01,
           "max_element_id": 4218},
          {"time": 7.977e-05, "max": 3748.51419693, "min": 0.0, "avg": 1.0,
           "max_element_id": 90210}],
    num_points=2,
)
chkb("온전한 계열은 truncated=False", full.truncated is False)
chk("피크 시점이 있으면 그 시각의 요소", full.peak_element_id, 90210)
chk("온전한 계열엔 사유 없음", full.peak_element_reason, "")

# 피크 시점은 남았지만 요소 ID 가 기록되지 않은 계열 (셸 경로 등).
noid = PartTimeSeries(
    part_id=2, part_name="X", quantity="von_mises", unit="MPa",
    global_max=1.0, global_min=0.0, time_of_max=0.5,
    data=[{"time": 0.5, "max": 1.0, "min": 0.0, "avg": 0.5}],
    num_points=1,
)
chk("요소 ID 미기록이면 None", noid.peak_element_id, None)
chkb("그 사유도 남는다", noid.peak_element_reason != "")

# 커밋된 표본 파일로 실제 파서까지 통과시킨다 (992 상태 · 20 점만 남은 JSON).
sample = Path(__file__).resolve().parents[1] / "single_report" / "analysis_result.json"
if sample.exists():
    raw = json.loads(sample.read_text(encoding="utf-8"))
    ts = _parse_series(raw["stress_history"][0])
    chk("표본: 남은 점 20", len(ts.data), 20)
    chkb("표본: truncated 로 표시", ts.truncated is True)
    chk("표본: 3748.5 MPa 피크의 요소 ID 는 미기록", ts.peak_element_id, None)
else:
    print("  -- 표본 analysis_result.json 없음 — 건너뜀")

print()

# ---------------------------------------------------------------------------
print("[2] 피크 변위 — 절점 최대를 쓴다 (파트 평균 변위 벡터 크기가 아니라)")

# 외팔보 PCB: 끝단 절점은 20 mm 움직이는데 파트 평균 변위 벡터 크기는 5 mm.
mo = MotionData(
    part_id=7, part_name="PCB",
    t=[0.0, 1.0e-3, 2.0e-3],
    disp_mag=[0.0, 2.5, 5.0],
    max_disp_mag=[0.0, 9.0, 20.0],
    max_disp_node=[0, 331, 412],
)
chk("peak_disp_mag = max(Max_Disp_Mag) = 20", mo.peak_disp_mag, 20.0)
chk("peak_avg_disp_mag = max(Avg_Disp_Mag) = 5", mo.peak_avg_disp_mag, 5.0)
chk("피크 변위 절점 ID", mo.peak_disp_node, 412)
chk("정상이면 사유 없음", mo.peak_disp_reason, "")

# Max_Disp_Mag 열이 없는 옛 CSV 는 미계측이다 — 평균으로 슬쩍 바꿔치지 않는다.
mo_old = MotionData(part_id=8, t=[0.0, 1.0], disp_mag=[0.0, 5.0])
chk("Max_Disp_Mag 없으면 None", mo_old.peak_disp_mag, None)
chk("그래도 평균 피크는 남는다", mo_old.peak_avg_disp_mag, 5.0)
chkb("미계측 사유가 남는다", mo_old.peak_disp_reason != "")

# CSV 파서: 헤더에 Max_Disp_Mag 가 없으면 0 으로 채우지 않는다.
import tempfile
from koo_deep_report.core.d3plot_reader import _parse_motion_csv

with tempfile.TemporaryDirectory() as td:
    old_csv = Path(td) / "part_9_motion.csv"
    old_csv.write_text(
        "Time,Avg_Disp_X,Avg_Disp_Y,Avg_Disp_Z,Avg_Disp_Mag,Avg_Vel_Mag,Avg_Acc_Mag\n"
        "0.0,0,0,0,0.0,0,0\n"
        "1.0,3,4,0,5.0,0,0\n", encoding="utf-8")
    md_old = _parse_motion_csv(old_csv)
    chk("옛 CSV: max_disp_mag 를 0 으로 채우지 않는다", len(md_old.max_disp_mag), 0)
    chk("옛 CSV: peak_disp_mag=None", md_old.peak_disp_mag, None)

    new_csv = Path(td) / "part_10_motion.csv"
    new_csv.write_text(
        "Time,Avg_Disp_Mag,Avg_Vel_Mag,Avg_Acc_Mag,Max_Disp_Mag,Max_Disp_Node_ID\n"
        "0.0,0.0,0,0,0.0,0\n"
        "1.0,5.0,0,0,20.0,412\n", encoding="utf-8")
    md_new = _parse_motion_csv(new_csv)
    chk("새 CSV: peak_disp_mag=20", md_new.peak_disp_mag, 20.0)
    chk("새 CSV: 절점 412", md_new.peak_disp_node, 412)

print()


def test_all():
    """pytest 진입점."""
    assert not fails, "실패 %d 건:\n  - %s" % (len(fails), "\n  - ".join(fails))


if __name__ == "__main__":
    if fails:
        print(f"[FAIL] 실패 {len(fails)} 건")
        for f in fails:
            print("   -", f)
        sys.exit(1)
    print("[PASS] 실패 0 건")
