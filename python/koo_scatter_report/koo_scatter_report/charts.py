# 외부 라이브러리 없이 SVG 문자열로 그림을 그리는 모듈 — 오프라인 보장
"""SVG 차트.

**왜 직접 그리나.**
기존 보고서는 Plotly 를 CDN 에서 받는다. 망이 막힌 환경에서는 그림이 통째로
사라지고, 그 실패는 화면에 아무 말도 남기지 않는다. 여기서는 의존 없이 SVG
문자열을 만든다 — 열리면 반드시 보인다.

**설계 규칙.**
- 예외를 던지지 않는다. 그릴 수 없으면 사유를 적은 SVG 를 돌려준다.
  (빈 문자열을 돌려주면 "그림이 왜 없지" 를 아무도 답하지 못한다.)
- 값이 없는 칸은 회색으로 비운다. 0 으로 칠하지 않는다.
- 색은 값의 순위가 아니라 **값 자체**에 대응시킨다. 범례에 실제 수치를 적는다.
"""

from __future__ import annotations

import html
import math

# 뜨거운 쪽이 진하게 — deep report 의 핫스팟 색과 같은 계열
_SCALE = [(0.0, (255, 243, 196)), (0.5, (252, 141, 60)), (1.0, (177, 0, 38))]
_EMPTY = "#33384a"      # 값 없음 (0 과 구분되는 회색)
_FG = "#e0e0e0"
_FG2 = "#9aa0b5"
_GRID = "#2a2f45"


def _esc(s) -> str:
    return html.escape(str(s), quote=True)


def color_at(t: float) -> str:
    """0..1 → 색. 범위를 벗어나면 끝값으로 잘라 쓴다."""
    try:
        t = float(t)
    except (TypeError, ValueError):
        return _EMPTY
    if math.isnan(t):
        return _EMPTY
    t = max(0.0, min(1.0, t))
    i = 0
    while i < len(_SCALE) - 2 and t > _SCALE[i + 1][0]:
        i += 1
    t0, c0 = _SCALE[i]
    t1, c1 = _SCALE[i + 1]
    f = (t - t0) / ((t1 - t0) or 1.0)
    rgb = [int(round(c0[k] + (c1[k] - c0[k]) * f)) for k in range(3)]
    return "#%02x%02x%02x" % tuple(rgb)


def _norm(v, lo, hi):
    if hi <= lo:
        return 0.5
    return (v - lo) / (hi - lo)


def _fmt(v, nd=4):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "—"
    if v == 0:
        return "0"
    if abs(v) >= 0.01 and abs(v) < 1e6:
        return f"{v:.{nd}g}"
    return f"{v:.3e}"


def note_svg(width: int, height: int, message: str) -> str:
    """그릴 수 없을 때 **사유를 적은** SVG. 빈 화면을 남기지 않는다."""
    return (f'<svg viewBox="0 0 {width} {height}" width="100%" '
            f'style="max-width:{width}px;background:#151a2b;border-radius:6px">'
            f'<text x="{width // 2}" y="{height // 2}" fill="{_FG2}" font-size="13" '
            f'text-anchor="middle">{_esc(message)}</text></svg>')


