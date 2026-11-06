# 장면을 벡터 SVG 로 — 같은 평행 투영 카메라, 앞면만 · 깊이 순서 · 음영, 호버하면 파트 이름 · 값이 뜬다
"""외부 라이브러리 없이 쓴다(폐쇄망 안전). 그리는 순서가 깊이 순서라 다각형을 파트별 <g> 로 묶을 수 없다 — 대신 다각형마다
`data-p`(파트 번호)를 달고, 내장 스크립트가 호버한 파트를 통째로 강조하고 툴팁(이름 · 이 순간 최대 · 안전율)을 띄운다.
스크립트가 안 도는 곳(<img> 로 넣은 경우 등)을 위해 다각형마다 `<title>` 도 단다.

이음새 — 맞닿은 다각형 사이에 안티에일리어싱 틈이 보이지 않게, 불투명한 타겟 면은 같은 색 0.6 px 테두리를 준다.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

import numpy as np

from . import colors as K
from .mesh import SHELL
from .scene import Scene, face_normals


def _f(x: float) -> str:
    return f"{x:.1f}".rstrip("0").rstrip(".")


def _fmt(v: float) -> str:
    return f"{v:.4g}" if np.isfinite(v) else "—"


def write(scene: Scene, out: str | Path, title_lines: list[str], part_info: dict[int, dict] | None = None,
          unit: str = "", legend_title: str = "von Mises") -> Path:
    s, cam = scene.surf, scene.cam
    W, H = cam.width, cam.height
    part_info = part_info or {}
    sel = np.nonzero(scene.target_mask | scene.context_mask)[0]
    faces = s.faces[sel]
    nrm = face_normals(s.coords, faces)
    # 닫힌 껍질(솔리드 · 두꺼운 셸)은 뒷면을 버린다. 셸은 양면이라 둔다.
    front = (nrm @ cam.direction) < 0
    keep = front | (s.face_kind[sel] == SHELL)
    sel, faces, nrm = sel[keep], faces[keep], nrm[keep]

    used = np.unique(faces[faces >= 0])
    proj = np.zeros((len(s.coords), 3))
    proj[used] = cam.project(s.coords[used])
    # 화면 밖 면은 버린다 — 카메라가 타겟에 맞춰져 있어 멀리 있는 주변 파트 면이 많다(파일 크기)
    f4 = np.where(faces >= 0, faces, faces[:, :1])
    px, py = proj[f4, 0], proj[f4, 1]
    on = (px.max(axis=1) >= 0) & (px.min(axis=1) <= W) & (py.max(axis=1) >= 0) & (py.min(axis=1) <= H)
    sel, faces, nrm = sel[on], faces[on], nrm[on]
    pz = np.where(faces >= 0, proj[np.maximum(faces, 0), 2], np.nan)
    depth = np.nanmean(pz, axis=1)
    is_t = scene.target_mask[sel]
    # 타겟을 늘 맨 위에 그린다 — 앞을 가린 반투명 주변 파트가 타겟 색을 회색으로 바래게 하지 않게(PNG 와 같다).
    # 각 무리 안에서는 먼 것부터(화가 알고리즘).
    order = np.lexsort((-depth, is_t))
    light = -cam.direction + 0.45 * cam.up - 0.35 * cam.right
    light = light / np.linalg.norm(light)
    base = np.where(is_t[:, None], K.rgb(s.face_value[sel], *scene.clim), np.array(K.CONTEXT)[None, :])
    fill = K.hex_colors(K.shade(base, nrm, light))

    pid = s.face_part[sel]
    names = {int(p): str((part_info.get(int(p)) or {}).get("name") or s.part_titles.get(int(p)) or f"Part {int(p)}")
             for p in np.unique(pid)}
    out_lines = []
    for i in order:
        f = faces[i]
        pts = proj[f[f >= 0]]
        d = "M" + "L".join(f"{_f(x)} {_f(y)}" for x, y in pts[:, :2]) + "Z"
        p = int(pid[i])
        if is_t[i]:
            out_lines.append(f'<path d="{d}" fill="{fill[i]}" stroke="{fill[i]}" data-p="{p}">'
                             f'<title>{html.escape(names[p])}</title></path>')
        else:
            out_lines.append(f'<path d="{d}" fill="{fill[i]}" class="c" data-p="{p}">'
                             f'<title>{html.escape(names[p])}</title></path>')

    lo, hi = scene.clim
    lx, ly, lw, lh = K.legend_box(W, H)
    n_steps = 64
    grad = []
    for k in range(n_steps):
        v = lo + (hi - lo) * (k + 0.5) / n_steps
        c = K.hex_colors(K.rgb(np.array([v]), lo, hi))[0]
        y0 = ly + lh * (1 - (k + 1) / n_steps)
        grad.append(f'<rect x="{_f(lx)}" y="{_f(y0)}" width="{_f(lw)}" height="{_f(lh / n_steps + 0.6)}" fill="{c}"/>')
    tick_svg = []
    for tv in K.ticks(lo, hi, 6):
        ty = ly + lh * (1 - (tv - lo) / (hi - lo))
        tick_svg.append(f'<line x1="{_f(lx + lw)}" y1="{_f(ty)}" x2="{_f(lx + lw + 5)}" y2="{_f(ty)}" stroke="#222"/>'
                        f'<text x="{_f(lx + lw + 8)}" y="{_f(ty + 4)}" class="tk">{_fmt(tv)}</text>')
    above = (f'<rect x="{_f(lx)}" y="{_f(ly - lw * 1.4)}" width="{_f(lw)}" height="{_f(lw * 1.1)}" fill="#ff00ff"/>'
             f'<text x="{_f(lx + lw + 8)}" y="{_f(ly - lw * 0.55)}" class="tk">&gt; {_fmt(hi)}</text>')
    legend = (f'<g id="legend"><text x="{_f(lx)}" y="{_f(ly - lw * 2.2)}" class="lt">{html.escape(legend_title)}'
              f'{" (" + html.escape(unit) + ")" if unit else ""}</text>{above}{"".join(grad)}'
              f'<rect x="{_f(lx)}" y="{_f(ly)}" width="{_f(lw)}" height="{_f(lh)}" fill="none" stroke="#222"/>'
              f'{"".join(tick_svg)}</g>')

    marker = ""
    if scene.peak_face >= 0:
        mx, my, _ = cam.project(scene.peak_point[None, :])[0]
        lab = f"{'surface max' if scene.peak_inside else 'max'} {_fmt(scene.peak_value)}{(' ' + unit) if unit else ''}"
        x0, y0, x1, y1 = K.label_box(mx, my, 8.6 * len(lab), W, H)
        ex, ey = (x0 if x0 > mx else x1), (y1 if y0 < my else y0)
        marker = (f'<g id="peak"><line x1="{_f(mx)}" y1="{_f(my)}" x2="{_f(ex)}" y2="{_f(ey)}" stroke="#000"/>'
                  f'<circle cx="{_f(mx)}" cy="{_f(my)}" r="6" fill="#ff00ff" stroke="#000"/>'
                  f'<rect x="{_f(x0)}" y="{_f(y0)}" width="{_f(x1 - x0)}" height="{_f(y1 - y0)}" rx="4" '
                  f'fill="#fff" fill-opacity="0.9" stroke="#333"/>'
                  f'<text x="{_f(x0 + 7)}" y="{_f(y0 + 18)}" class="pk">{html.escape(lab)}</text></g>')

    title = "".join(f'<text x="14" y="{24 + 22 * k}" class="{"t1" if k == 0 else "t2"}">{html.escape(t)}</text>'
                    for k, t in enumerate(title_lines))
    info = {str(p): {"name": names[p], **{k: v for k, v in (part_info.get(p) or {}).items() if k != "name"}}
            for p in names}
    css = (".c{fill-opacity:%.3f}path[data-p]{cursor:pointer}"
           ".t1{font:600 18px sans-serif;fill:#111}.t2{font:14px sans-serif;fill:#333}"
           ".tk{font:12px sans-serif;fill:#222}.lt{font:600 13px sans-serif;fill:#111}"
           ".pk{font:600 14px sans-serif;fill:#000}"
           "#tip{pointer-events:none}#tip rect{fill:#fff;fill-opacity:.95;stroke:#333}"
           "#tip text{font:13px sans-serif;fill:#000}") % scene.context_opacity
    script = ("(function(){function F(v){var a=Math.abs(v);return(a>=1e5||(a>0&&a<1e-3))?v.toExponential(3):"
              "String(+v.toPrecision(4));}var P=%s,U=%s,svg=document.currentScript?document.currentScript.ownerSVGElement:"
              "document.documentElement,hl=document.getElementById('hl'),tip=document.getElementById('tip'),"
              "tt=tip.querySelector('text');function show(e){var t=e.target,p=t.getAttribute&&t.getAttribute('data-p');"
              "if(!p){hide();return;}var i=P[p]||{};hl.textContent='path[data-p=\"'+p+'\"]{stroke:#111;"
              "stroke-width:.6px;stroke-opacity:.5;fill-opacity:1}';var L=[(i.name||('Part '+p))+'  (PID '+p+')'];"
              "if(i.value!=null)L.push('이 순간 최대 '+F(i.value)+(U?' '+U:''));if(i.peak!=null)L.push('런 전체 최대 '"
              "+F(i.peak)+(U?' '+U:''));if(i.sf!=null)L.push('안전율 '+i.sf);while(tt.firstChild)tt.removeChild("
              "tt.firstChild);L.forEach(function(s,k){var ts=document.createElementNS('http://www.w3.org/2000/svg',"
              "'tspan');ts.setAttribute('x',8);ts.setAttribute('dy',k?17:15);ts.textContent=s;tt.appendChild(ts);});"
              "var pt=svg.createSVGPoint();pt.x=e.clientX;pt.y=e.clientY;var q=pt.matrixTransform(svg.getScreenCTM()"
              ".inverse()),w=Math.max.apply(null,L.map(function(s){return s.length;}))*7.6+16,h=L.length*17+10;"
              "var x=Math.min(q.x+14,%d-w-4),y=Math.min(q.y+14,%d-h-4);tip.setAttribute('transform','translate('+x+"
              "','+y+')');var r=tip.querySelector('rect');r.setAttribute('width',w);r.setAttribute('height',h);"
              "tip.setAttribute('visibility','visible');}function hide(){hl.textContent='';tip.setAttribute("
              "'visibility','hidden');}svg.addEventListener('mousemove',show);svg.addEventListener('mouseleave',hide);"
              "})();") % (json.dumps(info, ensure_ascii=False), json.dumps(unit, ensure_ascii=False), W, H)
    doc = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
           f'font-family="sans-serif"><style>{css}</style><style id="hl"></style>'
           f'<rect width="{W}" height="{H}" fill="#fff"/><g id="mesh">{"".join(out_lines)}</g>'
           f'{marker}{legend}{title}'
           f'<g id="tip" visibility="hidden"><rect rx="4" width="10" height="10"/><text x="8" y="2"></text></g>'
           f'<script><![CDATA[{script}]]></script></svg>\n')
    out = Path(out)
    out.write_text(doc, encoding="utf-8")
    return out
