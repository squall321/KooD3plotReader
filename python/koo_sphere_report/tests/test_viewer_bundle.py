# sphere 뷰어 규칙 — 기본은 외부 스크립트 0, plotly 를 골라도 CDN 이 아니라 번들
"""sphere 리포트의 오프라인 원칙.

이 리포트는 외부 스크립트를 **하나도** 쓰지 않는다. 사내망·폐쇄망에서 열리는 것이
전제이고, CDN 을 하나라도 물리면 그곳에서 차트가 에러 없이 빈 칸이 된다.

`--viewer plotly` 는 호버·범례·축을 얻는 선택지다. 그때도 CDN 이 아니라
**번들**을 HTML 안에 넣는다 — 선택지를 쓴다고 오프라인 원칙이 깨지면 안 된다.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from koo_sphere_report.report import html_report, plotly_bundle  # noqa: E402

_SRC = Path(html_report.__file__).resolve()
_MAIN = _SRC.parent.parent / "__main__.py"


def test_bundle_is_vendored():
    """번들이 없으면 CDN 으로 돌아간다 — 배포본은 네트워크 없이 돌아야 한다."""
    assert plotly_bundle.bundle_path() is not None


def test_script_tag_embeds_not_links():
    tag = plotly_bundle.script_tag()
    assert tag.startswith("<script>")
    assert 'src="https://' not in tag
    assert "plotly.js (gl3d" in tag[:400], "다른 번들을 넣었나"


def test_no_external_script_in_template():
    """템플릿에 외부 스크립트·스타일시트가 들어오지 않았는지.

    `{_plotly_script}` 자리는 --viewer plotly 일 때만 채워지고, 그 내용도 번들이다.
    """
    src = _SRC.read_text(encoding="utf-8")
    bad = re.findall(r'<(?:script|link)[^>]*(?:src|href)="(https?://[^"]+)"', src)
    assert not bad, f"외부 리소스를 참조한다: {bad}"


def test_canvas_viewer_embeds_nothing():
    """기본 뷰어는 번들을 **안** 싣는다 — 977KB 리포트가 2.5MB 가 되면 안 된다."""
    src = _SRC.read_text(encoding="utf-8")
    assert '_plotly_script = plotly_bundle.script_tag() if viewer == "plotly" else ""' in src


def test_viewer_choices_are_wired():
    main = _MAIN.read_text(encoding="utf-8")
    assert '"--viewer"' in main
    assert 'choices=["canvas", "plotly"]' in main
    assert 'default="canvas"' in main, "기본이 canvas 가 아니면 오프라인 원칙이 깨진다"
    assert "viewer=args.viewer" in main, "인자가 generate_html 로 전달되지 않는다"


def test_plotly_path_uses_only_bundled_traces():
    """gl3d 번들에 있는 트레이스만 쓴다 — 없는 것은 조용히 빈 차트가 된다."""
    src = _SRC.read_text(encoding="utf-8")
    block = src[src.index("function hs3dDrawPlotly"):src.index("function fmtHs3d")]
    found = set(re.findall(r"""type: *['"]([a-z0-9]+)['"]""", block))
    # layout 쪽 값도 같은 문법이라 걸린다 (카메라 projection 등) — 트레이스만 남긴다
    used = found - {"orthographic", "perspective", "line", "rect", "circle", "path"}
    assert used, "Plotly 경로에서 트레이스를 못 찾았다 — 정규식이 낡았는지 확인"
    assert used <= {"scatter", "scatter3d", "surface", "mesh3d"}, (
        f"gl3d 번들에 없는 트레이스: {sorted(used - {'scatter','scatter3d','surface','mesh3d'})}")
