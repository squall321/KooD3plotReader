# 캠페인(sphere 전각도) 그림 — 파트별 최악 방향 런의 최대 순간 스냅샷 · 최악값 요약 차트 · manifest
"""sphere report.json 의 런 × 파트 최대 응력에서 파트마다 **최악 방향 런**을 고르고, 그 런의 최대 순간을 deep 꾸러미와
같은 엔진 · 같은 규칙(타겟 맨 위 · 주변 반투명 · 바닥 숨김 · 파트 모든 요소 최대)으로 그린다(계획 §2-4).

- 대상 — `figure_parts` 가 있으면 그것, 없으면 상위 5개: 안전율이 있으면 낮은 순, 없으면 최악 최대 응력 순.
  안전율은 report.json 의 part_yield_limits 중 von Mises 한계(가장 낮은 것) ÷ 최악 최대, 판정은 sphere 규칙
  (< 1 CRITICAL, < 1.5 WARNING) — sphere 보고서와 같은 판정이 되게.
- 상태 번호 — 런의 `stress/part_<PID>_von_mises.csv` 는 상태마다 한 줄이다. 최대값이 나온 **줄 번호**가 상태 번호다
  (CSV 시각은 소수 6자리라 상태 간격 1 µs 와 겹쳐 시각으로 찾으면 틀린다). 런마다 수십 MB 인 analysis_result.json 은
  열지 않는다. 읽은 상태의 파트 최대가 CSV 최대와 다르면 notes 에 남긴다.
- 출력 — report.json → `<test_dir>/figures/`, report_<그룹>.json → `<test_dir>/figures_<그룹>/`.
"""
from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import charts, pack

_GROUP_PREFIX = "report_"          # report_<그룹>.json — 그룹이 여럿인 캠페인


@dataclass
class Worst:
    pid: int
    name: str
    peak: float                        # 캠페인 전체에서 이 파트의 최악 최대 von Mises(덱 단위)
    run_folder: str
    angle: dict = field(default_factory=dict)
    time: float | None = None
    n_runs: int = 0
    sf: float | None = None
    severity: str = "UNKNOWN"

    @property
    def angle_text(self) -> str:
        a = self.angle or {}
        rpy = " ".join(f"{k} {pack._fmt(a.get(k))}°" for k in ("roll", "pitch", "yaw") if pack._num(a.get(k)) is not None)
        return (str(a.get("name") or self.run_folder) + (f" ({rpy})" if rpy else "")).strip()


def worst_runs(report: dict) -> dict[int, Worst]:
    """파트마다 최대 응력이 가장 큰 런. 값이 없는 런 · 파트는 건너뛴다(0 으로 치지 않는다)."""
    names = {}
    for k, v in (report.get("parts") or {}).items():
        try:
            names[int(k)] = (v or {}).get("part_name") or (v or {}).get("name") or f"Part {k}"
        except (TypeError, ValueError):
            continue
    best: dict[int, Worst] = {}
    count: dict[int, int] = {}
    for r in report.get("results_summary") or report.get("results") or []:
        folder = str((r or {}).get("run_folder") or "")
        for pid_s, pd in ((r or {}).get("parts") or {}).items():
            v = pack._num((pd or {}).get("peak_stress"))
            try:
                pid = int(pid_s)
            except (TypeError, ValueError):
                continue
            if v is None or not folder:
                continue
            count[pid] = count.get(pid, 0) + 1
            if pid not in best or v > best[pid].peak:
                best[pid] = Worst(pid, names.get(pid, f"Part {pid}"), v, folder, (r or {}).get("angle") or {},
                                  pack._num((pd or {}).get("time_of_peak_stress")))
    for pid, w in best.items():
        w.n_runs = count[pid]
    for pid_s, lims in (report.get("part_yield_limits") or {}).items():
        try:
            w = best.get(int(pid_s))
        except (TypeError, ValueError):
            continue
        vals = [pack._num((x or {}).get("value")) for x in lims or []
                if str((x or {}).get("criterion") or "von_mises") == "von_mises"]
        vals = [v for v in vals if v is not None and v > 0]
        if w is not None and vals and w.peak > 0:
            w.sf = min(vals) / w.peak
            w.severity = "CRITICAL" if w.sf < 1.0 else "WARNING" if w.sf < 1.5 else "OK"
    return best


