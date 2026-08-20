# 세트별 피크 표 + 3면 뷰 갤러리(스냅샷 클릭 시 영상 재생)를 담는 단독 HTML 빌더
"""Custom Report 단독 HTML.

미디어는 전부 상대경로 참조 (base64 인라인 금지 — 용량 원칙).
HTML 은 <out>/custom_report.html 에 두므로 media 상대경로
"set_reports/<safe>/..." 가 그대로 성립한다. file:// 에서도
<img>/<video> src 는 동작한다.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

from ..runner import RunResult, SetResult

# 필드 표기 (순서 = 표 순서)
_FIELD_LABELS = [
    ("von_mises", "σ_vm [MPa]"),
    ("max_principal_stress", "σ1 [MPa]"),
    ("min_principal_stress", "σ3 [MPa]"),
    ("eff_plastic_strain", "ε_p"),
    ("vm_strain", "ε_vm"),
    ("max_principal_strain", "ε1"),
    ("min_principal_strain", "ε3"),
]

_PLANE_LABELS = {"xy": "XY (탑뷰, Z축)", "yz": "YZ (측면, X축)", "zx": "ZX (정면, Y축)"}

_CSS = """
:root { --bg:#0f1115; --panel:#171a21; --fg:#e6e6e6; --fg2:#9aa0aa; --acc:#4ea1ff;
        --warn:#f2c94c; --err:#eb5757; --radius:8px; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: var(--bg); color: var(--fg);
       font-family: 'Segoe UI', 'Malgun Gothic', sans-serif; padding: 24px; }
h1 { font-size: 22px; margin-bottom: 4px; }
.sub { color: var(--fg2); font-size: 13px; margin-bottom: 20px; }
.set-card { background: var(--panel); border-radius: var(--radius);
            padding: 18px 20px; margin-bottom: 22px; }
.set-card h2 { font-size: 17px; margin-bottom: 2px; }
.set-meta { color: var(--fg2); font-size: 12px; margin-bottom: 10px; }
.notes { margin: 8px 0; }
.note { color: var(--warn); font-size: 12px; padding: 2px 0; }
table { border-collapse: collapse; margin: 10px 0 14px; font-size: 13px; }
th, td { border: 1px solid #2a2f3a; padding: 5px 12px; text-align: right; }
th { background: #1e232d; color: var(--fg2); font-weight: 600; }
td.name { text-align: left; }
td.na { color: var(--fg2); opacity: .55; }
.gallery { display: flex; flex-wrap: wrap; gap: 14px; }
.shot { width: 340px; }
.shot img { width: 100%; border-radius: 6px; border: 1px solid #2a2f3a;
            cursor: pointer; display: block; }
.shot .cap { color: var(--fg2); font-size: 12px; margin-top: 4px; }
.shot .cap b { color: var(--fg); }
.play-hint { color: var(--acc); }
#modal { display: none; position: fixed; inset: 0; background: rgba(0,0,0,.85);
         z-index: 50; align-items: center; justify-content: center; }
#modal.open { display: flex; }
#modal video { max-width: 92vw; max-height: 88vh; }
#modal .x { position: absolute; top: 16px; right: 24px; color: #fff;
            font-size: 28px; cursor: pointer; }
