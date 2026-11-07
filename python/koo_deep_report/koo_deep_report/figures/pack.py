# 런 하나의 리포트 그림 꾸러미 — 전체 · 상위 파트 최대 순간 스냅샷(PNG·SVG), 에너지 · 이력 · 파트 요약 차트, manifest.json
"""리포트가 그대로 가져다 쓰는 표준 묶음(계획 §2-2). 입력은 `RunInputs` 하나로 모으고, 만드는 길은 둘이다.
- `inputs_from_result(result)` — deep 리포트가 메모리에 든 SingleResult 에서.
- `inputs_from_dir(report_dir)` — deep 산출 폴더(analysis_result.json · result.json · motion/)에서(CLI · 캠페인 그림).

대상 파트(사용자 결정 11-06) — `figure_parts` 가 있으면 그것, 없으면 상위 5개: 안전율이 있는 파트를 낮은 순으로, 그다음 최대 응력 순.
안전율과 판정 색은 deep 이 셈한 값(PartSummary.safety_factor · stress_warning)을 그대로 쓴다 — 같은 보고서 안에서 판정이 둘이 되지 않게.
환경 파트(바닥)는 대상에서 빼고 그림에서 숨긴다. 그림 하나가 실패해도 나머지는 만들고, 실패는 manifest `notes` 에 남긴다.

상태 번호 — 응력 이력은 d3plot 상태마다 한 점이다(v14: 4,952 점 = 4,952 상태, 시각 차 최대 5e-13 s). 이력이 잘렸거나 점 수가
상태 수와 다르면 순번을 믿지 않고 그 파트는 그리지 않는다. 읽은 상태의 시각이 이력의 최대 시각과 다르면 notes 에 남긴다.

그림 제목은 영문 기술 표기(Part · state · color …)로 쓴다 — SIF 에 한글 글꼴이 없을 수 있어 PNG 에서 한글이 지워지면 문장이 깨진다.
설명(caption) · 차트(SVG, 보는 브라우저 글꼴로 그려진다)는 한글이다.
"""
from __future__ import annotations

import json
import math
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

import numpy as np

from . import charts

FORMAT = "kood3plot.figures"
FORMAT_VERSION = 1
DECK = "덱 단위"
#: 단위계 → (응력, 시간 단위, 시간을 ms 로 바꾸는 배율, 에너지, 표준 중력). 표준 중력은 ontology.deep._G0 와 같은 값
_UNITS = {"ton-mm-s": ("MPa", "s", 1e3, "mJ", 9806.65), "g-mm-ms": ("MPa", "ms", 1.0, "mJ", 9.80665e-3),
          "SI": ("Pa", "s", 1e3, "J", 9.80665)}
_RENDER_LOCK = threading.Lock()
_VERDICT = {"crit": "CRITICAL", "warn": "WARNING", "ok": "OK"}
#: 이 꾸러미가 쓰는 파일 — 다시 만들 때 지난 실행의 그림이 섞이지 않게 이것만 지운다
_OURS = re.compile(r"^(overview_(peak|worst)|part_\d+_(peak|worst)_[a-z_]+|part_\d+_history|energy|parts_(peak|worst))"
                   r"\.(png|svg)$"
                   r"|^(manifest\.json|index\.html)$")


@dataclass
class PartPeak:
    pid: int
    name: str
    peak: float | None                 # 런 전체 최대 von Mises(덱 단위)
    time: float | None                 # 그 시각(덱 단위)
    state: int | None                  # 그 시각의 d3plot 상태 번호. 못 정하면 None — 그리지 않는다
    sf: float | None = None            # 안전율(deep: 설계 한계 / 최대 응력)
    severity: str = "UNKNOWN"          # deep 판정 — CRITICAL · WARNING · OK · UNKNOWN
    hist_t: list = field(default_factory=list)
    hist_v: list = field(default_factory=list)
    acc_t: list = field(default_factory=list)   # 파트 평균 가속도 크기(motion CSV, 덱 단위)
    acc_v: list = field(default_factory=list)


