# Plotly 부분 번들 규칙 — 쓰는 트레이스가 번들에 없으면 '조용히 빈 차트' 가 된다
"""번들에 없는 트레이스를 쓰면 예외 없이 **빈 차트**가 나온다.

실측 배경 (2026-10-17): `cdn.plot.ly` 참조를 번들로 바꾸면서 부분 번들을 골랐다.
`plotly-gl3d` 는 1.6MB 로 전체(4.7MB)보다 훨씬 작지만 **`bar` 가 없다.**
그런데 `batch_report.py` 는 bar 를 쓴다 — 그대로 gl3d 를 물렸으면 배치 요약의
막대 차트가 전부 빈 칸이 되고, 에러 하나 없이 "데이터가 없나 보다" 로 읽혔을 것이다.

그래서 여기서 못박는다 — **리포트가 쓰는 트레이스 집합 ⊆ 그 리포트가 고른 번들의
트레이스 집합.** 나중에 누가 deep report 에 막대 차트를 하나 넣으면 이 시험이 깨진다.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from koo_deep_report.report import plotly_bundle  # noqa: E402

_REPORT_DIR = Path(plotly_bundle.__file__).resolve().parent

# 공식 부분 번들이 담는 트레이스 (plotly.js v3 CUSTOM_BUNDLE.md).
# 번들 파일 자체에서 실측으로 확인한 목록이다 — .work/envelope_g1/check_bundles.py
# 가 실제 브라우저에서 각 트레이스를 그려 본다.
_BUNDLE_TRACES = {
    plotly_bundle.GL3D: {"scatter", "scatter3d", "surface", "mesh3d",
                         "isosurface", "volume", "cone", "streamtube"},
    plotly_bundle.BASIC: {"scatter", "bar", "pie"},
}

# 어느 리포트가 어느 번들을 쓰는가 (호출부와 일치해야 한다)
_USES = {
    "html_report.py": plotly_bundle.GL3D,
    "batch_report.py": plotly_bundle.BASIC,
}


def _traces_used(src: str) -> set[str]:
    """소스에서 `type: 'xxx'` 로 쓰인 트레이스 이름.

    layout 의 shape type(`line`·`rect`·`circle`)과 카메라(`orthographic`),
    `all` 같은 값도 같은 문법으로 잡히므로 트레이스가 아닌 것은 걸러낸다.
    """
    found = set(re.findall(r"""type: *['"]([a-z0-9]+)['"]""", src))
    return found - {"line", "rect", "circle", "path", "orthographic",
                    "perspective", "all", "linear", "log", "date", "category"}


@pytest.mark.parametrize("fname,bundle", sorted(_USES.items()))
def test_used_traces_are_in_the_chosen_bundle(fname, bundle):
    src = (_REPORT_DIR / fname).read_text(encoding="utf-8")
    used = _traces_used(src)
    assert used, f"{fname} 에서 트레이스를 하나도 못 찾았다 — 정규식이 낡았는지 확인"
    missing = used - _BUNDLE_TRACES[bundle]
    assert not missing, (
        f"{fname} 이 {bundle} 에 없는 트레이스를 쓴다: {sorted(missing)}. "
        f"그대로 두면 예외 없이 빈 차트가 된다 — 번들을 바꾸거나 차트를 바꿀 것")


@pytest.mark.parametrize("fname,bundle", sorted(_USES.items()))
def test_source_picks_the_bundle_this_test_assumes(fname, bundle):
    """호출부가 실제로 그 번들을 고르는지 — 이 시험이 헛돌지 않게."""
    src = (_REPORT_DIR / fname).read_text(encoding="utf-8")
    const = "GL3D" if bundle == plotly_bundle.GL3D else "BASIC"
    assert f"plotly_bundle.{const}" in src, f"{fname} 이 {const} 를 고르지 않는다"


@pytest.mark.parametrize("bundle", sorted(_BUNDLE_TRACES))
def test_bundle_is_vendored(bundle):
    """번들이 저장소에 실제로 있어야 한다 — 없으면 CDN 으로 돌아간다."""
    assert plotly_bundle.bundle_path(bundle) is not None, (
        f"{bundle} 이 vendor/ 에 없다. 배포본은 네트워크 없이 돌아야 한다")


def test_no_cdn_script_tag_left():
    """CDN `<script src>` 가 남아 있으면 폐쇄망에서 차트가 조용히 죽는다."""
    for fname in _USES:
        src = (_REPORT_DIR / fname).read_text(encoding="utf-8")
        assert 'src="https://cdn.plot.ly' not in src, f"{fname} 에 CDN 태그가 남았다"


def test_script_tag_embeds_the_bundle():
    tag = plotly_bundle.script_tag(plotly_bundle.GL3D)
    assert tag.startswith("<script>") and "cdn.plot.ly/plotly-" not in tag[:200]
    assert "plotly.js (gl3d" in tag[:400], "번들 배너가 없다 — 다른 파일을 넣었나"
    # </script> 로 블록이 일찍 닫히면 안 된다
    assert "</script>" not in tag[:-10]


def test_missing_bundle_warns_instead_of_failing_silently(monkeypatch, tmp_path):
    """번들이 없으면 CDN 으로 돌아가되 **화면에 경고를 남긴다.**

    조용히 CDN 으로 돌아가면 폐쇄망에서 빈 차트가 되고 아무도 이유를 모른다.
    """
    monkeypatch.setattr(plotly_bundle, "_VENDOR", tmp_path)
    tag = plotly_bundle.script_tag(plotly_bundle.GL3D)
    assert "cdn.plot.ly" in tag
    assert "insertBefore" in tag, "경고를 화면에 붙이지 않는다"
