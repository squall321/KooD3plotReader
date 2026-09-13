# 파트 구간 분할(박스·부채꼴)과 구간별 통계를 검증하는 시험
"""`koo_deep_report.core.segment_boxes` 시험."""
import json
import math
import shutil
import sys
import tempfile
from pathlib import Path

from koo_deep_report.core.segment_boxes import (
    load_segments, segment_stats, SegmentSet,
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


tmp = Path(tempfile.mkdtemp(prefix="seg_"))


def w(name, obj):
    p = tmp / name
    p.write_text(json.dumps(obj) if not isinstance(obj, str) else obj, encoding="utf-8")
    return p


try:
    print("[1] 박스 구간")
    p = w("box.json", {"part_id": 7, "segments": [
        {"name": "A", "type": "box", "min": [0, 0, 0], "max": [10, 10, 10]},
        {"name": "B", "type": "box", "min": [10, 0, 0], "max": [20, 10, 10]},
    ]})
    ss = load_segments(p)
    chk("part_id", ss.part_id, 7)
    chk("구간 2개", len(ss.segments), 2)
    chk("A 안", ss.assign([5, 5, 5]), "A")
    chk("B 안", ss.assign([15, 5, 5]), "B")
    chk("경계는 포함", ss.assign([10, 5, 5]), "A")     # 겹치면 먼저 정의된 쪽
    chkb("밖이면 None", ss.assign([100, 0, 0]) is None)

    print("[2] 뒤집힌 경계를 바로잡는다")
    p = w("flip.json", {"part_id": 1, "segments": [
        {"name": "A", "type": "box", "min": [10, 10, 10], "max": [0, 0, 0]}]})
    ss = load_segments(p)
    chk("뒤집혀도 안에 든다", ss.assign([5, 5, 5]), "A")

    print("[3] 부채꼴 구간")
    p = w("sec.json", {"part_id": 2, "segments": [
        {"name": "E", "type": "sector", "center": [0, 0, 0],
         "r_min": 5, "r_max": 15, "theta_min_deg": -45, "theta_max_deg": 45},
        {"name": "N", "type": "sector", "center": [0, 0, 0],
         "r_min": 5, "r_max": 15, "theta_min_deg": 45, "theta_max_deg": 135},
    ]})
    ss = load_segments(p)
    chk("동쪽(+x)", ss.assign([10, 0, 0]), "E")
    chk("북쪽(+y)", ss.assign([0, 10, 0]), "N")
    chkb("반지름 밖", ss.assign([100, 0, 0]) is None)
    chkb("반지름 안쪽 구멍", ss.assign([1, 0, 0]) is None)
    chkb("서쪽은 어느 구간도 아님", ss.assign([-10, 0, 0]) is None)

    print("[4] ±180 을 감는 각도 구간")
    p = w("wrap.json", {"part_id": 3, "segments": [
        {"name": "W", "type": "sector", "center": [0, 0, 0],
         "r_min": 1, "r_max": 10, "theta_min_deg": 135, "theta_max_deg": -135}]})
    ss = load_segments(p)
    chk("+175°", ss.assign([-5 * math.cos(math.radians(5)), 5 * math.sin(math.radians(5)), 0]), "W")
    chk("-175°", ss.assign([-5 * math.cos(math.radians(5)), -5 * math.sin(math.radians(5)), 0]), "W")
    chkb("0° 는 아님", ss.assign([5, 0, 0]) is None)

    print("[5] 축 선택")
    p = w("axis.json", {"part_id": 4, "segments": [
        {"name": "X", "type": "sector", "center": [0, 0, 0], "axis": "x",
         "r_min": 1, "r_max": 10, "theta_min_deg": -180, "theta_max_deg": 180}]})
    ss = load_segments(p)
    chkb("x축 부채꼴은 y-z 평면으로 잰다", ss.assign([999, 5, 0]) == "X")

    print("[6] 구간별 통계")
    p = w("st.json", {"part_id": 5, "segments": [
        {"name": "A", "type": "box", "min": [0, 0, 0], "max": [10, 10, 10]},
        {"name": "B", "type": "box", "min": [10, 0, 0], "max": [20, 10, 10]},
    ]})
    ss = load_segments(p)
    pts = [[1, 1, 1], [2, 2, 2], [15, 5, 5], [100, 0, 0]]
    vals = [10.0, 30.0, 7.0, 99.0]
    st = segment_stats(pts, vals, ss)
    chk("A 개수", st.counts["A"], 2)
    chk("A 평균", st.means()["A"], 20.0)
    chk("A 최댓값", st.maxes["A"], 30.0)
    chk("B 개수", st.counts["B"], 1)
    chk("미배정", st.unassigned, 1)
    chkb("미배정을 조용히 버리지 않는다", st.unassigned == 1)
    st = segment_stats([[1, 1, 1], [2, 2, 2]], [1.0, float('nan')], ss)
    chk("NaN 값은 invalid", st.invalid, 1)
    chk("나머지는 센다", st.counts["A"], 1)

    print("[7] 잘못된 정의는 건너뛰고 사유를 남긴다")
    p = w("bad.json", {"part_id": 6, "segments": [
        {"name": "OK", "type": "box", "min": [0, 0, 0], "max": [1, 1, 1]},
        {"name": "NoMax", "type": "box", "min": [0, 0, 0]},
        {"name": "Short", "type": "box", "min": [0, 0], "max": [1, 1]},
        {"name": "OK", "type": "box", "min": [0, 0, 0], "max": [1, 1, 1]},
        {"name": "BadType", "type": "wedge"},
        {"name": "BadAxis", "type": "sector", "center": [0, 0, 0], "r_max": 1, "axis": "q"},
        "notadict",
    ]})
    ss = load_segments(p)
    chk("쓸 수 있는 구간 1개", len(ss.segments), 1)
    chkb("사유가 있다", bool(ss.note))
    chkb("이름 중복을 잡는다", "중복" in ss.note or len(ss.segments) == 1)

    print("[8] 에러를 내지 않는가")
    cases = [
        ("없는 파일", lambda: load_segments(tmp / "nope.json")),
        ("None 경로", lambda: load_segments(None)),
        ("숫자 경로", lambda: load_segments(1)),
        ("깨진 JSON", lambda: load_segments(w("broken.json", "{ not json"))),
        ("최상위 배열", lambda: load_segments(w("arr.json", [1, 2]))),
        ("part_id 없음", lambda: load_segments(w("nopid.json", {"segments": []}))),
        ("segments 없음", lambda: load_segments(w("noseg.json", {"part_id": 1}))),
        ("segments 빈 배열", lambda: load_segments(w("emptyseg.json", {"part_id": 1, "segments": []}))),
        ("assign: 문자열 점", lambda: ss.assign("abc")),
        ("assign: None", lambda: ss.assign(None)),
        ("assign: 좌표 2개", lambda: ss.assign([1, 2])),
        ("assign: NaN", lambda: ss.assign([float('nan')] * 3)),
        ("stats: 구간 없음", lambda: segment_stats([[0, 0, 0]], [1.0], SegmentSet())),
        ("stats: 길이 불일치", lambda: segment_stats([[0, 0, 0]], [], ss)),
        ("stats: 점이 목록 아님", lambda: segment_stats(None, None, ss)),
        ("stats: ss 가 아님", lambda: segment_stats([[0, 0, 0]], [1.0], "x")),
    ]
    for name, fn in cases:
        try:
            fn()
            print(f"  OK  예외 없음: {name}")
        except Exception as e:      # noqa: BLE001
            fails.append(f"예외 발생: {name} → {type(e).__name__}: {e}")
            print(f"  NG  예외 발생: {name} → {type(e).__name__}: {e}")

    s2 = load_segments(tmp / "nope.json")
    chkb("없는 파일: 사유", (not s2.segments) and bool(s2.note))
    s2 = load_segments(w("noseg.json", {"part_id": 1}))
    chkb("segments 없음: 사유", (not s2.segments) and bool(s2.note))
finally:
    shutil.rmtree(tmp, ignore_errors=True)

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
