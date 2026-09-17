# 배치 보고서가 만들어내는 JS 가 문법적으로 온전하고 값이 뭉개지지 않는지 검증하는 시험
"""`koo_deep_report.report.batch_report` 시험.

배치 보고서는 전부 인라인 JS 다. JS 가 한 글자라도 깨지면 페이지 전체가
빈 화면이 되므로 먼저 `node --check` 로 문법을 본다. node 가 없으면 그
검사는 건너뛴다(사유를 찍는다).
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from koo_deep_report.report.batch_report import _build_html

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


def _sample_result(label: str) -> dict:
    """result.json (koo_deep_report/1.0) 최소 형태."""
    return {
        "schema": "koo_deep_report/1.0",
        "label": label,
        "tier": 3,
        "metadata": {"project_name": label, "num_states": 100,
                     "t_end": 0.00100001, "num_parts": 2,
                     "normal_termination": True, "termination_source": "glstat"},
        "summary": {"peak_stress_global": 300.0, "peak_stress_part_id": 101,
                    "peak_strain_global": 4.0e-5, "peak_disp_global": 20.0,
                    "energy_ratio_min": 0.99},
        "parts": {},
        "glstat": None,
    }


def _scripts(html: str) -> list[str]:
    return re.findall(r"<script>(.*?)</script>", html, re.S)


NODE = shutil.which("node")


def node_check(tag: str, html: str) -> None:
    if not NODE:
        print(f"  -- node 없음 — {tag} 문법 검사 건너뜀")
        return
    with tempfile.TemporaryDirectory() as td:
        for i, sc in enumerate(_scripts(html)):
            f = Path(td) / f"{i}.js"
            f.write_text(sc, encoding="utf-8")
            r = subprocess.run([NODE, "--check", str(f)],
                               capture_output=True, text=True)
            chkb(f"{tag} script[{i}] 문법 통과" + (
                "" if r.returncode == 0 else f" — {r.stderr.strip().splitlines()[:3]}"),
                r.returncode == 0)


# ---------------------------------------------------------------------------
print("[1] 생성된 배치 보고서의 인라인 JS 가 문법적으로 온전한가")

html = _build_html([_sample_result("case_A")], [], [], Path("/tmp"), 0.0)
node_check("batch", html)

print()

# ---------------------------------------------------------------------------
print("[2] 배치 표의 숫자가 0 이나 같은 문자열로 뭉개지지 않는다")


def run_js(snippet: str, tag: str):
    """생성된 HTML 의 JS 조각 + 표현식을 node 로 돌려 결과를 받는다."""
    if not NODE:
        print(f"  -- node 없음 — {tag} 건너뜀")
        return None
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "x.js"
        f.write_text(snippet, encoding="utf-8")
        r = subprocess.run([NODE, str(f)], capture_output=True, text=True)
        if r.returncode != 0:
            fails.append(f"{tag} 실행 실패: {r.stderr.strip()[:300]}")
            return None
        return json.loads(r.stdout.strip())


# 페이지의 실제 포매터 원문을 뽑는다.
fmt_src = re.search(r"function fmt\(v, d=2\) \{[\s\S]*?\n\}", html) \
    or re.search(r"function fmt\(v, d=2\) \{.*\n", html)
sig_src = re.search(r"function fmtSig\([\s\S]*?\n\}", html)
val_src = re.search(r"function fmtVal\(v, field\) \{[\s\S]*?\n\}", html)
chkb("fmt() 원문을 찾았다", fmt_src is not None)
chkb("fmtSig() 원문을 찾았다", sig_src is not None)
chkb("fmtVal() 원문을 찾았다", val_src is not None)

if NODE and fmt_src and sig_src and val_src:
    src = fmt_src.group(0) + "\n" + sig_src.group(0) + "\n" + val_src.group(0) + "\n"
    # t_end: 초 단위 덱 (표본 result.json 이 0.00100001) — 옛 코드는 '0.0'.
    out = run_js(src + "console.log(JSON.stringify(["
                 "fmtSig(0.00100001), fmtSig(0.05), fmtSig(1.2e-4), fmtSig(30.0),"
                 "fmt(4e-5,4), fmt(1.2e-4,4), fmt(0,2), fmt(null,2),"
                 "fmtVal(4e-5,'peak_strain'), fmtVal(3e-9,'peak_strain'),"
                 "fmtVal(0,'peak_strain'), fmtVal(null,'peak_strain'),"
                 "fmt(300.0,2), fmtVal(300.0,'peak_stress')]));", "배치 포매터")
    if out:
        chk("t_end 0.00100001", out[0], "0.001")
        chk("t_end 0.05", out[1], "0.05")
        chk("t_end 1.2e-4", out[2], "1.200e-4")
        chk("t_end 30", out[3], "30")
        chk("변형률 4e-5", out[4], "4.000e-5")
        chkb("4e-5 와 1.2e-4 가 다른 문자열", out[4] != out[5])
        chk("진짜 0 은 0", out[6], "0")
        chk("결측은 —", out[7], "—")
        chk("파트표 변형률 4e-5", out[8], "4.000e-5")
        chk("파트표 변형률 3e-9", out[9], "3.000e-9")
        chk("파트표 진짜 0 은 0", out[10], "0")
        chk("파트표 결측은 —", out[11], "—")
        chk("정상 범위 응력은 그대로", out[12], "300.00")
        chk("파트표 정상 범위 응력", out[13], "300.00")

print()

# ---------------------------------------------------------------------------
print("[3] 이름이 같은 파트가 서로를 덮지 않는다")

# 조립 덱에는 같은 *PART 제목이 흔하다 (SCREW·FOAM·TAPE, 배터리 덱의 boxsolid).
dup = _sample_result("case_A")
dup["parts"] = {
    "101": {"name": "SCREW", "peak_stress": 900.0, "peak_strain": 0.01,
            "peak_disp_mag": 1.0},
    "102": {"name": "SCREW", "peak_stress": 50.0, "peak_strain": 0.001,
            "peak_disp_mag": 0.5},
    "103": {"name": "FOAM", "peak_stress": 20.0, "peak_strain": 0.2,
            "peak_disp_mag": 3.0},
}
html3 = _build_html([dup], [], [], Path("/tmp"), 0.0)
node_check("batch(dup)", html3)

m = re.search(r"const ALL_PARTS[\s\S]*?const CASE_LABELS = [^\n]*\n", html3)
chkb("ALL_PARTS 구성 코드를 찾았다", m is not None)
if NODE and m:
    src = ("const RESULTS = " + json.dumps([dup], ensure_ascii=False) + ";\n"
           + m.group(0)
           + "console.log(JSON.stringify(Object.values(ALL_PARTS)"
             ".map(v => [v.pid, v.name, Object.values(v.cases)[0].peak_stress])));")
    out = run_js(src, "ALL_PARTS")
    if out is not None:
        chk("파트 3개가 모두 남는다", len(out), 3)
        peaks = {row[0]: row[2] for row in out}
        chk("PID 101 (SCREW) 900 MPa 가 살아 있다", peaks.get(101), 900.0)
        chk("PID 102 (SCREW) 50 MPa 도 살아 있다", peaks.get(102), 50.0)
        chk("PID 103 (FOAM)", peaks.get(103), 20.0)

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
