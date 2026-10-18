# 미계측(null)을 0 으로 세지 않고 '—' 로 표기하는지 — 화면 JS 를 node 로 실행해 검증
"""HTML payload 의 null 을 읽는 쪽 규칙.

실측 배경 (2026-10-18). sphere 의 HTML payload 는 `json_report` 와 달리 **키를 항상
만들고 값에 null 을 넣는다** (화면 JS 49곳이 그 키를 읽는 구조라 그렇다). 그런데 읽는
쪽에 가드가 없어 두 가지가 났다.

① `null.toFixed()` 로 **탭 3개가 통째로 죽었다** (Statistics · Part Analysis ·
   Render Export). 이건 눈에 보인다.
② **`reduce`·`Math.max` 가 null 을 0 으로 세어 평균이 조용히 틀렸다.** 실측으로
   절반이 미계측인 파트에서 평균이 **50% 깎였다.** 화면에는 멀쩡한 숫자가 떴다.
   ①보다 이쪽이 나쁘다.

여기서 못박는 규칙 — **미계측은 집계에서 빼고, 표기는 '—' 다.**
'값 0' 과 '못 쟀다' 는 다른 말이고, 0 으로 세면 그 구분이 숫자 안으로 사라진다.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import jsutil as js  # noqa: E402

_JS = (Path(__file__).resolve().parents[1]
       / "koo_sphere_report" / "report" / "html_report.py").read_text(encoding="utf-8")

pytestmark = pytest.mark.skipif(js.node_bin() is None, reason="node 없음")


def _eval(expr):
    """헬퍼만 잘라 node 로 식을 평가한다 (문자열 검사가 아니라 실제 실행)."""
    src = js.extract_functions(_JS, ["isNum", "onlyNums", "fxd"]) \
          + f"\nconsole.log(String({expr}));\n"
    return js.run_js(src)[0]


def test_isnum_rejects_null_and_undefined():
    """null·undefined·NaN·Infinity 는 전부 '숫자 아님' 이다."""
    assert _eval("isNum(null)") == "false"
    assert _eval("isNum(undefined)") == "false"
    assert _eval("isNum(NaN)") == "false"
    assert _eval("isNum(Infinity)") == "false"


def test_isnum_accepts_zero():
    """**0 은 값이다.** 미계측과 섞어 버리면 '응력 0' 을 못 나타낸다."""
    assert _eval("isNum(0)") == "true"
    assert _eval("isNum(-3.5)") == "true"


def test_fxd_shows_dash_for_missing():
    assert _eval("fxd(null, 1)") == "—"
    assert _eval("fxd(undefined, 2)") == "—"
    assert _eval("fxd(NaN, 1)") == "—"


def test_fxd_keeps_zero_as_number():
    """0 은 '—' 가 아니라 '0.0' 이다."""
    assert _eval("fxd(0, 1)") == "0.0"
    assert _eval("fxd(12.345, 2)") == "12.35"


def test_onlynums_drops_missing():
    assert _eval("onlyNums([1, null, 2, undefined, NaN, 0]).join(',')") == "1,2,0"


def test_mean_is_not_diluted_by_missing():
    """**이 시험이 2026-10-18 의 조용한 결함을 잡는다.**

    절반이 미계측인 배열에서, null 을 0 으로 세면 평균이 절반으로 깎인다.
    """
    js = "(function(){const a=[100,null,110,null,120,null];" \
         "const n=onlyNums(a);return (n.reduce((x,y)=>x+y,0)/n.length).toFixed(1);})()"
    assert _eval(js) == "110.0"
    # 옛 방식(그대로 reduce)이면 55.0 이 된다 — 그 값이 나오면 안 된다
    old = "(function(){const a=[100,null,110,null,120,null];" \
          "return (a.reduce((x,y)=>x+y,0)/a.length).toFixed(1);})()"
    assert _eval(old) == "55.0", "전제 확인: 옛 방식은 실제로 절반으로 깎인다"


def test_max_is_not_pulled_down_by_missing():
    """Math.max 에 null 이 섞이면 0 으로 세어 음수 데이터의 최대가 0 이 된다."""
    js = "(function(){const n=onlyNums([-5,null,-3,null]);" \
         "return Math.max(...n).toFixed(1);})()"
    assert _eval(js) == "-3.0"
    old = "Math.max(-5, null, -3, null).toFixed(1)"
    assert _eval(old) == "0.0", "전제 확인: 옛 방식은 0 을 최대로 본다"


@pytest.mark.parametrize("site", [
    "renderStatistics", "buildStressEnvelopeSVG", "reDrawMiniMollweide",
])
def test_crash_sites_guard_nulls(site):
    """죽던 세 자리가 가드를 쓰는지 — 가드 없이 toFixed 를 부르지 않는다."""
    body = js.extract_functions(_JS, [site])
    assert "isNum(" in body or "fxd(" in body, f"{site} 에 null 가드가 없다"