def choose(worst: dict[int, Worst], top: int, figure_parts: list[int] | None, exclude: set[int]) -> list[int]:
    if figure_parts:
        return [p for p in dict.fromkeys(figure_parts) if p in worst and p not in exclude]
    cand = [w for w in worst.values() if w.pid not in exclude and w.peak > 0]
    cand.sort(key=lambda w: (w.sf is None, w.sf if w.sf is not None else 0.0, -w.peak))
    return [w.pid for w in cand[:max(0, top)]]


def run_files(test_dir: Path, folder: str) -> tuple[Path | None, Path | None]:
    """(analysis_results 의 런 폴더, d3plot). 그룹 배치(analysis_results/<그룹>/<런>) · Output 하위도 찾는다."""
    ar = next((p for p in [test_dir / "analysis_results" / folder,
                           *sorted(test_dir.glob(f"analysis_results/*/{folder}")),
                           *sorted(test_dir.glob(f".analysis_results_original/*/{folder}"))]
               if (p / "stress").is_dir()), None)
    d3 = next((p for p in [test_dir / "output" / folder / "d3plot", test_dir / "output" / folder / "Output" / "d3plot",
                           *sorted(test_dir.glob(f"output/*/{folder}/d3plot"))] if p.is_file()), None)
    return ar, d3


def peak_row(csv_path: Path) -> tuple[int, float, float] | None:
    """(상태 번호 = 최대값 줄 번호, 그 줄 시각, 최대값). 첫 최대를 쓴다."""
    best = None
    with open(csv_path, newline="", encoding="utf-8") as f:
        rd = csv.reader(f)
        head = next(rd, None) or []
        try:
            it, iv = head.index("Time"), next(i for i, h in enumerate(head) if h.startswith("Max_"))
        except (ValueError, StopIteration):
            return None
        for k, row in enumerate(rd):
            try:
                v = float(row[iv])
            except (ValueError, IndexError):
                continue
            if math.isfinite(v) and (best is None or v > best[2]):
                best = (k, float(row[it]), v)
    return best


