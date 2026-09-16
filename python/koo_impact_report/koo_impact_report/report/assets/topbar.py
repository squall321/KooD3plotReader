# 보고서 상단 고정 topbar HTML 빌더 (html_report.py 에서 기계적 분할)
from __future__ import annotations

from ..payload.common import _esc


def _build_topbar(meta: dict, unit_labels: dict | None = None) -> str:
    project = _esc(meta["project"])
    imp_type = _esc(meta["impactor"]["type"])
    n_faces = meta.get("_n_faces", 6)
    n_runs = meta.get("_n_runs", 0)
    gen_mode = _esc(meta["generation_mode"])
    dt_s = meta["sim_params"].get("dt", 1e-6)
    t_final = meta["sim_params"].get("t_final", 0.001)
    # Time label is data-driven: show raw seconds when units unspecified,
    # ms when the loader declared a known unit system (LS-DYNA mm-ton-s).
    t_unit = (unit_labels or {}).get("time", "")
    if t_unit == "ms":
        dt_str = f"{dt_s * 1e6:.1f} &micro;s"
        tf_str = f"{t_final * 1e3:.2f} ms"
    else:
        dt_str = f"{dt_s:g}"
        tf_str = f"{t_final:g}"
    # 어느 unified_analyzer 빌드로 분석한 결과인지. 런마다 다르면 경고한다 —
    # 차이가 모델 탓인지 도구 탓인지 구분할 수 없기 때문이다
    # (docs/postproc_gap_2026-09/). 기록이 없으면 아무것도 적지 않는다.
    _prov = meta.get("provenance") or {}
    _builds = _prov.get("analysis_builds") or {}
    _unknown = _prov.get("analysis_builds_unknown") or 0
    if _prov.get("analysis_builds_mixed"):
        _parts = [f"{k}({v})" for k, v in sorted(_builds.items())]
        if _unknown:
            _parts.append(f"기록없음({_unknown})")
        build_span = ('<span class="warn">&#9888; BUILDS <b>'
                      + _esc(", ".join(_parts)) + "</b></span>")
    elif _builds:
        build_span = f'<span>BUILD <b>{_esc(next(iter(_builds)))}</b></span>'
    elif _unknown:
        build_span = '<span>BUILD <b>기록 없음</b></span>'
    else:
        build_span = ""

    return f"""
<div class="topbar">
  <div class="brand">KOOD3PLOT &middot; MULTI-FACE IMPACT</div>
  <div class="meta">
    <span>PROJECT <b>{project}</b></span>
    <span>IMPACTOR <b>{imp_type}</b></span>
    <span>RUNS <b>{n_runs}</b></span>
    <span>FACES <b>{n_faces}</b></span>
    <span>MODE <b>{gen_mode}</b></span>
    <span>&Delta;t <b>{dt_str}</b></span>
    <span>T <b>{tf_str}</b></span>
    {build_span}
  </div>
  <div class="nav">
    <a data-target="s1" class="active">OVERVIEW</a>
    <a data-target="s2">INSPECTOR</a>
    <a data-target="s3">VERDICT</a>
    <a data-target="s4">PER-PART G</a>
    <a data-target="s5" id="navS5">DOE</a>
    <a data-target="s6" id="navS6">DEEP</a>
    <a data-target="s7" id="navS7">INSIGHTS</a>
    <a data-target="s8" id="navS8">PHYSICS</a>
    <a data-target="s9" id="navS9">POSITION</a>
    <a data-target="s10" id="navS10">SET</a>
    <a id="view-mode-btn" onclick="toggleViewMode()" style="opacity:0.75"
       title="탭/스크롤 보기 전환">SCROLL</a>
    <a id="lang-toggle-btn" onclick="toggleLang()" style="opacity:0.75">EN</a>
  </div>
</div>
"""
