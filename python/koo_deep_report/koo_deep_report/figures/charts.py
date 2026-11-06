# 리포트용 SVG 차트 — 시간 이력(선) · 파트 비교(막대). 외부 라이브러리 없이, 값마다 <title> 툴팁
"""리포트에 바로 붙이는 단순하고 깨끗한 차트. 다운샘플은 **구간 극값 보존**(피크가 빠지지 않게 — 2026-09 무결성 규약),
최대점은 표시한다. 값이 없으면 그 계열을 빼고 범례에도 싣지 않는다(0 으로 그리지 않는다).
"""
from __future__ import annotations

import html
import math
from pathlib import Path

import numpy as np

PALETTE = ["#1f77b4", "#d62728", "#2ca02c", "#ff7f0e", "#9467bd", "#8c564b", "#e377c2", "#17becf"]
SEVERITY_COLOR = {"CRITICAL": "#d62728", "WARNING": "#ff9f1c", "OK": "#2a9d8f", "UNKNOWN": "#8d99ae"}


def _nice_ticks(lo: float, hi: float, n: int = 5) -> list[float]:
    if not (math.isfinite(lo) and math.isfinite(hi)) or hi <= lo:
        return [lo]
    raw = (hi - lo) / max(n, 1)
    mag = 10 ** math.floor(math.log10(raw))
    step = next(s * mag for s in (1, 2, 2.5, 5, 10) if s * mag >= raw)
    t0 = math.ceil(lo / step) * step
    out, t = [], t0
    while t <= hi + step * 1e-9:
        out.append(round(t, 12))
        t += step
    return out


def _fmt(v: float) -> str:
    if v == 0:
        return "0"
    a = abs(v)
    return f"{v:.3g}" if (a >= 1e4 or a < 1e-2) else f"{v:.4g}"


def _extreme_indices(n: int, ys: np.ndarray, points: int) -> np.ndarray:
    """구간마다 최대 · 최소 순번을 남겨 피크를 보존하는 다운샘플."""
    if n <= points:
        return np.arange(n)
    edges = np.linspace(0, n, points // 2 + 1).astype(int)
    keep = {0, n - 1}
    for a, b in zip(edges[:-1], edges[1:]):
        if b > a:
            seg = ys[a:b]
            keep.add(a + int(np.nanargmax(seg)))
            keep.add(a + int(np.nanargmin(seg)))
    return np.array(sorted(keep))


def line_chart(out: str | Path, series: list[dict], title: str, xlabel: str, ylabel: str, **kw) -> Path:
    out = Path(out)
    out.write_text(line_svg(series, title, xlabel, ylabel, **kw), encoding="utf-8")
    return out


def stack(out: str | Path, docs: list[str], width: int = 960, height: int = 420) -> Path:
    """같은 크기 차트 여럿을 세로로 잇는다(예: 응력 이력 위 · 가속도 아래)."""
    body = "".join(f'<g transform="translate(0,{height * k})">{d}</g>' for k, d in enumerate(docs))
    out = Path(out)
    out.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height * len(docs)}" '
                   f'width="{width}" height="{height * len(docs)}">{body}</svg>\n', encoding="utf-8")
    return out


