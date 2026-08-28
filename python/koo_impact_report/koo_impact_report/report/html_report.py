"""Single-file interactive HTML report generator for multi-face partial impact.

Generates a fully self-contained HTML (no external scripts/CSS/fonts) that
visualises a 3D-DOE (face × position × part) drop-weight impact study, plus
the Energy Flow Dynamics page (force-directed graph, sunburst, sankey,
time-force heatmap, conservation check).

Design language follows Test_006_SphereDrop_Report.html — dark Bloomberg
aesthetic, dense KPI grids, JetBrains Mono numerics, panel.ph headers,
reveal-on-scroll, cyan/pink/purple accent palette.

Public API
----------
    html_str = generate_html(report: ImpactReport) -> str

When ``report.results`` is empty the generator falls back to a built-in mock
dataset so the page is still visually testable (5 parts, 8 contact edges,
6 faces × 6 positions). The same mock payload also drives the Energy-Flow
visualisations whenever a particular case has no EnergyFlow attached.
"""
from __future__ import annotations

import json

from ..models import ImpactReport
from .payload import _build_payload
from .payload.common import _esc, _Encoder


# ---------------------------------------------------------------------------
# HTML template — CSS
# ---------------------------------------------------------------------------

from .assets.css import _CSS


from .assets.topbar import _build_topbar  # noqa: F401 — re-export (분할 과도기)


from .sections.s1_overview import _PAGE1  # noqa: F401
from .sections.s2_inspector import _PAGE2  # noqa: F401
from .sections.s3_verdict import _PAGE3  # noqa: F401
from .sections.s4_part_g import _PAGE4  # noqa: F401
from .sections.s5_doe import _PAGE5  # noqa: F401
from .sections.s6_deep import _PAGE6  # noqa: F401
from .sections.s7_insights import _PAGE7  # noqa: F401
from .sections.s8_physics import _PAGE8  # noqa: F401
from .sections.s9_position import _PAGE9  # noqa: F401
from .sections.s10_set import _PAGE10  # noqa: F401










# ---------------------------------------------------------------------------
# JavaScript template — large but self-contained
# ---------------------------------------------------------------------------

from .assets.js_core import (  # noqa: F401
    _JS_HEAD, _JS_WIRING, _JS_TABS, _JS_LAZY, _JS_TAIL,
)
from .sections.s1_overview import _JS_S1  # noqa: F401
from .sections.s2_inspector import _JS_S2  # noqa: F401
from .sections.s3_verdict import _JS_S3  # noqa: F401
from .sections.s4_part_g import _JS_S4  # noqa: F401
from .sections.s5_doe import _JS_TRAJ, _JS_S5_DOE, _JS_S5_MAIN  # noqa: F401
from .sections.s6_deep import _JS_S6  # noqa: F401
from .sections.s7_insights import _JS_S7  # noqa: F401
from .sections.s8_physics import _JS_S8  # noqa: F401
from .sections.s9_position import _JS_S9  # noqa: F401
from .sections.s10_set import _JS_S10  # noqa: F401

# 원본 파일 순서 보존 조립 — 1단계 불변식: join == 분할 전 _JS 바이트 동일.
_JS = "".join((
    _JS_HEAD, _JS_S1, _JS_S2, _JS_S3, _JS_WIRING, _JS_TRAJ, _JS_S4,
    _JS_S5_DOE, _JS_S6, _JS_S7, _JS_S8, _JS_S9, _JS_S10, _JS_TABS, _JS_S5_MAIN,
    _JS_LAZY, _JS_TAIL,
))


# ---------------------------------------------------------------------------
# Top-level generator
# ---------------------------------------------------------------------------


def _script_safe(js_text: str) -> str:
    """<script> 블록에 넣을 JSON 을 HTML 파서로부터 안전하게 만든다.

    문자열 값 어디든 "</script>" 가 들어가면 브라우저가 그 지점에서 스크립트를
    끊어 보고서 전체가 깨진다 (경로·파트명·note 등 무엇이든 통로가 된다).
    "</" 를 "<\\/" 로 바꾼다 — JSON/JS 에서 동등한 문자열이고 HTML 파서는
    더 이상 종료 태그로 보지 않는다.
    """
    return js_text.replace("</", "<\\/")


