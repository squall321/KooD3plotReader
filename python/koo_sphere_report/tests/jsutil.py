# 생성 HTML 의 JS 조각을 node 로 실제 실행해 보는 시험 보조 (소스 문자열 검사 대신)
"""문자열이 들어 있는지가 아니라 **무엇이 찍히는지**를 본다.

배경(2026-09 적대적 검토). 화면 표기 시험 몇 건이 `assert "toPrecision" in _JS`
처럼 생성된 소스의 부분 문자열만 봤다. 그러면 호출 지점을 전부 옛 코드로
되돌려도 함수 정의만 남아 있으면 통과한다 — 0.0863 MPa 가 다시 '0.1 MPa' 로
찍혀도 잡지 못한다. 여기서는 필요한 함수만 잘라 내 node 로 실제 호출한다.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


def node_bin() -> str | None:
    """node 실행 파일 경로. 없으면 None (시험은 그때 건너뛴다)."""
    return shutil.which("node")


def extract_functions(js: str, names) -> str:
    """이름으로 `function <name>(...) {...}` 정의를 잘라 낸다 (중괄호 짝 맞추기)."""
    out = []
    for name in names:
        head = f"function {name}("
        i = js.find(head)
        assert i >= 0, f"JS 에 {name} 정의가 없다"
        j = js.index("{", i)
        depth = 0
        end = -1
        for k in range(j, len(js)):
            c = js[k]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    end = k
                    break
        assert end > 0, f"{name} 의 중괄호가 닫히지 않는다"
        out.append(js[i:end + 1])
    return "\n".join(out)


def run_js(src: str) -> list[str]:
    """node 로 돌리고 stdout 을 줄 목록으로 돌려준다."""
    node = node_bin()
    assert node, "node 가 없다 — 호출 전에 node_bin() 으로 확인할 것"
    path = Path(tempfile.mkdtemp()) / "snippet.js"
    path.write_text(src, encoding="utf-8")
    proc = subprocess.run([node, str(path)], capture_output=True, text=True,
                          timeout=30)
    assert proc.returncode == 0, f"node 실행 실패: {proc.stderr.strip()}"
    return proc.stdout.rstrip("\n").split("\n")
