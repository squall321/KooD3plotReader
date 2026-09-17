# 보고서 인라인 JS 의 숫자 표기 함수가 값을 뭉개지 않는지 node 로 직접 돌려 검증하는 시험
"""`koo_deep_report.report.html_report` 의 JS 시험.

보고서 숫자는 전부 JS `fmt()` 를 거친다. 고정 소수 자릿수만 쓰면
서로 다른 값이 같은 문자열이 되거나(1.2e-4 와 1.4e-4 가 둘 다 '0.0001')
0 이 아닌 값이 '0.00' 으로 찍힌다 — 읽는 사람은 '측정값이 0' 으로 읽는다.
그래서 실제 함수 원문을 뽑아 node 로 돌려 본다. node 가 없으면 건너뛴다.
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from koo_deep_report.report import html_report

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


NODE = shutil.which("node")

_FMT_SRC = re.search(r"function fmt\(v, dec=2\) \{[\s\S]*?\n\}", html_report._JS)


def run_fmt(cases: list[tuple[float, int]]) -> list[str]:
    """[(값, 자릿수)] 를 실제 fmt() 로 찍어 문자열 목록을 돌려준다."""
    if not NODE or _FMT_SRC is None:
        return []
    js = _FMT_SRC.group(0) + "\nconsole.log(JSON.stringify(%s.map(c => fmt(c[0], c[1]))));\n" % json.dumps(cases)
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "fmt.js"
        f.write_text(js, encoding="utf-8")
        r = subprocess.run([NODE, str(f)], capture_output=True, text=True)
        if r.returncode != 0:
            fails.append(f"fmt 실행 실패: {r.stderr.strip()[:300]}")
            return []
        return json.loads(r.stdout.strip())


# ---------------------------------------------------------------------------
print("[1] fmt() — 작은 값이 0 이나 같은 문자열로 뭉개지지 않는다")

chkb("html_report._JS 에서 fmt() 를 찾았다", _FMT_SRC is not None)

if not NODE:
    print("  -- node 없음 — fmt 검사 건너뜀")
else:
    # (값, 자릿수) → 기대 문자열
    cases = [
        # 표본 analysis_result.json 의 파트별 피크 시각 (초). 옛 코드는 전부 '0.0001'.
        (7.977e-05, 4), (8.584e-05, 4), (8.786e-05, 4),
        # 서로 다른 두 시각이 같은 문자열이 되면 안 된다.
        (1.2e-4, 4), (1.4e-4, 4),
        # 핫스팟 피크 시각 — 옛 코드는 '0.00000'.
        (3.2e-6, 5),
        # kg-mm-ms 덱의 GPa 응력 — 옛 코드는 '0.09' 와 '0.00'.
        (0.0863, 2), (0.0042, 2),
        # 작은 변형률 — 옛 코드는 둘 다 '0.0000'.
        (3e-5, 4), (4.9e-5, 4),
        # 정상 범위는 그대로 둔다.
        (3748.51419693, 2), (300.0, 2), (0.9912, 4),
    ]
    got = run_fmt(cases)
    if got:
        chk("7.977e-05 (t, 4자리)", got[0], "7.977e-5")
        chk("8.584e-05 (t, 4자리)", got[1], "8.584e-5")
        chk("8.786e-05 (t, 4자리)", got[2], "8.786e-5")
        chkb("1.2e-4 와 1.4e-4 가 다른 문자열", got[3] != got[4])
        chk("3.2e-6 (핫스팟 시각, 5자리)", got[5], "3.200e-6")
        chk("0.0863 (GPa 응력)", got[6], "8.630e-2")
        chk("0.0042 (GPa 응력·접촉 충격량)", got[7], "4.200e-3")
        chkb("3e-5 와 4.9e-5 가 다른 문자열", got[8] != got[9])
        chkb("3e-5 가 0 으로 찍히지 않는다", float(got[8]) != 0.0)
        chk("3748.51419693 (MPa) 는 그대로", got[10], "3748.51")
        chk("300.0 (MPa) 는 그대로", got[11], "300.00")
        chk("0.9912 (에너지비, 4자리) 는 그대로", got[12], "0.9912")

    # 결측·비유한값은 값으로 위장하지 않는다.
    edge = run_fmt([[None, 2], [float("nan"), 2] if False else [0, 2]])
    if edge:
        chk("null 은 —", edge[0], "—")
        chk("0 은 0", edge[1], "0")

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
