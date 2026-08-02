# 대용량 셀에서 프로파일만 축소하는 tier 정책 — 셀 수 기준 tier 표의 단일 소스
"""tier 정책.

**무엇이 무거운가.** 합성 지도(winner/trend/Δ/spread)는 셀당 스칼라 몇 개라
셀이 3000개여도 payload 가 가볍다. 무거운 것은 **전개 프로파일**이 그리는
per-cell × per-rev 값 계열이다(N개 리비전 × 셀 수). 따라서 tier 는 프로파일이
무엇을 그릴지만 줄이고, ``cells[]`` 자체는 손대지 않는다 — probe 와 지도 4종이
전량을 소비하기 때문이다. 즉 여기서 만드는 것은 **데이터 삭제가 아니라 표시 힌트**다.

tier 표 (셀 수 기준, 이 표가 단일 소스)

===== ============ ====================================================
tier  셀 수         프로파일 정책
===== ============ ====================================================
A     ≤ 200        전량 인라인 (축소 없음)
B     ≤ 800        top-K 400 + 나머지는 집계 밴드
C     ≤ 2000       top-K 300 + 나머지는 집계 밴드
D     > 2000       top-K 200 + 나머지는 집계 밴드
===== ============ ====================================================

지도는 어느 tier 에서도 축소하지 않는다 (원래 집계라 가볍다).
"""
from __future__ import annotations

from statistics import median as _median

#: (tier 이름, 셀 수 상한(포함, None=무한), 프로파일 top-K(None=전량))
TIER_TABLE = (
    ("A", 200, None),
    ("B", 800, 400),
    ("C", 2000, 300),
    ("D", None, 200),
)

#: 선정 예산 배분 — 심각도 60%, 리비전별 winner 20%, |trend| 20% (나머지는 심각도로 채움)
QUOTA_SEVERITY = 0.6
QUOTA_WINNER = 0.2


def _ceil(x: float) -> int:
    i = int(x)
    return i if i == x else i + 1


def tier_for(n_cells: int):
    """셀 수 → (tier 이름, 프로파일 top-K). top_k 가 None 이면 축소 없음."""
    for name, upper, top_k in TIER_TABLE:
        if upper is None or n_cells <= upper:
            return name, top_k
    return TIER_TABLE[-1][0], TIER_TABLE[-1][2]


def _rev_value(cell: dict, i: int):
    per = cell.get("per_rev") or []
    if i < 0 or i >= len(per):
        return None
    v = (per[i] or {}).get("value")
    return v if isinstance(v, (int, float)) else None


def _desc(idxs, value_of, keys):
    """값 내림차순 정렬. 값 없는 셀은 뒤로, 동점은 cell key 사전순 (결정적)."""
    return sorted(
        idxs,
        key=lambda i: (
            -(value_of(i) if value_of(i) is not None else float("-inf")),
            keys[i],
        ),
    )


