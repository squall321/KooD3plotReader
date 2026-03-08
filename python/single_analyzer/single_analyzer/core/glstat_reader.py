"""Parse LS-DYNA glstat ASCII output file."""
from __future__ import annotations
import re
from pathlib import Path

from ..report.models import GlstatData


# glstat 블록 구분 (점 개수는 버전마다 2~30개 이상 다양)
_RE_TIME = re.compile(r"time\.{2,}\s+([\d.Ee+\-]+)")
_RE_KINETIC = re.compile(r"kinetic energy\.{2,}\s+([\d.Ee+\-]+)")
_RE_INTERNAL = re.compile(r"internal energy\.{2,}\s+([\d.Ee+\-]+)")
_RE_HOURGLASS = re.compile(r"hourglass energy\s*\.{2,}\s*([\d.Ee+\-]+)")
# "total energy / initial energy" 보다 앞에 있는 "total energy" 라인만 매칭
_RE_TOTAL = re.compile(r"^ *total energy\.{2,}\s+([\d.Ee+\-]+)", re.MULTILINE)
_RE_ENERGY_RATIO = re.compile(r"total energy / initial energy\.{2,}\s+([\d.Ee+\-]+)")
_RE_MASS = re.compile(r"added mass\s*\.{2,}\s*([\d.Ee+\-]+)")


def parse_glstat(path: Path) -> GlstatData | None:
    """
    Parse glstat file. Returns None if file doesn't exist or is unreadable.
    Never raises — any parse error yields a partial or empty GlstatData.
    """
    if not path or not path.exists():
        return None

    try:
        text = path.read_text(errors="ignore")
    except OSError:
        return None

    data = GlstatData()

    # --- termination 판단 (마지막 50줄) ---
    lines = text.splitlines()
    tail_ns = "\n".join(lines[-50:]).replace(" ", "").lower()
    if "normaltermination" in tail_ns:
        data.normal_termination = True
    elif "errortermination" in tail_ns:
        data.normal_termination = False
    else:
        data.normal_termination = None

    # --- 블록 파싱 ---
    # glstat은 동일 패턴 블록이 반복. "time..." 출현마다 하나의 블록.
    # 블록을 시간 기준으로 분리: "time..." 라인을 앵커로.
    blocks = _split_blocks(text)
    for block in blocks:
        t = _extract(block, _RE_TIME)
        if t is None:
            continue
        data.t.append(t)
        data.kinetic_energy.append(_extract(block, _RE_KINETIC) or 0.0)
        data.internal_energy.append(_extract(block, _RE_INTERNAL) or 0.0)
        data.hourglass_energy.append(_extract(block, _RE_HOURGLASS) or 0.0)
        total = _extract(block, _RE_TOTAL)
        data.total_energy.append(total or 0.0)

        ratio = _extract(block, _RE_ENERGY_RATIO)
        if ratio is not None:
            data.energy_ratio.append(ratio)
        elif total and total > 0 and data.internal_energy:
            data.energy_ratio.append(data.internal_energy[-1] / total)
        else:
            data.energy_ratio.append(0.0)

        mass = _extract(block, _RE_MASS)
        data.mass.append(mass or 0.0)

    return data if data.t else GlstatData(normal_termination=data.normal_termination)


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _split_blocks(text: str) -> list[str]:
    """
    글stat 텍스트를 "time..." 라인 기준으로 블록 분리.
    각 블록은 해당 time... 라인부터 다음 time... 라인 직전까지.
    """
    # time 라인 위치 찾기
    lines = text.splitlines(keepends=True)
    block_starts: list[int] = []
    for i, line in enumerate(lines):
        if re.match(r"\s*time\.{3,}", line):
            block_starts.append(i)

    if not block_starts:
        return []

    blocks: list[str] = []
    for idx, start in enumerate(block_starts):
        end = block_starts[idx + 1] if idx + 1 < len(block_starts) else len(lines)
        blocks.append("".join(lines[start:end]))
    return blocks


def _extract(block: str, pattern: re.Pattern) -> float | None:
    m = pattern.search(block)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None
