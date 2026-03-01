"""CLI entry point: python -m koo_report"""
import argparse
import sys
import time
from pathlib import Path

from .analyzer import analyze
from .report.html_report import generate_html
from .report.json_report import save_json


def main():
    parser = argparse.ArgumentParser(
        prog="koo_report",
        description="KooReport - Full-angle drop simulation analysis report",
    )
    parser.add_argument(
        "--test-dir", required=True,
        help="Path to test directory (e.g., /data/Tests/Test_001_Full26_1Step)",
    )
    parser.add_argument(
        "--output", "-o", default=None,
        help="Output HTML file path (default: <test-dir>/report.html)",
    )
    parser.add_argument(
        "--json", default=None,
        help="Output JSON file path (default: alongside HTML)",
    )
    parser.add_argument(
        "--terminal-only", action="store_true",
        help="Print terminal report only, no file output",
    )
    parser.add_argument(
        "--format", nargs="+", default=["html", "terminal"],
        choices=["html", "json", "terminal"],
        help="Output formats (default: html terminal)",
    )
    parser.add_argument(
        "--yield-stress", type=float, default=0.0,
        help="Material yield stress (MPa) for safety factor calculation",
    )
    parser.add_argument(
        "--ts-points", type=int, default=0,
        help="Time series points per chart (0=auto: 100/30/20 based on N results)",
    )
    args = parser.parse_args()

    test_dir = Path(args.test_dir)
    if not test_dir.exists():
        print(f"Error: {test_dir} does not exist", file=sys.stderr)
        sys.exit(1)

    if not (test_dir / "analysis_results").exists():
        print(f"Error: No analysis_results in {test_dir}", file=sys.stderr)
        print("Run unified_analyzer --recursive first.", file=sys.stderr)
        sys.exit(1)

    print(f"Loading data from {test_dir}...")
    t0 = time.time()
    report = analyze(test_dir, yield_stress=args.yield_stress)
    t_load = time.time() - t0
    print(f"Loaded {report.successful_runs} results in {t_load:.1f}s")

    formats = ["terminal"] if args.terminal_only else args.format

    if "terminal" in formats:
        try:
            from .report.terminal import print_report
            print_report(report)
        except ImportError:
            print("Warning: rich not installed, skipping terminal output", file=sys.stderr)

    if "html" in formats:
        html_path = args.output or str(test_dir / "report.html")
        print(f"Generating HTML report: {html_path}")
        t0 = time.time()
        generate_html(report, html_path, ts_points=args.ts_points, test_dir=str(test_dir.resolve()))
        print(f"HTML report saved in {time.time()-t0:.1f}s ({Path(html_path).stat().st_size/1024:.0f} KB)")

    if "json" in formats:
        json_path = args.json or str(test_dir / "report.json")
        save_json(report, json_path)
        print(f"JSON report saved: {json_path}")

    print("Done.")


if __name__ == "__main__":
    main()
