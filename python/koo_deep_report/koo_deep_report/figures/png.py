# 장면을 pyvista(VTK) 오프스크린으로 그려 PNG 로 — 타겟 응력 색 · 주변 반투명 · 윤곽선 · 범례 · 제목 · 최대점
"""Xvfb 화면이 있어야 한다(`xvfb.display()` 안에서 부른다). 카메라는 장면의 평행 투영 카메라를 그대로 쓴다 — SVG 와 같은 그림.

두 겹으로 그려 겹친다 — 주변 파트(반투명, 흰 바탕)와 타겟(불투명, 투명 바탕). 한 번에 그리면 타겟 앞을 가린 반투명 주변
파트가 여러 겹 쌓여 타겟 색이 회색으로 바랜다(v14 PKG 10 — 기기 안쪽 파트일수록 심하다). 타겟은 늘 맨 위에 온다.

범례 · 최대점 · 제목은 VTK 글자가 아니라 PIL 로 얹는다 — VTK 기본 글꼴엔 한글이 없고, CJK 보충 글꼴(Droid Sans Fallback)은
영문이 없어 제목이 통째로 사라졌다(시안). 영문 · 한글을 함께 담은 글꼴(나눔 → Noto CJK)을 찾고, 없으면 한글을 빼고 쓴다.
범례 자리 · 최대점 이름표는 SVG 와 같은 규칙(colors.legend_box · label_box)이다.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from . import colors as K
from .scene import Scene

#: (경로, ttc 안 순번, 한글 가능) — 앞에서부터 있는 것을 쓴다
_FONTS = {
    "regular": [("/usr/share/fonts/truetype/nanum/NanumGothic.ttf", 0, True),
                ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 1, True),
                ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 0, False)],
    "bold": [("/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf", 0, True),
             ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 1, True),
             ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 0, False)],
}


def _font(kind: str, size: int):
    """(PIL 글꼴, 한글 가능). 글꼴 파일이 하나도 없으면 PIL 기본."""
    from PIL import ImageFont
    for path, idx, cjk in _FONTS[kind]:
        if Path(path).exists():
            return ImageFont.truetype(path, size, index=idx), cjk
    return ImageFont.load_default(), False


def ascii_fallback(text: str) -> str:
    """한글 글꼴이 없을 때 — ASCII 아닌 글자를 지운다(빈 괄호 · 겹친 공백도 정리)."""
    import re
    t = "".join(ch if ord(ch) < 128 else " " for ch in text)
    t = re.sub(r"\(\s*\)", "", t)
    return re.sub(r"\s{2,}", " ", t).strip()


def _text(dr, xy, text: str, kind: str, size: int, fill, anchor: str = "la") -> None:
    f, cjk = _font(kind, size)
    dr.text(xy, text if cjk else ascii_fallback(text), font=f, fill=fill, anchor=anchor)


def _fmt(v: float) -> str:
    return f"{v:.4g}" if np.isfinite(v) else "—"


def _draw_title(dr, lines: list[str]) -> None:
    """위쪽 제목 띠(장면이 비워 둔 자리)에 제목 · 부제를 쓴다."""
    y = 10
    for k, line in enumerate(lines):
        # 파트 이름의 역슬래시(묶음 구분)는 한글 글꼴에서 ₩ 로 그려진다 — 보기 좋게 「 / 」 로
        _text(dr, (16, y), line.replace("\\", " / "), "bold" if k == 0 else "regular", 24 if k == 0 else 17,
              (17, 17, 17) if k == 0 else (60, 60, 60))
        y += 32 if k == 0 else 24


def _draw_legend(dr, scene: Scene, title: str) -> None:
    W, H = scene.cam.width, scene.cam.height
    lo, hi = scene.clim
    lx, ly, lw, lh = K.legend_box(W, H)
    n = 256
    cols = np.round(K.rgb(lo + (hi - lo) * (np.arange(n) + 0.5) / n, lo, hi) * 255).astype(int)
    for k in range(n):
        dr.rectangle([lx, ly + lh * (1 - (k + 1) / n), lx + lw, ly + lh * (1 - k / n) + 1], fill=tuple(cols[k]))
    dr.rectangle([lx, ly, lx + lw, ly + lh], outline=(34, 34, 34))
    for tv in K.ticks(lo, hi, 6):
        ty = ly + lh * (1 - (tv - lo) / (hi - lo))
        dr.line([lx + lw, ty, lx + lw + 6, ty], fill=(34, 34, 34))
        _text(dr, (lx + lw + 9, ty), _fmt(tv), "regular", 15, (34, 34, 34), "lm")
    dr.rectangle([lx, ly - lw * 1.4, lx + lw, ly - lw * 0.3], fill=(255, 0, 255), outline=(34, 34, 34))
    _text(dr, (lx + lw + 9, ly - lw * 0.85), f"> {_fmt(hi)}", "regular", 15, (34, 34, 34), "lm")
    _text(dr, (lx, ly - lw * 2.2), title, "bold", 16, (17, 17, 17), "ls")


def _draw_peak(dr, scene: Scene, label: str) -> None:
    if scene.peak_face < 0 or not label:
        return
    W, H = scene.cam.width, scene.cam.height
    x, y, _ = scene.cam.project(scene.peak_point[None, :])[0]
    f, _ = _font("bold", 16)
    x0, y0, x1, y1 = K.label_box(x, y, dr.textlength(label, font=f), W, H)
    dr.line([x, y, x0 if x0 > x else x1, y1 if y0 < y else y0], fill=(0, 0, 0), width=2)
    dr.ellipse([x - 7, y - 7, x + 7, y + 7], fill=(255, 0, 255), outline=(0, 0, 0), width=2)
    dr.rounded_rectangle([x0, y0, x1, y1], radius=4, fill=(255, 255, 255), outline=(51, 51, 51))
    dr.text((x0 + 7, (y0 + y1) / 2), label, font=f, fill=(0, 0, 0), anchor="lm")


def polydata(coords: np.ndarray, faces: np.ndarray):
    """면 배열 → (pyvista PolyData, 셀 순서). 쓰는 절점만 남긴다 — 화면 맞춤 · 크기가 그것으로 정해진다."""
    import pyvista as pv
    used = np.unique(faces[faces >= 0])
    remap = np.full(len(coords), -1, np.int64)
    remap[used] = np.arange(len(used))
    tri = np.nonzero(faces[:, 3] < 0)[0]
    quad = np.nonzero(faces[:, 3] >= 0)[0]
    t = np.column_stack([np.full(len(tri), 3), remap[faces[tri, :3]]]).ravel()
    q = np.column_stack([np.full(len(quad), 4), remap[faces[quad]]]).ravel()
    order = np.concatenate([tri, quad])
    return pv.PolyData(coords[used], np.concatenate([t, q]).astype(np.int64)), order


def _layer(scene: Scene, context: bool) -> np.ndarray:
    """한 겹 — context=True 면 주변 파트(반투명, 흰 바탕 RGB), False 면 타겟(투명 바탕 RGBA)."""
    import pyvista as pv

    s = scene.surf
    W, H = scene.cam.width, scene.cam.height
    p = pv.Plotter(off_screen=True, window_size=(W, H))
    try:
        p.set_background("white")
        p.enable_parallel_projection()
        if context:
            cm, _ = polydata(s.coords, s.faces[scene.context_mask])
            p.add_mesh(cm, color=K.CONTEXT, opacity=scene.context_opacity, smooth_shading=False)
            p.add_mesh(cm.extract_feature_edges(feature_angle=40, boundary_edges=True, non_manifold_edges=False,
                                                manifold_edges=False),
                       color="#8c8c8c", line_width=0.6, opacity=min(1.0, scene.context_opacity * 3.0))
            p.enable_depth_peeling(number_of_peels=8)
        else:
            tm, order = polydata(s.coords, s.faces[scene.target_mask])
            tm.cell_data["v"] = s.face_value[scene.target_mask][order]
            p.add_mesh(tm, scalars="v", cmap=K.CMAP, clim=list(scene.clim), above_color=K.ABOVE,
                       nan_color=K.CONTEXT, smooth_shading=False, show_scalar_bar=False)
            p.add_mesh(tm.extract_feature_edges(feature_angle=30, boundary_edges=True, non_manifold_edges=False,
                                                manifold_edges=False), color="#1e1e1e", line_width=1.1)
        cam = scene.cam.to_vtk(distance=float(np.linalg.norm(np.ptp(s.coords, axis=0))) * 2.0 + 1.0)
        p.camera.focal_point = cam["focal_point"]
        p.camera.position = cam["position"]
        p.camera.up = cam["view_up"]
        p.camera.parallel_scale = cam["parallel_scale"]
        p.camera_set = True
        p.renderer.ResetCameraClippingRange()
        p.enable_anti_aliasing("ssaa")
        return np.asarray(p.screenshot(None, transparent_background=not context, return_img=True))
    finally:
        p.close()


def render(scene: Scene, out: str | Path, title_lines: list[str], legend_title: str = "von Mises",
           peak_label: str | None = None) -> Path:
    from PIL import Image, ImageDraw

    W, H = scene.cam.width, scene.cam.height
    top = Image.fromarray(_layer(scene, context=False)).convert("RGBA")
    base = (Image.fromarray(_layer(scene, context=True)).convert("RGBA") if scene.context_mask.any()
            else Image.new("RGBA", (W, H), (255, 255, 255, 255)))
    im = Image.alpha_composite(base, top).convert("RGB")
    dr = ImageDraw.Draw(im)
    _draw_legend(dr, scene, legend_title)
    _draw_peak(dr, scene, peak_label or "")
    _draw_title(dr, title_lines)
    out = Path(out)
    im.save(out)
    return out
