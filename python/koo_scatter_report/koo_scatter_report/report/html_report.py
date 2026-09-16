# 산포 캠페인 보고서 HTML 을 외부 의존 없이 조립하는 모듈
"""산포 보고서 HTML.

**있을 때/없을 때 규율.** 그릴 데이터가 없는 그림은 **자리를 남기고 사유를 적는다**.
섹션을 통째로 지우면 "원래 없는 것" 과 "데이터가 없어서 못 그린 것" 이 구분되지
않는다. 반대로 값을 지어내지도 않는다.
"""

from __future__ import annotations

import html
import math
from datetime import datetime, timezone

from .. import __version__
from .. import charts as C


def _esc(s) -> str:
    return html.escape(str(s), quote=True)


def _fin(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and not math.isnan(v)


def _metric_values(tbl, criterion, metric, part_id=None):
    """(run, dev_angle, face, value) 목록."""
    out = []
    for r in tbl.rows:
        if r[9] != criterion or r[10] != metric:
            continue
        if part_id is not None and r[7] != part_id:
            continue
        if not _fin(r[11]):
            continue
        out.append((r[0], r[5], r[4], r[11], r[1], r[2]))
    return out


def _section(title, body, note="") -> str:
    n = f'<p class="note">{_esc(note)}</p>' if note else ""
    return (f'<section><h2>{_esc(title)}</h2>{n}<div class="fig">{body}</div></section>')


def build_html(si, criterion: str, metric: str, part_id=None,
               title: str = "각도 산포 리포트") -> str:
    """ScatterInput → 자립 HTML 문자열."""
    tbl = si.table
    gt = si.gt
    segs = si.segments

    vals = _metric_values(tbl, criterion, metric, part_id)
    n_runs = tbl.n_runs
    faces = sorted({v[2] for v in vals if v[2]})

    # ── 머리말 (무엇으로 만든 보고서인지) ──
    builds = tbl.tool_builds or {}
    n_known = sum(builds.values())
    n_unknown = max(0, n_runs - n_known)
    if len(builds) > 1 or (builds and n_unknown):
        bnote = "⚠ 런마다 분석 빌드가 다릅니다 — " + ", ".join(
            [f"{k}({v}런)" for k, v in sorted(builds.items())]
            + ([f"기록 없음({n_unknown}런)"] if n_unknown else []))
    elif builds:
        bnote = f"분석 빌드: {next(iter(builds))}"
    else:
        bnote = "분석 빌드 기록이 없습니다 (2026-09-13 이전 산출물)"

    lat = {}
    for r in tbl.runs:
        if r[9]:
            lat.setdefault(r[9], set()).add(r[0])
    latnote = ", ".join(f"{k} {len(v)}런" for k, v in sorted(lat.items())) or "각도 정보 없음"
    off = lat.get("off_lattice")

    secs = []

    # ① 산포도 — 편차각 vs 값
    if vals:
        secs.append(_section(
            "① 편차각 산포",
            C.scatter([(v[1], v[3], v[2]) for v in vals if _fin(v[1])],
                      ylabel=f"{criterion} / {metric}"),
            "면 기준자세에서 얼마나 벗어났는지(편차각) 대비 값. "
            "절대각으로 보면 Front 가 180° 로 나와 부호가 뒤집힌다."))
    else:
        secs.append(_section("① 편차각 산포",
                             C.note_svg(720, 380, "선택한 기준량·지표에 값이 없습니다")))

    # ② 방향도
    secs.append(_section(
        "② 방향도 (roll–pitch)",
        C.direction_map([(v[4], v[5], v[3]) for v in vals if _fin(v[4]) and _fin(v[5])],
                        vlabel=metric),
        "각도 평면에 값을 색으로. 어느 자세가 위험한지 한눈에 본다."))

    # ③ 히트맵 — 면 × 편차각 구간
    edges = [0, 5, 10, 20, 30, 45, 60, 90, 180]
    labels = [f"{edges[i]}–{edges[i+1]}" for i in range(len(edges) - 1)]
    if faces and any(_fin(v[1]) for v in vals):
        grid = []
        for f in faces:
            row = []
            for i in range(len(edges) - 1):
                sel = [v[3] for v in vals
                       if v[2] == f and _fin(v[1])
                       and edges[i] <= v[1] < edges[i + 1]]
                row.append(sum(sel) / len(sel) if sel else None)
            grid.append(row)
        secs.append(_section("③ 면 × 편차각 히트맵",
                             C.heatmap(faces, labels, grid, vlabel=metric,
                                       xlabel="편차각 구간 [deg]"),
                             "빈 칸은 그 구간에 표본이 없다는 뜻이다 (0 이 아니다)."))
    else:
        secs.append(_section("③ 면 × 편차각 히트맵",
                             C.note_svg(720, 300, "면 또는 편차각 정보가 없습니다")))

    # ④ 회수율 곡선 — 불량 데이터가 있을 때만
    if gt is not None and getattr(gt, "rows", None):
        try:
            from koo_deep_report.core.ground_truth import part_recall
        except ImportError:
            part_recall = None
        if part_recall is None:
            secs.append(_section("④ 회수율", C.note_svg(560, 340,
                                 "koo_deep_report 를 가져오지 못했습니다")))
        else:
            by_part = {}
            for v in vals:
                pass
            for r in tbl.rows:
                if r[9] == criterion and r[10] == metric and _fin(r[11]):
                    by_part[r[7]] = max(by_part.get(r[7], float("-inf")), r[11])
            ks, rs, bs = [], [], []
            for k in range(1, max(2, len(by_part)) + 1):
                mr = part_recall(by_part, gt, k)
                if mr.recall is None:
                    continue
                ks.append(k); rs.append(mr.recall); bs.append(mr.baseline)
            secs.append(_section(
                "④ 회수율 recall@k",
                C.recall_curve(ks, rs, bs),
                f"시뮬 상위 k 파트를 검사했을 때 실제 불량을 몇 개 잡는가. "
                f"불량 파트 {len(gt.ng_parts())}개."))
    else:
        secs.append(_section(
            "④ 회수율 recall@k",
            C.note_svg(560, 340, "시험 불량 데이터가 없습니다 (--ground-truth 로 주세요)"),
            "정합성은 시뮬만으로 계산할 수 없다."))

    # ⑤ 편차각 구간 프로파일
    if any(_fin(v[1]) for v in vals):
        means, counts = [], []
        for i in range(len(edges) - 1):
            sel = [v[3] for v in vals if _fin(v[1]) and edges[i] <= v[1] < edges[i + 1]]
            counts.append(len(sel))
            means.append(sum(sel) / len(sel) if sel else None)
        secs.append(_section("⑤ 편차각 구간 프로파일",
                             C.bar_profile(labels, means, counts,
                                           xlabel="편차각 구간 [deg]", ylabel=metric),
                             "표본이 없는 구간은 흐린 칸으로 비워 둔다."))
    else:
        secs.append(_section("⑤ 편차각 구간 프로파일",
                             C.note_svg(680, 320, "편차각 정보가 없습니다")))

    # ⑤b 통계 — 순위검정·상관. 귀무가설을 산출물에 함께 적는다.
    try:
        from koo_deep_report.core.stats_ranking import mean_rank_test, spearman
        from koo_deep_report.core.doe_common import common_doe
    except ImportError:
        mean_rank_test = spearman = common_doe = None
    if mean_rank_test is not None and vals:
        lines = []
        # (a) 면별 평균순위 — "이 면이 위험하다" 가 우연인지
        by_run = {}
        for r in tbl.rows:
            if r[9] != criterion or r[10] != metric or not _fin(r[11]):
                continue
            by_run.setdefault(r[0], {})[r[7]] = max(
                by_run.get(r[0], {}).get(r[7], float("-inf")), r[11])
        parts_all = sorted({p for d in by_run.values() for p in d})
        if len(parts_all) >= 2 and len(by_run) >= 1:
            ranked = {}
            for run, d in by_run.items():
                order = sorted(d, key=lambda p: -d[p])
                for i, p_ in enumerate(order):
                    ranked.setdefault(p_, []).append(i + 1)
            scored = []
            for p_, rk in ranked.items():
                res = mean_rank_test(rk, len(parts_all))
                if res.p_value is not None:
                    scored.append((res.p_value, p_, res))
            scored.sort()
            for pv, p_, res in scored[:5]:
                mark = " ★" if pv < 0.05 else ""
                lines.append(f"파트 {p_}: 평균순위 {res.mean_rank:.2f} "
                             f"(귀무 {res.null_expected:.2f}) · p={pv:.4g} "
                             f"[{res.method}]{mark}")
            if scored:
                lines.append(f"귀무가설: {scored[0][2].null_hypothesis}")
        # (b) 편차각 ↔ 값 상관
        sp = spearman([v[1] for v in vals if _fin(v[1])],
                      [v[3] for v in vals if _fin(v[1])])
        if sp.rho is not None:
            lines.append(f"편차각 ↔ {metric} Spearman ρ = {sp.rho:.4f} (n={sp.n})")
        elif sp.note:
            lines.append(f"편차각 상관: {sp.note}")
        # (c) 런 간 공통 파트 — 표본이 어긋나면 비교가 무의미하다
        if common_doe is not None and len(by_run) >= 2:
            cd = common_doe({k: list(v) for k, v in by_run.items()}, min_common=1,
                            reject_below=False)
            lines.append(f"런 간 공통 파트: {cd.n_common}개" +
                         (f" · {cd.limiting[0][0]} 를 빼면 "
                          f"{cd.n_common + cd.limiting[0][1]}개" if cd.limiting else ""))
        body = ("<ul class='stat'>" + "".join(f"<li>{_esc(t)}</li>" for t in lines)
                + "</ul>") if lines else C.note_svg(560, 120, "통계를 낼 표본이 부족합니다")
        secs.append(_section("⑤b 순위 검정 · 상관", body,
                             "★ 는 p<0.05. 귀무가설은 코드에 고정돼 있다 — "
                             "매번 사람이 고르면 또 틀린다."))

    # ⑥ 리스크맵 — 클러스터 평면 투영
    items = [it for it in (tbl.items or []) if it.get("criterion") == criterion
             and (part_id is None or it.get("part_id") == part_id)]
    # 실물 불량 좌표 — 있으면 겹쳐 그린다. 없으면 표시하지 않는다(지어내지 않는다).
    marks = []
    if gt is not None and hasattr(gt, "ng_points"):
        try:
            marks = [(p_[0], p_[1], p_[3]) for p_ in gt.ng_points()]
        except Exception:      # noqa: BLE001 — 보고서가 죽지 않게
            marks = []
    if items:
        circ = []
        bmin = bmax = None
        for it in items:
            bmin = bmin or it.get("bbox_min")
            bmax = bmax or it.get("bbox_max")
            for c in it.get("clusters") or []:
                ctr = c.get("center")
                if not (isinstance(ctr, list) and len(ctr) == 3):
                    continue
                v = c.get("stress_max")
                if not _fin(v):
                    continue
                circ.append((ctr[0], ctr[1], c.get("radius_enclosing") or 0.0, v,
                             f"{it['run'][:18]} #{c.get('rank')}"))
        secs.append(_section("⑥ 리스크맵 (전 각도 중첩)",
                             C.risk_map(circ, bmin, bmax, vlabel="stress_max",
                                        marks=marks),
                             "모든 각도의 덩어리를 한 평면에 겹쳐 그린다. "
                             "자주·크게 뜨는 자리가 실제 위험 구역이다."
                             + (f" 하늘색 ✕ {len(marks)}개는 실물 불량 위치."
                                if marks else "")))
    else:
        secs.append(_section("⑥ 리스크맵",
                             C.note_svg(560, 460, "군집 데이터가 없습니다 "
                                        "(unified_analyzer --hotspot-clusters 필요)")))

    # ⑦ 구간도 — 구간 정의가 있을 때만
    if segs is not None and getattr(segs, "segments", None):
        boxes, svals = [], {}
        for s_ in segs.segments:
            if s_.kind != "box":
                continue
            boxes.append((s_.name, s_.lo[0], s_.lo[1], s_.hi[0], s_.hi[1]))
        centers = []
        for it in items:
            for c in it.get("clusters") or []:
                ctr = c.get("center")
                if isinstance(ctr, list) and len(ctr) == 3:
                    centers.append((ctr[0], ctr[1]))
                    nm = segs.assign(ctr)
                    v = c.get("stress_max")
                    if nm and _fin(v):
                        svals[nm] = max(svals.get(nm, float("-inf")), v)
        secs.append(_section("⑦ 구간도",
                             C.segment_map(boxes, svals, centers, vlabel="stress_max"),
                             "파트를 구간으로 쪼개 본다. 파랑 원은 군집 중심."))
    else:
        secs.append(_section("⑦ 구간도",
                             C.note_svg(560, 420, "구간 정의가 없습니다 (--segments 로 주세요)"),
                             "인터포저가 한 파트로 묶인 과제에서 쓴다."))

    # ⑧ 둘레 전개도
    if items:
        circ3 = []
        bmin = bmax = None
        for it in items:
            bmin = bmin or it.get("bbox_min")
            bmax = bmax or it.get("bbox_max")
            for c in it.get("clusters") or []:
                ctr = c.get("center")
                v = c.get("stress_max")
                if isinstance(ctr, list) and len(ctr) == 3 and _fin(v):
                    circ3.append((ctr[0], ctr[1], ctr[2],
                                  c.get("radius_enclosing") or 0.0, v,
                                  f"{it['run'][:18]} #{c.get('rank')}"))
        secs.append(_section("⑧ 둘레 전개도",
                             C.perimeter_unroll(circ3, bmin, bmax, axis=2,
                                                vlabel="stress_max"),
                             "측면을 둘레 각도로 펼친다. 옆면 어느 방향이 위험한지 본다."))
    else:
        secs.append(_section("⑧ 둘레 전개도",
                             C.note_svg(760, 300, "군집 데이터가 없습니다")))

    # ⑨ 크랙 오버레이 — 불량 좌표가 있을 때만
    if marks and items:
        # 시뮬 상위 덩어리만 남겨 실물 위치와 나란히 본다
        top = sorted(circ, key=lambda c: -c[3])[:40] if items else []
        secs.append(_section(
            "⑨ 실물 불량 오버레이",
            C.risk_map(top, bmin, bmax, vlabel="stress_max", marks=marks,
                       w=640, h=520),
            f"시뮬 상위 덩어리 {len(top)}개와 실물 불량 {len(marks)}곳을 겹친다. "
            f"✕ 가 뜨거운 자리에 놓이면 정합이 맞는 것이다."))
    else:
        why = ("불량 데이터에 좌표(x/y/z)가 없습니다 — 세 열을 채우면 겹쳐 그립니다"
               if (gt is not None and getattr(gt, "rows", None))
               else "시험 불량 데이터가 없습니다 (--ground-truth 로 주세요)")
        secs.append(_section(
            "⑨ 실물 불량 오버레이", C.note_svg(640, 300, why),
            "파트 단위 정합은 ④ 회수율이 담당한다. 위치 단위로 보려면 좌표가 필요하다."))

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    head = (f'<div class="meta">{_esc(title)} · 런 {n_runs}개 · 기준 {_esc(criterion)}'
            f' · 지표 {_esc(metric)}'
            + (f' · 파트 {part_id}' if part_id is not None else '')
            + f' · {now}</div>'
            f'<div class="sub">{_esc(bnote)}</div>'
            f'<div class="sub">각도 격자: {_esc(latnote)}'
            + (f' <b class="warn">⚠ 격자에서 벗어난 런 {len(off)}개 — '
               f'코너 각도 결함이 있던 도구로 만든 캠페인일 수 있습니다</b>' if off else '')
            + '</div>')

    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_esc(title)}</title>
