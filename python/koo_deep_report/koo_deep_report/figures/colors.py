# 응력 색 지도 · 색 범위 · 음영 — PNG(pyvista) 와 SVG 가 같은 색을 쓰게 한 곳에 둔다
"""색 지도는 jet(LS-PrePost 관례, 사용자 결정 11-06). 범위 기본은 0 – p99.5 — 요소 하나의 순간 최대가 범위를 정해 나머지가
다 파랗게 묻히는 일을 막는다(v14 시안: 최대 4,025 MPa, p99.5 = 233). 넘는 값은 자홍(ABOVE)으로 칠하고 최대점은 따로 표시한다.
"""
from __future__ import annotations

import numpy as np

CMAP = "jet"
ABOVE = (1.0, 0.0, 1.0)            # 범위를 넘는 값
CONTEXT = (0.62, 0.62, 0.62)       # 주변 파트


def color_range(values: np.ndarray, mode: str | float = "p99.5", lo: float = 0.0) -> tuple[float, float]:
    """색 범위 (lo, hi). mode — 'p99.5' 같은 백분위, 'max', 또는 수(고정 위 끝, 예: 항복값)."""
    v = np.asarray(values, dtype=np.float64)
    v = v[np.isfinite(v)]
    if isinstance(mode, (int, float)) and not isinstance(mode, bool):
        hi = float(mode)
    elif v.size == 0:
        hi = 1.0
    elif mode == "max":
        hi = float(v.max())
    elif isinstance(mode, str) and mode.startswith("p"):
        hi = float(np.percentile(v, float(mode[1:])))
    else:
        raise ValueError(f"모르는 색 범위 {mode!r} — 'p99.5', 'max' 또는 수")
    if not hi > lo:
        hi = lo + max(abs(lo), 1.0) * 1e-6 + (float(v.max()) - lo if v.size else 1.0)
    return float(lo), float(hi)


def rgb(values: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """값 → (n, 3) 0..1 RGB. 위 끝을 넘으면 ABOVE, nan 은 회색."""
    from matplotlib import colormaps
    v = np.asarray(values, dtype=np.float64)
    t = np.clip((v - lo) / (hi - lo), 0.0, 1.0)
    out = colormaps[CMAP](np.nan_to_num(t))[:, :3]
    out[v > hi] = ABOVE
    out[~np.isfinite(v)] = CONTEXT
    return out


def shade(base: np.ndarray, normals: np.ndarray, light: np.ndarray, ambient: float = 0.42) -> np.ndarray:
    """램버트 음영 — base(n,3) × (ambient + (1-ambient)·|n·l|). 양면 조명(뒤집힌 법선도 밝게)."""
    nn = normals / np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-15)
    lam = np.abs(nn @ light)
    return np.clip(base * (ambient + (1.0 - ambient) * lam)[:, None], 0.0, 1.0)


def hex_colors(rgb01: np.ndarray) -> list[str]:
    q = np.clip(np.round(np.asarray(rgb01) * 255), 0, 255).astype(int)
    return [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in q]


def ticks(lo: float, hi: float, n: int = 6) -> list[float]:
    """범례 눈금 — 보기 좋은 간격."""
    span = hi - lo
    if span <= 0:
        return [lo]
    raw = span / max(n - 1, 1)
    mag = 10 ** np.floor(np.log10(raw))
    step = min((s * mag for s in (1, 2, 2.5, 5, 10) if s * mag >= raw), default=raw)
    start = np.ceil(lo / step) * step
    out = list(np.arange(start, hi + step * 0.5, step))
    return [float(x) for x in out if lo - 1e-9 * span <= x <= hi + 1e-9 * span]


def legend_box(width: int, height: int) -> tuple[float, float, float, float]:
    """범례 막대 자리 (x, y, 폭, 높이) — PNG · SVG 가 같은 자리에 그린다(장면이 오른쪽 15% 를 비워 둔다)."""
    return width * 0.885, height * 0.16, width * 0.022, height * 0.62


def label_box(x: float, y: float, text_w: float, width: int, height: int) -> tuple[float, float, float, float]:
    """최대점 이름표 상자 (x0, y0, x1, y1) — 기본은 점의 오른쪽 위, 범례 · 제목 띠에 걸리면 왼쪽 · 아래로 뒤집는다."""
    bw, bh = text_w + 14, 26
    x0 = x + 26 if x + 26 + bw <= width * 0.86 else x - 26 - bw
    y0 = y - 40 if y - 40 >= height * 0.1 else y + 14
    return x0, y0, x0 + bw, y0 + bh
