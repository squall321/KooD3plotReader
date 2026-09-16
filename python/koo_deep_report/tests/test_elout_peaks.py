# elout 피크 교차 확인의 계산부를 합성 데이터로 검증하는 시험
"""`koo_deep_report.core.elout_peaks` 시험.

파싱부(`read_elout`)는 실덱 없이 검증할 수 없다 — 가진 덱 두 개 모두 elout 이
없다. 그래서 **계산부를 순수 함수로 분리**했고, 여기서 그 부분을 전부 검증한다.
파싱부는 elout 이 없을 때 **사유를 남기는지**만 확인한다.
"""
import math
import sys

from koo_deep_report.core.elout_peaks import (
    EloutData, read_elout, peak_by_element, compare_peaks, _vm_from_components,
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


print("[1] 성분 → von Mises")
# 단축 인장 σ → vm = σ
chk("단축 인장", _vm_from_components([100, 0, 0, 0, 0, 0]), 100.0, 1e-9)
# 순수 전단 τ → vm = √3·τ
chk("순수 전단", _vm_from_components([0, 0, 0, 50, 0, 0]), 50 * math.sqrt(3), 1e-9)
# 정수압 → vm = 0 (전단 성분이 없으면 형상 변화가 없다)
chk("정수압은 0", _vm_from_components([70, 70, 70, 0, 0, 0]), 0.0, 1e-9)

print("[2] 요소별 피크 추출")
ed = EloutData(kinds={"solid": {
    "time": [0.0, 1.0, 2.0, 3.0],
    "ids": [11, 22],
    # 요소 11 은 t=2 에서 300, 요소 22 는 t=1 에서 150
    "vm": [[100, 50], [200, 150], [300, 90], [250, 20]],
}})
pk = peak_by_element(ed)
chk("요소 11 피크값", pk[11][0], 300.0)
chk("요소 11 피크시각", pk[11][1], 2.0)
chk("요소 22 피크값", pk[22][0], 150.0)
chk("요소 22 피크시각", pk[22][1], 1.0)
chkb("없는 종류는 빈 dict", peak_by_element(ed, "shell") == {})

print("[3] 비교 — d3plot 이 피크를 놓친 경우")
# d3plot 은 t=0,3 만 봤다고 하자 → 요소 11 은 250 을 피크로 봄 (실제 300)
d3 = {11: (250.0, 3.0), 22: (150.0, 1.0)}
cmp = compare_peaks(d3, ed)
chk("비교 행 2개", len(cmp.rows), 2)
chk("놓친 요소 1개", cmp.n_missed, 1)
chk("최대 비율 300/250", cmp.worst_ratio, 1.2, 1e-9)
chkb("요약이 경고를 낸다", "⚠" in cmp.summary() and "놓쳤을 수 있습니다" in cmp.summary())
r11 = next(r for r in cmp.rows if r.element_id == 11)
chk("요소 11 elout 피크", r11.elout_peak, 300.0)
chk("요소 11 비율", r11.ratio, 1.2, 1e-9)
r22 = next(r for r in cmp.rows if r.element_id == 22)
chk("요소 22 는 일치", r22.ratio, 1.0, 1e-9)

print("[4] 놓친 게 없으면 경고하지 않는다")
cmp = compare_peaks({11: (300.0, 2.0), 22: (150.0, 1.0)}, ed)
chk("놓친 요소 0개", cmp.n_missed, 0)
chkb("요약에 경고 없음", "⚠" not in cmp.summary())
chkb("'놓친 피크 없음' 을 말한다", "놓친 피크 없음" in cmp.summary())

print("[5] 임계값")
cmp = compare_peaks({11: (290.0, 2.0)}, ed, threshold=1.5)
chk("임계 1.5 면 300/290 은 통과", cmp.n_missed, 0)
cmp = compare_peaks({11: (290.0, 2.0)}, ed, threshold=1.01)
chk("임계 1.01 이면 걸린다", cmp.n_missed, 1)
cmp = compare_peaks({11: (290.0, 2.0)}, ed, threshold="x")
chk("문자열 임계는 기본값", cmp.threshold, 1.05)

print("[6] 값을 지어내지 않는다")
cmp = compare_peaks({11: (0.0, 0.0)}, ed)
r = cmp.rows[0]
chkb("d3plot 피크 0 이면 비율 None + 사유", r.ratio is None and bool(r.note))
chk("놓친 것으로 세지 않는다", cmp.n_missed, 0)
cmp = compare_peaks({99: (10.0, 0.0)}, ed)
r = cmp.rows[0]
chkb("elout 에 없는 요소는 사유", r.elout_peak is None and "없습니다" in r.note)

print("[7] elout 이 없을 때 — 사유를 남긴다")
cmp = compare_peaks({11: (1.0, 0.0)}, EloutData(note="binout 에 elout 분기가 없습니다"))
chkb("행이 비고 사유가 전달된다",
     (not cmp.rows) and "elout 분기가 없습니다" in cmp.summary())
cmp = compare_peaks({11: (1.0, 0.0)}, EloutData())
chkb("사유가 없어도 뭔가 말한다", bool(cmp.summary()))

print("[8] 실덱으로 파싱부 확인 (elout 이 없는 덱)")
ed2 = read_elout("/data/battery_study/case_01_phase1_stacked_tier-1/binout0000")
chkb("elout 없음을 정확히 말한다",
     (not ed2.ok) and "elout 분기가 없습니다" in ed2.note)
chkb("있는 분기를 알려준다", "glstat" in ed2.note)
print(f"      note: {ed2.note[:90]}")

print("[9] 에러를 내지 않는가")
cases = [
    ("read: 없는 파일", lambda: read_elout("/nonexistent/binout")),
    ("read: None", lambda: read_elout(None)),
    ("read: 디렉토리", lambda: read_elout("/tmp")),
    ("peak: 빈 데이터", lambda: peak_by_element(EloutData())),
    ("peak: 어긋난 길이", lambda: peak_by_element(EloutData(kinds={"solid": {
        "time": [0.0], "ids": [1, 2, 3], "vm": [[1.0]]}}))),
    ("peak: NaN", lambda: peak_by_element(EloutData(kinds={"solid": {
        "time": [0.0], "ids": [1], "vm": [[float('nan')]]}}))),
    ("compare: d3 가 dict 아님", lambda: compare_peaks([1, 2], ed)),
    ("compare: 빈 d3", lambda: compare_peaks({}, ed)),
    ("compare: ed 가 아님", lambda: compare_peaks({1: (1.0, 0.0)}, "x")),
    ("compare: 잘못된 값", lambda: compare_peaks({"a": ("b", "c")}, ed)),
    ("compare: 없는 종류", lambda: compare_peaks({11: (1.0, 0.0)}, ed, kind="beam")),
]
for name, fn in cases:
    try:
        fn()
        print(f"  OK  예외 없음: {name}")
    except Exception as e:      # noqa: BLE001
        fails.append(f"예외 발생: {name} → {type(e).__name__}: {e}")
        print(f"  NG  예외 발생: {name} → {type(e).__name__}: {e}")

pk = peak_by_element(EloutData(kinds={"solid": {
    "time": [0.0], "ids": [1, 2, 3], "vm": [[1.0]]}}))
chkb("길이가 어긋나면 읽을 수 있는 것만", set(pk) == {1})

print()


def test_all():
    """pytest 진입점 — 이 함수가 없으면 `no tests ran` 으로 조용히 지나간다."""
    assert not fails, "실패 %d 건:\n  - %s" % (len(fails), "\n  - ".join(fails))


if __name__ == "__main__":
    if fails:
        print(f"[FAIL] 실패 {len(fails)} 건")
        for f in fails:
            print("   -", f)
        sys.exit(1)
    print("[PASS] 실패 0 건")