def line_svg(series: list[dict], title: str, xlabel: str, ylabel: str,
             width: int = 960, height: int = 420, mark_peaks: bool = True, points: int = 600) -> str:
    """series — [{"name", "x": [...], "y": [...], "color"?}]. 빈 계열은 뺀다."""
    ss = []
    for k, s in enumerate(series):
        x = np.asarray(s.get("x") or [], dtype=np.float64)
        y = np.asarray(s.get("y") or [], dtype=np.float64)
        if len(x) != len(y):                                 # 없는 열(빈 y) · 어긋난 열은 그리지 않는다
            continue
        ok = np.isfinite(x) & np.isfinite(y)
        if ok.sum() >= 2:
            ss.append({**s, "x": x[ok], "y": y[ok], "color": s.get("color") or PALETTE[k % len(PALETTE)]})
    ml, mr, mt, mb = 74, 24, 46, 54
    pw, ph = width - ml - mr, height - mt - mb
    body = []
    if ss:
        xlo = min(float(s["x"].min()) for s in ss); xhi = max(float(s["x"].max()) for s in ss)
        ylo = min(0.0, min(float(s["y"].min()) for s in ss)); yhi = max(float(s["y"].max()) for s in ss)
        if yhi <= ylo:
            yhi = ylo + 1.0
        yhi += (yhi - ylo) * 0.06
        if xhi <= xlo:
            xhi = xlo + 1.0

        def X(v): return ml + (v - xlo) / (xhi - xlo) * pw
        def Y(v): return mt + ph - (v - ylo) / (yhi - ylo) * ph
        for t in _nice_ticks(ylo, yhi, 5):
            body.append(f'<line x1="{ml}" y1="{Y(t):.1f}" x2="{ml + pw}" y2="{Y(t):.1f}" class="g"/>'
                        f'<text x="{ml - 8}" y="{Y(t) + 4:.1f}" class="ty">{_fmt(t)}</text>')
        for t in _nice_ticks(xlo, xhi, 6):
            body.append(f'<line x1="{X(t):.1f}" y1="{mt + ph}" x2="{X(t):.1f}" y2="{mt + ph + 5}" class="a"/>'
                        f'<text x="{X(t):.1f}" y="{mt + ph + 20}" class="tx">{_fmt(t)}</text>')
        for s in ss:
            idx = _extreme_indices(len(s["x"]), s["y"], points)
            pts = " ".join(f"{X(a):.1f},{Y(b):.1f}" for a, b in zip(s["x"][idx], s["y"][idx]))
            body.append(f'<polyline points="{pts}" fill="none" stroke="{s["color"]}" stroke-width="1.8">'
                        f'<title>{html.escape(s["name"])}</title></polyline>')
            if mark_peaks:
                i = int(np.argmax(s["y"]))
                px, py = X(s["x"][i]), Y(s["y"][i])
                body.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4" fill="{s["color"]}" stroke="#000">'
                            f'<title>{html.escape(s["name"])}: 최대 {_fmt(float(s["y"][i]))} @ {_fmt(float(s["x"][i]))}'
                            f'</title></circle>')
        lx = ml + 10
        for k, s in enumerate(ss):
            ly = mt + 14 + 18 * k
            body.append(f'<rect x="{lx}" y="{ly - 9}" width="14" height="4" fill="{s["color"]}"/>'
                        f'<text x="{lx + 20}" y="{ly - 4}" class="lg">{html.escape(s["name"])}</text>')
    else:
        body.append(f'<text x="{width / 2}" y="{height / 2}" class="tx">값이 없다</text>')
    doc = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" '
           f'height="{height}" font-family="sans-serif"><style>.g{{stroke:#e3e3e3}}.a{{stroke:#444}}'
           f'.ty{{font:12px sans-serif;text-anchor:end;fill:#333}}.tx{{font:12px sans-serif;text-anchor:middle;'
           f'fill:#333}}.lg{{font:12px sans-serif;fill:#222}}.t{{font:600 15px sans-serif;fill:#111}}'
           f'.al{{font:13px sans-serif;fill:#222}}</style><rect width="{width}" height="{height}" fill="#fff"/>'
           f'<text x="{ml}" y="26" class="t">{html.escape(title)}</text>'
           f'<rect x="{ml}" y="{mt}" width="{pw}" height="{ph}" fill="none" stroke="#444"/>{"".join(body)}'
           f'<text x="{ml + pw / 2}" y="{height - 12}" class="al" text-anchor="middle">{html.escape(xlabel)}</text>'
           f'<text x="16" y="{mt + ph / 2}" class="al" text-anchor="middle" '
           f'transform="rotate(-90 16 {mt + ph / 2})">{html.escape(ylabel)}</text></svg>\n')
    return doc


