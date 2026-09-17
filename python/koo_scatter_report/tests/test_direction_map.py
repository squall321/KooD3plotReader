# 방향도가 캠페인 각도 규약과 무관하게 모든 점을 화면 안에 그리는지 보는 시험
"""방향도(roll–pitch)의 축 범위.

배경(2026-09 전수조사). `direction_map` 은 x 축을 roll ±180, y 축을 pitch ±90 으로
**못박아** 두었다. 그런데 캠페인마다 규약이 다르다 — Test_001 은 roll ±180 /
pitch ±90 이지만, Test_006_Fibonacci_6deg(1144런)는 roll ±90 / pitch ±180 이다
(sphere 로더가 "표준" 이라 부르는 쪽이 후자다). 후자에서는 1144런 중 572런이
|pitch|>90 이라 축 밖으로 나가고, 그중 465개는 viewBox(0..380) 바깥이라 브라우저가
통째로 잘라냈다. 그런데 색막대의 최대·최소는 **보이지 않는 점까지** 포함해서
표시됐다 — "어느 자세가 위험한가" 를 답하라는 그림이 최악 점을 감춘 것이다.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from koo_scatter_report import charts as C  # noqa: E402

W, H = 560, 380


def _circles(svg: str):
    """그려진 점의 (cx, cy) 목록."""
    return [(float(cx), float(cy)) for cx, cy in
            re.findall(r'<circle cx="([-\d.]+)" cy="([-\d.]+)"', svg)]


def test_pitch_beyond_90_stays_inside_the_canvas():
    """|pitch|>90 규약(Test_006)에서도 점이 화면 안에 있어야 한다."""
    pts = [(-40.0, 30.0, 100.0), (-40.0, 150.0, 480.0), (20.0, -170.0, 350.0),
           (84.1, 177.5, 220.0), (-86.6, -178.5, 90.0)]
    svg = C.direction_map(pts)
    got = _circles(svg)
    assert len(got) == len(pts), f"점이 {len(got)}개만 그려졌다"
    for cx, cy in got:
        assert 0.0 <= cx <= W, f"cx={cx} 가 화면 밖이다"
        assert 0.0 <= cy <= H, f"cy={cy} 가 화면 밖이다"


def test_worst_point_is_visible():
    """최악 값(480)이 색막대에는 있는데 화면에는 없으면 그림이 거짓말을 한다."""
    pts = [(-40.0, 30.0, 100.0), (-40.0, 150.0, 480.0)]
    svg = C.direction_map(pts)
    assert "480" in svg, "색막대에서 최대값이 빠졌다"
    ys = [cy for _, cy in _circles(svg)]
    assert all(0.0 <= y <= H for y in ys), ys


def test_classic_convention_still_works():
    """roll ±180 / pitch ±90 규약(Test_001)도 그대로여야 한다 — 회귀 금지."""
    pts = [(-179.0, 89.0, 10.0), (179.0, -89.0, 20.0), (0.0, 0.0, 15.0)]
    svg = C.direction_map(pts)
    got = _circles(svg)
    assert len(got) == 3
    for cx, cy in got:
        assert 0.0 <= cx <= W and 0.0 <= cy <= H


def _y_ticks(svg: str):
    """y 축 눈금 라벨 (text-anchor=\"end\" 가 y 축 쪽이다)."""
    return [t for t in re.findall(r'text-anchor="end">([-\d.]+)</text>', svg)]


def test_axis_labels_follow_the_data():
    """y(pitch) 축 눈금이 데이터 범위를 따라야 한다."""
    ticks = _y_ticks(C.direction_map([(10.0, 150.0, 1.0), (-10.0, -150.0, 2.0)]))
    assert "180" in ticks and "-180" in ticks, f"pitch 축이 아직 ±90 에 묶여 있다: {ticks}"
    # 고전 규약은 그대로 ±90
    ticks2 = _y_ticks(C.direction_map([(150.0, 80.0, 1.0), (-150.0, -80.0, 2.0)]))
    assert "90" in ticks2 and "180" not in ticks2, ticks2


def test_all():
    """pytest 진입점."""
    test_pitch_beyond_90_stays_inside_the_canvas()
    test_worst_point_is_visible()
    test_classic_convention_still_works()
    test_axis_labels_follow_the_data()