def _axes(w, h, pad, x0, x1, y0, y1, xlabel, ylabel, xticks=5, yticks=5):
    """축·격자·눈금을 그린다. (svg 조각, 좌표변환 함수 2개) 를 돌려준다."""
    L, R, T, B = pad
    px = lambda v: L + (w - L - R) * _norm(v, x0, x1)
    py = lambda v: h - B - (h - T - B) * _norm(v, y0, y1)
    out = []
    for i in range(xticks + 1):
        v = x0 + (x1 - x0) * i / xticks
        X = px(v)
        out.append(f'<line x1="{X:.1f}" y1="{T}" x2="{X:.1f}" y2="{h - B}" stroke="{_GRID}"/>')
        out.append(f'<text x="{X:.1f}" y="{h - B + 16}" fill="{_FG2}" font-size="10" '
                   f'text-anchor="middle">{_fmt(v, 3)}</text>')
    for i in range(yticks + 1):
        v = y0 + (y1 - y0) * i / yticks
        Y = py(v)
        out.append(f'<line x1="{L}" y1="{Y:.1f}" x2="{w - R}" y2="{Y:.1f}" stroke="{_GRID}"/>')
        out.append(f'<text x="{L - 6}" y="{Y + 4:.1f}" fill="{_FG2}" font-size="10" '
                   f'text-anchor="end">{_fmt(v, 3)}</text>')
    out.append(f'<text x="{(L + w - R) / 2:.0f}" y="{h - 4}" fill="{_FG}" font-size="11" '
               f'text-anchor="middle">{_esc(xlabel)}</text>')
    out.append(f'<text x="12" y="{(T + h - B) / 2:.0f}" fill="{_FG}" font-size="11" '
               f'text-anchor="middle" transform="rotate(-90 12 {(T + h - B) / 2:.0f})">'
               f'{_esc(ylabel)}</text>')
    return "".join(out), px, py


def _open(w, h):
    return (f'<svg viewBox="0 0 {w} {h}" width="100%" style="max-width:{w}px;'
            f'background:#151a2b;border-radius:6px" xmlns="http://www.w3.org/2000/svg">')


# ── ① 산포도: 편차각 vs 값 ───────────────────────────────────────────
def scatter(points, xlabel="편차각 [deg]", ylabel="값", w=720, h=380,
            color_by_face: bool = True) -> str:
    """points = [(x, y, face 또는 None), ...]"""
    pts = []
    for p in points or []:
        try:
            x, y = float(p[0]), float(p[1])
        except (TypeError, ValueError, IndexError):
            continue
        if math.isnan(x) or math.isnan(y):
            continue
        pts.append((x, y, (p[2] if len(p) > 2 else None)))
    if not pts:
        return note_svg(w, h, "그릴 점이 없습니다 (편차각 또는 값이 비어 있습니다)")

    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    if x1 <= x0:
        x0, x1 = x0 - 0.5, x1 + 0.5
    if y1 <= y0:
        y0, y1 = y0 - 0.5, y1 + 0.5
    pad = (58, 18, 16, 34)
    grid, px, py = _axes(w, h, pad, x0, x1, y0, y1, xlabel, ylabel)

    faces = sorted({p[2] for p in pts if p[2]})
    fcol = {f: color_at(i / max(1, len(faces) - 1)) for i, f in enumerate(faces)} if faces else {}
    body = []
    for x, y, f in pts:
        c = fcol.get(f, "#4ecca3") if color_by_face else "#4ecca3"
        body.append(f'<circle cx="{px(x):.1f}" cy="{py(y):.1f}" r="3.2" fill="{c}" '
                    f'fill-opacity="0.78"><title>{_esc(f or "")} '
                    f'({_fmt(x)}, {_fmt(y)})</title></circle>')
    leg = []
    for i, f in enumerate(faces):
        X = w - 18 - 74 * (len(faces) - i)
        leg.append(f'<rect x="{X}" y="8" width="9" height="9" fill="{fcol[f]}"/>'
                   f'<text x="{X + 13}" y="16" fill="{_FG2}" font-size="10">{_esc(f)}</text>')
    return _open(w, h) + grid + "".join(body) + "".join(leg) + "</svg>"