<style>
:root {{ color-scheme: dark; }}
body {{ margin:0; background:#0f1320; color:#e0e0e0;
  font-family:system-ui,-apple-system,"Noto Sans KR",sans-serif; }}
header {{ padding:18px 20px; background:#151a2b; border-bottom:1px solid #2a2f45; }}
h1 {{ margin:0 0 6px; font-size:1.12rem; }}
.meta {{ color:#9aa0b5; font-size:0.83rem; }}
.sub {{ color:#9aa0b5; font-size:0.79rem; margin-top:3px; }}
.warn {{ color:#f5a623; }}
main {{ padding:16px 20px 48px; max-width:1100px; margin:0 auto; }}
section {{ margin:22px 0; }}
h2 {{ font-size:0.98rem; margin:0 0 6px; color:#cfd4e6; }}
.note {{ color:#9aa0b5; font-size:0.79rem; margin:0 0 8px; }}
.fig {{ background:#151a2b; border:1px solid #2a2f45; border-radius:8px; padding:10px; }}
ul.stat {{ margin:0; padding:6px 0 6px 20px; font-size:0.84rem; line-height:1.7; }}
ul.stat li {{ color:#cfd4e6; }}
.foot {{ color:#6b718c; font-size:0.75rem; padding:0 20px 24px; max-width:1100px; margin:0 auto; }}
</style></head>
<body>
<header><h1>{_esc(title)}</h1>{head}</header>
<main>{''.join(secs)}</main>
<div class="foot">koo_scatter_report v{_esc(__version__)} · 그림은 외부 라이브러리 없이
SVG 로 그렸습니다 (망이 막혀도 열립니다).</div>
</body></html>"""
