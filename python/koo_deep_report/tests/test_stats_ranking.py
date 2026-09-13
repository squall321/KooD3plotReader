# 순위검정·상관·회수율 유틸의 정확성과 경계 동작을 검증하는 시험
"""`koo_deep_report.core.stats_ranking` 시험.

핵심은 두 가지다.
1. 값이 맞는가 — scipy 와 대조하고, 해석적으로 아는 경우와 맞춘다.
2. **에러를 내지 않는가** — 빈 입력·NaN·범위 밖·동점에서 예외 없이
   사유를 담아 돌려주는지 확인한다. 보고서 생성 중 예외는 리포트 전체를 죽인다.
"""
import math
import random
import sys

from koo_deep_report.core.stats_ranking import (
    mean_rank_test, spearman, recall_at_k, bin_profile,
)

fails = []


def chk(name, got, want, tol=0.0):
    ok = (got == want) if tol == 0 else (
        got is not None and want is not None and abs(got - want) <= tol)
    if not ok:
        fails.append(f"{name}: got={got!r} want={want!r}")
    print(f"  {'OK ' if ok else 'NG '} {name}")


def chkb(name, cond):
    if not cond:
        fails.append(name)
    print(f"  {'OK ' if cond else 'NG '} {name}")


print("[1] 평균순위 검정 — 귀무 기대값이 (N+1)/2 로 고정")
r = mean_rank_test([1, 1, 3, 1], 6)
chk("귀무 기대값 = (6+1)/2 = 3.5", r.null_expected, 3.5)
chk("평균순위 = 1.5", r.mean_rank, 1.5)
chkb("정확 분포를 썼다", r.method == "exact")
chkb("p 가 0.05 미만 (유의)", r.p_value is not None and r.p_value < 0.05)
print(f"      p = {r.p_value:.6f}")

# 🔴 잘못된 귀무 (N+1)/(k+1) 로 비교하면 결론이 어떻게 달라지는가.
#    이 값(6+1)/(4+1)=1.4 는 '4개 중 최솟값' 의 기대값이라 평균순위와 견주면
#    1.5 가 거의 기대치로 보여 "랜덤 수준" 이라는 오판이 나온다.
wrong_null = (6 + 1) / (4 + 1)
chkb("잘못된 귀무(1.4)로 보면 관측 1.5 가 더 나빠 보인다 — 오판의 구조",
     r.mean_rank > wrong_null and r.mean_rank < r.null_expected)

print("[2] 평균순위 — 정확 분포의 건전성")
# 모든 시행에서 1위면 p = (1/N)^k
r = mean_rank_test([1, 1, 1], 4)
chk("전부 1위: p = (1/4)^3", r.p_value, (1 / 4) ** 3, 1e-12)
# 모든 시행에서 꼴찌면 p = 1
r = mean_rank_test([4, 4, 4], 4)
chk("전부 꼴찌: p = 1", r.p_value, 1.0, 1e-12)
# 단일 시행: P(r <= r_obs) = r_obs/N
r = mean_rank_test([2], 5)
chk("단일 시행 순위 2/5: p = 0.4", r.p_value, 0.4, 1e-12)

print("[3] 평균순위 — 귀무 하에서 p 값이 정확한가 (전수 열거)")
# 🔴 난수 표본으로 '십분위가 균일한가' 를 보면 안 된다. 가능한 p 값이 21가지뿐인
#    이산 분포라 십분위가 원리적으로 고를 수 없고, 멀쩡한 구현이 떨어진다.
#    정확 검정이 만족해야 하는 성질은 P(p ≤ v) == v 이고, N,k 가 작으면
#    **모든 경우를 열거해** 확정적으로 확인할 수 있다 (표본추출보다 강하다).
import itertools
from collections import Counter
N, k = 6, 4
cnt = Counter()
for combo in itertools.product(range(1, N + 1), repeat=k):
    cnt[mean_rank_test(list(combo), N).p_value] += 1
total = N ** k
vals = sorted(cnt)
worst = 0.0
cum = 0
for v in vals:
    cum += cnt[v]
    worst = max(worst, abs(cum / total - v))
print(f"      가능한 p 값 {len(vals)}가지, 전체 경우 {total}, 최대 오차 {worst:.2e}")
chkb("P(p ≤ v) == v 가 모든 p 값에서 성립", worst < 1e-12)
chkb("p 는 모두 (0, 1] 범위", all(0 < v <= 1 for v in vals))
chkb("가장 좋은 경우의 p = (1/N)^k", abs(vals[0] - (1 / N) ** k) < 1e-15)
chkb("가장 나쁜 경우의 p = 1", abs(vals[-1] - 1.0) < 1e-15)

print("[4] Spearman — scipy 대조")
try:
    from scipy.stats import spearmanr
    random.seed(7)
    for trial in range(5):
        n = random.randint(5, 40)
        x = [random.gauss(0, 1) for _ in range(n)]
        y = [xi * 0.7 + random.gauss(0, 1) for xi in x]
        if trial >= 3:                      # 동점을 일부러 만든다
            x = [round(v, 1) for v in x]
            y = [round(v, 1) for v in y]
        got = spearman(x, y).rho
        want = float(spearmanr(x, y).statistic)
        chk(f"scipy 일치 #{trial} (n={n})", got, want, 1e-12)
