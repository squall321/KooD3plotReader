#!/usr/bin/env python3
"""Multi-position partial-impact DOE demo.

Loads a KooDWITestSetRunner output tree (e.g. /data/koopark/Test_Impact_A),
runs unified_analyzer on every Run_*/Output/d3plot in parallel, and
generates the koo_impact_report HTML.

Usage:
    python3 tests/demo_doe.py <test_dir> [--output report.html] \\
        [--threads 2] [--parallel 4]

Example:
    python3 tests/demo_doe.py /data/koopark/Test_Impact_A \\
        --output /tmp/test_impact_A.html --parallel 6 --threads 2
"""
from __future__ import annotations
import argparse
import pickle
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_ROOT = HERE.parent
sys.path.insert(0, str(PKG_ROOT))
DEEP_REPORT = PKG_ROOT.parent / "koo_deep_report"
if DEEP_REPORT.exists():
    sys.path.insert(0, str(DEEP_REPORT))

from koo_impact_report.loader import load_partial_impact_doe_report
from koo_impact_report.analyzer import analyze
from koo_impact_report.report.html_report import generate_html


def main() -> int:
    p = argparse.ArgumentParser(description="Multi-position partial-impact DOE → HTML report")
    p.add_argument("test_dir", type=Path, help="Project root (contains scenario.json + output/Run_*/)")
    p.add_argument("--output", "-o", type=Path, default=Path("doe_report.html"))
    p.add_argument("--threads", type=int, default=2,
                   help="unified_analyzer threads per run")
    p.add_argument("--parallel", type=int, default=4,
                   help="number of runs processed concurrently")
    p.add_argument("--impactor", default=None,
                   help="Optional impactor part name substring (default: auto-detect "
                        "via *INITIAL_VELOCITY_* card)")
    p.add_argument("--cache", type=Path, default=None,
                   help="Pickle path. If the file exists, the ImpactReport is loaded from "
                        "it (skipping unified_analyzer); otherwise the new report is loaded "
                        "and written there for next time. Use this to iterate on the HTML "
                        "template without re-running the 16-min DOE.")
    args = p.parse_args()

    if not args.test_dir.exists():
        print(f"[demo] test_dir not found: {args.test_dir}", file=sys.stderr)
        return 1

    t0 = time.time()
    report = None
    if args.cache and args.cache.exists():
        print(f"[demo] loading ImpactReport from cache {args.cache}")
        try:
            with open(args.cache, "rb") as f:
                report = pickle.load(f)
            print(f"[demo] cache hit in {time.time()-t0:.1f}s")
        except Exception as e:
            print(f"[demo] cache load failed ({e!r}) — re-loading DOE")
            report = None

    if report is None:
        print(f"[demo] loading DOE from {args.test_dir}")
        report = load_partial_impact_doe_report(
            test_dir=args.test_dir,
            impactor_part_name=args.impactor,
            threads_per_run=args.threads,
            parallel_runs=args.parallel,
        )
        if args.cache:
            try:
                args.cache.parent.mkdir(parents=True, exist_ok=True)
                with open(args.cache, "wb") as f:
                    pickle.dump(report, f, protocol=pickle.HIGHEST_PROTOCOL)
                print(f"[demo] saved cache → {args.cache} ({args.cache.stat().st_size/1024:.0f} KB)")
            except Exception as e:
                print(f"[demo] cache save failed ({e!r}) — continuing")
    t_load = time.time() - t0
    face_code = report.faces[0].code if report.faces else ""
    print(f"[demo] loaded in {t_load:.1f}s — {len(report.positions_by_face.get(face_code, []))} "
          f"positions × {len(report.parts)} parts = {len(report.results)} PairResults")

    print(f"[demo] analyzing …")
    report = analyze(report)

    print(f"[demo] generating HTML …")
    html = generate_html(report)
    args.output.write_text(html, encoding="utf-8")
    print(f"[demo] wrote {args.output} ({args.output.stat().st_size/1024:.0f} KB)")

    # Brief on-screen summary
    print()
    print("=== DOE Summary ===")
    print(f"  project           : {report.project_name}")
    print(f"  impactor          : PID={report.impactor.part_id} "
          f"ρ={report.impactor.density:.3e} v₀={report.impactor.initial_velocity}")
    print(f"  face              : {face_code if face_code else '(none)'}")
    print(f"  positions         : {len(report.positions_by_face.get(face_code, []))}")
    print(f"  parts             : {len(report.parts)}")
    print(f"  total pair rows   : {len(report.results)}")
    print(f"  unit system       : {report.sim_params.get('units', '(unknown)')}")
    grid = report.sim_params.get("grid")
    if grid:
        print(f"  scenario grid     : {grid['nx']}×{grid['ny']} in bbox={grid['bbox']}")
    if report.findings:
        print(f"  findings          : {len(report.findings)} "
              f"({sum(1 for f in report.findings if str(f.severity).endswith('CRITICAL'))} critical)")
    print(f"  total elapsed     : {time.time()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
