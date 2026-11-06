# 리포트 그림 명령 — deep 산출 폴더에서 그림 꾸러미(pack), d3plot 한 상태의 스냅샷(snap)
"""
    python -m koo_deep_report.figures pack <deep 산출 폴더> [--d3plot P] [--out DIR] [--top 5] [--parts 21 16] [--hide 23]
    python -m koo_deep_report.figures snap <d3plot> --state N [--parts 21] [--hide 23] [--view iso|peak|top…] [--out DIR]

deep 리포트는 기본으로 꾸러미를 만든다(--no-figures 로 끈다). 이 명령은 이미 있는 산출 폴더에 다시 만들거나,
원하는 순간 · 파트 · 시점의 그림 하나를 따로 뽑을 때 쓴다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--hide", nargs="+", type=int, default=None, metavar="ID",
                   help="숨길 파트 — 바닥(환경 파트)은 자동으로 숨기고 이것을 더한다")
    p.add_argument("--no-auto-floor", action="store_true", help="바닥 자동 감지를 끈다")
    p.add_argument("--context-opacity", type=float, default=0.15, metavar="A", help="주변 파트 불투명도 (기본 0.15)")
    p.add_argument("--clim", default="p99.5",
                   help="색 범위 위 끝 — p99.5(기본) · max · 숫자(예: 항복 응력). 넘는 값은 자홍")
    p.add_argument("--size", default="1600x1100", help="그림 크기 WxH (기본 1600x1100)")


def _clim(s: str):
    try:
        return float(s)
    except ValueError:
        return s


def _size(s: str) -> tuple[int, int]:
    w, h = s.lower().split("x")
    return int(w), int(h)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m koo_deep_report.figures",
                                 description="리포트 그림 — 최대 순간 스냅샷(PNG · 호버 SVG) · 차트 · manifest")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pk = sub.add_parser("pack", help="deep 산출 폴더 → 그림 꾸러미(<폴더>/figures)")
    pk.add_argument("report_dir")
    pk.add_argument("--d3plot", default=None, help="d3plot 경로(기본: analysis_result 의 경로 → 폴더 위)")
    pk.add_argument("--out", default=None, help="출력 폴더(기본 <report_dir>/figures)")
    pk.add_argument("--top", type=int, default=5, help="상위 파트 수 — 안전율 낮은 순, 없으면 최대 응력 순 (기본 5)")
    pk.add_argument("--parts", nargs="+", type=int, default=None, metavar="ID", help="그릴 파트를 직접 고른다")
    pk.add_argument("--views", default="iso,peak", help="파트 그림 시점(쉼표) — iso · peak · top · front … (기본 iso,peak)")
    _common(pk)
    sn = sub.add_parser("snap", help="d3plot 한 상태 → 스냅샷 하나(PNG · SVG)")
    sn.add_argument("d3plot")
    sn.add_argument("--state", type=int, required=True, help="d3plot 상태 번호(0 부터)")
    sn.add_argument("--parts", nargs="+", type=int, default=None, metavar="ID", help="타겟 파트(비우면 전체)")
    sn.add_argument("--view", default="iso", help="iso · peak · top · bottom · front · back · left · right · iso_back")
    sn.add_argument("--out", default=".", help="출력 폴더(기본 현재 폴더)")
    sn.add_argument("--name", default="", help="파일 이름(확장자 없이, 기본 snap_s<상태>_<시점>)")
    _common(sn)
    a = ap.parse_args(argv)
    W, H = _size(a.size)

    from . import pack
    if a.cmd == "pack":
        inp = pack.inputs_from_dir(a.report_dir, a.d3plot)
        out = Path(a.out) if a.out else Path(a.report_dir) / "figures"
        m = pack.build(inp, out, top=a.top, figure_parts=a.parts, hide_parts=a.hide, auto_floor=not a.no_auto_floor,
                       context_opacity=a.context_opacity, views=tuple(v for v in a.views.split(",") if v),
                       width=W, height=H, clim=_clim(a.clim))
        print(f"{pack.summary(m)} → {out}")
        for n in m.get("notes") or []:
            print(f"  · {n}")
        return 0 if m.get("figures") else 1

    from . import mesh, png, scene, svg, xvfb
    s = mesh.read_state(a.d3plot, a.state)
    hidden = sorted(set(a.hide or []) | (set() if a.no_auto_floor else set(mesh.environment_parts(s))))
    uid, label, _ = pack._units([], pack._keyword(a.d3plot), None)
    inp = pack.RunInputs(Path(a.d3plot), Path(a.d3plot).resolve().parent.name, {}, uid, label)
    U = inp.stress_label
    sc = scene.build(s, a.parts, hidden, view=a.view, width=W, height=H, clim=_clim(a.clim),
                     context_opacity=a.context_opacity)
    head = "All parts" if not a.parts else " · ".join(f"Part {p} {s.part_titles.get(p, '')}".rstrip() for p in a.parts)
    title = [f"{head} — von Mises max {pack._fmt(sc.peak_value)} {U}",
             f"t = {inp.t_text(s.time)} · state {s.state_index} · color {pack._fmt(sc.clim[0])}–"
             f"{pack._fmt(sc.clim[1])} {U} · view {a.view}" + (f" · hidden {', '.join(map(str, hidden))}" if hidden else "")]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    name = a.name or f"snap_s{a.state}_{a.view}"
    with xvfb.display():
        png.render(sc, out / f"{name}.png", title, legend_title=f"von Mises ({U})",
                   peak_label=f"max {pack._fmt(sc.peak_value)}")
    svg.write(sc, out / f"{name}.svg", title, pack._part_info(inp, s, sc), unit=U)
    print(f"{out / name}.png · .svg (숨김 {hidden})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
