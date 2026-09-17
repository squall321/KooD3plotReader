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
