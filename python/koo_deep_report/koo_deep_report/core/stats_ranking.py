# 순위 검정·상관·회수율 — 귀무가설을 코드에 고정해 매번 고르지 않게 하는 모듈
"""캠페인 정합성 판정에 쓰는 통계.

**왜 이 모듈이 있나.**
2026-09 정합성 검증에서 평균순위를 *최소순위* 귀무 `(N+1)/(k+1)` 와 비교해
"면별 정합은 랜덤 수준" 이라고 잘못 결론냈다. 올바른 귀무는 `(N+1)/2` 이고,
고치니 F1_Back 이 4과제 중 3개에서 1위, p=0.016 으로 결론이 뒤집혔다.
귀무가설을 사람이 매번 고르는 구조면 또 틀린다 — 여기서 **코드로 고정**한다.

**설계 규칙.**
- 예외를 던지지 않는다. 계산할 수 없으면 결과에 사유를 담아 돌려준다.
  (보고서 생성 중 예외가 나면 리포트 전체가 죽는다.)
- 계산하지 못한 값은 `None` 이다. 0 으로 채우지 않는다.
- 근사를 썼으면 `method` 에 적는다. 정확값인 척하지 않는다.
- 의존은 numpy 하나. scipy 는 시험에서 대조용으로만 쓴다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

try:
    import numpy as np
except ImportError:          # numpy 는 이 저장소의 필수 의존이지만 방어적으로
    np = None                # 두어, import 만으로 리포트가 죽지 않게 한다


# ── 평균순위 검정 ────────────────────────────────────────────────────

#: 정확 분포를 동적계획법으로 구할 때 허용하는 최대 연산 수.
#: 넘으면 정규근사로 떨어지고 그 사실을 method 에 적는다.
_EXACT_MAX_OPS = 5_000_000


@dataclass
class MeanRankResult:
    """평균순위 검정 결과. 계산 못 한 값은 None 이다."""
    n_trials: int = 0               #: 시행 수 k (과제 수 등)
    n_items: int = 0                #: 각 시행의 후보 수 N (면 수 등)
    mean_rank: float | None = None  #: 관측 평균순위
    null_expected: float | None = None  #: 귀무 기대값 (N+1)/2
    p_value: float | None = None    #: 단측 p — "이보다 좋은(작은) 평균순위가 우연히 나올 확률"
    method: str = ""                #: "exact" | "normal_approx" | "" (계산 못 함)
    note: str = ""                  #: 계산하지 못한 사유
    #: 귀무가설을 사람이 아니라 코드가 정했음을 산출물에 남긴다
    null_hypothesis: str = "각 시행의 순위가 1..N 에서 균등·독립 (평균순위 기대값 (N+1)/2)"


def mean_rank_test(ranks, n_items: int) -> MeanRankResult:
    """관심 대상의 평균순위가 우연보다 좋은지 검정한다.

    Args:
        ranks: 시행별 순위 (1-based). 예) 4개 과제에서 F1_Back 의 순위 [1, 1, 3, 1]
        n_items: 각 시행의 후보 수 N (예: 면 6개)

    Returns:
        MeanRankResult. 단측 p 는 `P(평균순위 ≤ 관측값)` 이다 —
        **작을수록** 유의하다(순위는 작을수록 위험이 크다는 뜻이므로).

    🔴 귀무 기대값은 `(N+1)/2` 다. `(N+1)/(k+1)` 은 **k개 중 최솟값**의 기대값이라
       평균순위와 비교하면 안 된다. 이 혼동이 실제로 잘못된 결론을 만들었다.
    """
    res = MeanRankResult()

    # ── 입력 검사 — 조용히 0 을 만들지 않는다 ──
    try:
        rs = [int(r) for r in ranks]
    except (TypeError, ValueError):
        res.note = "순위 목록이 정수로 해석되지 않습니다"
        return res
    try:
        N = int(n_items)
    except (TypeError, ValueError):
        res.note = "n_items 가 정수가 아닙니다"
        return res

    res.n_trials = len(rs)
    res.n_items = N
    if N < 1:
        res.note = f"후보 수가 {N} 입니다 (1 이상이어야 합니다)"
        return res
    if not rs:
        res.note = "시행이 없습니다"
        return res
    bad = [r for r in rs if r < 1 or r > N]
    if bad:
        res.note = f"순위가 1..{N} 범위를 벗어납니다 (예: {bad[:3]})"
        return res

    k = len(rs)
    s_obs = sum(rs)
    res.mean_rank = s_obs / k
    res.null_expected = (N + 1) / 2.0      # ← 코드에 고정된 귀무

    if N == 1:
        # 후보가 하나면 순위는 항상 1 — 검정할 것이 없다
        res.p_value = 1.0
        res.method = "degenerate"
        res.note = "후보가 1개라 순위에 정보가 없습니다"
        return res

    # ── 정확 분포 (동적계획법) ──
    # 귀무 하에서 합 S = Σ r_i, 각 r_i ~ Uniform{1..N} 독립.
    # 누적합 슬라이딩으로 한 시행당 O(범위) — 카운트는 Python int 라 오차가 없다.
    span = k * (N - 1) + 1                 # 가능한 합의 가짓수
    ops = k * span
    if ops <= _EXACT_MAX_OPS:
        # dist[j] = 합이 (k_done + j) 일 경우의 수 — 오프셋을 빼서 배열을 작게 쓴다
        dist = [1]
        for _ in range(k):
            new = [0] * (len(dist) + N - 1)
            run = 0
            for i in range(len(new)):
                if i < len(dist):
                    run += dist[i]
                if i - N >= 0:
                    run -= dist[i - N]
                new[i] = run
            dist = new
        total = N ** k
        idx = s_obs - k                    # 합의 최솟값이 k 이므로 오프셋
        cum = sum(dist[: idx + 1])
        res.p_value = cum / total
        res.method = "exact"
        return res

    # ── 정규근사 (연속성 보정) ──
    mu = k * (N + 1) / 2.0
    var = k * (N * N - 1) / 12.0
    if var <= 0:
        res.p_value = 1.0
        res.method = "degenerate"
        res.note = "귀무 분산이 0 입니다"
        return res
    z = (s_obs + 0.5 - mu) / math.sqrt(var)
    res.p_value = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
    res.method = "normal_approx"
    res.note = (f"정확 분포 연산량이 {ops:,} 로 상한 {_EXACT_MAX_OPS:,} 를 넘어 "
                f"정규근사를 썼습니다")
    return res


# ── Spearman 순위상관 ────────────────────────────────────────────────

@dataclass
class SpearmanResult:
    n: int = 0
    rho: float | None = None
    note: str = ""


def _rankdata(a) -> list[float]:
    """동점은 평균 순위로 — scipy.stats.rankdata(method='average') 와 같은 규칙."""
    n = len(a)
    order = sorted(range(n), key=lambda i: a[i])
    out = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and a[order[j + 1]] == a[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0          # 1-based 평균 순위
        for t in range(i, j + 1):
            out[order[t]] = avg
        i = j + 1
    return out


def spearman(x, y) -> SpearmanResult:
    """Spearman 순위상관 ρ. 동점은 평균 순위로 처리한다.

    표본이 2 미만이거나 한쪽이 전부 같은 값이면 ρ 는 정의되지 않는다 —
    0 을 돌려주면 "상관 없음" 으로 오독되므로 None 을 돌려준다.
    """
    res = SpearmanResult()
    try:
        xs = [float(v) for v in x]
        ys = [float(v) for v in y]
    except (TypeError, ValueError):
        res.note = "숫자로 해석되지 않는 값이 있습니다"
        return res
    if len(xs) != len(ys):
        res.note = f"길이가 다릅니다 ({len(xs)} vs {len(ys)})"
        return res
    # NaN 은 쌍 단위로 제외한다 (한쪽만 결측인 쌍을 반만 쓰면 짝이 어긋난다)
    pairs = [(a, b) for a, b in zip(xs, ys)
             if not (math.isnan(a) or math.isnan(b))]
    res.n = len(pairs)
    if res.n < 2:
        res.note = f"유효 표본이 {res.n} 개입니다 (2 이상 필요)"
        return res
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]

    rx = _rankdata(xs)
    ry = _rankdata(ys)
    n = res.n
    mx = sum(rx) / n
    my = sum(ry) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sxx = sum((a - mx) ** 2 for a in rx)
    syy = sum((b - my) ** 2 for b in ry)
    if sxx <= 0 or syy <= 0:
        res.note = "한쪽 값이 전부 같아 순위상관이 정의되지 않습니다"
        return res
    res.rho = sxy / math.sqrt(sxx * syy)
    return res


# ── 회수율 recall@k ──────────────────────────────────────────────────

@dataclass
class RecallResult:
    k: int = 0
    n_candidates: int = 0
    n_positive: int = 0
    n_hit: int = 0
    recall: float | None = None
    baseline: float | None = None   #: 무작위로 k 개 골랐을 때의 기대 회수율 k/N
    note: str = ""


def recall_at_k(scores, positives, k: int, higher_is_worse: bool = True) -> RecallResult:
    """상위 k 개를 검사했을 때 실제 불량을 몇 개 잡는가.

    Args:
        scores: 후보별 위험도 점수
        positives: 같은 길이의 bool — 실제 불량 여부
        k: 검사할 상위 개수
        higher_is_worse: 점수가 클수록 위험하면 True (압축 기준이면 False)

    동점은 **불리하게** 처리한다 — 경계에서 동점이면 양성이 뒤로 가도록 정렬해,
    회수율을 우연히 부풀리지 않는다.
    """
    res = RecallResult()
    try:
        sc = [float(v) for v in scores]
        pos = [bool(v) for v in positives]
    except (TypeError, ValueError):
        res.note = "점수나 양성 표시를 해석하지 못했습니다"
        return res
    if len(sc) != len(pos):
        res.note = f"길이가 다릅니다 ({len(sc)} vs {len(pos)})"
        return res
    keep = [i for i in range(len(sc)) if not math.isnan(sc[i])]
    res.n_candidates = len(keep)
    res.n_positive = sum(1 for i in keep if pos[i])
    try:
        res.k = int(k)
    except (TypeError, ValueError):
        res.note = "k 가 정수가 아닙니다"
        return res
    if res.n_candidates == 0:
        res.note = "유효한 후보가 없습니다"
        return res
    if res.k < 1 or res.k > res.n_candidates:
        res.note = f"k={res.k} 가 1..{res.n_candidates} 범위를 벗어납니다"
        return res
    if res.n_positive == 0:
        res.note = "양성(실제 불량)이 없어 회수율이 정의되지 않습니다"
        return res

    # 위험한 순서로 정렬. 동점이면 양성을 뒤로 (양성 우선 = 과대평가)
    keep.sort(key=lambda i: (-sc[i] if higher_is_worse else sc[i], pos[i]))
    top = keep[: res.k]
    res.n_hit = sum(1 for i in top if pos[i])
    res.recall = res.n_hit / res.n_positive
    res.baseline = res.k / res.n_candidates
    return res


# ── 구간 프로파일 ────────────────────────────────────────────────────

@dataclass
class BinProfile:
    edges: list[float] = field(default_factory=list)
    counts: list[int] = field(default_factory=list)
    means: list[float | None] = field(default_factory=list)
    note: str = ""


def bin_profile(x, y, edges) -> BinProfile:
    """x 를 구간으로 나눠 각 구간의 y 평균을 낸다 (편차각 ↔ 응력 프로파일용).

    빈 구간의 평균은 `None` 이다 — 0 으로 채우면 "값이 0" 으로 읽힌다.
    구간은 `[edge[i], edge[i+1])`, 마지막 구간만 오른쪽을 포함한다.
    """
    prof = BinProfile()
    try:
        xs = [float(v) for v in x]
        ys = [float(v) for v in y]
        eg = [float(v) for v in edges]
    except (TypeError, ValueError):
        prof.note = "숫자로 해석되지 않는 값이 있습니다"
        return prof
    if len(xs) != len(ys):
        prof.note = f"길이가 다릅니다 ({len(xs)} vs {len(ys)})"
        return prof
    if len(eg) < 2:
        prof.note = "구간 경계가 2개 미만입니다"
        return prof
    if any(eg[i] >= eg[i + 1] for i in range(len(eg) - 1)):
        prof.note = "구간 경계가 증가 순서가 아닙니다"
        return prof

    nb = len(eg) - 1
    prof.edges = eg
    prof.counts = [0] * nb
    sums = [0.0] * nb
    for a, b in zip(xs, ys):
        if math.isnan(a) or math.isnan(b):
            continue
        if a < eg[0] or a > eg[-1]:
            continue
        # 마지막 구간만 오른쪽 끝을 포함
        j = nb - 1
        for i in range(nb):
            if a < eg[i + 1] or (i == nb - 1 and a <= eg[-1]):
                j = i
                break
        prof.counts[j] += 1
        sums[j] += b
    prof.means = [(sums[i] / prof.counts[i]) if prof.counts[i] else None
                  for i in range(nb)]
    return prof