def bar_chart(out: str | Path, bars: list[dict], title: str, ylabel: str, ref_line: tuple[float, str] | None = None,
              width: int = 960, height: int = 440) -> Path:
    """bars — [{"label", "value", "severity"?, "note"?}] (값 큰 순으로 넘긴다). 값 없는 막대는 뺀다."""
    bs = [b for b in bars if b.get("value") is not None and math.isfinite(float(b["value"]))]
    ml, mr, mt, mb = 74, 24, 46, 110
    pw, ph = width - ml - mr, height - mt - mb
    body = []
    if bs:
        yhi = max(float(b["value"]) for b in bs)
        if ref_line:
            yhi = max(yhi, ref_line[0])
        yhi = yhi * 1.08 if yhi > 0 else 1.0

        def Y(v): return mt + ph - v / yhi * ph
        for t in _nice_ticks(0.0, yhi, 5):
            body.append(f'<line x1="{ml}" y1="{Y(t):.1f}" x2="{ml + pw}" y2="{Y(t):.1f}" class="g"/>'
                        f'<text x="{ml - 8}" y="{Y(t) + 4:.1f}" class="ty">{_fmt(t)}</text>')
        bw = pw / len(bs)
        for k, b in enumerate(bs):
            v = float(b["value"])
            x = ml + k * bw + bw * 0.15
            col = SEVERITY_COLOR.get(str(b.get("severity") or "UNKNOWN"), SEVERITY_COLOR["UNKNOWN"])
            tip = f'{b["label"]}: {_fmt(v)}' + (f' — {b["note"]}' if b.get("note") else "")
            body.append(f'<rect x="{x:.1f}" y="{Y(v):.1f}" width="{bw * 0.7:.1f}" height="{mt + ph - Y(v):.1f}" '
                        f'fill="{col}"><title>{html.escape(tip)}</title></rect>'
                        f'<text x="{x + bw * 0.35:.1f}" y="{mt + ph + 12}" class="xl" '
                        f'transform="rotate(-40 {x + bw * 0.35:.1f} {mt + ph + 12})">{html.escape(str(b["label"]))}</text>')
        if ref_line:
            body.append(f'<line x1="{ml}" y1="{Y(ref_line[0]):.1f}" x2="{ml + pw}" y2="{Y(ref_line[0]):.1f}" '
                        f'stroke="#d62728" stroke-dasharray="6 4"/><text x="{ml + pw - 4}" y="{Y(ref_line[0]) - 6:.1f}" '
                        f'class="ty">{html.escape(ref_line[1])}</text>')
        lx = ml + pw - 330
        for k, (sev, col) in enumerate(SEVERITY_COLOR.items()):
            body.append(f'<rect x="{lx + 82 * k}" y="{mt + 8}" width="10" height="10" fill="{col}"/>'
                        f'<text x="{lx + 82 * k + 14}" y="{mt + 17}" class="lg">{sev}</text>')
    else:
        body.append(f'<text x="{width / 2}" y="{height / 2}" class="tx">값이 없다</text>')
    doc = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" '
           f'height="{height}" font-family="sans-serif"><style>.g{{stroke:#e3e3e3}}.ty{{font:12px sans-serif;'
           f'text-anchor:end;fill:#333}}.tx{{font:12px sans-serif;text-anchor:middle;fill:#333}}'
           f'.xl{{font:11px sans-serif;text-anchor:end;fill:#222}}.lg{{font:11px sans-serif;fill:#222}}'
           f'.t{{font:600 15px sans-serif;fill:#111}}.al{{font:13px sans-serif;fill:#222}}</style>'
           f'<rect width="{width}" height="{height}" fill="#fff"/><text x="{ml}" y="26" class="t">{html.escape(title)}</text>'
           f'<rect x="{ml}" y="{mt}" width="{pw}" height="{ph}" fill="none" stroke="#444"/>{"".join(body)}'
           f'<text x="16" y="{mt + ph / 2}" class="al" text-anchor="middle" '
           f'transform="rotate(-90 16 {mt + ph / 2})">{html.escape(ylabel)}</text></svg>\n')
    out = Path(out)
    out.write_text(doc, encoding="utf-8")
    return out