# ── ② 방향도: roll-pitch 격자에 값 색 ────────────────────────────────
def direction_map(points, w=560, h=380, vlabel="값") -> str:
    """points = [(roll, pitch, value), ...] — 각도 평면에 값을 색으로."""
    pts = []
    for p in points or []:
        try:
            r, q, v = float(p[0]), float(p[1]), float(p[2])
        except (TypeError, ValueError, IndexError):
            continue
        if any(math.isnan(t) for t in (r, q, v)):
            continue
        pts.append((r, q, v))
    if not pts:
        return note_svg(w, h, "각도·값 쌍이 없습니다")
    vs = [p[2] for p in pts]
    lo, hi = min(vs), max(vs)
    pad = (58, 66, 16, 34)
    # 축 범위는 **데이터에서** 정한다. 캠페인마다 규약이 다르다 — Test_001 은
    # roll ±180 / pitch ±90 이지만 Test_006(1144런)은 roll ±90 / pitch ±180 이다
    # (sphere 로더가 "표준" 이라 부르는 쪽이 후자다). ±90 으로 못박아 두었을 때
    # Test_006 은 1144런 중 572런이 축 밖으로 나갔고 465개는 viewBox 밖이라
    # 브라우저가 잘라냈다 — 그런데 색막대 최대값은 그 안 보이는 점까지 셌다.
    rx = 180.0 if max(abs(p[0]) for p in pts) > 90.0 else 90.0
    ry = 180.0 if max(abs(p[1]) for p in pts) > 90.0 else 90.0
    grid, px, py = _axes(w, h, pad, -rx, rx, -ry, ry, "roll [deg]", "pitch [deg]",
                         6 if rx > 90.0 else 4, 6 if ry > 90.0 else 4)
    body = []
    for r, q, v in pts:
        body.append(f'<circle cx="{px(r):.1f}" cy="{py(q):.1f}" r="6" '
                    f'fill="{color_at(_norm(v, lo, hi))}" stroke="#0b0e18" stroke-width="0.6">'
                    f'<title>roll {_fmt(r,4)}, pitch {_fmt(q,4)} → {_fmt(v)}</title></circle>')
    return _open(w, h) + grid + "".join(body) + _colorbar(w, h, lo, hi, vlabel) + "</svg>"


def _colorbar(w, h, lo, hi, label, x=None, top=20, height=None) -> str:
    X = (w - 52) if x is None else x
    H = (h - 80) if height is None else height
    out = [f'<defs><linearGradient id="cb{X}" x1="0" y1="1" x2="0" y2="0">']
    for t, _ in _SCALE:
        out.append(f'<stop offset="{t * 100:.0f}%" stop-color="{color_at(t)}"/>')
    out.append("</linearGradient></defs>")
    out.append(f'<rect x="{X}" y="{top}" width="13" height="{H}" fill="url(#cb{X})" '
               f'stroke="{_GRID}"/>')
    out.append(f'<text x="{X + 17}" y="{top + 9}" fill="{_FG2}" font-size="10">{_fmt(hi)}</text>')
    out.append(f'<text x="{X + 17}" y="{top + H}" fill="{_FG2}" font-size="10">{_fmt(lo)}</text>')
    out.append(f'<text x="{X + 7}" y="{top - 6}" fill="{_FG}" font-size="10" '
               f'text-anchor="middle">{_esc(label)}</text>')
    return "".join(out)


# ── ③ 히트맵: 행 × 열 ────────────────────────────────────────────────
def heatmap(rows, cols, values, w=720, h=None, vlabel="값",
            xlabel="", ylabel="") -> str:
    """values[i][j] — None 이면 값 없음(회색). rows/cols 는 라벨."""
    if not rows or not cols:
        return note_svg(w, h or 300, "행 또는 열이 비어 있습니다")
    nr, nc = len(rows), len(cols)
    cell = max(18, min(46, int(560 / max(1, nc))))
    L, R, T, B = 96, 66, 26, 44
    h = h or (T + B + cell * nr)
    flat = [v for r in (values or []) for v in (r or []) if isinstance(v, (int, float))
            and not math.isnan(v)]
    if not flat:
        return note_svg(w, h, "그릴 값이 없습니다 (모든 칸이 비었습니다)")
    lo, hi = min(flat), max(flat)
    out = [_open(w, h)]
    for i, rname in enumerate(rows):
        Y = T + i * cell
        out.append(f'<text x="{L - 8}" y="{Y + cell / 2 + 4:.0f}" fill="{_FG2}" '
                   f'font-size="10" text-anchor="end">{_esc(rname)}</text>')
        for j in range(nc):
            v = None
            try:
                v = values[i][j]
            except (IndexError, TypeError):
                v = None
            X = L + j * cell
            ok = isinstance(v, (int, float)) and not math.isnan(v)
            c = color_at(_norm(v, lo, hi)) if ok else _EMPTY
            out.append(f'<rect x="{X}" y="{Y}" width="{cell - 1}" height="{cell - 1}" '
                       f'fill="{c}"><title>{_esc(rname)} / {_esc(cols[j])}: '
                       f'{_fmt(v) if ok else "값 없음"}</title></rect>')
    for j, cname in enumerate(cols):
        X = L + j * cell + cell / 2
        out.append(f'<text x="{X:.0f}" y="{T - 8}" fill="{_FG2}" font-size="9" '
                   f'text-anchor="middle" transform="rotate(-35 {X:.0f} {T - 8})">'
                   f'{_esc(cname)}</text>')
    if xlabel:
        out.append(f'<text x="{(L + w - R) / 2:.0f}" y="{h - 6}" fill="{_FG}" '
                   f'font-size="11" text-anchor="middle">{_esc(xlabel)}</text>')
    out.append(_colorbar(w, h, lo, hi, vlabel, top=T, height=max(30, h - T - B)))
    out.append("</svg>")
    return "".join(out)