@dataclass
class RunInputs:
    d3plot: Path
    run_folder: str
    parts: dict[int, PartPeak]
    unit_system: str = ""              # "ton-mm-s" · "g-mm-ms" · "SI" · ""(모름)
    unit_stress: str = DECK            # 응력 표시 라벨
    glstat: dict | None = None         # {"t", "kinetic", "internal", "total", "hourglass"?}
    notes: list[str] = field(default_factory=list)

    @property
    def stress_label(self) -> str:
        """그림 글자용(ASCII) — VTK 범례 · 영문 제목."""
        return self.unit_stress if self.unit_stress.isascii() else "deck units"

    def t_text(self, t) -> str:
        if t is None or not math.isfinite(t):
            return "—"
        u = _UNITS.get(self.unit_system)
        return f"{t * u[2]:.4g} ms" if u else f"{t:.4g} (deck time)"


class _Job(NamedTuple):
    state: int
    fid: str
    targets: list[int] | None
    view: str
    t: float | None                    # 이력이 말하는 그 순간의 시각 — 읽은 상태와 대조
    caption: str
    kind: str
    pid: int | None


def _num(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _fmt(v) -> str:
    v = _num(v)
    return "—" if v is None else f"{v:.4g}"


def _from_series(stress, motion, num_states: int, summary: dict, notes: list[str]) -> dict[int, PartPeak]:
    """stress — PartTimeSeries 목록, motion — {pid: MotionData}, summary — {pid: (이름, 안전율, deep 판정)}."""
    parts: dict[int, PartPeak] = {}
    for st in stress:
        pid = int(st.part_id)
        name, sf, verdict = summary.get(pid, ("", None, "none"))
        times = [d.get("time") for d in st.data]
        state = None
        if st.data and not st.truncated and (not num_states or len(st.data) == num_states):
            state = int(np.argmin(np.abs(np.asarray(times, dtype=np.float64) - float(st.time_of_max))))
        elif st.data:
            notes.append(f"파트 {pid}: 응력 이력 점 수({len(st.data)}/{st.num_points}, 상태 {num_states})가 맞지 않아 "
                         f"최대 순간의 상태 번호를 정하지 못했다 — 스냅샷을 만들지 않는다")
        mo = motion.get(pid)
        parts[pid] = PartPeak(pid, name or st.part_name or f"Part {pid}", _num(st.global_max), _num(st.time_of_max),
                              state, _num(sf), _VERDICT.get(verdict, "UNKNOWN"), times,
                              [d.get("max") for d in st.data],
                              list(mo.t) if mo else [], list(mo.acc_mag) if mo else [])
    return parts


def _keyword(path):
    try:
        from ..core.keyword_parser import find_and_parse_keyword
        return find_and_parse_keyword(path)
    except Exception:  # noqa: BLE001
        return None


def _units(stress, keyword, end_time) -> tuple[str, str, str]:
    """(단위계, 응력 라벨, 단서). 라벨은 해석기가 준 것 → 덱 밀도 판정 → '덱 단위' 순."""
    analyzer = next((x.unit for x in stress if x.unit), "")
    try:
        from ..ontology.deep import detect_units
        uid, note = detect_units(keyword, end_time)
    except Exception as e:  # noqa: BLE001
        uid, note = "", f"단위계를 판정하지 못했다 — {type(e).__name__}: {e}"
    if analyzer and analyzer != "deck_units":
        return uid, analyzer, note
    return uid, (_UNITS[uid][0] if uid in _UNITS else DECK), note


def inputs_from_result(result, keyword=None) -> RunInputs:
    """deep 의 SingleResult → RunInputs. `keyword`(KeywordData)를 주면 덱을 다시 읽지 않는다."""
    from ..ontology.deep import run_folder_of
    si, d3 = result.sim_info, result.d3plot_result
    if d3 is None or si.d3plot is None:
        raise ValueError("d3plot 결과가 없다")
    notes: list[str] = []
    summary = {pid: (ps.part_name, ps.safety_factor, ps.stress_warning) for pid, ps in result.parts.items()}
    parts = _from_series(d3.stress, d3.motion, d3.num_states, summary, notes)
    gl = result.glstat_data
    glstat = ({"t": gl.t, "kinetic": gl.kinetic_energy, "internal": gl.internal_energy, "total": gl.total_energy,
               "hourglass": gl.hourglass_energy} if gl is not None and gl.t else None)
    uid, label, note = _units(d3.stress, keyword if keyword is not None else _keyword(si.keyword or si.d3plot),
                              d3.t_end)
    return RunInputs(Path(si.d3plot), run_folder_of(si.path), parts, uid, label, glstat,
                     notes + ([note] if note else []))


def inputs_from_dir(report_dir: str | Path, d3plot: str | Path | None = None) -> RunInputs:
    """deep 산출 폴더 → RunInputs. d3plot 은 인자 → analysis_result 의 경로 → 폴더 위(<Run>/Output/d3plot) 순으로 찾는다."""
    from ..core.d3plot_reader import _parse_outputs
    from ..ontology.deep import run_folder_of
    rd = Path(report_dir)
    d3 = _parse_outputs(rd, series={"stress"})
    res = json.loads((rd / "result.json").read_text(encoding="utf-8")) if (rd / "result.json").exists() else {}
    cands = [d3plot, d3.metadata.get("d3plot_path"), (res.get("metadata") or {}).get("d3plot_path"),
             rd.parent / "d3plot"]
    d3p = next((Path(c) for c in cands if c and Path(c).is_file()), None)
    if d3p is None:
        raise FileNotFoundError(f"d3plot 을 찾지 못했다(후보 {[str(c) for c in cands if c]}) — d3plot 경로를 준다")
    notes = [] if res else ["result.json 이 없어 안전율 · 판정 · 에너지 없이 만들었다"]
    summary = {int(k): (v.get("name") or "", v.get("safety_factor"), v.get("stress_warning") or "none")
               for k, v in (res.get("parts") or {}).items()}
    parts = _from_series(d3.stress, d3.motion, d3.num_states, summary, notes)
    gl = res.get("glstat") or {}
    glstat = ({"t": gl.get("t"), "kinetic": gl.get("kinetic_energy"), "internal": gl.get("internal_energy"),
               "total": gl.get("total_energy")} if gl.get("t") else None)
    uid, label, note = _units(d3.stress, _keyword(d3p), d3.t_end)
    return RunInputs(d3p, run_folder_of(d3p.parent), parts, uid, label, glstat, notes + ([note] if note else []))


def choose_targets(parts: dict[int, PartPeak], top: int, figure_parts: list[int] | None,
                   exclude: set[int]) -> list[int]:
    """지정이 있으면 그 순서대로(숨긴 파트는 뺀다), 없으면 안전율 낮은 순 → 최대 응력 순 상위 top 개."""
    if figure_parts:
        return [p for p in dict.fromkeys(figure_parts) if p not in exclude]
    cand = [p for p in parts.values() if p.pid not in exclude and p.state is not None and (p.peak or 0) > 0]
    cand.sort(key=lambda p: (p.sf is None, p.sf if p.sf is not None else 0.0, -(p.peak or 0.0)))
    return [p.pid for p in cand[:max(0, top)]]


def _part_info(inp: RunInputs, s, sc) -> dict[int, dict]:
    """SVG 툴팁 — 보이는 파트마다 이름 · 이 순간 최대(그 파트 모든 요소) · 런 전체 최대 · 안전율."""
    info = {}
    for pid in np.unique(s.face_part[sc.target_mask | sc.context_mask]).tolist():
        pp = inp.parts.get(pid)
        m = s.part_max.get(pid)
        info[pid] = {"name": pp.name if pp else s.part_titles.get(pid, f"Part {pid}"),
                     "value": round(m, 4) if m is not None and math.isfinite(m) else None,
                     "peak": round(pp.peak, 4) if pp and pp.peak is not None else None,
                     "sf": round(pp.sf, 3) if pp and pp.sf is not None else None}
    return info


def range_text(sc, clim, U: str) -> str:
    """제목 둘째 줄의 색 범위 — 「color 0–233 MPa (p99.5, above = magenta)」."""
    above = ", above = magenta" if (_num(sc.peak_value) or 0) > sc.clim[1] else ""
    return f"color {_fmt(sc.clim[0])}–{_fmt(sc.clim[1])} {U} ({clim if isinstance(clim, str) else 'fixed'}{above})"


def draw(s, targets, hidden, view: str, out: Path, fid: str, title, info, *, unit_label: str, width: int = 1600,
         height: int = 1100, clim: str | float = "p99.5", context_opacity: float = 0.15):
    """한 장 — 장면을 정하고 PNG · SVG 를 쓴다. title(sc) → 제목 줄, info(sc) → 툴팁 dict.
    (장면, manifest 항목의 공통 부분)을 돌려준다. 런 꾸러미와 캠페인 그림이 함께 쓴다."""
    from . import png, scene, svg
    sc = scene.build(s, targets, hidden, view=view, width=width, height=height, clim=clim,
                     context_opacity=context_opacity)
    lines = title(sc)
    png.render(sc, out / f"{fid}.png", lines, legend_title=f"von Mises ({unit_label})",
               peak_label=f"{'surface max' if sc.peak_inside else 'max'} {_fmt(sc.peak_value)}")
    svg.write(sc, out / f"{fid}.svg", lines, info(sc), unit=unit_label)
    cam = sc.cam
    return sc, {"id": fid, "targets": sc.targets, "hidden": sc.hidden, "state": s.state_index, "time": _num(s.time),
                "value": _num(sc.value_max), "surface_value": _num(sc.peak_value), "view": view,
                "color_range": [_num(sc.clim[0]), _num(sc.clim[1])],
                "camera": {"direction": np.round(cam.direction, 6).tolist(), "up": np.round(cam.up, 6).tolist(),
                           "focal": np.round(cam.focal, 6).tolist(), "parallel_scale": _num(cam.scale)},
                "files": {"png": f"{fid}.png", "svg": f"{fid}.svg"}}


def summary(manifest: dict) -> str:
    figs = manifest.get("figures") or []
    n_snap = sum(1 for f in figs if (f.get("files") or {}).get("png"))
    return (f"스냅샷 {n_snap}장 · 차트 {len(figs) - n_snap}개 · 대상 파트 {manifest.get('targets')}"
            + (f" · 알림 {len(manifest.get('notes') or [])}건" if manifest.get("notes") else ""))


def build(inp: RunInputs, out_dir: str | Path, *, top: int = 5, figure_parts: list[int] | None = None,
          hide_parts: list[int] | None = None, auto_floor: bool = True, context_opacity: float = 0.15,
          views: tuple[str, ...] = ("iso", "peak"), width: int = 1600, height: int = 1100,
          clim: str | float = "p99.5") -> dict:
    """그림을 만들고 manifest(dict)를 돌려준다. `out_dir/manifest.json` 도 쓴다."""
    from . import mesh, xvfb

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for f in out.iterdir():
        if f.is_file() and _OURS.match(f.name):
            f.unlink()
    U = inp.stress_label
    notes = list(inp.notes)
    hidden = sorted(set(hide_parts or []))
    ranked = sorted((p for p in inp.parts.values() if p.state is not None and (p.peak or 0) > 0),
                    key=lambda p: -(p.peak or 0.0))
    cache: dict = {}

    def state(i: int):
        if i not in cache:
            cache.clear()                                    # 큰 모델 — 상태는 하나만 들고 있는다
            cache[i] = mesh.read_state(inp.d3plot, i)
        return cache[i]

    # 배치는 스레드로 돈다 — Xvfb · VTK · DISPLAY 환경변수 · 상태 메모리는 프로세스 안에서 한 번에 하나만
    with _RENDER_LOCK:
        g = None
        if not ranked:
            notes.append("최대 순간을 정한 파트가 없어 스냅샷을 만들지 않았다")
        else:
            try:
                env = mesh.environment_parts(state(ranked[0].state)) if auto_floor else []
                if env:
                    notes.append(f"환경 파트(바닥 등)로 보고 숨겼다 — {env}")
                hidden = sorted(set(hidden) | set(env))
                g = next((p for p in ranked if p.pid not in hidden), None)
            except Exception as e:  # noqa: BLE001
                notes.append(f"상태 {ranked[0].state} 를 읽지 못했다 — {type(e).__name__}: {e}")
        targets = choose_targets(inp.parts, top, figure_parts, set(hidden)) if g else []

        jobs: list[_Job] = []
        if g is not None:
            jobs.append(_Job(g.state, "overview_peak", None, "iso", g.time,
                             f"전체 기기 — 가장 큰 von Mises 순간(파트 {g.pid} {g.name}, t = {inp.t_text(g.time)})"
                             + (f", 환경 파트 {hidden} 숨김." if hidden else "."), "overview", None))
            for pid in targets:
                pp = inp.parts.get(pid)
                if pp is not None and pp.state is not None:
                    st, t, why = pp.state, pp.time, f"최대 von Mises {_fmt(pp.peak)} {inp.unit_stress} 순간"
                else:
                    st, t, why = g.state, g.time, "응력 이력이 없어(셸 등) 전역 최대 순간"
                name = pp.name if pp else f"Part {pid}"
                for view in views:
                    vw = "최대점이 보이는 방향" if view == "peak" else f"{view} 시점"
                    jobs.append(_Job(st, f"part_{pid}_peak_{view}", [pid], view, t,
                                     f"파트 {pid} {name} — {why}(t = {inp.t_text(t)}), {vw}, 주변 파트 반투명"
                                     + (f", 안전율 {pp.sf:.3g}" if pp and pp.sf is not None else "") + ".", "part_peak", pid))

        def snapshot(j: _Job) -> dict:
            s = state(j.state)
            if j.t is not None and abs(s.time - j.t) > 1e-5 * abs(j.t) + 1e-12:
                notes.append(f"{j.fid}: 읽은 상태 {s.state_index} 의 시각 {s.time:.6g} 이 이력의 최대 시각 {j.t:.6g} 과 다르다")
            pp = inp.parts.get(j.pid) if j.pid is not None else None
            if j.pid is not None:
                head = f"Part {j.pid} {pp.name if pp else s.part_titles.get(j.pid, '')}".rstrip()
            else:
                head = "All parts"
            sc, fig = draw(
                s, j.targets, hidden, j.view, out, j.fid,
                lambda sc: [f"{head} — von Mises max {_fmt(sc.value_max)} {U}",
                            f"t = {inp.t_text(s.time)} · state {s.state_index} · {inp.run_folder} · "
                            f"{range_text(sc, clim, U)} · view {j.view}"
                            + (f" · hidden {', '.join(map(str, hidden))}" if hidden else "")],
                lambda sc: _part_info(inp, s, sc), unit_label=U, width=width, height=height, clim=clim,
                context_opacity=context_opacity)
            if pp is not None and pp.peak and j.state == pp.state:
                if abs(sc.value_max - pp.peak) > 1e-4 * abs(pp.peak):      # 같은 순간 · 같은 파트 — 해석기 최대와 같아야 한다
                    notes.append(f"{j.fid}: 그림의 최대 {sc.value_max:.6g} 이 해석기의 파트 최대 {pp.peak:.6g} 와 다르다")
            return {**fig, "kind": j.kind, "part_id": j.pid, "unit": inp.unit_stress, "caption": j.caption}

        done: dict[int, dict] = {}
        if jobs:
            try:
                with xvfb.display():
                    for k in sorted(range(len(jobs)), key=lambda k: jobs[k].state):   # 같은 상태끼리 이어서 — 읽기 한 번
                        try:
                            done[k] = snapshot(jobs[k])
                        except Exception as e:  # noqa: BLE001
                            notes.append(f"{jobs[k].fid} 실패 — {type(e).__name__}: {e}")
            except Exception as e:  # noqa: BLE001
                notes.append(f"화면 없는 렌더를 시작하지 못했다 — {type(e).__name__}: {e}")
        cache.clear()
        figs = [done[k] for k in range(len(jobs)) if k in done]

    # ── 차트 ──
    u = _UNITS.get(inp.unit_system)
    ts, tl = (u[2], "시간 (ms)") if u else (1.0, f"시간 ({DECK})")

    def scaled(xs):
        return [None if x is None else x * ts for x in (xs or [])]

    try:
        if inp.glstat:
            gs = inp.glstat
            ser = [{"name": n, "x": scaled(gs.get("t")), "y": gs.get(key) or []}
                   for n, key in (("운동에너지", "kinetic"), ("내부에너지", "internal"), ("hourglass", "hourglass"),
                                  ("전체", "total"))]
            charts.line_chart(out / "energy.svg", ser, "에너지 수지 (glstat)", tl,
                              f"에너지 ({u[3] if u else DECK})", mark_peaks=False)
            figs.append({"id": "energy", "kind": "chart", "files": {"svg": "energy.svg"},
                         "caption": "에너지 수지 — 운동 · 내부 · hourglass · 전체 에너지 시간 이력(glstat)."})
    except Exception as e:  # noqa: BLE001
        notes.append(f"에너지 차트 실패 — {type(e).__name__}: {e}")
    try:
        bars = sorted((p for p in inp.parts.values() if (p.peak or 0) > 0 and p.pid not in hidden),
                      key=lambda p: -(p.peak or 0.0))[:20]
        if bars:
            charts.bar_chart(out / "parts_peak.svg",
                             [{"label": f"{p.pid} {p.name}", "value": p.peak, "severity": p.severity,
                               "note": f"안전율 {p.sf:.3g}" if p.sf is not None else "안전율 없음"} for p in bars],
                             f"파트별 최대 von Mises (상위 {len(bars)}, 색 = deep 판정)", f"von Mises ({U})")
            figs.append({"id": "parts_peak", "kind": "chart", "files": {"svg": "parts_peak.svg"},
                         "caption": "파트별 최대 von Mises — 색은 deep 판정(최대 응력 ÷ 설계 한계 ≥ 1 CRITICAL, ≥ 0.8 "
                                    "WARNING, 한계 없음 UNKNOWN)" + (f", 환경 파트 {hidden} 제외." if hidden else ".")})
    except Exception as e:  # noqa: BLE001
        notes.append(f"파트 요약 차트 실패 — {type(e).__name__}: {e}")
    for pid in targets:
        pp = inp.parts.get(pid)
        if pp is None or not pp.hist_t:
            continue
        try:
            docs = [charts.line_svg([{"name": "파트 최대 von Mises", "x": scaled(pp.hist_t), "y": pp.hist_v}],
                                    f"파트 {pid} {pp.name} — von Mises 시간 이력", tl, f"von Mises ({U})")]
            if pp.acc_t:
                g0 = u[4] if u else None
                ys = [None if a is None else a / g0 for a in pp.acc_v] if g0 else pp.acc_v
                docs.append(charts.line_svg([{"name": "파트 평균 가속도 크기", "x": scaled(pp.acc_t), "y": ys,
                                              "color": "#2ca02c"}],
                                            f"파트 {pid} {pp.name} — 가속도 크기(파트 평균, 필터 없음)", tl,
                                            "가속도 (G)" if g0 else f"가속도 ({DECK})"))
            charts.stack(out / f"part_{pid}_history.svg", docs)
            figs.append({"id": f"part_{pid}_history", "kind": "chart", "part_id": pid,
                         "files": {"svg": f"part_{pid}_history.svg"},
                         "caption": f"파트 {pid} {pp.name} — 최대 von Mises 시간 이력(최대점 표시)"
                                    + (" · 파트 평균 가속도 크기." if pp.acc_t else ".")})
        except Exception as e:  # noqa: BLE001
            notes.append(f"파트 {pid} 이력 차트 실패 — {type(e).__name__}: {e}")

    try:
        from ..ontology.package import module_version
        ver = module_version()
    except Exception:  # noqa: BLE001
        ver = ""
    manifest = {
        "format": FORMAT, "format_version": FORMAT_VERSION,
        "producer": {"tool": "koo_deep_report.figures", "version": ver,
                     "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")},
        "run": {"run_folder": inp.run_folder, "d3plot": str(inp.d3plot)},
        "units": {"system": inp.unit_system, "stress": inp.unit_stress, "time": u[1] if u else DECK},
        "settings": {"top": top, "figure_parts": list(figure_parts or []), "hidden_parts": hidden,
                     "auto_floor": auto_floor, "context_opacity": context_opacity, "color_map": "jet",
                     "color_range": clim, "views": list(views), "size": [width, height]},
        "targets": targets, "figures": figs, "notes": notes,
    }
    write_gallery(out, manifest)
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return manifest


def write_gallery(out: Path, manifest: dict) -> None:
    """독립 갤러리(index.html) — 실패해도 그림은 그대로다(사유는 manifest notes)."""
    try:
        from .gallery import write_index
        write_index(out, manifest)
    except Exception as e:  # noqa: BLE001
        manifest.setdefault("notes", []).append(f"갤러리(index.html) 실패 — {type(e).__name__}: {e}")