except ImportError:
    print("      scipy 없음 — 해석적 경우로만 확인")

chk("완전 단조: rho = 1", spearman([1, 2, 3, 4], [10, 20, 30, 40]).rho, 1.0, 1e-12)
chk("완전 역단조: rho = -1", spearman([1, 2, 3, 4], [40, 30, 20, 10]).rho, -1.0, 1e-12)
chkb("전부 동점이면 None (0 이 아니다)", spearman([1, 1, 1], [1, 2, 3]).rho is None)

print("[5] recall@k")
sc = [9, 8, 7, 6, 5]
pos = [True, False, True, False, False]
r = recall_at_k(sc, pos, 2)
chk("상위 2개에서 1/2 회수", r.recall, 0.5, 1e-12)
chk("무작위 기준선 2/5", r.baseline, 0.4, 1e-12)
r = recall_at_k(sc, pos, 5)
chk("전부 검사하면 회수율 1", r.recall, 1.0, 1e-12)
# 동점은 불리하게 — 경계 동점에서 양성을 앞세우지 않는다
r = recall_at_k([5, 5, 5], [False, True, False], 1)
chk("경계 동점은 불리하게 처리", r.recall, 0.0, 1e-12)
# 압축 기준(작을수록 위험)
r = recall_at_k([-9, -8, 1], [True, False, False], 1, higher_is_worse=False)
chk("higher_is_worse=False", r.recall, 1.0, 1e-12)

print("[6] 구간 프로파일")
p = bin_profile([0.5, 1.5, 2.5], [10, 20, 30], [0, 1, 2, 3])
chk("구간별 도수", p.counts, [1, 1, 1])
chk("구간별 평균", p.means, [10.0, 20.0, 30.0])
p = bin_profile([0.5, 0.7], [10, 20], [0, 1, 2])
chkb("빈 구간의 평균은 None (0 이 아니다)", p.means[1] is None and p.counts[1] == 0)
p = bin_profile([3.0], [7], [0, 1, 2, 3])
chkb("마지막 구간은 오른쪽 끝을 포함", p.counts[-1] == 1)

print("[7] 에러를 내지 않는가 — 경계 입력 전수")
cases = [
    ("빈 순위", lambda: mean_rank_test([], 6)),
    ("N=0", lambda: mean_rank_test([1], 0)),
    ("N=1", lambda: mean_rank_test([1, 1], 1)),
    ("범위 밖 순위", lambda: mean_rank_test([0, 7], 6)),
    ("문자열 순위", lambda: mean_rank_test(["a"], 6)),
    ("None 순위", lambda: mean_rank_test([None], 6)),
    ("큰 N,k (근사 경로)", lambda: mean_rank_test([1] * 300, 1200)),
    ("빈 spearman", lambda: spearman([], [])),
    ("길이 불일치", lambda: spearman([1, 2], [1])),
    ("NaN 포함", lambda: spearman([1, float('nan'), 3], [1, 2, 3])),
    ("문자열 spearman", lambda: spearman(["a", "b"], [1, 2])),
    ("빈 recall", lambda: recall_at_k([], [], 1)),
    ("k 범위 밖", lambda: recall_at_k([1, 2], [True, False], 5)),
    ("양성 없음", lambda: recall_at_k([1, 2], [False, False], 1)),
    ("k 문자열", lambda: recall_at_k([1, 2], [True, False], "x")),
    ("경계 1개", lambda: bin_profile([1], [1], [0])),
    ("경계 역순", lambda: bin_profile([1], [1], [3, 1])),
    ("bin 길이 불일치", lambda: bin_profile([1, 2], [1], [0, 3])),
]
for name, fn in cases:
    try:
        out = fn()
        ok = out is not None
        print(f"  {'OK ' if ok else 'NG '} 예외 없음: {name}")
        if not ok:
            fails.append(f"예외 없음: {name}")
    except Exception as e:          # noqa: BLE001 — 예외가 나면 그것이 결함이다
        fails.append(f"예외 발생: {name} → {type(e).__name__}: {e}")
        print(f"  NG  예외 발생: {name} → {type(e).__name__}: {e}")

# 계산 못 한 경우엔 값이 None 이고 사유가 있어야 한다
r = mean_rank_test([], 6)
chkb("빈 입력: p 는 None 이고 사유가 있다", r.p_value is None and bool(r.note))
r = mean_rank_test([1] * 300, 1200)
chkb("근사 경로: method 에 근사라고 적힌다", r.method == "normal_approx" and bool(r.note))

print()


def test_all():
    """pytest 진입점.

    이 파일의 본문은 import 시점에 이미 실행된다(스크립트로도 돌릴 수 있게
    그렇게 썼다). pytest 는 여기서 결과만 단언한다 — 이 함수가 없으면
    `no tests ran` 으로 **조용히 지나가** CI 에서 무의미해진다.
    """
    assert not fails, "실패 %d 건:\n  - %s" % (len(fails), "\n  - ".join(fails))


if __name__ == "__main__":
    if fails:
        print(f"[FAIL] 실패 {len(fails)} 건")
        for f in fails:
            print("   -", f)
        sys.exit(1)
    print("[PASS] 실패 0 건")