# ── ④ 회수율 곡선 ────────────────────────────────────────────────────
def recall_curve(ks, recalls, baselines=None, w=560, h=340) -> str:
    pts = []
    for i, k in enumerate(ks or []):
        try:
            r = recalls[i]
        except (IndexError, TypeError):
            continue
        if r is None:
            continue
        try:
            pts.append((float(k), float(r)))
        except (TypeError, ValueError):
            continue
    if not pts:
        return note_svg(w, h, "회수율을 계산하지 못했습니다 (불량 데이터가 필요합니다)")
    kmax = max(p[0] for p in pts)
    pad = (58, 18, 16, 34)
    grid, px, py = _axes(w, h, pad, 0, kmax, 0, 1, "검사 상위 k", "회수율", 5, 5)
    path = " ".join(f"{'M' if i == 0 else 'L'}{px(x):.1f},{py(y):.1f}"
                    for i, (x, y) in enumerate(pts))
    out = [_open(w, h), grid,
           f'<path d="{path}" fill="none" stroke="#4ecca3" stroke-width="2"/>']
    if baselines:
        bl = []
        for i, k in enumerate(ks or []):
            try:
                b = baselines[i]
                if b is None:
                    continue
                bl.append((float(k), float(b)))
            except (IndexError, TypeError, ValueError):
                continue
        if bl:
            bp = " ".join(f"{'M' if i == 0 else 'L'}{px(x):.1f},{py(y):.1f}"
                          for i, (x, y) in enumerate(bl))
            out.append(f'<path d="{bp}" fill="none" stroke="{_FG2}" stroke-width="1.4" '
                       f'stroke-dasharray="5 4"/>')
            out.append(f'<text x="{px(kmax) - 6:.0f}" y="{py(bl[-1][1]) - 6:.0f}" '
                       f'fill="{_FG2}" font-size="10" text-anchor="end">무작위 기준선</text>')
    for x, y in pts:
        out.append(f'<circle cx="{px(x):.1f}" cy="{py(y):.1f}" r="3" fill="#4ecca3">'
                   f'<title>k={int(x)} → {y * 100:.1f}%</title></circle>')
    out.append("</svg>")
    return "".join(out)


