# 공통 DOE 교집합·거부 임계와 경계 입력 안전성을 검증하는 시험
"""`koo_deep_report.core.doe_common` 시험.

가장 중요한 시험은 [2] 다 — 2026-09 에 실제로 일어난 "미완주 과제가 교집합을
185 → 27 로 줄여 틀린 수치를 보고" 를 재현하고, 이 모듈이 그것을 잡는지 본다.
"""
import sys

from koo_deep_report.core.doe_common import (
    common_doe, incomplete_cases, DEFAULT_MIN_COMMON,
)

fails = []


def chk(name, got, want):
    ok = got == want
    if not ok:
        fails.append(f"{name}: got={got!r} want={want!r}")
    print(f"  {'OK ' if ok else 'NG '} {name}")


def chkb(name, cond):
    if not cond:
        fails.append(name)
    print(f"  {'OK ' if cond else 'NG '} {name}")


print("[1] 기본 교집합")
r = common_doe({"A": [1, 2, 3, 4], "B": [2, 3, 4, 5], "C": [3, 4, 9]}, min_common=2)
chk("교집합 = {3,4}", r.common, [3, 4])
chk("케이스별 크기", r.case_sizes, {"A": 4, "B": 4, "C": 3})
chkb("거부되지 않음", not r.rejected)
chk("A 에서 제외된 키", r.excluded["A"], [1, 2])

print("[2] 실제 사건 재현 — 미완주 과제가 교집합을 무너뜨린다")
# T1~T3 은 185각도를 다 돌았고, T4_PV1 은 33런만 끝난 상태로 끼어들었다.
full = list(range(185))
partial = list(range(27))          # 그중 27개만 겹친다고 하자
cases = {"T1": full, "T2": full, "T3": full, "T4_PV1": partial}
r = common_doe(cases, min_common=50)
chk("교집합이 27 로 줄었다", r.n_common, 27)
chkb("임계 미달이라 거부됐다", r.rejected)
chkb("사유에 표본 수가 적혀 있다", "27" in r.reason and "50" in r.reason)
chkb("범인을 지목한다 — T4_PV1", r.limiting and r.limiting[0][0] == "T4_PV1")
chk("T4_PV1 을 빼면 185 로 회복", r.n_common + r.limiting[0][1], 185)
print(f"      사유: {r.reason}")
print(f"      요약: {r.summary()}")

# 미완주 의심 탐지
inc = incomplete_cases(cases)
chkb("미완주 의심으로 T4_PV1 을 집는다", [n for n, _, _ in inc] == ["T4_PV1"])

# 임계를 낮추면 통과하되 범인은 여전히 보인다
r2 = common_doe(cases, min_common=10)
chkb("임계 10 이면 거부되지 않음", not r2.rejected)
chkb("그래도 범인 정보는 남는다", r2.limiting[0][0] == "T4_PV1")

print("[3] 거부 정책")
r = common_doe({"A": [1], "B": [1]}, min_common=DEFAULT_MIN_COMMON)
chkb("기본 임계 미만이면 거부", r.rejected)
r = common_doe({"A": [1], "B": [1]}, min_common=DEFAULT_MIN_COMMON, reject_below=False)
chkb("reject_below=False 면 거부하지 않되 사유는 남는다",
     (not r.rejected) and bool(r.reason))

print("[4] 교집합이 비는 경우")
r = common_doe({"A": [1, 2], "B": [3, 4]}, min_common=1)
chk("교집합 0", r.n_common, 0)
chkb("거부됨", r.rejected)

print("[4b] 임계값 정규화")
r = common_doe({"A": [1], "B": [1]}, min_common=-5)
chk("음수 임계는 0 으로 클램프", r.min_common, 0)
chkb("임계 0 이면 거부하지 않음", not r.rejected)
r = common_doe({"A": [1], "B": [1]}, min_common=10.9)
chk("실수 임계는 int 로 절삭", r.min_common, 10)
r = common_doe({"A": [1], "B": [1]}, min_common="x")
chk("해석 불가 임계는 기본값", r.min_common, DEFAULT_MIN_COMMON)
r = common_doe({"A": [1], "B": [1]}, min_common=None)
chk("None 임계는 기본값", r.min_common, DEFAULT_MIN_COMMON)

print("[5] 에러를 내지 않는가 — 경계 입력 전수")
cases_bad = [
    ("dict 아님", lambda: common_doe([1, 2])),
    ("케이스 0개", lambda: common_doe({})),
    ("케이스 1개", lambda: common_doe({"A": [1, 2]})),
    ("빈 DOE 포함", lambda: common_doe({"A": [], "B": [1]})),
    ("None 키목록", lambda: common_doe({"A": None, "B": [1]})),
    ("해시 불가 키", lambda: common_doe({"A": [[1]], "B": [[1]]})),
    ("정렬 불가 혼합 키", lambda: common_doe({"A": [1, "a"], "B": [1, "a"]})),
    ("min_common 문자열", lambda: common_doe({"A": [1], "B": [1]}, min_common="x")),
    ("min_common None", lambda: common_doe({"A": [1], "B": [1]}, min_common=None)),
    ("min_common 실수", lambda: common_doe({"A": [1], "B": [1]}, min_common=3.7)),
    ("min_common 음수", lambda: common_doe({"A": [1], "B": [1]}, min_common=-5)),
    ("튜플 키", lambda: common_doe({"A": [(0, 0, 0)], "B": [(0, 0, 0)]}, min_common=1)),
    ("incomplete: dict 아님", lambda: incomplete_cases([1])),
    ("incomplete: 빈 dict", lambda: incomplete_cases({})),
    ("incomplete: ratio 문자열", lambda: incomplete_cases({"A": [1, 2], "B": [1]}, ratio="x")),
    ("incomplete: 해시 불가", lambda: incomplete_cases({"A": [[1]], "B": [1]})),
]
for name, fn in cases_bad:
    try:
        out = fn()
        ok = out is not None
        print(f"  {'OK ' if ok else 'NG '} 예외 없음: {name}")
        if not ok:
            fails.append(f"예외 없음: {name}")
    except Exception as e:          # noqa: BLE001
        fails.append(f"예외 발생: {name} → {type(e).__name__}: {e}")
        print(f"  NG  예외 발생: {name} → {type(e).__name__}: {e}")

# 잘못된 입력은 사유가 있어야 한다
for bad in ([1, 2], {}, {"A": [1, 2]}):
    r = common_doe(bad)
    chkb(f"잘못된 입력({type(bad).__name__})은 거부 + 사유", r.rejected and bool(r.reason))

# 튜플 키(각도 (roll,pitch,yaw))가 정상 동작하는지 — 실제 쓰임새
r = common_doe({"A": [(0, 0, 0), (90, 0, 0)], "B": [(0, 0, 0)]}, min_common=1)
chk("튜플 키 교집합", r.common, [(0, 0, 0)])
chkb("튜플 키에서 거부되지 않음", not r.rejected)

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
