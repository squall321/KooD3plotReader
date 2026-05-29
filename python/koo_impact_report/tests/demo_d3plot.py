#!/usr/bin/env python3
"""Real-d3plot single-shot demo.

Generates a koo_impact_report HTML from one LS-DYNA d3plot — without the
multi-face DOE wrapper. Useful for validating the d3plot + binout integration.

Usage:
    python3 tests/demo_d3plot.py <d3plot_path> [--output report.html] [--name MyTest]

Example:
    python3 tests/demo_d3plot.py /data/ball_drop_test_v3/ex02_tet4_m027_baseline/d3plot \\
        --output /tmp/ex02_real.html --name Ex02_BallDrop

The d3plot's directory should contain a binout (binout0000 or binout) for full
energy data, and a keyword file (*.k) for impactor part auto-detection.
"""
import argparse
import sys
from pathlib import Path

# Allow running as script from anywhere
HERE = Path(__file__).resolve().parent
PKG_ROOT = HERE.parent
sys.path.insert(0, str(PKG_ROOT))
# Also expose koo_deep_report for binout/d3plot readers
DEEP_REPORT = PKG_ROOT.parent / "koo_deep_report"
if DEEP_REPORT.exists():
    sys.path.insert(0, str(DEEP_REPORT))

from koo_impact_report.loader import load_single_d3plot_report
from koo_impact_report.analyzer import analyze
from koo_impact_report.report.html_report import generate_html


def main() -> int:
    p = argparse.ArgumentParser(description="Real d3plot → single-shot impact report")
    p.add_argument("d3plot", type=Path, help="Path to d3plot file")
    p.add_argument("--output", "-o", type=Path, default=Path("real_d3plot_report.html"))
    p.add_argument("--name", default=None, help="Project name (default: parent dir name)")
    p.add_argument("--impactor", default=None,
                   help="Substring to match impactor part name. Default: "
                        "auto-detect by scanning *PART titles for 'impactor', "
                        "'ball', or 'punch' (case-insensitive).")
    p.add_argument("--face", default=None, choices=["F1", "F2", "F3", "F4", "F5", "F6"],
                   help="Force a face code (default: auto-detect from impactor initial velocity)")
    p.add_argument("--threads", type=int, default=2)
    args = p.parse_args()

    if not args.d3plot.exists():
        print(f"[demo] d3plot not found: {args.d3plot}", file=sys.stderr)
        return 1

    print(f"[demo] reading: {args.d3plot}")
    report = load_single_d3plot_report(
        d3plot_path=args.d3plot,
        project_name=args.name,
        impactor_part_name=args.impactor,
        face_code=args.face,
        threads=args.threads,
    )

    print(f"[demo] analyzing …")
    report = analyze(report)

    print(f"[demo] generating HTML …")
    html = generate_html(report)
    args.output.write_text(html, encoding="utf-8")
    size_kb = args.output.stat().st_size / 1024
    print(f"[demo] wrote {args.output} ({size_kb:.0f} KB)")

    if report.impactor_trajectories:
        traj = next(iter(report.impactor_trajectories.values()))
        print()
        print("=== Trajectory Summary ===")
        print(f"  n_states         : {len(traj.times)}")
        if traj.times:
            print(f"  duration         : {traj.times[0]:.6f} → {traj.times[-1]:.6f} s")
            print(f"  initial KE       : {traj.initial_ke:.3e}")
            print(f"  final KE         : {traj.final_ke:.3e}")
            print(f"  KE retention     : {traj.ke_retention:.4f}")
            print(f"  max penetration  : {traj.max_penetration_depth:.3e}")
            print(f"  contact steps    : {sum(traj.contact_engaged)}/{len(traj.contact_engaged)}")
            print(f"  behavior class   : {traj.behavior_class}")
            print(f"  rebound speed    : {traj.rebound_speed:.3e}")
        else:
            print("  (trajectory empty — impactor part not identified or no motion data)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