# ── ⑤ 구간 프로파일 (막대) ───────────────────────────────────────────
def bar_profile(labels, values, counts=None, w=680, h=320,
                xlabel="구간", ylabel="평균") -> str:
    vals = []
    for i, v in enumerate(values or []):
        vals.append(v if isinstance(v, (int, float)) and not math.isnan(v) else None)
    if not labels or not any(v is not None for v in vals):
        return note_svg(w, h, "구간에 값이 없습니다")
    fin = [v for v in vals if v is not None]
    lo, hi = min(fin + [0.0]), max(fin)
    if hi <= lo:
        hi = lo + 1.0
    L, R, T, B = 58, 18, 18, 44
    n = len(labels)
    bw = max(6, (w - L - R) / max(1, n) - 6)
    out = [_open(w, h)]
    for i in range(6):
        v = lo + (hi - lo) * i / 5
        Y = h - B - (h - T - B) * _norm(v, lo, hi)
        out.append(f'<line x1="{L}" y1="{Y:.1f}" x2="{w - R}" y2="{Y:.1f}" stroke="{_GRID}"/>')
        out.append(f'<text x="{L - 6}" y="{Y + 4:.1f}" fill="{_FG2}" font-size="10" '
                   f'text-anchor="end">{_fmt(v, 3)}</text>')
    for i, lab in enumerate(labels):
        X = L + (w - L - R) * i / max(1, n) + 3
        v = vals[i] if i < len(vals) else None
        cnt = None
        try:
            cnt = counts[i]
        except (IndexError, TypeError):
            cnt = None
        if v is None:
            out.append(f'<rect x="{X:.1f}" y="{T}" width="{bw:.1f}" height="{h - T - B}" '
                       f'fill="{_EMPTY}" fill-opacity="0.35"><title>{_esc(lab)}: 값 없음'
                       f'{f" (표본 {cnt})" if cnt is not None else ""}</title></rect>')
        else:
            Y = h - B - (h - T - B) * _norm(v, lo, hi)
            out.append(f'<rect x="{X:.1f}" y="{Y:.1f}" width="{bw:.1f}" '
                       f'height="{h - B - Y:.1f}" fill="{color_at(_norm(v, lo, hi))}">'
                       f'<title>{_esc(lab)}: {_fmt(v)}'
                       f'{f" (표본 {cnt})" if cnt is not None else ""}</title></rect>')
        out.append(f'<text x="{X + bw / 2:.1f}" y="{h - B + 14}" fill="{_FG2}" '
                   f'font-size="9" text-anchor="middle">{_esc(lab)}</text>')
    out.append(f'<text x="{(L + w - R) / 2:.0f}" y="{h - 4}" fill="{_FG}" font-size="11" '
               f'text-anchor="middle">{_esc(xlabel)}</text>')
    out.append(f'<text x="12" y="{h / 2:.0f}" fill="{_FG}" font-size="11" '
               f'text-anchor="middle" transform="rotate(-90 12 {h / 2:.0f})">'
               f'{_esc(ylabel)}</text>')
    out.append("</svg>")
    return "".join(out)


