# report/models.py 의 파생값(피크 요소 ID 등)이 원자료와 어긋나지 않는지 검증하는 시험
"""`koo_deep_report.report.models` 시험.

여기서 보는 것은 "파생값이 원자료를 배신하지 않는가" 하나다.
시계열이 잘려 피크 시점이 사라졌으면 그 시점의 요소 ID 는 **없는 것**이다.
가장 가까운 남은 점의 ID 를 대신 내놓으면 다른 시각의 요소를 피크라고
부르게 된다.
"""
import json
import sys
from pathlib import Path

from koo_deep_report.core.d3plot_reader import _parse_series
from koo_deep_report.report.models import PartTimeSeries

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