def build(report_path: str | Path, *, test_dir: str | Path | None = None, out_dir: str | Path | None = None,
          top: int = 5, figure_parts: list[int] | None = None, hide_parts: list[int] | None = None,
          auto_floor: bool = True, context_opacity: float = 0.15, views: tuple[str, ...] = ("iso", "peak"),
          width: int = 1600, height: int = 1100, clim: str | float = "p99.5") -> dict:
    """그림을 만들고 manifest(dict)를 돌려준다. 출력 폴더의 manifest.json 도 쓴다."""
    from . import mesh, xvfb

    rp = Path(report_path)
    report = json.loads(rp.read_text(encoding="utf-8"))
    td = Path(test_dir or report.get("test_dir") or rp.parent)
    group = rp.stem[len(_GROUP_PREFIX):] if rp.stem.startswith(_GROUP_PREFIX) else ""
    out = Path(out_dir) if out_dir else td / (f"figures_{group}" if group else "figures")
    out.mkdir(parents=True, exist_ok=True)
    for f in out.iterdir():
        if f.is_file() and pack._OURS.match(f.name):
            f.unlink()
    notes: list[str] = []
    worst = worst_runs(report)
    hidden = sorted(set(hide_parts or []))
    targets = choose(worst, top, figure_parts, set(hidden))
    if figure_parts:
        miss = [p for p in figure_parts if p not in worst]
        if miss:
            notes.append(f"report.json 에 응력 값이 없는 파트는 뺐다 — {miss}")
    gw = max((w for w in worst.values() if w.pid not in hidden and w.peak > 0), key=lambda w: w.peak, default=None)

    # 단위 — 첫 대상 런의 덱 밀도로 판정(deep 과 같은 규칙). report.json 이 단위를 실으면 그 라벨
    us = report.get("unit_system") if isinstance(report.get("unit_system"), dict) else {}
    first_d3 = next((run_files(td, worst[p].run_folder)[1] for p in targets), None)
    uid, label, note = pack._units([], pack._keyword(first_d3) if first_d3 else None, None)
    if us.get("id") in pack._UNITS:
        uid, label = us["id"], (report.get("unit_labels") or {}).get("stress") or pack._UNITS[us["id"]][0]
    if note and not us.get("id"):
        notes.append(note)
    U = label if label.isascii() else "deck units"
    tinp = pack.RunInputs(Path(first_d3 or "."), "", {}, uid, label)

    jobs = []                                   # (pid · None=전체, 런 폴더, 시점, 파일 id)
    if gw is not None:
        jobs.append((None, gw, "iso", "overview_worst"))
    for pid in targets:
        for view in views:
            jobs.append((pid, worst[pid], view, f"part_{pid}_worst_{view}"))

    figs: list[dict] = []
    with pack._RENDER_LOCK:
        try:
            with xvfb.display():
                cur = {}
                for pid, w, view, fid in jobs:
                    try:
                        ar, d3 = run_files(td, w.run_folder)
                        if ar is None or d3 is None:
                            raise FileNotFoundError(f"런 {w.run_folder} 의 analysis_results/stress · d3plot 을 찾지 못했다")
                        pk = peak_row(ar / "stress" / f"part_{w.pid}_von_mises.csv")
                        if pk is None:
                            raise ValueError(f"part_{w.pid}_von_mises.csv 에서 최대 줄을 찾지 못했다")
                        st, t_row, v_row = pk
                        key = (str(d3), st)
                        if cur.get("key") != key:
                            cur.clear()                  # 큰 모델 — 상태는 하나만 들고 있는다
                            s = mesh.read_state(d3, st)
                            env = mesh.environment_parts(s) if auto_floor else []
                            cur.update(key=key, s=s, hid=sorted(set(hidden) | set(env)))
                        s, hid = cur["s"], cur["hid"]
                        m = s.part_max.get(w.pid)
                        match = m is not None and abs(m - v_row) <= max(1e-4 * abs(v_row), 1e-6)
                        if not match:
                            notes.append(f"{fid}: 읽은 상태 {st} 의 파트 {w.pid} 최대 {pack._fmt(m)} 이 CSV 최대 "
                                         f"{v_row:.6g} 와 다르다 — 옛 분석기 산출물일 수 있다(다시 분석 권장)")
                        head = (f"Part {pid} {w.name}" if pid is not None else f"All parts @ worst of Part {w.pid} {w.name}")
                        info_peak = {p: worst[p] for p in worst}

                        def info(sc, s=s):
                            d = {}
                            for q in sorted(set(s.face_part[sc.target_mask | sc.context_mask].tolist())):
                                wq = info_peak.get(q)
                                mq = s.part_max.get(q)
                                d[q] = {"name": wq.name if wq else s.part_titles.get(q, f"Part {q}"),
                                        "value": round(mq, 4) if mq is not None and math.isfinite(mq) else None,
                                        "peak": round(wq.peak, 4) if wq else None,
                                        "sf": round(wq.sf, 3) if wq and wq.sf is not None else None}
                            return d

                        sc, fig = pack.draw(
                            s, [pid] if pid is not None else None, hid, view, out, fid,
                            lambda sc: [f"{head} — worst direction {w.angle_text} — von Mises max "
                                        f"{pack._fmt(sc.value_max)} {U}",
                                        f"{w.run_folder} · t = {tinp.t_text(s.time)} · state {s.state_index} · "
                                        f"{pack.range_text(sc, clim, U)} · view {view}"
                                        + (f" · hidden {', '.join(map(str, hid))}" if hid else "")],
                            info, unit_label=U, width=width, height=height, clim=clim,
                            context_opacity=context_opacity)
                        what = (f"파트 {pid} {w.name} — 전 방향 {w.n_runs}개 런 중 최악 방향 {w.angle_text} 의 최대 순간"
                                if pid is not None else
                                f"전체 기기 — 캠페인 최악(파트 {w.pid} {w.name}, {w.angle_text}) 순간")
                        warn = ("" if match else f" ⚠ 분석 결과(CSV · report.json)의 최대 {v_row:.4g} 와 이 상태의 실제 "
                                                 f"최대 {pack._fmt(m)} 가 다르다 — 옛 분석기 산출물일 수 있어 다시 분석을 권한다.")
                        figs.append({**fig, "kind": "campaign_overview" if pid is None else "campaign_worst",
                                     "part_id": pid, "run_folder": w.run_folder, "angle": w.angle, "unit": label,
                                     "check": {"part_id": w.pid, "csv_max": v_row, "d3plot_max": pack._num(m),
                                               "match": bool(match)},
                                     "caption": what + (f", 안전율 {w.sf:.3g}" if pid is not None and w.sf is not None
                                                        else "") + (f", {view} 시점" if pid is not None else "")
                                     + (f", 환경 파트 {hid} 숨김." if hid else ".") + warn})
                    except Exception as e:  # noqa: BLE001
                        notes.append(f"{fid} 실패 — {type(e).__name__}: {e}")
                cur.clear()
        except Exception as e:  # noqa: BLE001
            notes.append(f"화면 없는 렌더를 시작하지 못했다 — {type(e).__name__}: {e}")

    try:
        bars = sorted((w for w in worst.values() if w.pid not in hidden and w.peak > 0), key=lambda w: -w.peak)[:20]
        if bars:
            charts.bar_chart(out / "parts_worst.svg",
                             [{"label": f"{w.pid} {w.name}", "value": w.peak, "severity": w.severity,
                               "note": f"최악 방향 {w.angle_text}"
                                       + (f" · 안전율 {w.sf:.3g}" if w.sf is not None else "")} for w in bars],
                             f"파트별 최악 방향 최대 von Mises (상위 {len(bars)}, 런 {len(report.get('results_summary') or report.get('results') or [])}개)",
                             f"von Mises ({U})")
            figs.append({"id": "parts_worst", "kind": "chart", "files": {"svg": "parts_worst.svg"},
                         "caption": "파트별 최악 방향의 최대 von Mises — 막대에 마우스를 올리면 최악 방향 · 안전율, 색은 "
                                    "sphere 판정(안전율 < 1 CRITICAL, < 1.5 WARNING, 한계 없음 UNKNOWN)."})
    except Exception as e:  # noqa: BLE001
        notes.append(f"요약 차트 실패 — {type(e).__name__}: {e}")

    try:
        from ..ontology.package import module_version
        ver = module_version()
    except Exception:  # noqa: BLE001
        ver = ""
    manifest = {
        "format": pack.FORMAT, "format_version": pack.FORMAT_VERSION, "scope": "campaign",
        "producer": {"tool": "koo_deep_report.figures.campaign", "version": ver,
                     "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")},
        "campaign": {"test_dir": str(td), "report": rp.name, "group": group or None,
                     "runs": len(report.get("results_summary") or report.get("results") or [])},
        "units": {"system": uid, "stress": label, "time": pack._UNITS[uid][1] if uid in pack._UNITS else pack.DECK},
        "settings": {"top": top, "figure_parts": list(figure_parts or []), "hidden_parts": hidden,
                     "auto_floor": auto_floor, "context_opacity": context_opacity, "color_map": "jet",
                     "color_range": clim, "views": list(views), "size": [width, height]},
        "targets": targets,
        "worst": {str(p): {"name": w.name, "peak": w.peak, "run_folder": w.run_folder, "angle": w.angle,
                           "runs": w.n_runs, "sf": w.sf, "severity": w.severity} for p, w in sorted(worst.items())},
        "figures": figs, "notes": notes,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return manifest
