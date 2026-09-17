# 옛 이름으로 남은 산출물 폴더가 배치 표에 섞여 들어가지 않는지 검증하는 시험
"""`koo_deep_report.report.batch_report.load_results_from_dir` 시험.

배치 케이스 출력 폴더 이름이 잎 이름에서 배치 루트 기준 상대 경로로 바뀌면서,
같은 --output 으로 다시 돌리면 옛 이름 폴더가 고아로 남는다. 배치 표 입력은
이번 실행이 만든 목록이 아니라 output_root 를 통째로 훑는 것이라, 고아까지
함께 읽혀 케이스가 중복으로 세어지고 KPI '전체/성공' 과 평균·최대 응력,
파트 비교 표의 열이 전부 틀어진다. 경고도 없다.
"""
import json
import sys
import tempfile
from pathlib import Path

from koo_deep_report.report.batch_report import _build_html, load_results_from_dir

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


def _result(label: str) -> dict:
    return {
        "schema": "koo_deep_report/1.0", "label": label, "tier": 3,
        "metadata": {"project_name": label, "num_states": 10,
                     "t_end": 0.001, "num_parts": 1},
        "summary": {"peak_stress_global": 100.0, "peak_strain_global": 0.01,
                    "peak_disp_global": 1.0, "energy_ratio_min": 0.99},
        "parts": {}, "glstat": None,
    }


def _make_root(td: str) -> Path:
    root = Path(td)
    for name in ("A__output__Run_001", "A__output__Run_002", "Output"):
        d = root / name
        d.mkdir()
        (d / "result.json").write_text(json.dumps(_result(name)), encoding="utf-8")
    (root / "no_result").mkdir()
    return root


# ---------------------------------------------------------------------------
print("[1] 이번 배치가 만든 케이스만 읽는다")

with tempfile.TemporaryDirectory() as td:
    root = _make_root(td)
    this_run = ["A__output__Run_001", "A__output__Run_002"]

    results, found = load_results_from_dir(root, case_names=this_run)
    chk("표에 들어가는 것은 이번 케이스 2개", len(results), 2)
    chk("읽힌 라벨", sorted(r["label"] for r in results), sorted(this_run))
    chkb("고아 폴더도 찾은 목록에는 남아 알릴 수 있다", "Output" in found)

print()

# ---------------------------------------------------------------------------
print("[2] 목록을 주지 않으면 예전처럼 전부 읽는다 (다른 호출자 보호)")

with tempfile.TemporaryDirectory() as td:
    root = _make_root(td)
    results, found = load_results_from_dir(root)
    chk("셋 다 읽는다", len(results), 3)
    chk("result.json 이 없는 폴더는 세지 않는다", len(found), 3)

print()

# ---------------------------------------------------------------------------
print("[3] 뺀 폴더가 있으면 보고서에 그 사실이 실린다")

note = "이번 배치에 없는 산출물 폴더 1개를 표에서 뺐습니다: Output"
html = _build_html([_result("A__output__Run_001")], [], [], Path("/tmp"), 0.0,
                   notes=[note])
chkb("사유가 HTML 에 들어 있다", note in html)

html_none = _build_html([_result("A__output__Run_001")], [], [], Path("/tmp"), 0.0)
chkb("알릴 것이 없으면 상자도 없다", '<div class="batch-notes">' not in html_none)

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