def select_profile_cells(cells: list, baseline_idx: int, n_rev: int, top_k: int) -> dict:
    """프로파일에 그릴 셀을 top_k 개 고른다 — "이야기가 있는 셀"이 반드시 살아남게.

    선정 규칙 (순서대로, 이미 뽑힌 셀은 건너뛰며, 총합이 top_k 를 넘지 않는다)

    0. **앵커** — 각 리비전이 전 셀 중 최대값을 낸 셀(리비전당 1개). 보고서의
       worst KPI 가 가리키는 바로 그 셀이므로 무조건 포함한다.
    1. **심각도** — baseline 값 내림차순 상위 ``ceil(0.6 × top_k)`` 개.
       프로파일의 기본 X 정렬이 baseline 심각도순이므로 왼쪽(최악) 구간이 촘촘해진다.
    2. **winner** — 리비전 r 이 최악인 셀들 중 그 리비전 값 상위. 예산
       ``floor(0.2 × top_k)`` 를 리비전 수로 균등 분배(리비전당 최소 1개).
       "이 리비전만 유독 나쁜 방향"이 사라지지 않게 한다.
    3. **trend** — |trend| 내림차순 상위. 남은 예산 전부. 개선/악화 폭이 큰,
       설계 반복의 이야기가 있는 셀이다.
    4. **충원** — 그래도 top_k 에 못 미치면 심각도 순으로 채운다.

    동점·값 없음의 처리는 결정적이다(값 없음은 뒤로, 동점은 cell key 사전순).

    반환: ``{"keys": [...], "reasons": {key: 선정사유}, "counts": {사유: 개수}}``
    """
    n = len(cells)
    keys = [str(c.get("key")) for c in cells]
    idxs = list(range(n))

    picked: list = []
    reasons: dict = {}

    def take(order, quota, why):
        got = 0
        for i in order:
            if got >= quota or len(picked) >= top_k:
                break
            if keys[i] in reasons:
                continue
            reasons[keys[i]] = why
            picked.append(i)
            got += 1

    # 0. 앵커 — 리비전별 최대값 셀
    for r in range(n_rev):
        best_i, best_v = None, None
        for i in idxs:
            v = _rev_value(cells[i], r)
            if v is None:
                continue
            if best_v is None or v > best_v or (v == best_v and keys[i] < keys[best_i]):
                best_i, best_v = i, v
        if best_i is not None:
            take([best_i], 1, "anchor")

    sev_order = _desc(idxs, lambda i: _rev_value(cells[i], baseline_idx), keys)

    # 1. 심각도
    take(sev_order, _ceil(QUOTA_SEVERITY * top_k), "severity")

    # 2. 리비전별 winner
    win_budget = int(QUOTA_WINNER * top_k)
    per_rev_quota = max(1, win_budget // max(n_rev, 1))
    for r in range(n_rev):
        win_idx = [i for i in idxs if cells[i].get("winner") == r]
        take(_desc(win_idx, lambda i: _rev_value(cells[i], r), keys), per_rev_quota, "winner")

    # 3. |trend|
    def _abs_trend(i):
        t = cells[i].get("trend")
        return abs(t) if isinstance(t, (int, float)) else None

    take(_desc(idxs, _abs_trend, keys), top_k, "trend")

    # 4. 충원 (심각도 순)
    take(sev_order, top_k, "fill")

    counts: dict = {}
    for why in reasons.values():
        counts[why] = counts.get(why, 0) + 1
    return {
        "keys": [keys[i] for i in picked],
        "reasons": reasons,
        "counts": counts,
    }


def _band(values: list) -> dict:
    """값 목록 → {min, median, max}. 값이 없으면 전부 None."""
    vs = [v for v in values if isinstance(v, (int, float))]
    if not vs:
        return {"min": None, "median": None, "max": None}
    return {"min": min(vs), "median": float(_median(vs)), "max": max(vs)}


def _aggregate(rest: list, n_rev: int) -> dict:
    """표시되지 않는 셀들의 리비전별 min/median/max 밴드.

    - ``value`` 밴드는 게이트 여부와 무관하게 **측정값 전부**로 만든다
      (값 자체는 측정된 것이고, 신뢰 게이트가 막는 것은 Δ 판정이다).
    - ``delta_pct`` 밴드는 미판정 셀을 제외한다 (오염된 Δ 를 섞지 않는다).
    """
    val = {"min": [], "median": [], "max": []}
    dlt = {"min": [], "median": [], "max": []}
    for r in range(n_rev):
        b = _band([_rev_value(c, r) for c in rest])
        for k in val:
            val[k].append(b[k])
        d = _band(
            [
                (c.get("delta_pct") or [None] * n_rev)[r] if not c.get("gated") else None
                for c in rest
            ]
        )
        for k in dlt:
            dlt[k].append(d[k])
    return {
        "n": len(rest),
        "n_gated": sum(1 for c in rest if c.get("gated")),
        "value": val,
        "delta_pct": dlt,
    }


def build_tier_plan(cells: list, baseline_idx: int, n_rev: int) -> dict:
    """셀 목록 → 프로파일 축소 계획 (payload 계약의 tier/profile_cells/profile_aggregate).

    축소가 필요 없으면(tier A 또는 셀 수 ≤ top_k) profile_cells / profile_aggregate 는
    None 이고, 보고서는 전량을 그린다.
    """
    n_cells = len(cells)
    name, top_k = tier_for(n_cells)
    tier = {
        "name": name,
        "n_cells": n_cells,
        "top_k": top_k,
        "n_shown": n_cells,
        "n_aggregated": 0,
        "reduced": False,
        "selection": {},
        "rule": (
            f"tier {name} (셀 {n_cells}개) — "
            + ("프로파일 전량 인라인" if top_k is None else f"프로파일 top-K {top_k}")
            + ". 지도/probe 는 어느 tier 에서도 축소하지 않는다"
        ),
    }
    if top_k is None or n_cells <= top_k:
        return {"tier": tier, "profile_cells": None, "profile_aggregate": None}

    sel = select_profile_cells(cells, baseline_idx, n_rev, top_k)
    shown = set(sel["keys"])
    rest = [c for c in cells if str(c.get("key")) not in shown]
    tier.update(
        {
            "n_shown": len(sel["keys"]),
            "n_aggregated": len(rest),
            "reduced": True,
            "selection": sel["counts"],
        }
    )
    return {
        "tier": tier,
        "profile_cells": sel["keys"],
        "profile_aggregate": _aggregate(rest, n_rev),
    }
