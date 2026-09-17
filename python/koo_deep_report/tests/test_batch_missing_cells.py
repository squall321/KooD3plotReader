# 배치 표의 결측 칸이 '0' 이 아니라 '—' 로 찍히는지 검증하는 시험
"""`koo_deep_report.report.batch_report` 의 결측 표기 시험.

fmt/fmtSig 의 계약은 '진짜 0 은 0, 결측만 —' 이다. 그런데 ROWS 조립부가
`?? 0` 으로 결측을 0 으로 뭉개면 계약이 그 자리에서 깨진다 — 해석이 아예
돌지 않은 실패·스킵 행까지 'T end 0, 피크 응력 0, 피크 변형률 0,
피크 변위 0' 으로 나와 '측정된 0' 처럼 읽힌다.

생산자 쪽도 같이 본다. metadata.t_end 와 summary.peak_strain_global 이
키 부재가 아니라 0.0 값으로 나가면 소비자가 손쓸 방법이 없다.
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from koo_deep_report.report.batch_report import _build_html
from koo_deep_report.report.models import SimInfo, SingleResult

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


def run_js(snippet: str, tag: str):
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


# ---------------------------------------------------------------------------
print("[1] 결측 칸은 '0' 이 아니라 '—' 로 찍힌다")

ok_full = {
    "schema": "koo_deep_report/1.0", "label": "ok_full", "tier": 3,
    "metadata": {"project_name": "ok_full", "num_states": 100,
                 "t_end": 0.001, "num_parts": 2},
    "summary": {"peak_stress_global": 300.0, "peak_strain_global": 4.0e-5,
                "peak_disp_global": 20.0, "energy_ratio_min": 0.99},
    "parts": {}, "glstat": None,
}
# 해석이 0 초에서 끝난 것도, 변형률이 진짜 0 인 것도 실제로 있다 — 이건 '0'.
ok_zero = {
    "schema": "koo_deep_report/1.0", "label": "ok_zero", "tier": 1,
    "metadata": {"project_name": "ok_zero", "num_states": 1,
                 "t_end": 0.0, "num_parts": 1},
    "summary": {"peak_stress_global": 0.0, "peak_strain_global": 0.0,
                "peak_disp_global": 0.0, "energy_ratio_min": None},
    "parts": {}, "glstat": None,
}
# 계측되지 않은 것은 키가 없거나 null 이다.
ok_missing = {
    "schema": "koo_deep_report/1.0", "label": "ok_missing", "tier": 1,
    "metadata": {"project_name": "ok_missing", "num_states": 0, "num_parts": 0},
    "summary": {}, "parts": {}, "glstat": None,
}

html = _build_html([ok_full, ok_zero, ok_missing], ["case_fail"], ["case_skip"],
                   Path("/tmp"), 0.0)

rows_src = re.search(r"// Build row data[\s\S]*?\n\n// KPI", html)
fmt_src = re.search(r"function fmt\(v, d=2\) \{[\s\S]*?\n\}", html)
sig_src = re.search(r"function fmtSig\([\s\S]*?\n\}", html)
chkb("ROWS 조립부를 찾았다", rows_src is not None)
chkb("fmt()/fmtSig() 원문을 찾았다", fmt_src is not None and sig_src is not None)

if NODE and rows_src and fmt_src and sig_src:
    src = (
        "const RESULTS = " + json.dumps([ok_full, ok_zero, ok_missing]) + ";\n"
        "const FAILED = ['case_fail'];\nconst SKIPPED = ['case_skip'];\n"
        "const YIELD_STRESS = 0;\n"
        + rows_src.group(0).replace("// KPI", "")
        + fmt_src.group(0) + "\n" + sig_src.group(0) + "\n"
        + "const cell = r => [fmtSig(r.t_end), fmt(r.peak_stress),"
          " fmt(r.peak_strain, 4), fmt(r.peak_disp)];\n"
          "const out = {};\nfor (const r of ROWS) out[r.label] = cell(r);\n"
          "console.log(JSON.stringify(out));"
    )
    out = run_js(src, "ROWS 조립")
    if out:
        chk("계측된 값은 그대로", out["ok_full"],
            ["0.001", "300.00", "4.000e-5", "20.00"])
        chk("진짜 0 은 '0' 으로 남는다", out["ok_zero"], ["0", "0", "0", "0"])
        chk("결측은 T end 도 '—'", out["ok_missing"][0], "—")
        chk("결측은 피크 응력도 '—'", out["ok_missing"][1], "—")
        chk("결측은 피크 변형률도 '—'", out["ok_missing"][2], "—")
        chk("결측은 피크 변위도 '—'", out["ok_missing"][3], "—")
        chk("실패 행은 네 칸 모두 '—'", out["case_fail"], ["—", "—", "—", "—"])
        chk("스킵 행은 네 칸 모두 '—'", out["case_skip"], ["—", "—", "—", "—"])

print()

# ---------------------------------------------------------------------------
print("[2] 생산자도 결측을 0.0 으로 채우지 않는다")

si = SimInfo(path=Path("/tmp/nonexistent_case"))
empty = SingleResult(sim_info=si, label="empty")
d = empty.to_compare_dict()
chk("d3plot 결과가 없으면 t_end 는 null", d["metadata"]["t_end"], None)
chk("파트가 하나도 없으면 피크 변형률은 null",
    d["summary"]["peak_strain_global"], None)
chk("피크 응력도 null (기존 계약 유지)", d["summary"]["peak_stress_global"], None)
chk("피크 변위도 null (기존 계약 유지)", d["summary"]["peak_disp_global"], None)

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
