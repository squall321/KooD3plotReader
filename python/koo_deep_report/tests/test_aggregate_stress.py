# 응력 이력이 없는 파트(셸·두꺼운셸)를 '0 MPa' 로 보고하지 않는지 검증하는 시험
"""`koo_deep_report.__main__._aggregate` 의 응력 집계 시험.

C++ 의 stress_history 는 솔리드 전용이다. motion 은 셸·두꺼운셸·빔까지
전부 다룬다. 그래서 셸 파트는 '응력 미산출' 인데, 0.0 을 채워 넣으면
보고서가 '피크 응력 0.00 MPa' 라는 **측정값** 으로 보여준다 — 항복을
넘긴 셸이 가장 안전한 파트로 보인다.
"""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from koo_deep_report.__main__ import _aggregate
from koo_deep_report.report.html_report import _build_html
from koo_deep_report.report.models import (
    D3plotResult, MotionData, PartTimeSeries, SimInfo,
)

fails = []


def chk(name, got, want):
    ok = got == want
    if not ok:
        fails.append(f"{name}: got={got!r} want={want!r}")
    print(f"  {'OK ' if ok else 'NG '} {name}")


def chkb(name, cond):
    if not cond:
        fails.append(name)
    print(f"  {'OK ' if cond else 'NG '} {name}")


def _series(pid, gmax, t_of_max):
    return PartTimeSeries(
        part_id=pid, part_name=f"P{pid}", quantity="von_mises", unit="MPa",
        global_max=gmax, global_min=0.0, time_of_max=t_of_max,
        data=[{"time": 0.0, "max": 0.0, "min": 0.0, "avg": 0.0, "max_element_id": 1},
              {"time": t_of_max, "max": gmax, "min": 0.0, "avg": gmax / 2,
               "max_element_id": 77}],
        num_points=2,
    )


def _motion(pid, name):
    return MotionData(part_id=pid, part_name=name, t=[0.0, 1.0e-3],
                      disp_mag=[0.0, 1.0], vel_mag=[0.0, 2.0], acc_mag=[0.0, 3.0],
                      max_disp_mag=[0.0, 4.0], max_disp_node=[0, 9])


# 솔리드 파트 1(응력 있음) + 셸 파트 2(motion 만 있음)
dr = D3plotResult(
    metadata={"num_states": 2, "end_time": 1.0e-3, "analyzed_parts": [1, 2]},
    stress=[_series(1, 300.0, 5.0e-4)],
    strain=[],
    acceleration=[],
    motion={1: _motion(1, "HOUSING"), 2: _motion(2, "PCB_SHELL")},
    output_dir=Path("/tmp"),
)
si = SimInfo(path=Path("/tmp/case"), d3plot=Path("/tmp/case/d3plot"), tier=1)
res = _aggregate(si, dr, None, 0.0, "case")

# ---------------------------------------------------------------------------
print("[1] 응력 이력이 없는 파트는 0 이 아니라 미산출이다")

chk("솔리드 파트 피크 응력", res.parts[1].peak_stress, 300.0)
chk("셸 파트 피크 응력은 None", res.parts[2].peak_stress, None)
chk("셸 파트 피크 시각도 None", res.parts[2].time_of_peak_stress, None)
chkb("셸 파트에 미산출 사유가 있다", bool(res.parts[2].peak_stress_reason))
chk("솔리드 파트엔 사유 없음", res.parts[1].peak_stress_reason, "")
chk("전체 피크는 응력이 있는 파트에서", res.peak_stress_global, 300.0)
chk("전체 피크 파트 ID", res.peak_stress_part_id, 1)

# 설계기준을 줘도 미산출 파트에는 안전율이 생기지 않는다.
res2 = _aggregate(si, dr, None, 200.0, "case")
chkb("솔리드는 안전율이 계산된다", res2.parts[1].safety_factor is not None)
chk("셸은 안전율 없음", res2.parts[2].safety_factor, None)
chk("셸은 응력비 없음", res2.parts[2].stress_ratio, None)

print()

# ---------------------------------------------------------------------------
print("[2] 보고서가 셸 파트를 '0.00 MPa' 로 보여주지 않는다")

with tempfile.TemporaryDirectory() as td:
    html = _build_html(res, Path(td))

chkb("핫스팟 없이도 '솔리드만' 단서가 붙는다", "솔리드만" in html)
chkb("응력 미산출 파트 수를 밝힌다", "응력 이력 없음" in html or "미산출" in html)

NODE = shutil.which("node")
if NODE:
    with tempfile.TemporaryDirectory() as td:
        ok = True
        for i, sc in enumerate(re.findall(r"<script>(.*?)</script>", html, re.S)):
            f = Path(td) / f"{i}.js"
            f.write_text(sc, encoding="utf-8")
            r = subprocess.run([NODE, "--check", str(f)], capture_output=True, text=True)
            if r.returncode != 0:
                ok = False
                print("   ", r.stderr.strip()[:300])
        chkb("생성된 JS 문법 통과", ok)
else:
    print("  -- node 없음 — JS 문법 검사 건너뜀")

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
