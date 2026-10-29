# 파트별 항복 한계를 읽고 안전율을 내는 모듈 — **환산하지 않는 것**이 핵심이다
"""파트별 항복응력 (part_yield / --yield-map).

이 도구는 **응력을 환산하지 않는다.** 단위 검출 결과는 G 환산 계수와 표기
라벨에만 쓰이고 `peak_stress` 는 덱 단위 그대로 나간다
(`tests/test_sidecar_units.py` 가 못박고 있다). 안전율은 **비율**이라
양쪽이 덱 단위면 단위가 약분된다 — 그래서 맵 값도 **덱 단위 그대로** 둔다.

환산을 넣으면 오히려 위험하다. 단위 검출(`loader._detect_deck_units`)은
**미검출로 떨어지는 경로가 넷**이다(밀도 못 읽음 / 검출기 임포트 실패 /
밀도 애매 / ENDTIM 수상). 지금은 그 불확실성이 peak-G·라벨에만 머무는데,
안전율 경로에 끌어들이면 "검출 실패 → 1e6 배 틀린 안전율" 이 된다.

예외가 하나 있다. `--yield-stress` 는 **사람이 손으로 넣는 MPa** 다. 덱 단위로
재해석하면 SI 덱에서 "350 Pa" 라는 무의미한 값이 되므로, 이것만은 덱 단위로
환산해 쓴다. 단위를 모르면 **환산하지 않고 비교를 건너뛴다** — 모르는 채로
합부를 판정하느니 판정하지 않는 쪽이 낫다.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

#: 한계를 어느 응력과 비교할지. KMM 이 재료에서 정해 보낸다.
VON_MISES = "von_mises"
MAX_PRINCIPAL = "max_principal"

#: criterion → PartResult 에서 그 피크를 꺼내는 법.
#: 미계측이면 None 을 돌려준다 — **다른 양으로 대체하지 않는다.**
_MEASURE = {
    VON_MISES: lambda pr: pr.peak_stress,
    MAX_PRINCIPAL: lambda pr: pr.peak_principal,
}

#: 덱 응력 단위 라벨 → MPa 로 적힌 값을 덱 단위로 바꾸는 배수.
#: SI 덱은 Pa, mm-tonne 계열은 MPa (koo_impact_report 의 프리셋과 같다).
_MPA_TO_DECK = {"MPa": 1.0, "Pa": 1e6}


@dataclass
class YieldLimit:
    """한 파트의 항복 한계 하나. 값은 **덱 단위**다."""
    value: float
    criterion: str
    source: str = ""


@dataclass
class PartYield:
    """한 파트의 한계 모음."""
    part_id: int
    limits: list[YieldLimit] = field(default_factory=list)


@dataclass
class YieldVerdict:
    """한 파트의 안전율 판정.

    `complete=False` 는 "안전율을 못 냈다" 가 아니라 **"한계 일부를 못 쟀다"**
    는 뜻이다. 그 경우 남은 한계로 낸 안전율은 **실제보다 큰 쪽**이다 —
    구속하는 한계가 빠졌을 수 있기 때문이다. 그래서 CRITICAL 로 단정하지
    않는다. 놓치는 방향이 위험한 쪽이다.
    """
    sf: float | None = None
    binding: YieldLimit | None = None     # 안전율을 정한 한계
    measured: float | None = None         # 그 기준의 관측 피크
    complete: bool = True
    skipped: list[str] = field(default_factory=list)   # 사람에게 보일 사유


def _parse_limits(pid: int, entry: dict) -> tuple[PartYield, list[str]]:
    """맵 한 항목 → PartYield. 모르는 criterion 은 **추측하지 않고** 뺀다."""
    notes: list[str] = []
    lims: list[YieldLimit] = []
    raw = entry.get("limits")
    if isinstance(raw, list) and raw:
        for it in raw:
            if not isinstance(it, dict):
                continue
            try:
                v = float(it.get("value"))
            except (TypeError, ValueError):
                continue
            crit = str(it.get("criterion") or VON_MISES)
            if crit not in _MEASURE:
                notes.append(f"파트 {pid}: 모르는 기준 '{crit}' — 그 한계를 뺐습니다")
                continue
            lims.append(YieldLimit(v, crit, str(it.get("source") or "")))
    else:
        # 옛 맵(KMM v126 이전)에는 limits 가 없다 — yield 를 von Mises 로 본다.
        try:
            v = float(entry.get("yield"))
        except (TypeError, ValueError):
            return PartYield(pid), notes
        crit = str(entry.get("criterion") or VON_MISES)
        if crit not in _MEASURE:
            notes.append(f"파트 {pid}: 모르는 기준 '{crit}' — 그 파트를 뺐습니다")
            return PartYield(pid), notes
        lims.append(YieldLimit(v, crit, str(entry.get("source") or "")))
    return PartYield(pid, lims), notes


def _parse_block(block: dict, where: str) -> tuple[dict[int, PartYield], list[str]]:
    """`{"unit":…, "parts":{pid:{…}}}` 블록을 푼다."""
    notes: list[str] = []
    out: dict[int, PartYield] = {}
    parts = block.get("parts")
    if not isinstance(parts, dict):
        return out, [f"{where}: parts 가 없습니다"]
    for pid_s, entry in parts.items():
        try:
            pid = int(pid_s)
        except (TypeError, ValueError):
            continue
        if not isinstance(entry, dict):
            continue
        py, ns = _parse_limits(pid, entry)
        notes.extend(ns)
        if py.limits:
            out[pid] = py
    return out, notes


def load_from_dropset(output_dir: Path) -> tuple[dict[int, PartYield], str | None, list[str]]:
    """첫 **읽히는** DropSet.json 의 `model.part_yield` 를 읽는다.

    반환: (파트별 한계, 맵이 말한 단위 힌트, 사람에게 보일 사유들)
    키가 없으면 빈 dict — 옛 산출물에는 원래 없다(결함이 아니다).
    """
    notes: list[str] = []
    if not output_dir.is_dir():
        return {}, None, notes
    for run_dir in sorted(output_dir.iterdir()):
        ds = run_dir / "DropSet.json"
        if not ds.exists():
            continue
        try:
            d = json.loads(ds.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue          # 깨진 것은 건너뛴다 (loader 가 이미 사유를 찍는다)
        block = (d.get("model") or {}).get("part_yield")
        if not isinstance(block, dict):
            return {}, None, notes      # 첫 읽히는 것에 없으면 캠페인에 없는 것
        out, ns = _parse_block(block, "DropSet.json 의 model.part_yield")
        unit = block.get("unit")
        return out, (str(unit) if unit else None), notes + ns
    return {}, None, notes


def load_from_file(path: str | Path) -> tuple[dict[int, PartYield], str | None, list[str]]:
    """`--yield-map FILE` — 명시적 덮어쓰기. 값은 **덱 단위**다(MPa 아님)."""
    p = Path(path)
    d = json.loads(p.read_text(encoding="utf-8"))
    out, notes = _parse_block(d, f"{p.name}")
    unit = d.get("unit")
    return out, (str(unit) if unit else None), notes


def default_limit(default_mpa: float, stress_label: str) -> tuple[YieldLimit | None, str | None]:
    """`--yield-stress`(MPa) → 덱 단위 한계. 못 바꾸면 (None, 사유).

    단위를 모르면 **환산하지 않는다.** 모르는 채로 합부를 판정하느니
    판정하지 않고 사유를 말하는 쪽이 낫다.
    """
    if not (default_mpa > 0):
        return None, None
    f = _MPA_TO_DECK.get(stress_label or "")
    if f is None:
        return None, ("덱 응력 단위를 판정하지 못해 --yield-stress "
                      f"{default_mpa:g} MPa 를 덱 단위로 바꿀 수 없습니다")
    return YieldLimit(default_mpa * f, VON_MISES,
                      f"--yield-stress {default_mpa:g} MPa"), None


def evaluate(limits: list[YieldLimit], peaks: dict[str, float | None]) -> YieldVerdict:
    """한계마다 안전율을 내고 **작은 쪽**을 고른다.

    σ1 과 σvm 에는 대소가 없다. 하나만 보면 삼축 인장에서 파괴응력을,
    일축 압축에서 항복을 놓친다 — 그래서 전부 보고 최소를 쓴다.

    측도가 없는 기준은 건너뛰되 `complete=False` 로 표시한다. 조용히 빼면
    남은 한계로 낸 **더 큰** 안전율이 사실처럼 읽힌다.
    """
    v = YieldVerdict()
    for lim in limits:
        obs = peaks.get(lim.criterion)
        if obs is None:
            v.complete = False
            v.skipped.append(f"{lim.criterion} 미계측 — 한계 {lim.value:g}"
                             + (f" ({lim.source})" if lim.source else "")
                             + " 를 보지 못했습니다")
            continue
        if not (obs > 0):
            continue                      # 응력이 안 잡힌 파트는 판정 대상이 아니다
        sf = lim.value / obs
        if v.sf is None or sf < v.sf:
            v.sf, v.binding, v.measured = sf, lim, obs
    return v


def sanity_note(part_yields: dict[int, PartYield],
                observed: dict[int, float]) -> str | None:
    """맵이 응력이 아닌 값을 담고 있지 않은지 **자릿수만** 본다.

    계기 — KMM 의 `*MAT_PIECEWISE_LINEAR_PLASTICITY` 비-`_TITLE` 변종에서
    EPS 와 ES 가 뒤바뀐 적이 있다. 그러면 항복값 자리에 변형률(0.01 수준)이
    들어와 **거의 모든 각도가 "항복 초과"** 로 뜬다. 그럴듯하게 틀린 모양이라
    눈치채기 어렵다.

    재료 지식을 박아 넣지 않는다 — 관측 응력과 비교해 **전부** 3자릿수 이상
    아래일 때만 말한다. 그래야 이번 뒤바뀜뿐 아니라 같은 부류를 잡고,
    단위가 다른 정상 덱을 오경보하지 않는다.
    """
    pairs = [(py, observed.get(pid)) for pid, py in part_yields.items()]
    pairs = [(py, o) for py, o in pairs if o and o > 0 and py.limits]
    if len(pairs) < 2:
        return None                        # 표본이 적으면 단정하지 않는다
    if not all(max(l.value for l in py.limits) * 1000.0 < o for py, o in pairs):
        return None
    return ("⚠ 항복 맵의 값이 관측 응력보다 전 파트에서 1000배 이상 작습니다 — "
            "응력이 아닌 값(변형률 등)이 들어왔을 수 있습니다. "
            "맵을 만든 쪽의 단위와 커브 해석을 확인하세요.")
