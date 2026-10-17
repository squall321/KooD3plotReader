# 핫스팟 파트 메시(G1) 규칙 — 좌표계가 어긋나면 그림을 그리지 않는다
"""핫스팟 군집을 얹을 파트 메시의 규칙.

실측 배경 (2026-10-17): 처음에는 자세 미리보기와 같이 **시나리오 원본 `.k`** 에서
메시를 뽑았다. 각도별 런이 모델을 회전시키지 않는 것은 덱으로 확인했으므로
"같은 좌표계" 라고 보았는데, 틀렸다 — 회전은 같지만 **평행이동이 다르다.**
낙하 덱이 모델을 원점 중심으로 옮겨 놓아, 원본은 x∈[1,71] 인데 군집은
x∈[-34,35] 였다. 85개 군집 중 90% 가 메시 밖에 찍혔다.

이 종류의 결함은 **그림이 멀쩡해 보인다.** 메시도 나오고 구도 나오고 색도 맞는데
위치만 틀리다. 그래서 여기서 못박는 규칙은 둘이다.

1. 형상은 군집이 나온 바로 그 d3plot 에서 뽑는다.
2. 그래도 어긋나면 **메시를 싣지 않고 사유를 말한다** — 틀린 그림보다 없는 그림이 낫다.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from koo_sphere_report.report.html_report import (  # noqa: E402
    _hotspot_frame_check, _hotspot_mesh_name, _load_hotspot_mesh,
)


class _Run:
    """hotspot_clusters 만 가진 최소 SimulationResult 대역."""

    def __init__(self, clusters):
        self.hotspot_clusters = clusters


def _item(part_id, centers):
    return {"part_id": part_id,
            "clusters": [{"center": list(c)} for c in centers]}


# 한 변 10 짜리 정육면체 메시 (파트 7)
_MESH = {"bbox": [0.0, 0.0, 0.0, 10.0, 10.0, 10.0], "p": [7, 7]}


def test_name_is_order_independent():
    """캐시 이름은 파트 **집합**을 가리킨다 — 순서가 달라도 같은 이름이어야 한다."""
    assert _hotspot_mesh_name([15, 1, 21]) == _hotspot_mesh_name([1, 15, 21])
    assert _hotspot_mesh_name([1, 15, 21]) == "hotspot_mesh_1-15-21"


def test_name_falls_back_to_hash_when_too_long():
    """파트가 많아도 파일명 한계에 걸리지 않는다."""
    name = _hotspot_mesh_name(list(range(100, 200)))
    assert len(name) < 40
    assert name.startswith("hotspot_mesh_")
    # 같은 집합이면 같은 해시, 다른 집합이면 다른 해시
    assert name == _hotspot_mesh_name(list(range(199, 99, -1)))
    assert name != _hotspot_mesh_name(list(range(100, 199)))


def test_frame_check_passes_when_aligned():
    """군집이 메시 안에 있으면 통과 (None = 문제 없음)."""
    runs = [_Run([_item(7, [(1, 1, 1), (5, 5, 5), (9, 9, 9)])])]
    assert _hotspot_frame_check(_MESH, runs) is None


def test_frame_check_tolerates_boundary_clusters():
    """경계에 걸친 군집 몇 개로는 '어긋남' 이라고 하지 않는다.

    복셀 데시메이션이 경계를 조금 깎으므로 최대변의 2% 는 여유로 둔다.
    """
    runs = [_Run([_item(7, [(5, 5, 5), (5, 5, 5), (-0.1, 5, 5)])])]
    assert _hotspot_frame_check(_MESH, runs) is None


def test_frame_check_catches_translation():
    """**이 시험이 2026-10-17 의 결함을 잡는다.**

    메시와 군집이 평행이동만큼 어긋나면 — 모양도 크기도 같아서 그림은
    멀쩡해 보인다 — 사유를 돌려줘야 한다.
    """
    shifted = [(c[0] + 40, c[1] + 40, c[2] + 40) for c in
               [(1, 1, 1), (5, 5, 5), (9, 9, 9)]]
    note = _hotspot_frame_check(_MESH, [_Run([_item(7, shifted)])])
    assert note is not None
    assert "좌표계" in note
    assert "3/3" in note


def test_frame_check_ignores_parts_not_in_mesh():
    """메시에 없는 파트의 군집은 판정에 넣지 않는다 (밖에 있는 게 당연하다)."""
    runs = [_Run([_item(99, [(500, 500, 500)]), _item(7, [(5, 5, 5)])])]
    assert _hotspot_frame_check(_MESH, runs) is None


def test_frame_check_silent_without_data():
    """판정할 군집이 없으면 아무 말도 하지 않는다 — 없는 문제를 만들지 않는다."""
    assert _hotspot_frame_check(_MESH, []) is None
    assert _hotspot_frame_check({"bbox": [0, 0, 0, 1, 1, 1], "p": []}, []) is None
    assert _hotspot_frame_check({"p": [7]}, [_Run([_item(7, [(0, 0, 0)])])]) is None


def test_load_is_quiet_when_nothing_requested():
    """군집이 없으면 메시도 사유도 없다 — 빈 캠페인에 경고를 띄우지 않는다."""
    assert _load_hotspot_mesh("", [1]) == (None, None)
    assert _load_hotspot_mesh("/nonexistent", []) == (None, None)


def test_load_refuses_without_d3plot(tmp_path):
    """d3plot 이 없으면 **원본 .k 로 대신하지 않는다.**

    원본은 좌표계가 다를 수 있다(평행이동). 틀린 좌표계의 메시를 그리느니
    만들지 않고 사유를 말한다.
    """
    mesh, note = _load_hotspot_mesh(str(tmp_path), [1, 2])
    assert mesh is None
    assert note is not None and "d3plot" in note