# ── ⑥ 리스크맵: 평면 투영 + 반경 ─────────────────────────────────────
def risk_map(circles, bbox_min=None, bbox_max=None, axes=(0, 1),
             w=560, h=460, vlabel="위험도", marks=None) -> str:
    """circles = [(x, y, r, value, label)] — 클러스터를 평면에 투영.

    marks = [(x, y, label)] — 실물 불량 위치를 겹쳐 그린다 (없으면 생략).
    """
    cs = []
    for c in circles or []:
        try:
            x, y, r, v = float(c[0]), float(c[1]), float(c[2]), float(c[3])
        except (TypeError, ValueError, IndexError):
            continue
        if any(math.isnan(t) for t in (x, y, r, v)):
            continue
        cs.append((x, y, max(r, 0.0), v, (c[4] if len(c) > 4 else "")))
    if not cs:
        return note_svg(w, h, "투영할 군집이 없습니다")
    ax, ay = axes
    xs = [c[0] for c in cs]
    ys = [c[1] for c in cs]
    rs = [c[2] for c in cs]
    x0, x1 = min(xs) - max(rs), max(xs) + max(rs)
    y0, y1 = min(ys) - max(rs), max(ys) + max(rs)
    if isinstance(bbox_min, (list, tuple)) and isinstance(bbox_max, (list, tuple)) \
            and len(bbox_min) > max(ax, ay) and len(bbox_max) > max(ax, ay):
        try:
            x0 = min(x0, float(bbox_min[ax])); x1 = max(x1, float(bbox_max[ax]))
            y0 = min(y0, float(bbox_min[ay])); y1 = max(y1, float(bbox_max[ay]))
        except (TypeError, ValueError):
            pass
    if x1 <= x0:
        x0, x1 = x0 - 1, x1 + 1
    if y1 <= y0:
        y0, y1 = y0 - 1, y1 + 1
    # 등축 — 반경이 축마다 다르게 보이면 거짓말이 된다
    L, R, T, B = 58, 66, 18, 40
    pw, ph = w - L - R, h - T - B
    sx = pw / (x1 - x0)
    sy = ph / (y1 - y0)
    s = min(sx, sy)
    cx0 = L + (pw - s * (x1 - x0)) / 2
    cy0 = T + (ph - s * (y1 - y0)) / 2
    px = lambda v: cx0 + s * (v - x0)
    py = lambda v: cy0 + s * (y1 - v)
    vs = [c[3] for c in cs]
    lo, hi = min(vs), max(vs)
    out = [_open(w, h)]
    if isinstance(bbox_min, (list, tuple)) and isinstance(bbox_max, (list, tuple)):
        try:
            out.append(f'<rect x="{px(float(bbox_min[ax])):.1f}" '
                       f'y="{py(float(bbox_max[ay])):.1f}" '
                       f'width="{s * (float(bbox_max[ax]) - float(bbox_min[ax])):.1f}" '
                       f'height="{s * (float(bbox_max[ay]) - float(bbox_min[ay])):.1f}" '
                       f'fill="none" stroke="{_FG2}" stroke-dasharray="4 3"/>')
        except (TypeError, ValueError, IndexError):
            pass
    for x, y, r, v, lab in sorted(cs, key=lambda c: -c[2]):
        out.append(f'<circle cx="{px(x):.1f}" cy="{py(y):.1f}" r="{max(1.5, s * r):.1f}" '
                   f'fill="{color_at(_norm(v, lo, hi))}" fill-opacity="0.55" '
                   f'stroke="{color_at(_norm(v, lo, hi))}"><title>{_esc(lab)} '
                   f'{_fmt(v)} (반경 {_fmt(r, 3)})</title></circle>')
    for m in marks or []:
        try:
            mx, my = float(m[0]), float(m[1])
        except (TypeError, ValueError, IndexError):
            continue
        X, Y = px(mx), py(my)
        out.append(f'<path d="M{X - 6:.1f},{Y - 6:.1f}L{X + 6:.1f},{Y + 6:.1f}'
                   f'M{X + 6:.1f},{Y - 6:.1f}L{X - 6:.1f},{Y + 6:.1f}" '
                   f'stroke="#00e5ff" stroke-width="2.2">'
                   f'<title>실물 불량: {_esc(m[2] if len(m) > 2 else "")}</title></path>')
    axn = "xyz"
    out.append(f'<text x="{(L + w - R) / 2:.0f}" y="{h - 6}" fill="{_FG}" font-size="11" '
               f'text-anchor="middle">{axn[ax]} — {axn[ay]} 평면</text>')
    out.append(_colorbar(w, h, lo, hi, vlabel))
    out.append("</svg>")
    return "".join(out)


