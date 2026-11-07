# 그림 폴더의 독립 갤러리(figures/index.html)와, 기존 리포트 HTML 에 그 갤러리로 가는 링크를 끼우는 도구
"""리포트 HTML 을 다시 만들지 않고 그림에 닿게 한다 — 옛 deep 산출물(그림 탭이 없는 HTML)과 sphere 리포트(캠페인 그림 단계보다 먼저
만들어진다)가 대상이다. HTML 을 다시 지으면 그때 준 옵션(항복값 등)을 몰라 값이 바뀔 수 있어, 표지 주석 사이의 링크만 갈아 끼운다.

- `write_index(folder, manifest)` — manifest.json 으로 index.html(외부 라이브러리 없음, 폐쇄망 안전).
- `link_html(html, href, label)` — `</body>` 앞에 표지로 감싼 고정 버튼. 다시 부르면 그 블록만 바뀐다(하나만 남는다).
"""
from __future__ import annotations

import html as H
import json
import re
from pathlib import Path

BEGIN, END = "<!-- kood3plot.figures:begin -->", "<!-- kood3plot.figures:end -->"
_BLOCK = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.S)

_CSS = """
:root{--bg:#f6f7f9;--card:#fff;--fg:#1d2330;--fg2:#5b6475;--line:#d9dde5;--accent:#2b6cb0}
@media (prefers-color-scheme:dark){:root{--bg:#161a22;--card:#1f2430;--fg:#e6e9ef;--fg2:#a3abba;--line:#323a4a;--accent:#7fb3ff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 system-ui,sans-serif}
main{max-width:1600px;margin:0 auto;padding:20px 16px 40px}h1{font-size:22px;margin:0 0 4px}
.sub{color:var(--fg2);margin:0 0 14px}.notes{color:var(--fg2);font-size:13px;margin:0 0 16px 18px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(420px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px}
.card img{width:100%;display:block;border-radius:4px;background:#fff;cursor:zoom-in}
.cap{font-size:13px;margin:8px 0 4px}.links{font-size:12px;color:var(--fg2)}.links a{color:var(--accent)}
.chart{margin-top:18px}.chart object{width:100%;max-width:960px;display:block;background:#fff;border-radius:6px}
#modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,.9);z-index:9;align-items:center;justify-content:center;
flex-direction:column}#modal.open{display:flex}#modal object{width:95vw;height:86vh;background:#fff;border-radius:6px}
#modal .lab{color:#ccc;font-size:13px;margin-top:8px;max-width:95vw}#modal button{position:absolute;top:10px;right:16px;
background:none;border:0;color:#fff;font-size:28px;cursor:pointer}
@media (max-width:480px){.grid{grid-template-columns:1fr}}
"""

_JS = """
function openFig(svg,cap){var m=document.getElementById('modal');m.querySelector('.body').innerHTML=
'<object type="image/svg+xml" data="'+svg+'"></object>';m.querySelector('.lab').textContent=cap;m.classList.add('open');}
function closeFig(){var m=document.getElementById('modal');m.classList.remove('open');m.querySelector('.body').innerHTML='';}
document.addEventListener('keydown',function(e){if(e.key==='Escape')closeFig();});
"""


def write_index(folder: str | Path, manifest: dict) -> Path:
    """manifest(dict) → folder/index.html. 스냅샷은 PNG 미리보기(누르면 호버 SVG), 차트는 SVG 그대로."""
    folder = Path(folder)
    figs = manifest.get("figures") or []
    run = manifest.get("run") or {}
    camp = manifest.get("campaign") or {}
    where = run.get("run_folder") or (camp.get("test_dir") and Path(str(camp["test_dir"])).name) or ""
    title = "리포트 그림" + (f" — {where}" if where else "") + (" (캠페인 최악 방향)" if manifest.get("scope") == "campaign" else "")
    units = (manifest.get("units") or {}).get("stress") or ""
    prod = (manifest.get("producer") or {}).get("version") or ""
    cards, charts = [], []
    for f in figs:
        files = f.get("files") or {}
        cap = H.escape(str(f.get("caption") or f.get("id") or ""))
        if files.get("png"):
            svg, png = H.escape(files.get("svg") or files["png"]), H.escape(files["png"])
            cards.append(f'<div class="card"><img src="{png}" alt="{H.escape(str(f.get("id") or ""))}" loading="lazy" '
                         f'data-svg="{svg}" data-cap="{cap}" onclick="openFig(this.dataset.svg,this.dataset.cap)">'
                         f'<div class="cap">{cap}</div><div class="links"><a href="{svg}" target="_blank">SVG (호버)</a> · '
                         f'<a href="{png}" download>PNG</a></div></div>')
        elif files.get("svg"):
            svg = H.escape(files["svg"])
            charts.append(f'<div class="chart"><div class="cap">{cap}</div><object type="image/svg+xml" data="{svg}"></object>'
                          f'<div class="links"><a href="{svg}" target="_blank">SVG 새 창</a></div></div>')
    notes = "".join(f"<li>{H.escape(str(n))}</li>" for n in manifest.get("notes") or [])
    doc = (f'<!doctype html><html lang="ko"><head><meta charset="utf-8">'
           f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{H.escape(title)}</title>'
           f'<style>{_CSS}</style></head><body><main><h1>{H.escape(title)}</h1>'
           f'<p class="sub">최대 순간 스냅샷 — 타겟 파트는 응력 색, 주변 파트는 반투명, 바닥(환경 파트)은 숨김. 그림을 누르면 크게 열리고 '
           f'그 위에 마우스를 올리면 파트 이름 · 값이 뜬다.' + (f' 응력 단위 {H.escape(units)}.' if units else '')
           + (f' 판 {H.escape(prod)}.' if prod else '') + '</p>'
           + (f'<ul class="notes">{notes}</ul>' if notes else '')
           + (f'<div class="grid">{"".join(cards)}</div>' if cards else '<p class="sub">스냅샷이 없다 — 위 알림을 본다.</p>')
           + "".join(charts)
           + '</main><div id="modal"><button onclick="closeFig()" aria-label="닫기">&#x2715;</button>'
           '<div class="body"></div><div class="lab"></div></div>'
           f'<script>{_JS}</script></body></html>\n')
    out = folder / "index.html"
    out.write_text(doc, encoding="utf-8")
    return out


def link_html(html_path: str | Path, href: str, label: str = "리포트 그림") -> bool:
    """기존 HTML 의 `</body>` 앞에 표지로 감싼 고정 버튼을 끼운다(있으면 갈아 끼운다). HTML 이 없으면 False."""
    p = Path(html_path)
    if not p.is_file():
        return False
    s = p.read_text(encoding="utf-8", errors="replace")
    block = (f'{BEGIN}<a href="{H.escape(href)}" target="_blank" '
             'style="position:fixed;right:18px;bottom:18px;z-index:99999;background:#2b6cb0;color:#fff;'
             'padding:10px 14px;border-radius:20px;font:600 13px system-ui,sans-serif;text-decoration:none;'
             f'box-shadow:0 2px 8px rgba(0,0,0,.3)">{H.escape(label)}</a>{END}')
    if _BLOCK.search(s):
        s = _BLOCK.sub(lambda _m: block, s, count=1)
    elif "</body>" in s:
        i = s.rfind("</body>")
        s = s[:i] + block + s[i:]
    else:
        s = s + block
    p.write_text(s, encoding="utf-8")
    return True


def manifest_of(folder: str | Path) -> dict:
    return json.loads((Path(folder) / "manifest.json").read_text(encoding="utf-8"))
