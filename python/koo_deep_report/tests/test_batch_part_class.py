# 배치 보고서 파트표의 색 등급(valClass)이 생산자 어휘와 맞는지 검증하는 시험
"""`koo_deep_report.report.batch_report` 의 파트 비교표 색 등급 시험.

생산자(`PartSummary.stress_warning`)는 'none'|'ok'|'warn'|'crit' 을 내고
result.json 에 그대로 실린다. 소비자(batch_report 의 valClass)가 'OVER' 를
찾으면 한도를 넘긴 파트가 영영 위험색을 못 받고, 한도의 86% 인 파트와 같은
경고색으로 그려진다.

두 겹으로 본다. ① 생성된 HTML 의 문자열 — node 없이도 걸린다. ② node 가
있으면 valClass 를 실제로 꺼내 돌려 등급을 확인한다. node 가 없으면 ②는
건너뛴 사유를 출력한다 — 통과로 위장하지 않는다.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from koo_deep_report.report.batch_report import generate_batch_html
from koo_deep_report.report.models import PartSummary

fails = []
skips = []


def chk(name, got, want):
    ok = got == want
    if not ok:
        fails.append(f"{name}: got={got!r} want={want!r}")
    print(f"  {'OK ' if ok else 'NG '} {name}")


def chkb(name, cond):
    if not cond:
        fails.append(name)
    print(f"  {'OK ' if cond else 'NG '} {name}")


def _extract_fn(html: str, name: str) -> str:
    """HTML 안의 `function <name>(…) { … }` 본문을 중괄호 짝으로 잘라낸다."""
    i = html.index(f"function {name}(")
    j = html.index("{", i)
    depth = 0
    for k in range(j, len(html)):
        if html[k] == "{":
            depth += 1
        elif html[k] == "}":
            depth -= 1
            if depth == 0:
                return html[i:k + 1]
    raise ValueError(f"{name} 의 닫는 중괄호를 못 찾았다")


def _build_html_text() -> str:
    part = {
        "name": "P", "peak_stress": 300.0, "peak_strain": 0.01,
        "stress_limit": 100.0, "stress_ratio": 3.0,
        "strain_limit": 0.002, "strain_ratio": 5.0,
        "stress_warning": "crit", "strain_warning": "crit",
    }
    results = [{"schema": "koo_deep_report/1.0", "label": "case1",
                "metadata": {}, "parts": {"1": part}}]
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "batch_report.html"
        generate_batch_html(results, [], [], Path(td), out)
        return out.read_text(encoding="utf-8")


HTML = _build_html_text()

print("[1] 생산자 어휘 — models.PartSummary")
chk("ratio 3.0 → crit", PartSummary(1, "P", stress_ratio=3.0).stress_warning, "crit")
chk("ratio 0.9 → warn", PartSummary(1, "P", stress_ratio=0.9).stress_warning, "warn")
chk("ratio None → none", PartSummary(1, "P").stress_warning, "none")
chkb("'OVER' 는 생산자 어휘에 없다",
     "OVER" not in {PartSummary(1, "P", stress_ratio=r).stress_warning
                    for r in (0.1, 0.9, 3.0)})

print("[2] 생성된 HTML 이 생산자 어휘로 비교한다")
chkb("'OVER' 비교가 남아 있지 않다", "=== 'OVER'" not in HTML)
chkb("'crit' 으로 비교한다", "=== 'crit'" in HTML)

print("[3] valClass 실행 — 등급")
_node = shutil.which("node") or shutil.which("nodejs")
if not _node:
    skips.append("node 미설치 — valClass 실행 확인 생략")
    print("  -- 건너뜀: node 미설치")
else:
    fn = _extract_fn(HTML, "valClass")
    cases = [
        ("한도 초과(crit) → 위험색", {"stress_warning": "crit", "stress_ratio": 3.0},
         "peak_stress", "val-danger"),
        ("경고(warn) → 경고색", {"stress_warning": "warn", "stress_ratio": 0.9},
         "peak_stress", "val-warn"),
        # 생산자 경고 문턱은 0.8 — 0.82 도 warn 이다
        ("경고 문턱 0.8 바로 위 → 경고색", {"stress_warning": "warn", "stress_ratio": 0.82},
         "peak_stress", "val-warn"),
        ("정상(ok) → 기본색", {"stress_warning": "ok", "stress_ratio": 0.3},
         "peak_stress", "val-stress"),
        ("한도 없음(none) → 기본색", {"stress_warning": "none", "stress_ratio": None},
         "peak_stress", "val-stress"),
        ("변형률 crit → 위험색", {"strain_warning": "crit", "strain_ratio": 5.0},
         "peak_strain", "val-danger"),
        ("변형률 warn → 경고색", {"strain_warning": "warn", "strain_ratio": 0.9},
         "peak_strain", "val-warn"),
        ("변형률 ok → 기본색", {"strain_warning": "ok", "strain_ratio": 0.3},
         "peak_strain", "val-strain"),
        # warning 필드가 없는 옛 result.json — ratio 대비책이 살아 있어야 한다
        ("옛 result.json(ratio만) → 경고색", {"stress_ratio": 0.9},
         "peak_stress", "val-warn"),
    ]
    script = fn + "\nconst CASES = " + json.dumps(
        [[c[1], c[2]] for c in cases]) + ";\n" \
        "console.log(JSON.stringify(CASES.map(([p, f]) => valClass(p, f))));\n"
    proc = subprocess.run([_node, "-e", script], capture_output=True, text=True)
    if proc.returncode != 0:
        fails.append(f"node 실행 실패: {proc.stderr.strip()}")
        print("  NG  node 실행 실패:", proc.stderr.strip())
    else:
        got = json.loads(proc.stdout.strip())
        for (name, _p, _f, want), g in zip(cases, got):
            chk(name, g, want)

print()


def test_all():
    """pytest 진입점.

    이 파일의 본문은 import 시점에 이미 실행된다(스크립트로도 돌릴 수 있게
    그렇게 썼다). pytest 는 여기서 결과만 단언한다.
    """
    assert not fails, "실패 %d 건:\n  - %s" % (len(fails), "\n  - ".join(fails))


if __name__ == "__main__":
    for s in skips:
        print("   ~ 건너뜀:", s)
    if fails:
        print(f"[FAIL] 실패 {len(fails)} 건")
        for f in fails:
            print("   -", f)
        sys.exit(1)
    print("[PASS] 실패 0 건")