# ── ⑦ 구간도: 구간별 색 + 군집 중심 ──────────────────────────────────
def segment_map(segments, values, centers=None, w=560, h=420, vlabel="값") -> str:
    """segments = [(name, x0, y0, x1, y1)] — 박스 구간을 평면에 색칠."""
    segs = []
    for s_ in segments or []:
        try:
            segs.append((str(s_[0]), float(s_[1]), float(s_[2]), float(s_[3]), float(s_[4])))
        except (TypeError, ValueError, IndexError):
            continue
    if not segs:
        return note_svg(w, h, "구간 정의가 없습니다 (--segments 로 주세요)")
    fin = [v for v in (values or {}).values()
           if isinstance(v, (int, float)) and not math.isnan(v)]
    lo, hi = (min(fin), max(fin)) if fin else (0.0, 1.0)
    x0 = min(s_[1] for s_ in segs); x1 = max(s_[3] for s_ in segs)
    y0 = min(s_[2] for s_ in segs); y1 = max(s_[4] for s_ in segs)
    if x1 <= x0: x1 = x0 + 1
    if y1 <= y0: y1 = y0 + 1
    L, R, T, B = 40, 66, 18, 34
    pw, ph = w - L - R, h - T - B
    s = min(pw / (x1 - x0), ph / (y1 - y0))
    px = lambda v: L + s * (v - x0)
    py = lambda v: T + s * (y1 - v)
    out = [_open(w, h)]
    for name, a, b, c, d in segs:
        v = (values or {}).get(name)
        ok = isinstance(v, (int, float)) and not math.isnan(v)
        out.append(f'<rect x="{px(a):.1f}" y="{py(d):.1f}" width="{s * (c - a):.1f}" '
                   f'height="{s * (d - b):.1f}" fill="{color_at(_norm(v, lo, hi)) if ok else _EMPTY}" '
                   f'fill-opacity="0.8" stroke="{_GRID}">'
                   f'<title>{_esc(name)}: {_fmt(v) if ok else "값 없음"}</title></rect>')
        out.append(f'<text x="{px((a + c) / 2):.1f}" y="{py((b + d) / 2) + 3:.1f}" '
                   f'fill="#0b0e18" font-size="9" text-anchor="middle">{_esc(name)}</text>')
    for ct in centers or []:
        try:
            X, Y = px(float(ct[0])), py(float(ct[1]))
        except (TypeError, ValueError, IndexError):
            continue
        out.append(f'<circle cx="{X:.1f}" cy="{Y:.1f}" r="3.4" fill="none" '
                   f'stroke="#00e5ff" stroke-width="1.8"/>')
    out.append(_colorbar(w, h, lo, hi, vlabel))
    out.append("</svg>")
    return "".join(out)


# ── ⑧ 둘레 전개도 ────────────────────────────────────────────────────
def perimeter_unroll(circles, bbox_min, bbox_max, axis: int = 2,
                     w=760, h=300, vlabel="위험도") -> str:
    """측면을 둘레 각도로 펼친다. 중심축은 `axis`(기본 z).

    둘레 위치 θ = atan2(v−cy, u−cx) 를 x 축, 축방향 좌표를 y 축으로 놓는다.
    """
    try:
        bmin = [float(v) for v in bbox_min]
        bmax = [float(v) for v in bbox_max]
    except (TypeError, ValueError):
        return note_svg(w, h, "파트 경계상자가 없어 전개할 수 없습니다")
    if len(bmin) < 3 or len(bmax) < 3:
        return note_svg(w, h, "경계상자 좌표가 3개가 아닙니다")
    u_ax, v_ax = [i for i in range(3) if i != axis]
    cu = (bmin[u_ax] + bmax[u_ax]) / 2
    cv = (bmin[v_ax] + bmax[v_ax]) / 2
    pts = []
    for c in circles or []:
        try:
            x, y, z, r, val = (float(c[0]), float(c[1]), float(c[2]),
                               float(c[3]), float(c[4]))
        except (TypeError, ValueError, IndexError):
            continue
        p = (x, y, z)
        th = math.degrees(math.atan2(p[v_ax] - cv, p[u_ax] - cu))
        pts.append((th, p[axis], max(r, 0.0), val, (c[5] if len(c) > 5 else "")))
    if not pts:
        return note_svg(w, h, "전개할 군집이 없습니다")
    z0, z1 = bmin[axis], bmax[axis]
    if z1 <= z0:
        z0, z1 = z0 - 1, z1 + 1
    pad = (58, 66, 18, 40)
    grid, px, py = _axes(w, h, pad, -180, 180, z0, z1,
                         "둘레 각도 [deg]", f"{'xyz'[axis]} 위치", 6, 4)
    vs = [p[3] for p in pts]
    lo, hi = min(vs), max(vs)
    body = []
    for th, zz, r, val, lab in sorted(pts, key=lambda p: -p[2]):
        body.append(f'<circle cx="{px(th):.1f}" cy="{py(zz):.1f}" r="5" '
                    f'fill="{color_at(_norm(val, lo, hi))}" fill-opacity="0.72">'
                    f'<title>{_esc(lab)} θ={th:.1f}°, {"xyz"[axis]}={_fmt(zz,3)} → '
                    f'{_fmt(val)}</title></circle>')
    return _open(w, h) + grid + "".join(body) + _colorbar(w, h, lo, hi, vlabel) + "</svg>"