.missing { color: var(--fg2); font-size: 12px; font-style: italic; }
"""

_JS = """
function openVideo(src) {
  var m = document.getElementById('modal');
  m.innerHTML = '<span class="x" onclick="closeVideo()">&times;</span>' +
                '<video controls autoplay src="' + src + '"></video>';
  m.classList.add('open');
}
function closeVideo() {
  var m = document.getElementById('modal');
  m.classList.remove('open');
  m.innerHTML = '';
}
document.addEventListener('keydown', function (e) {
  if (e.key === 'Escape') closeVideo();
});
document.addEventListener('click', function (e) {
  if (e.target && e.target.id === 'modal') closeVideo();
});
"""


def _fmt(v: float, field: str) -> str:
    if "strain" in field:
        return f"{v:.6f}"
    return f"{v:.2f}"


def _set_section(sr: SetResult) -> str:
    m = sr.metrics
    parts: list[str] = []

    title = html.escape(str(m.get("title") or ""))
    head = html.escape(sr.name)
    sub_bits = [f"{html.escape(str(m.get('set_type') or '?'))} set {m.get('set_id')}"]
    if title:
        sub_bits.append(f"제목 '{title}'")
    rp = m.get("resolved_parts") or []
    mp = m.get("missing_parts") or []
    if rp:
        sub_bits.append("파트 " + ", ".join(str(p) for p in rp))
    if mp:
        sub_bits.append(f"누락 {len(mp)}개: " + ", ".join(str(p) for p in mp))

    parts.append(f'<div class="set-card"><h2>{head}</h2>')
    parts.append(f'<div class="set-meta">{" · ".join(sub_bits)}</div>')

    notes = m.get("notes") or []
    if notes:
        parts.append('<div class="notes">')
        for n in notes:
            parts.append(f'<div class="note">⚠ {html.escape(str(n))}</div>')
        parts.append("</div>")

    # ---- 피크 표 ----
    fields = {f.get("field"): f for f in (m.get("fields") or [])}
    if fields:
        parts.append("<table><thead><tr><th>필드</th><th>피크</th><th>시각 [s]</th>"
                     "<th>요소</th><th>파트</th></tr></thead><tbody>")
        for key, label in _FIELD_LABELS:
            f = fields.get(key)
            if f is None:
                continue
            if f.get("measured"):
                parts.append(
                    f'<tr><td class="name">{label}</td>'
                    f'<td>{_fmt(float(f["peak"]), key)}</td>'
                    f'<td>{float(f["peak_time"]):.6f}</td>'
                    f'<td>{f.get("peak_element_id", "")}</td>'
                    f'<td>{f.get("peak_part_id", "")}</td></tr>')
            else:
                note = html.escape(str(f.get("note") or "미계측"))
                parts.append(
                    f'<tr><td class="name">{label}</td>'
                    f'<td class="na" colspan="4">— ({note})</td></tr>')
        parts.append("</tbody></table>")

    # ---- 뷰 갤러리: 스냅샷 클릭 → 영상 ----
    shots: list[str] = []
    for stem, rel in sorted(sr.media.items()):
        if not stem.startswith("peak_"):
            continue
        # peak_<plane>_<field>
        rest = stem[len("peak_"):]
        plane, _, fname = rest.partition("_")
        video_rel = sr.media.get(f"view_{plane}_{fname}")
        cap_plane = _PLANE_LABELS.get(plane, plane)
        cap = f"<b>{cap_plane}</b> · {html.escape(fname)} 피크 시각"
        if video_rel:
            img = (f'<img src="{rel}" loading="lazy" '
                   f'onclick="openVideo(\'{video_rel}\')" '
                   f'title="클릭하면 영상 재생">')
            cap += ' · <span class="play-hint">▶ 클릭 시 영상</span>'
        else:
            img = f'<img src="{rel}" loading="lazy">'
        shots.append(f'<div class="shot">{img}<div class="cap">{cap}</div></div>')

    # 스냅샷 없이 영상만 있는 경우도 노출
    for stem, rel in sorted(sr.media.items()):
        if not stem.startswith("view_"):
            continue
        rest = stem[len("view_"):]
        plane, _, fname = rest.partition("_")
        if f"peak_{plane}_{fname}" in sr.media:
            continue
        cap_plane = _PLANE_LABELS.get(plane, plane)
        shots.append(
            f'<div class="shot"><video controls preload="none" src="{rel}" '
            f'style="width:100%"></video>'
            f'<div class="cap"><b>{cap_plane}</b> · {html.escape(fname)}</div></div>')

    if shots:
        parts.append('<div class="gallery">' + "".join(shots) + "</div>")
    elif rp:
        parts.append('<div class="missing">뷰 산출물 없음 — video/peak_snapshot 설정 '
                     "또는 위 경고를 확인.</div>")

    parts.append("</div>")
    return "".join(parts)


def build_html(result: RunResult, d3plot: str, out_path: str | Path) -> str:
    """단독 HTML 생성. 반환값은 파일 경로."""
    body: list[str] = []
    body.append("<h1>Custom Report — 세트 후처리</h1>")
    body.append(f'<div class="sub">d3plot: {html.escape(d3plot)} · 세트 '
                f"{len(result.sets)}개</div>")

    if not result.sets:
        body.append('<div class="set-card"><div class="missing">세트 산출물이 없다. '
                    "unified_analyzer 로그와 세트 파일을 확인.</div></div>")

    for sr in result.sets:
        body.append(_set_section(sr))

    body.append('<div id="modal"></div>')

    doc = ("<!doctype html><html><head><meta charset='utf-8'>"
           "<title>Custom Report</title>"
           f"<style>{_CSS}</style></head><body>"
           + "".join(body) +
           f"<script>{_JS}</script></body></html>")

    out_path = Path(out_path)
    out_path.write_text(doc, encoding="utf-8")
    return str(out_path)