def generate_html(report: ImpactReport, payload: dict | None = None,
                  deferred: bool = False) -> str:
    """Generate the full single-file HTML report.

    The output is fully self-contained — no external scripts, stylesheets,
    fonts, or images. JavaScript reads from one ``const DATA`` payload that
    is JSON-encoded inline.

    Args:
        payload: 미리 만든 payload (emit.py 청크 매니페스트 주입용). None 이면
            여기서 생성 — 기존 호출부/골든 테스트와 완전 호환.
        deferred: True 면 payload 를 ``<script type="application/json">`` 블록에
            두고 DATA 는 boot 시 JSON.parse (tier C/D, P4-3).
    """
    if payload is None:
        payload = _build_payload(report)
    payload["meta"]["_n_faces"] = len(payload["faces"])
    payload["meta"]["_n_runs"] = len({(r["face"], r["pos_id"]) for r in payload["results"]})

    kpi = payload["kpi"]
    worst = kpi["worst"]

    # SSR g-divisor — JS 와 일관되게 acc unit 기반.
    # mm/s² → 9810,  m/s²/mm/ms² → 9.81.  raw mm/s² 를 'G' 라벨로 출력하면 안 됨.
    _acc_label = (payload.get("unit_labels") or {}).get("acc", "")
    if _acc_label == "mm/s²":
        _g_div_ssr = 9810.0
    elif _acc_label in ("m/s²", "mm/ms²"):
        _g_div_ssr = 9.81
    else:
        _g_div_ssr = 9810.0  # legacy default
    _worst_g_in_G = (worst.get("g", 0) or 0) / _g_div_ssr
    _kpi_worst_g_in_G = (kpi.get("worst_g", 0) or 0) / _g_div_ssr

    page1 = (
        _PAGE1
        .replace("__N_FACES__", str(kpi["n_faces"]))
        .replace("__N_POSITIONS__", str(kpi["n_positions"]))
        .replace("__N_PARTS__", str(kpi["n_parts"]))
        .replace("__N_PAIRS__", str(kpi["n_pairs"]))
        .replace("__WORST_LINE__", _esc(f"{worst['face']} · X {worst['x']:.1f} / Y {worst['y']:.1f}"))
        .replace("__WORST_PART_LINE__", _esc(f"{_worst_g_in_G:,.0f} G  ON  {worst['part_name']}"))
        .replace("__WORST_G__", f"{_kpi_worst_g_in_G:,.0f}")
        .replace("__WORST_S__", f"{kpi['worst_s']:.0f}")
        .replace("__N_CRIT__", str(kpi["n_critical"]))
        .replace("__N_SAFE__", str(kpi["n_safe"]))
        .replace("__DISS_PCT__", f"{kpi['diss_pct']:.1f}" if kpi.get('diss_pct') is not None else "—")
        .replace("__IMP_SUB__", _esc(payload["meta"]["impactor"]["type"]))
    )

    topbar = _build_topbar(payload["meta"], payload.get("unit_labels"))
    payload_json = _script_safe(json.dumps(payload, cls=_Encoder, separators=(",", ":")))
    if deferred:
        # JSON 데이터 블록 + boot 시 JSON.parse — 대용량에서 JS 리터럴보다
        # 파싱이 빠르고 피크 메모리가 낮다. "</" 는 태그 조기 종료 방지 이스케이프.
        data_block = ("<script type=\"application/json\" id=\"koo-data\">"
                      + payload_json.replace("</", "<\\/")
                      + "</script>\n")
        js = _JS.replace(
            "__PAYLOAD__",
            "JSON.parse(document.getElementById('koo-data').textContent)")
    else:
        data_block = ""
        js = _JS.replace("__PAYLOAD__", payload_json)

    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"ko\">\n"
        "<head>\n"
        "<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"<title>{_esc(payload['meta']['project'])} — Multi-Face Impact Report</title>\n"
        "<link rel=\"icon\" href=\"data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'><rect width='64' height='64' rx='12' fill='%230e1320'/><text x='50%25' y='58%25' text-anchor='middle' font-family='monospace' font-size='30' font-weight='bold' fill='%234dd6ff'>K</text></svg>\">\n"
        "<style>\n" + _CSS + "\n</style>\n"
        "</head>\n"
        "<body>\n"
        + topbar
        + page1
        + _PAGE2
        + _PAGE3
        + _PAGE4
        + _PAGE5
        + _PAGE6
        + _PAGE7
        + _PAGE8
        + _PAGE9
        + _PAGE10
        + data_block
        + "<script>\n" + js + "\n</script>\n"
        "</body>\n</html>\n"
    )
