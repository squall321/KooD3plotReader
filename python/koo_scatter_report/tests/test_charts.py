# SVG 차트가 값을 제대로 그리고 경계에서 죽지 않는지 검증하는 시험
"""`koo_scatter_report.charts` 시험.

그림은 눈으로 봐야 한다고들 하지만, **깨지지 않는지**는 기계가 볼 수 있다.
- 유효한 SVG 인가 (XML 로 파싱되는가)
- 값이 있으면 도형이 생기는가 / 없으면 **사유가 적힌 SVG** 인가 (빈 화면 금지)
- 이상한 입력(NaN·문자열·길이 불일치)에서 예외가 나지 않는가
"""
import math
import sys
import xml.etree.ElementTree as ET

from koo_scatter_report import charts as C

fails = []


def chk(name, cond):
    if not cond:
        fails.append(name)
    print(f"  {'OK ' if cond else 'NG '} {name}")


def parse(svg):
    """유효한 XML 인지 확인하고 루트를 돌려준다."""
    return ET.fromstring(svg)


def shapes(svg):
    root = parse(svg)
    n = 0
    for tag in ("circle", "rect", "path", "line"):
        n += len(root.findall(f".//{{http://www.w3.org/2000/svg}}{tag}")) \
             + len(root.findall(f".//{tag}"))
    return n


def has_text(svg, frag):
    return frag in svg


print("[1] 색 스케일")
chk("0 → 밝은 쪽", C.color_at(0).startswith("#"))
chk("1 → 진한 쪽", C.color_at(1) == "#b10026")
chk("범위 밖은 잘라 쓴다", C.color_at(-5) == C.color_at(0) and C.color_at(5) == C.color_at(1))
chk("NaN 은 '값 없음' 색", C.color_at(float("nan")) == "#33384a")
chk("문자열도 '값 없음' 색", C.color_at("x") == "#33384a")

print("[2] 산포도")
svg = C.scatter([(1, 10, "F1"), (2, 20, "F2"), (3, 15, "F1")])
chk("유효한 SVG", parse(svg) is not None)
chk("점이 그려진다", shapes(svg) > 3)
chk("면 범례가 있다", has_text(svg, "F1") and has_text(svg, "F2"))
svg = C.scatter([])
chk("빈 입력은 사유를 적는다", "그릴 점이 없습니다" in svg)
svg = C.scatter([(float("nan"), 1, "F1"), (1, 2, "F1")])
chk("NaN 점은 버리고 나머지를 그린다", shapes(svg) > 0)
svg = C.scatter([(5, 5, "F1")])
chk("점 1개 (축 범위 0 나눗셈 없음)", parse(svg) is not None)

print("[3] 방향도")
svg = C.direction_map([(0, 0, 1.0), (90, -45, 2.0)])
chk("유효한 SVG", parse(svg) is not None)
chk("점이 그려진다", shapes(svg) > 2)
chk("색바 라벨", has_text(svg, "값"))
chk("빈 입력은 사유", "각도·값 쌍이 없습니다" in C.direction_map([]))

print("[4] 히트맵")
svg = C.heatmap(["F1", "F2"], ["0-5", "5-10"], [[1.0, 2.0], [3.0, None]])
chk("유효한 SVG", parse(svg) is not None)
chk("칸이 그려진다", shapes(svg) >= 4)
chk("값 없는 칸 표시", "값 없음" in svg)
chk("행/열 비면 사유", "비어 있습니다" in C.heatmap([], [], []))
chk("전부 None 이면 사유", "모든 칸이 비었습니다" in
    C.heatmap(["a"], ["b"], [[None]]))
chk("행 길이가 짧아도 안 죽는다", parse(C.heatmap(["a", "b"], ["c", "d"], [[1.0]])) is not None)

print("[5] 회수율 곡선")
svg = C.recall_curve([1, 2, 3], [0.2, 0.5, 1.0], [0.1, 0.2, 0.3])
chk("유효한 SVG", parse(svg) is not None)
chk("곡선이 그려진다", shapes(svg) > 3)
chk("기준선 표기", "무작위 기준선" in svg)
chk("빈 입력은 사유", "회수율을 계산하지 못했습니다" in C.recall_curve([], []))
chk("None 이 섞여도 안 죽는다",
    parse(C.recall_curve([1, 2], [None, 0.5])) is not None)

print("[6] 막대 프로파일")
svg = C.bar_profile(["a", "b", "c"], [1.0, None, 3.0], [5, 0, 7])
chk("유효한 SVG", parse(svg) is not None)
chk("막대가 그려진다", shapes(svg) >= 3)
chk("값 없는 구간 표시", "값 없음" in svg)
chk("표본 수 표기", "표본" in svg)
chk("전부 None 이면 사유", "구간에 값이 없습니다" in
    C.bar_profile(["a"], [None]))

