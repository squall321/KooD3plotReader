# 캔버스 뷰어 호버 집기(hs3dPick) 규칙 — 겹칠 때 앞쪽을 집는지 node 로 검증
"""핫스팟 3D 캔버스 뷰어의 호버.

실측 배경 (2026-10-18). Plotly 뷰어에는 호버가 있지만 그쪽은 값 상위
HS3D_PLOTLY_MAX 개만 그린다. 전수를 보는 쪽은 캔버스인데 거기에 호버가 없었다.
26각도 실데이터에서 군집 651개 중 **라벨은 겹침 때문에 16개만** 찍히므로,
나머지 635개는 "보이기는 하는데 어느 각도의 무엇인지 알 수 없는" 공이었다.

여기서 못박는 규칙.
- 겹치면 **앞쪽**(큰 z)을 집는다 — 눈에 보이는 것이 집혀야 한다.
- 작은 군집도 집힌다 (최소 집기 반경).
- 반경 밖은 안 집는다 — 아무 데나 집으면 엉뚱한 군집을 읽는다.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import jsutil as js

_JS = (Path(__file__).resolve().parents[1]
       / "koo_sphere_report" / "report" / "html_report.py").read_text(encoding="utf-8")

pytestmark = pytest.mark.skipif(js.node_bin() is None, reason="node 없음")

# hs3dPick 은 전역 HS3D 만 본다 — 그 자리를 시험이 채운다.
_PRELUDE = "const HS3D = { pick: null, pickMeasure: 'stress_max' };\n"


def _pick(spheres_js, mx, my):
    src = (_PRELUDE
           + js.extract_functions(_JS, ["hs3dPick"])
           + f"\nHS3D.pick = {spheres_js};\n"
           + f"const r = hs3dPick({mx}, {my});\n"
           + "console.log(r ? r.id : 'none');\n")
    return js.run_js(src)[0]


def _sph(id_, x, y, z, r):
    return f"{{id:'{id_}',x:{x},y:{y},z:{z},r:{r}}}"


def test_picks_front_when_overlapping():
    """**이 시험이 핵심이다** — 겹친 두 군집에서 뒤엣것을 집으면 거짓 정보가 된다."""
    back = _sph("back", 100, 100, -50, 60)
    front = _sph("front", 100, 100, 50, 40)
    assert _pick(f"[{back},{front}]", 100, 100) == "front"
    # 순서를 바꿔도 같아야 한다 (목록 순서가 아니라 z 로 고른다)
    assert _pick(f"[{front},{back}]", 100, 100) == "front"


def test_outside_radius_is_not_picked():
    """반경 밖은 안 집는다 — 빈 자리에서 툴팁이 뜨면 없는 것을 읽게 된다."""
    assert _pick(f"[{_sph('a', 100, 100, 0, 30)}]", 400, 400) == "none"


def test_small_cluster_still_pickable():
    """반경 2px 짜리도 집혀야 쓸 수 있다 (최소 집기 반경)."""
    # 반경 2 인 구의 중심에서 20px 떨어진 자리 — 최소 반경(28) 안이다
    assert _pick(f"[{_sph('tiny', 100, 100, 0, 2)}]", 120, 100) == "tiny"


def test_far_outside_min_radius_is_not_picked():
    """최소 반경도 무한하지 않다 — 40px 밖이면 안 집는다."""
    assert _pick(f"[{_sph('tiny', 100, 100, 0, 2)}]", 145, 100) == "none"


def test_empty_list_is_safe():
    """목록이 비거나 없을 때 터지지 않는다 (파트를 전부 끈 상태)."""
    assert _pick("[]", 10, 10) == "none"
    assert _pick("null", 10, 10) == "none"


def test_hover_handler_is_wired_to_canvas():
    """함수만 있고 결선이 없으면 무음 실패다 — 캔버스에 mousemove 가 붙는지."""
    assert "cv.addEventListener('mousemove'" in _JS, "캔버스에 호버가 안 붙었다"
    assert "cv.addEventListener('mouseleave', hs3dHideTip)" in _JS
    # 돌리는 중에는 방해하지 않는다
    body = _JS[_JS.index("cv.addEventListener('mousemove'"):][:400]
    assert "HS3D.drag" in body, "드래그 중에도 툴팁이 뜬다"


def test_tip_reports_missing_not_zero():
    """값이 없으면 0 이 아니라 '미계측' 이다 — [[null-guard]] 와 같은 규칙."""
    body = js.extract_functions(_JS, ["hs3dShowTip"])
    assert "미계측" in body
    assert "isFinite" in body
