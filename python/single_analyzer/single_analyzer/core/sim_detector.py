"""Detect simulation files, determine termination status, and assign analysis tier."""
from __future__ import annotations
import re
from pathlib import Path

from ..report.models import SimInfo


def _read_tail(path: Path, n: int = 50) -> str:
    """Read last n lines of a file."""
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            chunk = min(size, n * 120)  # estimate ~120 bytes/line
            f.seek(max(0, size - chunk))
            raw = f.read()
        lines = raw.decode("utf-8", errors="ignore").splitlines()
        return "\n".join(lines[-n:])
    except OSError:
        return ""


def check_termination(sim_dir: Path) -> tuple[bool | None, str]:
    """
    Returns (normal: bool|None, source: str)
    - (True,  "glstat") : 정상 종료
    - (False, "glstat") : 오류 종료
    - (True,  "d3hsp")  : d3hsp에서 확인
    - (None,  "unknown"): 판단 불가 → d3plot 있으면 계속 진행
    """
    # 1. glstat (우선순위 높음)
    for name in ("glstat", "glstat0000"):
        glstat = sim_dir / name
        if glstat.exists():
            tail = _read_tail(glstat, n=50)
            tail_ns = tail.replace(" ", "").lower()
            if "normaltermination" in tail_ns:
                return True, "glstat"
            if "errortermination" in tail_ns:
                return False, "glstat"
            break  # 파일 존재하지만 패턴 없음 → d3hsp로 넘어감

    # 2. d3hsp (보조)
    d3hsp = sim_dir / "d3hsp"
    if d3hsp.exists():
        try:
            # d3hsp는 크므로 마지막 부분만 확인
            tail = _read_tail(d3hsp, n=100)
            if "Normal termination" in tail:
                return True, "d3hsp"
            if "Error termination" in tail:
                return False, "d3hsp"
        except OSError:
            pass

    return None, "unknown"


def find_files(sim_dir: Path) -> SimInfo:
    """
    Scan sim_dir for known LS-DYNA output files.
    Assigns tier based on available files.
    """
    d3plot = _find_d3plot(sim_dir)
    glstat = _find_file(sim_dir, ["glstat", "glstat0000"])
    binout = _find_file(sim_dir, ["binout", "binout0000"])
    matsum = _find_file(sim_dir, ["matsum", "matsum0000"])
    rcforc = _find_file(sim_dir, ["rcforc", "rcforc0000"])
    rwforc = _find_file(sim_dir, ["rwforc", "rwforc0000"])
    spcforc = _find_file(sim_dir, ["spcforc"])
    sleout = _find_file(sim_dir, ["sleout"])
    keyword = _find_keyword(sim_dir)

    normal, source = check_termination(sim_dir)

    info = SimInfo(
        path=sim_dir,
        d3plot=d3plot,
        glstat=glstat,
        binout=binout,
        matsum=matsum,
        rcforc=rcforc,
        rwforc=rwforc,
        spcforc=spcforc,
        sleout=sleout,
        keyword=keyword,
        normal_termination=normal,
        termination_source=source,
    )
    info.tier = _assign_tier(info)
    return info


def find_all(root: Path, recursive: bool = True) -> list[SimInfo]:
    """
    Scan root for all simulation directories (containing d3plot).
    Returns list of SimInfo for each found simulation.
    """
    results = []
    if recursive:
        for d3plot_path in sorted(root.rglob("d3plot")):
            sim_dir = d3plot_path.parent
            results.append(find_files(sim_dir))
    else:
        info = find_files(root)
        if info.d3plot:
            results.append(info)
    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_d3plot(sim_dir: Path) -> Path | None:
    """d3plot 파일 탐색 (파일 or 디렉토리 내)."""
    candidate = sim_dir / "d3plot"
    if candidate.exists():
        return candidate
    # d3plot이 없으면 d3plot01, d3plot_family 등은 unified_analyzer가 처리
    return None


def _find_file(sim_dir: Path, names: list[str]) -> Path | None:
    for name in names:
        p = sim_dir / name
        if p.exists():
            return p
    return None


def _find_keyword(sim_dir: Path) -> Path | None:
    """키워드 파일 탐색 (.k, .key, .dyn)."""
    for ext in ("*.k", "*.key", "*.dyn", "*.inp"):
        matches = list(sim_dir.glob(ext))
        if matches:
            # 메인 파일 우선 (이름에 'main' 또는 '01_' 포함)
            for m in matches:
                if "main" in m.stem.lower() or m.stem.startswith("01_"):
                    return m
            return matches[0]
    return None


def _assign_tier(info: SimInfo) -> int:
    if info.normal_termination is False:
        return 0
    if info.d3plot is None:
        return 0
    if info.binout and (info.rcforc or info.rwforc or info.matsum):
        return 4
    if info.binout:
        return 3
    if info.glstat:
        return 2
    return 1
