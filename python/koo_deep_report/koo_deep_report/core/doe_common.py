# 리비전·과제 비교에서 공통 DOE 교집합을 구하고 표본이 부족하면 비교를 거부하는 모듈
"""공통 DOE 교집합.

**왜 이 모듈이 있나.**
리비전 비교는 *같은 각도끼리만* 유효하다. 2026-09 검증에서 33런만 끝난 과제가
교집합에 들어와 공통 DOE 를 185 → 27 로 줄였고, 그 27개로 계산한
"T4 는 ×1.97~2.49 로 확연히 안전" 을 보고했다가 철회했다(올바른 값 ×2.66~4.02).

교집합이 줄어든 사실 자체는 로그 어딘가에 있었지만, **누가 줄였는지**가 드러나지
않아 아무도 알아채지 못했다. 여기서는 케이스를 하나씩 빼 보고
"이걸 빼면 교집합이 27 → 185 로 는다" 를 지목한다.

**설계 규칙.**
- 예외를 던지지 않는다. 거부도 결과 객체로 돌려준다(`rejected=True` + 사유).
- 교집합이 임계 미만이면 **기본적으로 거부**한다. 조용히 적은 표본으로 비교하지 않는다.
- 키는 호출부가 정한다(각도 이름, 반올림한 (roll,pitch,yaw) 등).
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: 교집합이 이보다 적으면 비교를 거부한다. 리비전 비교에서 표본 10개 미만은
#: 순위·비율이 한두 런에 좌우되므로 수치를 내면 안 된다.
DEFAULT_MIN_COMMON = 10


@dataclass
class DoeIntersection:
    """공통 DOE 계산 결과. 거부되었으면 `rejected=True` 이고 `reason` 에 사유가 있다."""
    case_sizes: dict = field(default_factory=dict)   #: 케이스 → DOE 수
    common: list = field(default_factory=list)       #: 교집합 키 (정렬)
    n_common: int = 0
    excluded: dict = field(default_factory=dict)     #: 케이스 → 교집합에 못 든 키
    #: 교집합을 크게 줄인 케이스: [(케이스, 이걸 빼면 늘어나는 교집합 수)]
    limiting: list = field(default_factory=list)
    min_common: int = DEFAULT_MIN_COMMON
    rejected: bool = False
    reason: str = ""

    def summary(self) -> str:
        """보고서에 그대로 실을 수 있는 한 줄 요약."""
        if self.rejected:
            return f"비교 거부 — {self.reason}"
        s = f"공통 DOE {self.n_common}개 (케이스 {len(self.case_sizes)}개)"
        if self.limiting:
            name, gain = self.limiting[0]
            s += f" · {name} 를 빼면 {self.n_common + gain}개로 늘어남"
        return s


def common_doe(cases: dict, min_common: int = DEFAULT_MIN_COMMON,
               reject_below: bool = True) -> DoeIntersection:
    """여러 케이스의 DOE 키 교집합을 구한다.

    Args:
        cases: {케이스 이름: 그 케이스의 DOE 키 목록}
        min_common: 이보다 적으면 거부 (기본 10)
        reject_below: False 면 거부하지 않고 사유만 남긴다.
                      **기본값을 바꾸지 말 것** — 조용히 적은 표본으로 비교하는
                      것이 이 모듈이 막으려는 사고다.

    Returns:
        DoeIntersection. 입력이 잘못돼도 예외 대신 `rejected=True` 로 돌아온다.
    """
    # 임계값 정규화 — 문자열·실수·음수를 조용히 이상하게 해석하지 않는다.
    # (예전 판은 "10.5" 를 기본값으로, "-5" 를 음수 임계로 받아 항상 통과시켰다.)
    try:
        mc = int(min_common)
    except (TypeError, ValueError):
        mc = DEFAULT_MIN_COMMON
    res = DoeIntersection(min_common=max(0, mc))

    if not isinstance(cases, dict):
        res.rejected = True
        res.reason = "케이스가 {이름: 키목록} 형태의 dict 가 아닙니다"
        return res
    if len(cases) < 2:
        res.rejected = True
        res.reason = f"비교하려면 케이스가 2개 이상이어야 합니다 (지금 {len(cases)}개)"
        return res

    sets: dict = {}
    for name, keys in cases.items():
        try:
            ks = set(keys)
        except TypeError:
            res.rejected = True
            res.reason = f"케이스 '{name}' 의 키 목록을 집합으로 만들 수 없습니다"
            return res
        # 해시 불가능한 키(리스트 등)는 여기서 걸린다 — 조용히 빠지지 않게
        sets[str(name)] = ks
        res.case_sizes[str(name)] = len(ks)

    empty = [n for n, s in sets.items() if not s]
    if empty:
        res.rejected = True
        res.reason = f"DOE 가 비어 있는 케이스가 있습니다: {', '.join(sorted(empty))}"
        return res

    inter = set.intersection(*sets.values())
    try:
        res.common = sorted(inter)
    except TypeError:
        res.common = sorted(inter, key=repr)     # 정렬 불가 타입 섞임
    res.n_common = len(inter)
    res.excluded = {n: sorted(s - inter, key=repr) for n, s in sets.items()}

    # ── 누가 교집합을 줄였나 — 케이스를 하나씩 빼 본다 ──
    # 이것이 없으면 "교집합이 27개" 만 보이고 원인이 안 보인다.
    if len(sets) > 2:
        for name in sets:
            others = [s for n, s in sets.items() if n != name]
            gain = len(set.intersection(*others)) - res.n_common
            if gain > 0:
                res.limiting.append((name, gain))
        res.limiting.sort(key=lambda t: -t[1])

    if res.n_common < res.min_common:
        res.reason = (f"공통 DOE 가 {res.n_common}개로 임계 {res.min_common}개 미만입니다"
                      f" — 이 표본으로는 리비전 간 수치를 비교할 수 없습니다")
        if res.limiting:
            name, gain = res.limiting[0]
            res.reason += (f". '{name}' 를 빼면 {res.n_common + gain}개가 되므로,"
                           f" 그 케이스가 아직 다 돌지 않았는지 확인하세요")
        res.rejected = bool(reject_below)
    return res


def incomplete_cases(cases: dict, ratio: float = 0.5) -> list:
    """전체 DOE 수가 최대 케이스의 `ratio` 미만인 케이스 — 미완주 의심.

    반환: [(이름, 자기 DOE 수, 최대 DOE 수)] — 비어 있으면 의심 대상 없음.
    판단은 호출부가 한다. 여기서 자동으로 빼지 않는다 — 의도적으로 적은 DOE 를
    돌린 경우와 구분할 수 없기 때문이다.
    """
    out = []
    if not isinstance(cases, dict) or not cases:
        return out
    sizes = {}
    for name, keys in cases.items():
        try:
            sizes[str(name)] = len(set(keys))
        except TypeError:
            continue
    if not sizes:
        return out
    mx = max(sizes.values())
    if mx <= 0:
        return out
    try:
        r = float(ratio)
    except (TypeError, ValueError):
        r = 0.5
    for name, n in sorted(sizes.items()):
        if n < mx * r:
            out.append((name, n, mx))
    return out