print("[7] 리스크맵")
svg = C.risk_map([(0, 0, 1, 10, "A"), (5, 5, 2, 20, "B")],
                 [-1, -1, -1], [6, 6, 6])
chk("유효한 SVG", parse(svg) is not None)
chk("원이 그려진다", shapes(svg) >= 3)
chk("경계상자가 그려진다", "stroke-dasharray" in svg)
svg = C.risk_map([(0, 0, 1, 10, "A")], marks=[(0.5, 0.5, "crack")])
chk("불량 표시가 그려진다", "#00e5ff" in svg and "실물 불량" in svg)
chk("빈 입력은 사유", "투영할 군집이 없습니다" in C.risk_map([]))
chk("한 점이어도 안 죽는다", parse(C.risk_map([(1, 1, 0, 5, "x")])) is not None)

print("[8] 구간도")
svg = C.segment_map([("Q1", 0, 0, 1, 1), ("Q2", 1, 0, 2, 1)],
                    {"Q1": 5.0}, [(0.5, 0.5)])
chk("유효한 SVG", parse(svg) is not None)
chk("구간이 그려진다", shapes(svg) >= 2)
chk("값 없는 구간 표시", "값 없음" in svg)
chk("군집 중심 표시", "#00e5ff" in svg)
chk("정의 없으면 사유", "구간 정의가 없습니다" in C.segment_map([], {}))

print("[9] 둘레 전개도")
svg = C.perimeter_unroll([(1, 0, 0, 0.5, 10, "A"), (0, 1, 1, 0.5, 20, "B")],
                         [-2, -2, -2], [2, 2, 2])
chk("유효한 SVG", parse(svg) is not None)
chk("점이 그려진다", shapes(svg) > 2)
chk("경계상자 없으면 사유", "전개할 수 없습니다" in
    C.perimeter_unroll([(0, 0, 0, 1, 1, "")], None, None))
chk("군집 없으면 사유", "전개할 군집이 없습니다" in
    C.perimeter_unroll([], [-1, -1, -1], [1, 1, 1]))

print("[10] 에러를 내지 않는가 — 이상한 입력 전수")
cases = [
    ("scatter: None", lambda: C.scatter(None)),
    ("scatter: 문자열 점", lambda: C.scatter([("a", "b")])),
    ("scatter: 길이 1 튜플", lambda: C.scatter([(1,)])),
    ("direction: None", lambda: C.direction_map(None)),
    ("direction: NaN", lambda: C.direction_map([(float("nan"),) * 3])),
    ("heatmap: None", lambda: C.heatmap(None, None, None)),
    ("heatmap: values None", lambda: C.heatmap(["a"], ["b"], None)),
    ("recall: None", lambda: C.recall_curve(None, None)),
    ("recall: 길이 불일치", lambda: C.recall_curve([1, 2, 3], [0.5])),
    ("bar: None", lambda: C.bar_profile(None, None)),
    ("bar: counts 없음", lambda: C.bar_profile(["a"], [1.0], None)),
    ("risk: None", lambda: C.risk_map(None)),
    ("risk: 잘못된 bbox", lambda: C.risk_map([(0, 0, 1, 1, "")], "x", "y")),
    ("risk: 문자열 marks", lambda: C.risk_map([(0, 0, 1, 1, "")], marks=[("a", "b")])),
    ("segment: None", lambda: C.segment_map(None, None)),
    ("segment: values None", lambda: C.segment_map([("A", 0, 0, 1, 1)], None)),
    ("perimeter: None", lambda: C.perimeter_unroll(None, None, None)),
    ("perimeter: 좌표 2개 bbox", lambda: C.perimeter_unroll([], [0, 0], [1, 1])),
    ("note_svg", lambda: C.note_svg(100, 50, "<위험한 & 문자>")),
]
for name, fn in cases:
    try:
        out = fn()
        ok = isinstance(out, str) and out.startswith("<svg")
        if ok:
            try:
                parse(out)
            except ET.ParseError as e:
                ok = False
                fails.append(f"{name}: 유효하지 않은 SVG ({e})")
        print(f"  {'OK ' if ok else 'NG '} 예외 없음·유효 SVG: {name}")
        if not ok and f"{name}: 유효하지 않은 SVG" not in " ".join(fails):
            fails.append(f"SVG 아님: {name}")
    except Exception as e:      # noqa: BLE001
        fails.append(f"예외 발생: {name} → {type(e).__name__}: {e}")
        print(f"  NG  예외 발생: {name} → {type(e).__name__}: {e}")

chk("HTML 특수문자가 이스케이프된다", "&lt;" in C.note_svg(100, 50, "<a>"))

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
