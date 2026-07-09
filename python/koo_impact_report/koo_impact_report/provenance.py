# 보고서 출처 메타데이터(도구 버전/SIF/타임스탬프/입력 digest)를 수집하는 모듈
"""Provenance — 이 보고서가 "언제, 무엇으로, 어떤 입력에서" 만들어졌는지.

CLI(__main__) 레이어에서만 주입한다 — loader 는 채우지 않는다. 골든 회귀
테스트는 loader→generate_html 를 직접 호출하므로 타임스탬프가 골든 바이트를
깨지 않는다 (SOTA P2-5).
"""
from __future__ import annotations

import hashlib
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import __version__


def _read_module_version() -> dict:
    """설치된 모듈의 VERSION 파일 파싱 (SIF 내 /opt/kood3plot/VERSION).

    scripts/build_module.sh 가 생성하는 "Version: <git-describe>" /
    "Built: <UTC>" 라인만 취한다. 파일이 없으면(개발 호스트) 빈 dict.
    """
    candidates = []
    home = os.environ.get("KOOD3PLOT_HOME")
    if home:
        candidates.append(Path(home) / "VERSION")
    candidates.append(Path("/opt/kood3plot/VERSION"))
    for vf in candidates:
        try:
            if not vf.is_file():
                continue
            out: dict = {}
            for line in vf.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith("Version:"):
                    out["module_version"] = line.split(":", 1)[1].strip()
                elif line.startswith("Built:"):
                    out["module_built"] = line.split(":", 1)[1].strip()
            if out:
                return out
        except OSError:
            continue
    return {}


def _input_digest(report) -> dict:
    """입력 데이터셋 지문 — run 별 analysis_result.json 의 (이름, size, mtime).

    내용 해시가 아니라 stat 기반이라 수백 run 에서도 ~ms. 같은 test_dir 를
    같은 상태로 다시 돌리면 같은 digest, 어느 run 하나라도 재해석되면 변한다.
    """
    lines: list[str] = []
    n_runs = 0
    for positions in (report.positions_by_face or {}).values():
        for pos in positions or []:
            rd = getattr(pos, "run_dir", None)
            if rd is None:
                continue
            n_runs += 1
            try:
                ar = Path(rd) / "analysis_result.json"
                st = ar.stat()
                lines.append(f"{Path(rd).name}:{st.st_size}:{st.st_mtime_ns}")
            except OSError:
                lines.append(f"{Path(rd).name}:missing")
    h = hashlib.sha256("\n".join(sorted(lines)).encode()).hexdigest()[:16]
    return {"digest": h, "n_runs": n_runs}


def build_provenance(report, argv: list[str] | None = None) -> dict:
    """report 에 부착할 provenance dict 를 조립한다."""
    prov = {
        "tool": "koo_impact_report",
        "tool_version": __version__,
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python": platform.python_version(),
        "host": platform.node(),
        "argv": list(argv if argv is not None else sys.argv[1:]),
        "test_dir": str(report.test_dir or ""),
        "input": _input_digest(report),
    }
    prov.update(_read_module_version())
    return prov
