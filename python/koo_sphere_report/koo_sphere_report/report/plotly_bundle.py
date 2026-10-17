# --viewer plotly 일 때 Plotly gl3d 번들을 HTML 에 끼워 넣는 모듈 (sphere 전용)
"""Plotly 를 CDN 이 아니라 **번들로** 싣는다.

왜. 리포트는 단일 HTML 파일로 메일·사내망을 떠돈다. `cdn.plot.ly` 를 참조하면
네트워크가 없는 곳에서 스크립트 로드가 실패하고, 차트는 **에러도 없이 빈 칸**이
된다. 보는 사람은 "값이 없나 보다" 로 읽는다 — 이 저장소가 가장 싫어하는 무음 실패다.

부분 번들을 쓰는 이유. 전체 `plotly.min.js` 는 4.7MB 다. 쓰는 트레이스만 든
부분 번들이면 1.0~1.6MB 로 끝난다.

sphere 의 기본 뷰어는 **자체 캔버스**라 번들이 아예 안 들어간다. `--viewer plotly`
를 줬을 때만 gl3d(1.6MB)를 싣는다 — 쓰는 트레이스가 mesh3d·scatter3d 뿐이라
전체 번들(4.7MB)은 필요 없다.
"""
from __future__ import annotations

from pathlib import Path

GL3D = "plotly-gl3d.min.js"      # scatter · scatter3d · surface · mesh3d

_VENDOR = Path(__file__).resolve().parent / "vendor"
_CDN = "https://cdn.plot.ly/plotly-2.27.0.min.js"


def _script_safe(js: str) -> str:
    """`</script>` 로 스크립트 블록이 일찍 닫히는 것을 막는다.

    `</` 를 `<\\/` 로 바꾼다 — 자바스크립트 문자열에서도 정규식에서도 같은 값이고,
    HTML 파서는 더 이상 종료 태그로 보지 않는다.
    """
    return js.replace("</", "<\\/")


def script_tag(bundle: str = GL3D) -> str:
    """번들을 통째로 넣은 `<script>` 블록. 번들이 없으면 CDN + 눈에 보이는 경고.

    없을 때 조용히 CDN 으로 돌아가면 폐쇄망에서 빈 차트가 되고, 그 사실을
    아무도 모른다. 그래서 경고를 화면에 남긴다.
    """
    path = _VENDOR / bundle
    try:
        js = path.read_text(encoding="utf-8")
    except OSError:
        return (
            f'<script src="{_CDN}"></script>\n'
            f'<script>document.addEventListener("DOMContentLoaded",function(){{'
            f'var d=document.createElement("div");'
            f'd.style.cssText="background:#5a4300;color:#ffe9a8;padding:8px 12px;'
            f'font:13px system-ui;border-bottom:1px solid #7a5c00";'
            f'd.textContent="\\u26a0 Plotly \\ubc88\\ub4e4({bundle})\\uc744 '
            f'\\ucc3e\\uc9c0 \\ubabb\\ud574 CDN \\uc744 \\ucc38\\uc870\\ud569\\ub2c8\\ub2e4 '
            f'\\u2014 \\ub124\\ud2b8\\uc6cc\\ud06c\\uac00 \\uc5c6\\ub294 \\uace7\\uc5d0\\uc11c\\ub294 '
            f'\\ucc28\\ud2b8\\uac00 \\ube44\\uc5b4 \\ubcf4\\uc785\\ub2c8\\ub2e4.";'
            f'document.body.insertBefore(d,document.body.firstChild);}});</script>'
        )
    return f"<script>\n{_script_safe(js)}\n</script>"


def bundle_path(bundle: str = GL3D) -> Path | None:
    """번들 파일 경로 (없으면 None) — 시험·점검이 존재를 확인할 때 쓴다."""
    p = _VENDOR / bundle
    return p if p.is_file() else None
